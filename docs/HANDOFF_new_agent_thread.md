# Kontynuacja pracy nad projektem ACM – start w nowym wątku Agenta

**Przygotowano do handoffu** – dokument gotowy do wklejenia / odesłania w nowym wątku Cursor, żeby kontynuować pracę nad projektem.

*Ostatnia aktualizacja handoffu: 2026-03-01.*

---

Ten plik zawiera **wszystkie potrzebne informacje**, żeby w **nowym, czystym wątku** Agenta w Cursor od razu kontynuować pracę nad projektem.

---

## Jak zacząć

1. **Przeczytaj ten dokument** (krótkie podsumowanie + ostatnie zmiany).
2. **Przeczytaj `docs/HANDOFF_continue_project.md`** – pełna struktura projektu, config, skrypty, workflow, konwencje, dokumentacja.

---

## Czym jest projekt

- **ACM** (AI Content Automation): automatyczne generowanie **artykułów SEO** z YAML (use case’y → kolejka → szkielety → wypełnienie AI → render do HTML). Wiele hubów, strona główna z linkami do hubów i „Newest articles”, statyczny katalog `public/`.
- **Środowisko:** Python (stdlib + urllib do OpenAI), zmienne: `OPENAI_API_KEY`, opcjonalnie `OPENAI_BASE_URL`, `OPENAI_MODEL`.
- **Kluczowe katalogi:** `content/` (config.yaml, use_cases.yaml, queue.yaml, articles/, hubs/, affiliate_tools.yaml), `scripts/`, `templates/`, `public/`, `docs/`, `flowtaro_monitor/` (aplikacja GUI).

---

## Auto-korekta instrukcji use case’ów przy zapisie config

- Przy **zapisie** `content/config.yaml` (FlowMonitor → Zapisz) aktualizowany jest plik **`content/use_case_allowed_categories.json`** (lista `allowed_categories` + `scope_description` z hubów i sandbox).
- **generate_use_cases.py** czyta stamtąd listę dozwolonych kategorii i opis przestrzeni; jeśli plik nie istnieje lub config jest nowszy, skrypt sam wywołuje sync i zapisuje plik.
- Po **ręcznej** edycji configu warto uruchomić `python scripts/sync_use_case_categories.py`, żeby pipeline widział aktualne kategorie.

---

## Ostatnia sesja: layout nawigacji (logo + pasek)

- **Logo na górze, pasek nawigacji poniżej:** W szablonach (`templates/index.html`, `hub.html`, `article.html`, `search.html`) i we **wszystkich fallbackach** w `scripts/render_site.py` nie ma już `<header class="site-header">`. Logo jest na samej górze, pod nim pasek nawigacji.
- **Spójne marginesy (szerokość bloku):** Pasek nawigacji jest w **tym samym obrębie co podtytuł** (tekst „Flowtaro is an independent review…”) – kontener `max-w-4xl mx-auto px-4`. Sekcja hero ma osobny `max-w-4xl mx-auto`; sekcja about ma `max-w-4xl mx-auto px-4` – nav i about są w jednej szerokości.
- **Struktura w szablonach:** `<section class="bg-white pt-6 pb-6"><div class="max-w-4xl mx-auto px-4"><div class="text-center">logo</div><div class="mt-6"><!-- NAV --></div></div></section>`.
- **Nav:** `_build_nav_html(hubs)` w `render_site.py` buduje linki Home | hub1 | hub2 (etykiety z `NAV_LABELS` / hub title). Style: `.site-nav`, `.site-nav-link`, `.site-nav-sep` w `public/assets/styles.css`.
- Po zmianach w szablonach lub w `render_site.py` trzeba uruchomić `python scripts/render_site.py`, żeby zaktualizować `public/`.

---

## Wcześniejsze wdrożenie: Opcja A + C w generate_use_cases.py

- **Opcja A (replace mode):** Gdy w `content/config.yaml` jest niepuste **suggested_problems**, pierwszy wpis = „hard lock”. Zapis do use_cases.yaml **zastępuje całą listę** nową partią (do limit).
- **Opcja C (fail-fast):** Gdy 0 nowych use case’ów lub pod hard lock mniej niż limit nie-duplikatów → **exit code 2**.

Plik: `scripts/generate_use_cases.py`. Komentarze: „Option C: fail-fast”, „Option A: replace mode”.

---

## Ważne pliki i ścieżki

| Co | Gdzie |
|----|--------|
| Konfiguracja workflow | `content/config.yaml` (production_category, hub_slug, **hubs**, sandbox_categories, use_case_batch_size, use_case_audience_pyramid, suggested_problems, category_mode) |
| Use case’y | `content/use_cases.yaml` |
| Kolejka artykułów | `content/queue.yaml` |
| Artykuły (źródła) | `content/articles/*.md` i `*.html` |
| Narzędzia / linki afiliacyjne | `content/affiliate_tools.yaml` |
| Dozwolone kategorie (use case’y) | `content/use_case_allowed_categories.json` (generowany przy zapisie config; sync: `scripts/sync_use_case_categories.py`) |
| Szablony strony | `templates/index.html`, `hub.html`, `article.html`, `search.html` (placeholder `<!-- NAV -->`, sekcja logo+nav w `max-w-4xl mx-auto px-4`) |
| Render strony | `scripts/render_site.py` (_build_nav_html, _update_index, _write_privacy_page, fallbacki bez header) |
| Główny handoff (pełny opis) | `docs/HANDOFF_continue_project.md` |
| Referencja config | `docs/config_yaml_reference.md` |
| Referencja promptu use case’ów | `docs/generate_use_cases_prompt_reference.md` |
| Aplikacja GUI | `flowtaro_monitor/main.py` (Tkinter), i18n w `flowtaro_monitor/i18n.py` |

