# Propozycje rozwiązań: placeholdery typu [Insert …] / [Brand Name] w artykułach

## Kontekst

- W **QA** (fill_articles) treść jest skanowana wzorcem `\[[^\]]+\]` (nawiasy kwadratowe, bez markdown linku `](url)`). Jeśli takie fragmenty zostaną, artykuł dostaje błąd **„bracket placeholders still present”** i nie przechodzi (refresh/fill fail).
- W **15 artykułach** z ostatniego refreshu przyczyną niepowodzenia były m.in. placeholdery typu: `[Insert total views here]`, `[Brand Name]`, `[Campaign Name]`, `[Your Company]` itd.
- Model często zostawia te frazy zamiast podstawić konkretny przykład lub usunąć.

Poniżej **warianty** działań (bez implementacji) oraz **rekomendacja**.

---

## Wariant 1: Doprecyzowanie prompu fill (instrukcje dla modelu)

**Opis:** W systemie lub w user message prompu fill (fill_articles) dodać jasną regułę:
- Każdy fragment w nawiasach kwadratowych typu `[Insert …]`, `[Brand Name]`, `[Your Company]` itp. **musi** być:
  - **albo** zastąpiony konkretnym przykładem (np. „Acme Corp”, „150 views”, „Q1 2026”),
  - **albo** usunięty (zdanie przepisane tak, żeby nie było placeholderu).
- Nie wolno zostawiać w tekście końcowym żadnych `[ … ]` oprócz rzeczywistych linków markdown `[text](url)`.

**Plusy:** Brak zmian w QA i w pipeline; model od razu ma produkować „czysty” tekst.  
**Minusy:** Model nie zawsze stosuje się do instrukcji; przy długich artykułach placeholdery mogą nadal się pojawić.

---

## Wariant 2: Przykłady w prompcie („few-shot”)

**Opis:** W bloku instrukcji dodać 1–2 krótkie przykłady:
- „Zamiast: *Update [Brand Name] in the dashboard* napisz: *Update Acme Corp in the dashboard* lub *Update your brand name in the dashboard*.”
- „Zamiast: *[Insert total views here]* użyj konkretnej liczby, np. *1,200*, lub przepisz zdanie bez placeholderu.”

**Plusy:** Model widzi wzorzec „placeholder → konkret / usunięcie”.  
**Minusy:** Zajmuje miejsce w kontekście; nadal zależne od dyscypliny modelu.

---

## Wariant 3: Post-processing po odpowiedzi modelu (przed QA)

**Opis:** Po otrzymaniu treści od API, przed zapisem i QA, uruchomić krok „czyszczenia”:
- Wykryć wszystkie dopasowania `\[[^\]]+\]` (z wyłączeniem `](url)`).
- Dla każdego: podstawić **słownikową** zamianę (np. `[Brand Name]` → „[Your Brand]” lub „Acme Corp”) **albo** usunąć cały fragment (np. zdanie z placeholderem skrócić / usunąć).
- Słownik można budować z listy znanych placeholderów z logów (np. `[Insert …]`, `[Brand Name]`, `[Your Company]`) + generyczne fallbacki.

**Plusy:** Niezależne od modelu; QA widzi już „oczyszczoną” treść.  
**Minusy:** Wymaga utrzymania słownika; ryzyko nienaturalnych podstawień lub usunięcia sensu; trzeba jasno zdefiniować, co „konkretny przykład” (np. czy „[Your Brand]” jest OK, czy QA dalej to odrzuca).

---

## Wariant 4: Drugie wywołanie API tylko dla placeholderów („patch” pass)

**Opis:** Po pierwszej odpowiedzi modelu:
- Skanować treść wzorcem placeholderów.
- Jeśli są – wysłać **drugie** zapytanie do API z fragmentem tekstu i listą znalezionych placeholderów, z instrukcją: „Zamień każdy z poniższych fragmentów na konkretny przykład lub przepisz zdanie tak, żeby go nie było; zwróć tylko poprawiony fragment/akapit.”
- Wstawić poprawiony fragment z powrotem do treści i dopiero wtedy uruchomić QA.

**Plusy:** Model celowo „dopina” tylko problematyczne miejsca.  
**Minusy:** Większy koszt (dodatkowe wywołania) i czas; skomplikowanie pipeline’u; ryzyko rozjazdu stylu.

---

## Wariant 5: Rozluźnienie QA (whitelist / próg)

**Opis:**
- **5a)** Whitelist: zdefiniować listę dozwolonych wzorców `[...]` (np. tylko `[1]`, `[2]` w listach odwołań), które QA ignoruje; reszta nadal = fail.
- **5b)** Próg: nie failować, jeśli liczba placeholderów ≤ N (np. 1–2) lub jeśli występują tylko w określonych sekcjach (np. poza „Introduction” i „Conclusion”).

**Plusy:** Mniej fałów przy „prawie dobrych” artykułach.  
**Minusy:** Na stronie nadal mogą zostać mało profesjonalne „[Insert …]”; rozluźnienie może maskować problem zamiast go usuwać.

---

## Wariant 6: Kombinacja: prompt + opcjonalny post-processing

**Opis:**
- **Głównie:** Wariant 1 (i ewentualnie 2) – jasna reguła w prompcie + przykłady.
- **Fallback:** Jeśli po odpowiedzi modelu QA nadal zgłasza „bracket placeholders still present”, uruchomić **lekki** post-processing (Wariant 3): tylko dla znanych z logów fraz (np. `[Brand Name]`, `[Insert …]`) podstawić jeden ustalony przykład (np. „your brand”, „X”) lub krótkie zdanie bez placeholderu – **bez** drugiego wywołania API.

**Plusy:** Priorytet u źródła (model); post-processing tylko w razie potrzeby, z wąskim zakresem.  
**Minusy:** Trzeba zdefiniować listę „znanych” placeholderów i reguły podstawiania.

---

## Rekomendacja

**Rekomendowane:** **Wariant 6 (kombinacja), z naciskiem na Wariant 1 i 2.**

1. **Najpierw:** Doprecyzować **prompt fill** (Wariant 1): jedna wyraźna zasada – „wszystkie placeholdery w nawiasach kwadratowych [ … ] muszą być zastąpione konkretnymi przykładami lub usunięte; niedopuszczalne zostawianie [Insert …], [Brand Name] itp. w końcowej treści”.
2. **Dodatkowo:** Wstawić **1–2 krótkie przykłady** w instrukcji (Wariant 2), np. zamiana `[Brand Name]` na „Acme Corp” lub „your brand name”.
3. **Opcjonalnie na później:** Dodać **lekki post-processing** (Wariant 3) tylko dla powtarzających się w logach fraz, z prostymi zamianami (np. lista 10–20 wyrażeń → jeden generyczny zamiennik lub usunięcie), **bez** drugiego wywołania API. Uruchamiać go tylko gdy QA i tak by nie przeszła z powodu placeholderów – żeby nie zmieniać treści, która już jest dobra.

**Nie rekomendowane** na start: czyste rozluźnienie QA (Wariant 5) bez wymagania czystej treści oraz drugie wywołanie API „patch” (Wariant 4) ze względu na koszt i złożoność.

---

*Dokument tylko propozycją; bez implementacji do momentu zatwierdzenia.*
