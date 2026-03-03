# Audyt: merytoryka procesu „Try it yourself” — dobór narzędzia z treści, Recommended tools, CTA bez etykiety

**Data:** 2026-02-20  
**Kontekst:** Obecna instrukcja („pierwsze narzędzie z TOOLS_SELECTED w Try it yourself”) jest niedokładna i pozwala na wybór narzędzia niewłaściwego. Propozycja: dobór narzędzia i tekstów na podstawie **treści** Prompt #1 / Prompt #2 oraz jawnego bloku **Recommended tools** w Prompt #1; zmiana formuł nad/pod Prompt #2 i usunięcie etykiety „Action cue:”.  
**Status:** Audyt i rekomendacja — **bez wdrożenia w kodzie** do momentu zatwierdzenia.

---

## 1. Analiza merytoryczna obecnego procesu

### 1.1 Jak jest dziś

- **Wybór narzędzia:** „Pierwsze z listy TOOLS_SELECTED” — czyli to, co model wpisze jako pierwsze w jednej linii na końcu odpowiedzi. Model nie ma w tym momencie **obowiązku** dopasowania tego narzędzia do treści Prompt #1 ani Prompt #2.
- **Prompt #1** to zawsze **meta-prompt**: polecenie dla ogólnego AI, żeby wygenerował **kolejny prompt do konkretnego narzędzia** (np. „Return a prompt that can be pasted into Make / Descript”). Treść Prompt #1 więc **implicitly** mówi, do jakiego typu narzędzia jest ten drugi prompt (video tool, automation tool, chat, itd.).
- **Efekt:** Może powstać rozjazd: w Prompt #1 jest mowa o „governance framework”, a nad blokiem stoi „ready to use with **Opus Clip** (AI tool)” — bo Opus Clip był pierwszy w TOOLS_SELECTED, choć do treści nie pasuje.

### 1.2 Dlaczego to słabe merytorycznie

- Czytelnik widzi: „Wklej Prompt #1 do ogólnego AI, dostaniesz Prompt #2, użyj go w **Opus Clip**”. Tymczasem treść Prompt #2 to np. lista ról i KPI do governance — czego w Opus Clip nie da się „użyć” w sensowny sposób.
- Narzędzie nad Prompt #1 powinno być **wynikiem analizy treści** (do jakiego narzędzia jest ten meta-prompt / ten output), a nie **kolejności na liście** wybranej przy pisaniu całego artykułu.

---

## 2. Propozycja użytkownika — streszczenie

### 2.1 Nad pierwszym promptem („Here is the input (Prompt #1) ready to use with […]”)

- **Dobór narzędzia:** Inteligentnie przez API na podstawie treści — z opisem **rodzaju** narzędzia (np. „General AI chat”), pobranym z listy lub wygenerowanym z opisów z listy.
- **Uzasadnienie:** Do Prompt #1 zawsze jest wpisywany meta-prompt z poleceniem utworzenia promptu do **określonego** narzędzia — więc narzędzie w tekście nad Prompt #1 powinno być dopasowane do tej treści.

### 2.2 W ramie polecenia do API (generującej Prompt #1)

