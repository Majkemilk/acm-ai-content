# Lista miejsc: basic / standard / expert → standard / advanced / expert

## prompt-generator (kod + copy)

| Plik | Typ | Opis |
|------|-----|------|
| `lib/form-schema.ts` | kod | `level: z.enum(["basic", "standard", "expert"])` → `["standard", "advanced", "expert"]` |
| `lib/form-schema.ts` | kod | `LEVEL_CENTS`: klucze basic/standard/expert → standard/advanced/expert |
| `lib/form-schema.ts` | kod | `superRefine`: warunek audience/format `level === "standard" \|\| "expert"` → `"advanced" \|\| "expert"` |
| `lib/metaPrompt.ts` | kod | Stałe: META_PROMPT_BASIC → META_PROMPT_STANDARD, META_PROMPT_STANDARD → META_PROMPT_ADVANCED, EXPERT bez zmiany |
| `lib/metaPrompt.ts` | copy | Komentarz: "basic / standard / expert" → "standard / advanced / expert" |
| `app/api/get-prompt/route.ts` | kod | Import: BASIC→STANDARD, STANDARD→ADVANCED |
| `app/api/get-prompt/route.ts` | kod | LEVEL_INSTRUCTIONS: klucze basic/standard/expert → standard/advanced/expert |
| `app/api/get-prompt/route.ts` | kod | Mapowanie level → systemPrompt: standard/advanced/expert, default "standard" |
| `app/api/create-checkout/route.ts` | kod | metadata.level (wartość z formularza) – zmiana przez form-schema + page |
| `app/page.tsx` | kod | LEVEL_PRICES, LEVEL_DESCRIPTIONS, defaultValuesByLevel: klucze standard/advanced/expert |
| `app/page.tsx` | kod | Radio: value + label Standard (€0.50), Advanced (€1.00), Expert (€3.00) |
| `app/page.tsx` | kod | Warunki: audience/format/constraints `level === "advanced" \|\| "expert"`; expert-only bez zmiany |
| `app/page.tsx` | kod | defaultValues level "standard", defaultValuesByLevel.standard |
| `app/page.tsx` | copy | TOOLTIPS.level: "Standard: ... Advanced: ... Expert: ..." |
| `app/page.tsx` | copy | "What makes Flowtaro different": "(Standard, Advanced, Expert)" |
| `app/page.tsx` | copy | "How it works" – Choose your level: Standard (...), Advanced (...), Expert (...) |
| `app/page.tsx` | copy | "What you get": Standard:/Advanced:/Expert: + LEVEL_DESCRIPTIONS |
| `app/success/page.tsx` | - | Brak użycia nazw poziomów |

## Poza prompt-generator

- Stripe: nie wdrożony; metadata w checkout będzie wysyłane z nowymi wartościami (standard/advanced/expert).
- content/, docs/: słowa "basic"/"standard"/"expert" w artykułach oznaczają zwykły język, nie poziom produktu – bez zmian.
