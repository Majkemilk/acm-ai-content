#!/usr/bin/env python3
"""
Sync AI chat tools from content/affiliate_tools.yaml to prompt-generator.
Reads tools with category "ai-chat" and writes prompt-generator/app/ai-chat-tools.json
so the Flowtaro Prompt Generator can render linked names from the current affiliate list.
Run from project root: python scripts/sync_ai_chat_links_to_prompt_generator.py
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AFFILIATE_YAML = PROJECT_ROOT / "content" / "affiliate_tools.yaml"
OUTPUT_JSON = PROJECT_ROOT / "prompt-generator" / "app" / "ai-chat-tools.json"
AI_CHAT_CATEGORY = "ai-chat"


def _val(s: str) -> str:
    s = (s or "").strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1].replace('\\"', '"').strip()
    return s


def load_ai_chat_tools() -> list[dict]:
    """Load (name, affiliate_link) for tools with category ai-chat from affiliate_tools.yaml."""
    if not AFFILIATE_YAML.exists():
        return []
    text = AFFILIATE_YAML.read_text(encoding="utf-8")
    items: list[dict] = []
    in_tools = False
    current_name = ""
    current_url = ""
    current_category = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped == "tools:":
            in_tools = True
            continue
        if not in_tools:
            continue
        if stripped.startswith("- "):
            if current_name and (current_category or "").strip() == AI_CHAT_CATEGORY and (current_url or "").strip():
                items.append({"name": current_name.strip(), "url": current_url.strip()})
            current_name = ""
            current_url = ""
            current_category = ""
            part = stripped[2:].strip()
            kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", part)
            if kv:
                k, v = kv.group(1), _val(kv.group(2))
                if k == "name":
                    current_name = v
                elif k == "affiliate_link":
                    current_url = v
                elif k == "category":
                    current_category = v
            continue
        kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", stripped)
        if kv:
            k, v = kv.group(1), _val(kv.group(2))
            if k == "name":
                current_name = v
            elif k == "affiliate_link":
                current_url = v
            elif k == "category":
                current_category = v
    if current_name and (current_category or "").strip() == AI_CHAT_CATEGORY and (current_url or "").strip():
        items.append({"name": current_name.strip(), "url": current_url.strip()})
    return items


def main() -> None:
    tools = load_ai_chat_tools()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(tools, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(tools)} ai-chat tool(s) to {OUTPUT_JSON}: {[t['name'] for t in tools]}")


if __name__ == "__main__":
    main()
