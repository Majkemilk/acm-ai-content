#!/usr/bin/env python3
"""
Reconstruct missing article source files in content/articles/ from rendered HTML
in public/articles/. No API calls; local file read/write only.
Run from project root: python scripts/import_from_public.py [--limit N] [--dry-run]
"""

import argparse
import re
from datetime import date
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_SCRIPTS_DIR))

from content_index import load_config  # noqa: E402

PUBLIC_ARTICLES = _PROJECT_ROOT / "public" / "articles"
CONTENT_ARTICLES = _PROJECT_ROOT / "content" / "articles"
CONFIG_PATH = _PROJECT_ROOT / "content" / "config.yaml"

DEFAULT_CATEGORY = "ai-marketing-automation"

# Patterns for stripping injected blocks from article body
META_BLOCK_RE = re.compile(
    r'<div class="flex flex-wrap items-center gap-3[^>]*>.*?</div>',
    re.DOTALL,
)
READ_NEXT_RE = re.compile(
    r'<section class="bg-gray-50[^"]*">.*?Read Next:.*?</section>',
    re.DOTALL | re.IGNORECASE,
)
DISCLOSURE_RE = re.compile(
    r'<div class="mt-8 p-4 bg-yellow-50[^"]*">.*?</div>\s*$',
    re.DOTALL,
)
ARTICLE_BODY_RE = re.compile(
    r'<article\s+class="article-body"[^>]*>(.*?)</article>',
    re.DOTALL,
)
TITLE_RE = re.compile(r"<title>\s*(.*?)\s*</title>", re.DOTALL | re.IGNORECASE)
HUB_LINK_RE = re.compile(r'href="/hubs/([^/"]+)/"')
UPDATED_DATE_RE = re.compile(r"Updated:\s*(\d{4}-\d{2}-\d{2})")


def _get_missing_slugs(limit: int | None) -> list[str]:
    """Return list of slugs that exist in public/articles/ but not in content/articles/."""
    if not PUBLIC_ARTICLES.exists():
        return []
    missing = []
    for path in sorted(PUBLIC_ARTICLES.iterdir()):
        if not path.is_dir():
            continue
        slug = path.name
        md_file = CONTENT_ARTICLES / f"{slug}.md"
        html_file = CONTENT_ARTICLES / f"{slug}.html"
        if md_file.exists() or html_file.exists():
            continue
        missing.append(slug)
        if limit is not None and len(missing) >= limit:
            break
    return missing


def _extract_article_body(html: str) -> str | None:
    """Extract content inside <article class="article-body">...</article>. Return None if not found."""
    m = ARTICLE_BODY_RE.search(html)
    if not m:
        return None
    body = m.group(1).strip()
    # Remove meta block (category badge, date, reading time)
    body = META_BLOCK_RE.sub("", body, count=1).strip()
    # Remove Read Next section
    body = READ_NEXT_RE.sub("", body).strip()
    # Remove disclosure box (at end)
    body = DISCLOSURE_RE.sub("", body).strip()
    return body


def _extract_title(html: str) -> str:
    """Extract title from <title> tag; strip ' - Flowtaro'."""
    m = TITLE_RE.search(html)
    if not m:
        return ""
    title = m.group(1).strip()
    if title.endswith(" - Flowtaro"):
        title = title[: -len(" - Flowtaro")].strip()
    return title


def _extract_category(html: str, default: str) -> str:
    """Extract category from first hub link in content."""
    m = HUB_LINK_RE.search(html)
    if m:
        return m.group(1).strip()
    return default


def _extract_updated_date(html: str, slug: str) -> str:
    """Extract 'Updated: YYYY-MM-DD' from meta block; else use slug prefix or today."""
    m = UPDATED_DATE_RE.search(html)
    if m:
        return m.group(1).strip()
    # Slug often starts with date: 2026-02-18-...
    if len(slug) >= 10 and slug[4] == "-" and slug[7] == "-":
        return slug[:10]
    return date.today().isoformat()


