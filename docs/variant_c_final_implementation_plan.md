# Wariant C – dopracowany plan wdrożenia

## Cel

Wybór narzędzi (`primary_tool`, `secondary_tool`) odbywa się **wyłącznie** na etapie `fill_articles`, przez ten sam model AI, który pisze treść artykułu. Decyzja jest determinowana kontekstem artykułu (tytuł, keyword, audience, problem) i katalogiem narzędzi z `affiliate_tools.yaml`. Plik `use_case_tools_mapping.yaml` zostaje usunięty z pipeline. Mapowanie artykuł → narzędzia jest przechowywane w **frontmatter** artykułu (jedyne source of truth) oraz widoczne w aplikacji jako log/cache.

---

## Zasada powtarzalności

Po pierwszym fill:
- `primary_tool` i `secondary_tool` zapisane w frontmatter artykułu .md.
- Każde kolejne uruchomienie fill_articles (refresh, `--force`) **nie nadpisuje** istniejących wartości – używa tych z frontmatter.
- Ponowny wybór AI tylko gdy użytkownik jawnie tego zażąda (`--remap`).

---

## Zmiany – komponent po komponencie

### 1. `scripts/generate_queue.py`

**Usunąć:**
- Całą logikę AI mapping: `_fetch_ai_tools_mapping()`, `_build_mapping_prompt()`, `_parse_ai_mapping()`, `_call_responses_api()`, `_save_use_case_tools_mapping()`, `load_use_case_tools_mapping()`, `_default_tools_from_affiliate_list()`.
- Stałą `USE_CASE_TOOLS_MAPPING_PATH`.
- Argument `--no-ai-mapping`.
- Ładowanie i używanie `existing_mapping`, `existing_raw`, `problems_without_mapping`, `still_without`.
- Parametry `tools_mapping` i `default_tools` z `build_queue_items()`.

**Zachować:**
- `load_tools()`, `load_yaml_list()` – potrzebne gdzie indziej (import w `_monitor_data.py`).
- `load_use_case_tools_mapping()` – przenieść do `_monitor_data.py` jeśli zakładka Mapowanie zmieni źródło (patrz punkt 5).

**Zmienić:**
- `build_queue_items()` – usunąć `tools_mapping` i `default_tools`; pola `primary_tool` i `secondary_tool` ustawiać na pusty string `""`:

```python
def build_queue_items(use_cases: list[dict], today: str) -> list[dict]:
    items = []
    for uc in use_cases:
        problem = (uc.get("problem") or "").strip()
        if not problem:
            continue
        content_type = ...  # jak teraz
        category_slug = ...  # jak teraz
        title = title_for_entry(problem, content_type, "")
        item = {
            "title": title,
            "primary_keyword": title_to_primary_keyword(title),
            "content_type": content_type,
            "category_slug": category_slug,
            "primary_tool": "",
            "secondary_tool": "",
            "status": "todo",
            "last_updated": today,
            ...
        }
        items.append(item)
    return items
```

- `title_for_entry()` – przy pustym `tool_name` zwraca tytuł bez „with {tool}":

```python
def title_for_entry(problem: str, content_type: str, tool_name: str) -> str:
    ...
    if not tool_name:
        return f"{action} {problem}"   # ← to już tak działa w obecnym kodzie
    return f"{action} {problem} with {tool_name}"
```

