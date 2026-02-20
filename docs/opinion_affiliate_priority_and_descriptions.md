# Opinia: priorytetyzacja linków afiliacyjnych i opisy narzędzi w instrukcjach dla AI

## Podsumowanie

**Pomysł jest sensowny i warto go wdrożyć.** Priorytetyzacja linków afiliacyjnych oraz krótkie opisy przy linkach poprawiają konwersję, UX i SEO. Analiza techniczna trafnie wskazuje kierunek i ryzyka; poniżej jest co potwierdzam, co uzupełniam i z czym polemizuję.

---

## 1. Cel i zasady (Twoje priorytety)

- **Priorytet 1:** W danym miejscu w artykule, spośród narzędzi o zbliżonym działaniu pasujących do kontekstu – wybierać narzędzia z linkiem afiliacyjnym (np. `?via=d9d7c5`) zamiast zwykłego URL (np. `https://pictory.ai/`).
- **Priorytet 2:** Gdy żadne narzędzie afiliacyjne nie pasuje – wybierać najlepsze (wg wiedzy modelu) spośród pasujących narzędzi z linkami ogólnymi.
- **Wspólna zasada:** Przy każdym linkowanym narzędziu – w nawiasie krótki, treściwy opis po angielsku, np. *Pictory (AI video from text)*.

To da się sensownie zapisać w instrukcjach dla API i w danych wejściowych (listy narzędzi).

---

## 2. Ocena analizy techniczna

### Zgadzam się

- **Dwie listy (A = afiliacyjne, B = ogólne)** – czytelne dla modelu i łatwe w utrzymaniu. Instrukcja w stylu: „preferuj narzędzia z listy A; jeśli brak dobrego dopasowania, użyj z listy B” jest zrozumiała.
- **Konflikt z renderowaniem** – słusznie: dla **artykułów HTML** `render_site.py` w ogóle nie wywołuje `replace_tool_names_with_links` (logika jest w gałęzi `else`, tylko dla MD). Dla HTML linki pochodzą wyłącznie z AI, więc nie ma nadpisywania. Dla **MD** to render dziś wstawia linki; jeśli w przyszłości AI też będzie wstawiać linki w MD, trzeba będzie albo nie uruchamiać replace dla tego trybu, albo ujednolicić źródło linków.
- **Opisy – ryzyko halucynacji** – realne. Ograniczenie do faktów (kategoria, główne zastosowanie) i sugestia w prompcie („jeśli nie znasz opisu, użyj ogólnego np. *AI tool for …*”) to dobre zabezpieczenie.
- **Ewolucyjne wdrożenie i zabezpieczenia** – rozsądne.

### Uzupełnienia / krytyka

- **„Lista A vs lista B”** – w YAML masz jedną listę; każdy wpis ma jeden `affiliate_link`. Aby mieć A vs B, trzeba **wyznaczyć afiliacyjność po URL** (np. zawiera `?via=`, `?ref=`, `affiliate`, itd.) i w `fill_articles.py` dzielić narzędzia na dwie listy przed zbudowaniem promptu. To nie wymaga zmiany struktury YAML – wystarczy konwencja: link z parametrem = afiliacyjny.
- **Gdzie dokładnie opisy** – analiza sugeruje „pierwsze wystąpienie lub sekcja Tools mentioned”. To dobre. Dodatkowo warto **explicite** w instrukcji napisać: „przy **pierwszym** wystąpieniu danego narzędzia w tekście użyj formy: *Nazwa (krótki opis)*, a w kolejnych wystąpieniach samo *Nazwa* (bez powtarzania opisu)”. Unikasz przeładowania i zachowujesz spójność z sekcją „List of AI tools”.
- **Konflikt render vs AI** – dla **HTML** nie ma konfliktu. Dla **MD** ewentualna zmiana to: „dla artykułów generowanych przez AI w trybie, który wstawia linki, nie uruchamiać `replace_tool_names_with_links`” albo „uruchamiać tylko tam, gdzie nie ma jeszcze żadnego linku do narzędzia”. To da się doprecyzować przy faktycznym wdrożeniu trybu MD z linkami od AI.

---

## 3. Wykonalność w kodzie

| Element | Gdzie | Trudność |
|--------|--------|----------|
| Klasyfikacja URL: afiliacyjny vs ogólny | `fill_articles.py` (przy ładowaniu / budowaniu list) | Niska – heurystyka na URL (parametry zapytania, ścieżka). |
| Dwie listy w prompcie | `_build_html_prompt` | Niska – osobne bloki tekstowe „Affiliate tools (prefer when context fits): …” i „Other tools (use if no affiliate match): …”. |
| Instrukcja priorytetów | Ten sam prompt | Niska – 2–3 zdania w stylu analizy. |
| Opis przy pierwszym wystąpieniu | Instrukcja dla AI | Średnia – model musi rozpoznać „pierwsze wystąpienie” i dodać nawias; warto dać przykład w prompcie. |
| Sekcja „List of AI tools” | Już jest; opisy już wymagane | Brak zmiany – tylko spójność z nową zasadą (język angielski, krótko). |

Brak konieczności zmiany `render_site.py` dla trybu HTML.

---

## 4. Ryzyka i ograniczenia

- **Jakość dopasowania kontekstu** – model może błędnie uznać narzędzie za „pasujące” i wstawić link afiliacyjny tam, gdzie merytorycznie lepsze byłoby inne. Można to ograniczyć: w instrukcji wyraźnie napisać, że priorytet afiliacyjny stosować **tylko gdy** narzędzie jest rzeczywiście trafne do zdania/akapitu (inaczej wybrać najlepsze z listy B).
- **Halucynacje opisów** – jak w analizie: krótkie, ogólne opisy + fallback „AI tool for [category]” zmniejszają ryzyko. Opcjonalnie w YAML można dodać pole `short_description_en` i przekazywać je do promptu (wtedy model tylko wkleja, nie wymyśla).
- **Długość odpowiedzi / koszt API** – marginalna; opisy to kilka słów na narzędzie.

---

## 5. Rekomendacja końcowa

1. **Wdrożyć** priorytetyzację (lista afiliacyjna vs ogólna) i jasną instrukcję w prompcie – bez zmian w `render_site.py` dla HTML.
2. **Wprowadzić** zasadę opisu w nawiasie przy **pierwszym** wystąpieniu każdego narzędzia (angielski, jednym zdaniem); w sekcji „List of AI tools” opisy już są – utrzymać spójność.
3. **Zdefiniować** w kodzie heurystykę „czy URL jest afiliacyjny” (np. `?via=`, `?ref=`, `ref=`, ścieżka `/ref/` itd.) i budować dwie listy z jednego `affiliate_tools.yaml`.
4. **Opcjonalnie** – dodać w YAML pole `short_description_en` i używać go w prompcie zamiast polegać wyłącznie na wiedzy modelu; wtedy mniejsza szansa na błędy i większa spójność z SEO.

Analizę techniczną oceniam jako trafną w diagnozie i kierunku; powyższe to doprecyzowanie implementacji (gdzie opisy, jak wyznaczyć A/B z obecnego YAML, brak konfliktu dla HTML) oraz małe rozszerzenie (opcjonalne opisy w YAML).
