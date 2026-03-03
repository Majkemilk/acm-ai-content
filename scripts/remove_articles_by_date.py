#!/usr/bin/env python3
"""
Remove articles and skeletons by date or date range (Flowtaro-safe way):
- content/articles: move matching files to content/articles_archive/
- queue.yaml: remove entries that match those stems
- use_cases.yaml: set status to "discarded" for use cases corresponding to removed queue entries
- public/articles: remove directories for those stems

Modes:
- Single date: --date YYYY-MM-DD
- Date range: --date-from YYYY-MM-DD --date-to YYYY-MM-DD
- Optional: --stems "stem1,stem2,..." to restrict to selected stems (within the date range)
- --list-stems: only output stems one per line (for UI); use with --date or --date-from/--date-to

Default date: today. Use --dry-run (default when not --confirm) to preview.

Run from project root: python scripts/remove_articles_by_date.py [--date YYYY-MM-DD] [--date-from YYYY-MM-DD --date-to YYYY-MM-DD] [--stems "s1,s2"] [--list-stems] [--dry-run] [--confirm]
"""
import argparse
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = PROJECT_ROOT / "content"
ARTICLES_DIR = CONTENT_DIR / "articles"
ARCHIVE_DIR = CONTENT_DIR / "articles_archive"
QUEUE_PATH = CONTENT_DIR / "queue.yaml"
USE_CASES_PATH = CONTENT_DIR / "use_cases.yaml"
PUBLIC_ARTICLES_DIR = PROJECT_ROOT / "public" / "articles"

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from generate_queue import (
    load_existing_queue,
    save_queue,
    load_use_cases,
    _save_use_cases,
    title_for_entry,
)
from generate_articles import slug_from_keyword


def _stem_to_queue_rest(stem: str) -> str:
    """Part of stem after date prefix (YYYY-MM-DD-) for matching to queue."""
    parts = stem.split("-", 3)
    return parts[-1] if len(parts) == 4 else stem


def _queue_item_expected_rest(item: dict) -> str:
    """Expected rest (slug or slug.audience_XXX) for this queue item."""
    slug = slug_from_keyword(item.get("primary_keyword") or "")
    aud = (item.get("audience_type") or "").strip()
    return f"{slug}.audience_{aud}" if aud else slug


def _find_queue_index_by_stem(queue_items: list, stem: str) -> int | None:
    rest = _stem_to_queue_rest(stem)
    for i, item in enumerate(queue_items):
        if _queue_item_expected_rest(item) == rest:
            return i
    return None


def _find_use_case_index_by_queue_entry(use_cases: list, queue_item: dict) -> int | None:
    title = (queue_item.get("title") or "").strip()
    cat = (queue_item.get("category_slug") or "").strip()
    for i, uc in enumerate(use_cases):
        uc_title = title_for_entry(uc.get("problem") or "", uc.get("content_type") or "")
        uc_cat = (uc.get("category_slug") or "").strip()
        if uc_title == title and uc_cat == cat:
            return i
    return None


def get_stems_for_date(articles_dir: Path, date_str: str) -> list[str]:
    """Return unique stems of files in articles_dir whose stem starts with date_str (e.g. 2026-02-20)."""
    prefix = f"{date_str}-"
    stems: set[str] = set()
    if not articles_dir.exists():
        return []
    for path in articles_dir.iterdir():
        if not path.is_file() or path.suffix not in (".md", ".html"):
            continue
        if path.stem.startswith(prefix):
            stems.add(path.stem)
    return sorted(stems)


def get_stems_for_date_range(articles_dir: Path, date_from: str, date_to: str) -> list[str]:
    """Return unique stems for all dates in [date_from, date_to] inclusive. Dates as YYYY-MM-DD."""
    from datetime import datetime, timedelta
    start = datetime.strptime(date_from.strip()[:10], "%Y-%m-%d").date()
    end = datetime.strptime(date_to.strip()[:10], "%Y-%m-%d").date()
    if start > end:
        start, end = end, start
    all_stems: set[str] = set()
    d = start
    while d <= end:
        all_stems.update(get_stems_for_date(articles_dir, d.isoformat()))
        d += timedelta(days=1)
    return sorted(all_stems)


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


