# Propozycja: ponowienie odświeżania tylko dla nieudanych artykułów

## Cel

Umożliwić ponowną próbę odświeżenia **wyłącznie** tych artykułów, które w ostatnim uruchomieniu „Odśwież artykuły” zakończyły się komunikatem „Refresh failed”, **bez** ręcznego dry-run i wybierania ich z listy.

---

## Opcja A: Zapis listy nieudanych przez refresh_articles

**Mechanizm:**
- Skrypt `refresh_articles.py` na zakończenie (przed lub po Summary) zapisuje stemy wszystkich artykułów, dla których w tej sesji wystąpił „Refresh failed”, do pliku np. `logs/last_refresh_failed.txt` (jedna nazwa pliku bez .md na linię). Przy 0 failed plik nie jest tworzony lub jest pusty/usuwa się go.
- W zakładce „Odśwież artykuły” w Flowtaro Monitor pojawia się przycisk **„Ponów tylko nieudane”** (lub „Odśwież ostatnie nieudane”). Jest aktywny tylko gdy plik `logs/last_refresh_failed.txt` istnieje i jest niepusty.
- Kliknięcie uruchamia `refresh_articles.py --include-file logs/last_refresh_failed.txt` (z tymi samymi opcjami AI co zwykle: quality_gate, min-words-override, quality_retries, ewentualnie re-skeleton jeśli było zaznaczone – albo bez re-skeleton dla prostoty przy „ponów”). Nie uruchamia się dry-run.

**Zalety:** Proste, jedno źródło prawdy (skrypt sam wie, co failed).  
**Wady:** Trzeba utrzymywać jeden mały plik; przy wielu równoległych „sesjach” użytkowników teoretycznie konflikt (w ACM zwykle jeden użytkownik).

---

## Opcja B: Parsowanie ostatniego logu

**Mechanizm:**
- Nie zmieniamy `refresh_articles.py`. Flowtaro Monitor po zakończeniu odświeżania zapisuje pełny log (już to robi przy „Zapisz log do pliku” / „Zapisz do logs/”). W pamięci mamy ostatni output w `last_output_holder` dla akcji `refresh_articles`.
- Przycisk **„Ponów tylko nieudane”** w zakładce Odśwież: po kliknięciu parsujemy ostatni zapisany log (z `last_output_holder` lub z pliku w `logs/` z ostatniego uruchomienia) w poszukiwaniu linii typu `Refresh failed: <stem>.md (exit code ...)`. Wyciągamy listę stemów, zapisujemy do pliku tymczasowego i uruchamiamy `refresh_articles.py --include-file <tempfile>`.

**Zalety:** Brak zmian w refresh_articles; wszystko po stronie UI.  
**Wady:** Zależność od formatu komunikatu („Refresh failed: … .md”); jeśli użytkownik nie zapisał logu i zrestartował aplikację, lista może być pusta; nieco bardziej kruche.

---

## Rekomendacja

**Opcja A** – zapis `last_refresh_failed.txt` w `refresh_articles.py` + przycisk „Ponów tylko nieudane” w UI, który wywołuje refresh z `--include-file logs/last_refresh_failed.txt`.

- Zachowanie: po każdym uruchomieniu odświeżania lista nieudanych jest aktualna; użytkownik może wielokrotnie klikać „Ponów tylko nieudane” (np. po poprawce promptów / progu), aż plik będzie pusty lub nie będzie go w ogóle.
- Opcjonalnie: po udanym „Ponów tylko nieudane” można wyczyścić lub skrócić `last_refresh_failed.txt` (usunąć stemy, które tym razem przeszły), żeby kolejne „ponów” dotyczyło tylko wciąż nieudanych.

---

**Do zatwierdzenia:** wybór opcji (A vs B) oraz ewentualna decyzja, czy przy „Ponów tylko nieudane” przekazywać też flagę `--re-skeleton` jeśli była zaznaczona przy ostatnim pełnym odświeżaniu (prościej: przy „Ponów” nie przekazywać `--re-skeleton`, żeby tylko ponowić fill).
