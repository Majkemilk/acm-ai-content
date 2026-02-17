# Audyt CSS/HTML – brak stylów dla `.flowtaro-container`

## Opis problemu

W inspektorze przeglądarki element `.flowtaro-container` ma `margin: 0`, `padding: 0`, szerokość równą szerokości okna (np. 1350px). Reguły z `public/assets/styles.css` (w tym z `!important`) **w ogóle nie pojawiają się** w zakładce Styles.

## Wnioski z audytu

### 1. Plik CSS istnieje i ma poprawne reguły

- **Lokalizacja:** `public/assets/styles.css` – plik jest w repozytorium (nie jest generowany przez `render_site.py`).
- **Zawartość:** Klasa `.flowtaro-container` jest zdefiniowana z `max-width`, `margin-left/right: auto`, `padding-*` i `!important`.
- **Kopiowanie:** `render_site.py` **nie kopiuje** ani nie nadpisuje tego pliku (kopiuje tylko obrazy z `images/` do `public/images/`). Plik `public/assets/styles.css` jest zakładany jako istniejący plik źródłowy.

### 2. Generowany HTML jest poprawny

- W wygenerowanych plikach (np. `public/articles/.../index.html`) występuje:
  - `<div class="flowtaro-container">` – klasa jest w HTML.
  - `<link rel="stylesheet" href="/assets/styles.css">` – odwołanie do arkusza jest w `<head>`.
- Kolejność: w szablonie artykułu najpierw jest **Tailwind** (`<script src="https://cdn.tailwindcss.com"></script>`), potem **nasz CSS** (`<link ... href="/assets/styles.css">`). Ładowanie naszego pliku po Tailwindzie jest poprawne (nasze reguły z `!important` powinny mieć pierwszeństwo).

### 3. Główna przyczyna: ścieżka `/assets/styles.css` przy otwieraniu przez `file://`

- Wszystkie szablony i skrypty używają **ścieżki absolutnej**: `href="/assets/styles.css"`.
- Gdy strona jest otwierana **bez serwera** (np. przez dwuklik w pliku lub `file:///C:/.../public/articles/.../index.html`):
  - Przeglądarka interpretuje `/assets/styles.css` jako ścieżkę od **root systemu plików** (np. `file:///C:/assets/styles.css` lub `file:///assets/styles.css`), a **nie** od katalogu projektu.
  - Plik `public/assets/styles.css` **nie jest wtedy ładowany** (żądanie kończy się brakiem pliku lub innym zasobem).
  - W zakładce Styles nie widać żadnych reguł z naszego pliku – nie dlatego, że Tailwind je nadpisuje, ale dlatego, że **arkusz w ogóle nie został załadowany**.
- Tailwind działa, bo jest ładowany z pełnego URL: `https://cdn.tailwindcss.com` – niezależnie od protokołu strony.
- Efekt: kontener dostaje tylko style z Tailwinda i domyślne style przeglądarki (margin/padding 0), stąd pełna szerokość i brak naszych paddingów/marginów.

### 4. Serwer lokalny z niewłaściwego katalogu

- Jeśli uruchamiany jest np. `python -m http.server 8000` z katalogu **głównego projektu** (`ACM/`), a nie z `public/`:
  - URL `http://localhost:8000/assets/styles.css` wskazuje na `ACM/assets/styles.css` – taki katalog/plik może nie istnieć (style są w `public/assets/`).
  - W efekcie nasz CSS znowu się nie ładuje.
- Aby `/assets/styles.css` działał, serwer musi być uruchomiony w katalogu **`public/`** (np. `cd public && python -m http.server 8000`), wtedy `/` = `public/` i `/assets/styles.css` = `public/assets/styles.css`.

### 5. Brak innych przyczyn w kodzie

- Nie ma globalnego resetu typu `* { margin: 0; padding: 0 }` w `styles.css`, który zerowałby tylko nasz kontener; reset `body` nie wpływa na `.flowtaro-container`.
- Klasa `flowtaro-container` nie jest zmieniana ani usuwana przez JavaScript w szablonach.
- W `render_site.py` nie ma błędów ani pominięć przy zapisie HTML – szablony są wypełniane, a link do CSS jest wpisany.

## Rekomendowane rozwiązanie

**Użyć względnych ścieżek do arkusza CSS** w zależności od lokalizacji wygenerowanego pliku HTML:

| Plik wyjściowy | Ścieżka do CSS |
|----------------|----------------|
| `public/index.html` | `assets/styles.css` |
| `public/privacy.html` | `assets/styles.css` |
| `public/articles/<slug>/index.html` | `../../assets/styles.css` |
| `public/hubs/<slug>/index.html` | `../../assets/styles.css` |

Dzięki temu:

- Przy **otwieraniu przez `file://`** (dwuklik w plik) przeglądarka poprawnie ładuje `public/assets/styles.css` (np. z `public/articles/xxx/index.html` ścieżka `../../assets/styles.css` wskazuje na ten sam katalog co przy serwerze).
- Przy **serwerze z rootem w dowolnym katalogu** (np. `public/`) względna ścieżka nadal rozwiązuje się poprawnie do tego samego pliku CSS.

**Wdrożono (w tej samej sesji):**
- W szablonach `templates/article.html`, `templates/index.html`, `templates/hub.html` link do CSS ma postać `href="{{STYLESHEET_HREF}}"`.
- W `render_site.py`: przy renderze artykułu i huba ustawiane jest `../../assets/styles.css`, przy indeksie i privacy – `assets/styles.css`. Fallbacki (gdy brak szablonu) używają tych samych ścieżek względnych.
- Po ponownym uruchomieniu `python scripts/render_site.py` wygenerowane pliki mają poprawne względne ścieżki; przy otwieraniu stron przez `file://` (np. dwuklik w `index.html`) arkusz `styles.css` ładuje się poprawnie i reguły `.flowtaro-container` są stosowane.

## Podsumowanie

| Pytanie | Odpowiedź |
|--------|-----------|
| Czy `public/assets/styles.css` istnieje i ma reguły `.flowtaro-container`? | Tak. |
| Czy `render_site.py` nadpisuje lub kopiuje ten plik? | Nie. |
| Czy w HTML jest poprawny link do CSS? | Tak, ale tylko przy serwerze z rootem w `public/`. |
| Czy kolejność ładowania (Tailwind → nasz CSS) jest ok? | Tak. |
| Dlaczego w Styles nie widać naszych reguł? | Przy `file://` lub złym root serwera plik CSS **nie jest ładowany** – stąd brak jakichkolwiek reguł z naszego pliku. |
| Czy Tailwind „nadpisuje” nasze style? | Nie – nasze reguły w ogóle nie dochodzą do głosu, bo arkusz nie jest załadowany. |

Wdrożenie relative paths (jak w powyższej tabeli) usuwa problem zarówno przy podglądzie przez `file://`, jak i przy serwerze.
