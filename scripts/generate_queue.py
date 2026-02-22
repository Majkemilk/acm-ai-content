#!/usr/bin/env python3
"""
Generate content/queue.yaml from content/use_cases.yaml (and optionally affiliate_tools.yaml).
Creates one queue entry per use case. Number of entries = number of use cases in use_cases.yaml.
When use_case_tools_mapping.yaml has no entry for a problem, can call AI to suggest 1–2 tools per problem
(OPENAI_API_KEY required). Uses only Python standard library. Line-based YAML parsing (no external deps).
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = PROJECT_ROOT / "content"
AFFILIATE_TOOLS_PATH = CONTENT_DIR / "affiliate_tools.yaml"
USE_CASES_PATH = CONTENT_DIR / "use_cases.yaml"
QUEUE_PATH = CONTENT_DIR / "queue.yaml"
USE_CASE_TOOLS_MAPPING_PATH = CONTENT_DIR / "use_case_tools_mapping.yaml"

ALLOWED_CONTENT_TYPES = ["how-to", "guide", "best", "comparison", "review"]
DEFAULT_CONTENT_TYPE = "guide"

# Title action prefix by content_type: "{action} {problem} with {tool_name}"
CONTENT_TYPE_ACTION = {
    "how-to": "How to",
    "guide": "Guide to",
    "best": "Best",
    "comparison": "Comparison of",
}


def _strip_comments(text: str) -> str:
    """Remove lines that are entirely comments (optional # at start of line after strip)."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_quoted_value(val: str) -> str:
    """Unquote a YAML value if quoted."""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1].replace('\\"', '"')
    return val


def load_yaml_list(path: Path, list_key: str) -> list[dict]:
    """
    Load a YAML file with a single top-level key whose value is a list of objects.
    Simple line-based parser (no external libs). Supports:
    - use_cases: [ { problem: ..., suggested_content_type: ..., category_slug: ... }, ... ]
    - tools: [ { name: ..., category: ..., affiliate_link: ... }, ... ]
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


def load_tools(path: Path) -> list[dict]:
    """Load list of tools from affiliate_tools.yaml (key: tools)."""
    return load_yaml_list(path, "tools")


def load_use_cases(path: Path) -> list[dict]:
    """Load list of use cases from use_cases.yaml (key: use_cases)."""
    return load_yaml_list(path, "use_cases")


def load_use_case_tools_mapping(path: Path) -> dict[str, list[str]]:
    """
    Load problem -> tools from content/use_case_tools_mapping.yaml.
    Returns dict keyed by normalized problem (lowercase, strip); value = list of tool names (from affiliate_tools).
    """
    items = load_yaml_list(path, "mapping")
    out: dict[str, list[str]] = {}
    for item in items:
        problem = (item.get("problem") or "").strip()
        if not problem:
            continue
        tools_str = (item.get("tools") or "").strip()
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]
        key = problem.lower()
        out[key] = tools
    return out


def _call_responses_api(
    instructions: str,
    user_message: str,
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> str:
    """POST to {base_url}/v1/responses. Return response text or raise."""
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


def _build_mapping_prompt(problems: list[str], tools_for_prompt: list[dict]) -> tuple[str, str]:
    """Build (instructions, user_message) for AI to assign 1–2 tools per problem."""
    instructions = """You are a content strategist. Given a list of business problems (use cases for blog articles) and a list of AI/marketing tools, assign to each problem 1 or 2 tools that best fit solving that problem. Tool names must be chosen exactly from the provided list (no variations).

Output ONLY a valid JSON array. Each element must be an object with exactly two keys:
- "problem": string (the problem text exactly as given)
- "tools": array of 1 or 2 strings (tool names exactly as in the list; use at least one when possible)

