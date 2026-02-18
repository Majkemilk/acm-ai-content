# Audyt: formatowanie i marginesy (lokalnie vs www)

## Problem

Po zmianie ścieżek CSS na bezwzględne (`/assets/styles.css`) **ani strony w `/public` otwierane lokalnie, ani opublikowane na www nie miały marginesów** (m.in. `.flowtaro-container`, `.article-body`).

---

## Pełna logika wpływająca na formatowanie

### 1. Źródło stylów

- **`public/assets/styles.css`** – główny arkusz z:
  - `.flowtaro-container`: `max-width: 960px`, `margin-left/right: auto`, `padding` (z `!important`)
  - `.article-body`: `max-width: 70ch`, `margin-left/right: auto`, padding
  - style dla `body`, nagłówków, list, tabel itd.
- **Tailwind CDN** (`https://cdn.tailwindcss.com`) – ładowany w każdej stronie; daje preflight (reset) i klasy utility.

### 2. Jak ustawiana jest ścieżka do CSS

| Miejsce | Plik / funkcja | Gdzie ustawiane |
|--------|----------------|------------------|
| Artykuły (szablon) | `templates/article.html` | `{{STYLESHEET_HREF}}` → w `render_site.py` zamieniane na wartość |
| Artykuły (fallback) | `_wrap_page()` w `render_site.py` | Bezpośrednio w HTML |
| Huby | `templates/hub.html` + fallback | Jak wyżej |
| Index, Privacy | `templates/index.html` + fallback | Jak wyżej |

Wartości wstawiane przez `render_site.py`:

- **Strony w `public/` (index, privacy):** `assets/styles.css` (względna, jeden poziom).
- **Strony w `public/articles/{slug}/` i `public/hubs/{slug}/`:** `../../assets/styles.css` (względna, dwa poziomy w górę).

### 3. Rozwiązywanie ścieżek przez przeglądarkę

- **Ścieżka względna** (np. `../../assets/styles.css`) – rozwiązywana względem **URL bieżącej strony** (nie ścieżki pliku na dysku).
- **Ścieżka bezwzględna od roota** (np. `/assets/styles.css`) – rozwiązywana względem **origin** (schemat + host + port).

**Otwarcie z dysku (file://):**

- URL strony: np. `file:///C:/Users/.../ACM/public/articles/slug/index.html`
- Origin: `file:///C:` (lub inny dysk)
- Dla **`/assets/styles.css`** przeglądarka prosi: `file:///C:/assets/styles.css` → **plik nie istnieje** → CSS się nie ładuje → brak marginesów i innych stylów z `styles.css`.
- Dla **`../../assets/styles.css`** przeglądarka idzie w górę od `.../public/articles/slug/` i trafia na `.../public/assets/styles.css` → **plik jest** → CSS się ładuje.

**Strona na serwerze (https):**

- URL: np. `https://domena.pl/articles/slug/`
- Dla **`../../assets/styles.css`**: `https://domena.pl/assets/styles.css` → poprawne, o ile serwer serwuje `public/` jako root i ma `public/assets/styles.css` pod `/assets/styles.css`.
- Dla **`/assets/styles.css`**: też `https://domena.pl/assets/styles.css` → poprawne przy tym samym deployu. Problem z brakiem marginesów na www po zmianie na `/` mógł wynikać z innej konfiguracji (np. base URL, subkatalog) lub cache – bez szczegółów hostingu nie da się tego rozstrzygnąć.

### 4. Kolejność ładowania (Tailwind vs styles.css)

- W **article**: najpierw `<script src="...tailwindcss.com">`, potem `<link rel="stylesheet" href="...styles.css">` → nasz CSS ładuje się po skrypcie Tailwind; Tailwind i tak wstrzykuje style asynchronicznie, więc kolejność w DOM może być różna.
- W **index**: najpierw `<link ... styles.css`, potem `<script> Tailwind` → nasz CSS wcześniej, potem wstrzyknięty Tailwind.
- W **styles.css** reguły `.flowtaro-container` mają `!important`, więc wygrywają z typowymi klasami Tailwind.

**Wniosek:** Gdy **styles.css w ogóle się ładuje**, marginesy i kontener powinny działać. Główny problem to **brak załadowania** pliku CSS (np. przez złą ścieżkę przy file:// lub na serwerze).

### 5. Struktura HTML

- Artykuły: `<div class="flowtaro-container">` → `<article class="article-body">` → treść. Zgodne z selektorami w `styles.css`.
- Index/Privacy: też używają `.flowtaro-container`. Struktura jest spójna.

---

## Wnioski

1. **Przyczyna braku marginesów po zmianie na `/assets/styles.css`:**
   - **Lokalnie (file://):** Ścieżka `/assets/styles.css` jest rozwiązywana od roota dysku (`file:///C:/assets/...`), więc `public/assets/styles.css` nie jest nigdy brany pod uwagę → **CSS się nie ładuje** → brak marginesów.
   - **Na www:** Teoretycznie `/assets/styles.css` może być poprawne; jeśli mimo to marginesów nie było, możliwe przyczyny to: publikacja w subkatalogu bez poprawnego base URL, inna konfiguracja serwera lub cache (stary HTML / stary CSS).

2. **Ścieżki względne** są konieczne, jeśli:
   - strona ma działać przy **otwieraniu plików z dysku** (file://),
   - a jednocześnie ma działać na **normalnym hostingu**, gdzie `public/` jest rootem (wtedy `../../assets/styles.css` i `assets/styles.css` rozwiążą się poprawnie).

3. **Wdrożona poprawka:** Przywrócono ścieżki względne:
   - **index, privacy** (w `public/`): `assets/styles.css`
   - **artykuły, huby** (w `public/.../index.html`): `../../assets/styles.css`  
   Dzięki temu CSS ładuje się zarówno lokalnie (file://), jak i na serwerze przy standardowym deployu `public/` jako root.

4. **Na przyszłość:**
   - Jeśli strona będzie serwowana **z subkatalogu** (np. `https://domena.pl/blog/`), trzeba będzie dodać np. zmienną `BASE_URL` lub `<base href="...">` i budować ścieżki do CSS (i ewentualnie innych zasobów) od tego base.
   - Dla pewności, że na produkcji zawsze ładuje się dobry CSS, warto po wdrożeniu sprawdzić w DevTools (Zakładka Network) czy request do `styles.css` zwraca 200 i czy w zakładce Elements widać załadowane reguły `.flowtaro-container` i `.article-body`.

---

## Stan po audycie (render_site.py)

- Artykuły (szablon + `_wrap_page`): `../../assets/styles.css`
- Huby (szablon + fallback): `../../assets/styles.css`
- Index (szablon + fallback): `assets/styles.css`
- Privacy (szablon + fallback): `assets/styles.css`

Po ponownym uruchomieniu `python scripts/render_site.py` i odświeżeniu stron (lokalnie i na www) marginesy powinny być widoczne, o ile serwer poprawnie serwuje pliki z `public/`.