- **Wymóg literalny:** W treści Prompt #1 (output modelu) **przed** blokiem typu „Uncertainty” (w obecnym szablonie: przed **Uncertainty:**) dodać sekcję **Recommended tools**.
- **Instrukcja dla API:** W tym miejscu model ma **wylistować** narzędzia z listy AI, które nadają się do dalszej pracy nad celami/zadaniami/zaleceniami będącymi przedmiotem **Outputu** (czyli Prompt #2). Czyli: output ma jawnie zawierać rekomendację narzędzi pasujących do tego, co Prompt #2 ma realizować.

### 2.3 Nad Prompt #2

- **Tekst:** W stylu: „Below is the output (Prompt #2) the AI returns, which is ready to use with **[tu tylko powtórzona nazwa tego samego narzędzia co nad Prompt #1, bez linku]**” + dopisek: „w tym samym lub nowym wątku lub w **innym narzędziu z rodzaju (tu rodzaj z opisu, np. General AI chat)**”.
- Czyli: jedna spójna nazwa narzędzia (bez linku), plus informacja, że można użyć innego narzędzia tego samego typu.

### 2.4 Pod Prompt #2 (wezwanie do działania)

- **Sprawdzenie i dopasowanie:** Czy któreś z narzędzi **wskazanych w treści Prompt #2** pasuje do listy Selected_tools (affiliate/reference). Jeśli tak — w treści wezwania **powtórzyć podlinkowaną nazwę** tego narzędzia.
- **Etykieta:** Tytuły w rodzaju „Call to Action”, „Action cue:” itp. **nie** powinny występować w tym miejscu artykułu — wezwanie ma być zwykłym zdaniem, bez takiej etykiety.

---

## 3. Ocena krytyczna pomysłu

### 3.1 Mocne strony

| Element | Ocena |
|--------|--------|
| **Dobór narzędzia z treści** | Słuszne: narzędzie nad Prompt #1 powinno wynikać z tego, **do czego** jest ten meta-prompt (typ narzędzia, use case), a nie z kolejności w TOOLS_SELECTED. |
| **Recommended tools w Prompt #1** | Bardzo sensowne: daje **jawny**, możliwy do sparsowania fragment outputu (lista narzędzi), który można wykorzystać do wstawienia nazwy/linku nad Prompt #1 i ewentualnie w CTA. Zmniejsza zgadywanie. |
| **Nad Prompt #2: ta sama nazwa, bez linku + „lub inny tool typu X”** | Spójne z nad Prompt #1; unika drugiego linku w tym samym kontekście; „inny tool typu X” poszerza wybór czytelnika (np. inny General AI chat). |
| **CTA: dopasowanie narzędzi z treści Prompt #2 do Selected_tools i podlinkowanie** | Merytorycznie trafne: wezwanie odnosi się do konkretnych narzędzi, które faktycznie pojawiają się w Prompt #2, i daje im link. |
| **Brak etykiety „Action cue:”** | Tekst czyta się jak naturalna zachęta, nie jak nagłówek sekcji — to kwestia stylu i spójności z resztą artykułu. |

### 3.2 Wyzwania i ryzyka

| Element | Wyzwanie |
|--------|----------|
| **Recommended tools** | Model może podać nazwy w innej formie (np. „Chat GPT”), narzędzia spoza listy, lub pominąć sekcję. Trzeba: jasnego formatu w instrukcji (np. „exact names from the list”) i fallbacku (np. dopasowanie z treści Prompt #1 przez drugie wywołanie API lub heurystyki). |
| **„Rodzaj” narzędzia (General AI chat, itd.)** | W YAML jest `category` (np. ai-chat, video) i opcjonalnie `short_description_en`. Trzeba zdefiniować mapowanie category → czytelny „rodzaj” (np. ai-chat → „General AI chat”) lub użyć opisu; ewentualnie nowe pole w YAML. |
| **Parsowanie narzędzi z treści Prompt #2** | Prompt #2 to dowolny tekst (np. długi framework). Wymaga ekstrakcji nazw narzędzi (regex / NER / drugie API), potem dopasowania do listy affiliate. Możliwe fałszywe trafienia lub brak trafień. |
| **Usunięcie „Action cue:”** | Obecne QA i normalizacja szukają literalnie „Action cue:”. Trzeba zmienić QA i pipeline na „zdanie zachęcające po Prompt #2” (np. z opcjonalnym linkiem), bez wymogu tej etykiety. |

### 3.3 Spójność z resztą systemu

- **TOOLS_SELECTED** nadal może istnieć jako lista narzędzi „użytych w artykule” (np. do „List of platforms and tools” lub frontmatter), ale **nie** jako jedyne źródło narzędzia do „Try it yourself”. Źródłem staje się: (1) Recommended tools z Prompt #1, (2) ewentualnie dopasowanie z treści przez API.
- **List of platforms and tools** — bez zmian w stosunku do wcześniejszej rekomendacji: budowana z tego, co faktycznie jest w body (w tym z linków wstawionych nad Prompt #1 i w CTA).

---

## 4. Za i przeciw

### Za

- **Spójność merytoryczna:** Narzędzie nad Prompt #1 i rodzaj nad/pod Prompt #2 wynikają z treści, nie z kolejności na liście.
- **Jawność:** Blok Recommended tools w Prompt #1 daje czytelny kontrakt (model ma wylistować narzędzia); łatwiej parsować i fallbackować.
- **Lepsze UX:** „Użyj w [Narzędzie] lub w innym narzędziu typu X” + CTA z konkretnym linkiem do narzędzia z Prompt #2 — czytelnik wie, gdzie wkleić i co ma wybór.
- **Brak sztywnej etykiety CTA:** Artykuł brzmi naturalniej.

### Przeciw

- **Złożoność:** Więcej logiki (parsowanie Recommended tools, ekstrakcja narzędzi z Prompt #2, mapowanie typów), więcej edge case’ów.
- **Zależność od jakości outputu modelu:** Recommended tools może być puste lub błędne — potrzebne fallbacki (np. pierwsze z TOOLS_SELECTED, lub osobne wywołanie API „dopasuj narzędzie do tego tekstu”).
- **Koszt/opóźnienie:** Jeśli dopasowanie narzędzia do treści Prompt #1 robi drugie wywołanie API — dodatkowy koszt i czas.
- **Zmiana QA i normalizacji:** Obecne testy i _normalize_try_it_yourself_html są pod „Action cue:” i stałe wzorce descriptorów — trzeba je zaktualizować.

---

## 5. Proponowana wersja implementacji (bez kodu)

### 5.1 Ramka polecenia do API (generująca artykuł z Prompt #1)

- W instrukcji do sekcji „Try it yourself” (w obu wariantach: professional i non-professional) **dodać wymóg**:
  - W treści Prompt #1 (w output modelu) **przed** częścią **Uncertainty:** (i ewentualnie **Permission:**) musi występować blok:
  - **Recommended tools:** [lista 1–3 narzędzi z podanej listy Affiliate/Other, w dokładnych nazwach z listy, oddzielone przecinkami]. Instrukcja: „Wylistuj tutaj narzędzia z listy, które nadają się do realizacji celów, zadań lub zaleceń będących przedmiotem Outputu (Prompt #2). Używaj wyłącznie nazw z listy.”
- Zachować resztę struktury Prompt #1 (Role, Goal/Task/Objective, Chain of thought, Output specification, Edge cases, Uncertainty, Permission).

### 5.2 Dobór narzędzia nad Prompt #1

- **Źródło pierwszego wyboru:** Sparsować z wygenerowanego Prompt #1 blok „Recommended tools” (regex: np. `\*\*Recommended tools:\*\*\s*([^*]+)` lub w HTML odpowiednik); wyciągnąć pierwsze dopasowanie do listy affiliate/reference (po nazwie).
- **Fallback:** Jeśli brak Recommended tools lub żadna nazwa nie pasuje — wywołać (opcjonalnie) drugie, krótkie wywołanie API: „Given this meta-prompt text [fragment Prompt #1], which tool from the list [lista z opisami] best fits? Return only the exact tool name.” Alternatywa: użyć pierwszego z TOOLS_SELECTED jak dziś.
- **Opis rodzaju:** Z YAML: dodać pole opcjonalne `tool_type_display` (np. „General AI chat”, „Video AI tool”) lub mapować `category` na stały zestaw etykiet; jeśli brak — użyć `short_description_en` lub „AI tool”.

### 5.3 Tekst nad Prompt #1

- Zachować formułę w stylu: „Here is the input (Prompt #1) ready to use with **[Nazwa]** ([rodzaj z opisu lub type]).” — z **linkiem** do narzędzia (jak dziś). Nazwa i rodzaj pochodzą z kroku 5.2.

### 5.4 Tekst nad Prompt #2

- Wzorzec: „Below is the output (Prompt #2) the AI returns, which is ready to use with **[ta sama nazwa co nad Prompt #1, bez linku]** in the same or a new thread, or in another tool of the same type ([rodzaj], e.g. General AI chat).”
- W kodzie: jedna zmienna „tool name”, jedna „tool type/kind”; nad drugim `<pre>` wstawić ten tekst bez linku przy nazwie.

### 5.5 Wezwanie pod Prompt #2 (bez etykiety „Action cue:”)

- **Treść:** Jedno zdanie zachęcające do użycia Prompt #2 (np. z puli obecnych _TRY_CTA_VARIANTS, ale **bez** prefiksu „Action cue: ”). Jeśli w **treści Prompt #2** (wygenerowanego bloku) da się zidentyfikować nazwy narzędzi i któreś z nich są w Selected_tools / affiliate list — wstawić w tym zdaniu **podlinkowaną** nazwę (np. „Paste Prompt #2 into [ChatGPT] and refine the output.”).
- **Ekstrakcja narzędzi z Prompt #2:** Przeszukać blok Prompt #2 (tekst między drugim `<pre>` a końcem sekcji) pod kątem wystąpień nazw z listy affiliate; wybrać np. pierwsze trafienie lub wszystkie trafienia (jeden link w zdaniu vs. kilka — do ustalenia).
- **QA:** Zamiast wymagać literalnie „Action cue:”, wymagać obecności zdania zachęcającego po Prompt #2 (np. zawierającego „Prompt #2” lub link do narzędzia z listy).

### 5.6 Normalizacja i QA

- Rozszerzyć _normalize_try_it_yourself_html: wstrzykiwanie (1) linii nad Prompt #1 z narzędziem z Recommended tools / fallback, (2) linii nad Prompt #2 według nowego wzorca (ta sama nazwa, bez linku, + „or in another tool of type X”), (3) jednego zdania CTA bez etykiety, z opcjonalnym linkiem wyciągniętym z Prompt #2.
- W run_preflight_qa: usunąć wymóg „Action cue:”; dodać wymóg „obecność zdania zachęcającego po Prompt #2” i ewentualnie „nazwa narzędzia nad Prompt #1 i nad Prompt #2 ta sama”.

---

## 6. Rekomendacja

- **Wdrożyć kierunek proponowany przez użytkownika**, w wersji zbliżonej do opisu z p. 5:
  1. **Recommended tools** w Prompt #1 (literalny wymóg w instrukcji przed Uncertainty) + parsowanie tego bloku do wyboru narzędzia nad Prompt #1 (z fallbackiem).
  2. **Nad Prompt #2:** ta sama nazwa co nad Prompt #1, bez linku, + dopisek „or in another tool of the same type (rodzaj)”.
  3. **Pod Prompt #2:** jedno zdanie zachęcające **bez** etykiety „Action cue:”, z opcjonalnym dopasowaniem i podlinkowaniem narzędzia z treści Prompt #2 (jeśli pasuje do listy).
  4. **Rodzaj narzędzia:** z YAML (nowe pole `tool_type_display` lub mapowanie `category` → etykieta); brak → `short_description_en` lub „AI tool”.

- **Kolejność wdrożenia (po zatwierdzeniu):** (1) rozszerzenie instrukcji i ramki Prompt #1 o Recommended tools; (2) logika parsowania Recommended tools i fallback; (3) nowe wzorce tekstów nad/pod Prompt #2 i normalizacja; (4) ekstrakcja narzędzi z Prompt #2 do CTA; (5) aktualizacja QA (usunięcie wymogu „Action cue:”, nowe kryteria).

- **Nie kodować** do momentu zatwierdzenia przez użytkownika.

---

**Dokument przygotowany w trybie audytu; brak wdrożenia w kodzie do momentu zatwierdzenia.**
