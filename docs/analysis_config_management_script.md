# Analiza: zarządzanie `content/config.yaml` przez skrypt Python i integracja z FlowMonitor

Dokument analizuje wprowadzanie, zmianę i usuwanie wpisów w `content/config.yaml` za pomocą skryptu Python, z uwzględnieniem logiki późniejszego przetwarzania oraz propozycji nazw przyjaznych użytkownikowi i interfejsu pod przyszłą aplikację FlowMonitor.

---

## 1. Cel i zakres

- **Obecny stan:** Plik `content/config.yaml` jest tworzony i edytowany ręcznie; służy jako źródło prawdy dla workflow (render_site, generate_hubs, generate_use_cases, generate_sitemap, itd.).
- **Cel:** Umożliwić zarządzanie wszystkimi elementami configu przez skrypt (dodawanie, zmiana, usuwanie) z zachowaniem spójności z resztą pipeline’u oraz przygotowaniem do późniejszego włączenia tego kroku jako funkcji w aplikacji FlowMonitor.
- **Kontekst:** Zgodnie z `docs/generate_use_cases_prompt_reference.md` config dostarcza m.in. listę kategorii do promptu use case’ów (`production_category` + `sandbox_categories`); `hub_slug` i `production_category` są używane w renderze i sitemapie.

---

## 2. Obecna struktura `config.yaml` i konsumenci

| Klucz (techniczny)   | Typ        | Przykład / opis |
|----------------------|------------|------------------|
| `production_category` | string     | `"ai-marketing-automation"` – nazwa pliku huba (bez `.md`) w `content/hubs/`. |
| `hub_slug`           | string     | `"ai-marketing-automation"` – slug URL huba (adres strony). |
| `sandbox_categories` | list[str]  | `["LLM SEO", "Visual automation and integrations"]` – dodatkowe kategorie do generowania use case’ów. |

**Konsumenci (skrypty):**

| Skrypt | Użycie |
|--------|--------|
| **content_index.py** | `load_config()` – zwraca dict z trzema polami; domyślne wartości przy braku pliku: `production_category` i `hub_slug` = `"ai-marketing-automation"`, `sandbox_categories` = `[]`. |
| **render_site.py** | `production_category` → ścieżka pliku huba `content/hubs/{production_category}.md`; `hub_slug` → katalog wyjścia `public/hubs/{hub_slug}/index.html` i link „All articles”. |
| **generate_hubs.py** | `production_category` → plik zapisu `content/hubs/{production_category}.md`. |
| **generate_sitemap.py** | `hub_slug` → wpis w sitemapie `/hubs/{hub_slug}/`. |
| **generate_use_cases.py** | Lista kategorii = `[production_category] + sandbox_categories` → „Allowed category_slug values” w promptcie i walidacja odpowiedzi API; `--category` musi być z tej listy. |
| **import_from_public.py** | `production_category` jako domyślna kategoria przy imporcie. |
| **monitor.py** | `load_config()` (kontekst monitoringu). |
| **add_cluster.py** | Odczyt configu; **zapis** przez `write_config(path, production_category, sandbox_categories)` – **nie zapisuje `hub_slug`** (przy zapisie wartość ta może zostać utracona). |

**Uwaga:** Skrypt `add_cluster.py` przy zapisie nadpisuje cały plik i nie uwzględnia `hub_slug` – to luka; nowy skrypt zarządzania configiem powinien zawsze zapisywać wszystkie trzy pola.

---

## 3. Logika przetwarzania poszczególnych elementów

### 3.1 production_category

- **Znaczenie:** Nazwa pliku huba (bez `.md`) w `content/hubs/`. Używana do **odczytu** (render_site) i **zapisu** (generate_hubs) pliku huba.
- **Walidacja przy zapisie:**
  - Nie pusty string (po strip).
  - Opcjonalnie: sprawdzenie, że plik `content/hubs/{production_category}.md` istnieje (albo że użytkownik świadomie ustawia nazwę przed pierwszym wygenerowaniem huba).
- **Zmiana:** Zmiana wartości przełącza system na inny plik huba; stary plik nie jest usuwany. Trzeba upewnić się, że docelowy plik istnieje lub zostanie utworzony przez `generate_hubs.py`.
- **Usunięcie / puste:** W `load_config()` używana jest wartość domyślna `"ai-marketing-automation"`. Skrypt może albo **nie pozwalać** na usunięcie (wymagać wartości), albo traktować „usuń” jako ustawienie wartości domyślnej.
- **Zależności:** Artykuły z `category_slug` równym `hub_slug` linkują do `/hubs/{hub_slug}/`; nazwa pliku (`production_category`) może być inna niż slug (np. plik `AI Automation & AI Agents.md`, slug `ai-marketing-automation`).

### 3.2 hub_slug

- **Znaczenie:** Slug URL huba – adres strony i katalog w `public/hubs/`. Musi być w formacie slug (małe litery, myślniki, bez spacji).
- **Walidacja przy zapisie:**
  - Nie pusty.
  - Zalecane: tylko znaki `a-z`, cyfry, myślniki (regex np. `^[a-z0-9-]+$`); ewentualnie automatyczna normalizacja (spacje → myślniki, lowercase).
