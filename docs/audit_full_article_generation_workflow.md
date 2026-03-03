# Audyt: pełny workflow generowania artykułu (od konfiguracji do public/articles)

**Data:** 2026-02  
**Zakres:** Konfiguracja → pomysły (use case'y) → kolejka → szkielet artykułu → wypełnienie treścią (fill) → zapis do `public/articles`.  
**Cel:** Szczegółowy opis kroków, plików, instrukcji API, logiki i funkcji bez implementacji kodu.

---

## 1. Konfiguracja (content/config.yaml i content_index)

### 1.1 Źródło i odczyt

- **Plik:** `content/config.yaml` (YAML lub JSON).
- **Odczyt:** `content_index.load_config(path)` — zwraca słownik z polami używanymi w pipeline.

### 1.2 Pola konfiguracji i ich rola

| Pole | Typ | Znaczenie w workflow |
|------|-----|----------------------|
| **production_category** | string | Nazwa **pliku** huba w `content/hubs/` (bez `.md`). Używana przez: `generate_hubs.py` (zapis huba), `generate_use_cases.py` (pierwsza kategoria na liście dozwolonych), `render_site.py` (odczyt `content/hubs/{production_category}.md`). |
| **hub_slug** | string | Slug URL huba (małe litery, myślniki). Używany w: `render_site.py` (ścieżka `public/hubs/{hub_slug}/index.html`), `generate_sitemap.py`, link „All articles” na stronie głównej. Artykuły z `category` / `category_slug` zgodnym z `hub_slug` linkują do tego samego URL. |
| **sandbox_categories** | list[str] | Dodatkowe dozwolone kategorie przy generowaniu use case'ów. `generate_use_cases` dostaje listę `[production_category] + sandbox_categories` jako dozwolone wartości `category_slug`. Nie wpływa na to, które artykuły są renderowane (wszystkie nie-blocked z statusem filled trafiają do jednego huba). |
| **use_case_batch_size** | int | Liczba use case'ów do wygenerowania w jednym uruchomieniu `generate_use_cases.py` (np. 9). Jedyna źródłowa wartość — skrypt nie przyjmuje parametru `--limit`. |
| **use_case_audience_pyramid** | list[int] | Rozkład audience w batchu: np. [3, 3] → pierwsze 3 pozycje = beginner, następne 3 = intermediate, reszta = professional. Służy do przypisania `audience_type` w use case'ach. |
| **suggested_problems** | list[str] | Opcjonalne hasła/problem do preferowania przy generowaniu use case'ów. Przekazywane do promptu API; pierwszy element może być używany jako „hard lock” (wszystkie use case'y wokół tego problemu). |
| **category_mode** | string | `production_only` \| `preserve_sandbox`. W `generate_articles`: przy `production_only` wszystkie artykuły dostają kategorię = production_category; przy `preserve_sandbox` — zachowanie category_slug z kolejki, jeśli w whitelist (production + sandbox). |

### 1.3 Wartości domyślne (gdy plik brak lub pusty)

- production_category: `"ai-marketing-automation"`
- hub_slug: `"ai-marketing-automation"`
- sandbox_categories: `[]`
- use_case_batch_size: `9`
- use_case_audience_pyramid: `[3, 3]`
- suggested_problems: `[]`
- category_mode: `"production_only"`

---

## 2. Generowanie pomysłów (use case'y) — generate_use_cases.py

### 2.1 Wejście i wyjście

