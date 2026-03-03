# Analiza: artykuł lead-loss (sukces fillu, błędy w sekcji Try it yourself)

**Plik:** `public/articles/2026-02-24-guide-to-how-to-monitor-lead-loss-due-to-scenario-failures-in-ai-driven-marketing-automations.audience_intermediate/index.html`  
**Źródło fillu:** `content/articles/.../...audience_intermediate.html`  
**Kontekst:** Artykuł przeszedł fill i QA, ale w sekcji „Try it yourself” są błędy merytoryczne i niespójności.

---

## 1. Co jest nie tak (krótko)

### 1.1 Zawartość pod „Prompt #1” to nie Prompt #1 i brak Prompt #2

- **Oczekiwane:** Pod linią „Here is the input (Prompt #1) ready to use with Make (…).” powinien być **konkretny, krótki prompt do wklejenia** (Prompt #1), a dalej druga linia „Below is the output (Prompt #2)…” i **drugi blok** z wygenerowaną odpowiedzią AI (Prompt #2).
- **Faktycznie:** Jest **tylko jeden** blok `<pre>`. Zawiera on **meta-instrukcje** („To generate a comprehensive weekly report… I recommend using the following prompt:”, potem szkielet „Weekly Lost Leads Report Prompt”, pytania doprecyzowujące itd.) – czyli opis **jak zbudować** raport, a nie gotowy prompt do wklejenia ani wynik działania Prompt #1.
- **Skutek:** Czytelnik pod „Prompt #1” dostaje długi opis struktury, a **prawdziwego Prompt #1** (input do wklejenia) **w ogóle nie ma**. **Prompt #2** (output AI) też **nie ma** – brak drugiego `<pre>` i brak wstawionej treści z `_generate_real_prompt2`.

**Przyczyna w pipeline:** Model wygenerował jeden blok z meta-treścią zamiast (1) krótkiego Prompt #1 w pierwszym `<pre>` i (2) markera `[PROMPT2_PLACEHOLDER]` (zastępowanego później przez system). Bez drugiego bloku i bez placeholderu `_insert_prompt2` nic nie wstawia, a `_normalize_try_it_yourself_html` wstrzykuje drugą linię i CTA tylko gdy są **dwa** `<pre>` – więc w tym artykule nie ma linii przed „Prompt #2” ani zdania zachęty.

---

### 1.2 Opis narzędzia w linii przed blokiem vs lista na dole

- **W tekście (descriptor):** „Make **(AI or productivity tool)**”.
- **Na liście na dole:** „Make — **Visual automation and integrations**”.

Make w `affiliate_tools.yaml` ma `category: "referral"` i `short_description_en: "Visual automation and integrations"`. W pipeline dla HTML używana jest **kategoria** do opisu w sekcji Try it yourself: `_get_tool_type_display("Make")` zwraca `CATEGORY_TO_TYPE_DISPLAY["referral"]` = **„AI or productivity tool”**. Na liście „List of platforms and tools” używany jest **short_description_en**. Stąd rozjazd: ten sam tool raz jako „(AI or productivity tool)”, raz jako „Visual automation and integrations”.

---

### 1.3 Duplikat słowa w disclaimerze

- **W artykule:** „not a claim that they are **a strong option option**”.
- **Oczekiwane:** „a strong option” (jedno słowo „option”).

Stała `TOOLS_SECTION_DISCLAIMER_HTML` zawiera „the best option”. Sanityzacja zamienia „the best” → „a strong option”, więc „the best option” staje się „**a strong option** option”.

---

### 1.4 Inne (krótko)

- **Lista narzędzi na dole:** Tylko Make (środek G działa – w body jest tylko link do Make).
- **FAQ:** „What tools are **best**…” – w oryginale było „best”; po sanityzacji powinno być „a strong option” lub podobnie; w opublikowanym pliku jest nadal „best” (możliwy błąd w wersji / brak sanityzacji w tym miejscu w danej ścieżce). Warto w analizie zweryfikować, czy cały body przechodzi przez sanitize.

---

## 2. Propozycje modyfikacji (do zatwierdzenia)

### 2.1 Treść Prompt #1 vs meta-instrukcje i obecność Prompt #2

**Problem:** Model często generuje „jak zbudować prompt” zamiast **gotowego Prompt #1** i nie wstawia **drugiego bloku** z `[PROMPT2_PLACEHOLDER]`.

**Propozycje:**

- **A) Instrukcja w prompcie:** W bloku Try-it-yourself wyraźnie doprecyzować:
  - „Prompt #1 must be a **single, copy-pasteable prompt** (one short paragraph or a few lines) that the reader can paste into the tool. Do **not** output meta-instructions like ‘I recommend using the following prompt’ or a long structure; output **the actual prompt text**.”
  - „You **must** output exactly **two** code blocks in the Try-it-yourself section: first block = Prompt #1 (the input), then a line with [PROMPT2_PLACEHOLDER], which the system will replace with the real AI output. There must be two blocks.”
