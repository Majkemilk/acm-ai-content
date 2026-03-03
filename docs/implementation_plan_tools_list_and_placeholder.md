# Plan wdrożenia: lista narzędzi = TOOLS_SELECTED + linki z body oraz {{TOOLS_MENTIONED}} w szkielecie

**Do akceptacji przed kodowaniem.**  
Data: 2026-03-01

---

## 1. Cel

1. **Ścieżka HTML (fill_articles):** Lista w sekcji „List of platforms and tools mentioned in this article” ma być złożona z **dwóch części**: (a) narzędzia z linii TOOLS_SELECTED z odpowiedzi modelu (w ich kolejności), (b) **plus** wszystkie pozostałe zlinkowane nazwy platform/narzędzi z treści artykułu (kolejność pierwszego wystąpienia w body), bez duplikatów.
2. **generate_articles:** W szablonie **nie** podstawiać `{{TOOLS_MENTIONED}}` na tekst „ToolA, ToolB”; zawsze zostawiać w szkielecie literal **`{{TOOLS_MENTIONED}}`**, żeby listę z linkami generował dopiero `fill_articles` na podstawie `meta["tools"]`.

---

## 2. Sens i logika

### 2.1 Łączenie TOOLS_SELECTED + linki z body (pkt 1)

- **TOOLS_SELECTED** = to, co model jawnie wskazał jako narzędzia do artykułu; kolejność ma znaczenie (np. pierwsze = główne).
- **Linki w body** = narzędzia faktycznie użyte w tekście (affiliate URL); mogą być dodatkowe względem TOOLS_SELECTED.
- **Obecne zachowanie:** Albo tylko linki z body, albo tylko TOOLS_SELECTED (fallback). Często traci się TOOLS_SELECTED, gdy model nie wstawił affiliate linków w tekście.
- **Nowe zachowanie:** Zawsze uwzględniamy TOOLS_SELECTED (jeśli są), a następnie uzupełniamy listę o wszystkie narzędzia wyłapane z linków w body, które jeszcze nie są na liście. Daje to:
  - pełną listę rekomendowaną przez model (TOOLS_SELECTED),
  - plus każde inne zlinkowane narzędzie z artykułu,
  - bez duplikatów i z czytelną kolejnością: najpierw intencja modelu, potem „reszta” z treści.

**Ograniczenia:**  
- TOOLS_SELECTED jest już obcinane do max 5 nazw (walidacja w `_extract_tools_selected`). Lista końcowa może być dłuższa (TOOLS_SELECTED + dodatkowe z body). Opcjonalnie można dodać limit łączny (np. 10) – do decyzji przy wdrożeniu.

### 2.2 Zostawienie {{TOOLS_MENTIONED}} w szkielecie (pkt 2)

- **Obecne zachowanie:** Gdy w kolejce jest pole `tools` (np. „ToolA, ToolB”), `generate_articles` wstawia w miejsce `{{TOOLS_MENTIONED}}` ten sam tekst. W `fill_articles` (MD) nie ma już mustache do podmiany, więc sekcja zostaje z „ToolA, ToolB” bez linków.
- **Proponowane:** W `generate_articles` **nigdy** nie podstawiać wartości za `{{TOOLS_MENTIONED}}` – traktować jak placeholder do wypełnienia później. W body szkieletu zawsze zostaje **`{{TOOLS_MENTIONED}}`**. Frontmatter dalej dostaje `tools` z kolejki (bez zmian w `build_frontmatter`), więc `fill_articles` ma w `meta["tools"]` listę narzędzi i może wygenerować listę MD z linkami przez `_build_tools_mentioned_md(tool_list, name_to_url)` i podstawić ją w miejsce `{{TOOLS_MENTIONED}}`.
- **Konsekwencje:** W ścieżce Markdown sekcja zawsze będzie miała prawidłową listę z linkami (o ile są w `affiliate_tools.yaml`), a nie surowy tekst „ToolA, ToolB”. Gdy `meta["tools"]` jest puste, `fill_articles` podstawi pustą listę – dopuszczalne.

---

## 3. Zakres zmian (bez kodu – tylko opis)

### 3.1 `scripts/fill_articles.py` (ścieżka HTML)

**Miejsce:** Blok „Środek G” (około linii 2571–2581), po `_extract_tools_selected` i ustawieniu `meta["tools"]`.

