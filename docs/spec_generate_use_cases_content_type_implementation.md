# Specyfikacja wdrożenia: content_type w generate_use_cases (wariant zatwierdzony)

**Status:** Zaakceptowany do wdrożenia.  
**Data:** 2026-02-20.  
**Zakres:** generate_use_cases (prompt, walidacja, fallback), definicja ALL, jednorazowa migracja, wyłącznie `content_type`.

---

## 1. Cel i założenia

- **Źródło prawdy:** `content/use_cases.yaml` i `content/queue.yaml`. Brak mapowania kategoria → content_type w generate_articles.
- **Pole w use_cases:** `content_type` (ustalony typ; obowiązkowo jeden z typów zaznaczonych dla runu, wybrany przez model; przy błędzie API – fallback).
- **Jakość merytoryczna:** Model dostaje **osobne, krótkie instrukcje (2–4 zdania)** dla każdego typu treści z listy allowed, żeby „wiedział”, jakie są wymagania case’ów w tych typach.
- **ALL:** Pełna swoboda wyboru typu tylko gdy zaznaczono wszystkie typy; ALL = konkretna lista wszystkich obsługiwanych typów (z configu/szablonów); fallback tylko gdy zwrócony typ nie jest na tej liście.
- **generate_articles:** Bez zmian; szablon i frontmatter wyłącznie z `content_type` z kolejki.

---

## 2. Doprecyzowania przyjęte przy akceptacji

1. **Bloki instrukcji per typ:** Ograniczyć do **krótkich opisów (2–4 zdania per typ)**. W kolejnej iteracji dopuszczalne przeniesienie pełnych specyfikacji do pliku i wstrzykiwanie tylko dla zaznaczonych typów.
2. **ALL:** Zdefiniować jako **konkretną listę wszystkich obsługiwanych typów** (np. z configu/szablonów). Fallback stosować **tylko** gdy zwrócony typ nie znajduje się na tej liście.
3. **Migracja:** W specyfikacji wdrożenia uwzględnić **jednorazowy skrypt migracji**; po jego wykonaniu w pipeline używać **wyłącznie `content_type`** (brak odczytu ani zapisu `suggested_content_type` w plikach i w logice downstream).

---

## 3. Definicja ALL

- **Źródło listy ALL:** `content/config.yaml` → `content_types_all` (lista stringów). Jeśli brak lub pusta – użyć stałej fallback w kodzie (np. `ALLOWED_CONTENT_TYPES` w `generate_use_cases.py`).
- **Semantyka:** Run z zaznaczonymi **wszystkimi** typami z `content_types_all` = tryb ALL (pełna swoboda wyboru typu przez model). Run z podzbiorem = tylko te typy dozwolone; niedopuszczalne przypisanie typu spoza listy.
- **Fallback:** Stosować **tylko** gdy API zwróci `content_type` **niebędący** na liście dozwolonych dla danego runu (dla subsetu = allowed; dla ALL = `content_types_all`). Wtedy: ustaw `content_type = random.choice(allowed_types)` (gdzie `allowed_types` to lista dla tego runu).

---

## 4. Prompt (generate_use_cases)

### 4.1 Instrukcja główna (content_type)

- W **instructions** lub **user message** musi być jawnie:
  - Dozwolone są **wyłącznie** typy z listy `allowed_content_types` (dla runu subset) lub z listy ALL (dla runu ALL).
  - **Niedopuszczalne** jest przypisanie typu spoza tej listy.
- Dla runu **subset:** dodać blok typu: „You MUST set content_type for each use case to exactly one of these values only: [lista]. It is not permitted to assign a content_type outside this list. Choose one of these types for each use case (vary across the batch where appropriate).”
- Dla runu **ALL:** „For each use case, set content_type to exactly one of: [lista]. You may choose any type from this list as appropriate for each use case.”

### 4.2 Wymagania per typ (2–4 zdania)

- Dla **każdego** typu z listy `allowed_content_types` (dla danego runu) wstrzyknąć **jeden krótki blok** (2–4 zdania) z wymaganiami case’ów w tym typie.
- Przykłady (zachować zwięzłość):
  - **best-in-category:** listicle, kontekstowe H2, tabela porównawcza, CTA.
  - **product-comparison:** porównanie konkretnych produktów, kryteria, tabela, rekomendacja, CTA, angielski.
  - **sales:** produkt, ton konwersacyjny, wyraźne CTA, angielski, konwersja.
  - **guide / how-to / best / comparison / review / category-products:** analogicznie krótko (obecne `CONTENT_TYPE_SPECS` w skrypcie są wzorcem).
- Źródło tekstów: na wdrożenie – słownik/stała w `generate_use_cases.py` (np. `CONTENT_TYPE_SPECS`). W kolejnej iteracji – dopuszczalne przeniesienie do pliku (np. YAML) i wstrzykiwanie tylko dla zaznaczonych typów.

---

## 5. Walidacja i fallback (parse_ai_use_cases)

