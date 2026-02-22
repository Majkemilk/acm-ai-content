# Flowtaro Monitor

Aplikacja desktopowa (Tkinter) do monitorowania pipeline'u treści ACM i uruchamiania skryptów. Minimalistyczny UI, możliwość zbudowania do pojedynczego pliku **.exe**.

## Wymagania

- Python 3.x (w trybie deweloperskim)
- Tkinter (zazwyczaj w zestawie z Pythonem)
- **Do buildu .exe:** PyInstaller (`pip install pyinstaller`)

## Uruchomienie w trybie deweloperskim

Z **katalogu głównego projektu ACM** (tam gdzie są `content/`, `scripts/`, `flowtaro_monitor/`):

```bash
python flowtaro_monitor/main.py
```

albo:

```bash
python -m flowtaro_monitor.main
```

Otworzy się okno z zakładkami **Dashboard** i **Workflow**.

## Build do .exe

1. Zainstaluj PyInstaller (jednorazowo):
   ```bash
   pip install pyinstaller
   ```

2. Z **katalogu głównego ACM** uruchom:
   ```bash
   pyinstaller flowtaro_monitor/FlowtaroMonitor.spec
   ```

3. Plik wykonywalny pojawi się w `dist/FlowtaroMonitor.exe`.

4. **Skopiuj `FlowtaroMonitor.exe` do katalogu głównego projektu ACM** (tam gdzie leżą `content/`, `scripts/`, `logs/`) i uruchom dwuklikiem.

**Uwaga:** Aplikacja w .exe uruchamia skrypty z `scripts/` przez **Pythona z PATH** (polecenie `python`). Na maszynie, na której uruchamiasz .exe, musi być zainstalowany Python i zmienna PATH musi zawierać `python` (lub `python3`). Sam .exe nie zawiera interpretera – pełni tylko rolę UI.

## Zakładki

- **Dashboard** – metryki (artykuły, kolejka, koszty API), ostatnie uruchomienia, ostatnie błędy z `logs/errors.log`. Przycisk „Odśwież dane".
- **Workflow** – wybór akcji (np. Generuj use case'y, Uzupełnij kolejkę, Wypełnij artykuły, Renderuj stronę), opcjonalne parametry w linii, przycisk „Uruchom", podgląd logu, „Zapisz log do pliku…" oraz „Zapisz log do folderu logs/".

## Ścieżka projektu

- **Tryb deweloperski:** katalog główny ACM = katalog nad `flowtaro_monitor` (określany na podstawie położenia `main.py`).
- **Tryb .exe:** katalog główny ACM = **katalog, w którym leży plik .exe**. Umieść `FlowtaroMonitor.exe` w rootcie projektu ACM (obok `content/`, `scripts/`).
