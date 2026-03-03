# Koncepcja: automatyczne opisy przy akcji „Dodaj” w Linki (Flowtaro Monitor)

**Cel:** Po dodaniu nowego linku w zakładce „Linki” w Flowtaro Monitor nowy wpis od razu otrzymuje `short_description_en` (jedno zdanie po angielsku z API), tak aby nie było konieczności późniejszego uruchamiania skryptu `fill_affiliate_descriptions.py` ani ręcznej edycji opisu.

**Kontekst:** Jednorazowe uzupełnienie obecnego pliku realizuje skrypt `scripts/fill_affiliate_descriptions.py` (Wariant 2 z `proposal_auto_descriptions_affiliate_tools_yaml.md`). Niniejszy dokument opisuje koncepcję **ciągłego** uzupełniania opisów przy akcji „Dodaj” w UI.

---

## 1. Obecny flow „Dodaj” w Linki

- Użytkownik klika **„Dodaj”** → flow `_run_add_by_link_flow`:
  - Dialog „tylko link” → użytkownik wkleja URL.
  - Aplikacja proponuje **nazwę** (z URL, np. domena) i **kategorię** (np. `referral` gdy w URL jest `via=`/`ref=`).
  - **Opis (EN)** jest pusty: `short_description_en: ""`.
  - Użytkownik wybiera: **Zapisz** (od razu dodanie do listy), **Edytuj pola** (pełny formularz), lub przy duplikacie: **Dodaj z sugerowaną nazwą** / **Edytuj nazwę** / **Otwórz istniejący**.
- Po **Zapisz** lub **Dodaj z sugerowaną nazwą** do `tools_holder` trafia wpis **bez** `short_description_en`. Zapis do pliku (`save_affiliate_tools`) zapisuje go tak jak jest — bez opisu. Aby mieć opis, użytkownik musiałby później uruchomić skrypt jednorazowy albo ręcznie edytować wpis.

---

## 2. Proponowane kierunki

### Opcja A – Auto przy dodaniu wpisu (rekomendowana)

**Moment:** Zaraz po tym, jak użytkownik potwierdza dodanie nowego narzędzia („Zapisz” lub „Dodaj z sugerowaną nazwą”), zanim lub zaraz po `tools_holder.append(data)` i `refresh_tree()`.

**Działanie:**

- Jeśli `data.get("short_description_en", "").strip()` jest puste:
  - Wywołać **jedno** żądanie do Responses API (ten sam schemat co w `fill_affiliate_descriptions.py`: instrukcja „jedno krótkie zdanie po angielsku, faktograficznie, bez superlatywów”, input: nazwa + kategoria).
  - Otrzymany tekst z API: sanityzacja (jak w skrypcie: trim, nowe linie → spacja, max ~300 znaków, escape pod YAML).
  - Ustawić `data["short_description_en"] = wynik` (albo ustawić w już dołączonym elemencie na końcu `tools_holder`).
  - Odświeżyć drzewo: `refresh_tree()`.

**Plusy:** Nowy link od razu ma opis; brak dodatkowego kroku dla użytkownika.  
**Minusy:** Jedno wywołanie API przy każdym dodaniu; UI musi obsłużyć opóźnienie (np. 2–10 s).  
**UX:** Wskazane pokazanie krótkiego komunikatu „Generowanie opisu…” (np. w statusie lub w oknie) i po zakończeniu odświeżenie listy. W razie błędu API — wpis zostaje z pustym opisem; użytkownik może go uzupełnić w „Edytuj”.

---

### Opcja B – Przycisk „Wygeneruj opis” w dialogu

**Moment:** W dialogu dodawania/edycji wpisu („Dodaj” / „Edytuj”) — pole „Opis (EN)” pozostaje edytowalne; dodany zostaje przycisk np. **„Wygeneruj opis (AI)”**.

**Działanie:**

- Użytkownik wypełnia nazwę, kategorię, link. Jeśli opis jest pusty (lub niezależnie), klika „Wygeneruj opis (AI)”.
  - Aplikacja wysyła jedno żądanie do Responses API (ta sama instrukcja i wejście: nazwa + kategoria).
  - Wynik wpisywany jest w pole „Opis (EN)” w dialogu; użytkownik może go poprawić i dopiero potem zatwierdzić OK.

**Plusy:** Pełna kontrola użytkownika; brak automatycznego wywołania API bez wiedzy użytkownika.  
**Minusy:** Wymaga dodatkowego kliknięcia; łatwo zapomnieć i zapisać wpis bez opisu.

**Można łączyć z A:** Auto przy dodaniu **oraz** przycisk w dialogu dla edycji istniejących wpisów bez opisu.

---

### Opcja C – Uzupełnienie przy zapisie do pliku

**Moment:** W momencie wywołania **„Zapisz”** (save do `affiliate_tools.yaml`) — przed zapisem przejść po `tools_holder` i dla każdego wpisu z pustym `short_description_en` wywołać API i uzupełnić pole.

