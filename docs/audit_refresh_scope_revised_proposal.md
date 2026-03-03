# Krytyczna ocena pomysłów + zaktualizowana propozycja (Zakres, Odśwież artykuły)

## Krytyczna ocena Twoich pięciu pomysłów

### 1. Usunięcie „Młodsze niż”, zostawienie Od/Do + „Starsze niż”; UX: radio, tylko pola dla trybu, obie daty wymagane, jedna linia podsumowania

**Ocena: sensowne i spójne.**

- Usunięcie „Młodsze niż” redukuje rzadko używany przypadek (odśwież „ostatnie N dni”) i usuwa konflikt z „Starsze niż”. Dwa tryby (Starsze niż / Zakres dat) są łatwe do ogarnięcia.
- Radio + pokazywanie tylko pól dla wybranego trybu + wymaganie obu dat przy „Zakres dat” + jedna linia podsumowania – to spójny zestaw zmian UX, bez wewnętrznych sprzeczności.
- **Uwaga:** Po usunięciu „Młodsze niż” w Monitorze skrypt `refresh_articles.py` nadal obsługuje `--max-days`; można go zostawić (wywołania z CLI) albo w dalszej kolejności uznać za deprecated. Nie blokuje to zmian w UI.

**Wniosek: przyjąć.**

---

### 2. „Zakres dat” – nie wpisywanie ręczne, tylko wybór z miniatury kalendarza

**Ocena: zalety i wady; zależne od stacku.**

- **Plusy:** Mniej błędów formatu (YYYY-MM-DD), czytelność dla użytkownika nieobytego z datami, spójność z resztą systemu (jeśli kalendarz jest już używany).
- **Minusy:**
  - W standardowym Tkinterze **nie ma** gotowego widgetu kalendarza. Trzeba dołożyć zależność (np. `tkcalendar`) lub pisać własny widżet.
  - Dodatkowa zależność = instalacja, aktualizacje, ewentualne problemy z pakowaniem (PyInstaller). Dla aplikacji desktopowej to realny koszt.
  - Dla użytkowników wpisujących często te same zakresy (np. „od 2025-01-01 do 2025-01-31”) wpis z klawiatury bywa szybszy niż klikanie w kalendarz.
- **Kompromis:** Zostawić **pole tekstowe** z walidacją i placeholderem (YYYY-MM-DD), ewentualnie dodać mały przycisk „📅” otwierający kalendarz **opcjonalnie** (gdy będzie bezbolesna zależność). Albo w pierwszej iteracji tylko pola + walidacja, kalendarz w kolejnej jeśli będzie wyraźna potrzeba.

**Wniosek: nie rekomendować kalendarza w pierwszej iteracji;** ewentualnie jako opcję później, jeśli pojawi się lekka, sprawdzona zależność. Na teraz: pola tekstowe + jasna walidacja + ewentualnie placeholder/tooltip.

---

### 3. Licznik: „Ostatnie odświeżanie miało miejsce X dni temu”

**Ocena: wartościowe, przy jasnej definicji „ostatniego odświeżania”.**

- **Sens:** Sygnalizuje, kiedy ostatnio cokolwiek odświeżano; zmniejsza ryzyko przypadkowego „podwójnego” masowego odświeżania.
- **Implementacja:** Wymaga zapisania momentu „ostatniego odświeżania”. Dwa warianty:
  - **A)** Monitor przy starcie odświeżania zapisuje timestamp (np. w `~/.flowtaro_monitor/last_refresh_run.txt` lub w katalogu projektu `logs/`). Licznik = „od ostatniego **uruchomienia** odświeżania z Monitora”.
  - **B)** Skrypt `refresh_articles.py` na końcu udanego runu zapisuje timestamp (np. `logs/last_refresh_completed.txt`). Licznik = „od ostatniego **zakończonego** odświeżania”.
- **B)** jest bardziej sensowne merytorycznie („ostatnie udane odświeżanie”), ale wymaga zmiany skryptu. **A)** wystarczy w Monitorze i nie dotyka skryptu.
- **Preferencja:** Wariant A w Monitorze (zapis przy starcie runu) – prosty wdrożeniowo, wystarczający do „ostatni run był X dni temu”. Ewentualnie później ujednolicenie na B jeśli chcemy „ostatnie udane zakończenie”.

