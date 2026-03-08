#!/usr/bin/env python3
"""
Ustawia Typ linku (przez kategorię) na 'referral' wyłącznie dla linków,
w których w adresie jest trzeci znak / i niepusta treść po nim.
Pozostałe linki nie są zmieniane.
Uruchom z katalogu głównego: python scripts/update_link_type_referral_by_path.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from flowtaro_monitor._monitor_data import load_affiliate_tools, save_affiliate_tools
from flowtaro_monitor._affiliate_url_utils import is_referral_by_third_slash


def main():
    tools = load_affiliate_tools()
    updated = 0
    for t in tools:
        link = (t.get("affiliate_link") or "").strip()
        if not link or not is_referral_by_third_slash(link):
            continue
        if (t.get("category") or "").strip() == "referral":
            continue
        t["category"] = "referral"
        updated += 1
    save_affiliate_tools(tools)
    print(f"Ustawiono Typ linku (kategoria referral) dla {updated} linków (3. znak / z treścią).")


if __name__ == "__main__":
    main()
