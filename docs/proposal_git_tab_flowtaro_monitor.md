# Propozycja: zakładka Git w Flowtaro Monitor (add, commit, push artykułów)

## Pomysł

Dodać w aplikacji **nową zakładkę**, która umożliwi:
- **dodawanie do stagingu** (git add) wybranych plików artykułów lub całego katalogu `content/articles`,
- **komitowanie** z możliwością wpisania komunikatu,
- **wysyłanie** zmian do zdalnego repozytorium (git push).

Cel: wykonywanie typowego cyklu „wygenerowane/odświeżone artykuły → add → commit → push” bez wychodzenia z aplikacji i bez otwierania terminala.

---

## Ocena merytoryczna

**Sens:** Tak. Obecny flow to: Generuj/Odśwież w Monitorze → potem ręcznie w terminalu lub innej aplikacji: `git add`, `git commit`, `git push`. Jedna aplikacja do „produkcji treści” i do wypchnięcia zmian do repozytorium uprości pracę i ograniczy pomyłki (np. zapomniany push).

**Spójność z projektem:**  
- Monitor już operuje na katalogu projektu (`get_project_root()`), tam jest `content/articles` i ewentualnie `.git`.  
- Nie ma dziś żadnej integracji z gitem – wszystko po stronie użytkownika.  
- Zakładka Git byłaby **opcjonalna w użyciu**: kto woli terminal, nie musi z niej korzystać.

**Ryzyka:**  
- Git to narzędzie z dużą odpowiedzialnością (nadpisanie historii, force push, konflikty). UI musi być **przejrzyste i bezpieczne** (bez domyślnego force, z potwierdzeniami przy push).  
- Różne środowiska: użytkownik może nie mieć gita w PATH, repozytorium może nie być skonfigurowane (brak remote, brak brancha). Trzeba to obsłużyć komunikatem zamiast cichej porażki.

---

## Zakres funkcji – opcje do wyboru

### Opcja 1: Minimalna („add + commit + push”)

- **Add:** jeden przycisk „Dodaj zmiany w artykułach” = `git add content/articles/` (ew. `content/` jeśli chcemy objąć queue, config – rekomendacja: na start tylko `content/articles/`).
- **Commit:** pole tekstowe na komunikat + przycisk „Commit”. Wykonuje `git commit -m "<message>"` na tym, co jest w stagingu. Walidacja: nie pozwolić na pusty komunikat.
- **Push:** przycisk „Push” = `git push` (domyślny remote i bieżący branch). Bez `--force`. Przy pierwszym pushu brancha można ewentualnie sugerować `--set-upstream` (albo wywołać `git push -u origin <current-branch>` gdy brak upstream).

**Zakres plików przy add:**  
- **1a)** Tylko `content/articles/` (rekomendowane na start – jasny zakres „artykuły”).  
- **1b)** `content/` (artykuły + queue, use_cases, config – wszystko co często się zmienia w ACM).

Do zatwierdzenia: 1a vs 1b.

---

### Opcja 2: Rozszerzona (lista plików + wybór)

- **Status:** Lista plików zmienionych/untracked (wynik `git status --short` w `content/articles/` lub `content/`), z checkboxami. Użytkownik wybiera, co trafia do stagingu.
- **Add:** „Dodaj zaznaczone” = `git add` tylko wybrane pliki.
- **Commit / Push:** jak w Opcji 1.

Wymaga parsowania `git status`, odświeżania listy (przycisk „Odśwież”), ewentualnie filtrowania tylko `.md` / tylko `content/articles/`. Więcej kodu i UI, większa kontrola.

---

### Opcja 3: Tylko podgląd i skróty

- **Status:** Wyświetlenie `git status` (np. w polu tekstowym) w katalogu projektu. Przyciski: „Skopiuj komendy” – generuje gotowe polecenia `git add ...`, `git commit -m "..."`, `git push` do wklejenia w terminalu.
- **Bez wykonywania** git z poziomu aplikacji – zero ryzyka nadpisania czegoś przez UI; użytkownik nadal wykonuje komendy ręcznie, ale ma wygodę z jednego miejsca.

