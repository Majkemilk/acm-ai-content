#!/usr/bin/env python3
"""
Flowtaro Monitor: dashboard-like overview of content pipeline health.
Shows article stats, queue status, API cost estimates, recent errors, last run times.
Run from project root: python scripts/monitor.py [--summary] [--reset-costs] [--days N]
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from content_index import get_production_articles, load_config  # noqa: E402

ARTICLES_DIR = _PROJECT_ROOT / "content" / "articles"
QUEUE_PATH = _PROJECT_ROOT / "content" / "queue.yaml"
CONFIG_PATH = _PROJECT_ROOT / "content" / "config.yaml"
LOGS_DIR = _PROJECT_ROOT / "logs"
ERROR_LOG = LOGS_DIR / "errors.log"
API_COSTS_PATH = LOGS_DIR / "api_costs.json"


def _is_tty() -> bool:
    """True if stdout is a TTY (for enabling colors)."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _color(code: str, text: str, use_color: bool) -> str:
    if not use_color:
        return text
    return f"\033[{code}m{text}\033[0m"


def _green(text: str, use_color: bool) -> str:
    return _color("32", text, use_color)


def _yellow(text: str, use_color: bool) -> str:
    return _color("33", text, use_color)


def _red(text: str, use_color: bool) -> str:
    return _color("31", text, use_color)


def _parse_frontmatter_from_content(content: str) -> dict:
    """Minimal frontmatter parse: return dict of key: value from first --- block."""
    out = {}
    if not content.startswith("---"):
        return out
    end = content.find("\n---", 3)
    if end == -1:
        return out
    for line in content[3:end].split("\n"):
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if m:
            raw = m.group(2).strip().strip('"\'')
            out[m.group(1)] = raw
    return out


