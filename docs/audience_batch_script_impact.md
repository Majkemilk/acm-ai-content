# Wpływ audience_type i batch_id na skrypty – analiza i zmiany

Po wdrożeniu pól **audience_type** (beginner / intermediate / professional) i **batch_id** oraz nazewnictwa plików `.audience_X.md` sprawdzono wszystkie skrypty korzystające z artykułów. Poniżej: co wymagało zmiany, co działa bez zmian.

---

## 1. fill_articles.py – **zmodyfikowany**

- **Odczyt:** `ARTICLES_DIR.glob("*.md")` – pliki `*.md` (w tym `nazwa.audience_beginner.md`) są wykrywane; `_parse_frontmatter` parsuje wszystkie klucze, więc **audience_type** i **batch_id** trafiają do `meta`.
- **Zapis:** Przy aktualizacji tylko statusu (`filled`) używane jest `_serialize_frontmatter(meta, order, "filled")` – **kolejność i wszystkie klucze** z oryginalnego frontmatter (w tym audience_type, batch_id) są zachowane.
- **Zmiana:** Aby treść wypełniana przez AI była dostosowana do grupy odbiorców:
  - Dodano `_audience_instruction(audience_type)` – krótkie wytyczne tonu/głębokości (beginner = prosty język, intermediate = pewna znajomość tematu, professional = zaawansowany, scaling).
  - W **build_prompt** (tryb markdown): do instrukcji dodawana jest sekcja „Audience (MUST follow)”, a do user message pole „Target audience level: {audience_type}”.
  - W **_build_html_prompt** (tryb --html): to samo – dopisana wytyczna audience i pole w user message.

Dzięki temu model dostosowuje język i poziom szczegółowości do beginner / intermediate / professional.

- **Długość artykułów (słowa) zależna od audience:** W `fill_articles.py` zdefiniowano stałą `WORD_COUNT_BY_AUDIENCE`: początkujący (500 / 800 przy strict), średniozaawansowany (700 / 1000), zaawansowany (1000 / 1200). Bramka QA (`run_preflight_qa`) przyjmuje `audience_type` z frontmatter i stosuje odpowiedni próg. W promptach (MD i HTML) dopisano `_audience_length_guidance(audience_type)`, żeby model od razu pisał w docelowej długości.

---

## 2. Skrypty bez zmian (działają poprawnie)

| Skrypt | Powód |
|--------|--------|
| **content_index.py** | `_parse_frontmatter` wczytuje dowolne klucze (key: value) – audience_type i batch_id są w meta. `get_production_articles` zwraca listę (meta, path); slug = path.stem, więc slug zawiera np. `.audience_beginner`. |
| **render_site.py** | Używa `meta.get("slug") or path.stem` i `existing_slugs` z get_production_articles. Artykuły renderowane do `public/articles/{slug}/index.html` – slug z pełnym stem jest poprawny. |
| **generate_sitemap.py** | Slug z `meta.get("slug") or path.stem` – URL w sitemapie to `/articles/{stem}/`, w tym `.audience_X`. |
| **generate_hubs.py** | Korzysta z get_production_articles; nie zależy od formatu nazwy pliku. |
| **generate_articles.py** | Już wcześniej rozszerzony: nazwa pliku z `.audience_X`, frontmatter, select_internal_links z batch_id/audience_type. |
| **generate_queue.py** | Już wcześniej rozszerzony: kopiuje audience_type i batch_id z use case. |
| **generate_use_cases.py** | Źródło audience_type i batch_id. |
| **monitor.py** | Używa get_production_articles i frontmatter – dodatkowe pola są w meta. |
| **import_from_public.py** | Importuje istniejące artykuły; nowe pliki z audience w nazwie będą obsłużone jak każdy inny .md. |
| **audit_links.py** | Sprawdza linki w HTML; href do `/articles/slug/` – slug może zawierać `.audience_X`. |

Żaden z tych skryptów nie zakłada „czystego” slugu bez sufiksu; wszystkie opierają się na path.stem lub meta["slug"].

---

## 3. Podsumowanie

- **Wymagana modyfikacja:** tylko **fill_articles.py** – dopisanie audience do promptu (MD i HTML), żeby generowana treść była dostosowana do grupy odbiorców.
- **Pozostałe skrypty:** bez zmian; obsługa audience_type, batch_id i nazw plików `.audience_X` wynika z obecnej logiki (stem = slug, frontmatter z dowolnymi kluczami).
