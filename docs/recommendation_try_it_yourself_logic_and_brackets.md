# Rekomendacja: logika „Try it yourself” i nawiasy w placeholders

## 1. Try it yourself – czy wymaganie descriptorów jest spójne z opcjonalnością sekcji?

### Obecna logika

- **W promptach** (`_try_it_yourself_instruction`):
  - **how-to:** sekcja „Try it yourself” jest **wymagana** („You MUST include this subsection”).
  - **guide:** sekcja jest **opcjonalna** („Include ONLY if the article topic involves creating, processing, or transforming content with AI tools… If the topic is purely strategic, analytical, or organizational, omit this subsection”).

- **W QA** (`run_preflight_qa`, blok F):
  - Sprawdzenie descriptorów (Prompt #1, Prompt #2, Action cue) uruchamia się **zawsze, gdy w tekście występuje fraza „try it yourself”**.
  - QA **nie** dostaje `content_type` – nie wie, czy sekcja była wymagana, czy opcjonalna.

### Gdzie jest niespójność

- Dla **guide** dopuszczamy **pominięcie** całej sekcji (model może jej w ogóle nie dodać).
- Gdy model jednak **doda** sekcję (np. sam nagłówek „Try it yourself” i jedną linijkę), QA wymaga **pełnego** formatu (descriptor Prompt #1, Prompt #2, „Action cue:”).
- Skutek: artykuł typu guide z **częściową** sekcją „Try it yourself” failuje z „missing deterministic Prompt #1 descriptor line” itd., mimo że dla guide sekcja była opcjonalna. Wymagamy więc descriptorów w sytuacji, gdy sama sekcja nie była obowiązkowa – to błąd logiki.

Dla **how-to** sekcja jest wymagana, więc wymaganie descriptorów jest uzasadnione.

### Rekomendacja 1 (do zatwierdzenia)

**Sprowadzić wymaganie descriptorów do przypadków, w których sekcja jest obowiązkowa.**

- **Zmiana w kodzie:**  
  - Dodać do `run_preflight_qa` parametr `content_type: str | None = None`.  
  - W bloku F („Try it yourself”): **wymagać** descriptorów (Prompt #1, Prompt #2, Action cue) **tylko gdy** `content_type == "how-to"` **oraz** w tekście jest „try it yourself”.  
  - Dla `content_type != "how-to"` (guide, comparison, brak typu) **nie** uruchamiać sprawdzenia descriptorów – nawet jeśli w tekście jest „try it yourself”.  

- **Wywołanie:** W miejscu wywołania `run_preflight_qa` przekazać `content_type=(meta.get("content_type") or "").strip() or None`.

- **Efekt:**  
  - how-to: bez zmian – sekcja wymagana, descriptorzy wymagani.  
  - guide / inne: brak błędu „missing deterministic…” przy częściowej lub nietypowej sekcji „Try it yourself”; opcjonalność sekcji jest spójna z brakiem wymogu descriptorów.

---

## 2. Placeholdery w nawiasach – czy nakazać używanie ( ) zamiast [ ]?

### Obecna logika

- QA uznaje za błąd **wyłącznie** placeholdery w **nawiasach kwadratowych** `[ ... ]` (regex `\[[^\]]+\](?!\s*\()` – wyklucza linki markdown).
- Nawiasy **okrągłe** `( ... )` **nie** są sprawdzane; tekst typu „(Insert Video Title Here)” nie powoduje faila.

### Czy można „literalnie nakazać” używanie ( ) zamiast [ ]?

Tak. W prompcie do API można dodać jasną regułę:

- **„Do not use square brackets [ ] for placeholders, variables, or example slots. Use round parentheses ( ) when you need to indicate a variable or example, e.g. (video title) or (your product name).”**  
  (Opcjonalnie: „Replace any [placeholder] with concrete content, or if you must show a slot use (placeholder).”)

### Skutki

- **Zalety:**  
  - Model, który i tak zostawia „slot” (np. zamiast konkretnego tytułu), będzie pisał „(Insert Video Title Here)” lub „(video title)” zamiast „[Insert Video Title Here]”.  
  - Obecna QA **nie** flaguje `( ... )`, więc liczba failed z powodu „bracket placeholders” spadnie.  
  - Jedna, prosta reguła w prompcie, bez zmiany QA.

- **Ryzyka:**  
  - W treści mogą się pojawić literalne „(Insert …)” lub „(your X here)” – nadal to placeholdery, tylko w okrągłych nawiasach.  
  - Można to zaakceptować jako mniejsze zło niż fail QA, albo w dalszej kolejności rozważyć (np. sanityzację lub osobną regułę) tylko jeśli będzie problem.

### Rekomendacja 2 (do zatwierdzenia)

**Dodać w prompcie (markdown i HTML) jedno zdanie nakazujące używanie nawiasów okrągłych zamiast kwadratowych.**

- **Treść (EN, w instrukcjach „no bracket placeholders”):**  
  „Do not use square brackets [ ] for placeholders or example slots. If you need to indicate a variable or example, use round parentheses ( ) instead, e.g. (video title) or (your product name).”

- **Gdzie:** W tych samych miejscach, gdzie jest dzisiaj zakaz `[Name]`, `[Date]` itd. (LENGTH AND CONTENT RULES w HTML, OUTPUT CONTRACT / Defensible w markdown), jako uzupełnienie: „use ( ) not [ ] for any remaining slot”.

- **Bez zmian w kodzie QA:** Nie zmieniać regexu ani listy przyczyn fail; nadal odrzucać tylko `[ ... ]`. Nawiasy `( ... )` pozostają dozwolone.

- **Efekt:** Mniej failed z powodu „bracket placeholders”; ewentualne „(Insert…)” w tekście – do ewentualnej obróbki później, jeśli będzie potrzeba.

---

## 3. Podsumowanie do zatwierdzenia

| # | Rekomendacja | Zmiana |
|---|--------------|--------|
| **1** | **Try it yourself** | Dodać `content_type` do `run_preflight_qa` i wymagać descriptorów (Prompt #1, Prompt #2, Action cue) **tylko gdy** `content_type == "how-to"`. Dla guide i innych typów nie raportować „missing deterministic…”. |
| **2** | **Nawiasy** | W prompcie do API (markdown + HTML) dodać zdanie: nie używać `[ ]` dla placeholderów/slotów; używać `( )` np. (video title). QA bez zmian – nadal tylko `[ ... ]` powoduje fail. |

Pozostałe ustalenia z analizy (word count, nie osłabiać QA, raport breakdown) – bez zmian.

Po zatwierdzeniu tych dwóch punktów można wdrożyć zmiany w kodzie (rekomendacja 1) i w treściach promptów (rekomendacja 2).
