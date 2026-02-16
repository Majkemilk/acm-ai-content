# AI Content Automation

This project generates **SEO articles automatically** from YAML input files.

- **Articles** are stored as markdown files (e.g. under `content/articles/`).
- The system is **template-first**: content is produced from templates and structured input to ensure consistency and reduce hallucinations.

## Structure

- `content/` — Input and generated content (e.g. `queue.yaml`, `articles/`).
- `templates/` — Article and other content templates.
- `scripts/` — Automation and generation scripts.

No framework or dependencies are required for the initial setup.

## Sandbox policy

**Sandbox categories** (e.g. `seo`) are for test/regression content only. They are **never** included in production outputs.

- Articles with `category: seo` (or any category listed in `content/config.yaml` under `sandbox_categories`) are excluded from hubs, sitemap, and RSS.
- Production outputs use only `production_category` from `content/config.yaml` (e.g. `ai-marketing-automation`).
- You can keep sandbox articles in `content/articles/` for testing; they will not appear in generated hubs or future sitemap/RSS.

## Taxonomy

Category and content type are **strictly normalized** to keep the project aligned with the niche and prevent drift.

- **Category:** Only `ai-marketing-automation` is allowed. Common aliases in the queue (e.g. `seo`, `marketing-automation`, `automation`, `ai-automation`) are mapped to it. Any other value is normalized to `ai-marketing-automation`. Written frontmatter always uses the canonical category.
- **Content type:** Allowed values are `review`, `comparison`, `best`, `how-to`, `guide`. If missing, the generator uses `guide`. If a value is not in the list, it is reset to `guide` and a warning is printed. Frontmatter always contains one of the allowed values.

## Internal linking

The generator fills `{{INTERNAL_LINKS}}` automatically from existing articles in `content/articles/` (no external or affiliate URLs).

**Selection rules (priority order):**

1. Same `category` / `category_slug` as the new article → up to 3 links.
2. Same `primary_tool` → up to 2 more (if not already chosen).
3. Same `content_type` → up to 1 more.

The article never links to itself. If fewer than 3 matches exist, only available links are added; missing links are left as placeholders. Order is deterministic (by article slug).

**URL convention:** Internal links use paths of the form `/articles/{filename-without-extension}/` (e.g. `/articles/2025-02-14-choose-seo-tool/`). Routing is not implemented; the generator only emits these paths for consistency.

## Category hubs

Hub pages list articles by category and content type. Generate them with:

```bash
python scripts/generate_hubs.py
```

Output is written to `content/hubs/` (e.g. `content/hubs/ai-marketing-automation.md`). **Hub URL convention:** `/hubs/ai-marketing-automation/` (path without file extension; routing is not implemented).

## Sitemap

Generate a production-only sitemap:

```bash
python scripts/generate_sitemap.py
```

- **Output:** `public/sitemap.xml`
- Includes only production content (via `content/config.yaml`): hub URL `/hubs/{production_category}/` plus all production articles as `/articles/{slug}/`. Sandbox categories are excluded (uses `get_production_articles()` from `scripts/content_index.py`).

## robots.txt

A minimal `robots.txt` for the static site lives at **`public/robots.txt`**. It allows all crawlers (`Allow: /`) and references the sitemap with a path-only URL: **`/sitemap.xml`**.

## Static render (Markdown → HTML)

Render production content to HTML so sitemap URLs resolve:

```bash
python scripts/render_site.py
```

- **Inputs:** `content/articles/*.md`, `content/hubs/*.md`
- **Outputs:** `public/articles/{slug}/index.html`, `public/hubs/{slug}/index.html`; also updates `public/index.html` with a link to the production hub and up to 5 newest production articles.
- **Production-only:** Only articles in the production category (from config) are rendered; the article list on the homepage uses `content_index.get_production_articles()`. The hub rendered is the one matching `production_category`.

## Fill articles (AI)

Optional step: replace bracket placeholders `[...]` in draft articles with AI-generated prose (OpenAI Responses API). Fill is section-aware: the model follows per-section rules (e.g. Introduction, What you need to know first, Step-by-step workflow, FAQ) based on the nearest preceding heading. Leaves `{{...}}` and structure unchanged. Use `--style docs|concise|detailed` to tune instruction verbosity (default: docs).

```bash
python scripts/fill_articles.py          # dry-run (default)
python scripts/fill_articles.py --write  # apply changes (creates .bak per file)
```

Requires `OPENAI_API_KEY`. Optional: `OPENAI_BASE_URL`. Flags: `--model`, `--limit N`, `--since YYYY-MM-DD`, `--slug_contains TEXT`, `--force` (refill if already filled). Preflight QA runs by default when using `--write`; disable with `--no-qa`, or use `--qa` in dry-run to report pass/fail and `--qa_strict` for stricter checks.

## Cloudflare Pages (A1 deploy)

For an **A1 deploy** (publish only the static output):

- **Output directory:** `public`
- **Build command:** none (no build step required for A1)
- This deploy serves as a pipeline test: the site root shows a placeholder; `public/` must contain `index.html`, `robots.txt`, and `sitemap.xml`.
