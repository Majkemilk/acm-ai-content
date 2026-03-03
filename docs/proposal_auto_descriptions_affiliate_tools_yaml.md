# Propozycja: automatyczne uzupełnianie opisów w affiliate_tools.yaml przez API

**Cel:** Generowanie pola `short_description_en` dla wpisów, które go nie mają, przy użyciu wywołania API (np. ten sam model co do artykułów), bez obowiązku ręcznego wpisywania.

---

## Za

- **Mniej pracy ręcznej** — nowe narzędzia dodane do YAML z samym `name`, `category`, `affiliate_link` dostają opis jednym uruchomieniem skryptu zamiast ręcznego dopisywania zdań.
- **Spójność stylu** — przy jednym, ustalonym prompcie (jedno zdanie, angielski, faktograficznie) opisy są w podobnej długości i tonie.
- **Szybkie uzupełnienie backlogu** — można jednorazowo „doładować” opisy dla wszystkich wpisów bez `short_description_en`.
- **Możliwość cyklicznego uruchamiania** — np. po dodaniu nowych narzędzi do YAML uruchomienie skryptu sugeruje opisy tylko dla nowych wpisów.

---

## Przeciw

- **Koszt i opóźnienie API** — każde wywołanie (np. 1 request na narzędzie bez opisu) to koszt i czas; przy dziesiątkach narzędzi może być to odczuwalne.
- **Ryzyko jakości** — model może podać opis zbyt ogólny, marketingowy lub błędny; wymaga to weryfikacji przed uznaniem za „oficjalny” w YAML.
- **Nadpisywanie w repozytorium** — automatyczny zapis do `affiliate_tools.yaml` powoduje duże, automatyczne zmiany w pliku; ręcznie dopracowane opisy mogłyby zostać nadpisane przy kolejnym uruchomieniu.
- **Kiedy uruchamiać** — trzeba zdecydować: tylko na żądanie (skrypt), przy dodawaniu nowego wpisu, w CI — każde ma inne konsekwencje dla procesu i bezpieczeństwa.
- **Ograniczenia kontekstu** — API dostaje zwykle tylko nazwę i ewentualnie kategorię/URL; bez przeglądu strony produktu opis może być mniej trafny niż napisany przez człowieka.

---

## Proponowana wersja implementacji (bez kodu)

1. **Tryb „sugestia”, nie bezpośredni zapis**
   - Skrypt (np. `scripts/suggest_affiliate_descriptions.py`) czyta `content/affiliate_tools.yaml`, znajduje wpisy **bez** `short_description_en`.
   - Dla każdego takich wpisów: jedno wywołanie API z prompcem w stylu: *„In one short sentence in English, describe what this product/tool does. Name: [name]. Category: [category]. Be factual and concise; no marketing superlatives. Output only that one sentence.”* (opcjonalnie w kontekście można dodać URL do strony, jeśli API ma dostęp).
   - **Wynik nie zapisuje** od razu do `affiliate_tools.yaml`, tylko:
     - do pliku **sugestii** (np. `content/affiliate_tools_suggested_descriptions.yaml` lub `.txt` / `.md` z listą `name: "suggested sentence"`), **albo**
     - na stdout / do pliku patch, żeby człowiek mógł przejrzeć i ręcznie wkleić lub zmergować do YAML.
   - Dzięki temu: brak automatycznego nadpisywania, pełna kontrola przed commitem.

2. **Opcjonalny krok „zastosuj po review”**
   - Po zatwierdzeniu sugestii przez redaktora: osobna komenda lub skrypt (np. `--apply suggestions_file.yaml`) wczytuje zatwierdzoną listę `name → short_description_en` i **wtedy** aktualizuje `affiliate_tools.yaml` (np. dopisuje brakujące pola lub nadpisuje tylko te, które użytkownik oznaczył).  
   - Albo: ręczne skopiowanie z pliku sugestii do YAML — bez dodatkowego skryptu.

3. **Zasady wywołania API**
   - Jedno zdanie na narzędzie; opcjonalnie retry przy błędzie; timeout.
   - Nie zmieniać wpisów, które **już mają** `short_description_en` (chyba że jawnie dodamy tryb „nadpisz” z flagą).

4. **Bezpieczeństwo i wersjonowanie**
   - Nie committować automatycznie; zmiany w YAML tylko po zatwierdzeniu (ręczny merge lub `--apply` po review).
   - W README lub w komentarzu w YAML krótko opisać, że opisy mogą pochodzić z sugestii API i że warto je zweryfikować.

