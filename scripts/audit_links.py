#!/usr/bin/env python3
"""
One-off audit of internal links in public/. Read-only.
Checks: <a href>, <link rel="stylesheet" href> in all HTML under public/.
Resolves paths against public/ as site root. Reports broken links and missing resources.
"""

from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = PROJECT_ROOT / "public"


class LinkCollector(HTMLParser):
    """Collect href from <a> and <link rel="stylesheet">."""

    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []  # (tag, href)

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and "href" in d:
            self.links.append(("a", d["href"].strip()))
        if tag == "link" and d.get("rel", "").strip().lower() == "stylesheet" and "href" in d:
            self.links.append(("link", d["href"].strip()))


def is_external(href: str) -> bool:
    if not href:
        return True
    h = href.strip().lower()
    return h.startswith("http://") or h.startswith("https://") or h.startswith("mailto:") or h.startswith("javascript:")


def path_without_fragment(href: str) -> str:
    i = href.find("#")
    return href[:i].strip() if i >= 0 else href.strip()


def resolve_target(html_path: Path, href: str, public_root: Path) -> Path | None:
    """Resolve href to a path under public_root. Returns None if external or invalid."""
    if not href or is_external(href):
        return None
    path_part = path_without_fragment(href).lstrip("/")
    if not path_part:
        return None
    if href.strip().startswith("/"):
        target = (public_root / path_part).resolve()
    else:
        target = (html_path.parent / path_part).resolve()
    try:
        target.relative_to(public_root.resolve())
    except ValueError:
        return None
    return target


def resource_exists(target: Path, public_root: Path) -> bool:
    """True if the target exists as a file or as a directory with index.html."""
    if target.exists():
        if target.is_file():
            return True
        if target.is_dir():
            return (target / "index.html").exists()
    # URL like /articles/slug/ -> no trailing slash in path_part, so target = public/articles/slug (may not exist as dir name without trailing slash)
    if (target / "index.html").exists():
        return True
    return False


def audit() -> None:
    public_root = PUBLIC_DIR.resolve()
    if not public_root.exists():
        print(f"ERROR: public directory not found: {public_root}")
        return

    broken: list[tuple[Path, str, Path]] = []  # (source_file, href, resolved_target)
    checked_internal = 0
    skipped_external = 0

    for html_path in sorted(public_root.rglob("*.html")):
        try:
            text = html_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  (skip read {html_path}: {e})")
            continue
        parser = LinkCollector()
        try:
            parser.feed(text)
        except Exception as e:
            print(f"  (skip parse {html_path}: {e})")
            continue
        rel_path = html_path.relative_to(public_root)
        for tag, href in parser.links:
            if is_external(href):
                skipped_external += 1
                continue
            target = resolve_target(html_path, href, public_root)
            if target is None:
                continue
            checked_internal += 1
            if not resource_exists(target, public_root):
                broken.append((html_path, href, target))

    # Report
    print("=" * 60)
    print("INTERNAL LINK AUDIT (public/ as site root)")
    print("=" * 60)
    print(f"  HTML files scanned: {len(list(public_root.rglob('*.html')))}")
    print(f"  Internal links checked: {checked_internal}")
    print(f"  External links skipped: {skipped_external}")
    print()

    if broken:
        print("BROKEN OR MISSING LINKS")
        print("-" * 60)
        for source, href, resolved in broken:
            rel_src = source.relative_to(public_root)
            print(f"  Source: {rel_src}")
            print(f"    href: {href}")
            try:
                r = resolved.relative_to(public_root)
            except ValueError:
                r = resolved
            print(f"    resolved: {r}")
            print()
        print(f"  Total broken: {len(broken)}")
    else:
        print("All checked internal links point to existing resources.")

    # Quick asset check
    assets_css = public_root / "assets" / "styles.css"
    print()
    if assets_css.exists():
        print("  /assets/styles.css: OK")
    else:
        print("  /assets/styles.css: MISSING")

    # robots/sitemap (linked from index)
    for name in ("robots.txt", "sitemap.xml"):
        p = public_root / name
        if p.exists():
            print(f"  /{name}: OK")
        else:
            print(f"  /{name}: MISSING (linked from index)")
    print("=" * 60)


if __name__ == "__main__":
    audit()
