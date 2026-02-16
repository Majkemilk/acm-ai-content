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
        out_lines.append(line)
    if pricing_count:
        notes.append(f"replaced pricing->cost ({pricing_count}x)")
    if best_count:
        notes.append(f"replaced 'the best'->'a strong option' ({best_count}x)")
    if guarantee_count:
        notes.append(f"replaced guarantee(d)->assure(d) ({guarantee_count}x)")
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
) -> tuple[bool, list[str]]:
    """Validate filled output. Returns (ok, list of failure reasons)."""
    reasons: list[str] = []

    # A. Mustache preservation
    orig_tokens = set(MUSTACHE_REGEX.findall(original_full_text))
    filled_tokens = set(MUSTACHE_REGEX.findall(filled_full_text))
    missing = orig_tokens - filled_tokens
    added = filled_tokens - orig_tokens
    if missing:
        reasons.append(f"mustache removed: {sorted(missing)}")
    if added:
        reasons.append(f"mustache introduced: {sorted(added)}")

    # B. Bracket placeholders removed (ignore markdown checkboxes [ ], [x], [X], [-]; ignore content in Template 1/2 sections)
    body_without_templates = filled_body
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

    # C. H1 and H2 structure unchanged (H3/H4 may vary)
    orig_h1 = _h1_lines(original_body)
    filled_h1 = _h1_lines(filled_body)
    orig_h2 = _h2_lines(original_body)
    filled_h2 = _h2_lines(filled_body)
    if orig_h1 != filled_h1:
        reasons.append(f"H1 headings changed: expected {orig_h1!r}, got {filled_h1!r}")
    # Sprawdź, czy wszystkie oryginalne H2 są zachowane (dodatkowe są dozwolone)
    missing_h2 = set(orig_h2) - set(filled_h2)
    if missing_h2:
        reasons.append(f"H2 headings missing: {', '.join(missing_h2)}")

    # D. Word count
    word_count = len(filled_body.split())
    threshold = 1000 if strict else 700
    if word_count < threshold:
        reasons.append(f"word count {word_count} < {threshold}")

    # E. Forbidden patterns
    for pat, label in FORBIDDEN_PATTERNS:
        if pat.search(filled_body):
            reasons.append(f"forbidden pattern: {label}")

    return (len(reasons) == 0, reasons)


def should_process(meta: dict, body: str, force: bool) -> bool:
    """True if file is draft (or no status) and has bracket placeholders; or force."""
    if force:
        return has_bracket_placeholders(body)
    status = (meta.get("status") or "").strip().lower()
    if status == "filled" or status == "blocked":
        return False
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
    W zależności od content_type wymagania są różne.
    Zwraca listę stringów z opisami błędów (pusta = OK).
    """
    missing = []
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

IMPORTANT: In the "Template 1" and "Template 2" sections, you MUST generate concrete, realistic examples relevant to the article topic. Do NOT use placeholder text in square brackets like [Insert title] or [Key Point 1]. Instead, fill them with actual example content (e.g., a specific title, real bullet points, actionable steps). The templates should be immediately usable by the reader as examples.

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

D) Do not use the word "pricing". Do not use "the best" or "#1".

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
) -> str:
    """Process one file. Returns: 'wrote' | 'would_fill' | 'blocked' | 'qa_fail' | 'quality_fail' | 'api_fail' | 'skip'."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  Skip {path.name}: read error — {e}")
        return "skip"
    meta, order, body, body_start = _parse_frontmatter(content)
    if not body.strip():
        print(f"  Skip {path.name}: empty body")
        return "skip"
    base_instructions, user_message = build_prompt(meta, body, style=style)
    new_body = ""
    quality_failed_after_retries = False
    if quality_gate:
        attempt = 0
        while True:
            current_instructions = base_instructions
            if attempt > 0:
                current_instructions = base_instructions + "\n\nQUALITY FEEDBACK:\nYour previous output FAILED the Output Contract for these reasons:\n" + "\n".join("- " + r for r in last_reasons) + "\n\nFix ALL issues. Keep headings unchanged. Return the full markdown body."
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
    new_content = _serialize_frontmatter(meta, order) + "\n" + new_body

    if qa_enabled:
        ok, reasons = run_preflight_qa(content, new_content, body, new_body, strict=qa_strict)
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
        if should_process(meta, body, args.force):
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
