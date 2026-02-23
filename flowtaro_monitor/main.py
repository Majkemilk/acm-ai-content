# Flowtaro Monitor – aplikacja desktopowa (Tkinter)
# Uruchom z katalogu ACM: python flowtaro_monitor/main.py  lub  python -m flowtaro_monitor.main
# Build .exe: pyinstaller flowtaro_monitor/FlowtaroMonitor.spec
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import json
import os
import queue
import re
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from urllib.parse import urlparse, urlunparse

from flowtaro_monitor._config import CONFIG_PATH, LOGS_DIR, SCRIPTS_DIR, get_project_root, set_project_root
from flowtaro_monitor.i18n import LANG, t, set_lang

PREFS_DIR = Path.home() / ".flowtaro_monitor"
LAST_PARAMS_FILE = PREFS_DIR / "last_workflow_params.json"
HUB_SLUG_PATTERN = re.compile(r"^[a-z0-9-]*$")


def _create_tooltip(widget: tk.Widget, text: str):
    """Podpowiedź (tooltip) po najechaniu na widget."""
    tip = [None]
    def show(ev):
        if tip[0]:
            return
        x, y, _, _ = widget.bbox("insert") if hasattr(widget, "bbox") else (ev.x_root + 15, ev.y_root + 10, 0, 0)
        if not (x or y):
            x, y = ev.x_root + 15, ev.y_root + 10
        tip[0] = tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{ev.x_root + 15}+{ev.y_root + 10}")
        lbl = tk.Label(tw, text=text, justify=tk.LEFT, background="#ffffcc", relief=tk.SOLID, borderwidth=1, font=("TkDefaultFont", 9), wraplength=300)
        lbl.pack()
    def hide(ev):
        if tip[0]:
            tip[0].destroy()
            tip[0] = None
    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)


def _show_article_selector(parent, title: str, items: list[tuple[str, str]],
                           confirm_label: str, on_confirm):
    """Popup dialog with checkboxes for article selection.

    items: [(display_text, stem_value), ...]
    on_confirm: callable receiving list of selected stem_values.
    """
    if not items:
        messagebox.showinfo(t("msg.info"), t("sel.none"))
        return

    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry("780x420")
    dialog.transient(parent)
    dialog.grab_set()

    vars_map: dict[str, tk.BooleanVar] = {}
    all_var = tk.BooleanVar(value=True)

    def toggle_all():
        val = all_var.get()
        for v in vars_map.values():
            v.set(val)

    top_row = ttk.Frame(dialog, padding=5)
    top_row.pack(fill=tk.X)
    ttk.Checkbutton(top_row, text=t("sel.select_all"), variable=all_var,
                    command=toggle_all).pack(side=tk.LEFT)

    canvas = tk.Canvas(dialog, highlightthickness=0)
    sb = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
    sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    for display, stem in items:
        var = tk.BooleanVar(value=True)
        vars_map[stem] = var
        ttk.Checkbutton(inner, text=display, variable=var).pack(anchor=tk.W, padx=5, pady=1)

    btn_row = ttk.Frame(dialog, padding=10)
    btn_row.pack(fill=tk.X)

    def confirm():
        selected = [stem for stem, var in vars_map.items() if var.get()]
        dialog.destroy()
        if not selected:
            messagebox.showinfo(t("msg.info"), t("sel.none"))
            return
        on_confirm(selected)

    ttk.Button(btn_row, text=confirm_label, command=confirm).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)


