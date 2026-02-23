# Kontynuacja pracy nad projektem ACM – informacje dla nowego wątku Agenta

Dokument zbiorczy do szybkiego wejścia w kontekst i kontynuacji pracy w **nowym, czystym wątku** Agenta w Cursor.

---

## 1. Czym jest projekt

- **Nazwa / skrót:** ACM (AI Content Automation).
- **Cel:** Automatyczne generowanie **artykułów SEO** z wejścia YAML (kolejka, use case’y), szablony + AI (OpenAI) do wypełniania, statyczny render do HTML. Strona ma jeden główny **hub** (lista artykułów), strona główna z „Newest articles” i linkiem „All articles” do huba.
- **Środowisko:** Python (stdlib + urllib do API), bez frameworków. Opcjonalnie: `python-docx` dla privacy. Zmienne środowiskowe: `OPENAI_API_KEY`, opcjonalnie `OPENAI_BASE_URL`, `OPENAI_MODEL`.
- **Deploy:** Statyczny katalog `public/` (np. Cloudflare Pages) – `index.html`, `articles/{slug}/`, `hubs/{slug}/`, `sitemap.xml`, `robots.txt`, `privacy.html`.

---

## 2. Struktura katalogów (kluczowe)

```
content/
  config.yaml          # production_category, hub_slug, sandbox_categories
  use_cases.yaml       # lista use case’ów (problem, suggested_content_type, category_slug, status)
  queue.yaml           # kolejka do generowania artykułów (title, content_type, category_slug, primary_tool, ...)
  articles/            # .md i .html artykułów (frontmatter + body)
  hubs/                # .md plików hubów (jeden plik = production hub, nazwa = production_category)
  affiliate_tools.yaml # narzędzia (name, affiliate_link) do linkowania w artykułach
  articles_excluded_from_fill/  # artykuły przeniesione „poza” fill – nie są wypełniane przez fill_articles

templates/             # szablony artykułów (article.html, hub.html, index.html, best.md, guide.md, …)
scripts/               # wszystkie skrypty (render_site, generate_*, fill_articles, content_index, …)
public/                # output statyczny (index.html, articles/, hubs/, sitemap.xml, assets/, images/)
docs/                  # dokumentacja (config reference, multi-hub recommendation, audyty, prompt reference)
```

---

## 3. Config: `content/config.yaml`

Obecny stan i znaczenie pól (szczegóły w `docs/config_yaml_reference.md`):

| Pole | Obecna wartość | Znaczenie |
|------|----------------|-----------|
| **production_category** | `ai-marketing-automation` | Nazwa **pliku** huba w `content/hubs/`: `content/hubs/ai-marketing-automation.md`. Używane przez render_site i generate_hubs. |
| **hub_slug** | `ai-marketing-automation` | **URL** huba: `/hubs/ai-marketing-automation/`. Z tego slugu powstaje `public/hubs/ai-marketing-automation/index.html`. Link „All articles” i sitemap używają tego slugu. |
| **sandbox_categories** | `LLM SEO`, `Visual automation and integrations` | Dodatkowe dozwolone kategorie przy **generowaniu use case’ów** (generate_use_cases). Nie filtrują renderowanych artykułów – get_production_articles() zwraca wszystkie nie-blocked. |

Zasada: **production_category** = który plik huba; **hub_slug** = pod jakim adresem; **sandbox_categories** = z jakich kategorii model może wybierać przy use case’ach.

**Kategoria w Konfiguracji vs w zakładce Generuj artykuły:** W Konfiguracji ustawiasz **listę kategorii na stałe** (kategoria główna huba + kategorie sandbox) oraz tryb (production_only / preserve_sandbox). Ta lista jest używana w całym workflow i **źródłem opcji** w zakładce Generuj artykuły. Pole **„Kategoria (to uruchomienie)”** w tej zakładce to **filtr na jedno uruchomienie**: „dowolna” = model może przypisać use case’om dowolną z listy z config; wybór konkretnej kategorii = w tym runie wszystkie use case’y dostaną tylko ten jeden category_slug. Domyślnie pozostaje „— dowolna”.

