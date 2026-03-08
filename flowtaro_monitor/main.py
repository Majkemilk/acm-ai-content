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
import webbrowser
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from urllib.parse import urlparse, urlunparse

from flowtaro_monitor._config import (
    CONFIG_PATH,
    LOGS_DIR,
    SCRIPTS_DIR,
    get_content_dir,
    get_content_root,
    get_content_root_resolved,
    get_project_root,
    set_content_root,
    set_project_root,
    validate_content_root_pl,
)
from flowtaro_monitor.i18n import LANG, t, set_lang

PREFS_DIR = Path.home() / ".flowtaro_monitor"
LAST_PARAMS_FILE = PREFS_DIR / "last_workflow_params.json"
HUB_SLUG_PATTERN = re.compile(r"^[a-z0-9-]*$")

# Wszystkie typy treści obsługiwane przez generator i fill_articles (fallback gdy brak configu)
CONTENT_TYPES_ALL = (
    "how-to",
    "guide",
    "best",
    "comparison",
    "review",
    "sales",
    "product-comparison",
    "best-in-category",
    "category-products",
)


def get_content_types_all() -> tuple[str, ...]:
    """Lista wszystkich typów (ALL) z content/config.yaml content_types_all; przy braku configu zwraca CONTENT_TYPES_ALL."""
    try:
        from flowtaro_monitor._config import CONFIG_PATH
        from content_index import load_config
        cfg = load_config(CONFIG_PATH)
        ct = cfg.get("content_types_all")
        if isinstance(ct, list) and ct:
            return tuple(str(x).strip() for x in ct if str(x).strip())
    except Exception:
        pass
    return CONTENT_TYPES_ALL
# Dla workflow: (etykieta i18n lub wartość, wartość do --content-type). Pierwszy element = "wszystkie".
CONTENT_TYPE_CHOICES_WORKFLOW = [
    ("wf.content_all", None),
    ("how-to", "how-to"),
    ("guide", "guide"),
    ("best", "best"),
    ("comparison", "comparison"),
    ("wf.content_type_review", "review"),
    ("wf.content_type_sales", "sales"),
    ("wf.content_type_product_comparison", "product-comparison"),
    ("wf.content_type_best_in_category", "best-in-category"),
    ("wf.content_type_category_products", "category-products"),
]


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


def _show_article_selector(parent, title: str, items: list[tuple[str, str] | tuple[str, str, str]],
                           confirm_label: str, on_confirm,
                           description_text: str | None = None,
                           delete_label: str | None = None,
                           on_delete_selected=None,
                           open_public_label: str | None = None,
                           remove_unselected_var: tk.BooleanVar | None = None):
    """Popup dialog with checkboxes for article selection.

    items: [(display_text, stem_value)] or [(display_text, stem_value, status_key)] where status_key is 'failed', 'blocked', 'in_scope' or ''.
    on_confirm: callable receiving list of selected stem_values; if remove_unselected_var is set, called as on_confirm(selected, remove_unselected_var.get()).
    description_text: optional hint shown above the list.
    delete_label, on_delete_selected: when set, show "Usuń zaznaczone" button; on_delete_selected(selected_stems) is called and dialog closes.
    open_public_label: when set, show "Podgląd" button; opens selected article from public/ in browser (exactly one selected).
    remove_unselected_var: when set, show checkbox "Usuń niezaznaczone i przywróć do puli" (default off); on confirm, call on_confirm(selected, var.get()).
    """
    if not items:
        messagebox.showinfo(t("msg.info"), t("sel.none"))
        return

    # Normalize to (display, stem, status_key)
    normalized: list[tuple[str, str, str]] = []
    for it in items:
        if len(it) == 3:
            normalized.append((it[0], it[1], it[2]))
        else:
            normalized.append((it[0], it[1], ""))

    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry("780x420")
    dialog.transient(parent)
    dialog.grab_set()

    if description_text:
        desc_frame = ttk.Frame(dialog, padding=(10, 10, 10, 0))
        desc_frame.pack(fill=tk.X)
        tk.Label(desc_frame, text=description_text, wraplength=720, justify=tk.LEFT, fg="gray").pack(anchor=tk.W)

    vars_map: dict[str, tk.BooleanVar] = {}
    stem_to_status: dict[str, str] = {stem: sk for _d, stem, sk in normalized}
    all_var = tk.BooleanVar(value=True)

    def toggle_all():
        val = all_var.get()
        for v in vars_map.values():
            v.set(val)

    def select_failed_only():
        for stem, var in vars_map.items():
            var.set(stem_to_status.get(stem) == "failed")

    def deselect_failed():
        for stem, var in vars_map.items():
            if stem_to_status.get(stem) == "failed":
                var.set(False)

    top_row = ttk.Frame(dialog, padding=5)
    top_row.pack(fill=tk.X)
    ttk.Checkbutton(top_row, text=t("sel.select_all"), variable=all_var,
                    command=toggle_all).pack(side=tk.LEFT)
    has_failed = any(sk == "failed" for _d, _s, sk in normalized)
    if has_failed:
        ttk.Button(top_row, text=t("sel.select_failed_only"), command=select_failed_only).pack(side=tk.LEFT, padx=8)
        ttk.Button(top_row, text=t("sel.deselect_failed"), command=deselect_failed).pack(side=tk.LEFT)

    canvas = tk.Canvas(dialog, highlightthickness=0)
    sb = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
    sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    _status_labels = {"failed": "refresh.status_failed", "blocked": "refresh.status_blocked", "in_scope": "refresh.status_in_scope"}
    for display, stem, status_key in normalized:
        var = tk.BooleanVar(value=True)
        vars_map[stem] = var
        label = display
        if status_key and status_key in _status_labels:
            label = f"{display}  [{t(_status_labels[status_key])}]"
        ttk.Checkbutton(inner, text=label, variable=var).pack(anchor=tk.W, padx=5, pady=1)

    if remove_unselected_var is not None:
        opt_frame = ttk.Frame(dialog, padding=(10, 6, 10, 0))
        opt_frame.pack(fill=tk.X)
        ttk.Checkbutton(opt_frame, text=t("sel.remove_unselected_checkbox"), variable=remove_unselected_var).pack(anchor=tk.W)
        tk.Label(opt_frame, text=t("sel.remove_unselected_hint"), wraplength=720, justify=tk.LEFT, fg="gray", font=("TkDefaultFont", 9)).pack(anchor=tk.W, padx=(20, 0), pady=(2, 0))

    btn_row = ttk.Frame(dialog, padding=10)
    btn_row.pack(fill=tk.X)

    def confirm():
        selected = [stem for stem, var in vars_map.items() if var.get()]
        dialog.destroy()
        if not selected:
            messagebox.showinfo(t("msg.info"), t("sel.none"))
            return
        if remove_unselected_var is not None:
            on_confirm(selected, remove_unselected_var.get())
        else:
            on_confirm(selected)

    def do_delete():
        selected = [stem for stem, var in vars_map.items() if var.get()]
        dialog.destroy()
        if delete_label and on_delete_selected is not None:
            on_delete_selected(selected)

    def open_preview():
        selected = [stem for stem, var in vars_map.items() if var.get()]
        if len(selected) != 1:
            messagebox.showinfo(t("msg.info"), t("report.select_one_article"))
            return
        path = get_public_article_html_path(selected[0])
        if path.exists():
            webbrowser.open(path.as_uri())
        else:
            messagebox.showinfo(t("msg.info"), t("report.open_article_public_no_file"))

    ttk.Button(btn_row, text=confirm_label, command=confirm).pack(side=tk.LEFT, padx=5)
    if delete_label and on_delete_selected is not None:
        ttk.Button(btn_row, text=delete_label, width=18, command=do_delete).pack(side=tk.LEFT, padx=5)
    if open_public_label:
        ttk.Button(btn_row, text=open_public_label, command=open_preview).pack(side=tk.LEFT, padx=5)
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
from flowtaro_monitor._affiliate_descriptions import generate_short_description, translate_pl_to_en
from flowtaro_monitor._affiliate_url_utils import category_from_url as _category_from_url_impl
from flowtaro_monitor._monitor_data import (
    build_articles_report_html,
    get_article_report_data,
    get_public_article_html_path,
    get_article_tools_data,
    get_cost_chart_data,
    get_dashboard_data,
    get_use_case_defaults,
    load_affiliate_tools,
    reset_cost_data,
    save_affiliate_tools,
    validate_project_root,
)
from flowtaro_monitor._run_scripts import SCRIPT_MAP, run_script, run_workflow_script, run_workflow_streaming
from flowtaro_monitor.i18n import t
from flowtaro_monitor.run_tools_io import load_affiliate_catalog, load_run_tools as load_run_tools_io, save_run_tools as save_run_tools_io

# Queue/use_cases for preview dialog (revert todo, delete selected)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from generate_queue import (
        load_existing_queue,
        save_queue,
        load_use_cases,
        _save_use_cases,
        title_for_entry,
    )
    from generate_articles import slug_from_keyword
    _queue_use_cases_available = True
except Exception:
    _queue_use_cases_available = False
    load_existing_queue = save_queue = load_use_cases = _save_use_cases = title_for_entry = None
    slug_from_keyword = None


def _stem_to_queue_rest(stem: str) -> str:
    """Part of stem after date prefix (YYYY-MM-DD-) for matching to queue."""
    parts = stem.split("-", 3)
    return parts[-1] if len(parts) == 4 else stem


def _queue_item_expected_rest(item: dict) -> str:
    """Expected rest (slug or slug.audience_XXX) for this queue item."""
    if not slug_from_keyword:
        return ""
    slug = slug_from_keyword(item.get("primary_keyword") or "")
    aud = (item.get("audience_type") or "").strip()
    return f"{slug}.audience_{aud}" if aud else slug


def _find_queue_index_by_stem(queue_items: list, stem: str) -> int | None:
    rest = _stem_to_queue_rest(stem)
    for i, item in enumerate(queue_items):
        if _queue_item_expected_rest(item) == rest:
            return i
    return None


def _find_use_case_index_by_queue_entry(use_cases: list, queue_item: dict) -> int | None:
    if not title_for_entry:
        return None
    title = (queue_item.get("title") or "").strip()
    cat = (queue_item.get("category_slug") or "").strip()
    for i, uc in enumerate(use_cases):
        ct = (uc.get("content_type") or "").strip()
        uc_title = title_for_entry(uc.get("problem") or "", ct)
        uc_cat = (uc.get("category_slug") or "").strip()
        if uc_title == title and uc_cat == cat:
            return i
    return None

# Klucze i18n dla etykiet etapów (t() w UI)
WORKFLOW_LABEL_KEYS = {
    "generate_use_cases": "wf.gen_use_cases",
    "generate_queue": "wf.gen_queue",
    "pick_run_links": "wf.pick_run_links",
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


# generate_use_cases jest budowany dynamicznie w refresh_params_panel (kategoria z listy, typ treści multichoice; batch size tylko z configu)
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
    "render_site": [
        _p_choice("wf.render_site.site", "wf.render_site.site_desc", [
            ("wf.render_site.site_main", []),
            ("wf.render_site.site_pl", ["--site", "pl"]),
        ]),
    ],
}


