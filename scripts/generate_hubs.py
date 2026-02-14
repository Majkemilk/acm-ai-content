#!/usr/bin/env python3
"""
Category hub generator: reads content/config.yaml and content/articles/,
generates hub pages only for production_category (sandbox categories excluded). Stdlib only.
"""

import re
from datetime import date
from pathlib import Path

from content_index import get_production_articles, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
HUBS_DIR = PROJECT_ROOT / "content" / "hubs"
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"

HUB_SLUG = "ai-marketing-automation"
HUB_TITLE = "AI Marketing Automation Tools & Workflows"
ARTICLES_URL_PREFIX = "/articles/"
ARTICLES_URL_SUFFIX = "/"

# Section titles for each content_type (order for output)
CONTENT_TYPE_SECTIONS = [
    ("guide", "Guides"),
    ("how-to", "How-to"),
    ("review", "Reviews"),
    ("comparison", "Comparisons"),
    ("best", "Best"),
]
MAX_START_HERE = 5


def parse_frontmatter(path: Path) -> dict | None:
    """Parse frontmatter from a markdown file. Returns dict with title, slug, content_type, category, last_updated."""
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


def date_from_string(s: str) -> date | None:
    """Parse YYYY-MM-DD or return None."""
    if not s or len(s) < 10:
        return None
    s = s.strip()[:10]
    try:
        return date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except (ValueError, IndexError):
        return None


def sort_key_newest(meta: dict, path: Path) -> tuple[date, str]:
    """Sort key: newest first. Use last_updated if valid, else date from filename (YYYY-MM-DD-...)."""
    d = date_from_string(meta.get("last_updated") or "")
    if d is not None:
        return (d, meta.get("slug", path.stem))
    # Fallback: first 10 chars of filename as date
    stem = path.stem
    d = date_from_string(stem)
    if d is not None:
        return (d, stem)
    return (date.min, stem)


def build_hub_markdown(articles: list[tuple[dict, Path]]) -> str:
    """Build hub page markdown: H1, intro, Start here, then sections by content_type."""
    lines: list[str] = []
    lines.append(f"# {HUB_TITLE}")
    lines.append("")
    lines.append(
        "This hub collects guides, how-tos, reviews, and comparisons for AI-powered marketing and automation. "
        "Whether you are evaluating tools, designing workflows, or looking for step-by-step help, the articles below "
        "are organized by type so you can start with what fits your goal. Use the **Start here** links for the "
        "newest material, or browse by section."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Start here")
    lines.append("")
    # Newest first, take up to 5
    sorted_articles = sorted(articles, key=lambda x: sort_key_newest(x[0], x[1]), reverse=True)
    for meta, _ in sorted_articles[:MAX_START_HERE]:
        title = (meta.get("title") or meta.get("slug") or "").strip() or meta.get("slug", "")
        slug = meta.get("slug", "")
        url = f"{ARTICLES_URL_PREFIX}{slug}{ARTICLES_URL_SUFFIX}"
        lines.append(f"- [{title}]({url})")
    lines.append("")
    lines.append("---")
    lines.append("")
    # Group by content_type
    by_type: dict[str, list[tuple[dict, Path]]] = {}
    for meta, path in articles:
        ct = (meta.get("content_type") or "guide").strip().lower()
        by_type.setdefault(ct, []).append((meta, path))
    for content_type, section_title in CONTENT_TYPE_SECTIONS:
        group = by_type.get(content_type, [])
        if not group:
            continue
        lines.append(f"## {section_title}")
        lines.append("")
        for meta, _ in sorted(group, key=lambda x: (meta.get("slug", ""),)):
            title = (meta.get("title") or meta.get("slug") or "").strip() or meta.get("slug", "")
            slug = meta.get("slug", "")
            url = f"{ARTICLES_URL_PREFIX}{slug}{ARTICLES_URL_SUFFIX}"
            lines.append(f"- [{title}]({url})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    config = load_config(CONFIG_PATH)
    production_category = (config.get("production_category") or "ai-marketing-automation").strip()
    articles = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
    HUBS_DIR.mkdir(parents=True, exist_ok=True)
    content = build_hub_markdown(articles)
    out_path = HUBS_DIR / f"{production_category}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Hub written: {out_path} ({len(articles)} production articles)")


if __name__ == "__main__":
    main()