---

## 4. Główne skrypty i workflow

Kolejność typowa:

1. **Use case’y** → **Kolejka** → **Szkielety artykułów** → **Wypełnienie (AI)** → **Hub + render**

### 4.1 Generowanie use case’ów

```bash
python scripts/generate_use_cases.py [--limit N] [--category SLUG] [--content-type TYPE]
```

- Czyta `content/config.yaml` (kategorie, **suggested_problems**, use_case_batch_size, use_case_audience_pyramid), `content/use_cases.yaml` (istniejące), `content/articles/*.md` (słowa kluczowe, max 50).
- Wysyła do OpenAI Responses API prompt (instructions + user message); odpowiedź = JSON array z polami: problem, suggested_content_type, category_slug.
- **Opcja A (replace mode):** Gdy w config jest niepuste **suggested_problems**, skrypt traktuje pierwszy wpis jako „hard lock” – wszystkie wygenerowane use case’y muszą być semantycznie związane z tym problemem. W tym trybie zapis do `use_cases.yaml` **zastępuje** całą listę nową partią (do `limit`), zamiast dopisywać i capować.
- **Opcja C (fail-fast):** Jeśli po deduplikacji nie ma żadnego nowego use case’a do zapisania, skrypt kończy z **kodem 2** (pipeline może przerwać dalsze kroki). Również exit 2, gdy pod hard lock zostało mniej niż `limit` nie-duplikatów.
- Bez hard lock: dopisuje nowe wpisy ze statusem `todo`, cap listy na `limit`.
- Opcjonalnie: `--category`, `--content-type` (how-to, guide, best, comparison).
- Szczegóły promptu: `docs/generate_use_cases_prompt_reference.md`.

### 4.2 Kolejka z use case’ów

```bash
python scripts/generate_queue.py [--dry-run]
```

- Bierze z `content/use_cases.yaml` tylko wpisy ze **statusem `todo`**.
- Dla każdego tworzy wpis w `content/queue.yaml` (title, content_type, category_slug, primary_tool, …).
- Po dodaniu do kolejki ustawia tym use case’om status **`generated`** w `content/use_cases.yaml`.

### 4.3 Generowanie szkieletów artykułów

```bash
python scripts/generate_articles.py
```

- Czyta `content/queue.yaml`, wpisy ze statusem **`todo`**.
- Dla każdego: wybiera szablon z `templates/` po `content_type` (guide, how-to, best, comparison, review), podstawia zmienne z kolejki, zapisuje plik w `content/articles/` (np. `YYYY-MM-DD-tytul-slug.md`).
- Po zapisaniu ustawia status wpisu w kolejce na **`generated`**.

### 4.4 Wypełnianie artykułów (AI)

```bash
python scripts/fill_articles.py [--write] [--html] [--limit N] [--since YYYY-MM-DD] [--slug_contains TEXT] [--force] [--no-qa]
```

- Przetwarza pliki **.md** z `content/articles/` (nie z `articles_excluded_from_fill`).
- Zastępuje placeholdery `[...]` treścią z API (lub z `--html` generuje cały body jako HTML).
- Przy `--html --write` zapisuje wynik do **.html** i w .md ustawia **status `filled`** (bez zmiany treści .md).
- Domyślnie dry-run; `--write` zapisuje zmiany (backup .bak). Wymaga `OPENAI_API_KEY`.

### 4.5 Generowanie huba

```bash
python scripts/generate_hubs.py
```

- Czyta `content/config.yaml` → **production_category**.
- Pobiera listę artykułów przez `get_production_articles()` (wszystkie nie-blocked).
- Buduje treść huba: H1, intro (bez „Start here”), sekcje po **content_type** (Guides, How-to, Reviews, Comparisons, Best).
- Zapisuje **jeden plik**: `content/hubs/{production_category}.md` (obecnie `ai-marketing-automation.md`).

