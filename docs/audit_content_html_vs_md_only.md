# Audyt: pliki .html w content/articles vs generowanie/odświeżanie tylko z .md do public

## 1. Obecny przepływ (z pośrednim plikiem content/*.html)

### 1.1 Kto tworzy content/articles/*.html
- **fill_articles.py** z flagą **--html** (wywoływany tak przez refresh_articles):
  - Wejście: plik **.md** (lista kandydatów to zawsze `ARTICLES_DIR.glob("*.md")`).
  - Do API idzie tylko **meta** + instrukcje; **treść .md nie jest** wysyłana.
  - Model zwraca **cały body w HTML** (Tailwind, sekcje, Try it yourself z blokami `<pre>`).
  - Zapis: `path.with_suffix(".html")` → w content/articles powstaje plik **.html** (frontmatter w komentarzu HTML + body).
  - Dodatkowo: aktualizacja frontmatter w .md (status „filled”), **bez** zmiany body w .md.

### 1.2 Kto korzysta z content/articles/*.html
| Składnik | Zachowanie |
|----------|------------|
| **content_index.get_production_articles()** | Dla tego samego stem wybiera **.html zamiast .md** (`by_stem[path.stem] = path` gdy suffix == ".html"). |
| **render_site.py** | Używa listy z `get_production_articles`. Gdy path to .html: czyta .html, parsuje frontmatter z komentarza, **body bierze wprost z HTML** (bez konwersji MD→HTML). Gdy path to .md: czyta .md, konwertuje body przez `_md_to_html()`, `enhance_article()`, `replace_tool_names_with_links()`. |
| **refresh_articles.py** | Po fill_articles sprawdza `path.with_suffix(".html").exists()`; jeśli brak .html → uznaje refresh za nieudany. Potem dla --prompt2-only uruchamia fill_articles --prompt2-only. |
| **fill_articles.py --prompt2-only** | Szuka par (.md, .html) gdzie .html **istnieje** i zawiera `[PROMPT2_PLACEHOLDER]`. Czyta **content .html**, wyciąga Prompt #1 z pierwszego `<pre>`, wywołuje API, podmienia placeholder na treść Prompt #2, **zapisuje z powrotem do content .html**. |
| **update_affiliate_links.py** | Skanuje zarówno .md, jak i .html w articles_dir. |
| **clean_non_live_articles.py** | Przy zbieraniu statusu i listy plików: jedna ścieżka na stem, **.html wygrywa** z .md. |
| **monitor.py** | Jedna ścieżka na stem, preferuje .html. |
| **import_from_public.py** | Tworzy **brakujące** źródła w content (tylko gdy nie ma ani .md, ani .html dla danego sluga w public). Może zapisać content/articles/<slug>.html z public. |

### 1.3 Skutek
- Dla artykułów „odświeżanych” z --html **źródłem prawdy** staje się **content .html** (treść), a .md służy głównie do meta (status, last_updated itd.) i do wyboru kandydatów.
- Render_site buduje public/articles/<slug>/index.html **z content .html**, gdy taki istnieje – czyli publikowana strona jest wierną kopią (z szablonem) tego, co jest w content .html.
- Brak bloku Prompt #1 w VEED wynika z tego, że model w trybie --html zwrócił HTML z **jednym** `<pre>` w „Try it yourself”; ten stan został zapisany w content .html i potem zrenderowany do public.

---

## 2. Po co jest ten pośredni krok (content .html)?

