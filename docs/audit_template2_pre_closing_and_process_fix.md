# Audyt: błąd Template 2 </p> zamiast </pre> oraz naprawa procesu

## 1. Diagnoza błędu

### Objaw
W sekcji **„Try it yourself”** pierwszy blok `<pre>` (Prompt #1) wyświetlał **dodatkową treść** – m.in. nagłówek „Try it yourself”, opis, a nawet fragment Prompta #2. W efekcie „sekcja 1” nie zawierała wyłącznie treści Prompta #1.

### Przyczyna
W sekcji **Template 2** model zamykał blok z workflow sentence (`Human → Prompt #1 (to AI chat) → …`) tagiem **`</p>`** zamiast **`</pre>`**. Skutek:

- Blok `<pre>` w Template 2 nie był zamknięty.
- Kolejne fragmenty HTML (w tym cała sekcja „Try it yourself” i pierwszy prawdziwy `<pre>` z Promptem #1) traktowane były jako **zawartość tego samego, niezamkniętego `<pre>`**.
- Przeglądarka „zlewała” to w jeden blok, więc wizualnie wyglądało to jak obca treść wewnątrz Prompta #1.

To **ten sam typ błędu** co wcześniej (stray `</p>` zamiast `</pre>` w Template 2).

### Ostatnie wystąpienia (2026-02-28)
Skrypt `check_try_it_yourself_pre.py` wykrył 3 artykuły z tym błędem:

- `2026-02-28-comparison-of-scale-unique-bicycle-identification-processes-within-marketing-automation-frameworks.audience_professional.html`
- `2026-02-28-how-to-implement-unique-bicycle-identification-systems-in-marketing-automation-tools.audience_beginner.html`
- `2026-02-28-how-to-optimize-client-engagement-strategies-using-unique-bicycle-identification-systems.audience_professional.html`

Wszystkie trzy zostały naprawione skryptem **`fix_template2_pre_close.py`** (zamiana błędnego `</p>` na `</pre>` w bloku Template 2).

---

## 2. Dlaczego sanitacja nie zapobiegła błędu

- **`_sanitize_pre_blocks_html`** działa na **parach** `<pre>…</pre>` (regex `r'<pre([^>]*)>(.*?)</pre>'`).
- Gdy w Template 2 jest `<pre>…</p>` (bez `</pre>`), ten blok **nie** tworzy pary z żadnym `</pre>`.
- Następny `</pre>` w dokumencie zamyka **pierwszy** otwarty `<pre>` (np. w Try it yourself), więc regex „zbiera” do jednego bloku zawartość od Template 2 aż do tego `</pre>`.
- Sanitacja nie może poprawnie naprawić struktury, bo opiera się na już poprawnych parach; przy zepsutej strukturze sama staje się nieprzewidywalna.
- **`_validate_html_pre_blocks`** liczy `<pre` i `</pre>` – przy jednym niezamkniętym `<pre>` wykrywa nierównowagę i może zwrócić błąd. Mimo to artykuły z 2026-02-28 zostały zapisane – np. przy wyłączonym quality gate lub innym wariancie ścieżki (np. bez retry przy fail).

---

## 3. Wdrożone poprawki

### 3.1 Naprawa 3 ostatnio wygenerowanych artykułów
Uruchomiono **`fix_template2_pre_close.py`** – w każdym z 3 plików HTML w `content/articles/` zamieniono błędne `</p>` na `</pre>` w bloku Template 2 (wzorzec: `<pre class="bg-gray-100...">Human → Prompt #1 (to AI chat) → … </p>` → `… </pre>`).

### 3.2 Korekta w pipeline (fill_articles.py)

1. **Funkcja `_fix_template2_pre_closing(body)`**  
   - Wykonuje tę samą zamianę co skrypt fix (regex: Template 2 `<pre>…Human → Prompt #1…` zakończony `</p>` → `</pre>`).  
   - Zwraca `(new_body, was_fixed)`.

2. **Miejsce wywołania**  
   - Dla ścieżki z **quality gate** (retry) i dla ścieżki **bez quality gate**:  
     zaraz po podstawieniu placeholderów i **przed** `_sanitize_pre_blocks_html` wywoływane jest `_fix_template2_pre_closing(new_body)`.  
   - Dalsze kroki (sanitacja, walidacja, zapis) działają już na skorygowanym HTML.

3. **Efekt**  
   - Każda nowa odpowiedź API w trybie HTML jest **najpierw** korygowana pod kątem Template 2, potem sanitowana i walidowana.  
   - Nawet jeśli model znowu zwróci `</p>`, zapis do `.html` będzie miał poprawne `</pre>`.

### 3.3 Doprecyzowanie instrukcji w prompcie (HTML)
W bloku instrukcji dla generowania HTML (Template 1 / Template 2) dodano:

- „Every `<pre>` block MUST be closed with `</pre>`, never with `</p>`.”
- „In Template 2, the workflow sentence (Human → Prompt #1 → …) goes inside a single `<pre>…</pre>` block; close that block with `</pre>` only.”

Ma to ograniczyć powtarzanie się błędu po stronie modelu.

---

## 4. Propozycja dalszego usprawnienia procesu (MD + HTML)

### 4.1 Obecny stan
- **HTML:**  
  - Korekta Template 2 w pipeline (już wdrożona).  
  - Sanitacja i walidacja `<pre>`.  
  - Jasna instrukcja w prompcie o zamykaniu `<pre>` przez `</pre>`.

- **Markdown (.md):**  
  - W szkieletach sekcja „Try it yourself” może używać bloków kodu (triple backticks).  
  - Brak ekwiwalentu błędu „</p> zamiast </pre>” w czystym MD; ewentualny problem to np. niezamknięty blok ``` (brak drugiego ```).  
  - W obecnym flow **fill z `--html`** generuje od razu body w HTML i zapisuje do `.html`; `.md` dostaje tylko aktualizację statusu. W praktyce problem dotyczył wyłącznie HTML.

### 4.2 Rekomendacje

1. **Przy każdym fill z `--html`**  
   - Pipeline już stosuje `_fix_template2_pre_closing` przed sanitacją i zapisem – **utrzymać** ten porządek i nie pomijać tego kroku.

2. **Quality gate**  
   - Przy włączonym quality gate i `use_html` upewnić się, że **zawsze** wywoływane są `_fix_template2_pre_closing` → `_sanitize_pre_blocks_html` → `_validate_html_pre_blocks` i że przy nierównowadze `<pre>`/`</pre>` artykuł **nie** jest zapisywany (retry lub blocked). Obecna logika to robi; warto to zostawić jako obowiązkową ścieżkę dla HTML.

3. **Monitoring**  
   - Okresowo uruchamiać **`check_try_it_yourself_pre.py`** na `content/articles` i ewentualnie na `public/articles` (np. po renderze), żeby szybko wykryć ewentualne nowe wystąpienia (np. po zmianie modelu lub promptu).

4. **Markdown**  
   - Jeśli w przyszłości będzie używane wypełnianie **wyłącznie do .md** (bez HTML), dodać analogiczną regułę: bloki kodu muszą być zamknięte drugim ``` i ewentualnie prostą korektą/walidacją w pipeline dla MD.

5. **Dokumentacja**  
   - W HANDOFF lub w instrukcji dla developera opisać, że „Template 2 workflow sentence musi być w `<pre>…</pre>`; model czasem zamyka `</p>` – pipeline to koryguje w `fill_articles`”.

---

## 5. Podsumowanie

| Działanie | Status |
|-----------|--------|
| Naprawa 3 ostatnich artykułów (Template 2 `</p>` → `</pre>`) | Wykonane (`fix_template2_pre_close.py`) |
| Korekta w pipeline przed sanitacją (`_fix_template2_pre_closing`) | Wdrożona w `fill_articles.py` |
| Doprecyzowanie instrukcji w prompcie HTML | Wdrożone |
| Propozycja procesu (quality gate, monitoring, MD) | Opisana powyżej |

Dzięki temu zarówno **istniejące** 3 artykuły są poprawione, jak i **nowe** generowane do `.html` przechodzą przez automatyczną korektę Template 2 i wyraźną instrukcję, co powinno zapobiec ponownemu pojawianiu się tego błędu w treści.
