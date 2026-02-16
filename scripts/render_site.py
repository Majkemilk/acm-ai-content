#!/usr/bin/env python3
"""
Minimal static renderer: Markdown (content/) -> HTML (public/). Stdlib only.
Renders production articles and production hub; updates public/index.html.
"""

import html
import math
import re
import shutil
from datetime import date, datetime
from pathlib import Path

from content_index import get_production_articles, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
HUBS_DIR = PROJECT_ROOT / "content" / "hubs"
PUBLIC_DIR = PROJECT_ROOT / "public"
INDEX_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "index.html"

INLINE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
# Internal article link: [text](/articles/slug/) or [text](/articles/slug) or [text](/articles/slug#anchor)
INTERNAL_ARTICLE_LINK = re.compile(r"\[([^\]]*)\]\((/articles/[^)]*)\)")


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


def _word_count_md(md_body: str) -> int:
    """Approximate word count from markdown: strip fenced code blocks, then split on whitespace."""
    s = re.sub(r"```[\s\S]*?```", " ", md_body)
    return len(s.split())


def _reading_time_min(words: int) -> int:
    """Reading time in minutes at 200 wpm, minimum 1."""
    return max(1, math.ceil(words / 200))


def _updated_date_iso(meta: dict, path: Path) -> str:
    """Updated date YYYY-MM-DD from front matter or file mtime."""
    raw = (meta.get("last_updated") or meta.get("updated") or "").strip()
    if raw and len(raw) >= 10:
        try:
            y, m, d = int(raw[:4]), int(raw[5:7]), int(raw[8:10])
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except (ValueError, IndexError):
            pass
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        return datetime.now().strftime("%Y-%m-%d")


def _extract_lead(meta: dict, body_html: str) -> str:
    """1–2 sentences: excerpt/summary from meta, else first <p> from body, strip tags, trim ~220 chars."""
    explicit = (meta.get("excerpt") or meta.get("summary") or "").strip()
    if explicit:
        out = _escape(explicit)
        return out[:220].rsplit(" ", 1)[0] if len(out) > 220 else out
    m = re.search(r"<p>([\s\S]*?)</p>", body_html)
    if not m:
        return ""
    text = re.sub(r"<[^>]+>", "", m.group(1))
    text = html.unescape(text).strip()
    if not text:
        return ""
    out = _escape(text)
    return out[:220].rsplit(" ", 1)[0] if len(out) > 220 else out


def _article_meta_block(updated_iso: str, reading_min: int, category: str | None, lead: str) -> str:
    """HTML for meta block under H1 (articles only)."""
    parts = [f'<span>Updated: {_escape(updated_iso)}</span>', "<span> · </span>", f"<span>Reading time: {reading_min} min</span>"]
    if category:
        parts.append("<span> · </span>")
        parts.append(f"<span>Category: {_escape(category)}</span>")
    meta_html = '<p class="page-meta">\n  ' + "\n  ".join(parts) + "\n</p>"
    if lead:
        return meta_html + f'\n<p class="page-lead">{lead}</p>'
    return meta_html


def _strip_invalid_internal_links(body: str, existing_slugs: set[str] | None) -> str:
    """Replace [text](/articles/slug/) with just text when slug is not in existing_slugs. Keeps valid links unchanged."""
    if existing_slugs is None:
        return body

    def repl(match):
        link_text, url = match.group(1), match.group(2)
        if not url.startswith("/articles/"):
            return match.group(0)
        # Slug: path after /articles/ up to # or end, trailing / stripped
        slug = url[10:].split("#")[0].strip("/")
        if slug in existing_slugs:
            return match.group(0)
        return link_text

    return INTERNAL_ARTICLE_LINK.sub(repl, body)


AFFILIATE_DISCLOSURE_TEXT = (
    "Some links on this page are affiliate links. If you make a purchase through these links, "
    "we may earn a commission at no extra cost to you."
)


