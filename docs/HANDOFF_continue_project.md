# Kontynuacja pracy nad projektem ACM – informacje dla nowego wątku Agenta

Dokument zbiorczy do szybkiego wejścia w kontekst i kontynuacji pracy w **nowym, czystym wątku** Agenta w Cursor.

---

## 1. Czym jest projekt

- **Nazwa / skrót:** ACM (AI Content Automation).
- **Cel:** Automatyczne generowanie **artykułów SEO** z wejścia YAML (kolejka, use case’y), szablony + AI (OpenAI) do wypełniania, statyczny render do HTML. Strona ma **wiele hubów** (lista artykułów per kategoria), strona główna z linkami do hubów i sekcją „Newest articles”.
- **Środowisko:** Python (stdlib + urllib do API), bez frameworków. Opcjonalnie: `python-docx` dla privacy. Zmienne środowiskowe: `OPENAI_API_KEY`, opcjonalnie `OPENAI_BASE_URL`, `OPENAI_MODEL`.
- **Deploy:** Statyczny katalog `public/` (np. Cloudflare Pages) – `index.html`, `articles/{slug}/`, `hubs/{slug}/` (wiele hubów), `sitemap.xml`, `robots.txt`, `privacy.html`.
- **Aplikacja desktopowa:** **Flowtaro Monitor** (`flowtaro_monitor/`) – GUI (tkinter) do konfiguracji, generowania use case’ów, kolejki, szkieletów, wypełniania, odświeżania artykułów, czyszczenia nieżywych.
- **Subprojekt:** **prompt-generator** – osobny projekt Next.js (TypeScript, Tailwind, App Router) w katalogu `prompt-generator/`; Stripe, OpenAI, Resend, react-hook-form, zod.

---

## 2. Struktura katalogów (kluczowe)

```
content/
  config.yaml          # production_category, hub_slug, hub_title, hubs (lista), sandbox_categories, category_mode, suggested_problems, use_case_*
  use_cases.yaml        # lista use case’ów (problem, suggested_content_type, category_slug, status)
  queue.yaml            # kolejka do generowania artykułów (title, content_type, category_slug, primary_tool, ...)
  articles/             # .md i .html artykułów (frontmatter + body); status filled = production
  hubs/                 # .md plików hubów – jeden plik na hub: {slug}.md (np. ai-marketing-automation.md, marketplaces-products.md)
  affiliate_tools.yaml  # narzędzia (name, category, affiliate_link, short_description_en) do linkowania w artykułach
  articles_archive/     # zarchiwizowane pliki (np. po clean_non_live_articles)
  articles_excluded_from_fill/  # artykuły przeniesione „poza” fill – nie są wypełniane przez fill_articles

templates/             # szablony artykułów (article.html, hub.html, index.html, best.md, guide.md, …)
scripts/               # wszystkie skrypty (render_site, generate_*, fill_articles, content_index, check_try_it_yourself_pre, fix_template2_pre_close, clean_non_live_articles, …)
public/                # output statyczny (index.html, articles/, hubs/{slug}/, sitemap.xml, assets/, images/)
docs/                  # dokumentacja (config reference, audyty, prompt reference, handoff)
flowtaro_monitor/      # aplikacja GUI (main.py, _monitor_data.py, _run_scripts.py, i18n, config tab, Generuj artykuły, Refresh, Use case’y, …)
prompt-generator/      # subprojekt Next.js (App Router, TypeScript, Tailwind; stripe, openai, resend, react-hook-form, zod)
```

---

## 3. Config: `content/config.yaml`

Obecny stan i znaczenie pól (szczegóły w `docs/config_yaml_reference.md`):

| Pole | Znaczenie |
|------|-----------|
| **production_category** | Główna kategoria (np. pierwszy hub); używane przy braku listy `hubs`; w FlowMonitor „Kategoria główna huba”. |
| **hub_slug** | Slug „głównego” huba w URL; używany przy braku listy `hubs`. |
| **hub_title** | Tytuł jednego huba przy braku listy `hubs`. |
| **hubs** | **Lista hubów** – każdy: `slug`, `category`, `title`. Gdy niepusta, **generate_hubs**, **render_site** i **generate_sitemap** używają jej; artykuły są przypisywane do huba po `meta.category` == `hub["category"]`. Artykuły bez `category` trafiają do pierwszego huba z listy. |
| **category_mode** | `production_only` \| `preserve_sandbox` – przy generowaniu artykułów: czy wymuszać jedną kategorię (production), czy zachować category_slug z kolejki, jeśli jest w whitelist (production + sandbox). |
| **sandbox_categories** | Dodatkowe dozwolone kategorie (np. `marketplaces-products`, `automation workflows`). Używane przez generate_use_cases i generate_articles (allowed_categories). W FlowMonitor lista kategorii w dropdownie = **production_category + sandbox_categories**. |
| **suggested_problems** | Lista problemów do preferowania w use case’ach; pierwszy wpis = „hard lock” (wszystkie use case’y muszą być z tego samego obszaru; replace mode w use_cases.yaml). |
| **use_case_batch_size**, **use_case_audience_pyramid** | Liczba use case’ów na run, podział beginner/intermediate/professional. |