### 2.1 Przechowanie wyniku generacji HTML
- Model w trybie --html zwraca **gotowy HTML** (Tailwind, struktura, dwa bloki w Try it yourself).
- Ten wynik trzeba **gdzieś** zapisać. Obecnie zapis jest w content/articles/*.html.
- Daje to:
  - **Jedno miejsce „źródła”** dla renderu: render_site bierze ten sam plik i tylko opakowuje go w szablon strony.
  - **Wersjonowanie w repo**: content/ jest zwykle w git; .html w content można commitować i cofać.

### 2.2 Tryb --prompt2-only
- Wymaga pliku z **już wygenerowaną** treścią (w tym pierwszym blokiem Prompt #1) i z markerem `[PROMPT2_PLACEHOLDER]` w drugim bloku.
- Obecnie tym plikiem jest **content .html**: czytaj content .html → wyciągnij Prompt #1 → API → wstaw Prompt #2 → zapisz z powrotem do content .html.
- Bez pliku .html w content trzeba by mieć inną „bazę” do odczytu/zapisu (np. public albo .md z placeholderem w drugim bloku).

### 2.3 Rozdzielenie „edycji” od „buildu”
- content/ = źródła (md lub md+html).
- public/ = zbudowana strona (tylko do deployu).
- Dzięki temu można:
  - Mieć jeden katalog źródłowy (content) i jeden wynikowy (public).
  - Nie mieszać wersji „do edycji” z wersją „zgenerowaną przez model” w tym samym pliku co publiczna strona.

### 2.4 Różne ścieżki wejścia
- Część artykułów może być wypełniana z **.md** (fill bez --html) → tylko .md w content, render robi MD→HTML.
- Część z **--html** (refresh) → w content powstaje .html, render bierze ten .html.
- Preferencja „.html over .md” w get_production_articles sprawia, że gdy istnieje .html, to on decyduje o treści w public – nawet jeśli .md ma inną/starą treść.

---

## 3. Co by się stało, gdyby pominąć tworzenie .html w content i generować/odświeżać „bezpośrednio” z .md do .html w public?

Rozważamy **usunięcie** zapisu content/articles/*.html i używanie **wyłącznie .md** jako źródła do renderu (opcjonalnie: zapis wynikowego HTML od razu do public).

### 3.1 Wariant A: Fill tylko w .md, render zawsze .md → public
- **Fill (i refresh):** bez --html. Model zwraca **Markdown**. Zapis tylko do .md (obecna ścieżka `use_html=False`).
- **Render:** get_production_articles **nie** preferuje .html (albo w ogóle nie bierzemy .html z content). Zawsze path = .md. render_site czyta .md, `_md_to_html(body)`, enhance, linki, szablon → zapis do public/articles/<slug>/index.html.
- **Efekty:**
  - Brak plików .html w content – jeden format źródłowy (.md).
  - Treść w public jest **zawsze** z konwersji MD→HTML (render_site), więc np. dwa bloki kodu w .md → dwa `<pre>` w public (brak problemu „jednego bloku” jak przy generowanym HTML z --html).
  - Tryb „generuj od zera w HTML z Tailwind” (obecne --html) **znika** – albo rezygnacja z niego, albo trzeba by zapisywać wynik HTML gdzie indziej (np. od razu do public – patrz wariant B).
- **--prompt2-only:** Musiałby operować na **.md**: szukać w .md pierwszego bloku ``` (Prompt #1) i drugiego z [PROMPT2_PLACEHOLDER], wywołać API, podmienić drugi blok w .md, zapisać .md. Render potem zrobi .md→public. Wymaga to zmiany fill_prompt2_one / _insert_prompt2 na wersję MD (już częściowo jest w fill_articles dla ścieżki MD).

### 3.2 Wariant B: Fill dalej generuje HTML, ale zapisuje od razu do public (bez content .html)
- **Fill z --html:** Model zwraca HTML. Zamiast zapisywać do content/articles/<slug>.html, zapis do **public/articles/<slug>/index.html** (z tym samym opakowaniem co render_site: szablon, meta, disclosure itd.).
- **Render:** get_production_articles zwraca tylko .md (brak .html w content). Dla każdego artykułu path = .md → render jak dziś dla .md. **Konflikt:** dla „odświeżonych” artykułów treść w .md jest **nieaktualna** (fill z --html nie nadpisuje body w .md), więc render z .md nadpisałby publiczną stronę starą treścią z .md.
- Aby to miało sens, trzeba by:
  - Albo **nie** uruchamiać render_site dla artykułów „wypełnionych” tylko do public (np. lista „już zrenderowanych” slugu), albo
  - Render_site miałby dla takich slugu **pomijać** zapis (nie nadpisywać public) – wtedy public byłby aktualny tylko z fill.
- **--prompt2-only:** Czytałby **public** (np. public/articles/<slug>/index.html), wyciągał Prompt #1 z body, podmieniał placeholder, zapisywał z powrotem do public. Działa, ale:
  - Źródłem prawdy dla „wypełnionej” treści byłby **public**, a nie content (odwrotnie niż dziś).
  - Wersjonowanie w git: zmiany w public są zwykle ignorowane lub oddzielnie traktowane; trudniej cofnąć „wersję artykułu” niż przy content .html.

### 3.3 Wariant C: Nie tworzyć content .html i nie używać --html przy refresh
- Refresh wywołuje fill_articles **bez** --html. Fill uzupełnia/odświeża **.md** (model zwraca Markdown).
- Nie ma plików .html w content. get_production_articles zwraca tylko .md.
- Render_site zawsze renderuje z .md do public.
- **Efekty:**
  - Jeden spójny model: źródło = .md, wynik = public (MD→HTML w render_site).
  - Brak ryzyka „jednego bloku” z powodu odpowiedzi modelu w HTML (struktura z .md jest zachowana).
  - Rezygnacja z „pełnego HTML z Tailwind” generowanego w jednym kroku przez model – zamiast tego zawsze konwersja MD→HTML po stronie render_site (obecna ścieżka dla .md).

---

## 4. Zależności do zmiany przy rezygnacji z content .html

| Miejsce | Obecne zachowanie | Wymagana zmiana przy „tylko .md → public” |
|--------|--------------------|------------------------------------------|
| **content_index.get_production_articles()** | Preferuje .html nad .md dla tego samego stem. | Usunąć preferencję .html (albo nie zbierać .html) – wtedy zawsze zostaje .md. |
| **render_site._render_article()** | is_html = (path.suffix == ".html"); dla .html bierze body z HTML. | Nie będzie path .html z content; zawsze path .md → obecna gałąź dla .md zostaje. |
| **refresh_articles** | Po fill sprawdza istnienie path.with_suffix(".html"); wywołuje fill z --html. | Przy wariantach A/C: nie wywoływać --html; sukces = udany zapis .md. Przy B: sukces = zapis do public. |
| **fill_articles** (główny fill) | Przy use_html zapisuje do path.with_suffix(".html") i aktualizuje tylko frontmatter .md. | A/C: nie używać use_html w refresh; zapis tylko do .md. B: przy use_html zapisywać do public zamiast do content .html. |
| **fill_articles --prompt2-only** | Wymaga path.with_suffix(".html").exists(); czyta/zapisuje content .html. | A/C: operować na .md (szukać bloków ```, podmiana w body .md). B: czytać/zapisywać public/articles/<slug>/index.html. |
| **update_affiliate_links** | Iteruje po .md i .html. | Tylko .md – uproszczenie. |
| **clean_non_live_articles** | Jedna ścieżka na stem, .html wygrywa. | Jedna ścieżka na stem = .md. |
| **monitor / listy** | Preferuje .html. | Ustalić „zawsze .md” dla content. |
| **import_from_public** | Może tworzyć content .html. | Może tworzyć tylko .md (rekonstrukcja body z HTML→MD jest trudniejsza) albo zostawić tylko dla slugu bez żadnego pliku. |

---

## 5. Podsumowanie: po co pośredni krok (content .html)?

- **Przechowuje** wynik generacji „cały artykuł w HTML” (Tailwind, sekcje, bloki) w jednym miejscu w content.
- **Ustala „źródło prawdy”** dla odświeżonych artykułów: treść = content .html; .md tylko meta.
- **Umożliwia --prompt2-only** na pliku z pełną treścią i placeholderem (obecnie ten plik to content .html).
- **Oddziela** „źródła w content” od „buildu w public” – w content można trzymać i wersjonować zarówno .md, jak i wygenerowany .html.

**Koszt:** Dwa formaty w content (.md i .html), preferencja .html przy renderze, oraz to, że przy --html model generuje cały HTML „od zera” (bez treści .md), co prowadzi do problemów jak brak Prompt #1 gdy model zwróci tylko jeden blok.

**Gdyby pominąć ten krok:** Można generować/odświeżać tylko z .md i renderować .md → public (wariant A/C). Wtedy jeden format źródłowy (.md), spójna struktura (np. dwa bloki z .md), ale rezygnacja z „pełnego HTML z modelu” w content. Alternatywnie (B) zapisywać wygenerowany HTML od razu do public – wtedy content .html nie jest potrzebny, ale źródłem prawdy dla odświeżonych artykułów staje się public, co zmienia model wersjonowania i wymaga zmian w --prompt2-only oraz w render_site.

Audyt zakończony; bez zmian w kodzie.