### 4.6 Render strony (MD/HTML → public)

```bash
python scripts/render_site.py
```

- **Artykuły:** `content/articles/` (.md lub .html – .html ma pierwszeństwo przy tym samym stem) → `public/articles/{slug}/index.html`. Na każdej stronie artykułu: H1 (tytuł), meta (kategoria, data, czas czytania, lead), body, „Read next”, disclosure.
- **Hub:** Czyta `content/hubs/{production_category}.md`, renderuje do **`public/hubs/{hub_slug}/index.html`** (nie do folderu po production_category – używany jest hub_slug).
- **Strona główna:** `public/index.html` – link „All articles” → `/hubs/{hub_slug}/`, sekcja „Newest articles” (12 najnowszych).
- **Inne:** privacy, images, assets.

### 4.7 Sitemap

```bash
python scripts/generate_sitemap.py
```

- Generuje `public/sitemap.xml`: wpis dla `/hubs/{hub_slug}/` + wszystkie artykuły z `get_production_articles()`.

---

## 5. Ważne konwencje

- **Artykuły:** frontmatter zawiera m.in. `title`, `content_type`, `category` / `category_slug`, `primary_keyword`, `primary_tool`, `last_updated`, `status`. Badge kategorii w artykule linkuje do `/hubs/{category_slug}/` – żeby nie było 404, **category_slug** w artykułach powinien być równy **hub_slug** (obecnie `ai-marketing-automation`).
- **Hub:** Jeden główny hub; URL zawsze przez **hub_slug** (slug w URL). Plik źródłowy to **production_category** (może być inna nazwa pliku).
- **get_production_articles()** (w `scripts/content_index.py`): zwraca **wszystkie** artykuły z `content/articles/` o statusie ≠ `blocked`. **Nie** filtruje po kategorii – wszystkie trafiają do jednego huba i do sitemapy.
- **content_index.py:** `load_config()` zwraca dict z `production_category`, `hub_slug`, `sandbox_categories`. Używają go: render_site, generate_sitemap, generate_hubs, generate_use_cases.

---

## 6. Dokumentacja w repo (gdzie co znajdziesz)

| Plik | Zawartość |
|------|-----------|
| **docs/config_yaml_reference.md** | Znaczenie pól config.yaml (production_category, hub_slug, sandbox_categories) i odniesienia w systemie. |
| **docs/generate_use_cases_prompt_reference.md** | Dokładna treść promptu do generowania use case’ów, co jest „dawane” (instructions + user message), wytyczne, co jest parametryzowane i co można dalej. |
| **docs/recommendation_multi_hub_structure.md** | Rekomendacja: wiele hubów (lista hubów w config, slug w URL, filtrowanie artykułów per hub, generate_hubs i sitemap dla wielu hubów). **Nie wdrożone** – jeden hub. |
| **docs/audit_hub_ai-marketing-automation_index.md** | Audyt strony `public/hubs/ai-marketing-automation/index.html` i olinkowania (po wdrożeniu wariantu ze slugiem). |
| **docs/audit_article_title_above_intro.md** | Dlaczego tytuł artykułu nie był nad „Introduction” i jak to naprawiono (H1 z frontmatter, usunięcie duplikatu z body). |
| **README.md** | Ogólny opis projektu, sandbox, taxonomy, internal linking, komendy (generate_hubs, sitemap, render_site, fill_articles). |

---

## 7. Stan wdrożenia / znane decyzje

