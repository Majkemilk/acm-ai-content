# Ocena pomysłu: nowy status dla niezaznaczonych po „Generuj z podglądem” (Fill / Anuluj)

Ocena na życzenie; bez zmian w kodzie.

---

## 1. Treść propozycji

- **Po „Wypełnij zaznaczone”** oraz **po „Anuluj”**: niezaznaczone pliki `.md` są usuwane, a ich wpisy w kolejce dostają **nowy status** (nie `todo`), np. `preview_skipped`.
- Ten nowy status ma przy **następnym** „Generuj z podglądem” umożliwiać **ponowne wybranie** tych pozycji do zaznaczenia i doprowadzenia workflow do końca (szkielety → wypełnienie → huby → sitemap → render).

---

## 2. Stan obecny (krótko)

| Akcja | Niezaznaczone | Zaznaczone |
|-------|----------------|------------|
| **Wypełnij zaznaczone** | .md usuwane, status → `todo` | fill + reszta workflow |
| **Anuluj** | brak akcji ( .md zostają, status `generated` ) | — |
| **Usuń zaznaczone** | — | .md usunięte, wpisy/usecase’y oznaczane discarded |

- `generate_articles` przetwarza **tylko** wpisy z `status: todo` i ustawia im `generated`.
- Przy kolejnym „Generuj z podglądem” **wszystkie** `todo` (w tym te wrócone z „Wypełnij zaznaczone”) znowu trafiają do generowania szkieletów i do dialogu.

---

## 3. Różnica: propozycja vs tryb „Tylko podgląd” (kolejki)

| Aspekt | Tryb kolejki „Tylko podgląd” | Propozycja (nowy status po podglądzie) |
|--------|------------------------------|----------------------------------------|
| **Co uruchamiasz** | Jedna akcja: `generate_queue --dry-run` | Pełny podgląd: use_cases → generate_queue → generate_articles → dialog |
| **Pliki .md** | Nie powstają | Powstają szkielety; potem część jest usuwana (niezaznaczone) |
| **Kolejka** | Nie jest zapisywana (dry-run) | Jest zapisywana; nowy status (`preview_skipped`) dla niezaznaczonych |
| **Cel** | Zobaczyć, co *trafiłoby* do kolejki, bez efektów | Wygenerować szkielety, wybrać część do wypełnienia; resztę „odłożyć” na następny podgląd |
| **Ponowne użycie** | Brak (tylko raport) | Tak: przy następnym „Generuj z podglądem” pozycje z nowym statusem znów mogą być wygenerowane i wybrane |

„Tylko podgląd” = tylko raport kolejki, zero plików i zero zmiany statusów. Propozycja = pełny flow podglądu + **jednoznaczna semantyka**: „był w podglądzie, nie wybrano go” (nowy status) z możliwością ponownego wyboru przy kolejnym podglądzie.

---

## 4. Jak mogłoby to być realizowane

1. **Nowy status w kolejce**  
   Np. `preview_skipped` (albo `skipped`, `pending_preview`). Znaczenie: „już był w podglądzie jako szkielet, użytkownik go nie wybrał; przy następnym podglądzie można go znowu wygenerować i wybrać”.

2. **Zachowanie przy „Wypełnij zaznaczone”**  
   Jak dziś: niezaznaczone → usuń `.md`. Zamiast ustawiać status na `todo` → ustawić na `preview_skipped`.

3. **Zachowanie przy „Anuluj”**  
   Traktować jak „wszystkie niezaznaczone”: usunąć **wszystkie** szkielety z tego podglądu i wszystkim odpowiadającym wpisom w kolejce ustawić status `preview_skipped` (albo tylko tym, które mają jeszcze `generated` po tym runie).

4. **Następny „Generuj z podglądem”**  
   Aby te pozycje znów dało się wybrać i doprowadzić do końca:
   - **generate_queue**: nie zmieniać wpisów z `preview_skipped` na `todo` (albo tylko w trybie „dodaj też skipped”).
   - **generate_articles**: przy podglądzie przetwarzać nie tylko `todo`, ale i `preview_skipped` (np. flaga `--include-preview-skipped` lub osobna konwencja statusów). Efekt: szkielety tych pozycji znów powstają i trafiają do dialogu; użytkownik może je zaznaczyć i „Wypełnij zaznaczone” doprowadzi je do końca.

