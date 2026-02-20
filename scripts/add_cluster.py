#!/usr/bin/env python3
"""
Add a new topic cluster (category) to the system: update content/config.yaml,
then run generate_use_cases.py and generate_queue.py.
Run from project root: python scripts/add_cluster.py <category> [--production]
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Allow importing from same package (scripts/)
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from content_index import load_config  # noqa: E402
from config_manager import write_config as write_config_full  # noqa: E402

CONFIG_PATH = _PROJECT_ROOT / "content" / "config.yaml"
DEFAULT_HUB_SLUG = "ai-marketing-automation"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a new topic cluster (category) and run use-case/queue generators.",
    )
    parser.add_argument(
        "category",
        type=str,
        help="Slug of the new category (e.g. ai-for-sales).",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Set this category as production (overwrite current). Default: add to sandbox.",
    )
    args = parser.parse_args()

    category = (args.category or "").strip()
    if not category:
        print("Error: category is required.")
        sys.exit(1)

    # Load current config
    if not CONFIG_PATH.exists():
        print(f"Error: Config not found: {CONFIG_PATH}")
        sys.exit(1)
    try:
        config = load_config(CONFIG_PATH)
    except Exception as e:
        print(f"Error: Could not parse config: {e}")
        sys.exit(1)

    production = (config.get("production_category") or "").strip()
    sandbox = list(config.get("sandbox_categories") or [])
    if isinstance(sandbox, list):
        sandbox = [str(x).strip() for x in sandbox if str(x).strip()]
    else:
        sandbox = []

    already_present = False
    if args.production:
        if production == category:
            already_present = True
            print(f"Warning: '{category}' is already the production category. Skipping config change.")
        else:
            production = category
    else:
        if category in sandbox:
            already_present = True
            print(f"Warning: '{category}' is already in sandbox_categories. Skipping config change.")
        else:
            sandbox.append(category)

    if not already_present:
        hub_slug = (config.get("hub_slug") or DEFAULT_HUB_SLUG).strip()
        try:
            write_config_full(CONFIG_PATH, production, hub_slug, sandbox)
        except OSError as e:
            print(f"Error: Could not write config: {e}")
            sys.exit(1)
        print(f"Updated {CONFIG_PATH}.")

    # Run generators from project root
    for script_name in ("generate_use_cases.py", "generate_queue.py"):
        script_path = _SCRIPTS_DIR / script_name
        if not script_path.exists():
            print(f"Error: Script not found: {script_path}")
            sys.exit(1)
        cmd = [sys.executable, str(script_path)]
        result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        if result.returncode != 0:
            print(f"Error: {script_name} failed with exit code {result.returncode}.")
            sys.exit(result.returncode)
        print(f"Ran {script_name}.")

    prod_flag = " (production=True)" if args.production else " (production=False)"
    print()
    print(f"Added cluster: {category}{prod_flag}")
    print("Use cases and queue updated.")
    print("You can now run the main pipeline: generate_articles, fill_articles, render.")


if __name__ == "__main__":
    main()
