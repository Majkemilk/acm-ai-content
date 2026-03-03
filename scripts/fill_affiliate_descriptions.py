#!/usr/bin/env python3
"""
One-time: fill short_description_en in content/affiliate_tools.yaml for entries that lack it.
Uses the same Responses API as fill_articles. Never overwrites existing short_description_en.
Run from project root. Use --write to apply; default is dry-run.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AFFILIATE_TOOLS_PATH = PROJECT_ROOT / "content" / "affiliate_tools.yaml"

INSTRUCTIONS = (
    "You are a product classifier. Output only one short sentence in English that factually "
    "describes what this product or tool does. No marketing superlatives, no 'best' or 'leading'. "
    "Output only that one sentence, nothing else."
)


def _call_api(instructions: str, user_message: str, *, model: str, base_url: str, api_key: str) -> str:
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
        with urllib.request.urlopen(req, timeout=60) as resp:
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


def _yaml_quote(s: str) -> str:
    """Escape for YAML double-quoted value."""
    s = (s or "").strip().replace("\r", "").replace("\n", " ")
    if len(s) > 300:
        s = s[:297] + "..."
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _parse_block_name_category(block: str) -> tuple[str, str]:
    """Extract name and category from a tool block. Returns (name, category)."""
    name_m = re.search(r'name:\s*["\']([^"\']+)["\']', block, re.IGNORECASE)
    cat_m = re.search(r'category:\s*["\']([^"\']+)["\']', block, re.IGNORECASE)
    name = (name_m.group(1).strip() if name_m else "").strip()
    category = (cat_m.group(1).strip() if cat_m else "").strip()
    return name, category


def _fill_descriptions(
    path: Path,
    *,
    model: str,
    base_url: str,
    api_key: str,
    dry_run: bool,
) -> tuple[int, int]:
    """
    Read YAML, for each tool block without short_description_en call API, add line. Write back if not dry_run.
    Returns (filled_count, skipped_already_has).
    """
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"(\n  - name:)", text, maxsplit=0)
    if len(blocks) < 2:
        return 0, 0
    header = blocks[0]
    filled = 0
    skipped = 0
    new_blocks: list[str] = []
    for i in range(1, len(blocks), 2):
        delimiter = blocks[i]
        rest = blocks[i + 1] if i + 1 < len(blocks) else ""
        block = delimiter + rest
        if "short_description_en:" in block:
            skipped += 1
            new_blocks.append(delimiter)
            new_blocks.append(rest)
            continue
        name, category = _parse_block_name_category(block)
        if not name:
            new_blocks.append(delimiter)
            new_blocks.append(rest)
            continue
        user_msg = f"Product/tool name: {name}. Category: {category}."
        try:
            desc = _call_api(INSTRUCTIONS, user_msg, model=model, base_url=base_url, api_key=api_key)
        except Exception as e:
            print(f"  API failed for {name!r}: {e}", file=sys.stderr)
            new_blocks.append(delimiter)
            new_blocks.append(rest)
            continue
        desc_quoted = _yaml_quote(desc)
        if not desc_quoted:
            new_blocks.append(delimiter)
            new_blocks.append(rest)
            continue
        filled += 1
        print(f"  {name}: {desc[:60]}{'...' if len(desc) > 60 else ''}")
        line_to_add = f'\n    short_description_en: "{desc_quoted}"'
        if rest.endswith("\n"):
            inserted = rest.rstrip() + line_to_add + "\n"
        else:
            inserted = rest.rstrip() + line_to_add
        new_blocks.append(delimiter)
        new_blocks.append(inserted)
    if not dry_run and filled > 0:
        new_text = header + "".join(new_blocks)
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            backup.write_text(text, encoding="utf-8")
        except OSError as e:
            print(f"  Backup failed: {e}", file=sys.stderr)
            return filled, skipped
        path.write_text(new_text, encoding="utf-8")
    return filled, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill short_description_en in affiliate_tools.yaml for entries that lack it (one-time). Never overwrites."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply changes to file (with .bak backup). Default is dry-run.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model for API (default: gpt-4o-mini).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=AFFILIATE_TOOLS_PATH,
        help=f"Path to affiliate_tools.yaml (default: {AFFILIATE_TOOLS_PATH}).",
    )
    args = parser.parse_args()
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").strip()
    path = args.path
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        print(f"Error: {path} not found.", file=sys.stderr)
        sys.exit(1)
    dry_run = not args.write
    if dry_run:
        print("DRY-RUN (no file changes). Use --write to apply.\n")
    print(f"Reading {path.name} …")
    filled, skipped = _fill_descriptions(
        path,
        model=args.model,
        base_url=base_url,
        api_key=api_key,
        dry_run=dry_run,
    )
    print(f"\nFilled: {filled} (already had description: {skipped})")
    if dry_run and filled > 0:
        print("Run with --write to save changes.")


if __name__ == "__main__":
    main()
