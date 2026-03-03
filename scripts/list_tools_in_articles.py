#!/usr/bin/env python3
"""List tools and articles they appear in (from frontmatter tools field). Same source as Flowtaro Monitor tab."""
from pathlib import Path
import re
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"

def main():
    by_tool = defaultdict(list)
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        block = text[3:end]
        tools_str = ""
        for line in block.split("\n"):
            m = re.match(r"^tools:\s*(.*)$", line.strip())
            if m:
                raw = m.group(1).strip()
                if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                    raw = raw[1:-1]
                tools_str = raw.strip()
                break
        if not tools_str:
            continue
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]
        for t in tools:
            by_tool[t].append(path.stem)
    for tool in sorted(by_tool.keys()):
        slugs = sorted(set(by_tool[tool]))
        print(f"{tool}\t{len(slugs)}\t{' | '.join(slugs)}")

if __name__ == "__main__":
    main()
