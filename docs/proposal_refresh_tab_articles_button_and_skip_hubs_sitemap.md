# Propozycja: zakładka Odśwież artykuły — przycisk „Artykuły do odświeżenia” i „Pomiń render huba i sitemapy”

Propozycja do zatwierdzenia przed wdrożeniem; bez zmian w kodzie do momentu akceptacji.

---

## 1. Pomysł (w skrócie)

**A.** Zamiast checkboxa Dry-run dodać na dole przycisk **„Artykuły do odświeżenia”**, który otwiera dialog z listą artykułów do odświeżenia. Przycisk **„Odśwież artykuły”** usunąć.

**B.** W sekcji Opcje AI zmienić checkbox **„Pomiń render”** na **„Pomiń render huba i sitemapy”**. Render strony (render_site) ma pozostawać standardową końcówką workflow także przy zaznaczonym tym checkboxie.

---

## 2. Za (pros)

### 2.1 Przycisk „Artykuły do odświeżenia” zamiast Dry-run + usunięcie „Odśwież artykuły”

| Za | Uzasadnienie |
|----|--------------|
| **Jeden wejściowy krok** | Użytkownik zawsze najpierw widzi listę (zgodną z zakresem i limitem), potem decyduje, co odświeżyć. Brak ryzyka „odśwież wszystko” bez podglądu. |
| **Spójność z „Ponów tylko nieudane”** | Obie ścieżki prowadzą do tego samego dialogu wyboru artykułów; jedna metoda interakcji. |
| **Mniej opcji** | Usunięcie checkboxa Dry-run redukuje liczbę elementów w UI i usuwa dublowanie („Dry-run” vs „Odśwież” z wyborem w dialogu). |
| **Wymuszenie świadomego wyboru** | Trzeba wejść w listę i (co najmniej) potwierdzić zakres — mniej przypadkowego „kliknięcia Odśwież”. |

### 2.2 „Pomiń render huba i sitemapy” zamiast „Pomiń render”

| Za | Uzasadnienie |
|----|--------------|
| **Precyzyjna nazwa** | Użytkownik wie, że pomija tylko hub i sitemapę, a nie cały render strony. |
| **Strona zawsze zaktualizowana** | Po odświeżeniu treści public zawsze jest przebudowany (render_site), więc nie ma „odświeżonych artykułów bez aktualnego public”. |
| **Szybszy przebieg gdy nie trzeba huba/sitemapy** | Przy pracy tylko nad artykułami można pominąć generate_hubs i generate_sitemap, skracając czas bez rezygnacji z render_site. |

---

## 3. Przeciw (cons)

### 3.1 Przycisk „Artykuły do odświeżenia” + usunięcie „Odśwież artykuły”

| Przeciw | Uzasadnienie |
|---------|--------------|
| **Dodatkowy krok przy „wszystkie”** | Kto chciał odświeżyć „wszystkie z zakresu” jednym kliknięciem, musi teraz: otworzyć listę → zaznaczyć wszystkie (lub dodać „Odśwież wszystkie z listy”) → potwierdzić. |
| **Zależność od dry-run** | Lista jest budowana przez uruchomienie refresh_articles --dry-run; przy błędzie skryptu lub braku outputu dialog może być pusty lub nie otworzyć się. |
| **Zmiana przyzwyczajeń** | Użytkownicy przyzwyczajeni do „Odśwież artykuły” bez dry-run muszą przejść na nowy flow. |

### 3.2 „Pomiń render huba i sitemapy”

| Przeciw | Uzasadnienie |
|---------|--------------|
| **Brak opcji „pomiń cały render”** | Obecne „Pomiń render” pozwalało pominąć hubs + sitemapę + render_site (np. do szybkich testów). Po zmianie w UI nie ma już tej opcji (można ją dodać osobno, np. drugi checkbox). |
| **Zmiana skryptu** | refresh_articles.py musi dostać nową flagę (np. --no-hubs-sitemap) i logikę: gdy ustawiona — tylko render_site; gdy brak — generate_hubs, generate_sitemap, render_site. |

---

## 4. Proponowana wersja implementacji

### 4.1 Zakładka Odśwież artykuły (flowtaro_monitor)

**A. Lista i przycisk**

