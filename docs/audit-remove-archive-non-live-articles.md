# Audyt: usuwanie lub archiwizacja wyłącznie artykułów nieżywych (nieopublikowanych na www)

## 1. Definicja „żywych” vs „nieżywych”

W projekcie **„na żywo” (published)** = artykuł uwzględniany w `get_production_articles()` w `scripts/content_index.py`: musi mieć w `content/articles/` plik `.md` lub `.html` z frontmatterem, w którym **`status: filled`**. Artykuły z `status: blocked`, `draft`, `skeleton` lub bez statusu / z inną wartością **nie** trafiają do renderu, huba ani sitemapy i **nie** są uznawane za opublikowane.

| Grupa | content/articles | public/articles |
|--------|-------------------|------------------|
| **Żywe** | Stem z plikiem (.md lub .html) i **status: filled** | Katalog `public/articles/{slug}/` dla slugów z aktualnej listy production (get_production_articles). |
| **Nieżywe** | Stem z plikiem, ale **status ≠ filled** (blocked, draft, skeleton, pusty, nieparsowalny) **lub** brak poprawnego frontmatteru. | Katalog `public/articles/{slug}/`, którego **slug nie występuje** na aktualnej liście production (katalogi „stale” – np. po zmianie statusu na blocked lub po usunięciu pliku z content). |

Uwaga: `render_site` **nie usuwa** katalogów w `public/articles/`. Po zdjęciu artykułu z production (status → blocked) katalog `public/articles/{slug}/` zostaje na dysku – stąd możliwość „nieżywych” katalogów w public.

---

## 2. Co dokładnie można usuwać/archiwizować (tylko nieżywe)

### 2.1 content/articles

- **Pliki (.md i/lub .html)** dla stemów, gdzie **status ≠ "filled"**:
  - `status: blocked`, `draft`, `skeleton`, lub brak pola status / wartość nie rozpoznana.
  - Dla tego samego stemu może być tylko `.md`, tylko `.html`, lub oba – przy archiwizacji/usuwaniu bierzemy **oba** pliki o tym stemie (żeby nie zostawić „połówki”).
- **Stemy bez poprawnego frontmatteru** (np. uszkodzony plik) – można traktować jako nieżywe i włączyć do czyszczenia albo wykluczyć (np. tylko stemy z jawnym statusem ≠ filled).

### 2.2 public/articles

- **Katalogi** `public/articles/{slug}/` takie, że **slug nie jest** na liście zwracanej przez `get_production_articles(ARTICLES_DIR, CONFIG_PATH)`.
  - To są katalogi „stale”: albo odpowiadają artykułom z statusem blocked/draft, albo w content w ogóle nie ma już pliku dla tego slug (orphan).

Żadna z tych operacji **nie dotyka** artykułów żywych: nie zmieniamy plików ze statusem `filled` w content ani nie usuwamy katalogów w public odpowiadających aktualnej liście production.

---

## 3. Możliwości (kryteria i warianty)

### 3.1 Kryteria wyboru „nieżywych” w content/articles

- **Po statusie** – usuwać/archiwizować stemy, gdzie status ∈ {blocked, draft, skeleton} lub status ≠ filled (np. puste). To jest kryterium podstawowe dla „tylko nieżywe”.
- **Po dacie** – np. last_updated starsze niż X (dla nieżywych: „stare szkielety / stare drafty”).
- **Po liście stemów** – plik z listą stemów do usunięcia/archiwizacji (np. wygenerowaną z raportu w Monitorze).
- **Po wzorcu w nazwie** – np. stem zawiera `.audience_`, prefix daty `2024-` itd.
- **Kombinacja** – np. „status ≠ filled **i** last_updated przed 2025-01-01”.

Dla **public/articles** kryterium jest jedno: **slug nie należy do aktualnej listy production** (get_production_articles). Nie ma tu „częściowego” wyboru – albo katalog jest stale (usuwamy), albo jest na liście production (nie ruszamy).

### 3.2 Warianty działania

| Wariant | content/articles (tylko nieżywe) | public/articles (tylko stale) | Efekt |
|--------|-----------------------------------|---------------------------------|--------|
| **A. Tylko public** | Bez zmian | Usunąć katalogi `public/articles/{slug}/` dla slugów ∉ production | Stale URL-e znikają (404). Żywe URL-e bez zmian. content bez zmian. |
| **B. Tylko content** | Usunąć lub przenieść do archiwum pliki .md/.html dla stemów z status ≠ filled | Bez zmian | Mniej plików w content/articles (czystsza lista „do wypełnienia”). Stale katalogi w public zostają (URL dalej może działać na starej stronie). |
| **C. Content + public** | Jak B (usunąć/archiwizować nieżywe stemy) | Usunąć katalogi stale (slug ∉ production) | Pełne posprzątanie: ani nieżywe źródła, ani stale strony. Żywe artykuły nietknięte. |
| **D. Archiwizacja zamiast usuwania** | Przenieść nieżywe pliki do np. `content/archive_articles/` (zachować strukturę .md/.html) | Usunąć stale katalogi (albo tylko je usuwać, bez archiwum public – zwykle public się nie archiwizuje) | Odzyskanie miejsca i porządek przy możliwości przywrócenia treści z archiwum. |