def _md_to_html(body: str, existing_slugs: set[str] | None = None) -> str:
    """Minimal markdown to HTML: headings, - and 1. lists, paragraphs, [text](url), ``` code."""
    body = _strip_invalid_internal_links(body, existing_slugs)
    # Replace affiliate disclosure placeholder with standard text (before generic mustache removal)
    body = body.replace("{{AFFILIATE_DISCLOSURE}}", AFFILIATE_DISCLOSURE_TEXT)
    # Usuń mustache placeholdery {{...}}
    body = re.sub(r"\{\{[^}]+\}\}", "", body)
    # Usuń sekcję Verification policy (editors only)
    body = re.sub(
        r"^## Verification policy \(editors only\).*?(?=^##|\Z)",
        "",
        body,
        flags=re.DOTALL | re.MULTILINE,
    )
    # Usuń blok czterech linii metadanych (Content type, Category, Primary keyword, Last updated)
    body = re.sub(
        r"^\*\*Content type:\*\* .+\n\*\*Category:\*\* .+\n\*\*Primary keyword:\*\* .+\n\*\*Last updated:\*\* .+\n",
        "",
        body,
        flags=re.MULTILINE,
    )
    # Usuń znane sekcje, które powinny być puste (Tools mentioned, CTA, Pre-publish checklist).
    # Disclosure is kept so {{AFFILIATE_DISCLOSURE}} (replaced above) is shown.
    for section in ["Tools mentioned", "CTA", "Pre-publish checklist"]:
        pattern = r"^#{1,3}\s*" + re.escape(section) + r"\s*\n.*?(?=^#{1,3}|\Z)"
        body = re.sub(pattern, "", body, flags=re.DOTALL | re.MULTILINE)
    # Usuń puste sekcje (nagłówek + zawartość, jeśli po usunięciu placeholderów nie ma treści)
    section_pattern = r"(^#{2,3}\s+[^\n]+\n)(.*?)(?=^#{1,3}|\Z)"

    def remove_empty_section(match):
        header = match.group(1)
        content = match.group(2)
        if re.search(r"[a-zA-Z]", content):
            return header + content
        return ""

    body = re.sub(section_pattern, remove_empty_section, body, flags=re.DOTALL | re.MULTILINE)
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


def _footer_html() -> str:
    return (
        '<footer>\n'
        '    <p><a href="/robots.txt">robots.txt</a> · <a href="/sitemap.xml">sitemap.xml</a> · '
        '<a href="/privacy.html">Privacy Policy</a></p>\n'
        '</footer>'
    )


def _wrap_page(title: str, body_html: str, last_updated: str | None = None) -> str:
    meta = ""
    if last_updated:
        meta = f'<div class="meta">Last updated: {_escape(last_updated)}</div>\n'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape(title)}</title>
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
    <div class="container">
        {meta}
        {body_html}
        {_footer_html()}
    </div>
