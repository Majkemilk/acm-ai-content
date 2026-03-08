#!/usr/bin/env python3
"""
Minimal static renderer: Markdown (content/) -> HTML (public/). Stdlib only.
Renders production articles and production hub; updates public/index.html.
Supports --site (main | pl), --out-dir, --base-url for subdomain build (e.g. pl.flowtaro.com).
"""

import argparse
import hashlib
import html
import json
import math
import os
import random
import re
import shutil
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

# Windows path length limit (MAX_PATH 260); keep under to avoid FileNotFoundError 206
MAX_PATH_LEN = 250

from content_index import (
    get_production_articles,
    get_hubs_list_for_site,
    get_category_slugs_for_site,
    load_config,
)
from content_root import get_content_root_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = PROJECT_ROOT / "public"
# affiliate_tools współdzielony – zawsze z content/
AFFILIATE_TOOLS_PATH = PROJECT_ROOT / "content" / "affiliate_tools.yaml"
INDEX_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "index.html"
HUB_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "hub.html"
ARTICLE_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "article.html"
PRIVACY_MD_PATH = PROJECT_ROOT / "Privacy Policy.md"
PRIVACY_DOCX_PATH = PROJECT_ROOT / "privacy.docx"

try:
    from docx import Document as DocxDocument
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False

INLINE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
# Internal article link: [text](/articles/slug/) or [text](/articles/slug) or [text](/articles/slug#anchor)
INTERNAL_ARTICLE_LINK = re.compile(r"\[([^\]]*)\]\((/articles/[^)]*)\)")

# Tags inside which we do not replace tool names with links
TOOL_LINK_SKIP_TAGS = frozenset(("a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre"))

# Content-type title prefixes to strip for display (EN and PL: same reader-friendly title in H1 and <title>)
_TITLE_PREFIXES_STRIP = (
    "products in category: ", "best in category: ", "comparison of ", "guide to ",
    "how to ", "sales: ", "best ", "review: ",
)


def _strip_content_type_prefix_from_title(title: str) -> str:
    """Strip leading content-type prefix (case-insensitive) so H1 and <title> match PL style (no prefix)."""
    if not title or not title.strip():
        return title
    t = title.strip()
    lower = t.lower()
    for prefix in _TITLE_PREFIXES_STRIP:
        if lower.startswith(prefix):
            return t[len(prefix) :].strip() or t
    return t


def _slug_for_path(slug: str, out_dir: Path) -> str:
    """Return a filesystem-safe slug: same as slug if path fits in MAX_PATH_LEN, else shortened with hash suffix."""
    candidate = (out_dir / "articles" / slug / "index.html").resolve()
    if len(str(candidate)) <= MAX_PATH_LEN:
        return slug
    # Keep start of slug (date + start of title) and add short hash to keep unique and under limit
    prefix_len = min(80, len(slug))
    prefix = slug[:prefix_len].rstrip("-")
    digest = hashlib.md5(slug.encode("utf-8")).hexdigest()[:12]
    short = f"{prefix}-{digest}"
    return short


def _article_body_has_html_issues(body: str) -> bool:
    """True if article body has <pre> imbalance or orphan </ol>/</ul> in Try it yourself section."""
    if "<pre" not in body:
        return False
    opens = len(re.findall(r"<pre\b", body, flags=re.IGNORECASE))
    closes = len(re.findall(r"</pre\s*>", body, flags=re.IGNORECASE))
    if opens != closes:
        return True
    sections = re.split(r"<h2\s", body, flags=re.IGNORECASE)
    for i, sec in enumerate(sections):
        head = (sec[:300] if len(sec) > 300 else sec).lower()
        if "try it yourself" in head or "build your own ai prompt" in head:
            open_ol = len(re.findall(r"<ol\b", sec, flags=re.IGNORECASE))
            close_ol = len(re.findall(r"</ol\s*>", sec, flags=re.IGNORECASE))
            open_ul = len(re.findall(r"<ul\b", sec, flags=re.IGNORECASE))
            close_ul = len(re.findall(r"</ul\s*>", sec, flags=re.IGNORECASE))
            if close_ol > open_ol or close_ul > open_ul:
                return True
    return False


def _sanitize_article_html_body(body: str) -> str:
    """Last-line fix: Try it yourself <pre> </p> -> </pre> (heuristic) and remove orphan </ol>/</ul> in Try it yourself section."""
    # Fix unclosed <pre> in Try it yourself section: first <pre>...content...</p> -> ...</pre>
    try_start = body.lower().find("try it yourself")
    if try_start == -1:
        try_start = body.lower().find("build your own ai prompt")
    if try_start != -1 and "</p>" in body:
        h2_after = body.find("<h2", try_start + 1)
        if h2_after == -1:
            h2_after = len(body)
        section = body[try_start:h2_after]
        pre_then_p = re.compile(r"(<pre[^>]*>)((?:(?!</pre>).)*?)</p>", re.IGNORECASE | re.DOTALL)
        section_new, n = pre_then_p.subn(r"\1\2</pre>", section, count=1)
        if n == 1:
            body = body[:try_start] + section_new + body[h2_after:]
    # Remove orphan </ol>/</ul> in Try it yourself section
    sections = re.split(r"(<h2\s)", body, flags=re.IGNORECASE)
    if len(sections) >= 2:
        out = [sections[0]]
        for i in range(1, len(sections), 2):
            if i + 1 >= len(sections):
                out.append(sections[i])
                break
            out.append(sections[i])
            sec = sections[i + 1]
            head = (sec[:300] if len(sec) > 300 else sec).lower()
            if "try it yourself" in head or "build your own ai prompt" in head:
                open_ol = len(re.findall(r"<ol\b", sec, flags=re.IGNORECASE))
                close_ol = len(re.findall(r"</ol\s*>", sec, flags=re.IGNORECASE))
                open_ul = len(re.findall(r"<ul\b", sec, flags=re.IGNORECASE))
                close_ul = len(re.findall(r"</ul\s*>", sec, flags=re.IGNORECASE))
                for _ in range(close_ol - open_ol):
                    sec = sec.replace("</ol>", "", 1)
                for _ in range(close_ul - open_ul):
                    sec = sec.replace("</ul>", "", 1)
            out.append(sec)
        body = "".join(out)
    return body


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