**Ważne:** Zapis konfiguracji z **FlowMonitor** (Konfiguracja → Zapisz) wywołuje `config_manager.write_config()`, który **nie zapisuje** pól `hubs` ani `hub_title` – nadpisuje plik tylko production_category, hub_slug, sandbox_categories, suggested_problems, category_mode, use_case_*. Po zapisie z aplikacji lista **hubs** w pliku znika. Trzeba albo rozszerzyć write_config o zachowanie/odczyt hubs, albo nie zapisywać config z GUI przy wielu hubach.

---

## 4. Główne skrypty i workflow

Kolejność typowa:

1. **Use case’y** → **Kolejka** → **Szkielety artykułów** → **Wypełnienie (AI)** → **Hub + render + sitemap**

### 4.1 Generowanie use case’ów

```bash
python scripts/generate_use_cases.py [--category SLUG] [--content-type TYPE]
```

- Czyta `content/config.yaml` (kategorie z production + sandbox, **suggested_problems**, use_case_batch_size, use_case_audience_pyramid), `content/use_cases.yaml`, `content/articles/*.md` (słowa kluczowe).
- **Prompt (instructions):** „You are a content strategist. Your task is to suggest new business problems / use cases for blog content in the **Market-places products space or AI marketing automation space**. Output ONLY a valid JSON array…” (problem, suggested_content_type, category_slug).
- Przy niepustym **suggested_problems** pierwszy wpis = hard lock; zapis może zastąpić całą listę use case’ów (replace mode). Exit 2 przy 0 nowych lub za mało pod hard lock.
- Kategorie dozwolone: `get_categories_from_config()` = production_category + sandbox_categories.

### 4.2 Kolejka z use case’ów

```bash
python scripts/generate_queue.py [--dry-run]
```

- Use case’y ze statusem `todo` → wpisy w `content/queue.yaml`; status → `generated`.

### 4.3 Generowanie szkieletów artykułów

```bash
python scripts/generate_articles.py [--category SLUG]
```

- Kolejka `todo` → szablony z `templates/` → pliki w `content/articles/`. Category w artykule z kolejki (normalize_category według category_mode i sandbox).

### 4.4 Wypełnianie artykułów (AI)

```bash
python scripts/fill_articles.py [--write] [--html] [--limit N] [--since YYYY-MM-DD] [--slug_contains TEXT] [--force] [--no-qa]
```

- Placeholdery w .md lub generacja body HTML (--html). Zapis .html, status `filled` w .md. Wymaga OPENAI_API_KEY. Sekcja „Try it yourself” z Prompt #1 / Prompt #2; sanitacja i walidacja bloków `<pre>` w HTML.

### 4.5 Generowanie hubów

```bash
python scripts/generate_hubs.py
```

- **Multi-hub:** `get_hubs_list(config)` → dla każdego huba filtruje artykuły po `meta.category` == hub["category"], buduje treść, zapisuje `content/hubs/{slug}.md`.

### 4.6 Render strony

```bash
python scripts/render_site.py
```

- Artykuły (get_production_articles) → `public/articles/{slug}/index.html`. Dla każdego huba z get_hubs_list: `content/hubs/{slug}.md` → `public/hubs/{slug}/index.html`. Strona główna: linki do **wszystkich** hubów + „Newest articles”.

### 4.7 Sitemap

```bash
python scripts/generate_sitemap.py
```

- Wszystkie huby (get_hubs_list) + wszystkie production articles → `public/sitemap.xml`.

### 4.8 Inne skrypty

- **clean_non_live_articles.py** – archiwizacja content (status ≠ filled), usuwanie **stale** katalogów z `public/articles/` (slug nie w get_production_articles). `--public-only --dry-run` / `--confirm`.
- **check_try_it_yourself_pre.py** – skan `content/articles/*.html` lub `public/articles/*/index.html`: czy pierwszy `<pre>` w „Try it yourself” zawiera tylko Prompt #1, czy Template 2 nie jest zamknięty przez `</p>`.
- **fix_template2_pre_close.py** – zamiana błędnego `</p>` na `</pre>` w bloku Template 2 w podanych plikach HTML.

---

## 5. Ważne konwencje