</body>
</html>"""


def _render_article(path: Path, out_dir: Path, existing_slugs: set[str] | None = None) -> None:
    meta, body = _parse_md_file(path)
    slug = meta.get("slug") or path.stem
    title = (meta.get("title") or slug).strip()
    updated_iso = _updated_date_iso(meta, path)
    body_html = _md_to_html(body, existing_slugs)
    # Style the affiliate disclosure paragraph
    disclosure_para = "<p>" + _escape(AFFILIATE_DISCLOSURE_TEXT) + "</p>"
    body_html = body_html.replace(disclosure_para, '<p class="affiliate-disclosure">' + _escape(AFFILIATE_DISCLOSURE_TEXT) + "</p>", 1)
    words = _word_count_md(body)
    reading_min = _reading_time_min(words)
    html_path = out_dir / "articles" / slug / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(_wrap_page(title, body_html, updated_iso), encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")


def _render_hub(path: Path, out_dir: Path, existing_slugs: set[str] | None = None) -> None:
    meta, body = _parse_md_file(path)
    slug = meta.get("slug") or path.stem
    title = (meta.get("title") or "").strip()
    if not title and body.lstrip().startswith("# "):
        title = body.lstrip().split("\n", 1)[0].replace("# ", "").strip()
    if not title:
        title = slug
    body_html = _md_to_html(body, existing_slugs)
    html_path = out_dir / "hubs" / slug / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(_wrap_page(title, body_html), encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")


def _update_index(out_dir: Path, production_category: str, articles: list[tuple[dict, Path]]) -> None:
    index_path = out_dir / "index.html"
    sorted_articles = sorted(articles, key=lambda x: _sort_key_newest(x[0], x[1]), reverse=True)[:5]
    articles_html = "".join(
        f'      <li><a href="/articles/{a[0].get("slug", a[1].stem)}/">{_escape((a[0].get("title") or a[1].stem).strip())}</a></li>\n'
        for a in sorted_articles
    )
    indent = "    "
    newest_block = indent + "<p>Newest articles:</p>\n" + indent + "<ul>\n" + articles_html + indent + "</ul>\n" if articles_html else ""
    hub_link = f'{indent}<p><a href="/hubs/{_escape(production_category)}/">AI Marketing Automation hub</a></p>\n'
    dynamic_content = hub_link + (newest_block if newest_block else "")

    if INDEX_TEMPLATE_PATH.exists():
        content = INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("<!-- DYNAMIC_CONTENT -->", dynamic_content, 1)
    else:
        # Fallback: build full page with static footer (no template file)
        footer = '  <footer>\n    <p><a href="/robots.txt">robots.txt</a> · <a href="/sitemap.xml">sitemap.xml</a> · <a href="/privacy.html">Privacy Policy</a></p>\n  </footer>\n'
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Flowtaro</title>\n  <link rel=\"stylesheet\" href=\"/assets/styles.css\">\n</head>\n<body>\n"
            "  <div class=\"container\">\n"
            + dynamic_content
            + "\n"
            + footer
            + "  </div>\n</body>\n</html>\n"
        )

    index_path.write_text(content, encoding="utf-8")
    print(f"  {index_path.relative_to(out_dir)} (updated)")


def _write_privacy_page(out_dir: Path) -> None:
    """Generate public/privacy.html from index template with placeholder content."""
    privacy_placeholder = """
    <h1>Privacy Policy</h1>
    <p>This page will be updated with our privacy policy. Please check back soon.</p>
"""
    if INDEX_TEMPLATE_PATH.exists():
        content = INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("<!-- DYNAMIC_CONTENT -->", privacy_placeholder.strip(), 1)
        content = content.replace("<title>Flowtaro</title>", "<title>Privacy Policy - Flowtaro</title>", 1)
    else:
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Privacy Policy - Flowtaro</title>\n  <link rel=\"stylesheet\" href=\"/assets/styles.css\">\n</head>\n<body>\n"
            "  <div class=\"container\">\n"
            + privacy_placeholder
            + "\n  <footer>\n    <p><a href=\"/robots.txt\">robots.txt</a> · <a href=\"/sitemap.xml\">sitemap.xml</a> · <a href=\"/privacy.html\">Privacy Policy</a></p>\n  </footer>\n"
            "  </div>\n</body>\n</html>\n"
        )
    privacy_path = out_dir / "privacy.html"
    privacy_path.write_text(content, encoding="utf-8")
    print(f"  {privacy_path.relative_to(out_dir)} (updated)")


def _ensure_images(out_dir: Path) -> None:
    """Ensure project images/ exists; copy avatar to public/images/ if present."""
    images_root = PROJECT_ROOT / "images"
    images_root.mkdir(parents=True, exist_ok=True)
    src = images_root / "avatar.jpg"
    dst_dir = out_dir / "images"
    dst = dst_dir / "avatar.jpg"
    if src.exists():
        dst_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except OSError:
            pass


def main() -> None:
    config = load_config(CONFIG_PATH)
    production_category = (config.get("production_category") or "ai-marketing-automation").strip()
    public = PUBLIC_DIR
    public.mkdir(parents=True, exist_ok=True)

    print("Rendering production articles...")
    articles = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
    existing_slugs = {meta.get("slug") or path.stem for meta, path in articles}
    for meta, path in articles:
        _render_article(path, public, existing_slugs)

    print("Rendering production hub...")
    hub_path = HUBS_DIR / f"{production_category}.md"
    if hub_path.exists():
        _render_hub(hub_path, public, existing_slugs)
    else:
        print(f"  (no {hub_path.name})")

    print("Updating public/index.html...")
    _update_index(public, production_category, articles)

    print("Writing privacy page...")
    _write_privacy_page(public)

    _ensure_images(public)

    print("Done.")

    try:
        (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)
        (PROJECT_ROOT / "logs" / "last_run_render_site.txt").write_text(datetime.now().isoformat(), encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    main()
