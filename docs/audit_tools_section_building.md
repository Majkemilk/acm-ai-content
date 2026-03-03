# Audyt: budowanie sekcji „List of platforms and tools mentioned in this article”

**Data:** 2026-03-01  
**Zakres:** Wszystkie typy treści, szablony, ścieżka HTML i Markdown w `fill_articles.py`. Dlaczego pod listą pojawiają się lub nie pojawiają treści z linkami.

---

## 1. Gdzie sekcja jest zdefiniowana

### 1.1 Szablony (skeletony artykułów)

Wszystkie szablony w `templates/*.md` zawierają blok:

```markdown
## List of platforms and tools mentioned in this article

{{TOOLS_SECTION_DISCLAIMER}}

{{TOOLS_MENTIONED}}
```

Szablony: `how-to.md`, `guide.md`, `best.md`, `sales.md`, `comparison.md`, `product-comparison.md`, `best-in-category.md`, `category-products.md`.

- **{{TOOLS_SECTION_DISCLAIMER}}** — zastępowany stałym tekstem: *"The tools listed are a suggestion for the use case described; it does not mean they are better than other tools of this kind."*
- **{{TOOLS_MENTIONED}}** — zastępowany listą narzędzi (linki + opisy) w ścieżce **Markdown**. W ścieżce **HTML** ten blok nie występuje w ciele (model generuje cały HTML); sekcja jest wstawiana/nadpisywana przez `_upsert_tools_section_html`.

### 1.2 Generowanie szkieletów (`generate_articles.py`)

- Kolejka (`queue.yaml`) może zawierać `primary_tool`, `secondary_tool`, listę narzędzi.
- Przy renderze szablonu zmienne musztardowe są podstawiane: `TOOLS_MENTIONED` → `val_for("TOOLS_MENTIONED")` = `", ".join(tools_list)` gdy `tools_list` jest niepuste, w przeciwnym razie pozostawiane jest `{{TOOLS_MENTIONED}}`.
- **Konsekwencja:** Gdy w kolejce są narzędzia, w miejscu `{{TOOLS_MENTIONED}}` trafia **zwykły tekst** „ToolA, ToolB” (bez linków). Wtedy `fill_articles` w ścieżce MD **nie** ma już mustache do zastąpienia — sekcja zostaje z surowym tekstem „ToolA, ToolB” zamiast listy z linkami. Prawidłowa lista z linkami w MD powstaje tylko wtedy, gdy szkielet **zachował** `{{TOOLS_MENTIONED}}` (np. gdy przy generowaniu szkieletu nie było narzędzi w kolejce), a `fill_articles` podstawia tam wynik `_build_tools_mentioned_md(tool_list, name_to_url)` z `meta["tools"]`.

---

## 2. Dwie ścieżki wypełniania: HTML vs Markdown

### 2.1 Ścieżka HTML (`fill_articles.py --html`)

Używana przy normalnym wypełnianiu (m.in. `refresh_articles.py`, `fill_articles_stage1.py`). Ciało artykułu to **HTML** z API (model generuje cały artykuł w HTML).

Kolejność kroków dotyczących sekcji „List of platforms and tools”:

1. **Wyciągnięcie TOOLS_SELECTED z odpowiedzi modelu**  
   `_extract_tools_selected(body, valid_names)` szuka w body linii `TOOLS_SELECTED: ToolName1, ToolName2, ...`, usuwa ją z body, waliduje nazwy względem `affiliate_tools.yaml` (max 5). Wynik trafia do `meta["tools"]`.

2. **Źródło listy do sekcji (środek G)**  
   - Budowana jest mapa `url_to_name` z `affiliate_tools.yaml` (znormalizowany URL → nazwa).
   - **`tool_list_from_body = _extract_tool_names_from_body_html(new_body, url_to_name)`** — skan body w poszukiwaniu **wszystkich** `<a href="URL">`; jeśli URL (po normalizacji) jest w `url_to_name`, nazwa narzędzia jest dopisywana do listy (kolejność pierwszego wystąpienia, bez duplikatów).
   - **Jeśli** `tool_list_from_body` jest niepuste → **tool_list = tool_list_from_body** (preferowane).
   - **W przeciwnym razie** → **tool_list** z `meta["tools"]` (TOOLS_SELECTED).

