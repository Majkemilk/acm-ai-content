#!/usr/bin/env python3
"""
Sync content/use_case_allowed_categories.json from content/config.yaml.
Run after manual edits to config.yaml so generate_use_cases uses the same allowed categories.
Called automatically by FlowMonitor on config save.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_use_cases import CONFIG_PATH, sync_allowed_categories_file

PROJECT_ROOT = SCRIPTS_DIR.parent
CONTENT_DIR = PROJECT_ROOT / "content"
ALLOWED_CATEGORIES_FILE = CONTENT_DIR / "use_case_allowed_categories.json"


def main() -> None:
    config_path = CONFIG_PATH
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)
    sync_allowed_categories_file(config_path, ALLOWED_CATEGORIES_FILE)
    print(f"Updated {ALLOWED_CATEGORIES_FILE}")


if __name__ == "__main__":
    main()
