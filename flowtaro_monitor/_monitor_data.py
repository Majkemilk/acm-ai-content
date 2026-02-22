# Flowtaro Monitor – dane dashboardu (artykuły, kolejka, koszty, błędy, ostatnie uruchomienia)
# Wykorzystuje logikę z scripts/monitor.py
import sys
from datetime import date, timedelta
from pathlib import Path

from flowtaro_monitor._config import AFFILIATE_TOOLS_PATH, CONTENT_DIR, PROJECT_ROOT, SCRIPTS_DIR, LOGS_DIR

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from content_index import load_config  # noqa: E402
from generate_queue import load_tools, load_use_case_tools_mapping  # noqa: E402
from monitor import (  # noqa: E402
    API_COSTS_PATH,
    ARTICLES_DIR,
    CONFIG_PATH,
    ERROR_LOG,
    QUEUE_PATH,
    _load_cost_data,
    collect_article_stats,
    collect_cost_summary,
    collect_queue_status,
    format_ts,
    get_last_run,
    get_recent_errors,
)


def get_dashboard_data(cost_days: int = 30) -> dict:
    """Zbiera dane do dashboardu: artykuły, kolejka, koszty, ostatnie uruchomienia, błędy."""
    config = load_config(CONFIG_PATH)
    art = collect_article_stats(ARTICLES_DIR, config)
    items, q_by_status, oldest_todo = collect_queue_status(QUEUE_PATH)
    cost_data = _load_cost_data()
    total_cost, cost_last_n, avg_cost = collect_cost_summary(
        cost_data, cost_days, art["total"]
    )
    last_runs = {
        "generate_articles": get_last_run("generate_articles"),
        "fill_articles": get_last_run("fill_articles"),
        "render_site": get_last_run("render_site"),
    }
    recent_errors = get_recent_errors(20)

    return {
        "articles": art,
        "queue_items": items,
        "queue_by_status": q_by_status,
        "oldest_todo": oldest_todo,
        "cost_total": total_cost,
        "cost_last_n_days": cost_last_n,
        "cost_avg_per_article": avg_cost,
        "cost_days": cost_days,
        "cost_by_date": cost_data.get("by_date") or {},
        "last_runs": last_runs,
        "format_ts": format_ts,
        "recent_errors": recent_errors,
    }


def reset_cost_data() -> None:
    """Zeruje dane kosztów API (zapisuje pusty by_date do logs/api_costs.json)."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    API_COSTS_PATH.write_text('{"by_date": {}}\n', encoding="utf-8")


def validate_project_root() -> tuple[bool, str | None]:
    """Sprawdza, czy PROJECT_ROOT wygląda na katalog ACM (content/, scripts/). Zwraca (ok, komunikat_błędu)."""
    if not SCRIPTS_DIR.exists():
        return False, f"Brak folderu scripts/: {SCRIPTS_DIR}"
    if not CONTENT_DIR.exists():
        return False, f"Brak folderu content/: {CONTENT_DIR}"
    return True, None


def get_use_case_defaults() -> dict:
    """Dla akcji Generuj use case'y: batch_size (domyślny limit) i lista kategorii z config (production + sandbox)."""
    out = {"batch_size": 9, "categories": []}
    if not CONFIG_PATH.exists():
        return out
    cfg = load_config(CONFIG_PATH)
    out["batch_size"] = int(cfg.get("use_case_batch_size") or 9)
    prod = (cfg.get("production_category") or "").strip()
    sandbox = cfg.get("sandbox_categories") or []
    cats = [prod] if prod else []
    for s in sandbox:
        if isinstance(s, str) and s.strip() and s.strip() not in cats:
            cats.append(s.strip())
    out["categories"] = cats or ["ai-marketing-automation"]
    return out


MAPPING_PATH = CONTENT_DIR / "use_case_tools_mapping.yaml"


def get_mapping_data() -> list[tuple[str, str]]:
    """Zwraca listę (problem, tools_str) z use_case_tools_mapping.yaml."""
    if not MAPPING_PATH.exists():
        return []
    data = load_use_case_tools_mapping(MAPPING_PATH)
    return [(k, ", ".join(v)) for k, v in sorted(data.items())]


def _quote_yaml(s: str) -> str:
    """Quote string for YAML if needed."""
    s = str(s or "").strip()
    if "\n" in s or ":" in s or '"' in s or s.startswith("#"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return f'"{s}"'


def load_affiliate_tools() -> list[dict]:
    """Ładuje listę narzędzi z content/affiliate_tools.yaml. Każdy element: name, category, affiliate_link, short_description_en (opcjonalnie)."""
    if not AFFILIATE_TOOLS_PATH.exists():
        return []
    return load_tools(AFFILIATE_TOOLS_PATH)


def save_affiliate_tools(tools: list[dict]) -> None:
    """Zapisuje listę narzędzi do content/affiliate_tools.yaml."""
    AFFILIATE_TOOLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# List of AI tools with affiliate programs",
        "# Optional per tool: short_description_en — used in prompts for in-article and \"List of AI tools\" descriptions (English, one sentence).",
        "# First block: referral links (category \"referral\") — preferred when context fits; then rest alphabetically.",
        "tools:",
    ]
    for t in tools:
        name = (t.get("name") or "").strip()
        category = (t.get("category") or "").strip() or "general"
        link = (t.get("affiliate_link") or "").strip()
        desc = (t.get("short_description_en") or "").strip()
        if not name:
            continue
        lines.append(f"  - name: {_quote_yaml(name)}")
        lines.append(f"    category: {_quote_yaml(category)}")
        lines.append(f"    affiliate_link: {_quote_yaml(link)}")
        if desc:
            lines.append(f"    short_description_en: {_quote_yaml(desc)}")
    AFFILIATE_TOOLS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_cost_chart_data(cost_by_date: dict, days: int = 30) -> list[tuple[str, float]]:
    """Lista (data, koszt) dla ostatnich `days` dni, posortowana po dacie."""
    if not cost_by_date or not isinstance(cost_by_date, dict):
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    items = [(k, float(v)) for k, v in cost_by_date.items() if k >= cutoff]
    items.sort(key=lambda x: x[0])
    return items