- **Wejście:** `content/config.yaml`, `content/use_cases.yaml` (istniejące use case'y), `content/articles/` (frontmatter artykułów do unikania duplikatów).
- **Wyjście:** `content/use_cases.yaml` — lista obiektów pod kluczem `use_cases`; każdy: `problem`, `suggested_content_type`, `category_slug`, opcjonalnie `audience_type`, `batch_id`, `status`.

### 2.2 API

- **Endpoint:** POST `{OPENAI_BASE_URL}/v1/responses` (OpenAI Responses API).
- **Zmienne środowiskowe:** `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` (domyślnie `gpt-4o-mini`).

### 2.3 Instrukcje dla API (pełny opis i treści)

**Opis logiki:** Model pełni rolę content strategisty. Jego jedynym zadaniem jest zaproponowanie określonej liczby nowych problemów biznesowych (use case'ów) na blog w obszarze AI marketing automation. Odpowiedź musi być wyłącznie poprawną tablicą JSON — bez markdownu, bez komentarzy, bez tekstu przed lub po tablicy. Każdy element tablicy to obiekt z trzema kluczami: `problem`, `suggested_content_type`, `category_slug`. Wartości `category_slug` są podane w wiadomości użytkownika (lista dozwolonych kategorii z configu). Gdy w konfiguracji ustawiono pierwszy element listy `suggested_problems`, skrypt może włączyć „HARD LOCK”: wówczas w instrukcjach pojawia się wymóg, aby każdy use case pozostawał w tej samej domenie problemu (bez dryfowania na sąsiednie tematy). W wiadomości użytkownika przekazywane są: lista istniejących problemów (już w use_cases.yaml) — żeby nie duplikować; lista słów kluczowych/tematów z istniejących artykułów (inspiracja, bez powtórzeń); opcjonalnie lista „suggested problems” do preferowania; opcjonalnie BASE PROBLEM LOCK z dokładnym tekstem problemu bazowego oraz podziałem na trzy kąty (implementation/setup, monitoring/troubleshooting, scaling/governance). Na końcu user message jest prośba o wygenerowanie dokładnie N nowych, konkretnych, actionable problemów, ze ścisłą strukturą audience: pierwsze 3 dla beginner, następne 3 dla intermediate/mixed, reszta dla professional. Opcjonalnie filtr `content_type` wymusza jedną wartość `suggested_content_type` dla wszystkich (np. tylko how-to).

**Pełna treść instrukcji (system / instructions):**

```
You are a content strategist. Your task is to suggest new business problems / use cases for blog content in the AI marketing automation space.

Output ONLY a valid JSON array of objects. Each object must have exactly these keys:
- "problem": string, concise description of the business problem (e.g., "turn podcasts into written content")
- "suggested_content_type": string, one of: how-to, guide, best, comparison
- "category_slug": string, one of the allowed categories provided in the user message

Do not output any markdown, explanation, or text outside the JSON array. The response must be parseable as JSON.
```

Gdy włączony jest HARD LOCK (config ma `suggested_problems[0]` ustawione), do powyższego dopisywany jest blok:

```
HARD LOCK (MUST FOLLOW): Every generated use case must stay on the same base problem domain provided by the user. Do not drift to adjacent/general topics.
```

**Szablon wiadomości użytkownika (user message):**

- Stały początek: `Allowed category_slug values (use exactly one per use case):` + JSON tablica kategorii (np. `["ai-marketing-automation"]`).
- Następnie: `Existing use cases already in our list (do NOT suggest these or very similar ones):` + JSON tablica istniejących problemów.
- Następnie: `Existing article keywords/topics we already cover (suggest complementary or new angles, not duplicates):` + JSON tablica do 50 słów kluczowych/tematów z artykułów.
- Jeśli jest lista `suggested_problems`: `Optionally consider these problems (if not already covered); prefer turning them into use cases:` + JSON tablica.
- Jeśli jest HARD LOCK: `BASE PROBLEM LOCK (mandatory):` + JSON-string z dokładnym tekstem problemu bazowego + zdanie: „All generated use cases must be direct variants of this base problem. For exactly 3 use cases, enforce distinct angles: Use case #1: implementation / setup angle; Use case #2: monitoring / troubleshooting / optimization angle; Use case #3: scaling / governance / reliability angle.”
- Jeśli była wcześniejsza próba i zwrócono quality_feedback: blok „QUALITY FEEDBACK (previous attempt failed; fix all):” + lista punktów.
- Na końcu: „Generate exactly {count} new, specific, actionable business problems that people actively search for solutions to in AI marketing automation. Each must be different from the existing use cases and topics above. Structure by audience (follow this order strictly): First 3: for beginners (simple, entry-level). Next 3: for intermediate or mixed (can build on or complement the first three). Remaining: for professional users only (advanced, scaling, integration).” Jeśli ustawiono `content_type_filter`: „For every use case, set suggested_content_type to exactly: {value}.” W przeciwnym razie: „Prefer problems that fit how-to or guide content.” Ostatnie zdanie: „Return only the JSON array.”

### 2.4 Logika po stronie skryptu

- **Kategorie:** `get_categories_from_config()` → `[production_category] + sandbox_categories`.
- **Duplikaty:** funkcja `is_duplicate(problem, existing)` — porównanie case-insensitive oraz podobieństwo (jeden tekst zawiera drugi przy długości > 10).
- **Walidacja odpowiedzi:** `parse_ai_use_cases(raw, allowed_types, allowed_categories)` — wyciąga tablicę JSON z odpowiedzi (nawet gdy owrapowana w markdown), waliduje `suggested_content_type` i `category_slug`, zwraca tylko poprawne wpisy.
- **Audience:** `audience_type_for_position(position_1based, pyramid)` — na podstawie pozycji w batchu i piramidy zwraca `beginner` | `intermediate` | `professional`.
- **Zapis:** dopisanie nowych use case'ów do listy; nowe mają `status: "todo"` (żeby `generate_queue.py` je dodał do kolejki). Brak globalnego limitu liczby use case'ów w pliku.

### 2.5 Parametry CLI

- Liczba use case'ów w jednym uruchomieniu pochodzi wyłącznie z configu (`use_case_batch_size`); skrypt nie ma parametru `--limit`.
- `--category SLUG` — ograniczenie do jednej kategorii (musi być w production lub sandbox).
- `--content-type TYPE` — filtrowanie po typie (how-to, guide, best, comparison); można powtórzyć.

---

## 3. Kolejka (queue) — generate_queue.py

### 3.1 Wejście i wyjście

- **Wejście:** `content/use_cases.yaml` (wpisy z `status: "todo"`), opcjonalnie istniejący `content/queue.yaml`.
- **Wyjście:** `content/queue.yaml` — lista wpisów kolejki; każdy wpis: `title`, `primary_keyword`, `content_type`, `category_slug`, `tools` (puste), `status`, `last_updated`, opcjonalnie `audience_type`, `batch_id`.

### 3.2 Logika (bez mapowania narzędzi)

- **Plik use_case_tools_mapping.yaml:** w projekcie oznaczony jako DEPRECATED; narzędzia **nie** są ustawiane w kolejce. Pole `tools` w wpisach kolejki pozostaje puste.
- **Tytuł:** `title_for_entry(problem, content_type)` → np. „Guide to …”, „How to …” w zależności od `suggested_content_type`.
- **primary_keyword:** z tytułu (lowercase, uproszczony).
- **category_slug:** z use case'a lub domyślnie `"ai-marketing-automation"`.
- **status:** `"todo"`; po dodaniu do kolejki odpowiadające use case'y w `use_cases.yaml` są oznaczane jako `status: "generated"`.
- **Duplikaty:** po (title, content_type) — jeśli wpis już jest w kolejce, nie jest dodawany ponownie.

### 3.3 Parametry CLI

- `--dry-run` — tylko wypisanie, bez zapisu queue ani aktualizacji use_cases.yaml.

---

## 4. Generowanie szkieletów artykułów — generate_articles.py

### 4.1 Wejście i wyjście

- **Wejście:** `content/queue.yaml` (wpisy ze statusem `todo`), `content/config.yaml`, szablony z `templates/` (np. `how-to.md`, `guide.md`), istniejące artykuły w `content/articles/` (do linków wewnętrznych).
- **Wyjście:** pliki `.md` w `content/articles/` — po jednym na wpis kolejki; frontmatter + body z szablonu z podstawionymi zmiennymi; status w frontmatter: `draft`. Kolejka: status wpisów zmieniany na `generated`.

### 4.2 Konfiguracja a kategoria

- **category_mode**, **production_category**, **sandbox_categories** — jak w rozdz. 1. `normalize_category()` zwraca production_category przy `production_only` albo zachowuje category_slug z kolejki przy `preserve_sandbox` (jeśli w whitelist).

### 4.3 Szablony i zmienne

- **Szablon:** wybierany po `content_type` (np. how-to → `templates/how-to.md`, guide → `templates/guide.md`). Dozwolone typy: review, comparison, best, how-to, guide.
- **Zmienne szablonu (placeholdery):** `{{TITLE}}`, `{{PRIMARY_KEYWORD}}`, `{{CONTENT_TYPE}}`, `{{CATEGORY_SLUG}}`, `{{PRIMARY_TOOL}}`, `{{SECONDARY_TOOL}}`, `{{TOOLS_MENTIONED}}`, `{{INTERNAL_LINKS}}`, `{{CTA_BLOCK}}`, `{{AFFILIATE_DISCLOSURE}}`, `{{LAST_UPDATED}}`.
- **Źródło wartości:** z wpisu kolejki. Ponieważ `tools` w kolejce jest puste, `{{PRIMARY_TOOL}}`, `{{SECONDARY_TOOL}}`, `{{TOOLS_MENTIONED}}` pozostają jako placeholdery (do uzupełnienia w fill_articles).

### 4.4 Linki wewnętrzne

- **Funkcja:** `select_internal_links(existing, current_category, current_tools, current_content_type, …)`.
- **Priorytety:** (1) ten sam batch_id, preferowane audience sąsiednie (beginner↔intermediate, intermediate↔professional); (2) ta sama kategoria; (3) wspólne narzędzia (tools); (4) ten sam content_type. Maks. 6 linków (MAX_INTERNAL_LINKS).
- **Format w body:** markdown lista `- [Tytuł](/articles/slug/)`. Sekcja w szablonie: `## Internal links` z placeholderem `{{INTERNAL_LINKS}}`.

### 4.5 Nazwa pliku

- `{date}-{slug}.md` lub `{date}-{slug}.audience_{audience_type}.md` jeśli wpis ma `audience_type`. Slug z `primary_keyword` (slug_from_keyword).

### 4.6 Opcje CLI

- `--backfill` — tylko aktualizacja sekcji Internal links w istniejących .md (bez generowania z kolejki).
- `--re-skeleton PATH` — przebudowa szkieletu jednego pliku .md z zachowaniem frontmatter (nadpisanie body szablonem, ponowne obliczenie linków).

---

## 5. Wypełnianie treścią (fill) — fill_articles.py

### 5.1 Wybór plików do przetworzenia

- **Katalog:** `content/articles/` — skanowane są pliki `.md`.
- **Filtry:** `--since YYYY-MM-DD` (data w nazwie pliku), `--slug_contains TEXT`, `--limit N`.
- **Warunek wejścia:** `should_process(meta, body, force, use_html)` — gdy nie `--force`: pomijane pliki ze statusem `filled` lub `blocked`. Dla ścieżki MD wymagane jest występowanie placeholderów w nawiasach kwadratowych (`has_bracket_placeholders`); dla `--html` nie.

### 5.2 Tryb HTML (--html) vs Markdown

- **--html:** body artykułu generowane jest od razu w HTML z klasami Tailwind. Wynik zapisywany w pliku `.html` obok `.md`; frontmatter w komentarzu HTML na początku pliku. W .md aktualizowany jest tylko status na `filled`.
- **Bez --html:** body generowane w Markdown; zapis do tego samego pliku .md z uzupełnionym body i frontmatter.

### 5.3 Instrukcje API dla generowania body (HTML)

**Opis logiki:** Model ma rolę documentation writer. Jego zadaniem jest wygenerowanie **wyłącznie fragmentu HTML** — treści artykułu, która zostanie wstawiona wewnątrz `<article>`; strona ma już nagłówek, stopkę i tytuł (H1 z frontmatter). Model nie zwraca `<html>`, `<head>`, `<body>` ani H1 — zaczyna od pierwszej sekcji (np. Introduction lub pierwszego H2). Sekcja Disclosure nie jest dozwolona (szablon strony dodaje ją automatycznie). Lista wymaganych sekcji jest ściśle określona; każda musi wystąpić w logicznej kolejności. Sekcja „Try it yourself” jest wstrzykiwana dynamicznie w zależności od `content_type` (how-to / guide) i `audience_type` (beginner+intermediate vs professional) — osobne bloki tekstu dla professional (chain-of-thought, Role/Objective/Chain of thought/Output specification/Edge cases/Recommended tools/Uncertainty/Permission) i dla non-professional (Role/Goal/Task/Recommended tools/Uncertainty/Permission). W obu wariantach model **nie** generuje treści Prompt #2, tylko marker `[PROMPT2_PLACEHOLDER]`. Listy narzędzi (Affiliate tools, Other tools) są wstrzykiwane w instrukcjach w formacie `Name=URL` lub `Name=URL|short_description_en`; podane są reguły linkowania (pierwsze wystąpienie: link + opis w nawiasie; późniejsze: sam link) oraz wymóg użycia opisów z listy w sekcji „List of platforms and tools”. Na samym końcu odpowiedzi model musi dodać jedną linię tekstową: `TOOLS_SELECTED: ToolName1, ToolName2, ...` (1–5 narzędzi, nazwy dokładnie z list; pierwsze narzędzie będzie używane w Try it yourself). QA odrzuci artykuł przy placeholderach w nawiasach kwadratowych lub przy wystąpieniu fraz zabronionych (the best, unlimited, limit to, $, #1, pricing itd.). Długość i ton są modulowane przez audience (beginner / intermediate / professional) — dopisywane są bloki „Audience (MUST follow)” i „Length (MUST follow)”.

**Pełna treść instrukcji (instructions) — szkielet z wstawkami:**

Początek (stały):

```
You are a documentation writer. Generate the BODY of an article as HTML only. The output will be inserted inside an <article> tag; the page already has header, footer, and the article title (H1). Do NOT output <html>, <head>, <body>, or an H1 — start with the first section (e.g. Introduction or first H2). Do not generate any part of the page layout (header, footer, navigation); only the article content.
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
- List of platforms and tools mentioned in this article (place near the end, e.g. after FAQ or after Internal links; see "SECTION: List of platforms and tools" below)
- Optionally: Case study (a few paragraphs illustrating a real-world scenario: specific data, challenges, and outcomes; see example below)
```

Następnie wstawiana jest **pełna treść bloku Try it yourself** (z funkcji `_try_it_yourself_instruction(content_type, audience_type, html=True)`). Dla **how-to** zawsze wymagana; dla **guide** warunkowo (tylko gdy temat dotyczy tworzenia/przetwarzania treści z AI). Dla **professional** zawiera m.in.:

- Workflow: Human → Prompt #1 (meta-prompt do general AI, chain-of-thought) → AI zwraca Prompt #2 (gotowy do wklejenia w narzędzie) → użycie Prompt #2 w narzędziu.
- Prompt #1: struktura z etykietami **Role**, **Objective**, **Chain of thought**, **Output specification**, **Edge cases**, **Recommended tools** (WYMAGANE, 1–3 z listy), **Uncertainty**, **Permission**; każda część w osobnej linii; bloki w `<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">...</pre>`.
- Prompt #2: nie generować treści; wypisać tylko `[PROMPT2_PLACEHOLDER]`; system wstawi intro i prawdziwy Prompt #2.

Dla **beginner/intermediate** analogicznie, z etykietami **Role**, **Goal**, **Task** (zaczynające się od „Please create a prompt that will…”), **Recommended tools**, **Uncertainty**, **Permission**.

Potem stały blok:

```
SECTION: "List of platforms and tools mentioned in this article"
Include a section titled "List of platforms and tools mentioned in this article" near the end of the article (e.g. after FAQ or after Internal links; choose a consistent, logical position). This section gives readers a quick reference and supports affiliate links.
- Placement: Near the end, after FAQ or after Internal links. Do not place after the disclosure (the template adds disclosure automatically).
- Content: A bulleted list. For each tool that is both (a) in the Affiliate or Other tool list above and (b) actually linked or clearly mentioned in the article body, add one bullet containing: the tool name as a link using the exact URL from the list above, then a short one-sentence description in English. Do not list tools that you did not use or link in the article.
- Description rules: When a description was provided after | in the tool list above, use that exact description here and in the article body; do not invent a different one. Only when no description is given after |, write a factual one-sentence description in English. Avoid vague phrases like "powerful tool". Do not invent tools.
- Format: Use H2 for the section title. Use <ul class="list-disc list-inside space-y-2 text-gray-700"> for the list. Each item: <a href="URL">Tool Name</a> — description sentence. Include only tools that appear in the article body; do not invent tools. If both lists are empty, omit this section.

IMPORTANT — LENGTH: Follow the audience-based length rule (see Audience and Length below). To achieve the required word count:
- Expand "Template 1" and "Template 2" with rich, detailed examples (multiple lines or bullets each; real company names, metrics, and scenarios).
- Consider adding a "Case study" section after the templates: a concrete example of someone using the described AI tools, with specific data, challenges, and outcomes (a few paragraphs long).
Example case study tone: "A small e-commerce company, ShopSmart, used Descript to analyze competitor social media videos. They discovered that competitors were heavily using influencer marketing, which led them to pivot their strategy. Within three months, their engagement increased by 40%."

LENGTH AND CONTENT RULES:
- NEVER use square-bracket placeholders (e.g. [Name], [Date], [Customer Name], [Your Company], [Insert URL]). Every template field, example, and sentence must be filled with concrete, realistic content. Use real-looking example names, dates, product names — never leave or introduce any [bracket] token. QA will reject the article if any remain. If you need to indicate a variable or example slot, use round parentheses ( ) instead of square brackets, e.g. (video title) or (your product name).
- FORBIDDEN PHRASES (QA will reject the article if present): Never use the phrase "the best" in any generated article content (headings, body, lists, templates). Do not use "unlimited", "limit to", "limited to", or "up to [number]" (e.g. "up to 5"). Do not use $ or any currency amount (e.g. $99). Do not use "#1" or "pricing" anywhere in the article. Use neutral wording instead (e.g. "many", "as needed", "several", "a set of steps", "cost").

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
```

Następnie wstawiany jest **tools_blob**. Składa się z:

- Linii: „Affiliate tools (prefer when the tool truly fits the sentence/paragraph context; use exact URL): ” + lista w formacie `Name=URL` lub `Name=URL|short_description_en`, oddzielone przecinkami.
- Linii: „Other tools (use when no affiliate tool fits the context; choose the best match for the task): ” + analogiczna lista.
- Bloku **LINKING RULES** w dokładnej treści:

```
LINKING RULES:
- Prefer tools from the Affiliate list when they are a good fit for the context. Use the Other list only when no affiliate tool fits.
- Use the tool descriptions (after | in the list) to choose tools that match the article topic. For the "Try it yourself" section and "List of platforms and tools", the first tool in TOOLS_SELECTED will be used — it MUST be a tool that fits the article topic and the kind of Prompt #1/Prompt #2 you generate (e.g. video tools for video articles, automation tools for workflow articles). Do not choose a tool that cannot meaningfully use the generated prompts.
- At the first occurrence of each tool in the article body, use this format: <a href="URL">Name</a> (short description in English, one sentence). At later occurrences of the same tool, link only the name: <a href="URL">Name</a>, without repeating the description.
- If a tool has a description after | in the list above (e.g. Name=URL|description), use that description in the parentheses and in "List of platforms and tools"; do not invent a different description. Only when no description is given after |, write a factual one-sentence description; if unsure, use a generic form like "AI tool for [category or use case]".
```

Potem zakończenie instrukcji:

```
Output ONLY the HTML fragment that goes inside the article (no wrapper tags, no markdown).

At the very end of your response (after the HTML), add one plain-text line:
TOOLS_SELECTED: ToolName1, ToolName2, ...
- minimum 1, maximum 5 tools; names must match exactly one of the tools from the lists above; do not invent tool names.
- The first tool in this list will be used in the "Try it yourself" section. It MUST be a tool that fits the article topic and the kind of Prompt #1/Prompt #2 you generate (use the descriptions after | in the list to pick a tool that matches the article). Do not put a tool that cannot meaningfully use the generated prompts in first position.
```

Na końcu dopisywane są (gdy audience_type jest ustawione): `Audience (MUST follow):` + jedna z linii:
- beginner: „Target audience: beginners. Use simple language, avoid jargon; assume no prior experience; focus on getting started and clear step-by-step.”
- intermediate: „Target audience: intermediate. Assume some familiarity with the topic; you may use common terminology; include workflow depth and practical tradeoffs.”
- professional: „Target audience: professional/advanced. Assume experience; focus on scaling, integration, team use, and decision criteria; more concise, less hand-holding.”

Oraz `Length (MUST follow):` + jedna z:
- beginner: „Minimum length: 700 words.”
- intermediate/professional: „Minimum length: 900 words; for comprehensive sections aim for 1200.”
- domyślnie: „Minimum length: 700 words.”

**Treść wiadomości użytkownika (user / input):**

Składa się z linii: `Article title: {title}`, opcjonalnie `Primary keyword: {keyword}`, `Category: {category}`, `Content type: {content_type}`, `Target audience level: {audience_type}`, oraz zdania: „Generate the complete article body in HTML with Tailwind classes. Include all required sections (including 'List of platforms and tools mentioned in this article' near the end). {length_guide} No square-bracket placeholders; use round parentheses ( ) for any variable or example slot, e.g. (video title).”

**Pełna literalna treść bloku „Try it yourself” wstrzykiwanego do instrukcji HTML (dla audience professional):**

```
REQUIRED SECTION: "Try it yourself: Build your own AI prompt"
You MUST include this subsection (H3) inside the Step-by-step workflow section.

When you include this subsection, follow these rules:

1) Workflow explanation (required at the start): State the workflow as: Human → Prompt #1 (to AI chat) → AI returns ready-to-use Prompt #2 or questions or instruction → Human (paste Prompt #2 into AI chat or follow the instructions given).

2) Prompt #1 — Advanced chain-of-thought meta-prompt. Structure it with ALL of the following LABELED parts. Each part MUST start on a new line with its label in bold followed by a colon. Do NOT merge parts into a single paragraph. Each part must be substantive (not a one-line placeholder).
- **Role:** set the AI's expertise domain and constraints (e.g. "You are a senior marketing automation architect specializing in…").
- **Objective:** the end goal stated as a measurable outcome.
- **Chain of thought:** explicit instruction: "Think step by step: first analyze the input data, then identify the key variables, then construct the prompt for the target tool."
- **Output specification:** describe the exact format and structure of the desired Prompt #2 output (e.g. "Return a numbered list of steps that can be pasted directly into Make / Descript / etc.").
- **Edge cases:** list 2-3 edge cases the AI should handle (e.g. "If the input contains mixed languages…", "If the dataset exceeds 1000 rows…").
- **Recommended tools:** (REQUIRED — place this line before **Uncertainty:**.) List 1–3 tools from the Affiliate or Other tool list given in this prompt, using their exact names from that list. Choose tools that are suitable for the goals or tasks that are the subject of the Output (Prompt #2). Example: **Recommended tools:** Make, ChatGPT, Descript.
- **Uncertainty:** if the AI is unsure about any element, it must state so and ask for clarification.
- **Permission:** if context is insufficient, the AI should ask clarifying questions.

Use the actual tool name from the article. Put each prompt block inside <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">...</pre>.

3) Prompt #2 — Do NOT generate the content of Prompt #2 yourself. Instead, output the exact marker line [PROMPT2_PLACEHOLDER] where Prompt #2 should appear. The system will replace it with a real AI-generated output and will insert a single intro line before it (e.g. "The AI returns the following output (Prompt #2), which is ready to use with [tool] (AI tool)."). Do NOT write any sentence that introduces the output of Prompt #2 (e.g. "The AI returns the following…", "Below is the output…", "ready to use with your… tool"). Only output [PROMPT2_PLACEHOLDER]; the system will insert the single intro line automatically. Put each prompt block inside <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">...</pre>.

Emphasize that this approach makes the user the architect of a multi-step reasoning workflow, not a passive consumer of templates.
```

(Dla **guide** zamiast „REQUIRED SECTION” używane jest „CONDITIONAL SECTION” z warunkiem: „Include this subsection … ONLY if the article topic involves creating, processing, or transforming content with AI tools. If the topic is purely strategic, analytical, or organizational, omit this subsection.”)

**Pełna literalna treść bloku „Try it yourself” dla audience beginner/intermediate (HTML):**

```
REQUIRED SECTION: "Try it yourself: Build your own AI prompt"
You MUST include this subsection (H3) inside the Step-by-step workflow section.

When you include this subsection, follow these rules:

1) Workflow explanation (required at the start): The first paragraph MUST explicitly state the workflow as: Human → Prompt #1 (to AI chat) → AI returns ready-to-use Prompt #2 or questions or instruction → Human (paste Prompt #2 into AI chat or follow the instructions given). Do not omit or shorten this.

2) Prompt #1 — Structured meta-prompt. Structure it with ALL of the following LABELED parts. Each part MUST start on a new line with its label in bold followed by a colon. Do NOT merge parts into a single paragraph. Each part must be substantive (not a one-line placeholder).
- **Role:** define the role of a specialist best suited to accomplish the goal (e.g. "You are a marketing analyst with experience in…").
- **Goal:** what the user wants to achieve (the outcome).
- **Task:** a concrete request that MUST begin with "Please create a prompt that will…" for the specific tool and use case (e.g. "Please create a prompt that will analyze competitor video tone for use in Descript.").
- **Recommended tools:** (REQUIRED — place this line before **Uncertainty:**.) List 1–3 tools from the Affiliate or Other tool list given in this prompt, using their exact names from that list. Choose tools that are suitable for the goals or tasks that are the subject of the Output (Prompt #2). Example: **Recommended tools:** Make, ChatGPT, Descript.
- **Uncertainty:** if the AI is unsure about any element, it must state so and ask for clarification.
- **Permission:** if context is insufficient, the AI may ask for more details.

Use the actual tool name from the article. Put each prompt block inside <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">...</pre>.

3) Prompt #2 — Do NOT generate the content of Prompt #2 yourself. Instead, output the exact marker line [PROMPT2_PLACEHOLDER] where Prompt #2 should appear. The system will replace it with a real AI-generated output and will insert a single intro line before it (e.g. "The AI returns the following output (Prompt #2), which is ready to use with [tool] (AI tool)."). Do NOT write any sentence that introduces the output of Prompt #2 (e.g. "The AI returns the following…", "Below is the output…", "ready to use with your… tool"). Only output [PROMPT2_PLACEHOLDER]; the system will insert the single intro line automatically. Put each prompt block inside <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">...</pre>.

Emphasize that this approach makes the user the architect of the workflow, not just a passive consumer.
```

(W wersji Markdown zamiast `<pre>...</pre>` w instrukcji jest: „Put each prompt block inside a fenced code block (triple backticks).”)

### 5.4 Instrukcje API dla generowania body (Markdown)

**Opis logiki:** Model ma rolę documentation writer. Zadaniem jest zastąpienie **wyłącznie** placeholderów w nawiasach kwadratowych `[instruction or hint]` w podanym szkielecie markdown — realną prozą. Zwracany ma być pełny body (bez frontmatter). Placeholdery mustache `{{…}}` (np. `{{TOOLS_MENTIONED}}`, `{{CTA_BLOCK}}`, `{{AFFILIATE_DISCLOSURE}}`, `{{INTERNAL_LINKS}}`, `{{PRIMARY_TOOL}}`) muszą pozostać bez zmian. Nagłówki są zamrożone: nie wolno dodawać, usuwać ani zmieniać żadnego nagłówka; wyjątek: jeśli instrukcja wymaga sekcji „Try it yourself: Build your own AI prompt”, a szkielet jej nie zawiera, model musi dodać ją jako H3 wewnątrz sekcji Step-by-step workflow. W odpowiedzi nie może być żadnego tokena w nawiasach kwadratowych — każdy taki placeholder musi być zastąpiony konkretną wartością; do oznaczenia zmiennej/slotu używać nawiasów okrągłych `( )`. Zakazane są frazy: „the best”, „pricing”, „#1”; w razie potrzeby odniesienia do kosztu — neutralne sformułowania (cost, plan). Obowiązują reguły Defensible Content: persona (jedna z: Solo creator, Agency, Small business marketing lead, SaaS founder), decision rules (min. 6 bulletów „If… then…”, min. 2 „Do NOT use this when…”), tradeoffs, failure modes, SOP (5–9 punktów, bez checkboxów markdown), dwa szablony/snippety w Step-by-step. Wymagane są dokładne etykiety sekcji: „Decision rules:”, „Tradeoffs:”, „Failure modes:”, „SOP checklist:”, „Template 1:”, „Template 2:” — każda z min. 3–5 punktami. W Template 1 i Template 2 muszą być konkretne, realistyczne przykłady; żadnych `[Name]`, `[Date]` itd. Lista narzędzi: albo z frontmatter (tylko te narzędzia), albo z podanej listy dostępnych narzędzi z opisami w nawiasach — model wybiera 1–5 i na ostatniej linii odpowiedzi wypisuje `TOOLS_SELECTED: ToolName1, ToolName2, ...`. Blok „Try it yourself” wstrzykiwany jest tak jak dla HTML (how-to zawsze, guide warunkowo; professional vs beginner/intermediate). Na końcu instrukcji dopisywany jest Output Contract (A–E): wymagane markery, formatowanie (6+ bulletów Decision rules, 3+ Tradeoffs, 3+ Failure modes, 5–9 SOP, 5–10 linii Template 1/2), persona w Introduction, zakaz the best/pricing/#1/unlimited/limit to/$.

**Pełna treść instrukcji (instructions) — główne bloki:**

Początek (stały):

```
You are a documentation writer. Your task is to replace ONLY bracket placeholders [instruction or hint] in the given markdown article skeleton with real prose. Return the full markdown body (no frontmatter). Do not change any {{MUSTACHE}} placeholders (e.g. {{TOOLS_MENTIONED}}, {{CTA_BLOCK}}, {{AFFILIATE_DISCLOSURE}}, {{INTERNAL_LINKS}}, {{PRIMARY_TOOL}}). Leave them exactly as-is.
CRITICAL — No [bracket] tokens in output: Your response must not contain any text of the form [Anything] (e.g. [Name], [Date], [Customer Name], [Your Company], [Product]). Replace every such placeholder with a concrete example value. If you leave or introduce any [bracket] token, the QA check will reject the article. If you need to indicate a variable or example slot, use round parentheses ( ) instead, e.g. (video title) or (your product name).

Heading freeze: Do not add, remove, rename, or reformat any headings (#, ##, ###, ####). Do not introduce new headings of any level. Only replace bracket placeholders with plain text or lists under existing headings. Exception: if the instructions below require a "Try it yourself: Build your own AI prompt" subsection and the skeleton does not already contain it, you MUST add it as an H3 inside the Step-by-step workflow section.

Never use the phrase "the best" in any generated article content (headings, body, lists). Do not use the word "pricing" anywhere in the output (including in headings and phrases like "check pricing"). Do not use "#1" anywhere, including in headings. If you need to refer to cost, use neutral wording like "cost" or "plan" without numbers or specific claims; avoid cost talk if possible.
```

Następnie blok **Defensible Content Rules (MUST follow):**

- 1) No generic filler — każda sekcja musi zawierać co najmniej jeden konkretny constraint, tradeoff lub failure mode; zakaz vague lines („choose the right tool”, „streamline process”, „align with needs”).
- 2) Decision logic — w Main content lub Step-by-step workflow: subsection „Decision rules” (H3 lub inline), min. 6 bulletów „If … then …” lub „If … avoid … because …”, min. 2 „Do NOT use this when …”.
- 3) Use-case specificity — dokładnie jedna persona (Solo creator / Agency / Small business marketing lead / SaaS founder), wspomniana w Introduction; w workflow min. 2 constraints tej persony (time, budget, tools, approvals, compliance).
- 4) SOP / Template — w Step-by-step: krótka SOP checklist (5–9 punktów, zwykła lista; bez markdown [ ] checkboxów); 2 gotowe do skopiowania szablony (np. Content brief template, Repurposing prompt template).
- 5) Comparisons without facts — dozwolone: kryteria (speed vs control, quality vs volume); niedozwolone: ceny, limity, „best/#1”, daty wydań.
- 6) Tools discipline — narzędzia tylko z listy (albo z meta, albo z podanej listy); mini selection guide: „Use <Primary tool> when …”, „Use <Secondary tool> when …”, „Avoid both when …”.

