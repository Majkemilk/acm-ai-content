# Audyt: trzy artykuły z 22.02, linki afiliacyjne i puste mapowanie

## 1. Artykuły objęte audytem

- `2026-02-22-how-to-streamline-content-approval-processes-using-ai-tools-to-reduce-bottlenecks.audience_intermediate.md`
- `2026-02-22-how-to-integrate-ai-tools-for-automating-multi-channel-marketing-reporting.audience_intermediate.md`
- `2026-02-22-how-to-automate-troubleshooting-workflows-for-api-error-handling-in-marketing-tools.audience_professional.md`

---

## 2. Czy artykuły zawierają wszystkie wymagane elementy?

**Odniesienie:** szablon `templates/how-to.md` (nagłówki H2 i H3).

| Wymagana sekcja / element | Art. 1 (streamline) | Art. 2 (multi-channel) | Art. 3 (troubleshooting) |
|---------------------------|----------------------|--------------------------|----------------------------|
| Verification policy       | tak                  | tak                      | tak                       |
| Introduction              | tak (wypełniona)     | tak (wypełniona)         | tak (wypełniona)          |
| What you need to know first | tak (wypełniona)   | tak (wypełniona)         | tak (wypełniona)          |
| Main content              | tak                  | tak                      | tak                       |
| → Decision rules          | tak                  | tak                      | tak                       |
| → Tradeoffs               | tak                  | tak                      | tak                       |
| → Failure modes           | tak                  | tak                      | tak                       |
| → SOP checklist           | tak                  | tak                      | tak                       |
| → Template 1              | tak                  | tak                      | tak                       |
| → Template 2              | tak                  | tak                      | tak                       |
| Step-by-step workflow      | tak (7 kroków)       | tak (7 kroków)           | tak (7 kroków)            |
| When NOT to use this      | tak                  | tak                      | tak                       |
| FAQ                       | tak (5 punktów)      | tak (5 punktów)          | tak (5 punktów)           |
| Tools mentioned           | **nagłówek tak, treść NIE** (placeholder) | jw. | jw. |
| Internal links            | tak (lista linków)   | tak                      | tak                       |
| CTA                       | **placeholder**      | **placeholder**          | **placeholder**           |
| Disclosure                | **placeholder**      | **placeholder**          | **placeholder**           |
| Pre-publish checklist     | tak                  | tak                      | tak                       |

**Wniosek:** Struktura (wszystkie sekcje H2/H3) jest kompletna. Brakuje **treści** w miejscach, gdzie w szablonie są zmienne mustache, a w kolejce nie ma wartości:

- **Frontmatter:** `primary_tool: "{{PRIMARY_TOOL}}"`, `secondary_tool: "{{SECONDARY_TOOL}}"` – nie zastąpione (w `queue.yaml` te wpisy mają puste `primary_tool` i `secondary_tool`).
- **W treści:** w Verification policy nadal jest tekst „Descriptions of {{PRIMARY_TOOL}} (and {{SECONDARY_TOOL}}…”.
- **Tools mentioned:** sekcja zawiera tylko `{{TOOLS_MENTIONED}}` (brak listy narzędzi).
- **CTA:** `{{CTA_BLOCK}}`.
- **Disclosure:** `{{AFFILIATE_DISCLOSURE}}`.

---

## 3. Czy artykuły zawierają linki afiliacyjne?

**Nie.** W żadnym z trzech artykułów nie ma linków zewnętrznych (np. `](https://…)` ani `href="https://…"`). Są wyłącznie linki wewnętrzne do `/articles/...`. Żadne narzędzia z `affiliate_tools.yaml` nie są wstawione z linkami, bo:

- W kolejce nie ma `primary_tool` / `secondary_tool`, więc przy generowaniu nie powstaje lista narzędzi z linkami.
- `fill_articles` nie zamienia placeholderów mustache i nie wstawia linków afiliacyjnych w tej sekcji.

---

## 4. Dlaczego plik mapowania jest pusty i zakładka „Mapowanie” nic nie pokazuje?

### 4.1 Skąd bierze się zawartość `use_case_tools_mapping.yaml`?

- **Jedyny zapis** do tego pliku odbywa się w **`scripts/generate_queue.py`**, w kroku **AI mapping**:
  - Dla use case’ów ze statusem **`todo`** (z `use_cases.yaml`),
  - których **problem** nie ma jeszcze wpisu w `use_case_tools_mapping.yaml`,
  - skrypt wywołuje API (OpenAI Responses), dostaje przypisanie problem → 1–2 narzędzia,
  - a następnie **dopisuje** nowe wpisy do `use_case_tools_mapping.yaml` i zapisuje plik.

- Zakładka **„Mapowanie”** w aplikacji **tylko odczytuje** ten plik (`flowtaro_monitor/_monitor_data.py`: `get_mapping_data()` → `load_use_case_tools_mapping(MAPPING_PATH)`). Nie zapisuje do niego ani aplikacja, ani `fill_articles`, ani `generate_articles`.

### 4.2 Kiedy mapowanie nie zostaje uzupełnione?

Plik pozostaje pusty (albo bez nowych wpisów), gdy przy uruchomieniu `generate_queue.py`:

1. **Użyto `--no-ai-mapping`** – wtedy AI w ogóle nie jest wywoływane; używane jest tylko to, co już jest w pliku (czyli nic).
2. **Brak `OPENAI_API_KEY`** – w kodzie jest warunek `if api_key:`; przy pustym kluczu krok AI mapping jest pomijany, bez komunikatu w standardowym flow.
3. **Błąd API** – wyjątek z `_fetch_ai_tools_mapping` łapany jest w `except RuntimeError`, skrypt wypisuje „AI mapping skipped (API error): …” i nie zapisuje mapowania.
4. **Brak use case’ów ze statusem `todo`** – `problems_without_mapping` budowane jest tylko z use case’ów o `status == "todo"`. Jeśli wszystkie mają już `status: generated`, nie ma dla kogo uzupełniać mapowania (w takim przypadku nie dodaje się też nowych wpisów do kolejki w tym uruchomieniu).

W Twoim przypadku w `use_cases.yaml` wszystkie trzy use case’y mają **`status: generated`**. Oznacza to, że w **momencie ostatniego uruchomienia** `generate_queue` albo (a) nie było już żadnych `todo`, albo (b) wcześniej, gdy te trzy były jeszcze `todo`, kolejka została uzupełniona **bez** udanego kroku AI mapping (np. brak klucza API lub błąd API). W obu wariantach plik mapowania mógł pozostać pusty.

### 4.3 Dlaczego w kolejce i w artykułach brakuje narzędzi?

W `generate_queue.py` funkcja `build_queue_items()` ustawia `primary_tool` i `secondary_tool` **wyłącznie** z mapowania:

```python
tools = mapping.get(problem.lower()) or []
primary_tool = (tools[0] or "").strip() if tools else ""
secondary_tool = (tools[1] or "").strip() if len(tools) > 1 else ""
```

Jeśli `use_case_tools_mapping.yaml` jest pusty (lub nie ma w nim danego problemu), `mapping.get(problem.lower())` zwraca `[]`, więc wpisy w kolejce dostają **puste** `primary_tool` i `secondary_tool`. Na tej podstawie `generate_articles` i szablony nie mają czego podstawić pod `{{PRIMARY_TOOL}}`, `{{SECONDARY_TOOL}}` i `{{TOOLS_MENTIONED}}`, stąd placeholdery w artykułach i brak listy narzędzi (oraz brak linków afiliacyjnych z tego mechanizmu).

---

## 5. Podsumowanie przyczyn

| Problem | Przyczyna |
|--------|-----------|
| Puste **Tools mentioned**, brak listy narzędzi | W kolejce brak `primary_tool` / `secondary_tool`, bo mapowanie było puste przy budowaniu kolejki. |
| Brak **linków afiliacyjnych** | Nie ma narzędzi w kolejce → nie ma listy narzędzi z linkami w artykule; `update_affiliate_links` nie ma w tekście linków do podmiany. |
| Pusty **use_case_tools_mapping.yaml** | Przy ostatnim uruchomieniu `generate_queue` krok AI mapping nie zapisał pliku: albo `--no-ai-mapping`, albo brak `OPENAI_API_KEY`, albo błąd API, albo brak use case’ów `todo`. |
| Pusta zakładka **Mapowanie** | Zakładka czyta tylko `use_case_tools_mapping.yaml`; skoro plik jest pusty, nie ma co wyświetlić. |

---

## 6. Propozycje naprawy

### 6.1 Uzupełnienie mapowania (żeby kolejne uruchomienia miały narzędzia)

- **Opcja A – ręcznie:** Dodać do `content/use_case_tools_mapping.yaml` wpisy dla tych trzech problemów (tekst problemu dokładnie jak w `use_cases.yaml`, narzędzia z `affiliate_tools.yaml`), np.:
  - `streamline content approval processes using AI tools to reduce bottlenecks` → np. Make, Google Workspace
  - `integrate AI tools for automating multi-channel marketing reporting` → np. Make, 10Web
  - `automate troubleshooting workflows for API error handling in marketing tools` → np. Make, UptimeRobot
- **Opcja B – AI:** Ustawić w `use_cases.yaml` dla tych trzech wpisów ponownie `status: todo`, upewnić się, że `OPENAI_API_KEY` jest ustawione, uruchomić **tylko** `generate_queue.py` (bez `--no-ai-mapping`). Skrypt uzupełni mapowanie i **doda duplikaty** do kolejki (jeśli nie zablokuje tego logika po stronie duplikatów). Dlatego często sensowniejsze jest ręczne uzupełnienie mapowania (Opcja A), a potem ewentualnie **backfill** kolejki/artykułów (patrz niżej).

### 6.2 Już wygenerowane artykuły (te trzy)

- **Kolejka:** W `content/queue.yaml` dla tych trzech tytułów można **ręcznie** uzupełnić `primary_tool` i `secondary_tool` (zgodnie z mapowaniem lub wyborem redakcyjnym).
- **Artykuły .md:**  
  - Albo uruchomić skrypt, który w istniejących plikach .md (np. po dopasowaniu do tytułu/sluga) podstawi pod `{{PRIMARY_TOOL}}`, `{{SECONDARY_TOOL}}`, `{{TOOLS_MENTIONED}}` (oraz ewentualnie CTA/Disclosure) wartości z frontmatteru lub z kolejki.  
  - Albo ręcznie w każdym artykule: poprawić frontmatter, sekcję Tools mentioned (lista z linkami z `affiliate_tools.yaml`), CTA i Disclosure.

### 6.3 Zapobieganie na przyszłość

- Przed uruchomieniem pełnego workflow (generowanie kolejki z use case’ów) upewnić się, że:
  - **OPENAI_API_KEY** jest ustawione (jeśli chcesz, żeby mapowanie było uzupełniane przez AI), **albo**
  - plik **use_case_tools_mapping.yaml** ma ręczne wpisy dla wszystkich problemów, które trafiają do kolejki.
- W aplikacji: przy uruchomieniu „Generuj kolejkę” (generate_queue) można dodać krótką informację w UI lub w logu: „AI mapping włączony; wymagany OPENAI_API_KEY” oraz ewentualnie po zakończeniu „Mapowanie uzupełnione” / „Mapowanie pominięte (brak klucza API lub błąd)”, żeby od razu było widać, czy plik mapowania został zapisany.

---

## 7. OPENAI_API_KEY i automatyczne ustawianie primary/secondary tool

### 7.1 Sprawdzenie OPENAI_API_KEY

Klucz jest odczytywany **wyłącznie ze zmiennej środowiskowej** `OPENAI_API_KEY` (skrypty nie ładują pliku `.env`). W repozytorium nie ma pliku `.env`. W środowisku, w którym uruchomiono sprawdzenie (terminal w Cursor), zmienna **była ustawiona** (wartość niepusta). Jeśli aplikacja Flowtaro Monitor jest uruchamiana inną drogą (np. skrót, inny terminal), subprocess dziedziczy env po procesie nadrzędnym – więc jeśli przy starcie aplikacji w env nie ma `OPENAI_API_KEY`, krok AI mapping w `generate_queue` i tak go nie zobaczy.

### 7.2 Dlaczego primary_tool i secondary_tool nie były ustawiane

- W `build_queue_items()` wartości brały się **tylko** z `tools_mapping.get(problem.lower())`.
- Mapowanie było puste (AI mapping nie zapisał pliku przy wcześniejszym uruchomieniu), więc dla każdego problemu `tools = []` i w efekcie puste `primary_tool` / `secondary_tool`.

### 7.3 Wdrożone rozwiązanie (bez ręcznego wpisywania)

W **`scripts/generate_queue.py`** wprowadzono:

1. **Fallback domyślnych narzędzi**  
   Gdy dla danego problemu w mapowaniu nie ma wpisu, zamiast pustej listy używana jest lista **default_tools**: do 2 narzędzi z `affiliate_tools.yaml`, z preferencją dla kategorii `referral` (np. Opus Clip, Make), w przeciwnym razie pierwsze dwa narzędzia z pliku. Dzięki temu nowe wpisy w kolejce **zawsze** dostają co najmniej `primary_tool` i ewentualnie `secondary_tool`, nawet gdy mapowanie jest puste lub API nie zostało wywołane.

2. **Komunikat przy braku OPENAI_API_KEY**  
   Gdy są problemy bez mapowania i nie ustawiono `OPENAI_API_KEY`, skrypt wypisuje:  
   *"AI mapping skipped: OPENAI_API_KEY not set. Queue entries will use default tools (first 2 from affiliate_tools). Set OPENAI_API_KEY to fill use_case_tools_mapping.yaml automatically."*

3. **Informacja o domyślnych narzędziach**  
   Przy dodawaniu wpisów z kolejki (są use case’y ze statusem `todo`) skrypt wypisuje, jakie narzędzia domyślne są używane, gdy brak wpisu w mapowaniu.

Efekt: **primary_tool** i **secondary_tool** są ustawiane automatycznie (z mapowania z AI albo z listy domyślnej z `affiliate_tools`), bez ręcznego uzupełniania w pliku mapowania ani w kolejce.

---

## 8. Szybka weryfikacja

- **Sprawdzenie kolejki:**  
  `content/queue.yaml` – dla tych trzech artykułów pola `primary_tool` i `secondary_tool` są puste (potwierdzone w audycie).
- **Sprawdzenie mapowania:**  
  `content/use_case_tools_mapping.yaml` – sekcja `mapping:` bez wpisów (potwierdzone).
- **Sprawdzenie zapisu mapowania w kodzie:**  
  Jedynie `scripts/generate_queue.py` wywołuje `_save_use_case_tools_mapping()` po udanym wywołaniu AI mapping.