---

## Pipeline (kolejność skryptów)

1. **generate_use_cases.py** – generuje use case’y (przy hard lock: replace mode; exit 2 przy 0 nowych lub &lt; limit).
2. **generate_queue.py** – z use case’ów ze statusem `todo` uzupełnia `queue.yaml`, ustawia im status `generated`.
3. **generate_articles.py** – z kolejki (status `todo`) tworzy szkielety .md w `content/articles/`.
4. **fill_articles.py** – wypełnia treść (AI), generuje Prompt #2, wybór narzędzi (tools w frontmatter), zapis .html, QA (--block_on_fail → status blocked).
5. **generate_hubs.py**, **generate_sitemap.py**, **render_site.py** – hub, sitemap, render do `public/`.

Refresh artykułów: **refresh_articles.py** (wywołuje m.in. fill_articles z --html, opcjonalnie --prompt2-only dla placeholderów Prompt #2).

---

## Kody powrotu (ważne dla orchestracji)

- **generate_use_cases.py:** exit **2** = brak nowych use case’ów (wszystkie duplikaty) lub pod hard lock mniej niż `limit` nie-duplikatów. Powinno zatrzymać dalsze kroki.
- **fill_articles.py:** exit **2** = QA nie przeszła (np. --block_on_fail); artykuł może dostać status `blocked`.

---

## Konwencje

- **tools** w frontmatter (lista 1–5 narzędzi z affiliate_tools); „Prompt #1 (to a general AI)” → co najmniej jedno narzędzie typu general AI (np. ChatGPT, Claude).
- **category_mode** w config: `production_only` (wszystkie do production_category) lub `preserve_sandbox` (zachowanie sandbox_categories).
- **Badge poziomu trudności** w artykułach z `audience_type` (beginner/intermediate/professional) – render_site; artykuły 2026-02-18 do 2026-02-20 bez badge’a.
- **Kategoria w Konfiguracji vs w Generuj artykuły:** Config (production_category + sandbox_categories) = źródło listy kategorii na stałe; pole „Kategoria (to uruchomienie)” w zakładce Generuj artykuły = filtr na jedno uruchomienie („dowolna” lub jedna konkretna). Domyślnie „— dowolna”.
- **Zapis config z FlowMonitor:** write_config **nie** zapisuje pól `hubs` ani `hub_title` – przy wielu hubach edytuj config ręcznie po zapisie z GUI.

---

## Szybki checklist przy kontynuacji

- [ ] Przeczytać **HANDOFF_continue_project.md** w całości.
- [ ] Sprawdzić **content/config.yaml** (hubs, suggested_problems, use_case_audience_pyramid, category_mode).
- [ ] Pamiętać: **generate_use_cases** przy hard lock = replace + fail-fast (exit 2).
- [ ] **OPENAI_API_KEY** wymagane przy generate_use_cases i fill_articles.
- [ ] Przeczytać **HANDOFF_continue_project.md** w całości.
- [ ] Sprawdzić **content/config.yaml** (hubs, suggested_problems, use_case_audience_pyramid, category_mode).
- [ ] Pamiętać: **generate_use_cases** przy hard lock = replace + fail-fast (exit 2).
- [ ] **OPENAI_API_KEY** wymagane przy generate_use_cases i fill_articles.
- [ ] Layout: **logo na górze**, **pasek nawigacji poniżej**, w tej samej szerokości co podtytuł (`max-w-4xl mx-auto px-4`). Zmiany w szablonach/render_site → uruchomić `python scripts/render_site.py`.
- [ ] **Dozwolone kategorie use case’ów:** przy zapisie config (GUI) aktualizowany jest `content/use_case_allowed_categories.json`; po ręcznej edycji configu uruchomić `python scripts/sync_use_case_categories.py`.

---

## Jak przekazać pracę do nowego wątku

1. W nowym wątku (chat) w Cursor wklej lub napisz np.:  
   *„Kontynuuję projekt ACM. Przeczytaj docs/HANDOFF_new_agent_thread.md i docs/HANDOFF_continue_project.md, potem [opisz konkretne zadanie].”*
2. Możesz dołączyć ten plik (`docs/HANDOFF_new_agent_thread.md`) lub jego fragment jako kontekst.
3. Dla zadań związanych z config/skryptami/pipeline – podaj ścieżkę do `content/config.yaml` lub konkretnego skryptu.

---

*Ostatnia aktualizacja handoffu: 2026-03-01. Layout: logo na górze, nav poniżej, te same marginesy co podtytuł. Auto-sync dozwolonych kategorii przy zapisie config. Pełny kontekst: docs/HANDOFF_continue_project.md.*
