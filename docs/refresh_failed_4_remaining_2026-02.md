# Pozostałe 4 artykuły – nie udało się odświeżyć (stan z dzisiaj)

Z oryginalnych 8 failed po odświeżeniu udało się naprawić 4. Poniżej lista **4 artykułów, które nadal failują**, przyczyny i środki zaradcze na przyszłość.

---

## Lista 4 artykułów (niewykonane odświeżenie)

| # | Slug (artykuł) |
|---|------------------------------------------|
| 1 | `2026-02-20-how-to-automate-the-curation-of-user-generated-content-for-brand-promotion-using-ai` |
| 2 | `2026-02-20-how-to-implement-ai-tools-to-personalize-video-marketing-content.audience_beginner` |
| 3 | `2026-02-22-best-implement-chatbots-for-customer-support-automation-with-ai.audience_beginner` |
| 4 | `2026-02-22-how-to-automate-troubleshooting-workflows-for-api-error-handling-in-marketing-tools.audience_professional` |

---

## Przyczyny (z `logs/refresh_failure_reasons.txt`)

| Slug | Przyczyna |
|------|-----------|
| 1 | **Bracket placeholders:** `[AgencyName]`, `[Insert Date]` |
| 2 | **Bracket placeholders:** `[Introduction]`, `[Identifying Pain Points]`, `[Value Proposition]`, `[Engagement Element]`, `[Desired Outcomes]` |
| 3 | **Forbidden pattern:** "unlimited" / "limit to" / "up to N" |
| 4 | **Bracket placeholders:** `[List of endpoints]`, `[email/SMS/Slack]` **oraz** **forbidden pattern:** "unlimited/limit/up to N" |

---

## Środki zaradcze wdrożone (na przyszłość)

### 1. Nowe wpisy w `_KNOWN_BRACKET_FALLBACKS` (fill_articles.py)

Dodane zamiany przed QA, żeby podobne placeholdery nie blokowały odświeżenia:

- `[AgencyName]` → "your agency"
- `[Insert Date]` → "the date"
- `[Introduction]` → "the introduction"
- `[Identifying Pain Points]` → "pain points"
- `[Value Proposition]` → "the value proposition"
- `[Engagement Element]` → "the engagement element"
- `[Desired Outcomes]` → "the desired outcomes"
- `[List of endpoints]` → "the list of endpoints"
- `[email/SMS/Slack]` → "your channel (e.g. email or Slack)"

**Efekt:** Przy kolejnym refreshu artykuły #1, #2 i #4 nie powinny failować z powodu tych bracket placeholderów (zostaną zastąpione przed QA).

### 2. Sanityzacja „unlimited / limit to / up to N” w `sanitize_filled_body` (fill_articles.py)

Dodana automatyczna zamiana w treści (przed QA):

- `unlimited` → "many"
- `limited to` → "capped at"
- `limit to` → "cap at"
- `up to <liczba>` (np. "up to 5") → "several"

**Efekt:** Artykuły #3 i #4 nie powinny failować z powodu forbidden pattern "unlimited/limit/up to N" – frazy zostaną zastąpione przed QA.

---

## Co zrobić z obecnymi 4 artykułami

1. **Uruchomić refresh ponownie** (np. z Flowtaro Monitor lub `refresh_articles.py`) – po wdrożonych zmianach te 4 pliki powinny przejść QA, o ile nie pojawią się inne problemy (np. nowe placeholdery).
2. **Ewentualnie ręczna korekta:** jeśli po ponownym refreshu nadal będzie fail, w plikach `.md`/`.html` można ręcznie zamienić pozostałe `[xxx]` lub frazy "unlimited"/"limit to"/"up to N" na dopuszczalne wersje i ponowić refresh.

---

## Rekomendacje na przyszłość

- **Placeholdery:** W razie kolejnych failed z powodu `[NowyTyp]` dodać go do `_KNOWN_BRACKET_FALLBACKS` w `fill_articles.py` (albo rozważyć szerszą regułę, np. zamiana dowolnego `[Słowo]` na wersję w cudzysłowie).
- **Forbidden phrases:** Nowe wzorce, które QA odrzuca, warto od razu dodać do `sanitize_filled_body` z bezpieczną zamianą, zamiast tylko do promptów – zmniejsza to liczbę failed przy tym samym modelu.
- **Monitoring:** Po każdym refreshu sprawdzać `logs/refresh_failure_reasons.txt` i ewentualnie uzupełniać listę fallbacków/sanityzacji o nowe przypadki.