Do not output markdown, explanation, or text outside the JSON array."""

    tools_desc = []
    for t in tools_for_prompt:
        name = (t.get("name") or "").strip()
        if not name:
            continue
        cat = (t.get("category") or "").strip()
        short = (t.get("short_description_en") or "").strip()
        if short:
            tools_desc.append(f"{name} ({short})")
        elif cat:
            tools_desc.append(f"{name} [{cat}]")
        else:
            tools_desc.append(name)

    user = f"""Tools (choose only from this list; names must match exactly):
{json.dumps(tools_desc)}

Problems to assign tools to (return each problem exactly as written):
{json.dumps(problems)}

Return a JSON array of objects: {{"problem": "<exact problem string>", "tools": ["ToolName1", "ToolName2"]}}. Use 1–2 tools per problem. If no tool fits well, use the best available match."""

    return instructions, user


def _parse_ai_mapping(response_text: str, valid_tool_names: set[str]) -> dict[str, list[str]]:
    """Parse API response to problem -> list of tool names. Keys = original problem strings. Validates tool names."""
    text = response_text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        arr = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    out: dict[str, list[str]] = {}
    for item in arr:
        if not isinstance(item, dict):
            continue
        problem = (item.get("problem") or "").strip()
        if not problem:
            continue
        raw = item.get("tools")
        if isinstance(raw, str):
            raw = [t.strip() for t in raw.replace(",", " ").split() if t.strip()]
        elif not isinstance(raw, list):
            continue
        chosen = []
        for t in raw:
            t = str(t).strip()
            if not t:
                continue
            if t in valid_tool_names:
                chosen.append(t)
            else:
                for v in valid_tool_names:
                    if v.lower() == t.lower():
                        chosen.append(v)
                        break
        if chosen:
            out[problem] = chosen[:2]
    return out


def _fetch_ai_tools_mapping(
    problems: list[str],
    tools_list: list[dict],
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> dict[str, list[str]]:
    """Call API to get problem -> [tool1, tool2]. Returns mapping with original problem strings as keys."""
    if not problems or not tools_list:
        return {}
    valid_names = {(t.get("name") or "").strip() for t in tools_list if (t.get("name") or "").strip()}
    if not valid_names:
        return {}
    instructions, user_message = _build_mapping_prompt(problems, tools_list)
    response_text = _call_responses_api(
        instructions, user_message, model=model, base_url=base_url, api_key=api_key
    )
    return _parse_ai_mapping(response_text, valid_names)


def _save_use_case_tools_mapping(path: Path, entries: list[dict], header_lines: list[str] | None = None) -> None:
    """Write use_case_tools_mapping.yaml. entries = list of {problem: str, tools: str} (tools comma-separated)."""
    def q(v: str) -> str:
        v = str(v)
        if "\n" in v or ":" in v or v.startswith("#") or '"' in v:
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return v
    default_header = [
        "# Editorial mapping: use case problem (exact match, normalized) -> preferred tools for the article.",
        "# Tool names must match content/affiliate_tools.yaml \"name\" exactly.",
        "# Used by generate_queue.py; AI can fill missing entries when OPENAI_API_KEY is set.",
        "# Example:",
        "#   - problem: \"automate video thumbnails creation for social media\"",
        "#     tools: \"Canva, Pictory\"",
    ]
    lines = header_lines or default_header
    lines = list(lines) + ["mapping:"]
    for e in entries:
        problem = (e.get("problem") or "").strip()
        tools_str = (e.get("tools") or "").strip() if isinstance(e.get("tools"), str) else ", ".join(str(x) for x in (e.get("tools") or []))
        if not problem:
            continue
        lines.append(f"  - problem: {q(problem)}")
        lines.append(f"    tools: {q(tools_str)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def title_for_entry(problem: str, content_type: str, tool_name: str) -> str:
    """Generate title as '{action} {problem} with {tool_name}'."""
    problem = (problem or "").strip()
    tool_name = (tool_name or "").strip()
    action = CONTENT_TYPE_ACTION.get(
        (content_type or "").strip().lower(),
        "Guide to",
    )
    if not problem:
        return f"{action} with {tool_name}" if tool_name else "Untitled"
    if not tool_name:
        return f"{action} {problem}"
    return f"{action} {problem} with {tool_name}"


def title_to_primary_keyword(title: str) -> str:
    """Derive primary_keyword from title (lowercase, simple)."""
    return (title or "").strip().lower() or "article"


def build_queue_items(
    use_cases: list[dict],
    today: str,
    tools_mapping: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Build queue items: one entry per use case. primary_tool/secondary_tool from tools_mapping when set."""
    mapping = tools_mapping or {}
    items = []
    for uc in use_cases:
        problem = (uc.get("problem") or "").strip()
        if not problem:
            continue
        content_type = (uc.get("suggested_content_type") or "").strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            content_type = DEFAULT_CONTENT_TYPE
        category_slug = (uc.get("category_slug") or "").strip() or "ai-marketing-automation"
        tools = mapping.get(problem.lower()) or []
        primary_tool = (tools[0] or "").strip() if tools else ""
        secondary_tool = (tools[1] or "").strip() if len(tools) > 1 else ""
        title = title_for_entry(problem, content_type, primary_tool)
        item = {
            "title": title,
            "primary_keyword": title_to_primary_keyword(title),
            "content_type": content_type,
            "category_slug": category_slug,
            "primary_tool": primary_tool,
            "secondary_tool": secondary_tool,
            "status": "todo",
            "last_updated": today,
        }
        if uc.get("audience_type"):
            item["audience_type"] = (uc.get("audience_type") or "").strip()
        if uc.get("batch_id"):
            item["batch_id"] = (uc.get("batch_id") or "").strip()
        items.append(item)
    return items


