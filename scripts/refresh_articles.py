#!/usr/bin/env python3
"""
Refresh older articles by re-running the AI fill and updating last_updated.
Identifies articles older than a threshold (default 90 days), runs fill_articles
with --force and quality gate, then optionally runs hubs/sitemap/render.
Run from project root: python scripts/refresh_articles.py [--days N] [--dry-run] [--no-render] [--limit M]
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
ARTICLES_DIR = _PROJECT_ROOT / "content" / "articles"


def _get_frontmatter_block(content: str) -> str | None:
    """Return the frontmatter block (between first --- and second ---) or None."""
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    return content[3:end]


def _get_last_updated(path: Path, content: str) -> date | None:
    """Extract last_updated date from frontmatter or filename (YYYY-MM-DD-...). Returns date or None."""
    block = _get_frontmatter_block(content)
    if block:
        for line in block.split("\n"):
            m = re.match(r"^last_updated\s*:\s*(.+)$", line.strip(), re.I)
            if m:
                raw = m.group(1).strip().strip('"\'')
                try:
                    return datetime.strptime(raw[:10], "%Y-%m-%d").date()
                except ValueError:
                    pass
    stem = path.stem
    if len(stem) >= 10 and stem[4] == "-" and stem[7] == "-":
        try:
            return datetime.strptime(stem[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _update_last_updated_in_file(path: Path, today: str) -> bool:
    """Replace last_updated in frontmatter with today. Returns True if updated."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    block = _get_frontmatter_block(content)
    if not block:
        return False
    new_block = re.sub(
        r"^last_updated\s*:\s*.*$",
        f'last_updated: "{today}"',
        block,
        count=1,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if new_block == block:
        return False
    new_content = "---\n" + new_block + "\n---" + content[content.find("\n---", 3) + 4:]
    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError:
        return False
    return True


def find_articles_older_than(articles_dir: Path, days: int, limit: int = 0) -> list[Path]:
    """Return list of article paths whose last_updated is older than `days`. Sorted by path. Optional limit."""
    if not articles_dir.exists():
        return []
    today = date.today()
    candidates: list[tuple[date, Path]] = []
    for path in sorted(articles_dir.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        last = _get_last_updated(path, content)
        if last is None:
            continue
        if (today - last).days >= days:
            candidates.append((last, path))
    candidates.sort(key=lambda x: x[0])
    paths = [p for _, p in candidates]
    if limit > 0:
        paths = paths[:limit]
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh articles older than N days by re-filling with AI and updating last_updated.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        metavar="N",
        help="Refresh articles with last_updated older than N days (default: 90).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list articles that would be refreshed.",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Skip running generate_hubs, generate_sitemap, and render_site after refresh.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="M",
        help="Limit number of articles to refresh (0 = no limit).",
    )
    args = parser.parse_args()

    if not ARTICLES_DIR.exists():
        print("Error: Articles directory not found.")
        sys.exit(1)

    to_refresh = find_articles_older_than(ARTICLES_DIR, args.days, args.limit)

    if args.dry_run:
        print(f"Articles with last_updated older than {args.days} days (would refresh):")
        if not to_refresh:
            print("  (none)")
        else:
            for path in to_refresh:
                try:
                    content = path.read_text(encoding="utf-8")
                    last = _get_last_updated(path, content)
                    last_str = last.isoformat() if last else "?"
                    print(f"  {path.name}  last_updated: {last_str}")
                except OSError:
                    print(f"  {path.name}  (could not read)")
        print(f"\nTotal: {len(to_refresh)} article(s).")
        return

    if not to_refresh:
        print("No articles to refresh (all are within the threshold).")
        return

    # Check API key before starting
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)

    today = date.today().isoformat()
    refreshed = 0
    failed = 0

    fill_script = _SCRIPTS_DIR / "fill_articles.py"
    if not fill_script.exists():
        print(f"Error: {fill_script} not found.")
        sys.exit(1)

    for path in to_refresh:
        stem = path.stem
        cmd = [
            sys.executable,
            str(fill_script),
            "--write",
            "--force",
            "--slug_contains", stem,
            "--limit", "1",
            "--quality_gate",
            "--quality_retries", "2",
        ]
        result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        if result.returncode != 0:
            print(f"  Refresh failed: {path.name} (exit code {result.returncode})")
            failed += 1
            continue
        if _update_last_updated_in_file(path, today):
            print(f"  Refreshed and updated last_updated: {path.name}")
        else:
            print(f"  Refreshed (last_updated unchanged): {path.name}")
        refreshed += 1

    if not args.no_render:
        for name in ("generate_hubs.py", "generate_sitemap.py", "render_site.py"):
            script = _SCRIPTS_DIR / name
            if not script.exists():
                print(f"Warning: {name} not found, skipping.")
                continue
            r = subprocess.run([sys.executable, str(script)], cwd=str(_PROJECT_ROOT))
            if r.returncode != 0:
                print(f"Warning: {name} exited with code {r.returncode}.")
            else:
                print(f"Ran {name}.")

    total_md = len(list(ARTICLES_DIR.glob("*.md")))
    skipped_up_to_date = total_md - len(to_refresh)

    print()
    print("Summary:")
    print(f"  Refreshed: {refreshed}")
    print(f"  Failed:    {failed}")
    print(f"  Skipped (up to date): {skipped_up_to_date}")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