Rekomendacja w ramach tego audytu: **wariant C lub D** – czyścimy i content (nieżywe), i public (stale), z opcją archiwizacji w content (D) zamiast trwałego usunięcia.

---

## 4. Ograniczenia i konsekwencje

### 4.1 Brak wpływu na żywe URL-e

- Operujemy **wyłącznie** na nieżywych (content: status ≠ filled; public: slug ∉ production). Żadna strona aktualnie publikowana nie jest usuwana ani przenoszona.
- **Konsekwencja:** Zero 404 dla artykułów obecnie w hubie/sitemapie.

### 4.2 Stale katalogi w public

- Usunięcie `public/articles/{slug}/` dla slug ∉ production powoduje **404** dla tego konkretnego URL. To są adresy, które i tak **nie** są już w sitemapie ani w hubie (bo stem nie jest filled). Zewnętrzne linki do takich stron dziś mogą jeszcze działać (stara strona); po usunięciu katalogu dostaną 404.
- **Ograniczenie:** Nie ma w projekcie mechanizmu 301/410 dla tych URL-i; jeśli kiedyś będzie potrzebny „ładny” komunikat lub przekierowanie, trzeba to dodać (np. w serwerze/CDN).

### 4.3 Nieżywe w content: utrata draftów / szkieletów

- Usunięcie (bez archiwum) plików z statusem blocked/draft/skeleton **trwale** usuwa te treści z repozytorium. Można je odtworzyć z queue (generate_articles) tylko jeśli use case nadal jest w queue i szkielet da się wygenerować od nowa; wypełniona treść z AI – nie.
- **Archiwizacja** (przeniesienie do `content/archive_articles/`) zachowuje pliki do ewentualnego przywrócenia lub audytu.

### 4.4 queue.yaml

- Usunięcie/archiwizacja pliku w `content/articles/` **nie** aktualizuje `queue.yaml`. Wpis z statusem `generated` dla tego stemu pozostaje („martwy” wpis). Na ten audyt **nie** zakładamy automatycznej zmiany queue – można to rozważyć osobno (np. oznaczanie/usuwanie wpisów dla zdjętych stemów).

### 4.5 Skrypty i Monitor

- **refresh_articles**, **fill_articles**, **generate_articles** iterują po `content/articles/`. Mniej plików = szybsze skanowanie i mniej „szumu” (np. raporty tylko dla aktywnych/do wypełnienia).
- **Flowtaro Monitor** – jeśli liczy/lista artykuły z `content/articles/`, po przeniesieniu nieżywych do archiwum lub usunięciu lista będzie odzwierciedlać tylko „aktywne” stemy (albo trzeba uwzględnić archiwum w statystykach – osobna decyzja).

### 4.6 Identyfikacja „jednego pliku na stem”

- W content_index dla jednego stemu wybierany jest **jeden** plik: `.html` ma pierwszeństwo nad `.md`. Status czytany jest z tego jednego pliku. Przy czyszczeniu nieżywych trzeba dla każdego stemu: (1) ustalić, który plik „reprezentuje” stem (np. ta sama logika: .html nad .md), (2) odczytać status z frontmatteru, (3) jeśli status ≠ filled – do listy do usunięcia/archiwizacji włączyć **oba** pliki tego stemu (.md i .html), żeby nie zostawić osieroconego pliku.

---

## 5. Za i przeciw pomysłowi (tylko nieżywe)

### Za

- **Żadna żywa strona nie znika** – zero ryzyka 404 dla aktualnie publikowanych artykułów.
- **Mniej bałaganu** – content/articles bez dziesiątek blocked/draft/skeleton; public/articles bez katalogów „stale”.
- **Szybsze skrypty** – mniej plików do skanowania w content; mniej katalogów w public.
- **Jasna granica** – kryterium „status ≠ filled” i „slug ∉ production” jest jednoznaczne w kodzie (get_production_articles).
- **Bezpiecznie dla SEO** – sitemap i hub nie zawierają nieżywych; usuwamy tylko to, co i tak nie jest już w production.

### Przeciw

