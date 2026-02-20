#!/usr/bin/env python3
"""
Generate content/queue.yaml from content/use_cases.yaml (and optionally affiliate_tools.yaml).
Creates one queue entry per use case. Number of entries = number of use cases in use_cases.yaml.
Uses only Python standard library. Line-based YAML parsing (no external deps).
"""

import json
import re
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = PROJECT_ROOT / "content"
AFFILIATE_TOOLS_PATH = CONTENT_DIR / "affiliate_tools.yaml"
USE_CASES_PATH = CONTENT_DIR / "use_cases.yaml"
QUEUE_PATH = CONTENT_DIR / "queue.yaml"

ALLOWED_CONTENT_TYPES = ["how-to", "guide", "best", "comparison", "review"]
DEFAULT_CONTENT_TYPE = "guide"

# Title action prefix by content_type: "{action} {problem} with {tool_name}"
CONTENT_TYPE_ACTION = {
    "how-to": "How to",
    "guide": "Guide to",
    "best": "Best",
    "comparison": "Comparison of",
}


def _strip_comments(text: str) -> str:
    """Remove lines that are entirely comments (optional # at start of line after strip)."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_quoted_value(val: str) -> str:
    """Unquote a YAML value if quoted."""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1].replace('\\"', '"')
    return val


def load_yaml_list(path: Path, list_key: str) -> list[dict]:
    """
    Load a YAML file with a single top-level key whose value is a list of objects.
    Simple line-based parser (no external libs). Supports:
    - use_cases: [ { problem: ..., suggested_content_type: ..., category_slug: ... }, ... ]
    - tools: [ { name: ..., category: ..., affiliate_link: ... }, ... ]
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    text = _strip_comments(text)
    key_pattern = re.compile(rf"^{re.escape(list_key)}\s*:\s*$", re.MULTILINE)
    m = key_pattern.search(text)
    if not m:
        return []
    start = m.end()
    rest = text[start:]
    next_top = re.search(r"^\w+\s*:\s*", rest, re.MULTILINE)
    block = rest[: next_top.start()] if next_top else rest
    block = block.strip()
    if not block:
        return []
    items = []
    current: dict[str, str] = {}
    for line in block.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                items.append(current)
                current = {}
            continue
        if stripped == "-" or re.match(r"^-\s+", stripped):
            if current:
                items.append(current)
            current = {}
            inline = re.match(r"^-\s+(.+)$", stripped)
            if inline:
                part = inline.group(1).strip()
                kv = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(.*)$", part)
                if kv:
                    current[kv.group(1)] = _parse_quoted_value(kv.group(2))
            continue
        kv = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(.*)$", stripped)
        if kv:
            current[kv.group(1)] = _parse_quoted_value(kv.group(2))
    if current:
        items.append(current)
    return items


def load_tools(path: Path) -> list[dict]:
    """Load list of tools from affiliate_tools.yaml (key: tools)."""
    return load_yaml_list(path, "tools")


def load_use_cases(path: Path) -> list[dict]:
    """Load list of use cases from use_cases.yaml (key: use_cases)."""
    return load_yaml_list(path, "use_cases")


def title_for_entry(problem: str, content_type: str, tool_name: str) -> str:
    """Generate title as '{action} {problem} with {tool_name}'."""
    problem = (problem or "").strip()
    tool_name = (tool_name or "").strip()
    action = CONTENT_TYPE_ACTION.get(
        (content_type or "").strip().lower(),
        "Guide to",
    )
    if not problem:
        return f"{action} with {tool_name}" if tool_name else "Untitled"
    if not tool_name:
        return f"{action} {problem}"
    return f"{action} {problem} with {tool_name}"


def title_to_primary_keyword(title: str) -> str:
    """Derive primary_keyword from title (lowercase, simple)."""
    return (title or "").strip().lower() or "article"


def build_queue_items(use_cases: list[dict], today: str) -> list[dict]:
    """Build queue items: one entry per use case. Tool fields left empty for later assignment."""
    items = []
    for uc in use_cases:
        problem = (uc.get("problem") or "").strip()
        if not problem:
            continue
        content_type = (uc.get("suggested_content_type") or "").strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            content_type = DEFAULT_CONTENT_TYPE
        category_slug = (uc.get("category_slug") or "").strip() or "ai-marketing-automation"
        # No tool: title is "{action} {problem}" (title_for_entry with tool_name="")
        title = title_for_entry(problem, content_type, "")
        item = {
            "title": title,
            "primary_keyword": title_to_primary_keyword(title),
            "content_type": content_type,
            "category_slug": category_slug,
            "primary_tool": "",
            "secondary_tool": "",
            "status": "todo",
            "last_updated": today,
        }
        if uc.get("audience_type"):
            item["audience_type"] = (uc.get("audience_type") or "").strip()
        if uc.get("batch_id"):
            item["batch_id"] = (uc.get("batch_id") or "").strip()
        items.append(item)
    return items


