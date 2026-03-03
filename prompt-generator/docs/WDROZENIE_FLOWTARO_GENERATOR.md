# Wdrożenie Flowtaro Prompt Generator

Proces: **GitHub → Cloudflare Workers → domena generator.flowtaro.com → Stripe Live**.

---

## Krok 1 – GitHub

- Repozytorium: **acm-ai-content** (https://github.com/Majkemilk/acm-ai-content.git).
- Katalog **prompt-generator** musi być w repo (obecnie jest nieśledzony – trzeba go dodać i wypchnąć).
- W Cloudflare później ustawisz **Root directory**: `prompt-generator`.

**Działanie użytkownika:** zob. instrukcję poniżej w rozmowie (dodanie, commit, push).

---

## Krok 2 – Cloudflare Workers (Builds)

- Połączenie z Git (GitHub), branch np. `main`.
- **Root directory:** `prompt-generator`.
- **Build command:** `npx opennextjs-cloudflare build`
- **Deploy:** Cloudflare Workers Builds uruchomi build, potem deploy (np. `npx wrangler deploy` lub odpowiednik w UI).
- **Zmienne środowiskowe** (Production):  
  `STRIPE_SECRET_KEY`, `OPENAI_API_KEY`, ewentualnie `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` – ustawione w dashboardzie Workers.

---

## Krok 3 – Domena generator.flowtaro.com

- W Cloudflare: Workers & Pages → wybrany Worker → **Custom Domains** → Add `generator.flowtaro.com`.
- U rejestrara domeny (jeśli DNS nie jest w Cloudflare): CNAME `generator` → wskazanie podaną przez Cloudflare wartość (np. `xxx.workers.dev` lub target dla Workers).

---

## Krok 4 – Stripe Live

- Aktywacja konta Live w Stripe, wygenerowanie kluczy Live.
- W Cloudflare (Workers): podmiana zmiennych na klucze Live, redeploy / ponowne wdrożenie z Git.

---

*Szczegółowe instrukcje dla każdego kroku są podawane w rozmowie z asystentem.*
