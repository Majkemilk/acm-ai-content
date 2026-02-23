# Analiza: przeniesienie wyboru narzędzi do etapu fill_articles

## Kontekst

Obecne rozwiązanie: narzędzia są przypisywane do artykułu **przed** napisaniem treści (na etapie `generate_queue`), a fallback domyślnymi narzędziami daje wyniki formalnie poprawne, ale merytorycznie absurdalne (np. Opus Clip przypisany do artykułu o API error handling).

Propozycja: **przenieść decyzję o wyborze narzędzi do `fill_articles`** – model AI, mając pełny kontekst artykułu (tytuł, keyword, typ treści, persona, problem), sam wybiera 1–2 narzędzia z pełnej listy `affiliate_tools.yaml` na podstawie ich użyteczności do rozwiązywania problemu opisanego w artykule.

---

## Stan obecny vs. propozycja

| Aspekt | Teraz (generate_queue) | Propozycja (fill_articles) |
|--------|------------------------|----------------------------|
| **Kto wybiera narzędzia** | AI mapping (osobne wywołanie API) lub fallback domyślny | Ten sam model, który pisze treść artykułu |
| **Kontekst przy wyborze** | Tylko tekst problemu (1 zdanie) + lista narzędzi | Tytuł, keyword, content_type, audience_type, problem, szkielet artykułu + lista narzędzi z opisami |
| **Kiedy w pipeline** | Krok 2 (generate_queue) | Krok 4 (fill_articles) |
| **Zapis wyniku** | `use_case_tools_mapping.yaml` + `queue.yaml` (primary_tool, secondary_tool) | W treści artykułu (i opcjonalnie post-hoc do frontmatter/kolejki) |
| **Koszt API** | 1 dodatkowe wywołanie na batch problemów | Zero dodatkowych – wybór w ramach istniejącego wywołania fill |
| **Powtarzalność** | Taki sam wynik przy ponownym uruchomieniu (zapisany w pliku) | Może dać inny wynik przy ponownym fill (model nie jest deterministyczny) |

---

## Argumenty ZA przeniesieniem do fill_articles

### 1. Znacznie lepszy kontekst = znacznie lepsze dopasowanie

Na etapie `generate_queue` model widzi **tylko** jedno zdanie problemu:
> *"automate troubleshooting workflows for API error handling in marketing tools"*

Na etapie `fill_articles` model widzi:
- tytuł artykułu,
- keyword,
- audience_type (beginner / intermediate / professional),
- content_type (how-to / guide / best / comparison),
- **pełny szkielet artykułu** z nagłówkami sekcji.

To zasadniczo zmienia jakość decyzji. Model piszący artykuł o API error handling naturalnie wybierze UptimeRobot (monitoring) i Make/Zapier (automatyzacja workflow), a nie Opus Clip (klipy wideo). **Kontekst artykułu determinuje sensowność wyboru** – i ten kontekst istnieje dopiero na etapie fill.

### 2. Eliminacja osobnego wywołania API

Obecne AI mapping to **osobne** wywołanie API (`_fetch_ai_tools_mapping`) z dedykowanym promptem. Przeniesienie wyboru do fill_articles eliminuje ten koszt – model w jednym wywołaniu pisze treść **i** wybiera narzędzia. Zero dodatkowych zapytań do API.

### 3. Koniec problemu „brak klucza API = brak narzędzi"

Obecna architektura ma dwie ścieżki wymagające API: (a) AI mapping w generate_queue, (b) fill_articles. Jeśli w kroku (a) nie ma klucza, mapowanie jest domyślne (złe). W nowej architekturze **jedynym** miejscem wymagającym API jest fill_articles – i tam klucz **musi** być (bo bez niego nie ma treści). Problem „brak klucza przy mapowaniu" znika całkowicie.

### 4. Naturalnie spójna treść ↔ narzędzia

Gdy model sam wybiera narzędzia w trakcie pisania, **treść jest od razu spójna z wyborem**. Nie ma ryzyka, że w treści artykuł mówi o automatyzacji workflow, a w sekcji „Tools mentioned" jest Opus Clip, bo tak ustawił generate_queue.

