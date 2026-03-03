# Audyt: budowanie tytułów artykułów i zdublowane wyrazy na początku

## 1. Jak budowane są tytuły

### 1.1 Przepływ

1. **Use case (AI)** – skrypt `generate_use_cases.py` generuje wpisy do `content/use_cases.yaml`. Każdy use case ma m.in.:
   - **problem** – krótki opis problemu (np. "how to implement rate limit management in ai marketing tools")
   - **suggested_content_type** – jeden z: how-to, guide, best, comparison (ew. review)

2. **Kolejka** – `generate_queue.py` czyta use_cases i buduje wpisy do `content/queue.yaml`. Dla każdego use case’a:
   - **title** = `title_for_entry(problem, content_type)` → **`{action} {problem}`**
   - **primary_keyword** = `title_to_primary_keyword(title)` → tytuł w lowercase

3. **Stałe prefiksy** w `scripts/generate_queue.py`:

   ```text
   CONTENT_TYPE_ACTION = {
       "how-to": "How to",
       "guide": "Guide to",
       "best": "Best",
       "comparison": "Comparison of",
   }
   ```

   Czyli:
   - content_type **how-to** → prefix **"How to "** + problem
   - content_type **guide** → prefix **"Guide to "** + problem
   - content_type **best** → prefix **"Best "** + problem
   - content_type **comparison** → prefix **"Comparison of "** + problem

4. **Artykuł** – `generate_articles.py` z kolejki bierze `title` i `primary_keyword` i wstawia je do frontmatteru szablonu (bez ponownego dodawania prefiksu). Tytuł w artykule to zatem dokładnie to, co zapisano w queue (a queue = action + problem).

### 1.2 Wniosek

Tytuł w artykule = **prefiksu z content_type (How to / Guide to / Best / Comparison of) + pole „problem” z use case’a**.  
Jeśli **problem** zwracany przez model już zaczyna się od „how to”, „guide to” lub „best”, w tytule pojawia się **zdublowany początek**.

---

## 2. Dlaczego część tytułów ma zdublowane wyrazy

- **generate_queue** **zawsze** dokleja prefiks z `CONTENT_TYPE_ACTION` do `problem`.
- **Model** (use case’y) często zwraca **problem** w formie gotowego „tytułu” typu:
  - „how to implement …”, „how to set up …”, „how to monitor …”  
  - „how to optimize …”, „how to scale …”
  - „guide to …” (rzadziej, ale bywa)
  - „best strategies …”, „best practices …”

Efekt:

| content_type | action (prefix) | Przykład problemu z use case | Wynikowy tytuł (zdublowany początek) |
|--------------|----------------|-------------------------------|--------------------------------------|
| how-to       | How to         | how to implement X            | **How to how to** implement X        |
| how-to       | How to         | how to set up Y               | **How to how to** set up Y           |
| guide        | Guide to       | how to monitor Z              | **Guide to how to** monitor Z        |
| guide        | Guide to       | how to optimize W             | **Guide to how to** optimize W       |
| best         | Best           | how to scale V                | **Best how to** scale V              |
| best         | Best           | best strategies for U         | **Best best** strategies for U      |

Przyczyną jest **brak normalizacji** pola `problem` przed złożeniem tytułu: prefiks jest dodawany niezależnie od tego, czy `problem` już ten prefiks (lub odpowiednik) zawiera.

---

## 3. Lista artykułów ze zdublowanym początkiem tytułu

Poniżej **unikalne stemy** (jeden wpis = jeden artykuł; pliki `.md` i `.html` tego samego stemu mają ten sam tytuł w frontmatterze).

### 3.1 Wzorzec „How to how to …”

| Stem (plik) |
|-------------|
| 2026-02-23-how-to-how-to-implement-agentic-automations-with-consistent-outputs-in-marketing-tasks.audience_professional |
| 2026-02-23-how-to-how-to-effectively-train-ai-models-with-minimal-data-for-marketing-purposes.audience_beginner |
| 2026-02-23-how-to-how-to-set-up-predictable-workflows-using-agentic-automations.audience_beginner |
| 2026-02-23-how-to-how-to-govern-and-ensure-reliability-in-complex-agentic-automation-systems.audience_professional |
| 2026-02-24-how-to-how-to-implement-rate-limit-management-in-ai-marketing-tools-to-prevent-lead-loss.audience_intermediate |
| 2026-02-26-how-to-how-to-implement-basic-security-measures-for-ai-agents-in-marketing-automation.audience_beginner |