def load_existing_queue(path: Path) -> list[dict]:
    """Load existing queue using same format as generate_articles (list of mappings)."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [dict(item) for item in data]
        return []
    except json.JSONDecodeError:
        pass
    items = []
    blocks = re.split(r"\n(?=- )", text)
    for block in blocks:
        block = block.strip()
        if not block.startswith("- "):
            continue
        block = block[2:]
        item = {}
        for line in block.split("\n"):
            m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
            if m:
                key, val = m.group(1), m.group(2).strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1].replace('\\"', '"')
                item[key] = val
        if item:
            items.append(item)
    return items


def save_queue(path: Path, items: list[dict]) -> None:
    """Write queue as simple YAML (list of mappings). Same format as generate_articles.save_queue."""
    lines = []
    for item in items:
        first = True
        for k, v in item.items():
            v = str(v)
            if "\n" in v or ":" in v or v.startswith("#"):
                v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
            if first:
                lines.append(f"- {k}: {v}")
                first = False
            else:
                lines.append(f"  {k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _duplicate_key(item: dict) -> tuple[str, str, str]:
    """(title, primary_tool, content_type) for duplicate check."""
    return (
        (item.get("title") or "").strip(),
        (item.get("primary_tool") or "").strip(),
        (item.get("content_type") or "").strip(),
    )


USE_CASES_HEADER = """# List of business problems / use cases for content generation
# Each item should have:
# - problem: string (description of the problem, e.g., "turn podcasts into written content")
# - suggested_content_type: string (one of: how-to, guide, best, comparison)
# - category_slug: string (e.g., "ai-marketing-automation")
# - status: optional; "todo" = add to queue, missing or "generated" = skip (backward compat)
"""


def _save_use_cases(path: Path, items: list[dict]) -> None:
    """Write use_cases.yaml (same format as generate_use_cases). Preserves status."""
    def q(v: str) -> str:
        v = str(v)
        if "\n" in v or ":" in v or v.startswith("#") or '"' in v:
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return v
    lines = [USE_CASES_HEADER.strip(), "use_cases:"]
    for item in items:
        problem = (item.get("problem") or "").strip()
        content_type = (item.get("suggested_content_type") or "").strip()
        category = (item.get("category_slug") or "").strip()
        lines.append(f"  - problem: {q(problem)}")
        lines.append(f"    suggested_content_type: {q(content_type)}")
        lines.append(f"    category_slug: {q(category)}")
        if item.get("audience_type"):
            lines.append(f"    audience_type: {q(str(item.get('audience_type', '')).strip())}")
        if item.get("batch_id"):
            lines.append(f"    batch_id: {q(str(item.get('batch_id', '')).strip())}")
        if "status" in item and str(item.get("status", "")).strip():
            lines.append(f"    status: {q(str(item.get('status', '')).strip())}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Append queue entries from use_cases.yaml (one entry per use case).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be added, do not modify queue.yaml.",
    )
    args = parser.parse_args()

    today = date.today().isoformat()
    use_cases = load_use_cases(USE_CASES_PATH)
    # Only use cases with status "todo" go to queue; missing/empty = "generated" (backward compat)
    todo_use_cases = [
        uc for uc in use_cases
        if str(uc.get("status") or "generated").strip().lower() == "todo"
    ]
    candidates = build_queue_items(todo_use_cases, today)
    if not candidates:
        print("No queue entries to add (no use cases with status 'todo').")
        return

    existing = load_existing_queue(QUEUE_PATH)
    existing_keys = {_duplicate_key(e) for e in existing}
    added = [i for i in candidates if _duplicate_key(i) not in existing_keys]
    final = existing + added

    if args.dry_run:
        print(f"Would add {len(added)} new entr{'y' if len(added) == 1 else 'ies'} (duplicates skipped: {len(candidates) - len(added)}).")
        for item in added:
            print(f"  - {item.get('title')} | {item.get('primary_tool')} | {item.get('content_type')}")
        print("(dry run: queue.yaml not modified)")
        return

    if not added:
        print("No new entries to add (all combinations already in queue).")
        return

    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_queue(QUEUE_PATH, final)
    # Mark added use cases as generated so they are not queued again
    added_keys_set = {_duplicate_key(a) for a in added}
    for i, c in enumerate(candidates):
        if _duplicate_key(c) in added_keys_set:
            uc = todo_use_cases[i]
            p = (uc.get("problem") or "").strip()
            ct = (uc.get("suggested_content_type") or "").strip()
            cat = (uc.get("category_slug") or "").strip()
            for u in use_cases:
                if (u.get("problem") or "").strip() == p and (u.get("suggested_content_type") or "").strip() == ct and (u.get("category_slug") or "").strip() == cat:
                    u["status"] = "generated"
                    break
    _save_use_cases(USE_CASES_PATH, use_cases)
    print(f"Added {len(added)} new entr{'y' if len(added) == 1 else 'ies'} to {QUEUE_PATH}. Total queue: {len(final)}. Marked those use cases as 'generated' in use_cases.yaml.")


if __name__ == "__main__":
    main()
