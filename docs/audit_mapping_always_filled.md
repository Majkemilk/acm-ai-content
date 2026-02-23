# Audyt: wymuszenie wypełnienia mapowania i primary/secondary tool

## Cel

- Mapowanie (`use_case_tools_mapping.yaml`) **zawsze** ma wpis dla każdego problemu z `use_cases.yaml` – zero braków.
- W kolejce (`queue.yaml`) każdy wpis ma ustawione **primary_tool** i (opcjonalnie) **secondary_tool**.
- Bez ręcznego uzupełniania i bez polegania na „fallbacku tylko w pamięci” – braki są **zapisywane w pliku** mapowania.

---

## Przepływ (stan przed zmianami)

1. **generate_use_cases.py** – dopisuje do `use_cases.yaml` nowe problemy ze statusem `todo`.
2. **generate_queue.py**:
   - ładuje `use_cases.yaml`, `use_case_tools_mapping.yaml`, `affiliate_tools.yaml`;
   - wyznacza **tylko** use case’y ze statusem `todo` → `todo_use_cases`;
   - `problems_without_mapping` = problemy z **todo_use_cases**, których nie ma w mapowaniu;
   - jeśli jest OPENAI_API_KEY: wywołuje AI, dopisuje nowe wpisy do pliku mapowania;
   - jeśli brak klucza / błąd API: **nic nie zapisuje** do mapowania;
   - `build_queue_items(todo_use_cases, ..., tools_mapping, default_tools)` – brakujące w mapowaniu uzupełnia w pamięci domyślnymi narzędziami, **ale plik mapowania pozostaje bez tych wpisów**.

Skutek: przy braku API lub błędzie AI mapowanie w pliku jest niekompletne, a zakładka „Mapowanie” i kolejne uruchomienia dalej widzą puste miejsca. Fallback działa tylko dla bieżącego uruchomienia.

---

## Proponowane zmiany

### 1. Uzupełnianie mapowania dla **wszystkich** problemów z use_cases

- Nie ograniczać się do `todo_use_cases`.  
- **problems_without_mapping** = wszystkie unikalne problemy z `use_cases.yaml`, których **nie ma** w `existing_mapping` (porównanie po `problem.lower()`).
- Dzięki temu mapowanie jest uzupełniane także dla use case’ów już „generated”, a plik pozostaje kompletny przy każdym uruchomieniu.

### 2. Zapis domyślnych wpisów do pliku mapowania

- Po kroku AI (lub gdy AI nie było wywołane): dla każdego problemu z `problems_without_mapping`, który **nadal** nie ma wpisu w `existing_mapping`:
  - ustaw w pamięci: `existing_mapping[problem.lower()] = default_tools`;
  - dopisz do listy wpisów do zapisu: `{ "problem": problem, "tools": "Tool1, Tool2" }`.
- Zapisać plik: `_save_use_case_tools_mapping(USE_CASE_TOOLS_MAPPING_PATH, existing_raw + new_default_entries)`.
- Zaktualizować w pamięci `existing_raw`, żeby kolejne kroki (np. build_queue_items) widziały pełne mapowanie.

Efekt: **żaden** problem z use_cases nie zostaje bez wpisu w pliku – albo jest wpis z AI, albo wpis z domyślnymi narzędziami (referral / pierwsze z affiliate_tools).

### 3. Kolejka zawsze z primary_tool / secondary_tool

- Po zapisie mapowania **wszystkie** problemy z `use_cases.yaml` mają wpis w `existing_mapping`.
- `build_queue_items(todo_use_cases, ...)` korzysta z tego samego `existing_mapping`, więc każdy wpis w kolejce dostaje `primary_tool` i ewentualnie `secondary_tool` z mapowania.
- Opcjonalnie zostawić `default_tools` w `build_queue_items` jako awaryjny fallback (np. gdy `tools_list` jest pusty).

### 4. Kolejność w main()

1. Załadować use_cases, tools_list, existing_mapping, existing_raw.
2. Wyznaczyć **wszystkie** unikalne problemy z use_cases i **problems_without_mapping** (te, których nie ma w existing_mapping).
3. Dla problems_without_mapping: opcjonalnie AI (jeśli klucz i brak `--no-ai-mapping`), zapis nowych wpisów, odświeżenie existing_mapping i existing_raw.
4. Dla problemów **nadal** bez wpisu: dodać wpisy domyślne (default_tools) do existing_mapping i do listy do zapisu; **zapisać** plik mapowania; zaktualizować existing_raw.
5. Wyznaczyć todo_use_cases i build_queue_items(todo_use_cases, ..., tools_mapping=existing_mapping, default_tools=...).
6. Reszta bez zmian (deduplikacja kolejki, save queue, oznaczenie use case’ów jako generated).

---

## Gwarancje po wdrożeniu

- Przy każdym uruchomieniu **generate_queue.py** (bez `--dry-run`): każdy problem z `use_cases.yaml` ma wpis w `use_case_tools_mapping.yaml` (z AI lub domyślny); braki są **zapisywane w pliku**.
- W trybie `--dry-run` mapowanie jest uzupełniane tylko w pamięci (kolejka nie jest zapisywana i plik mapowania nie jest zmieniany).
- Każdy nowy wpis dodawany do `queue.yaml` ma ustawione `primary_tool` i ewentualnie `secondary_tool`.
- Zakładka „Mapowanie” w aplikacji pokazuje pełną listę, bez pustego pliku i bez brakujących problemów.
- Nie jest wymagane ręczne uzupełnianie mapowania ani kolejki.

---

## Wdrożenie (generate_queue.py)

- **Wszystkie problemy z use_cases:** `problems_without_mapping` budowane jest ze **wszystkich** unikalnych problemów z `use_cases.yaml`, nie tylko ze statusem `todo`. Dzięki temu mapowanie jest uzupełniane także dla use case’ów już wygenerowanych.
- **Zapis domyślnych wpisów:** Po kroku AI (lub gdy AI nie było wywołane) dla każdego problemu nadal bez wpisu do mapowania dopisywane są wpisy z `default_tools` (Opus Clip, Make itd.) i wynik jest **zapisywany** w `use_case_tools_mapping.yaml`.
- **Aktualizacja existing_raw po AI:** Po zapisie wpisów z AI zmienna `existing_raw` jest ustawiana na `full_entries`, żeby kolejny krok (domyślne wpisy) nie nadpisywał ich.
- **--dry-run:** Zapis do pliku mapowania (AI i domyślne wpisy) jest pomijany, gdy podano `--dry-run`.