3. **Budowa HTML listy**  
   `tools_html = _build_tools_mentioned_html(tool_list, toolinfo, audience_type)`:  
   - `toolinfo` = mapa nazwa → (url, short_description_en) z `affiliate_tools.yaml`.  
   - Dla każdej nazwy w `tool_list`: jeśli w `toolinfo` jest URL, generowany jest `<li><a href="url">name</a> — opis</li>`.  
   - **Brak URL w toolinfo** (np. narzędzie nie jest w affiliate_tools lub brak `affiliate_link`) → element **jest pomijany** (`if not url: continue`).  
   - Dla kategorii `ai-chat` i audience intermediate/professional opis może być zastępowany etykietą kategorii.

4. **Wstawienie / nadpisanie sekcji**  
   `_upsert_tools_section_html(new_body, tools_html)`:
   - Szuka w body pierwszego `<h2>…List of platforms and tools mentioned in this article</h2>` (regex).
   - **Jeśli znajdzie:** zamienia **całą zawartość między tym H2 a następnym H2 (lub końcem)** na:  
     **stały disclaimer** (TOOLS_SECTION_DISCLAIMER_HTML) + ewentualna **lista** `tools_html` („treści z linkami”).  
   - **Jeśli nie znajdzie:** dopisuje na końcu body: H2 + disclaimer + lista (jeśli jest).

Efekt: pod nagłówkiem sekcji zawsze jest **disclaimer**, a potem **albo** lista `<ul>` z linkami (gdy jest `tool_list` i poprawne wpisy w affiliate_tools), **albo** tylko disclaimer (brak listy).

### 2.2 Ścieżka Markdown (bez `--html`)

Ciało to **Markdown** (szkielet z szablonu, ewentualnie wypełniony przez API z zachowaniem mustache). Sekcja w szablonie ma postać:

```text
## List of platforms and tools mentioned in this article
{{TOOLS_SECTION_DISCLAIMER}}
{{TOOLS_MENTIONED}}
```

Kroki:

1. **TOOLS_SELECTED** w tej ścieżce **nie** jest używane (model nie zwraca HTML z tą linią).  
   **tool_list** pochodzi wyłącznie z **meta["tools"]** (frontmatter), czyli z tego, co było w szkieletie / kolejce.

2. **Podmiana mustache**  
   - `{{TOOLS_SECTION_DISCLAIMER}}` → stały tekst disclaimer (TOOLS_SECTION_DISCLAIMER).  
   - `{{TOOLS_MENTIONED}}` → `tools_md = _build_tools_mentioned_md(tool_list, name_to_url)`: lista w formacie `- [Name](url)` lub `- Name` (gdy brak URL w `name_to_url`).

3. **Kiedy lista ma linki**  
   Tylko gdy w body nadal jest literal **`{{TOOLS_MENTIONED}}`** i `tool_list` jest niepuste oraz nazwy mają wpisy w `affiliate_tools.yaml` (name → url).  
   **Kiedy lista się nie pojawia / jest bez linków:**  
   - szkielet miał już podstawione „ToolA, ToolB” zamiast `{{TOOLS_MENTIONED}}` (patrz 1.2), albo  
   - `meta["tools"]` jest puste, albo  
   - nazwy z meta nie pasują do kluczy w `name_to_url` (np. inna pisownia) → wtedy `_build_tools_mentioned_md` daje `- Name` bez linku.

---

## 3. Kiedy pod listą pojawiają się „treści z linkami”

- **Ścieżka HTML:**  
  „Treści z linkami” to **wyłącznie** to, co wstawia pipeline: **disclaimer + `<ul>` z `<a href>…`**.  
  Pojawiają się wtedy, gdy:
  1. W body HTML są **linki `<a href="URL">`** takie, że URL (po normalizacji) jest w `affiliate_tools.yaml`, **albo**
  2. Gdy takich linków nie ma — używane jest **meta["tools"]** (TOOLS_SELECTED z odpowiedzi modelu), **oraz**
  3. Dla każdej nazwy w `tool_list` istnieje w `affiliate_tools.yaml` wpis z **affiliate_link** (inaczej `_build_tools_mentioned_html` pomija ten element).

