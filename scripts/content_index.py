#!/usr/bin/env python3
"""
Content index helper: loads config and article metadata, exposes production-only list
for hubs, sitemap, RSS. Stdlib only.
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "content" / "config.yaml"
ARTICLES_DIR = PROJECT_ROOT / "content" / "articles"


def load_config(path: Path | None = None) -> dict:
    """
    Load content/config.yaml. Returns dict with production_category (str) and
    sandbox_categories (list[str]). Uses minimal YAML/JSON parsing (no deps).
    """
    p = path or CONFIG_PATH
    if not p.exists() or p.stat().st_size == 0:
        return {"production_category": "ai-marketing-automation", "sandbox_categories": []}
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return {"production_category": "ai-marketing-automation", "sandbox_categories": []}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {
                "production_category": data.get("production_category") or "ai-marketing-automation",
                "hub_slug": (data.get("hub_slug") or "ai-marketing-automation").strip(),
                "sandbox_categories": data.get("sandbox_categories") or [],
            }
    except json.JSONDecodeError:
        pass
    # Simple YAML: top-level key: value and sandbox_categories as list
    out: dict = {"production_category": "ai-marketing-automation", "hub_slug": "ai-marketing-automation", "sandbox_categories": []}
    in_list = False
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if in_list:
            if stripped.startswith("-"):
                val = stripped[1:].strip().strip('"\'')
                if val:
                    out["sandbox_categories"].append(val)
            else:
                in_list = False
        if not in_list and ":" in stripped:
            key, _, rest = stripped.partition(":")
            key, rest = key.strip(), rest.strip()
            if key == "production_category":
                out["production_category"] = rest.strip('"\'').strip() or out["production_category"]
            elif key == "hub_slug":
                out["hub_slug"] = rest.strip('"\'').strip() or out["hub_slug"]
            elif key == "sandbox_categories":
                in_list = True
                if rest and rest != "|":
                    first = rest.strip().strip('"\'')
                    if first.startswith("-"):
                        first = first[1:].strip().strip('"\'')
                    if first:
                        out["sandbox_categories"].append(first)
    return out


def _parse_frontmatter(path: Path) -> dict | None:
    """Parse frontmatter from a markdown file. Returns dict with title, slug, content_type, category, last_updated."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    block = content[3:end].strip()
    data: dict[str, str] = {"slug": path.stem}
    for line in block.split("\n"):
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1].replace('\\"', '"')
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        data[key] = raw
    return data


def _parse_html_frontmatter_from_comment(content: str) -> dict | None:
    """Parse frontmatter from the first HTML comment (<!-- key: value ... -->). Returns dict or None."""
    m = re.match(r"\s*<!--\s*(.*?)\s*-->", content, re.DOTALL)
    if not m:
        return None
    block = m.group(1).strip()
    data: dict[str, str] = {}
    for line in block.split("\n"):
        m2 = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line.strip())
        if not m2:
            continue
        key, raw = m2.group(1), m2.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1].replace('\\"', '"')
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        data[key] = raw
    return data if data else None


def get_production_articles(
    articles_dir: Path | None = None,
    config_path: Path | None = None,
) -> list[tuple[dict, Path]]:
    """
    Load all article metadata from articles_dir and return all articles that are
    not blocked (status != "blocked"). Category is not used; all non-blocked
    articles are treated as production. Returns list of (meta, path).
    """
    dir_path = articles_dir or ARTICLES_DIR
    if not dir_path.exists():
        return []
    # Collect paths: prefer .html over .md for same stem
    by_stem: dict[str, Path] = {}
    for path in dir_path.iterdir():
        if not path.is_file():
            continue
        if path.suffix == ".md":
            by_stem.setdefault(path.stem, path)
        elif path.suffix == ".html":
            by_stem[path.stem] = path  # overwrite so .html wins
    out: list[tuple[dict, Path]] = []
    for path in sorted(by_stem.values(), key=lambda p: p.name):
        if path.suffix == ".html":
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = _parse_html_frontmatter_from_comment(content)
            if not meta:
                continue
            meta.setdefault("slug", path.stem)
        else:
            meta = _parse_frontmatter(path)
            if not meta:
                continue
        if (meta.get("status") or "").strip().lower() == "blocked":
            continue
        out.append((meta, path))
    return out
