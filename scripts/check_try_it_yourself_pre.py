"""
One-off script: scan content/articles/*.html (or public/articles/*/index.html) and report files where
(1) the first <pre> in "Try it yourself" section contains Prompt #2 or other foreign content, or
(2) Template 2 contains <pre> closed with </p> (unclosed <pre>), which breaks DOM and makes "section 1" render wrong.

Usage:
  python check_try_it_yourself_pre.py                    # scan content/articles
  python check_try_it_yourself_pre.py public/articles   # scan public/articles/*/index.html
"""
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
CONTENT_ARTICLES = ROOT / "content" / "articles"
PUBLIC_ARTICLES = ROOT / "public" / "articles"

# Same markers as in fill_articles.py – lines that start Prompt #2 / sample output
PROMPT2_START_MARKERS = re.compile(
    r"^(?:\s*)(?:###\s+Steps|\*\*Prompt\s*#2\*\*|Would you like to provide|Example Prompt Construction|Steps to Achieve|\d+\.\s+\*\*Analyze)",
    re.IGNORECASE | re.MULTILINE,
)

# Stray HTML inside <pre> that corrupts structure
STRAY_HTML_IN_PRE = re.compile(
    r"</?\s*(?:p|div|span|h[1-6]|ul|ol|li|section|article)\b[^>]*>",
    re.IGNORECASE,
)

def find_try_it_yourself_section(html: str) -> str | None:
    """Return the substring starting at <h3> Try it yourself / Build your own AI prompt up to next <h2 or end."""
    m = re.search(
        r"<h3[^>]*>\s*Try\s+it\s+yourself\s*:?\s*Build\s+your\s+own\s+AI\s+prompt\s*</h3>",
        html,
        re.IGNORECASE,
    )
    if not m:
        return None
    start = m.start()
    # End at next <h2 or end of string
    rest = html[start:]
    h2 = re.search(r"<h2\b", rest, re.IGNORECASE)
    end_cut = h2.start() if h2 else len(rest)
    return rest[:end_cut]


def first_pre_content(section: str) -> str | None:
    """Return inner text of first <pre>...</pre> in section, or None."""
    m = re.search(r"<pre([^>]*)>(.*?)</pre>", section, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return m.group(2).strip()


def has_prompt2_or_foreign_in_first_pre(html: str) -> tuple[bool, list[str]]:
    """
    Check if the first <pre> in Try it yourself contains only Prompt #1.
    Returns (is_buggy, list of reasons).
    """
    section = find_try_it_yourself_section(html)
    if not section:
        return False, []  # no Try it yourself section – skip

    inner = first_pre_content(section)
    if not inner:
        return False, []  # empty first <pre> – OK

    reasons = []

    # 1) Prompt #2 start markers
    if PROMPT2_START_MARKERS.search(inner):
        reasons.append("first <pre> contains Prompt #2 start marker (e.g. ### Steps, **Prompt #2**, Would you like to provide)")

    # 2) Other obvious P2 phrases (looser check)
    p2_phrases = [
        "**Prompt #2 for",
        "Prompt #2 for ",
        "Here's Prompt #2",
        "Here is Prompt #2",
        "Feel free to ask if you need",
        "Continue in the same thread",
    ]
    for phrase in p2_phrases:
        if phrase in inner:
            reasons.append(f"first <pre> contains foreign phrase: {phrase!r}")
            break

    # 3) Stray HTML tags inside <pre>
    if STRAY_HTML_IN_PRE.search(inner):
        reasons.append("first <pre> contains raw HTML tags (e.g. </p>, <p>, <h2)")

    return bool(reasons), reasons


def has_template2_pre_closed_with_p(html: str) -> bool:
    """True if any <pre> in Template 2 is closed with </p> instead of </pre> (same line)."""
    return bool(
        re.search(
            r'<pre\s+class="bg-gray-100[^"]*"[^>]*>.*?Human\s+→\s+Prompt\s+#1\s+\(to\s+AI\s+chat\)\s+→[^<]*</p>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
    )


def main() -> None:
    if len(sys.argv) >= 2:
        target = Path(sys.argv[1])
        if not target.is_absolute():
            target = ROOT / target
        if not target.is_dir():
            print(f"Not a directory: {target}")
            sys.exit(1)
        # public/articles style: immediate subdirs with index.html
        html_files = sorted((p / "index.html") for p in target.iterdir() if p.is_dir() and (p / "index.html").exists())
        if not html_files:
            # content/articles style: flat *.html
            html_files = sorted(target.glob("*.html"))
    else:
        html_files = sorted(CONTENT_ARTICLES.glob("*.html"))

    buggy: list[tuple[Path, list[str]]] = []

    for path in html_files:
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            buggy.append((path, [f"read error: {e}"]))
            continue

        reasons: list[str] = []
        is_buggy, pre_reasons = has_prompt2_or_foreign_in_first_pre(html)
        reasons.extend(pre_reasons)
        if has_template2_pre_closed_with_p(html):
            reasons.append("Template 2 <pre> closed with </p> instead of </pre> (unclosed <pre>, breaks DOM; section 1 renders wrong)")
        if reasons:
            buggy.append((path, reasons))

    print("Articles where section 1 (first <pre> in Try it yourself) is wrong or DOM is broken:\n")
    if not buggy:
        print("None – all checked articles are OK.")
        return

    for path, reasons in buggy:
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        print(f"  {rel}")
        for r in reasons:
            print(f"    - {r}")
        print()

    print(f"Total: {len(buggy)} file(s).")


if __name__ == "__main__":
    main()
