# Rekomendacja: struktura strony pod wiele hubów

**Cel:** Więcej niż jeden hub – każdy hub ma własny URL, listę artykułów i treść.

---

## 1. Stan obecny (skrót)

- **Config:** `production_category` (jeden string), `sandbox_categories` (lista).
- **Hub:** Renderowany jest **tylko jeden** plik: `content/hubs/{production_category}.md` → `public/hubs/{path.stem}/index.html`. Drugi plik (`ai-marketing-automation.md`) nie jest używany.
- **Artykuły:** Wszystkie nie-blocked trafiają do jednego huba; w artykułach badge kategorii linkuje do `/hubs/{category_slug}/`. Jeśli `category_slug` ≠ nazwa pliku huba, link prowadzi do 404.
- **URL huba:** Obecnie `path.stem` (np. "AI Automation & AI Agents") – w URL lepiej używać **slug** (np. `ai-automation-agents`).
- **generate_hubs.py:** Stałe `HUB_SLUG`, `HUB_TITLE`; zapis jednego pliku pod `production_category`.

---

## 2. Proponowana struktura

### 2.1 Config: lista hubów

W `content/config.yaml` zamiast jednego `production_category` wprowadzić **listę hubów** ze **slug** i **tytułem**:

```yaml
# Obecne (zostaw opcjonalnie dla kompatybilności wstecznej):
# production_category: "AI Automation & AI Agents"

hubs:
  - slug: ai-automation-agents
    title: "AI Automation & AI Agents"
  - slug: ai-marketing-automation
    title: "AI Marketing Automation Tools & Workflows"
  - slug: llm-seo
    title: "LLM SEO"

sandbox_categories:
  - "Visual automation and integrations"
```

- **slug** – używany w URL (`/hubs/{slug}/`) i w nazwie pliku huba (`content/hubs/{slug}.md`).
- **title** – wyświetlany na stronie huba i w linkach.
- Artykuły z `category_slug` równym `slug` huba trafiają do tego huba.

Opcja: zamiast listy obiektów można mieć mapowanie `category_slug → title` (slug wtedy = klucz), jeśli chcesz minimalną zmianę YAML.

### 2.2 Zasób treści: jeden plik na hub

- **Ścieżka:** `content/hubs/{slug}.md` (np. `ai-automation-agents.md`, `ai-marketing-automation.md`).
- **Frontmatter:** opcjonalnie `slug`, `title` (nadpisują config).
- **Render:** Dla każdego wpisu z `hubs` w configu: jeśli istnieje `content/hubs/{slug}.md`, renderuj do `public/hubs/{slug}/index.html`; lista artykułów **tylko** dla tego huba (patrz 2.4).

### 2.2a Nawigacja i zawartość huba (audyt)

- **Strona główna:** "All articles" prowadzi do huba; "Newest articles" pokazuje 12 najnowszych. Użytkownik, który klika "All articles", już widział najnowsze na głównej.
- **Obecnie w hubie:** Intro zachęca do "Start here" (najnowszy materiał), potem sekcja "Start here" (5 kart), potem Guides / How-to / Reviews / Comparisons / Best. Sekcja "Start here" jest redundantna względem "Newest articles" na głównej i nie wnosi wartości.
- **Rekomendacja:** Usunąć sekcję "Start here" z huba oraz z intro zdanie o "Start here" / "newest material". Hub powinien zaczynać się od linku Home, tytułu, krótkiego intro (np. że artykuły są pogrupowane po typie), a następnie od razu sekcji Guides, How-to, Reviews, Comparisons, Best. Najnowsze artykuły pozostają wyłącznie na stronie głównej (Newest articles).

### 2.3 Strona główna (index)

- **"All articles":** Może prowadzić do:
  - **A)** pierwszego huba z listy (np. `/hubs/ai-automation-agents/`), albo
  - **B)** nowej strony **indeksu hubów** (`/hubs/` lub `index.html` w `public/hubs/`) z listą linków do każdego huba.
- **"Newest articles":** Można zostawić z wszystkich produkcji albo tylko z pierwszego huba – zależnie od produktu.

Rekomendacja: na początek **A)** (link do pierwszego huba), żeby nie mnożyć stron; później łatwo dodać **B)**.

### 2.4 Artykuły per hub (filtrowanie)

