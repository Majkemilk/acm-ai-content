# Instrukcja: build i deploy Prompt Generator (generator.flowtaro.com)

Szczegółowe kroki, aby zbudować aplikację Next.js i wdrożyć ją na Cloudflare Workers, tak aby była dostępna pod **https://generator.flowtaro.com**. Po wdrożeniu logo na górze strony przekierowuje do **https://flowtaro.com/**.

---

## 1. Wymagania

- **Node.js** 18+ (zalecane 20 LTS)
- **npm** (zazwyczaj z Node)
- **Konto Cloudflare** z dostępem do Workers
- **Klucze API:** Stripe (Secret Key), OpenAI (API Key) – do płatności i generowania promptów

---

## 2. Środowisko lokalne

### 2.1 Instalacja zależności

W katalogu projektu (ACM), wejdź do `prompt-generator` i zainstaluj pakiety:

```powershell
cd c:\Users\kajspr07k\ACM\prompt-generator
npm install
```

(W systemie Linux/macOS: `cd /ścieżka/do/ACM/prompt-generator` i `npm install`.)

### 2.2 Zmienne środowiskowe (lokalny preview)

Dla lokalnego podglądu (np. `npm run preview`) potrzebne są klucze w pliku **`.dev.vars`** (nie commituj tego pliku).

1. Skopiuj przykładowy plik (jeśli istnieje `.dev.vars.example`) lub utwórz `.dev.vars` w `prompt-generator/`.
2. Uzupełnij wartości (jedna zmienna w linii, format `NAZWA=wartość`):

```ini
STRIPE_SECRET_KEY=sk_test_XXXXXXXX
OPENAI_API_KEY=sk-proj-XXXXXXXX
```

Dla produkcji użyjesz tych samych nazw zmiennych w panelu Cloudflare.

### 2.3 Build (bez deployu)

Sprawdzenie, czy projekt się buduje:

```powershell
npm run build
```

To uruchamia standardowy build Next.js. Do deployu na Cloudflare używa się builda OpenNext (krok 3).

### 2.4 Preview lokalny (OpenNext + Wrangler)

Pełny build pod Cloudflare i podgląd lokalny:

```powershell
npm run preview
```

