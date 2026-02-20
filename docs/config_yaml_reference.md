# Znaczenie pól w `content/config.yaml`

## production_category

**Co to jest:** Nazwa **pliku** huba (bez `.md`) w `content/hubs/`. Używana wyłącznie do **wyboru pliku źródłowego** huba.

**Gdzie jest używane:**

| Miejsce | Znaczenie |
|--------|-----------|
| **render_site.py** | `hub_path = content/hubs/{production_category}.md` – z tego pliku czyta treść huba i renderuje ją do `public/hubs/{hub_slug}/index.html`. |
| **generate_hubs.py** | Zapisuje wygenerowany hub do `content/hubs/{production_category}.md`. |
| **generate_use_cases.py** | `get_categories_from_config()` zwraca listę kategorii: **pierwszy element** to `production_category`, potem `sandbox_categories`. Ta lista to dozwolone wartości `category_slug` przy generowaniu use case’ów (i przy `--category`). |

**Odniesienia:**

- **Plik huba:** musi istnieć `content/hubs/{production_category}.md` (np. `AI Automation & AI Agents.md` albo `ai-marketing-automation.md`).
- **Nazwa może być dowolna** (ze spacjami, znakami), bo to tylko nazwa pliku. Nie wpływa na URL strony – za URL odpowiada `hub_slug`.

**Czy powinno być „AI Marketing Automation” czy „AI Automation & AI Agents”?**

- Obecnie w `content/hubs/` masz dwa pliki: `AI Automation & AI Agents.md` i `ai-marketing-automation.md`.
- W configu masz `production_category: "AI Automation & AI Agents"` – więc używany jest plik **`AI Automation & AI Agents.md`**.
- Jeśli wrócisz do wcześniejszego ustawienia, np. `production_category: "ai-marketing-automation"`, wtedy używany będzie plik **`ai-marketing-automation.md`** (i dalej wszystko działa przez `hub_slug` jak teraz).

Ważne: **wartość musi dokładnie odpowiadać nazwie pliku** (bez `.md`). Nie ma w systemie osobnej nazwy „AI Marketing Automation” – są tylko te dwie nazwy plików. Wybór zależy od tego, który plik huba chcesz traktować jako główny (ten, który jest generowany przez `generate_hubs.py` i wyświetlany pod `/hubs/ai-marketing-automation/`).

---

## hub_slug

**Co to jest:** **Slug URL** huba – używany w adresie strony i w linkach. Zawsze w formie „slug” (małe litery, myślniki, bez spacji).

**Gdzie jest używane:**

| Miejsce | Znaczenie |
|--------|-----------|
| **render_site.py** | Zapis rendered huba do `public/hubs/{hub_slug}/index.html`. Link „All articles” na stronie głównej prowadzi do `/hubs/{hub_slug}/`. |
| **generate_sitemap.py** | W sitemapie jest wpis `/hubs/{hub_slug}/`. |
| **Artykuły** | Badge kategorii linkuje do `/hubs/{category_slug}/`. Aby linki działały, w frontmatter artykułów pole `category` / `category_slug` powinno być **zgodne ze slugiem huba** – u Ciebie `ai-marketing-automation`. |

**Odniesienia:**

- **URL huba:** `https://twoja-domena/hubs/ai-marketing-automation/`.
- **Katalog w public:** `public/hubs/ai-marketing-automation/index.html`.
- **Spójność z artykułami:** artykuły z `category: "ai-marketing-automation"` linkują do tego samego URL – wtedy główna, sitemap i artykuły wskazują jeden hub.

**Nie zmieniaj** `hub_slug` na wartość ze spacjami – URL ma być czytelny i stabilny (slug).

---

## sandbox_categories

**Co to jest:** Lista **nazw kategorii** używanych tylko do **generowania use case’ów** – model może przypisywać nowe use case’y do tych kategorii (obok `production_category`).

**Gdzie jest używane:**

| Miejsce | Znaczenie |
|--------|-----------|
| **generate_use_cases.py** | `get_categories_from_config()` zwraca `[production_category] + sandbox_categories`. Te wartości są „allowed category_slug” w promptcie i przy walidacji odpowiedzi API. Flaga `--category` musi wskazać jedną z tych kategorii. |

**Odniesienia:**

- **use_cases.yaml:** wygenerowane use case’y mogą mieć `category_slug` równy np. `"LLM SEO"` lub `"Visual automation and integrations"`.
- **queue.yaml / artykuły:** wpisy z kolejki i artykuły mogą mieć `category` / `category_slug` z tej listy.
- **Render i hub:** obecnie **wszystkie** nie-blocked artykuły trafiają do jednego huba (ten z `production_category` → `hub_slug`). Skrypt `get_production_articles()` **nie** filtruje po kategorii – więc sandbox nie oznacza „ukrytych” artykułów; to tylko lista dozwolonych kategorii przy generowaniu use case’ów. (Ewentualne rozdzielenie hubów per kategoria to docelowa struktura multi-hub z `docs/recommendation_multi_hub_structure.md`.)

---

## Podsumowanie

| Pole | Rola | Odniesienie w systemie |
|------|------|-------------------------|
| **production_category** | Nazwa pliku huba w `content/hubs/` (z rozszerzeniem .md). | `content/hubs/{production_category}.md` – źródło treści; generate_hubs zapisuje tu hub; pierwsza kategoria na liście w generate_use_cases. |
| **hub_slug** | Slug URL huba (adres strony). | `public/hubs/{hub_slug}/index.html`; link „All articles” i sitemap; artykuły powinny mieć `category_slug` = hub_slug, żeby linki z badge’a były poprawne. |
| **sandbox_categories** | Dodatkowe dozwolone kategorie przy generowaniu use case’ów. | Tylko w generate_use_cases (lista kategorii dla API i `--category`); nie zmienia tego, które artykuły są renderowane. |

**Obecna konfiguracja:**

- `production_category: "AI Automation & AI Agents"` → używany plik **`content/hubs/AI Automation & AI Agents.md`**.
- `hub_slug: "ai-marketing-automation"` → strona huba pod **`/hubs/ai-marketing-automation/`**.
- Artykuły z `category: "ai-marketing-automation"` linkują do tego samego URL.

Jeśli wcześniej miałeś „AI Marketing Automation”, mogło chodzić o tytuł huba (np. w pliku .md), a nie o wartość w configu. W configu sens ma albo **nazwa pliku** (`production_category`), albo **slug** – przy jednym hubie i pliku `ai-marketing-automation.md` możesz ustawić `production_category: "ai-marketing-automation"` i wtedy jedna nazwa służy i plikowi, i (jeśli zechcesz) spójności z artykułami; `hub_slug` i tak pozostaje `ai-marketing-automation` dla URL.
