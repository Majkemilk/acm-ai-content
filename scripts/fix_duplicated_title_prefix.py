#!/usr/bin/env python3
"""
Fix duplicated title prefix in content/articles frontmatter (title + primary_keyword).
Patterns: "How to how to ", "Guide to how to ", "Best how to ", "Best best " -> single prefix.

Run from project root: python scripts/fix_duplicated_title_prefix.py [--dry-run] [--confirm]
Without --confirm only prints what would be changed (dry-run).
"""
import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"

# (pattern, replacement) – title must start with pattern (case-sensitive as in content)
DUPLICATE_PREFIX_FIXES = [
    ("How to how to ", "How to "),
    ("Guide to how to ", "Guide to "),
    ("Best how to ", "Best "),
    ("Best best ", "Best "),
]


def _parse_md_frontmatter(content: str) -> tuple[dict[str, str] | None, int, int]:
    """Return (dict of key->value, start_offset, end_offset) or (None, 0, 0)."""
    if not content.startswith("---"):
        return None, 0, 0
    end_marker = "\n---"
    end = content.find(end_marker, 3)
    if end == -1:
        return None, 0, 0
    block = content[3:end].strip()
    data: dict[str, str] = {}
    for line in block.split("\n"):
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1].replace('\\"', '"')
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        data[key] = raw
    return data, 0, end + len(end_marker)


def _parse_html_frontmatter(content: str) -> tuple[dict[str, str] | None, int, int]:
    """Return (dict, start_offset, end_offset) for first <!-- ... --> block or (None, 0, 0)."""
    m = re.match(r"\s*<!--\s*(.*?)\s*-->", content, re.DOTALL)
    if not m:
        return None, 0, 0
    block = m.group(1).strip()
    data: dict[str, str] = {}
    for line in block.split("\n"):
        m2 = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if not m2:
            continue
        key, raw = m2.group(1), m2.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1].replace('\\"', '"')
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        data[key] = raw
    return data, m.start(), m.end()


def _fix_title_and_keyword(title: str) -> tuple[str, str] | None:
    """If title has duplicated prefix, return (new_title, new_primary_keyword); else None."""
    if not title:
        return None
    for pattern, replacement in DUPLICATE_PREFIX_FIXES:
        if title.startswith(pattern):
            new_title = replacement + title[len(pattern) :]
            new_keyword = new_title.lower()
            return new_title, new_keyword
    return None


def _replace_key_in_block(block: str, key: str, new_value: str) -> str:
    """Replace first key: "value" or key: 'value' in block. Value is single-line in practice."""
    escaped = new_value.replace("\\", "\\\\").replace('"', '\\"')
    # Match key: "value" or key: 'value' (value to next quote)
    pattern = re.compile(
        r"^(\s*" + re.escape(key) + r"\s*:\s*)[\"']([^\"']*)[\"']",
        re.MULTILINE,
    )
    new_block = pattern.sub(r'\1"' + escaped + '"', block, count=1)
    return new_block


def process_file(path: Path, dry_run: bool) -> bool:
    """Fix title/primary_keyword in one file. Return True if changed (or would change)."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    is_html = path.suffix.lower() == ".html"
    if is_html:
        meta, fm_start, fm_end = _parse_html_frontmatter(content)
    else:
        meta, _, fm_end = _parse_md_frontmatter(content)
        fm_start = 0
    if not meta:
        return False
    title = (meta.get("title") or "").strip()
    result = _fix_title_and_keyword(title)
    if not result:
        return False
    new_title, new_keyword = result
    if dry_run:
        print(f"  {path.name}")
        print(f"    title: {title!r} -> {new_title!r}")
        print(f"    primary_keyword: -> {new_keyword!r}")
        return True
    # Replace title and primary_keyword in frontmatter block
    block = content[fm_start:fm_end]
    block = _replace_key_in_block(block, "title", new_title)
    block = _replace_key_in_block(block, "primary_keyword", new_keyword)
    content = content[:fm_start] + block + content[fm_end:]
    path.write_text(content, encoding="utf-8")
    print(f"  Updated: {path.name}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Fix duplicated title prefix in content/articles (title + primary_keyword).")
    ap.add_argument("--dry-run", action="store_true", help="Only print what would be changed")
    ap.add_argument("--confirm", action="store_true", help="Apply changes to files")
    args = ap.parse_args()
    dry_run = not args.confirm
    if not args.confirm:
        print("Dry-run (use --confirm to apply changes):")
    if not ARTICLES_DIR.exists():
        print(f"Articles dir not found: {ARTICLES_DIR}", file=sys.stderr)
        sys.exit(1)
    count = 0
    for path in sorted(ARTICLES_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".md", ".html"):
            continue
        if process_file(path, dry_run):
            count += 1
    if count == 0:
        print("No files with duplicated title prefix found.")
    else:
        print(f"\nTotal: {count} file(s) {'would be updated' if dry_run else 'updated'}.")
    if dry_run and count:
        print("Run with --confirm to apply.")


if __name__ == "__main__":
    main()
