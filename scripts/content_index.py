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


def _default_config() -> dict:
    return {
        "production_category": "ai-marketing-automation",
        "hub_slug": "ai-marketing-automation",
        "hub_title": "AI Marketing Automation Tools & Workflows",
        "sandbox_categories": [],
        "use_case_batch_size": 9,
        "use_case_audience_pyramid": [3, 3],
        "suggested_problems": [],
        "category_mode": "production_only",
        "hubs": None,
        "content_types_all": [
            "how-to", "guide", "best", "comparison", "review",
            "sales", "product-comparison", "best-in-category", "category-products",
        ],
    }


def _inject_hubs_from_data(data: dict, out: dict) -> None:
    """If data has a valid 'hubs' list (from JSON), set out['hubs']; else leave out['hubs'] unset (None)."""
    raw = data.get("hubs")
    if raw is None:
        out["hubs"] = None
        return
    if isinstance(raw, list) and len(raw) > 0:
        hubs = []
        for h in raw:
            if not isinstance(h, dict):
                continue
            slug = (h.get("slug") or h.get("category") or "").strip()
            category = (h.get("category") or slug or "").strip()
            title = (h.get("title") or "").strip()
            if slug or category:
                hubs.append({"slug": slug or category, "category": category or slug, "title": title or slug})
        out["hubs"] = hubs if hubs else None
        return
    if isinstance(raw, str):
        try:
            arr = json.loads(raw.strip().strip("'\""))
            if isinstance(arr, list) and len(arr) > 0:
                hubs = []
                for h in arr:
                    if not isinstance(h, dict):
                        continue
                    slug = (h.get("slug") or h.get("category") or "").strip()
                    category = (h.get("category") or slug or "").strip()
                    title = (h.get("title") or "").strip()
                    if slug or category:
                        hubs.append({"slug": slug or category, "category": category or slug, "title": title or slug})
                out["hubs"] = hubs if hubs else None
                return
        except (json.JSONDecodeError, TypeError):
            pass
    out["hubs"] = None


def get_hubs_list(config: dict) -> list[dict]:
    """
    Return list of hub dicts: [{"slug", "category", "title"}, ...].
    If config has a non-empty "hubs" list, return it; else return a single hub
    from production_category, hub_slug, and hub_title (for backward compatibility).
    """
    hubs = config.get("hubs")
    if hubs and isinstance(hubs, list) and len(hubs) > 0:
        return hubs
    slug = (config.get("hub_slug") or "ai-marketing-automation").strip()
    category = (config.get("production_category") or "ai-marketing-automation").strip()
    title = (config.get("hub_title") or "AI Marketing Automation Tools & Workflows").strip()
    return [{"slug": slug, "category": category, "title": title}]