### 5. Infrastruktura jest już prawie gotowa

W obecnym `fill_articles.py` (linie 773–779) **już istnieje** mechanizm fallbacku: gdy `primary_tool` / `secondary_tool` są puste, model dostaje pełną listę narzędzi z `affiliate_tools.yaml` z instrukcją *"mention 1–2 that best fit the topic"*. Wystarczy rozbudować ten mechanizm o:
- strukturalny wybór (model zwraca wybraną listę w ustalonym formacie),
- post-hoc zapis wybranych narzędzi do frontmatter i opcjonalnie do kolejki/mapowania.

---

## Argumenty PRZECIW przeniesieniu do fill_articles

### 1. Utrata determinizmu i powtarzalności

Obecne mapowanie w pliku daje **powtarzalny** wynik: ten sam problem → te same narzędzia, niezależnie od liczby uruchomień. Przy wyborze w fill_articles model może za każdym razem wybrać inne narzędzia (temperatura > 0, różne konteksty). To oznacza:
- Refresh artykułu może zmienić narzędzia (inny primary_tool).
- Dwa artykuły o podobnym problemie mogą mieć różne narzędzia.

**Mitygacja:** Zapisywać wynik pierwszego fill do frontmatter (`primary_tool`, `secondary_tool`). Przy ponownym fill (refresh) używać zapisanych wartości, chyba że użytkownik jawnie wymusi ponowny wybór (`--remap`).

### 2. Tytuł artykułu zawiera nazwę narzędzia

`title_for_entry()` generuje tytuł w formacie *"How to … with {primary_tool}"*. Jeśli primary_tool nie jest znany na etapie generate_queue (bo wybór następuje w fill_articles), tytuł nie może zawierać nazwy narzędzia.

**Mitygacja:**
- Generować tytuł **bez** nazwy narzędzia (np. *"How to automate troubleshooting workflows for API error handling"*). To i tak lepsze SEO – keyword jest generyczny, nie zamknięty na jedno narzędzie.
- Albo: po fill aktualizować tytuł w frontmatter (ale to zmienia slug i nazwę pliku – ryzykowne).

