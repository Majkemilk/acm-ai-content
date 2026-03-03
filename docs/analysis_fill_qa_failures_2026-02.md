# Analiza: odrzucenia QA przy fillu (3 artykuły, 2026-02-24)

**Kontekst:** Wygenerowano 3 artykuły; wynik: 1 zapisany, 2 QA fail. Poniżej krótki opis przyczyn i propozycja zmian (do wdrożenia po zatwierdzeniu).

---

## 1. Co się stało (krótko)

| Zdarzenie | Znaczenie |
|-----------|-----------|
| **Sanitized: … 'the best'→'a strong option'** | Działanie zgodne z założeniami – frazy zabronione w treści są zamieniane. |
| **Replaced remaining placeholders: … [PROMPT2_PLACEHOLDER] -> "PROMPT2_PLACEHOLDER"** | Każdy `[xxx]` jest zamieniany na `"xxx"`. `[PROMPT2_PLACEHOLDER]` trafia do tej zamiany **przed** wstawieniem prawdziwego Prompt #2, więc w body ląduje literalny tekst `"PROMPT2_PLACEHOLDER"`. Krok `_insert_prompt2` i tak go potem znajduje (regex dopuszcza cudzysłowy) i zastępuje treścią Prompt #2 – więc treść jest wstawiana, ale log jest mylący i w edge case’ach można by nadpisać marker zanim go obsłuży _insert_prompt2. |
| **Warning: AI did not return TOOLS_SELECTED for …** | Model nie zwrócił linii `TOOLS_SELECTED: Tool1, Tool2`. W efekcie `meta["tools"]` zostaje puste, `tool_list` też – brak narzędzi do „Try it yourself” i listy na końcu. |
| **QA FAIL: bracket placeholders still present: ['[Insert AI tool name here]']** | Model zostawił w treści placeholder `[Insert AI tool name here]`. Nie ma go na liście znanych zamian (`_KNOWN_BRACKET_FALLBACKS`), a zamiana „pozostałych” `[xxx]` na `"xxx"` albo nie objęła tego wystąpienia (np. w innym kontekście), albo QA patrzy na wersję body, w której ten placeholder nadal jest. W efekcie QA zgłasza niedozwolone nawiasy. |
| **QA FAIL: missing deterministic Prompt #2 descriptor line** | QA wymaga w tekście zdania w stylu: „Below is the output (Prompt #2) … ready to use with **X** (AI tool).” lub „The AI returns the following output (Prompt #2) … ready to use with **X** (AI tool).”. Dla **HTML** taką linię wstrzykuje `_normalize_try_it_yourself_html`. Dla **MD** nic jej nie wstrzykuje – liczy się wyłącznie na to, co wygeneruje model. Gdy model napisze inaczej (np. „result of Prompt #2”, „output from Prompt #2”, inna kolejność słów), regex w QA nie znajdzie wzorca i zgłasza brak linii. |
| **QA FAIL: missing encouraging sentence or reference to Prompt #2 after Try-it-yourself block** | QA wymaga, żeby w body (po usunięciu szablonów) występowało „prompt #2” lub „prompt 2” (bez spacji). Jeśli model nie użyje tej frazy w zdaniu zachęty po bloku Try-it-yourself, QA uznaje to za błąd. |

**Podsumowanie:** Artykuły są **MD** (nie HTML). W ścieżce MD nie ma normalizacji „Try it yourself” (wstrzykiwanie linii z narzędziem); lista narzędzi i descriptor zależą od TOOLS_SELECTED i od tego, co model wpisze. Brak TOOLS_SELECTED + placeholder `[Insert AI tool name here]` + inna forma opisu Prompt #2 / brak jawnego „prompt #2” prowadzą do 2× QA fail.

---

## 2. Propozycje modyfikacji (do zatwierdzenia)

### 2.1 Placeholder `[Insert AI tool name here]`

- **Działanie:** Dodać do `_KNOWN_BRACKET_FALLBACKS` w `fill_articles.py` wpis:
  - `("[Insert AI tool name here]", "the suggested AI tool")`  
  (albo: „the chosen tool from the list above” / pierwsze narzędzie z `tool_list`, jeśli dostępne w momencie zamiany – wtedy trzeba by wykonać zamianę znanych placeholderów **po** ustawieniu `tool_list`, tylko dla tego jednego; prostsza wersja to stały tekst).
- **Efekt:** Placeholder znika z body przed QA; nie ma już błędu „bracket placeholders still present” z tym tokenem.
- **Opcjonalnie:** W instrukcji dla modelu dodać zdanie: „Do not output [Insert AI tool name here]; use the actual tool name from TOOLS_SELECTED.”

**Rekomendacja:** Wdrożyć wpis w `_KNOWN_BRACKET_FALLBACKS` (stały tekst „the suggested AI tool”); instrukcję wzmocnić opcjonalnie.

---