Zdanie: „Do NOT write sentences like: 'choose a tool that fits your needs'… Replace with: 'If you publish <X> pieces/week and need <Y> turnaround, prioritize <criterion>.'”

Następnie: „How to fill: Replace each bracket placeholder with content appropriate to the **nearest preceding heading**. Use the heading text as the section type cue. Do not change any heading text.”

**CRITICAL — wymagane nagłówki:** odpowiedź MUSI zawierać dokładnie te etykiety (jako nagłówki lub **Decision rules:** itd.): „Decision rules:”, „Tradeoffs:”, „Failure modes:”, „SOP checklist:”, „Template 1:”, „Template 2:”. Żadnej z tych sekcji nie wolno pominąć; każda min. 3–5 bulletów lub treść. W „Template 1” i „Template 2” — konkretne, realistyczne przykłady; zakaz jakiegokolwiek tokena [bracket]; w razie slotu użyć ( ). QA odrzuci artykuł, jeśli pozostanie [bracket].

**Section Rules (A–F):** A) Introduction — 2–3 akapity, persona + outcome, jedno zdanie „when this is NOT worth it”. B) What you need to know first — 4–6 bulletów, min. 2 constraints/assumptions. C) Main content — Decision rules, Tradeoffs (min. 3), 2–4 podsekcje. D) Step-by-step workflow — 7–10 kroków, SOP checklist, Inputs/Outputs, 3 Common pitfalls z mitigations, dwa szablony. E) When NOT to use this — 4–6 bulletów „avoid when … because …”. F) FAQ — 5 par Q&A, min. 2 odpowiedzi z troubleshooting steps.

