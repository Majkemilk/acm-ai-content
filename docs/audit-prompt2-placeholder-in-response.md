# Audyt: literal [PROMPT2_PLACEHOLDER] w „odpowiedzi API” (HTML)

## Pytanie
Dlaczego w odpowiedzi API (HTML) nadal ląduje literal `[PROMPT2_PLACEHOLDER]` zamiast wygenerowanego Prompt #2?

## Wnioski z audytu

### 1. Gdzie widać [PROMPT2_PLACEHOLDER]

W logu (np. `flowtaro_refresh_articles.log`) treść pod nagłówkiem **`--- SUROWA ODPOWIEDŹ API ---`** to **surowa odpowiedź modelu**, zaraz po `call_responses_api()`, **przed** jakimkolwiek post‑processingiem.

Kolejność w kodzie (`fill_articles.py`):

1. `new_body = call_responses_api(...)`  
2. **`print("--- SUROWA ODPOWIEDŹ API ---"); print(new_body)`**  ← tu w logu widać placeholder  
3. sanityzacja, strip editor notes, zamiana bracket placeholders (z wyjątkiem PROMPT2_PLACEHOLDER)  
4. (dalej w pipeline) ekstrakcja Prompt #1, `_generate_real_prompt2()`, **`_insert_prompt2()`**  
5. normalizacja Try-it-yourself (descriptor + CTA)  
6. QA, zapis pliku  

Czyli **obecność `[PROMPT2_PLACEHOLDER]` w tym fragmencie logu jest oczekiwana**: model dostaje instrukcję, żeby tam wstawić tylko marker; zamiana na prawdziwy Prompt #2 odbywa się w kroku 4.

### 2. Czy zamiana faktycznie się wykonuje?

W tym samym logu dla artykułu `veed-vs-submagic-vs-opus-clip-comparison` widać:

- `Generating real Prompt #2 for 2026-02-20-veed-vs-submagic-vs-opus-clip-comparison.md …`
- **`Prompt #2 inserted (1985 chars)`**
- `QA FAIL: … — missing deterministic Prompt #2 descriptor line`

Czyli **wstawienie Prompt #2 w treść (`_insert_prompt2`) działa** – w body, które idzie do QA, jest już wygenerowany Prompt #2, a nie placeholder. Placeholder w logu widać tylko dlatego, że logujemy stan **przed** tym wstawieniem.

### 3. Dlaczego może się wydawać, że „nadal ląduje” placeholder?

- **Źródło 1 – log:** Jedyny „pełny HTML” w logu to surowa odpowiedź API (punkt 2 powyżej). Nie ma tam drugiego dumpu body **po** wstawieniu Prompt #2, więc naturalne jest wrażenie, że „w odpowiedzi” cały czas jest placeholder.
- **Źródło 2 – brak zapisanego .html przy QA FAIL:** Gdy QA się nie powiedzie, **nie zapisujemy** wygenerowanego HTML na dysk (tylko ewentualnie blokujemy .md). W efekcie nie ma pliku .html z już wstawionym Prompt #2, a użytkownik nie widzi „poprawionej” wersji – widzi tylko surową odpowiedź w logu.

### 4. Rzeczywista przyczyna problemu z „brakiem” Prompt #2 w wyniku

Problem nie polega na tym, że placeholder nie jest zamieniany. Problem polega na tym, że **po wstawieniu Prompt #2 i po normalizacji sekcji Try-it-yourself QA i tak zgłasza** `missing deterministic Prompt #2 descriptor line`, więc cały run kończy się QA FAIL i **zapis pliku nie następuje**.

Przyczyna: **niedopasowanie formatu linii deskryptora do regexu w QA.**

- **Normalizer HTML** (`_normalize_try_it_yourself_html`) wstawia linię w formie:
  - `Below is the output (Prompt #2) the AI returns, which is ready to use with {tool} in the same or a new thread, or in another tool of the same type ({descriptor}).`
  - czyli po słowie **`thread`** jest **przecinek**: `thread, or in another...`

- **Regex w QA** (`output_re` w `run_preflight_qa`) wymaga po frazie `in the same or a new thread` **kropki** (`\.`):
  - `(?:\s+in the same or a new thread|\s*\(AI tool\))\.`
  - dopasowuje np. `... thread.` lub `(AI tool).`, ale **nie** `... thread, or ...`

Efekt: po normalizacji linia deskryptora jest poprawna merytorycznie, ale **regex QA jej nie akceptuje** → QA FAIL → użytkownik nie dostaje zapisanego .html i jedyne, co widzi, to surowa odpowiedź z placeholderem w logu.

## Podsumowanie przyczyn

| Zjawisko | Przyczyna |
|----------|-----------|
| Literal `[PROMPT2_PLACEHOLDER]` w „odpowiedzi API” w logu | Log „SUROWA ODPOWIEDŹ API” jest drukowany **przed** `_insert_prompt2()`. To zamierzone – placeholder w tym miejscu jest oczekiwany. |
| Brak wygenerowanego Prompt #2 w zapisanym pliku | Zapis .html następuje tylko przy QA PASS. QA failuje przez **regex deskryptora Prompt #2** (wymaga `thread.`, normalizer daje `thread,`), więc plik nie jest zapisywany i użytkownik nie widzi wersji z już wstawionym Prompt #2. |

## Rekomendacje

1. **Logowanie:** Dodać w logu krótką adnotację przy „SUROWA ODPOWIEDŹ API”, np.:  
   `(przed wstawieniem Prompt #2; placeholder zostanie zastąpiony w następnym kroku)`.  
   Opcjonalnie: drugi, zwięzły log po `_insert_prompt2` (np. długość body), żeby było widać, że krok się wykonał.

2. **QA vs normalizer (krytyczne):** Albo rozluźnić regex w QA tak, aby akceptował po `in the same or a new thread` także przecinek (np. `(?:thread\.|thread,)`), albo zmienić tekst wstrzykiwany w normalizerze tak, aby po `thread` była kropka (wtedy obecny regex zadziała). Rekomendacja: **dostosować regex w QA** do aktualnego formatu z normalizera (akceptować `thread,` lub `thread.`), żeby nie zmieniać treści widocznej dla użytkownika.

3. **Dokumentacja:** W opisie pipeline’u (np. w README lub wewnętrznej dokumentacji) zapisać, że „odpowiedź API” w logu to stan przed wstawieniem Prompt #2 i przed normalizacją Try-it-yourself.
