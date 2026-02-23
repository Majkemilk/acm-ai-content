#!/usr/bin/env python3
"""
Fill article skeletons: replace bracket placeholders [...] with AI-generated prose.
Uses OpenAI Responses API (stdlib urllib only). Leaves {{...}} and structure intact.
Default: dry-run. Use --write to modify files (with .bak backup).
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
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


REFRESH_FAILURE_REASONS_FILE = LOGS_DIR / "refresh_failure_reasons.txt"


def _append_error_log(slug: str, level: str, message: str) -> None:
    """Append one line to logs/errors.log. Creates logs/ if needed."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] {slug}: {message}\n")
    except OSError:
        pass


def _append_refresh_failure_reason(slug: str, reasons: list[str]) -> None:
    """Append stem and QA/quality failure reasons for refresh_articles breakdown report (R4)."""
    if not reasons:
        return
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(REFRESH_FAILURE_REASONS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{slug}\t{'; '.join(reasons)}\n")
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
    """Build frontmatter block; preserve order, set status to status_value.
    The 'tools' value is taken from meta (may have been updated by tool selection)."""
    status_set = False
    seen_keys: set[str] = set()
    lines = ["---"]
    for k, v in order:
        seen_keys.add(k)
        if k == "status":
            v = status_value
            status_set = True
        elif k == "tools":
            v = meta.get("tools", v)
        v = str(v)
        if "\n" in v or '"' in v:
            v = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k}: "{v}"')
    if not status_set:
        lines.append(f'status: "{status_value}"')
    if "tools" not in seen_keys and meta.get("tools"):
        v = str(meta["tools"])
        if "\n" in v or '"' in v:
            v = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'tools: "{v}"')
    lines.append("---")
    return "\n".join(lines) + "\n"


def has_bracket_placeholders(body: str) -> bool:
    """True if body contains [...] placeholders (not markdown links)."""
    return bool(BRACKET_PLACEHOLDER.search(body))


def is_checkbox_token(token: str) -> bool:
    """True if token is a markdown checkbox [ ], [x], [X], or [-] (not a placeholder)."""
    return token in ("[ ]", "[x]", "[X]", "[-]")


def sanitize_filled_body(text: str, skip_headings: bool = True) -> tuple[str, list[str]]:
    """Replace forbidden phrases in body. If skip_headings=True, heading lines (#) are left unchanged.
    If skip_headings=False, all lines are sanitized (use before QA so headings don't trigger fail)."""
    notes: list[str] = []
    pricing_count = 0
    best_count = 0
    guarantee_count = 0
    out_lines: list[str] = []
    dollar_count = 0
    for line in text.split("\n"):
        if skip_headings and line.lstrip().startswith("#"):
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
    ("[Product Name]", "the product"),
    ("[Product Category]", "the product category"),
    ("[Video Link]", "the video link"),
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


def replace_remaining_bracket_placeholders_with_quoted(text: str) -> tuple[str, list[str]]:
    """Replace any remaining [xxx] (not links, not checkboxes) with \"xxx\" so QA does not fail. Returns (text, notes)."""
    notes: list[str] = []

    def repl(match: re.Match[str]) -> str:
        full = match.group(0)
        if is_checkbox_token(full):
            return full
        inner = full[1:-1]
        escaped = inner.replace("\\", "\\\\").replace('"', '\\"')
        notes.append(f'placeholder [{inner}] -> "{inner}"')
        return '"' + escaped + '"'

    out = BRACKET_PLACEHOLDER.sub(repl, text)
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


# Word-count thresholds by audience (normal, strict). Used by run_preflight_qa.
# Raised +100 again to further reduce borderline QA failures.
WORD_COUNT_BY_AUDIENCE: dict[str, tuple[int, int]] = {
    "beginner": (700, 1000),
    "intermediate": (900, 1200),
    "professional": (900, 1200),
}
WORD_COUNT_DEFAULT = (700, 1000)  # when audience_type missing or unknown

STYLE_FOR_AUDIENCE: dict[str, str] = {
    "beginner": "docs",
    "intermediate": "concise",
    "professional": "detailed",
}
STYLE_DEFAULT = "docs"


def run_preflight_qa(
    original_full_text: str,
    filled_full_text: str,
    original_body: str,
    filled_body: str,
    strict: bool = False,
    is_html: bool = False,
    audience_type: str | None = None,
    min_words_override: int | None = None,
    content_type: str | None = None,
) -> tuple[bool, list[str]]:
    """Validate filled output. Returns (ok, list of failure reasons).
    When is_html=True, H1/H2 structure check is skipped; bracket/word/forbidden use stripped text.
    Word-count threshold depends on audience_type: beginner (700/1000), intermediate (900/1200), professional (900/1200).
    Try-it-yourself descriptor check (Prompt #1, Prompt #2, Action cue) runs only when content_type is 'how-to'."""
    reasons: list[str] = []

    # A. Mustache preservation (skip in HTML mode – HTML articles do not use {{...}})
    # Tool-related mustaches are legitimately replaced by fill_articles tool selection
    _TOOL_MUSTACHES = {"{{PRIMARY_TOOL}}", "{{SECONDARY_TOOL}}", "{{TOOLS_MENTIONED}}"}
    if not is_html:
        orig_tokens = set(MUSTACHE_REGEX.findall(original_full_text))
        filled_tokens = set(MUSTACHE_REGEX.findall(filled_full_text))
        missing = (orig_tokens - filled_tokens) - _TOOL_MUSTACHES
        added = filled_tokens - orig_tokens
        if missing:
            reasons.append(f"mustache removed: {sorted(missing)}")
        if added:
            reasons.append(f"mustache introduced: {sorted(added)}")

    # For HTML we run B/D/E on stripped text
    text_for_checks = _strip_html_tags(filled_body) if is_html else filled_body

    # B. Bracket placeholders removed (ignore markdown checkboxes [ ], [x], [X], [-]; ignore content in Template 1/2 sections; ignore fenced code blocks)
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
        # Usuń fenced code blocks — Prompt #1 i Prompt #2 mogą legalnie zawierać [placeholder] tokeny
        body_without_templates = re.sub(r"```[^`]*?```", "", body_without_templates, flags=re.DOTALL)
    all_bracket = BRACKET_PLACEHOLDER.findall(body_without_templates)
    remaining = [m for m in all_bracket if not is_checkbox_token(m)]
    if remaining:
        reasons.append(f"bracket placeholders still present: {remaining[:5]}{'...' if len(remaining) > 5 else ''}")

    # C. H1 and H2 structure unchanged (skip for HTML; H3/H4 may vary for markdown)
    # Static editorial sections are excluded — they are restored in post-processing, not regenerated by AI.
    _EDITORIAL_H2: set[str] = {
        "## Verification policy (editors only)",
        "## Pre-publish checklist",
    }
    if not is_html:
        orig_h1 = _h1_lines(original_body)
        filled_h1 = _h1_lines(filled_body)
        orig_h2 = _h2_lines(original_body)
        filled_h2 = _h2_lines(filled_body)
        if orig_h1 != filled_h1:
            reasons.append(f"H1 headings changed: expected {orig_h1!r}, got {filled_h1!r}")
        missing_h2 = (set(orig_h2) - set(filled_h2)) - _EDITORIAL_H2
        if missing_h2:
            reasons.append(f"H2 headings missing: {', '.join(missing_h2)}")

    # D. Word count (use stripped text for HTML); threshold by audience or override
    word_count = len(text_for_checks.split())
    if min_words_override is not None:
        threshold = min_words_override
    else:
        at = (audience_type or "").strip().lower()
        min_words, min_words_strict = WORD_COUNT_BY_AUDIENCE.get(at, WORD_COUNT_DEFAULT)
        threshold = min_words_strict if strict else min_words
    if word_count < threshold:
        at = (audience_type or "").strip().lower()
        reasons.append(f"word count {word_count} < {threshold} (audience: {at or 'default'})")

    # E. Forbidden patterns (use stripped text for HTML to avoid matching inside attributes)
    for pat, label in FORBIDDEN_PATTERNS:
        if pat.search(text_for_checks):
            reasons.append(f"forbidden pattern: {label}")

    # F. Deterministic Try-it-yourself labels and reference tool check (only when section is required: how-to)
    lowered = text_for_checks.lower()
    if "try it yourself" in lowered and (content_type or "").strip().lower() == "how-to":
        input_re = re.compile(
            r"(Here is the input \(Prompt #1\) ready to use with|This is the input \(Prompt #1\), ready to use with|Below is the input \(Prompt #1\), ready to use with|Use this input \(Prompt #1\), ready to use with)\s+(.+?)\s+\(AI tool\)\.",
            re.IGNORECASE,
        )
        output_re = re.compile(
            r"(The AI returns the following output \(Prompt #2\), (?:which|that) is ready to use with|Below is the output \(Prompt #2\) the AI returns, which is ready to use with)\s+(.+?)\s+\(AI tool\)\.",
            re.IGNORECASE,
        )
        m_in = input_re.search(text_for_checks)
        m_out = output_re.search(text_for_checks)
        if not m_in:
            reasons.append("missing deterministic Prompt #1 descriptor line")
        if not m_out:
            reasons.append("missing deterministic Prompt #2 descriptor line")
        if m_in and m_out:
            tool_in = m_in.group(2).strip()
            tool_out = m_out.group(2).strip()
            if tool_in != tool_out:
                reasons.append(f"Prompt #1 and Prompt #2 tool mismatch: '{tool_in}' vs '{tool_out}'")
            ref_tools = {(name or "").strip() for name, _url, _short in _load_affiliate_tools() if (name or "").strip()}
            if tool_in not in ref_tools:
                reasons.append(f"Prompt tool not in reference list: '{tool_in}'")
        if "Action cue:" not in text_for_checks:
            reasons.append("missing deterministic CTA line after Prompt #2")

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


