#!/usr/bin/env python3
"""
Category hub generator: reads content/config.yaml and content/articles/,
generates hub pages only for production_category (sandbox categories excluded). Stdlib only.
Outputs HTML with card grids (same structure as homepage).
"""

import html as html_module
import re
from datetime import date, datetime
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

H2_CLASS = 'class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center"'
GRID_CLASS = 'class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"'


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


def updated_iso(meta: dict, path: Path) -> str:
    """Return YYYY-MM-DD from frontmatter last_updated/updated or file mtime."""
    raw = (meta.get("last_updated") or meta.get("updated") or "").strip()
    if raw and len(raw) >= 10:
        try:
            y, m, d = int(raw[:4]), int(raw[5:7]), int(raw[8:10])
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except (ValueError, IndexError):
            pass
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        return datetime.now().strftime("%Y-%m-%d")


def _card_html(title: str, slug: str, date_iso: str) -> str:
    """Single article card HTML (same structure as homepage)."""
    t = html_module.escape(title, quote=True)
    s = html_module.escape(slug, quote=True)
    d = html_module.escape(date_iso, quote=True)
    return (
        f'        <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition">\n'
        f'            <h3 class="text-xl font-semibold mb-2">\n'
        f'                <a href="/articles/{s}/" class="text-gray-900 hover:text-[#17266B]">{t}</a>\n'
        f"            </h3>\n"
        f'            <p class="text-gray-600 text-sm mb-4">{d}</p>\n'
        f'            <a href="/articles/{s}/" class="inline-block bg-[#17266B] text-white px-4 py-2 rounded hover:bg-[#0f1a4a] transition">Read more</a>\n'
        f"        </div>\n"
    )


def _section_html(section_title: str, articles: list[tuple[dict, Path]]) -> str:
    """One section: h2 + grid of cards. Returns empty string if no articles."""
    if not articles:
        return ""
    parts = [f'<h2 {H2_CLASS}>{html_module.escape(section_title)}</h2>\n', f'<div {GRID_CLASS}>\n']
    for meta, path in articles:
        title = (meta.get("title") or meta.get("slug") or path.stem).strip() or path.stem
        slug = meta.get("slug") or path.stem
        date_iso = updated_iso(meta, path)
        parts.append(_card_html(title, slug, date_iso))
    parts.append("</div>\n")
    return "".join(parts)


def build_hub_content(articles: list[tuple[dict, Path]]) -> str:
    """Build hub page as HTML: H1, intro, Start here (cards), then sections by content_type (cards)."""
    parts: list[str] = []
    parts.append(f"<h1>{html_module.escape(HUB_TITLE)}</h1>\n")
    parts.append(
        "<p>This hub collects guides, how-tos, reviews, and comparisons for AI-powered marketing and automation. "
        "Whether you are evaluating tools, designing workflows, or looking for step-by-step help, the articles below "
        "are organized by type so you can start with what fits your goal. Use the <strong>Start here</strong> links "
        "for the newest material, or browse by section.</p>\n"
    )
    # Start here: newest 5
    sorted_articles = sorted(articles, key=lambda x: sort_key_newest(x[0], x[1]), reverse=True)
    start_here = sorted_articles[:MAX_START_HERE]
    parts.append(_section_html("Start here", start_here))
    # Group by content_type
    by_type: dict[str, list[tuple[dict, Path]]] = {}
    for meta, path in articles:
        ct = (meta.get("content_type") or "guide").strip().lower()
        by_type.setdefault(ct, []).append((meta, path))
    for content_type, section_title in CONTENT_TYPE_SECTIONS:
        group = by_type.get(content_type, [])
        section_html = _section_html(section_title, sorted(group, key=lambda x: (x[0].get("slug", x[1].stem),)))
        if section_html:
            parts.append(section_html)
    return "".join(parts)


def main() -> None:
    config = load_config(CONFIG_PATH)
    production_category = (config.get("production_category") or "ai-marketing-automation").strip()
    articles = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
    HUBS_DIR.mkdir(parents=True, exist_ok=True)
    html_body = build_hub_content(articles)
    # Write hub file with frontmatter (title for render_site) and HTML body
    frontmatter = f'---\ntitle: "{HUB_TITLE}"\n---\n\n'
    content = frontmatter + html_body
    out_path = HUBS_DIR / f"{production_category}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Hub written: {out_path} ({len(articles)} production articles)")


if __name__ == "__main__":
    main()
