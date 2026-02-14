#!/usr/bin/env python3
"""
Minimal static renderer: Markdown (content/) -> HTML (public/). Stdlib only.
Renders production articles and production hub; updates public/index.html.
"""

import html
import re
from datetime import date
from pathlib import Path

from content_index import get_production_articles, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
HUBS_DIR = PROJECT_ROOT / "content" / "hubs"
PUBLIC_DIR = PROJECT_ROOT / "public"

INLINE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")


def _parse_md_file(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Frontmatter ends at second ---."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}, ""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip()
    meta: dict[str, str] = {"slug": path.stem}
    for line in block.split("\n"):
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1].replace('\\"', '"')
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        meta[key] = raw
    body = text[end + 4 :].lstrip("\n")
    return meta, body


def _escape(s: str) -> str:
    return html.escape(s, quote=True)


def _inline_links(s: str) -> str:
    """Replace [text](url) with <a href="url">text</a>. s must be already escaped for &<>."""
    def sub(match: re.Match) -> str:
        t, u = match.group(1), match.group(2)
        return f'<a href="{_escape(u)}">{t}</a>'
    return INLINE_LINK.sub(sub, s)


def _date_from_string(s: str) -> date | None:
    if not s or len(s) < 10:
        return None
    s = s.strip()[:10]
    try:
        return date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except (ValueError, IndexError):
        return None


def _sort_key_newest(meta: dict, path: Path) -> tuple[date, str]:
    d = _date_from_string(meta.get("last_updated") or "")
    if d is not None:
        return (d, meta.get("slug", path.stem))
    d = _date_from_string(path.stem)
    if d is not None:
        return (d, path.stem)
    return (date.min, path.stem)


def _md_to_html(body: str) -> str:
    """Minimal markdown to HTML: headings, - and 1. lists, paragraphs, [text](url), ``` code."""
    lines = body.split("\n")
    out: list[str] = []
    i = 0
    in_pre = False
    in_ul = False
    in_ol = False
    paragraph_buf: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_buf
        if paragraph_buf:
            p = " ".join(paragraph_buf)
            p = _escape(p)
            p = _inline_links(p)
            out.append(f"<p>{p}</p>")
            paragraph_buf = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def close_ol() -> None:
        nonlocal in_ol
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while i < len(lines):
        line = lines[i]
        raw = line
        stripped = line.strip()
        if in_pre:
            if stripped.startswith("```"):
                out.append("</code></pre>")
                in_pre = False
            else:
                out.append(_escape(line) + "\n")
            i += 1
            continue
        if stripped.startswith("```"):
            flush_paragraph()
            close_ul()
            close_ol()
            out.append("<pre><code>")
            in_pre = True
            i += 1
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            close_ul()
            close_ol()
            t = _escape(stripped[4:])
            t = _inline_links(t)
            out.append(f"<h3>{t}</h3>")
            i += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            close_ul()
            close_ol()
            t = _escape(stripped[3:])
            t = _inline_links(t)
            out.append(f"<h2>{t}</h2>")
            i += 1
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            close_ul()
            close_ol()
            t = _escape(stripped[2:])
            t = _inline_links(t)
            out.append(f"<h1>{t}</h1>")
            i += 1
            continue
        if re.match(r"^\s*-\s+", line) or (stripped.startswith("- ") or stripped.startswith("-\t")):
            flush_paragraph()
            close_ol()
            item = stripped[1:].strip()
            item = _escape(item)
            item = _inline_links(item)
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{item}</li>")
            i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            flush_paragraph()
            close_ul()
            m = re.match(r"^\s*\d+\.\s+(.*)$", line)
            item = m.group(1).strip() if m else stripped
            item = _escape(item)
            item = _inline_links(item)
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{item}</li>")
            i += 1
            continue
        if stripped == "" or stripped == "---":
            flush_paragraph()
            close_ul()
            close_ol()
            i += 1
            continue
        paragraph_buf.append(stripped)
        i += 1
    flush_paragraph()
    close_ul()
    close_ol()
    if in_pre:
        out.append("</code></pre>")
    return "\n".join(out)


def _wrap_page(title: str, body_html: str, last_updated: str | None = None) -> str:
    meta = f'\n  <meta name="last-modified" content="{_escape(last_updated)}">' if last_updated else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape(title)}</title>{meta}
</head>
<body>
{body_html}
</body>
</html>
"""


def _render_article(path: Path, out_dir: Path) -> None:
    meta, body = _parse_md_file(path)
    slug = meta.get("slug") or path.stem
    title = (meta.get("title") or slug).strip()
    last_updated = (meta.get("last_updated") or "").strip()
    if last_updated and len(last_updated) >= 10:
        last_updated = last_updated[:10]
    else:
        last_updated = None
    body_html = _md_to_html(body)
    html_path = out_dir / "articles" / slug / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(_wrap_page(title, body_html, last_updated), encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")


def _render_hub(path: Path, out_dir: Path) -> None:
    meta, body = _parse_md_file(path)
    slug = meta.get("slug") or path.stem
    title = (meta.get("title") or "").strip()
    if not title and body.lstrip().startswith("# "):
        title = body.lstrip().split("\n", 1)[0].replace("# ", "").strip()
    if not title:
        title = slug
    body_html = _md_to_html(body)
    html_path = out_dir / "hubs" / slug / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(_wrap_page(title, body_html), encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")


def _update_index(out_dir: Path, production_category: str, articles: list[tuple[dict, Path]]) -> None:
    index_path = out_dir / "index.html"
    sorted_articles = sorted(articles, key=lambda x: _sort_key_newest(x[0], x[1]), reverse=True)[:5]
    articles_html = "".join(
        f'    <li><a href="/articles/{a[0].get("slug", a[1].stem)}/">{_escape((a[0].get("title") or a[1].stem).strip())}</a></li>\n'
        for a in sorted_articles
    )
    hub_link = f'  <p><a href="/hubs/{_escape(production_category)}/">AI Marketing Automation hub</a></p>\n'
    content = index_path.read_text(encoding="utf-8")
    if "AI Marketing Automation hub" not in content:
        content = content.replace(
            "<p>The content engine is being deployed. Links and articles will appear here soon.</p>",
            "<p>The content engine is being deployed. Links and articles will appear here soon.</p>\n" + hub_link + (
                "  <p>Newest articles:</p>\n  <ul>\n" + articles_html + "  </ul>\n" if articles_html else ""
            ),
        )
    else:
        # Already has hub link; ensure we have latest article list
        if articles_html and "Newest articles:" not in content:
            content = content.replace(
                hub_link,
                hub_link + "  <p>Newest articles:</p>\n  <ul>\n" + articles_html + "  </ul>\n",
            )
    index_path.write_text(content, encoding="utf-8")
    print(f"  {index_path.relative_to(out_dir)} (updated)")


def main() -> None:
    config = load_config(CONFIG_PATH)
    production_category = (config.get("production_category") or "ai-marketing-automation").strip()
    public = PUBLIC_DIR
    public.mkdir(parents=True, exist_ok=True)

    print("Rendering production articles...")
    articles = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
    for meta, path in articles:
        _render_article(path, public)

    print("Rendering production hub...")
    hub_path = HUBS_DIR / f"{production_category}.md"
    if hub_path.exists():
        _render_hub(hub_path, public)
    else:
        print(f"  (no {hub_path.name})")

    print("Updating public/index.html...")
    _update_index(public, production_category, articles)

    print("Done.")


if __name__ == "__main__":
    main()
