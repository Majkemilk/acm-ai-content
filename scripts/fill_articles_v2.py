#!/usr/bin/env python3
"""
fill_articles_v2.py - Wypełnia szkielety artykułów treścią AI.
Działa na nowych szablonach (same nagłówki, brak placeholderów []),
generując treść dla każdej sekcji.
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def make_openai_request(messages: list, model: str = "gpt-4o-mini", max_tokens: int = 4000) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY nie jest ustawiony")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
    url = f"{base_url}/v1/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        raise RuntimeError(f"API error {e.code}: {err_body}")

def parse_frontmatter(content: str):
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content
    block = content[3:end].strip()
    meta = {}
    for line in block.split("\n"):
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            meta[key] = val
    body = content[end + 4:].lstrip("\n")
    return meta, body

def build_section_prompt(section_name: str, article_meta: dict, existing_tools: list) -> str:
    title = article_meta.get("title", "?")
    keyword = article_meta.get("primary_keyword", "")
    audience = article_meta.get("audience_type", "beginner")
    lang = article_meta.get("lang", "en")
    
    lang_instructions = {
        "pl": "Pisz naturalnym, poprawnym językiem polskim. Używaj Emoji oszczędnie.",
        "en": "Write in natural, correct English. Use emoji sparingly.",
    }
    lang_instr = lang_instructions.get(lang, lang_instructions["en"])

    audience_rules = {
        "beginner": "Ton: prosty, wyjaśniaj pojęcia, unikaj żargonu.",
        "intermediate": "Ton: praktyczny, zakładaj podstawową wiedzę, pokaż workflow.",
        "professional": "Ton: zaawansowany, skup się na skalowalności, ROI, integracjach.",
    }
    aud_rule = audience_rules.get(audience, audience_rules["beginner"])

    prompt = f"""Wypełnij sekcję artykułu treścią.

ARTYKUŁ: {title}
SŁOWO KLUCZOWE: {keyword}
GRUPA DOCELOWA: {audience}
JĘZYK: {lang}

{lang_instr}
{aud_rule}

ZASADY:
- NIE powtarzaj nagłówka na początku treści.
- Pisz konkretnie, praktycznie, action-oriented.
- NIE używaj fraz: "the best", "#1", "guarantee", konkretnych cen, "unlimited".
- Jeśli sekcja wymaga przykładów, daj konkretne przykłady.
- Używaj formatowania Markdown (pogrubienia, listy, tabele jeśli potrzeba).
- Wspomnij o narzędziach: {", ".join(existing_tools) if existing_tools else "AI tools"}
- Długość: min 150-300 słów dla sekcji, rozbuduj jeśli to możliwe.

SEKCJA DO WYPEŁNIENIA:
---
{section_name}
---