- W **content_index** dodać funkcję np. `get_articles_for_hub(slug, articles_dir, config_path)`:
  - wywołuje `get_production_articles(...)`,
  - filtruje po `meta.get("category_slug") == slug` (albo po mapowaniu `category` → slug, jeśli w artykułach jest `category` a nie `category_slug`).
- W **render_site:** dla każdego huba z configu:
  - `articles_hub = get_articles_for_hub(slug, ...)`,
  - `_render_hub(hub_path, public, articles_hub, existing_slugs)`.
- **Linki z artykułu:** już są w formie `/hubs/{category_slug}/` – **upewnij się, że w frontmatter artykułów `category_slug` jest równy jednemu z `hubs[].slug`**. Wtedy linki nie będą 404.

### 2.5 generate_hubs.py

- **Wejście:** Lista hubów z configu (po slug + title).
- **Dla każdego huba:**
  - Pobierz artykuły dla tego huba (ta sama logika co w content_index: filtrowanie po `category_slug == slug`).
  - Wygeneruj treść (sekcje po content_type itd.) i zapisz **jeden plik**: `content/hubs/{slug}.md` (bez spacji/znaków w nazwie).
- **Zawartość huba:** Nie generować sekcji "Start here"; intro bez wzmianki o "Start here" ani "newest material". Po intro od razu sekcje po content_type (Guides, How-to, itd.).
- Usunąć stałe `HUB_SLUG` i `HUB_TITLE`; wszystko z configu.

### 2.6 Sitemap i indeks

- **generate_sitemap.py:** Zamiast jednego URL huba dodawać po jednym wpisie dla każdego huba z configu, np. `urls.append((f"/hubs/{slug}/", None))`.
- **Strona główna:** Link "All articles" → `/hubs/{pierwszy_slug}/` (albo w przyszłości `/hubs/`).

### 2.7 Ujednolicenie category_slug w artykułach

- Przejrzyj frontmatter w `content/articles/`: pole używane w linku to `category_slug` (albo `category` z normalizacją do slug).
- Wszystkie wartości powinny być **identyczne** z którymś z `hubs[].slug`. Np. jeśli hub ma `slug: ai-automation-agents`, to artykuły z tej kategorii powinny mieć `category_slug: ai-automation-agents` (nie "AI Automation & AI Agents").

---

## 3. Kolejność wdrożenia

1. **Config** – dodać `hubs: [{ slug, title }, ...]` w `config.yaml`; w `content_index.py` i gdzie potrzeba – wczytywać `hubs` (z fallbackiem na `production_category` jeśli brak `hubs`).
2. **content_index** – dodać `get_articles_for_hub(slug, ...)` filtrującą po `category_slug`.
3. **render_site** – pętla po `hubs`; dla każdego `slug`: ścieżka pliku `HUBS_DIR / f"{slug}.md"`, render do `public/hubs/{slug}/index.html`, przekazać `get_articles_for_hub(slug, ...)`; w `_update_index` użyć pierwszego huba (lub strony /hubs/) do linku "All articles".
4. **generate_hubs** – czytać listę hubów z configu; dla każdego generować `{slug}.md` z filtrowanymi artykułami.
5. **generate_sitemap** – dodawać URL dla każdego huba z listy.
6. **Artykuły** – ujednolicić `category_slug` w frontmatter z `hubs[].slug` (ręcznie lub skryptem).

---

## 4. Pliki do zmiany

| Plik | Zmiany |
|------|--------|
| `content/config.yaml` | Dodać `hubs: [{ slug, title }, ...]`. |
| `scripts/content_index.py` | `load_config`: obsługa `hubs`; nowa funkcja `get_articles_for_hub(slug, ...)`. |
| `scripts/render_site.py` | Pętla po hubach, ścieżka `{slug}.md`, filtrowane artykuły; `_update_index`: link do pierwszego huba (lub /hubs/). |
| `scripts/generate_hubs.py` | Lista hubów z configu; generowanie `{slug}.md` per hub; filtrowanie po `category_slug`; bez sekcji "Start here", intro bez wzmianki o "Start here"/"newest material". |
| `scripts/generate_sitemap.py` | Dodawanie wszystkich `/hubs/{slug}/` do sitemap. |
| Artykuły w `content/articles/` | Ujednolicić `category_slug` z slugami hubów. |

Dzięki temu strona będzie miała **więcej niż jeden hub**, spójne URL-e (`/hubs/{slug}/`), poprawne linki z artykułów i pełną sitemapę.
