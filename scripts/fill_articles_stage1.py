#!/usr/bin/env python3
"""
Stage 1 article fill (without Prompt #2 generation).

This script runs fill_articles.py in "content fill" mode and explicitly disables
Prompt #2 generation. It is intended for a two-step workflow:
1) fill_articles_stage1.py  -> generate article content + Prompt #1
2) fill_prompt2.py          -> generate Prompt #2 only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 1 fill: generate article content without Prompt #2.",
    )
    parser.add_argument("--slug_contains", metavar="TEXT", help="Only process filenames containing this text.")
    parser.add_argument("--limit", type=int, default=1, metavar="N", help="Process at most N files (default: 1).")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model for stage 1 fill.")
    parser.add_argument("--quality_retries", type=int, default=2, metavar="N", help="Quality-gate retries.")
    parser.add_argument("--no-quality-gate", action="store_true", help="Disable quality gate in stage 1.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    parser.add_argument("--force", action="store_true", help="Force fill even if status is already filled.")
    parser.add_argument("--remap", action="store_true", help="Force re-selection of tools.")
    args = parser.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    fill_script = scripts_dir / "fill_articles.py"
    if not fill_script.exists():
        print(f"Error: {fill_script} not found.")
        sys.exit(1)

    cmd = [sys.executable, str(fill_script), "--html", "--skip-prompt2", "--model", args.model, "--limit", str(args.limit)]
    if args.slug_contains:
        cmd.extend(["--slug_contains", args.slug_contains])
    if args.dry_run:
        cmd.append("--qa")
    else:
        cmd.extend(["--write", "--qa"])
    if args.force:
        cmd.append("--force")
    if args.remap:
        cmd.append("--remap")
    if not args.no_quality_gate:
        cmd.extend(["--quality_gate", "--quality_retries", str(args.quality_retries)])

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
