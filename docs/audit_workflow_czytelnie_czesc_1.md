# Workflow generowania artykułu — wersja czytelna (część 1)

**Zawartość tej części:** Konfiguracja, generowanie pomysłów (use case'y), kolejka.  
**Cel:** Ten sam audyt co w `audit_full_article_generation_workflow.md`, opisany od początku do końca po ludzku — bez skracania i bez pomijania.

---

## 1. Konfiguracja — skąd system wie, „na czym pracujemy”

### 1.1 Skąd bierzemy ustawienia

Wszystkie główne ustawienia pipeline'u trzymane są w **jednym pliku**: `content/config.yaml`. Może być zapisany w formacie YAML albo JSON. Aplikacja nie trzyma konfiguracji w bazie ani w zmiennych wewnątrz skryptów — czyta ten plik i na jego podstawie wie: jaki hub jest „produkcyjny”, jakie kategorie są dozwolone, ile use case'ów generować w jednej paczce, jak rozkładać je na beginner/intermediate/professional, czy są jakieś sugerowane problemy (w tym HARD LOCK), oraz czy artykuły mają wszędzie dostawać jedną kategorię, czy zachować kategorie z kolejki.

Odczyt realizuje funkcja **`load_config(path)`** w module `content_index.py`. Zwraca zwykły słownik (dict) z polami opisanymi poniżej. Ten sam słownik jest używany w różnych skryptach: generate_use_cases, generate_articles, content_index (dla render_site), itd.

### 1.2 Co znaczy każde pole — po ludzku

- **production_category** (tekst)  
  To **nazwa pliku** huba w katalogu `content/hubs/` — **bez** rozszerzenia `.md`. Np. jeśli wartość to `"ai-marketing-automation"`, system szuka pliku `content/hubs/ai-marketing-automation.md`. Ten plik jest używany do trzech rzeczy: (1) skrypt `generate_hubs.py` zapisuje do niego wygenerowaną treść huba; (2) skrypt `generate_use_cases.py` bierze z niego pierwszą dozwoloną kategorię przy generowaniu pomysłów; (3) `render_site.py` z niego czyta treść huba i renderuje ją na stronę. Ważne: to jest **nazwa pliku**, nie URL — URL budowany jest z `hub_slug`.

- **hub_slug** (tekst)  
  To **slug w adresie URL** — małe litery, myślniki, bez spacji. Np. `ai-marketing-automation`. Używany w: ścieżce zapisu strony huba (`public/hubs/{hub_slug}/index.html`), w sitemapie, w linku „Wszystkie artykuły” na stronie głównej. Artykuły, które w metadanych mają kategorię zgodną z tym slugiem, linkują do tego samego huba. Nie mylić z `production_category`: category to nazwa pliku, slug to fragment adresu.

- **sandbox_categories** (lista tekstów)  
  Dodatkowe kategorie, które są **dozwolone** przy generowaniu use case'ów. Skrypt `generate_use_cases.py` dostaje listę: najpierw jedna kategoria z `production_category`, potem wszystkie z `sandbox_categories`. Model może przypisać use case'owi dowolny `category_slug` z tej listy. To **nie** decyduje o tym, które artykuły trafiają na stronę — na stronę trafiają wszystkie artykuły ze statusem „filled” (nie-blocked); sandbox służy tylko do poszerzenia puli tematów przy generowaniu pomysłów.

- **use_case_batch_size** (liczba)
  **Liczba use case'ów** generowanych w jednym uruchomieniu `generate_use_cases.py`. Np. 9. Jedyna źródłowa wartość — skrypt nie ma parametru `--limit`. Czyli: „ile nowych pomysłów na artykuły wygenerować za jednym razem”.

- **use_case_audience_pyramid** (lista liczb)  
  Opisuje **podział odbiorców** w jednym batchu. Np. `[3, 3]` znaczy: pierwsze 3 pozycje na liście = odbiorca **beginner**, następne 3 = **intermediate**, wszystko powyżej = **professional**. Skrypt po wygenerowaniu use case'ów przypisuje każdemu `audience_type` na podstawie pozycji w tablicy i tej piramidy. Dzięki temu w jednej paczce mamy mix dla początkujących, średnio zaawansowanych i zaawansowanych.

- **suggested_problems** (lista tekstów)  
  Opcjonalna lista **haseł / problemów**, które mają być brane pod uwagę przy generowaniu use case'ów. Przekazywana do promptu API — model może je preferować. **Pierwszy element** listy ma specjalne znaczenie: jeśli jest ustawiony (niepusty), włącza się tryb **HARD LOCK**. Wtedy wszystkie wygenerowane use case'y muszą być wariantami tego samego problemu bazowego (bez „uciekania” na sąsiednie tematy). Szczegóły HARD LOCK są w rozdziale 2.

- **category_mode** (tekst: `production_only` lub `preserve_sandbox`)  
  Dotyczy etapu **generowania szkieletów** artykułów (`generate_articles.py`). Przy **production_only** każdy artykuł dostaje w metadanych kategorię równą `production_category` — niezależnie od tego, co było w kolejce. Przy **preserve_sandbox** system zachowuje `category_slug` z wpisu kolejki, ale tylko jeśli ten slug jest na liście dozwolonych (production + sandbox). Daje to możliwość trzymania w kolejce artykułów z różnych kategorii sandbox i zachowania ich przy tworzeniu plików .md.

### 1.3 Co się dzieje, gdy config jest pusty lub brak pliku

Jeśli plik nie istnieje, jest pusty albo parser nie może go poprawnie odczytać, używane są **wartości domyślne**:

- production_category: `"ai-marketing-automation"`
- hub_slug: `"ai-marketing-automation"`
- sandbox_categories: pusta lista `[]`
- use_case_batch_size: `9`
- use_case_audience_pyramid: `[3, 3]`
- suggested_problems: pusta lista `[]`
- category_mode: `"production_only"`

Czyli pipeline i tak może działać — po prostu z jednym hubem, jedną kategorią i bez HARD LOCK.

---

## 2. Generowanie pomysłów (use case'y) — co robi generate_use_cases.py

### 2.1 Z czego skrypt korzysta i co produkuje

**Wejście:**  
- Plik `content/config.yaml` (kategorie, batch size, piramida, suggested_problems).  
- Plik `content/use_cases.yaml` z listą use case'ów, które już mamy — po to, żeby ich nie duplikować.  
- Zawartość katalogu `content/articles/` — skrypt zagląda do frontmatter istniejących artykułów i zbiera słowa kluczowe / tematy, żeby z jednej strony nie powtarzać tych samych tematów, z drugiej — mieć inspirację do nowych kątów.

**Wyjście:**  
Ten sam plik `content/use_cases.yaml` — dopisane do listy **nowe** wpisy. Każdy wpis to obiekt z polami m.in.: `problem` (krótki opis problemu biznesowego), `suggested_content_type` (how-to, guide, best lub comparison), `category_slug` (jedna z dozwolonych kategorii), opcjonalnie `audience_type`, `batch_id`, `status`. Nowe wpisy dostają status `"todo"`, żeby w następnym kroku `generate_queue.py` mógł je zabrać do kolejki.

### 2.2 Jak skrypt rozmawia z API

Wysyłane jest jedno żądanie do **OpenAI Responses API**: POST na adres `{OPENAI_BASE_URL}/v1/responses`. Adres bazowy, klucz API i model brane są ze zmiennych środowiskowych: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` (gdy nie ustawione — domyślnie używany jest model `gpt-4o-mini`).

### 2.3 Instrukcje dla API — pełny opis po ludzku i dokładne treści

**O co chodzi w tym kroku:**  
Model dostaje rolę **content strategisty**. Jego zadanie to zaproponować **konkretną liczbę** nowych problemów biznesowych (use case'ów) na blog w obszarze AI i automatyzacji w marketingu. Odpowiedź ma być **wyłącznie** poprawną tablicą JSON: bez markdownu, bez wstępów ani podsumowań. Każdy element tablicy to obiekt z trzema kluczami: `problem`, `suggested_content_type`, `category_slug`. Wartości `category_slug` muszą pochodzić z listy dozwolonych kategorii — ta lista jest podana w wiadomości użytkownika (z configu).

Jeśli w configu jest ustawiony **pierwszy element** listy `suggested_problems`, skrypt włącza **HARD LOCK**. W instrukcjach pojawia się wtedy wymóg: każdy use case ma pozostawać w tej samej domenie problemu co podany „problem bazowy”; nie wolno schodzić na sąsiednie ani ogólne tematy. W wiadomości użytkownika dodawany jest blok BASE PROBLEM LOCK z dokładnym tekstem tego problemu oraz z podziałem na trzy kąty (dla dokładnie 3 use case'ów): pierwszy — implementation/setup, drugi — monitoring/troubleshooting/optimization, trzeci — scaling/governance/reliability.

W wiadomości użytkownika przekazywane są: lista dozwolonych `category_slug`; lista istniejących problemów z use_cases.yaml (żeby nie duplikować); lista słów kluczowych/tematów z istniejących artykułów (inspiracja, unikać duplikatów); opcjonalnie cała lista suggested_problems; opcjonalnie BASE PROBLEM LOCK; jeśli była wcześniejsza nieudana próba — blok QUALITY FEEDBACK z listą uwag. Na samym końcu jest prośba: wygeneruj dokładnie N nowych, konkretnych, „actionable” problemów, na które ludzie szukają rozwiązań w AI marketing automation; każdy ma być inny od istniejących; **kolejność ma znaczenie**: pierwsze 3 dla beginner, następne 3 dla intermediate/mixed, reszta dla professional. Jeśli ustawiono filtr typu treści (`content_type_filter`), dopisywane jest zdanie w stylu: „Dla każdego use case'a ustaw suggested_content_type dokładnie na: {wartość}.” W przeciwnym razie: „Preferuj problemy, które pasują do treści how-to lub guide.” Na koniec: „Zwróć tylko tablicę JSON.”

**Dokładna treść instrukcji (system / instructions) wysyłana do API:**

```
You are a content strategist. Your task is to suggest new business problems / use cases for blog content in the AI marketing automation space.

Output ONLY a valid JSON array of objects. Each object must have exactly these keys:
- "problem": string, concise description of the business problem (e.g., "turn podcasts into written content")
- "suggested_content_type": string, one of: how-to, guide, best, comparison
- "category_slug": string, one of the allowed categories provided in the user message

Do not output any markdown, explanation, or text outside the JSON array. The response must be parseable as JSON.
```

Gdy włączony jest HARD LOCK (w configu jest niepusty `suggested_problems[0]`), do powyższego dopisywany jest blok:

```
HARD LOCK (MUST FOLLOW): Every generated use case must stay on the same base problem domain provided by the user. Do not drift to adjacent/general topics.
```

**Z czego składa się wiadomość użytkownika (user message):**

1. Stały początek: „Allowed category_slug values (use exactly one per use case):” + tablica JSON kategorii (np. `["ai-marketing-automation"]`).
2. „Existing use cases already in our list (do NOT suggest these or very similar ones):” + tablica JSON istniejących problemów.
3. „Existing article keywords/topics we already cover (suggest complementary or new angles, not duplicates):” + tablica JSON (do 50 słów kluczowych/tematów z artykułów).
4. Jeśli jest lista suggested_problems: „Optionally consider these problems (if not already covered); prefer turning them into use cases:” + tablica JSON.
5. Jeśli jest HARD LOCK: „BASE PROBLEM LOCK (mandatory):” + JSON-string z dokładnym tekstem problemu bazowego + zdanie: „All generated use cases must be direct variants of this base problem. For exactly 3 use cases, enforce distinct angles: Use case #1: implementation / setup angle; Use case #2: monitoring / troubleshooting / optimization angle; Use case #3: scaling / governance / reliability angle.”
6. Jeśli była wcześniejsza próba i zwrócono quality_feedback: blok „QUALITY FEEDBACK (previous attempt failed; fix all):” + lista punktów.
7. Na końcu: „Generate exactly {count} new, specific, actionable business problems that people actively search for solutions to in AI marketing automation. Each must be different from the existing use cases and topics above. Structure by audience (follow this order strictly): First 3: for beginners (simple, entry-level). Next 3: for intermediate or mixed (can build on or complement the first three). Remaining: for professional users only (advanced, scaling, integration).” Następnie — jeśli ustawiono content_type_filter: „For every use case, set suggested_content_type to exactly: {value}.” W przeciwnym razie: „Prefer problems that fit how-to or guide content.” Ostatnie zdanie: „Return only the JSON array.”

### 2.4 Co robi skrypt po otrzymaniu odpowiedzi (logika po stronie aplikacji)

- **Kategorie:** Funkcja `get_categories_from_config()` zwraca listę: `[production_category] + sandbox_categories`. Tylko te wartości są uznawane za dozwolone dla `category_slug`.

- **Duplikaty:** Funkcja `is_duplicate(problem, existing)` sprawdza, czy nowy problem nie powtarza już istniejącego. Porównanie jest bez uwzględnienia wielkości liter; dodatkowo, jeśli oba teksty mają więcej niż 10 znaków, sprawdzane jest „podobieństwo” w sensie: czy jeden tekst zawiera drugi (żeby wyłapać np. „turn X into Y” i „turn X into Y with Z”).

- **Walidacja odpowiedzi:** Funkcja `parse_ai_use_cases(raw, allowed_types, allowed_categories)` wyciąga z odpowiedzi modelu tablicę JSON (nawet gdy model owinął ją w markdown). Sprawdza, czy każdy element ma poprawne `suggested_content_type` (jedna z: how-to, guide, best, comparison) i `category_slug` z listy dozwolonych. Zwracane są tylko te wpisy, które przechodzą walidację.

- **Przypisanie audience:** Na podstawie **pozycji** use case'a w zwróconej tablicy i konfiguracji `use_case_audience_pyramid` wywoływana jest funkcja `audience_type_for_position(position_1based, pyramid)`. Zwraca ona wartość: `beginner`, `intermediate` lub `professional`. Np. przy piramidzie [3, 3] pozycje 1–3 to beginner, 4–6 to intermediate, 7+ to professional.

- **Zapis:** Nowe use case'y są **dopisane** do listy w `content/use_cases.yaml`. Wszystkie mają status `"todo"` — to sygnał dla `generate_queue.py`, że te wpisy czekają na dodanie do kolejki. Plik może rosnąć bez górnego limitu.

### 2.5 Parametry linii poleceń (CLI)

- Liczba use case'ów w jednym uruchomieniu pochodzi wyłącznie z configu (`use_case_batch_size`); skrypt nie przyjmuje `--limit`.
- **--category SLUG** — Ograniczenie: wszystkie use case'y mają dostać ten sam `category_slug`. Wartość musi być na liście dozwolonych (production lub sandbox).
- **--content-type TYPE** — Filtr typu treści: model ma dla każdego use case'a ustawić `suggested_content_type` na podaną wartość (how-to, guide, best, comparison). Parametr można podać wielokrotnie (wtedy zwykle bierzona jest pierwsza wartość).

---

## 3. Kolejka — co robi generate_queue.py

### 3.1 Wejście i wyjście

**Wejście:**  
Plik `content/use_cases.yaml` — skrypt szuka wpisów ze **statusem `todo`**. Opcjonalnie istniejący już plik `content/queue.yaml` (kolejka artykułów do wygenerowania).

**Wyjście:**  
Plik `content/queue.yaml` — lista wpisów kolejki. Każdy wpis to m.in.: `title`, `primary_keyword`, `content_type`, `category_slug`, `tools` (na tym etapie **puste**), `status`, `last_updated`, opcjonalnie `audience_type`, `batch_id`. Dla każdego use case'a ze statusem todo tworzony jest jeden wpis w kolejce; odpowiadające use case'y w use_cases.yaml są oznaczane jako `status: "generated"`, żeby przy następnym uruchomieniu nie trafić do kolejki drugi raz.

### 3.2 Logika — bez mapowania narzędzi

Plik **use_case_tools_mapping.yaml** w projekcie jest oznaczony jako **zdeprecjonowany**. Narzędzia **nie** są na tym etapie przypisywane do wpisów kolejki. Pole `tools` w każdym wpisie kolejki pozostaje **puste**. Wybór narzędzi odbywa się dopiero przy wypełnianiu artykułu treścią (fill_articles).

- **Tytuł:** Budowany przez funkcję `title_for_entry(problem, content_type)`. W zależności od `suggested_content_type` używane są szablony w stylu „Guide to …”, „How to …” itd.
- **primary_keyword:** Wyciągany z tytułu — wersja w lowercase, uproszczona (slug).
- **category_slug:** Brany z use case'a; jeśli brak — domyślnie `"ai-marketing-automation"`.
- **status:** Wpis w kolejce dostaje status `"todo"`. Po dodaniu do kolejki odpowiadające mu use case'y w `use_cases.yaml` zmieniają status na `"generated"`.
- **Duplikaty:** Sprawdzane po parze (title, content_type). Jeśli taki wpis już jest w kolejce, nie jest dodawany ponownie.

### 3.3 Parametry CLI

- **--dry-run** — Skrypt tylko wypisuje, co by zrobił; **nie** zapisuje `queue.yaml` ani **nie** aktualizuje statusów w `use_cases.yaml`. Przydatne do podglądu przed właściwym uruchomieniem.

---

*Kolejna część: generowanie szkieletów artykułów (generate_articles.py) i wypełnianie treścią (fill_articles.py) — w pliku `audit_workflow_czytelnie_czesc_2.md`.*