def _infer_content_type(title: str) -> str:
    """Infer content_type from title."""
    t = title.strip()
    if t.startswith("How to"):
        return "how-to"
    if t.startswith("Guide to"):
        return "guide"
    if t.startswith("Best "):
        return "best"
    if "Comparison" in t or " vs " in t or " versus " in t:
        return "comparison"
    return "guide"


def _slug_to_primary_keyword(slug: str) -> str:
    """Derive primary_keyword from slug (hyphens to spaces, lowercase). Strip date prefix if present."""
    s = slug.strip()
    # Strip leading YYYY-MM-DD-
    if len(s) > 10 and s[4] == "-" and s[7] == "-" and s[10] == "-":
        s = s[11:]
    return s.replace("-", " ").strip().lower()


def _build_frontmatter_comment(
    title: str,
    slug: str,
    category: str,
    last_updated: str,
    content_type: str,
    primary_keyword: str,
) -> str:
    """Build HTML comment frontmatter as in content/articles/*.html."""
    lines = [
        "<!--",
        f'title: "{_escape_quotes(title)}"',
        'content_type: "{}"'.format(content_type),
        f'category: "{_escape_quotes(category)}"',
        f'primary_keyword: "{_escape_quotes(primary_keyword)}"',
        'primary_tool: ""',
        'secondary_tool: ""',
        f'last_updated: "{last_updated}"',
        'status: "filled"',
        f'slug: "{slug}"',
        "-->",
    ]
    return "\n".join(lines) + "\n\n"


def _escape_quotes(s: str) -> str:
    """Escape double quotes for frontmatter value."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def process_slug(slug: str, config: dict, dry_run: bool) -> bool:
    """
    Read public/articles/<slug>/index.html, extract body and metadata,
    write content/articles/<slug>.html. Return True on success.
    """
    index_path = PUBLIC_ARTICLES / slug / "index.html"
    if not index_path.exists():
        print(f"  Skip {slug}: index.html not found")
        return False
    try:
        html = index_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  Skip {slug}: read failed — {e}")
        return False

    body = _extract_article_body(html)
    if body is None:
        print(f"  Warning {slug}: <article class=\"article-body\"> not found; skipping")
        return False

    default_cat = (config.get("production_category") or DEFAULT_CATEGORY).strip()
    title = _extract_title(html)
    if not title:
        title = slug.replace("-", " ").title()
    category = _extract_category(html, default_cat)
    last_updated = _extract_updated_date(html, slug)
    content_type = _infer_content_type(title)
    primary_keyword = _slug_to_primary_keyword(slug)

    frontmatter = _build_frontmatter_comment(
        title=title,
        slug=slug,
        category=category,
        last_updated=last_updated,
        content_type=content_type,
        primary_keyword=primary_keyword,
    )
    out_content = frontmatter + body

    out_path = CONTENT_ARTICLES / f"{slug}.html"
    if dry_run:
        print(f"  Would write {out_path.relative_to(_PROJECT_ROOT)} ({len(body)} chars body)")
        return True
    try:
        CONTENT_ARTICLES.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_content, encoding="utf-8")
    except OSError as e:
        print(f"  Skip {slug}: write failed — {e}")
        return False
    print(f"  Wrote {out_path.name}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruct missing article sources in content/articles/ from public/articles/."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N missing articles (for testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; only report what would be done.",
    )
    args = parser.parse_args()

    missing = _get_missing_slugs(args.limit)
    if not missing:
        print("No missing articles found (every public/articles/* has a source in content/articles/).")
        return
    print(f"Found {len(missing)} missing article(s) to import.")
    if args.limit:
        print(f"(Limited to {args.limit})")
    if args.dry_run:
        print("(Dry run: no files will be written)")

    config = load_config(CONFIG_PATH)
    ok = 0
    for slug in missing:
        if process_slug(slug, config, args.dry_run):
            ok += 1
    print(f"\nDone: {ok}/{len(missing)} processed successfully.")


if __name__ == "__main__":
    main()
