#!/usr/bin/env python3
"""
Set status: "filled" in content/articles/*.md for articles that have a matching
published version in public/articles/{slug}/index.html (same slug = path.stem).
Read-only comparison; writes only content/articles .md frontmatter.
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_ARTICLES = PROJECT_ROOT / "content" / "articles"
PUBLIC_ARTICLES = PROJECT_ROOT / "public" / "articles"


def main() -> None:
    if not PUBLIC_ARTICLES.exists():
        print("public/articles not found")
        return
    public_slugs = set()
    for d in PUBLIC_ARTICLES.iterdir():
        if d.is_dir() and (d / "index.html").exists():
            public_slugs.add(d.name)
    print(f"Found {len(public_slugs)} published articles in public/articles")

    if not CONTENT_ARTICLES.exists():
        print("content/articles not found")
        return
    updated = []
    for path in sorted(CONTENT_ARTICLES.glob("*.md")):
        stem = path.stem
        if stem not in public_slugs:
            continue
        text = path.read_text(encoding="utf-8")
        if 'status: "filled"' in text or "status: 'filled'" in text:
            continue
        # Replace status line (any value) with status: "filled"
        new_text = re.sub(
            r'\nstatus:\s*["\'].*?["\']',
            '\nstatus: "filled"',
            text,
            count=1,
        )
        if new_text == text:
            continue
        path.write_text(new_text, encoding="utf-8")
        updated.append(path.name)
    print(f"Set status to 'filled' for {len(updated)} article(s) in content/articles:")
    for name in updated:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