**Wniosek: przyjąć;** w pierwszej wersji licznik w Monitorze na podstawie zapisu przy starcie odświeżania (wariant A).

---

### 4. Zmiana nazwy przycisku „Uruchom odświeżanie” → „Odśwież artykuły”

**Ocena: OK, z drobną uwagą.**

- Nazwa zakładki to już „Odśwież artykuły”; przycisk „Odśwież artykuły” powtarza tę samą akcję wprost i jest zrozumiały.
- Możliwa „redundancja” (ta sama fraza co tab) jest akceptowalna – wiele aplikacji ma przycisk głównej akcji zbieżny z nazwą ekranu.
- Krótsza alternatywa (np. „Odśwież”) też byłaby OK; „Odśwież artykuły” jest jednak bardziej jednoznaczne.

**Wniosek: przyjąć zmianę na „Odśwież artykuły”.**

---

### 5. Usunięcie przycisku „Ponów tylko nieudane” i przeniesienie tej logiki do okna po dry-run: pokazywanie statusów (w tym nieudanych) jako podpowiedź do wyboru

**Ocena: koncepcyjnie dobra, ale wymaga doprecyzowania, żeby nie pogorszyć workflow.**

- **Obecny stan:** Przycisk „Ponów tylko nieudane” czyta `logs/last_refresh_failed.txt` i uruchamia odświeżanie **tylko** tych slugów (bez dry-run, bez zakresu dat). Jedno kliknięcie = „odśwież dokładnie te, które ostatnio się nie udały”.
- **Pomysł:** Nie mieć osobnego przycisku; w oknie wyboru po dry-run pokazywać statusy (m.in. „nieudany”) i tam użytkownik ma zaznaczyć, co odświeżyć (w tym nieudane).
- **Problem:** Lista w oknie po dry-run pochodzi **z wyniku dry-run** – czyli z aktualnego zakresu (Starsze niż N / Zakres dat). Artykuły nieudane mogą mieć **dowolny** `last_updated` (np. sprzed dwóch miesięcy). Jeśli użytkownik zrobi dry-run „Starsze niż 7 dni”, na liście **w ogóle nie będzie** starych nieudanych. Nie da się ich wtedy „zaznaczyć” w tym samym oknie.
- **Żeby pomysł był spójny, trzeba jedno z dwóch:**
  - **Wariant A – „Dołącz nieudane do listy”:** W oknie wyboru po dry-run lista = artykuły z dry-run **plus** (jeśli plik `last_refresh_failed.txt` istnieje) artykuły z tego pliku, które **nie** są już na liście. Przy każdym wierszu widać etykietę: np. „z zakresu” / „nieudany (ostatni run)”. Użytkownik zaznacza, co chce (w tym nieudane). Wtedy jeden przycisk „Ponów tylko nieudane” jest zbędny – nieudane i tak wylądują na liście (z etykietą), a użytkownik może je szybko zaznaczyć (np. „Zaznacz tylko nieudane”).
  - **Wariant B – Osobny tryb „Lista tylko nieudane”:** Np. radio w Zakresie: „Starsze niż” | „Zakres dat” | „Tylko nieudane z ostatniego runu”. Przy „Tylko nieudane” uruchomienie (np. od razu dry-run lub od razu run) operuje wyłącznie na `last_refresh_failed.txt`. Wtedy nadal nie ma osobnego przycisku „Ponów tylko nieudane”, ale jest jawny tryb zakresu.
- **Rekomendacja:** **Wariant A** – w oknie wyboru po dry-run:
  - Lista = wynik dry-run (z zakresu) **+** slugi z `last_refresh_failed.txt` niewystępujące w tym wyniku.
  - Przy każdym wpisie krótka etykieta/status: np. „nieudany”, „blocked”, „z zakresu” (np. z frontmatter `status` + przynależność do failed).
  - Opcjonalnie przycisk „Zaznacz tylko nieudane” / „Odznacz nieudane” dla szybkiego wyboru.
  - Przycisk „Ponów tylko nieudane” znika; „ponów nieudane” = dry-run (dowolny zakres) → w oknie widać nieudane z etykietą → zaznaczasz je (ręcznie lub „Zaznacz tylko nieudane”) → „Odśwież zaznaczone”.

