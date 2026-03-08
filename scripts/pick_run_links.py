#!/usr/bin/env python3
"""
Dobierz linki: na podstawie kolejki (queue.yaml) i listy narzędzi (affiliate_tools.yaml)
wywołuje Responses API, które zwraca zestaw linków (affiliate, other, inne).
Zapisuje content/run_tools.yaml z article_built_around_links: false (domyślnie).

Kolejka: używane są pierwsze 80 pozycji ze statusem 'todo' (zgodność z pipeline generowania);
gdy brak todo — fallback na pierwsze 80 z całej kolejki (obsługa starych tematów / pełnej kolejki).
Odświeżanie linków (update_affiliate_links) nie zależy od kolejki ani run_tools — działa na wszystkich artykułach.
Uruchamiane przed dialogiem edycji w monitorze; po edycji i „Kontynuuj” monitor zapisuje run_tools ponownie.
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from content_index import load_config
from content_root import get_content_root_path
from fill_articles import _load_affiliate_tools, call_responses_api, save_run_tools
from generate_queue import load_existing_queue


# Limit tytułów wysyłanych do API (dobór linków dla tej samej „paczki” co pipeline generowania).
PICK_LINKS_QUEUE_LIMIT = 80


def _queue_items_for_link_pick(queue_items: list[dict]) -> tuple[list[dict], str]:
    """
    Zwraca (listę do 80 pozycji do promptu, opis trybu).
    Preferowane: pierwsze 80 pozycji ze statusem 'todo' (zgodne z pipeline generowania).
    Fallback: gdy brak todo — pierwsze 80 z całej kolejki (obsługa „starych” / pełna kolejka).
    """
    todo_items = [it for it in queue_items if (it.get("status") or "").strip().lower() == "todo"]
    if todo_items:
        chosen = todo_items[:PICK_LINKS_QUEUE_LIMIT]
        return chosen, f"do {PICK_LINKS_QUEUE_LIMIT} pozycji ze statusem todo (w tym runie: {len(chosen)}, łącznie todo: {len(todo_items)})"
    chosen = queue_items[:PICK_LINKS_QUEUE_LIMIT]
    return chosen, "Brak pozycji todo; używam pierwszych 80 z kolejki (fallback)."


def _run_scope_from_config(config: dict) -> str:
    """Krótki opis zakresu runu z config (production_category, sandbox, suggested_problems, hubs) — żeby model uwzględniał np. marketplaces/Amazon przy doborze linków."""
    parts = []
    prod = (config.get("production_category") or "").strip()
    if prod:
        parts.append(prod)
    sandbox = config.get("sandbox_categories") or []
    if isinstance(sandbox, list):
        for s in sandbox:
            if (s or "").strip():
                parts.append((s or "").strip())
    problems = config.get("suggested_problems") or []
    if isinstance(problems, list):
        for p in problems:
            if (p or "").strip():
                parts.append((p or "").strip())
    hubs = config.get("hubs")
    if isinstance(hubs, list):
        for h in hubs:
            if isinstance(h, dict):
                t = (h.get("title") or h.get("category") or "").strip()
                if t and t not in parts:
                    parts.append(t)
    if not parts:
        return ""
    return ", ".join(parts[:8])  # limit length


def _build_prompt(queue_items: list[dict], tools_text: str, config: dict | None = None) -> tuple[str, str]:
    """(instructions, user_message) for API to return JSON: affiliate, other, inne."""
    instructions = """You are a content planner. Given a list of article titles for a batch and a catalog of tools (name and URL), choose which tools should be used for this run.
Return ONLY valid JSON, no markdown or explanation. Use this exact structure:
{"affiliate": [{"name": "ToolName", "url": "https://..."}, ...], "other": [{"name": "ToolName", "url": "https://..."}, ...], "inne": [{"name": "Custom name", "url": "https://..."}, ...]}