**No invention policy:** brak nowych nazw narzędzi poza kontekstem; brak pricing, limitów, dat, claimów best/#1; porównania tylko kryteriowe; brak linków zewnętrznych; na końcu wstawiana jest fraza stylu (docs / concise / detailed).

Następnie wstawiany jest **pełny blok Try it yourself** (funkcja `_try_it_yourself_instruction(..., html=False)` — ten sam sens co dla HTML: workflow Human→Prompt#1→Prompt#2→narzędzie, Prompt#1 ze strukturowanymi częściami, Prompt#2 tylko jako `[PROMPT2_PLACEHOLDER]`, bloki w fenced code ```).

**OUTPUT CONTRACT (MUST FOLLOW EXACTLY):**

- A) Markery pod istniejącymi sekcjami (H3/H4): „Decision rules:”, „Tradeoffs:”, „Failure modes:”, „SOP checklist:”, „Template 1:”, „Template 2:”.
- B) Formatting: pod Decision rules min. 6 bulletów „If”/„When”/„Avoid”; pod Tradeoffs min. 3 z tradeoffem; pod Failure modes min. 3 (failure + mitigation); pod SOP 5–9 zwykłych bulletów (bez [ ]); pod Template 1/2 krótkie copy-ready bloki (5–10 linii). Bez linków zewnętrznych, pricing, best/#1.
- C) Persona: w Introduction jedno zdanie z personą (Solo creator / Agency / Small business marketing lead / SaaS founder) oraz 2 constraints.
- D) Nigdy „the best”; nie używać „pricing”, „#1”, „unlimited”, „limit to”, „limited to”, „up to [number]”, „$”, kwot; QA odrzuci artykuł. Neutralne sformułowania (many, as needed, several, cost).
- E) Jeśli nie da się spełnić kontraktu, regenerować do skutku; nie pomijać markerów.

