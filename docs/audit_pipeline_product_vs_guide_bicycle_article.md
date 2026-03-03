# Audyt pipeline: artykuł produktowy vs stary typ (guide)

## Cel audytu

Artykuł  
`public/articles/2026-03-01-guide-to-best-practices-for-scaling-unique-bicycle-identification-systems-to-ensure-reliability-in-small-marketing-campaigns.audience_professional`  
miał być wygenerowany ścieżką **produktową** (typ treści: sales, product-comparison, best-in-category, category-products) – angielski, ton konwersacyjny, kontekstowe H2, tabela porównawcza (gdzie wymagana), porównanie kosztów, CTA w dwóch elementach. Zamiast tego otrzymał **strukturę i treść starego pipeline’u** (guide: Decision rules, Tradeoffs, Template 1/2, Try it yourself). W dokumencie: pełny audyt kroków pipeline’u, analiza wyniku, przyczyna, rekomendacje wariantów (bez implementacji).

---

## 1. Przepływ pipeline’u (od konfiguracji do /public)

### 1.1 Konfiguracja (content/config.yaml)

- **production_category:** `marketplaces-products`
- **hub_slug / hub_title:** marketplaces-products, "Marketplaces & Popular Physical Products"
- **sandbox_categories:** m.in. `RFID bike stickers and Bicycle Theft Marking`
- **suggested_problems:** `Lack of Unique Bicycle Identification`
- **category_mode:** `preserve_sandbox`

Konfiguracja jest nastawiona na hub produktowy i temat rowerowy; nie określa jednak **typów treści** – te wybierane są w Flowtaro Monitor przy uruchomieniu „Generuj use case'y”.

### 1.2 Generowanie use case’ów (generate_use_cases.py)

- **Wejście:** istniejące use_cases.yaml, kategorie z configu, **allowed_content_types** z argumentów CLI (w Monitorze: ptaszkowanie „Typ treści” → `--content-type sales --content-type product-comparison` itd.).
- **Działanie:** API dostaje instrukcję, że `suggested_content_type` ma być **wyłącznie** z listy `allowed_content_types`. Dla każdego zwróconego pomysłu: jeśli `suggested_content_type` ∉ allowed → ustawiane jest **`guide`** (fallback).
- **Wyjście:** dopisanie wpisów do `content/use_cases.yaml` z polami: problem, suggested_content_type, category_slug, audience_type, batch_id, status.

**Kluczowe:** Typ treści artykułu jest **zablokowany** w tym kroku – w use_cases.yaml zapisuje się **suggested_content_type**. Kolejne kroki tylko go przepisują.

### 1.3 Uzupełnienie kolejki (generate_queue.py)

- **Wejście:** use_cases.yaml (status todo lub brak statusu → trafia do kolejki).
- **Działanie:** Dla każdego use case’a: `content_type` wpisu kolejki = **uc["suggested_content_type"]**. Tytuł z `title_for_entry(problem, content_type)`. Dla typów produktowych bez `lang` w use case → wpis dostaje `lang: "en"`.
- **Wyjście:** `content/queue.yaml` – lista wpisów z title, primary_keyword, **content_type**, category_slug, tools, status, last_updated, audience_type, batch_id, opcjonalnie lang.

**Brak filtra:** generate_queue **nie** filtruje po content_type; bierze wszystkie use case’y z odpowiednim statusem. To, czy w kolejce jest „guide” czy „best-in-category”, zależy **wyłącznie** od `suggested_content_type` w use_cases.yaml.

### 1.4 Generowanie szkieletów (generate_articles.py)

- **Wejście:** queue.yaml, config (category_mode, production_category, allowed_categories), szablony z `templates/{content_type}.md`.
- **Działanie:** Dla każdego wpisu kolejki: `content_type = normalize_content_type(item["content_type"])` → wybór szablonu **`templates/{content_type}.md`**. Np. `content_type: "guide"` → `templates/guide.md` (playbook: Decision rules, Tradeoffs, SOP checklist, Template 1/2, Try it yourself). Dla `best-in-category` → `templates/best-in-category.md` (produktowy).
- **Wyjście:** pliki w `content/articles/` z frontmatterem (title, content_type, category, primary_keyword, tools, last_updated, status draft, audience_type, batch_id, opcjonalnie lang) i treścią z szablonu (placeholderowe sekcje).

**Wniosek:** Jeśli w kolejce jest `content_type: "guide"`, szkielet **zawsze** pochodzi z `guide.md` – pełna struktura starego pipeline’u.

### 1.5 Wypełnianie treści (fill_articles.py)