### 3.2 Wzorzec „Guide to how to …”

| Stem (plik) |
|-------------|
| 2026-02-23-guide-to-how-to-monitor-and-troubleshoot-unexpected-behaviors-in-agentic-automation-processes.audience_intermediate |
| 2026-02-23-guide-to-how-to-develop-troubleshooting-processes-for-unexpected-agentic-automation-failures.audience_professional |
| 2026-02-23-guide-to-how-to-easily-set-up-ai-driven-customer-segmentation-without-advanced-technical-skills.audience_intermediate |
| 2026-02-23-guide-to-how-to-troubleshoot-unpredictable-responses-from-agentic-automations-during-campaigns.audience_professional |
| 2026-02-24-guide-to-how-to-monitor-lead-loss-due-to-scenario-failures-in-ai-driven-marketing-automations.audience_intermediate |
| 2026-02-24-guide-to-how-to-monitor-the-impact-of-rate-limits-on-campaign-effectiveness.audience_intermediate |
| 2026-02-25-guide-to-how-to-optimize-detection-and-response-strategies-for-lead-loss-during-a-rate-limit-breach.audience_professional |
| 2026-02-26-guide-to-how-to-monitor-ai-agents-for-security-vulnerabilities-in-marketing-automation.audience_intermediate |

### 3.3 Wzorzec „Best how to …”

| Stem (plik) |
|-------------|
| 2026-02-23-best-how-to-optimize-agentic-automations-to-align-with-marketing-goals-and-reduce-risks.audience_professional |
| 2026-02-23-best-how-to-scale-and-govern-agentic-automations-to-reduce-unpredictability.audience_intermediate |
| 2026-02-23-best-how-to-integrate-governance-models-for-high-reliability-in-agentic-automations.audience_professional |
| 2026-02-25-best-how-to-scale-ai-marketing-automations-to-handle-increased-lead-volume-without-failures.audience_professional |

### 3.4 Wzorzec „Best best …”

| Stem (plik) |
|-------------|
| 2026-02-25-best-best-strategies-for-enhancing-automation-frameworks-to-maintain-lead-generation-under-rate-limits.audience_professional |

---

**Razem: 19 unikalnych artykułów** (stemów) ze zdublowanym początkiem tytułu. Dla każdego mogą istnieć pliki `.md` i `.html` w `content/articles/` – oba mają ten sam tytuł w metadanych.

---

## 4. Propozycja naprawy

### 4.1 Naprawa źródła (żeby nowe tytuły się nie dublowały)

**Miejsce:** `scripts/generate_queue.py`, funkcja `title_for_entry(problem, content_type)`.

**Pomysł:** Przed złożeniem `title = f"{action} {problem}"` **usuń z początku `problem`** (case-insensitive) ewentualny prefiks, który by zduplikował action:

- Dla **how-to**: jeśli `problem` zaczyna się od „how to ” → uciąć te 8 znaków („how to “).
- Dla **guide**: jeśli `problem` zaczyna się od „guide to ” → uciąć („guide to “). Opcjonalnie: jeśli `problem` zaczyna się od „how to ” → też uciąć, żeby uniknąć „Guide to how to …” (wtedy zostanie „Guide to implement …” itd. – do decyzji, czy chcemy „Guide to [reszta]” czy „Guide to how to [reszta]” jako wyjątek; rekomendacja: uciąć „how to ” przy guide, żeby tytuł był „Guide to implement …”).
- Dla **best**: jeśli `problem` zaczyna się od „best ” → uciąć („best “). Opcjonalnie: jeśli `problem` zaczyna się od „how to ” → uciąć, żeby zamiast „Best how to …” było „Best implement …” / „Best set up …” (rekomendacja: uciąć „how to ” przy best).
- Dla **comparison** (i ewentualnie **review**): jeśli `problem` zaczyna się od „comparison of ” → uciąć.

**Szczegóły implementacji (do zatwierdzenia):**