def _load_last_params() -> dict:
    """Ostatnie zestawy parametrów per akcja (lista do 3 stringów)."""
    if not LAST_PARAMS_FILE.exists():
        return {}
    try:
        return json.loads(LAST_PARAMS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_last_params(action: str, extra: list):
    """Zapisz zestaw parametrów dla akcji (ostatnie 3)."""
    PREFS_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_last_params()
    s = " ".join(extra)
    lst = data.get(action, [])
    if s in lst:
        lst.remove(s)
    lst = [s] + lst[:2]
    data[action] = lst
    LAST_PARAMS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
from flowtaro_monitor._monitor_data import (
    get_dashboard_data,
    get_cost_chart_data,
    get_article_tools_data,
    get_use_case_defaults,
    load_affiliate_tools,
    reset_cost_data,
    save_affiliate_tools,
    validate_project_root,
)
from flowtaro_monitor._run_scripts import SCRIPT_MAP, run_workflow_script, run_workflow_streaming

# Klucze i18n dla etykiet etapów (t() w UI)
WORKFLOW_LABEL_KEYS = {
    "generate_use_cases": "wf.gen_use_cases",
    "generate_queue": "wf.gen_queue",
    "generate_articles": "wf.gen_articles",
    "fill_articles": "wf.fill_articles",
    "generate_hubs": "wf.gen_hubs",
    "generate_sitemap": "wf.gen_sitemap",
    "render_site": "wf.render_site",
    "refresh_articles": "wf.refresh_articles",
}

# Kolejność etapów w zakładce Workflow (refresh_articles ma osobną zakładkę)
SEQUENCE_ACTIONS = [
    "generate_use_cases",
    "generate_queue",
    "generate_articles",
    "fill_articles",
    "generate_hubs",
    "generate_sitemap",
    "render_site",
]

# Schemat parametrów per akcja: choice = lista rozwijana (wartość_display, args), text = pole wpisu (flag + wartość).
# Każdy parametr: label, type, description (podpowiedź kursywą), oraz choices/flag.
def _p_choice(label: str, description: str, choices: list[tuple[str, list[str]]]) -> dict:
    return {"label": label, "type": "choice", "description": description, "choices": choices}


def _p_bool(label: str, description: str, on_args: list[str], off_args: list[str] | None = None, default: bool = False) -> dict:
    return {"label": label, "type": "boolean", "description": description, "on_args": on_args, "off_args": off_args or [], "default": default}


def _p_text(label: str, description: str, flag: str, placeholder: str = "") -> dict:
    return {"label": label, "type": "text", "description": description, "flag": flag, "placeholder": placeholder}


def _p_multichoice(label: str, description: str, flag: str, choices: list[tuple[str, str]]) -> dict:
    """choices: (display, value). Wartości wybranych są przekazywane jako powtórzenia --flag value."""
    return {"label": label, "type": "multichoice", "description": description, "flag": flag, "choices": choices}


def _p_limit_override(label: str, default: int, min_val: int = 1, max_val: int = 100) -> dict:
    """Parametr limit z podpowiedzią (zakres + domyślna), checkbox 'Inna niż domyślna' i Spinbox w zakresie."""
    return {"label": label, "type": "limit_override", "default": default, "min": min_val, "max": max_val}


# generate_use_cases jest budowany dynamicznie w refresh_params_panel (limit z domyślnym z config, kategoria z listy, typ treści multichoice)
WORKFLOW_PARAM_SCHEMA: dict[str, list[dict]] = {
    "generate_use_cases": None,  # budowane w _build_param_widgets_for_action
    "generate_queue": [
        _p_choice("wf.gq.mode", "wf.gq.mode_desc", [("wf.gq.opt_run", []), ("wf.gq.opt_preview", ["--dry-run"])]),
    ],
    "generate_articles": [
        _p_choice("wf.ga.mode", "wf.ga.mode_desc", [("wf.ga.opt_queue", []), ("wf.ga.opt_backfill", ["--backfill"])]),
    ],
    "fill_articles": [
        _p_bool("wf.fill.write", "wf.fill.write_desc", ["--write"], default=True),
        _p_bool("wf.fill.force", "wf.fill.force_desc", ["--force"]),
        _p_choice("wf.fill.limit", "wf.fill.limit_desc", [("wf.fill.limit_none", []), ("wf.fill.limit_1", ["--limit", "1"]), ("wf.fill.limit_5", ["--limit", "5"]), ("wf.fill.limit_10", ["--limit", "10"]), ("wf.fill.limit_20", ["--limit", "20"]), ("wf.fill.limit_50", ["--limit", "50"])]),
        _p_choice("wf.fill.qa", "wf.fill.qa_desc", [("wf.fill.qa_default", []), ("wf.fill.qa_on", ["--qa"]), ("wf.fill.qa_off", ["--no-qa"])]),
        _p_bool("wf.fill.quality", "wf.fill.quality_desc", ["--quality_gate"]),
    ],
    "generate_hubs": [],
    "generate_sitemap": [],
    "render_site": [],
}


def _build_param_widgets_for_action(container: ttk.Frame, action: str, italic_font: tuple, hint_labels: list | None = None, combo_width: int | None = None) -> list:
    """Buduje w container pełny zestaw widgetów parametrów dla danej akcji. combo_width – stała szerokość pól select (jak przy Kategoria); gdy None, liczone z opcji."""
    hint_labels = hint_labels if hint_labels is not None else []
    schema = WORKFLOW_PARAM_SCHEMA.get(action)
    if schema is None and action == "generate_use_cases":
        defaults = get_use_case_defaults()
        schema = [
            _p_limit_override("wf.limit_label", default=defaults["batch_size"], min_val=1, max_val=100),
            _p_choice("wf.category", "wf.category_desc", [("wf.category_any", [])] + [(c, ["--category", c]) for c in defaults["categories"]]),
            {"label": "wf.content_type", "type": "content_type_checkboxes", "description": "wf.content_type_desc", "flag": "--content-type", "choices": [("wf.content_all", None), ("how-to", "how-to"), ("guide", "guide"), ("best", "best"), ("comparison", "comparison")]},
        ]
    widgets: list = []
    if not schema:
        ttk.Label(container, text=t("wf.no_params"), foreground="gray").pack(anchor=tk.W)
        return widgets
    for p in schema:
        row = ttk.Frame(container)
        row.pack(fill=tk.X, pady=(0, 6))
        label_text = t(p["label"]) if p.get("label") else ""
        desc_text = t(p["description"]) if p.get("description") else ""
        if p["type"] != "limit_override":
            lbl = ttk.Label(row, text=label_text, width=28, anchor=tk.W)
            lbl.pack(side=tk.LEFT, padx=(0, 5))
        if p["type"] == "limit_override":
            limit_lbl_text = t("wf.limit_line").format(min=p["min"], max=p["max"], default=p["default"])
            limit_lbl = ttk.Label(row, text=limit_lbl_text)
            limit_lbl.pack(side=tk.LEFT, padx=(0, 5))
            check_var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(row, text=t("wf.limit_other"), variable=check_var)
            cb.pack(side=tk.LEFT, padx=(0, 10))
            spin = tk.Spinbox(row, from_=p["min"], to=p["max"], width=6)
            spin.delete(0, tk.END)
            spin.insert(0, str(p["default"]))
            spin.config(state=tk.DISABLED)
            spin.pack(side=tk.LEFT)
            def _enable_spin(sv=spin, cv=check_var):
                sv.config(state=tk.NORMAL if cv.get() else tk.DISABLED)
            check_var.trace_add("write", lambda *a: _enable_spin())
            widgets.append((p, (check_var, spin)))
            _create_tooltip(limit_lbl, t("wf.limit_tooltip"))
            continue
        if p["type"] == "content_type_checkboxes":
            choices = p["choices"]
            vars_list = []
            hint_frame = ttk.Frame(row)
            hint_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            lbl_hint = tk.Label(hint_frame, text=desc_text, font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
            lbl_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
            hint_labels.append(lbl_hint)
            row_cb = ttk.Frame(container)
            row_cb.pack(fill=tk.X, pady=(0, 6))
            ttk.Label(row_cb, text="", width=28).pack(side=tk.LEFT, padx=(0, 5))
            cb_frame = ttk.Frame(row_cb)
            cb_frame.pack(anchor=tk.W)
            var_wszystkie = tk.BooleanVar(value=True)
            vars_list.append(("wszystkie", None, var_wszystkie))
            ttk.Checkbutton(cb_frame, text=t("wf.content_all_short"), variable=var_wszystkie).pack(side=tk.LEFT, padx=(0, 12))
            for _i, (disp, val) in enumerate(choices[1:], 1):
                v = tk.BooleanVar(value=False)
                vars_list.append((disp, val, v))
                ttk.Checkbutton(cb_frame, text=t(disp) if (disp and "." in disp) else disp, variable=v).pack(side=tk.LEFT, padx=(0, 12))
            def _on_wszystkie(vl=vars_list):
                if vl[0][2].get():
                    for _d, _val, vb in vl[1:]:
                        vb.set(False)
            def _on_single(vl=vars_list):
                if any(vb.get() for _d, _val, vb in vl[1:]):
                    vl[0][2].set(False)
            def _ensure_one(vl=vars_list):
                if not vl[0][2].get() and not any(vb.get() for _d, _val, vb in vl[1:]):
                    vl[0][2].set(True)
            var_wszystkie.trace_add("write", lambda *a: _on_wszystkie())
            for _d, _val, vb in vars_list[1:]:
                vb.trace_add("write", lambda *a: _on_single())
                vb.trace_add("write", lambda *a: _ensure_one())
            widgets.append((p, vars_list))
            _create_tooltip(lbl, desc_text)
            continue
        if p["type"] == "boolean":
            var = tk.BooleanVar(value=p.get("default", False))
            hint_frame = ttk.Frame(row)
            hint_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            lbl_hint = tk.Label(hint_frame, text=desc_text, font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
            lbl_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
            hint_labels.append(lbl_hint)
            cb = ttk.Checkbutton(row, variable=var)
            cb.pack(side=tk.LEFT)
            widgets.append((p, var))
            _create_tooltip(lbl, desc_text)
            continue
        if p["type"] == "choice":
            choices = p["choices"]
            disp_vals = [t(c[0]) for c in choices]
            w_width = combo_width if combo_width is not None else max(12, min(30, max((len(d) for d in disp_vals), default=10) + 2))
            hint_frame = ttk.Frame(row)
            hint_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            lbl_hint = tk.Label(hint_frame, text=desc_text, font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
            lbl_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
            hint_labels.append(lbl_hint)
            w = ttk.Combobox(row, values=disp_vals, state="readonly", width=combo_width if combo_width is not None else w_width)
            w.pack(side=tk.LEFT)
            if disp_vals:
                w.current(0)
            widgets.append((p, w))
            _create_tooltip(lbl, desc_text)
        elif p["type"] == "multichoice":
            choices = p["choices"]
            disp_vals = [t(c[0]) for c in choices]
            lb_width = combo_width if combo_width is not None else max(12, min(30, max((len(d) for d in disp_vals), default=10) + 2))
            hint_frame = ttk.Frame(row)
            hint_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            lbl_hint = tk.Label(hint_frame, text=desc_text, font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
            lbl_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
            hint_labels.append(lbl_hint)
            lb = tk.Listbox(row, height=min(4, len(disp_vals)), selectmode=tk.MULTIPLE, exportselection=False, width=lb_width)
            if combo_width is not None:
                lb.configure(width=combo_width)
            lb.pack(side=tk.LEFT)
            for v in disp_vals:
                lb.insert(tk.END, v)
            widgets.append((p, lb))
            _create_tooltip(lbl, desc_text)
        else:
            hint_frame = ttk.Frame(row)
            hint_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            lbl_hint = tk.Label(hint_frame, text=desc_text, font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
            lbl_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
            hint_labels.append(lbl_hint)
            w = ttk.Entry(row, width=25)
            w.pack(side=tk.LEFT)
            if p.get("placeholder"):
                w.insert(0, p["placeholder"])
                w.config(foreground="gray")
                def on_focus_in(ev, entry=w, ph=p.get("placeholder", "")):
                    if entry.get().strip() == ph:
                        entry.delete(0, tk.END)
                        entry.config(foreground="black")
                def on_focus_out(ev, entry=w, ph=p.get("placeholder", "")):
                    if not entry.get().strip():
                        entry.insert(0, ph)
                        entry.config(foreground="gray")
                w.bind("<FocusIn>", on_focus_in)
                w.bind("<FocusOut>", on_focus_out)
            widgets.append((p, w))
            _create_tooltip(lbl, desc_text)
    return widgets


def _collect_extra_from_widgets(param_widgets: list) -> list:
    """Z listy (param_def, widget) zbiera listę argumentów extra (flagi + wartości) do skryptu."""
    extra = []
    for p, w in param_widgets:
        if p["type"] == "boolean":
            if w.get():
                extra.extend(p["on_args"])
            else:
                extra.extend(p.get("off_args") or [])
            continue
        if p["type"] == "choice":
            try:
                i = w.current()
                choices = p["choices"]
                if 0 <= i < len(choices) and choices[i][1]:
                    extra.extend(choices[i][1])
            except (tk.TclError, TypeError):
                pass
        elif p["type"] == "multichoice":
            try:
                choices = p["choices"]
                for i in w.curselection():
                    if 0 <= i < len(choices):
                        extra.extend([p["flag"], choices[i][1]])
            except (tk.TclError, TypeError):
                pass
        elif p["type"] == "content_type_checkboxes":
            vars_list = w
            if not vars_list[0][2].get():
                for _d, val, vb in vars_list[1:]:
                    if val and vb.get():
                        extra.extend([p["flag"], val])
        elif p["type"] == "limit_override":
            check_var, spin = w
            if check_var.get():
                try:
                    val = spin.get().strip()
                    n = int(val)
                    n = max(p["min"], min(p["max"], n))
                    extra.extend(["--limit", str(n)])
                except (ValueError, tk.TclError):
                    extra.extend(["--limit", str(p["default"])])
            else:
                # R1: use current config batch_size at run time, not widget's frozen default
                defaults = get_use_case_defaults()
                extra.extend(["--limit", str(defaults["batch_size"])])
        else:
            val = w.get().strip()
            placeholder = p.get("placeholder", "").strip()
            if val and val != placeholder:
                extra.extend([p["flag"], val])
    return extra


def build_dashboard_tab(parent):
    """Zakładka Stats: suwak dni kosztów, metryki, tabele, reset kosztów, błędy ładowania."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        ttk.Label(f, text="Uruchom aplikację z katalogu głównego ACM lub wybierz katalog (menu Plik).").pack(anchor=tk.W)
        return f, lambda: None

    header = ttk.Frame(f)
    header.pack(fill=tk.X)
    ttk.Label(header, text=t("stats.title"), font=("", 14, "bold")).pack(side=tk.LEFT)
    ttk.Label(header, text=t("stats.cost_days")).pack(side=tk.LEFT, padx=(20, 5))
    cost_days_var = tk.IntVar(value=30)
    slider = ttk.Scale(header, from_=7, to=90, variable=cost_days_var, orient=tk.HORIZONTAL, length=120, command=lambda v: cost_days_var.set(round(float(v))))
    slider.pack(side=tk.LEFT, padx=5)
    lbl_days = ttk.Label(header, text="30")
    lbl_days.pack(side=tk.LEFT)

    def on_slider_change(*_):
        try:
            lbl_days.config(text=str(cost_days_var.get()))
        except tk.TclError:
            pass

    cost_days_var.trace_add("write", on_slider_change)

    def on_reset_costs():
        try:
            reset_cost_data()
            messagebox.showinfo(t("msg.info"), t("stats.costs_reset"))
            do_refresh()
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))

    btn_refresh = ttk.Button(header, text=t("stats.refresh"), command=lambda: do_refresh())
    btn_refresh.pack(side=tk.RIGHT, padx=5)
    btn_reset_costs = ttk.Button(header, text=t("stats.reset_costs"), command=on_reset_costs)
    btn_reset_costs.pack(side=tk.RIGHT, padx=5)

    metrics_frame = ttk.LabelFrame(f, text="Metryki", padding=5)
    metrics_frame.pack(fill=tk.X, pady=5)
    tables_frame = ttk.Frame(f)
    tables_frame.pack(fill=tk.X, pady=5)
    chart_frame = ttk.LabelFrame(f, text="Koszty w czasie (ostatnie dni)", padding=5)
    chart_frame.pack(fill=tk.X, pady=5)
    chart_canvas = tk.Canvas(chart_frame, width=600, height=120, bg="white", highlightthickness=0)
    chart_canvas.pack(fill=tk.X)
    details_frame = ttk.Frame(f)
    details_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    def do_refresh():
        btn_refresh.config(state=tk.DISABLED)
        try:
            days = cost_days_var.get()
            if days < 7:
                days = 7
            if days > 90:
                days = 90
            data = get_dashboard_data(cost_days=days)
            art = data["articles"]
            q_by = data["queue_by_status"]
            fmt = data["format_ts"]

            for w in metrics_frame.winfo_children():
                w.destroy()
            row = ttk.Frame(metrics_frame)
            row.pack(fill=tk.X)
            ttk.Label(row, text=f"Artykuły: {art['total']} łącznie, {art['production']} na żywo").pack(side=tk.LEFT, padx=5)
            ttk.Label(row, text=f"Kolejka: todo={q_by.get('todo', 0)}, generated={q_by.get('generated', 0)}").pack(side=tk.LEFT, padx=5)
            ttk.Label(row, text=f"Koszty: ${data['cost_total']:.4f} (całość), ${data['cost_last_n_days']:.4f} ({days} dni)").pack(side=tk.LEFT, padx=5)

            for w in tables_frame.winfo_children():
                w.destroy()
            tbl_f = ttk.Frame(tables_frame)
            tbl_f.pack(fill=tk.X)
            ttk.Label(tbl_f, text="Po statusie").pack(anchor=tk.W)
            tree_status = ttk.Treeview(tbl_f, columns=("status", "count"), show="headings", height=4)
            tree_status.heading("status", text="Status")
            tree_status.heading("count", text="Liczba")
            tree_status.column("status", width=120)
            tree_status.column("count", width=60)
            tree_status.pack(side=tk.LEFT, padx=(0, 20))
            for s, c in sorted(art["by_status"].items()):
                tree_status.insert("", tk.END, values=(s, c))
            ttk.Label(tbl_f, text="Po typie treści").pack(anchor=tk.W)
            tree_type = ttk.Treeview(tbl_f, columns=("ctype", "count"), show="headings", height=4)
            tree_type.heading("ctype", text="Typ")
            tree_type.heading("count", text="Liczba")
            tree_type.column("ctype", width=120)
            tree_type.column("count", width=60)
            tree_type.pack(side=tk.LEFT, padx=(0, 20))
            for t, c in sorted(art["by_content_type"].items()):
                tree_type.insert("", tk.END, values=(t, c))

            # Wykres kosztów (słupki)
            chart_data = get_cost_chart_data(data["cost_by_date"], days)
            chart_canvas.delete("all")
            if chart_data:
                w = chart_canvas.winfo_width() or 600
                h = 110
                pad = 4
                max_cost = max(c for _, c in chart_data) or 1
                n = len(chart_data)
                bar_w = max(2, (w - pad * 2) // n - 2)
                for i, (d, cost) in enumerate(chart_data):
                    x = pad + i * (bar_w + 2)
                    bar_h = int((cost / max_cost) * (h - 20)) if max_cost else 0
                    y0 = h - bar_h
                    chart_canvas.create_rectangle(x, y0, x + bar_w, h, fill="#4a9eff", outline="#2d6bb8")
                chart_canvas.config(width=w, height=h + 10)
            else:
                chart_canvas.create_text(200, 55, text="Brak danych kosztów", fill="gray")

            for w in details_frame.winfo_children():
                w.destroy()
            txt = scrolledtext.ScrolledText(details_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
            txt.pack(fill=tk.BOTH, expand=True)
            lines = []
            lines.append("Ostatnie uruchomienia:")
            for name, ts in data["last_runs"].items():
                lines.append(f"  {name}: {fmt(ts)}")
            lines.append("\nNajstarsze 5 todo:")
            for it in data["oldest_todo"][:5]:
                kw = (it.get("primary_keyword") or it.get("title") or "?")[:50]
                lines.append(f"  - {kw}")
            lines.append("\nOstatnie błędy (errors.log):")
            for line in data["recent_errors"][-10:]:
                lines.append(line[:100])
            txt.config(state=tk.NORMAL)
            txt.delete("1.0", tk.END)
            txt.insert(tk.END, "\n".join(lines) if lines else "Brak danych.")
            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))
        finally:
            btn_refresh.config(state=tk.NORMAL)

    do_refresh()
    return f, do_refresh


def build_workflow_tab(parent, last_output_holder: list):
    """Zakładka Generuj artykuły: 4 kroki z parametrami + podsumowanie (hub, sitemap, render); jeden przycisk Uruchom uruchamia całą sekwencję."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    italic_font = ("TkDefaultFont", 9, "italic")
    section_widgets: list = []  # po jednym wpisie na każdy etap SEQUENCE_ACTIONS (7)
    defaults_uc = get_use_case_defaults()
    cat_vals = [t("wf.category_any")] + list(defaults_uc.get("categories", []))
    combo_width = min(30, max((len(str(v)) for v in cat_vals), default=10) + 2)
    combo_width = max(12, combo_width)

    paned_h = ttk.PanedWindow(f, orient=tk.HORIZONTAL)
    paned_h.pack(fill=tk.BOTH, expand=True)

    left_frame = ttk.Frame(paned_h)
    paned_h.add(left_frame, weight=2)

    content_frame = ttk.Frame(left_frame)
    content_frame.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(content_frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    workflow_hint_labels: list = []

    def _on_canvas_configure(ev):
        canvas.itemconfig(canvas_window, width=ev.width)
        wrap_w = max(80, ev.width - 260)
        for lbl in workflow_hint_labels:
            try:
                lbl.configure(wraplength=wrap_w)
            except tk.TclError:
                pass
    canvas.bind("<Configure>", _on_canvas_configure)
    def _on_mousewheel(ev):
        canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
    canvas.bind("<MouseWheel>", _on_mousewheel)

    for i, action in enumerate(SEQUENCE_ACTIONS):
        if i < 4:
            section_title = "" if i == 0 else t(WORKFLOW_LABEL_KEYS.get(action, action))
            lf = ttk.LabelFrame(inner, text=section_title)
            lf.pack(fill=tk.X, pady=(0, 10))
            section_inner = ttk.Frame(lf, padding=5)
            section_inner.pack(fill=tk.X)
            widgets = _build_param_widgets_for_action(section_inner, action, italic_font, workflow_hint_labels, combo_width)
            section_widgets.append(widgets)
        elif i == 4:
            summary_frame = ttk.Frame(inner)
            summary_frame.pack(fill=tk.X, pady=(0, 10))
            summary_lbl = tk.Label(
                summary_frame,
                text=t("wf.sequence_summary"),
                font=italic_font,
                fg="gray",
                wraplength=620,
                justify=tk.LEFT,
            )
            summary_lbl.pack(anchor=tk.W)
            section_widgets.append([])
        else:
            section_widgets.append([])

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    row_btn = ttk.Frame(left_frame)
    row_btn.pack(fill=tk.X, pady=(8, 0))

    right_frame = ttk.Frame(paned_h)
    paned_h.add(right_frame, weight=1)

    def _set_initial_sash():
        paned_h.update_idletasks()
        w = paned_h.winfo_width()
        if w > 100:
            paned_h.sashpos(0, int(0.7 * w))
    f.after(400, _set_initial_sash)
    f.bind("<Map>", lambda e: f.after(100, _set_initial_sash))
    ttk.Label(right_frame, text=t("wf.log")).pack(anchor=tk.W, pady=(0, 2))
    step_label = ttk.Label(right_frame, text="", foreground="gray")
    step_label.pack(anchor=tk.W, pady=(0, 2))
    progress_bar = ttk.Progressbar(right_frame, maximum=len(SEQUENCE_ACTIONS), value=0, length=280)
    progress_bar.pack(fill=tk.X, pady=(0, 5))
    log_area = scrolledtext.ScrolledText(right_frame, height=14, wrap=tk.WORD, state=tk.DISABLED)
    log_area.pack(fill=tk.BOTH, expand=True, pady=5)
    status_label = ttk.Label(right_frame, text="", foreground="gray")
    status_label.pack(anchor=tk.W)

    process_holder = []
    sequence_cancelled = [False]
    preview_mode = [False]
    preview_remaining_steps = [[]]
    root = parent.winfo_toplevel()

    _generated_re = re.compile(r"^Generated:\s+(.+\.md)\s*$")

    def _parse_generated_articles(output: str) -> list[tuple[str, str]]:
        items = []
        for line in output.splitlines():
            m = _generated_re.match(line)
            if m:
                p = Path(m.group(1).strip())
                items.append((p.name, p.stem))
        return items

    def set_log(out, code, rbtn, cbtn):
        log_area.config(state=tk.NORMAL)
        if out:
            log_area.delete("1.0", tk.END)
            log_area.insert(tk.END, out)
        log_area.insert(tk.END, f"\n\n[Kod powrotu: {code}]")
        log_area.config(state=tk.DISABLED)
        rbtn.config(state=tk.NORMAL)
        cbtn.config(state=tk.DISABLED)
        status_label.config(text=t("wf.status_ok") if code == 0 else t("wf.status_error"), foreground="green" if code == 0 else "red")

    def append_log(line):
        log_area.config(state=tk.NORMAL)
        log_area.insert(tk.END, line + "\n")
        log_area.see(tk.END)
        log_area.config(state=tk.DISABLED)

    def poll_sequence(remaining, accumulated, current_out_lines, q, rbtn, cbtn, fill_total=0, fill_done=None):
        if fill_done is None:
            fill_done = [0]
        try:
            item = q.get_nowait()
            if item[1] is not None:
                code = item[1]
                new_accumulated = accumulated + current_out_lines
                full_text = "\n".join(new_accumulated)
                if sequence_cancelled[0]:
                    full_text += "\n\n" + t("wf.status_cancelled_msg")
                    code = -1
                completed_index = len(SEQUENCE_ACTIONS) - len(remaining) - 1
                failed_action = SEQUENCE_ACTIONS[completed_index] if 0 <= completed_index < len(SEQUENCE_ACTIONS) else None
                def done():
                    log_area.config(state=tk.NORMAL)
                    log_area.delete("1.0", tk.END)
                    log_area.insert(tk.END, full_text)
                    log_area.insert(tk.END, f"\n\n[Kod powrotu: {code}]")
                    log_area.config(state=tk.DISABLED)
                    rbtn.config(state=tk.NORMAL)
                    try:
                        preview_btn.config(state=tk.NORMAL)
                    except Exception:
                        pass
                    cbtn.config(state=tk.DISABLED)
                    completed = len(SEQUENCE_ACTIONS) - len(remaining)
                    progress_bar["value"] = len(SEQUENCE_ACTIONS) if not remaining else completed
                    if not remaining:
                        step_label.config(text=t("wf.step_done"))
                    if sequence_cancelled[0]:
                        status_text = t("wf.status_cancelled")
                    elif code == 0:
                        status_text = t("wf.status_ok")
                    elif code == 2:
                        status_text = t("wf.status_error_exit2") if failed_action == "generate_use_cases" else t("wf.status_error_exit2_other")
                    else:
                        status_text = t("wf.status_error_exit1")
                    status_label.config(
                        text=status_text,
                        foreground="red" if (sequence_cancelled[0] or code != 0) else "green",
                    )
                    process_holder.clear()
                    last_output_holder.clear()
                    last_output_holder.append((full_text, "sequence"))
                    if preview_mode[0] and code == 0 and not sequence_cancelled[0]:
                        preview_mode[0] = False
                        items = _parse_generated_articles(full_text)
                        if items:
                            step_label.config(text=t("wf.preview_done"))
                            status_label.config(text=t("wf.preview_done"), foreground="blue")
                            root.after(100, lambda: _show_article_selector(
                                root, t("sel.title_fill"), items,
                                t("sel.confirm_fill"),
                                lambda selected: _fill_selected(selected, items, full_text)))
                        else:
                            status_label.config(text=t("wf.status_ok"), foreground="green")
                if sequence_cancelled[0] or code != 0 or not remaining:
                    root.after(0, done)
                    return
                next_action, next_extra = remaining.pop(0)
                completed = len(SEQUENCE_ACTIONS) - len(remaining) - 1  # liczba ukończonych kroków
                progress_bar["value"] = completed
                next_fill_total = _parse_fill_limit(next_extra) if next_action == "fill_articles" else 0
                next_fill_done = [0]
                progress_bar["value"] = completed
                if next_fill_total > 0:
                    step_label.config(text=t("wf.step_progress_fill", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(next_action, next_action)), 0, next_fill_total))
                else:
                    step_label.config(text=t("wf.step_progress", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(next_action, next_action))))
                next_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(next_action, next_action)) + " ---", ""]
                for h in next_header:
                    root.after(0, lambda line=h: append_log(line))
                proc, new_q = run_workflow_streaming(next_action, next_extra)
                process_holder[0] = (next_action, proc)
                next_accumulated = new_accumulated + next_header
                root.after(50, lambda: poll_sequence(remaining, next_accumulated, [], new_q, rbtn, cbtn, next_fill_total, next_fill_done))
                return
            line = item[0]
            if line is not None:
                current_action = process_holder[0][0] if process_holder else None
                if current_action == "fill_articles" and fill_total > 0 and "  Filled:" in line:
                    fill_done[0] += 1
                    completed = len(SEQUENCE_ACTIONS) - len(remaining) - 1
                    step_label.config(text=t("wf.step_progress_fill", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get("fill_articles", "fill_articles")), fill_done[0], fill_total))
                    progress_bar["value"] = completed + (fill_done[0] / fill_total)
                current_out_lines.append(line)
                root.after(0, lambda l=line: append_log(l))
        except queue.Empty:
            pass
        root.after(50, lambda: poll_sequence(remaining, accumulated, current_out_lines, q, rbtn, cbtn, fill_total, fill_done))

    def _effective_use_case_limit(extra: list) -> int:
        """Parse --limit from generate_use_cases extra args, else config default."""
        for i, x in enumerate(extra):
            if x == "--limit" and i + 1 < len(extra):
                try:
                    return int(extra[i + 1])
                except ValueError:
                    pass
        return get_use_case_defaults()["batch_size"]

    def _parse_fill_limit(extra: list) -> int:
        """Parse --limit from fill_articles extra args. 0 = no limit."""
        for i, x in enumerate(extra):
            if x == "--limit" and i + 1 < len(extra):
                try:
                    return int(extra[i + 1])
                except ValueError:
                    pass
        return 0

    def run():
        steps = []
        for idx, action in enumerate(SEQUENCE_ACTIONS):
            extra = _collect_extra_from_widgets(section_widgets[idx])
            steps.append((action, extra))
            _save_last_params(action, extra)
        # R2: warn when generate_use_cases limit != pyramid sum
        if steps and steps[0][0] == "generate_use_cases":
            limit = _effective_use_case_limit(steps[0][1])
            defaults = get_use_case_defaults()
            if limit != defaults["pyramid_sum"]:
                if not messagebox.askyesno(
                    t("wf.limit_pyramid_title"),
                    t("wf.limit_pyramid_mismatch", limit, defaults["pyramid_sum"]),
                    icon=messagebox.WARNING,
                ):
                    return
        preview_mode[0] = False
        sequence_cancelled[0] = False
        run_btn.config(state=tk.DISABLED)
        preview_btn.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("wf.running"), foreground="gray")
        progress_bar["value"] = 0
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("wf.running") + "\n")
        log_area.config(state=tk.DISABLED)
        process_holder.clear()
        first_action, first_extra = steps.pop(0)
        first_fill_total = _parse_fill_limit(first_extra) if first_action == "fill_articles" else 0
        first_fill_done = [0]
        if first_fill_total > 0:
            step_label.config(text=t("wf.step_progress_fill", 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)), 0, first_fill_total))
        else:
            step_label.config(text=t("wf.step_progress", 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
        first_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)) + " ---", ""]
        for h in first_header:
            root.after(0, lambda line=h: append_log(line))
        proc, q = run_workflow_streaming(first_action, extra_args=first_extra)
        process_holder.append((first_action, proc))
        root.after(50, lambda: poll_sequence(steps, first_header, [], q, run_btn, cancel_btn, first_fill_total, first_fill_done))

    def run_preview():
        steps = []
        for idx, action in enumerate(SEQUENCE_ACTIONS):
            extra = _collect_extra_from_widgets(section_widgets[idx])
            steps.append((action, extra))
            _save_last_params(action, extra)
        # R2: warn when generate_use_cases limit != pyramid sum (first step is same)
        if steps and steps[0][0] == "generate_use_cases":
            limit = _effective_use_case_limit(steps[0][1])
            defaults = get_use_case_defaults()
            if limit != defaults["pyramid_sum"]:
                if not messagebox.askyesno(
                    t("wf.limit_pyramid_title"),
                    t("wf.limit_pyramid_mismatch", limit, defaults["pyramid_sum"]),
                    icon=messagebox.WARNING,
                ):
                    return
        preview_remaining_steps[0] = steps[3:]
        preview_steps = steps[:3]
        preview_mode[0] = True
        sequence_cancelled[0] = False
        run_btn.config(state=tk.DISABLED)
        preview_btn.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("wf.running"), foreground="gray")
        progress_bar["value"] = 0
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("wf.running") + "\n")
        log_area.config(state=tk.DISABLED)
        process_holder.clear()
        first_action, first_extra = preview_steps.pop(0)
        first_fill_total = _parse_fill_limit(first_extra) if first_action == "fill_articles" else 0
        first_fill_done = [0]
        if first_fill_total > 0:
            step_label.config(text=t("wf.step_progress_fill", 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)), 0, first_fill_total))
        else:
            step_label.config(text=t("wf.step_progress", 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
        first_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)) + " ---", ""]
        for h in first_header:
            root.after(0, lambda line=h: append_log(line))
        proc, q = run_workflow_streaming(first_action, extra_args=first_extra)
        process_holder.append((first_action, proc))
        root.after(50, lambda: poll_sequence(preview_steps, first_header, [], q, run_btn, cancel_btn, first_fill_total, first_fill_done))

    def _fill_selected(selected_stems: list[str], all_items: list[tuple[str, str]], prev_output: str):
        articles_dir = get_project_root() / "content" / "articles"
        all_stems = {stem for _, stem in all_items}
        rejected = all_stems - set(selected_stems)
        deleted = 0
        for stem in rejected:
            p = articles_dir / (stem + ".md")
            if p.exists():
                try:
                    p.unlink()
                    deleted += 1
                except OSError:
                    pass
        remaining_steps = list(preview_remaining_steps[0])
        sequence_cancelled[0] = False
        run_btn.config(state=tk.DISABLED)
        preview_btn.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("wf.fill_selected_running"), foreground="gray")
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, prev_output + "\n")
        if deleted:
            log_area.insert(tk.END, "\n" + t("sel.deleted_skeletons", deleted) + "\n")
        log_area.insert(tk.END, "\n" + t("wf.fill_selected_running") + "\n")
        log_area.config(state=tk.DISABLED)
        process_holder.clear()
        if not remaining_steps:
            return
        first_action, first_extra = remaining_steps.pop(0)
        completed = len(SEQUENCE_ACTIONS) - len(remaining_steps) - 1
        progress_bar["value"] = completed
        fill_total = _parse_fill_limit(first_extra) if first_action == "fill_articles" else 0
        fill_done = [0]
        if fill_total > 0:
            step_label.config(text=t("wf.step_progress_fill", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)), 0, fill_total))
        else:
            step_label.config(text=t("wf.step_progress", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
        first_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)) + " ---", ""]
        accumulated = prev_output.splitlines()
        if deleted:
            accumulated.append(t("sel.deleted_skeletons", deleted))
        accumulated += ["", t("wf.fill_selected_running")]
        for h in first_header:
            root.after(0, lambda line=h: append_log(line))
        accumulated += first_header
        proc, q = run_workflow_streaming(first_action, extra_args=first_extra)
        process_holder.append((first_action, proc))
        root.after(50, lambda: poll_sequence(remaining_steps, accumulated, [], q, run_btn, cancel_btn, fill_total, fill_done))

    def cancel_run():
        sequence_cancelled[0] = True
        if len(process_holder) >= 1 and isinstance(process_holder[0], tuple):
            _, proc = process_holder[0]
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    run_btn = ttk.Button(row_btn, text=t("btn.run"), command=run)
    run_btn.pack(side=tk.LEFT, padx=(0, 5))
    preview_btn = ttk.Button(row_btn, text=t("wf.preview_btn"), command=run_preview)
    preview_btn.pack(side=tk.LEFT, padx=(0, 5))
    cancel_btn = ttk.Button(row_btn, text=t("btn.cancel"), command=cancel_run, state=tk.DISABLED)
    cancel_btn.pack(side=tk.LEFT, padx=5)

    row2 = ttk.Frame(right_frame)
    row2.pack(fill=tk.X, pady=5)
    ttk.Button(row2, text=t("btn.save_log_file"), command=lambda: save_log()).pack(side=tk.LEFT, padx=5)

    def save_log():
        if not last_output_holder:
            messagebox.showinfo(t("msg.info"), t("wf.save_log_no"))
            return
        out, action = last_output_holder[0]
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log", "*.log"), ("Wszystkie", "*.*")],
            initialfile=f"flowtaro_{action}.log",
        )
        if path:
            try:
                Path(path).write_text(out, encoding="utf-8")
                messagebox.showinfo(t("msg.saved"), f"{t('msg.saved')}: {path}")
            except Exception as e:
                messagebox.showerror(t("msg.error"), str(e))

    def save_to_logs():
        if not last_output_holder:
            messagebox.showinfo(t("msg.info"), t("wf.save_logs_no"))
            return
        out, action = last_output_holder[0]
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / f"flowtaro_{action}.log"
        try:
            log_path.write_text(out, encoding="utf-8")
            messagebox.showinfo(t("msg.saved"), f"{t('msg.saved')}: {log_path}")
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))

    ttk.Button(row2, text=t("btn.save_logs_dir"), command=save_to_logs).pack(side=tk.LEFT, padx=5)
    return f


