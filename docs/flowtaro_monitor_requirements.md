# Flowtaro Monitor – założenia i plan wymagań systemowych (wersja do konsultacji)

*Aplikacja desktop, minimalistyczny UI, build do pojedynczego pliku .exe – uruchomienie bez przeglądarki i bez zależności od Streamlit.*

---

## 1. Cel i zakres aplikacji

**Flowtaro Monitor** to **niezależna aplikacja desktopowa** uruchamiana **lokalnie**, z **prostym minimalistycznym UI**, która:

1. **Ujednolica workflow** – uruchamianie istniejących skryptów pipeline'u (generowanie pomysłów → kolejka → artykuły → wypełnianie → render → publikacja) z jednego miejsca.
2. **Dodaje funkcję odświeżania** – „odśwież artykuły starsze niż X dni" z opcjonalnymi **filtrami** (kategoria, audience).
3. **Monitoruje kluczowe dane** – podgląd stanu pipeline'u (artykuły, kolejka, koszty API, błędy, ostatnie uruchomienia) w formie czytelnej dla użytkownika.

**Zakres:** jeden repozytorium / jeden katalog projektu (ACM). Aplikacja działa w katalogu projektu, czyta i zapisuje pliki w `content/`, `logs/`, uruchamia skrypty z `scripts/`. **Nie obejmuje** (na ten moment): deployu na serwer, multi-tenant, harmonogramu zadań w chmurze, autentykacji użytkowników.

---

## 2. Założenia ogólne

| Założenie | Opis |
|-----------|------|
| **Środowisko** | Lokalna maszyna (Windows w pierwszej kolejności; możliwość późniejszego wsparcia macOS/Linux). Aplikacja **budowana do pojedynczego pliku .exe** – użytkownik **nie musi** mieć zainstalowanego Pythona ani przeglądarki. |
| **Uruchomienie** | Użytkownik uruchamia **FlowtaroMonitor.exe** (lub inna nazwa). Plik .exe powinien znajdować się w **katalogu głównym projektu ACM** (tam gdzie `content/`, `scripts/`, `logs/`) lub użytkownik przy pierwszym uruchomieniu wybiera ten katalog. |
| **Single-user** | Aplikacja dla jednego użytkownika / jednego projektu. Brak logowania i ról. |
| **Bez zmian w skryptach** | FlowMonitor **wywołuje** istniejące skrypty (subprocess), nie zastępuje ich logiki. |
| **Źródło prawdy** | Pliki w `content/` i `logs/` – to źródło prawdy. UI tylko odczytuje i zapisuje te pliki oraz uruchamia skrypty. |
| **UI** | **Minimalistyczny interfejs desktopowy** – okno z zakładkami lub panelami (Dashboard, Workflow), przyciski, etykiety, pola tekstowe, obszar na logi. Bez przeglądarki, bez serwera HTTP. |

---

## 3. Wybór technologii UI i build

**Aplikacja desktopowa, build do .exe.**

- **UI:** **Tkinter** (biblioteka standardowa Pythona) – prosty, lekki, bez dodatkowych zależności; dobrze pakuje się do .exe. Alternatywnie: CustomTkinter lub PyQt – jeśli w kolejnym etapie zależy na nowoczesnym wyglądzie.
- **Build:** **PyInstaller** – pakowanie aplikacji Pythona (wraz z interpreterem i zależnościami) w **pojedynczy plik .exe**. Użytkownik otrzymuje jeden plik wykonywalny; uruchomienie bez `pip install` i bez Pythona w systemie.
- **Ścieżka projektu:** Przy uruchomieniu .exe: jeśli aplikacja jest „zamrożona" (frozen), katalog projektu = katalog, w którym leży .exe (zalecane: .exe w rootcie ACM). Opcjonalnie: przy pierwszym uruchomieniu okno wyboru katalogu ACM i zapis ścieżki w pliku konfiguracyjnym użytkownika.

---

## 4. Pełny workflow (skrypty do obsługi)

