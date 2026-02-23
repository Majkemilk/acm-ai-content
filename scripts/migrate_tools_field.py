#!/usr/bin/env python3
"""
One-time migration: merge primary_tool, secondary_tool, tools_mentioned into a single 'tools' field.
Applies to:
  1. All .md articles in content/articles/
  2. content/queue.yaml

Run: python scripts/migrate_tools_field.py [--dry-run]
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
QUEUE_PATH = PROJECT_ROOT / "content" / "queue.yaml"

FM_KEY_RE = re.compile(r'^([a-zA-Z0-9_]+):\s*(.*)$')
OLD_KEYS = {"primary_tool", "secondary_tool", "tools_mentioned"}


def _unquote(val: str) -> str:
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def _merge_tools(primary: str, secondary: str, mentioned: str) -> str:
    """Merge old fields into a single comma-separated tools string (deduplicated, order-preserving)."""
    names: list[str] = []
    for raw in (mentioned, primary, secondary):
        for n in raw.split(","):
            n = n.strip()
            if n and n not in names and not n.startswith("{{"):
                names.append(n)
    return ", ".join(names)


def migrate_article(path: Path, dry_run: bool) -> bool:
    """Migrate one .md article. Returns True if changed."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False

    fm_block = text[3:end]
    after_fm = text[end:]

    lines = fm_block.split("\n")
    new_lines: list[str] = []
    primary = secondary = mentioned = ""
    has_old = False
    has_tools = False

    for line in lines:
        m = FM_KEY_RE.match(line.strip())
        if m:
            key = m.group(1)
            val = _unquote(m.group(2))
            if key == "primary_tool":
                primary = val
                has_old = True
                continue
            if key == "secondary_tool":
                secondary = val
                has_old = True
                continue
            if key == "tools_mentioned":
                mentioned = val
                has_old = True
                continue
            if key == "tools":
                has_tools = True
        new_lines.append(line)

    if not has_old:
        return False

    merged = _merge_tools(primary, secondary, mentioned)

    if has_tools:
        final_lines = []
        for line in new_lines:
            m = FM_KEY_RE.match(line.strip())
            if m and m.group(1) == "tools" and not _unquote(m.group(2)):
                indent = line[:len(line) - len(line.lstrip())]
                final_lines.append(f'{indent}tools: "{merged}"')
            else:
                final_lines.append(line)
        new_lines = final_lines
    else:
        insert_idx = len(new_lines)
        for i, line in enumerate(new_lines):
            m = FM_KEY_RE.match(line.strip())
            if m and m.group(1) in ("last_updated", "status"):
                insert_idx = i
                break
        new_lines.insert(insert_idx, f'tools: "{merged}"')

    new_text = "---" + "\n".join(new_lines) + after_fm
    if new_text == text:
        return False

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True


def migrate_queue(path: Path, dry_run: bool) -> int:
    """Migrate queue.yaml. Returns number of entries changed."""
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    new_lines: list[str] = []
    changed = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("- ") or (i > 0 and not stripped.startswith("- ") and ":" in stripped and new_lines):
            block_start = i
            entry_lines: list[str] = [line]
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("- ") or s == "":
                    break
                entry_lines.append(lines[i])
                i += 1

            primary = secondary = mentioned = ""
            has_old = False
            has_tools_key = False
            kept: list[str] = []

            for el in entry_lines:
                m = FM_KEY_RE.match(el.strip())
                if m:
                    key = m.group(1)
                    val = _unquote(m.group(2))
                    if key == "primary_tool":
                        primary = val
                        has_old = True
                        continue
                    if key == "secondary_tool":
                        secondary = val
                        has_old = True
                        continue
                    if key == "tools_mentioned":
                        mentioned = val
                        has_old = True
                        continue
                    if key == "tools":
                        has_tools_key = True
                kept.append(el)

            if has_old:
                merged = _merge_tools(primary, secondary, mentioned)
                if has_tools_key:
                    final_kept = []
                    for el in kept:
                        m = FM_KEY_RE.match(el.strip())
                        if m and m.group(1) == "tools" and not _unquote(m.group(2)):
                            indent = el[:len(el) - len(el.lstrip())]
                            final_kept.append(f'{indent}tools: {merged}')
                        else:
                            final_kept.append(el)
                    kept = final_kept
                else:
                    insert_idx = len(kept)
                    for j, el in enumerate(kept):
                        m = FM_KEY_RE.match(el.strip())
                        if m and m.group(1) in ("status", "last_updated"):
                            insert_idx = j
                            break
                    indent = "  "
                    kept.insert(insert_idx, f'{indent}tools: {merged}')
                changed += 1
            new_lines.extend(kept)
        else:
            new_lines.append(line)
            i += 1

    if changed > 0 and not dry_run:
        path.write_text("\n".join(new_lines), encoding="utf-8")
    return changed


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    art_count = 0
    if ARTICLES_DIR.exists():
        for path in sorted(ARTICLES_DIR.glob("*.md")):
            if migrate_article(path, dry_run):
                art_count += 1
                print(f"  {'Would migrate' if dry_run else 'Migrated'}: {path.name}")

    q_count = migrate_queue(QUEUE_PATH, dry_run)

    print(f"\nArticles migrated: {art_count}")
    print(f"Queue entries migrated: {q_count}")
    if dry_run:
        print("(dry-run mode — no files modified)")


if __name__ == "__main__":
    main()
