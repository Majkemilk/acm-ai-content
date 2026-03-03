#!/usr/bin/env python3
"""
One-off: In all HTML articles, replace any <p> or <li> that contains the workflow
text with content containing only the literal (no intro/outro).
Run from project root. Use --write to modify files (default: dry-run).
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_LITERAL = "Human → Prompt #1 (to AI chat) → AI returns ready-to-use Prompt #2 or questions or instruction → Human (paste Prompt #2 into AI chat or follow the instructions given)"


def normalize(body: str) -> str:
    def replace_p(m):
        content = m.group(2)
        if "Human → Prompt #1 (to AI chat)" in content and "follow the instructions given)" in content:
            return m.group(1) + WORKFLOW_LITERAL + "</p>"
        return m.group(0)

    body = re.sub(r"(<p[^>]*>)(.*?)</p>", replace_p, body, flags=re.DOTALL)

    def replace_li(m):
        content = m.group(1)
        if "Human → Prompt #1 (to AI chat)" in content and "follow the instructions given)" in content:
            return "<li>" + WORKFLOW_LITERAL + "</li>"
        return m.group(0)

    body = re.sub(r"<li>(.*?)</li>", replace_li, body, flags=re.DOTALL)
    return body


def main() -> None:
    write = "--write" in sys.argv
    articles_dir = PROJECT_ROOT / "content" / "articles"
    archive_dir = PROJECT_ROOT / "content" / "articles_archive"
    dirs = [d for d in (articles_dir, archive_dir) if d.exists()]
    changed = 0
    for d in dirs:
        for path in d.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            new_text = normalize(text)
            if new_text != text:
                changed += 1
                print(path.relative_to(PROJECT_ROOT))
                if write:
                    path.write_text(new_text, encoding="utf-8")
    print(f"Total: {changed} file(s) {'updated.' if write else 'would be updated (run with --write).'}")


if __name__ == "__main__":
    main()