**Ocena:** To nie jest bloker. Obecne tytuły z generycznym narzędziem (np. „… with Opus Clip" przy artykule o API errors) są **gorsze** niż tytuł bez narzędzia. Usunięcie narzędzia z tytułu to poprawa, nie regresja.

### 3. Komplikacja post-hoc zapisu

Po fill_articles trzeba:
- Wyodrębnić z odpowiedzi modelu, **które** narzędzia wybrał.
- Zapisać je do frontmatter artykułu (`primary_tool`, `secondary_tool`).
- Opcjonalnie zaktualizować `queue.yaml` i `use_case_tools_mapping.yaml`.

To dodaje logikę parsowania i zapisu, której teraz nie ma. Model musi zwrócić wynik w formacie, z którego łatwo wyodrębnić listę narzędzi.

**Mitygacja:** Dodać do promptu instrukcję: *"At the end of your response, include a line: TOOLS_SELECTED: Tool1, Tool2"*. Post-processing w fill_articles parsuje tę linię, aktualizuje frontmatter, i opcjonalnie mapowanie.

### 4. Dłuższe okno kontekstowe

Lista 40+ narzędzi z opisami dodaje ~500–800 tokenów do promptu fill_articles. Przy obecnych modelach (128k+ context) to nieistotne, ale zwiększa koszt per-artykuł o kilka centów.

**Ocena:** Marginalne. Oszczędność z eliminacji osobnego wywołania AI mapping (krok 2) kompensuje to z nadwyżką.

### 5. Mapowanie traci rolę „source of truth"

Plik `use_case_tools_mapping.yaml` przestaje być centralnym rejestrem. Zakładka „Mapowanie" w UI albo staje się pusta, albo wymaga uzupełniania post-hoc.

**Mitygacja:** Po fill_articles dopisywać wynik (problem → narzędzia) do pliku mapowania. Plik staje się **cache'em / logiem** wyników AI, a nie danymi wejściowymi. Zakładka „Mapowanie" nadal działa.

---

## Warianty implementacji

### Wariant A: Pełne przeniesienie – wybór wyłącznie w fill_articles

- `generate_queue` nie przypisuje narzędzi (puste `primary_tool` / `secondary_tool`).
- `generate_articles` renderuje szablon bez narzędzi (lub z placeholderem).
- `fill_articles` dostaje pełną listę narzędzi z `affiliate_tools.yaml`, model wybiera 1–2 i pisze treść.
- Post-processing: wyodrębnienie wybranych narzędzi, zapis do frontmatter, opcjonalnie do mapowania.

**Zalety:** Czysta architektura, jedno miejsce decyzji.
**Wady:** Tytuł bez narzędzia, puste pola w kolejce do momentu fill.

### Wariant B: Dwuetapowy – mapping wstępny + walidacja/korekta w fill_articles

- `generate_queue` robi AI mapping jak teraz (ale bez fallbacku domyślnego – jeśli brak API, wpis trafia do kolejki bez narzędzia).
- `fill_articles` sprawdza: jeśli `primary_tool` jest ustawiony – używa go; jeśli pusty lub `{{PRIMARY_TOOL}}` – model wybiera sam z pełnej listy.
- Post-processing: zapis wyniku do frontmatter i mapowania.

**Zalety:** Zachowuje obecną architekturę dla „happy path" (API działa w generate_queue). Naprawia „sad path" (brak API / błąd) w fill_articles.
**Wady:** Dwie ścieżki logiki, dwa miejsca wywołań API z listą narzędzi.

### Wariant C: Mapping zawsze w fill_articles, generate_queue bez mapping

- `generate_queue` nie zajmuje się narzędziami w ogóle (usunąć AI mapping, fallback, plik mapowania jako input).
- `fill_articles` zawsze: pełna lista narzędzi → model wybiera → post-processing zapisuje do frontmatter i do pliku mapowania.
- Plik mapowania staje się wynikiem (output), nie wejściem (input).

**Zalety:** Najprostsza architektura. Jedno wywołanie API, jedno miejsce logiki.
**Wady:** Plik mapowania nie może być edytowany ręcznie jako „override" (bo fill go nadpisuje). Zakładka „Mapowanie" staje się read-only logiem.

---

## Kwestie techniczne

### Jak model zwraca wynik?

Prompt w fill_articles dodaje instrukcję:

```
After writing the full article body, include on the LAST LINE exactly:
TOOLS_SELECTED: ToolName1, ToolName2

Choose 1–2 tools from the list below that are most useful for solving the problem 
described in this article. Selection criteria: direct relevance to the article's task, 
not general popularity. If no tool fits well, write TOOLS_SELECTED: NONE.
```

Post-processing w `fill_one()`:
1. Szuka linii `TOOLS_SELECTED: ...` w odpowiedzi.
2. Parsuje nazwy narzędzi (waliduje vs `affiliate_tools.yaml`).
3. Usuwa tę linię z body artykułu.
4. Ustawia `meta["primary_tool"]` i `meta["secondary_tool"]`.
5. Buduje `{{TOOLS_MENTIONED}}` (lista bullet z linkami).
6. Zapisuje frontmatter z nowymi wartościami.

### Czy render_site wymaga zmian?

Nie. `render_site` czyta frontmatter i treść; zamienia nazwy narzędzi na linki afiliacyjne. Źródło nazw (mapping vs fill_articles) jest transparentne.

### Czy zakładka „Mapowanie" wymaga zmian?

Tylko jeśli plik mapowania jest nadal używany (wariant B/C – post-hoc zapis). Bez zmian w UI.

---

## Rekomendacja

### Wariant C z jednym rozszerzeniem

**Przenieść wybór narzędzi w całości do fill_articles. Usunąć AI mapping z generate_queue. Zachować plik mapowania jako cache/log wyników (zapisywany post-hoc przez fill_articles).**

Uzasadnienie:

1. **Sensowność merytoryczna** jest **jedynym** kryterium, które się liczy. Obecny system produkuje absurdalne przypisania (Opus Clip + API error handling). Jedyne miejsce, w którym model ma wystarczający kontekst do sensownej decyzji, to fill_articles – bo tam widzi pełny artykuł.

2. **Prostota.** Zamiast dwóch wywołań API (jedno dla mappingu, jedno dla treści) i dwóch miejsc logiki – jedno wywołanie, jedno miejsce. Mniej kodu, mniej punktów awarii.

3. **Brak klucza API = brak artykułu** (nie „brak narzędzi, ale artykuł powstaje z Opus Clip"). To uczciwy kontrakt: jeśli nie ma API, system nie produkuje treści niskiej jakości.

4. **Tytuł bez narzędzia** to poprawa, nie regresja. SEO keyword powinien opisywać problem, nie konkretne narzędzie. Narzędzie powinno być wzmianką w treści, nie w tytule.

5. **Determinizm** zapewnia zapis do frontmatter: po pierwszym fill wybrane narzędzia są trwałe. Ponowny fill (refresh) używa zapisanych wartości, chyba że użytkownik jawnie wymusi `--remap`.

### Jedno rozszerzenie: ręczny override w pliku mapowania

Zachować możliwość **ręcznego** wpisania mapowania w `use_case_tools_mapping.yaml`. Jeśli `fill_articles` wykryje, że dla danego problemu istnieje ręczny wpis w pliku, **użyje go** zamiast pytać model. To daje redaktorowi kontrolę nad przypisaniami bez zmiany kodu.

Kolejność priorytetów:
1. Frontmatter artykułu (jeśli `primary_tool` jest ustawiony i nie jest placeholderem) → użyj go.
2. `use_case_tools_mapping.yaml` (jeśli ma wpis dla tego problemu) → użyj go.
3. Brak obu → model wybiera z pełnej listy `affiliate_tools.yaml`.

To zachowuje elastyczność: system działa automatycznie, ale redaktor może nadpisać wybór AI dla konkretnego problemu.

---

## Zmiany do wdrożenia (podsumowanie)

| Komponent | Zmiana |
|-----------|--------|
| `generate_queue.py` | Usunąć AI mapping, fallback domyślny. Wpisy w kolejce mają puste `primary_tool` / `secondary_tool`. Usunąć `--no-ai-mapping`. |
| `generate_articles.py` | `get_replacements()`: przy pustym `primary_tool` → placeholder `{{PRIMARY_TOOL}}` (jak teraz). Bez zmian w logice. |
| `fill_articles.py` (`build_prompt`) | Zamiast obecnego fallbacku (linie 773–779): **zawsze** podawać pełną listę narzędzi z opisami z `affiliate_tools.yaml`. Dodać instrukcję `TOOLS_SELECTED: ...` na końcu odpowiedzi. |
| `fill_articles.py` (`fill_one`) | Post-processing: parsować `TOOLS_SELECTED`, walidować nazwy, ustawić `meta["primary_tool"]` / `meta["secondary_tool"]`, zapisać frontmatter. Opcjonalnie: dopisać do `use_case_tools_mapping.yaml`. |
| `fill_articles.py` (`fill_one`) | Przed wywołaniem API: sprawdzić frontmatter i plik mapowania – jeśli narzędzia są ustawione, użyć ich (ręczny override). |
| Szablony | `{{TOOLS_MENTIONED}}` wypełniany post-hoc w fill_articles (po parsowaniu TOOLS_SELECTED), nie w generate_articles. |
| `use_case_tools_mapping.yaml` | Zmiana roli: z danych wejściowych na cache/log + ręczny override. |
| Zakładka „Mapowanie" | Bez zmian (nadal odczyt pliku). |
| `title_for_entry()` | Nie dołączać `with {tool_name}` do tytułu (opcjonalnie: zostawić, gdy redaktor ręcznie ustawił narzędzie w mapowaniu). |
