# Flowtaro Monitor – uruchamianie skryptów z scripts/ z przechwyceniem outputu
import queue
import subprocess
import sys
import threading
from pathlib import Path

from flowtaro_monitor._config import PROJECT_ROOT, SCRIPTS_DIR, get_python_executable


def run_script(
    script_name: str,
    args: list[str] | None = None,
    timeout_seconds: int = 600,
) -> tuple[str, int]:
    """
    Uruchamia skrypt z scripts/ z cwd = PROJECT_ROOT.
    Zwraca (połączony stdout+stderr jako string, kod powrotu).
    """
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return f"Błąd: nie znaleziono skryptu {script_path}", -1
    cmd = [get_python_executable(), str(script_path)] + (args or [])
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        out = (result.stdout or "") + (result.stderr or "")
        return out.strip() or "(brak outputu)", result.returncode
    except subprocess.TimeoutExpired:
        return "Błąd: przekroczono limit czasu (timeout).", -1
    except Exception as e:
        return f"Błąd uruchomienia: {e}", -1


# Mapowanie nazwy akcji → skrypt + domyślne argumenty (opcjonalnie)
SCRIPT_MAP = {
    "generate_use_cases": "generate_use_cases.py",
    "generate_queue": "generate_queue.py",
    "generate_articles": "generate_articles.py",
    "fill_articles": "fill_articles.py",
    "update_affiliate_links": "update_affiliate_links.py",
    "generate_hubs": "generate_hubs.py",
    "generate_sitemap": "generate_sitemap.py",
    "render_site": "render_site.py",
    "refresh_articles": "refresh_articles.py",
}


def run_workflow_script(
    action: str,
    extra_args: list[str] | None = None,
    timeout_seconds: int = 600,
) -> tuple[str, int]:
    """Uruchamia skrypt workflow po nazwie akcji. extra_args dopisywane po domyślnych."""
    script_name = SCRIPT_MAP.get(action)
    if not script_name:
        return f"Nieznana akcja: {action}. Dozwolone: {list(SCRIPT_MAP)}", -1
    args = list(extra_args) if extra_args else []
    return run_script(script_name, args, timeout_seconds=timeout_seconds)


def start_script_streaming(
    script_name: str,
    args: list[str] | None = None,
) -> tuple[subprocess.Popen | None, queue.Queue]:
    """
    Uruchamia skrypt w tle; czyta stdout+stderr linia po linii i wrzuca do kolejki.
    W kolejce: (None, returncode) na końcu; wcześniej (line_str, None) dla każdej linii.
    Zwraca (process, queue). Aby anulować: process.terminate().
    """
    q: queue.Queue = queue.Queue()
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        q.put((None, -1))
        return None, q
    cmd = [get_python_executable(), str(script_path)] + (args or [])
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        q.put((f"Błąd uruchomienia: {e}", None))
        q.put((None, -1))
        return None, q

    def read_loop():
        try:
            for line in proc.stdout or []:
                q.put((line.rstrip(), None))
            proc.wait()
            q.put((None, proc.returncode))
        except Exception as e:
            q.put((str(e), None))
            q.put((None, -1))

    t = threading.Thread(target=read_loop, daemon=True)
    t.start()
    return proc, q


def run_workflow_streaming(
    action: str,
    extra_args: list[str] | None = None,
) -> tuple[subprocess.Popen | None, queue.Queue]:
    """Uruchamia skrypt workflow w trybie streamingu. Zwraca (process, queue)."""
    script_name = SCRIPT_MAP.get(action)
    if not script_name:
        q = queue.Queue()
        q.put((f"Nieznana akcja: {action}", None))
        q.put((None, -1))
        return None, q
    return start_script_streaming(script_name, extra_args or [])