- **Stale URL-e → 404** – ktoś mógł mieć link/bookmark do strony, która już nie jest w production; po usunięciu katalogu w public dostanie 404 (obecnie ta strona może jeszcze działać).
- **Utrata draftów przy usunięciu (bez archiwum)** – odzyskanie tylko z VCS lub z archiwum, jeśli wdrożymy archiwizację.
- **Queue nie jest czyszczone** – zostają wpisy dla stemów, których pliki już nie ma w content/articles (do ewentualnego posprzątania w przyszłości).

---

## 6. Propozycja implementacji (do zatwierdzenia)

### 6.1 Zakres

- **Dwa cele:** (1) usuwać/archiwizować w **content/articles** tylko stemy z **status ≠ filled**; (2) usuwać w **public/articles** tylko katalogi dla **slug ∉ production**.
- **Zawsze dry-run:** wypisanie listy stemów/slugów do operacji; wykonanie dopiero po potwierdzeniu (np. `--confirm`).
- **Opcja archiwum:** dla content – flaga np. `--archive` (przeniesienie do `content/archive_articles/` zamiast usuwania). Dla public – tylko usuwanie (bez archiwum stron HTML).

### 6.2 Kroki (proponowany flow)

1. **Production list**  
   Wywołać `get_production_articles(ARTICLES_DIR, CONFIG_PATH)`. Zbiór slugów production = `existing_slugs`.

2. **Lista nieżywych w content**  
   Dla każdego stemu w `content/articles/` (jeden path na stem, preferencja .html nad .md): odczytać status z frontmatteru; jeśli status ≠ "filled" (lub brak frontmatteru – opcjonalnie), dodać stem do listy. Dla każdego stemu z listy zbierać **wszystkie** pliki tego stemu (.md, .html).

3. **Lista stale w public**  
   Dla każdego katalogu `public/articles/{slug}/` (z `index.html`): jeśli slug ∉ existing_slugs, dodać slug do listy do usunięcia.

4. **Dry-run**  
   Wypisać: listę stemów nieżywych (content) z ścieżkami do usunięcia/przeniesienia; listę slugów stale (public) do usunięcia. **Nic nie zmieniać.**

5. **Wykonanie (np. `--confirm`)**  
   - **Content:** dla każdego stemu z listy nieżywych – albo usunąć wszystkie pliki tego stemu (.md, .html), albo przenieść je do `content/archive_articles/` (zachować nazwy plików).  
   - **Public:** dla każdego slug z listy stale – usunąć rekursywnie katalog `public/articles/{slug}/`.  
   Po operacji **nie** jest wymagane ponowne generowanie huba/sitemapy/renderu – nie zmieniliśmy żadnego artykułu żywego.

### 6.3 Gdzie zaimplementować

- **Opcja 1:** Nowy skrypt `scripts/clean_non_live_articles.py` (CLI: `--dry-run`, `--confirm`, `--archive` dla content, opcjonalnie `--content-only` / `--public-only`).
- **Opcja 2:** Zakładka lub przycisk w **Flowtaro Monitor**: „Wyczyść nieżywe (podgląd)” i „Wyczyść nieżywe (wykonaj)” z opcją archiwum; lista stemów/slugów w podglądzie.
- **Opcja 3:** Oba – skrypt do automatyzacji/CI; Monitor do ręcznego uruchomienia z podglądu.

Rekomendacja: **najpierw skrypt CLI** z `--dry-run`, `--confirm`, `--archive`, ewentualnie `--content-only` / `--public-only`, żeby móc czyścić tylko content albo tylko public. Potem opcjonalnie integracja w Monitorze.

### 6.4 queue.yaml

- Na pierwszy etap **nie** modyfikować queue.yaml. W dokumentacji lub w podsumowaniu dry-run dodać informację, że po usunięciu/archiwizacji nieżywych stemów warto przejrzeć `content/queue.yaml` pod kątem wpisów powiązanych z tymi stemami.

---

## 7. Rekomendacja

- **Wdrożyć** czyszczenie **wyłącznie nieżywych** artykułów: w **content/articles** (status ≠ filled) oraz **public/articles** (katalogi dla slug ∉ production).
- **Zalecany wariant:** **Content + public** (wariant C), z **archiwizacją** w content (wariant D) zamiast trwałego usunięcia – przenoszenie nieżywych plików do `content/archive_articles/`; w public – tylko usuwanie katalogów stale.
- **Implementacja:** skrypt `scripts/clean_non_live_articles.py` z `--dry-run`, `--confirm`, `--archive` (content), opcjonalnie `--content-only` / `--public-only`. Bez zmian w queue.yaml i bez kodowania do momentu zatwierdzenia.

**Nie kodować** do momentu Twojego zatwierdzenia: nazwy skryptu, ścieżki archiwum (`content/archive_articles/`), oraz tego, czy ma być tylko skrypt, tylko Monitor, czy oba.