- **B) QA / walidacja:** Po fillu (przed QA) sprawdzać w sekcji Try it yourself: czy są **dwa** bloki `<pre>` (HTML) lub dwa bloki ``` (MD); jeśli jest tylko jeden – dopisać do przyczyn odrzucenia QA np. „Try-it-yourself: expected two prompt blocks, found one” (żeby takie artykuły nie przechodziły).
- **C) Opcjonalnie – post-processing:** Jeśli po wygenerowaniu jest tylko jeden `<pre>` w sekcji Try it yourself i jest w nim tekst w stylu „I recommend…”, „following prompt:”, „structure will help…”, można próbować (np. heurystycznie) potraktować pierwszy akapit lub pierwszy zwięzły fragment jako „Prompt #1” i przenieść resztę / drugi blok – to bardziej ryzykowne i tylko jako ewentualne uzupełnienie po A+B.

**Rekomendacja:** Wdrożyć **A** i **B**; C tylko w razie potrzeby po ocenie skuteczności A+B.

---

### 2.2 Jednolity opis narzędzia (descriptor = short_description_en gdy jest)

**Problem:** W linii przed blokiem używany jest `type_display` z kategorii (np. „AI or productivity tool”), a na liście na dole – `short_description_en` (np. „Visual automation and integrations”), co daje niespójność.

**Propozycja:** W `_normalize_try_it_yourself_html` (oraz ewentualnie w MD, gdy będzie normalizacja): przy budowaniu linii „ready to use with X (…).” **gdy dla danego narzędzia jest `short_description_en` w YAML** – użyć go w nawiasie zamiast `type_display`, np. „Make (Visual automation and integrations).”. Gdy brak `short_description_en` – zostawić obecne `type_display` (np. „AI or productivity tool”). Dzięki temu descriptor i lista na dole będą zgodne.

**Rekomendacja:** Wdrożyć (użycie short_description_en w descriptorze gdy dostępne).

---

### 2.3 Duplikat „option” w disclaimerze

**Problem:** Sanityzacja zamienia „the best” → „a strong option”, przez co „the best option” staje się „a strong option option”.

**Propozycje:**

- **D1)** W stałej `TOOLS_SECTION_DISCLAIMER_HTML` od razu użyć tekstu bez „the best”: np. „not a claim that they are a strong option” – wtedy sanityzacja nie zmieni tej linii i nie będzie podwójnego „option”.
- **D2)** W `sanitize_filled_body`: najpierw zamieniać **całą frazę** „the best option” → „a strong option” (jednym wywołaniem), a dopiero potem ogólne „the best” → „a strong option”, żeby nigdzie nie powstawało „a strong option option”.

**Rekomendacja:** Zrobić **obydwa** – D1 (stała bez „the best”) i D2 (sanityzacja frazy „the best option” w jednym kroku).

---

## 3. Kolejność wdrożenia (po zatwierdzeniu)

1. **2.3** – Disclaimer (D1 + D2), żeby usunąć „a strong option option”.
2. **2.2** – Descriptor w Try it yourself: short_description_en gdy dostępne.
3. **2.1 A** – Doprecyzowanie instrukcji (Prompt #1 = jeden gotowy prompt, obowiązkowo dwa bloki + [PROMPT2_PLACEHOLDER]).
4. **2.1 B** – QA: wymóg dwóch bloków w sekcji Try it yourself (HTML/MD).

---

## 4. Pliki do zmiany

- **scripts/fill_articles.py**
  - Stała `TOOLS_SECTION_DISCLAIMER_HTML` (D1).
  - `sanitize_filled_body`: zamiana „the best option” przed „the best” (D2).
  - `_normalize_try_it_yourself_html`: użycie `short_description_en` w descriptorze gdy jest (2.2).
  - Instrukcje w promptach (build_prompt / user_message) dla Try-it-yourself (2.1 A).
  - `check_output_contract` lub inna funkcja QA: warunek „dwa bloki pre/code w Try it yourself” (2.1 B).

---

## 5. Podsumowanie

| Błąd | Przyczyna | Propozycja |
|------|-----------|------------|
| Pod „Prompt #1” meta-treść zamiast promptu; brak Prompt #2 | Model wygenerował jeden blok z instrukcjami; brak drugiego bloku i [PROMPT2_PLACEHOLDER] | A: instrukcja (Prompt #1 = gotowy prompt, dwa bloki); B: QA wymaga 2 bloków |
| „Make (AI or productivity tool)” vs „Make — Visual automation…” | Descriptor z kategorii, lista z short_description_en | Używać short_description_en w descriptorze gdy jest |
| „a strong option option” | Sanityzacja „the best” → „a strong option” w tekście „the best option” | D1: stała bez „the best”; D2: sanitize najpierw „the best option” → „a strong option” |

---

*Do wdrożenia dopiero po zatwierdzeniu.*