def _is_affiliate_url(url: str) -> bool:
    """True if URL looks like an affiliate/tracking link (query params or path indicating referral)."""
    if not url or not url.strip():
        return False
    if "?" in url:
        query = url.split("?", 1)[1].lower()
        if any(k in query for k in ("via=", "ref=", "affiliate=", "aff=", "tag=", "tid=", "pc=")):
            return True
    path = url.split("?")[0].lower()
    if "/ref/" in path or "/aff/" in path or "/affiliate" in path:
        return True
    return False


def _load_affiliate_tools() -> list[tuple[str, str, str]]:
    """Load (name, url, short_description_en) from content/affiliate_tools.yaml. Stdlib only.
    short_description_en is optional in YAML; use "" when missing."""
    path = PROJECT_ROOT / "content" / "affiliate_tools.yaml"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")

    def _val(s: str) -> str:
        s = (s or "").strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1].replace('\\"', '"').strip()
        return s

    items: list[tuple[str, str, str]] = []
    in_tools = False
    current_name = ""
    current_url = ""
    current_short = ""
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
                items.append((current_name, current_url, current_short))
            current_name = ""
            current_url = ""
            current_short = ""
            part = stripped[2:].strip()
            kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", part)
            if kv:
                k, v = kv.group(1), _val(kv.group(2))
                if k == "name":
                    current_name = v
                elif k == "affiliate_link":
                    current_url = v
                elif k == "short_description_en":
                    current_short = v
            continue
        kv = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", stripped)
        if kv:
            k, v = kv.group(1), _val(kv.group(2))
            if k == "name":
                current_name = v
            elif k == "affiliate_link":
                current_url = v
            elif k == "short_description_en":
                current_short = v
    if current_name:
        items.append((current_name, current_url, current_short))
    return items


def _split_tools_by_affiliate(
    tools: list[tuple[str, str, str]],
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Split (name, url, short_desc) into affiliate list and other list based on URL heuristics."""
    affiliate: list[tuple[str, str, str]] = []
    other: list[tuple[str, str, str]] = []
    for name, url, short_desc in tools:
        if not url:
            continue
        if _is_affiliate_url(url):
            affiliate.append((name, url, short_desc))
        else:
            other.append((name, url, short_desc))
    return (affiliate, other)


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


def _try_it_yourself_instruction(content_type: str, audience_type: str, *, html: bool = False) -> str:
    """Return the 'Try it yourself: Build your own AI prompt' instruction block.

    Rules:
    - how-to: always required
    - guide: required only when topic involves creating/processing content (AI decides)
    - best / comparison / review: not included
    Audience modulation:
    - beginner / intermediate: structured meta-prompt (Role/Goal/Task/Uncertainty/Permission)
    - professional: advanced chain-of-thought multi-step workflow
    """
    ct = (content_type or "").strip().lower()
    at = (audience_type or "").strip().lower()
    if ct not in ("how-to", "guide"):
        return ""

    if ct == "how-to":
        presence = (
            'REQUIRED SECTION: "Try it yourself: Build your own AI prompt"\n'
            "You MUST include this subsection (H3) inside the Step-by-step workflow section.\n"
        )
    else:
        presence = (
            'CONDITIONAL SECTION: "Try it yourself: Build your own AI prompt"\n'
            "Include this subsection (H3) inside the Step-by-step workflow section ONLY if "
            "the article topic involves creating, processing, or transforming content with AI tools. "
            "If the topic is purely strategic, analytical, or organizational, omit this subsection.\n"
        )

    if html:
        pre_tag = '<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">'
        pre_close = "</pre>"
        fmt_note = f"Put each prompt block inside {pre_tag}...{pre_close}."
    else:
        pre_tag = "```"
        pre_close = "```"
        fmt_note = "Put each prompt block inside a fenced code block (triple backticks)."

    if at == "professional":
        body = f"""{presence}
When you include this subsection, follow these rules:

1) Workflow explanation (required at the start): State the workflow as: Human → Prompt #1 (meta-prompt to a general AI, using chain-of-thought reasoning) → AI returns Prompt #2 (ready-to-paste prompt for the specific tool) → Use Prompt #2 in the tool.

2) Prompt #1 — Advanced chain-of-thought meta-prompt. Structure it with ALL of the following LABELED parts. Each part MUST start on a new line with its label in bold followed by a colon. Do NOT merge parts into a single paragraph. Each part must be substantive (not a one-line placeholder).
- **Role:** set the AI's expertise domain and constraints (e.g. "You are a senior marketing automation architect specializing in…").
- **Objective:** the end goal stated as a measurable outcome.
- **Chain of thought:** explicit instruction: "Think step by step: first analyze the input data, then identify the key variables, then construct the prompt for the target tool."
- **Output specification:** describe the exact format and structure of the desired Prompt #2 output (e.g. "Return a numbered list of steps that can be pasted directly into Make / Descript / etc.").
- **Edge cases:** list 2-3 edge cases the AI should handle (e.g. "If the input contains mixed languages…", "If the dataset exceeds 1000 rows…").
- **Uncertainty:** if the AI is unsure about any element, it must state so and ask for clarification.
- **Permission:** if context is insufficient, the AI should ask clarifying questions.

