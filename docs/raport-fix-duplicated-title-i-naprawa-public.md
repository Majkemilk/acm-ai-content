# Raport: co zmienił fix_duplicated_title_prefix.py i dlaczego w public/articles nadal są duble

## 1. Co zmienia skrypt

**Skrypt `scripts/fix_duplicated_title_prefix.py` działa wyłącznie na katalogu `content/articles/`.**

- **Modyfikowane pliki:** tylko pliki w `content/articles/` (rozszerzenia `.md` i `.html`).
- **Modyfikowane pola:** w **frontmatter** każdego pliku:
  - **title** – zamiana zduplikowanego prefiksu na pojedynczy (np. "How to how to X" → "How to X").
  - **primary_keyword** – ustawiane na `lowercase(nowy tytuł)`.
- **Niemodyfikowane:** katalog `public/articles/` w ogóle nie jest przez skrypt otwierany ani zapisywany.

Dlatego po uruchomieniu `--confirm` poprawione są **tylko** metadane (title, primary_keyword) w plikach źródłowych w `content/articles/`. Strony w `public/articles/` pozostają bez zmian.

---

## 2. Skąd bierze się treść w public/articles

Strony w `public/articles/{slug}/index.html` **nie są** aktualizowane przez żaden skrypt korekty tytułów. Powstają wyłącznie w wyniku uruchomienia **`scripts/render_site.py`**, który:

1. Czyta listę artykułów „na żywo” z `content/articles/` (get_production_articles).
2. Dla każdego artykułu bierze **frontmatter** (w tym **title**) z pliku `.md` lub `.html` w `content/articles/`.
3. Generuje pełną stronę HTML i zapisuje ją w `public/articles/{slug}/index.html`.  
   Tytuł wyświetlany na stronie (np. w `<title>`, w nagłówku H1) pochodzi z **meta["title"]** z frontmatteru, a nie z pierwszego nagłówka w treści.

**Wniosek:** Dopóki po poprawieniu frontmatteru w `content/articles/` nie uruchomisz ponownie **render_site.py**, pliki w `public/articles/` nadal będą zawierać **stare** tytuły (w tym zduplikowane prefiksy).

---

## 3. Dlaczego nadal widzisz duble

Możliwe przyczyny:

1. **Brak ponownego renderu**  
   Po uruchomieniu `fix_duplicated_title_prefix.py --confirm` nie został uruchomiony **`python scripts/render_site.py`**. Wtedy:
   - W `content/articles/` masz już poprawne **title** (i primary_keyword) w frontmatterze.
   - W `public/articles/` nadal leży stara wersja stron wygenerowana **przed** korektą.

2. **Duble w treści źródłowej (body)**  
   Skrypt poprawia **wyłącznie frontmatter** (title, primary_keyword). **Nie** zmienia pierwszej linii z nagłówkiem w treści (np. `# How to how to ...` w pliku `.md`).  
   Render_site i tak **nie używa** tego nagłówka do tytułu strony: usuwa pierwszy H1 z body i wstawia jeden H1 z `meta["title"]`.  
   W efekcie:
   - Na **stronie WWW** (po ponownym renderze) tytuł będzie poprawny.
   - W **pliku .md** w `content/articles/` nadal może być stary nagłówek `# How to how to ...` – to tylko niespójność w źródle.

---

## 4. Co zrobić, żeby poprawić tytuły w public/articles

### Krok 1: Ponowny render strony (obowiązkowy)

Uruchom z katalogu projektu:

```bash
python scripts/render_site.py
```

To wygeneruje na nowo wszystkie strony w `public/articles/` na podstawie **aktualnego** frontmatteru z `content/articles/`. Tytuły na stronie (i w `<title>`) będą wtedy bez zduplikowanych prefiksów.

Opcjonalnie (dla spójności huba i sitemapy):

```bash
python scripts/generate_hubs.py
python scripts/generate_sitemap.py
```

(Hub i sitemap też korzystają z get_production_articles, więc po korekcie tytułów w content mają już poprawne dane; powyższe polecenia odświeżą pliki wynikowe.)

---

## 5. Pozostałe duble: pierwszy nagłówek w treści (.md)

W wielu plikach `.md` w `content/articles/` **pierwszy nagłówek** (np. `# How to how to ...`) nadal zawiera zduplikowany prefiks. Skrypt go nie ruszał.

- **Wpływ na WWW:** brak – render_site używa `meta["title"]` i usuwa pierwszy H1 z body.
- **Wpływ na źródło:** niespójność (frontmatter poprawny, pierwszy # w pliku – nie).

### Propozycja naprawy (opcjonalna)

**Opcja A – rozszerzenie skryptu (np. `fix_duplicated_title_prefix.py`):**

- Dla każdego pliku `.md` w `content/articles/`:
  - po korekcie frontmatteru (lub jeśli tytuł w frontmatter już był poprawny),
  - znaleźć **pierwszą linię** zaczynającą się od `# ` (po ewentualnych pustych na początku body),
  - jeśli ta linia zaczyna się od jednego z wzorców ("How to how to ", "Guide to how to ", "Best how to ", "Best best "), zamienić ją na linię z pojedynczym prefiksem, używając **już poprawionego** tytułu z frontmatteru (np. `# ${title}\n`).
- Dla plików `.html` w `content/articles/`: jeśli w body jest pierwszy `<h1>...</h1>` z tymi samymi wzorcami, można go zastąpić wersją z poprawionym tytułem (np. wziętym z frontmatteru w komentarzu).  
  (W praktyce wiele .html w content nie ma H1 na początku body – wtedy ten krok nie jest potrzebny.)

**Opcja B – osobny skrypt (np. `fix_duplicated_h1_in_body.py`):**

- Działa tylko na treści (body): pierwszy `# ...` w .md i ewentualnie pierwszy `<h1>...</h1>` w .html.
- Wykrywa zduplikowane prefiksy i zamienia na wersję zgodną z tytułem z frontmatteru (albo z tą samą logiką co w fix_duplicated_title_prefix).
- Uruchamiany ręcznie lub po `fix_duplicated_title_prefix.py --confirm`.

Rekomendacja: **najpierw uruchomić `render_site.py`** (wtedy public/articles będzie miał poprawne tytuły). Ewentualną korektę pierwszego nagłówka w body (Opcja A lub B) traktować jako porządek w źródle, bez wpływu na to, co jest już na stronie.

---

## 6. Podsumowanie

| Miejsce | Co zrobił skrypt | Co jeszcze zrobić |
|--------|-------------------|-------------------|
| **content/articles/*.md, *.html** | Poprawiony **frontmatter** (title, primary_keyword). | Opcjonalnie: poprawić **pierwszą linię #** w body .md (i ewent. pierwszy H1 w body .html), żeby usunąć duble w źródle. |
| **public/articles/** | Nic (skrypt tam nie zapisuje). | **Uruchomić `python scripts/render_site.py`** – wtedy tytuły na stronach (i w public) będą poprawne. |

Po wykonaniu **render_site.py** tytuły w `public/articles` powinny być już bez zduplikowanych prefiksów. Jeśli po tym kroku nadal widzisz duble w konkretnym artykule, można wtedy zweryfikować ten jeden plik (content + wygenerowany HTML).