def _set_source_status_filled(path: Path) -> None:
    """Set status to 'filled' in a .md file's frontmatter after it has been rendered to public."""
    if path.suffix.lower() != ".md":
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    if not text.startswith("---"):
        return
    end = text.find("\n---", 3)
    if end == -1:
        return
    fm = text[3:end]
    if re.search(r"^\s*status\s*:", fm, re.MULTILINE):
        fm_new = re.sub(r"^status\s*:\s*.*$", 'status: "filled"', fm, count=1, flags=re.MULTILINE)
    else:
        fm_new = fm.rstrip() + '\nstatus: "filled"\n'
    new_text = "---\n" + fm_new + "\n---\n" + text[end + 4 :]
    path.write_text(new_text, encoding="utf-8")


def _escape(s: str) -> str:
    return html.escape(s, quote=True)


def _build_nav_html(
    hubs: list[dict],
    site: str = "main",
    base_url_pl: str | None = None,
    base_url_main: str | None = None,
) -> str:
    """Build site nav: Home | hub1 | hub2 | Prompt Generator. For site=pl append link to main (Flowtaro). For site=main append link to pl (Problem Fix & Find) if base_url_pl set."""
    parts: list[str] = []
    parts.append('<a href="/" class="site-nav-link">Home</a>')
    for h in hubs:
        slug = (h.get("slug") or h.get("category") or "").strip()
        if not slug:
            continue
        label = (h.get("title") or slug).strip()
        url = f"/hubs/{_escape(slug)}/"
        parts.append(f'<a href="{url}" class="site-nav-link">{_escape(label)}</a>')
    parts.append('<a href="https://generator.flowtaro.com" class="site-nav-link">Prompt Generator</a>')
    if site == "pl" and base_url_main:
        parts.append(f'<a href="{_escape(base_url_main)}" class="site-nav-link">Flowtaro</a>')
    elif site == "main" and base_url_pl:
        parts.append(f'<a href="{_escape(base_url_pl)}" class="site-nav-link">Problem Fix &amp; Find</a>')
    return '<nav class="site-nav" aria-label="Main">' + " <span class=\"site-nav-sep\" aria-hidden=\"true\">|</span> ".join(parts) + "</nav>"


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
    SOP checklist) with styled divs.
    """
    decision_sections = [
        "Decision rules:",
        "Tradeoffs:",
        "Failure modes:",
        "SOP checklist:",
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

    return html


def _strip_leading_h1(html: str) -> str:
    """Remove the first <h1>...</h1> from html so we can show a single title from frontmatter above meta."""
    return re.sub(r"^\s*<h1(?:\s[^>]*)?>.*?</h1>\s*", "", html, count=1, flags=re.DOTALL | re.IGNORECASE).lstrip()


# CTA block inserted above "When NOT to use this" in articles
_PROMPT_GENERATOR_CTA_HTML = (
    '<div class="my-6 p-4 bg-gray-50 rounded-lg border border-gray-200">'
    '<p class="mb-0">To create a tailored prompt for your use case, try the '
    '<a href="https://generator.flowtaro.com" target="_blank" rel="noopener noreferrer">Flowtaro Prompt Generator</a>.</p>'
    "</div>\n\n"
)


def _inject_prompt_generator_cta(body_html: str) -> str:
    """Insert the Prompt Generator CTA block immediately above the first 'When NOT to use this' H2, if present."""
    # Match <h2 ...>When NOT to use this</h2> with optional attributes and whitespace
    pattern = re.compile(
        r"(\s*)(<h2(?:\s[^>]*)?>\s*When NOT to use this\s*</h2>)",
        re.IGNORECASE,
    )
    match = pattern.search(body_html)
    if not match:
        return body_html
    prefix_ws, h2_tag = match.group(1), match.group(2)
    insert = prefix_ws + _PROMPT_GENERATOR_CTA_HTML + h2_tag
    return pattern.sub(insert, body_html, count=1)


def _article_title_h1(title: str) -> str:
    """HTML for article title as H1 (visible at top of article, above meta and Introduction)."""
    return f'<h1 class="text-2xl font-bold mb-6 text-[#17266B]">{_escape(title)}</h1>\n'


# Locale strings for article UI (meta block, Read Next, disclosure). Keys: "en", "pl".
_LOCALE = {
    "en": {
        "audience_beginner": "Beginner",
        "audience_intermediate": "Intermediate",
        "audience_advanced": "Advanced",
        "meta_updated": "Updated:",
        "meta_min_read": "min read",
        "read_next_heading": "Read Next:",
        "disclosure_heading": "Disclosure:",
        "disclosure_body": "Some links on this page are affiliate links. If you make a purchase through these links, we may earn a commission at no extra cost to you.",
        "affiliate_disclosure_placeholder": "Some links on this page are affiliate links. If you make a purchase through these links, we may earn a commission at no extra cost to you.",
        "footer_privacy": "Privacy Policy",
        "footer_prompt_generator": "Prompt Generator",
    },
    "pl": {
        "audience_beginner": "Początkujący",
        "audience_intermediate": "Średniozaawansowany",
        "audience_advanced": "Zaawansowany",
        "meta_updated": "Aktualizacja:",
        "meta_min_read": "min czytania",
        "read_next_heading": "Czytaj dalej:",
        "disclosure_heading": "Informacja:",
        "disclosure_body": "Część linków na tej stronie to linki afiliacyjne. Jeśli dokonasz zakupu przez nie, możemy otrzymać prowizję bez dodatkowych kosztów dla Ciebie.",
        "affiliate_disclosure_placeholder": "Część linków na tej stronie to linki afiliacyjne. Jeśli dokonasz zakupu przez nie, możemy otrzymać prowizję bez dodatkowych kosztów dla Ciebie.",
        "footer_privacy": "Polityka prywatności",
        "footer_prompt_generator": "Prompt Generator",
    },
}

def _locale(lang: str) -> dict:
    """Return locale dict for lang; fallback to en if unknown."""
    return _LOCALE.get((lang or "en").strip().lower(), _LOCALE["en"])


_AUDIENCE_BADGE: dict[str, tuple[str, str]] = {
    "beginner": ("Beginner", "bg-green-50 text-green-700"),
    "intermediate": ("Intermediate", "bg-blue-50 text-blue-700"),
    "professional": ("Advanced", "bg-purple-50 text-purple-700"),
}

VALID_AUDIENCE_TYPES = frozenset(_AUDIENCE_BADGE.keys())


def _audience_label_and_css(audience_type: str, page_lang: str) -> tuple[str, str]:
    """Return (label, css_class) for audience badge. Label is localized."""
    at = (audience_type or "").strip().lower()
    css = {"beginner": "bg-green-50 text-green-700", "intermediate": "bg-blue-50 text-blue-700", "professional": "bg-purple-50 text-purple-700"}.get(at, "bg-gray-50 text-gray-700")
    loc = _locale(page_lang)
    key = {"beginner": "audience_beginner", "intermediate": "audience_intermediate", "professional": "audience_advanced"}.get(at)
    label = loc.get(key, at) if key else at
    return (label, css)


def _audience_type_from_stem(stem: str) -> str | None:
    """If stem ends with .audience_<type> and type is beginner/intermediate/professional, return it; else None."""
    if not stem or ".audience_" not in stem:
        return None
    suffix = stem.split(".audience_")[-1].strip().lower()
    return suffix if suffix in VALID_AUDIENCE_TYPES else None


# Category slug -> badge label (PL and EN: same label for Problem Fix & Find hub)
_CATEGORY_BADGE_LABEL: dict[str, str] = {
    "problem-fix-find-pl": "Problem Fix & Find",
    "marketplaces-products": "Problem Fix & Find",
}


def _article_meta_block(updated_iso: str, reading_min: int, category_slug: str | None, lead: str,
                        audience_type: str | None = None, page_lang: str = "en") -> str:
    """HTML for meta block under H1 (articles only). Styled badge row with category, audience, date, reading time."""
    loc = _locale(page_lang)
    parts: list[str] = []
    if category_slug:
        slug_esc = _escape(category_slug)
        display = _CATEGORY_BADGE_LABEL.get(category_slug) or category_slug.replace("-", " ").title()
        display_esc = _escape(display)
        parts.append(
            f'<span class="bg-indigo-50 text-indigo-700 px-2 py-1 rounded">'
            f'<a href="/hubs/{slug_esc}/" class="hover:underline">{display_esc}</a></span>'
        )
        parts.append("<span>&bull;</span>")
    at = (audience_type or "").strip().lower()
    if at in VALID_AUDIENCE_TYPES:
        label, css = _audience_label_and_css(at, page_lang)
        parts.append(f'<span class="{css} px-2 py-1 rounded">{_escape(label)}</span>')
        parts.append("<span>&bull;</span>")
    parts.append(f"<span>{_escape(loc['meta_updated'])} {_escape(updated_iso)}</span>")
    parts.append("<span>&bull;</span>")
    parts.append(f"<span>{_escape(str(reading_min))} {_escape(loc['meta_min_read'])}</span>")
    meta_html = (
        '<div class="flex flex-wrap items-center gap-3 text-sm font-medium text-gray-500 mb-6">\n  '
        + "\n  ".join(parts)
        + "\n</div>"
    )
    if lead:
        return meta_html + f'\n<p class="text-xl text-gray-600 leading-relaxed border-l-4 border-indigo-500 pl-4 italic mb-8">{lead}</p>'
    return meta_html


def _strip_invalid_internal_links(
    body: str,
    existing_slugs: set[str] | None,
    slug_to_fs: dict[str, str] | None = None,
) -> str:
    """Replace [text](/articles/slug/) with just text when slug is not in existing_slugs.
    If slug_to_fs is provided, rewrite valid links to use filesystem slug (for Windows path length)."""
    if existing_slugs is None:
        return body

    def repl(match):
        link_text, url = match.group(1), match.group(2)
        if not url.startswith("/articles/"):
            return match.group(0)
        slug = url[10:].split("#")[0].strip("/")
        if slug not in existing_slugs:
            return link_text
        fs_slug = (slug_to_fs or {}).get(slug, slug)
        suffix = url[10 + len(slug) :] or "/"
        new_url = f"/articles/{fs_slug}{suffix}"
        return f"[{link_text}]({new_url})"

    return INTERNAL_ARTICLE_LINK.sub(repl, body)


AFFILIATE_DISCLOSURE_TEXT = (
    "Some links on this page are affiliate links. If you make a purchase through these links, "
    "we may earn a commission at no extra cost to you."
)


# Section titles to strip from markdown body (EN; PL equivalents added when page_lang=pl)
_SECTIONS_TO_STRIP_EN = ["Tools mentioned", "CTA", "Pre-publish checklist", "Disclosure"]
_SECTIONS_TO_STRIP_PL = [
    "Lista platform i narzędzi wymienionych w artykule",
    "CTA",
    "Lista kontrolna przed publikacją",
    "Informacja",
]


def _md_to_html(
    body: str,
    existing_slugs: set[str] | None = None,
    slug_to_fs: dict[str, str] | None = None,
    page_lang: str = "en",
) -> str:
    """Minimal markdown to HTML: headings, - and 1. lists, paragraphs, [text](url), ``` code."""
    body = _strip_invalid_internal_links(body, existing_slugs, slug_to_fs)
    loc = _locale(page_lang)
    disclosure_text = loc.get("affiliate_disclosure_placeholder", AFFILIATE_DISCLOSURE_TEXT)
    body = body.replace("{{AFFILIATE_DISCLOSURE}}", disclosure_text)
    # Usuń mustache placeholdery {{...}}
    body = re.sub(r"\{\{[^}]+\}\}", "", body)
    # Usuń sekcję Verification policy (editors only) lub polską wersję
    body = re.sub(
        r"^## Verification policy \(editors only\).*?(?=^##|\Z)",
        "",
        body,
        flags=re.DOTALL | re.MULTILINE,
    )
    body = re.sub(
        r"^## Polityka weryfikacji \(tylko redaktorzy\).*?(?=^##|\Z)",
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
    # Usuń znane sekcje (Tools mentioned, CTA, Pre-publish checklist, Disclosure) – EN i PL
    sections_to_strip = list(_SECTIONS_TO_STRIP_EN)
    if (page_lang or "en").strip().lower() == "pl":
        sections_to_strip = list(_SECTIONS_TO_STRIP_EN) + _SECTIONS_TO_STRIP_PL
    for section in sections_to_strip:
        pattern = r"^#{1,3}\s*" + re.escape(section) + r"\s*\n.*?(?=^#{1,3}|\Z)"
        body = re.sub(pattern, "", body, flags=re.DOTALL | re.MULTILINE)
    # Usuń puste sekcje (nagłówek + zawartość, jeśli po usunięciu placeholderów nie ma treści)
    section_pattern = r"(^#{2,3}\s+[^\n]+\n)(.*?)(?=^#{1,3}|\Z)"

    def remove_empty_section(match):
        header = match.group(1)
        content = match.group(2)
        if re.search(r"\S", content):  # any non-whitespace (incl. Polish etc.)
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


def _docx_to_html(path: Path) -> str:
    """Convert .docx paragraphs to HTML (h1/h2/h3/p). Requires python-docx."""
    if not _DOCX_AVAILABLE:
        return ""
    doc = DocxDocument(path)
    out: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        text = _escape(text)
        style = (para.style and para.style.name) or ""
        if style in ("Heading 1", "Title"):
            out.append(f"<h1>{text}</h1>")
        elif style == "Heading 2":
            out.append(f"<h2>{text}</h2>")
        elif style == "Heading 3":
            out.append(f"<h3>{text}</h3>")
        else:
            out.append(f"<p>{text}</p>")
    return "\n".join(out)


def _footer_html() -> str:
    return (
        '<footer class="text-center">\n'
        '    <p><a href="/robots.txt">robots.txt</a> · <a href="/sitemap.xml">sitemap.xml</a> · '
        '<a href="https://generator.flowtaro.com" target="_blank" rel="noopener noreferrer">Prompt Generator</a> · '
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
    <style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.6;color:#1e293b;background:#fff;margin:0;padding:0}.flowtaro-container{max-width:960px!important;margin-left:auto!important;margin-right:auto!important;padding:2rem 1rem!important}.article-body{max-width:70ch;margin-left:auto;margin-right:auto;line-height:1.7;color:#1e293b;padding:0 1rem}</style>
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


def _strip_disclosure_from_html(body: str) -> str:
    """Remove any Disclosure/Informacja heading and its content from article body. The script adds the disclosure in a yellow box at the end."""
    # EN: Disclosure; PL: Informacja
    body = re.sub(
        r"(?si)\s*<h[23](?:\s[^>]*)?>\s*Disclosure\s*</h[23]>.*?(?=<h[1-6](?:\s|>)|\Z)",
        "",
        body,
    )
    body = re.sub(
        r"(?si)\s*<h[23](?:\s[^>]*)?>\s*Informacja\s*</h[23]>.*?(?=<h[1-6](?:\s|>)|\Z)",
        "",
        body,
    )
    return body


# Canonical Tailwind classes for article body (EN and PL must match).
_ARTICLE_H2_CLASS = "text-3xl font-bold mt-8 mb-4"
_ARTICLE_H3_CLASS = "text-xl font-semibold mt-6 mb-3"
_ARTICLE_P_CLASS = "text-lg text-gray-700 mb-4"
_ARTICLE_UL_CLASS = "list-disc list-inside space-y-2 text-gray-700"
_ARTICLE_OL_CLASS = "list-decimal list-inside space-y-2 text-gray-700"
_ARTICLE_TABLE_CLASS = "min-w-full border border-gray-200"


def _normalize_article_body_styles(body: str) -> str:
    """Force canonical article body classes so EN and PL (and any AI output) render identically. Replaces opening tags for h2, h3, p, ul, ol, table."""
    body = re.sub(r"<h2(?:\s[^>]*)?>", f"<h2 class=\"{_ARTICLE_H2_CLASS}\">", body, flags=re.IGNORECASE)
    body = re.sub(r"<h3(?:\s[^>]*)?>", f"<h3 class=\"{_ARTICLE_H3_CLASS}\">", body, flags=re.IGNORECASE)
    body = re.sub(r"<p(?:\s[^>]*)?>", f"<p class=\"{_ARTICLE_P_CLASS}\">", body, flags=re.IGNORECASE)
    body = re.sub(r"<ul(?:\s[^>]*)?>", f"<ul class=\"{_ARTICLE_UL_CLASS}\">", body, flags=re.IGNORECASE)
    body = re.sub(r"<ol(?:\s[^>]*)?>", f"<ol class=\"{_ARTICLE_OL_CLASS}\">", body, flags=re.IGNORECASE)
    body = re.sub(r"<table(?:\s[^>]*)?>", f"<table class=\"{_ARTICLE_TABLE_CLASS}\">", body, flags=re.IGNORECASE)
    return body


def _render_article(
    path: Path,
    out_dir: Path,
    existing_slugs: set[str] | None = None,
    slug_to_fs: dict[str, str] | None = None,
    nav_html: str = "",
    page_lang: str = "en",
    site_articles: list[tuple[dict, Path]] | None = None,
    logo_href: str = "/",
    articles_dir: Path | None = None,
    config_path: Path | None = None,
) -> None:
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
        body_html = _md_to_html(body, existing_slugs, slug_to_fs, page_lang=page_lang)
        body_html = enhance_article(body_html)
        tool_list = _load_affiliate_tools(AFFILIATE_TOOLS_PATH)
        body_html = replace_tool_names_with_links(body_html, tool_list)
        words = _word_count_md(body)
        reading_min = _reading_time_min(words)

    # Last-line defense: fix Try it yourself <pre> closing and orphan list tags if inconsistencies detected
    if _article_body_has_html_issues(body_html):
        body_html = _sanitize_article_html_body(body_html)
    # Remove any Disclosure section from body; the script adds it in a yellow box at the end.
    body_html = _strip_disclosure_from_html(body_html)
    # Remove leading <h1> from body so we show one title from frontmatter above meta (avoids duplicate for .md)
    body_html = _strip_leading_h1(body_html)
    # Insert Prompt Generator CTA block above "When NOT to use this" when that section exists
    body_html = _inject_prompt_generator_cta(body_html)
    # Normalize body tag classes so EN and PL (and any AI output) render identically
    body_html = _normalize_article_body_styles(body_html)

    slug_fs = (slug_to_fs or {}).get(slug, slug)
    html_path = out_dir / "articles" / slug_fs / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)

    category_slug = (meta.get("category") or meta.get("category_slug") or "").strip() or None
    lead = _extract_lead(meta, body_html)
    # Display title without content-type prefix (EN and PL same; H1 and <title> use this)
    title_display = _strip_content_type_prefix_from_title(title) or title
    # Title (H1) at top, then meta block (category, date, reading time, lead), then body
    title_h1 = _article_title_h1(title_display)
    audience_type = (meta.get("audience_type") or "").strip() or None
    if not audience_type:
        audience_type = _audience_type_from_stem(path.stem)
    loc = _locale(page_lang)
    meta_html = _article_meta_block(updated_iso, reading_min, category_slug, lead, audience_type, page_lang=page_lang)
    full_body_html = title_h1 + meta_html + body_html

    # Generate "Read Next" section
    read_next_html = ""
    _articles_dir = articles_dir or (PROJECT_ROOT / "content" / "articles")
    _config_path = config_path or (PROJECT_ROOT / "content" / "config.yaml")
    try:
        all_articles = get_production_articles(_articles_dir, _config_path)
        other_articles = [a for a in all_articles if (a[0].get("slug") or a[1].stem) != slug]
        selected = random.sample(other_articles, min(3, len(other_articles)))
        if selected:
            read_next_html = '<section class="bg-gray-50 p-6 rounded-lg mt-8">'
            read_next_html += f'<h3 class="font-bold text-gray-900 mb-3">{_escape(loc["read_next_heading"])}</h3>'
            read_next_html += '<ul class="space-y-2">'
            for art_meta, art_path in selected:
                art_title = _escape(art_meta.get("title") or "Untitled")
                art_slug = art_meta.get("slug") or art_path.stem
                article_slug = _escape((slug_to_fs or {}).get(art_slug, art_slug))
                read_next_html += f'<li><a href="/articles/{article_slug}/" class="text-indigo-600 hover:text-indigo-800 hover:underline transition-colors">{art_title}</a></li>'
            read_next_html += "</ul></section>"
    except Exception as e:
        print(f"Warning: Could not generate Read Next section: {e}")

    full_body_html += read_next_html

    # Affiliate disclosure (yellow box, below Read Next, above footer)
    disclosure_html = f"""
<div class="mt-8 p-4 bg-yellow-50 border-l-4 border-yellow-400 text-yellow-800 text-sm rounded-r">
    <strong>{_escape(loc["disclosure_heading"])}</strong> {_escape(loc["disclosure_body"])}
</div>"""
    full_body_html += disclosure_html

    article_body_html = f"<article class=\"article-body\">{full_body_html}</article>"
    article_content = article_body_html

    if ARTICLE_TEMPLATE_PATH.exists():
        content = ARTICLE_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("{{TITLE}}", _escape(title_display), 1)
        content = content.replace("{{STYLESHEET_HREF}}", "../../assets/styles.css", 1)
        content = content.replace("<!-- ARTICLE_CONTENT -->", article_content, 1)
        content = content.replace("<!-- NAV -->", nav_html, 1)
        content = content.replace("{{LOGO_HREF}}", logo_href, 1)
        content = content.replace("{{PRIVACY_LABEL}}", _escape(loc.get("footer_privacy", "Privacy Policy")), 1)
        content = content.replace("{{PROMPT_GENERATOR_LABEL}}", _escape(loc.get("footer_prompt_generator", "Prompt Generator")), 1)
    else:
        content = _wrap_page(title, body_html, updated_iso)
    if page_lang != "en":
        content = re.sub(r'<html\s+lang="en"\s*>', f'<html lang="{page_lang}">', content, count=1)
    html_path.write_text(content, encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")
    # Mark source .md as filled so fill_articles skips it next time
    _set_source_status_filled(path)


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
    slug_to_fs: dict[str, str] | None = None,
) -> str:
    """Build HTML for hub DYNAMIC_CONTENT: link home, title, intro, then per-section h2 + card grid."""
    slug_to_fs = slug_to_fs or {}
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
                slug_esc = _escape(slug_to_fs.get(slug, slug))
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
    slug_to_fs: dict[str, str] | None = None,
    output_slug: str | None = None,
    nav_html: str = "",
    page_lang: str = "en",
    logo_href: str = "/",
) -> None:
    meta, body = _parse_md_file(path)
    slug = (output_slug or meta.get("slug") or path.stem).strip()
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
        # Rewrite long article slugs to filesystem slugs in prebuilt HTML
        if slug_to_fs:
            for logical, fs in slug_to_fs.items():
                if logical != fs:
                    dynamic_content = dynamic_content.replace(
                        f'href="/articles/{logical}/"',
                        f'href="/articles/{fs}/"',
                    ).replace(
                        f'href="/articles/{logical}"',
                        f'href="/articles/{fs}/"',
                    )
    else:
        intro_md, sections = _parse_hub_body(body)
        intro_html = _md_to_html(intro_md, existing_slugs, slug_to_fs) if intro_md else ""
        slug_to_meta = {}
        for art_meta, art_path in articles:
            s = art_meta.get("slug") or art_path.stem
            slug_to_meta[s] = {**art_meta, "last_updated": _updated_date_iso(art_meta, art_path)}
        dynamic_content = _build_hub_content(title, intro_html, sections, slug_to_meta, slug_to_fs)
    html_path = out_dir / "hubs" / slug / "index.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    if HUB_TEMPLATE_PATH.exists():
        content = HUB_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("HUB_TITLE_PLACEHOLDER", _escape(title), 1)
        content = content.replace("{{STYLESHEET_HREF}}", "../../assets/styles.css", 1)
        content = content.replace("<!-- DYNAMIC_CONTENT -->", dynamic_content, 1)
        content = content.replace("<!-- NAV -->", nav_html, 1)
        content = content.replace("{{LOGO_HREF}}", logo_href, 1)
    else:
        logo_esc = _escape(logo_href)
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            f"  <title>{_escape(title)}</title>\n  <link rel=\"stylesheet\" href=\"../../assets/styles.css\">\n"
            "  <style>body{font-family:-apple-system,sans-serif;line-height:1.6;color:#1e293b;background:#fff;margin:0;padding:0}.flowtaro-container{max-width:960px!important;margin-left:auto!important;margin-right:auto!important;padding:2rem 1rem!important}</style>\n"
            "<script src=\"https://cdn.tailwindcss.com\"></script>\n</head>\n<body>\n"
            f"  <section class=\"bg-white pt-6 pb-6\"><div class=\"max-w-4xl mx-auto px-4\"><div class=\"text-center\"><a href=\"{logo_esc}\"><img src=\"/images/logo.webp\" alt=\"Flowtaro\" class=\"w-56 h-auto mx-auto block\"></a></div><div class=\"mt-6\">" + nav_html + "</div></div></section>\n"
            "  <div class=\"flowtaro-container\">\n"
            + dynamic_content
            + "\n  </div>\n"
            "  <footer class=\"site-footer text-center\"><div class=\"site-footer-inner\">"
            "<p>&copy; 2026 Flowtaro. <a href=\"https://generator.flowtaro.com\">Prompt Generator</a> &middot; <a href=\"/privacy.html\">Privacy Policy</a></p></div></footer>\n"
            "</body>\n</html>\n"
        )
    if page_lang != "en":
        content = re.sub(r'<html\s+lang="en"\s*>', f'<html lang="{page_lang}">', content, count=1)
    html_path.write_text(content, encoding="utf-8")
    print(f"  {html_path.relative_to(out_dir)}")


def _update_index(
    out_dir: Path,
    hubs: list[dict],
    articles: list[tuple[dict, Path]],
    nav_html: str,
    slug_to_fs: dict[str, str] | None = None,
    page_lang: str = "en",
    logo_href: str = "/",
) -> None:
    slug_to_fs = slug_to_fs or {}
    index_path = out_dir / "index.html"
    newest = sorted(articles, key=lambda x: _sort_key_newest(x[0], x[1]), reverse=True)[:12]
    hub_links: list[str] = []
    for h in hubs:
        slug = (h.get("slug") or h.get("category") or "").strip()
        slug_esc = _escape(slug)
        label = (h.get("title") or slug).strip()
        label_esc = _escape(label)
        hub_links.append(f'<a href="/hubs/{slug_esc}/" class="text-[rgb(23,38,107)] hover:underline">{label_esc}</a>')
    hub_link = '<h2 class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center">' + " &middot; ".join(hub_links) + '</h2>\n'
    articles_html = ""
    if newest:
        articles_html = '<h2 class="text-2xl font-bold mb-6 text-[rgb(23,38,107)] text-center">Newest articles</h2>\n'
        articles_html += '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">\n'
        for meta, path in newest:
            slug = meta.get("slug") or path.stem
            title_esc = _escape((meta.get("title") or slug).strip())
            date_esc = _escape(meta.get("last_updated") or _updated_date_iso(meta, path))
            slug_esc = _escape(slug_to_fs.get(slug, slug))
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
        content = content.replace("<!-- NAV -->", nav_html, 1)
        content = content.replace("{{LOGO_HREF}}", logo_href, 1)
    else:
        # Fallback: build full page with static footer (no template file)
        logo_esc = _escape(logo_href)
        footer = '  <footer class="text-center">\n    <p><a href="/robots.txt">robots.txt</a> · <a href="/sitemap.xml">sitemap.xml</a> · <a href="https://generator.flowtaro.com">Prompt Generator</a> · <a href="/privacy.html">Privacy Policy</a></p>\n  </footer>\n'
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Flowtaro</title>\n  <link rel=\"stylesheet\" href=\"assets/styles.css\">\n  <style>body{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif;line-height:1.6;color:#1e293b;background:#fff;margin:0;padding:0}.flowtaro-container{max-width:960px!important;margin-left:auto!important;margin-right:auto!important;padding:2rem 1rem!important}</style>\n</head>\n<body>\n"
            f"  <section class=\"bg-white pt-6 pb-6\"><div class=\"max-w-4xl mx-auto px-4\"><div class=\"text-center\"><a href=\"{logo_esc}\"><img src=\"/images/logo.webp\" alt=\"Flowtaro\" class=\"w-56 h-auto mx-auto block\"></a></div><div class=\"mt-6\">" + nav_html + "</div></div></section>\n"
            "  <div class=\"flowtaro-container\">\n"
            + dynamic_content
            + "\n"
            + footer
            + "  </div>\n</body>\n</html>\n"
        )
    if page_lang != "en":
        content = re.sub(r'<html\s+lang="en"\s*>', f'<html lang="{page_lang}">', content, count=1)
    index_path.write_text(content, encoding="utf-8")
    print(f"  {index_path.relative_to(out_dir)} (updated)")


def _write_privacy_page(out_dir: Path, nav_html: str = "", page_lang: str = "en", logo_href: str = "/") -> None:
    """Generate public/privacy.html from privacy.docx or Privacy Policy.md (or placeholder if both missing)."""
    privacy_body: str
    if PRIVACY_DOCX_PATH.exists() and _DOCX_AVAILABLE:
        privacy_html = _docx_to_html(PRIVACY_DOCX_PATH)
        privacy_html = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", privacy_html)
        privacy_body = f'<div class="article-body">\n{privacy_html}\n</div>'
    else:
        if PRIVACY_DOCX_PATH.exists() and not _DOCX_AVAILABLE:
            print("  (privacy.docx found but python-docx not installed; run: pip install python-docx)")
        if PRIVACY_MD_PATH.exists():
            body = PRIVACY_MD_PATH.read_text(encoding="utf-8")
            privacy_html = _md_to_html(body, None)
            privacy_html = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", privacy_html)
            privacy_body = f'<div class="article-body">\n{privacy_html}\n</div>'
        else:
            privacy_body = '<div class="article-body"><h1>Privacy Policy</h1><p>This page will be updated with our privacy policy. Please check back soon.</p></div>'
    if ARTICLE_TEMPLATE_PATH.exists():
        content = ARTICLE_TEMPLATE_PATH.read_text(encoding="utf-8")
        content = content.replace("{{TITLE}}", "Privacy Policy", 1)
        content = content.replace("{{STYLESHEET_HREF}}", "assets/styles.css", 1)
        content = content.replace("<!-- ARTICLE_CONTENT -->", privacy_body, 1)
        content = content.replace("<!-- NAV -->", nav_html, 1)
        content = content.replace("{{LOGO_HREF}}", logo_href, 1)
    else:
        logo_esc = _escape(logo_href)
        content = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>Privacy Policy - Flowtaro</title>\n  <link rel=\"stylesheet\" href=\"assets/styles.css\">\n  <style>body{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif;line-height:1.6;color:#1e293b;background:#fff;margin:0;padding:0}.flowtaro-container{max-width:960px!important;margin-left:auto!important;margin-right:auto!important;padding:2rem 1rem!important}.article-body{max-width:70ch;margin-left:auto;margin-right:auto;line-height:1.7;color:#1e293b;padding:0 1rem}</style>\n</head>\n<body>\n"
            f"  <section class=\"bg-white pt-6 pb-6\"><div class=\"max-w-4xl mx-auto px-4\"><div class=\"text-center\"><a href=\"{logo_esc}\"><img src=\"/images/logo.webp\" alt=\"Flowtaro\" class=\"w-56 h-auto mx-auto block\"></a></div><div class=\"mt-6\">" + nav_html + "</div></div></section>\n"
            "  <div class=\"flowtaro-container\">\n" + privacy_body + "\n  </div>\n"
            "  <footer class=\"site-footer text-center\"><p>&copy; 2026 Flowtaro. <a href=\"https://generator.flowtaro.com\">Prompt Generator</a> &middot; <a href=\"/privacy.html\">Privacy Policy</a></p></footer>\n"
            "</body>\n</html>\n"
        )
    if page_lang != "en":
        content = re.sub(r'<html\s+lang="en"\s*>', f'<html lang="{page_lang}">', content, count=1)
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


def _ensure_assets(out_dir: Path) -> None:
    """Copy assets (e.g. styles.css) from public/assets to out_dir/assets so PL and other builds have CSS.
    When out_dir is public_pl, public/assets is the source; when out_dir is public, skip (assets already there)."""
    if out_dir == PUBLIC_DIR:
        return
    src_assets = PUBLIC_DIR / "assets"
    dst_assets = out_dir / "assets"
    if not src_assets.is_dir():
        print("  Warning: public/assets/ not found; styles.css will 404. Build main site first or add public/assets/.")
        return
    try:
        dst_assets.mkdir(parents=True, exist_ok=True)
        for name in os.listdir(src_assets):
            src_path = src_assets / name
            dst_path = dst_assets / name
            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
            elif src_path.is_dir():
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        print(f"  Copied assets to {dst_assets.relative_to(PROJECT_ROOT)}")
    except OSError as e:
        print(f"  Warning: could not copy assets: {e}")


def _articles_for_hub(
    all_articles: list[tuple[dict, Path]],
    hub_category: str,
    first_hub_category: str | None,
) -> list[tuple[dict, Path]]:
    """Return articles whose meta.category matches hub_category; articles without category go to first hub."""
    out: list[tuple[dict, Path]] = []
    for meta, path in all_articles:
        art_cat = (meta.get("category") or "").strip().lower()
        if art_cat:
            if art_cat == hub_category.lower():
                out.append((meta, path))
        else:
            if first_hub_category and hub_category.lower() == first_hub_category.lower():
                out.append((meta, path))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Render production articles and hubs to static HTML.")
    parser.add_argument("--content-root", default=os.environ.get("CONTENT_ROOT", "content"), help="Content root (content or content/pl).")
    parser.add_argument("--site", default=None, choices=("main", "pl"), help="Site: main (default) or pl (subdomain). Overridden by env SITE.")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory. Default: public_pl for --site pl, else public. Env: OUTPUT_DIR or OUT_DIR.",
    )
    parser.add_argument("--base-url", default=None, help="Base URL for absolute links (e.g. https://flowtaro.com). Overridden by env BASE_URL.")
    args = parser.parse_args()

    content_dir = get_content_root_path(PROJECT_ROOT, args.content_root)
    config_path = content_dir / "config.yaml"
    articles_dir = content_dir / "articles"
    hubs_dir = content_dir / "hubs"

    site = (args.site or os.environ.get("SITE") or "main").strip().lower()
    if site not in ("main", "pl"):
        site = "main"
    default_out = "public_pl" if site == "pl" else "public"
    # OUTPUT_DIR and OUT_DIR allow CI (e.g. Cloudflare) to force output dir; default follows --site pl → public_pl
    out_dir_raw = (
        args.out_dir
        or os.environ.get("OUTPUT_DIR")
        or os.environ.get("OUT_DIR")
        or default_out
    )
    public = Path(out_dir_raw)
    if not public.is_absolute():
        public = PROJECT_ROOT / public
    try:
        out_label = str(public.relative_to(PROJECT_ROOT))
    except ValueError:
        out_label = str(public)
    print(f"Output directory: {out_label}")
    base_url = (args.base_url or os.environ.get("BASE_URL") or ("https://pl.flowtaro.com" if site == "pl" else "https://flowtaro.com")).strip().rstrip("/")

    config = load_config(config_path)
    hubs = get_hubs_list_for_site(config, site)
    category_slugs = get_category_slugs_for_site(config, site)
    nav_html = _build_nav_html(hubs, site=site, base_url_pl="https://pl.flowtaro.com", base_url_main="https://flowtaro.com")
    logo_href = "https://flowtaro.com" if site == "pl" else "/"
    first_hub_category = hubs[0]["category"] if hubs else None
    public.mkdir(parents=True, exist_ok=True)

    print(f"Rendering production articles (site={site})...")
    all_articles = get_production_articles(articles_dir, config_path)
    articles = [(meta, path) for meta, path in all_articles if (meta.get("category") or meta.get("category_slug") or "").strip() in category_slugs]
    existing_slugs = {meta.get("slug") or path.stem for meta, path in articles}
    slug_to_fs = {meta.get("slug") or path.stem: _slug_for_path(meta.get("slug") or path.stem, public) for meta, path in articles}
    page_lang = "pl" if site == "pl" else "en"
    for meta, path in articles:
        _render_article(path, public, existing_slugs, slug_to_fs, nav_html, page_lang=page_lang, logo_href=logo_href, articles_dir=articles_dir, config_path=config_path)

    print("Rendering hubs...")
    for hub in hubs:
        slug = hub["slug"]
        category = hub["category"]
        hub_path = hubs_dir / f"{slug}.md"
        if hub_path.exists():
            hub_articles = _articles_for_hub(articles, category, first_hub_category)
            _render_hub(hub_path, public, hub_articles, existing_slugs, slug_to_fs, output_slug=slug, nav_html=nav_html, page_lang=page_lang, logo_href=logo_href)
        else:
            print(f"  (no {hub_path.name})")

    print("Updating index.html...")
    _update_index(public, hubs, articles, nav_html, slug_to_fs, page_lang=page_lang, logo_href=logo_href)

    print("Writing privacy page...")
    _write_privacy_page(public, nav_html, page_lang=page_lang, logo_href=logo_href)

    _ensure_images(public)
    _ensure_assets(public)

    print("Done.")

    try:
        (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)
        (PROJECT_ROOT / "logs" / "last_run_render_site.txt").write_text(datetime.now().isoformat(), encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    main()
