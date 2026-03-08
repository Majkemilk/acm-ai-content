#!/usr/bin/env python3
"""
Generate content/queue.yaml from content/use_cases.yaml.
Creates one queue entry per use case. The 'tools' field is left empty;
tools are selected by AI at the fill_articles stage based on article context.
Uses only Python standard library. Line-based YAML parsing (no external deps).
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from content_index import load_config, get_hubs_list
from content_root import get_content_root_path, get_affiliate_tools_path

# Defaults (overridden in main() from --content-root / CONTENT_ROOT)
CONTENT_DIR = PROJECT_ROOT / "content"
CONFIG_PATH = CONTENT_DIR / "config.yaml"
AFFILIATE_TOOLS_PATH = CONTENT_DIR / "affiliate_tools.yaml"
USE_CASES_PATH = CONTENT_DIR / "use_cases.yaml"
QUEUE_PATH = CONTENT_DIR / "queue.yaml"

# Default when config has no content_types_all (ALL = same list as generate_use_cases)
ALLOWED_CONTENT_TYPES = [
    "how-to",
    "guide",
    "best",
    "comparison",
    "review",
    "sales",
    "product-comparison",
    "best-in-category",
    "category-products",
]
DEFAULT_CONTENT_TYPE = "guide"

CONTENT_TYPE_ACTION = {
    "how-to": "How to",
    "guide": "Guide to",
    "best": "Best",
    "comparison": "Comparison of",
    "review": "Guide to",
    "sales": "Sales:",
    "product-comparison": "Comparison of",
    "best-in-category": "Best in category:",
    "category-products": "Products in category:",
}

# Prefixes to strip from start of problem (case-insensitive) to avoid duplicated title prefix
PREFIXES_TO_STRIP_BY_TYPE = {
    "how-to": ["how to "],
    "guide": ["guide to ", "how to "],
    "best": ["best ", "how to "],
    "comparison": ["comparison of "],
    "review": ["guide to ", "how to "],
    "sales": ["sales:", "sales "],
    "product-comparison": ["comparison of "],
    "best-in-category": ["best in category:", "best in category "],
    "category-products": ["products in category:", "products in category "],
}


def _strip_duplicate_prefix(problem: str, content_type: str) -> str:
    """Remove leading prefix from problem that would duplicate CONTENT_TYPE_ACTION (case-insensitive)."""
    if not problem:
        return problem
    ct = (content_type or "").strip().lower()
    prefixes = PREFIXES_TO_STRIP_BY_TYPE.get(ct)
    if not prefixes:
        return problem
    rest = problem.strip()
    for prefix in prefixes:
        if rest.lower().startswith(prefix):
            rest = rest[len(prefix) :].strip()
            break
    return rest or problem.strip()


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
    Simple line-based parser (no external libs).
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


def load_use_cases_with_default_lang(path: Path) -> tuple[list[dict], str | None]:
    """Load use cases and optional top-level default_lang (e.g. 'pl' for content/pl). Used to set lang on queue items."""
    if not path.exists():
        return [], None
    text = path.read_text(encoding="utf-8")
    # Parse default_lang from top-level key (before use_cases:)
    default_lang = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("use_cases"):
            break
        m = re.match(r"^default_lang\s*:\s*(.+)$", stripped, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().strip('"\'').strip().lower()
            if raw in ("en", "pl"):
                default_lang = raw
            break
    use_cases = load_yaml_list(path, "use_cases")
    return use_cases, default_lang


def title_for_entry(problem: str, content_type: str, add_prefix: bool = True) -> str:
    """Generate title as '{action} {problem}' when add_prefix=True, else just the problem (for PL reader-friendly titles).
    Strips from problem any leading prefix that would duplicate the action."""
    problem = (problem or "").strip()
    content_type_key = (content_type or "").strip().lower()
    problem = _strip_duplicate_prefix(problem, content_type_key)
    if not problem:
        return "Untitled"
    if not add_prefix:
        return problem
    action = CONTENT_TYPE_ACTION.get(content_type_key, "Guide to")
    return f"{action} {problem}"


def title_to_primary_keyword(title: str) -> str:
    """Derive primary_keyword from title (lowercase, simple)."""
    return (title or "").strip().lower() or "article"


def build_queue_items(
    use_cases: list[dict],
    today: str,
    allowed_content_types: list[str] | None = None,
    category_to_lang: dict[str, str] | None = None,
    content_dir: object = None,
    default_lang: str | None = None,
) -> list[dict]:
    """Build queue items: one entry per use case. Tools left empty (filled at fill_articles stage).
    allowed_content_types: from config content_types_all; if missing/invalid, content_type falls back to DEFAULT_CONTENT_TYPE.
    category_to_lang: optional map category_slug -> lang from config hubs (e.g. problem-fix-find-pl -> pl); used when use case has no lang.
    content_dir: optional Path; when its parts contain 'pl', titles are built without content-type prefix (PL reader-friendly).
    default_lang: optional top-level lang from use_cases.yaml (e.g. 'pl'); used when use case has no lang and category_to_lang has no entry."""
    allowed = list(allowed_content_types) if allowed_content_types else ALLOWED_CONTENT_TYPES
    cat_lang = category_to_lang or {}
    force_pl_titles = getattr(content_dir, "parts", None) and "pl" in getattr(content_dir, "parts", ())
    force_pl_lang = getattr(content_dir, "parts", None) and "pl" in getattr(content_dir, "parts", ())
    items = []
    for uc in use_cases:
        problem = (uc.get("problem") or "").strip()
        if not problem:
            continue
        content_type = (uc.get("content_type") or "").strip().lower()
        if content_type not in allowed:
            content_type = DEFAULT_CONTENT_TYPE
        category_slug = (uc.get("category_slug") or "").strip() or "ai-marketing-automation"
        # No content-type prefix in title for any locale (EN and PL reader-friendly; same as PL previously).
        title = title_for_entry(problem, content_type, add_prefix=False)
        item = {
            "title": title,
            "primary_keyword": title_to_primary_keyword(title),
            "content_type": content_type,
            "category_slug": category_slug,
            "tools": "",
            "status": "todo",
            "last_updated": today,
        }
        if uc.get("audience_type"):
            # Required for correct audience badge (Beginner/Intermediate/Advanced) in rendered articles
            item["audience_type"] = (uc.get("audience_type") or "").strip()
        if uc.get("batch_id"):
            item["batch_id"] = (uc.get("batch_id") or "").strip()
        # Lang: use case > default_lang (from use_cases.yaml) > category (from hub) > content root PL > en
        if uc.get("lang"):
            item["lang"] = (uc.get("lang") or "").strip().lower()
        elif default_lang:
            _dl = (default_lang or "").strip().lower()
            item["lang"] = _dl if _dl in ("en", "pl") else "en"
        elif category_slug in cat_lang:
            item["lang"] = (cat_lang[category_slug] or "en").strip().lower()
        elif force_pl_lang:
            item["lang"] = "pl"
        else:
            item["lang"] = "en"
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


def _duplicate_key(item: dict) -> tuple[str, str]:
    """(title, content_type) for duplicate check."""
    return (
        (item.get("title") or "").strip(),
        (item.get("content_type") or "").strip(),
    )


USE_CASES_HEADER = """# List of business problems / use cases for content generation
# default_lang: optional top-level key before use_cases:; "pl" or "en" — applied to queue items when generated (for content/pl use "pl").
# Each item should have:
# - problem: string (description of the problem, e.g., "turn podcasts into written content")
# - content_type: string (one of: how-to, guide, best, comparison, review, sales, product-comparison, best-in-category, category-products)
# - category_slug: string (e.g., "ai-marketing-automation")
# - status: optional; "todo" = add to queue; "generated" / "archived" / "discarded" or missing = skip
"""


def _save_use_cases(path: Path, items: list[dict], default_lang: str | None = None) -> None:
    """Write use_cases.yaml (same format as generate_use_cases). Preserves status and optional default_lang."""
    def q(v: str) -> str:
        v = str(v)
        if "\n" in v or ":" in v or v.startswith("#") or '"' in v:
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return v
    lines = [USE_CASES_HEADER.strip()]
    if default_lang and (default_lang or "").strip().lower() in ("en", "pl"):
        lines.append(f"default_lang: {(default_lang or '').strip().lower()}")
    lines.append("use_cases:")
    for item in items:
        problem = (item.get("problem") or "").strip()
        content_type = (item.get("content_type") or "").strip()
        category = (item.get("category_slug") or "").strip()
        lines.append(f"  - problem: {q(problem)}")
        lines.append(f"    content_type: {q(content_type)}")
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
    import os
    parser = argparse.ArgumentParser(
        description="Append queue entries from use_cases.yaml (one entry per use case).",
    )
    parser.add_argument("--content-root", default=os.environ.get("CONTENT_ROOT", "content"), help="Content root (content or content/pl)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be added, do not modify queue.yaml.",
    )
    args = parser.parse_args()

    content_dir = get_content_root_path(PROJECT_ROOT, args.content_root)
    config_path = content_dir / "config.yaml"
    use_cases_path = content_dir / "use_cases.yaml"
    queue_path = content_dir / "queue.yaml"

    # ALL = content_types_all from config (single source of truth; fallback when type not on list)
    config = load_config(config_path)
    allowed_content_types = list(config.get("content_types_all") or ALLOWED_CONTENT_TYPES)

    # Lang from hubs (e.g. pl for PL content root) so queue items get correct lang when use case has none
    category_to_lang = {}
    for hub in get_hubs_list(config) or []:
        if isinstance(hub, dict):
            cat = (hub.get("category") or "").strip()
            hlang = (hub.get("lang") or "").strip().lower()
            if cat and hlang:
                category_to_lang[cat] = hlang

    today = date.today().isoformat()
    use_cases, default_lang = load_use_cases_with_default_lang(use_cases_path)

    # Only use cases with status "todo" are added; "generated", "archived", "discarded" are skipped.
    todo_use_cases = [
        uc for uc in use_cases
        if str(uc.get("status") or "").strip().lower() == "todo"
    ]
    candidates = build_queue_items(
        todo_use_cases, today,
        allowed_content_types=allowed_content_types,
        category_to_lang=category_to_lang,
        content_dir=content_dir,
        default_lang=default_lang,
    )
    if not candidates:
        print("No queue entries to add (no use cases with status 'todo').")
        return

    existing = load_existing_queue(queue_path)
    existing_keys = {_duplicate_key(e) for e in existing}
    added = [i for i in candidates if _duplicate_key(i) not in existing_keys]
    final = existing + added

    if args.dry_run:
        print(f"Would add {len(added)} new entr{'y' if len(added) == 1 else 'ies'} (duplicates skipped: {len(candidates) - len(added)}).")
        for item in added:
            print(f"  - {item.get('title')} | {item.get('content_type')}")
        print("(dry run: queue.yaml not modified)")
        return

    if not added:
        print("No new entries to add (all combinations already in queue).")
        return

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    save_queue(queue_path, final)
    added_keys_set = {_duplicate_key(a) for a in added}
    for i, c in enumerate(candidates):
        if _duplicate_key(c) in added_keys_set:
            uc = todo_use_cases[i]
            p = (uc.get("problem") or "").strip()
            ct = (uc.get("content_type") or "").strip()
            cat = (uc.get("category_slug") or "").strip()
            for u in use_cases:
                if (u.get("problem") or "").strip() == p and (u.get("content_type") or "").strip() == ct and (u.get("category_slug") or "").strip() == cat:
                    u["status"] = "generated"
                    break
    _save_use_cases(use_cases_path, use_cases, default_lang=default_lang)
    print(f"Added {len(added)} new entr{'y' if len(added) == 1 else 'ies'} to {queue_path}. Total queue: {len(final)}. Marked those use cases as 'generated' in use_cases.yaml.")


if __name__ == "__main__":
    main()
