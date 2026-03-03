# Podsumowanie: zmiana nazewnictwa poziomów → standard / advanced / expert

## Wdrożone zmiany

- **Wartości poziomu:** `basic` → `standard`, `standard` → `advanced`, `expert` bez zmiany.
- **Pliki:** `lib/metaPrompt.ts`, `lib/form-schema.ts`, `app/api/get-prompt/route.ts`, `app/page.tsx`. `app/api/create-checkout/route.ts` korzysta z tych samych wartości przez formularz i `LEVEL_CENTS`.
- **Lista miejsc:** `prompt-generator/docs/LEVEL_RENAME_LIST.md`.

Stripe nie jest jeszcze w użyciu; metadata w checkout będzie zawierać `level: "standard" | "advanced" | "expert"`.

---

## Zagrożenia

1. **Stare linki / zapisane dane**  
   Jeśli gdziekolwiek (np. w e-mailach, CRM, logach) zapisano poziom jako `basic` lub stary `standard`, po wdrożeniu te wartości nie będą już rozpoznawane przez API. Dla nowego wdrożenia bez użytkowników ryzyko zerowe.

2. **Nazwa „BASIC ZERO-LIE” w meta-promptcie Advanced**  
   W treści `META_PROMPT_ADVANCED` nadal jest zwrot „BASIC ZERO-LIE” (z oryginalnego poziomu standard). To nazwa zestawu zasad, nie poziomu produktu – może być mylące przy czytaniu kodu. Można w przyszłości zmienić na np. „ZERO-LIE (core)” lub zostawić jako historyczne.

3. **Stałe `FORMAT_OPTIONS_STANDARD` / `FORMAT_OPTIONS_EXPERT` w `page.tsx`**  
   Odnoszą się do zestawu opcji formatu (standardowy vs rozszerzony), nie do poziomu produktu. Nazwy są w porządku; ewentualnie w przyszłości: `FORMAT_OPTIONS_DEFAULT` i `FORMAT_OPTIONS_EXTENDED`, żeby uniknąć skojarzenia z poziomem „Standard”.

4. **Domyślny poziom w API**  
   W `get-prompt/route.ts` domyślna wartość `metadata.level` to `"standard"`. To nadal poziom wejściowy (€0.50), zachowanie jest poprawne.

---

## Sugestie ulepszeń

1. **Testy**  
   Dodać testy (np. Vitest/Jest) dla: walidacji `level` w form-schema, mapowania level → meta-prompt i `LEVEL_CENTS` w API, żeby kolejna zmiana nie zepsuła któregoś poziomu.

2. **Jedno źródło prawdy dla etykiet**  
   Opisy poziomów („Quick, concise…”) są w `LEVEL_DESCRIPTIONS` w `page.tsx`. Jeśli kiedyś pojawią się też w e-mailach lub Stripe product description, warto wyciągnąć je do współdzielonego modułu (np. `lib/levels.ts`) z eksportem `LEVEL_LABELS`, `LEVEL_DESCRIPTIONS`, `LEVEL_CENTS`, żeby copy było spójne.

3. **Dokumentacja dla Stripe**  
   Przy wdrażaniu Stripe (Products/Prices) ustawić nazwy i opisy produktów zgodnie z `standard` / `advanced` / `expert` i etykietami z aplikacji, żeby raporty i receipt były spójne z UI.

4. **Komentarz w `metaPrompt.ts`**  
   Na górze pliku krótko opisać mapowanie: poziom „standard” = najprostszy meta-prompt, „advanced” = rozszerzony, „expert” = pełny ZERO-LIE + HIGH-RISK, żeby kolejni developerzy nie mylili nazw stałych z poziomami produktu.

---

## Weryfikacja

- TypeScript: brak błędów (lint).
- Logika: audience, format i constraints wymagane dla `advanced` i `expert`; tylko `expert` wymaga facts + acknowledgement; domyślny poziom formularza i fallback w API = `standard`.