- **Zmiana:** Zmiana slugu zmienia URL huba i ścieżkę w `public/`; stare linki z innych stron (główna, sitemap) zaczną wskazywać nowy URL. Artykuły z `category_slug` równym staremu slugowi będą miały nieaktualne linki w badge’u – warto to uwzględnić w dokumentacji lub w kolejnym kroku (aktualizacja frontmatter).
- **Usunięcie / puste:** W `load_config()` domyślnie `"ai-marketing-automation"`. Skrypt może wymagać wartości lub ustawiać domyślną.
- **Zależności:** `generate_sitemap.py`, `render_site.py`, linki w artykułach do `/hubs/{hub_slug}/`.

### 3.3 sandbox_categories

- **Znaczenie:** Lista nazw kategorii używanych **wyłącznie** przy generowaniu use case’ów (model może przypisywać nowe use case’y do tych kategorii). Nie wpływa na to, które artykuły są renderowane (wszystkie nie-blocked trafiają do jednego huba).
- **Walidacja przy zapisie:**
  - Wartość to lista stringów; każdy element po strip niepusty.
  - Przy dodawaniu pojedynczej kategorii: unikanie duplikatów (case-sensitive lub insensitive – zgodnie z `generate_use_cases.py`).
  - Opcjonalnie: brak duplikatu z `production_category` (jeśli system ma to egzekwować).
- **Zmiana:** Dodanie/usunięcie elementu zmienia listę dozwolonych `category_slug` w generate_use_cases; nie wymaga fizycznej zmiany plików hubów (obecnie jeden hub).
- **Usunięcie:** „Usunięcie” = ustawienie na listę pustą `[]` lub usunięcie jednego elementu z listy. Pusta lista jest poprawna – wtedy dozwolone jest tylko `production_category`.

---

## 4. Możliwości w skrypcie: wprowadzanie / zmiana / usuwanie

Poniżej zestawienie, co skrypt powinien umożliwiać, z uwzględnieniem logiki przetwarzania.

| Element | Wprowadzanie (set) | Zmiana (update) | Usuwanie |
|---------|--------------------|-----------------|----------|
| **production_category** | Ustawienie wartości (string); walidacja: niepusty; opcjonalnie sprawdzenie istnienia pliku huba. | Nadpisanie wartości; te same reguły co set. | Niedozwolone jako „usuń pole” – można ustawić wartość domyślną (np. `ai-marketing-automation`). |
| **hub_slug** | Ustawienie wartości; walidacja: niepusty, format slug (małe litery, myślniki). | Nadpisanie; ewentualna normalizacja. | Jak wyżej – tylko ustawienie wartości domyślnej. |
| **sandbox_categories** | Ustawienie całej listy lub **dodanie** jednej/kilku kategorii (bez duplikatów). | Zamiana listy lub append/remove pojedynczych. | Usunięcie całej listy (`[]`) lub **usunięcie pojedynczego** elementu z listy. |

**Propozycja operacji skryptu (CLI / później API dla FlowMonitor):**

- **Get** (odczyt): zwrócenie aktualnej wartości pojedynczego klucza lub całego configu.
- **Set** (ustawienie):
  - `--production-category VALUE` → ustawia `production_category`.
  - `--hub-slug VALUE` → ustawia `hub_slug` (z normalizacją).
  - `--sandbox-categories "A","B","C"` → nadpisuje listę.
- **Add** (dodanie):
  - `--add-sandbox-category "X"` → dopisuje do `sandbox_categories` (bez duplikatu).
- **Remove** (usunięcie):
  - `--remove-sandbox-category "X"` → usuwa jeden element z `sandbox_categories`.
- **Init** (opcjonalnie): utworzenie pliku config z wartościami domyślnymi, jeśli plik nie istnieje.

Zapis do pliku: zawsze pełna treść YAML z wszystkimi trzema kluczami (`production_category`, `hub_slug`, `sandbox_categories`), w ustalonej kolejności, żeby konsumenci i ludzie mieli spójny widok. Komentarze w istniejącym pliku można nie zachowywać (jak w `add_cluster.write_config`) albo w przyszłości dodać minimalny parser zachowujący komentarze – na start wystarczy nadpisanie bez komentarzy.

---

## 5. Nazwy przyjazne użytkownikowi (mapowanie)

Dla interfejsu użytkownika (CLI --help, FlowMonitor UI, komunikaty) proponowane nazwy zrozumiałe bez znajomości kodu:

| Klucz techniczny | Nazwa przyjazna (PL) | Krótki opis dla użytkownika |
|------------------|----------------------|-----------------------------|
| **production_category** | **Główny plik huba** | Nazwa pliku strony zbiorczej artykułów (bez .md) w folderze hubów. Na tej podstawie wybierany jest plik do wyświetlenia i generowania. |
| **hub_slug** | **Adres huba (slug)** | Adres URL strony huba (np. /hubs/ai-marketing-automation/). Tylko małe litery i myślniki. |
| **sandbox_categories** | **Kategorie do pomysłów** | Dodatkowe kategorie, z których model może wybierać przy generowaniu nowych pomysłów na artykuły (use case’y). Nie zmienia listy publikowanych artykułów. |

