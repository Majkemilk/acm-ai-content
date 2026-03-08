#!/usr/bin/env python3
"""
One-off: for each tool in content/affiliate_tools.yaml that has short_description_en
but no (or empty) short_description_pl, translate EN to PL and set short_description_pl.
Requires OPENAI_API_KEY. Use --dry-run to only print what would be done.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_queue import load_tools  # noqa: E402

# Import after path setup so flowtaro_monitor is resolvable
from flowtaro_monitor._affiliate_descriptions import translate_en_to_pl  # noqa: E402
from flowtaro_monitor._monitor_data import save_affiliate_tools  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate short_description_en to Polish and set short_description_pl for tools that lack it."
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be updated; do not write.")
    args = parser.parse_args()

    path = PROJECT_ROOT / "content" / "affiliate_tools.yaml"
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    tools = load_tools(path)
    if not tools:
        print("No tools in affiliate_tools.yaml.")
        sys.exit(0)

    updated = 0
    for t in tools:
        en = (t.get("short_description_en") or "").strip()
        pl = (t.get("short_description_pl") or "").strip()
        if not en or pl:
            continue
        name = (t.get("name") or "").strip() or "(no name)"
        if args.dry_run:
            print(f"Would translate: {name}: {en[:60]}{'…' if len(en) > 60 else ''}")
            updated += 1
            continue
        translated = translate_en_to_pl(en)
        if translated:
            t["short_description_pl"] = translated
            updated += 1
            print(f"Translated: {name}")
        else:
            print(f"Skip (translation failed): {name}", file=sys.stderr)

    if not args.dry_run and updated > 0:
        save_affiliate_tools(tools)
        print(f"Saved. Updated {updated} tool(s) with short_description_pl.")
    elif args.dry_run:
        print(f"Dry-run: would update {updated} tool(s).")
    else:
        print(f"Updated {updated} tool(s)." + (" No file written (dry-run)." if args.dry_run else ""))


if __name__ == "__main__":
    main()