- **Wejście:** plik .md z content/articles (frontmatter + body).
- **Działanie:** Odczyt `meta["content_type"]`.  
  - Jeśli `content_type` ∈ PRODUCT_CONTENT_TYPES (sales, product-comparison, best-in-category, category-products) → **`_build_product_md_prompt`** / **`_build_product_html_prompt`** (język EN, ton konwersacyjny, kontekstowe H2, bez Decision rules/Template 1/2/Try it yourself, tabela/CTA/cost comparison).  
  - W przeciwnym razie → **`build_prompt`** (playbook: Decision rules, Tradeoffs, Failure modes, SOP checklist, Template 1, Template 2, Try it yourself).
- **Wyjście:** zaktualizowany body (oraz status filled), zapis w content/articles.

**Wniosek:** Dla `content_type: "guide"` używany jest **stary** zestaw instrukcji i kontrakt QA (playbook). Krok fill **nie** nadpisuje content_type na podstawie kategorii ani konfiguracji.

### 1.6 Render do public (render_site / budowa HTML)

- **Wejście:** content/articles (md lub html), szablony strony, config hubów.
- **Działanie:** Generowanie stron w `public/articles/<stem>/index.html` itd. Bez zmiany struktury treści – tylko opakowanie w layout.

**Podsumowanie łańcucha:**  
Config → **use_cases (suggested_content_type)** → queue (content_type) → generate_articles (wybór szablonu) → fill_articles (wybór promptu/QA) → render.  
**Jedyna źródłowa informacja o typie treści** w całym pipeline’e to **suggested_content_type** w use_cases.yaml.

---

## 2. Analiza artykułu problematycznego (bicycle, 2026-03-01)

### 2.1 Źródło w use_cases.yaml

W pliku `content/use_cases.yaml` wpis (batch 2026-03-01T003530):

```yaml
- problem: Best practices for scaling unique bicycle identification systems to ensure reliability in small marketing campaigns.
  suggested_content_type: guide
  category_slug: RFID bike stickers and Bicycle Theft Marking
  audience_type: professional
  batch_id: 2026-03-01T003530
  status: generated
```

**suggested_content_type = `guide`.** Żaden późniejszy krok tego nie zmienia.

### 2.2 Kolejka (queue.yaml)

Wpis odpowiadający temu artykułowi ma m.in.:

- **content_type: guide**
- category_slug: RFID bike stickers and Bicycle Theft Marking  
(category w artykule jest znormalizowana do marketplaces-products przy zapisie frontmatteru, zgodnie z configiem i allowed_categories).

### 2.3 Szablon i szkielet (content/articles/... .md)

- Użyty szablon: **guide** → `templates/guide.md`.
- Struktura: Introduction, What you need to know first, Main content (Decision rules, Tradeoffs, Failure modes, SOP checklist, Template 1, Template 2), Step-by-step workflow, Try it yourself, When NOT to use this, FAQ, CTA (placeholder), Disclosure, Pre-publish checklist.
- Plik po wygenerowaniu (i po fill) nadal zawiera te same nagłówki i placeholdery typu „### Decision rules:“, „### Template 1:“, „### Try it yourself: Build your own AI prompt” – czyli **pełna struktura starego pipeline’u**. Brak sekcji produktowych (What to look for, Comparison table, Cost comparison, CTA w dwóch zdaniach z linkiem).

### 2.4 Wypełnienie (fill_articles)

- Dla `content_type: "guide"` wywołany został **build_prompt** (playbook), nie _build_product_*.
- Model dostał instrukcje: Decision rules, Tradeoffs, Failure modes, SOP checklist, Template 1/2, Try it yourself, persona, defensible content rules.
- Kontrakt QA (check_output_contract) wymagał markerów playbookowych, **nie** wymagał tabeli porównawczej ani CTA w dwóch elementach ani cost comparison.

W pliku .md artykułu w content/articles widać nadal szkielet z pustymi/placeholderowymi sekcjami (Decision rules, Tradeoffs, Template 1, Template 2, Try it yourself) – czyli fill albo nie został uruchomiony dla tego pliku, albo zapisano wersję przed fill. W public może być wersja z fill (HTML). Istotne: **decyzja o typie była już wcześniej** – content_type = guide → szablon i prompt są stare.

### 2.5 Public (wyrenderowany wynik)

- Ścieżka: `public/articles/2026-03-01-guide-to-best-practices-for-scaling-unique-bicycle-identification-systems-to-ensure-reliability-in-small-marketing-campaigns.audience_professional/`.
- Jeśli renderowano z tego samego .md (guide), wynik wizualny będzie zgodny ze starym typem (nagłówki typu Decision rules, Tradeoffs, Template 1/2, Try it yourself itd.), bez tabeli porównawczej i bez produktowego CTA.

