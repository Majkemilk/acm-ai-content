#!/usr/bin/env python3
"""
CLI do zarządzania content/config.yaml: odczyt, ustawienie pól, dodawanie/usuwanie
kategorii sandbox, inicjalizacja pliku. Zgodne z docs/analysis_config_management_script.md.
Uruchom z katalogu głównego projektu: python scripts/manage_config.py ...
"""

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config_manager import (  # noqa: E402
    CONFIG_KEYS,
    FRIENDLY_NAMES,
    get_config_value,
    init_config,
    update_config,
)

CONFIG_PATH = _PROJECT_ROOT / "content" / "config.yaml"


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Zarządzanie content/config.yaml (Główny plik huba, Adres huba, Kategorie do pomysłów).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help=f"Ścieżka do pliku config (domyślnie: content/config.yaml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Wyświetl wynik jako JSON (dla --get)",
    )
    # Get
    parser.add_argument(
        "--get",
        choices=list(CONFIG_KEYS),
        metavar="KEY",
        help="Odczytaj wartość: production_category, hub_slug, sandbox_categories, suggested_problems",
    )
    # Set
    parser.add_argument(
        "--production-category",
        type=str,
        metavar="VALUE",
        help="Ustaw Główny plik huba (production_category)",
    )
    parser.add_argument(
        "--hub-slug",
        type=str,
        metavar="VALUE",
        help="Ustaw Adres huba (hub_slug); zostanie znormalizowany do slugu",
    )
    parser.add_argument(
        "--sandbox-categories",
        type=str,
        metavar="A,B,C",
        help="Nadpisz Kategorie do pomysłów (lista po przecinku)",
    )
    # Add/Remove sandbox
    parser.add_argument(
        "--add-sandbox-category",
        type=str,
        metavar="NAME",
        help="Dodaj jedną kategorię do sandbox_categories",
    )
    parser.add_argument(
        "--remove-sandbox-category",
        type=str,
        metavar="NAME",
        help="Usuń jedną kategorię z sandbox_categories",
    )
    parser.add_argument(
        "--suggested-problems",
        type=str,
        metavar="A,B,C",
        help="Nadpisz sugerowane problemy (lista po przecinku; dla generowania use case’ów)",
    )
    # Init
    parser.add_argument(
        "--init",
        action="store_true",
        help="Utwórz config z wartościami domyślnymi, jeśli plik nie istnieje",
    )

    args = parser.parse_args()
    path = args.config.resolve()

    # --init
    if args.init:
        if init_config(path):
            print("Utworzono config z wartościami domyślnymi.", file=sys.stderr)
        else:
            print("Plik config już istnieje; nic nie zmieniono.", file=sys.stderr)
        return

    # Require config to exist for other operations (except --init)
    if not path.exists():
        print(f"Błąd: Brak pliku {path}. Użyj --init, aby utworzyć.", file=sys.stderr)
        sys.exit(1)

    # --get
    if args.get:
        try:
            val = get_config_value(path, args.get)
        except ValueError as e:
            print(f"Błąd: {e}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({args.get: val}, ensure_ascii=False))
        else:
            name = FRIENDLY_NAMES.get(args.get, args.get)
            if isinstance(val, list):
                for v in val:
                    print(v)
            else:
                print(val)
        return

    # Mutating operations
    has_change = any([
        args.production_category is not None,
        args.hub_slug is not None,
        args.sandbox_categories is not None,
        args.add_sandbox_category is not None,
        args.remove_sandbox_category is not None,
        args.suggested_problems is not None,
    ])
    if not has_change:
        parser.print_help()
        return
    try:
        sandbox_list = None
        if args.sandbox_categories is not None:
            sandbox_list = [p.strip() for p in args.sandbox_categories.split(",") if p.strip()]
        suggested_list = None
        if args.suggested_problems is not None:
            suggested_list = [p.strip() for p in args.suggested_problems.split(",") if p.strip()]
        update_config(
            path,
            production_category=args.production_category,
            hub_slug=args.hub_slug,
            sandbox_categories=sandbox_list,
            add_sandbox=args.add_sandbox_category,
            remove_sandbox=args.remove_sandbox_category,
            suggested_problems=suggested_list,
        )
        if not args.json:
            print("Zaktualizowano config.", file=sys.stderr)
    except ValueError as e:
        print(f"Błąd: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main()
