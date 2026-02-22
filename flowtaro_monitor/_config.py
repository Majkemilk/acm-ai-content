# Flowtaro Monitor – ścieżki projektu
# W trybie .exe (PyInstaller frozen): domyślnie katalog zawierający .exe.
# Można zapisać inny katalog w %USERPROFILE%\.flowtaro_monitor\project_root.txt (zrestartuj aplikację).
import sys
from pathlib import Path

_PREFS_DIR = Path.home() / ".flowtaro_monitor"
_PROJECT_ROOT_FILE = _PREFS_DIR / "project_root.txt"


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


PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CONTENT_DIR = PROJECT_ROOT / "content"
LOGS_DIR = PROJECT_ROOT / "logs"

CONFIG_PATH = CONTENT_DIR / "config.yaml"
AFFILIATE_TOOLS_PATH = CONTENT_DIR / "affiliate_tools.yaml"
ARTICLES_DIR = CONTENT_DIR / "articles"
QUEUE_PATH = CONTENT_DIR / "queue.yaml"
API_COSTS_PATH = LOGS_DIR / "api_costs.json"
ERROR_LOG = LOGS_DIR / "errors.log"


def get_python_executable() -> str:
    """Interpreter do uruchamiania skryptów z scripts/. Przy .exe: 'python' z PATH."""
    if getattr(sys, "frozen", False):
        return "python"
    return sys.executable
