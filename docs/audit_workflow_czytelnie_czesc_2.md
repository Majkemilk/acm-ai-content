# Workflow generowania artykułu — wersja czytelna (część 2)

**Zawartość tej części:** Generowanie szkieletów artykułów (generate_articles.py) oraz wypełnianie ich treścią (fill_articles.py) — od wyboru plików po zapis i QA.  
**Cel:** Ten sam audyt co w `audit_full_article_generation_workflow.md`, opisany po ludzku, bez skracania.

---

## 4. Generowanie szkieletów artykułów — co robi generate_articles.py

### 4.1 Z czego skrypt korzysta i co produkuje

**Wejście:**  
- Plik `content/queue.yaml` — skrypt bierze tylko wpisy ze **statusem `todo`**.  
- Plik `content/config.yaml` — do ustalenia kategorii (production_category, sandbox, category_mode).  
- Szablony z katalogu `templates/` (np. `how-to.md`, `guide.md`) — gotowe „ruszty” artykułu z placeholderami.  
- Istniejące artykuły w `content/articles/` — do wyboru linków wewnętrznych (które inne artykuły polecić w sekcji Internal links).

**Wyjście:**  
- W katalogu `content/articles/` powstaje **po jednym pliku .md na wpis kolejki**. Każdy plik ma frontmatter (tytuł, słowo kluczowe, typ treści, kategoria, status itd.) oraz body skopiowane z szablonu, w którym podstawione zostały zmienne (np. tytuł, słowo kluczowe, lista linków wewnętrznych). Status w frontmatter to **draft**.  
- W pliku `content/queue.yaml` status tych wpisów, które zostały „przerobione” na artykuły, zmienia się na **generated**, żeby przy następnym uruchomieniu nie tworzyć duplikatów.

### 4.2 Konfiguracja a kategoria artykułu

Z configu brane są: **category_mode**, **production_category**, **sandbox_categories**. Funkcja `normalize_category()` decyduje, jaką kategorię wpisać w metadane artykułu.  
- Przy **production_only**: każdy artykuł dostaje kategorię równą `production_category`, niezależnie od tego, co było w wpisie kolejki.  
- Przy **preserve_sandbox**: zachowywany jest `category_slug` z kolejki, **ale tylko** jeśli ten slug jest na liście dozwolonych (production + sandbox). Dzięki temu możesz mieć w kolejce wpisy z różnych kategorii sandbox i one zostaną w metadanych pliku .md.

### 4.3 Szablony i zmienne (placeholdery)

**Który szablon:**  
Wybierany na podstawie `content_type` z wpisu kolejki. Np. typ „how-to” → plik `templates/how-to.md`, „guide” → `templates/guide.md`. Dozwolone typy to: review, comparison, best, how-to, guide.

**Jakie placeholdery są w szablonie:**  
W treści szablonu występują zmienne w podwójnych nawiasach klamrowych, np. `{{TITLE}}`, `{{PRIMARY_KEYWORD}}`, `{{CONTENT_TYPE}}`, `{{CATEGORY_SLUG}}`, `{{PRIMARY_TOOL}}`, `{{SECONDARY_TOOL}}`, `{{TOOLS_MENTIONED}}`, `{{INTERNAL_LINKS}}`, `{{CTA_BLOCK}}`, `{{AFFILIATE_DISCLOSURE}}`, `{{LAST_UPDATED}}`. Wartości dla tytułu, słowa kluczowego, typu, kategorii, daty itd. pochodzą z wpisu kolejki.  
Ponieważ w kolejce pole **tools** jest puste, placeholdery `{{PRIMARY_TOOL}}`, `{{SECONDARY_TOOL}}`, `{{TOOLS_MENTIONED}}` **nie** są na tym etapie wypełniane — pozostają w tekście i zostaną uzupełnione dopiero przy wypełnianiu artykułu treścią (fill_articles).

### 4.4 Linki wewnętrzne