---

## Gdzie w UI

- **Nowa zakładka** w głównym notebooku: np. **„Git”** lub **„Commit i push”**, umieszczona np. po „Odśwież artykuły” lub przy „Konfiguracja”.
- Zawartość zakładki:
  - Sekcja **„Status”**: (opcjonalnie) wynik `git status` lub lista plików (Opcja 2).
  - Sekcja **„Dodaj”**: przycisk(e) add (Opcja 1 lub 2).
  - Sekcja **„Commit”**: pole na komunikat, przycisk „Commit”.
  - Sekcja **„Push”**: przycisk „Push”, ewentualnie informacja „Branch: …”, „Remote: …”.
  - Log / wynik ostatniej komendy w polu tekstowym (read-only), spójnie z zakładkami Workflow / Odśwież.

Wymagania wstępne przy wejściu w zakładkę (lub przy pierwszym Add/Commit/Push):
- Katalog projektu jest ustawiony i zawiera `content/articles`.
- W katalogu projektu istnieje `.git` (czyli to repozytorium). Jeśli nie – komunikat: „To nie jest repozytorium Git. Zainicjuj je (git init) lub wybierz inny katalog.” i przyciski Add/Commit/Push nieaktywne lub z komunikatem.

---

## Zachowanie i edge cases

- **Brak gita w PATH:** Przy pierwszym użyciu (np. Add) sprawdzić `git --version`. Jeśli błąd – komunikat „Git nie jest dostępny w PATH. Zainstaluj Git lub dodaj go do PATH.” i nie wykonujemy poleceń.
- **Brak .git:** Komunikat jak wyżej; nie wywoływać git.
- **Brak remote (origin):** Przy Push – „Brak zdalnego repozytorium (origin). Skonfiguruj: git remote add origin <url>.” Nie wykonywać `git push`.
- **Brak upstream dla brancha:** Wykonać `git push -u origin <current-branch>` przy pierwszym pushu (albo pokazać użytkownikowi sugestię).
- **Konflikty / push odrzucony (non-fast-forward):** Nie robić force. Pokazać w logu output gita i komunikat w stylu: „Push odrzucony. Pobierz zmiany (git pull) lub rozwiąż konflikt w terminalu.”.
- **Pusty komunikat przy Commit:** Nie wykonywać commit; komunikat „Podaj komunikat commita.”.
- **Nic w stagingu przy Commit:** `git commit` zwróci błąd – pokazać go w logu; nie blokować wstępnie w UI (można dodać opcjonalnie sprawdzenie `git diff --cached --quiet` i informację „Brak zmian w stagingu.”).
- **Encoding:** Uruchamiać gita z env zapewniającym UTF-8 (np. `PYTHONIOENCODING=utf-8` lub zmienna dla gita), żeby polskie znaki w komunikatach i w logu były poprawne.

---

## Bezpieczeństwo i ograniczenia

- **Nie implementować** w pierwszej wersji: `git push --force`, `git reset --hard`, `git checkout` zmieniający branch, edycja `.git/config` z UI.
- **Potwierdzenie:** Przy „Push” opcjonalnie dialog „Czy na pewno wypchnąć zmiany na origin?” (można dać checkbox „Nie pytaj ponownie” zapisany w prefs).
- **Tylko odczyt konfiguracji:** Branch i remote tylko odczytywane (`git branch --show-current`, `git remote get-url origin`), bez zmiany z poziomu zakładki (chyba że w późniejszej iteracji dodamy wybór brancha z listy).

---

## Za i przeciw