- **Jeden hub, URL po slugu:** Wdrożone. W config jest `hub_slug: "ai-marketing-automation"`. Render zapisuje hub do `public/hubs/ai-marketing-automation/`; główna i sitemap linkują tam. Artykuły z `category_slug: ai-marketing-automation` linkują do tego samego URL.
- **Sekcja „Start here” w hubie:** Usunięta z generate_hubs (redundantna z „Newest articles” na głównej). Intro huba bez wzmianki o „Start here”.
- **Tytuł nad „Introduction” w artykułach:** W render_site przed body jest wstawiany H1 z tytułu (frontmatter); pierwszy H1 z body jest usuwany, żeby nie duplikować.
- **fill_articles --html --write:** Po zapisie .html skrypt dopisuje w odpowiadającym .md **tylko** `status: "filled"` (bez zmiany treści .md).
- **articles_excluded_from_fill:** Katalog z artykułami .md przeniesionymi „na bok” – nie są brane pod uwagę przez fill_articles (skrypt czyta tylko z `content/articles/`). Używane jednorazowo przy fill tylko wybranych artykułów.
- **Multi-hub (wiele hubów):** Opisane w `docs/recommendation_multi_hub_structure.md`. Do wdrożenia: lista hubów w config, get_articles_for_hub(slug), render i sitemap po wielu hubach, ujednolicenie category_slug w artykułach ze slugami hubów.

---

## 8. Ostatnie wdrożenia (dla nowego wątku Agenta)

- **generate_use_cases.py – Opcja A + C (wdrożone):**
  - **Opcja A (replace mode):** Gdy w `config.yaml` jest `suggested_problems` z co najmniej jednym wpisem, skrypt używa pierwszego jako „hard lock” – generowane use case’y muszą być semantycznie zgodne z tym problemem (walidacja `_is_locked_to_problem`). W tym trybie **zapis do use_cases.yaml zastępuje całą listę** nową partią (`new_use_cases[:limit]`), zamiast dopisywać do istniejących i capować. Dzięki temu przy limit=3 i hard lock zawsze zapisane są 3 nowe use case’y, a nie 0 (gdy stara logika „existing + new” odcinała nowe przy pełnym pliku).
  - **Opcja C (fail-fast):** Gdy po deduplikacji nie ma żadnego nowego use case’a, skrypt kończy z **exit 2**. Również exit 2, gdy pod hard lock liczba nie-duplikatów &lt; limit. Aplikacja/orchestracja może sprawdzać kod powrotu i nie uruchamiać dalszych kroków (kolejka, szkielety, fill).
- **Pozostały kontekst:** fill_articles (Prompt #1/#2, QA, tools w frontmatter), refresh_articles (--html, prompt2-only), category_mode (production_only / preserve_sandbox), audience badges w render_site – szczegóły w poprzednich sekcjach i w docs.

---

## 9. Szybki checklist przy kontynuacji

- [ ] Przeczytać **config.yaml** i **docs/config_yaml_reference.md** – żeby nie pomylić production_category z hub_slug.
- [ ] Pamiętać, że **get_production_articles() nie filtruje po kategorii** – wszystkie nie-blocked idą do jednego huba i sitemapy.
- [ ] Przy zmianach w promptach use case’ów – **docs/generate_use_cases_prompt_reference.md** ma pełną specyfikację i miejsca do parametryzacji.
- [ ] Przy pracy nad wieloma hubami – **docs/recommendation_multi_hub_structure.md** (kolejność wdrożenia, pliki do zmiany).
- [ ] Środowisko: **OPENAI_API_KEY** (obligatoryjne przy generate_use_cases i fill_articles); opcjonalnie OPENAI_BASE_URL, OPENAI_MODEL.
- [ ] **generate_use_cases:** przy hard lock (suggested_problems) działa tryb replace + fail-fast (exit 2 przy 0 nowych lub &lt; limit). Pipeline powinien sprawdzać kod powrotu.

---

*Ostatnia aktualizacja handoffu: wdrożenie Opcji A + C w generate_use_cases.py (replace mode przy hard lock, fail-fast przy 0 nowych / &lt; limit). Stan docs i config jak wyżej.*