---

## Rekomendacja

- **Wdrożyć automatyczne *sugerowanie* opisów przez API** (skrypt czytający YAML → wywołania API → wynik do pliku sugestii lub stdout), **bez** automatycznego zapisu do `affiliate_tools.yaml` w domyślnym przebiegu.
- **Nie** włączać domyślnego nadpisywania `affiliate_tools.yaml` w pipeline (np. przy każdym fillu) — YAML ma pozostawać źródłem prawdy po stronie redakcji; API tylko wspomaga uzupełnianie.
- **Opcjonalnie** po zatwierdzeniu: drugi krok (skrypt `--apply` lub ręczne wklejenie) do jednorazowego dopisania zatwierdzonych opisów do YAML.

---

## Opcja: blokada nadpisywania, bez kroku „zastosuj”

Wariant, w którym **ryzyko nadpisania jest wyeliminowane** (albo nadpisanie jest zablokowane w logice), a **nie ma** osobnego kroku akceptacji przez „zastosuj”.

### Wariant 1 — Zapis tylko do pliku sugestii; nigdy do YAML

- Skrypt **wyłącznie** generuje plik z sugestiami (np. `affiliate_tools_suggested_descriptions.yaml` lub `.md`).
- Do `affiliate_tools.yaml` **nic nie jest zapisywane** przez skrypt — ani teraz, ani w żadnym kroku „zastosuj” (takiego kroku nie ma).
- Uzupełnienie YAML odbywa się **wyłącznie ręcznie** (skopiowanie/wklejenie z pliku sugestii przez użytkownika).

| Za | Przeciw |
|----|--------|
| **Zero ryzyka nadpisania** — skrypt w ogóle nie modyfikuje YAML. | Wymaga ręcznego przeniesienia opisów z sugestii do YAML (to jest jedyna forma „akceptacji”). |
| Brak kroku „zastosuj” — jeden skrypt, jeden plik wyjściowy. | Dwa miejsca do trzymania: YAML + plik sugestii. |
| Pełna kontrola: do głównego pliku trafia tylko to, co użytkownik wklei. | Przy dużej liczbie narzędzi ręczne wklejanie może być uciążliwe. |

---

### Wariant 2 — Zapis wprost do YAML wyłącznie dla pustych pól (blokada nadpisywania w kodzie)

- Skrypt czyta `affiliate_tools.yaml`, dla każdego wpisu **bez** `short_description_en` wywołuje API, otrzymuje jedno zdanie i **dopisuje** `short_description_en` tylko do tych wpisów, po czym zapisuje plik.
- **W kodzie obowiązuje zasada:** jeśli wpis **ma już** `short_description_en`, skrypt **go nie zmienia** (ani nie nadpisuje, ani nie usuwa). Żadna flaga „nadpisz” ani „zastosuj” nie istnieje.
- Jedno uruchomienie = uzupełnienie wyłącznie pustych pól; brak drugiego kroku i brak akceptacji przez „zastosuj”.

| Za | Przeciw |
|----|--------|
| **Brak nadpisywania** — istniejące opisy są nienaruszalne; zmieniane są tylko pola puste. | Opisy wygenerowane przez API trafiają od razu do YAML **bez** wcześniejszej akceptacji użytkownika (jedyne „zatwierdzenie” to świadome uruchomienie skryptu). |
| Brak kroku „zastosuj” — jeden skrypt, jeden plik (YAML). | Jakość: słabsza sugestia API zostanie zapisana; ewentualna korekta tylko ręcznie po fakcie. |
| Szybkie uzupełnienie brakujących opisów jednym poleceniem. | Wymaga zaufania do skryptu (zapis do repozytorium); sensowny backup/diff przed uruchomieniem. |

#### Jak zostałoby to wdrożone (Wariant 2)

