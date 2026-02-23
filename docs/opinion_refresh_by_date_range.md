# Opinia: odświeżanie z wyborem zakresu dat

## Pomysł

Dodać w aplikacji opcję **„Odśwież z okresu”** z możliwością wyboru **konkretnych dat** (od – do). System na tej podstawie wybierałby artykuły, których **data modyfikacji** (last_updated lub ewentualnie data pliku) mieści się w podanym zakresie.

---

## Ocena merytoryczna

**Sens:** Tak. Obecnie jest tylko „starsze niż N dni” i „młodsze niż N dni” – brakuje wyboru **konkretnego przedziału kalendarzowego**. Przypadki użycia:

- Odświeżyć tylko artykuły z konkretnej kampanii / batcha (np. 1–15 lutego).
- Powtórna próba tylko dla artykułów zmodyfikowanych w wybranym dniu/dniach (np. wczoraj).
- Celowane odświeżanie bez liczenia „dni wstecz” – użytkownik widzi kalendarz i wybiera zakres.

**Spójność z obecnym modelem:** Data, na której opiera się wybór, powinna być **ta sama co dziś** – pole **last_updated** z frontmatter (z fallbackiem na datę z nazwy pliku), a nie data modyfikacji pliku na dysku (mtime). Dzięki temu zakres dat oznacza „artykuły z last_updated w tym przedziale”.

---

## Gdzie w UI

W zakładce **„Odśwież artykuły”**, w sekcji **„Zakres”**:

- Obecnie: „Starsze niż (dni)” + „Młodsze niż (dni)” + limit.
- Rozszerzenie: **„Od daty”** i **„Do daty”** (np. dwa pola typu date lub combobox z datami). Gdy **oba** są ustawione, tryb „z zakresu dat” ma pierwszeństwo nad „starsze/młodsze niż N dni”. Gdy tylko jeden zakres (dni albo daty) jest ustawiony, działa jak dziś / tylko nowy tryb.

Ewentualnie jedna opcja „Zakres dat” z dwoma polami: **Data od**, **Data do** (włącznie). Puste = nie używaj zakresu dat (użyj „starsze/młodsze niż” jak dotąd).

---

## Zachowanie i edge cases

- **Przedział:** last_updated **≥ od** i **≤ do** (włącznie po obu stronach).
- **Kolejność:** np. od najstarszego do najnowszego (jak przy „starsze niż”), żeby wynik był przewidywalny; limit jak dziś.
- **Od > do:** Traktować jako błąd walidacji i nie uruchamiać odświeżania (komunikat w UI).
- **Tylko jedna data:** Opcjonalnie: „Od daty” bez „Do” = od tej daty do dziś; „Do daty” bez „Od” = od początku do tej daty. Dla prostoty pierwszego wdrożenia można **wymagać obu** pól przy trybie „z zakresu dat”.
- **Brak last_updated:** Artykuły bez last_updated (lub z nieparsowalną datą) są pomijane przy filtrowaniu po zakresie (tak jak dziś przy „starsze/młodsze niż”).

---

## Za i przeciw

| Za | Przeciw |
|----|--------|
| Precyzyjna kontrola: „tylko ten przedział”. | Więcej elementów w UI (dwa pola dat). |
| Naturalne dla użytkownika (kalendarz zamiast „N dni”). | Należy ustalić priorytet: zakres dat vs „starsze/młodsze niż” (rekomendacja: zakres dat ma pierwszeństwo gdy obie daty podane). |
| Spójne z logiką last_updated. | Trzeba dodać w skrypcie obsługę --from-date / --to-date i nową funkcję find_articles_in_date_range. |

---

## Rekomendacja

**Wdrożyć.**

1. **Skrypt `refresh_articles.py`:**
   - Argumenty: `--from-date YYYY-MM-DD`, `--to-date YYYY-MM-DD` (opcjonalne).
   - Gdy **oba** podane: wybór artykułów z `last_updated` w przedziale [from_date, to_date] (włącznie); funkcja `find_articles_in_date_range(articles_dir, from_date, to_date, limit)`.
   - Gdy tylko jeden lub żaden: działanie jak dotąd (--days / --max-days).

2. **Aplikacja (zakładka Odśwież):**
   - W sekcji „Zakres”: dwa pola **„Od daty”** i **„Do daty”** (puste = nie używaj zakresu).
   - Walidacja: jeśli oba wypełnione i od > do → komunikat, bez uruchamiania.
   - Przy „Uruchom odświeżanie” przekazać `--from-date` i `--to-date` gdy obie daty ustawione; wtedy nie przekazywać --days/--max-days (albo przekazywać, ale skrypt priorytetyzuje zakres dat).

3. **Opis:** Np. „Odśwież z okresu: wybierz datę od i do – odświeżane będą tylko artykuły z last_updated w tym zakresie.”

4. **Data:** Bazować na **last_updated** (frontmatter / nazwa pliku), nie na mtime – spójnie z resztą odświeżania.

---

**Podsumowanie:** Pomysł jest sensowny i wart wdrożenia. Rekomendacja: dodać opcję zakresu dat w zakładce Odśwież oraz argumenty --from-date / --to-date w refresh_articles.py, z priorytetem dla zakresu dat gdy obie daty są podane.
