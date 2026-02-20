# Generowanie use case’ów – co jest wysyłane do modelu i jak to parametryzować

## 1. Wywołanie API

Skrypt `scripts/generate_use_cases.py` wysyła do **OpenAI Responses API** (`POST .../v1/responses`) jeden request z:

- **model** – z env `OPENAI_MODEL` (domyślnie `gpt-4o-mini`)
- **instructions** – stały blok instrukcji („system” / kontekst)
- **input** – zmienna wiadomość użytkownika (user message) z danymi i wytycznymi

Odpowiedź modelu ma być **jednym** JSON arrayem obiektów; skrypt z niego wyciąga use case’y i dopisuje do `content/use_cases.yaml`.

---

## 2. Treść `instructions` (stała)

Wysłany tekst to dokładnie:

```
You are a content strategist. Your task is to suggest new business problems / use cases for blog content in the AI marketing automation space.

Output ONLY a valid JSON array of objects. Each object must have exactly these keys:
- "problem": string, concise description of the business problem (e.g., "turn podcasts into written content")
- "suggested_content_type": string, one of: how-to, guide, best, comparison
- "category_slug": string, one of the allowed categories provided in the user message

Do not output any markdown, explanation, or text outside the JSON array. The response must be parseable as JSON.
```

**Znaczenie:**  
Rola (content strategist), dziedzina (AI marketing automation), wymagany format odpowiedzi (JSON, trzy klucze), zakaz markdownu/tekstu poza tablicą.

**Czy da się to modelować/parametryzować?**  
Tak – ten string jest na stałe w `build_prompt()` w skrypcie. Można go przenieść do pliku (np. `content/prompts/use_cases_instructions.txt`) lub dodać zmienne (np. „blog content in **{domain}**”), żeby zmieniać dziedzinę bez edycji kodu.

---

## 3. Treść `input` (user message) – co jest „dawane”

Składnia (w kodzie): jeden f-string z blokami poniżej. W nawiasach podane jest **skąd** bierze się wartość.

### 3.1 Dozwolone kategorie

```
Allowed category_slug values (use exactly one per use case): {json.dumps(categories)}
```

- **Źródło:** `categories` = z configu `production_category` + `sandbox_categories`, ewentualnie zawężone do jednej przy `--category`.
- **Efekt:** Model może używać tylko tych wartości w polu `category_slug`.

### 3.2 Istniejące use case’y (żeby nie duplikować)

```
Existing use cases already in our list (do NOT suggest these or very similar ones):
{json.dumps(existing_problems)}
```

- **Źródło:** `existing_problems` = lista pól `problem` z `content/use_cases.yaml` (bez statusu).
- **Efekt:** Wytyczna „nie powtarzaj tych ani bardzo podobnych”.

### 3.3 Istniejące tematy z artykułów

```
Existing article keywords/topics we already cover (suggest complementary or new angles, not duplicates):
{json.dumps(keywords_list[:50])}
```

- **Źródło:** `article_keywords` = dla każdego `.md` z `content/articles/` brane są `primary_keyword` lub `title` (i opcjonalnie category); do user message trafia **max 50** pierwszych.
- **Efekt:** Model ma unikać powtórzeń i proponować uzupełniające / nowe kąty.

### 3.4 Wytyczna główna + liczba

```
Generate exactly {count} new, specific, actionable business problems that people actively search for solutions to in AI marketing automation. Each must be different from the existing use cases and topics above.
```

- **Źródło:** `count` = z `--limit` (domyślnie `TARGET_USE_CASE_COUNT`, np. 12), ograniczone do 1–100.
- **Efekt:** Konkretna liczba do wygenerowania, wymóg „specific, actionable”, „people actively search for” i „different from existing”.

### 3.5 Typ treści (opcjonalnie)

- **Jeśli podano `--content-type`:**  
  `For every use case, set suggested_content_type to exactly: "{content_type_filter}".`
- **Jeśli nie:**  
  `Prefer problems that fit how-to or guide content.`

Na końcu zawsze:  
`Return only the JSON array.`

---

## 4. Wytyczne do zadania (zbiorczo)