Use the actual tool name from the article. {fmt_note}

3) Prompt #2 — Do NOT generate the content of Prompt #2 yourself. Instead, output the exact marker line [PROMPT2_PLACEHOLDER] where Prompt #2 should appear. The system will replace it with a real AI-generated output and will insert a single intro line before it (e.g. "The AI returns the following output (Prompt #2), which is ready to use with [tool] (AI tool)."). Do not add a separate intro sentence before the marker. {fmt_note}

Emphasize that this approach makes the user the architect of a multi-step reasoning workflow, not a passive consumer of templates."""
    else:
        body = f"""{presence}
When you include this subsection, follow these rules:

1) Workflow explanation (required at the start): The first paragraph MUST explicitly state the workflow as: Human → Prompt #1 (to a general AI) → AI returns Prompt #2 (ready-to-paste prompt for the specific tool) → Use Prompt #2 in the tool. Do not omit or shorten this.

2) Prompt #1 — Structured meta-prompt. Structure it with ALL of the following LABELED parts. Each part MUST start on a new line with its label in bold followed by a colon. Do NOT merge parts into a single paragraph. Each part must be substantive (not a one-line placeholder).
- **Role:** define the role of a specialist best suited to accomplish the goal (e.g. "You are a marketing analyst with experience in…").
- **Goal:** what the user wants to achieve (the outcome).
- **Task:** a concrete request that MUST begin with "Please create a prompt that will…" for the specific tool and use case (e.g. "Please create a prompt that will analyze competitor video tone for use in Descript.").
- **Uncertainty:** if the AI is unsure about any element, it must state so and ask for clarification.
- **Permission:** if context is insufficient, the AI may ask for more details.

Use the actual tool name from the article. {fmt_note}

3) Prompt #2 — Do NOT generate the content of Prompt #2 yourself. Instead, output the exact marker line [PROMPT2_PLACEHOLDER] where Prompt #2 should appear. The system will replace it with a real AI-generated output and will insert a single intro line before it (e.g. "The AI returns the following output (Prompt #2), which is ready to use with [tool] (AI tool)."). Do not add a separate intro sentence before the marker. {fmt_note}

Emphasize that this approach makes the user the architect of the workflow, not just a passive consumer."""

    return body


def _build_html_prompt(
    meta: dict,
    affiliate_tools: list[tuple[str, str, str]],
    other_tools: list[tuple[str, str, str]],
) -> tuple[str, str]:
    """(instructions, user_message) for AI to generate article body as HTML with Tailwind.
    Each tool is (name, url, short_description_en). Prefer affiliate tools when context fits; else use best from other."""
    title = (meta.get("title") or "").strip()
    keyword = (meta.get("primary_keyword") or "").strip()
    category = (meta.get("category") or meta.get("category_slug") or "").strip()
    content_type = (meta.get("content_type") or "").strip()
    audience_type = (meta.get("audience_type") or "").strip()

    def _fmt(t: tuple[str, str, str]) -> str:
        name, url, short = t[0], t[1], t[2]
        if short:
            return f"{name}={url}|{short}"
        return f"{name}={url}"

    tools_blob = ""
    if affiliate_tools or other_tools:
        parts = []
        if affiliate_tools:
            parts.append(
                "Affiliate tools (prefer when the tool truly fits the sentence/paragraph context; use exact URL): "
                + ", ".join(_fmt(t) for t in affiliate_tools if t[1])
            )
        if other_tools:
            parts.append(
                "Other tools (use when no affiliate tool fits the context; choose the best match for the task): "
                + ", ".join(_fmt(t) for t in other_tools if t[1])
            )
        tools_blob = " ".join(parts) + "\n\n"
        tools_blob += (
            "LINKING RULES:\n"
            "- Prefer tools from the Affiliate list when they are a good fit for the context. Use the Other list only when no affiliate tool fits.\n"
            "- At the first occurrence of each tool in the article body, use this format: <a href=\"URL\">Name</a> (short description in English, one sentence). Example: <a href=\"https://example.com\">Pictory</a> (AI video from text). At later occurrences of the same tool, link only the name: <a href=\"URL\">Name</a>, without repeating the description.\n"
            "- If a tool has a description after | in the list above (e.g. Name=URL|description), use that description in the parentheses. Otherwise write a factual one-sentence description of what the tool does; if unsure, use a generic form like \"AI tool for [category or use case]\"."
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
- When NOT to use this (when to avoid this approach)
- FAQ (at least 2–3 questions and answers)
- Internal links (1–2 sentences suggesting related reads; you may use placeholder URLs like # or /blog/ for now)
- List of AI tools mentioned in this article (place near the end, e.g. after FAQ or after Internal links; see "SECTION: List of AI tools" below)
- Optionally: Case study (a few paragraphs illustrating a real-world scenario: specific data, challenges, and outcomes; see example below)

{_try_it_yourself_instruction(content_type, audience_type, html=True)}

SECTION: "List of AI tools mentioned in this article"
Include a section titled "List of AI tools mentioned in this article" near the end of the article (e.g. after FAQ or after Internal links; choose a consistent, logical position). This section gives readers a quick reference and supports affiliate links.
- Placement: Near the end, after FAQ or after Internal links. Do not place after the disclosure (the template adds disclosure automatically).
- Content: A bulleted list. For each tool that is both (a) in the Affiliate or Other tool list above and (b) relevant to the article (actually discussed or clearly pertinent), add one bullet containing: the tool name as a link using the exact URL from the list above, then a short one-sentence description in English.
- Description rules: Use the same style as in-article descriptions: factual, in English, one sentence (e.g. "video editing and transcription", "AI-powered transcription with speaker identification"). If a description was provided after | in the tool list, use it here too. Otherwise be concise and specific; if unsure, use a generic form like "AI tool for [use case]". Avoid vague phrases like "powerful tool". Do not invent tools.
- Format: Use H2 for the section title. Use <ul class="list-disc list-inside space-y-2 text-gray-700"> for the list. Each item: <a href="URL">Tool Name</a> — description sentence. Include only tools from the Affiliate or Other list above; do not invent tools. The AI decides which tools to include based on article relevance. If both lists are empty, omit this section.

IMPORTANT — LENGTH: Follow the audience-based length rule (see Audience and Length below). To achieve the required word count:
- Expand "Template 1" and "Template 2" with rich, detailed examples (multiple lines or bullets each; real company names, metrics, and scenarios).
- Consider adding a "Case study" section after the templates: a concrete example of someone using the described AI tools, with specific data, challenges, and outcomes (a few paragraphs long).
Example case study tone: "A small e-commerce company, ShopSmart, used Descript to analyze competitor social media videos. They discovered that competitors were heavily using influencer marketing, which led them to pivot their strategy. Within three months, their engagement increased by 40%."

LENGTH AND CONTENT RULES:
- NEVER use square-bracket placeholders (e.g. [Name], [Date], [Customer Name], [Your Company], [Insert URL]). Every template field, example, and sentence must be filled with concrete, realistic content. Use real-looking example names, dates, product names — never leave or introduce any [bracket] token. QA will reject the article if any remain. If you need to indicate a variable or example slot, use round parentheses ( ) instead of square brackets, e.g. (video title) or (your product name).
- FORBIDDEN PHRASES (QA will reject the article if present): Do not use "unlimited", "limit to", "limited to", or "up to [number]" (e.g. "up to 5"). Do not use $ or any currency amount (e.g. $99). Do not use "the best", "#1", or "pricing" anywhere in the article, including in headings. Use neutral wording instead (e.g. "many", "as needed", "several", "a set of steps", "cost").

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

Output ONLY the HTML fragment that goes inside the article (no wrapper tags, no markdown).

At the very end of your response (after the HTML), add one plain-text line:
TOOLS_SELECTED: ToolName1, ToolName2, ...
- minimum 1, maximum 5 tools
- names must match exactly one of the tools from the lists above
- do not invent tool names"""
    audience_line = _audience_instruction(audience_type)
    if audience_line:
        instructions += "\n\nAudience (MUST follow): " + audience_line
    instructions += "\n\nLength (MUST follow): " + _audience_length_guidance(audience_type)

    user = f"Article title: {title}\n"
    if keyword:
        user += f"Primary keyword: {keyword}\n"
    if category:
        user += f"Category: {category}\n"
    if content_type:
        user += f"Content type: {content_type}\n"
    if audience_type:
        user += f"Target audience level: {audience_type}\n"
    length_guide = _audience_length_guidance(audience_type)
    user += f"\nGenerate the complete article body in HTML with Tailwind classes. Include all required sections (including 'List of AI tools mentioned in this article' near the end). {length_guide} No square-bracket placeholders; use round parentheses ( ) for any variable or example slot, e.g. (video title)."
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

    # "Try it yourself" validation: required for how-to, structural check for guide
    try_marker = "try it yourself"
    has_try = try_marker in body_lower
    if content_type == "how-to" and not has_try:
        missing.append("missing required section: 'Try it yourself: Build your own AI prompt' (mandatory for how-to)")
    if has_try:
        prompt_1_present = "prompt #1" in body_lower or "prompt 1" in body_lower
        prompt_2_present = "prompt #2" in body_lower or "prompt 2" in body_lower
        if not prompt_1_present:
            missing.append("'Try it yourself' section missing Prompt #1 (meta-prompt)")
        if not prompt_2_present:
            missing.append("'Try it yourself' section missing Prompt #2 (ready-to-paste output)")

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