Opcjonalne warianty skrótowe (np. w tabelach):

- production_category → „Plik huba”
- hub_slug → „Slug huba” / „URL huba”
- sandbox_categories → „Kategorie (use case’y)” / „Dodatkowe kategorie”

W skrypcie i w FlowMonitor warto trzymać klucze techniczne w API/pliku, a nazwy przyjazne używać w komunikatach i etykietach.

---

## 6. Powiązanie z generowaniem use case’ów (generate_use_cases_prompt_reference.md)

Z dokumentu promptu wynika:

- **Dozwolone kategorie** w promptcie to `[production_category] + sandbox_categories` (punkt 3.1).
- **Parametryzacja:** lista kategorii pochodzi z configu; `--category` w generate_use_cases musi być jedną z tych wartości.

Skrypt zarządzający configem powinien więc:

- Przy **dodawaniu/usuwaniu** elementu w `sandbox_categories` mieć na uwadze, że zmieni to listę „Allowed category_slug values” w następnym uruchomieniu generate_use_cases.
- Nie wymagać od użytkownika znajomości nazw wewnętrznych – wystarczy użycie nazw przyjaznych w komunikatach, przy zachowaniu zapisu w YAML pod kluczami technicznymi.

---

## 7. Propozycja integracji z FlowMonitor (późniejszy krok)

Aby krok zarządzania configem mógł być w przyszłości funkcją w aplikacji FlowMonitor, sensowne jest:

- **Wydzielenie logiki do funkcji** w jednym module (np. `scripts/config_manager.py`):
  - `load_config(path) -> dict` – już jest w `content_index.py`; można reużywać lub wywołać z tego modułu.
  - `get_config_value(path, key) -> Any`
  - `set_config_value(path, key, value) -> None` (z walidacją)
  - `add_sandbox_category(path, category) -> bool` (True jeśli dodano)
  - `remove_sandbox_category(path, category) -> bool`
  - `write_config(path, production_category, hub_slug, sandbox_categories) -> None` – jeden punkt zapisu YAML (zawsze wszystkie trzy pola).
- **Skrypt CLI** (`scripts/manage_config.py` lub podobnie): parsowanie argumentów i wywołanie powyższych funkcji; wyjście tekstowe (np. „Updated hub_slug to …”) lub JSON dla maszynowego odczytu.
- **FlowMonitor:** Wywołanie tych samych funkcji (np. `config_manager.set_config_value(...)`) z poziomu aplikacji, bez uruchamiania CLI; ewentualnie wywołanie skryptu jako subprocess, jeśli aplikacja jest w innej technologii.

Interfejs funkcji powinien być stabilny (nazwy parametrów, zwracane typy), żeby później nie zmieniać kontraktu przy włączaniu do FlowMonitor.

---

## 8. Podsumowanie i kolejne kroki

- **Config** ma trzy elementy: `production_category`, `hub_slug`, `sandbox_categories`; każdy ma jasną logikę przetwarzania w skryptach (render, hub, sitemap, use case’y).
- **Skrypt** powinien umożliwiać: odczyt, ustawienie każdego pola, dla listy sandbox: dodawanie i usuwanie pojedynczych elementów; zapis zawsze z wszystkimi trzema kluczami (obecny `add_cluster.write_config` nie zapisuje `hub_slug` – to należy uzupełnić w nowym skrypcie).
- **Nazwy przyjazne:** „Główny plik huba”, „Adres huba (slug)”, „Kategorie do pomysłów” – do użycia w UI i komunikatach.
- **FlowMonitor:** Wydzielenie operacji do modułu z funkcjami (get/set/add/remove/write) pozwoli później zintegrować ten krok jako funkcję aplikacji bez duplikacji logiki.

Rekomendacja: zaimplementować `scripts/config_manager.py` z funkcjami wyżej oraz skrypt CLI `scripts/manage_config.py` korzystający z tego modułu; w dokumencacji (README lub osobny doc) podać mapowanie klucz → nazwa przyjazna i opis operacji.

---

## 9. Implementacja (wdrożone)

- **scripts/config_manager.py** – moduł z: `get_config_value`, `set_config_value`, `write_config`, `add_sandbox_category`, `remove_sandbox_category`, `init_config`, `update_config`; walidacja i normalizacja `hub_slug`; stała `FRIENDLY_NAMES`.
- **scripts/manage_config.py** – CLI: `--get KEY`, `--production-category`, `--hub-slug`, `--sandbox-categories A,B,C`, `--add-sandbox-category`, `--remove-sandbox-category`, `--init`, `--config PATH`, `--json`.
- **scripts/add_cluster.py** – zapis configu przez `config_manager.write_config(..., hub_slug, ...)`, dzięki czemu `hub_slug` nie jest gubiony przy dodawaniu klastra.
