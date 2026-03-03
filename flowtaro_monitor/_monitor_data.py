# Flowtaro Monitor – dane dashboardu (artykuły, kolejka, koszty, błędy, ostatnie uruchomienia)
# Wykorzystuje logikę z scripts/monitor.py
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from flowtaro_monitor._config import AFFILIATE_TOOLS_PATH, CONTENT_DIR, LOGS_DIR, PROJECT_ROOT, SCRIPTS_DIR

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from content_index import get_hubs_list, load_config  # noqa: E402
from generate_queue import load_tools  # noqa: E402
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
    """Dla akcji Generuj use case'y: batch_size, pyramid (lista int), suma piramidy i lista kategorii z config (production + sandbox)."""
    out = {"batch_size": 9, "pyramid": [3, 3], "categories": []}
    if not CONFIG_PATH.exists():
        out["pyramid_sum"] = sum(out["pyramid"])
        return out
    cfg = load_config(CONFIG_PATH)
    out["batch_size"] = int(cfg.get("use_case_batch_size") or 9)
    p = cfg.get("use_case_audience_pyramid")
    out["pyramid"] = [int(x) for x in p] if isinstance(p, list) and p else [3, 3]
    out["pyramid_sum"] = sum(out["pyramid"])
    prod = (cfg.get("production_category") or "").strip()
    sandbox = cfg.get("sandbox_categories") or []
    cats = [prod] if prod else []
    for s in sandbox:
        if isinstance(s, str) and s.strip() and s.strip() not in cats:
            cats.append(s.strip())
    # Include categories from hubs so new hub categories appear without adding to sandbox
    for hub in get_hubs_list(cfg) or []:
        if isinstance(hub, dict):
            c = (hub.get("category") or hub.get("slug") or "").strip()
            if c and c not in cats:
                cats.append(c)
    out["categories"] = cats or ["ai-marketing-automation"]
    return out


def get_article_tools_data() -> list[tuple[str, str]]:
    """Read (slug, tools) from all article frontmatters.
    Returns sorted by slug."""
    import re as _re
    results: list[tuple[str, str]] = []
    if not ARTICLES_DIR.exists():
        return results
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        block = text[3:end]
        meta: dict[str, str] = {}
        for line in block.split("\n"):
            m = _re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
            if m:
                key, val = m.group(1), m.group(2).strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                meta[key] = val
        tools = (meta.get("tools") or "").strip()
        if tools:
            results.append((path.stem, tools))
    return results


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
        "# List of platforms and tools with affiliate programs",
        "# Optional per tool: short_description_en — used in prompts for in-article and \"List of platforms and tools\" descriptions (English, one sentence).",
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


REFRESH_FAILURE_REASONS_PATH = LOGS_DIR / "refresh_failure_reasons.txt"


def _load_failure_reasons_by_stem() -> dict[str, str]:
    """stem -> last failure reason from refresh_failure_reasons.txt (tab-separated)."""
    out: dict[str, str] = {}
    if not REFRESH_FAILURE_REASONS_PATH.exists():
        return out
    try:
        for line in REFRESH_FAILURE_REASONS_PATH.read_text(encoding="utf-8").strip().splitlines():
            line = line.strip()
            if "\t" in line:
                stem, reason = line.split("\t", 1)
                out[stem.strip()] = reason.strip()
            elif ": " in line:
                stem, reason = line.split(": ", 1)
                out[stem.strip()] = reason.strip()
    except OSError:
        pass
    return out


def _load_last_error_by_stem_from_errors_log(max_lines: int = 500) -> dict[str, str]:
    """Parse errors.log: lines like 'date [ERROR] stem: reason' -> stem -> reason (last wins)."""
    out: dict[str, str] = {}
    if not ERROR_LOG.exists():
        return out
    try:
        lines = ERROR_LOG.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-max_lines:]:
            if "[ERROR]" not in line or ": " not in line:
                continue
            idx = line.find("[ERROR]")
            rest = line[idx + 7 :].strip()
            if ": " in rest:
                stem, reason = rest.split(": ", 1)
                out[stem.strip()] = reason.strip()
    except OSError:
        pass
    return out


