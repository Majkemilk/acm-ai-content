# Analiza: 8 niepowodzeń po odświeżaniu (po wdrożeniu R1+R2)

## Kontekst

- **Wynik odświeżania:** Refreshed: 32, Failed: 8, Skipped (up to date): 15.
- **Failure breakdown:** 5 × bracket placeholders, 2 × word count, 2 × deterministic/quality.
- **Źródło:** `logs/errors.log`, ostatnie wpisy z 2026-02-23 (ok. 22:41–23:09) oraz wcześniejsze z tego samego dnia odpowiadające tym samym artykułom.

Po wdrożeniu R1 (sanityzacja przed QA, w tym nagłówki) i R2 (prompt: zakaz fraz w nagłówkach) **„the best”** przestał być przyczyną failed – odświeżanie z tego samego zakresu dało 32 sukcesy zamiast 1. Pozostałe 8 failed wynika z innych reguł QA.

---

## 1. Bracket placeholders (5 wystąpień w breakdown)

### Z logów (przykłady)

- `[Insert Video Title Here]` – pojedynczy placeholder w treści.
- `[insert project theme, e.g., a new product launch]`, `[insert deadline, e.g., two weeks from start date]` – instrukcje w nawiasach zamiast konkretów.
- `[Brand Name]`, `[specific product or service]`, `[@BrandHandle]`, `[YourBrandHashtag]` – szablonowe etykiety.
- `[App Name]`, `[App Name]` – powtórzony placeholder.
- `[specify timeframe, e.g., month, week]`, `[list your specific keywords]` – wskazówki dla użytkownika zamiast wypełnionej treści.

### Dlaczego powstają

- Prompt wyraźnie każe **zastępować** wszystkie `[instruction or hint]` **konkretną** treścią i zabrania zostawiać tokeny w nawiasach. Mimo to model czasem:
  - traktuje fragment jako „szablon do wypełnienia przez czytelnika” i zostawia `[Insert X]` / `[Brand Name]` itd.;
  - wstawia **nowe** placeholdery w przykładach (np. w blokach kodu lub listach);
  - kopiuje styl instrukcji z szkieletu (`[specify…]`, `[list…]`) zamiast je rozwinąć w gotowy tekst.
- W artykułach HTML (refresh z `--html`) te same zasady obowiązują; QA sprawdza cały body (po strip tagów) i odrzuca, jeśli wykryje `[coś]` niebędące linkiem ani checkboxem.

### Wniosek

Przyczyna leży po stronie **zachowania modelu** (niespełnienie instrukcji „replace with concrete”), a nie braku reguły. QA słusznie blokuje publikację treści z niewypełnionymi placeholderami.

---

## 2. Word count (2)

### Z logów

- `word count 597 < 650 (audience: default)` – artykuł porównawczy (veed vs submagic vs opus-clip).
- `word count 623 < 650 (audience: beginner)` – best-implement-chatbots.

### Dlaczego powstają

- Dla audience **beginner** (i default) próg to 650 słów (strict). Model generuje nieco krótszą treść (ok. 600–620 słów), np. zwięzłe porównanie lub krótszą sekcję „Try it yourself”.
- Refresh używa `--min-words-override 650`, więc próg jest jednolity; przy 2–3 retries model nie zawsze „dobija” do 650.

### Wniosek

To **niewielkie niedobory długości** (kilkadziesiąt słów). Reguła długości jest sensowna; ewentualna decyzja to czy dla **refresh** akceptować lekko niższy próg (np. 600) albo dać w UI override tylko dla odświeżania – to kwestia polityki, nie błędu w kodzie.

---

## 3. Deterministic / quality (2)

### Z logów

- `missing deterministic Prompt #1 descriptor line; missing deterministic CTA line after Prompt #2` (how-to-automate-troubleshooting-workflows).
- Wcześniej też: `missing deterministic Prompt #1 descriptor line; missing deterministic Prompt #2 descriptor line; missing deterministic CTA line after Prompt #2` (guide-to-how-to-develop-troubleshooting-processes).
- Jeden wpis: `Quality gate fail: 'Try it yourself' section missing Prompt #1 (meta-prompt)`.

### Dlaczego powstają

