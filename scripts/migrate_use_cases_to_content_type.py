#!/usr/bin/env python3
"""
One-time migration: ensure every use case in content/use_cases.yaml has content_type.
Where content_type is missing, set content_type = suggested_content_type (or DEFAULT_CONTENT_TYPE if both missing).
Saves the file with only content_type; suggested_content_type is no longer written.
After running this script, the pipeline uses only content_type (no suggested_content_type).
Run once before production/release: python scripts/migrate_use_cases_to_content_type.py
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_use_cases import load_use_cases, save_use_cases

PROJECT_ROOT = _SCRIPTS_DIR.parent
USE_CASES_PATH = PROJECT_ROOT / "content" / "use_cases.yaml"
DEFAULT_CONTENT_TYPE = "guide"


def main() -> None:
    if not USE_CASES_PATH.exists():
        print(f"File not found: {USE_CASES_PATH}. Nothing to migrate.")
        return
    items = load_use_cases(USE_CASES_PATH)
    if not items:
        print("No use cases in file. Nothing to migrate.")
        return
    migrated = 0
    for uc in items:
        ct = (uc.get("content_type") or "").strip()
        suggested = (uc.get("suggested_content_type") or "").strip()
        if not ct and suggested:
            uc["content_type"] = suggested
            migrated += 1
        elif not ct:
            uc["content_type"] = DEFAULT_CONTENT_TYPE
            migrated += 1
        # Normalize key: we only persist content_type; drop suggested_content_type from dict
        # so that any future code reading from memory sees only content_type.
        if "suggested_content_type" in uc:
            del uc["suggested_content_type"]
    save_use_cases(USE_CASES_PATH, items)
    print(f"Migrated {len(items)} use cases. Set content_type in {migrated} item(s). File now uses only content_type.")


if __name__ == "__main__":
    main()
