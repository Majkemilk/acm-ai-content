# Audyt funkcji mapowania problem → narzędzia

## 1. Czym jest mapowanie

`content/use_case_tools_mapping.yaml` to plik-rejestr, w którym każdemu problemowi biznesowemu (use case'owi) przypisane są 1–2 narzędzia AI z katalogu `affiliate_tools.yaml`. Format:

```yaml
mapping:
  - problem: "streamline content approval processes using AI tools to reduce bottlenecks"
    tools: "Opus Clip, Make"
```

Kluczem jest tekst problemu (porównywany jako lowercase); wartością lista nazw narzędzi (rozdzielana przecinkami). Nazwy muszą dokładnie odpowiadać polu `name` w `affiliate_tools.yaml`.

---

## 2. Miejsce mapowania w workflow

Workflow składa się z siedmiu etapów uruchamianych kolejno (zakładka Workflow w aplikacji Flowtaro Monitor):

```
generate_use_cases → generate_queue → generate_articles → fill_articles
                                                           ↓
                                          generate_hubs → generate_sitemap → render_site
```

Mapowanie uczestniczy w **trzech** z tych etapów oraz jest odczytywane przez **jeden** moduł UI:

### 2.1 generate_queue.py (ZAPIS + ODCZYT)

**Jedyne miejsce, w którym plik mapowania jest zapisywany.**

Kolejność operacji w `main()` po poprawkach:

1. Załaduj `use_cases.yaml`, `affiliate_tools.yaml`, dotychczasowy `use_case_tools_mapping.yaml`.
2. Zbierz **wszystkie** unikalne problemy z `use_cases.yaml` (nie tylko ze statusem `todo`).
3. Wyznacz `problems_without_mapping` – problemy, których nie ma w pliku mapowania.
4. **Krok AI** (jeśli `--no-ai-mapping` nie podano i `OPENAI_API_KEY` ustawione):
   - Wyślij `problems_without_mapping` + listę narzędzi do API (model z `OPENAI_MODEL`).
   - API zwraca JSON: `[{problem, tools: [tool1, tool2]}, ...]`.
   - Odpowiedź jest walidowana (`_parse_ai_mapping`): nazwy narzędzi muszą istnieć w `affiliate_tools.yaml` (case-insensitive).
   - Nowe wpisy dopisywane do `existing_mapping` i zapisywane do pliku (chyba że `--dry-run`).
5. **Fallback domyślnymi narzędziami**: dla problemów nadal bez wpisu (AI nie odpowiedziało, brak klucza, błąd API) wpisy są dodawane z `default_tools` (do 2 narzędzi z kategorii `referral` z `affiliate_tools.yaml`, np. Opus Clip, Make) i **zapisywane w pliku**.
6. Wyznacz `todo_use_cases` (status `todo`).
7. `build_queue_items(todo_use_cases, ..., tools_mapping=existing_mapping, default_tools=default_tools)`:
   - Dla każdego use case'a: `primary_tool = tools[0]`, `secondary_tool = tools[1]` z mapowania; jeśli brak – z `default_tools` (in-memory fallback, praktycznie nieosiągalny po kroku 5).

**Powiązania wejścia/wyjścia:**

| Wejście | Plik |
|---------|------|
| Problemy biznesowe | `content/use_cases.yaml` |
| Katalog narzędzi | `content/affiliate_tools.yaml` |
| Dotychczasowe mapowanie | `content/use_case_tools_mapping.yaml` |

| Wyjście | Plik |
|---------|------|
| Uzupełnione mapowanie | `content/use_case_tools_mapping.yaml` |
| Kolejka artykułów (z primary_tool, secondary_tool) | `content/queue.yaml` |
| Zaktualizowane statusy use case'ów | `content/use_cases.yaml` |

### 2.2 generate_articles.py (ODCZYT pośredni)

Nie odczytuje pliku mapowania bezpośrednio, ale korzysta z jego efektów:

- Pobiera wpis z `queue.yaml` (który już zawiera `primary_tool` / `secondary_tool` ustawione przez generate_queue na podstawie mapowania).
- `get_replacements()` mapuje pola kolejki na zmienne szablonu:
  - `{{PRIMARY_TOOL}}` ← `item["primary_tool"]`
  - `{{SECONDARY_TOOL}}` ← `item["secondary_tool"]`
  - `{{TOOLS_MENTIONED}}` ← `item["tools_mentioned"]` (jeśli podane) **lub** lista bullet zbudowana z `primary_tool` + `secondary_tool` z linkami z `affiliate_tools.yaml` (funkcja `_build_tools_mentioned_from_queue_item`).
- `render_article()` wstawia te zmienne do szablonu (np. `templates/how-to.md`), tworząc gotowy plik `.md` z wypełnionymi polami.

### 2.3 fill_articles.py (ODCZYT pośredni)

Nie czyta pliku mapowania; korzysta z metadanych frontmatter artykułu (ustawionych przez generate_articles z kolejki):

- `build_prompt()` → odczytuje `primary_tool`, `secondary_tool` z frontmatteru i buduje prompt:
  - Jeśli narzędzia podane: *"You may mention only these tools (do not invent others): Tool1, Tool2."*
  - Jeśli brak: ładuje **wszystkie** narzędzia z `affiliate_tools.yaml` i daje modelowi wolny wybór 1–2 pasujących (*"No specific tools were assigned …"*).
- Model wypełnia placeholdery `[bracket]` w artykule, ale **nie zmienia** placeholderów `{{MUSTACHE}}` (w tym `{{TOOLS_MENTIONED}}`).

### 2.4 render_site.py (bez bezpośredniego związku z mapowaniem)

- Przy renderowaniu HTML **usuwa** sekcję „## Tools mentioned" z body markdown (jest traktowana jako redakcyjna, niepublikacyjna).
- Zamienia nazwy narzędzi w treści artykułu na linki afiliacyjne (`replace_tool_names_with_links` z `affiliate_tools.yaml`).
- Nie odczytuje pliku mapowania.

### 2.5 Flowtaro Monitor – zakładka „Mapowanie" (ODCZYT)

- `_monitor_data.py` → `get_mapping_data()` → `load_use_case_tools_mapping(MAPPING_PATH)` – odczytuje plik, zwraca listę `(problem, tools_str)`.
- `main.py` → `build_mapping_tab()` – wyświetla Treeview (kolumny: Problem, Narzędzia). Przycisk „Odśwież" ponownie wczytuje dane.
- Zakładka jest **tylko do odczytu**; nie edytuje pliku.

---

## 3. Diagram przepływu danych mapowania

```
                  ┌────────────────────┐
                  │  use_cases.yaml    │
                  │  (problemy)        │
                  └────────┬───────────┘
                           │
                           ▼
┌──────────────┐   ┌──────────────────────┐   ┌───────────────────────┐
│ affiliate_   │──▶│  generate_queue.py    │──▶│ use_case_tools_       │
│ tools.yaml   │   │                      │   │ mapping.yaml          │
│ (narzędzia)  │   │  1. AI mapping (API) │   │ (problem → narzędzia) │
│              │   │  2. default fallback  │   └───────────┬───────────┘
└──────────────┘   │  3. build_queue_items │               │
                   └──────────┬───────────┘               │
                              │                            │
                              ▼                            ▼
                   ┌──────────────────┐        ┌───────────────────┐
                   │  queue.yaml      │        │ Flowtaro Monitor  │
                   │  (primary_tool,  │        │ zakł. „Mapowanie" │
                   │   secondary_tool)│        │ (odczyt)          │
                   └────────┬─────────┘        └───────────────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │ generate_articles │
                   │ ({{PRIMARY_TOOL}} │
                   │  {{SECONDARY_TOOL}│
                   │  {{TOOLS_MENTIONED}│
                   │  → artykuł .md)   │
                   └────────┬──────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  fill_articles   │
                   │  (prompt: mention│
                   │   only these     │
                   │   tools …)       │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  render_site     │
                   │  (nazwy narzędzi │
                   │   → linki aff.)  │
                   └──────────────────┘
```

---

## 4. Funkcje Pythona zaangażowane w mapowanie

| Funkcja | Plik | Rola |
|---------|------|------|
| `load_use_case_tools_mapping(path)` | `generate_queue.py` | Odczyt pliku → `dict[str, list[str]]` |
| `_fetch_ai_tools_mapping(problems, tools_list, ...)` | `generate_queue.py` | Wywołanie API → `dict[str, list[str]]` |
| `_build_mapping_prompt(problems, tools)` | `generate_queue.py` | Buduje prompt (instructions, user_message) |
| `_parse_ai_mapping(response_text, valid_names)` | `generate_queue.py` | Parsuje JSON z API; waliduje nazwy |
| `_save_use_case_tools_mapping(path, entries)` | `generate_queue.py` | Zapis pliku YAML |
| `_default_tools_from_affiliate_list(tools_list)` | `generate_queue.py` | Domyślne 2 narzędzia (referral first) |
| `build_queue_items(use_cases, ..., tools_mapping, default_tools)` | `generate_queue.py` | Buduje wpisy kolejki z primary/secondary |
| `get_mapping_data()` | `_monitor_data.py` | Odczyt pliku → UI (lista krotek) |
| `_build_tools_mentioned_from_queue_item(item, name_to_url)` | `generate_articles.py` | Buduje listę bullet z linkami aff. |
| `get_replacements(item, today, ...)` | `generate_articles.py` | Mapuje pola kolejki → zmienne szablonu |

---

## 5. Co się zmieniło po poprawkach

| Aspekt | Przed | Po |
|--------|-------|----|
| Zakres mapowania | Tylko use case'y `todo` | **Wszystkie** unikalne problemy z `use_cases.yaml` |
| Brak klucza API | Mapowanie pominięte (brak zapisu, brak komunikatu) | Komunikat + wpisy domyślne **zapisywane w pliku** |
| Błąd API | Mapowanie pominięte (wpisy nie zapisane) | Wpisy domyślne **zapisywane w pliku** po niepowodzeniu AI |
| Plik mapowania po uruchomieniu | Mógł pozostać pusty | Zawsze kompletny (każdy problem ma wpis) |
| `primary_tool` / `secondary_tool` w kolejce | Puste przy braku mapowania | Zawsze ustawione (z mapowania lub domyślnych) |
| `{{TOOLS_MENTIONED}}` w artykule | Pozostawał jako placeholder | Budowany z `primary_tool` + `secondary_tool` + linki afiliacyjne |
| Szablony (`- {{TOOLS_MENTIONED}}`) | Podwójny myślnik przy wielu narzędziach | Sam `{{TOOLS_MENTIONED}}` (lista bullet generowana w kodzie) |

---

## 6. Ocena merytoryczna

### 6.1 Mocne strony

1. **Jedno źródło prawdy.** Plik mapowania jest centralnym rejestrem problem → narzędzia. Kolejka i artykuły korzystają z tych samych danych. Zmiana narzędzia w mapowaniu propaguje się do nowych artykułów bez zmian w kodzie.

2. **AI jako wsparcie, nie wymóg.** Mapowanie może być uzupełniane ręcznie, przez AI, albo domyślnymi narzędziami. System nie zatrzymuje się, gdy API jest niedostępne – jest fallback.

3. **Walidacja nazw narzędzi.** `_parse_ai_mapping` sprawdza, czy nazwy zwrócone przez AI istnieją w `affiliate_tools.yaml` (case-insensitive). Zapobiega „halucynacjom" narzędzi, które nie mają linków afiliacyjnych.

4. **Separacja odpowiedzialności.** Mapowanie jest **oddzielne** od kolejki i od artykułów. Pozwala na zmianę przypisań bez regenerowania całej kolejki.

5. **Kompletność po poprawkach.** Gwarancja: po każdym uruchomieniu `generate_queue` (bez `--dry-run`) plik mapowania jest kompletny – żaden problem nie zostaje bez wpisu.

### 6.2 Słabe strony i ryzyka

1. **Domyślne narzędzia są generyczne.** Fallback to zawsze te same 2 narzędzia (Opus Clip, Make) dla każdego problemu. Przy dużej liczbie use case'ów bez AI mapping powstaje monotonny content z ciągle tymi samymi narzędziami. Wynik jest „formalnie poprawny" (brak pustych pól), ale **merytorycznie słaby** – nie każdy problem rozwiązuje się narzędziem do klipów wideo czy integracją Make.

2. **Brak ponownego mapowania po uzupełnieniu klucza API.** Jeśli przy pierwszym uruchomieniu nie było `OPENAI_API_KEY` i wpisy zostały dodane z domyślnymi narzędziami, kolejne uruchomienie **nie nadpisze** tych domyślnych wpisów, bo `problems_without_mapping` nie uwzględnia problemów już obecnych w pliku. Aby uzyskać lepsze mapowanie (z AI), trzeba ręcznie usunąć wpisy z pliku mapowania.

3. **Brak edycji mapowania w UI.** Zakładka „Mapowanie" jest tylko do odczytu. Redaktor nie może zmienić przypisania problem → narzędzia bez ręcznej edycji YAML. Dla nietechnicznego użytkownika to bariera.

4. **Powiązanie z tytułem artykułu.** `title_for_entry(problem, content_type, primary_tool)` generuje tytuł z nazwą narzędzia (np. „How to … with Opus Clip"). Zmiana mapowania po wygenerowaniu kolejki nie zmienia tytułu w `queue.yaml` ani nazwy pliku `.md`. Tytuł i narzędzie mogą się rozjechać.

5. **Sekcja „Tools mentioned" w render_site jest usuwana.** `render_site.py` stripuje sekcję `## Tools mentioned` z HTML (traktowana jako redakcyjna). Oznacza to, że lista narzędzi z mapowania **nie jest widoczna** na opublikowanej stronie jako wyodrębniona sekcja. Narzędzia pojawiają się w treści artykułu (jeśli fill_articles je wzmiankowało) i są zamieniane na linki afiliacyjne przez `replace_tool_names_with_links`.

### 6.3 Czy ta funkcja jest sensowna w obecnej formie?

**Tak, ale z zastrzeżeniami.**

Mapowanie rozwiązuje realny problem: decyduje, **które** narzędzia (z puli afiliacyjnej) są wstawiane do artykułu. Bez mapowania artykuły albo nie miałyby narzędzi (puste placeholdery), albo model AI w fill_articles musiałby sam decydować – z ryzykiem halucynacji lub niespójnych wyborów.

Obecna implementacja jest **funkcjonalnie kompletna**: zapewnia, że każdy problem ma przypisanie, a kolejka i artykuły mają `primary_tool` / `secondary_tool`. System nie wymaga ręcznej interwencji.

**Główna słabość** to jakość domyślnych wpisów: generyczne Opus Clip + Make dla każdego problemu to rozwiązanie „formalne", nie merytoryczne. W praktyce oznacza to, że artykuły o np. „automate troubleshooting workflows for API error handling" będą sugerowały narzędzie do klipów wideo – co jest absurdalne merytorycznie.

### 6.4 Rekomendacje

1. **Priorytet: zawsze próbować AI mapping.** Obecna logika jest poprawna (AI → fallback), ale warto dodać mechanizm **ponownego mapowania** (`--remap` lub `--refresh-mapping`), który zastępuje domyślne wpisy wynikami AI, gdy klucz API stanie się dostępny.

2. **Lepszy fallback.** Zamiast stałych 2 narzędzi, fallback mógłby próbować dopasować narzędzie po `category` z `affiliate_tools.yaml` do `category_slug` use case'a (np. „automation workflows" → Make).

3. **Edycja w UI.** Rozszerzyć zakładkę „Mapowanie" o możliwość zmiany przypisania (combobox z listą narzędzi z affiliate_tools + zapis do pliku). To eliminuje konieczność ręcznej edycji YAML.

4. **Walidacja spójności tytuł ↔ narzędzie.** Po zmianie mapowania (ręcznie lub ponownym AI) sprawdzić, czy tytuły w kolejce i nazwy plików .md odpowiadają nowemu `primary_tool`. Jeśli nie – ostrzeżenie lub propozycja aktualizacji.
