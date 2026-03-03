# Audyt: Zakres w zakładce „Odśwież artykuły” (Flowtaro Monitor)

## 1. Stan obecny – co jest w sekcji „Zakres”

| Element UI | Opis | Mapowanie na `refresh_articles.py` | Uwagi |
|------------|------|-------------------------------------|--------|
| **Starsze niż (dni)** | Combobox: 7, 14, 30, 60, 90 (domyślnie 90) | `--days N` | Odśwież artykuły z `last_updated` starszym niż N dni. |
| **Młodsze niż (dni)** | Combobox: — (wył.), 0, 1, 2, 3, 4, 5, 6 | `--max-days N` | Gdy ustawione: artykuły z ostatnich N dni (0 = tylko z dzisiaj). **Nadpisuje** „Starsze niż”. |
| **Od daty** / **Do daty** | Dwa pola tekstowe YYYY-MM-DD | `--from-date` / `--to-date` | Gdy **oba** wypełnione: zakres dat `last_updated`. **Ma pierwszeństwo** nad „Starsze niż” i „Młodsze niż”. |
| **Limit artykułów** | Combobox: Bez limitu, 1, 5, 10, 20, 50 | `--limit M` | Maks. liczba artykułów w jednym uruchomieniu. |
| **Dry-run** | Checkbox | `--dry-run` | Tylko lista kandydatów; po zakończeniu można wybrać część i uruchomić „Odśwież zaznaczone”. |

**Kolejność ważności w skrypcie:**  
1) Jeśli podano obie daty (od + do) → zakres dat.  
2) Jeśli podano „Młodsze niż” (max-days) → ostatnie N dni.  
3) W przeciwnym razie → „Starsze niż” (days).

Przy **„Odśwież zaznaczone”** (po dry-run) do wywołania dodawany jest plik z wybranymi slugami (`--include-file`); skrypt najpierw buduje listę według powyższych reguł, potem **zostawia tylko** artykuły z pliku.

---

## 2. Ocena sensowności i przydatności

### Mocne strony

- **Starsze niż (dni)** – czytelny, typowy przypadek: „odśwież to, co długo nie było aktualizowane”. Domyślne 90 dni jest rozsądne.
- **Limit artykułów** – ogranicza ryzyko i koszt jednego uruchomienia; wartości 1, 5, 10, 20, 50 pokrywają typowe potrzeby.
- **Dry-run + wybór artykułów** – dobra ścieżka: zobacz listę → wybierz podzbiór → odśwież tylko ten podzbiór.
- **Od daty / Do daty** – przydatne do precyzyjnego zakresu (np. „wszystkie z lutego”) lub powtórzenia tego samego zakresu.

### Problemy i niespójności

1. **Trzy różne tryby w jednym bloku**  
   Użytkownik widzi naraz: „Starsze niż”, „Młodsze niż”, „Od/Do daty”. Nie jest wprost widać, że:
   - „Od/Do daty” wygrywa nad resztą,
   - „Młodsze niż” wygrywa nad „Starsze niż”.  
   Brak jasnego wyboru trybu (np. radio: „Starsze niż” / „Młodsze niż” / „Zakres dat”) powoduje ryzyko pomyłek (np. ustawienie dni i dat i przekonanie, że liczą się oba).

2. **„Młodsze niż” vs „Starsze niż”**  
   - „Starsze niż 90 dni” = nieaktualizowane od 90+ dni (typowe „odśwież stare”).  
   - „Młodsze niż 2 dni” = aktualizowane w ostatnich 2 dobach („odśwież ostatnie”).  
   Dwa przeciwne kierunki w jednej sekcji bez etykiety trybu mogą mylić. Dodatkowo „Młodsze niż” ma mały zakres (0–6); użyteczność „odśwież tylko z dzisiaj/ostatniej doby” jest niszowa w porównaniu z dominującym „odśwież stare”.

3. **Puste pola Od/Do daty**  
   Gdy użytkownik wypełni tylko „Od daty” lub tylko „Do daty”, skrypt **ignoruje** te pola i używa „Starsze niż” / „Młodsze niż”. W UI nie ma o tym informacji (np. „Wymagane oba pola”).

4. **Limit przy „Odśwież zaznaczone”**  
   Przy wywołaniu z `--include-file` limit z formularza **nie** jest przekazywany w `_run_selective_refresh`. Lista to dokładnie wybrane stemy; limit byłby zbędny. Zachowanie jest OK, ale różnica względem zwykłego „Uruchom” (gdzie limit działa) może nie być oczywista dla użytkownika.

5. **Brak podsumowania zakresu**  
   Przed uruchomieniem użytkownik nie widzi np. „Zakres: artykuły starsze niż 90 dni, max 10 sztuk”. Taka jedna linijka pod przyciskami zmniejszyłaby błędy.

---

## 3. Propozycje modyfikacji / uproszczenia

### Opcja A: Uproszczenie bez zmiany logiki skryptu

