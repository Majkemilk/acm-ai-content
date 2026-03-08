#!/usr/bin/env python3
"""
Production-only sitemap generator. Uses content_index for production articles;
outputs public/sitemap.xml with hub + articles. Stdlib only.
Supports --site (main|pl), --out-dir, --base-url for subdomain builds.
"""

import argparse
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from content_index import (
    get_production_articles,
    get_hubs_list_for_site,
    get_category_slugs_for_site,
    load_config,
)
from content_root import get_content_root_path
from render_site import _slug_for_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = PROJECT_ROOT / "public"
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


def _write_sitemap_xml(urls: list[tuple[str, str | None]], base_url: str) -> str:
    """Build sitemap XML string. urls = [(path, lastmod or None), ...]. loc = base_url + path."""
    root = ET.Element("urlset", xmlns=SITEMAP_NS)
    base = base_url.rstrip("/")
    for loc_path, lastmod in urls:
        url_el = ET.SubElement(root, "url")
        path = loc_path if loc_path.startswith("/") else "/" + loc_path
        ET.SubElement(url_el, "loc").text = base + path
        if lastmod:
            ET.SubElement(url_el, "lastmod").text = lastmod
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", default_namespace="", method="xml")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sitemap.xml for main or pl site.")
    parser.add_argument("--content-root", default=os.environ.get("CONTENT_ROOT", "content"), help="Content root (content or content/pl)")
    parser.add_argument("--site", default=os.environ.get("SITE", "main"), choices=("main", "pl"), help="Site variant")
    parser.add_argument("--out-dir", default=os.environ.get("OUT_DIR", str(PUBLIC_DIR)), help="Output directory (sitemap.xml written here)")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL"), help="Base URL for loc (default: pl.flowtaro.com for pl, flowtaro.com for main)")
    args = parser.parse_args()
    site = args.site
    content_dir = get_content_root_path(PROJECT_ROOT, args.content_root)
    config_path = content_dir / "config.yaml"
    articles_dir = content_dir / "articles"
    out_dir = Path(args.out_dir)
    base_url = (args.base_url or ("https://pl.flowtaro.com" if site == "pl" else "https://flowtaro.com")).strip().rstrip("/")
    out_path = out_dir / "sitemap.xml"

    config = load_config(config_path)
    hubs = get_hubs_list_for_site(config, site)
    category_slugs = get_category_slugs_for_site(config, site)
    articles = get_production_articles(articles_dir, config_path)
    if category_slugs:
        articles = [a for a in articles if ((a[0].get("category") or a[0].get("category_slug") or "").strip() in category_slugs)]
    articles_sorted = sorted(articles, key=lambda x: (x[0].get("slug") or x[1].stem,))

    urls: list[tuple[str, str | None]] = []
    for hub in hubs:
        slug = hub.get("slug") or hub.get("category") or ""
        if slug:
            urls.append((f"/hubs/{slug}/", None))
    for meta, path in articles_sorted:
        slug = meta.get("slug") or path.stem
        slug_fs = _slug_for_path(slug, out_dir)
        urls.append((f"/articles/{slug_fs}/", _lastmod_for_article(meta, path)))

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + _write_sitemap_xml(urls, base_url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml_str, encoding="utf-8")
    print(f"Sitemap written: {out_path} ({len(urls)} URLs)")


if __name__ == "__main__":
    main()
