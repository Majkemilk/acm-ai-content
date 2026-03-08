# Flowtaro Monitor – ścieżki projektu
# W trybie .exe (PyInstaller frozen): domyślnie katalog zawierający .exe.
# Można zapisać inny katalog w %USERPROFILE%\.flowtaro_monitor\project_root.txt (zrestartuj aplikację).
# Content root (EN vs PL): content_root.txt; PL = content/pl, walidacja przy przełączeniu (§4D).
import sys
from pathlib import Path

_PREFS_DIR = Path.home() / ".flowtaro_monitor"
_PROJECT_ROOT_FILE = _PREFS_DIR / "project_root.txt"
_CONTENT_ROOT_FILE = _PREFS_DIR / "content_root.txt"

_DEFAULT_CONTENT_ROOT = "content"
_CONTENT_ROOT_PL = "content/pl"


def get_project_root() -> Path:
    """Katalog główny projektu ACM. Czyta zapisaną ścieżkę lub zwraca domyślny."""
    if getattr(sys, "frozen", False):
        default = Path(sys.executable).resolve().parent
    else:
        default = Path(__file__).resolve().parent.parent
    if _PROJECT_ROOT_FILE.exists():
        try:
            raw = _PROJECT_ROOT_FILE.read_text(encoding="utf-8").strip()
            p = Path(raw)
            if p.is_dir() and (p / "content").is_dir() and (p / "scripts").is_dir():
                return p.resolve()
        except Exception:
            pass
    return default


def set_project_root(path: Path) -> None:
    """Zapisuje ścieżkę projektu (np. po wyborze w menu). Wymaga restartu aplikacji."""
    _PREFS_DIR.mkdir(parents=True, exist_ok=True)
    _PROJECT_ROOT_FILE.write_text(str(path.resolve()), encoding="utf-8")


def get_content_root() -> str:
    """Ścieżka content root względem project root: 'content' (EN) lub 'content/pl' (PL)."""
    if _CONTENT_ROOT_FILE.exists():
        try:
            raw = _CONTENT_ROOT_FILE.read_text(encoding="utf-8").strip()
            if raw in (_DEFAULT_CONTENT_ROOT, _CONTENT_ROOT_PL):
                return raw
        except Exception:
            pass
    return _DEFAULT_CONTENT_ROOT


def set_content_root(value: str) -> None:
    """Zapisuje content root ('content' lub 'content/pl'). Nie waliduje – walidacja przy przełączeniu w UI."""
    _PREFS_DIR.mkdir(parents=True, exist_ok=True)
    _CONTENT_ROOT_FILE.write_text(value.strip(), encoding="utf-8")


def validate_content_root_pl(project_root: Path) -> tuple[bool, str]:
    """Sprawdza, czy content/pl/ jest gotowy (katalog + config.yaml). Zwraca (ok, komunikat_błędu)."""
    pl_dir = project_root / _CONTENT_ROOT_PL
    config_path = pl_dir / "config.yaml"
    if not pl_dir.is_dir():
        return False, "Brak katalogu content/pl/."
    if not config_path.is_file():
        return False, "Brak pliku content/pl/config.yaml."
    return True, ""


def get_content_root_resolved(project_root: Path | None = None) -> str:
    """Content root z fallback: jeśli zapisano PL ale walidacja nie przechodzi, zwróć EN."""
    root = project_root or get_project_root()
    current = get_content_root()
    if current == _CONTENT_ROOT_PL:
        ok, _ = validate_content_root_pl(root)
        if not ok:
            return _DEFAULT_CONTENT_ROOT
    return current


def _content_dir_for_root(project_root: Path, content_root: str) -> Path:
    return (project_root / content_root).resolve()


def get_content_dir() -> Path:
    """Aktualny katalog content (odświeża zapis content root – do użycia w UI po przełączeniu)."""
    return _content_dir_for_root(get_project_root(), get_content_root_resolved())


# Po załadowaniu (używane przy starcie; w monitorze preferuj get_content_dir() po przełączeniu).
PROJECT_ROOT = get_project_root()
_CONTENT_ROOT_STR = get_content_root_resolved(PROJECT_ROOT)
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CONTENT_DIR = _content_dir_for_root(PROJECT_ROOT, _CONTENT_ROOT_STR)
LOGS_DIR = PROJECT_ROOT / "logs"

# affiliate_tools współdzielony – zawsze z content/ (EN)
AFFILIATE_TOOLS_PATH = PROJECT_ROOT / "content" / "affiliate_tools.yaml"
CONFIG_PATH = CONTENT_DIR / "config.yaml"
ARTICLES_DIR = CONTENT_DIR / "articles"
QUEUE_PATH = CONTENT_DIR / "queue.yaml"
RUN_TOOLS_PATH = CONTENT_DIR / "run_tools.yaml"
API_COSTS_PATH = LOGS_DIR / "api_costs.json"
ERROR_LOG = LOGS_DIR / "errors.log"


def get_python_executable() -> str:
    """Interpreter do uruchamiania skryptów z scripts/. Przy .exe: 'python' z PATH."""
    if getattr(sys, "frozen", False):
        return "python"
    return sys.executable