def _load_queue_simple(path: Path) -> list[dict]:
    """Load queue as list of dicts (minimal parser)."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    text = path.read_text(encoding="utf-8").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [dict(x) for x in data]
    except json.JSONDecodeError:
        pass
    items = []
    for block in re.split(r"\n(?=- )", text):
        block = block.strip()
        if not block.startswith("- "):
            continue
        item = {}
        for line in block[2:].split("\n"):
            m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
            if m:
                v = m.group(2).strip().strip('"\'')
                item[m.group(1)] = v
        if item:
            items.append(item)
    return items


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _load_cost_data() -> dict:
    if not API_COSTS_PATH.exists():
        return {}
    try:
        return json.loads(API_COSTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def collect_article_stats(articles_dir: Path, config: dict) -> dict:
    """Return counts: total, by status, production count, by content_type."""
    production_cat = (config.get("production_category") or "ai-marketing-automation").strip()
    total = 0
    by_status = {}
    production_count = 0
    by_content_type = {}
    if not articles_dir.exists():
        return {"total": 0, "by_status": {}, "production": 0, "by_content_type": {}}
    for path in articles_dir.glob("*.md"):
        total += 1
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = _parse_frontmatter_from_content(content)
        status = (meta.get("status") or "draft").strip().lower()
        by_status[status] = by_status.get(status, 0) + 1
        cat = (meta.get("category") or meta.get("category_slug") or "").strip()
        if cat == production_cat and status != "blocked":
            production_count += 1
        ctype = (meta.get("content_type") or "").strip().lower()
        if ctype:
            by_content_type[ctype] = by_content_type.get(ctype, 0) + 1
    return {
        "total": total,
        "by_status": by_status,
        "production": production_count,
        "by_content_type": by_content_type,
    }


def collect_queue_status(queue_path: Path) -> tuple[list[dict], dict, list[dict]]:
    """Return (items, counts_by_status, oldest_todo)."""
    items = _load_queue_simple(queue_path)
    by_status = {}
    todo_list = []
    for item in items:
        s = (item.get("status") or "todo").strip().lower()
        by_status[s] = by_status.get(s, 0) + 1
        if s == "todo":
            todo_list.append(item)
    todo_list.sort(key=lambda x: (x.get("primary_keyword") or ""))
    return items, by_status, todo_list[:5]


def collect_cost_summary(cost_data: dict, days: int, article_count: int) -> tuple[float, float, float]:
    """Return (total_all_time, total_last_n_days, avg_per_article)."""
    by_date = cost_data.get("by_date") or {}
    if not isinstance(by_date, dict):
        by_date = {}
    total_all = sum(float(v) for v in by_date.values())
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    last_n = sum(float(v) for k, v in by_date.items() if k >= cutoff)
    avg = total_all / article_count if article_count else 0
    return total_all, last_n, avg


def get_last_run(script_stem: str) -> str | None:
    """Return last run timestamp string or None."""
    path = LOGS_DIR / f"last_run_{script_stem}.txt"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def get_recent_errors(n: int = 10) -> list[str]:
    """Return last n lines from errors.log."""
    if not ERROR_LOG.exists():
        return []
    try:
        lines = ERROR_LOG.read_text(encoding="utf-8").strip().splitlines()
        return lines[-n:] if lines else []
    except OSError:
        return []


def format_ts(iso_ts: str | None) -> str:
    if not iso_ts:
        return "never"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_ts[:16] if len(iso_ts) >= 16 else iso_ts


def run_dashboard(summary_only: bool, days: int, use_color: bool) -> None:
    config = load_config(CONFIG_PATH)
    art = collect_article_stats(ARTICLES_DIR, config)
    items, q_by_status, oldest_todo = collect_queue_status(QUEUE_PATH)
    cost_data = _load_cost_data()
    total_cost, cost_last_n, avg_cost = collect_cost_summary(cost_data, days, art["total"])
    recent_errors = get_recent_errors(10)

    if summary_only:
        print(f"Articles: {art['total']} total, {art['production']} production")
        print(f"Queue: {q_by_status.get('todo', 0)} todo, {q_by_status.get('generated', 0)} generated")
        print(f"Estimated cost (all time): ${total_cost:.4f}")
        print(f"Recent errors: {len(recent_errors)}")
        return

    print()
    print("=" * 60)
    print("  FLOWTARO MONITOR")
    print("=" * 60)

    print("\n--- Article statistics ---")
    print(f"  Total .md files:     {art['total']}")
    print(f"  Production (live):   {art['production']}")
    print("  By status:")
    for s, c in sorted(art["by_status"].items()):
        print(f"    {s}: {c}")
    print("  By content type:")
    for t, c in sorted(art["by_content_type"].items()):
        print(f"    {t}: {c}")

    print("\n--- Queue status ---")
    print(f"  Total items:         {len(items)}")
    for s, c in sorted(q_by_status.items()):
        print(f"    {s}: {c}")
    if oldest_todo:
        print("  Oldest 5 todo:")
        for it in oldest_todo:
            kw = (it.get("primary_keyword") or it.get("title") or "?")[:50]
            print(f"    - {kw}")

    print("\n--- API cost (estimated) ---")
    print(f"  Total (all time):    ${total_cost:.4f}")
    print(f"  Last {days} days:        ${cost_last_n:.4f}")
    if art["total"]:
        print(f"  Avg per article:      ${avg_cost:.4f}")
    print("  (Blended ~$0.30/1M tokens; token estimate: chars/4)")

    print("\n--- Last run ---")
    for stem in ("generate_articles", "fill_articles", "render_site"):
        ts = get_last_run(stem)
        print(f"  {stem}: {format_ts(ts)}")

    print("\n--- Recent errors (last 10) ---")
    if not recent_errors:
        print("  " + _green("None", use_color))
    else:
        for line in recent_errors:
            print("  " + _red(line[:80] + ("..." if len(line) > 80 else ""), use_color))

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Flowtaro Monitor: pipeline health dashboard.")
    parser.add_argument("--summary", action="store_true", help="Short summary only.")
    parser.add_argument("--reset-costs", action="store_true", help="Reset api_costs.json.")
    parser.add_argument("--days", type=int, default=30, metavar="N", help="Cost window in days (default: 30).")
    args = parser.parse_args()

    if args.reset_costs:
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            API_COSTS_PATH.write_text('{"by_date": {}}\n', encoding="utf-8")
            print("Cost data reset.")
        except OSError as e:
            print(f"Error resetting costs: {e}", file=sys.stderr)
            sys.exit(1)
        if not args.summary and not sys.stdout.isatty():
            pass
        run_dashboard(args.summary, args.days, _is_tty())
        return

    run_dashboard(args.summary, args.days, _is_tty())


if __name__ == "__main__":
    main()
