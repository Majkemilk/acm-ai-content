#!/usr/bin/env python3
"""
Clean non-live articles only:
- content/articles: move files with status != "filled" to content/articles_archive/ (archive, not delete).
- public/articles: remove directories for slugs not in current production list (stale).

Run from project root: python scripts/clean_non_live_articles.py [--dry-run] [--confirm] [--archive] [--content-only | --public-only]
Default: --archive (for content). Without --confirm only prints what would be done.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Import after path setup
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from content_root import get_content_root_path
from content_index import (
    get_production_articles,
    _parse_frontmatter,
    _parse_html_frontmatter_from_comment,
)

# Set in main() from --content-root
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
PUBLIC_ARTICLES_DIR = PROJECT_ROOT / "public" / "articles"
ARCHIVE_DIR = PROJECT_ROOT / "content" / "articles_archive"


def _collect_content_stems_and_status(articles_dir: Path) -> dict[str, str]:
    """Return stem -> status (lowercase). One path per stem, .html wins over .md."""
    by_stem: dict[str, Path] = {}
    for path in articles_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix == ".md":
            by_stem.setdefault(path.stem, path)
        elif path.suffix == ".html":
            by_stem[path.stem] = path
    out: dict[str, str] = {}
    for path in by_stem.values():
        status = ""
        if path.suffix == ".html":
            try:
                meta = _parse_html_frontmatter_from_comment(path.read_text(encoding="utf-8"))
                if meta:
                    status = (meta.get("status") or "").strip().lower()
            except OSError:
                pass
        else:
            meta = _parse_frontmatter(path)
            if meta:
                status = (meta.get("status") or "").strip().lower()
        out[path.stem] = status
    return out


def get_non_live_content_stems(articles_dir: Path, production_slugs: set[str]) -> list[str]:
    """Stems in content/articles where status != 'filled' (or missing/invalid)."""
    stem_status = _collect_content_stems_and_status(articles_dir)
    return [s for s, st in stem_status.items() if st != "filled"]


def get_content_files_for_stems(articles_dir: Path, stems: list[str]) -> list[Path]:
    """All .md and .html files in articles_dir whose stem is in stems."""
    stems_set = set(stems)
    files: list[Path] = []
    for path in articles_dir.iterdir():
        if not path.is_file() or path.suffix not in (".md", ".html"):
            continue
        if path.stem in stems_set:
            files.append(path)
    return sorted(files, key=lambda p: p.name)


def get_stale_public_slugs(public_articles_dir: Path, production_slugs: set[str]) -> list[str]:
    """Slugs (directory names) in public/articles that are not in production."""
    if not public_articles_dir.exists():
        return []
    stale: list[str] = []
    for d in public_articles_dir.iterdir():
        if d.is_dir() and (d / "index.html").exists():
            if d.name not in production_slugs:
                stale.append(d.name)
    return sorted(stale)


def run(
    *,
    dry_run: bool = True,
    confirm: bool = False,
    archive: bool = True,
    content_only: bool = False,
    public_only: bool = False,
) -> tuple[list[str], list[str], list[Path], str]:
    """
    Compute and optionally perform clean. Returns (content_stems, public_slugs, content_files, message).
    If confirm and not dry_run: performs archive (content) and delete (public).
    """
    do_content = not public_only
    do_public = not content_only

    production = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
    production_slugs = {meta.get("slug") or path.stem for meta, path in production}

    content_stems: list[str] = []
    content_files: list[Path] = []
    if do_content and ARTICLES_DIR.exists():
        content_stems = get_non_live_content_stems(ARTICLES_DIR, production_slugs)
        content_files = get_content_files_for_stems(ARTICLES_DIR, content_stems)

    public_slugs: list[str] = []
    if do_public and PUBLIC_ARTICLES_DIR.exists():
        public_slugs = get_stale_public_slugs(PUBLIC_ARTICLES_DIR, production_slugs)

    lines: list[str] = []
    lines.append("Clean non-live articles")
    lines.append(f"  Production (live) count: {len(production_slugs)}")
    if do_content:
        lines.append(f"  Content: {len(content_stems)} non-live stem(s), {len(content_files)} file(s) to archive")
        for stem in content_stems:
            files_for_stem = [f for f in content_files if f.stem == stem]
            lines.append(f"    - {stem} -> {[f.name for f in files_for_stem]}")
    if do_public:
        lines.append(f"  Public: {len(public_slugs)} stale directory(ies) to remove")
        for slug in public_slugs:
            lines.append(f"    - public/articles/{slug}/")
    lines.append("")

    if not confirm or dry_run:
        return content_stems, public_slugs, content_files, "\n".join(lines)

    # Execute
    errors: list[str] = []
    if do_content and content_files and archive:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for path in content_files:
            try:
                dest = ARCHIVE_DIR / path.name
                shutil.move(str(path), str(dest))
                lines.append(f"  Archived: {path.name} -> content/articles_archive/")
            except Exception as e:
                errors.append(f"  Failed {path.name}: {e}")
    if do_public and public_slugs:
        for slug in public_slugs:
            d = PUBLIC_ARTICLES_DIR / slug
            try:
                if d.exists():
                    shutil.rmtree(d)
                    lines.append(f"  Removed: public/articles/{slug}/")
            except Exception as e:
                errors.append(f"  Failed public/articles/{slug}/: {e}")

    if errors:
        lines.append("Errors:")
        lines.extend(errors)
    else:
        lines.append("Done.")
    return content_stems, public_slugs, content_files, "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean non-live articles: archive content (status != filled), remove stale public dirs.")
    ap.add_argument("--content-root", default=os.environ.get("CONTENT_ROOT", "content"), help="Content root (content or content/pl)")
    ap.add_argument("--dry-run", action="store_true", help="Only print what would be done (default if --confirm not set)")
    ap.add_argument("--confirm", action="store_true", help="Perform archive and removal")
    ap.add_argument("--archive", action="store_true", default=True, help="Archive content files to content/articles_archive/ (default: True)")
    ap.add_argument("--no-archive", action="store_false", dest="archive", help="Do not archive; only list content (no move)")
    ap.add_argument("--content-only", action="store_true", help="Only process content/articles (do not touch public)")
    ap.add_argument("--public-only", action="store_true", help="Only remove stale public/articles dirs (do not touch content)")
    args = ap.parse_args()

    content_dir = get_content_root_path(PROJECT_ROOT, args.content_root)
    public_dir = PROJECT_ROOT / "public_pl" if args.content_root.strip().endswith("pl") else PROJECT_ROOT / "public"
    global CONFIG_PATH, ARTICLES_DIR, PUBLIC_ARTICLES_DIR, ARCHIVE_DIR
    CONFIG_PATH = content_dir / "config.yaml"
    ARTICLES_DIR = content_dir / "articles"
    PUBLIC_ARTICLES_DIR = public_dir / "articles"
    ARCHIVE_DIR = content_dir / "articles_archive"

    if args.content_only and args.public_only:
        print("Use at most one of --content-only and --public-only.", file=sys.stderr)
        sys.exit(1)

    dry_run = not args.confirm
    content_stems, public_slugs, content_files, msg = run(
        dry_run=dry_run,
        confirm=args.confirm,
        archive=args.archive,
        content_only=args.content_only,
        public_only=args.public_only,
    )
    print(msg)
    if args.confirm and not dry_run and (content_files or public_slugs):
        print("Run generate_hubs, render_site, generate_sitemap only if you also changed live articles; for non-live clean it is not required.")


if __name__ == "__main__":
    main()
