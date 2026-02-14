#!/usr/bin/env python3
"""
Local article generator: reads content/queue.yaml, renders templates into
content/articles/ as markdown. No frameworks or external dependencies.
Updates queue item status from "todo" to "generated" after each file is written.
Fills {{INTERNAL_LINKS}} from existing articles (same category/tool/content_type).
"""

import argparse
import json
import re
from datetime import date
from pathlib import Path

# Pattern: markdown link using our internal URL convention (already has links)
INTERNAL_LINK_PATTERN = re.compile(r"\]\s*\(\s*/articles/[^)]+\)")

# URL convention for internal links (no routing; path only)
INTERNAL_LINK_PREFIX = "/articles/"
INTERNAL_LINK_SUFFIX = "/"

# Taxonomy: enforced category and content_type to prevent drift (niche: ai-marketing-automation)
ALLOWED_CATEGORIES = ["ai-marketing-automation"]
ALLOWED_CONTENT_TYPES = ["review", "comparison", "best", "how-to", "guide"]
CATEGORY_ALIASES = {
    "seo": "ai-marketing-automation",
    "marketing-automation": "ai-marketing-automation",
    "automation": "ai-marketing-automation",
    "ai-automation": "ai-marketing-automation",
}
DEFAULT_CONTENT_TYPE = "guide"

# Paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = PROJECT_ROOT / "content" / "queue.yaml"
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "article-template.md"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"

# Template variable names (template uses {{VAR}}, queue uses snake_case)
TEMPLATE_VARS = [
    "TITLE",
    "PRIMARY_KEYWORD",
    "CONTENT_TYPE",
    "CATEGORY_SLUG",
    "PRIMARY_TOOL",
    "SECONDARY_TOOL",
    "TOOLS_MENTIONED",
    "INTERNAL_LINKS",
    "CTA_BLOCK",
    "AFFILIATE_DISCLOSURE",
    "LAST_UPDATED",
]

# Frontmatter keys (from queue, written at top of each article)
FRONTMATTER_KEYS = [
    "title",
    "content_type",
    "category",
    "primary_keyword",
    "primary_tool",
    "secondary_tool",
    "last_updated",
    "status",
]


def load_queue(path: Path) -> list[dict]:
    """Load queue from YAML-like file. Supports JSON (valid YAML subset) or simple list-of-maps YAML."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    # Try JSON first (no dependency; JSON is a YAML subset)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [dict(item) for item in data]
        return []
    except json.JSONDecodeError:
        pass
    # Simple YAML: list of mappings (each block starts with "- ")
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
    """Write queue back as simple YAML (list of mappings)."""
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


def normalize_category(raw: str) -> str:
    """Normalize category to allowed value; map aliases to ai-marketing-automation."""
    r = (raw or "").strip().lower()
    if not r:
        return ALLOWED_CATEGORIES[0]
    return CATEGORY_ALIASES.get(r, ALLOWED_CATEGORIES[0])


def normalize_content_type(raw: str) -> str:
    """Normalize content_type to allowed value; default 'guide' if missing or invalid. Warn if invalid."""
    r = (raw or "").strip().lower()
    if not r:
        return DEFAULT_CONTENT_TYPE
    if r in ALLOWED_CONTENT_TYPES:
        return r
    print(f"Warning: content_type '{raw}' not in {ALLOWED_CONTENT_TYPES}; using '{DEFAULT_CONTENT_TYPE}'.")
    return DEFAULT_CONTENT_TYPE


def slug_from_keyword(primary_keyword: str) -> str:
    """Build filename-safe slug from primary keyword."""
    if not primary_keyword:
        return "article"
    s = primary_keyword.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s or "article"


def parse_article_frontmatter(path: Path) -> dict | None:
    """Parse frontmatter from a markdown file. Returns dict with title, category, content_type, primary_tool, slug (filename stem)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end].strip()
    data: dict[str, str] = {"slug": path.stem}
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
    return data


def load_existing_articles(articles_dir: Path, exclude_slug: str) -> list[dict]:
    """Load metadata from all .md files in articles_dir. Exclude file with stem exclude_slug. Sorted by slug for stability."""
    if not articles_dir.exists():
        return []
    out: list[dict] = []
    for path in sorted(articles_dir.glob("*.md")):
        if path.stem == exclude_slug:
            continue
        meta = parse_article_frontmatter(path)
        if meta:
            out.append(meta)
    return out