- Zdefiniować dla każdego `content_type` listę **prefixów do usunięcia** z początku `problem` (lowercase), np.:
  - how-to: `["how to "]`
  - guide: `["guide to ", "how to "]`  // drugi żeby nie było „Guide to how to”
  - best: `["best ", "how to "]`       // drugi żeby nie było „Best how to”
  - comparison: `["comparison of "]`
- W `title_for_entry`: `problem_stripped = problem`; dla każdego prefiksu z listy: jeśli `problem_stripped.lower().startswith(prefix)`, to `problem_stripped = problem_stripped[len(prefix):].strip()` (jedno ucięcie na typ, np. tylko pierwszy pasujący prefiks).
- Na końcu: `return f"{action} {problem_stripped}"` (gdy po ucięciu zostanie pusty string, można fallback: `problem_stripped or problem` lub „Untitled”).

Dzięki temu **nowe** wpisy w queue (i nowe artykuły) nie będą miały zdublowanego początku.

### 4.2 Naprawa istniejących artykułów (19 stemów)

**Opcja A – skrypt korekty tytułów**

- Skrypt (np. `scripts/fix_duplicated_title_prefix.py`) działający na `content/articles/*.md` i `content/articles/*.html`:
  - Dla każdego pliku: odczyta frontmatter (title, primary_keyword).
  - Wykryje zdublowany początek (np. regex lub lista wzorców: „How to how to ”, „Guide to how to ”, „Best how to ”, „Best best ”).
  - Zamieni na wersję bez duplikatu (np. „How to how to implement X” → „How to implement X”, „Best best strategies” → „Best strategies”).
  - Zapisze zaktualizowany frontmatter (title i primary_keyword = lowercase(title)).
- Uruchomienie: ręcznie lub z Flowtaro Monitor (np. przycisk „Popraw zdublowane prefiksy w tytułach”); **dry-run** (wypisanie zmian bez zapisu) + **--confirm** (zapis).

**Opcja B – ręczna edycja**

- Lista 19 stemów i proponowane nowe tytuły (np. w tabeli w tym dokumencie); edycja frontmatteru w każdym pliku .md / .html ręcznie lub przez find-replace.

**Rekomendacja:** **4.1 (naprawa w generate_queue)** + **4.2 Opcja A (skrypt korekty z dry-run i --confirm)**. Skrypt można ograniczyć do znanych wzorców („How to how to ”, „Guide to how to ”, „Best how to ”, „Best best ”) i zamieniać je na „How to ”, „Guide to ”, „Best ”, „Best ” (jedno słowo/segment mniej), z odpowiednią aktualizacją `primary_keyword`.

### 4.3 Ewentualne uzupełnienie: prompt use case’ów

- W instrukcji dla modelu (generate_use_cases) można dodać zdanie: „The **problem** field should be a short phrase **without** leading 'how to', 'guide to', or 'best' (e.g. 'implement rate limit management in AI tools', not 'how to implement …').”
- To zmniejszy ryzyko, że nowe use case’y będą miały problem z prefiksem; **nie zastępuje** normalizacji w `title_for_entry`, która i tak powinna być (bo stare use_cases.yaml i ręczne wpisy mogą mieć prefiks).

---

## 5. Podsumowanie

| Element | Opis |
|--------|------|
| **Przyczyna** | W `generate_queue.py` tytuł = `{CONTENT_TYPE_ACTION[content_type]} {problem}`. Pole `problem` z use case’ów często już zaczyna się od „how to”, „guide to” lub „best”, co daje zdublowany początek. |
| **Liczba dotkniętych artykułów** | 19 unikalnych stemów (wzorce: „How to how to”, „Guide to how to”, „Best how to”, „Best best”). |
| **Naprawa źródła** | W `title_for_entry()` przed złożeniem tytułu uciąć z początku `problem` (case-insensitive) prefiksy: dla how-to „how to ”, dla guide „guide to ” i „how to ”, dla best „best ” i „how to ”, dla comparison „comparison of ”. |
| **Naprawa istniejących** | Skrypt korekty frontmatteru (title + primary_keyword) w `content/articles` z dry-run i --confirm, oparty na znanych wzorcach duplikacji. |
| **Opcjonalnie** | Doprecyzowanie promptu use case’ów, żeby **problem** nie zaczynał się od prefiksu. |

**Nie wdrażam zmian w kodzie ani skryptach do momentu Twojego zatwierdzenia.**
