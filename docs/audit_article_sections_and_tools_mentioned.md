# Audyt: sekcje artykułów i „List of AI tools mentioned”

## Porównanie dwóch artykułów

| Aspekt | 2026-02-20 (beginner) | 2026-02-22 (intermediate) |
|--------|----------------------|----------------------------|
| Plik | `...personalize-video-marketing-content.audience_beginner.md` | `...monitor-downtime-and-performance-issues....audience_intermediate.md` |
| Stan | **Szkielet** (puste placeholdery `[...]`, brak wypełnionej treści) | **Wypełniony** (pełna treść w Introduction, Main content, FAQ itd.) |
| Nagłówki H2 | Verification policy, Introduction, What you need to know first, Main content, Step-by-step workflow, When NOT to use this, FAQ, **Tools mentioned**, Internal links, CTA, Disclosure, Pre-publish checklist | **Te same** |
| Sekcja „Tools mentioned” | `## Tools mentioned` + `- {{TOOLS_MENTIONED}}` | `## Tools mentioned` + `- {{TOOLS_MENTIONED}}` |
| Treść „Tools mentioned” | Placeholder `{{TOOLS_MENTIONED}}` | Placeholder `{{TOOLS_MENTIONED}}` (nie zastąpiony) |

**Wniosek:** Oba artykuły mają **tę samą strukturę H2**. Artykuł z 22.02 **ma** sekcję „Tools mentioned”; brakuje w niej **treści** (lista narzędzi), bo pozostaje placeholder `{{TOOLS_MENTIONED}}`. Tytuł „List of AI tools mentioned in this article” występuje tylko w promptcie dla **HTML** (fill_articles, tryb `--html`); w szablonie markdown i we wszystkich artykułach .md używana jest nazwa **„Tools mentioned”**.

---

## Jakich sekcji „brakuje”?

- **„List of AI tools mentioned in this article”** – w .md **nie ma** takiego nagłówka; w szablonie jest **„Tools mentioned”**. Treść tej sekcji to zawsze `- {{TOOLS_MENTIONED}}`, czyli placeholder.
- **Żadne inne sekcje H2 nie znikają** w artykułach z 22.02: Verification policy, Introduction, What you need to know first, Main content (z Decision rules, Tradeoffs, Failure modes, SOP checklist, Template 1, Template 2), Step-by-step workflow, When NOT to use this, FAQ, Tools mentioned, Internal links, CTA, Disclosure, Pre-publish checklist – wszystkie są obecne w obu plikach.

Rzeczywisty problem to więc **pusta treść sekcji „Tools mentioned”** (placeholder nie jest zastępowany listą narzędzi), a nie brak sekcji ani inna struktura artykułów z 22.02.

---

## Dlaczego artykuły z 22.02 (i inne) nie mają „pełnej” sekcji narzędzi?

1. **Kolejka nie ma pola `tools_mentioned`**  
   W `generate_queue.py` wpisy mają `primary_tool`, `secondary_tool`, ale **nie** `tools_mentioned`. To pole w ogóle nie jest ustawiane.

2. **generate_articles.py**  
   Przy generowaniu .md z szablonu wywołuje `get_replacements(item, ...)`. Dla `TOOLS_MENTIONED` zwraca `item.get("tools_mentioned")` → **None**. W efekcie `replacements["{{TOOLS_MENTIONED}}"]` zostaje jako `"{{TOOLS_MENTIONED}}"` (placeholder zostaje w tekście).

3. **fill_articles.py**  
   Prompt wyraźnie każe **nie zmieniać** placeholderów mustache: *„Do not change any {{MUSTACHE}} placeholders (e.g. {{TOOLS_MENTIONED}}, …). Leave them exactly as-is.”* Model wypełnia tylko `[bracket]` placeholdery; sekcja „Tools mentioned” pozostaje z `- {{TOOLS_MENTIONED}}`.

4. **Brak późniejszego zastępowania**  
   Nigdzie w pipeline (generate_articles → fill_articles → render/update_affiliate_links) nie ma kroku, który podstawia pod `{{TOOLS_MENTIONED}}` gotową listę narzędzi (np. z `primary_tool` / `secondary_tool` lub z `affiliate_tools.yaml`).

Efekt: **wszystkie** artykuły .md (nie tylko z 22.02) mają sekcję „Tools mentioned”, ale jej treść to nie lista narzędzi, tylko niezmieniony placeholder.

---

## Propozycje naprawy

### 1. Zastępowanie `{{TOOLS_MENTIONED}}` przy generowaniu artykułu (zalecane)

