# Analiza korelacji: niepowodzenia Prompt #2 / zdanie zachęcające (Try it yourself) oraz propozycje rozwiązań

## 1. Kontekst wymagań QA

W `fill_articles.py` (run_preflight_qa) dla sekcji „Try it yourself” sprawdzane są:

1. **Deterministyczna linia deskryptora Prompt #1** – wzorzec typu:  
   `(Here is|This is|Below is) the input (Prompt #1) ... ready to use with X (type).`
2. **Deterministyczna linia deskryptora Prompt #2** – wzorzec:  
   `(Below is the output (Prompt #2)|The AI returns the following output (Prompt #2)) ... ready to use with X (in the same or a new thread|(AI tool).)`
3. **Zachęta / odniesienie do Prompt #2** – w treści (lub w sekcji Try-it-yourself dla MD) musi wystąpić fraza „prompt #2” lub „prompt 2”.

Przed QA uruchamiana jest **normalizacja** (`_normalize_try_it_yourself_html` lub `_normalize_try_it_yourself_md`), która **wstrzykuje** te linie i CTA, **ale tylko wtedy, gdy w sekcji „Try it yourself” są już co najmniej dwa bloki kodu** (dwa `<pre>` w HTML lub dwa ``` w MD). Jeśli model zwróci tylko jeden blok kodu albo sekcja jest pusta/nieprawidłowa, normalizer **nic nie wstrzykuje** (`return body`) i QA zgłasza brak deskryptora i zachęty.

---

## 2. Klasyfikacja 54 niepowodzeń (refresh_failure_reasons.txt)

Dla każdego stemu wyciągnięto:
- **content_type** z prefiksu nazwy pliku (guide-to → guide, how-to → how-to, best- → best, veed-vs / *comparison* → comparison; brak prefiksu → how-to/guide z kontekstu),
- **audience_type** z sufiksu (.audience_beginner, .audience_intermediate, .audience_professional) lub „default” przy braku sufiksu,
- **subtyp przyczyny**: tylko „descriptor #2”, „descriptor + encouraging”, „missing Prompt #1”, „missing Prompt #2 ready-to-paste”.

### 2.1 Rozkład po content_type

| content_type | Liczba niepowodzeń | % (z 54) |
|--------------|--------------------|----------|
| **how-to**   | 22                 | 41%      |
| **guide**    | 20                 | 37%      |
| **best**     | 11                 | 20%      |
| **comparison** | 1                | 2%       |

### 2.2 Rozkład po audience_type

| audience_type  | Liczba niepowodzeń | % (z 54) |
|----------------|--------------------|----------|
| **intermediate** | 20               | 37%      |
| **professional** | 18               | 33%      |
| **beginner**     | 12               | 22%      |
| **default**      | 4                | 7%      |

### 2.3 Tabela krzyżowa: content_type × audience_type

|                | beginner | intermediate | professional | default |
|----------------|----------|--------------|--------------|---------|
| **how-to**     | 5        | 8            | 4            | 5       |
| **guide**      | 3        | 8            | 8            | 1       |
| **best**       | 4        | 4            | 3            | 0       |
| **comparison** | 0        | 0            | 0            | 1       |

### 2.4 Subtyp przyczyny (wystąpienia w 54 wpisach)

| Subtyp | Opis | Liczba |
|--------|------|--------|
| **Tylko „missing deterministic Prompt #2 descriptor line”** (bez „encouraging”) | Model nie zwrócił dopasowanej linii; normalizer nie wstrzyknął (np. < 2 bloków kodu). | 34 |
| **„missing encouraging sentence or reference to Prompt #2”** (z lub bez descriptor) | Brak frazy „prompt #2” / „prompt 2” w treści lub w sekcji. | 15 |
| **„Try it yourself missing Prompt #2 (ready-to-paste)”** | Sekcja ma < 2 bloków kodu (brak gotowego outputu Prompt #2). | 2 |
| **„Try it yourself missing Prompt #1 (meta-prompt)”** | Sekcja ma < 2 bloków kodu (brak Prompt #1). | 2 |

Uwaga: jeden stem może łączyć kilka przyczyn (np. descriptor + encouraging).

---

## 3. Obserwacje i korelacje

### 3.1 content_type

- **how-to** i **guide** łącznie to ~78% niepowodzeń (42/54). Oba typy wymagają sekcji „Try it yourself” z dwoma blokami i dopasowaną linią Prompt #2.
- **best** – 11 niepowodzeń (20%); w kodzie dla best/comparison CTA jest inny (workflow/steps), ale wymóg deskryptora Prompt #2 jest ten sam.
- **comparison** – tylko 1 przypadek (veed-vs-submagic); za mało danych na korelację.

Nie ma wyraźnej korelacji „jeden typ artykułu = zawsze fail”; problem dotyczy **wszystkich** typów z sekcją Try it yourself (how-to, guide, best, comparison).

### 3.2 audience_type

- **intermediate** i **professional** łącznie: 38/54 (70%). **beginner**: 12 (22%).
- Nie widać silnej zależności „tylko professional” lub „tylko beginner”; rozkład jest względnie równomierny (beginner nieco mniej). Możliwy czynnik: więcej artykułów w batchu to intermediate/professional, więc więcej faili tam się pojawia.

### 3.3 Główna przyczyna techniczna

- W **większości** przypadków (34) występuje wyłącznie „missing deterministic Prompt #2 descriptor line” (bez wzmianki o „encouraging”). To spójne z tym, że:
  - **normalizer wstrzykuje deskryptor i CTA tylko gdy w sekcji są ≥ 2 bloki kodu**;
  - jeśli model zwróci **0 lub 1 blok kodu** w „Try it yourself”, normalizer nie dodaje nic → QA zgłasza brak deskryptora (i często też brak „prompt #2” w tekście, czyli encouraging).
- Dwa stemy z „missing Prompt #1” i dwa z „missing Prompt #2 (ready-to-paste)” potwierdzają, że **brak drugiego bloku kodu** (lub w ogóle niepełna sekcja) jest bezpośrednią przyczyną: normalizer nie działa, QA fail.

**Wniosek:** Główna korelacja nie jest „problem–typ artykułu–audience”, tylko **„model często nie zwraca dwóch bloków kodu w sekcji Try it yourself”** (albo zwraca sekcję w formie, której parser nie uznaje za 2 bloki). Dotyczy to wszystkich content_type i audience w podobnym stopniu.

---

## 4. Propozycje rozwiązań (bez implementacji)

### 4.1 Wzmocnienie instrukcji w prompcie fill (zalecane)

- **Jasno i osobno** opisać wymóg sekcji „Try it yourself”:
  - **Dwa bloki kodu:** pierwszy = „Prompt #1” (meta-prompt / input), drugi = „Prompt #2” (gotowy output do wklejenia).
  - **Jedna linia przed drugim blokiem:** w stylu: „Below is the output (Prompt #2) the AI returns, which is ready to use with [nazwa narzędzia] (AI tool).” (albo podać dokładną frazę z kodu).
  - **Jedno zdanie po drugim bloku:** zachęta zawierająca frazę „Prompt #2” (np. „Now run Prompt #2 in your AI tool and iterate on the result.”).
- Dodać **krótki przykład** (1–2 zdania + dwa bloki ```) w systemie lub w user message, żeby model miał wzór.
- Opcjonalnie: **osobne zdania w instrukcji** dla content_type „best” i „comparison” (np. że CTA może mówić o „workflow” / „steps”, ale **Prompt #2 i dwa bloki są obowiązkowe**).

Efekt: mniej odpowiedzi z jednym blokiem lub bez linii deskryptora, więc normalizer częściej będzie mógł uzupełnić ewentualne braki, a QA będzie rzadziej failować.

### 4.2 Normalizer zawsze wstrzykuje deskryptor + CTA przy ≥1 bloku (rozszerzenie normalizera)

- Obecnie: przy **< 2 blokach** normalizer nic nie robi.
- Propozycja: jeśli jest **co najmniej jeden** blok kodu w „Try it yourself”:
  - traktować go jako Prompt #1,
  - **wstrzyknąć** przed nim linię deskryptora Prompt #1 (jeśli brak),
  - **wstrzyknąć** po nim **drugi blok placeholder** (np. „# Paste the output of Prompt #1 here”) + linię deskryptora Prompt #2 + CTA,
  - albo: wstrzyknąć tylko linię deskryptora Prompt #2 + CTA **po tym jednym bloku**, a QA rozluźnić dla przypadku „1 blok” (np. nie wymagać drugiego bloku, tylko deskryptora i CTA).

Wymaga to doprecyzowania: czy akceptujemy artykuły z jednym blokiem (Prompt #1) i placeholderem na Prompt #2, czy wymagamy zawsze dwóch „realnych” bloków. Decyzja produktowa.

### 4.3 Rozluźnienie QA przy obecności „prompt #2” w sekcji (tylko MD)

- W kodzie jest już **relaksacja dla MD**: jeśli w sekcji Try-it-yourself jest „prompt #2”/„prompt 2” oraz „ready to use”, to nie dodaje się „missing deterministic Prompt #2 descriptor line” (linie 452–473).
- Można rozważyć: uznawać **samą obecność** „prompt #2” (i ewentualnie „ready to use”) w sekcji za wystarczającą, **nie** wymagając dokładnego dopasowania regexu do pełnej linii deskryptora – o ile normalizer i tak ma szansę później ujednolicić format. To zmniejszyłoby liczbę fałów przy „prawie dobrej” odpowiedzi modelu.

### 4.4 Post-processing po odpowiedzi modelu (fallback)

- Przed normalizerem: **wykryć** sekcję „Try it yourself” i policzyć bloki kodu.
- Jeśli jest **0 lub 1 blok**:
  - **Opcja A:** dołożyć drugi blok placeholder (np. komentarz „# Output of Prompt #1”) i uruchomić normalizer → deskryptor i CTA zostaną wstrzyknięte; artykuł ma „szkielet” na Prompt #2.
  - **Opcja B:** jednym **ponownym** wywołaniem API (np. „Add a second code block (Prompt #2 output) to the Try it yourself section”) wygenerować tylko brakujący blok i dopiąć do treści, potem normalizer.

Wymaga to ustalenia, czy drugi blok może być placeholderem, czy musi być od razu treścią od modelu.

### 4.5 Szablony szkieletów (generate_articles / templates)

- Sprawdzić, czy szablony **how-to**, **guide**, **best**, **comparison** w `templates/` zawierają już **gotową sekcję „Try it yourself”** z dwoma pustymi blokami kodu (np. ```\n# Prompt #1\n``` i ```\n# Prompt #2\n```) oraz placeholderem na linię deskryptora.
- Jeśli tak: fill tylko uzupełnia treść bloków; jeśli nie – **dodać** taki szkielet do szablonów, żeby model zawsze miał „dwa bloki” do wypełnienia i nie musiał ich sam tworzyć (wtedy normalizer zawsze ma gdzie wstrzyknąć deskryptor i CTA).

---

## 5. Rekomendacja kolejności działań

1. **Szybkie:** Doprecyzować w **prompcie fill** wymóg dwóch bloków kodu, dokładnej linii deskryptora Prompt #2 i zdania z „Prompt #2” (rozwiązanie 4.1) + ewentualnie dodać **szkielet Try it yourself** w szablonach (4.5).
2. **Średnie:** Zdecydować, czy akceptujemy **1 blok + placeholder**; jeśli tak – rozszerzyć **normalizer** (4.2) i ewentualnie **QA** (4.3).
3. **Opcjonalne:** Wprowadzić **post-processing** (4.4) jako fallback, gdy po 4.1 i 4.5 nadal będzie brakować drugiego bloku.

Nie kodować do momentu zatwierdzenia kierunku (które rozwiązania wdrożyć w jakiej kolejności).