def _build_param_widgets_for_action(container: ttk.Frame, action: str, italic_font: tuple, hint_labels: list | None = None, combo_width: int | None = None) -> list:
    """Buduje w container pełny zestaw widgetów parametrów dla danej akcji. combo_width – stała szerokość pól select (jak przy Kategoria); gdy None, liczone z opcji."""
    hint_labels = hint_labels if hint_labels is not None else []
    schema = WORKFLOW_PARAM_SCHEMA.get(action)
    if schema is None and action == "generate_use_cases":
        defaults = get_use_case_defaults()
        schema = [
            _p_choice("wf.category", "wf.category_desc", [("wf.category_any", [])] + [(c, ["--category", c]) for c in defaults["categories"]]),
            {"label": "wf.content_type", "type": "content_type_checkboxes", "description": "wf.content_type_desc", "flag": "--content-type", "choices": CONTENT_TYPE_CHOICES_WORKFLOW},
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
        lbl = ttk.Label(row, text=label_text, width=28, anchor=tk.W)
        lbl.pack(side=tk.LEFT, padx=(0, 5))
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


def _show_run_tools_dialog(parent, content_dir: Path):
    """Dialog edycji content/run_tools.yaml: trzy grupy (Affiliate, Other, Inne), checkbox 'Te linki są głównym tematem' (domyślnie wyłączony), Kontynuuj zapisuje i zamyka."""
    from flowtaro_monitor.i18n import t
    data = load_run_tools_io(content_dir)
    if data is None:
        data = {"affiliate": [], "other": [], "inne": [], "article_built_around_links": False}
    catalog = load_affiliate_catalog(content_dir)
    catalog_names = [it["name"] for it in catalog if (it.get("name") or "").strip()]

    dlg = tk.Toplevel(parent)
    dlg.title(t("run_links.dialog_title"))
    dlg.transient(parent)
    dlg.grab_set()
    main_f = ttk.Frame(dlg, padding=10)
    main_f.pack(fill=tk.BOTH, expand=True)

    def _list_display(items: list) -> list:
        return [f"{it.get('name', '')} | {it.get('url', '')}" for it in items]

    def _sync_listbox(lb: tk.Listbox, items: list):
        lb.delete(0, tk.END)
        for row in _list_display(items):
            lb.insert(tk.END, row)

    # Affiliate
    lf_aff = ttk.LabelFrame(main_f, text=t("run_links.group_affiliate"))
    lf_aff.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
    row_aff = ttk.Frame(lf_aff)
    row_aff.pack(fill=tk.X)
    lb_aff = tk.Listbox(row_aff, height=4, selectmode=tk.EXTENDED, width=70)
    lb_aff.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    fr_aff_btn = ttk.Frame(row_aff)
    fr_aff_btn.pack(side=tk.LEFT)
    ttk.Button(fr_aff_btn, text=t("btn.remove"), command=lambda: _remove_selected(data["affiliate"], lb_aff)).pack(fill=tk.X, pady=2)
    combo_aff = ttk.Combobox(fr_aff_btn, values=catalog_names, state="readonly", width=20)
    combo_aff.pack(fill=tk.X, pady=2)
    ttk.Button(fr_aff_btn, text=t("btn.add"), command=lambda: _add_from_catalog(data["affiliate"], combo_aff, catalog, lb_aff)).pack(fill=tk.X, pady=2)

    # Other
    lf_oth = ttk.LabelFrame(main_f, text=t("run_links.group_other"))
    lf_oth.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
    row_oth = ttk.Frame(lf_oth)
    row_oth.pack(fill=tk.X)
    lb_oth = tk.Listbox(row_oth, height=4, selectmode=tk.EXTENDED, width=70)
    lb_oth.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    fr_oth_btn = ttk.Frame(row_oth)
    fr_oth_btn.pack(side=tk.LEFT)
    ttk.Button(fr_oth_btn, text=t("btn.remove"), command=lambda: _remove_selected(data["other"], lb_oth)).pack(fill=tk.X, pady=2)
    combo_oth = ttk.Combobox(fr_oth_btn, values=catalog_names, state="readonly", width=20)
    combo_oth.pack(fill=tk.X, pady=2)
    ttk.Button(fr_oth_btn, text=t("btn.add"), command=lambda: _add_from_catalog(data["other"], combo_oth, catalog, lb_oth)).pack(fill=tk.X, pady=2)

    # Inne
    lf_inne = ttk.LabelFrame(main_f, text=t("run_links.group_inne"))
    lf_inne.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
    row_inne = ttk.Frame(lf_inne)
    row_inne.pack(fill=tk.X)
    lb_inne = tk.Listbox(row_inne, height=3, selectmode=tk.EXTENDED, width=70)
    lb_inne.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    fr_inne_btn = ttk.Frame(row_inne)
    fr_inne_btn.pack(side=tk.LEFT)
    ttk.Button(fr_inne_btn, text=t("btn.remove"), command=lambda: _remove_selected(data["inne"], lb_inne)).pack(fill=tk.X, pady=2)
    ttk.Button(fr_inne_btn, text=t("btn.add"), command=lambda: _add_inne(data["inne"], lb_inne)).pack(fill=tk.X, pady=2)

    def _remove_selected(items: list, lb: tk.Listbox):
        sel = list(lb.curselection())
        for i in reversed(sel):
            if 0 <= i < len(items):
                items.pop(i)
        _sync_listbox(lb, items)

    def _add_from_catalog(items: list, combo: ttk.Combobox, cat: list, lb: tk.Listbox):
        name = (combo.get() or "").strip()
        if not name:
            return
        for it in cat:
            if (it.get("name") or "").strip() == name:
                if not any((x.get("name") or "").strip() == name for x in items):
                    items.append({"name": it.get("name", ""), "url": it.get("url", "")})
                break
        _sync_listbox(lb, items)

    def _add_inne(items: list, lb: tk.Listbox):
        sub = tk.Toplevel(dlg)
        sub.title(t("links.dialog_add_title"))
        sub.transient(dlg)
        fsub = ttk.Frame(sub, padding=10)
        fsub.pack(fill=tk.BOTH, expand=True)
        ttk.Label(fsub, text=t("links.dialog_name")).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        e_name = ttk.Entry(fsub, width=35)
        e_name.grid(row=0, column=1, pady=2)
        ttk.Label(fsub, text=t("links.dialog_link")).grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        e_url = ttk.Entry(fsub, width=35)
        e_url.grid(row=1, column=1, pady=2)
        def ok():
            na, ur = e_name.get().strip(), e_url.get().strip()
            if na or ur:
                items.append({"name": na, "url": ur})
                _sync_listbox(lb, items)
            sub.destroy()
        ttk.Button(fsub, text=t("btn.ok"), command=ok).grid(row=2, column=1, pady=5)
        sub.wait_window()

    _sync_listbox(lb_aff, data["affiliate"])
    _sync_listbox(lb_oth, data["other"])
    _sync_listbox(lb_inne, data["inne"])

    var_built_around = tk.BooleanVar(value=bool(data.get("article_built_around_links", False)))
    ttk.Checkbutton(main_f, text=t("run_links.checkbox_built_around"), variable=var_built_around).pack(anchor=tk.W, pady=5)

    def on_continue():
        data["article_built_around_links"] = var_built_around.get()
        save_run_tools_io(content_dir, data)
        dlg.destroy()

    row_btn = ttk.Frame(main_f)
    row_btn.pack(fill=tk.X, pady=10)
    btn_cont = ttk.Button(row_btn, text=t("run_links.continue"), command=on_continue)
    btn_cont.pack(side=tk.LEFT, padx=(0, 5))
    _create_tooltip(btn_cont, t("run_links.tooltip_continue"))
    ttk.Button(row_btn, text=t("btn.cancel"), command=dlg.destroy).pack(side=tk.LEFT)
    dlg.wait_window()


def build_workflow_tab(parent, last_output_holder: list):
    """Zakładka Generuj artykuły: przyciski Uzupełnij kolejkę, Dobierz linki, Generuj szkielety i wypełnij; parametry i log."""
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
            section_title = t("wf.section_params") if i == 0 else t(WORKFLOW_LABEL_KEYS.get(action, action))
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
        elif i == 6:
            # render_site: wybór site (main / pl)
            section_title = t(WORKFLOW_LABEL_KEYS.get(action, action))
            lf = ttk.LabelFrame(inner, text=section_title)
            lf.pack(fill=tk.X, pady=(0, 10))
            section_inner = ttk.Frame(lf, padding=5)
            section_inner.pack(fill=tk.X)
            widgets = _build_param_widgets_for_action(section_inner, action, italic_font, workflow_hint_labels, combo_width)
            section_widgets.append(widgets)
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
    progress_label = ttk.Label(right_frame, text="", foreground="gray")
    progress_label.pack(anchor=tk.W, pady=(0, 2))
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
    run_buttons_list = []
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

    def poll_sequence(remaining, accumulated, current_out_lines, q, rbtn, cbtn, fill_total=0, fill_done=None, on_success_callback=None):
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
                    for b in run_buttons_list:
                        try:
                            b.config(state=tk.NORMAL)
                        except Exception:
                            pass
                    cbtn.config(state=tk.DISABLED)
                    completed = len(SEQUENCE_ACTIONS) - len(remaining)
                    progress_bar["value"] = len(SEQUENCE_ACTIONS) if not remaining else completed
                    if not remaining:
                        step_label.config(text=t("wf.step_done"))
                        progress_label.config(text="")
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
                    if on_success_callback and code == 0 and not sequence_cancelled[0] and not remaining:
                        try:
                            on_success_callback()
                        except Exception:
                            pass
                    if preview_mode[0] and code == 0 and not sequence_cancelled[0]:
                        preview_mode[0] = False
                        items = _parse_generated_articles(full_text)
                        if items:
                            step_label.config(text=t("wf.preview_done"))
                            status_label.config(text=t("wf.preview_done"), foreground="blue")
                            root.after(100, lambda: _show_article_selector(
                                root, t("sel.title_fill"), items,
                                t("sel.confirm_fill"),
                                lambda selected, remove_unselected=False: _fill_selected(selected, items, full_text, remove_unselected),
                                description_text=t("sel.preview_fill_desc"),
                                delete_label=t("sel.delete_selected"),
                                on_delete_selected=lambda selected: _delete_selected(selected),
                                remove_unselected_var=tk.BooleanVar(value=False)))
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
                    progress_label.config(text=t("wf.progress_of", 0, next_fill_total))
                else:
                    step_label.config(text=t("wf.step_progress", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(next_action, next_action))))
                    progress_label.config(text="")
                next_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(next_action, next_action)) + " ---", ""]
                for h in next_header:
                    root.after(0, lambda line=h: append_log(line))
                proc, new_q = run_workflow_streaming(next_action, next_extra)
                process_holder[0] = (next_action, proc)
                next_accumulated = new_accumulated + next_header
                root.after(50, lambda: poll_sequence(remaining, next_accumulated, [], new_q, rbtn, cbtn, next_fill_total, next_fill_done, on_success_callback))
                return
            line = item[0]
            if line is not None:
                current_action = process_holder[0][0] if process_holder else None
                if current_action == "fill_articles" and fill_total > 0 and "  Filled:" in line:
                    fill_done[0] += 1
                    completed = len(SEQUENCE_ACTIONS) - len(remaining) - 1
                    step_label.config(text=t("wf.step_progress_fill", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get("fill_articles", "fill_articles")), fill_done[0], fill_total))
                    progress_label.config(text=t("wf.progress_of", fill_done[0], fill_total))
                    progress_bar["value"] = completed + (fill_done[0] / fill_total)
                current_out_lines.append(line)
                root.after(0, lambda l=line: append_log(l))
        except queue.Empty:
            pass
        root.after(50, lambda: poll_sequence(remaining, accumulated, current_out_lines, q, rbtn, cbtn, fill_total, fill_done, on_success_callback))

    def _parse_fill_limit(extra: list) -> int:
        """Parse --limit from fill_articles extra args. 0 = no limit."""
        for i, x in enumerate(extra):
            if x == "--limit" and i + 1 < len(extra):
                try:
                    return int(extra[i + 1])
                except ValueError:
                    pass
        return 0

    def _start_run(steps: list, on_success=None):
        preview_mode[0] = False
        sequence_cancelled[0] = False
        for b in run_buttons_list:
            b.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("wf.running"), foreground="gray")
        progress_bar["value"] = 0
        progress_label.config(text="")
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("wf.running") + "\n")
        log_area.config(state=tk.DISABLED)
        process_holder.clear()
        first_action, first_extra = steps.pop(0)
        first_fill_total = _parse_fill_limit(first_extra) if first_action == "fill_articles" else 0
        first_fill_done = [0]
        if first_fill_total > 0:
            step_label.config(text=t("wf.step_progress_fill", 1, len(steps) + 1, t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)), 0, first_fill_total))
            progress_label.config(text=t("wf.progress_of", 0, first_fill_total))
        else:
            step_label.config(text=t("wf.step_progress", 1, len(steps) + 1, t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
            progress_label.config(text="")
        first_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)) + " ---", ""]
        for h in first_header:
            root.after(0, lambda line=h: append_log(line))
        proc, q = run_workflow_streaming(first_action, extra_args=first_extra)
        process_holder.append((first_action, proc))
        root.after(50, lambda: poll_sequence(steps, first_header, [], q, run_buttons_list[0] if run_buttons_list else None, cancel_btn, first_fill_total, first_fill_done, on_success))

    def run_fill_queue():
        steps = []
        for idx in (0, 1):
            extra = _collect_extra_from_widgets(section_widgets[idx])
            steps.append((SEQUENCE_ACTIONS[idx], extra))
            _save_last_params(SEQUENCE_ACTIONS[idx], extra)
        _start_run(steps)

    def run_pick_links():
        steps = [("pick_run_links", [])]
        _start_run(steps, on_success=lambda: _show_run_tools_dialog(root, get_content_dir()))

    def run_generate_and_fill():
        steps = []
        for idx in (2, 3):
            extra = _collect_extra_from_widgets(section_widgets[idx])
            steps.append((SEQUENCE_ACTIONS[idx], extra))
            _save_last_params(SEQUENCE_ACTIONS[idx], extra)
        _start_run(steps)

    def run_preview():
        steps = []
        for idx, action in enumerate(SEQUENCE_ACTIONS):
            extra = _collect_extra_from_widgets(section_widgets[idx])
            steps.append((action, extra))
            _save_last_params(action, extra)
        preview_remaining_steps[0] = steps[3:]
        preview_steps = steps[2:3]  # start from step 3: generate_articles only (skip generate_use_cases, generate_queue)
        preview_mode[0] = True
        sequence_cancelled[0] = False
        for b in run_buttons_list:
            b.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("wf.running"), foreground="gray")
        progress_bar["value"] = 0
        progress_label.config(text="")
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
            progress_label.config(text=t("wf.progress_of", 0, first_fill_total))
        else:
            step_label.config(text=t("wf.step_progress", 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
            progress_label.config(text="")
        first_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)) + " ---", ""]
        for h in first_header:
            root.after(0, lambda line=h: append_log(line))
        proc, q = run_workflow_streaming(first_action, extra_args=first_extra)
        process_holder.append((first_action, proc))
        root.after(50, lambda: poll_sequence(preview_steps, first_header, [], q, run_buttons_list[0] if run_buttons_list else None, cancel_btn, first_fill_total, first_fill_done))

    def _fill_selected(selected_stems: list[str], all_items: list[tuple[str, str]], prev_output: str, remove_unselected: bool = False):
        articles_dir = get_content_dir() / "articles"
        all_stems = {stem for _, stem in all_items}
        rejected = all_stems - set(selected_stems)
        deleted = 0
        queue_path = get_content_dir() / "queue.yaml"
        if remove_unselected and _queue_use_cases_available and queue_path.exists() and rejected:
            try:
                queue_items = load_existing_queue(queue_path)
                for stem in rejected:
                    idx = _find_queue_index_by_stem(queue_items, stem)
                    if idx is not None:
                        queue_items[idx]["status"] = "todo"
                save_queue(queue_path, queue_items)
            except Exception:
                pass
        if remove_unselected:
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
        for b in run_buttons_list:
            b.config(state=tk.DISABLED)
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
            progress_label.config(text=t("wf.progress_of", 0, fill_total))
        else:
            step_label.config(text=t("wf.step_progress", completed + 1, len(SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
            progress_label.config(text="")
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
        rbtn = run_buttons_list[0] if run_buttons_list else None
        root.after(50, lambda: poll_sequence(remaining_steps, accumulated, [], q, rbtn, cancel_btn, fill_total, fill_done))

    def _delete_selected(selected_stems: list[str]):
        """Remove selected skeletons: delete .md, remove from queue, set use case status to discarded."""
        if not selected_stems or not _queue_use_cases_available:
            if selected_stems and not _queue_use_cases_available:
                messagebox.showerror(t("msg.error"), t("sel.queue_use_cases_unavailable"))
            return
        if not messagebox.askokcancel(
            t("sel.delete_confirm_title"),
            t("sel.delete_confirm_msg").format(len(selected_stems)),
            icon=messagebox.WARNING,
        ):
            return
        root_dir = get_project_root()
        articles_dir = get_content_dir() / "articles"
        queue_path = get_content_dir() / "queue.yaml"
        use_cases_path = get_content_dir() / "use_cases.yaml"
        try:
            queue_items = load_existing_queue(queue_path)
            use_cases = load_use_cases(use_cases_path)
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))
            return
        to_remove = set()
        deleted_count = 0
        for stem in selected_stems:
            p = articles_dir / (stem + ".md")
            if p.exists():
                try:
                    p.unlink()
                    deleted_count += 1
                except OSError:
                    pass
            idx = _find_queue_index_by_stem(queue_items, stem)
            if idx is not None:
                to_remove.add(idx)
        removed_entries = [queue_items[i] for i in sorted(to_remove)]
        queue_new = [e for i, e in enumerate(queue_items) if i not in to_remove]
        discarded_count = 0
        for entry in removed_entries:
            uc_idx = _find_use_case_index_by_queue_entry(use_cases, entry)
            if uc_idx is not None:
                use_cases[uc_idx]["status"] = "discarded"
                discarded_count += 1
        save_queue(queue_path, queue_new)
        _save_use_cases(use_cases_path, use_cases)
        log_line = t("sel.deleted_selected_log", deleted_count, discarded_count)
        try:
            log_area.config(state=tk.NORMAL)
            log_area.insert(tk.END, "\n" + log_line + "\n")
            log_area.see(tk.END)
            log_area.config(state=tk.DISABLED)
        except tk.TclError:
            pass
        messagebox.showinfo(t("msg.info"), t("sel.deleted_selected_done", deleted_count, discarded_count))

    def cancel_run():
        sequence_cancelled[0] = True
        if len(process_holder) >= 1 and isinstance(process_holder[0], tuple):
            _, proc = process_holder[0]
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    btn_fill_queue = ttk.Button(row_btn, text=t("wf.btn_fill_queue"), command=run_fill_queue)
    btn_fill_queue.pack(side=tk.LEFT, padx=(0, 5))
    btn_pick_links = ttk.Button(row_btn, text=t("wf.btn_pick_links"), command=run_pick_links)
    btn_pick_links.pack(side=tk.LEFT, padx=(0, 5))
    btn_generate_fill = ttk.Button(row_btn, text=t("wf.btn_generate_and_fill"), command=run_generate_and_fill)
    btn_generate_fill.pack(side=tk.LEFT, padx=(0, 5))
    preview_btn = ttk.Button(row_btn, text=t("wf.preview_btn"), command=run_preview)
    preview_btn.pack(side=tk.LEFT, padx=(0, 5))
    cancel_btn = ttk.Button(row_btn, text=t("btn.cancel"), command=cancel_run, state=tk.DISABLED)
    cancel_btn.pack(side=tk.LEFT, padx=5)
    run_buttons_list.extend([btn_fill_queue, btn_pick_links, btn_generate_fill, preview_btn])

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


# Pierwsze 4 kroki pipeline (Generuj łatwo artykuły)
EASY_SEQUENCE_ACTIONS = SEQUENCE_ACTIONS[:4]

# Tooltip keys per content_type for easy tab (easy.tt_*)
EASY_CONTENT_TYPE_TOOLTIP_KEYS = {
    "how-to": "easy.tt_howto",
    "guide": "easy.tt_guide",
    "best": "easy.tt_best",
    "comparison": "easy.tt_comparison",
    "review": "easy.tt_review",
    "sales": "easy.tt_sales",
    "product-comparison": "easy.tt_product_comparison",
    "best-in-category": "easy.tt_best_in_category",
    "category-products": "easy.tt_category_products",
}

# Grupy typów treści w zakładce easy: (klucz etykiety, klucz tooltipa, tuple typów)
EASY_CONTENT_GROUPS = [
    ("easy.group_playbook_label", "easy.group_playbook", ("how-to", "guide", "best", "comparison")),
    ("easy.group_product_label", "easy.group_product", ("sales", "product-comparison", "best-in-category", "category-products")),
    ("easy.group_review_label", "easy.group_review", ("review",)),
]


def build_easy_workflow_tab(parent, last_output_holder: list):
    """Zakładka Generuj łatwo artykuły: uproszczony formularz (kategoria, problemy, limit, typy treści) + te same przyciski Uruchom / Generuj z podglądem co w Generuj artykuły."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from content_index import get_hubs_list, load_config
        from config_manager import write_config
    except ImportError as e:
        ttk.Label(f, text=f"Błąd importu: {e}", foreground="red").pack(anchor=tk.W)
        return f

    italic_font = ("TkDefaultFont", 9, "italic")
    config_path = get_content_dir() / "config.yaml"
    section_widgets: list = [None, [], [], []]  # step1 from A+D; steps 2,3,4 from param widgets
    easy_hint_labels: list = []

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

    def _on_canvas_configure(ev):
        canvas.itemconfig(canvas_window, width=ev.width)
        wrap_w = max(80, ev.width - 260)
        for lbl in easy_hint_labels:
            try:
                lbl.configure(wraplength=wrap_w)
            except tk.TclError:
                pass
    canvas.bind("<Configure>", _on_canvas_configure)
    def _on_mousewheel(ev):
        canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
    canvas.bind("<MouseWheel>", _on_mousewheel)

    # --- Sekcja A: Gdzie trafią artykuły (tryb: jeden hub vs wiele kategorii, kategoria, hub) ---
    lf_a = ttk.LabelFrame(inner, text=t("easy.section_where"))
    lf_a.pack(fill=tk.X, pady=(0, 10))
    inner_a = ttk.Frame(lf_a, padding=5)
    inner_a.pack(fill=tk.X)
    try:
        _cfg_a = load_config(config_path)
        _single_hub_cfg = bool(_cfg_a.get("use_case_single_hub", True))
    except Exception:
        _single_hub_cfg = True
    var_where_mode = tk.StringVar(value="one_hub" if _single_hub_cfg else "multiple_categories")
    row_a_choice = ttk.Frame(lf_a, padding=(0, 0))
    row_a_choice.pack(fill=tk.X)
    rb_one_hub = ttk.Radiobutton(row_a_choice, text=t("easy.where_one_hub"), variable=var_where_mode, value="one_hub")
    rb_one_hub.pack(side=tk.LEFT, padx=(0, 20))
    rb_multi_cat = ttk.Radiobutton(row_a_choice, text=t("easy.where_multi_cat"), variable=var_where_mode, value="multiple_categories")
    rb_multi_cat.pack(side=tk.LEFT)
    defaults_uc = get_use_case_defaults()
    cat_vals = list(defaults_uc.get("categories", []) or ["ai-marketing-automation"])
    cat_display = list(defaults_uc.get("categories_display", []) or cat_vals)
    if len(cat_display) != len(cat_vals):
        cat_display = cat_vals
    row_a_cat = ttk.Frame(lf_a, padding=(5, 5))
    row_a_cat.pack(fill=tk.X)
    ttk.Label(row_a_cat, text=t("easy.hub_dropdown_label") + ":", width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    e_prod = ttk.Combobox(row_a_cat, values=cat_display, state="readonly", width=min(45, max(20, len(max(cat_display, key=len)) + 2)))
    e_prod.pack(side=tk.LEFT, padx=(0, 5))
    if cat_display:
        try:
            cfg = load_config(config_path)
            prod_cfg = (cfg.get("production_category") or "").strip()
            if prod_cfg and prod_cfg in cat_vals:
                e_prod.set(cat_display[cat_vals.index(prod_cfg)])
            else:
                e_prod.set(cat_display[0])
        except Exception:
            e_prod.set(cat_display[0])
    lbl_a_hint = tk.Label(lf_a, text=t("easy.category_hint"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=520)
    lbl_a_hint.pack(anchor=tk.W, padx=(5, 5), pady=(0, 4))
    easy_hint_labels.append(lbl_a_hint)
    row_a_hub = ttk.Frame(lf_a, padding=(0, 5))
    row_a_hub.pack(fill=tk.X)
    ttk.Label(row_a_hub, text=t("config.hub_slug"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    e_hub = ttk.Combobox(row_a_hub, width=40)
    e_hub.pack(side=tk.LEFT, padx=(0, 5))
    lbl_hub_hint = tk.Label(row_a_hub, text=t("config.hub_slug_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_hub_hint.pack(anchor=tk.W, padx=(0, 5))
    easy_hint_labels.append(lbl_hub_hint)
    row_a_mode = ttk.Frame(lf_a, padding=(0, 5))
    ttk.Label(row_a_mode, text=t("config.category_mode"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    e_category_mode = ttk.Combobox(
        row_a_mode,
        values=(t("config.category_mode_production_only"), t("config.category_mode_preserve_sandbox")),
        width=40,
        state="readonly",
    )
    e_category_mode.pack(side=tk.LEFT, padx=(0, 5))
    if _single_hub_cfg:
        e_category_mode.set(t("config.category_mode_production_only"))
    else:
        _mode = str(_cfg_a.get("category_mode") or "production_only").strip().lower()
        if _mode == "preserve_sandbox":
            e_category_mode.set(t("config.category_mode_preserve_sandbox"))
        else:
            e_category_mode.set(t("config.category_mode_production_only"))
    lbl_mode_hint = tk.Label(row_a_mode, text=t("config.category_mode_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_mode_hint.pack(anchor=tk.W, padx=(0, 5))
    easy_hint_labels.append(lbl_mode_hint)
    if var_where_mode.get() == "one_hub":
        row_a_mode.pack_forget()
    else:
        row_a_mode.pack(fill=tk.X)

    def _toggle_where_mode():
        if var_where_mode.get() == "one_hub":
            row_a_mode.pack_forget()
        else:
            row_a_mode.pack(fill=tk.X, pady=(0, 5))
    var_where_mode.trace_add("write", lambda *a: _toggle_where_mode())

    # --- Sekcja B: Problemy i obszar tematyczny ---
    lf_b = ttk.LabelFrame(inner, text=t("easy.section_problems"))
    lf_b.pack(fill=tk.X, pady=(0, 10))
    inner_b = ttk.Frame(lf_b, padding=5)
    inner_b.pack(fill=tk.X)
    row_base = ttk.Frame(inner_b)
    row_base.pack(fill=tk.X)
    ttk.Label(row_base, text=t("config.base_problem"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    e_base = ttk.Entry(row_base, width=45)
    e_base.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    ttk.Button(row_base, text=t("btn.add"), command=lambda: _lb_add(lb_suggested, e_base)).pack(side=tk.LEFT, padx=2)
    ttk.Button(row_base, text=t("btn.remove"), command=lambda: e_base.delete(0, tk.END)).pack(side=tk.LEFT, padx=2)
    row_sug = ttk.Frame(inner_b)
    row_sug.pack(fill=tk.X, pady=(4, 0))
    ttk.Label(row_sug, text=t("config.suggested_list"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    lb_suggested = tk.Listbox(row_sug, height=3, selectmode=tk.EXTENDED, width=45)
    lb_suggested.pack(side=tk.LEFT, fill=tk.X, expand=True)
    e_sug_new = ttk.Entry(row_sug, width=30)
    e_sug_new.pack(side=tk.LEFT, padx=(5, 2))
    ttk.Button(row_sug, text=t("btn.add"), command=lambda: _lb_add(lb_suggested, e_sug_new)).pack(side=tk.LEFT, padx=2)
    ttk.Button(row_sug, text=t("btn.remove"), command=lambda: _lb_remove(lb_suggested)).pack(side=tk.LEFT, padx=2)
    row_sand = ttk.Frame(inner_b)
    row_sand.pack(fill=tk.X, pady=(4, 0))
    ttk.Label(row_sand, text=t("config.sandbox"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    lb_sandbox = tk.Listbox(row_sand, height=2, selectmode=tk.EXTENDED, width=45)
    lb_sandbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
    e_sand_new = ttk.Entry(row_sand, width=30)
    e_sand_new.pack(side=tk.LEFT, padx=(5, 2))
    ttk.Button(row_sand, text=t("btn.add"), command=lambda: _lb_add(lb_sandbox, e_sand_new)).pack(side=tk.LEFT, padx=2)
    ttk.Button(row_sand, text=t("btn.remove"), command=lambda: _lb_remove(lb_sandbox)).pack(side=tk.LEFT, padx=2)

    def _lb_add(lb, entry):
        val = entry.get().strip()
        if val:
            lb.insert(tk.END, val)
            entry.delete(0, tk.END)
    def _lb_remove(lb):
        for i in reversed(lb.curselection()):
            lb.delete(i)

    # --- Sekcja C: Limit pomysłów i odbiorcy (podpowiedzi jak w Konfiguracji) ---
    lf_c = ttk.LabelFrame(inner, text=t("easy.section_limit"))
    lf_c.pack(fill=tk.X, pady=(0, 10))
    inner_c = ttk.Frame(lf_c, padding=5)
    inner_c.pack(fill=tk.X)
    row_c_batch = ttk.Frame(inner_c)
    row_c_batch.pack(fill=tk.X)
    ttk.Label(row_c_batch, text=t("config.batch_friendly"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_batch_c = ttk.Frame(row_c_batch)
    hint_batch_c.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_batch_hint = tk.Label(hint_batch_c, text=t("config.batch_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_batch_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    easy_hint_labels.append(lbl_batch_hint)
    row_c_spin = ttk.Frame(inner_c)
    row_c_spin.pack(fill=tk.X, pady=(2, 6))
    e_batch = ttk.Spinbox(row_c_spin, from_=1, to=12, width=6)
    e_batch.pack(side=tk.LEFT, padx=(33, 15))
    row_c_pyr = ttk.Frame(inner_c)
    row_c_pyr.pack(fill=tk.X)
    ttk.Label(row_c_pyr, text=t("config.pyramid_friendly"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_pyr_c = ttk.Frame(row_c_pyr)
    hint_pyr_c.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_pyr_hint = tk.Label(hint_pyr_c, text=t("config.pyramid_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_pyr_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    easy_hint_labels.append(lbl_pyr_hint)
    sp_beg = tk.IntVar(value=3)
    sp_int = tk.IntVar(value=3)
    sp_pro = tk.IntVar(value=3)
    lbl_sum = tk.StringVar(value="")

    def _pyr_update_sum_easy(*_args):
        try:
            total = int(e_batch.get())
        except (ValueError, TypeError):
            total = 9
        b, i, p = sp_beg.get(), sp_int.get(), sp_pro.get()
        s = b + i + p
        lbl_sum.set(f"{t('config.pyr_sum')}: {s} / {total}")
        color = "green" if s == total else ("red" if s > total else "orange")
        sum_label_c.config(fg=color)

    def _pyr_clamp_easy(var: tk.IntVar, *_args):
        try:
            total = int(e_batch.get())
        except (ValueError, TypeError):
            total = 9
        b, i, p = sp_beg.get(), sp_int.get(), sp_pro.get()
        if var is sp_beg:
            sp_beg.set(max(0, min(total, b)))
            sp_pro.set(max(0, total - sp_beg.get() - sp_int.get()))
        elif var is sp_int:
            sp_int.set(max(0, min(total, i)))
            sp_pro.set(max(0, total - sp_beg.get() - sp_int.get()))
        else:
            sp_pro.set(max(0, total - sp_beg.get() - sp_int.get()))
        _pyr_update_sum_easy()

    row_c_pyr_sum = ttk.Frame(inner_c)
    row_c_pyr_sum.pack(fill=tk.X, pady=(2, 0))
    sum_label_c = tk.Label(row_c_pyr_sum, textvariable=lbl_sum, font=italic_font, anchor=tk.W)
    sum_label_c.pack(side=tk.LEFT, padx=(33, 12))
    ttk.Label(row_c_pyr_sum, text=t("config.pyr_beginner"), width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Spinbox(row_c_pyr_sum, from_=0, to=12, width=5, textvariable=sp_beg, command=lambda: _pyr_clamp_easy(sp_beg)).pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(row_c_pyr_sum, text=t("config.pyr_intermediate"), width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Spinbox(row_c_pyr_sum, from_=0, to=12, width=5, textvariable=sp_int, command=lambda: _pyr_clamp_easy(sp_int)).pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(row_c_pyr_sum, text=t("config.pyr_professional"), width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Spinbox(row_c_pyr_sum, from_=0, to=12, width=5, textvariable=sp_pro, command=lambda: _pyr_clamp_easy(sp_pro)).pack(side=tk.LEFT, padx=2)
    sp_beg.trace_add("write", lambda *a: _pyr_clamp_easy(sp_beg))
    sp_int.trace_add("write", lambda *a: _pyr_clamp_easy(sp_int))
    sp_pro.trace_add("write", lambda *a: _pyr_clamp_easy(sp_pro))
    e_batch.config(command=lambda: _pyr_update_sum_easy())
    _pyr_update_sum_easy()

    # --- Sekcja D: Typy treści (grupy: Playbook, Produktowe, Recenzja) ---
    def _display_for_content_type(ct: str) -> str:
        for disp, val in CONTENT_TYPE_CHOICES_WORKFLOW[1:]:
            if val == ct:
                return t(disp) if disp and "." in disp else (disp or ct)
        return ct

    lf_d = ttk.LabelFrame(inner, text=t("easy.section_content_types"))
    lf_d.pack(fill=tk.X, pady=(0, 10))
    inner_d = ttk.Frame(lf_d, padding=5)
    inner_d.pack(fill=tk.X)
    allowed_types_set = set(get_content_types_all())
    content_type_vars: list = []
    var_all = tk.BooleanVar(value=True)
    content_type_vars.append(("wf.content_all", None, var_all))

    # Wiersz: ALL
    row_d_all = ttk.Frame(inner_d)
    row_d_all.pack(fill=tk.X)
    ttk.Label(row_d_all, text="", width=28).pack(side=tk.LEFT, padx=(0, 5))
    cb_all = ttk.Checkbutton(row_d_all, text=t("wf.content_all_short"), variable=var_all)
    cb_all.pack(side=tk.LEFT, padx=(0, 12))
    _create_tooltip(cb_all, t("wf.content_type_desc"))

    # Wiersze grup: etykieta + wyjaśnienie (wyszarzone, kursywa) + checkboxy typów
    for label_key, tooltip_key, group_types in EASY_CONTENT_GROUPS:
        row_grp = ttk.Frame(inner_d)
        row_grp.pack(fill=tk.X, pady=(6, 0))
        row_grp_top = ttk.Frame(row_grp)
        row_grp_top.pack(fill=tk.X)
        lbl_grp = ttk.Label(row_grp_top, text=t(label_key), width=28, anchor=tk.W)
        lbl_grp.pack(side=tk.LEFT, padx=(0, 5))
        hint_grp_frame = ttk.Frame(row_grp_top)
        hint_grp_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        lbl_grp_hint = tk.Label(hint_grp_frame, text=t(tooltip_key), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
        lbl_grp_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
        easy_hint_labels.append(lbl_grp_hint)
        row_grp_cb = ttk.Frame(row_grp)
        row_grp_cb.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(row_grp_cb, text="", width=28).pack(side=tk.LEFT, padx=(0, 5))
        cb_frame = ttk.Frame(row_grp_cb)
        cb_frame.pack(side=tk.LEFT, anchor=tk.W)
        for ct in group_types:
            if ct not in allowed_types_set:
                continue
            display = _display_for_content_type(ct)
            var = tk.BooleanVar(value=False)
            content_type_vars.append((display, ct, var))
            cb = ttk.Checkbutton(cb_frame, text=display, variable=var)
            cb.pack(side=tk.LEFT, padx=(0, 12))
            tip_key = EASY_CONTENT_TYPE_TOOLTIP_KEYS.get(ct, "")
            if tip_key:
                _create_tooltip(cb, t(tip_key))

    def _on_all_ct():
        if var_all.get():
            for _d, _v, vb in content_type_vars[1:]:
                vb.set(False)
    def _on_single_ct():
        if any(vb.get() for _d, _v, vb in content_type_vars[1:]):
            var_all.set(False)
    var_all.trace_add("write", lambda *a: _on_all_ct())
    for _d, _v, vb in content_type_vars[1:]:
        vb.trace_add("write", lambda *a: _on_single_ct())

    # --- Sekcja: Pełna lista typów treści (content_types_all) ---
    lf_ct_all = ttk.LabelFrame(inner, text=t("ucp.section_content_types_all"))
    lf_ct_all.pack(fill=tk.X, pady=(0, 10))
    inner_ct = ttk.Frame(lf_ct_all, padding=5)
    inner_ct.pack(fill=tk.X)
    lbl_ct_hint = tk.Label(inner_ct, text=t("ucp.content_types_all_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=520)
    lbl_ct_hint.pack(anchor=tk.W, pady=(0, 4))
    easy_hint_labels.append(lbl_ct_hint)
    row_ct = ttk.Frame(inner_ct)
    row_ct.pack(fill=tk.X)
    lb_content_types_all = tk.Listbox(row_ct, height=4, selectmode=tk.EXTENDED, width=50)
    lb_content_types_all.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
    e_ct_new = ttk.Entry(row_ct, width=25)
    e_ct_new.pack(side=tk.LEFT, padx=(0, 2))
    ttk.Button(row_ct, text=t("btn.add"), command=lambda: _lb_add(lb_content_types_all, e_ct_new)).pack(side=tk.LEFT, padx=2)
    ttk.Button(row_ct, text=t("btn.remove"), command=lambda: _lb_remove(lb_content_types_all)).pack(side=tk.LEFT, padx=2)

    # --- Sekcja: Lista hubów + tytuł główny ---
    lf_hubs = ttk.LabelFrame(inner, text=t("ucp.section_hubs"))
    lf_hubs.pack(fill=tk.X, pady=(0, 10))
    inner_hubs = ttk.Frame(lf_hubs, padding=5)
    inner_hubs.pack(fill=tk.X)
    lbl_hubs_hint = tk.Label(inner_hubs, text=t("ucp.hubs_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=520)
    lbl_hubs_hint.pack(anchor=tk.W, pady=(0, 4))
    easy_hint_labels.append(lbl_hubs_hint)
    row_hub_title = ttk.Frame(inner_hubs)
    row_hub_title.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(row_hub_title, text=t("ucp.hub_title_label"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    e_hub_title = ttk.Entry(row_hub_title, width=55)
    e_hub_title.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    hubs_data = []
    lb_hubs = tk.Listbox(inner_hubs, height=3, selectmode=tk.EXTENDED, width=70)
    lb_hubs.pack(fill=tk.X, pady=(0, 4))
    def _hubs_display():
        lb_hubs.delete(0, tk.END)
        for h in hubs_data:
            s = h.get("slug") or ""
            c = h.get("category") or ""
            ttl = h.get("title") or ""
            lb_hubs.insert(tk.END, f"{s} | {c} | {ttl}")
    def _hub_add_edit(edit_index=None):
        sub = tk.Toplevel(inner_hubs.winfo_toplevel())
        sub.title(t("links.dialog_add_title") if edit_index is None else t("links.dialog_edit_title"))
        sub.transient(inner_hubs.winfo_toplevel())
        sub.grab_set()
        fsub = ttk.Frame(sub, padding=10)
        fsub.pack(fill=tk.BOTH, expand=True)
        ttk.Label(fsub, text=t("ucp.hubs_col_slug")).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        e_slug = ttk.Entry(fsub, width=35)
        e_slug.grid(row=0, column=1, pady=2)
        ttk.Label(fsub, text=t("ucp.hubs_col_category")).grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        e_cat = ttk.Entry(fsub, width=35)
        e_cat.grid(row=1, column=1, pady=2)
        ttk.Label(fsub, text=t("ucp.hubs_col_title")).grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        e_ttl = ttk.Entry(fsub, width=35)
        e_ttl.grid(row=2, column=1, pady=2)
        if edit_index is not None and 0 <= edit_index < len(hubs_data):
            h = hubs_data[edit_index]
            e_slug.insert(0, h.get("slug") or "")
            e_cat.insert(0, h.get("category") or "")
            e_ttl.insert(0, h.get("title") or "")
        def ok():
            slug = (e_slug.get() or "").strip().lower().replace(" ", "-")
            cat = (e_cat.get() or "").strip()
            title = (e_ttl.get() or "").strip()
            if slug or cat:
                entry = {"slug": slug or cat, "category": cat or slug, "title": title or slug or cat}
                if edit_index is not None and 0 <= edit_index < len(hubs_data):
                    hubs_data[edit_index] = entry
                else:
                    hubs_data.append(entry)
                _hubs_display()
            sub.destroy()
        ttk.Button(fsub, text=t("btn.ok"), command=ok).grid(row=3, column=1, pady=5)
        sub.wait_window()
    def _hub_remove():
        for i in reversed(lb_hubs.curselection()):
            if 0 <= i < len(hubs_data):
                hubs_data.pop(i)
        _hubs_display()
    row_hubs_btn = ttk.Frame(inner_hubs)
    row_hubs_btn.pack(fill=tk.X)
    ttk.Button(row_hubs_btn, text=t("btn.add"), command=lambda: _hub_add_edit()).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(row_hubs_btn, text=t("btn.remove"), command=_hub_remove).pack(side=tk.LEFT, padx=5)

    # --- Sekcja E: Kroki 2–4 (parametry) ---
    for idx, action in enumerate(EASY_SEQUENCE_ACTIONS[1:], 1):
        lf_e = ttk.LabelFrame(inner, text=t(WORKFLOW_LABEL_KEYS.get(action, action)))
        lf_e.pack(fill=tk.X, pady=(0, 10))
        section_inner = ttk.Frame(lf_e, padding=5)
        section_inner.pack(fill=tk.X)
        widgets = _build_param_widgets_for_action(section_inner, action, italic_font, easy_hint_labels, 14)
        section_widgets[idx] = widgets

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    row_btn = ttk.Frame(left_frame)
    row_btn.pack(fill=tk.X, pady=(8, 0))
    right_frame = ttk.Frame(paned_h)
    paned_h.add(right_frame, weight=1)
    ttk.Label(right_frame, text=t("wf.log")).pack(anchor=tk.W, pady=(0, 2))
    step_label = ttk.Label(right_frame, text="", foreground="gray")
    step_label.pack(anchor=tk.W, pady=(0, 2))
    progress_label = ttk.Label(right_frame, text="", foreground="gray")
    progress_label.pack(anchor=tk.W, pady=(0, 2))
    progress_bar = ttk.Progressbar(right_frame, maximum=len(EASY_SEQUENCE_ACTIONS), value=0, length=280)
    progress_bar.pack(fill=tk.X, pady=(0, 5))
    log_area = scrolledtext.ScrolledText(right_frame, height=14, wrap=tk.WORD, state=tk.DISABLED)
    log_area.pack(fill=tk.BOTH, expand=True, pady=5)
    status_label = ttk.Label(right_frame, text="", foreground="gray")
    status_label.pack(anchor=tk.W)

    process_holder = []
    sequence_cancelled = [False]
    preview_mode = [False]
    preview_remaining_steps = [[]]
    easy_run_buttons_list = []
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

    def append_log(line):
        log_area.config(state=tk.NORMAL)
        log_area.insert(tk.END, line + "\n")
        log_area.see(tk.END)
        log_area.config(state=tk.DISABLED)

    def _parse_fill_limit(extra: list) -> int:
        for i, x in enumerate(extra):
            if x == "--limit" and i + 1 < len(extra):
                try:
                    return int(extra[i + 1])
                except ValueError:
                    pass
        return 0

    def _prod_slug() -> str:
        """Mapuj wybraną etykietę (np. 'Problem Fix & Find (PL)') na slug kategorii."""
        sel = (e_prod.get() or "").strip()
        if sel in cat_vals:
            return sel
        try:
            idx = cat_display.index(sel)
            return cat_vals[idx] if 0 <= idx < len(cat_vals) else (cat_vals[0] if cat_vals else "ai-marketing-automation")
        except (ValueError, AttributeError):
            return cat_vals[0] if cat_vals else "ai-marketing-automation"

    def _collect_step1_extra() -> list:
        prod = _prod_slug()
        extra = ["--category", prod]
        if not var_all.get():
            for _d, val, vb in content_type_vars[1:]:
                if val and vb.get():
                    extra.extend(["--content-type", val])
        return extra

    def _save_config_and_sync():
        prod = _prod_slug()
        hub = (e_hub.get() or "").strip() or prod
        one_hub = var_where_mode.get() == "one_hub"
        if one_hub:
            category_mode = "production_only"
        else:
            mode_display = (e_category_mode.get() or "").strip()
            category_mode = "preserve_sandbox" if mode_display == t("config.category_mode_preserve_sandbox") else "production_only"
        sandbox = [lb_sandbox.get(i) for i in range(lb_sandbox.size()) if lb_sandbox.get(i).strip()]
        base_val = e_base.get().strip()
        rest_suggested = [lb_suggested.get(i) for i in range(lb_suggested.size()) if lb_suggested.get(i).strip()]
        suggested = [base_val] + rest_suggested if base_val else rest_suggested
        if not suggested and rest_suggested:
            suggested = [""] + rest_suggested
        try:
            batch = int(e_batch.get().strip() or 9)
        except ValueError:
            batch = 9
        batch = max(1, min(12, batch))
        try:
            beg = int(sp_beg.get())
            inte = int(sp_int.get())
        except (ValueError, tk.TclError):
            beg, inte = 3, 0
        pyramid = [beg, inte]
        cta = [lb_content_types_all.get(i).strip() for i in range(lb_content_types_all.size()) if lb_content_types_all.get(i).strip()]
        hub_title_val = (e_hub_title.get() or "").strip()
        write_config(
            config_path,
            prod,
            hub,
            sandbox,
            use_case_batch_size=batch,
            use_case_audience_pyramid=pyramid,
            suggested_problems=suggested,
            category_mode=category_mode,
            use_case_single_hub=one_hub,
            content_types_all=cta if cta else None,
            hubs=hubs_data if hubs_data else None,
            hub_title=hub_title_val if hub_title_val else None,
        )
        try:
            from generate_use_cases import sync_allowed_categories_file
            sync_allowed_categories_file(config_path, get_content_dir() / "use_case_allowed_categories.json")
        except Exception:
            pass

    def _start_easy_run(steps: list, on_success=None):
        _save_config_and_sync()
        preview_mode[0] = False
        sequence_cancelled[0] = False
        for b in easy_run_buttons_list:
            b.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("wf.running"), foreground="gray")
        progress_bar["value"] = 0
        progress_label.config(text="")
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("wf.running") + "\n")
        log_area.config(state=tk.DISABLED)
        process_holder.clear()
        first_action, first_extra = steps[0]
        first_fill_total = _parse_fill_limit(first_extra) if first_action == "fill_articles" else 0
        first_fill_done = [0]
        if first_fill_total > 0:
            step_label.config(text=t("wf.step_progress_fill", 1, len(steps), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)), 0, first_fill_total))
            progress_label.config(text=t("wf.progress_of", 0, first_fill_total))
        else:
            step_label.config(text=t("wf.step_progress", 1, len(steps), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
        first_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)) + " ---", ""]
        for h in first_header:
            root.after(0, lambda line=h: append_log(line))
        proc, q = run_workflow_streaming(first_action, first_extra)
        process_holder.append((first_action, proc))
        remaining = steps[1:]
        rbtn = easy_run_buttons_list[0] if easy_run_buttons_list else None
        root.after(50, lambda: _poll_easy_sequence(remaining, first_header, [], q, rbtn, cancel_btn, first_fill_total, first_fill_done, on_success))

    def run_fill_queue_easy():
        step1_extra = _collect_step1_extra()
        steps = [
            (EASY_SEQUENCE_ACTIONS[0], step1_extra),
            (EASY_SEQUENCE_ACTIONS[1], _collect_extra_from_widgets(section_widgets[1])),
        ]
        _start_easy_run(steps)

    def run_pick_links_easy():
        steps = [("pick_run_links", [])]
        _start_easy_run(steps, on_success=lambda: _show_run_tools_dialog(root, get_content_dir()))

    def run_generate_and_fill_easy():
        steps = [
            (EASY_SEQUENCE_ACTIONS[2], _collect_extra_from_widgets(section_widgets[2])),
            (EASY_SEQUENCE_ACTIONS[3], _collect_extra_from_widgets(section_widgets[3])),
        ]
        _start_easy_run(steps)

    def run_render_articles_easy():
        """Run generate_hubs → generate_sitemap → render_site (build public/)."""
        steps = [
            ("generate_hubs", []),
            ("generate_sitemap", []),
            ("render_site", []),
        ]
        _start_easy_run(steps)

    def run_preview():
        _save_config_and_sync()
        steps = [
            (EASY_SEQUENCE_ACTIONS[2], _collect_extra_from_widgets(section_widgets[2])),
        ]
        preview_remaining_steps[0] = [
            (EASY_SEQUENCE_ACTIONS[3], _collect_extra_from_widgets(section_widgets[3])),
        ]
        preview_mode[0] = True
        sequence_cancelled[0] = False
        for b in easy_run_buttons_list:
            b.config(state=tk.DISABLED)
        cancel_btn.config(state=tk.NORMAL)
        status_label.config(text=t("wf.running"), foreground="gray")
        progress_bar["value"] = 0
        progress_label.config(text="")
        log_area.config(state=tk.NORMAL)
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, t("wf.running") + "\n")
        log_area.config(state=tk.DISABLED)
        process_holder.clear()
        first_action, first_extra = steps[0]
        first_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)) + " ---", ""]
        for h in first_header:
            root.after(0, lambda line=h: append_log(line))
        proc, q = run_workflow_streaming(first_action, first_extra)
        process_holder.append((first_action, proc))
        rbtn = easy_run_buttons_list[0] if easy_run_buttons_list else None
        root.after(50, lambda: _poll_easy_sequence([], first_header, [], q, rbtn, cancel_btn, 0, [0]))

    def _poll_easy_sequence(remaining, accumulated, current_out_lines, q, rbtn, cbtn, fill_total=0, fill_done=None, on_success_callback=None):
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
                completed_index = len(EASY_SEQUENCE_ACTIONS) - len(remaining) - 1
                failed_action = EASY_SEQUENCE_ACTIONS[completed_index] if 0 <= completed_index < len(EASY_SEQUENCE_ACTIONS) else None
                def done():
                    log_area.config(state=tk.NORMAL)
                    log_area.delete("1.0", tk.END)
                    log_area.insert(tk.END, full_text)
                    log_area.insert(tk.END, f"\n\n[Kod powrotu: {code}]")
                    log_area.config(state=tk.DISABLED)
                    for b in easy_run_buttons_list:
                        try:
                            b.config(state=tk.NORMAL)
                        except Exception:
                            pass
                    cbtn.config(state=tk.DISABLED)
                    completed = len(EASY_SEQUENCE_ACTIONS) - len(remaining)
                    progress_bar["value"] = len(EASY_SEQUENCE_ACTIONS) if not remaining else completed
                    if not remaining:
                        step_label.config(text=t("wf.step_done"))
                        progress_label.config(text="")
                    if sequence_cancelled[0]:
                        status_text = t("wf.status_cancelled")
                    elif code == 0:
                        status_text = t("wf.status_ok")
                    elif code == 2:
                        status_text = t("wf.status_error_exit2") if failed_action == "generate_use_cases" else t("wf.status_error_exit2_other")
                    else:
                        status_text = t("wf.status_error_exit1")
                    status_label.config(text=status_text, foreground="red" if (sequence_cancelled[0] or code != 0) else "green")
                    process_holder.clear()
                    last_output_holder.clear()
                    last_output_holder.append((full_text, "easy_sequence"))
                    if on_success_callback and code == 0 and not sequence_cancelled[0] and not remaining:
                        try:
                            on_success_callback()
                        except Exception:
                            pass
                    if preview_mode[0] and code == 0 and not sequence_cancelled[0]:
                        preview_mode[0] = False
                        items = _parse_generated_articles(full_text)
                        if items:
                            step_label.config(text=t("wf.preview_done"))
                            status_label.config(text=t("wf.preview_done"), foreground="blue")
                            root.after(100, lambda: _show_article_selector(
                                root, t("sel.title_fill"), items,
                                t("sel.confirm_fill"),
                                lambda selected, remove_unselected=False: _fill_selected_easy(selected, items, full_text, remove_unselected),
                                description_text=t("sel.preview_fill_desc"),
                                delete_label=t("sel.delete_selected"),
                                on_delete_selected=lambda selected: _delete_selected_easy(selected),
                                remove_unselected_var=tk.BooleanVar(value=False)))
                        else:
                            status_label.config(text=t("wf.status_ok"), foreground="green")
                if sequence_cancelled[0] or code != 0 or not remaining:
                    root.after(0, done)
                    return
                next_action, next_extra = remaining.pop(0)
                completed = len(EASY_SEQUENCE_ACTIONS) - len(remaining) - 1
                progress_bar["value"] = completed
                next_fill_total = _parse_fill_limit(next_extra) if next_action == "fill_articles" else 0
                next_fill_done = [0]
                if next_fill_total > 0:
                    step_label.config(text=t("wf.step_progress_fill", completed + 1, len(EASY_SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(next_action, next_action)), 0, next_fill_total))
                    progress_label.config(text=t("wf.progress_of", 0, next_fill_total))
                else:
                    step_label.config(text=t("wf.step_progress", completed + 1, len(EASY_SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(next_action, next_action))))
                next_header = ["", "--- " + t(WORKFLOW_LABEL_KEYS.get(next_action, next_action)) + " ---", ""]
                for h in next_header:
                    root.after(0, lambda line=h: append_log(line))
                proc, new_q = run_workflow_streaming(next_action, next_extra)
                process_holder[0] = (next_action, proc)
                root.after(50, lambda: _poll_easy_sequence(remaining, new_accumulated + next_header, [], new_q, rbtn, cbtn, next_fill_total, next_fill_done, on_success_callback))
                return
            line = item[0]
            if line is not None:
                current_action = process_holder[0][0] if process_holder else None
                if current_action == "fill_articles" and fill_total > 0 and "  Filled:" in line:
                    fill_done[0] += 1
                    completed = len(EASY_SEQUENCE_ACTIONS) - len(remaining) - 1
                    step_label.config(text=t("wf.step_progress_fill", completed + 1, len(EASY_SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get("fill_articles", "fill_articles")), fill_done[0], fill_total))
                    progress_label.config(text=t("wf.progress_of", fill_done[0], fill_total))
                    progress_bar["value"] = completed + (fill_done[0] / fill_total)
                current_out_lines.append(line)
                root.after(0, lambda l=line: append_log(l))
        except queue.Empty:
            pass
        root.after(50, lambda: _poll_easy_sequence(remaining, accumulated, current_out_lines, q, rbtn, cbtn, fill_total, fill_done, on_success_callback))

    def cancel_run():
        sequence_cancelled[0] = True
        if process_holder and isinstance(process_holder[0], tuple):
            _, proc = process_holder[0]
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    def _fill_selected_easy(selected_stems: list[str], all_items: list[tuple[str, str]], prev_output: str, remove_unselected: bool = False):
        articles_dir = get_content_dir() / "articles"
        all_stems = {stem for _, stem in all_items}
        rejected = all_stems - set(selected_stems)
        deleted = 0
        queue_path = get_content_dir() / "queue.yaml"
        if remove_unselected and _queue_use_cases_available and queue_path.exists() and rejected:
            try:
                queue_items = load_existing_queue(queue_path)
                for stem in rejected:
                    idx = _find_queue_index_by_stem(queue_items, stem)
                    if idx is not None:
                        queue_items[idx]["status"] = "todo"
                save_queue(queue_path, queue_items)
            except Exception:
                pass
        if remove_unselected:
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
        for b in easy_run_buttons_list:
            b.config(state=tk.DISABLED)
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
        completed = len(EASY_SEQUENCE_ACTIONS) - len(remaining_steps) - 1
        progress_bar["value"] = completed
        fill_total = _parse_fill_limit(first_extra) if first_action == "fill_articles" else 0
        fill_done = [0]
        if fill_total > 0:
            step_label.config(text=t("wf.step_progress_fill", completed + 1, len(EASY_SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action)), 0, fill_total))
            progress_label.config(text=t("wf.progress_of", 0, fill_total))
        else:
            step_label.config(text=t("wf.step_progress", completed + 1, len(EASY_SEQUENCE_ACTIONS), t(WORKFLOW_LABEL_KEYS.get(first_action, first_action))))
            progress_label.config(text="")
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
        rbtn = easy_run_buttons_list[0] if easy_run_buttons_list else None
        root.after(50, lambda: _poll_easy_sequence(remaining_steps, accumulated, [], q, rbtn, cancel_btn, fill_total, fill_done))

    def _delete_selected_easy(selected_stems: list[str]):
        if not selected_stems or not _queue_use_cases_available:
            if selected_stems and not _queue_use_cases_available:
                messagebox.showerror(t("msg.error"), t("sel.queue_use_cases_unavailable"))
            return
        if not messagebox.askokcancel(t("sel.delete_confirm_title"), t("sel.delete_confirm_msg").format(len(selected_stems)), icon=messagebox.WARNING):
            return
        root_dir = get_project_root()
        articles_dir = get_content_dir() / "articles"
        queue_path = get_content_dir() / "queue.yaml"
        use_cases_path = get_content_dir() / "use_cases.yaml"
        try:
            queue_items = load_existing_queue(queue_path)
            use_cases = load_use_cases(use_cases_path)
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))
            return
        to_remove = set()
        deleted_count = 0
        for stem in selected_stems:
            p = articles_dir / (stem + ".md")
            if p.exists():
                try:
                    p.unlink()
                    deleted_count += 1
                except OSError:
                    pass
            idx = _find_queue_index_by_stem(queue_items, stem)
            if idx is not None:
                to_remove.add(idx)
        removed_entries = [queue_items[i] for i in sorted(to_remove)]
        queue_new = [e for i, e in enumerate(queue_items) if i not in to_remove]
        discarded_count = 0
        for entry in removed_entries:
            uc_idx = _find_use_case_index_by_queue_entry(use_cases, entry)
            if uc_idx is not None:
                use_cases[uc_idx]["status"] = "discarded"
                discarded_count += 1
        save_queue(queue_path, queue_new)
        _save_use_cases(use_cases_path, use_cases)
        try:
            log_area.config(state=tk.NORMAL)
            log_area.insert(tk.END, "\n" + t("sel.deleted_selected_log", deleted_count, discarded_count) + "\n")
            log_area.see(tk.END)
            log_area.config(state=tk.DISABLED)
        except tk.TclError:
            pass
        messagebox.showinfo(t("msg.info"), t("sel.deleted_selected_done", deleted_count, discarded_count))

    btn_fill_queue_easy = ttk.Button(row_btn, text=t("wf.btn_fill_queue"), command=run_fill_queue_easy)
    btn_fill_queue_easy.pack(side=tk.LEFT, padx=(0, 5))
    btn_pick_links_easy = ttk.Button(row_btn, text=t("wf.btn_pick_links"), command=run_pick_links_easy)
    btn_pick_links_easy.pack(side=tk.LEFT, padx=(0, 5))
    btn_generate_fill_easy = ttk.Button(row_btn, text=t("wf.btn_generate_and_fill"), command=run_generate_and_fill_easy)
    btn_generate_fill_easy.pack(side=tk.LEFT, padx=(0, 5))
    preview_btn = ttk.Button(row_btn, text=t("wf.preview_btn"), command=run_preview)
    preview_btn.pack(side=tk.LEFT, padx=(0, 5))
    btn_render_articles = ttk.Button(row_btn, text=t("easy.render_articles"), command=run_render_articles_easy)
    btn_render_articles.pack(side=tk.LEFT, padx=(0, 5))
    cancel_btn = ttk.Button(row_btn, text=t("btn.cancel"), command=cancel_run, state=tk.DISABLED)
    cancel_btn.pack(side=tk.LEFT, padx=5)
    easy_run_buttons_list.extend([btn_fill_queue_easy, btn_pick_links_easy, btn_generate_fill_easy, preview_btn, btn_render_articles])

    def _set_initial_sash():
        paned_h.update_idletasks()
        w = paned_h.winfo_width()
        if w > 100:
            paned_h.sashpos(0, int(0.7 * w))
    f.after(400, _set_initial_sash)
    f.bind("<Map>", lambda e: f.after(100, _set_initial_sash))

    def load_ui():
        if not config_path.exists():
            return
        cfg = load_config(config_path)
        prod = (cfg.get("production_category") or "").strip()
        hub = (cfg.get("hub_slug") or "").strip()
        cats = [prod] if prod else []
        for h in get_hubs_list(cfg) or []:
            if isinstance(h, dict):
                c = (h.get("category") or h.get("slug") or "").strip()
                if c and c not in cats:
                    cats.append(c)
        if hub and hub not in cats:
            cats.append(hub)
        if cats:
            e_prod["values"] = cats
            e_prod.set(prod if prod else cats[0])
            e_hub["values"] = cats
            e_hub.set(hub if hub else (prod or cats[0]))
        mode_raw = (cfg.get("category_mode") or "production_only").strip().lower()
        if mode_raw == "preserve_sandbox":
            e_category_mode.set(t("config.category_mode_preserve_sandbox"))
        else:
            e_category_mode.set(t("config.category_mode_production_only"))
        suggested = cfg.get("suggested_problems") or []
        base_val = suggested[0] if suggested else ""
        e_base.delete(0, tk.END)
        e_base.insert(0, base_val if isinstance(base_val, str) else str(base_val))
        lb_suggested.delete(0, tk.END)
        for s in (suggested[1:] if len(suggested) > 1 else []):
            lb_suggested.insert(tk.END, s if isinstance(s, str) else str(s))
        sandbox = cfg.get("sandbox_categories") or []
        lb_sandbox.delete(0, tk.END)
        for s in sandbox:
            lb_sandbox.insert(tk.END, s if isinstance(s, str) else str(s))
        try:
            e_batch.delete(0, tk.END)
            e_batch.insert(0, str(cfg.get("use_case_batch_size") or 9))
        except tk.TclError:
            pass
        pyramid = cfg.get("use_case_audience_pyramid") or [3, 3]
        batch_int = int(cfg.get("use_case_batch_size") or 9)
        beg_count = int(pyramid[0]) if len(pyramid) >= 1 else 3
        inter_count = int(pyramid[1]) if len(pyramid) >= 2 else 0
        pro_count = batch_int - beg_count - inter_count
        if pro_count < 0:
            pro_count = 0
        try:
            sp_beg.set(beg_count)
            sp_int.set(inter_count)
            sp_pro.set(pro_count)
            _pyr_update_sum_easy()
        except (tk.TclError, ValueError):
            pass
        try:
            var_where_mode.set("one_hub" if bool(cfg.get("use_case_single_hub")) else "multiple_categories")
        except tk.TclError:
            pass
        cta = cfg.get("content_types_all") or []
        lb_content_types_all.delete(0, tk.END)
        for ct in cta:
            lb_content_types_all.insert(tk.END, ct if isinstance(ct, str) else str(ct))
        hubs_data.clear()
        for h in (cfg.get("hubs") or []):
            if isinstance(h, dict):
                hubs_data.append({
                    "slug": (h.get("slug") or "").strip(),
                    "category": (h.get("category") or "").strip(),
                    "title": (h.get("title") or "").strip(),
                })
            elif isinstance(h, str):
                hubs_data.append({"slug": h.strip(), "category": "", "title": ""})
        lb_hubs.delete(0, tk.END)
        for row in hubs_data:
            lb_hubs.insert(tk.END, f"{row.get('slug', '')} | {row.get('category', '')} | {row.get('title', '')}")
        try:
            e_hub_title.delete(0, tk.END)
            e_hub_title.insert(0, (cfg.get("hub_title") or "").strip())
        except tk.TclError:
            pass

    load_ui()
    ttk.Button(row_btn, text=t("btn.refresh_file"), command=load_ui).pack(side=tk.LEFT, padx=5)
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

    # --- Zakres: tryb Starsze niż | Zakres dat (radio), jedna linia podsumowania, licznik ostatniego odświeżenia ---
    lf_scope = ttk.LabelFrame(inner, text=t("refresh.section_scope"))
    lf_scope.pack(fill=tk.X, pady=(0, 10))
    scope_inner = ttk.Frame(lf_scope, padding=5)
    scope_inner.pack(fill=tk.X)

    scope_mode_var = tk.StringVar(value="older")
    row_mode = ttk.Frame(scope_inner)
    row_mode.pack(fill=tk.X)
    ttk.Radiobutton(row_mode, text=t("refresh.scope_mode_older"), variable=scope_mode_var, value="older").pack(side=tk.LEFT, padx=(0, 12))
    ttk.Radiobutton(row_mode, text=t("refresh.scope_mode_dates"), variable=scope_mode_var, value="date_range").pack(side=tk.LEFT)

    row = ttk.Frame(scope_inner)
    row.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(row, text=t("refresh.days_label")).pack(side=tk.LEFT, padx=(0, 5))
    days_combo = ttk.Combobox(row, values=("7", "14", "30", "60", "90"), width=8, state="readonly")
    days_combo.pack(side=tk.LEFT, padx=5)
    days_combo.set("90")
    _hint(row, "refresh.days_desc")

    row_range = ttk.Frame(scope_inner)
    row_range.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(row_range, text=t("refresh.from_date_label")).pack(side=tk.LEFT, padx=(0, 5))
    from_date_entry = ttk.Entry(row_range, width=12)
    from_date_entry.pack(side=tk.LEFT, padx=2)
    ttk.Label(row_range, text=t("refresh.to_date_label")).pack(side=tk.LEFT, padx=(8, 5))
    to_date_entry = ttk.Entry(row_range, width=12)
    to_date_entry.pack(side=tk.LEFT, padx=2)
    today_only_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(row_range, text=t("refresh.today_only"), variable=today_only_var).pack(side=tk.LEFT, padx=(12, 0))
    _hint(row_range, "refresh.date_range_desc")

    limit_values = (t("refresh.limit_none"), "1", "5", "10", "20", "50")
    row_lim = ttk.Frame(scope_inner)
    row_lim.pack(fill=tk.X, pady=(6, 0))
    ttk.Label(row_lim, text=t("refresh.limit_label")).pack(side=tk.LEFT, padx=(0, 5))
    limit_combo = ttk.Combobox(row_lim, values=limit_values, width=12, state="readonly")
    limit_combo.pack(side=tk.LEFT, padx=5)
    limit_combo.set(t("refresh.limit_none"))
    _hint(row_lim, "refresh.limit_desc")

    scope_summary_var = tk.StringVar(value="")
    row_summary = ttk.Frame(scope_inner)
    row_summary.pack(fill=tk.X, pady=(8, 0))
    tk.Label(row_summary, textvariable=scope_summary_var, font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W)
    last_refresh_var = tk.StringVar(value=t("refresh.last_refresh_never"))
    row_last = ttk.Frame(scope_inner)
    row_last.pack(fill=tk.X, pady=(2, 0))
    tk.Label(row_last, textvariable=last_refresh_var, font=italic_font, fg="gray").pack(anchor=tk.W)

    def _update_scope_visibility():
        mode = scope_mode_var.get()
        if mode == "older":
            row.pack(fill=tk.X, pady=(6, 0))
            row_range.pack_forget()
        else:
            row.pack_forget()
            row_range.pack(fill=tk.X, pady=(6, 0))
        _update_scope_summary()

    def _update_scope_summary():
        mode = scope_mode_var.get()
        limit_raw = (limit_combo.get() or "").strip()
        limit_str = "0" if not limit_raw or limit_raw == t("refresh.limit_none") else limit_raw
        if mode == "older":
            days = (days_combo.get() or "90").strip()
            part = f"{t('refresh.days_label').split('(')[0].strip()} {days} {t('refresh.days_unit')}, limit {limit_str}"
            scope_summary_var.set(t("refresh.scope_summary", part))
        else:
            if today_only_var.get():
                part = t("refresh.today_only") + f", limit {limit_str}"
            else:
                fr = (from_date_entry.get() or "").strip() or "?"
                to = (to_date_entry.get() or "").strip() or "?"
                part = t("refresh.from_to", fr, to) + f", limit {limit_str}"
            scope_summary_var.set(t("refresh.scope_summary", part))

    def _update_last_refresh_label():
        root = get_project_root()
        stamp_file = root / "logs" / "last_refresh_started.txt"
        if not stamp_file.exists():
            last_refresh_var.set(t("refresh.last_refresh_never"))
            return
        try:
            raw = stamp_file.read_text(encoding="utf-8").strip()
            if not raw:
                last_refresh_var.set(t("refresh.last_refresh_never"))
                return
            from datetime import date as date_type
            stamp_date = datetime.strptime(raw[:10], "%Y-%m-%d").date()
            days_ago = (date_type.today() - stamp_date).days
            if days_ago == 0:
                last_refresh_var.set(t("refresh.last_refresh", t("refresh.today")))
            else:
                last_refresh_var.set(t("refresh.last_refresh", t("refresh.days_ago", days_ago)))
        except Exception:
            last_refresh_var.set(t("refresh.last_refresh_never"))

    def _write_last_refresh_timestamp():
        root = get_project_root()
        log_dir = root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp_file = log_dir / "last_refresh_started.txt"
        stamp_file.write_text(datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        _update_last_refresh_label()

    def _on_today_only_changed():
        if today_only_var.get():
            today_str = date.today().isoformat()
            from_date_entry.delete(0, tk.END)
            from_date_entry.insert(0, today_str)
            to_date_entry.delete(0, tk.END)
            to_date_entry.insert(0, today_str)
            from_date_entry.config(state=tk.DISABLED)
            to_date_entry.config(state=tk.DISABLED)
        else:
            from_date_entry.config(state=tk.NORMAL)
            to_date_entry.config(state=tk.NORMAL)
        _update_scope_summary()

    today_only_var.trace_add("write", lambda *a: _on_today_only_changed())
    days_combo.bind("<<ComboboxSelected>>", lambda e: _update_scope_summary())
    limit_combo.bind("<<ComboboxSelected>>", lambda e: _update_scope_summary())
    scope_mode_var.trace_add("write", lambda *a: _update_scope_visibility())
    from_date_entry.bind("<KeyRelease>", lambda e: _update_scope_summary())
    to_date_entry.bind("<KeyRelease>", lambda e: _update_scope_summary())
    _update_scope_visibility()
    _update_last_refresh_label()

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
    show_selector_on_done = [False]

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

    def _get_article_status(stem: str) -> str:
        """Return frontmatter status (blocked, filled, etc.) or ''."""
        path = get_content_dir() / "articles" / f"{stem}.md"
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return ""
        if not text.startswith("---"):
            return ""
        end = text.find("\n---", 3)
        if end == -1:
            return ""
        for line in text[3:end].split("\n"):
            mo = re.match(r"^status\s*:\s*(.+)$", line.strip(), re.I)
            if mo:
                val = mo.group(1).strip().strip("'\"")
                if val.lower() == "blocked":
                    return "blocked"
                if val.lower() == "filled":
                    return "in_scope"
                return val.lower() or ""
        return ""

    def _load_failed_stems() -> set[str]:
        failed_file = get_project_root() / "logs" / "last_refresh_failed.txt"
        if not failed_file.exists():
            return set()
        try:
            return {line.strip() for line in failed_file.read_text(encoding="utf-8").splitlines() if line.strip()}
        except OSError:
            return set()

    def _build_merged_refresh_items(dry_run_items: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
        """Merge dry-run list with last_refresh_failed.txt; each item (display, stem, status_key)."""
        failed_stems = _load_failed_stems()
        dry_stems = {stem for _d, stem in dry_run_items}
        out: list[tuple[str, str, str]] = []
        for display, stem in dry_run_items:
            if stem in failed_stems:
                status_key = "failed"
            else:
                fm = _get_article_status(stem)
                status_key = "blocked" if fm == "blocked" else ("in_scope" if fm else "in_scope")
            out.append((display, stem, status_key))
        for stem in sorted(failed_stems - dry_stems):
            out.append((f"{stem}.md", stem, "failed"))
        return out

    def _get_limit_value() -> str:
        raw = (limit_combo.get() or "").strip()
        if not raw or raw == t("refresh.limit_none"):
            return "0"
        return raw

    def _run_selective_refresh(stems: list[str]):
        import tempfile
        tmp = Path(tempfile.mktemp(suffix=".txt", prefix="flowtaro_refresh_"))
        tmp.write_text("\n".join(stems), encoding="utf-8")
        mode = scope_mode_var.get()
        if mode == "date_range":
            if today_only_var.get():
                from_str = to_str = date.today().isoformat()
            else:
                from_str = (from_date_entry.get() or "").strip()
                to_str = (to_date_entry.get() or "").strip()
                if not from_str or not to_str:
                    messagebox.showerror(t("msg.error"), t("refresh.date_range_required"))
                    return
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
            extra = ["--days", (days_combo.get() or "90").strip(), "--include-file", str(tmp)]
        if no_render_var.get():
            extra.append("--no-render")
        _append_common_extra(extra)
        _write_last_refresh_timestamp()
        articles_btn.config(state=tk.DISABLED)
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
        root_w.after(50, lambda: poll(q, articles_btn, cancel_btn, out_lines))

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
        _update_last_refresh_label()
        if code == 0 and show_selector_on_done[0] and out:
            dry_items = _parse_dry_run_articles(out)
            show_selector_on_done[0] = False
            if dry_items:
                merged = _build_merged_refresh_items(dry_items)
                root_w = parent.winfo_toplevel()
                root_w.after(100, lambda: _show_article_selector(
                    root_w, t("sel.title_refresh"), merged,
                    t("sel.confirm_refresh"), _run_selective_refresh,
                    open_public_label=t("sel.preview_public")))
        else:
            show_selector_on_done[0] = False

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

    def run_articles_list():
        limit_val = _get_limit_value()
        mode = scope_mode_var.get()
        if mode == "date_range":
            if today_only_var.get():
                from_str = to_str = date.today().isoformat()
            else:
                from_str = (from_date_entry.get() or "").strip()
                to_str = (to_date_entry.get() or "").strip()
                if not from_str or not to_str:
                    messagebox.showerror(t("msg.error"), t("refresh.date_range_required"))
                    return
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
            extra = ["--days", (days_combo.get() or "90").strip(), "--limit", limit_val]
        extra.append("--dry-run")
        if no_render_var.get():
            extra.append("--no-render")
        _append_common_extra(extra)
        show_selector_on_done[0] = True
        _write_last_refresh_timestamp()
        articles_btn.config(state=tk.DISABLED)
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
        root.after(50, lambda: poll(q, articles_btn, cancel_btn, out_lines))

    def cancel_run():
        if process_holder and isinstance(process_holder[0], tuple):
            _, proc = process_holder[0]
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    articles_btn = ttk.Button(refresh_btn_row, text=t("refresh.btn_articles_to_refresh"), command=run_articles_list)
    articles_btn.pack(side=tk.LEFT, padx=5)
    cancel_btn = ttk.Button(refresh_btn_row, text=t("refresh.run_cancel"), command=cancel_run, state=tk.DISABLED)
    cancel_btn.pack(side=tk.LEFT, padx=5)
    return f


def build_git_tab(parent):
    """Zakładka Publikuj: add content/articles/, commit z komunikatem, push (bez force). Status, walidacje repo i PATH."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    root_dir = get_project_root()
    articles_dir = get_content_dir() / "articles"
    if not articles_dir.is_dir():
        content_root_rel = get_content_root().replace("\\", "/")
        ttk.Label(f, text=f"Błąd: brak {content_root_rel}/articles/", foreground="red").pack(anchor=tk.W)
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
            return ("Publish: timeout.", 124)

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

    # Lewy panel z przewijaniem, żeby sekcje Commit i Push były zawsze widoczne
    canvas = tk.Canvas(left_outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(left_outer, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas, padding=5)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    def _on_canvas_configure(ev):
        canvas.itemconfig(canvas_window, width=ev.width)
    canvas.bind("<Configure>", _on_canvas_configure)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    def _on_mousewheel(ev):
        canvas.yview_scroll(int(-1 * (ev.delta / 120)), tk.UNITS)
    canvas.bind("<MouseWheel>", _on_mousewheel)

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
    commit_placeholder = t("git.commit_message_placeholder")
    commit_entry.insert(0, commit_placeholder)

    def _clear_commit_placeholder():
        if commit_entry.get().strip() == commit_placeholder:
            commit_entry.delete(0, tk.END)

    def _restore_commit_placeholder():
        if not commit_entry.get().strip():
            commit_entry.delete(0, tk.END)
            commit_entry.insert(0, commit_placeholder)

    commit_entry.bind("<FocusIn>", lambda ev: _clear_commit_placeholder())
    commit_entry.bind("<FocusOut>", lambda ev: _restore_commit_placeholder())
    btn_commit = ttk.Button(commit_inner, text=t("git.btn_commit"), command=lambda: _do_commit())
    btn_commit.pack(side=tk.LEFT, padx=5)
    _create_tooltip(btn_commit, t("git.btn_commit_desc"))
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
        rel = get_content_root().replace("\\", "/") + "/articles/"
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
        if not msg or msg == commit_placeholder:
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


def build_config_tab(parent, ideas_tab=None):
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
        from content_index import get_hubs_list, load_config
        from config_manager import write_config
    except ImportError as e:
        ttk.Label(f, text=f"Błąd importu: {e}", foreground="red").pack(anchor=tk.W)
        return f

    italic_font = ("TkDefaultFont", 9, "italic")
    defaults_uc = get_use_case_defaults()
    cat_vals = [t("wf.category_any")] + list(defaults_uc.get("categories", []))
    combo_width = min(30, max((len(str(v)) for v in cat_vals), default=10) + 2)
    combo_width = max(12, combo_width)
    config_entry_width = 60

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
        config_path = get_content_dir() / "config.yaml"
        if not config_path.exists():
            return
        cfg = load_config(config_path)
        prod = (cfg.get("production_category") or "").strip()
        hub = (cfg.get("hub_slug") or "").strip()
        sandbox = cfg.get("sandbox_categories") or []
        category_mode = (cfg.get("category_mode") or "production_only").strip().lower()
        if category_mode not in {"production_only", "preserve_sandbox"}:
            category_mode = "production_only"
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
        hubs_list = get_hubs_list(cfg) if cfg else []
        if hubs_list:
            hub_vals = list(dict.fromkeys([h.get("slug") or h.get("category") or "" for h in hubs_list if isinstance(h, dict)]))
            hub_vals = [s for s in hub_vals if s]
        else:
            hub_vals = list(dict.fromkeys([hub, prod] + [s for s in sandbox if isinstance(s, str) and s.strip()]))
        e_hub["values"] = hub_vals
        e_hub.set(hub or (hub_vals[0] if hub_vals else ""))
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
        _validate_hub()

    def save_ui():
        try:
            config_path = get_content_dir() / "config.yaml"
            cfg = load_config(config_path) if config_path.exists() else {}
            if e_prod.get().strip() == t("config.other"):
                prod = e_prod_other.get().strip() or "ai-marketing-automation"
            else:
                prod = e_prod.get().strip()
                if not prod:
                    prod = (e_prod["values"] or ["ai-marketing-automation"])[0]
            hub = e_hub.get().strip()
            sandbox = [lb_sandbox.get(i) for i in range(lb_sandbox.size()) if lb_sandbox.get(i).strip()]
            mode_display = (e_category_mode.get() or "").strip()
            category_mode = "preserve_sandbox" if mode_display == t("config.category_mode_preserve_sandbox") else "production_only"
            batch = int(cfg.get("use_case_batch_size") or 9)
            pyramid = cfg.get("use_case_audience_pyramid") or [3, 3]
            if not isinstance(pyramid, list) or len(pyramid) < 2:
                pyramid = [3, 3]
            suggested = cfg.get("suggested_problems") or []
            use_case_single_hub = bool(cfg.get("use_case_single_hub"))
            write_config(
                config_path,
                prod,
                hub,
                sandbox,
                use_case_batch_size=batch,
                use_case_audience_pyramid=pyramid[:2],
                suggested_problems=suggested,
                category_mode=category_mode,
                use_case_single_hub=use_case_single_hub,
            )
            # Sync use_case_allowed_categories.json from config (production + sandbox + hubs)
            # so generate_use_cases and workflow category dropdown use up-to-date categories.
            try:
                if str(SCRIPTS_DIR) not in sys.path:
                    sys.path.insert(0, str(SCRIPTS_DIR))
                from generate_use_cases import sync_allowed_categories_file
                sync_allowed_categories_file(config_path, get_content_dir() / "use_case_allowed_categories.json")
            except Exception:
                pass
            messagebox.showinfo(t("msg.saved"), f"{t('config.saved')}\n\n{config_path}")
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))

    # Strona / hub
    lf_hub = ttk.LabelFrame(inner, text=t("config.section_hub"), padding=5)
    lf_hub.pack(fill=tk.X, pady=(0, 10))
    row1 = ttk.Frame(lf_hub)
    row1.pack(fill=tk.X, pady=(0, 2))
    ttk.Label(row1, text=t("config.production"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_prod = ttk.Frame(row1)
    hint_prod.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_prod_hint = tk.Label(hint_prod, text=t("config.production_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_prod_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_prod_hint)
    e_prod = ttk.Combobox(row1, width=config_entry_width, state="readonly")
    e_prod.pack(side=tk.LEFT)
    row1b = ttk.Frame(lf_hub)
    row1b.pack(fill=tk.X, pady=2)
    e_prod_other = ttk.Entry(row1b, width=config_entry_width)
    e_prod_other.pack(side=tk.LEFT, padx=(33, 0), fill=tk.X, expand=True)
    row1b.pack_forget()
    def _on_prod_change():
        if e_prod.get().strip() == t("config.other"):
            row1b.pack(fill=tk.X, pady=2)
        else:
            row1b.pack_forget()
    e_prod.bind("<<ComboboxSelected>>", lambda e: _on_prod_change())
    row2 = ttk.Frame(lf_hub)
    row2.pack(fill=tk.X, pady=(0, 2))
    ttk.Label(row2, text=t("config.hub_slug"), width=28, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
    hint_hub = ttk.Frame(row2)
    hint_hub.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    lbl_hub_hint = tk.Label(hint_hub, text=t("config.hub_slug_desc"), font=italic_font, fg="gray", anchor=tk.W, justify=tk.LEFT, wraplength=450)
    lbl_hub_hint.pack(anchor=tk.W, fill=tk.X, expand=True)
    config_hint_labels.append(lbl_hub_hint)
    e_hub = ttk.Combobox(row2, width=config_entry_width)
    e_hub.pack(side=tk.LEFT)
    hub_validation_lbl = tk.Label(lf_hub, text="", font=italic_font, fg="red", wraplength=520)
    hub_validation_lbl.pack(anchor=tk.W, padx=(33, 0), pady=(0, 0))
    hub_validation_lbl.pack_forget()
    def _validate_hub():
        val = e_hub.get().strip()
        if not val:
            hub_validation_lbl.config(text="")
            hub_validation_lbl.pack_forget()
            return
        if HUB_SLUG_PATTERN.match(val):
            hub_validation_lbl.config(text="")
            hub_validation_lbl.pack_forget()
        else:
            hub_validation_lbl.config(text=t("config.hub_invalid"))
            hub_validation_lbl.pack(anchor=tk.W, padx=(33, 0), pady=(0, 0))
    e_hub.bind("<KeyRelease>", lambda e: _validate_hub())
    e_hub.bind("<<ComboboxSelected>>", lambda e: _validate_hub())

    row2b = ttk.Frame(lf_hub)
    row2b.pack(fill=tk.X, pady=(0, 2))
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
        width=config_entry_width,
        state="readonly",
    )
    e_category_mode.pack(side=tk.LEFT)

    # --- Obszary tematyczne (na dole, tuż nad przyciskami)
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
    row3_grid = ttk.Frame(lf_sand)
    row3_grid.pack(fill=tk.X, pady=(0, 2))
    row3_grid.columnconfigure(0, weight=4)
    row3_grid.columnconfigure(1, weight=6)
    ttk.Label(row3_grid, text=t("config.sub_label_type"), font=("TkDefaultFont", 9), anchor=tk.W).grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
    ttk.Label(row3_grid, text=t("config.sub_label_preview"), font=("TkDefaultFont", 9), anchor=tk.W).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=(0, 2))
    col_sand_left = ttk.Frame(row3_grid)
    col_sand_left.grid(row=1, column=0, sticky=tk.EW)
    e_sandbox_new = ttk.Entry(col_sand_left, width=config_entry_width)
    e_sandbox_new.pack(fill=tk.X, expand=True)
    fr_sandbox = ttk.Frame(row3_grid)
    fr_sandbox.grid(row=1, column=1, sticky=tk.NSEW, padx=(10, 0))
    lb_sandbox = tk.Listbox(fr_sandbox, height=3, width=20)
    lb_sandbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb_sand = ttk.Scrollbar(fr_sandbox, orient=tk.VERTICAL, command=lb_sandbox.yview)
    sb_sand.pack(side=tk.RIGHT, fill=tk.Y)
    lb_sandbox.config(yscrollcommand=sb_sand.set)
    col_sand_btn_left = ttk.Frame(row3_grid)
    col_sand_btn_left.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))
    col_sand_btn_right = ttk.Frame(row3_grid)
    col_sand_btn_right.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=(4, 0))
    ttk.Button(col_sand_btn_left, text=t("btn.add"), width=8, command=lambda: _list_add(lb_sandbox, e_sandbox_new)).pack()
    ttk.Button(col_sand_btn_right, text=t("btn.remove"), width=18, command=lambda: _list_remove_selected(lb_sandbox)).pack()

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
    ttk.Label(f, text=t("links.dialog_desc_pl")).grid(row=3, column=0, sticky=tk.W, pady=2)
    e_desc_pl = ttk.Entry(f, width=45)
    e_desc_pl.grid(row=3, column=1, padx=5, pady=2)
    e_desc_pl.insert(0, initial.get("short_description_pl", ""))
    lbl_desc_pl_hint = tk.Label(f, text=t("links.dialog_desc_pl_hint"), font=("TkDefaultFont", 9, "italic"), fg="gray", wraplength=400, justify=tk.LEFT)
    lbl_desc_pl_hint.grid(row=4, column=1, sticky=tk.W, padx=5, pady=(0, 2))
    ttk.Label(f, text=t("links.dialog_desc")).grid(row=5, column=0, sticky=tk.W, pady=2)
    e_desc = ttk.Entry(f, width=45)
    e_desc.grid(row=5, column=1, padx=5, pady=2)
    e_desc.insert(0, initial.get("short_description_en", ""))
    ttk.Label(f, text=t("links.dialog_action_button_label")).grid(row=6, column=0, sticky=tk.W, pady=2)
    e_action_label = ttk.Entry(f, width=45)
    e_action_label.grid(row=6, column=1, padx=5, pady=2)
    e_action_label.insert(0, initial.get("cta_button_label", ""))
    lbl_action_hint = tk.Label(f, text=t("links.dialog_action_button_label_hint"), font=("TkDefaultFont", 9, "italic"), fg="gray", wraplength=400, justify=tk.LEFT)
    lbl_action_hint.grid(row=7, column=1, sticky=tk.W, padx=5, pady=(0, 4))
    result = [None]

    def ok():
        desc_pl = e_desc_pl.get().strip()
        desc_en = e_desc.get().strip()
        if desc_pl and not desc_en:
            wait_win = tk.Toplevel(win)
            wait_win.title("")
            wait_win.transient(win)
            wait_win.grab_set()
            ttk.Label(wait_win, text=t("links.generating_description")).pack(padx=24, pady=24)
            wait_win.update()
            try:
                translated = translate_pl_to_en(desc_pl)
                if translated:
                    desc_en = translated
            except Exception:
                pass
            try:
                wait_win.destroy()
            except tk.TclError:
                pass
        result[0] = {
            "name": e_name.get().strip(),
            "category": (combo_cat.get() or "general").strip() or "general",
            "affiliate_link": e_link.get().strip(),
            "short_description_pl": desc_pl,
            "short_description_en": desc_en,
            "cta_button_label": e_action_label.get().strip(),
        }
        if not result[0]["name"]:
            messagebox.showwarning(t("msg.warning"), t("msg.name_required"), parent=win)
            return
        win.destroy()

    def cancel():
        win.destroy()

    btn_row = ttk.Frame(f)
    btn_row.grid(row=8, column=0, columnspan=2, pady=15)
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
    """Referral gdy 3. znak '/' w URL ma treść po sobie LUB query (via=, ref=, referrer=); inaczej general."""
    return _category_from_url_impl(url)


