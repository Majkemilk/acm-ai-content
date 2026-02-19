#!/usr/bin/env python3
"""
Fill article skeletons: replace bracket placeholders [...] with AI-generated prose.
Uses OpenAI Responses API (stdlib urllib only). Leaves {{...}} and structure intact.
Default: dry-run. Use --write to modify files (with .bak backup).
"""

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"
LOGS_DIR = PROJECT_ROOT / "logs"
ERROR_LOG = LOGS_DIR / "errors.log"
API_COSTS_PATH = LOGS_DIR / "api_costs.json"

# Blended rate $0.30 per 1M tokens (placeholder; no input/output split)
COST_PER_MILLION_TOKENS = 0.30


def _estimate_tokens(text: str) -> int:
    """Rough heuristic: 1 token ~ 4 characters for English."""
    return len(text) // 4


def _append_error_log(slug: str, level: str, message: str) -> None:
    """Append one line to logs/errors.log. Creates logs/ if needed."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] {slug}: {message}\n")
    except OSError:
        pass


def _record_fill_cost(slug: str, content: str) -> None:
    """Append estimated cost for this fill to logs/api_costs.json (by date)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        tokens = _estimate_tokens(content)
        cost = (tokens / 1_000_000) * COST_PER_MILLION_TOKENS
        data = {}
        if API_COSTS_PATH.exists():
            try:
                data = json.loads(API_COSTS_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        by_date = data.get("by_date") or {}
        today = datetime.now().strftime("%Y-%m-%d")
        by_date[today] = by_date.get(today, 0) + cost
        data["by_date"] = by_date
        API_COSTS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass

# Bracket placeholder: [...] that is NOT a markdown link [...](url)
BRACKET_PLACEHOLDER = re.compile(r"\[[^\]]+\](?!\s*\()")

# Mustache: extract all {{...}} tokens for QA
MUSTACHE_REGEX = re.compile(r"\{\{[^}]+\}\}")

# Forbidden claim patterns (case-insensitive)
# Patterns that trigger QA failure. Prompt instructions must forbid these so the model avoids them (see LENGTH AND CONTENT RULES in HTML prompt and OUTPUT CONTRACT D in markdown prompt).
FORBIDDEN_PATTERNS = [
    (re.compile(r"\b#\s*1\b", re.I), "#1"),
    (re.compile(r"\bnumber\s*one\b", re.I), "number one"),
    (re.compile(r"\bthe best\b", re.I), "the best"),
    (re.compile(r"\bguarantee(d)?\b", re.I), "guarantee(d)"),
    (re.compile(r"\$\d"), "$ pricing digit"),
    (re.compile(r"\bUSD\b", re.I), "USD"),
    (re.compile(r"\bper month\b", re.I), "per month"),
    (re.compile(r"\bper year\b", re.I), "per year"),
    (re.compile(r"\bpricing\b", re.I), "pricing"),
    (re.compile(r"\b(unlimited|limit(ed)? to|up to \d+)\b", re.I), "unlimited/limit/up to N"),
]


def _parse_frontmatter(content: str) -> tuple[dict, list[tuple[str, str]], str, int]:
    """Return (meta dict, ordered key-value pairs, body, body_start). No YAML lib."""
    if not content.startswith("---"):
        return {}, [], content, 0
    end = content.find("\n---", 3)
    if end == -1:
        return {}, [], content, 0
    block = content[3:end].strip()
    meta: dict[str, str] = {}
    order: list[tuple[str, str]] = []
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
        order.append((key, raw))
    body_start = end + 4
    body = content[body_start:].lstrip("\n")
    return meta, order, body, body_start


def _serialize_frontmatter(meta: dict, order: list[tuple[str, str]], status_value: str = "filled") -> str:
    """Build frontmatter block; preserve order, set status to status_value."""
    status_set = False
    lines = ["---"]
    for k, v in order:
        if k == "status":
            v = status_value
            status_set = True
        v = str(v)
        if "\n" in v or '"' in v:
            v = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k}: "{v}"')
    if not status_set:
        lines.append(f'status: "{status_value}"')
    lines.append("---")
    return "\n".join(lines) + "\n"


def has_bracket_placeholders(body: str) -> bool:
    """True if body contains [...] placeholders (not markdown links)."""
    return bool(BRACKET_PLACEHOLDER.search(body))


def is_checkbox_token(token: str) -> bool:
    """True if token is a markdown checkbox [ ], [x], [X], or [-] (not a placeholder)."""
    return token in ("[ ]", "[x]", "[X]", "[-]")


def sanitize_filled_body(text: str) -> tuple[str, list[str]]:
    """Replace forbidden phrases in body only (skip heading lines). Returns (sanitized_text, notes)."""
    notes: list[str] = []
    pricing_count = 0
    best_count = 0
    guarantee_count = 0
    out_lines: list[str] = []
    dollar_count = 0
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            out_lines.append(line)
            continue
        line, n = re.subn(r"\bpricing\b", "cost", line, flags=re.IGNORECASE)
        pricing_count += n
        line, n = re.subn(r"\bthe\s+best\b", "a strong option", line, flags=re.IGNORECASE)
        best_count += n
        line, n = re.subn(r"\bguarantee\b", "assure", line, flags=re.IGNORECASE)
        guarantee_count += n
        line, n = re.subn(r"\bguaranteed\b", "assured", line, flags=re.IGNORECASE)
        guarantee_count += n
        line, n = re.subn(r"\$\d+(?:\.\d+)?", "cost", line)
        dollar_count += n
        out_lines.append(line)
    if pricing_count:
        notes.append(f"replaced pricing->cost ({pricing_count}x)")
    if best_count:
        notes.append(f"replaced 'the best'->'a strong option' ({best_count}x)")
    if guarantee_count:
        notes.append(f"replaced guarantee(d)->assure(d) ({guarantee_count}x)")
    if dollar_count:
        notes.append(f"replaced $ amount->cost ({dollar_count}x)")
    return ("\n".join(out_lines), notes)


