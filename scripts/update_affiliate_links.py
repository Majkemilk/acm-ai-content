#!/usr/bin/env python3
"""
Update external links in content/articles to use affiliate URLs from affiliate_tools.yaml.
Finds links that point to the same base URL as a tool (scheme+host+path, no query/fragment)
and replaces them with the tool's affiliate_link when different (e.g. add ?via=).
Default: dry-run (report only). Use --write to modify files (with optional .bak backup).
See docs/proposal_affiliate_links_update_script.md for workflow and design.
"""

import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
AFFILIATE_TOOLS_PATH = PROJECT_ROOT / "content" / "affiliate_tools.yaml"

# External links: markdown ](https?://...) and HTML href="https?://..."
MD_LINK_PATTERN = re.compile(r"\]\((https?://[^)\s]+)\)")
HTML_HREF_PATTERN = re.compile(r'href="(https?://[^"]+)"')


def _normalize_base(url: str) -> str:
    """Return scheme + netloc + path (no query, no fragment). Lowercase host; path without trailing slash (root stays /)."""
    try:
        p = urlparse(url.strip())
        if not p.scheme or not p.netloc:
            return ""
        scheme = p.scheme.lower()
        netloc = p.netloc.lower()
        path = (p.path or "/").rstrip("/") or "/"
        return urlunparse((scheme, netloc, path, "", "", ""))
    except Exception:
        return ""


def _load_affiliate_tools(path: Path) -> list[tuple[str, str]]:
    """Load (name, affiliate_link) from YAML. Stdlib only."""
    if not path.exists():
        return []

    def _val(s: str) -> str:
        s = (s or "").strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1].replace('\\"', '"').strip()
        return s

    text = path.read_text(encoding="utf-8")
    items: list[tuple[str, str]] = []
    in_tools = False
    current_name = ""
    current_url = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped == "tools:":
            in_tools = True
            continue
        if not in_tools:
            continue
        if stripped.startswith("- "):
            if current_name and current_url:
                items.append((current_name, current_url))
            current_name = ""
            current_url = ""
            part = stripped[2:].strip()
            kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", part)
            if kv:
                k, v = kv.group(1), _val(kv.group(2))
                if k == "name":
                    current_name = v
                elif k == "affiliate_link":
                    current_url = v
            continue
        kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", stripped)
        if kv:
            k, v = kv.group(1), _val(kv.group(2))
            if k == "name":
                current_name = v
            elif k == "affiliate_link":
                current_url = v
    if current_name and current_url:
        items.append((current_name, current_url))
    return items


def _build_base_to_affiliate(tools: list[tuple[str, str]]) -> dict[str, tuple[str, str]]:
    """Map base URL -> (name, full_affiliate_link). First tool wins if same base."""
    out: dict[str, tuple[str, str]] = {}
    for name, url in tools:
        base = _normalize_base(url)
        if base and base not in out:
            out[base] = (name, url)
    return out


def _find_replacements_in_text(
    content: str, base_to_affiliate: dict[str, tuple[str, str]], is_html: bool
) -> list[tuple[str, str, str]]:
    """Return list of (old_url, new_url, tool_name) to replace. Order by length descending so we replace longest first."""
    pattern = HTML_HREF_PATTERN if is_html else MD_LINK_PATTERN
    replacements: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in pattern.finditer(content):
        full_match = m.group(0)
        if is_html:
            url = m.group(1)
        else:
            url = m.group(1)
        base = _normalize_base(url)
        if not base or base not in base_to_affiliate:
            continue
        name, affiliate_url = base_to_affiliate[base]
        if url.strip() == affiliate_url.strip():
            continue
        key = (url, affiliate_url)
        if key in seen:
            continue
        seen.add(key)
        replacements.append((url, affiliate_url, name))
    return replacements


def _apply_replacements(content: str, replacements: list[tuple[str, str, str]]) -> str:
    """Replace all occurrences of each old_url with new_url. Dedupe by (old, new) to avoid redundant work."""
    seen: set[tuple[str, str]] = set()
    for old_url, new_url, _ in replacements:
        key = (old_url, new_url)
        if key in seen:
            continue
        seen.add(key)
        content = content.replace(old_url, new_url)
    return content


def scan_and_report(
    articles_dir: Path, affiliate_path: Path, write: bool = False, backup: bool = True
) -> list[tuple[Path, list[tuple[str, str, str]]]]:
    """
    Scan all .md and .html in articles_dir; for each file compute list of (old_url, new_url, tool_name).
    If write=True, apply replacements and save (with .bak if backup=True).
    Returns list of (path, replacements) for files that had at least one replacement.
    """
    tools = _load_affiliate_tools(affiliate_path)
    base_to_affiliate = _build_base_to_affiliate(tools)
    if not base_to_affiliate:
        return []

    updated: list[tuple[Path, list[tuple[str, str, str]]]] = []
    for ext in ("*.md", "*.html"):
        for path in sorted(articles_dir.glob(ext)):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            is_html = path.suffix.lower() == ".html"
            replacements = _find_replacements_in_text(content, base_to_affiliate, is_html)
            if not replacements:
                continue
            updated.append((path, replacements))
            if write:
                new_content = _apply_replacements(content, replacements)
                if backup:
                    backup_path = path.with_suffix(path.suffix + ".bak")
                    backup_path.write_text(content, encoding="utf-8")
                path.write_text(new_content, encoding="utf-8")
    return updated


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Update external links in articles to affiliate URLs from affiliate_tools.yaml."
    )
    parser.add_argument(
        "--articles-dir",
        type=Path,
        default=ARTICLES_DIR,
        help=f"Articles directory (default: content/articles)",
    )
    parser.add_argument(
        "--affiliate-file",
        type=Path,
        default=AFFILIATE_TOOLS_PATH,
        help="Path to affiliate_tools.yaml",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply changes to files (default: dry-run, report only)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak backup when --write",
    )
    args = parser.parse_args()
    articles_dir = args.articles_dir.resolve()
    affiliate_path = args.affiliate_file.resolve()
    if not articles_dir.exists():
        print(f"Articles dir not found: {articles_dir}")
        return
    if not affiliate_path.exists():
        print(f"Affiliate tools file not found: {affiliate_path}")
        return

    updated = scan_and_report(
        articles_dir, affiliate_path, write=args.write, backup=not args.no_backup
    )
    if not updated:
        print("No links to update.")
        return
    print(f"Files with link updates: {len(updated)}")
    for path, replacements in updated:
        try:
            rel = path.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = path
        print(f"\n  {rel}")
        for old_url, new_url, name in replacements:
            print(f"    -> {name}")
            print(f"       was: {old_url[:80]}{'...' if len(old_url) > 80 else ''}")
            print(f"       now: {new_url[:80]}{'...' if len(new_url) > 80 else ''}")
    if args.write:
        print(f"\nWrote {len(updated)} file(s). Run render_site.py then deploy public/ to publish.")
    else:
        print("\nDry-run. Use --write to apply changes.")


if __name__ == "__main__":
    main()