def _ensure_description_then_append(root, data: dict, tools_holder: list, refresh_tree) -> None:
    """If data has no short_description_en, call API to generate it (with 'Generating…' window), then append and refresh."""
    data.setdefault("short_description_en", "")
    if (data.get("short_description_en") or "").strip():
        tools_holder.append(data)
        refresh_tree()
        return
    wait_win = tk.Toplevel(root)
    wait_win.title("")
    wait_win.transient(root)
    wait_win.grab_set()
    ttk.Label(wait_win, text=t("links.generating_description")).pack(padx=24, pady=24)
    wait_win.update_idletasks()
    try:
        desc = generate_short_description(data.get("name", ""), data.get("category", ""))
        if desc:
            data["short_description_en"] = desc
    except Exception:
        pass
    finally:
        try:
            wait_win.grab_release()
            wait_win.destroy()
        except tk.TclError:
            pass
    tools_holder.append(data)
    refresh_tree()


def _parse_bulk_link_input(text: str) -> tuple[list[tuple[str, str]], int]:
    """Dzieli wklejony tekst na pary (opis_pl, link). Format: opis; link; opis; link; …
    Zwraca (listę par, liczbę pominiętych nieprawidłowych par)."""
    out: list[tuple[str, str]] = []
    tokens = [t.strip() for t in (text or "").split(";")]
    invalid = 0
    for i in range(0, len(tokens) - 1, 2):
        desc_pl, link = tokens[i], tokens[i + 1]
        if not link:
            invalid += 1
            continue
        if not (link.startswith("http://") or link.startswith("https://")):
            invalid += 1
            continue
        try:
            p = urlparse(link)
            if not p.netloc:
                invalid += 1
                continue
        except Exception:
            invalid += 1
            continue
        out.append((desc_pl, link))
    return out, invalid