- W artykułach **HTML** sekcja „Try it yourself” musi zawierać **sztywne frazy** (regex w QA), np.:
  - „Here is the input (Prompt #1) ready to use with … (AI tool).”
  - „The AI returns the following output (Prompt #2)…”
  - „Action cue:”
- Model czasem:
  - parafrazuje te zdania (inny szyk, słowa), przez co regex nie łapie;
  - pomija „Action cue” albo jeden z descriptorów;
  - w ogóle nie dodaje sekcji „Try it yourself” w wymaganej formie (quality gate).

### Wniosek

Wymóg **deterministycznego** formatu ma na celu spójność i ewentualne parsowanie; jest świadomą decyzją. Fail oznacza, że **output modelu nie spełnia tego formatu** – albo prompt pod kątem „Try it yourself” trzeba doprecyzować (wzór zdania, obowiązkowe „Action cue”), albo zaakceptować, że część artykułów przy pierwszym odświeżeniu nie przejdzie i wymaga ponowienia / ręcznej korekty.

---

## 4. Wnioski ogólne

1. **R1+R2 są skuteczne:** Usunięcie „the best” (i sanityzacja przed QA) radykalnie zmniejszyło liczbę failed (z 39 do 8) przy tym samym typie odświeżania. Nie ma powodu wycofywać tych zmian.

2. **Bracket placeholders** to główna pozostała przyczyna (5 z 8). Model nadal zostawia lub dodaje `[Placeholder]` / `[Insert X]` mimo jasnej instrukcji. Można to adresować tylko po stronie promptu (mocniejszy nacisk, więcej przykładów „zastąp X przez Y”) lub ewentualnie rozszerzeniem listy „known placeholders” do auto-zamiany przed QA – bez zmiany samej reguły QA.

3. **Word count** – marginalnie (2). Progi są czytelne; ewentualna elastyczność tylko dla refresh (np. 600 zamiast 650) to decyzja produktowa.

4. **Deterministic/quality** – 2 failed. Wymóg sztywnego formatu „Try it yourself” jest celowy; fail oznacza niespełnienie tego formatu przez model. Opcje: doprecyzować prompt (wzór zdania, obowiązkowe „Action cue”) albo traktować te artykuły jako do ponowienia / ręcznej poprawki.

5. **Zakres dat i dry run:** To, że artykuły pojawiły się dopiero po dodaniu dzisiejszego dnia do zakresu, potwierdza wcześniejszą diagnozę: albo wcześniej `last_updated` było poza zakresem, albo UI nie przekazywało dat. Włączenie „dzisiaj” lub statusu „blocked” + today pozwala łapać też te artykuły, które wcześniej failowały i mają już dzisiejszą datę – to spójne z ostatnimi zmianami w `find_articles_in_date_range`.

---

## 5. Rekomendacje (bez zmian w kodzie)

| # | Rekomendacja | Uzasadnienie |
|---|--------------|--------------|
| 1 | **Nie osłabiać QA** | Reguły bracket placeholders, word count i deterministic są uzasadnione. Obecne 8 failed to akceptowalny poziom przy 32 sukcesach. |
| 2 | **Bracket placeholders** | W kolejnej iteracji promptu (fill_articles / szablony HTML): wzmocnić jedną–dwie zdaniową regułę w stylu „Never output [Insert X], [Brand Name], or any [bracket] text; always replace with a concrete example (e.g. real name, real product, real date).” Opcjonalnie: rozważyć rozszerzenie listy „known” placeholderów do automatycznej zamiany przed QA tylko tam, gdzie da się to zrobić bez utraty sensu. |
| 3 | **Word count** | Na razie zostawić progi. Jeśli w kolejnych batchach często będzie 2–3 failed tylko z powodu 10–50 słów, rozważyć osobno: lekki obniżenie progu dla trybu refresh (np. 600) lub opcję w UI „min words dla tego odświeżania”. |
| 4 | **Deterministic / Try it yourself** | W promptach HTML: dodać jawny wzór zdania dla „Prompt #1” i „Prompt #2” oraz wymóg linii „Action cue:”. Ewentualnie w dokumentacji wewnętrznej opisać, że artykuły z tym błędem można ponowić („Ponów tylko nieudane”) lub poprawić ręcznie sekcję. |
| 5 | **Kontynuować raport breakdown** | Failure breakdown (R4) ułatwia decyzje – widać, że teraz dominują placeholdery, a nie „the best”. Warto go nadal używać przy kolejnych odświeżeniach. |

---

## 6. Podsumowanie

- **Przyczyny 8 failed:** (1) Model zostawia lub dodaje placeholdery w nawiasach `[ … ]` mimo instrukcji. (2) Dwa artykuły nieznacznie poniżej progu słów (597, 623 < 650). (3) Dwa artykuły bez wymaganego, sztywnego formatu sekcji „Try it yourself” (brak descriptorów Prompt #1/#2 lub „Action cue”).
- **Wnioski:** R1+R2 działają; pozostałe błędy wynikają z ograniczeń modelu względem obecnych reguł, a nie z błędów w pipeline. Nie rekomenduje się zmiany kodu na tym etapie; rekomenduje się ewentualne doprecyzowanie promptów (placeholdery, Try it yourself) i ewentualną politykę progu słów/refresh w kolejnej iteracji.