---

## 3. Porównanie ze standardowym pipeline’em (stary typ)

### 3.1 Artykuł referencyjny (stary pipeline)

- **Plik:** `public/articles/2026-02-26-guide-to-how-to-monitor-ai-agents-for-security-vulnerabilities-in-marketing-automation.audience_intermediate/index.html`
- **Źródło:** use case z **suggested_content_type: guide** (lub how-to), queue z **content_type: guide**, szablon **guide.md**, fill przez **build_prompt** (playbook).
- **Struktura:** Introduction, What you need to know first, Decision rules, Tradeoffs, Failure modes, SOP checklist, Template 1, Template 2, Try it yourself (Prompt #1, Prompt #2), When NOT to use this, FAQ, Internal links, List of platforms and tools, Disclosure.
- **Ton:** dokumentacyjny / B2B, „Before diving into…”, checklisty, szablony do wklejenia.

### 3.2 Artykuł rowerowy (2026-03-01)

- **Oczekiwanie:** produktowy (best-in-category lub inny z zestawu sales/product-comparison/best-in-category/category-products) – angielski, konwersacyjny, H2 kontekstowe, tabela porównawcza (dla best-in-category/product-comparison), Cost comparison, CTA (zdanie angażujące + zdanie z linkiem).
- **Faktycznie:** cały łańcuch oparty na **content_type: guide** → ten sam rodzaj szablonu i promptu co artykuł referencyjny (monitor AI agents). Struktura i typ treści są **zgodne ze starym pipeline’em**, a nie z produktowym.

---

## 4. Dlaczego ten artykuł dostał treść i strukturę starego pipeline’u?

**Bezpośrednia przyczyna:** W pliku `content/use_cases.yaml` dla pomysłu „Best practices for scaling unique bicycle identification systems to ensure reliability in small marketing campaigns.” zapisano **suggested_content_type: guide**. Na tej wartości opiera się queue → generate_articles (szablon) → fill_articles (prompt i QA). Skoro typ to „guide”, w całym pipeline’ie używany jest stary zestaw (guide.md + build_prompt + kontrakt playbook).

**Możliwe przyczyny po stronie procesu:**

1. **Uruchomienie „Generuj use case'y” z innym zestawem typów**  
   Jeśli przy generowaniu batcha 2026-03-01T003530 w Monitorze były zaznaczone np. „wszystkie” lub typy guide / how-to / best / comparison (a nie tylko sales, product-comparison, best-in-category, category-products), model mógł przypisać temu problemowi „guide” lub „best”, a fallback w skrypcie (gdy typ nie z listy) to „guide”.

2. **Fallback w generate_use_cases**  
   Gdy API zwróci typ **spoza** `allowed_content_types`, skrypt ustawia `suggested_content_type = "guide"`. Jeśli więc przy uruchomieniu z samymi typami produktowymi model i tak zwrócił „guide”, po walidacji zapisano „guide”.

3. **Brak mapowania kategoria → typ**  
   Pipeline **nigdzie** nie ustawia content_type na podstawie category_slug (np. „RFID bike stickers…” czy „marketplaces-products”). Nawet przy hubie produktowym typ treści pochodzi wyłącznie z use case’a. Ptaszkowanie typów w Monitorze ogranicza **dozwolone** typy przy generowaniu use case’ów; nie zmienia istniejących wpisów ani nie wymusza „dla tej kategorii zawsze produktowy”.

**Wniosek:** Artykuł ma strukturę i treść starego pipeline’u, bo **w źródle danych (use_cases.yaml) dla tego pomysłu jest suggested_content_type: guide**, a cały pipeline konsekwentnie używa tej wartości bez nadpisywania jej na podstawie kategorii czy konfiguracji.

---

## 5. Rekomendacje – warianty zmian

### Wariant A: Wymuszenie typów produktowych przy generowaniu use case’ów (tylko product)

- **Opis:** Przy uruchomieniu „Generuj use case'y” z zaznaczonymi **tylko** typami produktowymi (sales, product-comparison, best-in-category, category-products) w generate_use_cases: (1) w prompcie do API wyraźnie wymagać, że **każdy** use case musi dostać jeden z tych czterech typów; (2) w fallbacku, gdy API zwróci typ spoza listy, **nie** ustawiać „guide”, tylko np. pierwszy z listy allowed (np. „best-in-category”) lub losowy z allowed.
- **Za:** Nie zmienia się struktury plików; zmniejsza ryzyko zapisania „guide” przy intencji „tylko produkt”.
- **Przeciw:** Nie naprawia już istniejących wpisów z guide; jeśli model uparcie zwraca guide, i tak trzeba go poprawiać ręcznie lub w batchu.

### Wariant B: Mapowanie kategoria → content_type przy budowaniu kolejki

- **Opis:** W generate_queue: jeśli category_slug (lub category po normalizacji) należy do zbioru „kategorii produktowych” (np. z configu: `product_categories: [marketplaces-products, "RFID bike stickers and Bicycle Theft Marking"]`), nadpisać `content_type` wpisu kolejki na wybrany typ produktowy (np. „best-in-category” lub „category-products”), niezależnie od suggested_content_type.
- **Za:** Artykuły z kategorii „produktowych” zawsze idą ścieżką produktową (szablon + fill + QA). Nie trzeba zmieniać use_cases.yaml po fakcie.
- **Przeciw:** Rozjechanie się use_cases.yaml (nadal guide) i queue (best-in-category) – mniej spójności; przy zmianie kategorii później logika „produktowa” zależy od konfiguracji; możliwe konflikty, jeśli kiedyś ten sam use case trafi do wielu kategorii.

### Wariant C: Mapowanie kategoria → content_type w generate_articles (przy wyborze szablonu)

- **Opis:** W generate_articles przy wyborze szablonu: jeśli category (po normalizacji) ∈ product_categories z configu, użyć szablonu produktowego (np. best-in-category) i **w frontmatterze** zapisać content_type produktowy, nawet gdy w queue jest guide.
- **Za:** Bez zmiany queue i use_cases; artykuły z „kategorii produktowych” dostają szablon i (po fill) prompt produktowy (bo fill czyta content_type z frontmatteru).
- **Przeciw:** Dwa źródła prawdy (queue vs frontmatter); queue i use_cases dalej mówią „guide”; możliwe zamieszanie przy ponownym generowaniu z kolejki.

### Wariant D: Ręczna / batchowa korekta suggested_content_type w use_cases.yaml

- **Opis:** Dla istniejących (i ewentualnie przyszłych) pomysłów z kategorii „produktowych” ustawiać w use_cases.yaml `suggested_content_type` na jeden z typów produktowych (np. best-in-category). Monitor już pozwala edytować use case (w tym typ). Opcjonalnie: skrypt lub akcja w Monitorze „Ustaw typ na produktowy dla kategorii X”.
- **Za:** Jedna spójna źródłowa prawda; cały pipeline (queue → generate_articles → fill) działa bez dodatkowych reguł nadpisywania.
- **Przeciw:** Wymaga świadomej pracy po każdym wygenerowaniu use case’ów lub po batchu; łatwo zapomnieć; nie rozwiązuje automatycznie przypadku „model zwrócił guide mimo ograniczenia do product”.

### Wariant E: Rozszerzenie konfiguracji + nadpisanie w dwóch miejscach

- **Opis:** W config dodać np. `product_categories: [marketplaces-products, "RFID bike stickers and Bicycle Theft Marking"]`. (1) W generate_use_cases: jeśli kategoria use case’a ∈ product_categories i zwrócony typ ∉ product types → zamienić na domyślny typ produktowy. (2) W generate_queue lub generate_articles: jeśli category ∈ product_categories a content_type ∉ product types → nadpisać content_type na domyślny produktowy.
- **Za:** Zachowanie spójności „kategoria produktowa ⇒ zawsze produktowy typ” nawet przy błędzie modelu lub starych danych.
- **Przeciw:** Więcej logiki i konfiguracji; możliwość nadpisywania intencji użytkownika (np. celowo „guide” w kategorii produktowej).

---

## 6. Podsumowanie

- Pipeline od configu do public jest **w pełni sterowany** przez **suggested_content_type** w use_cases.yaml (→ content_type w queue → szablon → prompt i QA w fill).
- Artykuł rowerowy 2026-03-01 ma strukturę i treść starego pipeline’u, ponieważ w use_cases.yaml dla tego pomysłu jest **suggested_content_type: guide**. Ptaszkowanie typów w Monitorze ogranicza tylko to, jakie typy są **dozwolone** przy generowaniu nowych use case’ów; nie zmienia ani istniejących wpisów, ani nie wymusza typów produktowych dla konkretnej kategorii.
- Rekomendowane kierunki: **A** (mocniejsza kontrola przy generowaniu use case’ów + sensowny fallback) i/lub **D** (korekta w use_cases + ewentualnie narzędzie w Monitorze). **B/C/E** dają automatyczne „kategoria produktowa ⇒ typ produktowy” kosztem dodatkowej logiki i możliwej rozbieżności między use_cases a queue/frontmatter.

Po wyborze wariantu (albo kombinacji) można zaplanować konkretne zmiany w kodzie i procedurach. Niczego nie kodowano w ramach tego audytu.
