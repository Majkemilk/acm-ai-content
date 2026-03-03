# Workflow generowania artykułu — wersja czytelna (spis i podsumowanie)

Ta wersja audytu to **pełne** przerobienie dokumentu **audit_full_article_generation_workflow.md** na opis „po ludzku”: ten sam zakres (od konfiguracji do zapisu w public/articles), bez skracania i bez pomijania, z wszystkimi istotnymi treściami instrukcji API, tabelami i logiką — tylko sformułowane w zrozumiały sposób.

---

## Spis części

| Plik | Zawartość |
|------|-----------|
| **audit_workflow_czytelnie_czesc_1.md** | 1. Konfiguracja (config.yaml, content_index, wszystkie pola i domyślne wartości). 2. Generowanie pomysłów — use case'y (generate_use_cases.py: wejście/wyjście, API, pełne instrukcje i user message, HARD LOCK, logika skryptu, CLI). 3. Kolejka (generate_queue.py: wejście/wyjście, logika bez mapowania narzędzi, CLI). |
| **audit_workflow_czytelnie_czesc_2.md** | 4. Generowanie szkieletów (generate_articles.py: wejście/wyjście, config a kategoria, szablony i placeholdery, linki wewnętrzne, nazwy plików, CLI). 5. Wypełnianie treścią (fill_articles.py: wybór plików, tryb HTML vs MD, instrukcje API dla body HTML i MD z pełnymi treściami, post-processing, TOOLS_SELECTED i lista narzędzi, Prompt #2, normalizacja Try it yourself, quality gate, preflight QA, zapis, CLI). |
| **audit_workflow_czytelnie_czesc_3.md** | 6. Od content do public (render_site, content_index: które artykuły są production, render pojedynczego artykułu, hub i strona główna, ścieżka od fill do public). 7. Tabela plików i katalogów. 8. Przepływ end-to-end (szóstka kroków od configu do public). |

---

## Krótkie podsumowanie całości

**Konfiguracja** w jednym pliku (config.yaml) ustala: który hub jest „produkcyjny”, jaki slug ma w URL, jakie kategorie są dozwolone przy use case'ach, ile use case'ów generować w paczce i jak je rozłożyć na beginner/intermediate/professional, czy jest HARD LOCK (pierwszy element suggested_problems), oraz czy przy generowaniu artykułów wszędzie nadawać jedną kategorię, czy zachować kategorie z kolejki.

**Use case'y** to pomysły na artykuły: skrypt generate_use_cases pyta API o N konkretnych problemów biznesowych w AI marketing automation; odpowiedź to tablica JSON (problem, typ treści, kategoria); skrypt waliduje, przypisuje audience po pozycji i dopisuje wpisy do use_cases.yaml ze statusem todo.

**Kolejka** zamienia use case'y ze statusem todo na wpisy w queue.yaml (tytuł, słowo kluczowe, typ, kategoria; pole tools puste); status use case'ów zmienia na generated.

**Szkielety** to generate_articles: z kolejki (status todo) tworzy po jednym pliku .md w content/articles/ na wpis, z szablonu (how-to, guide itd.) z podstawionymi zmiennymi i linkami wewnętrznymi; status w kolejce → generated, w pliku → draft.

**Fill** to wypełnienie treścią: dla każdego .md (spełniającego warunki) jedno lub dwa wywołania API (body HTML lub MD, ewentualnie Prompt #2), post-processing (TOOLS_SELECTED, lista narzędzi z body, sanityzacja, placeholdery), opcjonalnie quality gate i zawsze preflight QA; zapis .html + aktualizacja .md lub sam .md; status → filled.

**Render** bierze z content/articles/ tylko pliki ze statusem filled (blocked pomijane), przy tej samej nazwie preferuje .html, dla każdego buduje stronę z szablonu i zapisuje w public/articles/{slug}/index.html; dodatkowo hub i strona główna.

Żaden z tych kroków nie został w wersji czytelnej pominięty ani uproszczony ponad to, co wynika z przełożenia na język potoczny — wszystkie istotne instrukcje API, reguły, funkcje i ścieżki plików są uwzględnione w odpowiedniej części.
