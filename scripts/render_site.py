#!/usr/bin/env python3
"""
Minimal static renderer: Markdown (content/) -> HTML (public/). Stdlib only.
Renders production articles and production hub; updates public/index.html.
"""

import html
import math
import random
import re
import shutil
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

from content_index import get_production_articles, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
HUBS_DIR = PROJECT_ROOT / "content" / "hubs"
PUBLIC_DIR = PROJECT_ROOT / "public"
AFFILIATE_TOOLS_PATH = PROJECT_ROOT / "content" / "affiliate_tools.yaml"
INDEX_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "index.html"
HUB_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "hub.html"
ARTICLE_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "article.html"

INLINE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
# Internal article link: [text](/articles/slug/) or [text](/articles/slug) or [text](/articles/slug#anchor)
INTERNAL_ARTICLE_LINK = re.compile(r"\[([^\]]*)\]\((/articles/[^)]*)\)")

# Tags inside which we do not replace tool names with links
TOOL_LINK_SKIP_TAGS = frozenset(("a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre"))


def _parse_quoted_yaml_value(val: str) -> str:
    """Unquote a YAML value if quoted."""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1].replace('\\"', '"')
    return val


def _load_affiliate_tools(path: Path) -> list[tuple[str, str]]:
    """
    Load content/affiliate_tools.yaml and return list of (name, url).
    url is affiliate_link; empty string if missing or empty. Stdlib only.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    text = "\n".join(lines)
    if "tools:" not in text:
        return []
    start = text.index("tools:") + 6
    rest = text[start:].strip()
    if not rest.startswith("-"):
        return []
    items: list[tuple[str, str]] = []
    current_name = ""
    current_url = ""
    for line in rest.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_name:
                items.append((current_name, current_url or ""))
            current_name = ""
            current_url = ""
            part = stripped[2:].strip()
            kv = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(.*)$", part)
            if kv:
                k, v = kv.group(1), _parse_quoted_yaml_value(kv.group(2))
                if k == "name":
                    current_name = v
                elif k == "affiliate_link":
                    current_url = v
            continue
        kv = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(.*)$", stripped)
        if kv:
            k, v = kv.group(1), _parse_quoted_yaml_value(kv.group(2))
            if k == "name":
                current_name = v
            elif k == "affiliate_link":
                current_url = v
    if current_name:
        items.append((current_name, current_url or ""))
    return items


def _replace_tool_names_in_text(text: str, tool_list: list[tuple[str, str]]) -> str:
    """
    Replace tool names in plain text with <a href="url">matched</a>.
    Word boundaries, case-insensitive. Longer names first to avoid partial matches.
    """
    if not text or not tool_list:
        return text
    # Sort by name length descending so e.g. "Pictory" is tried before "Otter" if they could overlap
    sorted_tools = sorted([t for t in tool_list if t[1]], key=lambda x: -len(x[0]))
    if not sorted_tools:
        return text
    result = []
    remaining = text
    while remaining:
        best_start: int | None = None
        best_end: int | None = None
        best_url = ""
        best_matched = ""
        for name, url in sorted_tools:
            m = re.search(r"\b" + re.escape(name) + r"\b", remaining, re.IGNORECASE)
            if m and (best_start is None or m.start() < best_start):
                best_start, best_end = m.start(), m.end()
                best_url = url
                best_matched = remaining[m.start() : m.end()]
        if best_start is None:
            result.append(remaining)
            break
        result.append(remaining[:best_start])
        result.append(f'<a href="{_escape(best_url)}">{_escape(best_matched)}</a>')
        remaining = remaining[best_end:]
    return "".join(result)


class _ToolLinkReplacer(HTMLParser):
    """HTMLParser that replaces tool names with links in text nodes, skipping links/headings/code/pre."""

    def __init__(self, tool_list: list[tuple[str, str]]) -> None:
        super().__init__()
        self.tool_list = tool_list
        self.output: list[str] = []
        self.tag_stack: list[str] = []

    def _in_skip_tag(self) -> bool:
        return bool(self.tag_stack and self.tag_stack[-1] in TOOL_LINK_SKIP_TAGS)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag_stack.append(tag)
        attrs_str = "".join(f' {k}="{_escape(v)}"' if v else f" {k}" for k, v in attrs)
        self.output.append(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag: str) -> None:
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
        self.output.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_str = "".join(f' {k}="{_escape(v)}"' if v else f" {k}" for k, v in attrs)
        self.output.append(f"<{tag}{attrs_str}>")

    def handle_data(self, data: str) -> None:
        if self._in_skip_tag():
            self.output.append(data)
        else:
            self.output.append(_replace_tool_names_in_text(data, self.tool_list))

    def get_result(self) -> str:
        return "".join(self.output)


def replace_tool_names_with_links(html: str, tool_list: list[tuple[str, str]]) -> str:
    """Replace tool names in article HTML with links; skip inside a, h1–h6, code, pre."""
    if not tool_list:
        return html
    parser = _ToolLinkReplacer(tool_list)
    try:
        parser.feed(html)
        return parser.get_result()
    except Exception:
        return html


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
    """1–2 sentences: lead/excerpt/summary from meta, else first <p> from body, strip tags, trim ~220 chars."""
    explicit = (meta.get("lead") or meta.get("excerpt") or meta.get("summary") or "").strip()
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


def enhance_article(html: str) -> str:
    """
    Wraps special sections (Decision rules, Tradeoffs, Failure modes,
    SOP checklist, Template 1, Template 2) with styled divs.
    """
    decision_sections = [
        "Decision rules:",
        "Tradeoffs:",
        "Failure modes:",
        "SOP checklist:",
    ]
    template_sections = [
        "Template 1:",
        "Template 2:",
    ]

    def wrap_section(match: re.Match[str], section_class: str) -> str:
        header = match.group(1)
        content = match.group(2)
        return f'<div class="{section_class}">{header}{content}</div>'

    decision_class = "bg-indigo-50 p-6 rounded-lg border border-indigo-100 my-6"
    for sec in decision_sections:
        pattern = rf"(<h3[^>]*>{re.escape(sec)}</h3>)(.*?)(?=<h[23]|\Z)"
        html = re.sub(
            pattern,
            lambda m, c=decision_class: wrap_section(m, c),
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

    template_class = "bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow mb-4"
    for sec in template_sections:
        pattern = rf"(<h3[^>]*>{re.escape(sec)}</h3>)(.*?)(?=<h[23]|\Z)"
        html = re.sub(
            pattern,
            lambda m, c=template_class: wrap_section(m, c),
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

    return html


def _article_meta_block(updated_iso: str, reading_min: int, category_slug: str | None, lead: str) -> str:
    """HTML for meta block under H1 (articles only). Styled badge row with category, date, reading time."""
    parts: list[str] = []
    if category_slug:
        slug_esc = _escape(category_slug)
        display = category_slug.replace("-", " ").title()
        display_esc = _escape(display)
        parts.append(
            f'<span class="bg-indigo-50 text-indigo-700 px-2 py-1 rounded">'
            f'<a href="/hubs/{slug_esc}/" class="hover:underline">{display_esc}</a></span>'
        )
        parts.append("<span>&bull;</span>")
    parts.append(f"<span>Updated: {_escape(updated_iso)}</span>")
    parts.append("<span>&bull;</span>")
    parts.append(f"<span>{_escape(str(reading_min))} min read</span>")
    meta_html = (
        '<div class="flex flex-wrap items-center gap-3 text-sm font-medium text-gray-500 mb-6">\n  '
        + "\n  ".join(parts)
        + "\n</div>"
    )
    if lead:
        return meta_html + f'\n<p class="text-xl text-gray-600 leading-relaxed border-l-4 border-indigo-500 pl-4 italic mb-8">{lead}</p>'
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
    body_html = "\n".join(out)
    # Replace affiliate disclosure paragraph with styled div
    disclosure_div = (
        '<div class="mt-8 p-4 bg-gray-100 border-l-4 border-[rgb(23,38,107)] text-gray-700 text-sm">\n'
        "    Some links on this page are affiliate links. If you make a purchase through these links, "
        "we may earn a commission at no extra cost to you.\n"
        "</div>"
    )
    body_html = body_html.replace(
        "<p>" + _escape(AFFILIATE_DISCLOSURE_TEXT) + "</p>",
        disclosure_div,
        1,
    )
    return body_html


def _footer_html() -> str:
    return (
        '<footer>\n'
        '    <p><a href="/robots.txt">robots.txt</a> · <a href="/sitemap.xml">sitemap.xml</a> · '
        '<a href="/privacy.html">Privacy Policy</a></p>\n'
        '</footer>'
    )


def _wrap_page(title: str, body_html: str, last_updated: str | None = None) -> str:
    """Fallback page for articles when ARTICLE_TEMPLATE_PATH is missing. Uses relative path to CSS from articles/slug/."""
    meta = ""
    if last_updated:
        meta = f'<div class="meta">Last updated: {_escape(last_updated)}</div>\n'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape(title)}</title>
    <link rel="stylesheet" href="../../assets/styles.css">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body>
    <div class="flowtaro-container">
        {meta}
        {body_html}
        {_footer_html()}
    </div>
</body>
</html>"""