| Za | Przeciw |
|----|--------|
| Jeden punkt pracy: generowanie/odświeżanie i wypchnięcie do repo. | Więcej kodu i przypadków brzegowych (brak gita, brak repo, konflikty). |
| Mniej przełączania się na terminal. | Część użytkowników i tak woli terminal lub zewnętrzny klient Git. |
| Spójne z koncepcją Monitora (wszystko w jednym oknie). | Trzeba utrzymywać zgodność z różnymi wersjami Gita i systemami (Windows/Linux). |
| Można zacząć od Opcji 1 (minimalna), bez listy plików. | Opcja 2 (lista + checkboxy) wymaga parsowania `git status` i odświeżania. |

---

## Rekomendacja

**Wdrożyć zakładkę Git w wariancie minimalnym (Opcja 1), z jasnymi ograniczeniami i komunikatami.**

### Rekomendowane szczegóły

1. **Zakres „Add”:** Na start **tylko `content/articles/`** (Opcja 1a). Jednoznaczne i bezpieczne; później można dodać „Dodaj cały content/” jako drugi przycisk.
2. **Funkcje:**  
   - Przycisk **„Dodaj artykuły”** → `git add content/articles/`.  
   - Pole **Komunikat** + przycisk **„Commit”** → `git commit -m "..."`.  
   - Przycisk **„Push”** → `git push` (bez force); przy braku upstream: `git push -u origin $(git branch --show-current)`.  
   - Opcjonalnie: **„Odśwież status”** wywołujące `git status` i wyświetlające wynik w polu logu (bez add/commit/push).
3. **Walidacje przed wykonaniem:**  
   - Katalog projektu ustawiony i zawiera `content/articles`.  
   - W katalogu projektu jest `.git`.  
   - Git dostępny w PATH.  
   - Przy Commit: niepusty komunikat.  
   - Przy Push: istnieje remote (np. origin); w razie błędu (np. rejected) – pokazać output, nie wykonywać force.
4. **Potwierdzenie Push:** Dla pierwszej wersji **tak** – prosty dialog „Czy wypchnąć zmiany na origin?” z możliwością zapamiętania wyboru (nie pytaj ponownie).
5. **i18n:** Wszystkie etykiety i komunikaty w pliku tłumaczeń (PL/EN), np. `git.*`.
6. **Log:** Wynik ostatniej komendy (add/commit/push/status) w ScrolledText w zakładce Git, analogicznie do zakładki Odśwież/Workflow.

---

## Opcje do przeglądu i weryfikacji przed zatwierdzeniem

Do decyzji przed wdrożeniem:

| # | Pytanie | Opcje | Rekomendacja |
|---|--------|--------|--------------|
| 1 | Zakres plików przy „Add” | (1a) Tylko `content/articles/` / (1b) Cały `content/` | **1a** na start |
| 2 | Potwierdzenie przed Push | Zawsze / Tylko pierwszy raz / Checkbox „Nie pytaj” / Bez potwierdzenia | **Dialog z checkboxem „Nie pytaj ponownie”** |
| 3 | Przycisk „Status” / „Odśwież” | Tak, pokazuje `git status` w logu / Nie na start | **Tak** – niski koszt, duża użyteczność |
| 4 | Wyświetlanie bieżącego brancha i remote | Tak (np. nad przyciskiem Push) / Nie | **Tak** – użytkownik wie, gdzie trafi push |
| 5 | Rozszerzenie późniejsze: lista plików z checkboxami (Opcja 2) | Planowane / Nie planowane | **Opcjonalnie w kolejnej iteracji** |

---

## Podsumowanie

Pomysł **zakładki Git (add, commit, push)** w Flowtaro Monitor jest **sensowny i wart wdrożenia** w wariancie minimalnym: add `content/articles/`, commit z komunikatem, push bez force, z walidacją repo i gita oraz czytelnymi komunikatami błędów. Rekomendacja: przyjąć powyższe opcje do przeglądu (tabela), zatwierdzić zakres (1a vs 1b, potwierdzenie push, przycisk Status), a następnie zaimplementować zakładkę zgodnie z rekomendacją i bez niebezpiecznych operacji (force, reset, zmiana brancha).
