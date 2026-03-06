# Zakładka „Generuj łatwo artykuły” — podsumowanie i pipeline

## Podsumowanie zmian

### Nowa zakładka
- **Nazwa:** „Generuj łatwo artykuły” (PL) / „Generate articles (easy)” (EN).
- **Lokalizacja:** Obok zakładki „Generuj artykuły” w notebooku (zaraz po niej).
- **Obecna zakładka** „Generuj artykuły” pozostaje bez zmian.

### Przyciski (identyczne jak w „Generuj artykuły”)
- **Uruchom** (`btn.run`) — uruchamia pełną sekwencję 4 kroków (generate_use_cases → generate_queue → generate_articles → fill_articles).
- **Generuj z podglądem** (`wf.preview_btn`) — uruchamia tylko pierwsze 3 kroki; po zakończeniu pokazuje okno wyboru artykułów do wypełnienia (fill); po wyborze wykonuje krok 4 (fill_articles) dla wybranych.
- **Anuluj** (`btn.cancel`) — przerywa bieżące uruchomienie.

### Sekcje UI (A–E)
- **A. Gdzie trafią artykuły:** Kategoria główna huba (dropdown z `use_case_defaults`), podpowiedź.
- **B. Problemy i obszar tematyczny:** Pole problemu bazowego, listy „Problemy sugerowane” i „Obszar tematyczny (sandbox)” z przyciskami Dodaj/Usuń.
- **C. Limit pomysłów i odbiorcy:** Podpowiedzi (szary, kursywa) jak w Konfiguracji: `config.batch_desc`, `config.pyramid_desc`. Spinbox limitu (1–12), etykiety Beginner / Intermediate / Professional i trzy spinboxy piramidy.
- **D. Typy treści:** Checkbox „Wszystkie” + grupy Playbook, Produktowe, Recenzja. Przy etykietach grup wyjaśnienie w **tekście wyszarzonym i pochyłym** (bez dymków); przy każdym typie — tooltip (dymek) `easy.tt_*`.
- **E. Kroki 2–4:** Parametry dla generate_queue, generate_articles, fill_articles (te same widgety co w workflow).

### Zapis konfiguracji
Przy **Uruchom** i **Generuj z podglądem** przed startem wywoływane jest `_save_config_and_sync()`:
- Zapis do `config.yaml`: `production_category`, `hub_slug`, `sandbox`, `suggested_problems`, `use_case_batch_size`, `use_case_audience_pyramid`, `category_mode="production_only"`.
- Aktualizacja pliku `content/use_case_allowed_categories.json` przez `sync_allowed_categories_file`.

### i18n
- Klucze: `tab.easy_workflow`, `easy.section_where`, `easy.section_problems`, `easy.section_limit`, `easy.section_content_types`, `easy.category_hint`, oraz tooltipy typów treści `easy.tt_*`.

---

## Workflow pełnego pipeline („po nowemu”)

### Kolejność kroków (4 akcje)
1. **generate_use_cases** — generowanie pomysłów use case’ów (argumenty z sekcji A + D: `--category`, opcjonalnie `--content-type`).
2. **generate_queue** — budowa kolejki (parametry z sekcji E, krok 2).
3. **generate_articles** — generowanie szkieletów artykułów (parametry z sekcji E, krok 3).
4. **fill_articles** — wypełnianie treścią (parametry z sekcji E, krok 4).

### Ścieżka „Uruchom”
1. Użytkownik ustawia A–E i klika **Uruchom**.
2. Zapis configu + sync `use_case_allowed_categories.json`.
3. Uruchamiane są po kolei kroki 1 → 2 → 3 → 4 (strumieniowy log w prawym panelu).
4. Po zakończeniu wszystkich kroków: status OK, log zawiera pełne wyjście.

### Ścieżka „Generuj z podglądem”
1. Użytkownik ustawia A–E i klika **Generuj z podglądem**.
2. Zapis configu + sync (jak wyżej).
3. Uruchamiane są tylko kroki **1, 2, 3** (bez fill).
4. Po zakończeniu kroku 3: parsowanie listy wygenerowanych plików (linie `Generated: … .md`).
5. Otwarcie okna **Wyboru artykułów do wypełnienia**: lista artykułów, użytkownik zaznacza, które wypełnić; opcja „Usuń niewybrane szkielety”; przycisk „Wypełnij wybrane”.
6. Po „Wypełnij wybrane”: uruchamiany jest **krok 4 (fill_articles)** tylko dla wybranych (z zachowaniem opcji usuwania niewybranych i ustawienia statusu w kolejce).
7. Log i pasek postępu w zakładce „Generuj łatwo artykuły” pokazują przebieg fill; po zakończeniu — status gotowe.

### Wspólne elementy
- **Anuluj** w trakcie run/preview przerywa bieżący proces (terminate).
- Prawy panel: log, etykieta kroku, etykieta postępu (N/M), pasek postępu, status.
- W trybie podglądu „fill” używa lokalnych `_fill_selected_easy` i `_delete_selected_easy`, tak aby log i stan przycisków odnosiły się do tej samej zakładki.

---

## Konfiguracja vs Generuj łatwo artykuły

### Które ustawienia się pokrywają

Oba miejsca zapisują do tego samego pliku **content/config.yaml** i odczytują z niego przy starcie / przy ładowaniu zakładki.