Zakończenie: „Output must feel like an internal playbook: decisions + steps + templates.”

Na końcu dopisywane są (gdy audience_type ustawione): „Audience (MUST follow):” + ta sama linia co dla HTML (beginner/intermediate/professional) oraz „Length (MUST follow):” + ta sama długość (700 / 900 słów).

**Treść wiadomości użytkownika (user):**

Linie: `Article title: {title}`, `Primary keyword: {keyword}` (opcjonalnie), `Category:`, `Content type:`, `Target audience level:`, następnie: „Markdown body to fill (replace only [...] placeholders; keep {{...}} and all headings):” oraz **pełna treść body** szkieletu (frontmatter nie jest wysyłany).

### 5.5 Post-processing po odpowiedzi API (wspólne dla HTML i MD)

1. **Usunięcie ewentualnego frontmatter z odpowiedzi** (jeśli model zwrócił --- … ---).
2. **Sanityzacja:** `sanitize_filled_body()` — zamiana zabronionych fraz: „the best” → „a strong option”, „pricing” → „cost”, „guarantee” → „assure”, kwoty $ → „cost”, „unlimited”/„limit to”/„up to N” → odpowiednie zamienniki.
3. **Strip editor notes:** usunięcie znanych linii w nawiasach (np. notatki redakcyjne).
4. **Zamiana znanych placeholderów:** `replace_known_bracket_placeholders()` — lista `_KNOWN_BRACKET_FALLBACKS` (np. [Name] → konkretna wartość). Celem uniknięcie failu QA.
5. **Zamiana pozostałych [xxx]:** `replace_remaining_bracket_placeholders_with_quoted()` — każdy pozostały `[xxx]` (oprócz checkboxów) na `"xxx"`. Wyjątek: `[PROMPT2_PLACEHOLDER]` jest pomijany (nie zamieniany na literal), żeby system mógł go później zastąpić treścią Prompt #2.
6. **Przywracanie sekcji statycznych (tylko MD):** np. „## Verification policy (editors only)” — jeśli były w oryginalnym body i zniknęły w odpowiedzi, wstawiane z powrotem przed pierwszym H2.