- Usunąć checkbox **Dry-run**.
- Usunąć przycisk **„Odśwież artykuły”** (obecny `run_btn` z `t("refresh.run")`).
- Dodać na dole (w tym samym wierszu co Anuluj lub w osobnym) przycisk **„Artykuły do odświeżenia”** (np. `t("refresh.btn_articles_to_refresh")`).
- Akcja przycisku:
  1. Zbierać parametry zakresu/limitu jak dziś `run()`.
  2. Uruchomić `refresh_articles` z **--dry-run** (i z tymi samymi opcjami co dziś: dni/zakres, limit, block_on_fail, remap, re_skeleton, quality_retries, no_render → patrz 4.2).
  3. Po zakończeniu (sukces) sparsować output i wywołać **ten sam dialog** co dziś po dry-run: `_show_article_selector(..., t("sel.title_refresh"), merged, t("sel.confirm_refresh"), _run_selective_refresh, ...)`.
  4. W dialogu przycisk potwierdzenia np. „Odśwież zaznaczone” wywołuje `_run_selective_refresh(stems)` z --include-file (bez --dry-run).

- Opcjonalnie: w dialogu dodać przycisk **„Odśwież wszystkie z listy”** (wszystkie z wyświetlonej listy bez konieczności zaznaczania), żeby zachować możliwość jednego kliknięcia „odśwież cały zakres”.

- **Anuluj** zostaje (anulowanie uruchomionego dry-run / refresh).

**B. Checkbox „Pomiń render” → „Pomiń render huba i sitemapy”**

- W sekcji Opcje AI zamienić etykietę i hint:
  - Tekst: np. `t("refresh.no_hubs_sitemap")` = „Pomiń render huba i sitemapy”.
  - Hint: np. `t("refresh.no_hubs_sitemap_desc")` = „Po odświeżeniu i tak uruchamiany jest render strony (public). Zaznacz, aby nie uruchamiać generate_hubs ani generate_sitemap.”
- Zmienna: np. `no_hubs_sitemap_var` (zamiast lub obok `no_render_var`). Do skryptu przekazywać np. `--no-hubs-sitemap` (patrz 4.2).
- **Nie** przekazywać już `--no-render` z tego checkboxa (albo całkiem usunąć przekazywanie --no-render, jeśli rezygnujemy z „pomiń cały render” w UI).

### 4.2 Skrypt refresh_articles.py

- Dodać argument np. `--no-hubs-sitemap`: gdy ustawiony, po zakończeniu odświeżania **nie** uruchamiać `generate_hubs.py` ani `generate_sitemap.py`, ale **uruchomić** `render_site.py`.
- Obecna logika: `if not args.no_render: for name in ("generate_hubs.py", "generate_sitemap.py", "render_site.py"): ...`
- Nowa propozycja:
  - Gdy `args.no_render`: nie uruchamiać żadnego z trzech (zachowanie wstecz).
  - Gdy `args.no_hubs_sitemap` (i brak `no_render`): uruchomić **tylko** `render_site.py`.
  - Gdy brak obu: uruchomić po kolei generate_hubs, generate_sitemap, render_site.

### 4.3 i18n (PL / EN)

- Dodać klucze: `refresh.btn_articles_to_refresh`, `refresh.no_hubs_sitemap`, `refresh.no_hubs_sitemap_desc`.
- Usunąć lub zostawić (dla ewentualnego „Pomiń cały render”): `refresh.no_render`, `refresh.no_render_desc` — w tej wersji można zostawić w słowniku i nie używać w zakładce.

---

## 5. Rekomendacja

- **Rekomendacja: wdrożyć obie zmiany**, z jedną modyfikacją względem „usuń przycisk Odśwież artykuły”:
  - W dialogu listy dodać **„Odśwież wszystkie z listy”** (jeden przycisk w dialogu), żeby zachować ścieżkę „odśwież cały aktualny zakres w jednym kroku” bez konieczności zaznaczania każdego artykułu. Wtedy flow to: „Artykuły do odświeżenia” → lista → „Odśwież wszystkie z listy” lub zaznaczenie podzbioru → „Odśwież zaznaczone”.
- Dla checkboxa: **pełna rekomendacja** — zmiana na „Pomiń render huba i sitemapy” z zawsze uruchamianym render_site przy odświeżaniu; opcję „pomiń cały render” można dodać później osobnym checkboxem, jeśli będzie potrzebna.

Po zatwierdzeniu tej propozycji można przystąpić do implementacji (flowtaro_monitor, refresh_articles.py, i18n).