_PROMPT1_HTML_RE = re.compile(
    r"(?:Try it yourself|Build your own AI prompt).*?"
    r"<pre[^>]*>(.*?)</pre>",
    re.DOTALL | re.IGNORECASE,
)
_PROMPT1_MD_RE = re.compile(
    r"(?:Try it yourself|Build your own AI prompt).*?"
    r"```(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_PROMPT2_PLACEHOLDER = "[PROMPT2_PLACEHOLDER]"
_PROMPT2_PLACEHOLDER_RE = re.compile(r'["\[\(\s]*PROMPT2_PLACEHOLDER["\]\)\s]*')
_PROMPT2_PRE_RE = re.compile(
    r"<pre[^>]*>[^<]*?PROMPT2_PLACEHOLDER[^<]*?</pre>",
    re.IGNORECASE | re.DOTALL,
)
_PROMPT2_MD_BLOCK_RE = re.compile(
    r"```[^\n]*\n[^`]*?PROMPT2_PLACEHOLDER[^`]*?\n```",
    re.DOTALL,
)
_PROMPT2_MAX_TOKENS = 600

_TRY_INPUT_VARIANTS = [
    "Here is the input (Prompt #1) ready to use with {tool} (AI tool).",
    "This is the input (Prompt #1), ready to use with {tool} (AI tool).",
    "Below is the input (Prompt #1), ready to use with {tool} (AI tool).",
    "Use this input (Prompt #1), ready to use with {tool} (AI tool).",
]

_TRY_OUTPUT_VARIANTS = [
    "The AI returns the following output (Prompt #2), which is ready to use with {tool} (AI tool).",
    "The AI returns the following output (Prompt #2), that is ready to use with {tool} (AI tool).",
    "Below is the output (Prompt #2) the AI returns, which is ready to use with {tool} (AI tool).",
]

_TRY_CTA_VARIANTS = [
    "Now the next move is yours—run this in your AI tool and build from the result.",
    "Continue from here by pasting Prompt #2 into your AI tool and iterating the output.",
    "Your momentum starts now—use Prompt #2 in the AI tool and refine what comes back.",
    "Take it live: run Prompt #2 in your AI tool and shape the output to your case.",
    "You are in control—paste Prompt #2 into the AI tool and guide the next iteration.",
    "The next step depends on you: execute Prompt #2 in the AI tool and optimize.",
    "Push this forward by running Prompt #2 in your AI tool and tuning the result.",
    "Make it practical now—use Prompt #2 in the AI tool and adapt it to your workflow.",
    "Your implementation begins here: paste Prompt #2 into the AI tool and act on it.",
    "Turn this into action by executing Prompt #2 in your AI tool today.",
    "The rest is execution: run Prompt #2 in the AI tool and apply the outcome.",
    "From strategy to action—use Prompt #2 in your AI tool and iterate quickly.",
    "Bring it to life now: paste Prompt #2 into the AI tool and continue building.",
    "You are one step away—run Prompt #2 in the AI tool and refine the response.",
    "Take ownership of the next phase by using Prompt #2 in your AI tool.",
    "Your next win starts here—execute Prompt #2 in the AI tool and improve output quality.",
    "Move ahead confidently: run Prompt #2 in your AI tool and calibrate results.",
    "Now convert this into outcomes by pasting Prompt #2 into the AI tool.",
    "The continuation is on your side—use Prompt #2 in the AI tool and optimize.",
    "Put this into motion: execute Prompt #2 in your AI tool and iterate.",
    "Advance to the practical step—run Prompt #2 in your AI tool and adjust.",
    "Next, use Prompt #2 in the AI tool to generate the output you can build on.",
    "Your turn to execute: paste Prompt #2 in the AI tool and fine-tune.",
    "Create your next result by running Prompt #2 in the AI tool.",
    "Keep going by applying Prompt #2 directly in your AI tool.",
    "The final stretch is yours—use Prompt #2 in the AI tool and refine.",
    "Now unlock the real value: run Prompt #2 in the AI tool and adapt.",
    "Take the generated prompt and execute it in your AI tool to continue.",
    "Proceed by pasting Prompt #2 into your AI tool and improving the response.",
    "You decide what comes next—run Prompt #2 in your AI tool now.",
    "Convert this plan into execution with Prompt #2 in your AI tool.",
    "From here, launch Prompt #2 in the AI tool and iterate for better fit.",
    "Take action now: use Prompt #2 in your AI tool and build the next version.",
    "The next output depends on your run—execute Prompt #2 in the AI tool.",
    "Continue with confidence by running Prompt #2 in your AI tool.",
    "Move from draft to results: paste Prompt #2 into your AI tool.",
    "Now produce your tailored output by using Prompt #2 in the AI tool.",
    "Keep the workflow moving—execute Prompt #2 in your AI tool and adjust.",
    "Your practical continuation starts with Prompt #2 in the AI tool.",
    "Deploy Prompt #2 in the AI tool now and evolve the result.",
    "You are ready for execution: run Prompt #2 in your AI tool.",
    "Push this one level higher by using Prompt #2 in your AI tool.",
    "Take the baton and run Prompt #2 in the AI tool to proceed.",
    "Activate the next phase by pasting Prompt #2 into your AI tool.",
    "Drive the process forward with Prompt #2 in your AI tool.",
    "Now generate your real output by executing Prompt #2 in the AI tool.",
    "Turn insight into output—use Prompt #2 in your AI tool right away.",
    "Your continuation path is clear: run Prompt #2 in the AI tool.",
    "Next output is in your hands—execute Prompt #2 in your AI tool.",
    "Keep building: paste Prompt #2 into your AI tool and iterate.",
]


def _variant_for_slug(slug: str, key: str, variants: list[str]) -> str:
    if not variants:
        return ""
    digest = hashlib.sha1(f"{slug}:{key}".encode("utf-8")).digest()
    idx = int.from_bytes(digest[:4], "big") % len(variants)
    return variants[idx]


def _first_reference_tool_name() -> str:
    for name, _url, _short in _load_affiliate_tools():
        nm = (name or "").strip()
        if nm:
            return nm
    return "ChatGPT"


def _inject_before_nth_pre_html(section: str, paragraph_html: str, n: int) -> str:
    matches = list(re.finditer(r"<pre[^>]*>.*?</pre>", section, flags=re.IGNORECASE | re.DOTALL))
    if len(matches) < n:
        return section
    target = matches[n - 1]
    return section[:target.start()] + paragraph_html + "\n" + section[target.start():]


def _normalize_try_it_yourself_html(body: str, *, slug: str, tool_name: str) -> str:
    """Deterministically enforce Prompt #1/#2 descriptor lines and CTA in Try-it-yourself section."""
    h3 = re.search(
        r"<h3[^>]*>\s*Try it yourself:\s*Build your own AI prompt\s*</h3>",
        body,
        flags=re.IGNORECASE,
    )
    if not h3:
        return body
    section_start = h3.end()
    next_h2 = re.search(r"<h2[^>]*>", body[section_start:], flags=re.IGNORECASE)
    section_end = section_start + next_h2.start() if next_h2 else len(body)
    section = body[section_start:section_end]

    # Remove previously auto-inserted descriptor/CTA lines so reruns stay clean.
    section = re.sub(
        r"<p[^>]*>[^<]*Prompt #1[^<]*\(AI tool\)\.[^<]*</p>\s*",
        "",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )
    section = re.sub(
        r"<p[^>]*>[^<]*Prompt #2[^<]*\(AI tool\)\.[^<]*</p>\s*",
        "",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Also remove AI-generated variants like "...output (Prompt #2), which is ready to use with your specific...":
    section = re.sub(
        r"<p[^>]*>[^<]*The AI returns the following output \(Prompt #2\)[^<]*</p>\s*",
        "",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )
    section = re.sub(
        r"<p[^>]*>[^<]*The AI returns the following:\s*</p>\s*",
        "",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )
    section = re.sub(
        r"<p[^>]*>[^<]*(?:Here is the output you would receive|This is the output you would receive):\s*</p>\s*",
        "",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )
    section = re.sub(
        r"<p[^>]*>\s*Action cue:.*?</p>\s*",
        "",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )

    safe_tool = (tool_name or "").strip() or _first_reference_tool_name()
    # Link tool name to affiliate/reference URL when available (ready to use with X)
    tool_url = next(
        (url for name, url, _ in _load_affiliate_tools() if (name or "").strip() == safe_tool),
        None,
    )
    if tool_url:
        linked_tool = f'<a href="{html.escape(tool_url, quote=True)}">{html.escape(safe_tool)}</a>'
    else:
        linked_tool = html.escape(safe_tool)
    in_line = _variant_for_slug(slug, "try-input", _TRY_INPUT_VARIANTS).format(tool=linked_tool)
    out_line = _variant_for_slug(slug, "try-output", _TRY_OUTPUT_VARIANTS).format(tool=linked_tool)
    cta_line = "Action cue: " + _variant_for_slug(slug, "try-cta", _TRY_CTA_VARIANTS)

    in_html = f'<p class="text-lg text-gray-700 mb-4">{in_line}</p>'
    out_html = f'<p class="text-lg text-gray-700 mb-4">{out_line}</p>'
    cta_html = f'<p class="text-lg text-gray-700 mb-4">{cta_line}</p>'

    section = _inject_before_nth_pre_html(section, in_html, 1)
    section = _inject_before_nth_pre_html(section, out_html, 2)
    pre_matches = list(re.finditer(r"<pre[^>]*>.*?</pre>", section, flags=re.IGNORECASE | re.DOTALL))
    if len(pre_matches) >= 2:
        p2_end = pre_matches[1].end()
        section = section[:p2_end] + "\n" + cta_html + section[p2_end:]

    return body[:section_start] + section + body[section_end:]


def _extract_prompt1(body: str, *, is_html: bool) -> str | None:
    """Extract the first code block (Prompt #1) from the Try-it-yourself section."""
    pattern = _PROMPT1_HTML_RE if is_html else _PROMPT1_MD_RE
    m = pattern.search(body)
    if not m:
        return None
    text = m.group(1).strip()
    if not text or len(text) < 30:
        return None
    return text


def _generate_real_prompt2(
    prompt1: str,
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> str | None:
    """Execute Prompt #1 via a separate API call to produce Prompt #2."""
    instructions = "wykonaj"
    try:
        result = call_responses_api(
            instructions, prompt1, model=model, base_url=base_url, api_key=api_key
        )
    except Exception as e:
        print(f"  Prompt #2 generation failed: {e}")
        return None
    if not result or len(result) < 20:
        return None
    return result.strip()


def _has_prompt2_placeholder(body: str) -> bool:
    """Check if body contains any variant of the PROMPT2_PLACEHOLDER marker."""
    return bool(_PROMPT2_PLACEHOLDER_RE.search(body))


def _insert_prompt2(body: str, prompt2_text: str, *, is_html: bool) -> str:
    """Replace PROMPT2_PLACEHOLDER (in any wrapper) with real Prompt #2 content."""
    escaped = re.sub(r"[<>&]", lambda m: {"<": "&lt;", ">": "&gt;", "&": "&amp;"}[m.group()], prompt2_text)
    if is_html:
        pre_match = _PROMPT2_PRE_RE.search(body)
        if pre_match:
            replacement = (
                '<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">'
                + escaped + "</pre>"
            )
            return body[:pre_match.start()] + replacement + body[pre_match.end():]
    else:
        md_match = _PROMPT2_MD_BLOCK_RE.search(body)
        if md_match:
            replacement = "```\n" + prompt2_text + "\n```"
            return body[:md_match.start()] + replacement + body[md_match.end():]
    return _PROMPT2_PLACEHOLDER_RE.sub(
        escaped if is_html else prompt2_text, body, count=1
    )


def _audience_instruction(audience_type: str) -> str:
    """One-line instruction for tone/depth by audience (from use-case batch)."""
    at = (audience_type or "").strip().lower()
    if at == "beginner":
        return "Target audience: beginners. Use simple language, avoid jargon; assume no prior experience; focus on getting started and clear step-by-step."
    if at == "intermediate":
        return "Target audience: intermediate. Assume some familiarity with the topic; you may use common terminology; include workflow depth and practical tradeoffs."
    if at == "professional":
        return "Target audience: professional/advanced. Assume experience; focus on scaling, integration, team use, and decision criteria; more concise, less hand-holding."
    return ""


def _audience_length_guidance(audience_type: str) -> str:
    """Minimum and target word count for prompt by audience (aligned with WORD_COUNT_BY_AUDIENCE)."""
    at = (audience_type or "").strip().lower()
    if at == "beginner":
        return "Minimum length: 700 words."
    if at == "intermediate":
        return "Minimum length: 900 words; for comprehensive sections aim for 1200."
    if at == "professional":
        return "Minimum length: 900 words; for comprehensive sections aim for 1200."
    return "Minimum length: 700 words."


_TOOLS_SELECTED_RE = re.compile(r"^TOOLS_SELECTED:\s*(.+)$", re.MULTILINE)


def _extract_tools_selected(body: str, valid_names: set[str]) -> tuple[str, list[str]]:
    """Extract TOOLS_SELECTED line from body. Returns (body without that line, validated tool names up to 5)."""
    match = _TOOLS_SELECTED_RE.search(body)
    if not match:
        return body, []
    raw = match.group(1).strip()
    names = [n.strip() for n in raw.split(",") if n.strip()]
    validated: list[str] = []
    for name in names:
        if name in valid_names:
            validated.append(name)
        else:
            for v in valid_names:
                if v.lower() == name.lower():
                    validated.append(v)
                    break
    body_clean = _TOOLS_SELECTED_RE.sub("", body).rstrip("\n") + "\n"
    return body_clean, validated[:5]


def _build_name_to_url_map() -> dict[str, str]:
    """name -> affiliate_link from affiliate_tools.yaml."""
    return {name: url for name, url, _ in _load_affiliate_tools() if url}


def _build_name_to_toolinfo_map() -> dict[str, tuple[str, str]]:
    """name -> (url, short_description_en) from affiliate_tools.yaml."""
    out: dict[str, tuple[str, str]] = {}
    for name, url, short_desc in _load_affiliate_tools():
        nm = (name or "").strip()
        if not nm or not url:
            continue
        out[nm] = (url, (short_desc or "").strip())
    return out


def _build_tools_mentioned_md(tools: list[str], name_to_url: dict[str, str]) -> str:
    """Build markdown bullet list for Tools mentioned section."""
    lines: list[str] = []
    for name in tools:
        url = name_to_url.get(name)
        if url:
            lines.append(f"- [{name}]({url})")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


# One sentence before "List of AI tools" (Option B disclaimer)
TOOLS_SECTION_DISCLAIMER_HTML = (
    '<p class="text-lg text-gray-700 mb-4">'
    "The tools listed are a suggestion for the use case described, not a claim that they are the best option."
    "</p>\n"
)


def _build_tools_mentioned_html(tools: list[str], toolinfo: dict[str, tuple[str, str]]) -> str:
    """Build HTML bullet list for tools with links and one-line descriptions."""
    items: list[str] = []
    for name in tools:
        url, short_desc = toolinfo.get(name, ("", ""))
        if not url:
            continue
        desc = short_desc if short_desc else f"AI tool for {name} workflows."
        items.append(f'  <li><a href="{url}">{name}</a> — {desc}</li>')
    if not items:
        return ""
    return "<ul class=\"list-disc list-inside space-y-2 text-gray-700\">\n" + "\n".join(items) + "\n</ul>"


def _upsert_tools_section_html(body: str, tools_ul_html: str) -> str:
    """Replace existing tools section in HTML or append if missing."""
    if not tools_ul_html:
        return body
    section_re = re.compile(
        r"(<h2[^>]*>\s*List of AI tools mentioned in this article\s*</h2>)(.*?)(?=<h2[^>]*>|$)",
        re.IGNORECASE | re.DOTALL,
    )
    m = section_re.search(body)
    if m:
        replacement = m.group(1) + "\n" + TOOLS_SECTION_DISCLAIMER_HTML + tools_ul_html + "\n\n"
        return body[:m.start()] + replacement + body[m.end():]
    heading = '<h2 class="text-3xl font-bold mt-8 mb-4">List of AI tools mentioned in this article</h2>\n'
    suffix = "" if body.endswith("\n") else "\n"
    return body + suffix + "\n" + heading + TOOLS_SECTION_DISCLAIMER_HTML + tools_ul_html + "\n"


def _has_assigned_tools(meta: dict) -> bool:
    """True if frontmatter has real (non-placeholder) tools."""
    tools = (meta.get("tools") or "").strip()
    return bool(tools) and not tools.startswith("{{")


def build_prompt(meta: dict, body: str, style: str = "docs") -> tuple[str, str]:
    """(instructions, user_message) for the model. style: docs | concise | detailed."""
    title = (meta.get("title") or "").strip()
    keyword = (meta.get("primary_keyword") or "").strip()
    category = (meta.get("category") or meta.get("category_slug") or "").strip()
    content_type = (meta.get("content_type") or "").strip()
    audience_type = (meta.get("audience_type") or "").strip()
    tools_note = ""
    if _has_assigned_tools(meta):
        tool_names = [t.strip() for t in (meta.get("tools") or "").split(",") if t.strip()]
        unique = list(dict.fromkeys(tool_names))
        tools_note = f" You may mention only these tools (do not invent others): {', '.join(unique)}."
    else:
        all_tools = _load_affiliate_tools()
        tools_for_prompt: list[str] = []
        for name, _url, short_desc in all_tools:
            name = name.strip()
            if not name:
                continue
            if short_desc:
                tools_for_prompt.append(f"{name} ({short_desc})")
            else:
                tools_for_prompt.append(name)
        if tools_for_prompt:
            tools_note = (
                " No tools are pre-assigned. From the list below, choose 1 to 5 tools "
                "that are MOST USEFUL for solving the problem described in this article. "
                "Selection criteria: direct relevance to the article's task and goals, "
                "not general popularity. Prefer tools from the 'referral' category when they fit.\n"
                f"Available tools: {', '.join(tools_for_prompt)}.\n"
                "IMPORTANT: At the very end of your response, on the LAST LINE, write exactly:\n"
                "TOOLS_SELECTED: ToolName1, ToolName2, ...\n"
                "(minimum 1, maximum 5 tools, comma-separated, names exactly as in the list above). "
                "Do not invent tool names outside this list."
            )

    style_phrase = {
        "concise": "Be concise: shorter sentences, fewer examples.",
        "detailed": "Include more detail and examples where helpful.",
    }.get(style, "Use a documentation-like tone: clear, actionable, B2B/SOHO, English.")

    instructions = f"""You are a documentation writer. Your task is to replace ONLY bracket placeholders [instruction or hint] in the given markdown article skeleton with real prose. Return the full markdown body (no frontmatter). Do not change any {{{{MUSTACHE}}}} placeholders (e.g. {{{{TOOLS_MENTIONED}}}}, {{{{CTA_BLOCK}}}}, {{{{AFFILIATE_DISCLOSURE}}}}, {{{{INTERNAL_LINKS}}}}, {{{{PRIMARY_TOOL}}}}). Leave them exactly as-is.
CRITICAL — No [bracket] tokens in output: Your response must not contain any text of the form [Anything] (e.g. [Name], [Date], [Customer Name], [Your Company], [Product]). Replace every such placeholder with a concrete example value. If you leave or introduce any [bracket] token, the QA check will reject the article. If you need to indicate a variable or example slot, use round parentheses ( ) instead, e.g. (video title) or (your product name).

Heading freeze: Do not add, remove, rename, or reformat any headings (#, ##, ###, ####). Do not introduce new headings of any level. Only replace bracket placeholders with plain text or lists under existing headings. Exception: if the instructions below require a "Try it yourself: Build your own AI prompt" subsection and the skeleton does not already contain it, you MUST add it as an H3 inside the Step-by-step workflow section.

Do not use the word "pricing" anywhere in the output (including in headings and phrases like "check pricing"). Do not use "the best" or "#1" anywhere, including in headings. If you need to refer to cost, use neutral wording like "cost" or "plan" without numbers or specific claims; avoid cost talk if possible.

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

IMPORTANT: In the "Template 1" and "Template 2" sections, you MUST generate concrete, realistic examples relevant to the article topic. Never leave or introduce any [bracket] token in the entire output. Forbidden examples: [Name], [Date], [Month], [Customer Name], [Your Company], [Product], [Insert title], [Key Point 1], [user's email], [Personalized ...], or any [Anything]. Replace every such placeholder with a concrete value (real example names, dates, product names, email examples). The QA check will reject the article if any [bracket] text remains. If you must show a slot, use round parentheses ( ) e.g. (video title), not square brackets. The templates should be immediately usable by the reader as examples.

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

{_try_it_yourself_instruction(content_type, audience_type, html=False)}

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

D) Do not use the word "pricing". Do not use "the best" or "#1". Do not use "unlimited", "limit to", "limited to", or "up to [number]" (e.g. "up to 5"). Do not use $ or any currency amount (e.g. $99, $10/mo). Do not use these phrases anywhere in the article, including in headings; the QA check will reject the article. Use neutral wording (e.g. "many", "as needed", "several", "cost") instead.

E) If you cannot comply with the OUTPUT CONTRACT, regenerate until you can. Do not omit the markers.

Output must feel like an internal playbook: decisions + steps + templates."""
    audience_line = _audience_instruction(audience_type)
    if audience_line:
        instructions += "\n\nAudience (MUST follow): " + audience_line
    instructions += "\n\nLength (MUST follow): " + _audience_length_guidance(audience_type)

    user = f"Article title: {title}\n"
    if keyword:
        user += f"Primary keyword: {keyword}\n"
    if category:
        user += f"Category: {category}\n"
    if content_type:
        user += f"Content type: {content_type}\n"
    if audience_type:
        user += f"Target audience level: {audience_type}\n"
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
    remap: bool = False,
    generate_prompt2: bool = True,
    min_words_override: int | None = None,
) -> str:
    """Process one file. Returns: 'wrote' | 'would_fill' | 'blocked' | 'qa_fail' | 'quality_fail' | 'api_fail' | 'skip'."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  Skip {path.name}: read error — {e}")
        return "skip"
    meta, order, body, body_start = _parse_frontmatter(content)
    if remap:
        meta["tools"] = ""
    if not use_html and not body.strip():
        print(f"  Skip {path.name}: empty body")
        return "skip"
    if use_html:
        all_tools = _load_affiliate_tools()
        affiliate_tools, other_tools = _split_tools_by_affiliate(all_tools)
        base_instructions, user_message = _build_html_prompt(meta, affiliate_tools, other_tools)
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
            new_body, remaining_notes = replace_remaining_bracket_placeholders_with_quoted(new_body)
            if remaining_notes:
                print(f"  Replaced remaining placeholders: {path.name} — {'; '.join(remaining_notes)}")
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
            _append_refresh_failure_reason(path.stem, last_reasons)
            if write and block_on_fail:
                # Preserve original frontmatter (including last_updated) so refresh can retry by date range
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
        new_body, remaining_notes = replace_remaining_bracket_placeholders_with_quoted(new_body)
        if remaining_notes:
            print(f"  Replaced remaining placeholders: {path.name} — {'; '.join(remaining_notes)}")

    # --- Restore static editorial sections stripped by AI ---
    if not use_html:
        _SECTIONS_TO_RESTORE = ["## Verification policy (editors only)"]
        for heading in _SECTIONS_TO_RESTORE:
            if heading in body and heading not in new_body:
                # Extract section text from original body (up to next ## or end)
                start = body.find(heading)
                rest = body[start:]
                next_section = re.search(r"\n##\s", rest[len(heading):])
                section_text = rest[: next_section.start() + len(heading)] if next_section else rest
                section_text = section_text.rstrip()
                # Insert before first ## heading in new_body
                first_h2 = re.search(r"(^|\n)##\s", new_body)
                if first_h2:
                    ins = first_h2.start() + (1 if new_body[first_h2.start()] == "\n" else 0)
                    new_body = new_body[:ins] + section_text + "\n\n---\n\n" + new_body[ins:]
                else:
                    new_body = section_text + "\n\n---\n\n" + new_body
                print(f"  Restored static section: {heading}")

    # --- Tool selection post-processing ---
    valid_names = {t[0].strip() for t in _load_affiliate_tools() if (t[0] or "").strip()}
    new_body, selected_tools = _extract_tools_selected(new_body, valid_names)
    if selected_tools:
        meta["tools"] = ", ".join(selected_tools)
        print(f"  Tools selected by AI: {', '.join(selected_tools)}")
    else:
        if not _has_assigned_tools(meta):
            print(f"  Warning: AI did not return TOOLS_SELECTED for {path.name}")

    tools_raw = (meta.get("tools") or "").strip()
    tool_list = [n.strip() for n in tools_raw.split(",") if n.strip()] if tools_raw else []

    if not use_html:
        name_to_url = _build_name_to_url_map()
        if tool_list:
            pt = tool_list[0]
            st = tool_list[1] if len(tool_list) > 1 else pt
            tools_md = _build_tools_mentioned_md(tool_list, name_to_url)
            new_body = new_body.replace("{{PRIMARY_TOOL}}", pt)
            new_body = new_body.replace("{{SECONDARY_TOOL}}", st)
            new_body = new_body.replace("{{TOOLS_MENTIONED}}", tools_md)
    else:
        if tool_list:
            toolinfo = _build_name_to_toolinfo_map()
            tools_html = _build_tools_mentioned_html(tool_list, toolinfo)
            if tools_html:
                new_body = _upsert_tools_section_html(new_body, tools_html)

    # --- Generate real Prompt #2 via separate API call ---
    if generate_prompt2 and _has_prompt2_placeholder(new_body):
        prompt1_text = _extract_prompt1(new_body, is_html=use_html)
        fallback_html = '<em>Prompt #2 could not be generated automatically &mdash; please run Prompt&nbsp;#1 above to get your result.</em>'
        fallback_md = "*(Prompt #2 could not be generated automatically — please run Prompt #1 above to get your result.)*"
        if prompt1_text:
            print(f"  Generating real Prompt #2 for {path.name} …")
            p2 = _generate_real_prompt2(
                prompt1_text, model=model, base_url=base_url, api_key=api_key
            )
            if p2:
                new_body = _insert_prompt2(new_body, p2, is_html=use_html)
                print(f"  Prompt #2 inserted ({len(p2)} chars)")
            else:
                new_body = _insert_prompt2(new_body, fallback_html if use_html else fallback_md, is_html=use_html)
                print(f"  Prompt #2 generation failed — fallback text inserted")
        else:
            new_body = _insert_prompt2(new_body, fallback_html if use_html else fallback_md, is_html=use_html)
            print(f"  Prompt #1 not found for Prompt #2 extraction — fallback text inserted")

    # --- Deterministic descriptors in Try-it-yourself for HTML ---
    if use_html:
        tools_raw2 = (meta.get("tools") or "").strip()
        tool_list2 = [n.strip() for n in tools_raw2.split(",") if n.strip()] if tools_raw2 else []
        try_tool = tool_list2[0] if tool_list2 else _first_reference_tool_name()
        new_body = _normalize_try_it_yourself_html(new_body, slug=path.stem, tool_name=try_tool)

    # --- R1: Final sanitization before QA (including headings) so forbidden phrases don't fail QA ---
    new_body, _ = sanitize_filled_body(new_body, skip_headings=False)

    new_content = _serialize_frontmatter(meta, order) + "\n" + new_body

    if qa_enabled:
        ok, reasons = run_preflight_qa(
            content, new_content, body, new_body,
            strict=qa_strict, is_html=use_html,
            audience_type=(meta.get("audience_type") or "").strip() or None,
            min_words_override=min_words_override,
            content_type=(meta.get("content_type") or "").strip() or None,
        )
        if not ok:
            print(f"  QA FAIL: {path.name} — {'; '.join(reasons)}")
            _append_refresh_failure_reason(path.stem, reasons)
            if write and block_on_fail:
                # Preserve original frontmatter (including last_updated) so refresh_articles can retry by date range
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
        # Update .md frontmatter only: set status to "filled" (body unchanged)
        md_content = _serialize_frontmatter(meta, order, "filled") + "\n" + body
        try:
            path.write_text(md_content, encoding="utf-8")
        except OSError:
            pass  # .html already written; .md status update is best-effort
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


def fill_prompt2_one(
    path: Path,
    *,
    model: str,
    base_url: str,
    api_key: str,
    dry_run: bool,
) -> str:
    """Fill [PROMPT2_PLACEHOLDER] in an already-generated .html (and matching .md).

    Returns: 'wrote' | 'would_fill' | 'skip' | 'api_fail' | 'no_placeholder'
    """
    # Operate on the .html file (source of truth for filled content)
    html_path = path.with_suffix(".html")
    if not html_path.exists():
        print(f"  Skip {path.name}: no .html found")
        return "skip"
    try:
        html_content = html_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  Skip {path.name}: read error — {e}")
        return "skip"

    if not _has_prompt2_placeholder(html_content):
        return "no_placeholder"

    prompt1_text = _extract_prompt1(html_content, is_html=True)
    if not prompt1_text:
        print(f"  Skip {path.name}: [PROMPT2_PLACEHOLDER] found but Prompt #1 not extractable")
        return "skip"

    if dry_run:
        print(f"  Would fill Prompt #2: {path.name}")
        return "would_fill"

    print(f"  Generating Prompt #2 for {path.name} …")
    p2 = _generate_real_prompt2(prompt1_text, model=model, base_url=base_url, api_key=api_key)
    fallback = '<em>Prompt #2 could not be generated automatically &mdash; please run Prompt&nbsp;#1 above to get your result.</em>'
    if not p2:
        print(f"  Prompt #2 API call failed — fallback inserted")
        p2_for_insert = fallback
    else:
        p2_for_insert = p2

    new_html = _insert_prompt2(html_content, p2_for_insert, is_html=True)

    # Backup and write .html
    backup = html_path.with_suffix(".html.bak")
    try:
        backup.write_text(html_content, encoding="utf-8")
    except OSError as e:
        print(f"  Skip {path.name}: backup failed — {e}")
        return "skip"
    try:
        html_path.write_text(new_html, encoding="utf-8")
    except OSError as e:
        print(f"  Skip {path.name}: write failed — {e}")
        return "skip"

    if p2:
        print(f"  Prompt #2 filled: {html_path.name} ({len(p2)} chars)")
    return "wrote" if p2 else "api_fail"


def main() -> None:
    # Ensure stdout handles Unicode (e.g. emoji in API response) on Windows
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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
        "--min-words-override",
        type=int,
        default=None,
        metavar="N",
        help="Use N as minimum word count for QA instead of audience-based threshold (e.g. for refresh).",
    )
    parser.add_argument(
        "--style",
        choices=["docs", "concise", "detailed"],
        default=None,
        help="Instruction style override. If omitted, auto-selected by audience_type (beginner=docs, intermediate=concise, professional=detailed).",
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
    parser.add_argument(
        "--remap",
        action="store_true",
        help="Force AI to re-select tools even if tools are already set in frontmatter.",
    )
    parser.add_argument(
        "--prompt2-only",
        action="store_true",
        dest="prompt2_only",
        help=(
            "Only fill [PROMPT2_PLACEHOLDER] in already-generated .html files. "
            "Does not regenerate article content. "
            "Reads existing .html, extracts Prompt #1, calls API, inserts real Prompt #2."
        ),
    )
    parser.add_argument(
        "--skip-prompt2",
        action="store_true",
        dest="skip_prompt2",
        help="Skip Prompt #2 generation during the main fill pass (useful for two-step workflow).",
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

    # --- --prompt2-only mode: fill placeholders in existing .html, no article regeneration ---
    if args.prompt2_only:
        candidates_p2: list[Path] = []
        for path in sorted(ARTICLES_DIR.glob("*.md")):
            stem = path.stem
            if args.since and len(stem) >= 10 and stem[:10] < args.since:
                continue
            if args.slug_contains and args.slug_contains not in stem:
                continue
            html_path = path.with_suffix(".html")
            if not html_path.exists():
                continue
            try:
                html_content = html_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if _has_prompt2_placeholder(html_content):
                candidates_p2.append(path)
        if args.limit > 0:
            candidates_p2 = candidates_p2[: args.limit]
        if not candidates_p2:
            print("No articles with [PROMPT2_PLACEHOLDER] found.")
            return
        print(f"Prompt-2-only mode: {len(candidates_p2)} article(s) with placeholder.\n")
        wrote = would_fill = api_failed = skipped = 0
        for path in candidates_p2:
            result = fill_prompt2_one(
                path, model=args.model, base_url=base_url, api_key=api_key, dry_run=dry_run
            )
            if result == "wrote":
                wrote += 1
            elif result == "would_fill":
                would_fill += 1
            elif result == "api_fail":
                api_failed += 1
            elif result == "skip":
                skipped += 1
        print(f"\nSummary (--prompt2-only):")
        print(f"  filled:     {wrote}")
        print(f"  would fill: {would_fill} (dry-run)")
        print(f"  API failed: {api_failed}")
        print(f"  skipped:    {skipped}")
        if api_failed > 0 and wrote == 0:
            sys.exit(2)
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
        if args.style:
            effective_style = args.style
        else:
            try:
                _tmp = path.read_text(encoding="utf-8")
                _m, _, _, _ = _parse_frontmatter(_tmp)
                at = (_m.get("audience_type") or "").strip().lower()
            except OSError:
                at = ""
            effective_style = STYLE_FOR_AUDIENCE.get(at, STYLE_DEFAULT)
        result = fill_one(
            path,
            model=args.model,
            base_url=base_url,
            api_key=api_key,
            dry_run=dry_run,
            write=args.write,
            qa_enabled=qa_enabled,
            qa_strict=args.qa_strict,
            style=effective_style,
            block_on_fail=args.block_on_fail,
            quality_gate=args.quality_gate,
            quality_retries=args.quality_retries,
            quality_strict=args.quality_strict,
            use_html=args.html,
            remap=args.remap,
            generate_prompt2=not args.skip_prompt2,
            min_words_override=args.min_words_override,
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

    total_failures = qa_failed + quality_failed + api_failed
    if total_failures > 0 and wrote == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
