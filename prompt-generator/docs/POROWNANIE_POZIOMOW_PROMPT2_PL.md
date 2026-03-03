# Porównanie poziomów: Standard vs Advanced vs Expert (PROMPT #2)

Poniżej znajdziesz opisowe porównanie trzech poziomów generowania **PROMPT #2** (czyli gotowego, „copy‑paste” pierwszego promptu do nowego czatu z AI).  
Tekst jest napisany tak, aby można go było łatwo skopiować do pliku `.docx`.

---

### Co jest wspólne dla wszystkich poziomów?

- **Wynik to zawsze PROMPT #2**: gotowy do wklejenia jako pierwsza wiadomość w nowym czacie.
- **Brak „pustych ogólników”**: prompt ma wykorzystywać dane użytkownika (topic, objective, context; a gdy są: audience, constraints, format).
- **Brak zgadywania faktów**: jeśli temat wymaga wiedzy zewnętrznej albo weryfikacji, prompt może (lub powinien) to wyraźnie sygnalizować.

Różnice między poziomami dotyczą tego, jak **mocno** wymuszamy: precyzję, zasady „Zero‑Lie”, kontrolę ryzyka oraz sposób pracy (workflow) w odpowiedzi modelu.

---

## Standard — „konkretny, szybki, bez ciężkiej procedury”

### Dla kogo?
Dla większości codziennych tematów, kiedy chcesz szybko dostać sensowną odpowiedź, ale bez rozbudowanej kontroli ryzyka.

### Jak wygląda PROMPT #2 na Standard?
PROMPT #2 jest krótki, ale **konkretny i użyteczny**:

- **MUST CONTAIN (rdzeń):**
  - **ROLE** — rola **konkretna i dopasowana do tematu** (nie „helpful assistant”).
  - **OBJECTIVE** — jasno: co ma powstać / co ma być zrobione.
  - **CONTEXT** — informacje wpływające na odpowiedź.
  - **TASK** — czego dokładnie oczekujesz od AI.
  - Placeholders `[ ... ]` tylko, gdy brakuje danych.

### Co dodajemy w nowej propozycji (wzmacniacze jakości)?
- **HIGHEST PRIORITY (light):** dokładność > „ładne brzmienie”. Zero zgadywania, a przy braku weryfikacji — jawna niepewność.
- **ZERO‑LIE (minimal):**
  - TRUTH FIRST — krótkie formułki niepewności („I am not certain…”, „I cannot verify…”).
  - UNCERTAINTY → CLARIFY — jeśli brakuje krytycznych danych, prompt może zadać **1–3 pytania doprecyzowujące**.
- **Actionable & specific:** PROMPT #2 ma być „używalny od razu” i nie może być ogólnym pytaniem.

### Efekt w praktyce
 - Zamiast „ładnie brzmiącego pytania”, dostajesz prompt, który **od razu prowadzi** do sensownej odpowiedzi.
 - Jeśli temat wymaga doprecyzowania (np. brak celu, ograniczeń), Standard potrafi poprosić o brakujące dane, ale nie robi z tego długiej procedury.

---

## Advanced — „dobry balans: Zero‑Lie + dopasowanie do odbiorcy + format”

### Dla kogo?
- Dla tematów biznesowych, edukacyjnych i planistycznych, gdzie ważny jest **format odpowiedzi** (np. lista kroków) oraz **dopasowanie do odbiorcy**.
- Gdy chcesz ograniczyć ryzyko „wymyślania”, ale bez pełnego reżimu eksperckiego.

### Jak wygląda PROMPT #2 na Advanced?

- **MUST CONTAIN (rdzeń):**
  - **ROLE** — rola ekspercka, ale nadal **konkretna i dopasowana** do tematu i odbiorcy.
  - **OBJECTIVE**
  - **CONTEXT/INPUT**
  - **TASK**
  - **OUTPUT FORMAT**

### Co wzmacniamy w nowej propozycji?

- **ROLE doprecyzowane:** „optimal expert role concrete and specific to the user's topic and audience”.
- **Actionable & specific (wprost):** PROMPT #2 ma prowadzić do **skupionej** odpowiedzi, bez ogólników, z użyciem topic/objective/audience.
- **Usable for audience:** PROMPT #2 ma być **natychmiast używalny** przez wskazaną grupę docelową (język, poziom szczegółowości, ton).
- **REFLECTION — bardziej praktyczne:**
  - PROMPT #2 ma ująć: objective, constraints, brakujące dane,
  - oraz — gdy to ma sens — jakie założenia AI może przyjąć,
  - a jeśli kontekst jest „cienki”, może poprosić o doprecyzowanie.
