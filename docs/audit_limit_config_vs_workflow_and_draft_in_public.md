# Audyt: limit 3 vs 9, szkielety w public

## Opis sytuacji

- W Konfiguracji: limit pomysłów **3**, piramida **2-1-0** (beginner–intermediate–professional).
- W zakładce Generuj artykuły krok „Generuj use case'y” był ustawiony na limit **9**.
- Efekt: wygenerowano **9** use case’ów → 9 wpisów w kolejce → 9 szkieletów → fill na 9; część (ok. 6) trafiła do **public** jako **niewypełnione poprawnie**, ale sformatowane szkielety.

---

## 1. Skąd rozjazd limit 3 (config) vs 9 (workflow)?

### 1.1 Przepływ limitu

- **Config:** `use_case_batch_size` (np. 3) + `use_case_audience_pyramid` (np. [2,1,0]) – definiują „ile pomysłów na batch” i rozkład audience.
- **Zakładka „Generuj artykuły”:** Dla kroku „Generuj use case'y” widget limitu jest budowany **jednorazowo** przy tworzeniu zakładki:
  - `_build_param_widgets_for_action(..., "generate_use_cases")` wywołuje `get_use_case_defaults()` **w tym momencie** i wstawia `default=defaults["batch_size"]` do schematu oraz do Spinboxa (`spin.insert(0, str(p["default"]))`).
- **Konsekwencja:** Wartość domyślna w polu „limit” to **stan configu z chwili zbudowania zakładki** (np. przy starcie aplikacji). Jeśli użytkownik **później** zmieni w Konfiguracji `use_case_batch_size` na 3 (i ustawi 2-1-0), zakładka Generuj artykuły **nie odświeża** tej wartości – Spinbox dalej może pokazywać 9.
- Przy uruchomieniu pipeline’u: jeśli **„Inny limit” jest odznaczony**, do skryptu idzie `p["default"]` z widgetu (wciąż 9). Jeśli zaznaczone – wartość z Spinboxa (też może być 9). W obu przypadkach możliwy jest **limit 9 przy configu 3**.

### 1.2 Wnioski (limit)

- Domyślna wartość limitu w kroku „Generuj use case'y” **nie jest** odświeżana po zmianie Konfiguracji.
- Brak wymuszenia spójności: limit w workflow może być inny niż `use_case_batch_size` i inny niż suma piramidy (2+1+0=3).

---

## 2. Dlaczego szkielety trafiły do public?

### 2.1 Kto decyduje, co trafia do public?

- **`get_production_articles()`** (w `content_index.py`) zwraca **wszystkie** artykuły z `content/articles/`, dla których **`status != "blocked"`**.
- Nie ma filtrowania po `status == "filled"`. Artykuły z **`status: "draft"`** (szkielety niewypełnione lub po nieudanym fill) **są uznawane za production** i przekazywane dalej.
- **render_site.py**, **generate_hubs.py**, **generate_sitemap.py** używają `get_production_articles()` – więc **drafty są renderowane do public**, pojawiają się w hubie i w sitemapie.

### 2.2 Przebieg przy limit 9

1. generate_use_cases → 9 use case’ów.
2. generate_queue → 9 wpisów w kolejce.
3. generate_articles → 9 szkieletów .md z `status: "draft"`.
4. fill_articles → próba wypełnienia 9; część może nie przejść QA lub zakończyć się błędem → pozostają jako draft lub z niepełną treścią.
5. generate_hubs / generate_sitemap / render_site → **wszystkie nie-blocked** (w tym drafty) trafiają do public.

### 2.3 Wnioski (public)

- Obecna definicja „production” = **wszystko, co nie jest `blocked`**, więc **drafty są publikowane**.
- Brak bramki „do public tylko wypełnione” powoduje, że szkielety i artykuły niewypełnione poprawnie i tak lądują na stronie.

---

## 3. Rekomendacje do wdrożenia po akceptacji

### R1. Limit w workflow = aktualny config (bez odświeżania zakładki)

**Cel:** Gdy użytkownik nie ustawia „Inny limit”, zawsze używana ma być **aktualna** wartość z configu (`use_case_batch_size`), a nie wartość „zamrożona” przy budowaniu zakładki.

