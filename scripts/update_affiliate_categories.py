#!/usr/bin/env python3
"""
Aktualizuje Kategorię (i w konsekwencji Typ linku) w content/affiliate_tools.yaml
wg logiki: referral gdy w URL jest trzeci '/' z niepustą treścią po nim LUB query (via=, ref=, referrer=);
w przeciwnym razie general.
Uruchom z katalogu głównego projektu: python scripts/update_affiliate_categories.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from flowtaro_monitor._monitor_data import load_affiliate_tools, save_affiliate_tools
from flowtaro_monitor._affiliate_url_utils import category_from_url


def main():
    tools = load_affiliate_tools()
    updated = 0
    for t in tools:
        link = (t.get("affiliate_link") or "").strip()
        if not link:
            continue
        new_cat = category_from_url(link)
        old_cat = (t.get("category") or "").strip() or "general"
        if old_cat != new_cat:
            updated += 1
        t["category"] = new_cat
    save_affiliate_tools(tools)
    print(f"Zaktualizowano kategorie w content/affiliate_tools.yaml (zmienionych wpisów: {updated})")


if __name__ == "__main__":
    main()
