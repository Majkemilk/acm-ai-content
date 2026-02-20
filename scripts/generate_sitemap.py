#!/usr/bin/env python3
"""
Production-only sitemap generator. Uses content_index for production articles;
outputs public/sitemap.xml with hub + articles. Stdlib only.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from content_index import get_production_articles, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
OUT_PATH = PROJECT_ROOT / "public" / "sitemap.xml"

BASE_URL = "https://flowtaro.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _date_from_string(s: str) -> str | None:
    """Return YYYY-MM-DD if s is valid, else None."""
    if not s or len(s) < 10:
        return None
    s = s.strip()[:10]
    if len(s) != 10 or s[4] != "-" or s[7] != "-":
        return None
    try:
        y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"
    except (ValueError, IndexError):
        pass
    return None


def _lastmod_for_article(meta: dict, path: Path) -> str | None:
    """lastmod from frontmatter last_updated or filename date prefix."""
    lastmod = _date_from_string(meta.get("last_updated") or "")
    if lastmod:
        return lastmod
    stem = path.stem
    return _date_from_string(stem)


def _write_sitemap_xml(urls: list[tuple[str, str | None]]) -> str:
    """Build sitemap XML string. urls = [(path, lastmod or None), ...]. loc = absolute URL."""
    root = ET.Element("urlset", xmlns=SITEMAP_NS)
    for loc_path, lastmod in urls:
        url_el = ET.SubElement(root, "url")
        path = loc_path if loc_path.startswith("/") else "/" + loc_path
        ET.SubElement(url_el, "loc").text = BASE_URL + path
        if lastmod:
            ET.SubElement(url_el, "lastmod").text = lastmod
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", default_namespace="", method="xml")


def main() -> None:
    config = load_config(CONFIG_PATH)
    hub_slug = (config.get("hub_slug") or "ai-marketing-automation").strip()
    articles = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
    articles_sorted = sorted(articles, key=lambda x: (x[0].get("slug") or x[1].stem,))

    urls: list[tuple[str, str | None]] = []
    urls.append((f"/hubs/{hub_slug}/", None))
    for meta, path in articles_sorted:
        slug = meta.get("slug") or path.stem
        urls.append((f"/articles/{slug}/", _lastmod_for_article(meta, path)))

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + _write_sitemap_xml(urls)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(xml_str, encoding="utf-8")
    print(f"Sitemap written: {OUT_PATH} ({len(urls)} URLs)")


if __name__ == "__main__":
    main()