# Editor-note bracket lines to remove (exact substring match; line must be "[...]" only)
_EDITOR_NOTE_SUBSTRINGS = [
    ("Add only relevant internal links", "internal-links"),
    ("Short call-to-action placeholder", "cta"),
    ("Placeholder only. Replace with your actual disclosure text", "disclosure"),
]


def strip_editor_notes(text: str) -> tuple[str, list[str]]:
    """Remove known editor-note bracket lines from body. Returns (clean_text, notes)."""
    removed_labels: list[str] = []
    out_lines: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            matched = None
            for substr, label in _EDITOR_NOTE_SUBSTRINGS:
                if substr in s:
                    matched = label
                    break
            if matched is not None:
                removed_labels.append(matched)
                continue
        out_lines.append(line)
    notes: list[str] = []
    if removed_labels:
        notes.append(f"removed {len(removed_labels)} line(s) [{', '.join(removed_labels)}]")
    return ("\n".join(out_lines), notes)


# Known bracket placeholders the model sometimes leaves; replace with safe prose before QA.
# (placeholder_substring, replacement) — replacement is used for all occurrences.
_KNOWN_BRACKET_FALLBACKS: list[tuple[str, str]] = [
    ("[Link to blog]", "the blog post"),
    ("[Link to article]", "the article"),
    ("[Insert link]", "the link"),
    ("[Insert URL]", "the link"),
    ("[Your company]", "your company"),
    ("[Your Company]", "your company"),
    ("[Company name]", "your company"),
    ("[Product name]", "the product"),
    ("[Product Category]", "the product category"),
    ("[Customer name]", "the customer"),
    ("[Customer Name]", "the customer"),
    ("[Discount/Offer]", "the offer"),
    ("[Date]", "the date"),
    ("[Key Point 1]", "the main point"),
    ("[Key Point 2]", "another point"),
    ("[Your Brand Name]", "your brand"),
    ("[Recipient's Name]", "the recipient"),
    ("[Relevant Topic]", "the topic"),
    ("[Your Name]", "your name"),
    ("[Your Position]", "your role"),
]


def replace_known_bracket_placeholders(text: str) -> tuple[str, list[str]]:
    """Replace known leftover bracket placeholders with safe text so QA does not fail. Returns (text, notes)."""
    notes: list[str] = []
    out = text
    for placeholder, replacement in _KNOWN_BRACKET_FALLBACKS:
        count = out.count(placeholder)
        if count:
            out = out.replace(placeholder, replacement)
            notes.append(f"replaced {placeholder!r} -> {replacement!r} ({count}x)")
    return (out, notes)


def _h1_lines(body: str) -> list[str]:
    """Extract H1 lines (exactly # then space), stripped."""
    out: list[str] = []
    for line in body.split("\n"):
        s = line.rstrip()
        if s.startswith("# ") and not s.startswith("##"):
            out.append(s)
    return out


def _h2_lines(body: str) -> list[str]:
    """Extract H2 lines (exactly ## then space), stripped."""
    out: list[str] = []
    for line in body.split("\n"):
        s = line.rstrip()
        if s.startswith("## ") and not s.startswith("###"):
            out.append(s)
    return out


def run_preflight_qa(
    original_full_text: str,
    filled_full_text: str,
    original_body: str,
    filled_body: str,
    strict: bool = False,
    is_html: bool = False,
) -> tuple[bool, list[str]]:
    """Validate filled output. Returns (ok, list of failure reasons).
    When is_html=True, H1/H2 structure check is skipped; bracket/word/forbidden use stripped text."""
    reasons: list[str] = []

    # A. Mustache preservation (skip in HTML mode – HTML articles do not use {{...}})
    if not is_html:
        orig_tokens = set(MUSTACHE_REGEX.findall(original_full_text))
        filled_tokens = set(MUSTACHE_REGEX.findall(filled_full_text))
        missing = orig_tokens - filled_tokens
        added = filled_tokens - orig_tokens
        if missing:
            reasons.append(f"mustache removed: {sorted(missing)}")
        if added:
            reasons.append(f"mustache introduced: {sorted(added)}")

    # For HTML we run B/D/E on stripped text
    text_for_checks = _strip_html_tags(filled_body) if is_html else filled_body

    # B. Bracket placeholders removed (ignore markdown checkboxes [ ], [x], [X], [-]; ignore content in Template 1/2 sections)
    body_without_templates = text_for_checks
    if not is_html:
        # Usuń bloki Template (dowolny poziom nagłówka # do ###)
        body_without_templates = re.sub(
            r"^#{1,3}\s*Template\s*1:.*?(?=^#{1,3}|\Z)",
            "",
            body_without_templates,
            flags=re.DOTALL | re.MULTILINE,
        )
        body_without_templates = re.sub(
            r"^#{1,3}\s*Template\s*2:.*?(?=^#{1,3}|\Z)",
            "",
            body_without_templates,
            flags=re.DOTALL | re.MULTILINE,
        )
    all_bracket = BRACKET_PLACEHOLDER.findall(body_without_templates)
    remaining = [m for m in all_bracket if not is_checkbox_token(m)]
    if remaining:
        reasons.append(f"bracket placeholders still present: {remaining[:5]}{'...' if len(remaining) > 5 else ''}")

    # C. H1 and H2 structure unchanged (skip for HTML; H3/H4 may vary for markdown)
    if not is_html:
        orig_h1 = _h1_lines(original_body)
        filled_h1 = _h1_lines(filled_body)
        orig_h2 = _h2_lines(original_body)
        filled_h2 = _h2_lines(filled_body)
        if orig_h1 != filled_h1:
            reasons.append(f"H1 headings changed: expected {orig_h1!r}, got {filled_h1!r}")
        missing_h2 = set(orig_h2) - set(filled_h2)
        if missing_h2:
            reasons.append(f"H2 headings missing: {', '.join(missing_h2)}")

    # D. Word count (use stripped text for HTML)
    word_count = len(text_for_checks.split())
    # TEMPORARY: lowered for testing; revert to 1000/700 later
    threshold = 800 if strict else 500
    if word_count < threshold:
        reasons.append(f"word count {word_count} < {threshold}")

    # E. Forbidden patterns (use stripped text for HTML to avoid matching inside attributes)
    for pat, label in FORBIDDEN_PATTERNS:
        if pat.search(text_for_checks):
            reasons.append(f"forbidden pattern: {label}")

    return (len(reasons) == 0, reasons)