**Gdzie:** `scripts/generate_articles.py`, w `get_replacements()` (lub pomocniczo przy budowaniu `replacements`).

**Co:** Jeśli `item.get("tools_mentioned")` jest puste, **wygenerować** listę z pól, które już są w kolejce:

- Zbudować listę nazw: `primary_tool`, `secondary_tool` (pominąć puste).
- Opcjonalnie załadować `affiliate_tools.yaml` i dla każdej nazwy dodać link (np. format: `- [Nazwa](url)`).
- Ustawić `replacements["{{TOOLS_MENTIONED}}"]` na tę listę (np. kilka linii markdown).

Dzięki temu już w momencie generowania .md sekcja „Tools mentioned” będzie miała realną treść (nazwy, ewentualnie linki), bez zmiany promptu fill_articles.

### 2. Spójna nazwa sekcji (opcjonalnie)

- W **szablonach** .md (np. `templates/how-to.md`) zmienić nagłówek z `## Tools mentioned` na `## List of AI tools mentioned in this article`, jeśli chcesz pełną spójność z promptem HTML i z oczekiwaniami redakcji.
- W **fill_articles** (prompt markdown) można dodać zdanie, że pod sekcją „Tools mentioned” (albo „List of AI tools…”) model **nie** wstawia treści – treść pochodzi z placeholderów (po implementacji p. 1).

### 3. Uzupełnienie kolejki o `tools_mentioned` (alternatywa do 1)

- W `generate_queue.py` przy budowaniu wpisu (gdy mamy `primary_tool`, `secondary_tool`) budować też pole `tools_mentioned` (np. jedna linia markdown: „- Tool1, Tool2” lub lista bullet).
- W `generate_articles.get_replacements()` używać `item.get("tools_mentioned")` – wtedy gdy kolejka będzie je ustawiać, placeholder zostanie zastąpiony bez zmiany logiki w generate_articles (poza ewentualnym fallbackiem jak w p. 1 gdy `tools_mentioned` nadal puste).

---

## Rekomendacja

- **Zaimplementować propozycję 1** w `generate_articles.py`: przy braku `tools_mentioned` w elemencie kolejki budować listę z `primary_tool` i `secondary_tool` (oraz opcjonalnie z `affiliate_tools.yaml` w formacie „- [Nazwa](url)”) i podstawiać pod `{{TOOLS_MENTIONED}}`.
- **Opcjonalnie** propozycja 2 (zmiana nagłówka na „List of AI tools mentioned in this article”) dla spójności z HTML i z opisem audytu.
- Propozycja 3 może być uzupełnieniem (kolejka ustawia `tools_mentioned`, a generate_articles tylko go używa lub robi fallback jak w 1).

Po wdrożeniu p. 1 nowe i odświeżane artykuły będą miały w sekcji „Tools mentioned” (lub „List of AI tools…”) faktyczną listę narzędzi zamiast samego placeholderu.

---

## Wdrożenie (propozycja 1)

Zaimplementowano:

- **scripts/generate_articles.py**
  - Dodano `AFFILIATE_TOOLS_PATH` oraz `_load_affiliate_tools_name_to_url()` (stdlib, bez zewnętrznych zależności) – ładuje słownik nazwa → `affiliate_link` z `content/affiliate_tools.yaml`.
  - Dodano `_build_tools_mentioned_from_queue_item(item, name_to_url)` – buduje listę bullet z `primary_tool` i `secondary_tool`; jeśli narzędzie jest w affiliate_tools, wstawiany jest link w formacie `- [Nazwa](url)`.
  - W `get_replacements()` dla `TOOLS_MENTIONED`: używana jest wartość z kolejki (`tools_mentioned`), jeśli jest; w przeciwnym razie używana jest lista zbudowana z `primary_tool` i `secondary_tool` (z linkami z affiliate_tools).
- **Szablony** (`templates/how-to.md`, `guide.md`, `best.md`, `comparison.md`): sekcja „Tools mentioned” ma teraz sam placeholder `{{TOOLS_MENTIONED}}` (bez prefiksu `- `), żeby podstawiana treść mogła być wieloliniową listą bullet (`- [Tool](url)` itd.) bez podwójnego myślnika.

Efekt: przy generowaniu artykułu z kolejki (gdy wpis ma `primary_tool` i/lub `secondary_tool`) sekcja „Tools mentioned” otrzymuje gotową listę narzędzi z linkami afiliacyjnymi. Istniejące artykuły z pustym placeholderem można uzupełnić przez ponowne wygenerowanie (np. backfill lub refresh) albo ręcznie.