def load_existing_queue(path: Path) -> list[dict]:
    """Load existing queue using same format as generate_articles (list of mappings)."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [dict(item) for item in data]
        return []
    except json.JSONDecodeError:
        pass
    items = []
    blocks = re.split(r"\n(?=- )", text)
    for block in blocks:
        block = block.strip()
        if not block.startswith("- "):
            continue
        block = block[2:]
        item = {}
        for line in block.split("\n"):
            m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
            if m:
                key, val = m.group(1), m.group(2).strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1].replace('\\"', '"')
                item[key] = val
        if item:
            items.append(item)
    return items


def save_queue(path: Path, items: list[dict]) -> None:
    """Write queue as simple YAML (list of mappings). Same format as generate_articles.save_queue."""
    lines = []
    for item in items:
        first = True
        for k, v in item.items():
            v = str(v)
            if "\n" in v or ":" in v or v.startswith("#"):
                v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
            if first:
                lines.append(f"- {k}: {v}")
                first = False
            else:
                lines.append(f"  {k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _duplicate_key(item: dict) -> tuple[str, str, str]:
    """(title, primary_tool, content_type) for duplicate check."""
    return (
        (item.get("title") or "").strip(),
        (item.get("primary_tool") or "").strip(),
        (item.get("content_type") or "").strip(),
    )


USE_CASES_HEADER = """# List of business problems / use cases for content generation
# Each item should have:
# - problem: string (description of the problem, e.g., "turn podcasts into written content")
# - suggested_content_type: string (one of: how-to, guide, best, comparison)
# - category_slug: string (e.g., "ai-marketing-automation")
# - status: optional; "todo" = add to queue, missing or "generated" = skip (backward compat)
"""


def _save_use_cases(path: Path, items: list[dict]) -> None:
    """Write use_cases.yaml (same format as generate_use_cases). Preserves status."""
    def q(v: str) -> str:
        v = str(v)
        if "\n" in v or ":" in v or v.startswith("#") or '"' in v:
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return v
    lines = [USE_CASES_HEADER.strip(), "use_cases:"]
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


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Append queue entries from use_cases.yaml (one entry per use case).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be added, do not modify queue.yaml.",
    )
    parser.add_argument(
        "--no-ai-mapping",
        action="store_true",
        help="Do not call AI to fill missing problem->tools mapping; use only use_case_tools_mapping.yaml.",
    )
    args = parser.parse_args()

    today = date.today().isoformat()
    use_cases = load_use_cases(USE_CASES_PATH)
    tools_list = load_tools(AFFILIATE_TOOLS_PATH) if AFFILIATE_TOOLS_PATH.exists() else []

    existing_mapping: dict[str, list[str]] = {}
    existing_raw: list[dict] = []
    if USE_CASE_TOOLS_MAPPING_PATH.exists():
        existing_mapping = load_use_case_tools_mapping(USE_CASE_TOOLS_MAPPING_PATH)
        existing_raw = load_yaml_list(USE_CASE_TOOLS_MAPPING_PATH, "mapping")

    todo_use_cases = [
        uc for uc in use_cases
        if str(uc.get("status") or "generated").strip().lower() == "todo"
    ]
    problems_without_mapping = [
        (uc.get("problem") or "").strip()
        for uc in todo_use_cases
        if ((uc.get("problem") or "").strip().lower() not in existing_mapping)
        and ((uc.get("problem") or "").strip())
    ]

    if not args.no_ai_mapping and problems_without_mapping and tools_list:
        api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if api_key:
            base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").strip()
            model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
            try:
                ai_mapping = _fetch_ai_tools_mapping(
                    problems_without_mapping,
                    tools_list,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                )
                if ai_mapping:
                    existing_problem_lowers = {e.get("problem", "").strip().lower() for e in existing_raw}
                    for p, t in ai_mapping.items():
                        if p.lower() not in existing_mapping:
                            existing_mapping[p.lower()] = t
                    new_entries = [
                        {"problem": p, "tools": ", ".join(t)}
                        for p, t in ai_mapping.items()
                        if p.lower() not in existing_problem_lowers
                    ]
                    if new_entries:
                        full_entries = existing_raw + new_entries
                        _save_use_case_tools_mapping(USE_CASE_TOOLS_MAPPING_PATH, full_entries)
                        print(f"AI mapping: added {len(new_entries)} problem->tools entr{'y' if len(new_entries) == 1 else 'ies'} to use_case_tools_mapping.yaml.")
            except RuntimeError as e:
                print(f"AI mapping skipped (API error): {e}")

    tools_mapping = existing_mapping
    candidates = build_queue_items(todo_use_cases, today, tools_mapping=tools_mapping)
    if not candidates:
        print("No queue entries to add (no use cases with status 'todo').")
        return

    existing = load_existing_queue(QUEUE_PATH)
    existing_keys = {_duplicate_key(e) for e in existing}
    added = [i for i in candidates if _duplicate_key(i) not in existing_keys]
    final = existing + added

    if args.dry_run:
        print(f"Would add {len(added)} new entr{'y' if len(added) == 1 else 'ies'} (duplicates skipped: {len(candidates) - len(added)}).")
        for item in added:
            print(f"  - {item.get('title')} | {item.get('primary_tool')} | {item.get('content_type')}")
        print("(dry run: queue.yaml not modified)")
        return

    if not added:
        print("No new entries to add (all combinations already in queue).")
        return

    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_queue(QUEUE_PATH, final)
    # Mark added use cases as generated so they are not queued again
    added_keys_set = {_duplicate_key(a) for a in added}
    for i, c in enumerate(candidates):
        if _duplicate_key(c) in added_keys_set:
            uc = todo_use_cases[i]
            p = (uc.get("problem") or "").strip()
            ct = (uc.get("suggested_content_type") or "").strip()
            cat = (uc.get("category_slug") or "").strip()
            for u in use_cases:
                if (u.get("problem") or "").strip() == p and (u.get("suggested_content_type") or "").strip() == ct and (u.get("category_slug") or "").strip() == cat:
                    u["status"] = "generated"
                    break
    _save_use_cases(USE_CASES_PATH, use_cases)
    print(f"Added {len(added)} new entr{'y' if len(added) == 1 else 'ies'} to {QUEUE_PATH}. Total queue: {len(final)}. Marked those use cases as 'generated' in use_cases.yaml.")


if __name__ == "__main__":
    main()
