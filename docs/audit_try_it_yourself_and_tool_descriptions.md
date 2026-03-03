# Audyt: sekcja „Try it yourself”, narzędzia i linki, opisy narzędzi

**Data:** 2026-02-20  
**Zakres:** Jakość merytoryczna i formalna sekcji „Try it yourself” oraz **zgodność narzędzi i linków z pełną treścią artykułu** (w tym sekcja „List of platforms and tools mentioned in this article”); środki zapobiegawcze na przyszłość; wykorzystanie pliku linków referencyjnych (opisy narzędzi).  
**Status:** Propozycja — **bez wdrożenia w kodzie** do momentu zatwierdzenia.

---

## 1. Cel audytu

1. **Wdrożenie globalnego rozwiązania** — środki zapobiegające w przyszłych generacjach i odświeżeniach:
   - podwójnej/zbędnej linii intro przed blokiem Prompt #2,
   - rozjazdom temat artykułu ↔ narzędzie w sekcji „Try it yourself”,
   - **rozbieżności między listą narzędzi na końcu artykułu a faktycznymi linkami/wystąpieniami w treści.**
2. **Sprawdzenie i poprawki wszystkich wygenerowanych artykułów** w zakresie:
   - **jedna linia intro** przed Prompt #2: wybranym narzędziem + „(AI tool)”;
   - usunięcie pierwszej, zbędnej linii (np. „…ready to use with your governance tool” lub wariantu z innym opisem/narzędziem);
   - **sekcja „List of platforms and tools mentioned in this article”:** tylko narzędzia, które **faktycznie występują** w treści (link lub nazwa w body).
3. **Pełen audyt jakości merytorycznej** w tym zakresie oraz **rola pliku linków referencyjnych** (`content/affiliate_tools.yaml`): opisy (`short_description_en`) — gdzie brakują, jak je dodać i jak API może z nich korzystać przy wstawianiu narzędzi i linków w tej sekcji i innych.

---

## 2. Wyniki audytu istniejących artykułów

### 2.1 Źródło danych

- Artykuły: pliki `.html` w `content/articles/` zawierające sekcję „Try it yourself”.
- Kryterium duplikatu: w sekcji „Try it yourself” występują **dwa lub więcej** akapitów (`<p>`) będących intro do Prompt #2 (np. „The AI returns the following output (Prompt #2)…”, „Below is the output (Prompt #2)…”), zanim pojawi się drugi blok `<pre>` (zawartość Prompt #2).

### 2.2 Przyczyna duplikatów w obecnym pipeline

- **Instrukcja dla modelu** (fill_articles): *„Do not add a separate intro sentence before the marker [PROMPT2_PLACEHOLDER].”* Mimo to model często generuje własną linijkę intro (np. „…ready to use with your governance tool” lub „…ready to use with Descript (AI-powered…)”).
- **Normalizacja HTML** (`_normalize_try_it_yourself_html`): usuwa tylko akapity zawierające **dokładnie** wzorzec z **„(AI tool)”** w środku. Akapity z innymi wariantami („your governance tool”, „Descript (AI-powered…)”, „Make (Visual automation…)”, „Canva”) **nie** są usuwane.
- **Efekt:** Przed drugim `<pre>` pozostają: (1) linia wygenerowana przez model (bez „(AI tool)” lub z innym opisem) + (2) linia wstrzykiwana przez system z „X (AI tool).” → **dwie linie intro**.

### 2.3 Lista artykułów z podwójną linią intro przed Prompt #2

