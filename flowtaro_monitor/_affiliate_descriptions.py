# Generate short_description_en for affiliate tools via Responses API (same as fill_affiliate_descriptions.py).
# Used by Flowtaro Monitor when adding a new link (Option A: auto-fill on add).

import json
import os
import urllib.error
import urllib.request

INSTRUCTIONS = (
    "You are a product classifier. Output only one short sentence in English that factually "
    "describes what this product or tool does. No marketing superlatives, no 'best' or 'leading'. "
    "Output only that one sentence, nothing else."
)

DEFAULT_BASE_URL = "https://api.openai.com"
DEFAULT_MODEL = "gpt-4o-mini"


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
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode("utf-8"))
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


def _sanitize_description(s: str) -> str:
    """Trim, collapse newlines, limit length. Value will be quoted by save_affiliate_tools."""
    s = (s or "").strip().replace("\r", "").replace("\n", " ")
    if len(s) > 300:
        s = s[:297] + "..."
    return s


def generate_short_description(name: str, category: str) -> str | None:
    """
    Call Responses API to get one short English sentence for the tool.
    Returns None if OPENAI_API_KEY is missing or on any error (caller keeps empty description).
    """
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    base_url = (os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).strip()
    model = (os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL).strip()
    user_message = f"Name: {name or ''}\nCategory: {category or ''}"
    try:
        text = _call_api(INSTRUCTIONS, user_message, model=model, base_url=base_url, api_key=api_key)
        return _sanitize_description(text) if text else None
    except Exception:
        return None


INSTRUCTIONS_PL_TO_EN = (
    "Translate the following single short sentence from Polish to English. "
    "Output only the English sentence, nothing else. Keep the same factual, descriptive style."
)
INSTRUCTIONS_EN_TO_PL = (
    "Translate the following single short sentence from English to Polish. "
    "Output only the Polish sentence, nothing else. Keep the same factual, descriptive style."
)


def translate_pl_to_en(text_pl: str) -> str | None:
    """
    Translate one short sentence from Polish to English via Responses API.
    Returns None if OPENAI_API_KEY is missing or on any error.
    """
    text_pl = (text_pl or "").strip()
    if not text_pl:
        return None
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    base_url = (os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).strip()
    model = (os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL).strip()
    try:
        out = _call_api(INSTRUCTIONS_PL_TO_EN, text_pl, model=model, base_url=base_url, api_key=api_key)
        return _sanitize_description(out) if out else None
    except Exception:
        return None


def translate_en_to_pl(text_en: str) -> str | None:
    """
    Translate one short sentence from English to Polish via Responses API.
    Returns None if OPENAI_API_KEY is missing or on any error.
    """
    text_en = (text_en or "").strip()
    if not text_en:
        return None
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    base_url = (os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).strip()
    model = (os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL).strip()
    try:
        out = _call_api(INSTRUCTIONS_EN_TO_PL, text_en, model=model, base_url=base_url, api_key=api_key)
        return _sanitize_description(out) if out else None
    except Exception:
        return None
