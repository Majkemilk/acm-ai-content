#!/usr/bin/env python3
"""
Content root dla wariantu 4D: ścieżka do content (EN) lub content/pl (PL).
Źródło: env CONTENT_ROOT lub argument --content-root. Domyślnie: content.
"""
import os
from pathlib import Path

DEFAULT_CONTENT_ROOT = "content"


def get_content_root_path(project_root: Path, content_root_arg: str | None = None) -> Path:
    """
    Zwraca Path do katalogu content root.
    content_root_arg: z argparse (args.content_root) lub None.
    Gdy None, czyta os.environ.get("CONTENT_ROOT", "content").
    """
    raw = content_root_arg or os.environ.get("CONTENT_ROOT", DEFAULT_CONTENT_ROOT)
    raw = (raw or "").strip() or DEFAULT_CONTENT_ROOT
    return (project_root / raw).resolve()


def get_affiliate_tools_path(project_root: Path) -> Path:
    """Ścieżka do affiliate_tools.yaml – zawsze z content/ (współdzielony EN/PL)."""
    return project_root / "content" / "affiliate_tools.yaml"