- **get_production_articles()** (`content_index.py`): zwraca wszystkie artykuły z `content/articles/` o **statusie `filled`** (blocked pomijane). **Nie** filtruje po kategorii – filtrowanie per hub robią generate_hubs i render_site na podstawie `meta.category` i listy hubów.
- **get_hubs_list(config):** jeśli config ma niepustą listę **hubs**, zwraca ją; w przeciwnym razie jeden hub z production_category, hub_slug, hub_title.
- **Artykuły:** frontmatter: `title`, `content_type`, `category` / `category_slug`, `primary_keyword`, `tools`, `last_updated`, `status`. Badge kategorii linkuje do `/hubs/{category_slug}/`.
- **FlowMonitor:** lista kategorii w UI = **get_use_case_defaults()["categories"]** = production_category + sandbox_categories (nie z listy hubs). Żeby nowa kategoria (np. nowy hub) była wybieralna w aplikacji, musi być w **sandbox_categories**.

---

## 6. Dokumentacja w repo (wybór)

| Plik | Zawartość |
|------|-----------|
| **docs/config_yaml_reference.md** | Znaczenie pól config.yaml. |
| **docs/generate_use_cases_prompt_reference.md** | Prompt use case’ów, instructions + user message. |
| **docs/recommendation_multi_hub_structure.md** | Rekomendacja multi-hub – **zrealizowana** (hubs w config, get_hubs_list, filtrowanie po category). |
| **docs/audit-remove-archive-published-articles.md** | Usuwanie/archiwizacja nieżywych artykułów, czyszczenie public/articles. |
| **docs/audit_full_article_generation_workflow.md** | Pełny workflow generowania artykułów. |
| **README.md** | Opis projektu, komendy, sandbox, internal linking. |

---

## 7. Stan wdrożenia / znane decyzje

- **Layout nawigacji (aktualny):** Logo na samej górze, pod nim pasek nawigacji w tym samym obrębie co podtytuł (kontener `max-w-4xl mx-auto px-4`). Szablony: `templates/index.html`, `hub.html`, `article.html` – sekcja z logo + `<!-- NAV -->` w jednej sekcji. Fallbacki w `render_site.py` (index, hub/article, privacy) używają tej samej struktury (bez `<header>`).
- **Multi-hub (wdrożone):** Lista **hubs** w config; generate_hubs, render_site, generate_sitemap iterują po get_hubs_list(); artykuły przypisywane do huba po `meta.category`; strona główna linkuje do wszystkich hubów.
- **Zapis config z FlowMonitor:** write_config **nie** zapisuje `hubs` ani `hub_title` – po „Zapisz” w Konfiguracji te pola znikają z pliku. Do naprawy lub obchodzenia (edycja config ręcznie przy wielu hubach).
- **Sekcja „Try it yourself” w artykułach:** Prompt #1 (meta-prompt) w pierwszym `<pre>`; Prompt #2 w drugim. Skrypty check_try_it_yourself_pre i fix_template2_pre_close naprawiają błąd „Template 2 zamknięte przez </p>”.
- **Stale katalogi w public/articles:** render_site nie usuwa katalogów; żeby zdjąć artykuły z WWW (404), trzeba uruchomić clean_non_live_articles.py --public-only --confirm (po zmianie listy production).
- **generate_use_cases:** prompt obejmuje „Market-places products space or AI marketing automation space”; output = tylko JSON array (problem, suggested_content_type, category_slug).

---

## 8. Szybki checklist przy kontynuacji

- [ ] Przeczytać **content/config.yaml** – sprawdzić **hubs** (lista), **sandbox_categories**, **category_mode**. Pamiętać, że zapis z FlowMonitor nadpisuje plik bez hubs.
- [ ] **get_production_articles()** zwraca wszystkie status=filled; przypisanie do huba po **meta.category** i listy hubów.
- [ ] Nowa kategoria w UI FlowMonitor = dodać ją do **sandbox_categories** w config (oraz ewentualnie do listy **hubs**).
- [ ] Środowisko: **OPENAI_API_KEY** (generate_use_cases, fill_articles); opcjonalnie OPENAI_BASE_URL, OPENAI_MODEL.
- [ ] Przy czyszczeniu WWW: **clean_non_live_articles.py --public-only --dry-run** (podgląd), potem **--confirm**; potem push `public/`.
- [ ] Prompt use case’ów: **scripts/generate_use_cases.py** (instructions) – „Market-places products space or AI marketing automation space”.

---

*Ostatnia aktualizacja handoffu: stan po wdrożeniu multi-hub, sandbox_categories z marketplaces-products, prompt use case’ów (Market-places / AI marketing), skrypty check/fix Try it yourself i clean_non_live_articles. Config może mieć production_category/hub_slug ustawione na któryś z hubów; lista hubs w pliku decyduje o renderze wielu hubów.*