def should_process(meta: dict, body: str, force: bool, use_html: bool = False) -> bool:
    """True if file should be processed. When use_html=True, bracket placeholders are not required."""
    if force:
        return True if use_html else has_bracket_placeholders(body)
    status = (meta.get("status") or "").strip().lower()
    if status == "filled" or status == "blocked":
        return False
    if use_html:
        return True
    return has_bracket_placeholders(body)


# Output contract markers (quality gate)
CONTRACT_MARKERS = [
    "Decision rules:",
    "Tradeoffs:",
    "Failure modes:",
    "SOP checklist:",
    "Template 1:",
    "Template 2:",
]


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags for text-based checks (e.g. contract markers)."""
    return re.sub(r"<[^>]+>", " ", html)


def _load_affiliate_tools() -> list[tuple[str, str]]:
    """Load (name, url) from content/affiliate_tools.yaml. Stdlib only."""
    path = PROJECT_ROOT / "content" / "affiliate_tools.yaml"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    items: list[tuple[str, str]] = []
    in_tools = False
    current_name = ""
    current_url = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped == "tools:":
            in_tools = True
            continue
        if not in_tools:
            continue
        if stripped.startswith("- "):
            if current_name:
                items.append((current_name, current_url))
            current_name = ""
            current_url = ""
            part = stripped[2:].strip()
            kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", part)
            if kv:
                k, v = kv.group(1), kv.group(2).strip().strip('"\'')
                if k == "name":
                    current_name = v
                elif k == "affiliate_link":
                    current_url = v
            continue
        kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", stripped)
        if kv:
            k, v = kv.group(1), kv.group(2).strip().strip('"\'')
            if k == "name":
                current_name = v
            elif k == "affiliate_link":
                current_url = v
    if current_name:
        items.append((current_name, current_url))
    return items


def _frontmatter_comment_string(meta: dict, status_value: str = "filled") -> str:
    """Build frontmatter as HTML comment for .html articles."""
    lines = ["<!--"]
    for k, v in meta.items():
        v = str(v)
        if "\n" in v or '"' in v:
            v = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k}: "{v}"')
    if "status" not in meta:
        lines.append(f'status: "{status_value}"')
    else:
        # Ensure status is set
        idx = next((i for i, s in enumerate(lines) if s.startswith("status:")), None)
        if idx is not None:
            lines[idx] = f'status: "{status_value}"'
    lines.append("-->")
    return "\n".join(lines) + "\n"


def _build_html_prompt(meta: dict, tool_list: list[tuple[str, str]]) -> tuple[str, str]:
    """(instructions, user_message) for AI to generate article body as HTML with Tailwind."""
    title = (meta.get("title") or "").strip()
    keyword = (meta.get("primary_keyword") or "").strip()
    category = (meta.get("category") or meta.get("category_slug") or "").strip()
    content_type = (meta.get("content_type") or "").strip()
    tools_blob = ""
    if tool_list:
        tools_blob = (
            "Tool names and URLs to link (first occurrence only): "
            + ", ".join(f"{name}={url}" for name, url in tool_list if url)
            + ". Link each tool name at its first occurrence as <a href=\"URL\">Name</a> using the exact URL provided."
        )

    instructions = f"""You are a documentation writer. Generate the BODY of an article as HTML only. The output will be inserted inside an <article> tag; the page already has header, footer, and the article title (H1). Do NOT output <html>, <head>, <body>, or an H1 — start with the first section (e.g. Introduction or first H2). Do not generate any part of the page layout (header, footer, navigation); only the article content.
IMPORTANT: Do NOT include a "Disclosure" section. The site template adds a disclosure box automatically at the end of every article.

REQUIRED SECTIONS (include every one, in a logical order; use H2 for main sections, H3 for subsections):
- Introduction (brief context and what the reader will learn)
- What you need to know first (prerequisites or key concepts)
- Decision rules: (when to use this approach; use the special box style below)
- Tradeoffs: (pros/cons; use the special box style)
- Failure modes: (what can go wrong and how to avoid it; use the special box style)
- SOP checklist: (step-by-step checklist; use the special box style)
- Template 1: (a ready-to-use template with real example content; use the template card style below)
- Template 2: (a second template with different real example content; use the template card style)
- Step-by-step workflow (numbered steps for the main process)
- Optionally (within Step-by-step workflow): "Try it yourself: Build your own AI prompt" — include only if the topic lends itself to a practical exercise; see "OPTIONAL SECTION" below.
- When NOT to use this (when to avoid this approach)
- FAQ (at least 2–3 questions and answers)
- Internal links (1–2 sentences suggesting related reads; you may use placeholder URLs like # or /blog/ for now)
- List of AI tools mentioned in this article (place near the end, e.g. after FAQ or after Internal links; see "SECTION: List of AI tools" below)
- Optionally: Case study (a few paragraphs illustrating a real-world scenario: specific data, challenges, and outcomes; see example below)

OPTIONAL SECTION: "Try it yourself: Build your own AI prompt"
If the topic lends itself to a practical exercise, include a dedicated subsection (H3) titled "Try it yourself: Build your own AI prompt" inside the Step-by-step workflow section. When you include this subsection, you MUST follow these rules without exception:

1) Workflow explanation (required at the start): The first paragraph of this subsection MUST explicitly state the suggested workflow as: Human → Prompt #1 (to a general AI) → Prompt #2 (for the specific tool, e.g., Descript) → Use in the tool. Do not omit or shorten this; the reader must see this exact workflow at the beginning.

