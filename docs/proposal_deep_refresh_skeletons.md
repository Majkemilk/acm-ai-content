# Propozycja: rozszerzenie odświeżania o nowe szkielety („deep refresh”)

## Cel

Umożliwić odświeżanie starych artykułów nie tylko przez **ponowne wypełnienie** (obecne zachowanie), ale także przez **wygenerowanie nowego szkieletu** według aktualnych szablonów i zasad, a dopiero potem wypełnienie. W efekcie stare artykuły zyskałyby nową strukturę (sekcje, Try-it-yourself, limity słów, internal links itd.) przy zachowaniu **tego samego tematu/pomysłu** (bez generowania nowych use case’ów z API).

---

## Opcje zakresu

| Opcja | Zakres | Opis |
|-------|--------|------|
| **A. Jak dziś** | Tylko wypełnianie | Stary szkielet .md → fill_articles → nowa treść w tej samej strukturze. |
| **B. Od szkieletu** | Stary pomysł → nowy szkielet → wypełnienie | Dla wybranych artykułów: na podstawie metadanych (title, primary_keyword, content_type, category, audience_type) tworzony jest wpis w kolejce; generate_articles generuje **nowy** .md z aktualnego szablonu; potem fill_articles. Slug pozostaje ten sam (URL bez zmian). |
| **C. Maksymalnie od początku** | Pomysł z artykułu → use_cases / queue → szkielet → wypełnienie | Jak B, ale pomysł jest jawnie wpisany do use_cases.yaml lub queue.yaml (np. status „todo”), po czym uruchamiany jest standardowy flow: generate_queue (jeśli potrzeba) → generate_articles → fill_articles. Można zachować minimalne wytyczne (internal links, kategoria, content_type). |

Rekomendowana do wdrożenia jest **opcja B** (od szkieletu, bez zmiany use_cases/queue na stałe). Opcja C ma sens, jeśli chcemy, żeby „odświeżane” pomysły były widoczne w queue/use_cases i podlegały tym samym regułom co nowe pomysły.

---

## Proponowany przepływ (opcja B)

1. **Wybór artykułów**  
   Jak dziś: np. starsze niż N dni (albo jawny wybór po slugach).

2. **Backup**  
   Kopia .md i .html do `content/backups/...`.

3. **Dla każdego artykułu:**  
   - Odczyt frontmatter z istniejącego .md: `title`, `primary_keyword`, `content_type`, `category` / `category_slug`, `audience_type`, ewentualnie `tools`.  
   - **Syntetyczny wpis w kolejce** (w pamięci lub tymczasowy plik): jeden element z tymi polami, `status: todo`. Nie modyfikujemy na stałe `queue.yaml` ani `use_cases.yaml` (albo modyfikujemy tylko tymczasowo / w dedykowanym trybie).  
   - **generate_articles** w trybie „tylko ten wpis”, z **wymuszeniem tego samego sluga** co stary artykuł (np. `primary_keyword` ustawione tak, że `slug_from_keyword(primary_keyword)` = obecny stem pliku), żeby nowy szkielet nadpisał stary plik .md (ten sam URL).  
   - **fill_articles** dla tego sluga (--slug_contains, --write, --force, --html, --quality_gate, ewentualnie --min-words-override jak przy zwykłym odświeżaniu).

4. **Zachowanie minimalnych wytycznych**  
   - **Internal links:** generate_articles już uzupełnia `{{INTERNAL_LINKS}}` na podstawie istniejących artykułów (ta sama kategoria / content_type / narzędzia). Nowy szkielet dostanie aktualną listę linków.  
   - **Kategoria / content_type / audience:** pochodzą z frontmatter starego artykułu, więc spójność z resztą strony zostaje.  
   - **Szablony:** używane są aktualne pliki z `templates/` (how-to, guide, best, comparison itd.), więc nowa struktura (nagłówki, sekcje, placeholdery) jest zgodna z obecnymi zasadami.

5. **Na koniec**  
   Jak dziś: ewentualna aktualizacja `last_updated`, uruchomienie generate_hubs, generate_sitemap, render_site.

---

## Za

- **Aktualna struktura** – stare artykuły zyskują sekcje i wymagania z bieżących szablonów (np. Try-it-yourself, Verification policy, List of AI tools), bez ręcznej przeróbki.  
- **Ten sam temat, ten sam URL** – slug pozostaje, więc nie ma duplikatów ani rozjazdu linków; internal links w innych artykułach dalej działają.  
- **Jednorodna jakość** – wszystkie artykuły przechodzą przez te same bramki (długość, QA, quality gate) i te same szablony.  
- **Bez nowych pomysłów z API** – nie uruchamiamy generate_use_cases; używamy tylko „pomysłu” zapisanego w starym artykule (title / primary_keyword / content_type itd.).  
- **Kontrola zakresu** – można ograniczyć deep refresh do np. „starsze niż 180 dni” albo do ręcznie wybranych slugu.

