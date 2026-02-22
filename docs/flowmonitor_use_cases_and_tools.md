# FlowtaroMonitor – use case’y i mapowanie narzędzi

Krótkie zestawienie elementów wdrożonych pod kątem integracji z aplikacją FlowtaroMonitor: sugerowane problemy w configu oraz mapowanie problem → narzędzia.

---

## 1. Sugerowane problemy (config)

- **Źródło:** `content/config.yaml` → klucz **`suggested_problems`** (lista stringów).
- **Znaczenie:** Lista problemów biznesowych, które model ma **preferować** przy generowaniu use case’ów („Optionally consider these problems… prefer turning them into use cases”). Deduplikacja względem istniejących use case’ów nadal obowiązuje.
- **Odczyt/zapis:**
  - `scripts/content_index.load_config()` zwraca `suggested_problems` (domyślnie `[]`).
  - `scripts/config_manager`: `get_config_value(path, "suggested_problems")`, `set_config_value(path, "suggested_problems", list)`, `update_config(path, suggested_problems=list)`.
  - CLI: `python scripts/manage_config.py --get suggested_problems`, `--suggested-problems "problem A, problem B"`.
- **Użycie:** `scripts/generate_use_cases.py` wczytuje config i przekazuje `suggested_problems` do `build_prompt()`; gdy lista niepusta, w user message dodawany jest odpowiedni blok.

---

## 2. Mapowanie problem → narzędzia (kolejka)

- **Źródło:** `content/use_case_tools_mapping.yaml` (lista wpisów `problem` + `tools`).
- **Format:**  
  `tools` = jeden string z nazwami narzędzi z `affiliate_tools.yaml`, po przecinku (np. `"Canva, Pictory"`). Dopasowanie do use case’a po **znormalizowanym** tekście problemu (lowercase, strip).
- **Znaczenie:** Dla każdego use case’a z statusem `todo` skrypt `generate_queue.py` ustawia w wpisie kolejki **primary_tool** i **secondary_tool** (pierwsze dwa z listy). Te pola są przekazywane do `fill_articles` i wykorzystywane jako priorytetowe narzędzia w artykule.
- **Odczyt:** `scripts/generate_queue.load_use_case_tools_mapping(path)` → `dict[str, list[str]]` (klucz = problem.lower(), wartość = lista nazw narzędzi).
- **Edycja:** Ręczna w pliku lub **automatycznie przez AI** w ramach `generate_queue.py` (patrz niżej). Nowe wpisy z AI są dopisywane do pliku.
- **AI mapping (wewnątrz generate_queue):** Jeśli w pliku brak wpisu dla danego problemu (use case ze statusem `todo`), skrypt `generate_queue.py` może wywołać model (OpenAI Responses API), podając listę problemów i listę narzędzi z `affiliate_tools.yaml`, i zapisać zwrócone przypisania (1–2 narzędzia na problem) do `use_case_tools_mapping.yaml`. Wymaga ustawionego `OPENAI_API_KEY`. Aby wyłączyć: `--no-ai-mapping` (wtedy używane jest tylko to, co już jest w pliku).
- **Gdy mapowanie jest puste (lub bez AI):** W `scripts/fill_articles.py` przy budowaniu promptu, jeśli w meta artykułu nie ma `primary_tool` / `secondary_tool`, model i tak dostaje **pełną listę narzędzi z affiliate_tools.yaml** z instrukcją: „You may mention 1–2 tools from this list that best fit the topic”. Dzięki temu w nowo generowanych artykułach pojawiają się nazwy narzędzi, a przy renderze (`render_site.py`) nazwy te są zamieniane na linki. Mapowanie (ręczne lub z AI) poprawia precyzję (konkretne narzędzia per problem).

---

## 3. Przepływ (dla FlowMonitor)

1. **Config** – użytkownik może edytować `suggested_problems` (np. ekran „Konfiguracja” / „Use case’y”).
2. **generate_use_cases.py** – uruchamiany z bieżącym configiem; model dostaje sugerowane problemy, gdy lista niepusta.
3. **use_case_tools_mapping.yaml** – użytkownik może dodawać/edytować wpisy problem → narzędzia (nazwy z `affiliate_tools.yaml`).
4. **generate_queue.py** – przy dodawaniu wpisów do kolejki ustawia `primary_tool` / `secondary_tool` z mapowania.
5. **fill_articles** – korzysta z `primary_tool` / `secondary_tool` z meta kolejki (bez zmian w fill_articles).

Wymagane w FlowMonitor: odczyt/zapis `config.yaml` (w tym `suggested_problems`), odczyt/zapis `use_case_tools_mapping.yaml` oraz uruchamianie skryptów jak dotychczas.