def build_refresh_tab(parent, last_output_holder: list):
    """Zakładka Odśwież artykuły — sekcjonowany layout z Canvas+Scrollbar, progress bar."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    italic_font = ("TkDefaultFont", 9, "italic")
    refresh_hint_labels: list = []

    def _hint(parent_row, key):
        hf = ttk.Frame(parent_row)
        hf.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        lbl = tk.Label(hf, text=t(key), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=400)
        lbl.pack(anchor=tk.W, fill=tk.X, expand=True)
        refresh_hint_labels.append(lbl)

    paned_h = ttk.PanedWindow(f, orient=tk.HORIZONTAL)
    paned_h.pack(fill=tk.BOTH, expand=True)

    left_outer = ttk.Frame(paned_h)
    paned_h.add(left_outer, weight=2)

    # R8: Canvas + Scrollbar
    canvas = tk.Canvas(left_outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(left_outer, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

    def _on_canvas_cfg(ev):
        canvas.itemconfig(canvas_window, width=ev.width)
        wrap_w = max(80, ev.width - 260)
        for lbl in refresh_hint_labels:
            try:
                lbl.configure(wraplength=wrap_w)
            except tk.TclError:
                pass
    canvas.bind("<Configure>", _on_canvas_cfg)
    canvas.bind("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _set_initial_sash_refresh():
        paned_h.update_idletasks()
        w = paned_h.winfo_width()
        if w > 100:
            paned_h.sashpos(0, int(0.7 * w))
    f.after(400, _set_initial_sash_refresh)
    f.bind("<Map>", lambda e: f.after(100, _set_initial_sash_refresh))

    # --- R4: sekcja „Zakres" ---
    lf_scope = ttk.LabelFrame(inner, text=t("refresh.section_scope"))
    lf_scope.pack(fill=tk.X, pady=(0, 10))
    scope_inner = ttk.Frame(lf_scope, padding=5)
    scope_inner.pack(fill=tk.X)

    row = ttk.Frame(scope_inner); row.pack(fill=tk.X)
    ttk.Label(row, text=t("refresh.days_label")).pack(side=tk.LEFT, padx=(0, 5))
    days_combo = ttk.Combobox(row, values=("7", "14", "30", "60", "90"), width=8, state="readonly")
    days_combo.pack(side=tk.LEFT, padx=5); days_combo.set("90")
    _hint(row, "refresh.days_desc")

    row_max = ttk.Frame(scope_inner); row_max.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(row_max, text=t("refresh.max_days_label")).pack(side=tk.LEFT, padx=(0, 5))
    max_days_combo = ttk.Combobox(row_max, values=(t("refresh.max_days_off"), "0", "1", "2", "3", "4", "5", "6"), width=8, state="readonly")
    max_days_combo.pack(side=tk.LEFT, padx=5); max_days_combo.set(t("refresh.max_days_off"))
    _hint(row_max, "refresh.max_days_desc")

    # Zakres dat (od – do); gdy oba ustawione, ma pierwszenstwo nad „starsze/młodsze niż”
    row_range = ttk.Frame(scope_inner); row_range.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(row_range, text=t("refresh.from_date_label")).pack(side=tk.LEFT, padx=(0, 5))
    from_date_entry = ttk.Entry(row_range, width=12)
    from_date_entry.pack(side=tk.LEFT, padx=2)
    ttk.Label(row_range, text=t("refresh.to_date_label")).pack(side=tk.LEFT, padx=(8, 5))
    to_date_entry = ttk.Entry(row_range, width=12)
    to_date_entry.pack(side=tk.LEFT, padx=2)
    _hint(row_range, "refresh.date_range_desc")

    # R3+R9: Limit — „Bez limitu" zamiast „0", unified values
    limit_values = (t("refresh.limit_none"), "1", "5", "10", "20", "50")
    row_lim = ttk.Frame(scope_inner); row_lim.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(row_lim, text=t("refresh.limit_label")).pack(side=tk.LEFT, padx=(0, 5))
    limit_combo = ttk.Combobox(row_lim, values=limit_values, width=12, state="readonly")
    limit_combo.pack(side=tk.LEFT, padx=5); limit_combo.set(t("refresh.limit_none"))
    _hint(row_lim, "refresh.limit_desc")

    row_dry = ttk.Frame(scope_inner); row_dry.pack(fill=tk.X, pady=(6, 0))
    dry_run_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(row_dry, text=t("refresh.dry_run"), variable=dry_run_var).pack(side=tk.LEFT, padx=(0, 5))
    _hint(row_dry, "refresh.dry_run_desc")

    # --- R4: sekcja „Opcje AI" ---
    lf_ai = ttk.LabelFrame(inner, text=t("refresh.section_ai_options"))
    lf_ai.pack(fill=tk.X, pady=(0, 10))
    ai_inner = ttk.Frame(lf_ai, padding=5)
    ai_inner.pack(fill=tk.X)

    row_nr = ttk.Frame(ai_inner); row_nr.pack(fill=tk.X)
    no_render_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(row_nr, text=t("refresh.no_render"), variable=no_render_var).pack(side=tk.LEFT, padx=(0, 5))
    _hint(row_nr, "refresh.no_render_desc")

    row_block = ttk.Frame(ai_inner); row_block.pack(fill=tk.X, pady=(6, 0))
    block_on_fail_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(row_block, text=t("refresh.block_on_fail"), variable=block_on_fail_var).pack(side=tk.LEFT, padx=(0, 5))
    _hint(row_block, "refresh.block_on_fail_desc")

    row_remap = ttk.Frame(ai_inner); row_remap.pack(fill=tk.X, pady=(6, 0))
    remap_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(row_remap, text=t("refresh.remap"), variable=remap_var).pack(side=tk.LEFT, padx=(0, 5))
    _hint(row_remap, "refresh.remap_desc")

    row_re_skeleton = ttk.Frame(ai_inner); row_re_skeleton.pack(fill=tk.X, pady=(6, 0))
    re_skeleton_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(row_re_skeleton, text=t("refresh.re_skeleton"), variable=re_skeleton_var).pack(side=tk.LEFT, padx=(0, 5))
    _hint(row_re_skeleton, "refresh.re_skeleton_desc")

    row_retries = ttk.Frame(ai_inner); row_retries.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(row_retries, text=t("refresh.quality_retries_label")).pack(side=tk.LEFT, padx=(0, 5))
    retries_combo = ttk.Combobox(row_retries, values=(t("refresh.retries_1"), t("refresh.retries_2"), t("refresh.retries_3")), width=14, state="readonly")
    retries_combo.pack(side=tk.LEFT, padx=5); retries_combo.set(t("refresh.retries_2"))
    _hint(row_retries, "refresh.quality_retries_desc")

    # R6: info o hardcoded parametrach
    row_info = ttk.Frame(ai_inner); row_info.pack(fill=tk.X, pady=(8, 0))
    tk.Label(row_info, text=t("refresh.hardcoded_info"), font=italic_font, fg="#888", anchor=tk.W).pack(anchor=tk.W)

    refresh_btn_row = ttk.Frame(inner)
    refresh_btn_row.pack(fill=tk.X, pady=(8, 0))

    right_frame = ttk.Frame(paned_h)
    paned_h.add(right_frame, weight=1)
    ttk.Label(right_frame, text=t("wf.log")).pack(anchor=tk.W, pady=(0, 2))
    progress_label = ttk.Label(right_frame, text="", foreground="gray")
    progress_label.pack(anchor=tk.W, pady=(0, 2))
    progress_bar = ttk.Progressbar(right_frame, mode="determinate", maximum=1, value=0, length=280)
    progress_bar.pack(fill=tk.X, pady=(0, 5))
    log_area = scrolledtext.ScrolledText(right_frame, height=14, wrap=tk.WORD, state=tk.DISABLED)
    log_area.pack(fill=tk.BOTH, expand=True, pady=5)
    status_label = ttk.Label(right_frame, text="", foreground="gray")
    status_label.pack(anchor=tk.W)
    row_save = ttk.Frame(right_frame)
    row_save.pack(fill=tk.X, pady=5)
    ttk.Button(row_save, text=t("btn.save_log_file"), command=lambda: _save_log_refresh()).pack(side=tk.LEFT, padx=5)
    ttk.Button(row_save, text=t("btn.save_logs_dir"), command=lambda: _save_to_logs_refresh()).pack(side=tk.LEFT, padx=5)
    process_holder = []

    def _save_log_refresh():
        if not last_output_holder:
            messagebox.showinfo(t("msg.info"), t("wf.save_log_no"))
            return
        out, action = last_output_holder[0]
        path = filedialog.asksaveasfilename(defaultextension=".log", filetypes=[("Log", "*.log"), ("Wszystkie", "*.*")], initialfile=f"flowtaro_{action}.log")
        if path:
            try:
                Path(path).write_text(out, encoding="utf-8")
                messagebox.showinfo(t("msg.saved"), f"{t('msg.saved')}: {path}")
            except Exception as e:
                messagebox.showerror(t("msg.error"), str(e))

    def _save_to_logs_refresh():
        if not last_output_holder:
            messagebox.showinfo(t("msg.info"), t("wf.save_logs_no"))
            return
        out, action = last_output_holder[0]
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / f"flowtaro_{action}.log"
        try:
            log_path.write_text(out, encoding="utf-8")
            messagebox.showinfo(t("msg.saved"), f"{t('msg.saved')}: {log_path}")
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))

    def append_log(line):
        log_area.config(state=tk.NORMAL)
        log_area.insert(tk.END, line + "\n")
        log_area.see(tk.END)
        log_area.config(state=tk.DISABLED)

    def handle_refresh_progress_line(line: str) -> bool:
        """If line is FLOWTARO_PROGRESS_TOTAL or FLOWTARO_PROGRESS, update progress bar/label and return True (do not log)."""
        s = (line or "").strip()
        if s.startswith("FLOWTARO_PROGRESS_TOTAL:"):
            try:
                n = int(s.split(":", 1)[1].strip())
                progress_bar["maximum"] = max(1, n)
                progress_bar["value"] = 0
                progress_label.config(text=t("refresh.progress_step", 0, n))
            except (ValueError, IndexError):
                pass
            return True
        if s.startswith("FLOWTARO_PROGRESS:"):
            try:
                m = int(s.split(":", 1)[1].strip())
                total = progress_bar["maximum"]
                if total < 1:
                    total = 1
                progress_bar["value"] = min(m, total)
                progress_label.config(text=t("refresh.progress_step", m, total))
            except (ValueError, IndexError):
                pass
            return True
        return False

    _refresh_article_re = re.compile(r"^\s+(\S+\.md)\s+last_updated:")

    def _parse_dry_run_articles(output: str) -> list[tuple[str, str]]:
        items = []
        for line in output.splitlines():
            m = _refresh_article_re.match(line)
            if m:
                fname = m.group(1).strip()
                stem = fname.removesuffix(".md")
                items.append((fname, stem))
        return items

    def _get_limit_value() -> str:
        raw = (limit_combo.get() or "").strip()
        if not raw or raw == t("refresh.limit_none"):
            return "0"
        return raw

    def _run_selective_refresh(stems: list[str]):
        import tempfile
        tmp = Path(tempfile.mktemp(suffix=".txt", prefix="flowtaro_refresh_"))
        tmp.write_text("\n".join(stems), encoding="utf-8")
        from_str = (from_date_entry.get() or "").strip()
        to_str = (to_date_entry.get() or "").strip()
        if from_str and to_str:
            try:
                from_d = datetime.strptime(from_str, "%Y-%m-%d").date()
                to_d = datetime.strptime(to_str, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror(t("msg.error"), t("refresh.date_invalid_format"))
                return
            if from_d > to_d:
                messagebox.showerror(t("msg.error"), t("refresh.date_range_invalid"))
                return
            extra = ["--from-date", from_str, "--to-date", to_str, "--include-file", str(tmp)]
        else:
            max_days_val = (max_days_combo.get() or "").strip()
            if max_days_val and max_days_val != t("refresh.max_days_off"):
                extra = ["--max-days", max_days_val]
            else:
                extra = ["--days", (days_combo.get() or "90").strip()]
            extra += ["--include-file", str(tmp)]
        if no_render_var.get():
            extra.append("--no-render")
        _append_common_extra(extra)
        run_btn.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("refresh.running"), foreground="gray")
        progress_bar["maximum"] = 1
        progress_bar["value"] = 0
        progress_label.config(text="")
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("refresh.running") + "\n")
        log_area.config(state=tk.DISABLED)
        out_lines = []
        process_holder.clear()
        proc, q = run_workflow_streaming("refresh_articles", extra_args=extra)
        process_holder.append(("refresh_articles", proc))
        root_w = parent.winfo_toplevel()
        root_w.after(50, lambda: poll(q, run_btn, cancel_btn, out_lines))

    def set_done(out, code, rbtn, cbtn):
        progress_label.config(text="")
        log_area.config(state=tk.NORMAL)
        if out:
            log_area.delete("1.0", tk.END)
            log_area.insert(tk.END, out)
        log_area.insert(tk.END, f"\n\n[Kod powrotu: {code}]")
        log_area.config(state=tk.DISABLED)
        rbtn.config(state=tk.NORMAL)
        cbtn.config(state=tk.DISABLED)
        status_label.config(text=t("refresh.status_ok") if code == 0 else t("refresh.status_error"), foreground="green" if code == 0 else "red")
        last_output_holder.clear()
        last_output_holder.append((out or "", "refresh_articles"))
        if code == 0 and dry_run_var.get() and out:
            items = _parse_dry_run_articles(out)
            if items:
                root_w = parent.winfo_toplevel()
                root_w.after(100, lambda: _show_article_selector(
                    root_w, t("sel.title_refresh"), items,
                    t("sel.confirm_refresh"), _run_selective_refresh))

    def poll(q, run_btn, cancel_btn, out_lines):
        try:
            while True:
                item = q.get_nowait()
                if item[1] is not None:
                    root = parent.winfo_toplevel()
                    root.after(0, lambda: set_done("\n".join(out_lines), item[1], run_btn, cancel_btn))
                    return
                if item[0] is not None:
                    line = item[0]
                    if not handle_refresh_progress_line(line):
                        out_lines.append(line)
                        root = parent.winfo_toplevel()
                        root.after(0, lambda l=line: append_log(l))
        except queue.Empty:
            root = parent.winfo_toplevel()
            root.after(50, lambda: poll(q, run_btn, cancel_btn, out_lines))

    def _append_common_extra(extra: list[str], include_re_skeleton: bool = True):
        if block_on_fail_var.get():
            extra.append("--block_on_fail")
        if remap_var.get():
            extra.append("--remap")
        if include_re_skeleton and re_skeleton_var.get():
            extra.append("--re-skeleton")
        retries_raw = (retries_combo.get() or "").strip()
        retries_val = retries_raw[0] if retries_raw and retries_raw[0].isdigit() else "2"
        if retries_val != "2":
            extra += ["--quality_retries", retries_val]

    def _run_retry_failed():
        failed_file = get_project_root() / "logs" / "last_refresh_failed.txt"
        if not failed_file.exists():
            messagebox.showinfo(t("msg.info"), t("refresh.retry_failed_no_list"))
            return
        try:
            content = failed_file.read_text(encoding="utf-8").strip()
        except OSError:
            messagebox.showwarning(t("msg.warning"), t("refresh.retry_failed_no_list"))
            return
        if not content:
            messagebox.showinfo(t("msg.info"), t("refresh.retry_failed_no_list"))
            return
        extra = ["--include-file", str(failed_file)]
        if no_render_var.get():
            extra.append("--no-render")
        _append_common_extra(extra, include_re_skeleton=False)
        run_btn.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("refresh.running"), foreground="gray")
        progress_bar["maximum"] = 1
        progress_bar["value"] = 0
        progress_label.config(text="")
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("refresh.running") + "\n")
        log_area.config(state=tk.DISABLED)
        out_lines = []
        process_holder.clear()
        proc, q = run_workflow_streaming("refresh_articles", extra_args=extra)
        process_holder.append(("refresh_articles", proc))
        root = parent.winfo_toplevel()
        root.after(50, lambda: poll(q, run_btn, cancel_btn, out_lines))

    def run():
        limit_val = _get_limit_value()
        from_str = (from_date_entry.get() or "").strip()
        to_str = (to_date_entry.get() or "").strip()
        if from_str and to_str:
            try:
                from_d = datetime.strptime(from_str, "%Y-%m-%d").date()
                to_d = datetime.strptime(to_str, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror(t("msg.error"), t("refresh.date_invalid_format"))
                return
            if from_d > to_d:
                messagebox.showerror(t("msg.error"), t("refresh.date_range_invalid"))
                return
            extra = ["--from-date", from_str, "--to-date", to_str, "--limit", limit_val]
        else:
            max_days_val = (max_days_combo.get() or "").strip()
            if max_days_val and max_days_val != t("refresh.max_days_off"):
                extra = ["--max-days", max_days_val, "--limit", limit_val]
            else:
                extra = ["--days", (days_combo.get() or "90").strip(), "--limit", limit_val]
        if dry_run_var.get():
            extra.append("--dry-run")
        if no_render_var.get():
            extra.append("--no-render")
        _append_common_extra(extra)
        run_btn.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("refresh.running"), foreground="gray")
        progress_bar["maximum"] = 1
        progress_bar["value"] = 0
        progress_label.config(text="")
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("refresh.running") + "\n")
        log_area.config(state=tk.DISABLED)
        out_lines = []
        process_holder.clear()
        proc, q = run_workflow_streaming("refresh_articles", extra_args=extra)
        process_holder.append(("refresh_articles", proc))
        root = parent.winfo_toplevel()
        root.after(50, lambda: poll(q, run_btn, cancel_btn, out_lines))

    def cancel_run():
        if process_holder and isinstance(process_holder[0], tuple):
            _, proc = process_holder[0]
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    run_btn = ttk.Button(refresh_btn_row, text=t("refresh.run"), command=run)
    run_btn.pack(side=tk.LEFT, padx=5)
    cancel_btn = ttk.Button(refresh_btn_row, text=t("refresh.run_cancel"), command=cancel_run, state=tk.DISABLED)
    cancel_btn.pack(side=tk.LEFT, padx=5)
    retry_failed_btn = ttk.Button(refresh_btn_row, text=t("refresh.retry_failed"), command=_run_retry_failed)
    retry_failed_btn.pack(side=tk.LEFT, padx=5)
    _create_tooltip(retry_failed_btn, t("refresh.retry_failed_desc"))
    return f


def build_git_tab(parent):
    """Zakładka Git: add content/articles/, commit z komunikatem, push (bez force). Status, walidacje repo i PATH."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    root_dir = get_project_root()
    articles_dir = root_dir / "content" / "articles"
    if not articles_dir.is_dir():
        ttk.Label(f, text="Błąd: brak content/articles/", foreground="red").pack(anchor=tk.W)
        return f

    italic_font = ("TkDefaultFont", 9, "italic")
    GIT_PUSH_SKIP_FILE = PREFS_DIR / "git_push_confirm_skip.txt"

    def _run_git(args: list[str]) -> tuple[str, int]:
        """Uruchamia git w katalogu projektu. Zwraca (stdout+stderr, kod)."""
        env = {**os.environ}
        for k in ("LANG", "LC_ALL", "PYTHONIOENCODING"):
            env.setdefault(k, "utf-8")
        try:
            r = subprocess.run(
                ["git"] + args,
                cwd=root_dir,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            out = (r.stdout or "") + (r.stderr or "")
            return (out.strip() if out else "", r.returncode)
        except FileNotFoundError:
            return (t("git.err_no_git"), 128)
        except subprocess.TimeoutExpired:
            return ("Git: timeout.", 124)

    def _is_repo() -> tuple[bool, str]:
        if not (root_dir / ".git").exists():
            return False, t("git.err_not_repo")
        return True, ""

    def _git_available() -> bool:
        out, code = _run_git(["--version"])
        return code == 0

    def _get_branch() -> str:
        out, code = _run_git(["branch", "--show-current"])
        return out.strip() if code == 0 else ""

    def _get_remote() -> str:
        out, code = _run_git(["remote", "get-url", "origin"])
        return out.strip() if code == 0 else ""

    def _append_log(text: str):
        log_area.config(state=tk.NORMAL)
        log_area.insert(tk.END, text + "\n")
        log_area.see(tk.END)
        log_area.config(state=tk.DISABLED)

    def _update_branch_remote_label():
        branch = _get_branch() or "—"
        remote = _get_remote() or "—"
        branch_remote_var.set(t("git.branch_remote", branch, remote))

    paned_h = ttk.PanedWindow(f, orient=tk.HORIZONTAL)
    paned_h.pack(fill=tk.BOTH, expand=True)

    left_outer = ttk.Frame(paned_h)
    paned_h.add(left_outer, weight=1)

    inner = ttk.Frame(left_outer, padding=5)
    inner.pack(fill=tk.X)

    lf_status = ttk.LabelFrame(inner, text=t("git.section_status"))
    lf_status.pack(fill=tk.X, pady=(0, 8))
    status_inner = ttk.Frame(lf_status, padding=5)
    status_inner.pack(fill=tk.X)
    ttk.Button(status_inner, text=t("git.btn_status"), command=lambda: _do_status()).pack(side=tk.LEFT, padx=(0, 5))
    tk.Label(status_inner, text=t("git.btn_status_desc"), font=italic_font, fg="gray", wraplength=320).pack(anchor=tk.W)

    lf_add = ttk.LabelFrame(inner, text=t("git.section_add"))
    lf_add.pack(fill=tk.X, pady=(0, 8))
    add_inner = ttk.Frame(lf_add, padding=5)
    add_inner.pack(fill=tk.X)
    ttk.Button(add_inner, text=t("git.btn_add"), command=lambda: _do_add()).pack(side=tk.LEFT, padx=(0, 5))
    tk.Label(add_inner, text=t("git.btn_add_desc"), font=italic_font, fg="gray", wraplength=320).pack(anchor=tk.W)

    lf_commit = ttk.LabelFrame(inner, text=t("git.section_commit"))
    lf_commit.pack(fill=tk.X, pady=(0, 8))
    commit_inner = ttk.Frame(lf_commit, padding=5)
    commit_inner.pack(fill=tk.X)
    ttk.Label(commit_inner, text=t("git.commit_message")).pack(side=tk.LEFT, padx=(0, 5))
    commit_entry = ttk.Entry(commit_inner, width=36)
    commit_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
    ttk.Button(commit_inner, text=t("git.btn_commit"), command=lambda: _do_commit()).pack(side=tk.LEFT, padx=5)
    commit_inner.pack(fill=tk.X)
    tk.Label(lf_commit, text=t("git.btn_commit_desc"), font=italic_font, fg="gray", wraplength=320).pack(anchor=tk.W, padx=5, pady=(0, 5))

    branch_remote_var = tk.StringVar(value="")
    _update_branch_remote_label()
    lf_push = ttk.LabelFrame(inner, text=t("git.section_push"))
    lf_push.pack(fill=tk.X, pady=(0, 8))
    push_inner = ttk.Frame(lf_push, padding=5)
    push_inner.pack(fill=tk.X)
    tk.Label(push_inner, textvariable=branch_remote_var, font=italic_font, fg="gray").pack(anchor=tk.W)
    ttk.Button(push_inner, text=t("git.btn_push"), command=lambda: _do_push()).pack(anchor=tk.W, pady=(4, 0))
    tk.Label(lf_push, text=t("git.btn_push_desc"), font=italic_font, fg="gray", wraplength=320).pack(anchor=tk.W, padx=5, pady=(0, 5))

    right_frame = ttk.Frame(paned_h)
    paned_h.add(right_frame, weight=1)
    ttk.Label(right_frame, text=t("git.log_title")).pack(anchor=tk.W, pady=(0, 2))
    log_area = scrolledtext.ScrolledText(right_frame, height=18, wrap=tk.WORD, state=tk.DISABLED)
    log_area.pack(fill=tk.BOTH, expand=True, pady=5)

    def _do_status():
        repo_ok, repo_err = _is_repo()
        if not repo_ok:
            _append_log(repo_err)
            return
        if not _git_available():
            _append_log(t("git.err_no_git"))
            return
        out, code = _run_git(["status", "--short"])
        _append_log("git status --short\n" + ("---\n" + out if out else "(pusty)"))
        if code == 0:
            _update_branch_remote_label()

    def _do_add():
        repo_ok, repo_err = _is_repo()
        if not repo_ok:
            messagebox.showerror(t("msg.error"), repo_err)
            return
        if not _git_available():
            messagebox.showerror(t("msg.error"), t("git.err_no_git"))
            return
        rel = "content/articles/"
        out, code = _run_git(["add", rel])
        _append_log(f"git add {rel}\n---\n" + (out if out else "(OK)"))
        if code == 0:
            _update_branch_remote_label()

    def _do_commit():
        repo_ok, repo_err = _is_repo()
        if not repo_ok:
            messagebox.showerror(t("msg.error"), repo_err)
            return
        if not _git_available():
            messagebox.showerror(t("msg.error"), t("git.err_no_git"))
            return
        msg = (commit_entry.get() or "").strip()
        if not msg:
            messagebox.showwarning(t("msg.warning"), t("git.err_commit_empty"))
            return
        out, code = _run_git(["commit", "-m", msg])
        _append_log("git commit -m \"...\"\n---\n" + (out if out else "(OK)"))
        if code == 0:
            commit_entry.delete(0, tk.END)
            _update_branch_remote_label()

    def _do_push():
        repo_ok, repo_err = _is_repo()
        if not repo_ok:
            messagebox.showerror(t("msg.error"), repo_err)
            return
        if not _git_available():
            messagebox.showerror(t("msg.error"), t("git.err_no_git"))
            return
        remote = _get_remote()
        if not remote:
            messagebox.showerror(t("msg.error"), t("git.err_no_remote"))
            return
        skip_confirm = GIT_PUSH_SKIP_FILE.exists() and (GIT_PUSH_SKIP_FILE.read_text(encoding="utf-8").strip() == "1")
        if not skip_confirm:
            dialog = tk.Toplevel(parent.winfo_toplevel())
            dialog.title(t("git.confirm_push_title"))
            dialog.transient(parent.winfo_toplevel())
            dialog.grab_set()
            dialog.geometry("380x120")
            var_skip = tk.BooleanVar(value=False)
            ttk.Label(dialog, text=t("git.confirm_push")).pack(pady=(15, 10), padx=15, anchor=tk.W)
            ttk.Checkbutton(dialog, text=t("git.confirm_push_skip"), variable=var_skip).pack(anchor=tk.W, padx=15)
            btn_row = ttk.Frame(dialog)
            btn_row.pack(pady=10, padx=15)

            def on_yes():
                if var_skip.get():
                    PREFS_DIR.mkdir(parents=True, exist_ok=True)
                    GIT_PUSH_SKIP_FILE.write_text("1", encoding="utf-8")
                dialog.destroy()
                _run_push()

            def on_no():
                dialog.destroy()

            ttk.Button(btn_row, text=t("btn.run"), command=on_yes).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_row, text=t("btn.cancel"), command=on_no).pack(side=tk.LEFT, padx=5)
            dialog.focus_set()
            return
        _run_push()

    def _run_push():
        out, code = _run_git(["push"])
        if code != 0 and "has no upstream" in out:
            branch = _get_branch()
            if branch:
                out2, code2 = _run_git(["push", "-u", "origin", branch])
                out = out + "\n---\n(git push -u origin " + branch + ")\n" + out2
                code = code2
        _append_log("git push\n---\n" + (out if out else "(OK)"))
        if code == 0:
            _update_branch_remote_label()

    def _set_initial_sash():
        paned_h.update_idletasks()
        w = paned_h.winfo_width()
        if w > 100:
            paned_h.sashpos(0, min(320, int(0.4 * w)))
    f.after(300, _set_initial_sash)
    f.bind("<Map>", lambda e: f.after(100, _set_initial_sash))

    return f


