# Usuwanie artykułów wg daty i zakresu (Flowtaro Monitor)

## 1. Gdzie jest funkcja

Zakładka **„Czyść nieżywe”** (Clean non-live) w Flowtaro Monitor zawiera dwie sekcje:

### A) Usuń artykuły z wybranego dnia
- **Pola:** Data (YYYY-MM-DD).
- **Przyciski:** Podgląd, Wykonaj usunięcie.
- **Efekt:** Usuwane są **wszystkie** artykuły i szkielety z podanego dnia (archiwizacja do `content/articles_archive/`, usunięcie z kolejki, use case'y → discarded, usunięcie z `public/`).
- **Tip:** Aby usunąć tylko część artykułów z jednego dnia, użyj sekcji „Usuń artykuły z zakresu dat” z tą samą datą w polach Od i Do, wczytaj listę i zaznacz tylko wybrane.

### B) Usuń artykuły z zakresu dat (z wyborem)
- **Pola:** Od daty (YYYY-MM-DD), Do daty (YYYY-MM-DD).
- **Przyciski:** Wczytaj listę → lista stemów w Listboxie → Zaznacz wszystkie / Odznacz wszystkie → Podgląd → Wykonaj usunięcie zaznaczonych.
- **Efekt:** Usuwane są **tylko zaznaczone** pozycje z listy (archiwizacja, kolejka, use case'y, public/).
- **Zakres:** Można ustawić jeden dzień (Od = Do) albo wiele dni; lista zawiera wszystkie stemy z tego zakresu. Zaznaczasz ręcznie, które chcesz usunąć.

Skrypt: `scripts/remove_articles_by_date.py`  
Opcje: `--date`, `--date-from` / `--date-to`, `--stems "s1,s2,..."`, `--list-stems`, `--dry-run`, `--confirm`.

---

## 2. Ocena pomysłu: „Wypełnij zaznaczone” / Anuluj → usuwanie niezaznaczonych i status w kolejce

### Pomysł
Po zakończeniu **„Generuj z podglądem”** pojawia się dialog z listą wygenerowanych artykułów. Propozycja:
- Po **„Wypełnij zaznaczone”** oraz po **Anuluj**: pliki **.md** (szkielety) **niezaznaczonych** byłyby usuwane, a ich wpisy w kolejce otrzymywałyby **status inny niż todo** (np. `reverted` lub `skeleton_removed`), tak aby przy kolejnym „Generuj z podglądem” można było znowu je wybrać i doprowadzić do końca (np. ponowne wygenerowanie szkieletu + wypełnienie).

### Jak mogłoby to być realizowane
- **W momencie zamknięcia dialogu** (przyciski „Wypełnij zaznaczone” lub „Anuluj” / zamknięcie okna):  
  - **Niezaznaczone** = wszystkie stemy z listy podglądu minus stemy zaznaczone (przy Anuluj: wszystkie traktowane jako „niezaznaczone”).
- Dla każdego **niezaznaczonego** stemu:
  1. **Usunąć** pliki `content/articles/<stem>.md` (oraz opcjonalnie `.html` jeśli istnieje).
  2. **Kolejka:** usunąć wpis odpowiadający temu stemowi (jak dziś przy „Usuń zaznaczone”) **albo** ustawić w kolejce pole np. `status: reverted` / `skeleton_removed` (wymaga rozszerzenia schematu queue).
  3. **Use case'y:** **nie** ustawiać `discarded` (żeby pomysł nadal mógł wrócić do generowania); ewentualnie ustawić np. `status: todo` lub osobny status „do ponownego wygenerowania”.
- Przy **następnym** „Generuj z podglądem”: `generate_queue` buduje kolejkę z use case'ów (np. z `status: todo`); te pomysły znów trafiają do kolejki, `generate_articles` znowu tworzy szkielety, użytkownik znowu wybiera, które wypełnić.

Realizacja sprowadza się do: (1) wykrycia „niezaznaczonych” przy zamknięciu dialogu (Fill / Cancel), (2) wywołania logiki usuwania plików .md (i ewent. .html) tylko dla tych stemów, (3) aktualizacji `queue.yaml` (usunięcie wpisów lub nowy status) oraz ewentualnie `use_cases.yaml` (np. przywrócenie `todo`), przy zachowaniu spójności z `remove_articles_by_date` (archiwacja vs trwałe usunięcie – tu zwykle trwałe usunięcie .md, bez archiwacji, bo to „cofnięcie” podglądu).

### Za
- **Czysty stan:** Niezaznaczone szkielety nie zalegają na dysku; użytkownik nie musi ich ręcznie czyścić.
- **Powtórna szansa:** Pomysły z niezaznaczonych wracają do puli (use case z `todo` / kolejka), więc przy następnym „Generuj z podglądem” można je znowu wygenerować i wybrać do wypełnienia.
- **Spójność z intencją:** „Wypełniam tylko wybrane” = reszta jest jakby anulowana; automatyczne usunięcie niezaznaczonych to konsekwentne dokończenie tej decyzji.

### Przeciw
- **Ryzyko pomyłki:** Użytkownik może odznaczyć artykuł przez przypadek; automatyczne usuwanie .md i zmiana kolejki/use case'ów jest nieodwracalne (o ile nie ma archiwizacji).
- **Różnica Cancel vs Fill:** Przy **Anuluj** usuwanie „wszystkich” jako niezaznaczonych może być mylące („anulowałem, a jednak coś usunięto”). Wymaga bardzo jasnego opisu w UI.
- **Dwa zachowania:** Obecne „Usuń zaznaczone” usuwa **zaznaczone** i ustawia use case'y na `discarded`. Propozycja usuwa **niezaznaczone** i przywraca je do obiegu. Trzeba tego nie pomylić w komunikacie i w kodzie.
- **Archiwizacja:** Obecny „bezpieczny” flow (remove_articles_by_date) archiwizuje do `articles_archive`. Tutaj zwykle chcemy „cofnąć podgląd”, więc często zakłada się po prostu usunięcie .md (bez archiwacji). Wtedy przy pomyłce nie ma łatwego „odkopania” z archiwum.

### Rekomendacja
- **Wariant ostrożny (rekomendowany):**  
  Nie wdrażać automatycznego usuwania niezaznaczonych przy „Wypełnij zaznaczone” ani przy Anuluj. Zamiast tego:
  - Zachować obecne zachowanie (tylko zaznaczone idą do wypełnienia; „Usuń zaznaczone” usuwa zaznaczone).
  - Dodać w zakładce **„Czyść nieżywe”** / „Usuń artykuły z zakresu dat” krótką instrukcję: „Szkielety z podglądu, których nie wypełniłeś, możesz usunąć tutaj (zakres dat = dzień generowania, wczytaj listę i zaznacz te do usunięcia).”  
  Daje to ten sam efekt końcowy (usunięcie niechcianych szkieletów i ewentualny powrót do kolejki/use case'ów), ale z jasnym, świadomym wyborem użytkownika i bez ryzyka przypadkowego usunięcia.

- **Jeśli jednak wdrożyć automatyzację:**  
  Wprowadzić ją **tylko** przy **„Wypełnij zaznaczone”** (nie przy Anuluj): po wyborze „Wypełnij zaznaczone” najpierw dla **niezaznaczonych** usunąć .md (i ewent. .html), usunąć ich wpisy z kolejki i ustawić odpowiadające use case'y na `todo`. Przy **Anuluj** / zamknięciu okna nic nie zmieniać (wszystkie szkielety zostają). W UI dodać wyraźną informację: „Niezaznaczone szkielety zostaną usunięte z dysku i wrócą do puli do ponownego wygenerowania.” oraz opcję (checkbox?) „Usuń niezaznaczone i przywróć do puli” domyślnie wyłączoną, żeby wymagać świadomej zgody.

---

*Dokument generowany w ramach wytycznych do pipeline'u Flowtaro.*