Funkcja **select_internal_links** wybiera, do których istniejących artykułów dodać link w sekcji „Internal links”. Priorytety: (1) artykuły z tego samego batch_id, przy tym preferowane są „sąsiednie” poziomy odbiorcy (beginner↔intermediate, intermediate↔professional); (2) ta sama kategoria; (3) wspólne narzędzia (tools); (4) ten sam content_type. Maksymalna liczba linków jest ograniczona (np. 6 — stała MAX_INTERNAL_LINKS).  
W body szablonu sekcja ma postać listy markdown, np. `- [Tytuł](/articles/slug/)`. W szablonie jest placeholder `{{INTERNAL_LINKS}}`, który skrypt zastępuje wygenerowaną listą.

### 4.5 Jak nazywa się plik

Nazwa pliku .md budowana jest z daty i sluga. Slug pochodzi z primary_keyword (funkcja slug_from_keyword). Format: `{data}-{slug}.md`. Jeśli wpis kolejki ma pole `audience_type`, w nazwie może się pojawić także sufiks, np. `{data}-{slug}.audience_{audience_type}.md`.

### 4.6 Opcje CLI

- **--backfill** — Skrypt **nie** generuje nowych plików z kolejki. Tylko aktualizuje sekcję Internal links w **już istniejących** plikach .md (przelicza linki wewnętrzne i nadpisuje tę sekcję).
- **--re-skeleton ŚCIEŻKA** — Przebudowa szkieletu **jednego** pliku .md: frontmatter zostaje, body jest zastępowane treścią z odpowiedniego szablonu, linki wewnętrzne są przeliczane od zera. Przydatne, gdy zmienił się szablon albo lista artykułów.

---

## 5. Wypełnianie treścią (fill) — co robi fill_articles.py

### 5.1 Które pliki są przetwarzane

