#!/usr/bin/env python3
"""
Refresh older articles by re-running the AI fill and updating last_updated.
Identifies articles older than a threshold (default 90 days), runs fill_articles
with --force and quality gate, then optionally runs hubs/sitemap/render.
Run from project root: python scripts/refresh_articles.py [--days N] [--dry-run] [--no-render] [--limit M]
"""

import argparse
from collections import Counter
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
ARTICLES_DIR = _PROJECT_ROOT / "content" / "articles"
BACKUPS_DIR = _PROJECT_ROOT / "content" / "backups"
ERROR_LOG = _PROJECT_ROOT / "logs" / "errors.log"
FAILED_LIST_PATH = _PROJECT_ROOT / "logs" / "last_refresh_failed.txt"

_PROMPT2_PLACEHOLDER_RE = re.compile(r'PROMPT2_PLACEHOLDER')


def _get_recent_errors_for_slug(stem: str, max_lines: int = 3) -> list[str]:
    """Return the last max_lines from logs/errors.log that mention this article stem (slug)."""
    if not ERROR_LOG.exists():
        return []
    try:
        text = ERROR_LOG.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [ln.strip() for ln in text.splitlines() if stem in ln and "[ERROR]" in ln]
    return lines[-max_lines:] if len(lines) > max_lines else lines


def _get_frontmatter_block(content: str) -> str | None:
    """Return the frontmatter block (between first --- and second ---) or None."""
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    return content[3:end]


def _get_status(content: str) -> str | None:
    """Extract status from frontmatter. Returns value or None."""
    block = _get_frontmatter_block(content)
    if not block:
        return None
    for line in block.split("\n"):
        m = re.match(r"^status\s*:\s*(.+)$", line.strip(), re.I)
        if m:
            return m.group(1).strip().strip('"\'')
    return None


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
    """Replace last_updated in frontmatter with today, or add it if missing. Returns True if updated."""
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
        # Key missing: add last_updated so the article drops out of date range on next run
        if re.search(r"^\s*last_updated\s*:", block, re.IGNORECASE | re.MULTILINE):
            return False
        new_block = block.rstrip() + "\n" + f'last_updated: "{today}"' + "\n"
    new_block_stripped = new_block.strip("\n")
    new_content = "---\n" + new_block_stripped + "\n---" + content[content.find("\n---", 3) + 4:]
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


def find_articles_younger_than(articles_dir: Path, max_days: int, limit: int = 0) -> list[Path]:
    """Return list of article paths whose last_updated is at most `max_days` ago. 0 = today only. Sorted by path."""
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
        if (today - last).days <= max_days:
            candidates.append((last, path))
    candidates.sort(key=lambda x: x[0], reverse=True)
    paths = [p for _, p in candidates]
    if limit > 0:
        paths = paths[:limit]
    return paths