def build_config_tab(parent):
    """Zakładka Konfiguracja: spójna z Generuj artykuły – przewijany formularz, etykiety 28 znaków, podpowiedzi kursywą."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    try:
        from content_index import load_config
        from config_manager import write_config
    except ImportError as e:
        ttk.Label(f, text=f"Błąd importu: {e}", foreground="red").pack(anchor=tk.W)
        return f

    italic_font = ("TkDefaultFont", 9, "italic")
    defaults_uc = get_use_case_defaults()
    cat_vals = [t("wf.category_any")] + list(defaults_uc.get("categories", []))
    combo_width = min(30, max((len(str(v)) for v in cat_vals), default=10) + 2)
    combo_width = max(12, combo_width)

    canvas = tk.Canvas(f, highlightthickness=0)
    scrollbar = ttk.Scrollbar(f, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    config_hint_labels: list = []

    def _on_canvas_configure(ev):
        canvas.itemconfig(canvas_window, width=ev.width)
        wrap_w = max(80, ev.width - 260)
        for lbl in config_hint_labels:
            try:
                lbl.configure(wraplength=wrap_w)
            except tk.TclError:
                pass
    canvas.bind("<Configure>", _on_canvas_configure)
    def _on_mousewheel(ev):
        canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
    canvas.bind("<MouseWheel>", _on_mousewheel)

    def load_ui():
        config_path = get_project_root() / "content" / "config.yaml"
        if not config_path.exists():
            return
        cfg = load_config(config_path)
        prod = (cfg.get("production_category") or "").strip()
        hub = (cfg.get("hub_slug") or "").strip()
        sandbox = cfg.get("sandbox_categories") or []
        suggested = cfg.get("suggested_problems") or []
        category_mode = (cfg.get("category_mode") or "production_only").strip().lower()
        if category_mode not in {"production_only", "preserve_sandbox"}:
            category_mode = "production_only"
        batch = str(cfg.get("use_case_batch_size") or 9)
        pyramid = cfg.get("use_case_audience_pyramid") or [3, 3]
        pyramid_str = ", ".join(str(x) for x in pyramid)
        # production: lista [prod] + sandbox (bez duplikatów)
        cats = [prod] if prod else []
        for s in sandbox:
            if isinstance(s, str) and s.strip() and s.strip() not in cats:
                cats.append(s.strip())
        prod_vals = (cats if cats else [prod or "ai-marketing-automation"]) + [t("config.other")]
        e_prod["values"] = prod_vals
        if prod and prod in (cats if cats else []):
            e_prod.set(prod)
            e_prod_other.pack_forget()
        else:
            e_prod.set(t("config.other"))
            e_prod_other.delete(0, tk.END)
            e_prod_other.insert(0, prod or "")
            e_prod_other.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        hub_vals = list(dict.fromkeys([hub, prod] + [s for s in sandbox if isinstance(s, str) and s.strip()]))
        e_hub["values"] = hub_vals
        e_hub.set(hub or "")
        mode_vals = {
            "production_only": t("config.category_mode_production_only"),
            "preserve_sandbox": t("config.category_mode_preserve_sandbox"),
        }
        e_category_mode["values"] = [
            t("config.category_mode_production_only"),
            t("config.category_mode_preserve_sandbox"),
        ]
        e_category_mode.set(mode_vals.get(category_mode, t("config.category_mode_production_only")))
        lb_sandbox.delete(0, tk.END)
        for s in sandbox:
            lb_sandbox.insert(tk.END, s if isinstance(s, str) else str(s))
        e_sandbox_new.delete(0, tk.END)
        lb_suggested.delete(0, tk.END)
        for s in suggested:
            lb_suggested.insert(tk.END, s if isinstance(s, str) else str(s))
        e_suggested_new.delete(0, tk.END)
        e_batch.set(batch)
        batch_int = int(batch)
        inter_count = pyramid[0] if len(pyramid) >= 1 else 3
        pro_count = pyramid[1] if len(pyramid) >= 2 else 0
        beg_count = batch_int - inter_count - pro_count
        if beg_count < 0:
            beg_count = 0
        sp_beg.set(beg_count)
        sp_int.set(inter_count)
        sp_pro.set(pro_count)
        _pyr_update_sum()

    def save_ui():
        try:
            if e_prod.get().strip() == t("config.other"):
                prod = e_prod_other.get().strip() or "ai-marketing-automation"
            else:
                prod = e_prod.get().strip()
                if not prod:
                    prod = (e_prod["values"] or ["ai-marketing-automation"])[0]
            hub = e_hub.get().strip()
            sandbox = [lb_sandbox.get(i) for i in range(lb_sandbox.size()) if lb_sandbox.get(i).strip()]
            suggested = [lb_suggested.get(i) for i in range(lb_suggested.size()) if lb_suggested.get(i).strip()]
            mode_display = (e_category_mode.get() or "").strip()
            category_mode = "preserve_sandbox" if mode_display == t("config.category_mode_preserve_sandbox") else "production_only"
            batch = int(e_batch.get().strip() or 9)
            pyramid = [sp_int.get(), sp_pro.get()]
            config_path = get_project_root() / "content" / "config.yaml"
            write_config(
                config_path,
                prod,
                hub,
                sandbox,
                use_case_batch_size=batch,
                use_case_audience_pyramid=pyramid,
                suggested_problems=suggested,
                category_mode=category_mode,
            )
            messagebox.showinfo(t("msg.saved"), f"{t('config.saved')}\n\n{config_path}")
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))

    # Strona / hub
    lf_hub = ttk.LabelFrame(inner, text=t("config.section_hub"), padding=5)
    lf_hub.pack(fill=tk.X, pady=(0, 10))
    row1 = ttk.Frame(lf_hub)
    row1.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(row1, text=t("config.production"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_prod = ttk.Frame(row1)
    hint_prod.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_prod_hint = tk.Label(hint_prod, text=t("config.production_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_prod_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_prod_hint)
    e_prod = ttk.Combobox(row1, width=combo_width, state="readonly")
    e_prod.pack(side=tk.LEFT)
    row1b = ttk.Frame(lf_hub)
    row1b.pack(fill=tk.X, pady=2)
    e_prod_other = ttk.Entry(row1b, width=40)
    e_prod_other.pack(side=tk.LEFT, padx=(33, 0), fill=tk.X, expand=True)
    row1b.pack_forget()
    def _on_prod_change():
        if e_prod.get().strip() == t("config.other"):
            row1b.pack(fill=tk.X, pady=2)
        else:
            row1b.pack_forget()
    e_prod.bind("<<ComboboxSelected>>", lambda e: _on_prod_change())
    row2 = ttk.Frame(lf_hub)
    row2.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(row2, text=t("config.hub_slug"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_hub = ttk.Frame(row2)
    hint_hub.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_hub_hint = tk.Label(hint_hub, text=t("config.hub_slug_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_hub_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_hub_hint)
    e_hub = ttk.Combobox(row2, width=combo_width)
    e_hub.pack(side=tk.LEFT)
    hub_validation_lbl = tk.Label(lf_hub, text="", font=italic_font, fg="red", wraplength=520)
    hub_validation_lbl.pack(anchor=tk.W, padx=(33, 0), pady=(0, 2))
    def _validate_hub():
        val = e_hub.get().strip()
        if not val:
            hub_validation_lbl.config(text="")
            return
        if HUB_SLUG_PATTERN.match(val):
            hub_validation_lbl.config(text="")
        else:
            hub_validation_lbl.config(text=t("config.hub_invalid"))
    e_hub.bind("<KeyRelease>", lambda e: _validate_hub())
    e_hub.bind("<<ComboboxSelected>>", lambda e: _validate_hub())

    row2b = ttk.Frame(lf_hub)
    row2b.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(row2b, text=t("config.category_mode"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_mode = ttk.Frame(row2b)
    hint_mode.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_mode_hint = tk.Label(
        hint_mode,
        text=t("config.category_mode_desc"),
        font=italic_font,
        fg="gray",
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=450,
    )
    lbl_mode_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_mode_hint)
    e_category_mode = ttk.Combobox(
        row2b,
        values=(t("config.category_mode_production_only"), t("config.category_mode_preserve_sandbox")),
        width=combo_width,
        state="readonly",
    )
    e_category_mode.pack(side=tk.LEFT)

    # Use case'y
    lf_uc = ttk.LabelFrame(inner, text=t("config.section_use_cases"), padding=5)
    lf_uc.pack(fill=tk.X, pady=(0, 10))
    row_batch = ttk.Frame(lf_uc)
    row_batch.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(row_batch, text=t("config.batch_friendly") + " (" + t("config.batch_size") + ")", width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_batch = ttk.Frame(row_batch)
    hint_batch.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_batch_hint = tk.Label(hint_batch, text=t("config.batch_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_batch_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_batch_hint)
    e_batch = ttk.Spinbox(row_batch, from_=1, to=12, width=5, increment=1)
    e_batch.pack(side=tk.LEFT)

    row_pyr = ttk.Frame(lf_uc)
    row_pyr.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(row_pyr, text=t("config.pyramid_friendly"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_pyr = ttk.Frame(row_pyr)
    hint_pyr.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_pyr_hint = tk.Label(hint_pyr, text=t("config.pyramid_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_pyr_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_pyr_hint)

    pyr_frame = ttk.Frame(lf_uc)
    pyr_frame.pack(fill=tk.X, pady=(0, 6), padx=(0, 0))
    sp_beg = tk.IntVar(value=3)
    sp_int = tk.IntVar(value=3)
    sp_pro = tk.IntVar(value=3)
    lbl_sum = tk.StringVar(value="")

    def _pyr_update_sum(*_args):
        try:
            total = int(e_batch.get())
        except (ValueError, TypeError):
            total = 9
        b, i, p = sp_beg.get(), sp_int.get(), sp_pro.get()
        s = b + i + p
        lbl_sum.set(f"{t('config.pyr_sum')}: {s} / {total}")
        color = "green" if s == total else ("red" if s > total else "orange")
        sum_label.config(fg=color)

    def _pyr_clamp(var: tk.IntVar, *_args):
        try:
            total = int(e_batch.get())
        except (ValueError, TypeError):
            total = 9
        val = var.get()
        others = sum(v.get() for v in (sp_beg, sp_int, sp_pro) if v is not var)
        max_allowed = total - others
        if val > max_allowed:
            var.set(max(0, max_allowed))
        _pyr_update_sum()

    pad_lbl = 32
    row_beg = ttk.Frame(pyr_frame)
    row_beg.pack(fill=tk.X, pady=1)
    ttk.Label(row_beg, text="", width=pad_lbl).pack(side=tk.LEFT)
    ttk.Label(row_beg, text=t("config.pyr_beginner"), width=14, anchor=tk.W).pack(side=tk.LEFT)
    ttk.Spinbox(row_beg, from_=0, to=12, width=5, textvariable=sp_beg, command=lambda: _pyr_clamp(sp_beg)).pack(side=tk.LEFT)

    row_inter = ttk.Frame(pyr_frame)
    row_inter.pack(fill=tk.X, pady=1)
    ttk.Label(row_inter, text="", width=pad_lbl).pack(side=tk.LEFT)
    ttk.Label(row_inter, text=t("config.pyr_intermediate"), width=14, anchor=tk.W).pack(side=tk.LEFT)
    ttk.Spinbox(row_inter, from_=0, to=12, width=5, textvariable=sp_int, command=lambda: _pyr_clamp(sp_int)).pack(side=tk.LEFT)

    row_pro = ttk.Frame(pyr_frame)
    row_pro.pack(fill=tk.X, pady=1)
    ttk.Label(row_pro, text="", width=pad_lbl).pack(side=tk.LEFT)
    ttk.Label(row_pro, text=t("config.pyr_professional"), width=14, anchor=tk.W).pack(side=tk.LEFT)
    ttk.Spinbox(row_pro, from_=0, to=12, width=5, textvariable=sp_pro, command=lambda: _pyr_clamp(sp_pro)).pack(side=tk.LEFT)

    row_sum = ttk.Frame(pyr_frame)
    row_sum.pack(fill=tk.X, pady=(2, 0))
    ttk.Label(row_sum, text="", width=pad_lbl).pack(side=tk.LEFT)
    ttk.Label(row_sum, text="", width=14).pack(side=tk.LEFT)
    sum_label = tk.Label(row_sum, textvariable=lbl_sum, font=italic_font, anchor=tk.W)
    sum_label.pack(side=tk.LEFT)

    sp_beg.trace_add("write", lambda *a: _pyr_clamp(sp_beg))
    sp_int.trace_add("write", lambda *a: _pyr_clamp(sp_int))
    sp_pro.trace_add("write", lambda *a: _pyr_clamp(sp_pro))
    e_batch.config(command=lambda: _pyr_update_sum())

    # Sandbox / problemy
    lf_sand = ttk.LabelFrame(inner, text=t("config.section_sandbox"), padding=5)
    lf_sand.pack(fill=tk.X, pady=(0, 10))
    row3 = ttk.Frame(lf_sand)
    row3.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(row3, text=t("config.sandbox"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_sand = ttk.Frame(row3)
    hint_sand.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_sand_hint = tk.Label(hint_sand, text=t("config.sandbox_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_sand_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_sand_hint)
    fr_sandbox = ttk.Frame(row3)
    fr_sandbox.pack(side=tk.LEFT)
    lb_sandbox = tk.Listbox(fr_sandbox, height=3, width=combo_width)
    lb_sandbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
    sb_sand = ttk.Scrollbar(fr_sandbox, orient=tk.VERTICAL, command=lb_sandbox.yview)
    sb_sand.pack(side=tk.RIGHT, fill=tk.Y)
    lb_sandbox.config(yscrollcommand=sb_sand.set)
    row3b = ttk.Frame(lf_sand)
    row3b.pack(fill=tk.X, pady=2)
    e_sandbox_new = ttk.Entry(row3b, width=60)
    e_sandbox_new.pack(side=tk.LEFT, padx=(33, 5))
    ttk.Button(row3b, text=t("btn.add"), width=8, command=lambda: _list_add(lb_sandbox, e_sandbox_new)).pack(side=tk.LEFT, padx=2)
    ttk.Button(row3b, text=t("btn.remove"), width=14, command=lambda: _list_remove_selected(lb_sandbox)).pack(side=tk.LEFT, padx=2)
    row4 = ttk.Frame(lf_sand)
    row4.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(row4, text=t("config.suggested"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_sugg = ttk.Frame(row4)
    hint_sugg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_sugg_hint = tk.Label(hint_sugg, text=t("config.suggested_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_sugg_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_sugg_hint)
    fr_sugg = ttk.Frame(row4)
    fr_sugg.pack(side=tk.LEFT)
    lb_suggested = tk.Listbox(fr_sugg, height=3, width=combo_width)
    lb_suggested.pack(side=tk.LEFT, fill=tk.X, expand=True)
    row4b = ttk.Frame(lf_sand)
    row4b.pack(fill=tk.X, pady=2)
    e_suggested_new = ttk.Entry(row4b, width=60)
    e_suggested_new.pack(side=tk.LEFT, padx=(33, 5))
    ttk.Button(row4b, text=t("btn.add"), width=8, command=lambda: _list_add(lb_suggested, e_suggested_new)).pack(side=tk.LEFT, padx=2)
    ttk.Button(row4b, text=t("btn.remove"), width=14, command=lambda: _list_remove_selected(lb_suggested)).pack(side=tk.LEFT, padx=2)
    btn_row = ttk.Frame(inner)
    btn_row.pack(fill=tk.X, pady=(14, 0))
    ttk.Button(btn_row, text=t("btn.refresh_file"), command=load_ui).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.save"), command=save_ui).pack(side=tk.LEFT, padx=5)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    load_ui()
    return f


def _list_add(listbox: tk.Listbox, entry: ttk.Entry):
    val = entry.get().strip()
    if not val:
        return
    listbox.insert(tk.END, val)
    entry.delete(0, tk.END)


def _list_remove_selected(listbox: tk.Listbox):
    for i in reversed(listbox.curselection()):
        listbox.delete(i)


def _normalize_base_url(url: str) -> str:
    """Scheme + netloc + path (no query/fragment). Lowercase host; path without trailing slash."""
    try:
        p = urlparse((url or "").strip())
        if not p.scheme or not p.netloc:
            return ""
        scheme = p.scheme.lower()
        netloc = p.netloc.lower().replace("www.", "", 1) if p.netloc.lower().startswith("www.") else p.netloc.lower()
        path = (p.path or "/").rstrip("/") or "/"
        return urlunparse((scheme, netloc, path, "", "", ""))
    except Exception:
        return ""


# Sugerowane nazwy z hosta (wyjątki dla znanych marek)
_NAME_FROM_HOST = {
    "10web.io": "10Web.io",
    "cj.com": "CJ Affiliate",
    "shareasale.com": "ShareASale",
    "workspace.google.com": "Google Workspace",
    "jvzoo.com": "JVZoo",
    "warriorplus.com": "Warrior Plus",
}


def _name_from_affiliate_link(url: str) -> str:
    """Sugerowana nazwa na podstawie hosta (netloc)."""
    try:
        p = urlparse((url or "").strip())
        netloc = (p.netloc or "").lower().replace("www.", "", 1)
        if not netloc:
            return ""
        if netloc in _NAME_FROM_HOST:
            return _NAME_FROM_HOST[netloc]
        # np. make.com -> Make; app.example.com -> App Example
        parts = netloc.split(".")
        if len(parts) >= 2 and parts[-1] in ("com", "io", "co", "net", "org", "ai"):
            name = parts[-2]
        else:
            name = parts[0] if parts else netloc
        return name.strip().title() if name else netloc
    except Exception:
        return ""


def _affiliate_edit_dialog(parent, title: str, initial: dict | None = None) -> dict | None:
    """Formularz: Nazwa, Kategoria, Link, Opis (EN). Zwraca dict lub None przy Anuluj."""
    initial = initial or {}
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    f = ttk.Frame(win, padding=15)
    f.pack(fill=tk.BOTH, expand=True)
    categories = ("referral", "affiliate-network", "ai-chat", "website-builder", "hosting", "automation", "design", "video", "productivity", "writing", "transcription", "monitoring", "general")
    ttk.Label(f, text=t("links.dialog_name")).grid(row=0, column=0, sticky=tk.W, pady=2)
    e_name = ttk.Entry(f, width=45)
    e_name.grid(row=0, column=1, padx=5, pady=2)
    e_name.insert(0, initial.get("name", ""))
    ttk.Label(f, text=t("links.dialog_category")).grid(row=1, column=0, sticky=tk.W, pady=2)
    combo_cat = ttk.Combobox(f, values=categories, width=42, state="readonly")
    combo_cat.grid(row=1, column=1, padx=5, pady=2)
    cat = (initial.get("category") or "general").strip()
    if cat in categories:
        combo_cat.set(cat)
    else:
        combo_cat.current(0)
    ttk.Label(f, text=t("links.dialog_link")).grid(row=2, column=0, sticky=tk.W, pady=2)
    e_link = ttk.Entry(f, width=45)
    e_link.grid(row=2, column=1, padx=5, pady=2)
    e_link.insert(0, initial.get("affiliate_link", ""))
    ttk.Label(f, text=t("links.dialog_desc")).grid(row=3, column=0, sticky=tk.W, pady=2)
    e_desc = ttk.Entry(f, width=45)
    e_desc.grid(row=3, column=1, padx=5, pady=2)
    e_desc.insert(0, initial.get("short_description_en", ""))
    result = [None]

    def ok():
        result[0] = {
            "name": e_name.get().strip(),
            "category": (combo_cat.get() or "general").strip() or "general",
            "affiliate_link": e_link.get().strip(),
            "short_description_en": e_desc.get().strip(),
        }
        if not result[0]["name"]:
            messagebox.showwarning(t("msg.warning"), t("msg.name_required"), parent=win)
            return
        win.destroy()

    def cancel():
        win.destroy()

    btn_row = ttk.Frame(f)
    btn_row.grid(row=4, column=0, columnspan=2, pady=15)
    ttk.Button(btn_row, text="OK", command=ok).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text="Anuluj", command=cancel).pack(side=tk.LEFT, padx=5)
    win.wait_window()
    return result[0]


def _affiliate_link_only_dialog(parent) -> str | None:
    """Dialog z jednym polem Link. Zwraca URL (strip) lub None przy Anuluj."""
    win = tk.Toplevel(parent)
    win.title(t("links.dialog_link_only_title"))
    win.transient(parent)
    win.grab_set()
    f = ttk.Frame(win, padding=15)
    f.pack(fill=tk.BOTH, expand=True)
    ttk.Label(f, text=t("links.dialog_link")).grid(row=0, column=0, sticky=tk.W, pady=2)
    e_link = ttk.Entry(f, width=50)
    e_link.grid(row=0, column=1, padx=5, pady=2)
    result = [None]

    def ok():
        url = e_link.get().strip()
        if not url:
            win.destroy()
            return
        if not url.startswith("http://") and not url.startswith("https://"):
            messagebox.showwarning(t("msg.warning"), t("links.msg_invalid_url"), parent=win)
            return
        try:
            p = urlparse(url)
            if not p.netloc:
                messagebox.showwarning(t("msg.warning"), t("links.msg_invalid_url"), parent=win)
                return
        except Exception:
            messagebox.showwarning(t("msg.warning"), t("links.msg_invalid_url"), parent=win)
            return
        result[0] = url
        win.destroy()

    def cancel():
        win.destroy()

    btn_row = ttk.Frame(f)
    btn_row.grid(row=1, column=0, columnspan=2, pady=15)
    ttk.Button(btn_row, text="OK", command=ok).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.cancel"), command=cancel).pack(side=tk.LEFT, padx=5)
    win.wait_window()
    return result[0]


def _category_from_url(url: str) -> str:
    """Zwraca 'referral' jeśli w URL są parametry typu via= lub ref=, inaczej 'general'."""
    try:
        p = urlparse((url or "").strip())
        if not p.query:
            return "general"
        q = p.query.lower()
        if "via=" in q or "ref=" in q or "referrer=" in q:
            return "referral"
    except Exception:
        pass
    return "general"


def _run_add_by_link_flow(parent, tools_holder: list, refresh_tree):
    """Flow: dialog tylko link -> walidacja -> duplikat lub potwierdzenie -> zapis / edycja."""
    root = parent.winfo_toplevel()
    url = _affiliate_link_only_dialog(root)
    if not url:
        return
    suggested_name = _name_from_affiliate_link(url)
    category = _category_from_url(url)
    suggested = {
        "name": suggested_name,
        "category": category,
        "affiliate_link": url,
        "short_description_en": "",
    }
    base = _normalize_base_url(url)
    existing_idx = None
    for i, tool in enumerate(tools_holder):
        link = tool.get("affiliate_link") or ""
        if _normalize_base_url(link) == base:
            existing_idx = i
            break

    if existing_idx is not None:
        existing_name = (tools_holder[existing_idx].get("name") or "").strip() or "(bez nazwy)"
        win_dup = tk.Toplevel(root)
        win_dup.title(t("msg.warning"))
        win_dup.transient(root)
        win_dup.grab_set()
        f_dup = ttk.Frame(win_dup, padding=15)
        f_dup.pack(fill=tk.BOTH, expand=True)
        choice = [None]

        ttk.Label(f_dup, text=t("links.duplicate_message", existing_name), wraplength=400).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

        def on_add_suggested():
            choice[0] = "add"
            win_dup.destroy()

        def on_edit_name():
            choice[0] = "edit_name"
            win_dup.destroy()

        def on_open_existing():
            choice[0] = "open_existing"
            win_dup.destroy()

        def on_cancel_dup():
            choice[0] = "cancel"
            win_dup.destroy()

        btn_row_dup = ttk.Frame(f_dup)
        btn_row_dup.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(btn_row_dup, text=t("links.btn_add_suggested"), command=on_add_suggested).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row_dup, text=t("links.btn_edit_name"), command=on_edit_name).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row_dup, text=t("links.btn_open_existing"), command=on_open_existing).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row_dup, text=t("btn.cancel"), command=on_cancel_dup).pack(side=tk.LEFT, padx=3)
        win_dup.wait_window()

        if choice[0] == "cancel":
            return
        if choice[0] == "open_existing":
            data = _affiliate_edit_dialog(root, t("links.dialog_edit_title"), initial=tools_holder[existing_idx])
            if data:
                tools_holder[existing_idx] = data
                refresh_tree()
            return
        if choice[0] == "edit_name":
            data = _affiliate_edit_dialog(root, t("links.dialog_add_title"), initial=suggested)
            if data:
                data.setdefault("short_description_en", "")
                tools_holder.append(data)
                refresh_tree()
            return
        assert choice[0] == "add"

    win_conf = tk.Toplevel(root)
    win_conf.title(t("links.dialog_link_only_title"))
    win_conf.transient(root)
    win_conf.grab_set()
    f_conf = ttk.Frame(win_conf, padding=15)
    f_conf.pack(fill=tk.BOTH, expand=True)
    conf_choice = [None]

    ttk.Label(f_conf, text=t("links.confirm_suggested", suggested_name, category), wraplength=400).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

    def on_save():
        conf_choice[0] = "save"
        win_conf.destroy()

    def on_edit_fields():
        conf_choice[0] = "edit"
        win_conf.destroy()

    def on_cancel_conf():
        conf_choice[0] = "cancel"
        win_conf.destroy()

    btn_row_conf = ttk.Frame(f_conf)
    btn_row_conf.grid(row=1, column=0, columnspan=2, pady=5)
    ttk.Button(btn_row_conf, text=t("btn.save"), command=on_save).pack(side=tk.LEFT, padx=3)
    ttk.Button(btn_row_conf, text=t("links.btn_edit_fields"), command=on_edit_fields).pack(side=tk.LEFT, padx=3)
    ttk.Button(btn_row_conf, text=t("btn.cancel"), command=on_cancel_conf).pack(side=tk.LEFT, padx=3)
    win_conf.wait_window()

    if conf_choice[0] == "cancel":
        return
    if conf_choice[0] == "save":
        suggested.setdefault("short_description_en", "")
        tools_holder.append(suggested)
        refresh_tree()
        return
    if conf_choice[0] == "edit":
        data = _affiliate_edit_dialog(root, t("links.dialog_add_title"), initial=suggested)
        if data:
            data.setdefault("short_description_en", "")
            tools_holder.append(data)
            refresh_tree()


def _link_type_display(tool: dict) -> str:
    """Zwraca 'referral' lub 'ogólny' do wyświetlenia w kolumnie Typ linku."""
    cat = (tool.get("category") or "").strip().lower()
    return t("links.link_type_referral") if cat == "referral" else t("links.link_type_general")


def build_affiliate_tab(parent):
    """Zakładka Linki: przegląd (z kolumną Typ linku), dodawanie, edycja, usuwanie, zapis; sekcja Odśwież linki."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    tools_holder = []
    ttk.Label(f, text="Narzędzia z linkami (content/affiliate_tools.yaml)").pack(anchor=tk.W)
    tree = ttk.Treeview(f, columns=("name", "category", "link_type", "link", "desc"), show="headings", height=16)
    tree.heading("name", text="Nazwa")
    tree.heading("category", text="Kategoria")
    tree.heading("link_type", text=t("links.link_type"))
    tree.heading("link", text="Link")
    tree.heading("desc", text="Opis (EN)")
    tree.column("name", width=120)
    tree.column("category", width=110)
    tree.column("link_type", width=70)
    tree.column("link", width=200)
    tree.column("desc", width=180)
    tree.pack(fill=tk.BOTH, expand=True, pady=5)

    def refresh_tree():
        for i in tree.get_children():
            tree.delete(i)
        for tool in tools_holder:
            link = (tool.get("affiliate_link") or "")[:50] + ("…" if len(tool.get("affiliate_link") or "") > 50 else "")
            desc = (tool.get("short_description_en") or "")[:35] + ("…" if len(tool.get("short_description_en") or "") > 35 else "")
            link_type = _link_type_display(tool)
            tree.insert("", tk.END, values=(tool.get("name", ""), tool.get("category", ""), link_type, link, desc))

    def load_from_file():
        tools_holder.clear()
        tools_holder.extend(load_affiliate_tools())
        for tool in tools_holder:
            tool.setdefault("short_description_en", "")
        refresh_tree()

    def add_tool():
        _run_add_by_link_flow(parent, tools_holder, refresh_tree)

    def edit_tool():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo(t("msg.info"), t("msg.select_row_edit"), parent=parent.winfo_toplevel())
            return
        idx = tree.index(sel[0])
        if idx < 0 or idx >= len(tools_holder):
            return
        data = _affiliate_edit_dialog(parent.winfo_toplevel(), t("links.dialog_edit_title"), initial=tools_holder[idx])
        if data:
            tools_holder[idx] = data
            refresh_tree()

    def remove_tool():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo(t("msg.info"), t("msg.select_row_delete"), parent=parent.winfo_toplevel())
            return
        idx = tree.index(sel[0])
        if idx < 0 or idx >= len(tools_holder):
            return
        if messagebox.askyesno(t("msg.delete_title"), t("msg.delete_confirm", tools_holder[idx].get("name", ""))):
            tools_holder.pop(idx)
            refresh_tree()

    def save_to_file():
        try:
            save_affiliate_tools(tools_holder)
            messagebox.showinfo(t("msg.saved"), t("msg.affiliate_saved"), parent=parent.winfo_toplevel())
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e), parent=parent.winfo_toplevel())

    btn_row = ttk.Frame(f)
    btn_row.pack(fill=tk.X, pady=5)
    ttk.Button(btn_row, text=t("btn.refresh_file"), command=load_from_file).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.add"), command=add_tool).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("links.dialog_edit_title"), command=edit_tool).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.remove"), command=remove_tool).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.save"), command=save_to_file).pack(side=tk.LEFT, padx=5)
    load_from_file()

    # Sekcja: Odśwież linki we wszystkich artykułach
    italic_font_links = ("TkDefaultFont", 9, "italic")
    sep = ttk.Separator(f, orient=tk.HORIZONTAL)
    sep.pack(fill=tk.X, pady=(15, 10))
    lf_refresh = ttk.LabelFrame(f, text=t("links.refresh_section"))
    lf_refresh.pack(fill=tk.X, pady=(0, 5))
    inner_refresh = ttk.Frame(lf_refresh, padding=8)
    inner_refresh.pack(fill=tk.X)
    tk.Label(inner_refresh, text=t("links.refresh_section_desc"), font=italic_font_links, fg="gray").pack(anchor=tk.W)
    tk.Label(inner_refresh, text=t("wf.refresh_links_desc"), font=italic_font_links, fg="gray", wraplength=600, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 8))
    refresh_result_var = tk.StringVar(value="")
    refresh_result_lbl = tk.Label(inner_refresh, textvariable=refresh_result_var, fg="gray")
    refresh_result_lbl.pack(anchor=tk.W, pady=(0, 5))

    def run_refresh_links():
        refresh_result_var.set("")
        out, code = run_workflow_script("update_affiliate_links", extra_args=["--write"])
        if code != 0:
            first_line = (out or "").strip().split("\n")[0] or out or str(code)
            refresh_result_var.set(t("links.refresh_result_error", first_line))
            refresh_result_lbl.config(fg="red")
            return
        import re
        m = re.search(r"Files with link updates:\s*(\d+)", out or "")
        if m:
            refresh_result_var.set(t("links.refresh_result", m.group(1)))
        elif "No links to update" in (out or ""):
            refresh_result_var.set(t("links.refresh_result_none"))
        else:
            refresh_result_var.set(out.strip()[:200] if out else "")
        refresh_result_lbl.config(fg="green")

    ttk.Button(inner_refresh, text=t("wf.refresh_links"), command=run_refresh_links).pack(anchor=tk.W)
    return f