- **Jednoznaczny wybór trybu** (np. radio):
  - **„Starsze niż N dni”** (domyślnie) – obecne „Starsze niż”, bez „Młodsze niż” w głównym widoku.
  - **„Młodsze niż N dni”** – opcjonalnie w rozwijanym „Zaawansowane” lub drugi radio z wartościami 0–6.
  - **„Zakres dat (od – do)”** – widoczne tylko gdy wybrany ten tryb; oba pola wymagane.
- **Komunikat** przy niepełnym zakresie dat: „Aby użyć zakresu dat, wypełnij oba pola: Od i Do.”.
- **Krótkie podsumowanie** przed startem: np. „Zakres: starsze niż 90 dni, limit 10” (na podstawie aktualnych wartości pól).

**Za:** mniej pomyłek, jasna hierarchia, bez zmiany `refresh_articles.py`.  
**Przeciw:** trzeba zaktualizować UI (radio, warunkowe pokazywanie pól).

---

### Opcja B: Uproszczenie z redukcją opcji

- **Zostawić tylko:**
  - **„Starsze niż (dni)”** (7, 14, 30, 60, 90) + **Limit** + **Dry-run**.
- **Usunąć z Zakresu:** „Młodsze niż”, „Od daty”, „Do daty”.
- **„Ponów tylko nieudane”** zostaje (nie zależy od Zakresu).
- Zakres dat i „młodsze niż” realizować w razie potrzeby przez:
  - dry-run → zapis listy → ręczna edycja pliku / przyszła opcja „Odśwież z pliku” (lista slugów).

**Za:** minimalny, najprostszy interfejs; pokrywa główny przypadek (odśwież stare).  
**Przeciw:** tracisz wygodę „odśwież z dokładnego przedziału dat” i „tylko z ostatnich N dni” w jednym kliku.

---

### Opcja C: Zachować możliwości, poprawić UX (bez usuwania)

- **Bez usuwania** „Młodsze niż” i „Od/Do daty”.
- **Dodać:**
  - Radio lub zakładki: **„Starsze niż”** | **„Młodsze niż”** | **„Zakres dat”** – pokazuj tylko powiązane pola (np. przy „Zakres dat” tylko Od/Do, przy „Starsze niż” tylko dni).
  - Walidację: przy „Zakres dat” wymagane oba pola; ewentualnie tooltip przy Od/Do: „Oba pola wymagane.”.
  - Jednolinijkowe **podsumowanie zakresu** nad przyciskiem „Uruchom odświeżanie”.
- **Opcjonalnie:** „Młodsze niż” przenieść do „Zaawansowane” (zwinięty panel), żeby domyślnie widoczne było tylko „Starsze niż” + limit + dry-run.

**Za:** zachowana pełna funkcjonalność, mniej błędów, czytelna hierarchia.  
**Przeciw:** więcej elementów UI (radio/zakładki, ewentualnie panel Zaawansowane).

---

## 4. Rekomendacja

- **Rekomendacja:** **Opcja C** (zachować wszystkie tryby, uporządkować UX).
  - Główny powód: zakres dat i „młodsze niż” są użyteczne (np. powtórzenie odświeżenia dla tego samego przedziału, retesty po zmianach), a ich usunięcie (Opcja B) ograniczałoby możliwości bez wyraźnej korzyści dla prostoty.
  - Opcja A jest bliska C; C jawnie zakłada też podsumowanie i ewentualne schowanie „Młodsze niż” pod „Zaawansowane”, co zmniejsza szum przy typowym użyciu („starsze niż” + limit).
- **Minimum do wdrożenia w pierwszej iteracji (nawet bez pełnej Opcji C):**
  - Wymaganie **obu** pól przy zakresie dat + krótki komunikat w UI („Aby użyć zakresu dat, wypełnij oba pola.”).
  - **Jedna linia podsumowania** przed uruchomieniem (np. „Zakres: starsze niż 90 dni, limit: 10” / „Zakres: od 2025-01-01 do 2025-02-20, limit: 20”).

---

## 5. Podsumowanie

| Aspekt | Ocena | Uwaga |
|--------|--------|--------|
| Przydatność „Starsze niż” + limit | Wysoka | Główny przypadek użycia. |
| Przydatność „Od/Do daty” | Średnia–wysoka | Przydatne przy powtarzalnych zakresach. |
| Przydatność „Młodsze niż” | Niska–średnia | Niszowe (np. „tylko z dzisiaj”). |
| Zrozumiałość hierarchii (co nad czym) | Niska | Brak jawnego wyboru trybu. |
| Ryzyko pomyłek (niepełne daty, mieszanie trybów) | Średnie | Warto wymusić oba pola i dodać podsumowanie. |

**Rekomendacja końcowa:** wdrożyć **Opcję C** (lub w pierwszym kroku minimum: walidacja zakresu dat + podsumowanie zakresu), **bez** usuwania obecnych możliwości Zakresu. Po zatwierdzeniu przez Ciebie można zaplanować konkretne zmiany w kodzie (flowtaro_monitor + ewentualnie i18n).