| Krok | Skrypt | Opis (dla UI) |
|------|--------|----------------|
| 1 | **manage_config** (odczyt/zapis) | Konfiguracja huba: główny plik huba, slug, kategorie sandbox, sugerowane problemy. Wywołanie `config_manager` (get/set/update). |
| 2 | **generate_use_cases.py** | Generowanie pomysłów na artykuły (use case'y) z API; wynik w `content/use_cases.yaml`. Parametry: `--limit`, `--category`, `--content-type`. |
| 3 | **generate_queue.py** | Tworzenie wpisów kolejki z use case'ów (z mapowaniem narzędzi); wynik w `content/queue.yaml`. Parametry: `--dry-run`. |
| 4 | **generate_articles.py** | Generowanie szkieletów artykułów z kolejki (status todo → generated). Opcja: `--backfill`. |
| 5 | **fill_articles.py** | Wypełnianie szkieletów treścią z AI. Parametry: `--write`, `--force`, `--limit`, `--slug_contains`, `--since`, `--qa` / `--no-qa`, `--quality_gate`, itd. |
| 6 | **update_affiliate_links.py** | Podmiana linków w artykułach na linki afiliacyjne. Parametry: `--write`, `--no-backup`. |
| 7 | **generate_hubs.py** | Generowanie pliku huba. |
| 8 | **generate_sitemap.py** | Generowanie sitemapy. |
| 9 | **render_site.py** | Render strony do `public/`. |
| — | **refresh_articles.py** | Odświeżanie artykułów starszych niż X dni (z filtrami – patrz sekcja 5). |
| — | **add_cluster.py** | Dodawanie nowego klastra (kategorii) – opcjonalnie w UI. |

**Wymaganie:** Aplikacja uruchamia każdy skrypt z parametrami wybranymi przez użytkownika (lub domyślnymi), z podglądem wyniku (log) i opcją **„Zapisz log"**.

---

## 5. Funkcja „Odświeżanie artykułów starszych niż X"

- **Definicja:** Użytkownik podaje próg wieku w dniach (np. 90) oraz opcjonalnie **filtry**: kategoria (z configu), audience (beginner / intermediate / professional). Aplikacja znajduje artykuły spełniające kryteria, dla każdego uruchamia fill i aktualizuje `last_updated`; opcjonalnie – hub/sitemap/render.

- **Istniejący skrypt:** `scripts/refresh_articles.py` (parametry: `--days`, `--limit`, `--dry-run`, `--no-render`). Filtry kategoria/audience realizowane po stronie aplikacji (odczyt frontmatter, filtrowanie listy, wywołanie fill per artykuł).

- **UI:** Formularz: „Starsze niż [X] dni", „Limit [M]", filtr „Kategoria", „Audience", „Uruchom render po odświeżeniu", „Dry-run".

---

## 6. Monitorowanie kluczowych danych

| Obszar | Dane (źródło) | Prezentacja w UI |
|--------|----------------|------------------|
| **Artykuły** | Liczba wszystkich (po stem), production (status ≠ blocked), rozkład po statusie i typie treści. | Etykiety / lista: „Artykuły: X łącznie, Y na żywo", „Po statusie", „Po typie". |
| **Kolejka** | Liczba wpisów, rozkład po statusie (todo / generated), najstarsze todo. | „Kolejka: N wpisów, K todo", lista 5 najstarszych todo. |
| **Koszty API** | `logs/api_costs.json`: suma całości, suma za ostatnie N dni, średnia na artykuł. | Tekst; opcjonalnie wykres w kolejnym etapie. Przycisk „Reset kosztów". |
| **Ostatnie uruchomienia** | `logs/last_run_*.txt`. | „Ostatnie uruchomienie: …" per skrypt. |
| **Błędy** | Ostatnie linie z `logs/errors.log`. | Rozwijana sekcja lub pole tekstowe z ostatnimi 10–20 wpisami. |

**Odświeżanie:** Przycisk „Odśwież dane" lub odświeżanie przy przełączeniu na zakładkę Dashboard.

---

## 7. Konfiguracja i dane edytowalne w UI

| Element | Plik / moduł | Operacje w UI |
|---------|----------------|----------------|
| **Config huba** | `content/config.yaml` przez `config_manager` | Odczyt i edycja: production_category, hub_slug, sandbox_categories, suggested_problems, use_case_batch_size, use_case_audience_pyramid. Nazwy przyjazne: `config_manager.FRIENDLY_NAMES`. |
| **Mapowanie problem → narzędzia** | `content/use_case_tools_mapping.yaml` | **Pierwsza wersja:** tylko **odczyt i wyświetlanie** mapowania. **Kolejny etap:** edycja wpisów. |

---

## 8. Funkcje aplikacji – zbiorcza lista

1. **Dashboard** – podsumowanie: artykuły, kolejka, koszty, ostatnie uruchomienia, ostatnie błędy; przycisk „Odśwież dane".
2. **Konfiguracja** – edycja `config.yaml` (wszystkie pola); zapis przez `config_manager`.
3. **Workflow** – przyciski/akcje dla każdego skryptu z opcjonalnymi parametrami; po uruchomieniu – **obszar z logiem** i **„Zapisz log"** do pliku.
4. **Odświeżanie artykułów** – formularz z progą wieku, limitem, filtrami kategoria/audience, dry-run, „Pomiń render".
5. **Mapowanie problem → narzędzia** – podgląd (odczyt); ewentualna edycja w kolejnej fazie.
6. **Logi wykonania** – podgląd stdout/stderr po uruchomieniu skryptu, przycisk „Zapisz log" do pliku.

**Bezpieczeństwo:** Klucze API nie trafiają do logów (subprocess z przechwyceniem outputu; skrypty nie powinny wypisywać kluczy).

---

## 9. Wymagania techniczne (kierunkowe)

- **Stack:** Python 3.x + **Tkinter** (stdlib). **Build:** PyInstaller → jeden plik **.exe** (np. `FlowtaroMonitor.exe`).
- **Ścieżka projektu:** Przy uruchomieniu .exe – katalog zawierający .exe = katalog główny ACM (zalecane umieszczenie .exe w rootcie projektu). W trybie deweloperskim (python main.py) – katalog nad `flowtaro_monitor/` = ACM.
- **Wywołanie skryptów:** subprocess z cwd = katalog projektu; przechwytywanie stdout/stderr; wyświetlanie w UI i zapis do pliku.
- **Kompatybilność:** Zachowanie działania istniejących skryptów (cwd, env, encoding).

---

## 10. Kolejność wdrożenia (etapy)

| Etap | Zakres | Opis |
|------|--------|------|
| **MVP** | Dashboard + podstawowe skrypty + build .exe | Odczyt stanu (artykuły, kolejka, koszty, błędy, ostatnie uruchomienia). Uruchomienie skryptów: generate_use_cases, generate_queue, generate_articles, fill_articles, render_site – z ograniczonymi parametrami. Podgląd logów i „Zapisz log". Build do .exe (PyInstaller). |
| **Odświeżanie** | Pełna funkcja z filtrami | Formularz odświeżania z progą wieku, limitem, filtrami kategoria i audience. Dry-run, „Pomiń render". Zapisz log. |
| **Konfiguracja i mapowanie** | Edycja configu i podgląd mapowania | Edycja `config.yaml` w UI. Odczyt i wyświetlanie `use_case_tools_mapping.yaml`; ewentualnie edycja w kolejnym kroku. |
| **Wykresy i raporty** | Wizualizacja (opcjonalnie) | Wykres kosztów API w czasie (np. matplotlib w oknie lub eksport do pliku). |

---

## 11. Poza zakresem (na ten moment)

- Harmonogram zadań (cron / scheduler).
- Deploy na serwer / dostęp zdalny.
- Wieloprojektowość (wiele katalogów ACM).
- Zaawansowana edycja `queue.yaml` i `use_cases.yaml` w UI.
- Integracja z systemem kontroli wersji (git).

---

## 12. Kryteria akceptacji (propozycja)

- Użytkownik uruchamia **jeden plik .exe** (bez instalacji Pythona i bez przeglądarki).
- Użytkownik może z jednego okna zobaczyć stan pipeline'u (artykuły, kolejka, koszty, błędy, ostatnie uruchomienia).
- Użytkownik może uruchomić wybrane skrypty workflow z parametrami, zobaczyć log i zapisać go do pliku.
- Użytkownik może uruchomić „Odśwież artykuły starsze niż X dni" z wyborem X, limitu, filtrów i opcji renderu.
- Użytkownik może przeglądać mapowanie problem → narzędzia (odczyt).
- Aplikacja nie zmienia logiki skryptów; stan plików po wywołaniu skryptów taki sam jak przy CLI.
- .exe umieszczony w katalogu głównym projektu ACM (lub wybór katalogu przy pierwszym uruchomieniu).

---

*Wersja dokumentu: aplikacja desktop, build do .exe, UI minimalistyczny (Tkinter), bez Streamlit.*