| Parametr | Konfiguracja | Generuj łatwo artykuły |
|----------|--------------|------------------------|
| Kategoria główna (production) | Sekcja „Strona / hub”: Kategoria produkcji, slug huba | Sekcja „Gdzie trafią”: dropdown kategoria huba |
| Limit pomysłów (batch) | Sekcja „Pomysły”: Limit pomysłów / run + spinbox | Sekcja „Limit pomysłów i odbiorcy”: spinbox |
| Piramida odbiorców | Sekcja „Pomysły”: Beginner / Intermediate / Professional + suma | Ta sama sekcja: trzy spinboxy |
| Problem bazowy | Sekcja „Problemy wskazane…”: listbox + wpis | Sekcja „Problemy i obszar”: pole problemu bazowego |
| Problemy sugerowane | Ta sama sekcja: listbox + Dodaj/Usuń | Ta sama sekcja: listbox + Dodaj/Usuń |
| Obszar tematyczny (sandbox) | Sekcja „Obszary tematyczne” | Sekcja „Problemy i obszar”: sandbox |

**Jak działa ustawianie:** W „Generuj łatwo artykuły” przy **Uruchom** lub **Generuj z podglądem** wywoływane jest `_save_config_and_sync()` — wartości z formularza (kategoria, sandbox, suggested_problems, batch, piramida) są zapisywane do config.yaml. Zakładka Konfiguracja przy otwarciu ładuje config i wypełnia swoje pola. Zmiany w jednej zakładce są więc widoczne w drugiej po ponownym wejściu w zakładkę lub po ponownym załadowaniu okna (load_ui). Nie ma osobnych „ustawień tylko dla Easy” — jest jeden wspólny config.

### Czego nie ma w „Generuj łatwo artykuły”

- **Tryb kategorii (category_mode):** W Konfiguracji można wybrać „Tylko production” lub „Zachowaj sandbox”. W Easy przy zapisie zawsze ustawiane jest `category_mode="production_only"`. Użytkownik nie wybiera trybu w Easy.
- **Pełna edycja huba:** W Konfiguracji: slug huba (Combobox), tytuł huba, opcja „Inna” kategoria. W Easy jest tylko wybór kategorii z listy (bez ręcznego slugu i tytułu).
- **Przycisk „Pomysły”:** W Konfiguracji — przejście do zakładki Use case’y. W Easy tego przycisku nie ma.
- **Suma piramidy (Suma: X / limit):** W Konfiguracji jest etykieta na żywo i (w zależności od implementacji) dopasowanie sumy do limitu. W Easy są tylko trzy spinboxy bez podsumowania.

### Rekomendacja: uproszczenie Konfiguracji

Aby nie powielać tych samych ustawień w dwóch miejscach i uprościć UI:

1. **Usunąć z zakładki Konfiguracja sekcję „Pomysły” (limit + piramida)**  
   Limit i podział odbiorców są w całości dostępne w „Generuj łatwo artykuły” i tam są zapisywane przed każdym runem. W Konfiguracji można zostawić jedynie krótką informację typu: „Limit pomysłów i piramidę ustaw w zakładce **Generuj łatwo artykuły**” (oraz ewentualnie przycisk „Przejdź do Generuj łatwo artykuły”).

2. **Usunąć z Konfiguracji sekcję „Problemy wskazane do generowania…” (problem bazowy + lista sugerowanych)**  
   Te same pola są w „Generuj łatwo artykuły” w sekcji „Problemy i obszar tematyczny”. Ustawianie w jednym miejscu (Easy) wystarczy.

3. **Zostawić w Konfiguracji:**  
   - **Strona / hub** — kategoria (lista), slug huba, tytuł, tryb (production_only / preserve_sandbox). To są ustawienia „globalne” strony/huba, które mogą być edytowane bez uruchamiania pipeline’u.  
   - **Obszary tematyczne (sandbox)** — można zostawić jako osobna sekcja dla zaawansowanych (edycja listy sandbox bez wchodzenia w Easy) albo też przenieść wyłącznie do Easy i w Config pokazać tylko informację „Sandbox ustaw w Generuj łatwo artykuły”.

4. **Efekt:** Konfiguracja skupia się na **hubie i trybie** (gdzie i jak publikować), a **parametry generowania** (limit, piramida, problemy, typy treści) są w jednym miejscu — „Generuj łatwo artykuły”. Mniej duplikacji, mniej ryzyka rozjazdu wartości.

---

## Wdrożenie uproszczenia Konfiguracji (zrobione)

- Z zakładki **Konfiguracja** usunięto:
  - sekcję **Pomysły** (limit pomysłów / run, podział odbiorców, przycisk „Pomysły”, suma piramidy);
  - sekcję **Problemy wskazane do generowania…** (problem bazowy, listbox + wpis, problemy sugerowane).
- W Konfiguracji pozostały: **Strona / hub** (kategoria, slug, tytuł, tryb) oraz **Obszary tematyczne (sandbox)**.
- Przy zapisie z Konfiguracji wartości `use_case_batch_size`, `use_case_audience_pyramid`, `suggested_problems` są **odczytywane z pliku config** i zapisywane bez zmian (nie nadpisuje ich formularz Konfiguracji).

## Licznik sumy piramidy w „Generuj łatwo artykuły”

- Pod etykietą **Podział odbiorców** dodano wiersz z licznikiem **Suma …/…** (np. „Suma: 9 / 9”) oraz spinboxami Beginner / Intermediate / Professional.
- Logika jak w dawnej Konfiguracji: **IntVar** dla trzech wartości, **suma na żywo**, kolor (zielony = równa limitowi, czerwony/pomarańczowy przy rozjazdzie), **clamp** — zmiana Beginner/Intermediate automatycznie koryguje Professional tak, aby suma = limit; zmiana limitu odświeża licznik.