- **Ścieżka Markdown:**  
  Lista z linkami pojawia się tylko gdy:
  1. W szkieletie pozostało **`{{TOOLS_MENTIONED}}`** (nie zostało wcześniej zastąpione przez generate_articles zwykłym tekstem), oraz  
  2. `meta["tools"]` zawiera nazwy z `affiliate_tools.yaml` (żeby `name_to_url` zwracało URL).

---

## 4. Kiedy lista jest pusta lub bez linków

| Sytuacja | HTML | Markdown |
|----------|------|----------|
| W body nie ma żadnego `<a href="...">` z URL z affiliate_tools | fallback na meta["tools"]; jeśli puste → tylko disclaimer | — |
| Model nie zwrócił linii TOOLS_SELECTED | meta["tools"] puste → tylko disclaimer | meta z frontmatter; jeśli puste → pusta lista / brak listy |
| Narzędzie w tool_list nie ma w affiliate_tools lub brak affiliate_link | Ten element jest pomijany w _build_tools_mentioned_html | Link nie powstanie; tylko „- Name” |
| Szkielet z generate_articles miał tools_list → {{TOOLS_MENTIONED}} zastąpione „ToolA, ToolB” | Nie dotyczy (HTML z API) | Brak mustache → brak podmiany; pod sekcją zostaje surowy tekst „ToolA, ToolB” |

---

## 5. Stałe i funkcje (fill_articles.py) – szybki indeks

- **TOOLS_SECTION_DISCLAIMER / TOOLS_SECTION_DISCLAIMER_HTML** — stały disclaimer pod H2; zawsze wstawiany (nawet przy pustej liście).
- **`_extract_tools_selected`** — wyciąga i usuwa linię TOOLS_SELECTED z body; zwraca listę zwalidowanych nazw (max 5).
- **`_extract_tool_names_from_body_html`** — zbiera z HTML tylko nazwy narzędzi, których **href** pasuje do URL z affiliate_tools (mapa url_to_name).
- **`_build_tools_mentioned_html(tool_list, toolinfo, audience_type)`** — buduje `<ul>` z linkami i opisami; pomija narzędzia bez URL w toolinfo.
- **`_build_tools_mentioned_md(tool_list, name_to_url)`** — buduje listę MD `- [Name](url)` lub `- Name`.
- **`_upsert_tools_section_html(body, tools_ul_html)`** — nadpisuje zawartość sekcji (H2 + wszystko do następnego H2/końca) lub dopisuje sekcję na końcu; wstawia disclaimer + opcjonalną listę.

---

## 6. Rekomendacje

1. **Ścieżka Markdown / generate_articles:**  
   Nie podstawiać w szablonie `{{TOOLS_MENTIONED}}` na „ToolA, ToolB” z kolejki. Zawsze zostawiać w szkielecie literal **`{{TOOLS_MENTIONED}}`**, a listę z linkami generować wyłącznie w `fill_articles` z `meta["tools"]` (np. z frontmatter uzupełnionego z kolejki bez zmiany body). Albo: w generate_articles wstawiać od razu poprawną listę MD (np. z `_build_tools_mentioned_md`), jeśli w tym miejscu mamy dostęp do `name_to_url` i listy narzędzi — przy zachowaniu spójności z fill_articles.

2. **Spójność nazw:**  
  Lista do sekcji (HTML i MD) opiera się na **dokładnym dopasowaniu nazw** do wpisów w `affiliate_tools.yaml`. Warto w instrukcji dla modelu (TOOLS_SELECTED) podkreślić używanie **identycznych** nazw jak w podanej liście narzędzi.

3. **Narzędzia bez affiliate_link:**  
  Obecnie nie trafiają do listy w HTML (są pomijane w `_build_tools_mentioned_html`). Jeśli mają się pojawiać jako zwykły tekst (bez linku), można rozszerzyć logikę: gdy brak URL, wstawiać `<li>Name — opis</li>` (bez `<a>`).

---

*Audyt: proces budowania sekcji „List of platforms and tools mentioned in this article” dla wszystkich typów treści i obu ścieżek (HTML/MD).*
