# Instrukcja: zobaczenie paska nawigacji na żywo (generator.flowtaro.com)

Pasek nawigacji (logo + linki Flowtaro, Problem Fix & Find, Problem Fix & Find (PL), Prompt Generator, EN, PL) jest w kodzie aplikacji. Aby zobaczyć go na **https://generator.flowtaro.com/**, trzeba **zbudować i wdrożyć** aplikację na Cloudflare.

---

## Sposób 1: Deploy z komputera (CLI) – zalecany na start

### Krok 1: Wejście do katalogu generatora

W PowerShell (lub terminalu):

```powershell
cd c:\Users\kajspr07k\ACM\prompt-generator
```

### Krok 2: Zależności (jeśli jeszcze nie instalowane)

```powershell
npm install
```

### Krok 3: Logowanie do Cloudflare (jeśli jeszcze nie zalogowany)

```powershell
npx wrangler login
```

Otworzy się przeglądarka – zaloguj się do Cloudflare i zatwierdź dostęp. Wystarczy raz na komputer.

### Krok 4: Build i deploy

```powershell
npm run deploy
```

To polecenie:
1. Buduje aplikację pod Cloudflare (`opennextjs-cloudflare build` → katalog `.open-next/`).
2. Wgrywa Workera do Cloudflare i go aktywuje (`opennextjs-cloudflare deploy`).

Jeśli deploy się powiedzie, na końcu zobaczysz adres typu `https://flowtaro-prompt-generator.<konto>.workers.dev` oraz informację o wdrożeniu.

### Krok 5: Sprawdzenie na żywo

1. Otwórz **https://generator.flowtaro.com** (jeśli domena jest już podpięta do tego Workera).
2. Odśwież stronę (najlepiej Ctrl+F5 lub tryb incognito, żeby ominąć cache).
3. U góry strony powinien być widoczny **pasek nawigacji**: logo Flowtaro, linki (Flowtaro, Problem Fix & Find, Problem Fix & Find (PL), Prompt Generator, EN, PL).

---

## Sposób 2: Deploy z Gita (Cloudflare Workers Builds)

Jeśli generator.flowtaro.com jest budowany z repozytorium (Cloudflare łączy się z GitHubem i po pushu sam buduje i wdraża):

### Krok 1: Upewnij się, że zmiany są w repo

W katalogu **ACM** (nad `prompt-generator`):

```powershell
cd c:\Users\kajspr07k\ACM
git status
```

Powinny być zmiany w `prompt-generator/` (m.in. `app/components/SiteNav.tsx`, `app/layout.tsx`).

### Krok 2: Dodaj, commit, push

```powershell
git add prompt-generator/
git commit -m "Generator: pasek nawigacji (SiteNav) w layout"
git push origin main
```

(lub `master` zamiast `main`, zależnie od brancha.)

### Krok 3: Build w Cloudflare

- Wejdź na [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages**.
- Otwórz projekt przypisany do **generator.flowtaro.com** (np. „flowtaro-prompt-generator”).
- Po pushu Cloudflare powinien automatycznie uruchomić nowy build. Sprawdź **Deployments** – czy pojawił się nowy deployment z ostatniego commita.
- Jeśli buildów z Gita nie ma: w **Settings** → **Builds** upewnij się, że repo i branch są podłączone oraz że **Root directory** = `prompt-generator`, **Build command** = `npm run deploy` lub `npx @opennextjs/cloudflare build && npx wrangler deploy`.

### Krok 4: Sprawdzenie na żywo

Otwórz **https://generator.flowtaro.com**, odśwież (Ctrl+F5). Pasek nawigacji powinien być u góry.

---

## Jeśli nadal nie widać paska

1. **Cache przeglądarki** – spróbuj w trybie incognito lub innej przeglądarce.
2. **Ostatni deployment** – w Cloudflare → Workers & Pages → projekt → Deployments sprawdź, czy najnowszy deployment ma status **Success** i czy powstał **po** Twoich zmianach w kodzie.
3. **Domena** – upewnij się, że **generator.flowtaro.com** jest w **Custom domains** tego samego projektu Workera, który właśnie wdrożyłeś (Settings → Domains / Triggers).
4. **Zmienne środowiskowe** – przy pierwszym deployu Worker musi mieć ustawione **STRIPE_SECRET_KEY** i **OPENAI_API_KEY** (Settings → Variables). Bez nich strona może się nie budować lub nie działać poprawnie; pasek nawigacji nie zależy od tych zmiennych, ale brak ich może blokować udany deploy.

---

## Szybka ścieżka (CLI, skopiuj i wklej)

```powershell
cd c:\Users\kajspr07k\ACM\prompt-generator
npm install
npx wrangler login
npm run deploy
```

Potem otwórz https://generator.flowtaro.com i odśwież stronę (Ctrl+F5).
