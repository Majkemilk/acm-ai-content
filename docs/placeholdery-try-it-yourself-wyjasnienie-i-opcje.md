# Placeholdery a sekcja „Try it yourself” – wyjaśnienie i opcje naprawy

## Twój tok myślenia (i co z niego wynika)

Masz rację: **w blokach z promptami (Prompt #1, Prompt #2) w sekcji „Try it yourself” placeholdery typu [Insert …] czy [Your tool name] są często dopuszczalne albo nawet pożądane** – to gotowe szablony promptów, które czytelnik ma skopiować i uzupełnić. Wymaganie, żeby tam nie było żadnych `[ … ]`, może być zbyt ostre i powodować niepotrzebne fały QA.

Pytanie brzmi: **czy QA dziś w ogóle wyklucza te sekcje przy sprawdzaniu placeholderów?** Odpowiedź z kodu jest taka:

---

## Co robi QA dziś (w skrócie)

- Szuka w treści wszystkiego, co wygląda jak **placeholder w nawiasach kwadratowych** `[ … ]` (z wyłączeniem linków markdown `[tekst](url)` i checkboxów `[ ]`, `[x]`).
- Zanim to zliczy, **część treści jest usuwana**, żeby nie traktować jej jako „błędnego” placeholderu.

**Dla artykułów w formacie Markdown (.md):**

- Usuwane są sekcje **„Template 1:”** i **„Template 2:”**.
- Usuwane są **bloki w fenced code** (```…```) – czyli **cała zawartość Prompt #1 i Prompt #2** w „Try it yourself”.
- Komentarz w kodzie mówi wprost: *„Prompt #1 i Prompt #2 mogą legalnie zawierać [placeholder] tokeny”*.

**Wniosek dla MD:** placeholdery **wewnątrz** dwóch bloków kodu w „Try it yourself” **nie są** brane pod uwagę – QA ich nie sprawdza. Twój tok myślenia w przypadku **samego Markdowna** nie wyjaśnia więc fałów; tam problemem są placeholdery **poza** tymi blokami (w zwykłej prozie).

**Dla artykułów w formacie HTML (.html):**

- Do sprawdzenia używana jest treść po usunięciu **samych tagów** (`_strip_html_tags`): zostaje zwykły tekst, w tym to, co było wewnątrz `<pre>`, `<p>` itd.
- **Nie** ma żadnego usuwania sekcji „Try it yourself” ani bloków `<pre>…</pre>`.
- Czyli **zawartość Prompt #1 i Prompt #2 w HTML (w `<pre>`) jest dalej skanowana** i każdy `[Insert …]` / `[Brand Name]` itd. **jest liczony** i może dać „bracket placeholders still present”.

**Wniosek dla HTML:** tak – **problem jest związany ze sprawdzaniem treści w sekcjach z promptami w „Try it yourself”**. W HTML te bloki nie są wykluczane, więc placeholdery **dopuszczalne w promptach** mogą powodować fał QA.

Podsumowując:

- **MD:** placeholdery w „Try it yourself” (w ```) są już ignorowane; fały = placeholdery w **prozie**.
- **HTML:** placeholdery w „Try it yourself” (w `<pre>`) **nie** są ignorowane; fały mogą wynikać i z prozy, i z **treści promptów**.

---

## Dlaczego tak jest (ludzkim językiem)

- W **MD** bloki promptów są wyraźnie wydzielone (```…```), więc kod je po prostu **wyrzuca** z tekstu przed liczeniem placeholderów.
- W **HTML** nie ma odpowiednika tego kroku: po zrzuceniu tagów cała treść (w tym to, co w `<pre>`) trafia do jednego „worka” i jest skanowana. Nie ma reguły w stylu: „wszystko między nagłówkiem Try it yourself a następnym ##” albo „wszystko w `<pre>` pomiń”. Stąd niespójność: to, co w MD jest dozwolone (placeholdery w promptach), w HTML jest karane.

---

## Opcje naprawy (do wyboru do próby)

Poniżej opcje **bez implementacji** – tylko co można zrobić w kodzie/regułach.

### Opcja 1: Dla HTML – wykluczyć z sprawdzania treść sekcji „Try it yourself”

- **Pomysł:** Przed liczeniem placeholderów (dla `is_html`) usunąć z treści **całą sekcję** od nagłówka „Try it yourself” / „Build your own AI prompt” do następnego nagłówka wyższego poziomu (np. następne `<h2>` lub koniec sekcji).
- **Efekt:** Placeholdery w promptach (w tym w `<pre>`) nie będą już powodować fału. Nadal będą sprawdzane placeholdery w **reszcie** artykułu (proza).
- **Plusy:** Spójne z intencją „w promptach [ … ] są OK”; dopasowanie zachowania HTML do MD.
- **Minusy:** Trzeba pewnie określić regex / parser, który w HTML niezawodnie znajdzie tę sekcję (np. po `<h3>Try it yourself` i końcu na `<h2>`).

### Opcja 2: Dla HTML – wykluczyć z sprawdzania tylko bloki `<pre>…</pre>`

- **Pomysł:** Przed liczeniem placeholderów (dla `is_html`) usunąć z treści wszystkie fragmenty między `<pre …>` a `</pre>` (albo najpierw znormalizować tagi, potem wycinać).
- **Efekt:** Wszystko, co jest „w bloku kodu” (w tym oba prompty w Try it yourself), nie będzie skanowane. Placeholdery w zwykłej prozie (poza `<pre>`) dalej = fail.
- **Plusy:** Prostsze niż wycinanie całej sekcji; spójne z MD (tam też wycinamy „bloki kodu”).
- **Minusy:** Teoretycznie jakiś inny `<pre>` w artykule też by nie był sprawdzany (zwykle to akceptowalne).

### Opcja 3: Jedna wspólna reguła dla MD i HTML („wyklucz bloki kodu”)

- **Pomysł:** Przed liczeniem placeholderów zawsze:
  - w **MD** – usuwać ```…``` (jak teraz),
  - w **HTML** – usuwać treść wewnątrz `<pre>…</pre>` (np. po zamianie na „tekst do sprawdzenia”).
- **Efekt:** W obu formatach „bloki kodu” (prompty w Try it yourself i ewentualnie inne) nie uczestniczą w sprawdzaniu placeholderów.
- **Plusy:** Jedna zasada: „placeholdery w blokach kodu są dopuszczalne”.
- **Minusy:** Wymaga dopisania obsługi HTML (np. usuwania `<pre>…</pre>` przed przekazaniem do tego samego sprawdzenia).

### Opcja 4: Nie zmieniać QA, tylko prompty / treść

- **Pomysł:** Zostawić QA jak jest i wymagać w instrukcjach dla modelu, żeby **nawet w promptach** nie było `[Insert …]` / `[Brand Name]` – tylko konkretne przykłady lub neutralne etykiety bez nawiasów (np. „YOUR_BRAND_NAME”).
- **Efekt:** Mniej placeholderów wszędzie, w tym w Try it yourself; mniej fałów, ale prompty mogą być mniej „szablonowe”.
- **Plusy:** Brak zmian w kodzie QA.
- **Minusy:** Może być mniej naturalne dla czytelnika („wstaw [Brand Name]” jest zrozumiałe; „wstaw YOUR_BRAND_NAME” też, ale wymaga innej konwencji).

---

## Rekomendacja (co warto spróbować)

- **Najpierw:** **Opcja 2 lub 3** – dla ścieżki HTML **wykluczyć z sprawdzania placeholderów treść wewnątrz `<pre>…</pre>`** (albo zunifikować z MD: „bloki kodu nie są skanowane”). To bezpośrednio adresuje Twoją intuicję: placeholdery w sekcjach z promptami (Try it yourself) **są dopuszczalne**; problemem ma być tylko proza.
- **Dodatkowo (opcjonalnie):** W instrukcjach dla modelu krótko doprecyzować, że **poza** blokami promptów (poza ``` / `<pre>`) placeholdery `[ … ]` mają być zastępowane lub usuwane – żeby fały z „normalnej” prozy też spadły.

Dzięki temu:
- Nie karze się artykułów za dopuszczalne placeholdery w promptach.
- Zachowuje się wymóg czystej prozy w reszcie artykułu.
- Zachowuje się spójność MD vs HTML.

---

*Dokument tylko wyjaśnieniem i propozycją; bez implementacji do momentu zatwierdzenia.*