2) Structure of the example Prompt #1 (mandatory): The copy-paste-ready example of Prompt #1 MUST be structured with all of the following labeled parts. Each part must be clearly present and substantive (not one-line placeholders):
- Role — define the role of a specialist or team best suited to accomplish the goal (e.g., "You are a marketing analyst with experience in…").
- Goal — what the user wants to achieve (the outcome).
- Task — mandatory: a concrete request that must always begin with the phrase "Please create a prompt that will [Goal]" for the specific tool and use case (e.g. "Please create a prompt that will analyze competitor video tone for use in Descript.").
- Uncertainty Flagging — an explicit instruction that if the AI is unsure about any element, it must state so and ask for clarification before proceeding.
- Permission to ask clarifying questions — an explicit instruction that if context is insufficient, the AI may (and should) ask the user for more details.

Do not merge or abbreviate these into a single short paragraph. The meta-prompt must be detailed enough that the reader gets a complete, usable template. Use the actual tool name from the article (e.g., Descript, Pictory, Otter). Put the meta-prompt inside <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">...</pre>. Emphasize that this approach makes the user the architect of the workflow, not just a passive consumer.

SECTION: "List of AI tools mentioned in this article"
Include a section titled "List of AI tools mentioned in this article" near the end of the article (e.g. after FAQ or after Internal links; choose a consistent, logical position). This section gives readers a quick reference and supports affiliate links.
- Placement: Near the end, after FAQ or after Internal links. Do not place after the disclosure (the template adds disclosure automatically).
- Content: A bulleted list. For each tool that is both (a) in the tool list above and (b) relevant to the article (actually discussed or clearly pertinent), add one bullet containing: the tool name as a link using the exact URL from the tool list above, then a short one-sentence description.
- Description rules: The one-sentence description must be factual and state what the tool does and its key differentiator (e.g. "video editing and transcription", "AI-powered transcription with speaker identification", "AI content generation for blogs"). Be concise and specific; avoid vague phrases like "powerful tool" or "comprehensive solution". If you cannot provide a reliable, factual description for a tool, omit that tool from the list.
- Format: Use H2 for the section title. Use <ul class="list-disc list-inside space-y-2 text-gray-700"> for the list. Each item: <a href="URL">Tool Name</a> — description sentence. Include only tools from the tool list above; do not invent tools. The AI decides which tools to include based on article relevance. If the tool list is empty, omit this section.

IMPORTANT — LENGTH: The article MUST be at least 700 words. For comprehensive guides, aim for 900+ words. To achieve this:
- Expand "Template 1" and "Template 2" with rich, detailed examples (multiple lines or bullets each; real company names, metrics, and scenarios).
- Consider adding a "Case study" section after the templates: a concrete example of someone using the described AI tools, with specific data, challenges, and outcomes (a few paragraphs long).
Example case study tone: "A small e-commerce company, ShopSmart, used Descript to analyze competitor social media videos. They discovered that competitors were heavily using influencer marketing, which led them to pivot their strategy. Within three months, their engagement increased by 40%."

LENGTH AND CONTENT RULES:
- NEVER use square-bracket placeholders (e.g. [Name], [Date], [Customer Name], [Your Company], [Insert URL]). Every template field, example, and sentence must be filled with concrete, realistic content. Use real-looking example names, dates, product names — never leave or introduce any [bracket] token. QA will reject the article if any remain.
- FORBIDDEN PHRASES (QA will reject the article if present): Do not use "unlimited", "limit to", "limited to", or "up to [number]" (e.g. "up to 5"). Do not use $ or any currency amount (e.g. $99). Use neutral wording instead (e.g. "many", "as needed", "several", "a set of steps", "cost").

STYLE (Tailwind CSS utility classes):
- Main section headings: <h2 class="text-3xl font-bold mt-8 mb-4">. Subsection: <h3 class="text-xl font-semibold mt-6 mb-3">.
- Paragraphs: <p class="text-lg text-gray-700 mb-4">. Lists: <ul class="list-disc list-inside space-y-2 text-gray-700"> or <ol class="list-decimal list-inside space-y-2 text-gray-700">.
- Special sections (Decision rules, Tradeoffs, Failure modes, SOP checklist): wrap in <div class="bg-indigo-50 p-6 rounded-lg border border-indigo-100 my-6"> with an <h3 class="text-xl font-semibold"> inside. Example:
  <div class="bg-indigo-50 p-6 rounded-lg border border-indigo-100 my-6">
    <h3 class="text-xl font-semibold mb-3">Decision rules:</h3>
    <ul class="list-disc list-inside space-y-2 text-gray-700">...</ul>
  </div>
- Template 1 / Template 2 cards: wrap in <div class="bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow mb-4">. Put real example content inside <pre> or structured <p>/<ul>, never [Insert ...]. Example:
  <div class="bg-white border border-gray-200 rounded-lg p-5 shadow-sm mb-4">
    <h3 class="text-xl font-semibold mb-3">Template 1:</h3>
    <p class="text-lg text-gray-700 mb-2">Use this to...</p>
    <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">Competitor: Acme Corp
Strengths: Strong social presence, fast shipping
Weaknesses: Limited international
...</pre>
  </div>
- Blockquotes: <blockquote class="border-l-4 border-indigo-500 pl-4 italic text-gray-600 my-4">. Inline code: <code class="bg-gray-100 px-1 py-0.5 rounded text-sm">. Code blocks: <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto">.

{tools_blob}

