# Workflow generowania artykułu — wersja czytelna (część 3)

**Zawartość tej części:** Od plików w content/articles do gotowych stron w public (render_site.py, content_index), zestawienie plików i katalogów oraz pełny przepływ end-to-end.  
**Cel:** Ten sam audyt co w `audit_full_article_generation_workflow.md`, opisany po ludzku, bez skracania.

---

## 6. Od „content” do „public” — jak artykuły trafiają na stronę

### 6.1 Które artykuły uznajemy za „produkcyjne”

Funkcja **get_production_articles(articles_dir, config_path)** w module **content_index.py** odpowiada na pytanie: które artykuły w ogóle bierzemy pod uwagę przy budowaniu strony.

**Źródło plików:** Katalog **content/articles/**. Przeglądane są pliki .md i .html. Dla **tej samej** nazwy pliku (stem) — np. `2025-01-15-how-to-repurpose-videos` — jeśli istnieją zarówno plik .md, jak i .html, system **preferuje .html**. Czyli przy renderze używana jest wersja wypełniona w trybie HTML, jeśli ją mamy.

**Filtry:**  
- Do dalszego przetwarzania trafiają **tylko** artykuły, które w metadanych (frontmatter lub komentarz HTML) mają **status `filled`**.  
- Artykuły ze statusem **blocked** są **pomijane** — nie trafiają na stronę.  
- Wszystkie inne statusy (draft, brak statusu itd.) też są pomijane.

**Wynik:** Lista par **(meta, path)** — meta to słownik z frontmatter (dla .md odczytywany z początku pliku, dla .html z komentarza na początku), path to ścieżka do pliku źródłowego (.html lub .md). Ta lista jest przekazywana dalej do renderowania.

### 6.2 Render pojedynczego artykułu — co robi _render_article

**Wejście:** Ścieżka do pliku w content/articles/ (plik .html lub .md), katalog wyjściowy (np. public), opcjonalnie zbiór istniejących slugów (do linków, unikania kolizji).

**Dla pliku HTML:** Odczytywany jest frontmatter z komentarza na początku oraz body HTML. Z body liczona jest liczba słów (do wyświetlenia „czas czytania”). W razie potrzeby usuwane są z body sekcja Disclosure (bo szablon strony i tak ją doda) oraz ewentualny nadmiarowy H1.

**Dla pliku Markdown:** Parsowany frontmatter i body. Body jest konwertowane z Markdown do HTML (funkcja _md_to_html). Stosowane są enhance_article oraz zamiana nazw narzędzi na linki (replace_tool_names_with_links z listy affiliate_tools.yaml).

**Wspólne dla obu ścieżek:** Budowana jest pełna strona artykułu: H1 (tytuł z meta), blok meta (kategoria, data, czas czytania, lead), treść body, sekcja „Read Next” (linki do 3 innych artykułów produkcyjnych, losowo wybranych), boks Disclosure. Szablon strony pochodzi z **templates/article.html** — w nim wstawiane są m.in. {{TITLE}}, {{STYLESHEET_HREF}} oraz miejsce na treść artykułu (<!-- ARTICLE_CONTENT -->).

**Zapis:** Gotowa strona zapisywana jest w **out_dir / "articles" / slug / "index.html"** — czyli w praktyce **public/articles/{slug}/index.html**. Dzięki temu każdy artykuł ma czytelny URL, np. /articles/how-to-repurpose-videos/.

### 6.3 Hub i strona główna

**Hub:** Treść huba jest w pliku **content/hubs/{production_category}.md** — nazwa pliku bierze się z configu (production_category). Skrypt render_site odczytuje ten plik, parsuje sekcje (wstęp + listy linków do artykułów) i renderuje go do **public/hubs/{hub_slug}/index.html**. Slug w ścieżce to hub_slug z configu (np. ai-marketing-automation), więc URL huba to np. /hubs/ai-marketing-automation/.

**Strona główna:** Plik **public/index.html** jest aktualizowany — lista najnowszych artykułów, link do huba itd.

### 6.4 Podsumowanie ścieżki „od fill do public”

1. **Fill** zapisuje gotowy artykuł w **content/articles/** — przy --html powstaje plik .html i w .md aktualizowany jest tylko status; bez --html zapisywany jest zaktualizowany .md. W obu przypadkach w metadanych ustawiany jest **status `filled`**.

2. **render_site.py** przy starcie wywołuje **get_production_articles(ARTICLES_DIR, CONFIG_PATH)**. Dostaje listę tylko tych plików z content/articles/, które mają status **filled** (blocked i inne są odfiltrowane). Dla tej samej nazwy pliku (stem) wybierany jest .html, jeśli istnieje.

3. Dla każdej pary (meta, path) wywoływana jest **_render_article(path, public, …)**. Wynik to gotowa strona HTML zapisana w **public/articles/{slug}/index.html**. Po uruchomieniu render_site w katalogu public masz pełną stronę: hub, strona główna i wszystkie artykuły ze statusem filled.

---

## 7. Pliki i katalogi kluczowe dla workflow

Poniżej zestawienie ścieżek i ich roli — żeby w jednym miejscu mieć „mapę” całego procesu.

| Ścieżka | Rola |
|---------|------|
| **content/config.yaml** | Główny plik konfiguracji: hub (production_category, hub_slug), kategorie (sandbox), batch use case'ów (use_case_batch_size), piramida odbiorców (use_case_audience_pyramid), sugerowane problemy i HARD LOCK (suggested_problems), tryb kategorii przy generowaniu artykułów (category_mode). |
| **content/use_cases.yaml** | Lista pomysłów na artykuły (use case'y): problem, suggested_content_type, category_slug, audience_type, batch_id, status. Uzupełniana przez generate_use_cases.py, czytana przez generate_queue.py. |
| **content/queue.yaml** | Kolejka artykułów do wygenerowania: title, primary_keyword, content_type, category_slug, tools (na tym etapie puste), status, last_updated, audience_type, batch_id itd. Uzupełniana przez generate_queue.py, czytana przez generate_articles.py. |
| **content/affiliate_tools.yaml** | Lista narzędzi AI (nazwa, kategoria, link, short_description_en). Używana przy wypełnianiu artykułów (fill) oraz przy renderze (zamiana nazw na linki). |
| **content/articles/*.md** | Szkielety i wypełnione artykuły w Markdown: frontmatter + body. Tu powstają pliki z generate_articles; tu fill_articles zapisuje wersję MD lub tylko aktualizuje status przy --html. |
| **content/articles/*.html** | Wypełnione artykuły w HTML (frontmatter w komentarzu na początku). Powstają przy fill_articles --html. Przy renderze preferowane nad .md przy tej samej nazwie pliku. |
| **templates/*.md** | Szablony szkieletu artykułu (how-to.md, guide.md itd.) — używane przez generate_articles do tworzenia plików .md z placeholderami. |
| **content/hubs/{production_category}.md** | Treść huba (np. ai-marketing-automation.md). Generowana przez generate_hubs.py, czytana przez render_site.py. |
| **public/articles/{slug}/index.html** | Gotowa, opublikowana wersja artykułu — efekt render_site. Tu użytkownik wchodzi przez przeglądarkę. |
| **public/hubs/{hub_slug}/index.html** | Gotowa strona huba — lista artykułów, intro itd. |

---

## 8. Przepływ end-to-end — całość w skrócie

Poniżej pełna sekwencja od konfiguracji do widocznej strony; nic nie jest pomijane, tylko ułożone w jeden ciąg.

1. **Konfiguracja**  
   Uzupełniasz (lub zostawiasz domyślny) plik **content/config.yaml**: production_category, hub_slug, sandbox_categories, use_case_batch_size, use_case_audience_pyramid, suggested_problems (opcjonalnie z HARD LOCK), category_mode. Od tego zależy cały dalszy pipeline.

2. **Use case'y**  
   Uruchamiasz **generate_use_cases.py**. Skrypt ładuje config i use_cases.yaml, zbiera słowa kluczowe z istniejących artykułów, buduje prompt i wysyła żądanie do API. Otrzymuje tablicę JSON z nowymi problemami biznesowymi; waliduje je, przypisuje audience_type na podstawie pozycji i piramidy, dopisuje wpisy do **content/use_cases.yaml** ze statusem **todo**.

3. **Kolejka**  
   Uruchamiasz **generate_queue.py**. Skrypt bierze use case'y ze statusem todo, dla każdego tworzy wpis w **content/queue.yaml** (tytuł, słowo kluczowe, typ treści, kategoria, tools puste, status todo itd.) i w use_cases.yaml zmienia status na **generated**.

4. **Szkielety**  
   Uruchamiasz **generate_articles.py**. Skrypt bierze wpisy z kolejki ze statusem todo, dla każdego wybiera szablon (how-to, guide itd.), podstawia zmienne (tytuł, słowo kluczowe, kategoria, linki wewnętrzne itd.) i zapisuje w **content/articles/** plik .md z frontmatter i body; status w frontmatter to **draft**, w kolejce — **generated**.

5. **Fill**  
   Uruchamiasz **fill_articles.py** (z --html jeśli chcesz HTML, z --write żeby zapisać). Dla każdego .md spełniającego warunki (status nie filled/blocked, ewentualnie filtry --since, --slug_contains, --limit) skrypt buduje prompt (HTML lub Markdown), wywołuje API, odbiera body, wyciąga TOOLS_SELECTED, ewentualnie generuje Prompt #2 w osobnym wywołaniu, wstawia listę narzędzi (środek G dla HTML), normalizuje sekcję Try it yourself (HTML), sanityzuje treść, zamienia placeholdery, uruchamia QA. Zapis: przy --html plik .html + aktualizacja statusu w .md; bez --html — zaktualizowany .md. Status w metadanych: **filled**.

6. **Render**  
   Uruchamiasz **render_site.py**. Skrypt wywołuje get_production_articles — bierze z **content/articles/** tylko pliki ze statusem **filled** (blocked pomijane), przy tej samej nazwie preferuje .html. Dla każdego artykułu buduje pełną stronę (H1, meta, body, Read Next, Disclosure) z szablonu article.html i zapisuje w **public/articles/{slug}/index.html**. Dodatkowo renderuje hub z content/hubs/{production_category}.md do public/hubs/{hub_slug}/index.html oraz aktualizuje stronę główną public/index.html.

Po tych krokach w **public/** masz gotową stronę: hub, lista artykułów i każdy artykuł pod własnym URL. Żaden krok nie jest opcjonalny w sensie „można pominąć” — każdy ma jasno zdefiniowane wejście i wyjście w tym dokumencie i w oryginalnym audycie.

---

*Koniec części 3. Spis wszystkich części i krótkie podsumowanie całości — w pliku `audit_workflow_czytelnie_index.md`.*