5. **Opcjonalnie w UI**  
   W dialogu listy: dwie grupy, np. „Nowe (z bieżącego podglądu)” vs „Wcześniej pominięte” (z `preview_skipped`), żeby było widać, co jest świeże z use_cases, a co wraca z poprzedniego podglądu.

6. **generate_queue**  
   Przy dodawaniu z use_cases tylko nowe wpisy dostają `todo`. Istniejące w kolejce z `preview_skipped` nie są nadpisywane na `todo` (żeby nie mieszać z „świeżymi” z use_cases, jeśli chcesz to rozdzielać).

---

## 5. Za (pros)

| Argument | Uzasadnienie |
|----------|----------------|
| **Spójne Anuluj** | Przy Anuluj stan kolejki i dysku jest określony: szkielety z tego podglądu znikają, wpisy nie wracają do `todo`, tylko do „do ponownego podglądu”. |
| **Semantyka statusu** | `preview_skipped` jasno oznacza „był w podglądzie, nie wybrano”; `todo` może zostać zarezerwowane dla „świeżych” z use_cases. |
| **Kontrola nad „świeżością”** | Można rozróżniać w kolejce: nowe pomysły (`todo`) vs odłożone z poprzedniego podglądu (`preview_skipped`); ewentualnie w UI pokazać to w dwóch grupach. |
| **Brak niepotrzebnego mieszania** | Obecnie niezaznaczone wracają do `todo`, więc przy następnym podglądzie mieszają się z każdym nowym batch’em. Nowy status pozwala trzymać „odłożone” osobno. |
| **Ponowny wybór bez gubienia** | Użytkownik może za drugim (trzecim) razem wybrać te same tematy w „Generuj z podglądem” i doprowadzić je do końca, bez ręcznego grzebania w queue/use_cases. |

---

## 6. Przeciw (cons)

| Argument | Uzasadnienie |
|----------|----------------|
| **Więcej logiki** | generate_articles musi obsłużyć drugi status (np. `preview_skipped`) przy podglądzie; generate_queue i ewentualnie use_cases muszą być spójne (kto ustawia / czyta status). |
| **Zmiana zachowania** | Dziś niezaznaczone wracają do `todo` i przy następnym „Generuj z podglądem” i tak są znowu w puli. Po zmianie będą w puli tylko jeśli generate_articles jawnie weźmie `preview_skipped` — trzeba to dopisać i przetestować. |
| **Anuluj = czyszczenie** | Przy Anuluj usuwanie wszystkich szkieletów z tego runu może być zaskakujące dla kogoś, kto myślał „tylko zamykam dialog”. Warto to wyraźnie opisać w UI (np. tooltip / krótka informacja). |
| **Dwa „źródła” w podglądzie** | Jeśli w dialogu będą dwie grupy (nowe vs pominięte), trzeba spójnie budować listę (np. z jednego runu generate_articles biorącego `todo` + `preview_skipped`) i ewentualnie oznaczać pochodzenie w UI. |

---

## 7. Rekomendacja

**Rekomendacja: wdrożyć propozycję**, z kilkoma warunkami:

1. **Wprowadzić status `preview_skipped`** (lub inną, spójną nazwę) i przy „Wypełnij zaznaczone” oraz „Anuluj” ustawiać go niezaznaczonym (przy Anuluj — wszystkim z bieżącego podglądu) zamiast `todo`, przy jednoczesnym usuwaniu odpowiadających plików `.md`.
2. **W generate_articles** dodać obsługę `preview_skipped` w trybie podglądu (np. gdy wywołanie z monitora w kontekście podglądu, albo jawna flaga), tak aby przy następnym „Generuj z podglądem” te wpisy znów generowały szkielety i trafiały do dialogu.
3. **Anuluj** opisać w UI (np. podpis/tooltip): „Zamknięcie bez wypełniania: szkielety z tego podglądu zostaną usunięte, a pozycje w kolejce oznaczone jako do ponownego podglądu”.
4. **Opcjonalnie** w dialogu listy rozróżnić grupy „Nowe” / „Wcześniej pominięte” — dla przejrzystości, nie jako warunek pierwszego wdrożenia.

Różnica względem trybu „Tylko podgląd” dla kolejki pozostaje taka, jak w sekcji 3: „Tylko podgląd” to tylko suchy raport kolejki; ta propozycja dotyczy pełnego flow „Generuj z podglądem” i porządku statusów po wyborze / anulowaniu, z możliwością ponownego wyboru przy kolejnym podglądzie.
