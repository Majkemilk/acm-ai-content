#!/usr/bin/env python3
"""
Populate content/use_cases.yaml with business problems/use cases for content generation.
Uses existing articles (keywords/topics) and OpenAI API to suggest new, non-duplicative use cases.
Stdlib only + OpenAI Responses API (urllib). No PyYAML; simple line-based YAML read/write.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Allow importing from same package (scripts/)
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from content_index import load_config  # noqa: E402

PROJECT_ROOT = _SCRIPTS_DIR.parent
CONTENT_DIR = PROJECT_ROOT / "content"
CONFIG_PATH = CONTENT_DIR / "config.yaml"
USE_CASES_PATH = CONTENT_DIR / "use_cases.yaml"
ARTICLES_DIR = CONTENT_DIR / "articles"

ALLOWED_CONTENT_TYPES = ["how-to", "guide", "best", "comparison"]
TARGET_USE_CASE_COUNT = 12  # Exact number of use cases to keep; change here to affect both use_cases.yaml and queue size
USE_CASES_HEADER = """# List of business problems / use cases for content generation
# Each item should have:
# - problem: string (description of the problem, e.g., "turn podcasts into written content")
# - suggested_content_type: string (one of: how-to, guide, best, comparison)
# - category_slug: string (e.g., "ai-marketing-automation")
# - audience_type: optional; beginner | intermediate | professional (from batch position)
# - batch_id: optional; run id (e.g. 2026-02-20T143022)
# - status: optional; "todo" = add to queue, missing or "generated" = skip (backward compat)
"""

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "over", "under", "your", "you",
    "are", "was", "were", "how", "what", "when", "why", "who", "will", "can", "could", "should",
    "using", "use", "based", "across", "through", "into", "without", "about", "their", "them",
    "oraz", "or", "i", "w", "na", "do", "z", "dla", "bez", "przez", "jak", "czy", "to", "ten",
}

# Suffixes to strip for stem-like normalization (longest first). Min stem length 3.
_STEM_SUFFIXES = (
    "ibility", "ability", "ation", "tion", "ness", "ity", "able", "ible",
    "abil", "ibil", "ing", "ement", "ment", "ly", "ed", "es", "s",
)


def _stem_token(word: str) -> str:
    """Reduce word to a common stem by stripping typical suffixes iteratively (no external deps)."""
    w = (word or "").lower()
    if len(w) <= 3:
        return w
    while True:
        prev = w
        for suf in _STEM_SUFFIXES:
            if len(suf) < len(w) and w.endswith(suf):
                candidate = w[: -len(suf)]
                if len(candidate) >= 3:
                    w = candidate
                    break
        if w == prev:
            break
    return w


def _norm_tokens(text: str) -> set[str]:
    """Tokenize text and return set of stemmed tokens (stopwords and len<=2 excluded)."""
    raw = {t.lower() for t in _TOKEN_RE.findall((text or "").lower())}
    return {_stem_token(t) for t in raw if len(t) > 2 and t not in _STOPWORDS}


def _is_locked_to_problem(problem: str, anchor_problem: str) -> bool:
    """Semantic-ish lock check: overlap against anchor problem must be strong."""
    p = (problem or "").strip().lower()
    a = (anchor_problem or "").strip().lower()
    if not p or not a:
        return False
    if a in p:
        return True
    p_tokens = _norm_tokens(p)
    a_tokens = _norm_tokens(a)
    if not p_tokens or not a_tokens:
        return False
    overlap = len(p_tokens & a_tokens)
    ratio_to_anchor = overlap / max(1, len(a_tokens))
    ratio_to_problem = overlap / max(1, len(p_tokens))
    return ratio_to_anchor >= 0.35 or (ratio_to_anchor >= 0.25 and ratio_to_problem >= 0.25)


def _strip_comments(text: str) -> str:
    """Remove lines that are entirely comments."""
    lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    return "\n".join(lines)


def _parse_quoted_value(val: str) -> str:
    """Unquote a YAML value if quoted."""
    val = (val or "").strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1].replace('\\"', '"')
    return val


def load_yaml_list(path: Path, list_key: str) -> list[dict]:
    """
    Load a YAML file with a single top-level key whose value is a list of objects.
    Same line-based approach as generate_queue.py; no external YAML lib.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    text = _strip_comments(text)
    key_pattern = re.compile(rf"^{re.escape(list_key)}\s*:\s*$", re.MULTILINE)
    m = key_pattern.search(text)
    if not m:
        return []
    start = m.end()
    rest = text[start:]
    next_top = re.search(r"^\w+\s*:\s*", rest, re.MULTILINE)
    block = rest[: next_top.start()] if next_top else rest
    block = block.strip()
    if not block:
        return []
    items = []
    current: dict[str, str] = {}
    for line in block.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                items.append(current)
                current = {}
            continue
        if stripped == "-" or re.match(r"^-\s+", stripped):
            if current:
                items.append(current)
            current = {}
            inline = re.match(r"^-\s+(.+)$", stripped)
            if inline:
                part = inline.group(1).strip()
                kv = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(.*)$", part)
                if kv:
                    current[kv.group(1)] = _parse_quoted_value(kv.group(2))
            continue
        kv = re.match(r"^([a-zA-Z0-9_]+)\s*:\s*(.*)$", stripped)
        if kv:
            current[kv.group(1)] = _parse_quoted_value(kv.group(2))
    if current:
        items.append(current)
    return items


