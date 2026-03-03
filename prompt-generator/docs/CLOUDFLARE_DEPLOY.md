# Cloudflare Workers (OpenNext) – wdrożenie

Aplikacja jest skonfigurowana do budowy i wdrożenia na Cloudflare Workers przy użyciu [@opennextjs/cloudflare](https://opennext.js.org/cloudflare/get-started).

## Różnice względem instrukcji „Vercel output”

- **Katalog build:** OpenNext dla Cloudflare generuje katalog **`.open-next`** (worker + assets), a nie `.vercel/output/static`. W `wrangler.jsonc` używane są `main: ".open-next/worker.js"` oraz `assets.directory: ".open-next/assets"`.
- **Preview:** Użyj `npm run preview` (buduje i uruchamia lokalnie w Wrangler). Nie używaj `wrangler pages dev .vercel/output/static`.
- **Deploy:** `npm run deploy` buduje i wdraża Workera; dla CI/CD ustaw Build command: `npx @opennextjs/cloudflare build`, Deploy command: `npx @opennextjs/cloudflare deploy`.

## Skrypty

| Skrypt | Opis |
|--------|------|
| `npm run preview` | `opennextjs-cloudflare build` + `opennextjs-cloudflare preview` – budowa i podgląd lokalny |
| `npm run deploy` | Budowa + wdrożenie na Cloudflare |
| `npm run upload` | Budowa + upload nowej wersji (bez natychmiastowego deployu) |
| `npm run cf-typegen` | Generuje `cloudflare-env.d.ts` z typami env |

## Zmienne środowiskowe

- **Lokalnie:** Skopiuj `.dev.vars.example` do `.dev.vars` i uzupełnij klucze (Stripe, OpenAI). Plik `.dev.vars` jest w `.gitignore`.
- **Produkcja:** Ustaw zmienne w panelu Cloudflare (Workers & Pages → projekt → Settings → Variables).

## Pierwszy build

Jeśli `npm run preview` zgłasza błąd typu `ERR_MODULE_NOT_FOUND` (np. `ansi-styles`), wykonaj:

```bash
rm -rf node_modules
npm install
npm run preview
```

Na Windows (PowerShell): usuń folder `node_modules`, potem `npm install` i `npm run preview`.

## Cloudflare Pages (Git)

Jeśli łączysz repozytorium z Cloudflare Pages / Workers Builds:

- **Build command:** `npx @opennextjs/cloudflare build`
- **Deploy command:** `npx @opennextjs/cloudflare deploy`
- **Build output directory:** nie ustawiaj katalogu „static” – deploy wysyła Workera z katalogu `.open-next`.