def build_mapping_tab(parent):
    """Zakładka Narzędzia w artykułach – odczyt pola tools z frontmatter artykułów."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    ttk.Label(f, text=t("mapping.title")).pack(anchor=tk.W)
    tree = ttk.Treeview(f, columns=("slug", "tools"), show="headings", height=20)
    tree.heading("slug", text=t("mapping.col_slug"))
    tree.heading("tools", text=t("mapping.col_tools"))
    tree.column("slug", width=380)
    tree.column("tools", width=320)
    tree.pack(fill=tk.BOTH, expand=True, pady=5)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        for slug, tools_str in get_article_tools_data():
            tree.insert("", tk.END, values=(slug, tools_str))

    ttk.Button(f, text=t("btn.refresh"), command=refresh).pack(anchor=tk.W, pady=5)
    refresh()
    return f


def main():
    if getattr(sys, "frozen", False):
        for name in ("python", "py", "python3"):
            try:
                subprocess.run([name, "--version"], capture_output=True, timeout=5, check=False)
                break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        else:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(t("msg.no_python_title"), t("msg.no_python"))
            root.destroy()
            return

    root = tk.Tk()
    root.title("Flowtaro Monitor")
    root.minsize(700, 500)
    root.geometry("900x600")

    prefs_dir = Path.home() / ".flowtaro_monitor"
    geometry_file = prefs_dir / "window_geometry.txt"
    if geometry_file.exists():
        try:
            geom = geometry_file.read_text(encoding="utf-8").strip()
            if geom:
                root.geometry(geom)
        except Exception:
            pass

    def on_closing():
        try:
            prefs_dir.mkdir(parents=True, exist_ok=True)
            geometry_file.write_text(root.geometry(), encoding="utf-8")
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    icon_path = Path(__file__).resolve().parent / "FlowtaroMonitor.ico"
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass

    menubar = tk.Menu(root)
    root.config(menu=menubar)
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label=t("menu.file"), menu=file_menu)
    view_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label=t("menu.view"), menu=view_menu)
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label=t("menu.help"), menu=help_menu)

    nb = ttk.Notebook(root)
    nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    last_output_holder = []

    def choose_folder():
        path = filedialog.askdirectory(title=t("menu.choose_folder"))
        if path:
            p = Path(path)
            if (p / "content").is_dir() and (p / "scripts").is_dir():
                set_project_root(p)
                messagebox.showinfo(t("msg.info"), t("msg.choose_folder_ok"))
            else:
                messagebox.showerror(t("msg.error"), t("msg.choose_folder_err"))

    def menu_save_log():
        if not last_output_holder:
            messagebox.showinfo(t("msg.info"), t("wf.save_log_no"))
            return
        out, action = last_output_holder[0]
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log", "*.log"), ("Wszystkie", "*.*")],
            initialfile=f"flowtaro_{action}.log",
        )
        if path:
            try:
                Path(path).write_text(out, encoding="utf-8")
                messagebox.showinfo(t("msg.saved"), f"{t('msg.saved')}: {path}")
            except Exception as e:
                messagebox.showerror(t("msg.error"), str(e))

    def build_all_tabs():
        for tid in list(nb.tabs()):
            w = nb.nametowidget(tid)
            nb.forget(tid)
            w.destroy()
        tab_config = build_config_tab(nb)
        nb.add(tab_config, text=t("tab.config"))
        tab_work = build_workflow_tab(nb, last_output_holder)
        nb.add(tab_work, text=t("tab.workflow"))
        tab_refresh = build_refresh_tab(nb, last_output_holder)
        nb.add(tab_refresh, text=t("tab.refresh"))
        tab_git = build_git_tab(nb)
        nb.add(tab_git, text=t("tab.git"))
        tab_mapping = build_mapping_tab(nb)
        nb.add(tab_mapping, text=t("tab.mapping"))
        tab_affiliate = build_affiliate_tab(nb)
        nb.add(tab_affiliate, text=t("tab.affiliate"))
        tab_dash, dash_refresh = build_dashboard_tab(nb)
        nb.add(tab_dash, text=t("tab.stats"))
        return dash_refresh

    def refresh_menus(dash_refresh):
        file_menu.delete(0, tk.END)
        file_menu.add_command(label=t("menu.choose_folder"), command=choose_folder)
        file_menu.add_separator()
        file_menu.add_command(label=t("menu.save_log"), command=menu_save_log)
        file_menu.add_command(label=t("menu.close"), command=on_closing)
        view_menu.delete(0, tk.END)
        view_menu.add_command(label=t("menu.refresh_stats"), command=dash_refresh)
        view_menu.add_command(label=t("lang.switch"), command=on_lang_switch)
        help_menu.delete(0, tk.END)
        help_menu.add_command(label=t("menu.about"), command=lambda: messagebox.showinfo(t("about.title"), t("about.text")))

    def on_lang_switch():
        set_lang("en" if LANG == "pl" else "pl")
        dash_refresh = build_all_tabs()
        refresh_menus(dash_refresh)

    dash_refresh = build_all_tabs()
    refresh_menus(dash_refresh)

    root.mainloop()


if __name__ == "__main__":
    main()