Wygeneruj treść tej sekcji:"""
    return prompt

SECTIONS_TO_FILL = [
    "Introduction",
    "What you need to know first", 
    "Main content",
    "Step-by-step workflow (practical)",
    "When NOT to use this",
    "FAQ",
]

def fill_article(path: str, model: str = "gpt-4o-mini", write: bool = False) -> dict:
    content = open(path, encoding="utf-8").read()
    meta, body = parse_frontmatter(content)
    
    result = {"file": os.path.basename(path), "sections_filled": 0, "status": "skipped"}
    tools_raw = meta.get("tools", "")
    tools = [t.strip() for t in tools_raw.split(",") if t.strip()] if tools_raw else []
    
    for section_name in SECTIONS_TO_FILL:
        # Find section in body
        pattern = re.compile(rf"^##\s*{re.escape(section_name)}\s*$", re.MULTILINE)
        m = pattern.search(body)
        if not m:
            # Try fuzzy match
            escaped_name = section_name.replace('(', r'\(').replace(')', r'\)')
            pattern = re.compile(rf"^##\s*{escaped_name}", re.MULTILINE | re.IGNORECASE)
            m = pattern.search(body)
        
        if m:
            start = m.end()
            # Find next section
            next_section = re.search(r"^##\s+", body[start:], re.MULTILINE)
            if next_section:
                end_pos = start + next_section.start()
            else:
                end_pos = len(body)
            
            current_content = body[start:end_pos].strip()
            
            # Skip if already has substantial content (>100 chars without mustache)
            clean = re.sub(r'\{\{[^}]+\}\}', '', current_content).strip()
            if len(clean) > 100:
                continue
            
            print(f"  Wypełniam sekcję: {section_name}")
            prompt = build_section_prompt(section_name, meta, tools)
            
            try:
                messages = [
                    {"role": "system", "content": "Jesteś ekspertem od marketingu AI i automatyzacji. Pisz konkretne, praktyczne treści."},
                    {"role": "user", "content": prompt}
                ]
                section_content = make_openai_request(messages, model=model)
                
                # Replace empty section
                new_section = f"## {section_name}\n\n{section_content}"
                if next_section:
                    body = body[:start] + "\n" + section_content + "\n\n" + body[start + next_section.start():]
                else:
                    body = body[:start] + "\n" + section_content + "\n\n" + body[end_pos:]
                
                result["sections_filled"] += 1
            except Exception as e:
                print(f"  Błąd w sekcji {section_name}: {e}")
                result["error"] = str(e)
    
    if result["sections_filled"] > 0:
        # Update frontmatter
        meta["status"] = "filled"
        meta["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        
        # Serialize frontmatter
        fm_lines = ["---"]
        for key in ["title", "content_type", "category", "primary_keyword", "tools", 
                    "last_updated", "status", "lang", "audience_type", "batch_id"]:
            if key in meta:
                fm_lines.append(f'{key}: "{meta[key]}"')
        fm_lines.append("---")
        
        new_content = "\n".join(fm_lines) + "\n" + body
        
        if write:
            # Backup
            backup = path + ".bak_v2"
            open(backup, "w", encoding="utf-8").write(content)
            open(path, "w", encoding="utf-8").write(new_content)
            result["status"] = "wrote"
        else:
            result["status"] = "would_write"
    
    return result

def main():
    parser = argparse.ArgumentParser(description="Fill article skeleton sections with AI-generated content")
    parser.add_argument("--write", action="store_true", help="Actually write changes")
    parser.add_argument("--limit", type=int, default=0, help="Max articles to process (0=all)")
    parser.add_argument("--since", default=None, help="Only files with date >= YYYY-MM-DD")
    parser.add_argument("--slug_contains", default=None, help="Only files containing this text")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model")
    args = parser.parse_args()

    articles_dir = PROJECT_ROOT / "content" / "articles"
    
    files = sorted(articles_dir.glob("*.md"))
    if args.since:
        files = [f for f in files if f.stem.split(".")[0] >= args.since]
    if args.slug_contains:
        files = [f for f in files if args.slug_contains in f.name]
    
    # Filter: status = draft
    draft_files = []
    for f in files:
        content = f.read_text(encoding="utf-8")
        if re.search(r'status:\s*"draft"', content):
            draft_files.append(f)
    
    if args.limit > 0:
        draft_files = draft_files[:args.limit]
    
    print(f"Znaleziono {len(draft_files)} artykułów do wypełnienia")
    mode = "ZAPIS" if args.write else "DRY-RUN"
    print(f"Tryb: {mode}\n")
    
    results = []
    for i, path in enumerate(draft_files):
        print(f"[{i+1}/{len(draft_files)}] {path.name}")
        result = fill_article(str(path), model=args.model, write=args.write)
        results.append(result)
        print(f"  -> {result['status']}: {result['sections_filled']} sekcji wypełnionych\n")
    
    # Summary
    total_filled = sum(r["sections_filled"] for r in results)
    wrote = sum(1 for r in results if r["status"] == "wrote")
    would = sum(1 for r in results if r["status"] == "would_write")
    print(f"\nPodsumowanie:")
    print(f"  Artykuły: {len(results)}")
    print(f"  Sekcje wypełnione: {total_filled}")
    print(f"  Zapisanych: {wrote}")
    print(f"  Do zapisu (dry-run): {would}")

if __name__ == "__main__":
    main()