### 2.2 Nie zamieniać `[PROMPT2_PLACEHOLDER]` w „remaining placeholders”

- **Działanie:** W `replace_remaining_bracket_placeholders_with_quoted` pominąć dokładnie `[PROMPT2_PLACEHOLDER]` (np. jeśli `inner.strip().upper() == "PROMPT2_PLACEHOLDER"`, zwrócić `full` bez zamiany).
- **Efekt:** Marker zostaje w body do momentu `_insert_prompt2`; log nie pokazuje mylącego „placeholder [PROMPT2_PLACEHOLDER] -> "PROMPT2_PLACEHOLDER"”; mniejsze ryzyko edge case’ów.

**Rekomendacja:** Wdrożyć.

---

### 2.3 Fallback przy braku TOOLS_SELECTED

- **Działanie:** Gdy po `_extract_tools_selected` lista `selected_tools` jest pusta **i** w `meta` nie ma wcześniej przypisanych narzędzi (np. z kolejki), ustawić `meta["tools"]` z fallbacku:
  - np. `primary_tool` / `secondary_tool` z frontmatter (jeśli są), **albo**
  - jedno–dwa narzędzia z `_load_affiliate_tools()` (np. pierwsze z kategorii referral lub `_first_reference_tool_name()`).
- **Efekt:** Artykuł ma mimo wszystko narzędzie do „Try it yourself” i do listy na końcu; mniej „Warning: AI did not return TOOLS_SELECTED” kończących się pustą listą.

**Rekomendacja:** Wdrożyć fallback (kolejność: meta primary_tool/secondary_tool → pierwsze referral z YAML).

---

### 2.4 Linia descriptor Prompt #2 (MD) i QA

- **Problem:** Dla MD nie ma odpowiednika `_normalize_try_it_yourself_html` – linia „… ready to use with X (AI tool).” przed Prompt #2 musi pochodzić od modelu; QA ma sztywny regex.
- **Opcje:**  
  - **A)** Dodać krok normalizacji dla MD: przed drugim blokiem kodu (Prompt #2) w sekcji „Try it yourself” wstawić jedną linię z narzędziem (np. „The AI returns the following output (Prompt #2), which is ready to use with {tool} (AI tool).”), jeśli wykryto brak takiego zdania (np. brak dopasowania obecnego regexu). Narzędzie: z `tool_list[0]` lub fallbacku z p. 2.3.  
  - **B)** Rozluźnić regex w QA tak, aby akceptował więcej sformułowań (np. „output of Prompt #2”, „result of Prompt #2”, „following output (Prompt #2)” oraz „ready to use with X (AI tool).” / „ready to use with X.”).
- **Rekomendacja:** Wdrożyć **A** (normalizacja MD – wstrzyknięcie linii gdy brak) **oraz** lekko **B** (rozszerzyć wzorzec QA, żeby nie odrzucać sensownych wariantów).

---

### 2.5 Zachęta po Try-it-yourself („encouraging sentence”)

- **Działanie:** Albo (1) rozluźnić warunek w QA (np. dopuścić „second prompt”, „prompt 2” z spacją, „output above”), albo (2) dodać w instrukcji dla modelu wyraźną wymóg: „After the Try-it-yourself block you must include one short encouraging sentence that refers to Prompt #2 (e.g. paste Prompt #2 into…, use the output above…).”.
- **Rekomendacja:** Wdrożyć (2); opcjonalnie (1) jako zabezpieczenie przed fałszywymi odrzuceniami.

---

## 3. Kolejność wdrożenia (po zatwierdzeniu)

1. **2.1** – `[Insert AI tool name here]` w `_KNOWN_BRACKET_FALLBACKS`.  
2. **2.2** – Pomijanie `[PROMPT2_PLACEHOLDER]` w `replace_remaining_bracket_placeholders_with_quoted`.  
3. **2.3** – Fallback narzędzi gdy brak TOOLS_SELECTED (meta / referral z YAML).  
4. **2.4** – Normalizacja MD: wstrzyknięcie linii descriptor przed Prompt #2 gdy brak + ewentualne rozluźnienie regexu QA.  
5. **2.5** – Doprecyzowanie instrukcji (obowiązkowa zachęta odnosząca się do Prompt #2); opcjonalnie rozluźnienie warunku QA.

---

## 4. Pliki do zmiany

- `scripts/fill_articles.py`:  
  - `_KNOWN_BRACKET_FALLBACKS` (2.1),  
  - `replace_remaining_bracket_placeholders_with_quoted` (2.2),  
  - blok po `_extract_tools_selected` (2.3),  
  - nowa funkcja / krok normalizacji Try-it-yourself dla MD (2.4),  
  - regex w `check_output_contract` (2.4 B, 2.5),  
  - instrukcje w `build_prompt` / blokach promptu (2.5, opcjonalnie 2.1).

---

*Do wdrożenia dopiero po zatwierdzeniu.*