def select_internal_links(
    existing: list[dict],
    current_category: str,
    current_primary_tool: str,
    current_content_type: str,
    max_category: int = 3,
    max_tool: int = 2,
    max_content_type: int = 1,
) -> list[tuple[str, str]]:
    """Select 3–6 internal links by priority: same category (up to 3), same primary_tool (up to 2), same content_type (up to 1). Deterministic order."""
    current_category = (current_category or "").strip().lower()
    current_primary_tool = (current_primary_tool or "").strip().lower()
    current_content_type = (current_content_type or "").strip().lower()

    def url_for(slug: str) -> str:
        return f"{INTERNAL_LINK_PREFIX}{slug}{INTERNAL_LINK_SUFFIX}"

    def title_for(meta: dict) -> str:
        return (meta.get("title") or meta.get("slug") or "").strip() or meta.get("slug", "")

    chosen: list[tuple[str, str]] = []
    used_slugs: set[str] = set()

    for meta in existing:
        slug = meta.get("slug") or ""
        if not slug or slug in used_slugs:
            continue
        cat = (meta.get("category") or meta.get("category_slug") or "").strip().lower()
        if cat == current_category:
            chosen.append((title_for(meta), url_for(slug)))
            used_slugs.add(slug)
            if len(chosen) >= max_category:
                break
    for meta in existing:
        slug = meta.get("slug") or ""
        if not slug or slug in used_slugs:
            continue
        tool = (meta.get("primary_tool") or "").strip().lower()
        if tool and tool == current_primary_tool:
            chosen.append((title_for(meta), url_for(slug)))
            used_slugs.add(slug)
            if len(chosen) >= max_category + max_tool:
                break
    for meta in existing:
        slug = meta.get("slug") or ""
        if not slug or slug in used_slugs:
            continue
        ctype = (meta.get("content_type") or "").strip().lower()
        if ctype and ctype == current_content_type:
            chosen.append((title_for(meta), url_for(slug)))
            used_slugs.add(slug)
            if len(chosen) >= max_category + max_tool + max_content_type:
                break
    return chosen



def format_internal_links_bullets(links: list[tuple[str, str]]) -> str:
    """Format (title, url) pairs as markdown bullet list. No external or affiliate URLs."""
    return "\n".join(f"- [{title}]({url})" for title, url in links)


def _body_after_frontmatter(content: str) -> str:
    """Return content after the closing --- of frontmatter."""
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 3)
    if end == -1:
        return content
    return content[end + 4 :].lstrip("\n")


def _find_internal_links_section(body: str) -> tuple[int, int] | None:
    """Return (start, end) byte range of the '## Internal links' section in body, or None."""
    marker = "## Internal links"
    start = body.find(marker)
    if start == -1:
        return None
    end = body.find("\n## ", start + len(marker))
    if end == -1:
        end = len(body)
    return (start, end)


