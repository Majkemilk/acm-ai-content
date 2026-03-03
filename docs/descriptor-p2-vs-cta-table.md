# Descriptor nad Prompt #2 vs treści zachęty (CTA) po drugim bloku

Descriptor przed drugim blokiem kodu jest **jednolity dla wszystkich rodzajów artykułów** (how-to, guide, best, comparison).  
Składa się z:
- **pierwszego zdania** w stylu „przykładowy output zwracany przez AI”;
- **drugiego zdania**: możesz kontynuować w tym samym wątku czatu **lub** kontynuować workflow zgodnie z instrukcjami poniżej, **używając wskazanych narzędzi** — lista narzędzi jest dynamicznie budowana z treści Prompt #1 (patrz niżej).

W tekście descriptora **nie ma** odniesień do „Prompt #2”, „wklejania”, „uruchamiania Prompt #2”.  
Zachęta do użycia w konkretnym narzędziu `{tool}` lub w innym narzędziu tego samego typu `({type})` jest **wyłącznie w CTA po drugim bloku**, nie w descriptorze.

---

## Skąd biorą się „wskazane narzędzia” w descriptorze (`{tools_phrase}`)

1. **Źródło nazw:** z treści **Prompt #1** (pierwszego bloku kodu w sekcji Try it yourself):
   - linia **Recommended tools:** (split po przecinku/średniku),
   - oraz wszystkie nazwy z listy afiliacyjnej (`affiliate_tools.yaml`), które występują w tekście Prompt #1.
2. **Dopasowanie do listy afiliacyjnej:** każda wyciągnięta nazwa jest porównywana z listą narzędzi (exact / case-insensitive).  
   - **Dopasowanie:** w descriptorze wstawiany jest **link** do narzędzia + **etykieta** (opis z „List of platforms and tools” / `short_description_en` z YAML).  
   - **Brak dopasowania:** nazwa jest wstawiana jako **zwykły tekst** (bez linku).
3. **Format frazy:** np. „ChatGPT (General AI chat), Make (Automation platform) and OtherTool” — z linkami w HTML, w MD: `[ChatGPT](url) (General AI chat), ...`.  
   Gdy nie wykryto żadnych narzędzi, używany jest fallback: „the tools mentioned in the prompt above”.

---

## Lista wariantów descriptora: `_DESCRIPTOR_P2_VARIANTS` (z `{tools_phrase}`)

Placeholder `{tools_phrase}` jest podstawiany wygenerowaną frazą (linki + etykiety lub zwykły tekst, jak wyżej).  
Wybór wariantu: deterministycznie po slugu artykułu (klucz `try-descriptor-p2`).

| # | Tekst descriptora (szablon z {tools_phrase}) |
|---|---------------------------------------------|
| 1 | Below is example output from the AI. You can continue in the same chat thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 2 | This is sample output the AI returns. You may continue in the same thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 3 | Here is example output from the AI. Continue in the same chat thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 4 | The AI returns output like this. You can keep working in the same chat thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 5 | Below is sample output from the AI tool. You may continue in the same thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 6 | This is example output the AI returns. Continue in the same chat thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 7 | Here is the kind of output the AI can return. You can continue in the same chat thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 8 | The following is example output from the AI. You may continue in the same thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 9 | Below is example output the AI returns. Continue in the same chat thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 10 | This is sample output from the AI. You can work in the same thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 11 | Here is example output the AI can produce. You may continue in the same chat thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 12 | The AI can return output like this. Continue in the same thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 13 | Below is the kind of output the AI returns. You can continue in the same chat thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 14 | This is example output from the AI tool. You may continue in the same thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 15 | Here is sample output the AI returns. You can continue in the same chat thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 16 | The following is sample output from the AI. Continue in the same thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 17 | Below is example output the AI can return. You may continue in the same chat thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 18 | This is the kind of output the AI returns. You can keep working in the same thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |
| 19 | Here is example output from the AI. You may continue in the same chat thread or follow the workflow below using the indicated tools: {tools_phrase}. |
| 20 | The AI returns sample output like this. Continue in the same thread or continue the workflow according to the instructions below using the indicated tools: {tools_phrase}. |

---

## CTA po drugim bloku

Dla **wszystkich** typów artykułów (HTML i MD) używana jest jedna lista: **`_CTA_AFTER_P2_VARIANTS`**.  
Placeholdery: `{tool}` = narzędzie (w HTML z linkiem), `{type}` = etykieta typu (np. „General AI chat” lub short description z listy).  
Przykłady: „Use it in {tool} or in another tool of the same type ({type}) and iterate on the result.”, „Continue the workflow in {tool} or in another tool of the same type ({type}).”

---

## Podsumowanie zmian (implementacja)

- **Descriptor nad Prompt #2:**  
  - Pierwsze zdanie bez zmian (styl „example output from the AI”).  
  - Drugie zdanie: zamiast samej frazy „continue in the same chat thread or start a new conversation” jest **„continue in the same chat thread or continue/follow the workflow according to the instructions below using the indicated tools: {tools_phrase}”**.  
  - `{tools_phrase}`: budowane z treści Prompt #1 — wyciągane nazwy z linii „Recommended tools” oraz z całego tekstu (dopasowanie do listy afiliacyjnej); przy dopasowaniu: link + etykieta z List of platforms and tools, przy braku dopasowania: zwykły tekst.  
  - W descriptorze **nie ma** już `{tool}` ani `{type}` — te są tylko w CTA po bloku.

- **Nowe funkcje w `fill_articles.py`:**  
  - `_get_prompt1_text_from_section(section, is_html)` — ekstrakcja tekstu pierwszego bloku kodu (HTML `<pre>` lub MD ```).  
  - `_extract_tools_from_prompt1(prompt1_text)` — zwraca listę par (display_name, (name, url, short_desc) | None).  
  - `_build_tools_phrase_html(items)` / `_build_tools_phrase_md(items)` — budowa frazy z linkami i etykietami lub zwykłym tekstem; fallback „the tools mentioned in the prompt above” gdy brak narzędzi.

- **CTA po drugim bloku:** jedna lista `_CTA_AFTER_P2_VARIANTS` dla wszystkich typów (how-to, guide, best, comparison) i dla HTML oraz MD.

- **Reruns:** w HTML usuwane są poprzednio wstrzyknięte paragrafy descriptora (wzorce „example output from the AI” + „continue in the same chat thread” / „using the indicated tools”), żeby uniknąć duplikatów.