Rules:
- "affiliate": tools that have referral/affiliate URLs and fit the article topics.
- "other": tools from the catalog that are not affiliate but useful for the articles.
- "inne": only if you need custom links not in the catalog (otherwise use []).
- Every name/url in affiliate and other must come from the catalog below. Do not invent URLs.
- Prefer a focused set (e.g. 3–8 affiliate, 2–5 other) rather than the entire catalog.
- If the run scope or article titles mention marketplaces, physical products, bike, anti-theft, or similar, include relevant catalog entries (e.g. Amazon/product links like Amzn when present in the catalog)."""
    titles = []
    for item in queue_items:
        t = (item.get("title") or "").strip()
        if t:
            titles.append(t)
    scope_line = ""
    if config:
        scope = _run_scope_from_config(config)
        if scope:
            scope_line = f"Site scope for this run (include tools that fit these themes): {scope}\n\n"
    user = scope_line + "Article titles in this run:\n" + "\n".join(f"- {t}" for t in titles) + "\n\nCatalog of tools (name=url):\n" + tools_text
    return instructions, user


def _parse_api_response(text: str) -> dict | None:
    """Parse API response as JSON with keys affiliate, other, inne. Return None if invalid."""
    text = (text or "").strip()
    # Strip possible markdown code fence
    if text.startswith("```"):
        idx = text.find("\n")
        if idx != -1:
            text = text[idx + 1 :]
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    for key in ("affiliate", "other", "inne"):
        if key not in data:
            data[key] = []
        if not isinstance(data[key], list):
            data[key] = []
        out = []
        for it in data[key]:
            if isinstance(it, dict) and (it.get("name") or it.get("url")):
                out.append({"name": (it.get("name") or "").strip(), "url": (it.get("url") or "").strip()})
        data[key] = out
    return data


def main() -> int:
    content_root = (os.environ.get("CONTENT_ROOT") or "content").strip() or "content"
    content_dir = get_content_root_path(PROJECT_ROOT, content_root)
    queue_path = content_dir / "queue.yaml"
    if not queue_path.exists():
        print("Brak pliku content/queue.yaml. Uruchom najpierw „Uzupełnij kolejkę”.", file=sys.stderr)
        return 1
    queue_items = load_existing_queue(queue_path)
    if not queue_items:
        print("Kolejka jest pusta. Uzupełnij kolejkę (generate_use_cases + generate_queue).", file=sys.stderr)
        return 1
    items_for_pick, mode_desc = _queue_items_for_link_pick(queue_items)
    if not items_for_pick:
        print("Brak pozycji do doboru linków (kolejka bez todo i pusta?).", file=sys.stderr)
        return 1
    print(f"Dobór linków: {mode_desc}", file=sys.stderr)
    all_tools = _load_affiliate_tools()
    if not all_tools:
        print("Brak narzędzi w content/affiliate_tools.yaml.", file=sys.stderr)
        return 1
    tools_text = ", ".join(f"{name}={url}" for name, url, *_ in all_tools if url)
    config_path = content_dir / "config.yaml"
    config = load_config(config_path) if config_path.exists() else None
    instructions, user_message = _build_prompt(items_for_pick, tools_text, config)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
        return 1
    base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1").strip()
    try:
        response_text = call_responses_api(
            instructions, user_message, model=model, base_url=base_url, api_key=api_key
        )
    except Exception as e:
        print(f"Błąd API: {e}", file=sys.stderr)
        return 1
    run_data = _parse_api_response(response_text)
    if not run_data:
        print("Odpowiedź API nieprawidłowa lub brak oczekiwanego JSON (affiliate, other, inne). Zapisuję pusty zestaw.", file=sys.stderr)
        run_data = {"affiliate": [], "other": [], "inne": [], "article_built_around_links": False}
    run_data["article_built_around_links"] = False
    run_tools_path = content_dir / "run_tools.yaml"
    save_run_tools(run_data, path=run_tools_path)
    print(f"Zapisano {run_tools_path}: affiliate={len(run_data['affiliate'])}, other={len(run_data['other'])}, inne={len(run_data['inne'])}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