**Plusy:** Jedna logika „uzupełnij puste” przy zapisie; nie trzeba zmieniać flowu dodawania.  
**Minusy:** Przy pierwszym zapisie po dodaniu wielu linków bez opisów — wiele wywołań API i długie blokowanie UI (albo skomplikowana kolejka/background). Mniej przewidywalne dla użytkownika („dlaczego Zapisz trwa tak długo?”).

---

## 3. Rekomendacja

- **Wdrożyć Opcję A** jako domyślne zachowanie: przy akcji „Dodaj” (potwierdzenie „Zapisz” lub „Dodaj z sugerowaną nazwą”) dla wpisu z pustym `short_description_en` — jedno wywołanie Responses API i uzupełnienie opisu przed odświeżeniem listy.
- **Opcjonalnie dodać Opcję B** w dialogu edycji/dodawania: przycisk „Wygeneruj opis (AI)” dla bieżącego wpisu (szczególnie przy ręcznej edycji starych wpisów bez opisu).
- **Nie** realizować Opcji C jako głównego mechanizmu (ryzyko długiego „Zapisz” i wielu wywołań naraz).

---

## 4. Wymagania techniczne (dla Opcji A i B)

| Element | Szczegóły |
|--------|-----------|
| **API** | Ten sam co w `fill_affiliate_descriptions.py`: POST na `{OPENAI_BASE_URL}/v1/responses`, payload: `model`, `instructions`, `input`. Klucz: `OPENAI_API_KEY`, baza: `OPENAI_BASE_URL` (opcjonalnie z env/configu Monitora). |
| **Instrukcja** | Stała tekstowa: jedno krótkie zdanie po angielsku, faktograficznie, bez superlatywów (np. „You are a product classifier. Output only one short sentence in English that factually describes what this product or tool does. No marketing superlatives.”). |
| **Wejście** | Dla jednego narzędzia: np. `"Name: {name}\nCategory: {category}"`. |
| **Reużycie kodu** | Można wyekstrahować z `scripts/fill_affiliate_descriptions.py` funkcję `_call_api` + `_yaml_quote` (lub ich odpowiedniki) do wspólnego modułu (np. `flowtaro_monitor/_affiliate_descriptions.py` lub w `_monitor_data.py`) i wywoływać z Monitora oraz ze skryptu. |
| **Błędy** | Przy błędzie sieci/API: nie blokować zapisu; wpis pozostaje z pustym `short_description_en`; ewentualnie komunikat „Nie udało się wygenerować opisu (sprawdź API key). Możesz dodać go ręcznie w Edytuj.” |
| **Konfiguracja** | Jeśli w Monitorze nie ma ustawionego klucza API / bazy URL, Opcja A może być nieaktywna (np. nie wywoływać API, tylko dopisać wpis z pustym opisem) lub wyświetlić jednorazową podpowiedź „Ustaw OPENAI_API_KEY, aby automatycznie generować opisy”. |

---

## 5. Krótki plan wdrożenia (po akceptacji koncepcji)

1. **Wspólna warstwa API** (opcjonalnie, ale zalecana): wydzielić w projekcie moduł z `_call_api` i sanityzacją opisu (np. `scripts/_affiliate_description_api.py` lub w `flowtaro_monitor`), tak aby `fill_affiliate_descriptions.py` i Flowtaro Monitor z niego korzystały.
2. **Opcja A w `main.py`:** W `_run_add_by_link_flow`, w gałęziach gdzie wykonujemy `tools_holder.append(data)` (po „Zapisz”, „Dodaj z sugerowaną nazwą”, „Edytuj nazwę”), jeśli `(data.get("short_description_en") or "").strip() == ""`, wywołać API dla `data["name"]` i `data["category"]`, ustawić `data["short_description_en"]`, potem `refresh_tree()`. Dodać krótki komunikat „Generowanie opisu…” (np. w etykiecie lub w oknie dialogu) i obsługę wyjątków.
3. **Opcja B (opcjonalnie):** W `_affiliate_edit_dialog` dodać przycisk „Wygeneruj opis (AI)”, który dla bieżących wartości nazwy i kategorii wywołuje API i wstawia wynik do pola „Opis (EN)”.
4. **Testy:** Ręcznie: dodać nowy link (tylko URL → Zapisz) i sprawdzić, czy w liście pojawia się wpis z wygenerowanym opisem; sprawdzić zachowanie przy braku klucza API / błędzie sieci.

---

## 6. Zależności

- **Jednorazowe wypełnienie:** nadal realizowane przez `python scripts/fill_affiliate_descriptions.py [--write]` dla obecnego stanu pliku.
- **Nowe wpisy:** po wdrożeniu Opcji A (i ewentualnie B) nowe linki dodane z Monitora będą miały opisy od razu; lista nie będzie wymagała późniejszej masowej aktualizacji tylko z powodu nowych linków.

---

*Dokument koncepcji; do implementacji po zatwierdzeniu.*