def _parse_html_article(path: Path) -> tuple[dict, str] | None:
    """Read .html article file: parse frontmatter from first <!-- ... -->, return (meta, body_html)."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.match(r"\s*<!--\s*(.*?)\s*-->", content, re.DOTALL)
    if not m:
        return None
    end = m.end()
    block = m.group(1).strip()
    meta: dict[str, str] = {}
    for line in block.split("\n"):
        m2 = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if m2:
            key, raw = m2.group(1), m2.group(2).strip()
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw[1:-1].replace('\\"', '"')
            elif raw.startswith("'") and raw.endswith("'"):
                raw = raw[1:-1]
            meta[key] = raw
    meta.setdefault("slug", path.stem)
    body_html = content[end:].lstrip()
    return (meta, body_html)


def _word_count_html(html: str) -> int:
    """Approximate word count from HTML: strip tags, then split on whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    return len(text.split())


def _render_article(path: Path, out_dir: Path, existing_slugs: set[str] | None = None) -> None:
    is_html = path.suffix.lower() == ".html"
    if is_html:
        parsed = _parse_html_article(path)
        if not parsed:
            print(f"  Skip {path.name}: invalid HTML frontmatter")
            return
        meta, body_html = parsed
        slug = meta.get("slug") or path.stem
        title = (meta.get("title") or slug).strip()
        updated_iso = (meta.get("last_updated") or meta.get("updated") or "").strip()[:10] or _updated_date_iso(meta, path)
        words = _word_count_html(body_html)
        reading_min = _reading_time_min(words)
    else:
        meta, body = _parse_md_file(path)
        slug = meta.get("slug") or path.stem
        title = (meta.get("title") or slug).strip()
        updated_iso = _updated_date_iso(meta, path)
        body_html = _md_to_html(body, existing_slugs)
        body_html = enhance_article(body_html)
        tool_list = _load_affiliate_tools(AFFILIATE_TOOLS_PATH)
        body_html = replace_tool_names_with_links(body_html, tool_list)
        words = _word_count_md(body)
        reading_min = _reading_time_min(words)

    html_path = out_dir / "articles" / slug / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)

    category_slug = (meta.get("category") or meta.get("category_slug") or "").strip() or None
    lead = _extract_lead(meta, body_html)
    # Prepend meta block (category badge, date, reading time, lead) for all article types (MD and HTML)
    meta_html = _article_meta_block(updated_iso, reading_min, category_slug, lead)
    full_body_html = meta_html + body_html

    # Generate "Read Next" section
    read_next_html = ""
    try:
        all_articles = get_production_articles(ARTICLES_DIR, CONFIG_PATH)
        other_articles = [a for a in all_articles if (a[0].get("slug") or a[1].stem) != slug]
        selected = random.sample(other_articles, min(3, len(other_articles)))
        if selected:
            read_next_html = '<section class="bg-gray-50 p-6 rounded-lg mt-8">'
            read_next_html += '<h3 class="font-bold text-gray-900 mb-3">Read Next:</h3>'
            read_next_html += '<ul class="space-y-2">'
            for art_meta, art_path in selected:
                art_title = _escape(art_meta.get("title") or "Untitled")
                article_slug = _escape(art_meta.get("slug") or art_path.stem)
                read_next_html += f'<li><a href="/articles/{article_slug}/" class="text-indigo-600 hover:text-indigo-800 hover:underline transition-colors">{art_title}</a></li>'
            read_next_html += "</ul></section>"
    except Exception as e:
        print(f"Warning: Could not generate Read Next section: {e}")

    full_body_html += read_next_html

    # Affiliate disclosure (yellow box, below Read Next, above footer)
    disclosure_html = """
<div class="mt-8 p-4 bg-yellow-50 border-l-4 border-yellow-400 text-yellow-800 text-sm rounded-r">
    <strong>Disclosure:</strong> Some links on this page are affiliate links. If you make a purchase through these links, we may earn a commission at no extra cost to you.
</div>"""
    full_body_html += disclosure_html

    article_body_html = f"<article class=\"article-body\">{full_body_html}</article>"
    article_content = article_body_html

    if ARTICLE_TEMPLATE_PATH.exists():
        content = ARTICLE_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("{{TITLE}}", _escape(title), 1)
        content = content.replace("{{STYLESHEET_HREF}}", "../../assets/styles.css", 1)
        content = content.replace("<!-- ARTICLE_CONTENT -->", article_content, 1)
    else:
        content = _wrap_page(title, body_html, updated_iso)
    html_path.write_text(content, encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")


def _parse_hub_body(body: str) -> tuple[str, list[tuple[str, list[tuple[str, str]]]]]:
    """Return (intro_md, sections) where sections is list of (section_title, list of (link_text, slug))."""
    # Split by \n## so first block is intro (may include # Title and paragraphs)
    parts = re.split(r"\n## ", body.strip(), maxsplit=0)
    intro_md = (parts[0].strip() if parts else "").lstrip()
    # Drop leading # from first line if present so intro doesn't duplicate hub title
    if intro_md.startswith("# "):
        intro_md = re.sub(r"^#\s+[^\n]+\n?", "", intro_md, count=1)
    intro_md = intro_md.strip()
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    for block in parts[1:]:
        lines = block.split("\n")
        if not lines:
            continue
        section_title = lines[0].strip()
        links: list[tuple[str, str]] = []
        for line in lines[1:]:
            line = line.strip()
            if not line.startswith("- "):
                continue
            m = INTERNAL_ARTICLE_LINK.search(line)
            if m:
                link_text, url = m.group(1).strip(), m.group(2)
                slug = url.replace("/articles/", "").split("#")[0].strip("/")
                links.append((link_text, slug))
        sections.append((section_title, links))
    return intro_md, sections


def _build_hub_content(
    hub_title: str,
    intro_html: str,
    sections: list[tuple[str, list[tuple[str, str]]]],
    slug_to_meta: dict[str, dict],
) -> str:
    """Build HTML for hub DYNAMIC_CONTENT: link home, title, intro, then per-section h2 + card grid."""
    out_parts: list[str] = []
    out_parts.append(
        '<h2 class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center">'
        '<a href="/" class="text-[rgb(23,38,107)] hover:underline">Home</a></h2>\n'
    )
    out_parts.append(f'<h1 class="text-2xl font-bold mb-6 text-[#17266B] text-center">{_escape(hub_title)}</h1>\n')
    if intro_html.strip():
        out_parts.append(f'<div class="mb-8 text-gray-700">\n{intro_html.strip()}\n</div>\n')
    for section_title, links in sections:
        out_parts.append(
            f'<h2 class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center">{_escape(section_title)}</h2>\n'
        )
        if links:
            out_parts.append('<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">\n')
            for link_text, slug in links:
                meta = slug_to_meta.get(slug) or {}
                title_esc = _escape(link_text)
                date_esc = _escape(meta.get("last_updated") or meta.get("updated") or "")
                slug_esc = _escape(slug)
                out_parts.append(
                    f'''        <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition">
            <h3 class="text-xl font-semibold mb-2">
                <a href="/articles/{slug_esc}/" class="text-gray-900 hover:text-[#17266B]">{title_esc}</a>
            </h3>
            <p class="text-gray-600 text-sm mb-4">{date_esc}</p>
            <a href="/articles/{slug_esc}/" class="inline-block bg-[#17266B] text-white px-4 py-2 rounded hover:bg-[#0f1a4a] transition">Read more</a>
        </div>
'''
                )
            out_parts.append("</div>\n")
        else:
            out_parts.append('<p class="text-gray-600">No articles in this section.</p>\n')
    return "".join(out_parts)


def _render_hub(
    path: Path,
    out_dir: Path,
    articles: list[tuple[dict, Path]],
    existing_slugs: set[str] | None = None,
) -> None:
    meta, body = _parse_md_file(path)
    slug = meta.get("slug") or path.stem
    title = (meta.get("title") or "").strip()
    if not title and body.lstrip().startswith("# "):
        title = body.lstrip().split("\n", 1)[0].replace("# ", "").strip()
    if not title:
        title = slug
    # Hub body may be prebuilt HTML (from generate_hubs.py) or Markdown lists
    if body.strip().startswith("<"):
        home_link = (
            '<h2 class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center">'
            '<a href="/" class="text-[rgb(23,38,107)] hover:underline">Home</a></h2>\n'
        )
        dynamic_content = home_link + body
    else:
        intro_md, sections = _parse_hub_body(body)
        intro_html = _md_to_html(intro_md, existing_slugs) if intro_md else ""
        slug_to_meta = {}
        for art_meta, art_path in articles:
            s = art_meta.get("slug") or art_path.stem
            slug_to_meta[s] = {**art_meta, "last_updated": _updated_date_iso(art_meta, art_path)}
        dynamic_content = _build_hub_content(title, intro_html, sections, slug_to_meta)
    html_path = out_dir / "hubs" / slug / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    if HUB_TEMPLATE_PATH.exists():
        content = HUB_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("HUB_TITLE_PLACEHOLDER", _escape(title), 1)
        content = content.replace("{{STYLESHEET_HREF}}", "../../assets/styles.css", 1)
        content = content.replace("<!-- DYNAMIC_CONTENT -->", dynamic_content, 1)
    else:
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            f"  <title>{_escape(title)}</title>\n  <link rel=\"stylesheet\" href=\"../../assets/styles.css\">\n"
            "<script src=\"https://cdn.tailwindcss.com\"></script>\n</head>\n<body>\n"
            "  <header class=\"site-header\"><div class=\"header-inner\"></div></header>\n"
            "  <div class=\"flowtaro-container\">\n"
            + dynamic_content
            + "\n  </div>\n"
            "  <footer class=\"site-footer text-center\"><div class=\"site-footer-inner\">"
            "<p>&copy; 2026 Flowtaro. <a href=\"/privacy.html\">Privacy Policy</a></p></div></footer>\n"
            "</body>\n</html>\n"
        )
    html_path.write_text(content, encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")


def _update_index(out_dir: Path, production_category: str, articles: list[tuple[dict, Path]]) -> None:
    index_path = out_dir / "index.html"
    newest = sorted(articles, key=lambda x: _sort_key_newest(x[0], x[1]), reverse=True)[:5]
    hub_link = f'<h2 class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center"><a href="/hubs/{_escape(production_category)}/" class="text-[rgb(23,38,107)] hover:underline">All articles</a></h2>\n'
    articles_html = ""
    if newest:
        articles_html = '<h2 class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center">Newest articles</h2>\n'
        articles_html += '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">\n'
        for meta, path in newest:
            slug = meta.get("slug") or path.stem
            title_esc = _escape((meta.get("title") or slug).strip())
            date_esc = _escape(meta.get("last_updated") or _updated_date_iso(meta, path))
            slug_esc = _escape(slug)
            articles_html += f'''        <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition">
            <h3 class="text-xl font-semibold mb-2">
                <a href="/articles/{slug_esc}/" class="text-gray-900 hover:text-[#17266B]">{title_esc}</a>
            </h3>
            <p class="text-gray-600 text-sm mb-4">{date_esc}</p>
            <a href="/articles/{slug_esc}/" class="inline-block bg-[#17266B] text-white px-4 py-2 rounded hover:bg-[#0f1a4a] transition">Read more</a>
        </div>
'''
        articles_html += '</div>\n'
    else:
        articles_html = '<p class="text-gray-600">No articles yet.</p>\n'
    dynamic_content = hub_link + articles_html

    if INDEX_TEMPLATE_PATH.exists():
        content = INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("{{STYLESHEET_HREF}}", "assets/styles.css", 1)
        content = content.replace("<!-- DYNAMIC_CONTENT -->", dynamic_content, 1)
    else:
        # Fallback: build full page with static footer (no template file)
        footer = '  <footer>\n    <p><a href="/robots.txt">robots.txt</a> · <a href="/sitemap.xml">sitemap.xml</a> · <a href="/privacy.html">Privacy Policy</a></p>\n  </footer>\n'
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Flowtaro</title>\n  <link rel=\"stylesheet\" href=\"assets/styles.css\">\n</head>\n<body>\n"
            "  <div class=\"flowtaro-container\">\n"
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
        content = content.replace("{{STYLESHEET_HREF}}", "assets/styles.css", 1)
        content = content.replace("<!-- DYNAMIC_CONTENT -->", privacy_placeholder.strip(), 1)
        content = content.replace("<title>Flowtaro</title>", "<title>Privacy Policy - Flowtaro</title>", 1)
    else:
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Privacy Policy - Flowtaro</title>\n  <link rel=\"stylesheet\" href=\"assets/styles.css\">\n</head>\n<body>\n"
            "  <div class=\"flowtaro-container\">\n"
            + privacy_placeholder
            + "\n  <footer>\n    <p><a href=\"/robots.txt\">robots.txt</a> · <a href=\"/sitemap.xml\">sitemap.xml</a> · <a href=\"/privacy.html\">Privacy Policy</a></p>\n  </footer>\n"
            "  </div>\n</body>\n</html>\n"
        )
    privacy_path = out_dir / "privacy.html"
    privacy_path.write_text(content, encoding="utf-8")
    print(f"  {privacy_path.relative_to(out_dir)} (updated)")


def _ensure_images(out_dir: Path) -> None:
    """Ensure project images/ exists; copy avatar and logo to public/images/ if present."""
    images_root = PROJECT_ROOT / "images"
    images_root.mkdir(parents=True, exist_ok=True)
    dst_dir = out_dir / "images"
    for name in ("avatar.jpg", "logo.webp"):
        src = images_root / name
        dst = dst_dir / name
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
        _render_hub(hub_path, public, articles, existing_slugs)
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