Na podstawie przeszukania plików HTML (wzorce „output (Prompt #2)” / „following output (Prompt #2)” w sekcji Try it yourself) — pliki, w których w tej sekcji występują **dwa** takie akapity (czyli duplikat intro):

| # | Plik HTML |
|---|-----------|
| 1 | `2026-02-20-how-to-automate-video-thumbnails-creation-for-social-media.audience_beginner.html` |
| 2 | `2026-02-20-guide-to-leverage-ai-to-enhance-collaborative-video-editing-workflows.audience_professional.html` |
| 3 | `2026-02-22-how-to-integrate-multiple-ai-tools-for-advanced-customer-journey-mapping-analysis.audience_professional.html` |
| 4 | `2026-02-22-how-to-monitor-downtime-and-performance-issues-in-ai-marketing-tools-effectively.audience_intermediate.html` |
| 5 | `2026-02-22-how-to-use-ai-to-automate-the-creation-of-targeted-audience-profiles.audience_beginner.html` |
| 6 | `2026-02-23-guide-to-how-to-easily-set-up-ai-driven-customer-segmentation-without-advanced-technical-skills.audience_intermediate.html` |
| 7 | `2026-02-23-guide-to-how-to-monitor-and-troubleshoot-unexpected-behaviors-in-agentic-automation-processes.audience_intermediate.html` |
| 8 | `2026-02-23-guide-to-how-to-troubleshoot-unpredictable-responses-from-agentic-automations-during-campaigns.audience_professional.html` |
| 9 | `2026-02-23-guide-to-how-to-develop-troubleshooting-processes-for-unexpected-agentic-automation-failures.audience_professional.html` |
| 10 | `2026-02-23-how-to-how-to-effectively-train-ai-models-with-minimal-data-for-marketing-purposes.audience_beginner.html` |
| 11 | `2026-02-23-how-to-how-to-govern-and-ensure-reliability-in-complex-agentic-automation-systems.audience_professional.html` |
| 12 | `2026-02-23-how-to-implement-robust-ai-systems-for-real-time-error-monitoring-and-adjustments-in-marketing-automation-processes.audience_professional.html` |
| 13 | `2026-02-23-guide-to-automate-the-analysis-of-customer-behaviors-across-multiple-platforms-for-more-effective-ad-targeting.audience_intermediate.html` |
| 14 | `2026-02-23-how-to-create-a-unified-customer-profile-through-ai-tools-to-enhance-marketing-effectiveness.audience_intermediate.html` |

**Pozostałe** pliki HTML z sekcją „Try it yourself” mają w tej sekcji **jedną** linię intro przed Prompt #2 (stan poprawny lub do weryfikacji ręcznej przy innych problemach, np. rozjazd temat–narzędzie).

### 2.4 Inne problemy jakościowe (przykłady)

- **Rozjazd temat–narzędzie:** Artykuł o governance / agentic automation z Opus Clip w „Try it yourself” — treść Prompt #1/Prompt #2 dotyczy frameworku governance, a Opus Clip to narzędzie do wideo (dokument: `docs/analysis_try_it_yourself_governance_opus_clip.md`).
- **Niespójna nazwa/opis w dwóch liniach:** Np. pierwsza linia „ready to use with Descript (AI-powered…)”, druga „ready to use with Opus Clip (AI tool)” — mylące dla czytelnika.
- **Różne narzędzia w descriptorze vs treść:** Prompt #1/Prompt #2 merytorycznie pod inne narzędzie niż to wstawione w descriptorze (np. treść pod Make, descriptor pod Opus Clip).

### 2.5 Audyt uzupełniający: narzędzia i linki w pełnej treści artykułu

**Case study: artykuł o governance i niezawodności w systemach agentowych**

- **Plik:** `2026-02-23-how-to-how-to-govern-and-ensure-reliability-in-complex-agentic-automation-systems.audience_professional.html`  
  (odpowiednik w `public/articles/`: ten sam artykuł po publikacji.)

**Pełna treść artykułu — gdzie występują linki do narzędzi:**

| Miejsce w artykule | Narzędzie | Link / wystąpienie |
|--------------------|-----------|---------------------|
| Sekcja „Try it yourself” — descriptor Prompt #1 | **Opus Clip** | `<a href="https://www.opus.pro/?via=d9d7c5">Opus Clip</a> (AI tool)` |
| Sekcja „Try it yourself” — descriptor Prompt #2 | **Opus Clip** | `<a href="https://www.opus.pro/?via=d9d7c5">Opus Clip</a> (AI tool)` |
| Introduction, Decision rules, Tradeoffs, Failure modes, SOP, Templates, Step-by-step, FAQ, Internal links | **Make** | **brak** |
| Jak wyżej | **Descript** | **brak** |

**Sekcja na końcu: „List of platforms and tools mentioned in this article”:**

- Wylistowane są: **Opus Clip**, **Make**, **Descript** (z linkami i opisami).
- W **całej treści** artykułu (poza tą listą) link do narzędzia występuje **wyłącznie** przy **Opus Clip** (dwa razy w „Try it yourself”).
- **Make** i **Descript** w artykule w ogóle się nie pojawiają — ani w tekście, ani jako link.

**Wniosek:** Część linków podanych na końcu jako „występujące w artykule” **w treści artykułu nie występuje**. Czytelnik dostaje listę trzech narzędzi, z których tylko jedno jest faktycznie użyte/wylinkowane w body.

**Przyczyna w pipeline:**

- Lista w sekcji „List of platforms and tools mentioned in this article” jest budowana **nie** na podstawie skanowania treści artykułu, lecz z **frontmatter `tools`** (wartość z linii TOOLS_SELECTED zwracanej przez model przy generacji).
- W `fill_articles.py`: `tool_list = [n.strip() for n in tools_raw.split(",") ...]` z `meta["tools"]`; potem `_build_tools_mentioned_html(tool_list, toolinfo)` i `_upsert_tools_section_html(new_body, tools_html)` **nadpisują** sekcję listą **wszystkich** narzędzi z TOOLS_SELECTED.
- Model wybiera np. „Opus Clip, Make, Descript”, ale w wygenerowanym body linkuje tylko Opus Clip (w „Try it yourself”). Pipeline i tak wstawia na końcu listę wszystkich trzech — stąd rozbieżność.

---

## 3. Plik linków referencyjnych (`content/affiliate_tools.yaml`)

### 3.1 Stan opisów

- **Pole:** `short_description_en` (opcjonalne) — jednozdaniowy opis po angielsku; używany w promptach do generacji (lista narzędzi z formatem `Name=URL|description`).
- **Obecny stan:** Tylko **3 narzędzia** mają uzupełnione `short_description_en`: **Opus Clip**, **Make**, **UptimeRobot**. Pozostałe wpisy mają wyłącznie `name`, `category`, `affiliate_link`.
- **Skutek:** Dla większości narzędzi model dostaje tylko nazwę i URL; w promptach jest instrukcja „jeśli brak opisu po |, napisz factual one-sentence description”. W sekcji „Try it yourself” i „List of platforms and tools” opisy są więc często wymyślane przez model — co może prowadzić do niespójności i gorszego dopasowania narzędzia do tematu.

### 3.2 Jak dodać brakujące opisy

- **Format:** Dla każdego narzędzia, które ma być sensownie wybierane/wstawiane w artykułach, dodać (lub uzupełnić):
  - `short_description_en: "Jedno zdanie po angielsku: co robi narzędzie (np. AI short-form clips from long videos)."`
- **Źródła:** Strona produktu, dokumentacja, istniejące opisy w artykułach (jako baza do ujednolicenia). Można zacząć od narzędzi najczęściej wybieranych (np. z frontmatter `tools` w artykułach).
- **Priorytet:** Najpierw narzędzia z kategorii `referral` i te, które już występują w sekcjach „Try it yourself”, potem pozostałe według potrzeb redakcyjnych.

### 3.3 Jak API może inteligentnie korzystać z opisów

- **Obecnie:** W `fill_articles.py` lista narzędzi jest budowana z `_load_affiliate_tools()`; do promptu przekazywane są m.in. „Affiliate tools” i „Other tools” w formacie `Name=URL` lub `Name=URL|short_description_en`. Model wybiera narzędzia (TOOLS_SELECTED) i generuje treść; w sekcji „Try it yourself” wstawiany jest **pierwszy** wybrany tool z frontmatter (`tools`) jako nazwa w descriptorze.
- **Propozycja użycia opisów:**
  1. **W instrukcji generacji:** Jawnie podać modelowi, że w sekcji „Try it yourself” ma używać **wyłącznie** narzędzia z listy, które **merytorycznie pasuje** do tematu artykułu i do treści Prompt #1/Prompt #2; opisy z listy (gdy są) mają pomóc w wyborze dopasowanego narzędzia.
  2. **W promptach:** Nie zmieniać samego formatu descriptorów (jedna linia „X (AI tool).”), ale przy wyborze narzędzi do artykułu podawać w kontekście opisy, żeby model nie wybierał np. Opus Clip do artykułu o governance.
  3. **Opcjonalnie — logika po stronie kodu:** Jeśli w przyszłości pojawi się mapowanie use-case → preferowane narzędzie (np. reaktywacja/rozszerzenie pliku typu `use_case_tools_mapping.yaml`), można podawać do promptu „preferred tool for Try-it-yourself: X” na podstawie słów kluczowych / kategorii artykułu; opisy z YAML służyłyby wtedy także do weryfikacji spójności (np. QA: „czy primary_tool ma short_description_en pasujący do tematu?”).

---

## 4. Środki zapobiegawcze (globalne) — przyszłe generacje i odświeżenia

### 4.1 Jedna linia intro przed Prompt #2

| Środek | Opis | Za | Przeciw |
|--------|------|----|--------|
| **A. Rozszerzenie normalizacji HTML** | W `_normalize_try_it_yourself_html`: przed wstrzyknięciem jednej linii out_line usuwać **wszystkie** akapity `<p>`, które wyglądają jak intro do Prompt #2 (np. zawierają „output (Prompt #2)” lub „following output (Prompt #2)” lub „Below is the output (Prompt #2)” — **niezależnie** od tego, czy zawierają „(AI tool)”). Następnie wstrzyknąć dokładnie jedną linię z `_TRY_OUTPUT_VARIANTS` i prawidłową nazwą narzędzia. | Jednorazowa zmiana w jednej funkcji; eliminuje duplikaty przy każdym fill/refresh. | Trzeba doprecyzować regex tak, by nie usuwać innych sensownych zdań (np. w FAQ). Ograniczyć stosowanie do sekcji między H3 „Try it yourself” a następnym H2. |
| **B. Zaostrzenie instrukcji w prompcie** | Dodać w `_try_it_yourself_instruction` zdanie w stylu: „Do NOT write any sentence that introduces the output of Prompt #2 (e.g. 'The AI returns the following…' or 'Below is the output…'). Only output [PROMPT2_PLACEHOLDER]. The system will insert the single intro line automatically.” | Zmniejsza szansę, że model doda własną linię. | Model i tak może czasem dodać; bez rozszerzenia normalizacji (A) duplikaty mogą nadal występować. |
| **C. Sanityzacja po wstawieniu Prompt #2** | Po `_insert_prompt2` (przed normalizacją) przeszukać sekcję „Try it yourself” i usunąć dowolny `<p>` zawierający „output (Prompt #2)” lub „Below is the output (Prompt #2)” i **nie** zawierający wzorca „(AI tool)\.” (kanoniczna linia jest wstrzykiwana później). | Działa na już wygenerowanym HTML; uzupełnia (A). | Wymaga ostrożnego regexu (tylko sekcja Try it yourself). |

**Rekomendacja:** Wdrożyć **A + B**; opcjonalnie **C** jako dodatkową warstwę (np. w tej samej funkcji co A, przed wstrzyknięciem out_line).

### 4.2 Spójność temat artykułu ↔ narzędzie w „Try it yourself”

| Środek | Opis | Za | Przeciw |
|--------|------|----|--------|
| **D. Instrukcja w prompcie** | W bloku Try-it-yourself i przy TOOLS_SELECTED: „The first tool in TOOLS_SELECTED will be used in the 'Try it yourself' section. It MUST be a tool that fits the article topic and the Prompt #1 / Prompt #2 content (e.g. video tools for video articles, automation tools for workflow articles). Do not choose a tool that cannot meaningfully use the generated prompts.” | Brak zmian w kodzie poza promptem; lepsze wybory modelu. | Model może nadal wybierać źle; brak twardej walidacji. |
| **E. Wykorzystanie opisów z YAML** | W promptach podawać listę narzędzi z opisami (już częściowo jest); dodać zdanie: „Use the tool descriptions to pick a tool that matches the article topic for the Try-it-yourself section.” | Wykorzystuje istniejące pole `short_description_en`; lepsze dopasowanie przy uzupełnionych opisach. | Wymaga uzupełnienia opisów w YAML (patrz sekcja 3). |
| **F. QA — ostrzeżenie o rozjeździe** | Opcjonalnie: w `run_preflight_qa` (blok F) dodać heurystykę: jeśli w treści Prompt #1/Prompt #2 występują słowa kluczowe tematu (np. „governance”, „agent”) a w descriptorze jest narzędzie z kategorii „video” (np. Opus Clip) — dodać warning (nie blokować). | Wykrywa oczywiste rozjazdy. | Ryzyko fałszywych alarmów; wymaga listy słów/kategorii; bardziej złożone. |

**Rekomendacja:** Wdrożyć **D + E** (prompt + opisy). **F** — opcjonalnie w drugiej iteracji po zebraniu danych, czy takie przypadki się powtarzają.

### 4.3 Lista „List of platforms and tools” zgodna z pełną treścią artykułu

| Środek | Opis | Za | Przeciw |
|--------|------|----|--------|
| **G. Budowa listy z treści body** | Przed wywołaniem `_upsert_tools_section_html`: skanować `new_body` (HTML) w poszukiwaniu faktycznych wystąpień narzędzi — np. wszystkie `<a href="URL">` gdzie URL należy do `affiliate_tools.yaml`, oraz ewentualnie nazwy narzędzi w tekście (np. wewnątrz „(AI tool)” lub w znanym kontekście). Zbudować `tool_list` tylko z narzędzi **występujących** w body; tym listem wywołać `_build_tools_mentioned_html` i `_upsert_tools_section_html`. | Lista na końcu = tylko to, co faktycznie jest w artykule; spójność z treścią; brak „wymyślonych” linków. | Wymaga funkcji „extract tool names/URLs from body” i mapowania URL→nazwa z YAML; edge case: tool wspomniany tylko w tekście bez linku (opcjonalnie można uwzględniać). |
| **H. Instrukcja w prompcie** | W sekcji „List of platforms and tools” w instrukcji: „List ONLY tools that you have actually linked or clearly mentioned by name in the article body. Do not include tools from the Affiliate/Other list that you did not use in the article.” | Wzmacnia intencję „tylko to, co w tekście”. | Obecnie pipeline **nadpisuje** listę listą z frontmatter — bez (G) sama instrukcja nie usunie z listy narzędzi niewystępujących w body. |
| **I. Frontmatter `tools` = tylko faktycznie użyte** | Po wygenerowaniu artykułu: zamiast zapisywać w `meta["tools"]` całe TOOLS_SELECTED, najpierw zeskanować body pod kątem wystąpień; zapisać w frontmatter tylko narzędzia faktycznie obecne w treści. Lista na końcu budowana dalej z meta["tools"]. | Jedno źródło prawdy (frontmatter) zgodne z treścią. | Wymaga tej samej logiki „extract from body”; przy refresh trzeba ponownie skanować body. |

**Rekomendacja:** Wdrożyć **G** (budowa listy z body); opcjonalnie **I** (spójność frontmatter z treścią). **H** warto dodać jako wsparcie, ale bez G problem pozostaje.

### 4.4 Audyt: dlaczego sekcja „List of platforms and tools” była budowana z frontmatter (TOOLS_SELECTED)

**W jakim celu i dla jakich procesów to wprowadzono (wnioski z kodu):**

- W `fill_articles.py` po wygenerowaniu body przez model: (1) z odpowiedzi wyciągana jest linia `TOOLS_SELECTED: ToolName1, ToolName2, ...` i zapisywana w `meta["tools"]`; (2) lista `tool_list` pochodzi wyłącznie z `meta["tools"]`; (3) `_build_tools_mentioned_html(tool_list, toolinfo)` buduje listę z linkami i opisami z YAML; (4) `_upsert_tools_section_html(new_body, tools_html)` **nadpisuje** całą sekcję „List of platforms and tools” tą listą (albo dopisuje ją, jeśli sekcji nie ma).
- **Prawdopodobne powody takiego rozwiązania:**
  1. **Jednolity format** — zawsze ten sam disclaimer (TOOLS_SECTION_DISCLAIMER_HTML), ten sam układ `<ul>`, te same klasy CSS.
  2. **Jedno źródło opisów** — opisy z `affiliate_tools.yaml` (`short_description_en`) zamiast dowolnych opisów wymyślanych przez model w sekcji.
  3. **Gwarancja kompletności** — sekcja zawsze istnieje i jest wypełniona, nawet gdy model pominął listę lub wstawił ją w złym formacie.
  4. **Spójność z resztą pipeline’u** — frontmatter `tools` jest używane m.in. do „Try it yourself” (pierwsze narzędzie), do placeholderów typu `{{PRIMARY_TOOL}}` w ścieżce MD; jedna lista „oficjalnych” narzędzi artykułu w jednym miejscu (meta).

**W jakich procesach to działa:**

- **Główny fill (HTML):** generacja body → ekstrakcja TOOLS_SELECTED → zapis w meta → budowa listy z meta → nadpisanie sekcji „List of platforms and tools”.
- **Odświeżanie (refresh):** przy ponownym fillu meta jest już wypełnione (np. z poprzedniego runu); `tool_list` z meta znowu nadpisuje sekcję — więc lista nie jest wtedy „skanem body”, tylko odtwarzeniem listy z ostatniego TOOLS_SELECTED.

**Za i przeciw pozostawienia budowania z frontmatter w konkretnych przypadkach**

| Opcja | Za | Przeciw |
|-------|----|--------|
| **Pozostawić wszędzie budowanie z frontmatter** | Jedna źródło prawdy (meta); stały format i opisy z YAML; brak zależności od skanowania HTML. | Lista może zawierać narzędzia niewystępujące w body (np. governance: Make, Descript tylko w meta, w tekście tylko Opus Clip) — mylące dla czytelnika i niespójne z tytułem sekcji („mentioned in this article”). |
| **Pozostawić tylko w procesach „szkieletowych” / bez pełnego body** | Gdy body nie jest jeszcze kompletne (np. tylko szkielet), lista z meta ma sens jako „planowane narzędzia”. | W obecnym pipeline fill generuje od razu pełne body; nie ma osobnej fazy „tylko szkielet”. |
| **Pozostawić przy refresh bez ponownego generowania body** | Przy refresh tylko Prompt #2 / drobne poprawki, bez ponownego generowania całego artykułu — meta i lista z meta pozostają spójne z „ostatnią wersją” wyboru narzędzi. | Nadal nie gwarantuje zgodności z aktualną treścią body (np. po ręcznej edycji body lista by się nie zaktualizowała). |

**Rekomendacja**

- **Dla głównego fillu i refreshu:** **nie** opierać sekcji „List of platforms and tools” wyłącznie na frontmatter. Wdrożyć **budowę listy z faktycznej treści body** (środek G): ekstrakcja linków/nazw z body, mapowanie na narzędzia z YAML, budowa listy tylko z tych narzędzi. Daje to zgodność z tytułem sekcji („mentioned in this article”) i eliminuje linki do narzędzi niewystępujących w tekście.
- **Opcjonalnie** w wyjątkowych procesach (np. eksport „tylko metadane” lub generowanie podglądu bez body) można nadal wystawiać listę z meta — ale w standardowym fillu/refreshu rekomendacja: lista z body, a frontmatter `tools` ewentualnie aktualizować do listy zgodnej z body (środek I) po wygenerowaniu, żeby inne miejsca (np. „Try it yourself”) nadal miały spójne dane.

**Do zatwierdzenia przed wdrożeniem:** zmiana pipeline na budowę sekcji „List of platforms and tools” z body (środek G) — czekam na zatwierdzenie.

---

## 5. Środki naprawcze dla istniejących artykułów

### 5.1 Usunięcie zbędnej pierwszej linii przed Prompt #2

- **Cel:** W każdym artykule z listy z p. 2.3 (oraz ewentualnie innych, gdzie ręcznie wykryto duplikat) przed blokiem Prompt #2 ma zostać **tylko jedna** linia: z wybranym narzędziem i „(AI tool).”
- **Procedura (propozycja):**
  1. Dla każdego pliku `.html` z listy: w sekcji od `<h3>Try it yourself…</h3>` do następnego `<h2>` znaleźć wszystkie `<p>…</p>` które są intro do Prompt #2 (zawierają „output (Prompt #2)” / „Below is the output (Prompt #2)” / „following output (Prompt #2)”).
  2. Zostawić **tylko jeden** taki akapit — ten, który zawiera **oficjalną** formę z „(AI tool).” i nazwą narzędzia zgodną z frontmatter `tools` (pierwsze z listy). Wszystkie pozostałe akapity będące intro do Prompt #2 — **usunąć**.
  3. Jeśli żaden akapit nie ma „(AI tool).”, wybrać narzędzie z frontmatter i **wstawić** jedną linię wg `_TRY_OUTPUT_VARIANTS` (np. „The AI returns the following output (Prompt #2), which is ready to use with &lt;a href=…&gt;Tool&lt;/a&gt; (AI tool).”) bezpośrednio przed drugim `<pre>` w sekcji.

### 5.2 Ewentualna korekta narzędzia w sekcji

- Dla artykułów z rażącym rozjazdem temat–narzędzie (np. governance + Opus Clip): decyzja redakcyjna — albo zmiana narzędzia w sekcji (i we frontmatter) na pasujące (np. Make), albo zmiana treści Prompt #1/Prompt #2 na use case pasujący do obecnego narzędzia. Szczegóły dla przykładu governance + Opus Clip: `docs/analysis_try_it_yourself_governance_opus_clip.md`.

### 5.3 Korekta sekcji „List of platforms and tools” — tylko narzędzia występujące w treści

- **Cel:** W artykułach, gdzie na końcu wylistowano narzędzia niewystępujące w body (np. governance: Make, Descript tylko na liście, w tekście tylko Opus Clip), **zastąpić** sekcję „List of platforms and tools mentioned in this article” listą zawierającą **wyłącznie** narzędzia, które faktycznie pojawiają się w treści (link lub jednoznaczna nazwa).
- **Procedura (propozycja):**
  1. Dla każdego pliku `.html`: wyciągnąć z body wszystkie URL-e z `<a href="...">` i zmapować je na nazwy z `affiliate_tools.yaml`; opcjonalnie uwzględnić nazwy narzędzi w kontekście „(AI tool)” lub w znanym fragmencie „Try it yourself”.
  2. Zbudować listę unikalnych narzędzi faktycznie występujących w body (w kolejności pierwszego wystąpienia lub alfabetycznie).
  3. Zastąpić zawartość sekcji H2 „List of platforms and tools mentioned in this article” nową listą `<ul>` z tymi narzędziami (link + opis z YAML lub domyślny).
  4. Opcjonalnie: zaktualizować frontmatter `tools` do listy zgodnej z body (żeby przy kolejnym refresh nie nadpisać poprawionej listy pełnym TOOLS_SELECTED).
- **Artykuł governance:** W ramach tej korekty w „List of platforms and tools” powinno zostać tylko **Opus Clip** (Make i Descript — usunąć z listy).

---

## 6. Propozycja wykorzystania opisów w API/pipeline

- **Gdzie opisy są już używane:** W `fill_articles.py` przy budowaniu `tools_blob` (lista narzędzi do promptu); jeśli jest `short_description_en`, format to `Name=URL|description`.
- **Gdzie warto je wykorzystać bardziej:**
  - **Generacja treści:** Instrukcja: „Use the tool descriptions to select tools that match the article topic. For 'Try it yourself', the first selected tool must be one that can actually be used with the kind of Prompt #2 you generate.”
  - **Sekcja „List of platforms and tools” i linki w tekście:** Już jest reguła „use description from list or write factual one sentence” — przy pełniejszych opisach w YAML mniej wymyślania przez model, większa spójność.
- **Jak dodać opisy tam, gdzie ich brak:** Ręcznie lub półautomatycznie (skrypt wyciągający nazwę + category i generujący szablon `short_description_en` do uzupełnienia). Nie zmienia to API — tylko zawartość YAML i ewentualnie jeden raz skrypt do uzupełnienia szablonów.

---

## 7. Podsumowanie: za i przeciw oraz rekomendacja

### Za wdrożeniem proponowanych środków

- **Jakość:** Jedna, czytelna linia intro przed Prompt #2; mniej pomyłek narzędzie–temat; **lista narzędzi na końcu zgodna z pełną treścią** — brak linków „występujących w artykule”, które w tekście w ogóle się nie pojawiają.
- **Skalowalność:** Rozszerzenie normalizacji (A) + instrukcje (B, D, E) + budowa listy z body (G) zabezpieczają przyszłe generacje i odświeżenia.
- **Wykorzystanie danych:** Plik `affiliate_tools.yaml` z opisanymi narzędziami staje się jednym źródłem prawdy dla opisów w artykułach i lepszego doboru narzędzi.

### Przeciw / ryzyka

- **Normalizacja (A):** Regex musi być ograniczony do sekcji „Try it yourself”, żeby nie usuwać zdań w innych sekcjach.
- **Opisy w YAML:** Ręczne uzupełnienie wymaga czasu; bez tego korzyść z (E) jest ograniczona.
- **Korekty istniejących artykułów:** Wymagają uruchomienia skryptu naprawczego lub ręcznej edycji 14 plików; przy zmianie narzędzia (rozjazd temat–narzędzie) — dodatkowa decyzja redakcyjna.
- **Środek G (lista z body):** Wymaga implementacji ekstrakcji linków/nazw z HTML i mapowania na narzędzia z YAML; przy „wspomnieniu bez linku” trzeba zdefiniować politykę (uwzględniać czy nie).

### Rekomendacja

1. **Zatwierdzić kierunek:**  
   - Rozszerzenie normalizacji HTML (środek A) + zaostrzenie instrukcji (B, D, E).  
   - **Budowa sekcji „List of platforms and tools” wyłącznie z narzędzi faktycznie występujących w treści (G).**  
   - Jednorazowa naprawa istniejących artykułów: usunięcie zbędnej pierwszej linii przed Prompt #2 (procedura z p. 5.1) oraz **korekta sekcji „List of platforms and tools”** tam, gdzie na liście są narzędzia niewystępujące w body (procedura z p. 5.3).
2. **Kolejność wdrożenia (po zatwierdzeniu):**  
   - Najpierw zmiany w kodzie: A, B, ewentualnie C; D, E w promptach; **G** (ekstrakcja z body + budowa listy).  
   - Potem skrypt lub ręczna korekta: 14 plików (duplikat intro) + artykuły z rozbieżną listą narzędzi (w tym governance — tylko Opus Clip na liście).  
   - Uzupełnienie `short_description_en` w `affiliate_tools.yaml` stopniowo (najpierw referral + często używane).
3. **Opcjonalnie:** Heurystyka QA (F); aktualizacja frontmatter `tools` do listy zgodnej z body (I).

---

---

## 8. Plan uzupełnienia opisów w `affiliate_tools.yaml` (do wykonania po zatwierdzeniu)

**Nie uzupełniano jeszcze opisów** — poniżej tylko plan, gotowy do wdrożenia po Twoim zatwierdzeniu.

- **Mają już `short_description_en` (3):** Opus Clip, Make, UptimeRobot.
- **Brak `short_description_en` (pozostałe wpisy):** 10Web.io, Answrr, Awin, Blaze, Canva, CJ Affiliate, ClickBank, Copy.ai, CustomGPT, Descript, FlexOffers, FutureTools.io, Google Workspace, HeyGen, Hostinger, Impact, Insta Engine AI, Jasper, JVZoo, Lately AI, MarketingBlocks, Microsoft 365, Narrato, nazwa.pl, Notta, OmniMint AI, OVHcloud, Pictory, Rewardful, ShareASale, Shopify Collabs, Synthesia, Writesonic, Wise, Zapier, Claude, EcomFly.ai, Lovable, n8n, Perplexity AI, Sora, Veo, Otter, ChatGPT, Gemini, Blogify, VEED, Murf AI.

**Proponowana forma uzupełnienia:**

- Dla każdego narzędzia dodać linię: `short_description_en: "Jedno zdanie po angielsku: co robi narzędzie (np. AI short-form clips from long videos)."`
- Źródła: strona produktu, dokumentacja, kategoria w YAML (np. video → "AI video creation", transcription → "Transcription and meeting notes").
- **Priorytet:** najpierw narzędzia z kategorii `referral` (już uzupełnione), potem te często występujące w artykułach (np. Descript, Canva, Copy.ai, ChatGPT, Otter, VEED, Pictory, n8n, Zapier), potem reszta według potrzeb.

Po zatwierdzeniu można wykonać uzupełnienie (ręcznie lub skryptem generującym szablony do ręcznej redakcji). Następnie zająć się **naprawą istniejących artykułów** (duplikat intro, lista narzędzi vs. body).

---

**Dokument przygotowany w trybie audytu; brak wdrożenia w kodzie do momentu zatwierdzenia.**
