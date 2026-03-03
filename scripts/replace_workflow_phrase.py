#!/usr/bin/env python3
"""One-off: replace old workflow phrase with new in HTML and MD files."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# Canonical literal (must appear everywhere)
NEW = "Human → Prompt #1 (to AI chat) → AI returns ready-to-use Prompt #2 or questions or instruction → Human (paste Prompt #2 into AI chat or follow the instructions given)"

OLD1 = "Human → Prompt #1 (to a general AI) → AI returns Prompt #2 (ready-to-paste prompt for the specific tool) → Use Prompt #2 in the tool."
OLD2 = "Human → Prompt #1 (meta-prompt to a general AI, using chain-of-thought reasoning) → AI returns Prompt #2 (ready-to-paste prompt for the specific tool) → Use Prompt #2 in the tool."

# All variants → same literal (substring replace)
REPLACEMENTS = [
    (OLD1, NEW),
    (OLD2, NEW),
    ("Human → Prompt #1 (meta-prompt to a general AI) → AI returns Prompt #2 (ready-to-paste prompt for the specific tool) → Use Prompt #2 in the tool.", NEW),
    ("Human → Prompt #1 → AI returns Prompt #2 → Use Prompt #2 in the tool.", NEW),
    ("Human → Prompt #1 (meta-prompt to a general AI) → AI returns Prompt #2 → Use Prompt #2 in the tool.", NEW),
    ("Human → Prompt #1  → AI returns Prompt #2 → Use Prompt #2 in the tool.", NEW),
    ("Prompt #1 (meta-prompt to a general AI, using chain-of-thought reasoning) → AI returns Prompt #2 (ready-to-paste prompt for the specific tool) → Use Prompt #2 in the tool.", NEW),
    # Already "ready-to-use... Human (paste..." but still "to a general AI" or "meta-prompt..."
    ("Human → Prompt #1 (to a general AI) → AI returns ready-to-use Prompt #2 or questions or instruction → Human (paste Prompt #2 into AI chat or follow the instructions given)", NEW),
    ("Human → Prompt #1 (meta-prompt to a general AI, using chain-of-thought reasoning) → AI returns ready-to-use Prompt #2 or questions or instruction → Human (paste Prompt #2 into AI chat or follow the instructions given)", NEW),
    # "Prompt #2 (for X) → Use in the tool" variants
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for the specific tool) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for a specific tool, e.g., Descript) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for Descript tool) → Use in Descript.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for Pictory) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for Pictory) → Use in Pictory.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for Otter) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for Otter) → Use in Otter.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for Descript) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for the specific tool, e.g., Pictory) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for the specific tool, e.g., Descript) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for the tool, e.g., Google Analytics) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for ChatGPT) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for specific tool, e.g. Descript) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for specific tool, e.g., SEMrush) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for the specific tool, e.g., Make) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for a specific tool) → Use in the tool.", NEW),
    ("Human → Prompt #1 (to a general AI) → Prompt #2 (for the specific tool, e.g., ChatGPT) → Use in the tool.", NEW),
]
# <li> variant: normalize to literal inside <li>
OLD_LI_GENERAL = "<li>Human → Prompt #1 (to a general AI) → AI returns ready-to-use Prompt #2 or questions or instruction → Human (paste Prompt #2 into AI chat or follow the instructions given)</li>"
# Two <li> variant: merge into one
OLD_TWO_LI = "<li>Human → Prompt #1 (to a general AI) → AI returns Prompt #2 (ready-to-paste prompt for the specific tool).</li>\n    <li>Use Prompt #2 in the tool.</li>"
NEW_ONE_LI = f"<li>{NEW}</li>"

def main():
    updated = []
    bases = ["content/articles", "public/articles", "content/articles_archive", "content/backups", "docs"]
    for base in bases:
        root = PROJECT / base
        if not root.exists():
            continue
        for ext in ("*.html", "*.md"):
            for path in root.rglob(ext):
                if not path.is_file():
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                orig = text
                for old, new in REPLACEMENTS:
                    if old in text:
                        text = text.replace(old, new)
                if OLD_TWO_LI in text:
                    text = text.replace(OLD_TWO_LI, NEW_ONE_LI)
                if OLD_LI_GENERAL in text:
                    text = text.replace(OLD_LI_GENERAL, NEW_ONE_LI)
                if text != orig:
                    path.write_text(text, encoding="utf-8")
                    updated.append(str(path.relative_to(PROJECT)))
    for p in updated:
        print(p)
    print(f"Updated {len(updated)} files")

if __name__ == "__main__":
    main()