def backfill_internal_links_in_file(
    path: Path,
    articles_dir: Path,
) -> str:
    """
    Update one article file: replace {{INTERNAL_LINKS}} placeholder with computed links.
    Returns: "updated" | "skipped" (already has links) | "unchanged" (no placeholder / no section).
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return "unchanged"
    if not content.startswith("---"):
        return "unchanged"
    body = _body_after_frontmatter(content)
    section_range = _find_internal_links_section(body)
    if section_range is None:
        return "unchanged"
    start, end = section_range
    section = body[start:end]
    if INTERNAL_LINK_PATTERN.search(section):
        return "skipped"
    if "{{INTERNAL_LINKS}}" not in section:
        return "unchanged"
    meta = parse_article_frontmatter(path)
    if not meta:
        return "unchanged"
    slug = meta.get("slug") or path.stem
    existing = load_existing_articles(articles_dir, exclude_slug=slug)
    category = (meta.get("category") or meta.get("category_slug") or "").strip()
    primary_tool = (meta.get("primary_tool") or "").strip()
    content_type = (meta.get("content_type") or "").strip()
    links = select_internal_links(
        existing, current_category=category, current_primary_tool=primary_tool, current_content_type=content_type
    )
    new_bullets = format_internal_links_bullets(links)
    if "- {{INTERNAL_LINKS}}" in section:
        section_new = section.replace("- {{INTERNAL_LINKS}}", new_bullets)
    else:
        section_new = section.replace("{{INTERNAL_LINKS}}", new_bullets)
    if section_new == section:
        return "unchanged"
    body_new = body[:start] + section_new + body[end:]
    front_end = content.find("\n---", 3) + 4
    new_content = content[:front_end] + body_new
    path.write_text(new_content, encoding="utf-8")
    return "updated"


def run_backfill(articles_dir: Path) -> None:
    """Backfill internal links in all .md files in articles_dir. No queue, no new generation."""
    if not articles_dir.exists():
        print("Articles directory not found.")
        return
    updated = skipped = unchanged = 0
    for path in sorted(articles_dir.glob("*.md")):
        result = backfill_internal_links_in_file(path, articles_dir)
        if result == "updated":
            updated += 1
            print(f"Updated: {path.name}")
        elif result == "skipped":
            skipped += 1
        else:
            unchanged += 1
    print(f"\nSummary: {updated} updated, {skipped} skipped (already have links), {unchanged} unchanged.")


def build_frontmatter(item: dict, today: str) -> str:
    """Build YAML frontmatter from queue item; use placeholders for missing required fields. Category and content_type are normalized."""
    raw_cat = (item.get("category_slug") or item.get("category") or "").strip()
    raw_ct = (item.get("content_type") or "").strip()
    fm = {
        "title": item.get("title") or "{{TITLE}}",
        "content_type": normalize_content_type(raw_ct),
        "category": normalize_category(raw_cat),
        "primary_keyword": item.get("primary_keyword") or "{{PRIMARY_KEYWORD}}",
        "primary_tool": item.get("primary_tool") or "{{PRIMARY_TOOL}}",
        "secondary_tool": item.get("secondary_tool") or "{{SECONDARY_TOOL}}",
        "last_updated": item.get("last_updated") or today,
        "status": "draft",
    }
    lines = ["---"]
    for k, v in fm.items():
        v = str(v)
        if "\n" in v or '"' in v:
            v = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k}: "{v}"')
    lines.append("---")
    return "\n".join(lines) + "\n"


def get_replacements(
    item: dict,
    today: str,
    internal_links_override: str | None = None,
) -> dict[str, str]:
    """Map queue item to template variables. Missing values stay as placeholder {{VAR}}.
    If internal_links_override is set, use it for {{INTERNAL_LINKS}}; else use queue value or placeholder."""
    def val_for(var: str) -> str | None:
        if var == "TITLE":
            return (item.get("title") or "").strip() or None
        if var == "PRIMARY_KEYWORD":
            return (item.get("primary_keyword") or "").strip() or None
        if var == "CONTENT_TYPE":
            return normalize_content_type((item.get("content_type") or "").strip())
        if var == "CATEGORY_SLUG":
            return normalize_category((item.get("category_slug") or item.get("category") or "").strip())
        if var == "PRIMARY_TOOL":
            return (item.get("primary_tool") or "").strip() or None
        if var == "SECONDARY_TOOL":
            return (item.get("secondary_tool") or "").strip() or None
        if var == "TOOLS_MENTIONED":
            return (item.get("tools_mentioned") or "").strip() or None
        if var == "INTERNAL_LINKS":
            if internal_links_override is not None:
                return internal_links_override
            return (item.get("internal_links") or "").strip() or None
        if var == "CTA_BLOCK":
            return (item.get("cta_block") or "").strip() or None
        if var == "AFFILIATE_DISCLOSURE":
            return (item.get("affiliate_disclosure") or "").strip() or None
        if var == "LAST_UPDATED":
            return (item.get("last_updated") or today).strip() or today
        return None
    replacements = {}
    for var in TEMPLATE_VARS:
        val = val_for(var)
        if val:
            replacements[f"{{{{{var}}}}}"] = val
        else:
            replacements[f"{{{{{var}}}}}"] = today if var == "LAST_UPDATED" else f"{{{{{var}}}}}"
    return replacements


def render_article(
    template: str,
    item: dict,
    today: str,
    internal_links_override: str | None = None,
) -> str:
    """Produce article body: frontmatter + template with variables replaced."""
    front = build_frontmatter(item, today)
    body = template
    for placeholder, value in get_replacements(
        item, today, internal_links_override=internal_links_override
    ).items():
        body = body.replace(placeholder, value)
    return front + body


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate articles from queue or backfill internal links.")
    parser.add_argument("--backfill", action="store_true", help="Update existing articles with internal links; do not generate from queue.")
    args = parser.parse_args()

    articles_dir = ARTICLES_DIR
    articles_dir.mkdir(parents=True, exist_ok=True)

    if args.backfill:
        run_backfill(articles_dir)
        return

    today = date.today().isoformat()
    if not QUEUE_PATH.exists():
        print(f"Queue not found: {QUEUE_PATH}")
        return
    items = load_queue(QUEUE_PATH)
    if not items:
        print("Queue is empty.")
        return

    if not TEMPLATE_PATH.exists():
        print(f"Template not found: {TEMPLATE_PATH}")
        return
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    todo_indices = [i for i, it in enumerate(items) if it.get("status") == "todo"]
    if not todo_indices:
        print("No queue items with status: todo.")
        return

    for i in todo_indices:
        item = items[i]
        slug = slug_from_keyword(item.get("primary_keyword") or "")
        filename = f"{today}-{slug}.md"
        out_slug = filename.removesuffix(".md")
        out_path = articles_dir / filename

        existing = load_existing_articles(articles_dir, exclude_slug=out_slug)
        category = normalize_category((item.get("category_slug") or item.get("category") or "").strip())
        content_type = normalize_content_type((item.get("content_type") or "").strip())
        primary_tool = (item.get("primary_tool") or "").strip()
        links = select_internal_links(
            existing, current_category=category, current_primary_tool=primary_tool, current_content_type=content_type
        )
        internal_links_str = format_internal_links_bullets(links) if links else None

        content = render_article(
            template, item, today, internal_links_override=internal_links_str
        )
        out_path.write_text(content, encoding="utf-8")
        print(f"Generated: {out_path}")
        item["status"] = "generated"

    save_queue(QUEUE_PATH, items)
    print("Queue updated: todo -> generated.")


if __name__ == "__main__":
    main()