**Wniosek: przyjąć ideę (usunąć przycisk, statusy w oknie wyboru), ale wdrożyć to jako wariant A (dołączenie nieudanych do listy + etykiety statusów + ewentualnie „Zaznacz tylko nieudane”).** Bez tego nieudane spoza aktualnego zakresu byłyby niewidoczne i funkcja „ponów nieudane” by zniknęła.

---

## Zaktualizowana propozycja modyfikacji (jedna lista)

| # | Zmiana | Za | Przeciw | Rekomendacja |
|---|--------|-----|--------|--------------|
| **1** | Usunąć „Młodsze niż”. Zostawić tylko tryby „Starsze niż” i „Zakres dat”. Radio (lub zakładki) – jawny wybór trybu; pokazywanie tylko pól dla wybranego trybu. Przy „Zakres dat” wymagane obie daty. Jedna linia podsumowania przed uruchomieniem (np. „Zakres: starsze niż 90 dni, limit 10”). | Mniej opcji, jasna hierarchia, mniej pomyłek. | Tracisz „odśwież ostatnie N dni” w UI (rzadki przypadek). | **Wdrożyć.** |
| **2** | Zakres dat: zamiast wpisywania dat – wybór z minikalendarza. | Mniej błędów formatu, wygodniej dla części użytkowników. | Brak kalendarza w Tk; zależność (tkcalendar) lub własny widget; pakowanie; dla power userów wpis bywa szybszy. | **Nie w pierwszej iteracji.** Zostawić pola YYYY-MM-DD + walidacja + placeholder/tooltip. Ewentualnie kalendarz później jako opcja. |
| **3** | Licznik „Ostatnie odświeżanie: X dni temu” (np. nad przyciskami). Zapis timestamp przy **starcie** odświeżania z Monitora (plik w prefs lub `logs/`). | Świadomość „kiedy ostatnio”; mniej przypadkowego powtarzania. | Jedna dodatkowa zmienna stanu i odczyt pliku. | **Wdrożyć** (wersja „od ostatniego uruchomienia”). |
| **4** | Zmiana etykiety przycisku z „Uruchom odświeżanie” na „Odśwież artykuły”. | Spójność z nazwą zakładki, czytelna akcja. | Drobna redundancja z nazwą zakładki. | **Wdrożyć.** |
| **5** | Usunąć przycisk „Ponów tylko nieudane”. W oknie wyboru po dry-run: (a) lista = wynik dry-run **+** slugi z `last_refresh_failed.txt` (bez duplikatów); (b) przy każdym wpisie etykieta statusu (np. „nieudany”, „blocked”, „z zakresu”); (c) opcjonalnie „Zaznacz tylko nieudane” / „Odznacz nieudane”. | Jedna ścieżka: zawsze wybór z listy; nieudane widoczne w kontekście; brak osobnego przycisku. | Wymaga rozszerzenia okna wyboru (kolumna/etykieta statusu, dołączenie listy failed, ewentualnie przyciski zaznacz/odznacz nieudane). | **Wdrożyć** w formie **wariantu A** (dołączenie nieudanych do listy + statusy + szybkie zaznaczenie nieudanych). |

---

## Rekomendacja końcowa

- **Wdrożyć w pierwszej iteracji:** punkty **1, 3, 4, 5** (w tym 5 jako wariant A: nieudane w oknie po dry-run + statusy + „Zaznacz tylko nieudane”, bez osobnego przycisku).
- **Nie wdrażać na razie:** punkt **2** (kalendarz); zostawić pola dat z walidacją.
- **Opcjonalnie w przyszłości:** minikalendarz jako opcja przy polach dat (jeśli pojawi się lekka zależność i potrzeba).

Po Twoim zatwierdzeniu można przejść do konkretnych zmian w kodzie (flowtaro_monitor + i18n); nic nie koduję do momentu Twojej akceptacji.
