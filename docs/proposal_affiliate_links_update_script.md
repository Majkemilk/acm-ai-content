# Propozycja: skrypt aktualizacji linków afiliacyjnych w artykułach

## 1. Cel

- Przeskanować wszystkie artykuły w `content/articles/` (pliki `.md` i `.html`).
- Znaleźć linki zewnętrzne wskazujące na domeny narzędzi z `content/affiliate_tools.yaml`.
- Tam, gdzie link w artykule to „ogólny” URL (np. bez parametrów referencyjnych), podmienić go na **link afiliacyjny** z YAML (ten sam lub z parametrami typu `?via=`, `?pc=`).

Efekt: w opublikowanych artykułach wszystkie odnośniki do narzędzi z listy afiliacyjnej prowadzą do aktualnych linków referencyjnych.

---

## 2. Zasada dopasowania

- **Źródło prawdy:** `content/affiliate_tools.yaml` → dla każdego wpisu: `name`, `affiliate_link`.
- **„Baza” URL narzędzia:** `affiliate_link` bez query string i bez fragmentu (#), z znormalizowaną ścieżką (np. usunięty trailing slash dla roota). Np. `https://www.opus.pro/?via=d9d7c5` → baza `https://www.opus.pro`.
- **W artykule:** dla każdego linku zewnętrznego (markdown `[text](url)` lub HTML `<a href="url">`) obliczamy bazę URL (scheme + host + path, bez query i #).
- **Podmiana:** jeśli baza linku z artykułu **jest równa** bazie któregoś narzędzia z YAML, a aktualny URL w artykule **różni się** od `affiliate_link` tego narzędzia (np. brakuje parametrów), wstawiamy w artykule pełny `affiliate_link`.

Dzięki temu:
- linki już afiliacyjne (z parametrami) nie są zmieniane,
- linki „ogólne” (ta sama domena/ścieżka, bez parametrów) są ujednolicane do wersji z YAML.

---

## 3. Zakres plików i formaty

- **Katalog:** `content/articles/` (wyłącznie; bez `articles_excluded_from_fill` chyba że dodasz opcję).
- **Pliki:** `*.md`, `*.html`.
- **Markdown:** linki `[tekst](url)` – tylko URL zewnętrzny (http/https); nie ruszamy `[tekst](/articles/...)` ani `[tekst](#anchor)`.
- **HTML:** atrybuty `href="url"` w tagach `<a>` – tylko URL zewnętrzne.

---

## 4. Workflow od skryptu do publikacji

1. **Aktualizacja `affiliate_tools.yaml`**  
   Upewnij się, że listy narzędzi i linki afiliacyjne są aktualne (ręcznie lub osobnym procesem).

2. **Dry-run (podgląd)**  
   ```bash
   python scripts/update_affiliate_links.py [--articles-dir content/articles]
   ```  
   Skrypt bez `--write`:
   - ładuje `affiliate_tools.yaml`,
   - skanuje `.md` i `.html`,
   - wypisuje raport: plik, znaleziony URL, docelowy `affiliate_link`, nazwa narzędzia.  
   Żadna plik nie jest zapisywany.

3. **Zapis zmian**  
   ```bash
   python scripts/update_affiliate_links.py --write
   ```  
   Dla każdego pliku, w którym są do podmiany:
   - opcjonalnie: backup `.bak` (np. `ścieżka.md.bak`),
   - podmiana URL-i w treści,
   - zapis tego samego pliku.  
   Raport na stdout (jak wyżej), plus informacja które pliki zostały zapisane.

4. **Render strony**  
   ```bash
   python scripts/render_site.py
   ```  
   Czyta zaktualizowane pliki z `content/articles/` i generuje `public/articles/.../index.html`. Linki w HTML-u będą już z aktualnymi URL-ami afiliacyjnymi.

5. **Sitemap (opcjonalnie)**  
   ```bash
   python scripts/generate_sitemap.py
   ```  
   Jeśli sitemapa zależy od listy artykułów (bez zmiany URL-i artykułów), zwykle wystarczy jeden run po `render_site.py`.

6. **Publikacja na WWW**  
   Wgranie katalogu `public/` na hosting (np. Cloudflare Pages): deploy jak zwykle (np. `git push` lub upload `public/`). Użytkownicy zobaczą zaktualizowane artykuły z linkami afiliacyjnymi.

**Podsumowanie sekwencji:**  
`update_affiliate_links.py --write` → `render_site.py` → (opcjonalnie `generate_sitemap.py`) → deploy `public/`.

---

## 5. Szczegóły implementacyjne (propozycja)

- **Parsowanie YAML:** bez zewnętrznych bibliotek (jak w `fill_articles._load_affiliate_tools` lub `render_site._load_affiliate_tools`): odczyt listy `tools`, dla każdego wpisu: `name`, `affiliate_link`; budowa mapy „baza URL → (name, full affiliate_link)”.
- **Normalizacja bazy URL:** `urllib.parse.urlparse` → scheme, netloc, path; path bez trailing `/` jeśli to tylko root; złożenie z powrotem bez query i fragment. Dla spójności: lowercase host (dla porównań).
- **Wykrywanie linków:**  
  - MD: regex dla `](http(s)?://[^)\s]+)` (nie łapiemy `](/...` ani `](#...`).  
  - HTML: regex dla `href="(http(s)?://[^"]+)"` lub prosty parser (unikać łapania w atrybutach w środku treści).
- **Backup:** przy `--write` przed zapisem skopiować oryginał do `path + '.bak'` (lub `path.with_suffix(path.suffix + '.bak')`); przy kolejnych uruchomieniach można nadpisywać ten sam `.bak` lub nie tworzyć backupu jeśli brak zmian w pliku.
- **Raport:** stdout w formie tekstowej (np. CSV lub czytelne linie: plik | stary_url | nowy_url | nazwa_narzędzia). Opcjonalnie `--report plik.json` dla maszynowego przetwarzania.

---

## 6. Ograniczenia i ryzyka

- **Głębokie linki:** Jeśli w artykule jest np. `https://www.descript.com/features`, a w YAML tylko `https://www.descript.com`, propozycja z p. 2 podmienia tylko gdy **baza** jest taka sama (scheme+host+path). Dla `https://www.descript.com/features` baza to `https://www.descript.com/features` – nie będzie równa `https://www.descript.com`, więc taki link nie zostanie podmieniony (bez rozszerzenia logiki o „prefix hosta”). Można później dodać opcję „replace by domain” (dowolna ścieżka na tej domenie → affiliate_link).
- **Duplikaty domen:** Jeśli w YAML dwa narzędzia mają ten sam host (np. różne ścieżki), mapa „baza → narzędzie” musi być jednoznaczna – np. dłuższa ścieżka wygrywa, albo pierwszeństwo ma wpis z listy.
- **Pliki .md vs .html:** Ten sam artykuł może istnieć jako `.md` i `.html`; skrypt aktualizuje oba niezależnie. Po `render_site.py` HTML w `public/` jest generowany z `.md` lub z `.html` (wg przyjętej w projekcie reguły) – więc po aktualizacji w `content/articles/` i ponownym renderze `public/` będzie spójne.

---

## 7. Zależności

- Tylko stdlib (re, pathlib, urllib.parse). Ścieżki względem katalogu projektu (np. `PROJECT_ROOT = Path(__file__).resolve().parent.parent`).
- Jeden plik skryptu: np. `scripts/update_affiliate_links.py`; opcjonalnie współdzielona funkcja ładowania YAML z `fill_articles` lub `render_site` (import lub skopiowanie minimalnej logiki).

---

## 8. Wdrożenie

- **Skrypt:** `scripts/update_affiliate_links.py`
- **Użycie:**  
  - `python scripts/update_affiliate_links.py` – dry-run (raport bez zapisu)  
  - `python scripts/update_affiliate_links.py --write` – zapis zmian; domyślnie backup `*.md.bak` / `*.html.bak`  
  - `--no-backup` – bez backupu przy `--write`  
  - `--articles-dir`, `--affiliate-file` – ścieżki (domyślnie `content/articles`, `content/affiliate_tools.yaml`)
- Dopasowanie: baza URL = scheme + host (lowercase) + path (bez trailing slash). Podmiana tylko gdy link w artykule ma tę samą bazę co narzędzie, a aktualny URL ≠ `affiliate_link` (np. brak parametrów referencyjnych).