def load_config(path: Path | None = None) -> dict:
    """
    Load content/config.yaml. Returns dict with production_category (str) and
    sandbox_categories (list[str]). Uses minimal YAML/JSON parsing (no deps).
    """
    p = path or CONFIG_PATH
    if not p.exists() or p.stat().st_size == 0:
        return _default_config()
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return _default_config()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            pyramid = data.get("use_case_audience_pyramid")
            if not isinstance(pyramid, list):
                pyramid = [3, 3]
            pyramid = [int(x) for x in pyramid if isinstance(x, (int, float))]
            if not pyramid:
                pyramid = [3, 3]
            suggested = data.get("suggested_problems")
            if not isinstance(suggested, list):
                suggested = []
            else:
                suggested = [str(x).strip() for x in suggested if str(x).strip()]
            category_mode = str(data.get("category_mode") or "production_only").strip().lower()
            if category_mode not in {"production_only", "preserve_sandbox"}:
                category_mode = "production_only"
            out = {
                "production_category": data.get("production_category") or "ai-marketing-automation",
                "hub_slug": (data.get("hub_slug") or "ai-marketing-automation").strip(),
                "hub_title": (data.get("hub_title") or "AI Marketing Automation Tools & Workflows").strip(),
                "sandbox_categories": data.get("sandbox_categories") or [],
                "use_case_batch_size": int(data["use_case_batch_size"]) if isinstance(data.get("use_case_batch_size"), (int, float)) else 9,
                "use_case_audience_pyramid": pyramid,
                "suggested_problems": suggested,
                "category_mode": category_mode,
            }
            _inject_hubs_from_data(data, out)
            raw_ct = data.get("content_types_all")
            if isinstance(raw_ct, list) and len(raw_ct) > 0:
                out["content_types_all"] = [str(x).strip() for x in raw_ct if str(x).strip()]
            else:
                out["content_types_all"] = _default_config().get("content_types_all", [])[:]
            return out
    except (json.JSONDecodeError, ValueError):
        pass
    # Simple YAML: top-level key: value and list keys
    out: dict = _default_config().copy()
    in_list = False
    list_key: str | None = None
    hubs_list: list[dict] = []
    current_hub: dict = {}
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if in_list and list_key:
            if list_key == "hubs":
                if stripped.startswith("-"):
                    if current_hub and (current_hub.get("slug") or current_hub.get("category")):
                        hubs_list.append({
                            "slug": (current_hub.get("slug") or current_hub.get("category") or "").strip() or "ai-marketing-automation",
                            "category": (current_hub.get("category") or current_hub.get("slug") or "").strip() or "ai-marketing-automation",
                            "title": (current_hub.get("title") or current_hub.get("slug") or current_hub.get("category") or "").strip(),
                        })
                    current_hub = {}
                    after_dash = stripped[1:].strip()
                    if ":" in after_dash:
                        k, _, v = after_dash.partition(":")
                        k, v = k.strip(), v.strip().strip('"\'').strip()
                        if k in ("slug", "category", "title"):
                            current_hub[k] = v
                elif ":" in stripped:
                    k, _, v = stripped.partition(":")
                    k, v = k.strip(), v.strip().strip('"\'').strip()
                    if k in ("slug", "category", "title"):
                        current_hub[k] = v
                    else:
                        in_list = False
                        if current_hub and (current_hub.get("slug") or current_hub.get("category")):
                            hubs_list.append({
                                "slug": (current_hub.get("slug") or current_hub.get("category") or "").strip() or "ai-marketing-automation",
                                "category": (current_hub.get("category") or current_hub.get("slug") or "").strip() or "ai-marketing-automation",
                                "title": (current_hub.get("title") or current_hub.get("slug") or current_hub.get("category") or "").strip(),
                            })
                        out["hubs"] = hubs_list if hubs_list else None
                        list_key = None
                else:
                    in_list = False
                    if current_hub and (current_hub.get("slug") or current_hub.get("category")):
                        hubs_list.append({
                            "slug": (current_hub.get("slug") or current_hub.get("category") or "").strip() or "ai-marketing-automation",
                            "category": (current_hub.get("category") or current_hub.get("slug") or "").strip() or "ai-marketing-automation",
                            "title": (current_hub.get("title") or current_hub.get("slug") or current_hub.get("category") or "").strip(),
                        })
                    out["hubs"] = hubs_list if hubs_list else None
                    list_key = None
            elif stripped.startswith("-"):
                val = stripped[1:].strip().strip('"\'')
                if val and list_key == "sandbox_categories":
                    out["sandbox_categories"].append(val)
                elif val and list_key == "use_case_audience_pyramid":
                    try:
                        out["use_case_audience_pyramid"].append(int(val))
                    except ValueError:
                        pass
                elif list_key == "suggested_problems":
                    out["suggested_problems"].append(val)  # allow empty string (no HARD LOCK)
                elif val and list_key == "content_types_all":
                    out.setdefault("content_types_all", []).append(val)
            else:
                if list_key == "hubs" and current_hub and (current_hub.get("slug") or current_hub.get("category")):
                    hubs_list.append({
                        "slug": (current_hub.get("slug") or current_hub.get("category") or "").strip() or "ai-marketing-automation",
                        "category": (current_hub.get("category") or current_hub.get("slug") or "").strip() or "ai-marketing-automation",
                        "title": (current_hub.get("title") or current_hub.get("slug") or current_hub.get("category") or "").strip(),
                    })
                    out["hubs"] = hubs_list if hubs_list else None
                in_list = False
                list_key = None
        if not in_list and ":" in stripped:
            key, _, rest = stripped.partition(":")
            key, rest = key.strip(), rest.strip()
            if key == "production_category":
                out["production_category"] = rest.strip('"\'').strip() or out["production_category"]
            elif key == "hub_slug":
                out["hub_slug"] = rest.strip('"\'').strip() or out["hub_slug"]
            elif key == "hub_title":
                out["hub_title"] = rest.strip('"\'').strip() or out["hub_title"]
            elif key == "hubs":
                raw = rest.strip().strip('"\'').strip()
                if raw and raw.startswith("["):
                    try:
                        arr = json.loads(raw)
                        if isinstance(arr, list) and len(arr) > 0:
                            hubs = []
                            for h in arr:
                                if not isinstance(h, dict):
                                    continue
                                slug = (h.get("slug") or h.get("category") or "").strip()
                                category = (h.get("category") or slug or "").strip()
                                title = (h.get("title") or "").strip()
                                if slug or category:
                                    hubs.append({"slug": slug or category, "category": category or slug, "title": title or slug})
                            out["hubs"] = hubs if hubs else None
                        else:
                            out["hubs"] = None
                    except (json.JSONDecodeError, TypeError):
                        out["hubs"] = None
                else:
                    in_list = True
                    list_key = "hubs"
                    hubs_list = []
                    current_hub = {}
            elif key == "use_case_batch_size":
                try:
                    out["use_case_batch_size"] = int(rest.strip())
                except ValueError:
                    pass
            elif key == "sandbox_categories":
                in_list = True
                list_key = "sandbox_categories"
                if rest and rest != "|":
                    first = rest.strip().strip('"\'')
                    if first.startswith("-"):
                        first = first[1:].strip().strip('"\'')
                    if first:
                        out["sandbox_categories"].append(first)
            elif key == "use_case_audience_pyramid":
                in_list = True
                list_key = "use_case_audience_pyramid"
                out["use_case_audience_pyramid"] = []
                if rest and rest != "|":
                    try:
                        first = rest.strip().strip('"\'')
                        if first.startswith("-"):
                            first = first[1:].strip().strip('"\'')
                        if first:
                            out["use_case_audience_pyramid"].append(int(first))
                    except ValueError:
                        pass
            elif key == "suggested_problems":
                in_list = True
                list_key = "suggested_problems"
                out["suggested_problems"] = []
                if rest and rest.strip() != "[]" and rest != "|":
                    first = rest.strip().strip('"\'')
                    if first.startswith("-"):
                        first = first[1:].strip().strip('"\'')
                    if first and first != "[]":
                        out["suggested_problems"].append(first)
            elif key == "category_mode":
                mode = rest.strip('"\'').strip().lower()
                out["category_mode"] = mode if mode in {"production_only", "preserve_sandbox"} else "production_only"
            elif key == "content_types_all":
                in_list = True
                list_key = "content_types_all"
                out["content_types_all"] = []
                if rest and rest != "|":
                    first = rest.strip().strip('"\'')
                    if first.startswith("-"):
                        first = first[1:].strip().strip('"\'')
                    if first:
                        out["content_types_all"].append(first)
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
    Load all article metadata from articles_dir and return only articles with
    status "filled" (production-ready). Blocked and draft/skeleton articles
    are excluded so they are not rendered to public. Returns list of (meta, path).
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
        status = (meta.get("status") or "").strip().lower()
        if status == "blocked":
            continue
        if status != "filled":
            continue
        out.append((meta, path))
    return out