### 5.6 Ekstrakcja TOOLS_SELECTED i lista narzędzi

- **Regex:** `^TOOLS_SELECTED:\s*(.+)$` (multiline). Linia usuwana z body; wartość parsowana do listy nazw (max 5), walidacja przeciw `affiliate_tools.yaml`. Zapis w `meta["tools"]`.
- **Ścieżka HTML:** Lista na końcu artykułu („List of platforms and tools…”) **nie** jest budowana wyłącznie z `meta["tools"]`. Stosowany jest **środek G:** `_extract_tool_names_from_body_html(body, url_to_name)` — skan body w poszukiwaniu `<a href="URL">`; URL normalizowany i mapowany na nazwę z `affiliate_tools.yaml`. Lista narzędzi do sekcji = tylko te występujące w body (kolejność pierwszego wystąpienia). Gdy brak dopasowań — fallback na listę z `meta["tools"]`.
- **Budowa HTML listy:** `_build_tools_mentioned_html(tool_list, toolinfo)` — każdy element: link + opis z YAML (lub domyślny). Sekcja wstawiana/aktualizowana przez `_upsert_tools_section_html()`. Disclaimer nad listą: stała `TOOLS_SECTION_DISCLAIMER_HTML` (tekst bez „the best”, np. „not a claim that they are a strong option”).