Output ONLY the HTML fragment that goes inside the article (no wrapper tags, no markdown)."""

    user = f"Article title: {title}\n"
    if keyword:
        user += f"Primary keyword: {keyword}\n"
    if category:
        user += f"Category: {category}\n"
    if content_type:
        user += f"Content type: {content_type}\n"
    user += "\nGenerate the complete article body in HTML with Tailwind classes. Include all required sections (including 'List of AI tools mentioned in this article' near the end), at least 700 words (expand templates and add a case study if helpful), and no square-bracket placeholders."
    return instructions, user


def _extract_block(body: str, start_label: str, stop_labels: list[str]) -> str:
    """Return text after start_label until the first occurrence of any stop_label or H2."""
    idx = body.find(start_label)
    if idx == -1:
        return ""
    start = idx + len(start_label)
    end = len(body)
    for stop in stop_labels:
        pos = body.find(stop, start)
        if pos != -1 and pos < end:
            end = pos
    return body[start:end].strip()


def check_output_contract(body: str, content_type: str, strict: bool = False) -> list[str]:
    """
    Sprawdza, czy treść zawiera wymagane sekcje (markery).
    Dla HTML: najpierw usuwa tagi, potem sprawdza (case-insensitive).
    Zwraca listę stringów z opisami błędów (pusta = OK).
    """
    missing = []
    # Strip HTML tags so markers inside <h3> etc. are found
    if "<" in body and ">" in body:
        body = _strip_html_tags(body)
    body_lower = body.lower()

    # Markery wymagane dla wszystkich typów
    required_all = [
        "Decision rules:",
        "Tradeoffs:",
    ]

    # Failure modes wymagane dla instruktażowych typów treści
    if content_type in ["how-to", "guide", "comparison"]:
        required_all.append("Failure modes:")

    # Dodatkowe markery tylko dla 'how-to' i 'guide'
    if content_type in ["how-to", "guide"]:
        required_all.extend([
            "SOP checklist:",
            "Template 1:",
            "Template 2:",
        ])

    for marker in required_all:
        if marker.lower() not in body_lower:
            missing.append(f"missing marker: '{marker}'")

    return missing


def call_responses_api(
    instructions: str,
    user_message: str,
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> str:
    """POST to {base_url}/v1/responses. Return extracted text or raise."""
    url = base_url.rstrip("/") + "/v1/responses"
    payload = {
        "model": model,
        "instructions": instructions,
        "input": user_message,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"API error {e.code}: {body}") from e
    # Prefer output_text; else scan output items for message content
    if isinstance(out.get("output_text"), str) and out["output_text"].strip():
        return out["output_text"].strip()
    for item in out.get("output") or []:
        if item.get("type") == "message" and "content" in item:
            c = item["content"]
            if isinstance(c, str):
                return c.strip()
            if isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        if part.get("text"):
                            return part["text"].strip()
    raise RuntimeError("No output text in API response")


def build_prompt(meta: dict, body: str, style: str = "docs") -> tuple[str, str]:
    """(instructions, user_message) for the model. style: docs | concise | detailed."""
    title = (meta.get("title") or "").strip()
    keyword = (meta.get("primary_keyword") or "").strip()
    category = (meta.get("category") or meta.get("category_slug") or "").strip()
    content_type = (meta.get("content_type") or "").strip()
    tools_note = ""
    tool_keys = ["primary_tool", "secondary_tool", "tools_mentioned", "tools"]
    tool_names: list[str] = []
    for k in tool_keys:
        v = meta.get(k)
        if isinstance(v, str) and v.strip():
            tool_names.extend(t.strip() for t in v.replace(",", " ").split() if t.strip())
        elif isinstance(v, list):
            tool_names.extend(str(x).strip() for x in v if str(x).strip())
    if tool_names:
        tools_note = f" You may mention only these tools (do not invent others): {', '.join(dict.fromkeys(tool_names))}."

    style_phrase = {
        "concise": "Be concise: shorter sentences, fewer examples.",
        "detailed": "Include more detail and examples where helpful.",
    }.get(style, "Use a documentation-like tone: clear, actionable, B2B/SOHO, English.")

    instructions = f"""You are a documentation writer. Your task is to replace ONLY bracket placeholders [instruction or hint] in the given markdown article skeleton with real prose. Return the full markdown body (no frontmatter). Do not change any {{{{MUSTACHE}}}} placeholders (e.g. {{{{TOOLS_MENTIONED}}}}, {{{{CTA_BLOCK}}}}, {{{{AFFILIATE_DISCLOSURE}}}}, {{{{INTERNAL_LINKS}}}}, {{{{PRIMARY_TOOL}}}}). Leave them exactly as-is.
CRITICAL — No [bracket] tokens in output: Your response must not contain any text of the form [Anything] (e.g. [Name], [Date], [Customer Name], [Your Company], [Product]). Replace every such placeholder with a concrete example value. If you leave or introduce any [bracket] token, the QA check will reject the article.

Heading freeze: Do not add, remove, rename, or reformat any headings (#, ##, ###, ####). Do not introduce new headings of any level. Only replace bracket placeholders with plain text or lists under existing headings.

Do not use the word "pricing" anywhere in the output (including phrases like "check pricing"). If you need to refer to cost, use neutral wording like "cost" or "plan" without numbers or specific claims; avoid cost talk if possible.

Defensible Content Rules (MUST follow):

1) No generic filler — Every section must include at least ONE concrete constraint, tradeoff, or failure mode. Disallow vague lines like "choose the right tool", "streamline process", "align with needs". Prefer: specific conditions (volume, team size, content type, turnaround time, quality bar).

2) Decision logic — In Main content OR Step-by-step workflow, include a "Decision rules" subsection in plain text (no new H2; use H3 or inline). Include at least 6 bullet rules of the form "If … then …" or "If … avoid … because …". Include at least 2 "Do NOT use this when …" rules.

3) Use-case specificity — Pick exactly ONE primary persona from: Solo creator / Agency / Small business marketing lead / SaaS founder (based on title/keyword). Mention that persona explicitly in the Introduction (1 line). In the workflow, include at least 2 constraints that persona commonly has (time, budget, tools, approvals, compliance).