**Propozycja:** Przy zbieraniu argumentów dla akcji `generate_use_cases` (w `_collect_extra_from_widgets` lub w miejscu, gdzie budowana jest lista `extra` przed uruchomieniem): jeśli **nie** jest zaznaczone „Inny limit”, **nie** brać `p["default"]` z widgetu, tylko **na bieżąco** wywołać `get_use_case_defaults()` i użyć `defaults["batch_size"]` jako wartości `--limit`. Dzięki temu po zmianie Konfiguracji na 3 kolejne „Uruchom” bez „Inny limit” pójdzie z limitem 3.

**Za:** Spójność z Konfiguracją bez konieczności przeładowania zakładki.  
**Przeciw:** Drobna zmiana w logice zbierania argumentów.

---

### R2. Ostrzeżenie przy rozjazdzie limit vs piramida (opcjonalnie)

**Cel:** Sygnalizacja, gdy limit w workflow nie zgadza się z sumą piramidy (np. limit 9 przy 2-1-0).

**Propozycja:** Przed uruchomieniem sekwencji (lub przed krokiem generate_use_cases) odczytać z configu `use_case_batch_size` i `use_case_audience_pyramid`; jeśli używany limit (z widgetu lub z configu) ≠ suma piramidy, wyświetlić komunikat typu: „Limit use case’ów (X) nie jest równy sumie piramidy (Y). Uruchomić anyway?” z opcjami Kontynuuj / Anuluj.

**Za:** Świadoma decyzja przy rozjazdzie.  
**Przeciw:** Dodatkowy dialog; niektórzy użytkownicy mogą celowo chcieć limit ≠ suma.

---

### R3. Do public tylko artykuły wypełnione (status „filled”)

**Cel:** Aby w public (render_site, hub, sitemap) trafiały **tylko** artykuły z `status: "filled"`, a drafty i inne stany nie były publikowane.

**Propozycja:** Zmienić **`get_production_articles()`** tak, aby do listy production zaliczać tylko pliki, dla których `(meta.get("status") or "").strip().lower() == "filled"`. Artykuły z `status: "draft"`, pustym statusem lub innymi wartościami **nie** trafiają do public (nie są zwracane przez `get_production_articles()`).

**Konsekwencje:**
- Hub i sitemap będą zawierać tylko wypełnione artykuły.
- Szkielety (draft) pozostaną w `content/articles/`, ale nie pojawią się na stronie ani w sitemapie.
- Artykuły z innymi statusami (np. przyszłe „review”, „archived”) też nie trafią do public, dopóki nie będą miały `status: "filled"` (lub ewentualnie rozszerzymy później whitelistę).

**Za:** Brak szkieletów i niewypełnionych treści w public; jasna reguła.  
**Przeciw:** Zmiana semantyki „production”; każdy skrypt używający `get_production_articles()` będzie widział tylko „filled”. To jest zamierzony efekt.

---

### R4. Odświeżanie domyślnej wartości limitu przy wejściu na zakładkę (alternatywa do R1)

**Cel:** Zamiast „w momencie Run brać config”, można przy każdym wejściu na zakładkę „Generuj artykuły” (lub przy pokazaniu sekcji use case’ów) odświeżyć domyślną wartość limitu z configu i ustawić Spinbox (oraz etykietę „domyślnie X”) na aktualne `use_case_batch_size`.

**Za:** W UI użytkownik od razu widzi aktualny limit z configu.  
**Przeciw:** Wymaga powiązania zdarzenia „wybór zakładki” / „visibility” z odświeżeniem widgetów i ponownym odczytem configu; nieco więcej zmian w UI niż R1.

---

## 4. Rekomendacja końcowa

- **Wdrożyć R1** – przy Run używać aktualnego `use_case_batch_size` z configu, gdy „Inny limit” nie jest zaznaczony (eliminuje rozjazd 3 vs 9 przy nieodświeżonej zakładce).
- **Wdrożyć R3** – do public tylko `status: "filled"` (eliminuje trafianie szkieletów i draftów do public).
- **R2** – opcjonalnie, po akceptacji (ostrzeżenie limit vs piramida).
- **R4** – opcjonalnie jako uzupełnienie R1 (odświeżanie widoku limitu przy wejściu na zakładkę), jeśli zechcesz spójność także wizualną.

Po zatwierdzeniu R1 i R3 można przejść do konkretnych zmian w kodzie (main.py / _collect_extra + content_index.py get_production_articles).
