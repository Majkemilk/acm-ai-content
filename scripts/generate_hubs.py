#!/usr/bin/env python3
"""
Category hub generator: reads content/config.yaml and content/articles/,
generates hub pages for each hub in config (get_hubs_list). If config has multiple hubs,
articles are assigned by meta.category; otherwise all production articles go to the single hub.
Stdlib only. Outputs HTML with card grids (same structure as homepage).
"""

import html as html_module
import re
from datetime import date, datetime
from pathlib import Path

from content_index import get_production_articles, get_hubs_list, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
HUBS_DIR = PROJECT_ROOT / "content" / "hubs"
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"

ARTICLES_URL_PREFIX = "/articles/"
ARTICLES_URL_SUFFIX = "/"

# Section titles for each content_type (order for output)
CONTENT_TYPE_SECTIONS = [
    ("guide", "Guides"),
    ("how-to", "How-to"),
    ("review", "Reviews"),
    ("comparison", "Comparisons"),
    ("product-comparison", "Product comparisons"),
    ("best", "Best"),
    ("best-in-category", "Best in category"),
    ("sales", "Sales"),
    ("category-products", "Category products"),
]
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


def build_hub_content(hub_title: str, hub_intro: str, articles: list[tuple[dict, Path]]) -> str:
    """Build hub page as HTML: H1, intro, then sections by content_type (cards)."""
    parts: list[str] = []
    intro = hub_intro.strip() or (
        "This hub collects guides, how-tos, reviews, and comparisons. "
        "The articles below are organized by type so you can find what fits your goal."
    )
    parts.append(
        '<div style="text-align: justify">\n'
        f"<h1 style=\"margin-bottom: 1em\">{html_module.escape(hub_title)}</h1>\n\n"
        f"<p>{html_module.escape(intro)}</p>\n"
        "</div>\n"
    )
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


def _articles_for_hub(
    all_articles: list[tuple[dict, Path]],
    hub_category: str,
    first_hub_category: str | None,
) -> list[tuple[dict, Path]]:
    """Return articles whose meta.category matches hub_category; articles without category go to first hub."""
    out: list[tuple[dict, Path]] = []
    for meta, path in all_articles:
        art_cat = (meta.get("category") or "").strip().lower()
        if art_cat:
            if art_cat == hub_category.lower():
                out.append((meta, path))
        else:
            if first_hub_category and hub_category.lower() == first_hub_category.lower():
                out.append((meta, path))
    return out


def main() -> None:
    config = load_config(CONFIG_PATH)
    hubs = get_hubs_list(config)
    all_articles = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
    first_hub_category = hubs[0]["category"] if hubs else None
    HUBS_DIR.mkdir(parents=True, exist_ok=True)
    hub_intros: dict[str, str] = {
        "ai-marketing-automation": (
            "This hub collects guides, how-tos, reviews, and comparisons for AI-powered marketing and automation. "
            "Whether you are evaluating tools, designing workflows, or looking for step-by-step help, the articles below "
            "are organized by type so you can find what fits your goal."
        ),
        "marketplaces-products": (
            "This hub focuses on marketplaces and popular physical products sold on them. "
            "Find guides, comparisons, and how-tos to choose and sell better on major marketplaces."
        ),
    }
    for hub in hubs:
        slug = hub["slug"]
        category = hub["category"]
        title = hub["title"] or slug
        articles = _articles_for_hub(all_articles, category, first_hub_category)
        intro = hub_intros.get(slug, hub_intros.get(category, ""))
        html_body = build_hub_content(title, intro, articles)
        frontmatter = f'---\ntitle: "{title}"\n---\n\n'
        content = frontmatter + html_body
        out_path = HUBS_DIR / f"{slug}.md"
        out_path.write_text(content, encoding="utf-8")
        print(f"Hub written: {out_path} ({len(articles)} articles)")


if __name__ == "__main__":
    main()