---

## Przeciw

- **Złożoność** – jeden skrypt (np. refresh_articles) musi koordynować: odczyt .md → budowa wpisu kolejki → wywołanie generate_articles (z wymuszeniem sluga) → wywołanie fill_articles. Wymaga to doprecyzowania interfejsu generate_articles (np. „generuj tylko dla tego jednego wpisu” i „użyj tego sluga”).  
- **Koszt i czas** – każde odświeżenie to: 1× generacja szkieletu (jeśli używa AI w generate_articles – sprawdzić) + 1× fill (API). Przy dziesiątkach artykułów wyraźnie więcej niż przy samym fill.  
- **Ryzyko rozjazdu treści** – nowy szkielet może mieć inne sekcje niż stary; model przy fill może nieco inaczej rozłożyć akcenty. To zamierzone („nowa struktura”), ale przy bardzo specyficznych starych artykułach efekt może być mniej przewidywalny.  
- **Zależność od jakości metadanych** – jeśli w starym .md brakuje `primary_keyword` lub `content_type`, trzeba je wywnioskować (np. z title/sluga) lub pominąć artykuł; bez spójnych metadanych „ten sam temat” jest trudniejszy do zachowania.

---

## Zagrożenia wdrożenia

1. **Inna konwencja sluga** – generate_articles dziś buduje slug z `primary_keyword`. Stary plik mógł powstać z inną konwencją. Trzeba **wymusić zapis nowego szkieletu pod tym samym stemem** co stary plik (np. opcja `--output-slug` lub nadpisanie pliku o zadanym stemie), inaczej powstaną dwa pliki (stary + nowy) i trzeba będzie decydować, co zrobić ze starym (usunięcie, przekierowanie).  
2. **Kolejka i statusy** – jeśli wpisy „z odświeżania” trafiają do queue.yaml, mogą mieszać się z normalną kolejką (status todo/generated). Warto rozróżnić tryb „tylko na potrzeby tego odświeżania” (np. tymczasowy bufor w pamięci) albo osobny status/flagę.  
3. **Internal links** – generate_articles wybiera linki z istniejących artykułów. Przy nadpisywaniu tego samego sluga artykuł „sam siebie” nie powinien być w puli (już jest exclude_slug). Należy upewnić się, że przy generowaniu szkieletu „w miejscu” exclude_slug = ten artykuł.  
4. **Rollback** – przy nieudanym fill (QA/quality gate) nowy szkielet już zastąpił stary .md. Backup z kroku 2 pozwala przywrócić starą wersję; warto to jasno udokumentować i ewentualnie przy błędzie fill przywracać .md z backupu (opcjonalnie).  
5. **Prompt #2 / Try-it-yourself** – nowe szablony mogą wymagać placeholderów PROMPT2_PLACEHOLDER itd. Flow „szkielet → fill” już to obsługuje; po deep refresh może być potrzebna dodatkowa passa --prompt2-only jak przy zwykłym odświeżaniu.

---

## Rekomendacja

- **Rekomendowane:** wdrożyć **opcję B (od szkieletu)** jako **osobny tryb** (np. „deep refresh” lub „refresh with new skeleton”), z możliwością wyboru w UI/CLI obok obecnego „refresh (fill only)”.  
- **Zakres pierwszego wdrożenia:**  
  - Tryb włączany jawnie (np. checkbox „Odśwież z nowym szkieletem” lub flaga `--re-skeleton`).  
  - Domyślnie **bez** zmiany queue.yaml/use_cases.yaml na stałe: syntetyczny wpis tylko na czas jednego uruchomienia (albo zapis do queue z flagą „from_refresh”, żeby generate_articles obsłużył tylko te wpisy).  
  - **Wymuszenie sluga:** generate_articles musi móc wygenerować plik o zadanym stemie (obecny slug artykułu), żeby nadpisać stary .md i nie tworzyć duplikatów.  
- **Minimalne wytyczne:** zachować (internal links z generate_articles, kategoria/content_type/audience z frontmatter, aktualne szablony).  
- **Faza 2 (opcjonalnie):** opcja C (jawny zapis do use_cases/queue) jeśli będzie potrzeba, żeby „odświeżane” pomysły były widoczne w kolejce i podlegały tym samym regułom co nowe.

**Nie wprowadzano żadnych zmian w kodzie** – powyższa propozycja jest do zatwierdzenia przed implementacją.
