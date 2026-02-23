#!/usr/bin/env python3
"""
Stage 2 Prompt #2 generation (only).

This script runs fill_articles.py in --prompt2-only mode, so it only reads
already generated .html files, extracts Prompt #1, and writes Prompt #2.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 2: generate Prompt #2 only for articles with placeholder.",
    )
    parser.add_argument("--slug_contains", metavar="TEXT", help="Only process filenames containing this text.")
    parser.add_argument("--limit", type=int, default=1, metavar="N", help="Process at most N files (default: 1).")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model for Prompt #2 generation (default: gpt-4o).")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    args = parser.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    fill_script = scripts_dir / "fill_articles.py"
    if not fill_script.exists():
        print(f"Error: {fill_script} not found.")
        sys.exit(1)

    cmd = [
        sys.executable,
        str(fill_script),
        "--prompt2-only",
        "--model",
        args.model,
        "--limit",
        str(args.limit),
    ]
    if args.slug_contains:
        cmd.extend(["--slug_contains", args.slug_contains])
    if not args.dry_run:
        cmd.append("--write")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