Efekt: tytuł jest generyczny (np. „How to automate troubleshooting workflows for API error handling in marketing tools") – lepsze SEO, bez absurdalnych dopasowań.

- `main()` – uprościć: załadować use_cases, zbudować kolejkę, dodać wpisy, zapisać. Bez AI mapping, bez fallbacku, bez mapowania.

### 2. `scripts/generate_articles.py`

**Zachować bez zmian.** Obecna logika:
- `get_replacements()` – przy pustym `primary_tool` zostawia `{{PRIMARY_TOOL}}` jako placeholder w szablonie.
- `_build_tools_mentioned_from_queue_item()` – przy pustym `primary_tool` zwraca pusty string → `{{TOOLS_MENTIONED}}` zostaje jako placeholder.
- Oba placeholdery zostaną zastąpione **po fill_articles** (w post-processingu fill_one).

### 3. `scripts/fill_articles.py` – GŁÓWNA ZMIANA

#### 3a. `build_prompt()` – zmiana logiki wyboru narzędzi

Obecny kod (linie 763–779): jeśli `primary_tool` jest w frontmatter → restrykcja do tych narzędzi; jeśli pusty → podaj wszystkie.

**Nowa logika:**

```python
def build_prompt(meta, body, style="docs"):
    ...
    primary = (meta.get("primary_tool") or "").strip()
    secondary = (meta.get("secondary_tool") or "").strip()
    has_assigned_tools = primary and primary != "{{PRIMARY_TOOL}}"

    if has_assigned_tools:
        # Narzędzia już przypisane (z poprzedniego fill lub ręcznie) – użyj ich
        tool_names = [t for t in [primary, secondary] if t and t != "{{SECONDARY_TOOL}}"]
        tools_note = f" You may mention only these tools: {', '.join(tool_names)}."
    else:
        # Brak przypisanych narzędzi – model wybiera z pełnej listy
        all_tools = _load_affiliate_tools()
        tools_for_prompt = []
        for name, url, short_desc in all_tools:
            if short_desc:
                tools_for_prompt.append(f"{name} ({short_desc})")
            else:
                tools_for_prompt.append(name)
        tools_note = (
            f" No tools are pre-assigned. From the list below, choose exactly 1 or 2 tools "
            f"that are MOST USEFUL for solving the problem described in this article. "
            f"Selection criteria: direct relevance to the article's task and goals, "
            f"not general popularity.\n"
            f"Available tools: {', '.join(tools_for_prompt)}.\n"
            f"At the very end of your response, on the LAST LINE, write exactly:\n"
            f"TOOLS_SELECTED: ToolName1, ToolName2\n"
            f"(or just one tool if only one fits). "
            f"Do not invent tool names outside this list."
        )
    ...
```

Kluczowy punkt: instrukcja `TOOLS_SELECTED:` pojawia się **tylko** gdy narzędzia nie są jeszcze przypisane. Przy ponownym fill (refresh) narzędzia są w frontmatter → model ich nie wybiera ponownie.

#### 3b. `fill_one()` – post-processing po odpowiedzi API

Po otrzymaniu odpowiedzi z API i sanityzacji, dodać krok **przed** zapisem:

```python
def _extract_tools_selected(body: str, valid_names: set[str]) -> tuple[str, list[str]]:
    """Wyodrębnia linię TOOLS_SELECTED z body. Zwraca (body bez tej linii, lista nazw narzędzi)."""
    pattern = re.compile(r"^TOOLS_SELECTED:\s*(.+)$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return body, []
    raw = match.group(1).strip()
    names = [n.strip() for n in raw.split(",") if n.strip()]
    # Walidacja nazw (case-insensitive)
    validated = []
    for name in names:
        if name in valid_names:
            validated.append(name)
        else:
            for v in valid_names:
                if v.lower() == name.lower():
                    validated.append(v)
                    break
    body_clean = pattern.sub("", body).rstrip("\n") + "\n"
    return body_clean, validated[:2]
```

W `fill_one()`, po sanityzacji i przed zapisem:

```python
# Po: new_body, remaining_notes = replace_remaining_bracket_placeholders_with_quoted(new_body)
# Dodać:

primary = (meta.get("primary_tool") or "").strip()
needs_tool_selection = not primary or primary == "{{PRIMARY_TOOL}}"

if needs_tool_selection:
    valid_names = {t[0].strip() for t in _load_affiliate_tools() if t[0].strip()}
    new_body, selected_tools = _extract_tools_selected(new_body, valid_names)
    if selected_tools:
        meta["primary_tool"] = selected_tools[0]
        if len(selected_tools) > 1:
            meta["secondary_tool"] = selected_tools[1]
        else:
            meta["secondary_tool"] = ""
        # Dodaj do order (frontmatter), jeśli nie ma
        order_keys = {k for k, v in order}
        if "primary_tool" not in order_keys:
            order.append(("primary_tool", selected_tools[0]))
        if "secondary_tool" not in order_keys:
            order.append(("secondary_tool", selected_tools[1] if len(selected_tools) > 1 else ""))
        # Zastąp {{PRIMARY_TOOL}} i {{SECONDARY_TOOL}} w body
        new_body = new_body.replace("{{PRIMARY_TOOL}}", meta["primary_tool"])
        new_body = new_body.replace("{{SECONDARY_TOOL}}", meta.get("secondary_tool") or "")
        # Zbuduj listę Tools mentioned
        name_to_url = _build_name_to_url_map()
        tools_md = _build_tools_mentioned_md(selected_tools, name_to_url)
        new_body = new_body.replace("{{TOOLS_MENTIONED}}", tools_md)
        print(f"  Tools selected by AI: {', '.join(selected_tools)}")
    else:
        print(f"  Warning: AI did not return TOOLS_SELECTED line for {path.name}")
```

Pomocnicze:

```python
def _build_name_to_url_map() -> dict[str, str]:
    """name → affiliate_link z affiliate_tools.yaml."""
    return {name: url for name, url, _ in _load_affiliate_tools() if url}

def _build_tools_mentioned_md(tools: list[str], name_to_url: dict[str, str]) -> str:
    """Zbuduj sekcję markdown Tools mentioned."""
    lines = []
    for name in tools:
        url = name_to_url.get(name)
        if url:
            lines.append(f"- [{name}]({url})")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)
```

#### 3c. `_serialize_frontmatter()` – aktualizacja order

Istniejąca logika zachowuje klucze z `order` i nadpisuje `status`. Trzeba dodać aktualizację `primary_tool` i `secondary_tool` w order, jeśli meta je zmienił:

```python
def _serialize_frontmatter(meta, order, status_value="filled"):
    status_set = False
    lines = ["---"]
    seen_keys = set()
    for k, v in order:
        if k == "status":
            v = status_value
            status_set = True
        elif k in ("primary_tool", "secondary_tool"):
            v = meta.get(k, v)  # użyj wartości z meta (może być zaktualizowana)
        v = str(v)
        if "\n" in v or '"' in v:
            v = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k}: "{v}"')
        seen_keys.add(k)
    if not status_set:
        lines.append(f'status: "{status_value}"')
    # Dodaj primary_tool/secondary_tool jeśli nie było w oryginalnym order
    for k in ("primary_tool", "secondary_tool"):
        if k not in seen_keys and meta.get(k):
            v = str(meta[k])
            if "\n" in v or '"' in v:
                v = v.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k}: "{v}"')
    lines.append("---")
    return "\n".join(lines) + "\n"
```

#### 3d. Nowy argument `--remap`

```python
parser.add_argument(
    "--remap",
    action="store_true",
    help="Force AI to re-select tools even if primary_tool is already set in frontmatter.",
)
```

W `fill_one()`:

```python
if remap:
    meta["primary_tool"] = ""
    meta["secondary_tool"] = ""
```

Wywołanie: `python fill_articles.py --write --remap --force` – wymusza ponowne wypełnienie z nowym wyborem narzędzi.

### 4. Plik `content/use_case_tools_mapping.yaml`

**Usunąć z pipeline.** Nie jest odczytywany ani zapisywany przez żaden skrypt.

Fizycznie plik można:
- **Usunąć** z repozytorium, albo
- **Zachować jako archiwum** (przenieść do `docs/archive/` lub zostawić z komentarzem `# DEPRECATED – tools are now selected at fill_articles stage`).

### 5. Flowtaro Monitor – zakładka „Mapowanie"

**Zmiana źródła danych.** Zamiast czytać `use_case_tools_mapping.yaml`, zakładka odczytuje **frontmatter artykułów** i pokazuje log: artykuł (slug) → primary_tool, secondary_tool.

#### `_monitor_data.py` – nowa funkcja:

```python
def get_article_tools_data() -> list[tuple[str, str, str]]:
    """Zwraca listę (slug, primary_tool, secondary_tool) z frontmatterów artykułów."""
    if not ARTICLES_DIR.exists():
        return []
    result = []
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        block = text[3:end]
        primary = ""
        secondary = ""
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("primary_tool:"):
                primary = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("secondary_tool:"):
                secondary = line.split(":", 1)[1].strip().strip('"').strip("'")
        if primary and primary != "{{PRIMARY_TOOL}}":
            result.append((path.stem, primary, secondary if secondary != "{{SECONDARY_TOOL}}" else ""))
    return result
```

Usunąć import `load_use_case_tools_mapping` i `MAPPING_PATH`.

#### `main.py` – zmienić `build_mapping_tab()`:

```python
def build_mapping_tab(parent):
    """Zakładka: artykuł → przypisane narzędzia (z frontmatterów)."""
    f = ttk.Frame(parent, padding=10)
    ...
    ttk.Label(f, text="Artykuł → narzędzia (z frontmatter, tylko odczyt)").pack(...)
    tree = ttk.Treeview(f, columns=("slug", "primary", "secondary"), show="headings", height=20)
    tree.heading("slug", text="Artykuł")
    tree.heading("primary", text="Primary tool")
    tree.heading("secondary", text="Secondary tool")
    tree.column("slug", width=350)
    tree.column("primary", width=150)
    tree.column("secondary", width=150)
    ...
    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        for slug, primary, secondary in get_article_tools_data():
            tree.insert("", tk.END, values=(slug, primary, secondary))
    ...
```

Nazwa zakładki zmienia się z „Mapowanie" na „Narzędzia w artykułach" (i18n: `tab.mapping` → `tab.article_tools`).

---

## Przepływ po wdrożeniu

```
generate_use_cases
    ↓ use_cases.yaml (problemy, bez narzędzi)
generate_queue
    ↓ queue.yaml (primary_tool="", secondary_tool="")
generate_articles
    ↓ artykuł .md ({{PRIMARY_TOOL}}, {{SECONDARY_TOOL}}, {{TOOLS_MENTIONED}} – placeholdery)
fill_articles ← affiliate_tools.yaml (pełna lista narzędzi z opisami)
    │
    ├─ Frontmatter ma primary_tool? → TAK → użyj go, nie pytaj AI o narzędzia
    │
    └─ Frontmatter nie ma primary_tool? → model AI wybiera 1–2 narzędzia
         │                                 z pełnej listy na podstawie kontekstu artykułu
         │                                 (tytuł, keyword, audience, problem)
         ↓
       Post-processing:
         1. Wyodrębnia TOOLS_SELECTED z odpowiedzi
         2. Waliduje nazwy vs affiliate_tools.yaml
         3. Zapisuje primary_tool, secondary_tool do frontmatter
         4. Zastępuje {{PRIMARY_TOOL}}, {{SECONDARY_TOOL}}, {{TOOLS_MENTIONED}} w body
         5. Zapisuje artykuł .md
    ↓
render_site
    ↓ Nazwy narzędzi w treści → linki afiliacyjne
    ↓ HTML
```

---

## Gwarancje

| Gwarancja | Mechanizm |
|-----------|-----------|
| Narzędzia zawsze dopasowane merytorycznie | Model AI widzi pełny kontekst artykułu i wybiera z listy |
| Brak API = brak artykułu (nie: brak narzędzi) | fill_articles wymaga OPENAI_API_KEY; bez niego nie pisze treści |
| Powtarzalność przy re-fill | Zapisane w frontmatter; używane przy ponownym fill |
| Ponowny wybór na żądanie | `--remap` czyści frontmatter i wymusza nowy wybór AI |
| Brak ręcznego uzupełniania | Zero plików do edytowania ręcznie |
| Walidacja nazw narzędzi | Post-processing sprawdza vs `affiliate_tools.yaml` |
| Widoczność w aplikacji | Zakładka „Narzędzia w artykułach" pokazuje frontmatter z artykułów |

---

## Co usunąć

| Element | Akcja |
|---------|-------|
| `use_case_tools_mapping.yaml` | Usunąć lub przenieść do `docs/archive/` |
| `generate_queue.py`: AI mapping, fallback, `--no-ai-mapping` | Usunąć |
| `generate_queue.py`: `build_queue_items` param `tools_mapping`, `default_tools` | Usunąć |
| `generate_articles.py`: `_build_tools_mentioned_from_queue_item()` | Usunąć (logika przeniesiona do fill_articles) |
| `generate_articles.py`: `_load_affiliate_tools_name_to_url()` | Usunąć (logika przeniesiona do fill_articles) |
| `_monitor_data.py`: `get_mapping_data()`, import `load_use_case_tools_mapping` | Zastąpić `get_article_tools_data()` |

---

## Co dodać

| Element | Akcja |
|---------|-------|
| `fill_articles.py`: `_extract_tools_selected()` | Parsowanie TOOLS_SELECTED z odpowiedzi |
| `fill_articles.py`: `_build_name_to_url_map()`, `_build_tools_mentioned_md()` | Budowanie sekcji Tools mentioned |
| `fill_articles.py`: post-processing w `fill_one()` | Zapis do meta, zastąpienie placeholderów |
| `fill_articles.py`: `_serialize_frontmatter()` | Aktualizacja primary_tool / secondary_tool w order |
| `fill_articles.py`: `--remap` | Argument CLI |
| `_monitor_data.py`: `get_article_tools_data()` | Odczyt narzędzi z frontmatterów |
| `main.py`: zmiana `build_mapping_tab()` | Treeview z frontmatterów zamiast pliku mapowania |
| `i18n.py`: `tab.article_tools` | Nowa etykieta zakładki |

---

## Kolejność wdrożenia

1. **fill_articles.py** – dodać `_extract_tools_selected`, `_build_name_to_url_map`, `_build_tools_mentioned_md`, post-processing w `fill_one`, zmianę `build_prompt`, zmianę `_serialize_frontmatter`, argument `--remap`.
2. **generate_queue.py** – usunąć AI mapping, fallback, `--no-ai-mapping`, uprościć `build_queue_items`.
3. **generate_articles.py** – usunąć `_load_affiliate_tools_name_to_url`, `_build_tools_mentioned_from_queue_item`, uprościć `get_replacements` dla `TOOLS_MENTIONED`.
4. **_monitor_data.py** – dodać `get_article_tools_data()`, usunąć `get_mapping_data`.
5. **main.py** – zmienić `build_mapping_tab()`.
6. **i18n.py** – dodać `tab.article_tools`.
7. **use_case_tools_mapping.yaml** – usunąć lub przenieść.

Kroki 1 i 2–3 mogą być wdrażane niezależnie. Krok 1 jest krytyczny (nowa funkcjonalność). Kroki 2–7 to czyszczenie starej logiki.

---

## Rekomendacja

Wdrożyć w kolejności powyżej. Po kroku 1 (fill_articles) system od razu produkuje artykuły z sensownymi narzędziami. Kroki 2–7 to porządkowanie kodu – ważne, ale nie blokujące nowej funkcjonalności.

Test po wdrożeniu: uruchomić `fill_articles --write --limit 1 --force` na jednym z trzech artykułów z 22.02 (które teraz mają `{{PRIMARY_TOOL}}`). Sprawdzić:
- Frontmatter ma sensowne `primary_tool` / `secondary_tool`.
- Treść artykułu odnosi się do wybranych narzędzi.
- Sekcja „Tools mentioned" ma listę z linkami afiliacyjnymi.
- Ponowne uruchomienie bez `--remap` nie zmienia narzędzi.