4) SOP / Template — In Step-by-step workflow: include a short SOP checklist (5–9 items as plain bullet list; do NOT use markdown [ ] checkboxes). Include 2 ready-to-copy templates/snippets (e.g. "Content brief template", "Repurposing prompt template", "QA checklist template", "Publishing checklist"). Keep them short and clearly labeled.

5) Comparisons without facts — Allowed: criteria-based (speed vs control, quality vs volume, learning curve). Not allowed: pricing numbers, limits, "best/#1" claims, release dates. Never claim features as facts unless already in provided body/context.

6) Tools discipline — Tools may only be mentioned if in the metadata list.{tools_note} If tool list is empty, write tool-agnostic content (no new tool names). If tools exist, include a mini selection guide: "Use <Primary tool> when …", "Use <Secondary tool> when …", "Avoid both when … (and propose non-tool alternative like manual approach)."

Do NOT write sentences like: "choose a tool that fits your needs", "streamline your workflow", "align with your goals". Replace with: "If you publish <X> pieces/week and need <Y> turnaround, prioritize <criterion>."

How to fill: Replace each bracket placeholder with content appropriate to the **nearest preceding heading**. Use the heading text as the section type cue. Do not change any heading text.

CRITICAL: Your response MUST contain the following exact section headings, each as a heading (e.g., "## Decision rules:" or "**Decision rules:**").
The required headings are:
- "Decision rules:"
- "Tradeoffs:"
- "Failure modes:"
- "SOP checklist:"
- "Template 1:"
- "Template 2:"

Do not omit any of these sections. Each section must contain at least 3-5 bullet points (or detailed content) relevant to the article topic.
Failure to include all these headings will result in rejection.

IMPORTANT: In the "Template 1" and "Template 2" sections, you MUST generate concrete, realistic examples relevant to the article topic. Never leave or introduce any [bracket] token in the entire output. Forbidden examples: [Name], [Date], [Month], [Customer Name], [Your Company], [Product], [Insert title], [Key Point 1], [user's email], [Personalized ...], or any [Anything]. Replace every such placeholder with a concrete value (real example names, dates, product names, email examples). The QA check will reject the article if any [bracket] text remains. The templates should be immediately usable by the reader as examples.

Section Rules (each section must include at least one of: constraint, tradeoff, failure mode, decision rule):

A) Introduction — 2–3 short paragraphs. First sentence: business problem and target user. Second: outcome/benefit. Must include persona line (see Defensible rule 3) + outcome. Include one "when this is NOT worth it" sentence (no new heading). No "best/#1" claims, pricing, limits, or dates.

B) What you need to know first — 4–6 bullet points. At least 2 bullets must be constraints/assumptions (e.g. source format quality, approval loop). No tool marketing language.

C) Main content (e.g. Section 1/2/3) — Must include a "Decision rules" bullet list (see Defensible rule 2). Must include a "Tradeoffs" bullet list (at least 3). 2–4 subsections (H3 optional), concrete and actionable. Mention tools only if in article context; do not invent tools.

D) Step-by-step workflow — Numbered list of 7–10 steps. Must include: SOP checklist (plain bullets, no markdown checkboxes). Inputs/Outputs and 3 Common pitfalls with mitigations. Two templates/snippets (see Defensible rule 4). Action-oriented steps.

E) When NOT to use this — 4–6 bullets with concrete "avoid when … because …" (no generic statements).

F) FAQ — 5 Q&A pairs. At least 2 answers must include troubleshooting steps (numbered list allowed). Each answer must mention a constraint or a reason; avoid generic statements.

No invention policy:
- Do not introduce new tool names beyond those provided in the article context.
- Do not introduce pricing, feature limits, release dates, or "best/#1" ranking claims.
- If comparing, use criteria-based comparisons only; no hard facts unless given.
- Do not add external links.
- {style_phrase}

OUTPUT CONTRACT (MUST FOLLOW EXACTLY):

A) You MUST include these exact marker labels somewhere under existing sections (H3/H4 allowed, no new H2):
- "Decision rules:"
- "Tradeoffs:"
- "Failure modes:"
- "SOP checklist:"
- "Template 1:"
- "Template 2:"

B) Formatting: Under "Decision rules:" at least 6 bullet lines starting with "If " or "When " or "Avoid ". Under "Tradeoffs:" at least 3 bullets containing a tradeoff (e.g. "vs", "at the cost of", "tradeoff"). Under "Failure modes:" at least 3 bullets (failure + mitigation). Under "SOP checklist:" 5–9 plain bullets (do NOT use markdown [ ] checkboxes). Under "Template 1:" and "Template 2:" short copy-ready blocks (5–10 lines each). No external links, no pricing, no "best/#1".

C) Persona: In Introduction include exactly one sentence stating the persona (one of: Solo creator, Agency, Small business marketing lead, SaaS founder). Include 2 constraints for that persona (time, approvals, volume, compliance).

D) Do not use the word "pricing". Do not use "the best" or "#1". Do not use "unlimited", "limit to", "limited to", or "up to [number]" (e.g. "up to 5"). Do not use $ or any currency amount (e.g. $99, $10/mo); the QA check will reject the article. Use neutral wording (e.g. "many", "as needed", "several", "cost") instead.

E) If you cannot comply with the OUTPUT CONTRACT, regenerate until you can. Do not omit the markers.