**Obecna logika (skrót):**
- `tool_list` z `meta["tools"]` (po split po przecinku).
- `tool_list_from_body = _extract_tool_names_from_body_html(new_body, url_to_name)`.
- Jeśli `tool_list_from_body` niepuste → **`tool_list = tool_list_from_body`** (nadpisanie).
- Potem `tools_html = _build_tools_mentioned_html(tool_list, ...)` i `_upsert_tools_section_html(...)`.

**Nowa logika:**
- Zachować wyciąganie **selected_tools** z `_extract_tools_selected` (już jest) oraz `tool_list_from_body = _extract_tool_names_from_body_html(...)`.
- **Składanie listy:**
  - Część 1: `tool_list = list(selected_tools)` (kolejność z TOOLS_SELECTED).
  - Część 2: dla każdego `name` z `tool_list_from_body`: jeśli `name` nie występuje jeszcze w `tool_list`, dopisać na koniec.
- Reszta bez zmian: `tools_html = _build_tools_mentioned_html(tool_list, toolinfo, ...)`, `_upsert_tools_section_html(new_body, tools_html)`.

**Uwaga:** `selected_tools` jest już zwracane przez `_extract_tools_selected`; trzeba użyć tej listy zamiast ponownego parsowania `meta["tools"]` do budowy „części 1”, żeby zachować kolejność i walidację (max 5 z TOOLS_SELECTED).

### 3.2 `scripts/generate_articles.py`

**Miejsce:** Funkcja `get_replacements` → obsługa zmiennej `TOOLS_MENTIONED` (około linii 618–619).

**Obecne zachowanie:**  
`if var == "TOOLS_MENTIONED": return ", ".join(tools_list) if tools_list else None`  
→ przy niepustej liście narzędzi z kolejki w body wstawiane jest „ToolA, ToolB”, a mustache znika.

**Nowe zachowanie:**  
Dla `var == "TOOLS_MENTIONED"` **zawsze** zwracać `None` (nigdy nie podstawiać listy narzędzi w body).  
Dzięki temu w pętli replacements dla `TOOLS_MENTIONED` wartość będzie „brak” i obowiązywać będzie istniejąca gałąź else: `replacements["{{TOOLS_MENTIONED}}"] = "{{TOOLS_MENTIONED}}"`, czyli w body szablonu pozostanie literal **`{{TOOLS_MENTIONED}}`**.

**Nie zmieniać:**  
- `build_frontmatter`: dalej `fm["tools"] = item.get("tools", "")` – frontmatter nadal dostaje narzędzia z kolejki, z których `fill_articles` zbuduje listę z linkami.
- `PRIMARY_TOOL` / `SECONDARY_TOOL`: można zostawić jak jest (podstawianie z kolejki) albo ewentualnie w przyszłości rozważyć spójność z listą – poza zakresem tego planu.

---

## 4. Weryfikacja po wdrożeniu

- **HTML:** Artykuł wypełniony z `--html`, w którym model podał TOOLS_SELECTED i w tekście wstawił linki do innych narzędzi z affiliate_tools → sekcja „List of platforms and tools” powinna zawierać najpierw narzędzia z TOOLS_SELECTED (w tej kolejności), potem pozostałe z linków w body, bez powtórzeń.
- **HTML:** Artykuł bez linków w body, ale z TOOLS_SELECTED → sekcja jak dziś: lista z TOOLS_SELECTED.
- **Markdown:** Szkielet wygenerowany z kolejki z polem `tools` → w pliku .md w sekcji „List of platforms and tools” ma być literal `{{TOOLS_MENTIONED}}` (bez „ToolA, ToolB”). Po uruchomieniu `fill_articles` (bez `--html`) w tym samym pliku w miejscu `{{TOOLS_MENTIONED}}` ma być lista w formacie `- [Name](url)` (dla nazw z affiliate_tools).

---

## 5. Podsumowanie

| # | Zadanie | Plik | Zmiana |
|---|--------|------|--------|
| 1 | Lista = TOOLS_SELECTED + linki z body (bez duplikatów) | `fill_articles.py` | W bloku HTML: budować `tool_list` jako `selected_tools` + uzupełnienie z `tool_list_from_body` (tylko nazwy jeszcze nieobecne). Nie nadpisywać całkowicie `tool_list` przez `tool_list_from_body`. |
| 2 | Zostawić `{{TOOLS_MENTIONED}}` w szkielecie | `generate_articles.py` | W `get_replacements` dla `TOOLS_MENTIONED` zawsze zwracać `None`, żeby w body pozostawał placeholder do podmiany w fill_articles. |

Po akceptacji tego planu można przejść do implementacji (konkretne zmiany w kodzie).