def run(
    *,
    date_str: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    stems_include: list[str] | None = None,
    dry_run: bool = True,
    confirm: bool = False,
    list_stems_only: bool = False,
) -> tuple[list[str], list[Path], list[str], str]:
    """
    Find articles by date(s) or by selected stems, optionally archive content, update queue/use_cases, remove public dirs.
    Returns (stems, content_files, public_slugs, message).
    When list_stems_only=True, message is one stem per line (for UI).
    """
    stems: list[str] = []
    if stems_include:
        stems = sorted(set(s.strip() for s in stems_include if s and s.strip()))
    elif date_from and date_to:
        stems = get_stems_for_date_range(ARTICLES_DIR, date_from, date_to)
    elif date_str:
        stems = get_stems_for_date(ARTICLES_DIR, date_str)
    else:
        stems = []

    content_files = get_content_files_for_stems(ARTICLES_DIR, stems) if stems else []
    public_slugs: list[str] = []
    if PUBLIC_ARTICLES_DIR.exists():
        public_slugs = [s for s in stems if (PUBLIC_ARTICLES_DIR / s).is_dir()]

    if list_stems_only:
        return stems, content_files, public_slugs, "\n".join(stems)

    range_label = f"{date_from} to {date_to}" if (date_from and date_to) else (date_str or "selected")
    lines: list[str] = []
    lines.append(f"Remove articles: {range_label}")
    lines.append(f"  Stems (content): {len(stems)}")
    for s in stems:
        files_for_stem = [f for f in content_files if f.stem == s]
        lines.append(f"    - {s} -> {[f.name for f in files_for_stem]}")
    lines.append(f"  Public dirs to remove: {len(public_slugs)}")
    for slug in public_slugs:
        lines.append(f"    - public/articles/{slug}/")
    lines.append("")

    if not confirm or dry_run:
        return stems, content_files, public_slugs, "\n".join(lines)

    # Load queue and use_cases
    queue_items = load_existing_queue(QUEUE_PATH)
    use_cases = load_use_cases(USE_CASES_PATH)

    # Queue indices to remove (by stem)
    to_remove_queue: set[int] = set()
    for stem in stems:
        idx = _find_queue_index_by_stem(queue_items, stem)
        if idx is not None:
            to_remove_queue.add(idx)

    removed_entries = [queue_items[i] for i in sorted(to_remove_queue)]
    queue_new = [e for i, e in enumerate(queue_items) if i not in to_remove_queue]

    # Use cases: set discarded for removed queue entries
    discarded_count = 0
    for entry in removed_entries:
        uc_idx = _find_use_case_index_by_queue_entry(use_cases, entry)
        if uc_idx is not None:
            use_cases[uc_idx]["status"] = "discarded"
            discarded_count += 1

    errors: list[str] = []

    # 1. Archive content files
    if content_files:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for path in content_files:
            try:
                dest = ARCHIVE_DIR / path.name
                shutil.move(str(path), str(dest))
                lines.append(f"  Archived: {path.name} -> content/articles_archive/")
            except Exception as e:
                errors.append(f"  Failed archive {path.name}: {e}")

    # 2. Save queue and use_cases
    try:
        save_queue(QUEUE_PATH, queue_new)
        lines.append(f"  Queue: removed {len(removed_entries)} entry(ies).")
        _save_use_cases(USE_CASES_PATH, use_cases)
        lines.append(f"  Use cases: marked {discarded_count} as discarded.")
    except Exception as e:
        errors.append(f"  Failed save queue/use_cases: {e}")

    # 3. Remove public dirs
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
    return stems, content_files, public_slugs, "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Remove articles and skeletons by date or date range (archive content, update queue and use_cases, remove public dirs)."
    )
    ap.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Single date (default: today if no range given).",
    )
    ap.add_argument("--date-from", metavar="YYYY-MM-DD", help="Start of date range (use with --date-to).")
    ap.add_argument("--date-to", metavar="YYYY-MM-DD", help="End of date range (use with --date-from).")
    ap.add_argument("--stems", metavar="STEM1,STEM2", help="Comma-separated stems to remove (optional; within date range).")
    ap.add_argument("--list-stems", action="store_true", help="Only output stems one per line (for UI).")
    ap.add_argument("--dry-run", action="store_true", help="Only print what would be done (default if --confirm not set).")
    ap.add_argument("--confirm", action="store_true", help="Perform archive, queue/use_cases update, and public removal.")
    args = ap.parse_args()

    date_str = (args.date or "").strip()[:10] if args.date else None
    date_from = (args.date_from or "").strip()[:10] if args.date_from else None
    date_to = (args.date_to or "").strip()[:10] if args.date_to else None
    stems_include = [s.strip() for s in (args.stems or "").split(",") if s.strip()] or None

    if args.list_stems:
        if date_from and date_to:
            try:
                datetime.strptime(date_from, "%Y-%m-%d")
                datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                print("Error: --date-from and --date-to must be YYYY-MM-DD.", file=sys.stderr)
                sys.exit(1)
            stems, _, _, msg = run(date_from=date_from, date_to=date_to, list_stems_only=True)
        elif date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                print("Error: --date must be YYYY-MM-DD.", file=sys.stderr)
                sys.exit(1)
            stems, _, _, msg = run(date_str=date_str, list_stems_only=True)
        else:
            date_str = date.today().isoformat()
            stems, _, _, msg = run(date_str=date_str, list_stems_only=True)
        print(msg)
        return

    if not date_str and not (date_from and date_to) and not stems_include:
        date_str = date.today().isoformat()
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            print("Error: --date must be YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)
    if date_from or date_to:
        if not date_from or not date_to:
            print("Error: use both --date-from and --date-to for a range.", file=sys.stderr)
            sys.exit(1)
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
            datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            print("Error: --date-from and --date-to must be YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

    dry_run = not args.confirm
    stems, content_files, public_slugs, msg = run(
        date_str=date_str,
        date_from=date_from,
        date_to=date_to,
        stems_include=stems_include,
        dry_run=dry_run,
        confirm=args.confirm,
    )
    print(msg)

    if not stems and not content_files:
        print("No articles found for the given date(s) or selection.")
        return

    if args.confirm and not dry_run and (content_files or public_slugs):
        print("You may run generate_hubs, render_site, generate_sitemap if you need to refresh the live site.")


if __name__ == "__main__":
    main()