- **Format odpowiedzi nie jest dekoracją:**
  - PROMPT #2 ma **jawnie poprosić** o odpowiedź w wybranym formacie (np. checklist/table/step‑by‑step).
- **Edge cases zamiast „opcjonalnie”:**
  - PROMPT #2 ma zawierać **1–3 edge cases / granice / warunki stopu**, gdy temat na tym zyskuje,
  - i krótki „reminder” o weryfikacji punktów krytycznych.
- **QUALITY doprecyzowane:**
  - jeśli w kontekście lub ograniczeniach są luki, prompt może krótko wskazać, jakie dodatkowe info poprawiłoby odpowiedź.

### Efekt w praktyce
- Output jest wyraźnie bardziej „produktowy”: z formatem, granicami i dopasowaniem do odbiorcy.
- Spada ryzyko odpowiedzi „nie w tym stylu” lub „zbyt ogólnej”, bo prompt wymusza strukturę.

---

## Expert — „najwyższa precyzja + kontrola ryzyka + workflow”

### Dla kogo?
- Dla tematów wysokiego ryzyka (prawo, finanse, zdrowie, decyzje strategiczne) albo gdy zależy Ci na **maksymalnej rzetelności**.
- Gdy wolisz ostrożność, doprecyzowanie i jawne granice zamiast „szybkiej odpowiedzi za wszelką cenę”.

### Jak wygląda PROMPT #2 na Expert?

Expert zawiera wszystko z Advanced, ale z pełnym reżimem **HIGHEST PRIORITY + ZERO‑LIE + HIGH‑RISK MODE** oraz bardziej kontrolowanym sposobem pracy.

- **HIGHEST PRIORITY (twardo):**
  - Absolute accuracy, zero hallucinations,
  - nigdy nie zgadywać,
  - nieweryfikowalne elementy — jawnie oznaczać.

- **ZERO‑LIE PRINCIPLES (MANDATORY):**
  - **TRUTH FIRST:** gotowe formułki niepewności.
  - **UNCERTAINTY → CLARIFY:** gdy brakuje krytycznych danych, AI ma najpierw dopytać.
  - **REFLECTION LOOP (rozszerzone):** objective, constraints, braki danych, ryzyka halucynacji, ewentualne założenia.
  - **INLINE VERIFICATION:** źródła albo oznaczenie „unverifiable”.
  - **CONTROLLED WORKFLOW:** krok po kroku, krótkie bloki, opcje + rekomendacja, sugestia rozdzielenia pracy na osobne czaty.
  - **HIGH‑RISK MODE:** Chain‑of‑Verification (analysis → questions → reanalysis → final + confidence level).
  - **Dodatkowo:** jeśli brakuje krytycznych informacji — **do 5 pytań doprecyzowujących**.

- **MUST CONTAIN (rozszerzony rdzeń):**
  - [HIGHEST PRIORITY] + [ZERO‑LIE principles]
  - **ROLE** — ekspercka / zespół, konkretnie dopasowana do tematu i odbiorcy
  - OBJECTIVE + CONTEXT/INPUT + TASK + OUTPUT FORMAT
  - **Format odpowiedzi „na twardo”:** AI ma jawnie poprosić o odpowiedź w tym formacie.
  - **Edge cases 2–5:** limity, wyjątki, warunki stopu/eskalacji.
  - Recommended tools + uncertainty rules + permission/questions + self‑check + final reminder o niezależnej weryfikacji.

- **QUALITY (z lukami):**
  - wskazanie brakujących danych,
  - oraz co konkretnie poprawiłoby jakość/bezpieczeństwo odpowiedzi.

### Efekt w praktyce
- Output jest najdłuższy i najbardziej sformalizowany, ale też **najbezpieczniejszy**.
- Najmniej miejsca na „zmyślanie”, najwięcej na doprecyzowanie, granice, weryfikację i kontrolę ryzyka.

---

## Krótki skrót różnic (1 zdanie na poziom)

- **Standard:** krótko i konkretnie — rola + cel + kontekst + zadanie, z lekką ochroną przed zgadywaniem.  
- **Advanced:** balans jakości — Zero‑Lie (basic), dopasowanie do odbiorcy, wymuszony format odpowiedzi, 1–3 edge cases.  
- **Expert:** maksymalna rzetelność — pełny Zero‑Lie + High‑Risk + kontrolowany workflow + 2–5 edge cases + pytania (do 5) gdy braki są krytyczne.