Wymaga zalogowania do Cloudflare (`npx wrangler login`, jeśli jeszcze nie). Otwórz w przeglądarce adres podany w terminalu (np. `http://localhost:8788`). Sprawdź, czy logo u góry prowadzi do flowtaro.com (w preview link może być ustawiony na https://flowtaro.com/).

---

## 3. Deploy na Cloudflare

Są dwa sposoby: **z poziomu komputera (CLI)** albo **z Git w panelu Cloudflare (Workers Builds)**.

---

### Opcja A: Deploy z komputera (CLI)

#### Krok A1: Logowanie do Cloudflare

```powershell
npx wrangler login
```

Otworzy się przeglądarka – zaloguj się do konta Cloudflare i zatwierdź dostęp.

#### Krok A2: Zmienne środowiskowe (Production)

Klucze muszą być ustawione w Cloudflare jako **Variables** (lub **Secrets**) dla Workera.

1. W przeglądarce: [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages**.
2. Wybierz Worker **flowtaro-prompt-generator** (jeśli już istnieje) albo utworzysz go przy pierwszym deployu.
3. **Settings** → **Variables** (lub **Variables and Secrets**).
4. W sekcji **Environment Variables** (Production) dodaj:
   - `STRIPE_SECRET_KEY` = twój klucz Stripe (np. `sk_live_...` dla produkcji),
   - `OPENAI_API_KEY` = twój klucz OpenAI.
5. Zapisz (Save).

Alternatywa z CLI (po pierwszym deployu):

```powershell
npx wrangler secret put STRIPE_SECRET_KEY
npx wrangler secret put OPENAI_API_KEY
```

(Wpiszesz wartość po Enter; nie będzie ona widoczna w logach.)

#### Krok A3: Build i deploy

W katalogu `prompt-generator`:

```powershell
npm run deploy
```

To wykonuje:

1. `opennextjs-cloudflare build` – buduje aplikację do katalogu `.open-next/` (worker + assets),
2. `opennextjs-cloudflare deploy` – wgrywa Workera do Cloudflare i go aktywuje.

Po zakończeniu zobaczysz adres typu `https://flowtaro-prompt-generator.<twoje-konto>.workers.dev`.

#### Krok A4: Domena własna generator.flowtaro.com

1. W Cloudflare: **Workers & Pages** → **flowtaro-prompt-generator** → **Custom Domains** (lub **Triggers** → **Custom Domains**).
2. **Add custom domain** → wpisz **generator.flowtaro.com**.
3. Zatwierdź. Jeśli DNS domeny flowtaro.com jest w Cloudflare, rekord (CNAME lub inny) często dodawany jest automatycznie. W przeciwnym razie u rejestrara ustaw CNAME: `generator` → wartość podaną przez Cloudflare.

Po propagacji DNS strona będzie dostępna pod **https://generator.flowtaro.com**.

---

### Opcja B: Deploy z Git (Cloudflare Workers Builds)

Build i deploy z repozytorium przy każdym pushu.

#### Krok B1: Połączenie repozytorium

1. Cloudflare: **Workers & Pages** → **Create application** → **Create Worker** → **Deploy with Workers Builds** (lub **Connect to Git**).
2. Wybierz **GitHub** (lub GitLab), autoryzuj, wybierz repozytorium (np. ACM).
3. **Branch:** np. `main`.
4. **Root directory:** ustaw **`prompt-generator`** (ważne – build ma działać w tym katalogu).
5. **Build configuration:**
   - **Build command:** `npx @opennextjs/cloudflare build`
   - **Build output directory:** zostaw puste (OpenNext sam tworzy `.open-next`; deploy nie używa „static output” jak przy Pages).
   - **Deploy command** (jeśli jest): `npx wrangler deploy` albo zostaw domyślny (często Workers Builds sam wywołuje deploy po buildzie; wtedy Build command może być tylko `npx @opennextjs/cloudflare build`, a deploy jest w jednym kroku).

Jeśli w UI jest jedno pole „Build command”, wpisz:

```bash
npx @opennextjs/cloudflare build && npx wrangler deploy
```

(albo tylko `npm run deploy`, jeśli w `package.json` jest już `"deploy": "opennextjs-cloudflare build && opennextjs-cloudflare deploy"` – wtedy w Build command ustaw: `npm run deploy`.)

#### Krok B2: Zmienne środowiskowe w Cloudflare

W ustawieniach projektu (Workers Builds):

- **Settings** → **Variables and Secrets** (lub **Environment variables**).
- Dla **Production** dodaj:
  - `STRIPE_SECRET_KEY`
  - `OPENAI_API_KEY`

Wartości ustaw raz i zapisz; przy kolejnych buildach będą dostępne dla Workera.

#### Krok B3: Pierwszy deploy

- **Save** / **Deploy** – Cloudflare zbuduje projekt z Git i wdroży Workera.
- W **Deployments** sprawdź, czy build zakończył się sukcesem.

#### Krok B4: Domena generator.flowtaro.com

Jak w **Krok A4**: w projekcie Worker → **Custom Domains** → **Add** → **generator.flowtaro.com**.

---

## 4. Weryfikacja po wdrożeniu

1. Otwórz **https://generator.flowtaro.com** (lub adres `*.workers.dev` przed dodaniem domeny).
2. Sprawdź, czy strona generatora się ładuje (formularz, poziom Standard/Advanced/Expert).
3. **Kliknij logo u góry strony** – powinno otworzyć **https://flowtaro.com/** w tej samej lub nowej karcie (w zależności od implementacji linku).
4. Sprawdź też podstronę **/success** (np. po testowej płatności) – logo tam również powinno prowadzić do https://flowtaro.com/.

---

## 5. Podsumowanie: logo na wszystkich domenach

| Miejsce | Adres logo (docelowy) |
|--------|------------------------|
| flowtaro.com (strona główna, artykuły, huby) | https://flowtaro.com/ |
| pl.flowtaro.com (strona PL, artykuły, huby) | https://flowtaro.com/ |
| generator.flowtaro.com (Prompt Generator) | https://flowtaro.com/ |

Implementacja: w kodzie statycznym (render_site) i w komponencie nawigacji generatora (`SiteNav.tsx`) link w logo jest ustawiony na `https://flowtaro.com/`. Po każdym wdrożeniu (content + generator) kliknięcie logo wszędzie przekierowuje na główną stronę Flowtaro.

---

## 6. Częste problemy

- **Build się wywala (np. ERR_MODULE_NOT_FOUND):** usuń `node_modules` i `.open-next`, potem `npm install` i ponownie `npm run build` / `npm run deploy`.
- **Stripe/OpenAI nie działają w produkcji:** sprawdź, czy zmienne `STRIPE_SECRET_KEY` i `OPENAI_API_KEY` są ustawione w Cloudflare dla **Production** (Settings → Variables).
- **Domena generator.flowtaro.com nie działa:** sprawdź DNS (CNAME dla `generator`) i w Cloudflare Custom Domains status domeny (np. „Active”).
- **Logo nie przekierowuje:** upewnij się, że po zmianach w kodzie zrobiłeś ponowny build i deploy (content: `render_site.py`; generator: `npm run deploy` lub push do Git przy Workers Builds).