### 5.7 Prompt #2 (osobne wywołanie API)

**Opis logiki:** Prompt #2 to gotowy prompt do wklejenia w konkretne narzędzie AI (np. Descript, Make). Nie jest generowany w tym samym wywołaniu co body artykułu — model w body wypisuje tylko marker `[PROMPT2_PLACEHOLDER]`. System w osobnym wywołaniu API „wykonuje” Prompt #1 (meta-prompt do general-purpose AI): wysyła treść Prompt #1 jako input do modelu z minimalną instrukcją „wykonaj”. Odpowiedź modelu traktowana jest jako treść Prompt #2 i wstawiana w miejsce placeholderu w body (w HTML w `<pre>`, w Markdown w bloku ```). Warunek uruchomienia: w body występuje marker `[PROMPT2_PLACEHOLDER]` (lub wariant wewnątrz bloku `<pre>`/fenced code). Ekstrakcja Prompt #1: pierwszy blok `<pre>` (HTML) lub pierwszy blok ``` (MD) w sekcji Try it yourself.

**Dokładna treść instrukcji i inputu dla API (Prompt #2):**

- **Endpoint:** ten sam co przy fillu — POST `{base_url}/v1/responses`.
- **Instrukcja (pole `instructions`):** dosłownie jeden wyraz: **`wykonaj`**. Nie ma rozbudowanego system promptu; model dostaje tylko tę jedną komendę.
- **Input (pole `input`):** **pełna treść Prompt #1** — czyli tekst wyciągnięty z artykułu przez `_extract_prompt1(body, is_html)` (pierwszy blok `<pre>` w sekcji Try it yourself dla HTML, pierwszy blok ``` dla MD). To jest ten sam meta-prompt, który w artykule opisuje, co użytkownik ma wkleić do general-purpose AI (Role, Goal, Task, Recommended tools itd.).
- **Oczekiwany wynik:** model ma „wykonać” ten meta-prompt — czyli wygenerować taką odpowiedź, jaką general-purpose AI zwróciłoby użytkownikowi (gotowy prompt do wklejenia w narzędzie). Ta odpowiedź jest traktowana jako treść Prompt #2 i wstawiana w body w miejsce `[PROMPT2_PLACEHOLDER]`.

**Wstawienie wyniku w body:** funkcja `_insert_prompt2(body, prompt2_text, is_html)` — szuka bloku zawierającego PROMPT2_PLACEHOLDER (regex `_PROMPT2_PRE_RE` dla HTML, `_PROMPT2_MD_BLOCK_RE` dla MD) i zamienia cały ten blok na sformatowaną treść Prompt #2 (w HTML: escaped HTML wewnątrz `<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">`; w MD: treść w bloku ```). Jeśli dopasowanie bloku się nie uda, zamieniane jest pierwsze wystąpienie samego placeholderu (regex).

### 5.8 Normalizacja „Try it yourself” (tylko HTML)

- **Funkcja:** `_normalize_try_it_yourself_html(body, slug, tool_name)`.
- **Kroki:** (1) Znajdowanie sekcji od H3 „Try it yourself…” do następnego H2. (2) Usunięcie istniejących akapitów z intro do Prompt #1 i Prompt #2 (różne warianty). (3) Rozpoznanie narzędzia: z pierwszego `<pre>` (Recommended tools) lub z parametru `tool_name`. (4) Pobranie opisu: `short_description_en` z `affiliate_tools.yaml` gdy jest, w przeciwnym razie `type_display` z kategorii (np. „Automation platform”). (5) Wstrzyknięcie przed pierwszym `<pre>` linii: „Here is the input (Prompt #1) ready to use with [link] (opis).” (6) Wstrzyknięcie przed drugim `<pre>` linii: „Below is the output (Prompt #2)… ready to use with [nazwa] … or in another tool of the same type (opis).” (7) Po drugim `<pre>` wstrzyknięcie jednego zdania CTA (z puli _TRY_CTA_VARIANTS), z ewentualnym linkiem do narzędzia wymienionego w treści Prompt #2.

### 5.9 Quality gate (opcjonalnie)

- Przy `--quality_gate` przed zapisem uruchamiana jest `check_output_contract(new_body, content_type, quality_strict)` — sprawdzenie wymaganych sekcji (Decision rules, Tradeoffs, Failure modes, SOP, Template 1/2 itd.). Przy niepowodzeniu ponowne wywołanie API z feedbackiem (do `quality_retries`). Po wyczerpaniu prób: `blocked` lub `quality_fail` zależnie od `block_on_fail`.

### 5.10 Preflight QA (run_preflight_qa)

- **A. Mustache (tylko MD):** placeholdery `{{…}}` — dozwolone usunięcie tylko `{{PRIMARY_TOOL}}`, `{{SECONDARY_TOOL}}`, `{{TOOLS_MENTIONED}}` (zastępowane przez fill). Inne usunięte/dodane → fail.
- **B. Placeholdery w nawiasach:** po wykluczeniu sekcji Template 1/2 i bloków kodu (MD) — żaden `[xxx]` (oprócz checkboxów) nie może pozostać.
- **C. Nagłówki (tylko MD):** H1 i H2 bez zmian (poza dozwolonymi wyjątkami redakcyjnymi).
- **D. Liczba słów:** próg zależny od audience (np. beginner 700/1000, intermediate/professional 900/1200) lub `min_words_override`. Dla HTML liczone na tekście po usunięciu tagów.
- **E. Wzorce zabronione:** `FORBIDDEN_PATTERNS` (np. „the best”, „#1”) — obecność w tekście → fail.
- **F. Try it yourself (gdy content_type how-to):** wymagana linia descriptor przed Prompt #1 („ready to use with X (…)”), linia przed Prompt #2 („Below is the output (Prompt #2)” … „ready to use with X (AI tool).” lub „in the same or a new thread”). Spójność narzędzia w obu; narzędzie z listy referencyjnej. Wymagane zdanie zachęty po bloku (odniesienie do Prompt #2) — bez literalnej etykiety „Action cue:”.

### 5.11 Zapis po fillu

- **Ścieżka HTML (--html):** Zapis body do pliku `content/articles/{stem}.html` z frontmatter w komentarzu na początku. Plik `.md` aktualizowany tylko w frontmatter (status `filled`). Koszty API rejestrowane.
- **Ścieżka MD:** Zapis pełnej treści (frontmatter + body) do tego samego `.md`; status `filled`. Backup `.bak` przed zapisem (gdy `--write`).

### 5.12 Parametry CLI fill_articles (wybór)

- `--write`, `--force`, `--limit`, `--since`, `--slug_contains`, `--qa` / `--no-qa`, `--qa_strict`, `--block_on_fail`, `--quality_gate`, `--quality_retries`, `--quality_strict`, `--html`, `--remap`, `--skip-prompt2`, `--prompt2-only`, `--min-words-override`, `--style`.

---

## 6. Od kontekstu do public — render_site.py i content_index

### 6.1 Które artykuły są „production”

- **Funkcja:** `get_production_articles(articles_dir, config_path)` w `content_index.py`.
- **Źródło plików:** `content/articles/`. Dla tego samego stem preferowany jest plik `.html` nad `.md` (słownik po stem, .html nadpisuje).
- **Filtry:** Tylko wpisy z **statusem `filled`**. Status `blocked` → pomijane. Inne statusy (draft, brak) → pomijane.
- **Wynik:** lista par `(meta, path)` — meta z frontmatter (dla .md) lub z komentarza HTML (dla .html), path do pliku źródłowego.

### 6.2 Render pojedynczego artykułu (_render_article)

- **Wejście:** ścieżka do pliku w `content/articles/` (.html lub .md), katalog wyjściowy `public`, opcjonalnie zbiór istniejących slugów.
- **HTML:** odczyt frontmatter z komentarza + body HTML; liczba słów z body; ewentualne stripowanie sekcji Disclosure i nadmiarowego H1.
- **MD:** parsowanie frontmatter i body; konwersja MD→HTML (`_md_to_html`), `enhance_article`, zamiana nazw narzędzi na linki (`replace_tool_names_with_links` z `affiliate_tools.yaml`).
- **Wspólne:** budowa strony: H1 (tytuł), blok meta (kategoria, data, czas czytania, lead), body, sekcja „Read Next” (3 losowe inne artykuły production), boks Disclosure. Szablon strony z `templates/article.html` ({{TITLE}}, {{STYLESHEET_HREF}}, <!-- ARTICLE_CONTENT -->).
- **Zapis:** `out_dir / "articles" / slug / "index.html"` — czyli **public/articles/{slug}/index.html**.

### 6.3 Hub i strona główna

- **Hub:** odczyt `content/hubs/{production_category}.md`; parsowanie sekcji (intro + listy linków do artykułów). Render do `public/hubs/{hub_slug}/index.html`.
- **Strona główna:** `public/index.html` — aktualizowana (lista najnowszych, link do huba).

### 6.4 Podsumowanie ścieżki „od fill do public”

1. Fill zapisuje artykuł w `content/articles/` (`.html` przy `--html` lub zaktualizowany `.md`) z **statusem `filled`** w frontmatter.
2. `render_site.py` wywołuje `get_production_articles(ARTICLES_DIR, CONFIG_PATH)` → tylko pliki ze statusem `filled`, przy tym samym stem wybierany jest `.html` jeśli istnieje.
3. Dla każdej pary (meta, path) wywoływane jest `_render_article(path, public, …)` → wynik w **public/articles/{slug}/index.html**.

---

## 7. Pliki i katalogi kluczowe dla workflow

| Ścieżka | Rola |
|---------|------|
| content/config.yaml | Konfiguracja huba, kategorii, batcha use case'ów, piramidy audience, suggested_problems. |
| content/use_cases.yaml | Lista pomysłów (problem, suggested_content_type, category_slug, audience_type, batch_id, status). |
| content/queue.yaml | Kolejka artykułów (title, primary_keyword, content_type, category_slug, tools, status, last_updated, …). |
| content/affiliate_tools.yaml | Lista narzędzi (name, category, affiliate_link, short_description_en); używana w fill i render. |
| content/articles/*.md | Szkielety i wypełnione artykuły (MD); frontmatter + body. |
| content/articles/*.html | Wypełnione artykuły (HTML) z frontmatter w komentarzu; preferowane przy renderze. |
| templates/*.md | Szablony szkieletu (how-to, guide, …). |
| content/hubs/{production_category}.md | Treść huba (generowana przez generate_hubs.py). |
| public/articles/{slug}/index.html | Opublikowana wersja artykułu. |
| public/hubs/{hub_slug}/index.html | Opublikowana strona huba. |

---

## 8. Przepływ end-to-end (skrót)

1. **Konfiguracja** — uzupełnienie `content/config.yaml` (production_category, hub_slug, sandbox, batch size, pyramid, suggested_problems).
2. **Use case'y** — `generate_use_cases.py` → API → `content/use_cases.yaml` (nowe wpisy z statusem todo).
3. **Kolejka** — `generate_queue.py` → z use case'ów z statusem todo budowane wpisy w `content/queue.yaml` (tools puste).
4. **Szkielety** — `generate_articles.py` → z kolejki (status todo) generowane pliki .md w `content/articles/` z szablonów, uzupełnione linki wewnętrzne; status wpisów kolejki → generated.
5. **Fill** — `fill_articles.py [--html] [--write]` → dla każdego .md (spełniającego warunki) wywołanie API (body HTML lub MD), post-processing (TOOLS_SELECTED, lista narzędzi z body, Prompt #2, normalizacja Try it yourself dla HTML), QA; zapis .html (i aktualizacja .md) lub .md, status filled.
6. **Render** — `render_site.py` → odczyt artykułów ze statusem filled z `content/articles/` (preferencja .html), generacja `public/articles/{slug}/index.html`, hub i index.

---

*Audyt wyłącznie opisowy; bez zmian w kodzie.*
