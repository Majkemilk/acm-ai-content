# Audyt: usuwanie i archiwizacja artykułów już opublikowanych (www, public/articles, content/articles)

## 1. Stan obecny – gdzie co jest i jak się łączy

| Miejsce | Zawartość | Kto z tego korzysta |
|--------|-----------|---------------------|
| **content/articles/** | Pliki źródłowe: `.md` (szkielet/frontmatter) i `.html` (wypełniona treść). Frontmatter zawiera m.in. `status`, `last_updated`, `content_type`, `audience_type`. | fill_articles, refresh, **render_site**, generate_hubs, content_index.get_production_articles |
| **public/articles/{slug}/index.html** | Gotowa strona artykułu na www (render z szablonu). | Serwis WWW, sitemap, hub (linki), strona główna (Read Next) |
| **content/hubs/{production_category}.md** | Treść huba: lista linków do artykułów. Generowana przez **generate_hubs.py** z listy **production** (get_production_articles). | render_site → public/hubs/{hub_slug}/index.html |
| **public/sitemap.xml** | Lista URL-i: hub + **wszystkie artykuły production**. Generowana przez **generate_sitemap.py** z get_production_articles. | SEO, indeksowanie |
| **content/queue.yaml** | Kolejka use case’ów (do wygenerowania szkieletów). Wpis ma m.in. status (todo/generated), slug/stem wynikowego artykułu. | generate_articles (tworzy .md), monitor, refresh (nie usuwa wpisów) |

**„Production”** = w `content_index.get_production_articles()`: tylko artykuły z **`status: filled`**. Artykuły z `status: blocked` lub innym (np. draft) **nie** trafiają do renderu, huba ani sitemapy.

**Ważne:** `render_site.py` **nie usuwa** katalogów w `public/articles/`. Przy każdym uruchomieniu zapisuje tylko te artykuły, które są aktualnie na liście production. Katalogi `public/articles/{slug}/` dla artykułów wcześniej zdjętych z production (np. po ustawieniu statusu na `blocked`) **pozostają na dysku** – adres URL dalej może zwracać starą stronę („stale”).

---

## 2. Możliwości

### 2.1 Kryteria wyboru artykułów do zdjęcia / usunięcia / archiwizacji

- **Po dacie** – np. `last_updated` starsze niż X miesięcy.
- **Po statusie** – tylko `filled` (już opublikowane) albo dodatkowo `blocked` (np. do posprzątania).
- **Po typie / audiencji** – `content_type`, `audience_type` (np. zdjąć wszystkie „sandbox”).
- **Po liście stemów/slugów** – plik lub lista w UI (ręczny wybór).
- **Po wzorcu w nazwie** – np. stem zawiera `audience_`, lub prefix daty `2024-`.
- **Kombinacja** – np. „filled + last_updated przed 2025-01-01”.

### 2.2 Warianty działania

| Wariant | Opis | content/articles | public/articles | Efekt na WWW |
|--------|------|-------------------|------------------|--------------|
| **A. Tylko „unpublish” (status)** | Ustawienie `status: blocked` (lub usunięcie z listy production w inny sposób). Brak fizycznego usuwania plików. | Bez zmian (pliki zostają) | Bez zmian (obecny render **nie** czyści starych katalogów) | Artykuł znika z huba, sitemapy, strony głównej. **URL /articles/{slug}/ nadal może działać** (stara strona), dopóki ktoś ręcznie nie usunie katalogu lub nie wdroży czyszczenia. |
| **B. Unpublish + czyszczenie public** | Jak A + **usunięcie** `public/articles/{slug}/` dla zdjętych artykułów. | Bez zmian | Katalogi usunięte | URL zwraca 404. Sitemap i hub już nie wskazują tego adresu (po ponownym wygenerowaniu). |
| **C. Archiwizacja** | Przeniesienie plików z `content/articles/` do katalogu archiwum (np. `content/archive_articles/` lub `content/articles_archive/`) + usunięcie `public/articles/{slug}/`. Opcjonalnie: ustawienie statusu na `archived` (wymaga rozszerzenia logiki production). | Pliki w archiwum | Katalogi usunięte | Jak B; ponadto źródła są zachowane w jednym miejscu (backup, ewentualny przywrót). |
| **D. Pełne usunięcie** | Usunięcie plików z `content/articles/` (.md + .html) **oraz** `public/articles/{slug}/`. | Pliki usunięte | Katalogi usunięte | Trwałe usunięcie z repozytorium i z www. Brak lokalnego backupu (poza VCS / zewnętrznym backupem). |

W obecnym kodzie **render nie czyści** `public/articles/` z katalogów nieobecnych w production, więc żeby „zdjąć artykuł z www” w sensie 404, trzeba **jawnie usuwać** (lub przenosić) katalogi w `public/articles/` (wariant B, C lub D) albo **dodać krok czyszczenia** w renderze (patrz niżej).

---

## 3. Ograniczenia i konsekwencje

### 3.1 Linki wewnętrzne

- W treści innych artykułów mogą być linki `href="/articles/{slug}/"`.  
- **render_site** w `_strip_invalid_internal_links` zamienia linki do slugów **nieobecnych w aktualnej liście production** na zwykły tekst (bez `<a>`).  
- **Konsekwencja:** Po zdjęciu artykułu A z production i ponownym renderze, linki do A w pozostałych artykułach staną się zwykłym tekstem. Nie ma w kodzie automatycznych przekierowań 301.

### 3.2 Linki zewnętrzne i SEO

- Zewnętrzne strony, social media, bookmarki mogą wskazywać na `/articles/{slug}/`.  
- **Jeśli usuniemy** `public/articles/{slug}/`: adres zwraca **404**.  
- **Opcje:** 410 Gone („na stałe usunięte”), 301 redirect na hub lub na inną stronę – **obecnie nie ma tego w pipeline**; można dodać (np. statyczna strona 410 lub reguły w serwerze/CDN).

### 3.3 Kolejka queue.yaml

- Wpisy w `queue.yaml` odnoszą się do use case’ów; po wygenerowaniu szkieletu mają status `generated` i mogą zawierać stem/slug wynikowego artykułu.  
- **Usunięcie lub archiwizacja** pliku w `content/articles/` **nie aktualizuje** queue.yaml. Można zostawić „martwe” wpisy albo dodać krok: oznaczanie/usuwanie wpisów powiązanych ze zdjętymi stemami (wymaga ustalenia mapowania queue → stem).

### 3.4 Hub i sitemap

- **generate_hubs** i **generate_sitemap** korzystają z `get_production_articles()`.  
- Po ustawieniu `status: blocked` (lub usunięciu pliku z content/articles) i ponownym uruchomieniu **generate_hubs** + **render_site** + **generate_sitemap**: artykuł znika z huba, sitemapy i strony głównej.  
- **Warunek:** Trzeba faktycznie **uruchomić** te skrypty po zmianie statusu/plików; same zmiany w content nie aktualizują automatycznie public.

### 3.5 Backupy

- W projekcie jest m.in. `content/backups/` (np. przy refresh).  
- Archiwizacja (wariant C) daje dodatkową warstwę: źródła w jednym katalogu zamiast trwałego usunięcia.  
- Pełne usunięcie (D) – odzyskanie tylko z VCS lub zewnętrznego backupu.

### 3.6 Flowtaro Monitor i inne skrypty

- Monitor i skrypty często iterują po `content/articles/*.md` lub czytają status z frontmatter.  
- Przeniesienie plików do archiwum **zmniejsza** listę „aktywnych” artykułów w tych narzędziach (co jest pożądane przy archiwizacji).  
- Usunięcie plików – te same skrypty po prostu nie widzą tych artykułów.

---

## 4. Za i przeciw pomysłowi (usuwanie/archiwizacja opublikowanych)

### Za

- **Kontrola nad tym, co jest na żywo** – możliwość zdjęcia nieaktualnych lub błędnych treści.
- **SEO i jakość** – mniej słabych/starych stron w indeksie, mniej rozczarowujących wejść (np. 404 z jasnym komunikatem lub 410).
- **Prostsza nawigacja** – hub i lista artykułów nie zaśmiecone dziesiątkami starych pozycji.
- **Zgodność z RODO/ polityką** – możliwość realnego usunięcia treści z serwera.
- **Archiwum** – wariant C pozwala zachować źródła do audytu lub przywrócenia bez zaśmiecania „produkcji”.

### Przeciw

- **Linki zewnętrzne** – wejścia na zdjęte URL-e dadzą 404 (lub 410) bez automatycznych przekierowań.
- **Ryzyko pomyłki** – usunięcie/archiwizacja po złych kryteriach (np. za szeroki zakres dat) może objąć wartościowe artykuły; potrzebne potwierdzenie (dry-run, lista do zatwierdzenia).
- **Zależności** – queue.yaml, ewentualne zewnętrzne referencje (dokumenty, CRM) – bez aktualizacji zostaną „martwe” linki.
- **Operacyjnie** – wymaga ustalenia: kto, kiedy i według jakich kryteriów wykonuje akcję; bez tego łatwo o niespójny stan (np. public bez czyszczenia przy samym zmianie statusu).

---

## 5. Propozycja implementacji (do zatwierdzenia)

### 5.1 Zakres

- **Jedna spójna ścieżka:** „Unpublish + opcjonalne usunięcie z public + opcjonalna archiwizacja w content”.
- **Kryteria wyboru:** konfigurowalne (np. plik z listą stemów, lub filtr: last_updated przed datą, status = filled, opcjonalnie content_type/audience_type). **Zawsze dry-run** z wypisaniem listy stemów do operacji; wykonanie dopiero po potwierdzeniu (np. flaga `--confirm` lub odpowiedź w UI).
- **Nie** implementować na razie: automatycznych 301/410 w samej aplikacji (można to później dodać po stronie serwera/CDN).

### 5.2 Kroki operacji (proponowany flow)

1. **Wybór zestawu**  
   Na podstawie kryteriów (lista stemów z pliku, data, status, typ) zbudować listę stemów do „unpublish”.

2. **Dry-run**  
   Wypisać: stem, tytuł (z frontmatter), last_updated, ścieżki do usunięcia/przeniesienia. **Nic nie zmieniać.**

3. **Właściwe wykonanie (np. `--confirm`)**  
   - Dla każdego stemu z listy:  
     - **content/articles:** ustawić w `.md` (i ewentualnie w komentarzu w `.html`) `status: blocked` **albo** przenieść parę `.md` + `.html` do `content/archive_articles/` (lub inna ustalona ścieżka).  
     - **public/articles:** usunąć katalog `public/articles/{stem}/` (cały katalog z `index.html`).  
   - Po operacji: **zalecane** uruchomienie `generate_hubs`, `render_site`, `generate_sitemap`, żeby hub, strona główna i sitemap były spójne.

4. **Opcjonalnie:** krok „clean” w **render_site**: przed zapisem nowych artykułów usunąć z `public/articles/` te katalogi, których stemów **nie ma** w aktualnym `get_production_articles()`. Wtedy sama zmiana statusu na `blocked` + ponowny render spowoduje zniknięcie strony z www bez osobnego skryptu czyszczącego (ale nadal potrzebny jest skrypt/UI do masowego ustawiania statusu według kryteriów).

### 5.3 Gdzie to zaimplementować

- **Opcja 1:** Nowy skrypt `scripts/unpublish_articles.py` (CLI: kryteria, `--dry-run`, `--confirm`, `--archive`).  
- **Opcja 2:** Zakładka w **Flowtaro Monitor**: wybór kryteriów (lub lista stemów), podgląd listy, przycisk „Unpublish (dry-run)” i „Unpublish (wykonaj)” + opcja „Przenieś do archiwum”.  
- **Opcja 3:** Oba: skrypt CLI dla automatyzacji/ciągów; w Monitorze – wygodny podgląd i pojedyncze/zbiorcze zdjęcie z potwierdzeniem.

Rekomendacja: **najpierw skrypt CLI** (`unpublish_articles.py`) z `--dry-run`, `--confirm`, `--archive`, kryteriami (np. `--before-date`, `--stems-file`), potem opcjonalnie integracja w Monitorze (wywołanie skryptu z parametrami z formularza).

### 5.4 Queue.yaml

- Na pierwszy etap: **nie** zmieniać automatycznie queue.yaml przy unpublish/archiwizacji.  
- W dokumentacji (lub w podsumowaniu dry-run) dodać informację: „Po zdjęciu artykułów warto przejrzeć content/queue.yaml pod kątem wpisów powiązanych ze zdjętymi stemami”.  
- Ewentualne automatyczne oznaczanie/usuwanie wpisów w queue – osobna decyzja i osobny krok (np. v2).

---

## 6. Rekomendacja

- **Wdrożyć** mechanizm zdjęcia opublikowanych artykułów z www i opcjonalnej archiwizacji, w formie **kontrolowanej** (dry-run + potwierdzenie) i z **jawnym usuwaniem** katalogów w `public/articles/`, żeby URL-e faktycznie przestały działać (404).  
- **Zalecany wariant operacji:** **Unpublish (status blocked lub przeniesienie do archiwum) + usunięcie `public/articles/{slug}/`**; po operacji uruchamiać generate_hubs, render_site, generate_sitemap.  
- **Pierwsza implementacja:** skrypt `scripts/unpublish_articles.py` z kryteriami (np. plik z listą stemów, data last_updated), `--dry-run`, `--confirm`, `--archive` (przenoszenie do `content/archive_articles/`).  
- **Opcjonalnie w render_site:** krok czyszczenia `public/articles/` z katalogów nieobecnych w aktualnej liście production – wtedy sama zmiana statusu + render da spójny stan www bez konieczności ręcznego usuwania katalogów dla każdego stemu.

**Nie kodować** do momentu Twojego zatwierdzenia: zakresu kryteriów, nazwy skryptu, ścieżki archiwum oraz tego, czy docelowo ma być tylko skrypt, tylko Monitor, czy oba.