- **Skrypt:** Np. `scripts/fill_affiliate_descriptions.py` (lub inna nazwa), uruchamiany z katalogu projektu. Używa tej samej ścieżki do YAML co reszta pipeline’u (np. `PROJECT_ROOT / "content" / "affiliate_tools.yaml"`).
- **Wejście:** Tylko plik `content/affiliate_tools.yaml`. Opcjonalnie zmienne środowiskowe lub argumenty dla API (base_url, api_key, model), tak jak w `fill_articles.py`.
- **Logika w jednym przebiegu:**
  1. Wczytanie YAML (struktura `tools: [ - name: ... category: ... affiliate_link: ... short_description_en: ... ]`). Zachowanie kolejności wpisów i formatu (wcięcia, cudzysłowy), żeby diff był minimalny.
  2. **Filtrowanie:** Z listy `tools` wybór wyłącznie wpisów, w których `short_description_en` brakuje lub jest pusty (po trim). Wpisy z już ustawionym opisem **nie są** przekazywane do API ani modyfikowane.
  3. **Blokada nadpisywania w kodzie:** W pętli po wpisach — warunek typu „if short_description_en is empty”: tylko wtedy wywołanie API i uzupełnienie. Nigdzie w skrypcie nie ma ścieżki „nadpisz istniejący short_description_en” (brak flagi `--overwrite` itd.).
  4. **Wywołanie API:** Dla każdego wpisu bez opisu: jeden request z prompcem (np. nazwa, kategoria, ewentualnie URL), instrukcja: jedno zdanie po angielsku, faktograficznie. Odpowiedź po oczyszczeniu (trim, ewentualnie obcięcie do jednego zdania) traktowana jako wartość `short_description_en`.
  5. **Zapis do pliku:** Po zebraniu wszystkich nowych opisów — aktualizacja tylko tych wpisów w strukturze w pamięci, które były puste; następnie zapis całego pliku YAML na dysk (z zachowaniem kolejności i stylu, np. przez bibliotekę YAML z round-trip lub ręczne dopisanie klucza `short_description_en:` pod odpowiednim wpisem). Istniejące wpisy z opisem są zapisywane **bez zmian** (odczyt → brak modyfikacji → zapis tej samej wartości).
- **Bezpieczeństwo:** Przed zapisem można opcjonalnie utworzyć kopię zapasową pliku (np. `affiliate_tools.yaml.bak`); w dokumentacji skryptu wyraźna informacja: „uzupełnia tylko puste pola, nigdy nie nadpisuje istniejących opisów”.

#### Jak wyglądałby proces (Wariant 2)

1. **Przed uruchomieniem:** Użytkownik ma zaktualizowany `content/affiliate_tools.yaml` (np. nowe narzędzia dodane z `name`, `category`, `affiliate_link`, bez `short_description_en`). Opcjonalnie: `git diff` lub kopia pliku na wszelki wypadek.
2. **Uruchomienie:** W katalogu projektu jedna komenda, np. `python scripts/fill_affiliate_descriptions.py` (lub z opcjonalnymi argumentami: `--dry-run`, ścieżka do YAML, zmienne API). Skrypt ładuje YAML, wykrywa N wpisów bez opisu.
3. **Przebieg:** Dla każdego z N wpisów: wywołanie API → otrzymanie jednego zdania → przypisanie do tego wpisu w strukturze. Wpisy z już ustawionym opisem są pomijane (zero wywołań API dla nich). Na stdout: krótki log, np. „Uzupełniono 12 opisów (pominięto 3 wpisy z już ustawionym opisem).”
4. **Zapis:** Skrypt zapisuje zaktualizowany YAML do `content/affiliate_tools.yaml`. W pliku: przy N uzupełnionych wpisach pojawiają się nowe linie `short_description_en: "..."` tylko tam, gdzie wcześniej ich nie było; pozostałe wpisy pozostają identyczne jak przed uruchomieniem.
5. **Po uruchomieniu:** Użytkownik robi `git diff` na YAML, ewentualnie poprawia ręcznie wygenerowane opisy, commituje. Kolejne uruchomienie skryptu znowu nic nie nadpisze (te wpisy mają już opis), uzupełni tylko ewentualne kolejne nowe wpisy bez opisu.

Podsumowanie: jeden skrypt, jedno uruchomienie, zapis tylko do pustych pól, bez kroku „zastosuj” i bez możliwości nadpisania istniejących opisów w kodzie.

---

### Rekomendacja dla tej opcji

- Jeśli **maksymalne bezpieczeństwo** i brak jakiejkolwiek modyfikacji YAML przez skrypt są ważniejsze niż wygoda: **Wariant 1** (tylko plik sugestii, bez zapisu do YAML, bez „zastosuj”).
- Jeśli **wygoda** (jedno uruchomienie = uzupełnione puste pola w YAML) jest ważniejsza, a akceptujesz brak osobnego kroku „zastosuj”: **Wariant 2** (zapis tylko do pustych pól, z sztywną blokadą nadpisywania w kodzie).

**Brak wdrożenia w kodzie do momentu zatwierdzenia.**
