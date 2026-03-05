"""
Fix Try it yourself <pre> closed with </p> → </pre> in content/articles/*.html or public/articles/*/index.html.
Run after check_try_it_yourself_pre.py to fix all reported files.

Usage:
  python fix_template2_pre_close.py                # fix content/articles
  python fix_template2_pre_close.py public/articles  # fix public/articles/*/index.html
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_ARTICLES = ROOT / "content" / "articles"

# Try it yourself workflow <pre> that ends with </p> instead of </pre> (same line)
TRY_IT_YOURSELF_PRE_CLOSED_WITH_P = re.compile(
    r'(<pre\s+class="bg-gray-100[^"]*"[^>]*>.*?Human\s+→\s+Prompt\s+#1\s+\(to\s+AI\s+chat\)\s+→[^<]*)</p>',
    re.IGNORECASE | re.DOTALL,
)


def fix_one(html: str) -> tuple[str, int]:
    """Replace mistaken </p> with </pre> for Try it yourself workflow block. Returns (new_html, number of replacements)."""
    new_html, n = TRY_IT_YOURSELF_PRE_CLOSED_WITH_P.subn(r"\1</pre>", html, count=1)
    return new_html, n


def main() -> None:
    if len(sys.argv) >= 2:
        target = Path(sys.argv[1])
        if not target.is_absolute():
            target = ROOT / target
        if not target.is_dir():
            print(f"Not a directory: {target}")
            sys.exit(1)
        html_files = sorted((p / "index.html") for p in target.iterdir() if p.is_dir() and (p / "index.html").exists())
        if not html_files:
            html_files = sorted(target.glob("*.html"))
    else:
        html_files = sorted(CONTENT_ARTICLES.glob("*.html"))

    fixed_count = 0
    for path in html_files:
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"Skip {path.name}: {e}")
            continue
        new_html, n = fix_one(html)
        if n:
            path.write_text(new_html, encoding="utf-8")
            fixed_count += 1
            try:
                rel = path.relative_to(ROOT)
            except ValueError:
                rel = path
            print(f"Fixed: {rel}")
    print(f"\nDone. Fixed {fixed_count} file(s).")


if __name__ == "__main__":
    main()
