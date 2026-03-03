"""
Fix last 7 generated articles: (1) Template 2 first <pre> closed with </p> -> </pre>;
(2) Second prompt block (Prompt #2) trimmed to only proper content (remove intro + trailing chatter).

Usage: python fix_last7_second_prompt_block.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_ARTICLES = ROOT / "content" / "articles"

# Template 2 <pre> workflow line closed with </p> instead of </pre> — replace ALL occurrences
TEMPLATE2_PRE_CLOSED_WITH_P = re.compile(
    r'(<pre\s+class="bg-gray-100[^"]*"[^>]*>.*?Human\s+→\s+Prompt\s+#1\s+\(to\s+AI\s+chat\)\s+→[^<]*)</p>',
    re.IGNORECASE | re.DOTALL,
)

# Start of actual Prompt #2 content (keep from this line onward when trimming leading)
PROMPT2_START = re.compile(
    r"^(?:\s*)(?:\*\*Prompt\s*#2\s*\*?\:*|###\s+Prompt\s+for|###\s+Steps|\d+\.\s+\*\*|```)",
    re.IGNORECASE | re.MULTILINE,
)

# Trailing chatter to remove (line or sentence that should not be inside Prompt #2 block)
TRAILING_CHATTER = re.compile(
    r"\n?\s*(?:Feel free to let me know[^!]*!|"
    r"Let me know if (?:you need|any)[^.!]*[.!]|"
    r"I hope this (?:helps|is)[^.!]*[.!]|"
    r"If there'?s an aspect of[^.]*\.|"
    r"If (?:you need|any) (?:adjustments|changes)[^.]*\.|"
    r"Please (?:let me know|provide)[^.]*\.?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def fix_template2_closing(html: str) -> str:
    """Replace all mistaken </p> with </pre> for Template 2 workflow blocks."""
    return TEMPLATE2_PRE_CLOSED_WITH_P.sub(r"\1</pre>", html)


def find_template2_section(html: str) -> tuple[int, int] | None:
    """Return (start, end) of Template 2 section (from <h2>Template 2:</h2> to next <h2>)."""
    m = re.search(r"<h2[^>]*>\s*Template\s+2\s*:\s*</h2>", html, re.IGNORECASE)
    if not m:
        return None
    start = m.start()
    rest = html[start:]
    # Next <h2> after current one (skip first 20 chars to avoid matching same h2)
    h2_next = re.search(r"<h2\b", rest[20:], re.IGNORECASE)
    if h2_next:
        end = start + 20 + h2_next.start()
    else:
        end = len(html)
    return start, end


def trim_second_pre_content(inner: str) -> str:
    """Remove leading intro and trailing chatter from Prompt #2 block content."""
    lines = inner.split("\n")
    # Drop leading lines until we hit a line that starts actual Prompt #2
    start_idx = 0
    for i, line in enumerate(lines):
        if PROMPT2_START.search(line.strip()) or (line.strip().startswith("```") and i > 0):
            start_idx = i
            break
        if re.match(r"^\s*\d+\.\s+\*\*", line):
            start_idx = i
            break
    trimmed = "\n".join(lines[start_idx:]).strip()
    # Remove trailing chatter (single line or sentence at end)
    trimmed = TRAILING_CHATTER.sub("", trimmed).strip()
    return trimmed


def fix_second_block_in_section(html: str) -> str:
    """Fix the second prompt block: trim its content. Returns new html."""
    template2 = find_template2_section(html)
    if not template2:
        return html
    start, end = template2
    section = html[start:end]
    pre_pattern = re.compile(r"<pre([^>]*)>(.*?)</pre>", re.IGNORECASE | re.DOTALL)
    replaced = [False]

    def repl(m: re.Match) -> str:
        inner = m.group(2).strip()
        if "Human → Prompt #1 (to AI chat)" in inner and len(inner) < 200:
            return m.group(0)
        if not (PROMPT2_START.search(inner) or "**Prompt #2**" in inner or "### Prompt" in inner or "### Steps" in inner):
            return m.group(0)
        if replaced[0]:
            return m.group(0)
        replaced[0] = True
        trimmed = trim_second_pre_content(inner)
        if trimmed == inner:
            return m.group(0)
        return f"<pre{m.group(1)}>{trimmed}</pre>"

    new_section = pre_pattern.sub(repl, section)
    if new_section == section:
        return html
    return html[:start] + new_section + html[end:]


def main() -> None:
    html_files = sorted(
        CONTENT_ARTICLES.glob("*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:7]
    print("Last 7 articles (by mtime):")
    for p in html_files:
        print(" ", p.relative_to(ROOT))
    print()
    for path in html_files:
        html = path.read_text(encoding="utf-8", errors="replace")
        original = html
        html = fix_template2_closing(html)
        html = fix_second_block_in_section(html)
        if html != original:
            path.write_text(html, encoding="utf-8")
            print("Fixed:", path.relative_to(ROOT))
    print("Done.")


if __name__ == "__main__":
    main()
