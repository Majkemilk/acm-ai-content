# Audyt: `public/hubs/ai-marketing-automation/index.html` w kontekście olinkowania

## 1. Co jest w tym pliku

- Strona huba: tytuł „AI Marketing Automation Tools & Workflows”, intro (ze starą wzmianką „Start here”), sekcja „Start here” (5 kart), potem Guides / How-to / Reviews / Comparisons / Best.
- Linki **z** tej strony: Home (`/`), wiele linków do `/articles/{slug}/`.
- Struktura i treść odpowiadają staremu outputowi (przed usunięciem „Start here” i zmianą intro w `generate_hubs.py`).

---

## 2. Kto linkuje **do** tej strony

| Źródło | URL docelowy | Czy trafia do `ai-marketing-automation`? |
|--------|----------------|------------------------------------------|
| **Strona główna** (`public/index.html`) | `/hubs/AI Automation & AI Agents/` | **Nie** – inny segment URL. |
| **Sitemap** (`public/sitemap.xml`) | `/hubs/{production_category}/` = `/hubs/AI Automation & AI Agents/` | **Nie** – inny segment. |
| **Artykuły** (badge kategorii w `render_site.py`) | `/hubs/{category_slug}/` | **Tak** – w artykułach jest `category` / `category_slug`: `ai-marketing-automation`, więc link to `/hubs/ai-marketing-automation/`. |

W efekcie **strona jest używana**: wszystkie obecne artykuły w `content/articles` mają `category: "ai-marketing-automation"`, więc badge kategorii prowadzi właśnie do `public/hubs/ai-marketing-automation/`.

---

## 3. Kto **generuje** ten plik

- **`render_site.py`** renderuje **tylko jeden** hub:  
  `hub_path = HUBS_DIR / f"{production_category}.md"`  
  przy `production_category: "AI Automation & AI Agents"` → plik `content/hubs/AI Automation & AI Agents.md` → wynik w **`public/hubs/AI Automation & AI Agents/index.html`** (slug z `path.stem`).
- **`public/hubs/ai-marketing-automation/`** **nie** jest tworzony przez obecny pipeline. To najpewniej pozostałość po starej konfiguracji (np. gdy `production_category` było `ai-marketing-automation`) lub po ręcznej budowie.
- **`generate_hubs.py`** zapisuje do `content/hubs/{production_category}.md`, czyli obecnie do `AI Automation & AI Agents.md`, a nie do `ai-marketing-automation.md`.

Wniosek: **strona jest używana (linki z artykułów), ale nie jest już generowana** – nie ma jej w aktualnym pipeline’ie, więc treść jest przestarzała i nie będzie się odświeżać.

---

## 4. Niespójność olinkowania

- **Główna + sitemap:** jeden hub → `/hubs/AI Automation & AI Agents/`.
- **Artykuły:** drugi adres → `/hubs/ai-marketing-automation/`.
- Są więc **dwa fizyczne huby** w `public/hubs/`:
  - `AI Automation & AI Agents/index.html` – aktualnie budowany, linkowany z głównej i sitemapy.
  - `ai-marketing-automation/index.html` – niebudowany, linkowany tylko z artykułów, treść stara.

Użytkownik z głównej trafia na jeden hub, z artykułu na drugi; zawartość i struktura (np. „Start here”) mogą się różnić.

---

## 5. Czy ta strona jest potrzebna

- **Tak** – w obecnym stanie jest **potrzebna**, bo bez niej linki z badge’y w artykułach prowadziłyby na 404 (bo `category_slug` = `ai-marketing-automation`).
- **Ale** w dłuższej perspektywie lepiej **mieć jeden canonical hub** i spójne linkowanie (główna, sitemap, artykuły → ten sam URL).

---

## 6. Rekomendacje zmian

### A) Szybkie ujednolicenie (jedna „oficjalna” strona huba)

1. **Zdecydować jeden URL huba** używany wszędzie (główna, sitemap, badge w artykułach).
2. **Wariant 1 – zostawić URL z production_category (ze spacjami):**
   - W artykułach ustawić `category_slug` (lub mapowanie `category` → slug w renderze) na wartość równą `production_category`, np. `"AI Automation & AI Agents"`, żeby badge linkował do `/hubs/AI Automation & AI Agents/`.
   - Wtedy `public/hubs/ai-marketing-automation/` staje się **nieużywane**. Można je usunąć albo zostawić przekierowanie 301 do `/hubs/AI Automation & AI Agents/` (jeśli chcesz nie psuć starych linków).
3. **Wariant 2 – przejść na slug (rekomendacja z docu multi-hub):**
   - Wprowadzić w configu slug dla huba (np. `ai-marketing-automation`) i renderować hub do `public/hubs/ai-marketing-automation/index.html`.
   - Główna i sitemap niech linkują do `/hubs/ai-marketing-automation/`.
   - Artykuły już używają `category_slug: ai-marketing-automation` → bez zmian linki będą poprawne.
   - Wtedy **`public/hubs/AI Automation & AI Agents/`** można uznać za zbędne (albo przekierować do slugowej wersji), a **`public/hubs/ai-marketing-automation/`** stanie się jedyną, odświeżaną wersją huba.

### B) Co zrobić z `public/hubs/ai-marketing-automation/index.html`

- **Jeśli wybierzesz wariant 1 (URL = production_category):**  
  - albo **usunąć** katalog `public/hubs/ai-marketing-automation/` po zmianie linków w artykułach na `/hubs/AI Automation & AI Agents/`,  
  - albo zostawić tam **stronę przekierowującą** (meta refresh lub 301) do `/hubs/AI Automation & AI Agents/`.
- **Jeśli wybierzesz wariant 2 (slug w URL):**  
  - **zachować** ścieżkę `public/hubs/ai-marketing-automation/` jako docelową dla renderu i **zmienić pipeline**, żeby to właśnie tam zapisywał hub (na podstawie slug z configu), a nie do `public/hubs/AI Automation & AI Agents/`.  
  - Wtedy obecny plik w `ai-marketing-automation` będzie nadpisywany przy każdym `render_site` i przestanie być „sierotą”.

### C) Sitemap

- Obecnie w sitemap jest tylko `/hubs/AI Automation & AI Agents/`.
- Po ujednoliceniu: w sitemap powinien być **tylko ten jeden** URL huba, który jest canonical (albo wszystkie huby, gdy wejdzie w życie struktura multi-hub ze slugami).

---

## 7. Podsumowanie

| Pytanie | Odpowiedź |
|--------|-----------|
| Czy strona jest **używana**? | **Tak** – linkują do niej badge’e kategorii we wszystkich obecnych artykułach. |
| Czy jest **potrzebna**? | W obecnym stanie **tak** (bez niej te linki by nie działały). Długoterminowo lepiej **jeden** canonical hub. |
| Czy jest **aktualnie generowana**? | **Nie** – pipeline buduje tylko `public/hubs/AI Automation & AI Agents/index.html`. |
| Rekomendacja | **Ujednolicić** linkowanie na jeden URL huba (slug w URL + render do `public/hubs/ai-marketing-automation/` albo zmiana linków w artykułach na obecny hub), a drugi katalog huba usunąć lub przekierować; sitemap i główna niech wskazują ten sam URL co artykuły. |
