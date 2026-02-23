#!/usr/bin/env python3
"""
Config manager for content/config.yaml. Provides load, get, set, add/remove
sandbox categories, and write with validation. For use by CLI (manage_config.py)
and future FlowMonitor integration. Stdlib only.
"""

import re
from pathlib import Path

from content_index import load_config  # noqa: E402

# Keys and defaults (must match content_index.load_config contract)
CONFIG_KEYS = ("production_category", "hub_slug", "sandbox_categories", "suggested_problems", "category_mode")
DEFAULT_PRODUCTION_CATEGORY = "ai-marketing-automation"
DEFAULT_HUB_SLUG = "ai-marketing-automation"
DEFAULT_CATEGORY_MODE = "production_only"
HUB_SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")


def _quote_yaml_value(s: str) -> str:
    """Quote a string for YAML if it contains special chars."""
    s = str(s)
    if "\n" in s or ":" in s or '"' in s or s.startswith("#"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return f'"{s}"'


def _normalize_hub_slug(value: str) -> str:
    """Normalize to slug: lowercase, spaces and underscores to hyphens, strip invalid."""
    s = (value or "").strip().lower().replace(" ", "-").replace("_", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    return re.sub(r"[^a-z0-9-]", "", s) or DEFAULT_HUB_SLUG


def _validate_production_category(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("production_category (Główny plik huba) nie może być pusty")
    return v


def _validate_hub_slug(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("hub_slug (Adres huba) nie może być pusty")
    normalized = _normalize_hub_slug(v)
    if not HUB_SLUG_PATTERN.match(normalized):
        raise ValueError("hub_slug może zawierać tylko małe litery, cyfry i myślniki")
    return normalized


def _validate_sandbox_categories(value: list) -> list:
    if not isinstance(value, list):
        raise ValueError("sandbox_categories musi być listą")
    out = []
    seen = set()
    for item in value:
        s = (str(item) or "").strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _validate_category_mode(value: str) -> str:
    v = (value or "").strip().lower()
    if v not in {"production_only", "preserve_sandbox"}:
        raise ValueError("category_mode musi mieć wartość: production_only lub preserve_sandbox")
    return v


def write_config(
    path: Path,
    production_category: str,
    hub_slug: str,
    sandbox_categories: list[str],
    use_case_batch_size: int | None = None,
    use_case_audience_pyramid: list[int] | None = None,
    suggested_problems: list[str] | None = None,
    category_mode: str | None = None,
) -> None:
    """
    Write content/config.yaml. Preserves use_case_batch_size, use_case_audience_pyramid,
    and suggested_problems from existing file when not provided. No comments preserved.
    """
    production_category = _validate_production_category(production_category)
    hub_slug = _validate_hub_slug(hub_slug)
    sandbox_categories = _validate_sandbox_categories(
        sandbox_categories if sandbox_categories is not None else []
    )
    existing: dict = {}
    if path.exists():
        existing = load_config(path)
    if use_case_batch_size is None:
        use_case_batch_size = int(existing.get("use_case_batch_size", 9))
    if use_case_audience_pyramid is None:
        p = existing.get("use_case_audience_pyramid")
        use_case_audience_pyramid = [int(x) for x in p] if isinstance(p, list) and p else [3, 3]
    if suggested_problems is None:
        suggested_problems = list(existing.get("suggested_problems") or [])
    else:
        suggested_problems = [str(x).strip() for x in suggested_problems if str(x).strip()]
    if category_mode is None:
        category_mode = str(existing.get("category_mode") or DEFAULT_CATEGORY_MODE).strip().lower()
    category_mode = _validate_category_mode(category_mode)
    lines = [
        f"production_category: {_quote_yaml_value(production_category)}",
        f"hub_slug: {_quote_yaml_value(hub_slug)}",
        f"category_mode: {_quote_yaml_value(category_mode)}",
        "sandbox_categories:",
    ]
    for cat in sandbox_categories:
        lines.append(f'  - {_quote_yaml_value(cat)}')
    lines.append(f"use_case_batch_size: {int(use_case_batch_size)}")
    lines.append("use_case_audience_pyramid:")
    for n in use_case_audience_pyramid:
        lines.append(f"  - {int(n)}")
    lines.append("suggested_problems:")
    for prob in suggested_problems:
        lines.append(f'  - {_quote_yaml_value(prob)}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_config_value(path: Path, key: str):
    """
    Return current value for one key. path: path to config.yaml.
    key: production_category | hub_slug | sandbox_categories | suggested_problems | category_mode.
    """
    if key not in CONFIG_KEYS:
        raise ValueError(f"Nieznany klucz: {key}. Dozwolone: {list(CONFIG_KEYS)}")
    config = load_config(path)
    if key == "hub_slug":
        return config.get("hub_slug") or DEFAULT_HUB_SLUG
    if key == "suggested_problems":
        return list(config.get("suggested_problems") or [])
    if key == "category_mode":
        mode = str(config.get("category_mode") or DEFAULT_CATEGORY_MODE).strip().lower()
        return mode if mode in {"production_only", "preserve_sandbox"} else DEFAULT_CATEGORY_MODE
    return config.get(key) if config.get(key) is not None else (
        [] if key == "sandbox_categories" else (DEFAULT_PRODUCTION_CATEGORY if key == "production_category" else None)
    )


def _validate_suggested_problems(value: list) -> list:
    if not isinstance(value, list):
        raise ValueError("suggested_problems musi być listą")
    return [str(x).strip() for x in value if str(x).strip()]


def set_config_value(path: Path, key: str, value) -> None:
    """
    Set one key and write config. value: str for production_category/hub_slug,
    list[str] for sandbox_categories / suggested_problems, str for category_mode.
    Validates and normalizes (hub_slug).
    """
    if key not in CONFIG_KEYS:
        raise ValueError(f"Nieznany klucz: {key}. Dozwolone: {list(CONFIG_KEYS)}")
    config = load_config(path)
    prod = (config.get("production_category") or DEFAULT_PRODUCTION_CATEGORY).strip()
    hub = (config.get("hub_slug") or DEFAULT_HUB_SLUG).strip()
    sandbox = list(config.get("sandbox_categories") or [])
    suggested = list(config.get("suggested_problems") or [])
    category_mode = str(config.get("category_mode") or DEFAULT_CATEGORY_MODE).strip().lower()

    if key == "production_category":
        prod = _validate_production_category(str(value))
    elif key == "hub_slug":
        hub = _validate_hub_slug(str(value))
    elif key == "sandbox_categories":
        sandbox = _validate_sandbox_categories(value if isinstance(value, list) else [])
    elif key == "suggested_problems":
        suggested = _validate_suggested_problems(value if isinstance(value, list) else [])
    elif key == "category_mode":
        category_mode = _validate_category_mode(str(value))
    write_config(path, prod, hub, sandbox, suggested_problems=suggested, category_mode=category_mode)


def add_sandbox_category(path: Path, category: str) -> bool:
    """
    Append one category to sandbox_categories (no duplicate). Returns True if added.
    """
    category = (category or "").strip()
    if not category:
        raise ValueError("Kategoria nie może być pusta")
    config = load_config(path)
    sandbox = list(config.get("sandbox_categories") or [])
    if any(c.strip() == category for c in sandbox):
        return False
    sandbox.append(category)
    prod = (config.get("production_category") or DEFAULT_PRODUCTION_CATEGORY).strip()
    hub = (config.get("hub_slug") or DEFAULT_HUB_SLUG).strip()
    write_config(path, prod, hub, sandbox)
    return True


def remove_sandbox_category(path: Path, category: str) -> bool:
    """
    Remove one category from sandbox_categories (first match, case-sensitive).
    Returns True if removed.
    """
    category = (category or "").strip()
    config = load_config(path)
    sandbox = list(config.get("sandbox_categories") or [])
    try:
        sandbox.remove(category)
    except ValueError:
        return False
    prod = (config.get("production_category") or DEFAULT_PRODUCTION_CATEGORY).strip()
    hub = (config.get("hub_slug") or DEFAULT_HUB_SLUG).strip()
    write_config(path, prod, hub, sandbox)
    return True


def init_config(path: Path) -> bool:
    """
    Create config with defaults if file does not exist. Returns True if created.
    """
    if path.exists() and path.stat().st_size > 0:
        return False
    write_config(
        path,
        DEFAULT_PRODUCTION_CATEGORY,
        DEFAULT_HUB_SLUG,
        [],
    )
    return True


def update_config(
    path: Path,
    *,
    production_category: str | None = None,
    hub_slug: str | None = None,
    sandbox_categories: list[str] | None = None,
    add_sandbox: str | None = None,
    remove_sandbox: str | None = None,
    suggested_problems: list[str] | None = None,
    category_mode: str | None = None,
) -> bool:
    """
    Load config, apply optional overrides (set/add/remove), write. Returns True if written.
    For FlowMonitor or CLI: pass only the keys to change.
    """
    config = load_config(path)
    prod = (config.get("production_category") or DEFAULT_PRODUCTION_CATEGORY).strip()
    hub = (config.get("hub_slug") or DEFAULT_HUB_SLUG).strip()
    sandbox = list(config.get("sandbox_categories") or [])
    suggested = list(config.get("suggested_problems") or [])
    mode = str(config.get("category_mode") or DEFAULT_CATEGORY_MODE).strip().lower()

    if production_category is not None:
        prod = _validate_production_category(production_category)
    if hub_slug is not None:
        hub = _validate_hub_slug(hub_slug)
    if sandbox_categories is not None:
        sandbox = _validate_sandbox_categories(sandbox_categories)
    if suggested_problems is not None:
        suggested = _validate_suggested_problems(suggested_problems)
    if category_mode is not None:
        mode = _validate_category_mode(category_mode)
    if add_sandbox is not None:
        add_sandbox = add_sandbox.strip()
        if add_sandbox and add_sandbox not in sandbox:
            sandbox.append(add_sandbox)
    if remove_sandbox is not None:
        remove_sandbox = remove_sandbox.strip()
        if remove_sandbox in sandbox:
            sandbox.remove(remove_sandbox)

    write_config(path, prod, hub, sandbox, suggested_problems=suggested, category_mode=mode)
    return True


# User-friendly names for messages (FlowMonitor / CLI)
FRIENDLY_NAMES = {
    "production_category": "Główny plik huba",
    "hub_slug": "Adres huba (slug)",
    "sandbox_categories": "Kategorie do pomysłów",
    "suggested_problems": "Sugerowane problemy (do use case’ów)",
    "category_mode": "Tryb kategorii artykułów",
}
