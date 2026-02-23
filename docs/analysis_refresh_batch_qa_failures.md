# Analiza: odświeżanie dużej liczby artykułów – błędy QA (39 failed)

## Kontekst

- **Wynik odświeżania:** Refreshed: 1, Failed: 39, Skipped (up to date): 15 → **55 artykułów w scope**, zdecydowana większość odrzucona przez QA.
- **Źródło:** `logs/errors.log`, ostatni batch ok. 2026-02-23 21:26–22:01.

---

## 1. Rozkład przyczyn w ostatnim batchu (errors.log)

| Przyczyna | Szacowana liczba | Uwagi |
|-----------|------------------|--------|
| **forbidden pattern: the best** | **większość** (~35+) | Pojedynczo lub z innymi (word count, placeholdery). |
| word count poniżej progu | kilkanaście | professional 1000, intermediate 700, beginner 650. |
| bracket placeholders still present | kilka | `[Customer Name]`, `[Product]`, `[Y]` itd. |
| H2 headings missing: ## Verification policy | kilka | Sekcja usunięta przez model, przywracana w kodzie. |
| mustache removed ({{TOOLS_MENTIONED}} itd.) | kilka | Wcześniejsze runy (22–23.02). |
| forbidden: per month / unlimited / pricing / $ | po 1–2 | Często razem z "the best". |
| missing deterministic Prompt #1/#2 / CTA | po 1–2 | Try-it-yourself (HTML). |
| Quality gate fail (meta-prompt) | 1 | Inna reguła. |

**Wniosek:** Główny „bloker” to **„the best”** – model wielokrotnie wstawia tę frazę mimo instrukcji; QA konsekwentnie odrzuca.

---

## 2. Dlaczego „the best” nadal przechodzi do QA?

W `fill_articles.py`:

- **Sanityzacja** (`sanitize_filled_body`) zamienia w treści m.in. `the best` → `a strong option`, **ale tylko w liniach, które nie są nagłówkami** (linie zaczynające się od `#` są pomijane).
- **QA** (`run_preflight_qa`) sprawdza **cały** `filled_body` (w tym nagłówki) i używa tych samych wzorców co lista `FORBIDDEN_PATTERNS` (m.in. `\bthe best\b`).

Efekty:

1. **Nagłówki:** Np. `## The best tools for…` nigdy nie jest sanityzowany → QA wykrywa „the best” i fail.
2. **Sekcje przywracane:** Po wypełnieniu treści kod przywraca z oryginalnego body sekcje typu `## Verification policy (editors only)`. Ta przywrócona treść **nie przechodzi ponownie przez sanityzację**, więc ewentualne „the best” w szablonie oryginału trafia do QA.
3. **Brak drugiego przejścia:** Sanityzacja jest tylko zaraz po odpowiedzi API; wszystko, co później dopisywane (restore, Prompt #2, itd.) nie jest ponownie sanityzowane.

Stąd przy masowym odświeżaniu **ta sama** przyczyna („the best”) powtarza się w dziesiątkach artykułów.

---

## 3. Wnioski

1. **Jeden dominujący wzorzec:** „forbidden pattern: the best” odpowiada za większość z 39 failed. Redukcja tej jednej przyczyny znacząco obniży liczbę niepowodzeń.
2. **Sanityzacja nie obejmuje całej treści przed QA:** Obecna logika (sanityzacja tylko po API + pomijanie nagłówków + brak sanityzacji przywróconych bloków) powoduje, że część treści z zakazanymi frazami nie jest czyszczona przed `run_preflight_qa`.
3. **Progi słów i placeholdery:** Word count i `[placeholder]` też się pojawiają, ale w tym batchu są zwykle drugą przyczyną obok „the best”.
4. **Retries nie rozwiązują:** Przy 2–3 próbach model często znowu wstawia „the best” (w tym w nagłówkach), więc kolejne retry nie pomagają bez zmiany w pipeline.

---

## 4. Rekomendacje (do zatwierdzenia przed wdrożeniem)

### R1. Sanityzacja przed QA (rekomendacja główna)

- **Dodać jeden, wspólny krok sanityzacji** wykonywany **tuż przed** `run_preflight_qa`, na **całej** treści, która trafi do QA (np. na `new_body` / `filled_body` używanym w QA).
- W tym kroku stosować te same zamiany co w `sanitize_filled_body` („the best” → „a strong option”, „pricing” → „cost”, itd.), **włącznie z liniami nagłówkowymi** (usunąć wyjątek „skip heading lines”), tak aby QA nigdy nie widziało już „the best” / „pricing” itd. w tej samej formie co `FORBIDDEN_PATTERNS`.
- Opcjonalnie: zamiast drugiego pełnego przejścia, **rozszerzyć** obecne `sanitize_filled_body` o nagłówki (zamieniać zakazane frazy także w liniach zaczynających się od `#`) i **wywołać sanityzację ponownie** na końcu pipeline’u (na `new_body` po restore sekcji i po wszystkich wstawkach), zanim zbuduje się `new_content` i wywoła `run_preflight_qa`.

**Efekt:** Artykuły, które failują **wyłącznie** z powodu „the best” (i ewentualnie innych już obsługiwanych zamianami), zaczną przechodzić QA; liczba failed przy masowym odświeżaniu powinna wyraźnie spaść.

### R2. Wzmocnienie promptu (uzupełnienie)

- W instrukcjach dla modelu (markdown/HTML) **wyraźnie** zabronić używania „the best”, „#1”, „per month” itd. **również w nagłówkach i podtytułach** (np. jedna zdaniowa reguła: „Do not use these phrases anywhere in the article, including in headings.”).
- To ograniczy powstawanie problemu u źródła; R1 i tak zabezpieczy przed przeoczeniami.

### R3. Zachowanie obecnego zachowania

- **Nie** usuwać ani nie osłabiać reguł QA (FORBIDDEN_PATTERNS, progi słów, placeholdery, mustache, H2). Mają zostać jak są; poprawiamy tylko to, że treść przed QA będzie w pełni sanityzowana.
- **Nie** zmieniać domyślnej liczby retries ani logiki „Ponów tylko nieudane” – po R1 mniej artykułów będzie lądować na liście failed.

### R4. Opcjonalnie (później)

- **Raport po odświeżaniu:** Skrypt mógłby na końcu wypisać (lub zapisać do pliku) zestawienie: ile failed z powodu „the best”, ile z word count, ile z placeholders itd., żeby łatwiej ocenić skuteczność R1 i ewentualne dalsze tuningi.
- **Word count:** Jeśli po R1 nadal będzie dużo failed tylko z powodu progu słów (professional 1000 itd.), można rozważyć osobną decyzję: lekka podbić minimalne słowa dla trybu „refresh” albo dodać w UI opcję override tylko dla odświeżania – **nie** w ramach tej analizy, tylko jako osobny krok po wdrożeniu R1.

---

## 5. Podsumowanie

| Element | Wniosek |
|--------|--------|
| Główna przyczyna 39 failed | **„forbidden pattern: the best”** w treści, często w nagłówkach lub w treści przywróconej bez ponownej sanityzacji. |
| Luka w pipeline | Sanityzacja nie działa na nagłówkach i nie jest uruchamiana na końcowej wersji treści przed QA. |
| Rekomendacja priorytetowa | **R1:** Jedna, końcowa sanityzacja (w tym nagłówki) na treści przed `run_preflight_qa` – te same zamiany co dziś, pełny zakres tekstu. |
| Dodatkowo | **R2:** Doprecyzować w promptach zakaz „the best”/„#1”/„per month” także w nagłówkach. |
| Bez zmian | Reguły QA, progi, retries, „Ponów tylko nieudane”. |

Po zatwierdzeniu R1 (i opcjonalnie R2) można wdrożyć zmiany w `fill_articles.py` (sanityzacja przed QA + ewentualne rozszerzenie promptów).