def _run_bulk_add_flow(parent, tools_holder: list, refresh_tree):
    """Otwiera dialog z polem tekstowym (format: opis; link; …), parsuje, sprawdza duplikaty, tłumaczy opisy PL→EN i dopisuje do listy."""
    root = parent.winfo_toplevel()
    win = tk.Toplevel(root)
    win.title(t("links.bulk_add_title"))
    win.transient(root)
    win.grab_set()
    f = ttk.Frame(win, padding=15)
    f.pack(fill=tk.BOTH, expand=True)
    ttk.Label(f, text=t("links.bulk_add_prompt"), wraplength=500).pack(anchor=tk.W, pady=(0, 8))
    text_widget = tk.Text(f, width=70, height=14, wrap=tk.WORD)
    text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    result_holder: list[str] = []

    def ok():
        result_holder.append(text_widget.get("1.0", tk.END))
        win.destroy()

    btn_row = ttk.Frame(f)
    btn_row.pack(fill=tk.X)
    ttk.Button(btn_row, text="OK", command=ok).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.cancel"), command=win.destroy).pack(side=tk.LEFT, padx=5)
    win.wait_window()

    if not result_holder:
        return
    raw = result_holder[0]
    pairs, invalid_parsed = _parse_bulk_link_input(raw)
    if not pairs:
        messagebox.showinfo(t("msg.info"), t("links.bulk_add_no_pairs"), parent=root)
        return

    existing_bases = {_normalize_base_url((t.get("affiliate_link") or "")) for t in tools_holder}
    added = 0
    skipped_dup = 0
    progress_win = tk.Toplevel(root)
    progress_win.title("")
    progress_win.transient(root)
    progress_win.grab_set()
    progress_label = ttk.Label(progress_win, text="")
    progress_label.pack(padx=24, pady=24)
    progress_win.update_idletasks()

    for idx, (desc_pl, url) in enumerate(pairs):
        base = _normalize_base_url(url)
        if base in existing_bases:
            skipped_dup += 1
            continue
        progress_label.config(text=t("links.generating_description") + " " + str(idx + 1) + "/" + str(len(pairs)))
        progress_win.update()
        name = _name_from_affiliate_link(url)
        category = _category_from_url(url)
        short_en = ""
        if (desc_pl or "").strip():
            try:
                short_en = (translate_pl_to_en(desc_pl) or "").strip()
            except Exception:
                pass
        data = {
            "name": name,
            "category": category,
            "affiliate_link": url,
            "short_description_pl": (desc_pl or "").strip(),
            "short_description_en": short_en,
            "cta_button_label": "",
        }
        tools_holder.append(data)
        existing_bases.add(base)
        added += 1

    try:
        progress_win.grab_release()
        progress_win.destroy()
    except tk.TclError:
        pass
    refresh_tree()
    messagebox.showinfo(
        t("msg.info"),
        t("links.bulk_add_result", added, skipped_dup, invalid_parsed),
        parent=root,
    )


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
        "short_description_pl": "",
        "short_description_en": "",
        "cta_button_label": "",
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
                _ensure_description_then_append(root, data, tools_holder, refresh_tree)
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
        _ensure_description_then_append(root, suggested, tools_holder, refresh_tree)
        return
    if conf_choice[0] == "edit":
        data = _affiliate_edit_dialog(root, t("links.dialog_add_title"), initial=suggested)
        if data:
            _ensure_description_then_append(root, data, tools_holder, refresh_tree)


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
    tk.Label(f, text=t("links.category_hint"), font=("TkDefaultFont", 9, "italic"), fg="gray", wraplength=620, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 4))
    tree = ttk.Treeview(f, columns=("name", "category", "link_type", "link", "desc_pl", "desc_en"), show="headings", height=16)
    tree.heading("name", text="Nazwa")
    tree.heading("category", text="Kategoria")
    tree.heading("link_type", text=t("links.link_type"))
    tree.heading("link", text="Link")
    tree.heading("desc_pl", text=t("links.dialog_desc_pl"))
    tree.heading("desc_en", text=t("links.dialog_desc"))
    tree.column("name", width=120)
    tree.column("category", width=110)
    tree.column("link_type", width=70)
    tree.column("link", width=200)
    tree.column("desc_pl", width=160)
    tree.column("desc_en", width=160)
    tree.pack(fill=tk.BOTH, expand=True, pady=5)

    def refresh_tree():
        for i in tree.get_children():
            tree.delete(i)
        for tool in tools_holder:
            link = (tool.get("affiliate_link") or "")[:50] + ("…" if len(tool.get("affiliate_link") or "") > 50 else "")
            desc_pl = (tool.get("short_description_pl") or "")[:35] + ("…" if len(tool.get("short_description_pl") or "") > 35 else "")
            desc_en = (tool.get("short_description_en") or "")[:35] + ("…" if len(tool.get("short_description_en") or "") > 35 else "")
            link_type = _link_type_display(tool)
            tree.insert("", tk.END, values=(tool.get("name", ""), tool.get("category", ""), link_type, link, desc_pl, desc_en))

    def _sort_tools():
        """Sort: typ linku malejąco (referral first), kategoria rosnąco, nazwa rosnąco."""
        def _key(t):
            cat = (t.get("category") or "").strip().lower()
            return (1 - (1 if cat == "referral" else 0), (cat or "general"), (t.get("name") or "").strip().lower())
        tools_holder.sort(key=_key)

    def load_from_file():
        tools_holder.clear()
        tools_holder.extend(load_affiliate_tools())
        for tool in tools_holder:
            tool.setdefault("short_description_en", "")
            tool.setdefault("short_description_pl", "")
        _sort_tools()
        refresh_tree()

    def add_tool():
        _run_add_by_link_flow(parent, tools_holder, refresh_tree)

    def bulk_add_tools():
        _run_bulk_add_flow(parent, tools_holder, refresh_tree)

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
            _sort_tools()
            save_affiliate_tools(tools_holder)
            refresh_tree()
            messagebox.showinfo(t("msg.saved"), t("msg.affiliate_saved"), parent=parent.winfo_toplevel())
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e), parent=parent.winfo_toplevel())

    btn_row = ttk.Frame(f)
    btn_row.pack(fill=tk.X, pady=5)
    ttk.Button(btn_row, text=t("btn.refresh_file"), command=load_from_file).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("btn.add"), command=add_tool).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text=t("links.bulk_add"), command=bulk_add_tools).pack(side=tk.LEFT, padx=5)
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