def find_articles_in_date_range(
    articles_dir: Path, from_date: date, to_date: date, limit: int = 0
) -> list[Path]:
    """Return list of article paths whose last_updated is in [from_date, to_date] (inclusive).
    Also includes articles with status 'blocked' and last_updated == today (so failed/blocked
    articles that got today's date are still retried when re-running the same range)."""
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
        in_range = from_date <= last <= to_date
        status = _get_status(content)
        blocked_today = status == "blocked" and last == today
        if in_range or blocked_today:
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
        help="Refresh articles with last_updated older than N days (default: 90). Ignored when --max-days is set.",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=None,
        metavar="N",
        help="Refresh articles with last_updated at most N days ago (0 = today only). When set (0-6), overrides --days.",
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
    parser.add_argument(
        "--include-file",
        metavar="PATH",
        help="Only refresh articles whose stems appear in this file (one stem per line).",
    )
    parser.add_argument(
        "--block_on_fail",
        action="store_true",
        help="Set article status to 'blocked' if QA fails (passed to fill_articles.py).",
    )
    parser.add_argument(
        "--remap",
        action="store_true",
        help="Force AI to re-select tools even if already assigned (passed to fill_articles.py).",
    )
    parser.add_argument(
        "--quality_retries",
        type=int,
        default=2,
        metavar="N",
        help="Number of quality-gate retries (default: 2; passed to fill_articles.py).",
    )
    parser.add_argument(
        "--no-batch-backup",
        action="store_true",
        help="Skip batch backup of articles to content/backups/<timestamp>/ before refresh (default: backup is created).",
    )
    parser.add_argument(
        "--re-skeleton",
        action="store_true",
        dest="re_skeleton",
        help="Odswiez z nowym szkieletem: najpierw wygeneruj nowy szkielet z aktualnych szablonow (ten sam slug), potem wypelnij.",
    )
    parser.add_argument(
        "--from-date",
        dest="from_date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Refresh articles with last_updated on or after this date. Use with --to-date (range takes priority over --days/--max-days).",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Refresh articles with last_updated on or before this date. Use with --from-date.",
    )
    args = parser.parse_args()

    if not ARTICLES_DIR.exists():
        print("Error: Articles directory not found.")
        sys.exit(1)

    to_refresh: list[Path]
    filter_desc: str
    if args.from_date is not None and args.to_date is not None:
        try:
            from_d = datetime.strptime(args.from_date.strip()[:10], "%Y-%m-%d").date()
            to_d = datetime.strptime(args.to_date.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            print("Error: --from-date and --to-date must be YYYY-MM-DD.")
            sys.exit(1)
        if from_d > to_d:
            print("Error: --from-date must be <= --to-date.")
            sys.exit(1)
        to_refresh = find_articles_in_date_range(ARTICLES_DIR, from_d, to_d, args.limit)
        filter_desc = f"last_updated in range [{from_d.isoformat()}, {to_d.isoformat()}]"
    elif args.max_days is not None:
        to_refresh = find_articles_younger_than(ARTICLES_DIR, args.max_days, args.limit)
        filter_desc = f"younger than {args.max_days} day(s) (last_updated within last {args.max_days} days)"
    else:
        to_refresh = find_articles_older_than(ARTICLES_DIR, args.days, args.limit)
        filter_desc = f"older than {args.days} days"

    if args.include_file:
        try:
            include_stems = {
                line.strip() for line in Path(args.include_file).read_text(encoding="utf-8").splitlines() if line.strip()
            }
        except OSError as e:
            print(f"Error reading include file: {e}")
            sys.exit(1)
        to_refresh = [p for p in to_refresh if p.stem in include_stems]

    if args.dry_run:
        print(f"Articles with last_updated {filter_desc} (would refresh):")
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
        print(f"No articles to refresh ({filter_desc}).")
        return

    # Check API key before starting
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)

    # Batch backup (default: copy only files to be refreshed to content/backups/<timestamp>/)
    backup_dir: Path | None = None
    if not args.no_batch_backup:
        timestamp_str = datetime.now().strftime("%Y-%m-%dT%H%M%S")
        backup_dir = BACKUPS_DIR / timestamp_str
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            for path in to_refresh:
                if path.exists():
                    shutil.copy2(path, backup_dir / path.name)
                html_path = path.with_suffix(".html")
                if html_path.exists():
                    shutil.copy2(html_path, backup_dir / html_path.name)
            print(f"Batch backup: {len(to_refresh)} article(s) -> {backup_dir}")
        except OSError as e:
            print(f"Warning: batch backup failed - {e}. Continuing without backup.")

    today = date.today().isoformat()
    refreshed = 0
    failed = 0

    fill_script = _SCRIPTS_DIR / "fill_articles.py"
    if not fill_script.exists():
        print(f"Error: {fill_script} not found.")
        sys.exit(1)

    gen_articles_script = _SCRIPTS_DIR / "generate_articles.py"
    if args.re_skeleton and not gen_articles_script.exists():
        print(f"Error: {gen_articles_script} not found (required for --re-skeleton).")
        sys.exit(1)

    prompt2_pending: list[Path] = []  # articles that need --prompt2-only after refresh
    failed_stems: list[str] = []  # for logs/last_refresh_failed.txt (Option A)

    # R4: clear failure-reasons file so this run's fill_articles can append
    _failure_reasons_path = _PROJECT_ROOT / "logs" / "refresh_failure_reasons.txt"
    try:
        if _failure_reasons_path.exists():
            _failure_reasons_path.write_text("", encoding="utf-8")
    except OSError:
        pass

    print(f"FLOWTARO_PROGRESS_TOTAL: {len(to_refresh)}")
    for path in to_refresh:
        stem = path.stem
        if args.re_skeleton:
            r_sk = subprocess.run(
                [sys.executable, str(gen_articles_script), "--re-skeleton", str(path)],
                cwd=str(_PROJECT_ROOT),
            )
            if r_sk.returncode != 0:
                print(f"  Re-skeleton failed: {path.name} (exit code {r_sk.returncode})")
                failed += 1
                failed_stems.append(stem)
                print(f"FLOWTARO_PROGRESS: {refreshed + failed}")
                continue
        cmd = [
            sys.executable,
            str(fill_script),
            "--write",
            "--force",
            "--html",
            "--slug_contains", stem,
            "--limit", "1",
            "--quality_gate",
            "--quality_retries", str(args.quality_retries),
            "--min-words-override", "650",
        ]
        if args.block_on_fail:
            cmd.append("--block_on_fail")
        if args.remap:
            cmd.append("--remap")
        result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        if result.returncode != 0:
            print(f"  Refresh failed: {path.name} (exit code {result.returncode})")
            recent = _get_recent_errors_for_slug(stem, max_lines=3)
            if recent:
                for line in recent:
                    # Avoid UnicodeEncodeError on Windows console (cp1250)
                    safe = line.encode("ascii", "replace").decode("ascii")
                    print(f"    errors.log: {safe}")
            elif result.returncode == 2:
                print(f"    (Exit 2 = QA/quality/API failure; check logs/errors.log or run fill_articles.py with --slug_contains {stem!r} to see details.)")
            failed += 1
            failed_stems.append(stem)
            print(f"FLOWTARO_PROGRESS: {refreshed + failed}")
            continue
        html_path = path.with_suffix(".html")
        if not html_path.exists():
            print(f"  Refresh failed: {path.name} (fill completed but .html not produced - likely QA failure)")
            for line in _get_recent_errors_for_slug(stem, max_lines=3):
                safe = line.encode("ascii", "replace").decode("ascii")
                print(f"    errors.log: {safe}")
            failed += 1
            failed_stems.append(stem)
            print(f"FLOWTARO_PROGRESS: {refreshed + failed}")
            continue
        if _update_last_updated_in_file(path, today):
            print(f"  Refreshed and updated last_updated: {path.name}")
        else:
            print(f"  Refreshed (last_updated unchanged): {path.name}")
        refreshed += 1
        print(f"FLOWTARO_PROGRESS: {refreshed + failed}")

        # Check if Prompt #2 placeholder remains — schedule --prompt2-only pass
        try:
            html_text = html_path.read_text(encoding="utf-8")
            if _PROMPT2_PLACEHOLDER_RE.search(html_text):
                prompt2_pending.append(path)
                print(f"  Note: [PROMPT2_PLACEHOLDER] detected in {html_path.name} - will run --prompt2-only")
        except OSError:
            pass

    # --- Prompt #2 fill pass for articles that still have placeholder ---
    if prompt2_pending:
        print(f"\nRunning --prompt2-only for {len(prompt2_pending)} article(s)...")
        p2_filled = 0
        p2_failed = 0
        for path in prompt2_pending:
            stem = path.stem
            cmd_p2 = [
                sys.executable,
                str(fill_script),
                "--write",
                "--prompt2-only",
                "--slug_contains", stem,
                "--limit", "1",
            ]
            r2 = subprocess.run(cmd_p2, cwd=str(_PROJECT_ROOT))
            if r2.returncode == 0:
                print(f"  Prompt #2 filled: {path.name}")
                p2_filled += 1
            else:
                print(f"  Prompt #2 fill failed: {path.name} (exit code {r2.returncode})")
                p2_failed += 1
        print(f"  Prompt #2 pass: filled={p2_filled}, failed={p2_failed}")

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

    # R4: failure breakdown from fill_articles appends (forbidden, word count, placeholders, etc.)
    if _failure_reasons_path.exists():
        try:
            lines = _failure_reasons_path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                categories: Counter[str] = Counter()
                for line in lines:
                    if "\t" not in line:
                        continue
                    _stem, reasons_str = line.split("\t", 1)
                    for part in reasons_str.split("; "):
                        part = part.strip()
                        if "forbidden pattern:" in part:
                            categories["forbidden: " + part.split("forbidden pattern:")[-1].strip()] += 1
                        elif "word count" in part:
                            categories["word count"] += 1
                        elif "bracket placeholders" in part or "bracket placeholder" in part:
                            categories["bracket placeholders"] += 1
                        elif "mustache" in part:
                            categories["mustache"] += 1
                        elif "H2 headings missing" in part or "headings missing" in part:
                            categories["missing H2"] += 1
                        elif "missing deterministic" in part or "Quality gate fail" in part:
                            categories["deterministic/quality"] += 1
                        elif part:
                            categories["other"] += 1
                if categories:
                    print()
                    print("Failure breakdown (by reason):")
                    for reason, count in categories.most_common():
                        print(f"  {count:3d}  {reason}")
        except OSError:
            pass

    # Option A: write failed stems for "Ponow tylko nieudane" (retry without --re-skeleton)
    try:
        logs_dir = _PROJECT_ROOT / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        if failed_stems:
            FAILED_LIST_PATH.write_text("\n".join(failed_stems) + "\n", encoding="utf-8")
        elif FAILED_LIST_PATH.exists():
            FAILED_LIST_PATH.unlink()
    except OSError:
        pass

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
