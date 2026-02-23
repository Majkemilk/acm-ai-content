# Kontynuacja pracy nad projektem ACM – start w nowym wątku Agenta

Ten plik zawiera **wszystkie potrzebne informacje**, żeby w **nowym, czystym wątku** Agenta w Cursor od razu kontynuować pracę nad projektem.

---

## Jak zacząć

1. **Przeczytaj ten dokument** (krótkie podsumowanie + ostatnie zmiany).
2. **Przeczytaj `docs/HANDOFF_continue_project.md`** – pełna struktura projektu, config, skrypty, workflow, konwencje, dokumentacja.

---

## Czym jest projekt

- **ACM** (AI Content Automation): automatyczne generowanie **artykułów SEO** z YAML (use case’y → kolejka → szkielety → wypełnienie AI → render do HTML). Jedna strona, jeden hub, statyczny katalog `public/`.
- **Środowisko:** Python (stdlib + urllib do OpenAI), zmienne: `OPENAI_API_KEY`, opcjonalnie `OPENAI_BASE_URL`, `OPENAI_MODEL`.
- **Kluczowe katalogi:** `content/` (config.yaml, use_cases.yaml, queue.yaml, articles/, hubs/, affiliate_tools.yaml), `scripts/`, `templates/`, `public/`, `docs/`, `flowtaro_monitor/` (aplikacja GUI).

---

## Ostatnie wdrożenie: Opcja A + C w generate_use_cases.py

- **Opcja A (replace mode):** Gdy w `content/config.yaml` jest niepuste **suggested_problems**, pierwszy wpis = „hard lock”. Wszystkie wygenerowane use case’y muszą być semantycznie związane z tym problemem. W tym trybie **zapis do use_cases.yaml zastępuje całą listę** nową partią (do `limit`), zamiast dopisywać i capować – dzięki czemu przy limit=3 zawsze zapisane są 3 nowe, a nie 0.
- **Opcja C (fail-fast):** Gdy po deduplikacji nie ma żadnego nowego use case’a **lub** pod hard lock jest mniej niż `limit` nie-duplikatów, skrypt kończy z **exit code 2**. Pipeline (np. Flowtaro Monitor) może na tym przerwać dalsze kroki.

Plik: `scripts/generate_use_cases.py`. Komentarze w kodzie: „Option C: fail-fast”, „Option A: replace mode”.

---

## Ważne pliki i ścieżki

| Co | Gdzie |
|----|--------|
| Konfiguracja workflow | `content/config.yaml` (production_category, hub_slug, sandbox_categories, use_case_batch_size, use_case_audience_pyramid, suggested_problems, category_mode) |
| Use case’y | `content/use_cases.yaml` |
| Kolejka artykułów | `content/queue.yaml` |
| Artykuły (źródła) | `content/articles/*.md` i `*.html` |
| Narzędzia / linki afiliacyjne | `content/affiliate_tools.yaml` |
| Główny handoff (pełny opis projektu) | `docs/HANDOFF_continue_project.md` |
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

---

## Szybki checklist przy kontynuacji

- [ ] Przeczytać **HANDOFF_continue_project.md** w całości.
- [ ] Sprawdzić **content/config.yaml** (suggested_problems, limit, pyramid, category_mode).
- [ ] Pamiętać: **generate_use_cases** przy hard lock = replace + fail-fast (exit 2).
- [ ] **OPENAI_API_KEY** wymagane przy generate_use_cases i fill_articles.

---

*Dokument przygotowany po wdrożeniu Opcji A + C w generate_use_cases.py. Pełny kontekst projektu: docs/HANDOFF_continue_project.md.*