def build_use_cases_tab(parent):
    """Zakładka Use case'y – przegląd, filtr po statusie, zmiana statusu, edycja, usuwanie."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    if not _queue_use_cases_available:
        ttk.Label(f, text=t("uc.unavailable"), foreground="gray", wraplength=500).pack(anchor=tk.W)
        return f

    use_cases_path = get_content_dir() / "use_cases.yaml"
    use_cases_list: list[dict] = []
    filtered_indices: list[int] = []

    ttk.Label(f, text=t("uc.title")).pack(anchor=tk.W)

    top_row = ttk.Frame(f)
    top_row.pack(fill=tk.X, pady=(5, 2))
    ttk.Label(top_row, text=t("uc.col_status") + ":").pack(side=tk.LEFT, padx=(0, 5))
    filter_var = tk.StringVar(value=t("uc.filter_all"))
    filter_combo = ttk.Combobox(
        top_row, textvariable=filter_var, values=(
            t("uc.filter_all"), t("uc.filter_todo"), t("uc.filter_generated"), t("uc.filter_archived"), t("uc.filter_discarded")
        ), state="readonly", width=14
    )
    filter_combo.pack(side=tk.LEFT, padx=(0, 15))

    tree_container = ttk.Frame(f)
    tree_container.pack(fill=tk.BOTH, expand=True, pady=5)
    tree = ttk.Treeview(
        tree_container, columns=("problem", "content_type", "category", "status", "batch"),
        show="headings", height=18, selectmode="extended"
    )
    tree.heading("problem", text=t("uc.col_problem"))
    tree.heading("content_type", text=t("uc.col_content_type"))
    tree.heading("category", text=t("uc.col_category"))
    tree.heading("status", text=t("uc.col_status"))
    tree.heading("batch", text=t("uc.col_batch"))
    tree.column("problem", width=280)
    tree.column("content_type", width=80)
    tree.column("category", width=140)
    tree.column("status", width=80)
    tree.column("batch", width=120)
    tree.pack(fill=tk.BOTH, expand=True)
    empty_msg_lbl = tk.Label(tree_container, text=t("uc.empty_list"), font=("TkDefaultFont", 10), foreground="gray")
    last_read_var = tk.StringVar(value="")
    file_read_row = ttk.Frame(f)
    file_read_row.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(file_read_row, text=t("uc.file_label"), font=("TkDefaultFont", 9), foreground="gray").pack(side=tk.LEFT, padx=(0, 15))
    ttk.Label(file_read_row, textvariable=last_read_var, font=("TkDefaultFont", 9), foreground="gray").pack(side=tk.LEFT)

    def _problem_short(s: str, max_len: int = 50) -> str:
        s = (s or "").strip()
        return (s[: max_len - 3] + "...") if len(s) > max_len else s

    def apply_filter():
        nonlocal filtered_indices
        val = filter_var.get().strip()
        if val == t("uc.filter_todo"):
            status_filter = "todo"
        elif val == t("uc.filter_generated"):
            status_filter = "generated"
        elif val == t("uc.filter_archived"):
            status_filter = "archived"
        elif val == t("uc.filter_discarded"):
            status_filter = "discarded"
        else:
            status_filter = None
        filtered_indices = []
        for i, uc in enumerate(use_cases_list):
            st = (uc.get("status") or "").strip().lower()
            if status_filter is None or st == status_filter:
                filtered_indices.append(i)
        for item in tree.get_children():
            tree.delete(item)
        for pos, idx in enumerate(filtered_indices):
            uc = use_cases_list[idx]
            tree.insert("", tk.END, iid=str(pos), values=(
                _problem_short(uc.get("problem") or ""),
                (uc.get("content_type") or "").strip(),
                (uc.get("category_slug") or "").strip(),
                (uc.get("status") or "").strip(),
                (uc.get("batch_id") or "").strip(),
            ))

    def load_data():
        nonlocal use_cases_list
        try:
            use_cases_list = load_use_cases(use_cases_path) if use_cases_path.exists() else []
        except Exception:
            use_cases_list = []
        last_read_var.set(t("uc.last_read", datetime.now().strftime("%H:%M")))
        if not use_cases_list:
            tree.pack_forget()
            empty_msg_lbl.pack(pady=20)
        else:
            empty_msg_lbl.pack_forget()
            tree.pack(fill=tk.BOTH, expand=True)
            apply_filter()

    def get_selected_indices() -> list[int]:
        sel = tree.selection()
        out = []
        for iid in sel:
            try:
                pos = int(iid)
                if 0 <= pos < len(filtered_indices):
                    out.append(filtered_indices[pos])
            except ValueError:
                pass
        return out

    def change_status():
        indices = get_selected_indices()
        if not indices:
            messagebox.showinfo(t("msg.info"), t("uc.select_first"))
            return
        dialog = tk.Toplevel(f)
        dialog.title(t("uc.status_dialog_title"))
        dialog.transient(f.winfo_toplevel())
        dialog.grab_set()
        ttk.Label(dialog, text=t("uc.status_prompt")).pack(anchor=tk.W, padx=10, pady=(10, 5))
        status_var = tk.StringVar(value="todo")
        fr = ttk.Frame(dialog)
        fr.pack(fill=tk.X, padx=10, pady=5)
        for s in ("todo", "generated", "discarded"):
            ttk.Radiobutton(fr, text=s, variable=status_var, value=s).pack(side=tk.LEFT, padx=(0, 12))
        def ok():
            new_status = status_var.get().strip()
            if len(indices) > 1 and not messagebox.askokcancel(t("msg.info"), t("uc.status_confirm_multi", new_status, len(indices)), icon=messagebox.QUESTION):
                return
            for i in indices:
                use_cases_list[i]["status"] = new_status
            try:
                _save_use_cases(use_cases_path, use_cases_list)
                apply_filter()
                messagebox.showinfo(t("msg.info"), t("uc.saved"))
            except Exception as e:
                messagebox.showerror(t("msg.error"), str(e))
            dialog.destroy()
        btn_row = ttk.Frame(dialog)
        btn_row.pack(pady=10)
        ttk.Button(btn_row, text=t("btn.ok"), command=ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text=t("btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    _content_type_allowed = get_content_types_all()

    def edit_one():
        indices = get_selected_indices()
        if not indices:
            messagebox.showinfo(t("msg.info"), t("uc.select_first"))
            return
        idx = indices[0]
        uc = use_cases_list[idx]
        categories = (get_use_case_defaults().get("categories") or ["ai-marketing-automation"])[:]
        dialog = tk.Toplevel(f)
        dialog.title(t("uc.edit_title"))
        dialog.transient(f.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("420x280")
        fields = {}
        row = ttk.Frame(dialog, padding=5)
        row.pack(fill=tk.X)
        ttk.Label(row, text=t("uc.problem"), width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        fields["problem"] = tk.Entry(row, width=45)
        fields["problem"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        fields["problem"].insert(0, (uc.get("problem") or "").strip())
        row = ttk.Frame(dialog, padding=5)
        row.pack(fill=tk.X)
        ttk.Label(row, text=t("uc.col_content_type"), width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        fields["content_type"] = ttk.Combobox(row, values=list(_content_type_allowed), width=42, state="readonly")
        ct_val = (uc.get("content_type") or "guide").strip().lower()
        fields["content_type"].set(ct_val if ct_val in _content_type_allowed else "guide")
        fields["content_type"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        row = ttk.Frame(dialog, padding=5)
        row.pack(fill=tk.X)
        ttk.Label(row, text=t("uc.category_slug"), width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        fields["category_slug"] = ttk.Combobox(row, values=categories, width=42, state="readonly")
        cur_cat = (uc.get("category_slug") or "").strip()
        fields["category_slug"].set(cur_cat if cur_cat in categories else (categories[0] if categories else ""))
        fields["category_slug"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        row = ttk.Frame(dialog, padding=5)
        row.pack(fill=tk.X)
        ttk.Label(row, text=t("uc.audience_type"), width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        fields["audience_type"] = tk.Entry(row, width=45)
        fields["audience_type"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        fields["audience_type"].insert(0, (uc.get("audience_type") or "").strip())
        row = ttk.Frame(dialog, padding=5)
        row.pack(fill=tk.X)
        ttk.Label(row, text=t("uc.batch_id"), width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        fields["batch_id"] = tk.Entry(row, width=45)
        fields["batch_id"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        fields["batch_id"].insert(0, (uc.get("batch_id") or "").strip())

        def ok():
            uc["problem"] = fields["problem"].get().strip()
            ct = (fields["content_type"].get() or "").strip().lower()
            uc["content_type"] = ct if ct in _content_type_allowed else "guide"
            if "suggested_content_type" in uc:
                del uc["suggested_content_type"]
            cat = (fields["category_slug"].get() or "").strip()
            if not cat and categories:
                cat = categories[0]
            if not cat:
                messagebox.showwarning(t("msg.info"), t("uc.category_required"))
                return
            uc["category_slug"] = cat
            aud = fields["audience_type"].get().strip()
            if aud:
                uc["audience_type"] = aud
            elif "audience_type" in uc:
                del uc["audience_type"]
            bid = fields["batch_id"].get().strip()
            if bid:
                uc["batch_id"] = bid
            elif "batch_id" in uc:
                del uc["batch_id"]
            try:
                _save_use_cases(use_cases_path, use_cases_list)
                apply_filter()
                messagebox.showinfo(t("msg.info"), t("uc.saved"))
            except Exception as e:
                messagebox.showerror(t("msg.error"), str(e))
            dialog.destroy()

        btn_row = ttk.Frame(dialog)
        btn_row.pack(pady=10)
        ttk.Button(btn_row, text=t("btn.ok"), command=ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text=t("btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def delete_selected():
        indices = get_selected_indices()
        if not indices:
            messagebox.showinfo(t("msg.info"), t("uc.select_first"))
            return
        n = len(indices)
        msg = t("uc.delete_confirm") if n == 1 else t("uc.delete_confirm_multi", n)
        if not messagebox.askokcancel(t("msg.info"), msg, icon=messagebox.WARNING):
            return
        for i in sorted(indices, reverse=True):
            use_cases_list.pop(i)
        try:
            _save_use_cases(use_cases_path, use_cases_list)
            apply_filter()
            messagebox.showinfo(t("msg.info"), t("uc.saved"))
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))

    filter_combo.bind("<<ComboboxSelected>>", lambda e: apply_filter())

    btn_row = ttk.Frame(f)
    btn_row.pack(anchor=tk.W, pady=5)
    ttk.Button(btn_row, text=t("uc.refresh_list"), command=load_data).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text=t("uc.change_status"), command=change_status).pack(side=tk.LEFT, padx=(0, 8))
    edit_btn = ttk.Button(btn_row, text=t("uc.edit"), command=edit_one)
    edit_btn.pack(side=tk.LEFT, padx=(0, 8))
    _create_tooltip(edit_btn, t("uc.edit_tooltip"))
    ttk.Button(btn_row, text=t("uc.delete"), command=delete_selected).pack(side=tk.LEFT)

    tk.Label(f, text=t("uc.hint_status"), font=("TkDefaultFont", 9, "italic"), foreground="gray", wraplength=600, justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 0))
    tk.Label(f, text=t("uc.hint_discarded"), font=("TkDefaultFont", 9, "italic"), foreground="gray", wraplength=600, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))

    f.bind("<F5>", lambda e: load_data())
    f.bind("<Control-r>", lambda e: load_data())
    load_data()
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
    tree = ttk.Treeview(
        f, columns=("slug", "tools"), show="headings", height=20, selectmode="extended"
    )
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

    def copy_selected():
        sel = tree.selection()
        if not sel:
            return
        lines = []
        for item_id in sel:
            vals = tree.item(item_id, "values")
            if len(vals) >= 2:
                lines.append(f"{vals[0]}\t{vals[1]}")
            elif len(vals) == 1:
                lines.append(vals[0])
        if lines:
            text = "\n".join(lines)
            root = tree.winfo_toplevel()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            messagebox.showinfo(t("mapping.copy_selected"), t("mapping.copied_n", len(lines)))

    btn_row = ttk.Frame(f)
    btn_row.pack(anchor=tk.W, pady=5)
    ttk.Button(btn_row, text=t("btn.refresh"), command=refresh).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text=t("mapping.copy_selected"), command=copy_selected).pack(side=tk.LEFT)
    ttk.Label(f, text=t("mapping.copy_hint"), font=("TkDefaultFont", 9, "italic"), foreground="gray").pack(anchor=tk.W)
    tree.bind("<Control-c>", lambda e: copy_selected())
    tree.bind("<Control-C>", lambda e: copy_selected())
    refresh()
    return f


def build_clean_non_live_tab(parent):
    """Zakładka Czyszczenie nieżywych: zakres (content/public/both), podgląd (dry-run), wykonaj."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    ttk.Label(f, text=t("clean.title"), font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
    ttk.Label(f, text=t("clean.desc"), wraplength=700, justify=tk.LEFT, foreground="gray").pack(anchor=tk.W, pady=(4, 12))

    scope_var = tk.StringVar(value="both")
    row_scope = ttk.Frame(f)
    row_scope.pack(anchor=tk.W, pady=(0, 8))
    ttk.Label(row_scope, text=t("clean.scope")).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Radiobutton(row_scope, text=t("clean.scope_both"), variable=scope_var, value="both").pack(side=tk.LEFT, padx=(0, 12))
    ttk.Radiobutton(row_scope, text=t("clean.scope_content"), variable=scope_var, value="content_only").pack(side=tk.LEFT, padx=(0, 12))
    ttk.Radiobutton(row_scope, text=t("clean.scope_public"), variable=scope_var, value="public_only").pack(side=tk.LEFT)

    def build_args(dry_run: bool) -> list[str]:
        args = ["--archive"]
        if dry_run:
            args.append("--dry-run")
        else:
            args.append("--confirm")
        if scope_var.get() == "content_only":
            args.append("--content-only")
        elif scope_var.get() == "public_only":
            args.append("--public-only")
        return args

    out_text = scrolledtext.ScrolledText(f, height=16, wrap=tk.WORD, state=tk.NORMAL, font=("Consolas", 9))
    out_text.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

    def run_and_show(dry_run: bool):
        out_text.delete("1.0", tk.END)
        out_text.insert(tk.END, "Uruchamianie…\n")
        f.update_idletasks()
        args = build_args(dry_run)
        out, code = run_script("clean_non_live_articles.py", args, timeout_seconds=120)
        out_text.delete("1.0", tk.END)
        out_text.insert(tk.END, out if out else "(brak outputu)")
        if code != 0:
            out_text.insert(tk.END, f"\n\n[Kod powrotu: {code}]")

    def do_preview():
        run_and_show(dry_run=True)

    def do_execute():
        if not messagebox.askyesno(t("msg.warning"), t("clean.execute_confirm"), icon=messagebox.WARNING):
            return
        run_and_show(dry_run=False)
        messagebox.showinfo(t("msg.info"), t("clean.done_hint"))

    btn_row = ttk.Frame(f)
    btn_row.pack(anchor=tk.W)
    ttk.Button(btn_row, text=t("clean.preview"), command=do_preview).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text=t("clean.execute"), command=do_execute).pack(side=tk.LEFT)

    # --- Remove by date (same output area) ---
    sep = ttk.Separator(f, orient=tk.HORIZONTAL)
    sep.pack(fill=tk.X, pady=(20, 12))
    ttk.Label(f, text=t("clean.by_date_title"), font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
    ttk.Label(f, text=t("clean.by_date_desc"), wraplength=700, justify=tk.LEFT, foreground="gray").pack(anchor=tk.W, pady=(4, 8))
    row_date = ttk.Frame(f)
    row_date.pack(anchor=tk.W, pady=(0, 8))
    ttk.Label(row_date, text=t("clean.by_date_from"), width=22, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 8))
    by_date_from_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(row_date, textvariable=by_date_from_var, width=12).pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(row_date, text=t("clean.by_date_to"), width=8, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 4))
    by_date_to_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(row_date, textvariable=by_date_to_var, width=12).pack(side=tk.LEFT, padx=(0, 8))

    def do_by_date_articles():
        date_f = (by_date_from_var.get() or "").strip()[:10]
        date_t = (by_date_to_var.get() or "").strip()[:10]
        try:
            datetime.strptime(date_f, "%Y-%m-%d")
            datetime.strptime(date_t, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror(t("msg.info"), t("clean.by_date_invalid_date"))
            return
        out_text.delete("1.0", tk.END)
        out_text.insert(tk.END, "Wczytywanie listy…\n")
        f.update_idletasks()
        out, code = run_script("remove_articles_by_date.py", ["--date-from", date_f, "--date-to", date_t, "--list-stems"], timeout_seconds=60)
        stems = [s.strip() for s in (out or "").strip().splitlines() if s.strip()]
        if not stems:
            out_text.delete("1.0", tk.END)
            out_text.insert(tk.END, t("clean.by_date_none"))
            messagebox.showinfo(t("msg.info"), t("clean.by_date_none"))
            return
        out_text.delete("1.0", tk.END)
        out_text.insert(tk.END, t("clean.by_range_loaded", len(stems)))

        def execute_removal(selected: list):
            if not selected:
                messagebox.showinfo(t("msg.info"), t("clean.by_range_none_selected"))
                return
            if not messagebox.askyesno(t("msg.warning"), t("clean.by_range_confirm", len(selected)), icon=messagebox.WARNING):
                return
            out_text.delete("1.0", tk.END)
            out_text.insert(tk.END, "Uruchamianie…\n")
            f.update_idletasks()
            args = ["--stems", ",".join(selected), "--confirm"]
            out, code = run_script("remove_articles_by_date.py", args, timeout_seconds=120)
            out_text.delete("1.0", tk.END)
            out_text.insert(tk.END, out if out else "(brak outputu)")
            if code != 0:
                out_text.insert(tk.END, f"\n\n[Kod powrotu: {code}]")
            messagebox.showinfo(t("msg.info"), t("clean.by_range_done"))

        root = f.winfo_toplevel()
        items = [(stem, stem) for stem in stems]
        root.after(100, lambda: _show_article_selector(
            root, t("clean.by_date_dialog_title"), items,
            t("clean.by_date_confirm_btn"), execute_removal,
            description_text=t("clean.by_range_loaded", len(stems))))

    btn_row_date = ttk.Frame(f)
    btn_row_date.pack(anchor=tk.W)
    ttk.Button(btn_row_date, text=t("clean.by_date_btn_articles"), command=do_by_date_articles).pack(side=tk.LEFT)

    # --- Remove by date range with selection ---
    sep2 = ttk.Separator(f, orient=tk.HORIZONTAL)
    sep2.pack(fill=tk.X, pady=(20, 12))
    ttk.Label(f, text=t("clean.by_range_title"), font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
    ttk.Label(f, text=t("clean.by_range_desc"), wraplength=700, justify=tk.LEFT, foreground="gray").pack(anchor=tk.W, pady=(4, 8))
    ttk.Label(f, text=t("clean.preview_skeletons_hint"), wraplength=700, justify=tk.LEFT, foreground="gray", font=("TkDefaultFont", 9, "italic")).pack(anchor=tk.W, pady=(0, 8))
    row_range = ttk.Frame(f)
    row_range.pack(anchor=tk.W, pady=(0, 4))
    ttk.Label(row_range, text=t("clean.by_range_from"), width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 4))
    date_from_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(row_range, textvariable=date_from_var, width=12).pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(row_range, text=t("clean.by_range_to"), width=8, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 4))
    date_to_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(row_range, textvariable=date_to_var, width=12).pack(side=tk.LEFT, padx=(0, 8))

    range_stems: list[str] = []

    lb_frame = ttk.Frame(f)
    lb_frame.pack(anchor=tk.W, fill=tk.BOTH, expand=True, pady=(4, 4))
    range_listbox = tk.Listbox(lb_frame, height=8, selectmode=tk.EXTENDED, font=("Consolas", 9))
    range_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    range_scroll = ttk.Scrollbar(lb_frame, orient=tk.VERTICAL, command=range_listbox.yview)
    range_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    range_listbox.config(yscrollcommand=range_scroll.set)

    def load_range_list():
        nonlocal range_stems
        date_f = (date_from_var.get() or "").strip()[:10]
        date_t = (date_to_var.get() or "").strip()[:10]
        try:
            datetime.strptime(date_f, "%Y-%m-%d")
            datetime.strptime(date_t, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror(t("msg.info"), t("clean.by_date_invalid_date"))
            return
        out, code = run_script("remove_articles_by_date.py", ["--date-from", date_f, "--date-to", date_t, "--list-stems"], timeout_seconds=60)
        range_stems = [s.strip() for s in (out or "").strip().splitlines() if s.strip()]
        range_listbox.delete(0, tk.END)
        for s in range_stems:
            range_listbox.insert(tk.END, s)
        out_text.delete("1.0", tk.END)
        out_text.insert(tk.END, t("clean.by_range_loaded", len(range_stems)))

    def range_select_all():
        range_listbox.selection_set(0, tk.END)

    def range_deselect_all():
        range_listbox.selection_clear(0, tk.END)

    def run_by_range(dry_run: bool):
        sel = list(range_listbox.curselection())
        if not sel:
            out_text.delete("1.0", tk.END)
            out_text.insert(tk.END, t("clean.by_range_none_selected"))
            return
        stems_to_remove = [range_listbox.get(i) for i in sel]
        stems_arg = ",".join(stems_to_remove)
        out_text.delete("1.0", tk.END)
        out_text.insert(tk.END, "Uruchamianie…\n")
        f.update_idletasks()
        args = ["--stems", stems_arg, "--dry-run"] if dry_run else ["--stems", stems_arg, "--confirm"]
        out, code = run_script("remove_articles_by_date.py", args, timeout_seconds=120)
        out_text.delete("1.0", tk.END)
        out_text.insert(tk.END, out if out else "(brak outputu)")
        if code != 0:
            out_text.insert(tk.END, f"\n\n[Kod powrotu: {code}]")
        if not dry_run and code == 0:
            for i in reversed(sel):
                range_listbox.delete(i)
            range_stems[:] = [range_listbox.get(i) for i in range(range_listbox.size())]

    def do_by_range_preview():
        run_by_range(dry_run=True)

    def do_by_range_execute():
        sel = list(range_listbox.curselection())
        if not sel:
            messagebox.showinfo(t("msg.info"), t("clean.by_range_none_selected"))
            return
        n = len(sel)
        if not messagebox.askyesno(t("msg.warning"), t("clean.by_range_confirm", n), icon=messagebox.WARNING):
            return
        run_by_range(dry_run=False)
        messagebox.showinfo(t("msg.info"), t("clean.by_range_done"))

    row_range_btn = ttk.Frame(f)
    row_range_btn.pack(anchor=tk.W, pady=(4, 0))
    ttk.Button(row_range_btn, text=t("clean.by_range_load"), command=load_range_list).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(row_range_btn, text=t("clean.by_range_select_all"), command=range_select_all).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Button(row_range_btn, text=t("clean.by_range_deselect_all"), command=range_deselect_all).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(row_range_btn, text=t("clean.by_range_preview"), command=do_by_range_preview).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(row_range_btn, text=t("clean.by_range_execute"), command=do_by_range_execute).pack(side=tk.LEFT)

    return f


def build_articles_report_tab(parent):
    """Zakładka Raport artykułów: Treeview + odśwież + otwórz raport HTML w przeglądarce."""
    f = ttk.Frame(parent, padding=10)
    f.pack(fill=tk.BOTH, expand=True)

    ok, err = validate_project_root()
    if not ok:
        ttk.Label(f, text=f"Błąd: {err}", foreground="red").pack(anchor=tk.W)
        return f

    ttk.Label(f, text=t("report.title")).pack(anchor=tk.W)
    tree = ttk.Treeview(
        f,
        columns=("stem", "status", "last_updated", "content_type", "audience", "lang", "has_html", "last_error"),
        show="headings",
        height=18,
        selectmode="extended",
    )
    tree.heading("stem", text=t("report.col_stem"))
    tree.heading("status", text=t("report.col_status"))
    tree.heading("last_updated", text=t("report.col_last_updated"))
    tree.heading("content_type", text=t("report.col_content_type"))
    tree.heading("audience", text=t("report.col_audience"))
    tree.heading("lang", text=t("report.col_lang"))
    tree.heading("has_html", text=t("report.col_has_html"))
    tree.heading("last_error", text=t("report.col_last_error"))
    for col, w in [("stem", 220), ("status", 70), ("last_updated", 95), ("content_type", 90), ("audience", 90), ("lang", 40), ("has_html", 45), ("last_error", 200)]:
        tree.column(col, width=w)
    tree.pack(fill=tk.BOTH, expand=True, pady=5)

    status_var = tk.StringVar(value="")
    content_type_var = tk.StringVar(value="")
    lang_var = tk.StringVar(value="")
    filter_frame = ttk.Frame(f)
    filter_frame.pack(anchor=tk.W, pady=(0, 5))
    ttk.Label(filter_frame, text=t("report.filter_status")).pack(side=tk.LEFT, padx=(0, 6))
    status_combo = ttk.Combobox(filter_frame, textvariable=status_var, values=("", "draft", "filled", "blocked"), width=10, state="readonly")
    status_combo.pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(filter_frame, text=t("report.filter_content_type")).pack(side=tk.LEFT, padx=(0, 6))
    content_type_combo = ttk.Combobox(
        filter_frame, textvariable=content_type_var,
        values=("", "sales", "product-comparison", "best-in-category", "category-products", "guide", "how-to", "best", "comparison", "review"),
        width=18, state="readonly"
    )
    content_type_combo.pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(filter_frame, text=t("report.filter_lang")).pack(side=tk.LEFT, padx=(0, 6))
    lang_combo = ttk.Combobox(filter_frame, textvariable=lang_var, values=("", "en", "pl"), width=6, state="readonly")
    lang_combo.pack(side=tk.LEFT)

    def apply_filter_and_refresh():
        for i in tree.get_children():
            tree.delete(i)
        status_filter = (status_var.get() or "").strip().lower()
        content_type_filter = (content_type_var.get() or "").strip().lower()
        lang_filter = (lang_var.get() or "").strip().lower()
        for row in get_article_report_data():
            if status_filter and (row.get("status") or "").strip().lower() != status_filter:
                continue
            if content_type_filter and (row.get("content_type") or "").strip().lower() != content_type_filter:
                continue
            if lang_filter and (row.get("lang") or "").strip().lower() != lang_filter:
                continue
            tree.insert("", tk.END, values=(
                row.get("stem", ""),
                row.get("status", ""),
                row.get("last_updated", ""),
                row.get("content_type", ""),
                row.get("audience_type", ""),
                row.get("lang", ""),
                "✓" if row.get("has_html") else "—",
                row.get("last_error", ""),
            ))
        _update_open_article_btn_state()

    def open_report_in_browser():
        data = get_article_report_data()
        report_path = LOGS_DIR / "articles_report.html"
        try:
            build_articles_report_html(data, report_path)
            webbrowser.open(report_path.as_uri())
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))

    def open_article_public():
        sel = tree.selection()
        if len(sel) != 1:
            messagebox.showinfo(t("msg.info"), t("report.select_one_article"))
            return
        item = tree.item(sel[0])
        vals = item.get("values") or ()
        stem = (vals[0] or "").strip() if vals else ""
        if not stem:
            messagebox.showinfo(t("msg.info"), t("report.open_article_public_no_file"))
            return
        path = get_public_article_html_path(stem)
        if path.exists():
            webbrowser.open(path.as_uri())
        else:
            messagebox.showinfo(t("msg.info"), t("report.open_article_public_no_file"))

    def _update_open_article_btn_state(*_):
        open_article_btn.state(["!disabled"] if len(tree.selection()) == 1 else ["disabled"])

    def delete_selected_articles():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo(t("msg.info"), t("report.select_one_article"))
            return
        stems = []
        for item_id in sel:
            item = tree.item(item_id)
            vals = item.get("values") or ()
            stem = (vals[0] or "").strip() if vals else ""
            if stem:
                stems.append(stem)
        if not stems:
            return
        if not messagebox.askokcancel(
            t("report.delete_confirm_title"),
            t("report.delete_confirm_msg").format(len(stems)),
            icon=messagebox.WARNING,
        ):
            return
        root_dir = get_project_root()
        articles_dir = get_content_dir() / "articles"
        queue_path = get_content_dir() / "queue.yaml"
        use_cases_path = get_content_dir() / "use_cases.yaml"
        out_dir_name = "public_pl" if get_content_root().replace("\\", "/") == "content/pl" else "public"
        public_articles_dir = root_dir / out_dir_name / "articles"
        if not load_existing_queue or not save_queue or not load_use_cases or not _save_use_cases:
            messagebox.showerror(t("msg.error"), "Queue/use_cases module unavailable.")
            return
        try:
            queue_items = load_existing_queue(queue_path)
            use_cases = load_use_cases(use_cases_path)
        except Exception as e:
            messagebox.showerror(t("msg.error"), str(e))
            return
        to_remove = set()
        for stem in stems:
            for ext in (".md", ".html"):
                p = articles_dir / (stem + ext)
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            pub_dir = public_articles_dir / stem
            if pub_dir.is_dir():
                try:
                    import shutil as _shutil
                    _shutil.rmtree(pub_dir)
                except OSError:
                    pass
            idx = _find_queue_index_by_stem(queue_items, stem)
            if idx is not None:
                to_remove.add(idx)
        removed_entries = [queue_items[i] for i in sorted(to_remove)]
        queue_new = [e for i, e in enumerate(queue_items) if i not in to_remove]
        discarded_count = 0
        for entry in removed_entries:
            uc_idx = _find_use_case_index_by_queue_entry(use_cases, entry)
            if uc_idx is not None:
                use_cases[uc_idx]["status"] = "discarded"
                discarded_count += 1
        save_queue(queue_path, queue_new)
        _save_use_cases(use_cases_path, use_cases)
        apply_filter_and_refresh()
        messagebox.showinfo(t("msg.info"), t("report.deleted_done").format(len(stems), discarded_count))

    btn_row = ttk.Frame(f)
    btn_row.pack(anchor=tk.W, pady=5)
    ttk.Button(btn_row, text=t("report.refresh"), command=apply_filter_and_refresh).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text=t("report.open_html"), command=open_report_in_browser).pack(side=tk.LEFT, padx=(0, 8))
    open_article_btn = ttk.Button(btn_row, text=t("report.open_article_public"), command=open_article_public, state="disabled")
    open_article_btn.pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text=t("report.delete_selected"), command=delete_selected_articles).pack(side=tk.LEFT)
    tree.bind("<<TreeviewSelect>>", _update_open_article_btn_state)
    status_combo.bind("<<ComboboxSelected>>", lambda e: apply_filter_and_refresh())
    content_type_combo.bind("<<ComboboxSelected>>", lambda e: apply_filter_and_refresh())
    lang_combo.bind("<<ComboboxSelected>>", lambda e: apply_filter_and_refresh())
    apply_filter_and_refresh()
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

    # Etykiety głównych sekcji (LabelFrame): powiększenie i pogrubienie
    style = ttk.Style()
    try:
        style.configure("TLabelframe.Label", font=("TkDefaultFont", 10, "bold"))
    except tk.TclError:
        pass

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
        tab_use_cases = build_use_cases_tab(nb)
        nb.add(tab_use_cases, text=t("tab.use_cases"))
        tab_work = build_workflow_tab(nb, last_output_holder)
        nb.add(tab_work, text=t("tab.workflow"))
        tab_easy_work = build_easy_workflow_tab(nb, last_output_holder)
        nb.add(tab_easy_work, text=t("tab.easy_workflow"))
        tab_refresh = build_refresh_tab(nb, last_output_holder)
        nb.add(tab_refresh, text=t("tab.refresh"))
        tab_git = build_git_tab(nb)
        nb.add(tab_git, text=t("tab.git"))
        tab_mapping = build_mapping_tab(nb)
        nb.add(tab_mapping, text=t("tab.mapping"))
        tab_articles_report = build_articles_report_tab(nb)
        nb.add(tab_articles_report, text=t("tab.articles_report"))
        tab_clean_non_live = build_clean_non_live_tab(nb)
        nb.add(tab_clean_non_live, text=t("tab.clean_non_live"))
        tab_affiliate = build_affiliate_tab(nb)
        nb.add(tab_affiliate, text=t("tab.affiliate"))
        tab_dash, dash_refresh = build_dashboard_tab(nb)
        nb.add(tab_dash, text=t("tab.stats"))
        return dash_refresh

    def switch_content_root_en():
        set_content_root("content")
        new_dash = build_all_tabs()
        refresh_menus(new_dash)

    def switch_content_root_pl():
        ok, err = validate_content_root_pl(get_project_root())
        if not ok:
            messagebox.showerror(t("msg.error"), err or "Brak content/pl/ lub content/pl/config.yaml – nie przełączono na PL.")
            return
        set_content_root("content/pl")
        new_dash = build_all_tabs()
        refresh_menus(new_dash)

    def refresh_menus(dash_refresh):
        file_menu.delete(0, tk.END)
        file_menu.add_command(label=t("menu.choose_folder"), command=choose_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Pracuj na: EN (content)", command=switch_content_root_en)
        file_menu.add_command(label="Pracuj na: PL (content/pl)", command=switch_content_root_pl)
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
