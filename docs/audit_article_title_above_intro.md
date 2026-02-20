# Audyt: brak tytułu artykułu nad „Introduction”

## Problem
Po wejściu w artykuł (klik w tytuł) na stronie widać treść, ale **nad sekcją „Introduction” nie ma widocznego tytułu artykułu**.

## Przyczyna

1. **Artykuły w HTML** (np. z `fill_articles` z outputem HTML) **nie zawierają H1 w treści**. Body zaczyna się od `<h2>Introduction</h2>`. Tytuł jest tylko w frontmatter (komentarz `<!-- title: "..." -->`) i w `<title>` strony – nie w body.
2. **Szablon `article.html`** wstawia tylko `<!-- ARTICLE_CONTENT -->`; nie ma w nim bloku z tytułem (H1) – tytuł jest wyłącznie w `<title>{{TITLE}}</title>` (zakładka przeglądarki).
3. **Render** składa treść jako `meta_html + body_html` (meta: kategoria, data, czas czytania, lead). Nie dodaje na górze H1 z tytułem z frontmatter.

Artykuły z **.md** mają w treści `# Tytuł`, więc po konwersji do HTML pojawia się `<h1>`. Przy **.html** (gdy w `content/articles/` jest plik .html i jest preferowany nad .md) body nie ma H1 → użytkownik widzi od razu meta + „Introduction”.

## Rekomendacja

- **Zawsze** wyświetlać tytuł artykułu (z frontmatter) jako **H1 na górze treści**, przed blokiem meta i przed „Introduction”.
- W `render_site.py`: przed złożeniem `full_body_html`:
  - dodać na początku **H1 z tytułem** (np. ten sam styl co na hubie: `text-2xl font-bold mb-6 text-[#17266B]`),
  - opcjonalnie **usunąć pierwszy `<h1>...</h1>` z `body_html`**, żeby przy artykułach .md nie było dwóch tytułów (jeden z szablonu, drugi z treści).

Dzięki temu zarówno artykuły .md, jak i .html będą miały jeden, widoczny tytuł nad „Introduction”.