def get_article_report_data() -> list[dict]:
    """Lista słowników: stem, status, last_updated, content_type, audience_type, has_html, last_error.
    Posortowana po stem. last_error z refresh_failure_reasons lub ostatni z errors.log."""
    failure_reasons = _load_failure_reasons_by_stem()
    error_log_reasons = _load_last_error_by_stem_from_errors_log()
    rows: list[dict] = []
    if not ARTICLES_DIR.exists():
        return rows
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        stem = path.stem
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            rows.append({"stem": stem, "status": "?", "last_updated": "", "content_type": "", "audience_type": "", "lang": "", "has_html": False, "last_error": ""})
            continue
        if not text.startswith("---"):
            meta = {}
        else:
            end = text.find("\n---", 3)
            block = text[3:end] if end != -1 else text[3:]
            meta = {}
            for line in block.split("\n"):
                m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
                if m:
                    val = m.group(2).strip().strip('"\'')
                    meta[m.group(1)] = val
        status = (meta.get("status") or "draft").strip()
        last_updated = (meta.get("last_updated") or "").strip()[:10]
        content_type = (meta.get("content_type") or "").strip()
        audience_type = (meta.get("audience_type") or "").strip()
        lang = (meta.get("lang") or "").strip() or ""
        has_html = (path.with_suffix(".html")).exists()
        last_error = failure_reasons.get(stem) or error_log_reasons.get(stem) or ""
        if len(last_error) > 120:
            last_error = last_error[:117] + "..."
        rows.append({
            "stem": stem,
            "status": status,
            "last_updated": last_updated,
            "content_type": content_type,
            "audience_type": audience_type,
            "lang": lang,
            "has_html": has_html,
            "last_error": last_error,
        })
    return rows


def get_article_slug(stem: str) -> str:
    """Slug artykułu: frontmatter 'slug' lub stem (zgodnie z render_site)."""
    path = ARTICLES_DIR / f"{stem}.md"
    if not path.exists():
        return stem
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return stem
    if not text.startswith("---"):
        return stem
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else text[3:]
    for line in block.split("\n"):
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if m and m.group(1).lower() == "slug":
            val = m.group(2).strip().strip('"\'')
            return val if val else stem
    return stem


def get_public_article_html_path(stem: str) -> Path:
    """Ścieżka do pliku artykułu w public/articles/<slug>/index.html (do podglądu w przeglądarce)."""
    slug = get_article_slug(stem)
    return PROJECT_ROOT / "public" / "articles" / slug / "index.html"


def build_articles_report_html(data: list[dict], output_path: Path) -> None:
    """Zapisuje raport artykułów jako HTML (tabela + filtry po statusie)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows_html = []
    for row in data:
        stem = (row.get("stem") or "").replace("<", "&lt;").replace(">", "&gt;")
        status = (row.get("status") or "").replace("<", "&lt;")
        last_updated = (row.get("last_updated") or "").replace("<", "&lt;")
        content_type = (row.get("content_type") or "").replace("<", "&lt;")
        audience_type = (row.get("audience_type") or "").replace("<", "&lt;")
        lang = (row.get("lang") or "").replace("<", "&lt;")
        has_html = "✓" if row.get("has_html") else "—"
        last_error = (row.get("last_error") or "").replace("<", "&lt;").replace("&", "&amp;")
        rows_html.append(f"<tr><td>{stem}</td><td>{status}</td><td>{last_updated}</td><td>{content_type}</td><td>{audience_type}</td><td>{lang}</td><td>{has_html}</td><td>{last_error}</td></tr>")
    table_body = "\n".join(rows_html)
    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Raport artykułów – Flowtaro Monitor</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1rem; background: #f5f5f5; }}
h1 {{ font-size: 1.25rem; }}
.report-meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1rem; }}
table {{ border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; }}
th {{ background: #17266B; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.filter {{ margin-bottom: 0.75rem; }}
.filter select {{ padding: 0.35rem 0.5rem; }}
.col-error {{ max-width: 320px; overflow: hidden; text-overflow: ellipsis; }}
</style>
</head>
<body>
<h1>Raport artykułów</h1>
<p class="report-meta">Wygenerowano: {now} · {len(data)} artykułów</p>
<div class="filter">
<label for="statusFilter">Status: </label>
<select id="statusFilter">
<option value="">Wszystkie</option>
<option value="draft">draft</option>
<option value="filled">filled</option>
<option value="blocked">blocked</option>
</select>
</div>
<table>
<thead><tr><th>Stem</th><th>Status</th><th>Ostatnia aktualizacja</th><th>Typ treści</th><th>Audience</th><th>Lang</th><th>HTML</th><th>Ostatni błąd</th></tr></thead>
<tbody>
{table_body}
</tbody>
</table>
<script>
(function() {{
  var sel = document.getElementById('statusFilter');
  var rows = document.querySelectorAll('tbody tr');
  sel.addEventListener('change', function() {{
    var v = this.value.toLowerCase();
    rows.forEach(function(r) {{
      var status = (r.children[1] && r.children[1].textContent || '').trim().toLowerCase();
      r.style.display = (!v || status === v) ? '' : 'none';
    }});
  }});
}})();
</script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