| Wytyczna | Skąd | Gdzie w promptcie |
|----------|------|-------------------|
| Rola i dziedzina | Stała w `instructions` | „content strategist”, „AI marketing automation” |
| Format odpowiedzi | Stała w `instructions` | JSON array, klucze: problem, suggested_content_type, category_slug |
| Dozwolone kategorie | Config + `--category` | „Allowed category_slug values” w user message |
| Nie duplikować problemów | use_cases.yaml | „Existing use cases… do NOT suggest” |
| Nie duplikować tematów | content/articles (max 50) | „Existing article keywords/topics… not duplicates” |
| Liczba use case’ów | `--limit` | „Generate exactly {count} new…” |
| Jakość / intencja | Stała w user message | „specific, actionable”, „people actively search for”, „different from existing” |
| Preferowany / wymuszony typ | `--content-type` lub brak | „Prefer how-to or guide” albo „set suggested_content_type to exactly: X” |

Po stronie skryptu jest jeszcze **walidacja po odpowiedzi:**  
`parse_ai_use_cases()` sprawdza, że `suggested_content_type` jest z listy dozwolonych (np. z `--content-type` lub `ALLOWED_CONTENT_TYPES`), a `category_slug` z listy `categories`; w razie błędu ustawiane są wartości domyślne (guide, pierwsza kategoria). Dodatkowo **deduplikacja** po tekście `problem` względem istniejących use case’ów (case-insensitive + proste dopasowanie „jeden zawiera drugi”).

---

## 5. Co jest już parametryzowane

| Parametr | Sposób | Domyślna wartość / zachowanie |
|----------|--------|-------------------------------|
| Liczba use case’ów | `--limit N` | 12 (`TARGET_USE_CASE_COUNT`) |
| Kategoria | `--category SLUG` | Wszystkie z configu (production + sandbox) |
| Typ treści | `--content-type TYPE` | Dowolny z how-to, guide, best, comparison; w tekście: „Prefer how-to or guide” |
| Lista kategorii | `content/config.yaml` | production_category + sandbox_categories |
| Model API | Zmienna środowiskowa `OPENAI_MODEL` | gpt-4o-mini |
| Adres API | `OPENAI_BASE_URL` | https://api.openai.com |

Stałe w kodzie (bez flag ani configu):

- `ALLOWED_CONTENT_TYPES` = ["how-to", "guide", "best", "comparison"]
- Tekst `instructions` (rola, dziedzina „AI marketing automation”, format JSON)
- Fragmenty user message: „specific, actionable”, „people actively search for”, „different from existing”
- Limit 50 słów kluczowych z artykułów (`keywords_list[:50]`)
- Cap łącznej listy use case’ów w pliku: `limit` (po dopisaniu nowych zostaje ostatnie `limit` wpisów)

---

## 6. Jak można to dalej modelować / parametryzować

- **Domena / nisza**  
  Zamienić na stałe „AI marketing automation” na zmienną (np. z configu lub `--domain`) i wstawiać ją do `instructions` i do zdania „people actively search for solutions to in **{domain}**”.

- **Instrukcje**  
  Czytać `instructions` z pliku (np. `content/prompts/use_cases_instructions.txt`) zamiast stringa w `build_prompt()` – wtedy wytyczne da się edytować bez zmiany kodu.

- **Wytyczne jakości**  
  Dodać opcjonalny plik lub listę zdań (np. „focus on B2B”, „avoid pricing”) i doklejać je do user message.

- **Limit słów kluczowych**  
  Zastąpić stałe `50` przez argument lub wpis w configu (np. `max_article_keywords: 80`).

- **Dozwolone typy**  
  Zamiast stałej `ALLOWED_CONTENT_TYPES` – lista z configu (wtedy `--content-type` i walidacja muszą z niej korzystać).

- **Stałe domyślne**  
  `TARGET_USE_CASE_COUNT` i domyślna kategoria fallback („ai-marketing-automation”) można przenieść do `config.yaml` jako np. `default_use_case_count` i `default_category_slug`.

Dokładna treść tego, co jest „dawane” w poleceniu generowania use case’ów, to powyższe `instructions` + złożony `input` (user message) z punktów 3.1–3.5; wytyczne to całość tych instrukcji i bloków, a parametryzacja jest częściowo już zaimplementowana (CLI + config), a częściowo możliwa przez rozszerzenie configu i plików promptów.
