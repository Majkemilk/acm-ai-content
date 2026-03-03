# Propozycja implementacji: tylko .md jako źródło renderu (rezygnacja z content/*.html)

Na podstawie: `docs/audit_content_html_vs_md_only.md`. Propozycja do zatwierdzenia przed wdrożeniem; bez zmian w kodzie do momentu akceptacji.

---

## 1. Rekomendowany wariant: **A/C (fill tylko .md, render zawsze z .md)**

- **Refresh** wywołuje fill_articles **bez** `--html`. Model zwraca **Markdown**; zapis wyłącznie do `.md`.
- **Render_site** zawsze korzysta z pliku `.md` (w content nie zbieramy ani nie preferujemy `.html`). Public budowany jest z konwersji MD→HTML w render_site.
- **content/articles/*.html** przestaje być tworzony i używany; istniejące pliki `.html` w content można usunąć lub zarchiwizować (decyzja operacyjna).

---

## 2. Za (pros)

| Aspekt | Korzyść |
|--------|--------|
| **Jedno źródło prawdy** | Zawsze `.md`. Brak rozjazdu treści między .md a .html (np. stary .md przy „odświeżonym” .html). |
| **Struktura Try it yourself** | Sekcja pochodzi z .md (dwa bloki ``` → dwa `<pre>`). Brak problemu „jednego bloku” jak przy generowanym HTML (np. VEED). |
| **Prostszy model** | Jeden format w content, jedna ścieżka w render_site (tylko gałąź .md). Łatwiej opisać i utrzymać. |
| **--prompt2-only po .md** | Operuje na .md: wyciąga Prompt #1 z pierwszego bloku ```, API → Prompt #2, podmiana drugiego bloku w .md. Po renderze public jest aktualny. Spójne z „źródło = .md”. |
| **Wersjonowanie** | W git w content są tylko .md; historia zmian treści w jednym miejscu. |
| **Mniej plików** | Brak duplikatu .md + .html dla tego samego artykułu. |
| **Inne skrypty** | update_affiliate_links, clean_non_live_articles, monitor – uproszczenie (np. tylko .md, brak preferencji .html). |

---

## 3. Przeciw (cons)

| Aspekt | Koszt / ryzyko |
|--------|-----------------|
| **Rezygnacja z „pełnego HTML z modelu”** | Obecnie przy `--html` model zwraca cały body w HTML (Tailwind, sekcje). Po zmianie fill zwraca tylko Markdown; HTML powstaje w render_site z MD→HTML. Różnica w wyglądzie/strukturze możliwa (zależna od jakości _md_to_html i enhance_article). |
| **Jakość konwersji MD→HTML** | Spójność stylu (Tailwind, klasy) zależy od render_site. Trzeba mieć pewność, że _md_to_html + enhance_article dają wystarczająco dobry wynik dla wszystkich typów artykułów. |
| **Migracja istniejących .html** | Artykuły, które dziś mają w content tylko .html (albo .md nieaktualny), po przełączeniu będą renderowane z .md. Gdy .md jest stary/niekompletny, trzeba go uzupełnić lub wygenerować na nowo (np. jeden fill bez --html z aktualnego stanu). |
| **Usunięcie/archiwizacja .html** | Jednorazowa akcja: usunąć lub przenieść content/articles/*.html, żeby get_production_articles nie wybierał .html. Można to zrobić skryptem z backupem. |

---

## 4. Odrzucone warianty (krótko)

- **B (fill zapisuje HTML od razu do public):** Źródłem prawdy staje się public; wersjonowanie i --prompt2-only komplikują się; render_site musiałby „omijać” takie artykuły. **Nie rekomendowane.**
- **Zachowanie status quo:** Dwa formaty i problemy typu brak Prompt #1 przy --html pozostają. **Nie rekomendowane** przy celu uproszczenia i spójności.

---

## 5. Proponowany zakres zmian (kroki implementacji)

1. **content_index.get_production_articles()**  
   Nie preferować .html: dla danego stem zwracać tylko .md (np. zbierać tylko pliki .md albo przy tej samej nazwie stem wybierać .md zamiast .html). Efekt: render_site zawsze dostaje path = .md.

2. **refresh_articles**  
   Wywoływać fill_articles **bez** `--html`. Kryterium sukcesu: udany zapis .md (nie sprawdzać istnienia .html). Opcjonalnie: po refresh nie uruchamiać --prompt2-only na podstawie „czy w .html jest placeholder” – zamiast tego: osobna logika „czy w .md jest [PROMPT2_PLACEHOLDER]” (patrz punkt 5).

3. **fill_articles (główny fill)**  
   W refresh nie przekazywać `--html` (punkt 2). Opcjonalnie: usunąć lub zostawić nieużywaną ścieżkę zapisu do content .html (path.with_suffix(".html")) – można zostawić na później, żeby nie wywoływać fill z --html z zewnątrz; przy braku preferencji .html w get_production_articles i tak nikt nie będzie czytał content .html.

4. **fill_articles --prompt2-only**  
   Zmiana na pracę z **.md**:  
   - kandydaci: pliki .md zawierające w body [PROMPT2_PLACEHOLDER] (lub odpowiednik w MD);  
   - odczyt: treść .md;  
   - wyciągnięcie Prompt #1: pierwszy blok ``` w sekcji Try it yourself (istniejąca logika dla MD);  
   - API → Prompt #2;  
   - wstawienie: podmiana drugiego bloku ``` (albo markera [PROMPT2_PLACEHOLDER]) na treść Prompt #2 w body .md;  
   - zapis: .md.  
   Nie czytać ani nie zapisywać content/articles/*.html.

5. **refresh_articles a --prompt2-only**  
   Po passie fill (bez --html) wykrywać artykuły z placeholderem w **.md** (np. szukać [PROMPT2_PLACEHOLDER] w pliku .md). Dla nich uruchomić pass --prompt2-only (już operujący na .md).

6. **render_site**  
   Brak zmian w logice _render_article – nadal obsługuje path .md i path .html. Po zmianie w get_production_articles path będzie zawsze .md, więc w praktyce używana będzie tylko gałąź .md.

7. **update_affiliate_links, clean_non_live_articles, monitor**  
   Ujednolicenie: przy „jedna ścieżka na stem” brać tylko .md (nie zbierać .html lub nie preferować .html). Dopasować do nowej zasady „w content tylko .md jako źródło artykułów”.

8. **import_from_public**  
   Decyzja: przy rekonstrukcji brakującego źródła zapisywać tylko .md (konwersja HTML→MD jeśli potrzebna) albo tylko wtedy gdy nie ma .md – bez tworzenia content .html. Można zostawić na później lub uprościć do „tworzenie tylko .md”.

9. **Istniejące pliki content/articles/*.html**  
   Jednorazowo: usunąć lub przenieść do archiwum (np. content/articles_archive_html/) i ewentualnie nie iterować po nich w get_production_articles. Dzięki temu od razu „tylko .md” bez zmiany logiki zbierania (jeśli zbieramy tylko .md) albo z zmianą preferencji na .md.

---

## 6. Rekomendacja

**Rekomendacja: wdrożyć wariant A/C** – fill i refresh tylko na .md, render zawsze z .md, rezygnacja z tworzenia i używania content/articles/*.html.

- Usuwa przyczynę problemu z brakującym Prompt #1 (jedna ścieżka, struktura z .md).
- Upraszcza model danych (jedno źródło, jeden format) i ułatwia utrzymanie.
- Koszt to rezygnacja z „gotowego HTML z modelu” w content i uzależnienie wyglądu od MD→HTML w render_site; przy obecnej roli render_site jest to akceptowalne.
- Wymaga skoordynowanej zmiany w content_index, refresh_articles, fill_articles (--prompt2-only), ewentualnie w pozostałych skryptach z tabeli z audytu oraz jednorazowej akcji na istniejących .html.

Po zatwierdzeniu tej propozycji można przystąpić do wdrożenia krok po kroku (bez kodowania przed akceptacją).
