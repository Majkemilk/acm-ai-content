#!/usr/bin/env python3
"""
Sync content/use_case_allowed_categories.json from content/config.yaml.
Run after manual edits to config.yaml so generate_use_cases uses the same allowed categories.
Called automatically by FlowMonitor on config save.
"""

import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from content_root import get_content_root_path
from generate_use_cases import sync_allowed_categories_file

PROJECT_ROOT = SCRIPTS_DIR.parent


def main() -> None:
    content_root = os.environ.get("CONTENT_ROOT", "content").strip() or "content"
    content_dir = get_content_root_path(PROJECT_ROOT, content_root)
    config_path = content_dir / "config.yaml"
    allowed_categories_file = content_dir / "use_case_allowed_categories.json"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)
    sync_allowed_categories_file(config_path, allowed_categories_file)
    print(f"Updated {allowed_categories_file}")


if __name__ == "__main__":
    main()