Skrypt przegląda katalog **content/articles/** i szuka plików **.md**.  
Dodatkowo można zawęzić listę przez parametry: **--since YYYY-MM-DD** (tylko pliki, których nazwa ma datę nie wcześniejszą niż podana), **--slug_contains TEKST** (tylko pliki, w których nazwie występuje ten tekst), **--limit N** (maksymalnie N plików).

Dla każdego pliku .md sprawdzany jest warunek **should_process(meta, body, force, use_html)**. Bez **--force** pomijane są pliki, które w frontmatter mają już status **filled** lub **blocked**. Dla ścieżki **Markdown** (bez --html) wymagane jest, żeby w body występowały placeholdery w nawiasach kwadratowych (`has_bracket_placeholders`) — inaczej nie ma czego wypełniać. Dla ścieżki **HTML** (--html) tego warunku nie ma — cały body jest generowany od zera.

### 5.2 Tryb HTML (--html) a tryb Markdown

- **Z flagą --html:** Treść artykułu (body) jest generowana od razu w **HTML** z klasami Tailwind. Wynik zapisywany jest w pliku **.html** obok .md (ta sama nazwa, inne rozszerzenie). Frontmatter w pliku .html jest trzymany w komentarzu HTML na początku. W pliku .md aktualizowany jest wtedy **tylko** status na `filled` (żeby render wiedział, że artykuł jest gotowy).
- **Bez --html:** Body jest generowane w **Markdown**. Zapis idzie do tego samego pliku .md — uzupełniony body i zaktualizowany frontmatter; status `filled`.

### 5.3 Instrukcje API dla generowania body w HTML — opis po ludzku i pełne treści

**O co chodzi:**  
Model ma rolę **documentation writer**. Ma wygenerować **tylko fragment HTML** — treść, która trafi do środka tagu `<article>`. Strona ma już nagłówek, stopkę i tytuł (H1 z frontmatter), więc model nie zwraca `<html>`, `<head>`, `<body>` ani H1 — zaczyna od pierwszej sekcji (np. Introduction lub pierwszego H2). Sekcji „Disclosure” nie wolno dodawać — szablon strony dokleja ją na końcu automatycznie.

Lista **wymaganych sekcji** jest ściśle określona (Introduction, What you need to know first, Decision rules, Tradeoffs, Failure modes, SOP checklist, Template 1, Template 2, Step-by-step workflow, When NOT to use this, FAQ, Internal links, List of platforms and tools mentioned in this article, opcjonalnie Case study). Sekcja **„Try it yourself: Build your own AI prompt”** jest wstrzykiwana do instrukcji dynamicznie — inny tekst dla odbiorcy professional (chain-of-thought, Role/Objective/Chain of thought/Output specification/Edge cases/Recommended tools/Uncertainty/Permission) i dla beginner/intermediate (Role/Goal/Task/Recommended tools/Uncertainty/Permission). W obu wariantach model **nie** generuje treści „Prompt #2” — wstawia tylko marker `[PROMPT2_PLACEHOLDER]`; system później w osobnym wywołaniu API wygeneruje prawdziwy Prompt #2 i wstawi go w to miejsce.

Listy narzędzi (Affiliate tools, Other tools) są wstrzykiwane w instrukcjach w formacie np. `Name=URL` lub `Name=URL|short_description_en`. Są podane reguły: przy pierwszym wystąpieniu narzędzia w tekście — link + opis w nawiasie; przy kolejnych — sam link; opisy w sekcji „List of platforms and tools” mają być z listy, nie wymyślone. Na **samym końcu** odpowiedzi model musi dodać jedną linię tekstową: **TOOLS_SELECTED: ToolName1, ToolName2, ...** (od 1 do 5 narzędzi, nazwy dokładnie z list; pierwsze narzędzie z listy będzie używane w sekcji Try it yourself).

QA odrzuci artykuł, jeśli w treści zostaną placeholdery w nawiasach kwadratowych albo zabronione frazy (np. „the best”, „unlimited”, „limit to”, „$”, „#1”, „pricing”). Długość i ton są zależne od odbiorcy (beginner / intermediate / professional) — do instrukcji dopisywane są bloki „Audience (MUST follow)” i „Length (MUST follow)”.

**Początek instrukcji (stały):**

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

Następnie wstawiana jest **pełna treść bloku Try it yourself** — dla how-to sekcja jest obowiązkowa, dla guide tylko gdy temat dotyczy tworzenia/przetwarzania treści z AI. Dla **professional** blok zawiera m.in.: workflow Human → Prompt #1 (meta-prompt do general AI, chain-of-thought) → AI zwraca Prompt #2 → użycie Prompt #2 w narzędziu; Prompt #1 z etykietami Role, Objective, Chain of thought, Output specification, Edge cases, Recommended tools (wymagane, 1–3 z listy), Uncertainty, Permission; Prompt #2 tylko jako `[PROMPT2_PLACEHOLDER]`. Dla **beginner/intermediate** — Role, Goal, Task (zaczynające się od „Please create a prompt that will…”), Recommended tools, Uncertainty, Permission; Prompt #2 znowu tylko placeholder.

**Stały blok dalej:**

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
- Special sections (Decision rules, Tradeoffs, Failure modes, SOP checklist): wrap in <div class="bg-indigo-50 p-6 rounded-lg border border-indigo-100 my-6"> with an <h3 class="text-xl font-semibold"> inside.
- Template 1 / Template 2 cards: wrap in <div class="bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow mb-4">. Put real example content inside <pre> or structured <p>/<ul>, never [Insert ...].
- Blockquotes: <blockquote class="border-l-4 border-indigo-500 pl-4 italic text-gray-600 my-4">. Inline code: <code class="bg-gray-100 px-1 py-0.5 rounded text-sm">. Code blocks: <pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto">.
```

Potem wstawiany jest **tools_blob**: linia „Affiliate tools (prefer when the tool truly fits…):” + lista w formacie Name=URL lub Name=URL|opis; linia „Other tools (use when no affiliate tool fits…):” + lista; oraz blok **LINKING RULES** w dokładnej treści:

```
LINKING RULES:
- Prefer tools from the Affiliate list when they are a good fit for the context. Use the Other list only when no affiliate tool fits.
- Use the tool descriptions (after | in the list) to choose tools that match the article topic. For the "Try it yourself" section and "List of platforms and tools", the first tool in TOOLS_SELECTED will be used — it MUST be a tool that fits the article topic and the kind of Prompt #1/Prompt #2 you generate (e.g. video tools for video articles, automation tools for workflow articles). Do not choose a tool that cannot meaningfully use the generated prompts.
- At the first occurrence of each tool in the article body, use this format: <a href="URL">Name</a> (short description in English, one sentence). At later occurrences of the same tool, link only the name: <a href="URL">Name</a>, without repeating the description.
- If a tool has a description after | in the list above (e.g. Name=URL|description), use that description in the parentheses and in "List of platforms and tools"; do not invent a different description. Only when no description is given after |, write a factual one-sentence description; if unsure, use a generic form like "AI tool for [category or use case]".
```

**Zakończenie instrukcji:**

```
Output ONLY the HTML fragment that goes inside the article (no wrapper tags, no markdown).

At the very end of your response (after the HTML), add one plain-text line:
TOOLS_SELECTED: ToolName1, ToolName2, ...
- minimum 1, maximum 5 tools; names must match exactly one of the tools from the lists above; do not invent tool names.
- The first tool in this list will be used in the "Try it yourself" section. It MUST be a tool that fits the article topic and the kind of Prompt #1/Prompt #2 you generate (use the descriptions after | in the list to pick a tool that matches the article). Do not put a tool that cannot meaningfully use the generated prompts in first position.
```

Na końcu dopisywane są (gdy ustawiony jest audience_type): **Audience (MUST follow):** — beginner: „Target audience: beginners. Use simple language, avoid jargon; assume no prior experience; focus on getting started and clear step-by-step.” — intermediate: „Target audience: intermediate. Assume some familiarity with the topic; you may use common terminology; include workflow depth and practical tradeoffs.” — professional: „Target audience: professional/advanced. Assume experience; focus on scaling, integration, team use, and decision criteria; more concise, less hand-holding.”  
Oraz **Length (MUST follow):** — beginner: „Minimum length: 700 words.” — intermediate/professional: „Minimum length: 900 words; for comprehensive sections aim for 1200.” — domyślnie: „Minimum length: 700 words.”

**Wiadomość użytkownika (input)** składa się z linii: Article title, Primary keyword, Category, Content type, Target audience level, oraz zdania z prośbą o wygenerowanie pełnego body w HTML z Tailwind, ze wszystkimi wymaganymi sekcjami, z podanym minimum słów i z zakazem placeholderów w nawiasach kwadratowych (zamiast nich używać nawiasów okrągłych).

**Pełna literalna treść bloku „Try it yourself” dla audience professional (HTML)** — jak w oryginalnym audycie: REQUIRED SECTION, workflow Human→Prompt#1→Prompt#2→tool, Prompt #1 z Role, Objective, Chain of thought, Output specification, Edge cases, Recommended tools, Uncertainty, Permission; Prompt #2 tylko [PROMPT2_PLACEHOLDER]; bloki w `<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto text-sm">...</pre>`.  
Dla **guide** zamiast REQUIRED SECTION używane jest CONDITIONAL SECTION (włączyć tylko gdy temat dotyczy tworzenia/przetwarzania treści z AI).  
**Dla beginner/intermediate** — ten sam schemat, z etykietami Role, Goal, Task („Please create a prompt that will…”), Recommended tools, Uncertainty, Permission; Prompt #2 tylko [PROMPT2_PLACEHOLDER]. W wersji Markdown w instrukcji zamiast `<pre>` jest „fenced code block (triple backticks)”.

### 5.4 Instrukcje API dla generowania body w Markdown — opis po ludzku i główne bloki

Model ma zastąpić **tylko** placeholdery w nawiasach kwadratowych `[instruction or hint]` w szkielecie markdown — realną prozą. Zwraca **pełny body** (bez frontmatter). Placeholdery mustache `{{…}}` (np. {{TOOLS_MENTIONED}}, {{CTA_BLOCK}}, {{PRIMARY_TOOL}}) muszą **pozostać bez zmian**. Nagłówki są „zamrożone” — nie wolno ich dodawać, usuwać ani zmieniać; wyjątek: jeśli instrukcja wymaga sekcji „Try it yourself…”, a szkielet jej nie ma, model musi dodać ją jako H3 w sekcji Step-by-step workflow.

W odpowiedzi **nie może** być żadnego tokena w nawiasach kwadratowych — każdy placeholder musi być zastąpiony konkretną wartością; do zmiennych/slotów używać nawiasów okrągłych. Zakazane frazy: „the best”, „pricing”, „#1”; przy kosztach — neutralne sformułowania (cost, plan).

Obowiązują reguły **Defensible Content**: jedna persona (Solo creator / Agency / Small business marketing lead / SaaS founder), decision rules (min. 6 bulletów „If… then…”, min. 2 „Do NOT use this when…”), tradeoffs, failure modes, SOP (5–9 punktów, bez checkboxów), dwa szablony w Step-by-step. Wymagane etykiety sekcji: „Decision rules:”, „Tradeoffs:”, „Failure modes:”, „SOP checklist:”, „Template 1:”, „Template 2:” — każda z min. 3–5 punktami. W Template 1 i 2 — konkretne przykłady, żadnych [Name], [Date] itd. Narzędzia: albo z frontmatter, albo model wybiera 1–5 z podanej listy i na ostatniej linii wypisuje TOOLS_SELECTED: ToolName1, ToolName2, ...  
Blok Try it yourself wstrzykiwany tak jak dla HTML (how-to zawsze, guide warunkowo; professional vs beginner/intermediate). Na końcu instrukcji **Output Contract (A–E)**: wymagane markery, formatowanie (6+ bulletów Decision rules, 3+ Tradeoffs, 3+ Failure modes, 5–9 SOP, 5–10 linii Template 1/2), persona w Introduction, zakaz the best/pricing/#1/unlimited/limit to/$.

**Początek instrukcji (stały):** You are a documentation writer; replace ONLY bracket placeholders; return full markdown body; do not change {{MUSTACHE}}; CRITICAL — no [bracket] tokens in output; Heading freeze; Never "the best", "pricing", "#1"; cost → neutral wording.  
Następnie **Defensible Content Rules** 1–6 (no generic filler, decision logic, use-case specificity, SOP/Template, comparisons without facts, tools discipline), zdanie o unikaniu fraz w stylu „choose a tool that fits your needs”, „How to fill” (replace placeholders under nearest heading). **CRITICAL — wymagane nagłówki:** Decision rules:, Tradeoffs:, Failure modes:, SOP checklist:, Template 1:, Template 2: — każda min. 3–5 punktów; w Template 1/2 konkretne przykłady, zakaz [bracket]. **Section Rules A–F** (Introduction, What you need to know first, Main content, Step-by-step workflow, When NOT to use this, FAQ). **No invention policy.** Pełny blok Try it yourself (jak dla HTML, z fenced code). **OUTPUT CONTRACT A–E** (markery, formatting, persona, zakaz the best/pricing/#1/unlimited/$, nie pomijać). Zakończenie: „Output must feel like an internal playbook: decisions + steps + templates.” Na końcu Audience i Length (jak przy HTML).

**Wiadomość użytkownika:** linie z tytułem, słowem kluczowym, kategorią, typem treści, poziomem odbiorcy, potem „Markdown body to fill (replace only [...] placeholders; keep {{...}} and all headings):” oraz **cała treść body** szkieletu (frontmatter nie jest wysyłany).

### 5.5 Post-processing po odpowiedzi API (wspólne dla HTML i MD)

1. **Usunięcie frontmatter z odpowiedzi** — jeśli model mimo wszystko zwrócił blok --- … ---, jest on usuwany z body.  
2. **Sanityzacja** — funkcja `sanitize_filled_body()` zamienia zabronione frazy na dozwolone: np. „the best” → „a strong option”, „pricing” → „cost”, „guarantee” → „assure”, kwoty w $ → „cost”, „unlimited” / „limit to” / „up to N” → odpowiednie zamienniki.  
3. **Strip editor notes** — usuwane są znane linie w nawiasach (np. notatki redakcyjne).  
4. **Zamiana znanych placeholderów** — `replace_known_bracket_placeholders()`: lista _KNOWN_BRACKET_FALLBACKS (np. [Name] → konkretna wartość), żeby uniknąć niepotrzebnego failu QA.  
5. **Zamiana pozostałych [xxx]** — `replace_remaining_bracket_placeholders_with_quoted()`: każdy pozostały `[xxx]` (oprócz checkboxów typu [ ], [x]) zamieniany jest na `"xxx"`. **Wyjątek:** `[PROMPT2_PLACEHOLDER]` **nie** jest zamieniany — zostaje, żeby system mógł go później zastąpić prawdziwą treścią Prompt #2.  
6. **Przywracanie sekcji statycznych (tylko MD)** — np. „## Verification policy (editors only)” — jeśli była w oryginalnym body i zniknęła w odpowiedzi, jest wstawiana z powrotem przed pierwszym H2.

### 5.6 Ekstrakcja TOOLS_SELECTED i budowa listy narzędzi

Linia **TOOLS_SELECTED:** w odpowiedzi jest wyszukiwana regexem (np. `^TOOLS_SELECTED:\s*(.+)$` w trybie multiline). Ta linia jest **usuwana** z body. Wartość po dwukropku parsowana jest do listy nazw (maks. 5), sprawdzana pod kątem listy narzędzi z affiliate_tools.yaml; wynik zapisywany w **meta["tools"]**.

Dla **ścieżki HTML** sekcja „List of platforms and tools mentioned in this article” **nie** jest budowana wyłącznie z meta["tools"]. Stosowany jest tzw. **środek G**: funkcja `_extract_tool_names_from_body_html(body, url_to_name)` skanuje body w poszukiwaniu linków `<a href="URL">`; URL jest normalizowany i mapowany na nazwę z affiliate_tools.yaml. Lista narzędzi do wyświetlenia w sekcji = tylko te, które **faktycznie występują** w body (w kolejności pierwszego wystąpienia). Gdy brak dopasowań — używana jest lista z meta["tools"].

Budowa HTML listy: funkcja `_build_tools_mentioned_html(tool_list, toolinfo)` — każdy element to link + opis z YAML (lub domyślny). Sekcja wstawiana/aktualizowana przez `_upsert_tools_section_html()`. Nad listą dodawany jest disclaimer (stała TOOLS_SECTION_DISCLAIMER_HTML — tekst bez „the best”, np. że to nie twierdzenie, iż są „najlepsze”, tylko „a strong option”).

### 5.7 Prompt #2 — osobne wywołanie API

**O co chodzi:** Prompt #2 to gotowy prompt do wklejenia w konkretne narzędzie (np. Descript, Make). Nie jest generowany w tym samym wywołaniu co body — w body model wstawia tylko marker `[PROMPT2_PLACEHOLDER]`. System w **osobnym** wywołaniu API „wykonuje” Prompt #1: wysyła treść Prompt #1 (meta-prompt do general-purpose AI) jako **input** do modelu z minimalną instrukcją „wykonaj”. Odpowiedź modelu traktowana jest jako treść Prompt #2 i wstawiana w miejsce placeholderu (w HTML w `<pre>`, w Markdown w bloku ```).  
Warunek: w body musi występować marker [PROMPT2_PLACEHOLDER] (lub wariant w bloku <pre>/fenced code). Prompt #1 jest wyciągany: pierwszy blok `<pre>` (HTML) lub pierwszy blok ``` (MD) w sekcji Try it yourself.

**Dokładna treść wywołania API dla Prompt #2:**  
- Endpoint: ten sam co przy fillu — POST `{base_url}/v1/responses`.  
- **instructions:** dosłownie jeden wyraz: **wykonaj**.  
- **input:** **pełna treść Prompt #1** z artykułu (wyciągnięta przez _extract_prompt1).  
- Oczekiwany wynik: odpowiedź modelu = treść Prompt #2 (gotowy prompt do wklejenia w narzędzie); ta treść jest wstawiana w body w miejsce [PROMPT2_PLACEHOLDER].

Funkcja **_insert_prompt2(body, prompt2_text, is_html)** szuka bloku z PROMPT2_PLACEHOLDER i zamienia go na sformatowaną treść (w HTML — escape + `<pre>`, w MD — blok ```). Gdy blok się nie dopasuje, zamieniane jest pierwsze wystąpienie samego placeholderu.

### 5.8 Normalizacja „Try it yourself” (tylko HTML)

Funkcja **_normalize_try_it_yourself_html(body, slug, tool_name)**. Kroki: (1) Znaleźć sekcję od H3 „Try it yourself…” do następnego H2. (2) Usunąć istniejące akapity z intro do Prompt #1 i Prompt #2 (różne warianty tekstów). (3) Rozpoznać narzędzie: z pierwszego `<pre>` (Recommended tools) lub z parametru tool_name. (4) Pobrać opis: short_description_en z affiliate_tools.yaml, albo type_display z kategorii (np. „Automation platform”). (5) Wstrzyknąć przed pierwszym `<pre>` linię w stylu: „Here is the input (Prompt #1) ready to use with [link] (opis).” (6) Wstrzyknąć przed drugim `<pre>` linię: „Below is the output (Prompt #2)… ready to use with [nazwa] … or in another tool of the same type (opis).” (7) Po drugim `<pre>` wstrzyknąć jedno zdanie CTA (z puli _TRY_CTA_VARIANTS), ewentualnie z linkiem do narzędzia z Prompt #2.

### 5.9 Quality gate (opcjonalnie)

Przy **--quality_gate** przed zapisem uruchamiana jest **check_output_contract(new_body, content_type, quality_strict)** — sprawdzenie, czy w treści są wymagane sekcje (Decision rules, Tradeoffs, Failure modes, SOP, Template 1, Template 2, Try it yourself gdy how-to itd.). Przy niepowodzeniu — ponowne wywołanie API z feedbackiem (do **quality_retries** razy). Po wyczerpaniu prób: artykuł oznaczany jako **blocked** lub zwracany jest **quality_fail** (zależnie od **--block_on_fail**).

### 5.10 Preflight QA (run_preflight_qa)

Sprawdzenia przed uznaniem artykułu za poprawny:  
- **A. Mustache (tylko MD):** Placeholdery {{…}} — dozwolone usunięcie tylko {{PRIMARY_TOOL}}, {{SECONDARY_TOOL}}, {{TOOLS_MENTIONED}} (zastępowane przez fill). Inne usunięte lub dodane → fail.  
- **B. Placeholdery w nawiasach:** Po wykluczeniu sekcji Template 1/2 i bloków kodu — żaden [xxx] (oprócz checkboxów) nie może pozostać.  
- **C. Nagłówki (tylko MD):** H1 i H2 bez zmian (poza dozwolonymi wyjątkami redakcyjnymi).  
- **D. Liczba słów:** Próg zależny od audience (np. beginner 700/1000, intermediate/professional 900/1200) lub min_words_override. Dla HTML liczone na tekście po usunięciu tagów.  
- **E. Wzorce zabronione:** FORBIDDEN_PATTERNS (np. „the best”, „#1”) — obecność w tekście → fail.  
- **F. Try it yourself (gdy content_type how-to):** Wymagana linia descriptor przed Prompt #1 („ready to use with X (…)”), linia przed Prompt #2 („Below is the output (Prompt #2)” … „ready to use with X (AI tool).” lub „in the same or a new thread”). Spójność narzędzia w obu; narzędzie z listy. Wymagane zdanie zachęty po bloku (odniesienie do Prompt #2) — bez literalnej etykiety „Action cue:”.

### 5.11 Zapis po fillu

- **Ścieżka HTML (--html):** Body zapisywane do pliku **content/articles/{stem}.html** z frontmatter w komentarzu na początku. W pliku .md aktualizowany jest **tylko** status na `filled`. Koszty API są rejestrowane.  
- **Ścieżka MD:** Pełna treść (frontmatter + body) zapisywana do tego samego .md; status `filled`. Przy --write przed zapisem tworzona jest kopia zapasowa .bak.

### 5.12 Parametry CLI fill_articles (wybór)

--write, --force, --limit, --since, --slug_contains, --qa / --no-qa, --qa_strict, --block_on_fail, --quality_gate, --quality_retries, --quality_strict, --html, --remap, --skip-prompt2, --prompt2-only, --min-words-override, --style (szczegóły w oryginalnym audycie).

---

*Kolejna część: render do public, pliki i katalogi, przepływ end-to-end — w pliku `audit_workflow_czytelnie_czesc_3.md`.*