- Dla każdego obiektu z odpowiedzi API:
  - Odczyt: `content_type = (item.get("content_type") lub item.get("suggested_content_type"))` – dopuszczalne dla **odpowiedzi API** (kompatybilność z różnymi formatami odpowiedzi).
  - **Walidacja:** czy `content_type` należy do listy `allowed_types` przekazanej do funkcji (dla runu subset = zaznaczone typy; dla runu ALL = `content_types_all` z configu).
  - **Fallback:** jeśli `content_type not in allowed_types` → `content_type = random.choice(allowed_types)`.
- Do pliku i do dalszego pipeline’u zwracać **wyłącznie** pole `content_type` (bez `suggested_content_type`).

---

## 6. Zapis use_cases i kolejki

- **Zapis do `content/use_cases.yaml`:** Tylko pole `content_type`. Nie zapisywać `suggested_content_type`.
- **Odczyt w generate_queue (i wszędzie downstream):** Tylko `content_type`. Po migracji **brak** fallbacku na `suggested_content_type` przy odczycie z use_cases.
- **Kolejka:** Wpis z use_cases do kolejki zawiera `content_type` z use case’a (po walidacji/fallbacku w generate_use_cases; w generate_queue – jeśli brak lub nie z listy allowed, można ustawić `DEFAULT_CONTENT_TYPE` zgodnie z obecną logiką).

---

## 7. Jednorazowa migracja

- **Skrypt:** `scripts/migrate_use_cases_to_content_type.py` (istniejący).
- **Działanie:**
  - Dla każdego wpisu w `content/use_cases.yaml`: jeśli brak `content_type`, ustaw `content_type = suggested_content_type` (lub wartość domyślną, np. `guide`, jeśli obu brak).
  - Zapis do pliku **tylko** z kluczem `content_type`; usunąć z każdego wpisu klucz `suggested_content_type` (nie zapisywać go w pliku).
- **Kolejność wdrożenia:** Najpierw wdrożyć zmiany w generate_use_cases (prompt, ALL, fallback, zapis tylko `content_type`). Przed przekazaniem do produkcji/release: **uruchomić jednorazowo** `python scripts/migrate_use_cases_to_content_type.py` na aktualnym `content/use_cases.yaml`. Po migracji: w całym pipeline (generate_queue, monitor, itd.) używać wyłącznie `content_type`; nie czytać `suggested_content_type` z plików.
- **Uwaga:** W parserze odpowiedzi API nadal można akceptować `suggested_content_type` z JSON (odpowiedź modelu), ale wynik zawsze normalizować do `content_type` i tylko tak zapisywać.

---

## 8. Pliki i zmiany (checklist)

| Miejsce | Zmiana |
|--------|--------|
| `content/config.yaml` | Upewnić się, że `content_types_all` zawiera pełną listę typów (np. how-to, guide, best, comparison, review, sales, product-comparison, best-in-category, category-products). Już obecne. |
| `scripts/generate_use_cases.py` | ALL z configu (`content_types_all`); prompt z blokami 2–4 zdania per typ tylko dla `allowed_content_types`; jawna instrukcja „tylko z listy”; walidacja + fallback losowy; zapis tylko `content_type`. |
| `scripts/generate_queue.py` | Odczyt z use case tylko `content_type`. Brak odwołań do `suggested_content_type` przy budowaniu kolejki (już tak jest; po migracji nie dodawać fallbacku na suggested). |
| `scripts/migrate_use_cases_to_content_type.py` | Użyć jednorazowo po wdrożeniu; dokumentować w README/release. |
| Inne skrypty czytające use_cases/queue | Upewnić się, że używają tylko `content_type` (np. `remove_articles_by_date.py` – zamienić `suggested_content_type` na `content_type`). |
| Flowtaro Monitor | Po migracji wyświetlanie/edycja use case tylko w oparciu o `content_type`; przy odczycie z pliku nie polegać na `suggested_content_type` (fallback `content_type or suggested_content_type` dopuszczalny do czasu migracji; po migracji w pliku jest tylko `content_type`). |

---

## 9. Kryteria akceptacji

- Run z **subsetem** typów (np. tylko best-in-category, product-comparison): w use_cases i kolejce tylko te typy; prompt zawiera krótkie wymagania wyłącznie dla tych typów; przy zwróceniu typu spoza listy – fallback losowy z tej listy.
- Run z **ALL:** model może wybrać dowolny typ z `content_types_all`; fallback tylko gdy API zwróci wartość spoza `content_types_all`.
- Po uruchomieniu migracji: w `content/use_cases.yaml` tylko klucz `content_type`; brak `suggested_content_type`.
- generate_articles bez zmian; szablon wybierany po `content_type` z kolejki.
- Jedno źródło prawdy: use_cases + queue; brak mapowania kategoria → content_type w generate_articles.

---

## 10. Kolejna iteracja (opcjonalnie)

- Przeniesienie pełnych specyfikacji typów do pliku (np. `content/content_type_specs.yaml`) i wstrzykiwanie do promptu **tylko** bloków dla zaznaczonych w runie typów (ograniczenie długości promptu przy wielu typach).

---

*Dokument stanowi jedyny rekomendowany wariant wdrożeniowy do implementacji. W razie rozbieżności z kodem decyduje niniejsza specyfikacja.*