Output must feel like an internal playbook: decisions + steps + templates."""

    user = f"Article title: {title}\n"
    if keyword:
        user += f"Primary keyword: {keyword}\n"
    if category:
        user += f"Category: {category}\n"
    if content_type:
        user += f"Content type: {content_type}\n"
    user += "\nMarkdown body to fill (replace only [...] placeholders; keep {{...}} and all headings):\n\n"
    user += body
    return instructions, user


def fill_one(
    path: Path,
    *,
    model: str,
    base_url: str,
    api_key: str,
    dry_run: bool,
    write: bool,
    qa_enabled: bool,
    qa_strict: bool,
    style: str = "docs",
    block_on_fail: bool = False,
    quality_gate: bool = False,
    quality_retries: int = 2,
    quality_strict: bool = False,
    use_html: bool = False,
) -> str:
    """Process one file. Returns: 'wrote' | 'would_fill' | 'blocked' | 'qa_fail' | 'quality_fail' | 'api_fail' | 'skip'."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  Skip {path.name}: read error — {e}")
        return "skip"
    meta, order, body, body_start = _parse_frontmatter(content)
    if not use_html and not body.strip():
        print(f"  Skip {path.name}: empty body")
        return "skip"
    if use_html:
        tool_list = _load_affiliate_tools()
        base_instructions, user_message = _build_html_prompt(meta, tool_list)
    else:
        base_instructions, user_message = build_prompt(meta, body, style=style)
    new_body = ""
    quality_failed_after_retries = False
    if quality_gate:
        attempt = 0
        while True:
            current_instructions = base_instructions
            if attempt > 0:
                suffix = "Return the full HTML body." if use_html else "Return the full markdown body."
                current_instructions = base_instructions + "\n\nQUALITY FEEDBACK:\nYour previous output FAILED the Output Contract for these reasons:\n" + "\n".join("- " + r for r in last_reasons) + "\n\nFix ALL issues. Keep headings unchanged. " + suffix
            try:
                new_body = call_responses_api(
                    current_instructions, user_message, model=model, base_url=base_url, api_key=api_key
                )
            except Exception as e:
                print(f"  Skip {path.name}: API error — {e}")
                _append_error_log(path.stem, "ERROR", f"API error: {e}")
                return "api_fail"
            # TYMCZASOWE: logowanie surowej odpowiedzi
            print("\n--- SUROWA ODPOWIEDŹ API ---")
            print(new_body)
            print("--- KONIEC ODPOWIEDZI ---\n")
            if new_body.startswith("---"):
                idx = new_body.find("\n---", 3)
                if idx != -1:
                    new_body = new_body[idx + 4 :].lstrip("\n")
            new_body, sanitize_notes = sanitize_filled_body(new_body)
            if sanitize_notes:
                print(f"  Sanitized: {path.name} — {'; '.join(sanitize_notes)}")
            new_body, strip_notes = strip_editor_notes(new_body)
            if strip_notes:
                print(f"  Stripped editor notes: {path.name} — {'; '.join(strip_notes)}")
            new_body, bracket_notes = replace_known_bracket_placeholders(new_body)
            if bracket_notes:
                print(f"  Replaced known placeholders: {path.name} — {'; '.join(bracket_notes)}")
            last_reasons = check_output_contract(new_body, meta.get("content_type", ""), quality_strict)
            if not last_reasons:
                if attempt > 0:
                    print(f"  Quality Gate PASS: {path.name}")
                break
            if attempt >= quality_retries:
                print(f"  Quality Gate FAIL: {path.name} — {'; '.join(last_reasons)} (after {quality_retries} retries)")
                quality_failed_after_retries = True
                break
            print(f"  Quality Gate FAIL: {path.name} — {'; '.join(last_reasons)}; retry {attempt + 1}/{quality_retries}")
            attempt += 1
        if quality_failed_after_retries:
            if write and block_on_fail:
                blocked_content = _serialize_frontmatter(meta, order, "blocked") + "\n" + body
                backup = path.with_suffix(path.suffix + ".bak")
                try:
                    backup.write_text(content, encoding="utf-8")
                except OSError as e:
                    print(f"  Skip {path.name}: backup failed (blocked) — {e}")
                    return "quality_fail"
                path.write_text(blocked_content, encoding="utf-8")
                print(f"  Blocked (quality gate): {path.name}")
                return "blocked"
            _append_error_log(path.stem, "ERROR", f"Quality gate fail: {'; '.join(last_reasons)}")
            return "quality_fail"
    else:
        try:
            new_body = call_responses_api(
                base_instructions, user_message, model=model, base_url=base_url, api_key=api_key
            )
        except Exception as e:
            print(f"  Skip {path.name}: API error — {e}")
            _append_error_log(path.stem, "ERROR", f"API error: {e}")
            return "api_fail"
        # TYMCZASOWE: logowanie surowej odpowiedzi
        print("\n--- SUROWA ODPOWIEDŹ API ---")
        print(new_body)
        print("--- KONIEC ODPOWIEDZI ---\n")
        if new_body.startswith("---"):
            idx = new_body.find("\n---", 3)
            if idx != -1:
                new_body = new_body[idx + 4 :].lstrip("\n")
        new_body, sanitize_notes = sanitize_filled_body(new_body)
        if sanitize_notes:
            print(f"  Sanitized: {path.name} — {'; '.join(sanitize_notes)}")
        new_body, strip_notes = strip_editor_notes(new_body)
        if strip_notes:
            print(f"  Stripped editor notes: {path.name} — {'; '.join(strip_notes)}")
        new_body, bracket_notes = replace_known_bracket_placeholders(new_body)
        if bracket_notes:
            print(f"  Replaced known placeholders: {path.name} — {'; '.join(bracket_notes)}")
    new_content = _serialize_frontmatter(meta, order) + "\n" + new_body

    if qa_enabled:
        ok, reasons = run_preflight_qa(
            content, new_content, body, new_body, strict=qa_strict, is_html=use_html
        )
        if not ok:
            print(f"  QA FAIL: {path.name} — {'; '.join(reasons)}")
            if write and block_on_fail:
                blocked_content = _serialize_frontmatter(meta, order, "blocked") + "\n" + body
                backup = path.with_suffix(path.suffix + ".bak")
                try:
                    backup.write_text(content, encoding="utf-8")
                except OSError as e:
                    print(f"  Skip {path.name}: backup failed (blocked) — {e}")
                    return "qa_fail"
                path.write_text(blocked_content, encoding="utf-8")
                print(f"  Blocked: {path.name} (reason: QA fail)")
                return "blocked"
            _append_error_log(path.stem, "ERROR", f"QA fail: {'; '.join(reasons)}")
            return "qa_fail"
        if dry_run:
            print(f"  QA PASS: {path.name} (dry-run)")
            return "would_fill"

    if dry_run or not write:
        if not qa_enabled:
            print(f"  Would fill: {path.name} (dry-run)")
        return "would_fill"

    meta["status"] = "filled"
    if use_html:
        out_path = path.with_suffix(".html")
        new_content = _frontmatter_comment_string(meta) + "\n" + new_body
        had_existing = out_path.exists()
        if had_existing:
            backup = out_path.with_suffix(".html.bak")
            try:
                backup.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError as e:
                print(f"  Skip {path.name}: backup of existing .html failed — {e}")
                return "skip"
        try:
            out_path.write_text(new_content, encoding="utf-8")
        except OSError as e:
            print(f"  Skip {path.name}: write failed — {e}")
            return "skip"
        _record_fill_cost(path.stem, new_content)
        print(f"  Filled: {out_path.name}" + (f" (backup: {backup.name})" if had_existing else ""))
        return "wrote"
    new_content = _serialize_frontmatter(meta, order) + "\n" + new_body
    backup = path.with_suffix(path.suffix + ".bak")
    try:
        backup.write_text(content, encoding="utf-8")
    except OSError as e:
        print(f"  Skip {path.name}: backup failed — {e}")
        return "skip"
    path.write_text(new_content, encoding="utf-8")
    _record_fill_cost(path.stem, new_content)
    print(f"  Filled: {path.name} (backup: {backup.name})")
    return "wrote"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill article skeletons: replace [...] with AI-generated prose. Default: dry-run."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write changes (creates .bak backup per file).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refill even if status is already 'filled'.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model (default: gpt-4o-mini).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Process at most N files (0 = no limit).",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="Only process files with filename date >= this date.",
    )
    parser.add_argument(
        "--slug_contains",
        metavar="TEXT",
        help="Only process filenames containing this text.",
    )
    parser.add_argument(
        "--qa",
        action="store_true",
        help="Run preflight QA (default when --write; use in dry-run to report pass/fail).",
    )
    parser.add_argument(
        "--no-qa",
        action="store_true",
        help="Disable preflight QA even when using --write.",
    )
    parser.add_argument(
        "--qa_strict",
        action="store_true",
        help="Stricter QA (e.g. higher word-count threshold).",
    )
    parser.add_argument(
        "--style",
        choices=["docs", "concise", "detailed"],
        default="docs",
        help="Instruction style: docs (default), concise, or detailed.",
    )
    parser.add_argument(
        "--block_on_fail",
        action="store_true",
        help="On QA fail with --write: set article status to 'blocked' (frontmatter-only write) and continue.",
    )
    parser.add_argument(
        "--quality_gate",
        action="store_true",
        help="Enable output contract checks and retries (Decision rules, Tradeoffs, SOP, Templates).",
    )
    parser.add_argument(
        "--quality_retries",
        type=int,
        default=2,
        metavar="N",
        help="Extra API attempts when quality gate fails (default: 2).",
    )
    parser.add_argument(
        "--quality_strict",
        action="store_true",
        help="Stricter quality gate (higher bullet/word counts).",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate article body as HTML with Tailwind (output .html with comment frontmatter).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        return
    base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").strip()

    dry_run = not args.write
    if dry_run:
        print("DRY-RUN (no files will be modified). Use --write to apply changes.\n")

    if not ARTICLES_DIR.exists():
        print("Articles directory not found.")
        return

    candidates: list[Path] = []
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        stem = path.stem
        if args.since and len(stem) >= 10 and stem[:10] < args.since:
            continue
        if args.slug_contains and args.slug_contains not in stem:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _, body, _ = _parse_frontmatter(content)
        if should_process(meta, body, args.force, use_html=args.html):
            candidates.append(path)

    if args.limit > 0:
        candidates = candidates[: args.limit]
    if not candidates:
        print("No matching draft articles to process.")
        return

    qa_enabled = (args.write and not args.no_qa) or (dry_run and args.qa)
    if args.write and args.no_qa:
        print("Preflight QA disabled (--no-qa).\n")
    elif qa_enabled:
        print("Preflight QA enabled.\n")

    print(f"Processing {len(candidates)} file(s)...\n")
    wrote = 0
    would_fill = 0
    qa_failed = 0
    quality_failed = 0
    api_failed = 0
    skipped = 0
    blocked = 0
    for path in candidates:
        result = fill_one(
            path,
            model=args.model,
            base_url=base_url,
            api_key=api_key,
            dry_run=dry_run,
            write=args.write,
            qa_enabled=qa_enabled,
            qa_strict=args.qa_strict,
            style=args.style,
            block_on_fail=args.block_on_fail,
            quality_gate=args.quality_gate,
            quality_retries=args.quality_retries,
            quality_strict=args.quality_strict,
            use_html=args.html,
        )
        if result == "wrote":
            wrote += 1
        elif result == "would_fill":
            would_fill += 1
        elif result == "blocked":
            blocked += 1
        elif result == "qa_fail":
            qa_failed += 1
        elif result == "quality_fail":
            quality_failed += 1
        elif result == "api_fail":
            api_failed += 1
        else:
            skipped += 1

    print(f"\nSummary:")
    print(f"  candidates found:     {len(candidates)}")
    print(f"  filled successfully: {wrote} wrote, {would_fill} would fill (dry-run)")
    print(f"  QA failed:           {qa_failed}")
    print(f"  quality failed:     {quality_failed}")
    print(f"  API failed:          {api_failed}")
    print(f"  skipped:             {skipped}")
    print(f"  blocked:             {blocked}")

    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        (LOGS_DIR / "last_run_fill_articles.txt").write_text(datetime.now().isoformat(), encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    main()