def load_use_cases(path: Path) -> list[dict]:
    """Load use cases from use_cases.yaml. Returns [] if file missing or empty."""
    return load_yaml_list(path, "use_cases")


def save_use_cases(path: Path, items: list[dict]) -> None:
    """Write use_cases.yaml with header comments and list of use cases (same format as template)."""
    def q(v: str) -> str:
        v = str(v)
        if "\n" in v or ":" in v or v.startswith("#") or '"' in v:
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return v
    lines = [USE_CASES_HEADER.strip(), "use_cases:"]
    if items:
        for item in items:
            problem = (item.get("problem") or "").strip()
            content_type = (item.get("suggested_content_type") or "").strip()
            category = (item.get("category_slug") or "").strip()
            lines.append(f"  - problem: {q(problem)}")
            lines.append(f"    suggested_content_type: {q(content_type)}")
            lines.append(f"    category_slug: {q(category)}")
            if item.get("audience_type"):
                lines.append(f"    audience_type: {q(str(item.get('audience_type', '')).strip())}")
            if item.get("batch_id"):
                lines.append(f"    batch_id: {q(str(item.get('batch_id', '')).strip())}")
            if "status" in item and str(item.get("status", "")).strip():
                lines.append(f"    status: {q(str(item.get('status', '')).strip())}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_categories_from_config(config_path: Path) -> list[str]:
    """Return list of categories (production_category + sandbox_categories) from config.yaml."""
    config = load_config(config_path)
    prod = (config.get("production_category") or "").strip()
    sandbox = config.get("sandbox_categories") or []
    cats = [prod] if prod else []
    for s in sandbox:
        if isinstance(s, str) and s.strip() and s.strip() not in cats:
            cats.append(s.strip())
    return cats or ["ai-marketing-automation"]


def parse_article_frontmatter(path: Path) -> dict | None:
    """Parse frontmatter from a markdown file. Returns dict with title, primary_keyword, category, etc."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    block = content[3:end].strip()
    data: dict[str, str] = {"slug": path.stem}
    for line in block.split("\n"):
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1].replace('\\"', '"')
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        data[key] = raw
    return data


def collect_article_keywords(articles_dir: Path) -> list[dict]:
    """Extract title, primary_keyword, category from all .md files in articles_dir."""
    if not articles_dir.exists():
        return []
    out = []
    for path in sorted(articles_dir.glob("*.md")):
        meta = parse_article_frontmatter(path)
        if not meta:
            continue
        title = (meta.get("title") or "").strip()
        keyword = (meta.get("primary_keyword") or "").strip()
        category = (meta.get("category") or meta.get("category_slug") or "").strip()
        if title or keyword:
            out.append({"title": title, "primary_keyword": keyword, "category": category})
    return out


def call_responses_api(
    instructions: str,
    user_message: str,
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> str:
    """POST to {base_url}/v1/responses. Return response text or raise. Same as fill_articles.call_responses_api."""
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


def build_prompt(
    existing_use_cases: list[dict],
    article_keywords: list[dict],
    categories: list[str],
    count: int,
    content_type_filter: str | None = None,
    suggested_problems: list[str] | None = None,
    hard_lock_problem: str | None = None,
    quality_feedback: list[str] | None = None,
) -> tuple[str, str]:
    """Build (instructions, user_message) for the model. count = how many use cases to ask for.
    If content_type_filter is set, prompt restricts suggested_content_type to that value.
    suggested_problems (from config): optional list of problems to prefer turning into use cases."""
    instructions = """You are a content strategist. Your task is to suggest new business problems / use cases for blog content in the AI marketing automation space.

Output ONLY a valid JSON array of objects. Each object must have exactly these keys:
- "problem": string, concise description of the business problem (e.g., "turn podcasts into written content")
- "suggested_content_type": string, one of: how-to, guide, best, comparison
- "category_slug": string, one of the allowed categories provided in the user message

Do not output any markdown, explanation, or text outside the JSON array. The response must be parseable as JSON."""
    if hard_lock_problem:
        instructions += (
            "\n\nHARD LOCK (MUST FOLLOW): Every generated use case must stay on the same base problem domain provided by the user. "
            "Do not drift to adjacent/general topics."
        )

    # Existing use cases (problems) to avoid duplicating
    existing_problems = [
        (uc.get("problem") or "").strip()
        for uc in existing_use_cases
        if (uc.get("problem") or "").strip()
    ]
    # Existing topics from articles (for inspiration; suggest new angles, don't repeat)
    keywords_list = [
        (a.get("primary_keyword") or a.get("title") or "").strip()
        for a in article_keywords
        if (a.get("primary_keyword") or a.get("title") or "").strip()
    ]

    suggested_list = list(suggested_problems or [])
    user = f"""Allowed category_slug values (use exactly one per use case): {json.dumps(categories)}

Existing use cases already in our list (do NOT suggest these or very similar ones):
{json.dumps(existing_problems)}

Existing article keywords/topics we already cover (suggest complementary or new angles, not duplicates):
{json.dumps(keywords_list[:50])}
"""
    if suggested_list:
        user += f"""Optionally consider these problems (if not already covered); prefer turning them into use cases: {json.dumps(suggested_list)}

"""
    if hard_lock_problem:
        user += f"""BASE PROBLEM LOCK (mandatory): {json.dumps(hard_lock_problem)}
All generated use cases must be direct variants of this base problem.
For exactly 3 use cases, enforce distinct angles:
- Use case #1: implementation / setup angle
- Use case #2: monitoring / troubleshooting / optimization angle
- Use case #3: scaling / governance / reliability angle
"""
    if quality_feedback:
        user += "QUALITY FEEDBACK (previous attempt failed; fix all):\n"
        for reason in quality_feedback:
            user += f"- {reason}\n"
        user += "\n"
    user += f"""Generate exactly {count} new, specific, actionable business problems that people actively search for solutions to in AI marketing automation. Each must be different from the existing use cases and topics above.

Structure by audience (follow this order strictly):
- First 3: for beginners (simple, entry-level).
- Next 3: for intermediate or mixed (can build on or complement the first three).
- Remaining: for professional users only (advanced, scaling, integration)."""
    if content_type_filter:
        user += f" For every use case, set suggested_content_type to exactly: {json.dumps(content_type_filter)}."
    else:
        user += " Prefer problems that fit how-to or guide content."
    user += " Return only the JSON array."

    return instructions, user


def audience_type_for_position(position_1based: int, pyramid: list[int]) -> str:
    """Return beginner | intermediate | professional from 1-based position and pyramid [n1, n2]."""
    n1 = pyramid[0] if pyramid else 3
    n2 = pyramid[1] if len(pyramid) > 1 else 3
    if position_1based <= n1:
        return "beginner"
    if position_1based <= n1 + n2:
        return "intermediate"
    return "professional"


def parse_ai_use_cases(raw: str, allowed_types: list[str], allowed_categories: list[str]) -> list[dict]:
    """
    Parse AI response into list of use case dicts. Validates suggested_content_type and category_slug.
    Returns only valid items; skips invalid or malformed entries.
    """
    # Try to extract JSON array (in case model wrapped in markdown)
    text = raw.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    allowed_types_set = set(allowed_types)
    allowed_cats_set = set(allowed_categories)
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        problem = (item.get("problem") or "").strip()
        if not problem:
            continue
        content_type = (item.get("suggested_content_type") or "").strip().lower()
        if content_type not in allowed_types_set:
            content_type = "guide"
        category = (item.get("category_slug") or "").strip()
        if category not in allowed_cats_set:
            category = allowed_categories[0] if allowed_categories else "ai-marketing-automation"
        out.append({
            "problem": problem,
            "suggested_content_type": content_type,
            "category_slug": category,
            "status": "todo",  # so generate_queue.py adds them to the queue
        })
    return out


def is_duplicate(problem: str, existing: list[dict]) -> bool:
    """True if problem already exists (case-insensitive) or is too similar (substring match)."""
    p = (problem or "").strip().lower()
    if not p:
        return True
    for uc in existing:
        existing_p = (uc.get("problem") or "").strip().lower()
        if existing_p == p:
            return True
        # Simple similarity: one contains the other (avoid "turn X into Y" vs "turn X into Y with Z")
        if len(p) > 10 and len(existing_p) > 10:
            if p in existing_p or existing_p in p:
                return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate new use cases and append to content/use_cases.yaml")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Number of use cases to generate and cap total list at (default: from config use_case_batch_size, else 9)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        metavar="SLUG",
        help="Restrict generated use cases to this category_slug only (must be in config production_category or sandbox_categories).",
    )
    parser.add_argument(
        "--content-type",
        type=str,
        action="append",
        default=None,
        metavar="TYPE",
        choices=ALLOWED_CONTENT_TYPES,
        help="Restrict suggested_content_type to one or more (repeat for multiple: how-to, guide, best, comparison).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)
    base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

    # Load config for categories, batch size, pyramid; optionally restrict to --category
    config_path = CONFIG_PATH
    config = load_config(config_path)
    batch_size = int(config.get("use_case_batch_size", 9))
    pyramid = list(config.get("use_case_audience_pyramid") or [3, 3])
    if not pyramid:
        pyramid = [3, 3]
    pyramid = [int(x) for x in pyramid]
    limit = args.limit if args.limit is not None else batch_size
    limit = max(1, min(100, limit))
    all_categories = get_categories_from_config(config_path)
    if args.category:
        if args.category.strip() not in all_categories:
            print(f"Error: --category {args.category!r} is not in allowed categories: {all_categories}")
            sys.exit(1)
        categories = [args.category.strip()]
    else:
        categories = all_categories
    if args.content_type:
        allowed_types = [t.strip().lower() for t in args.content_type if t and t.strip() in ALLOWED_CONTENT_TYPES]
        if not allowed_types:
            allowed_types = ALLOWED_CONTENT_TYPES
    else:
        allowed_types = ALLOWED_CONTENT_TYPES

    # Load existing use cases (create file with empty list if missing)
    existing = load_use_cases(USE_CASES_PATH)
    if not USE_CASES_PATH.exists():
        save_use_cases(USE_CASES_PATH, [])

    # Collect keywords from existing articles
    article_keywords = collect_article_keywords(ARTICLES_DIR)

    # Build prompt and call API (ask for exactly limit use cases)
    suggested_problems = list(config.get("suggested_problems") or [])
    content_type_filter = (args.content_type[0].strip().lower() if args.content_type else None)
    raw_first = (suggested_problems[0].strip() if suggested_problems and suggested_problems[0].strip() else None)
    # Use only first line or first 200 chars as anchor so a pasted paragraph doesn't flood logs or break lock
    if raw_first and len(raw_first) > 200:
        first_line = raw_first.split("\n")[0].strip()
        hard_lock_problem = first_line[:200].strip() if len(first_line) > 200 else first_line
        print("Note: suggested_problems[0] is long; using first line (max 200 chars) as hard lock. Prefer a short phrase in config.")
    else:
        hard_lock_problem = raw_first
    max_attempts = 3 if hard_lock_problem else 1
    candidates: list[dict] = []
    last_issues: list[str] = []

    for attempt in range(1, max_attempts + 1):
        instructions, user_message = build_prompt(
            existing,
            article_keywords,
            categories,
            limit,
            content_type_filter=content_type_filter,
            suggested_problems=suggested_problems,
            hard_lock_problem=hard_lock_problem,
            quality_feedback=last_issues if attempt > 1 else None,
        )
        try:
            response_text = call_responses_api(
                instructions,
                user_message,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )
        except RuntimeError as e:
            print(f"API error: {e}")
            sys.exit(1)

        # Parse JSON and validate (use restricted types/categories when --content-type/--category were set)
        candidates = parse_ai_use_cases(response_text, allowed_types, categories)
        if not candidates:
            last_issues = ["API returned empty or invalid JSON array of use cases."]
            if attempt < max_attempts:
                print(f"Attempt {attempt}/{max_attempts} failed: invalid or empty JSON. Retrying...")
                continue
            print("No valid use cases in API response (invalid or empty JSON).")
            sys.exit(2)

        # Tag each candidate with original position (for audience assignment after optional reorder)
        for i, uc in enumerate(candidates):
            uc["_orig_i"] = i

        # Cap candidates to requested limit BEFORE lock checks/audience assignment
        n_returned = len(candidates)
        if n_returned > limit:
            if hard_lock_problem:
                locked = [c for c in candidates if _is_locked_to_problem(c.get("problem", ""), hard_lock_problem)]
                rest = [c for c in candidates if c not in locked]
                candidates = (locked + rest)[:limit]
                print(f"  AI returned {n_returned} candidates, preferring {len(locked)} locked to problem; capped to {limit}.")
            else:
                candidates = candidates[:limit]
                print(f"  AI returned {n_returned} candidates, capping to {limit}.")

        if hard_lock_problem:
            mismatched = [
                uc.get("problem", "")
                for uc in candidates
                if not _is_locked_to_problem(uc.get("problem", ""), hard_lock_problem)
            ]
            if mismatched:
                last_issues = [
                    f"Hard lock mismatch against base problem: {hard_lock_problem}",
                    *[f"Mismatched candidate: {m}" for m in mismatched[:5]],
                ]
                if attempt < max_attempts:
                    print(f"Attempt {attempt}/{max_attempts} failed: {len(mismatched)} use case(s) drifted from hard-locked problem. Retrying...")
                    continue
                print("Fail-fast: generated use cases do not stay on the hard-locked suggested problem.")
                for m in mismatched[:5]:
                    print(f"  - Drifted: {m}")
                sys.exit(2)

        # Success path
        break

    # Assign audience_type by original position in API response (preserves beginner/intermediate/professional order after locked-first capping)
    batch_id = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    for i, uc in enumerate(candidates):
        orig_1based = uc.get("_orig_i", i) + 1
        uc["audience_type"] = audience_type_for_position(orig_1based, pyramid)
        uc["batch_id"] = batch_id
        uc.pop("_orig_i", None)

    # Deduplicate against existing
    new_use_cases = [
        uc for uc in candidates
        if not is_duplicate(uc.get("problem") or "", existing)
    ]

    # Option C: fail-fast when nothing new would be saved (exit 2 so pipeline can stop)
    if not new_use_cases:
        print("All generated use cases were duplicates or too similar to existing ones. Nothing added.")
        sys.exit(2)
    if hard_lock_problem and len(new_use_cases) < limit:
        print(
            f"Fail-fast: only {len(new_use_cases)} non-duplicate use case(s) remained, below requested {limit} under hard lock."
        )
        print(f"Base locked problem: {hard_lock_problem}")
        sys.exit(2)

    # Option A: replace mode when hard lock — save only the new batch (overwrite). Otherwise append and cap.
    if hard_lock_problem:
        combined = new_use_cases[:limit]
        save_use_cases(USE_CASES_PATH, combined)
        kept = len(combined)
        msg = f"Saved {kept} use case(s) to {USE_CASES_PATH} (replace mode). Total in file: {len(combined)} (limit: {limit})."
    else:
        combined = (existing + new_use_cases)[:limit]
        save_use_cases(USE_CASES_PATH, combined)
        kept = len(combined) - len(existing)
        kept = max(0, kept)
        dropped = len(new_use_cases) - kept
        msg = f"Saved {kept} new use case(s) to {USE_CASES_PATH}. Total in file: {len(combined)} (limit: {limit})."
        if dropped > 0:
            msg += f" Dropped {dropped} (exceeded limit)."
        print(msg)
        for uc in new_use_cases[:kept]:
            print(f"  - {uc.get('problem')} ({uc.get('suggested_content_type')}, {uc.get('category_slug')}, {uc.get('audience_type')})")
        if not hard_lock_problem:
            return  # avoid double-print below
    print(msg)
    for uc in combined:
        print(f"  - {uc.get('problem')} ({uc.get('suggested_content_type')}, {uc.get('category_slug')}, {uc.get('audience_type')})")


if __name__ == "__main__":
    main()
