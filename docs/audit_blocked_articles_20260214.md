# Audit: Blocked Articles (2026-02-14)

## 1. Audit findings

### Current status (before fixes)
- **Monitor** (`python scripts/monitor.py --summary`): 25 articles total, **23 production**, 0 todo in queue, 0 recent errors.
- **Blocked articles**: 2 (excluded from production count).

### Blocked articles identified
| Slug | Content type | Notes |
|------|--------------|--------|
| `2026-02-15-how-to-automate-social-media-posting-schedules-with-ai-with-pictory` | how-to | Pictory |
| `2026-02-15-guide-to-personalize-email-marketing-campaigns-using-ai-insights-with-otter` | guide | Otter |

### Block reasons (inferred)
- **`logs/errors.log`** did not exist at audit time, so exact failure reasons (e.g. "quality gate fail", "QA fail") were not available.
- **Content inspection**: Both articles had **unfilled template bodies** (headings only, no prose under sections like "Introduction", "Decision rules:", "Tradeoffs:", "Failure modes:", "SOP checklist:", "Template 1:", "Template 2:", etc.). This suggests either:
  - The fill run failed (API or quality gate) and the script set `status: blocked` while leaving the original template body, or
  - Fill was never run successfully for these slugs.
- **Frontmatter**: Both had `secondary_tool: "{{SECONDARY_TOOL}}"` (placeholder). The quality gate / QA logic may flag such placeholders; fixing or filling them is part of re-running fill.

### Categorization of failures
- **Inferred**: Likely **missing or insufficient content** (empty sections) and/or **unreplaced placeholders** (`{{SECONDARY_TOOL}}`), rather than a specific "forbidden phrase" in the body. No evidence of relaxed vs strict contract issues in the current codebase for these two.

---

## 2. Actions taken

### Backups (before any edits)
- **Articles**: Copies of the two blocked article files saved to  
  `content/articles_backup_20260214/`
- **Logs**: Full copy of `logs/` to `logs_backup_20260214/`

### Unblocking (no prompt/contract code changes)
- Status changed from `blocked` to `draft` for:
  - `content/articles/2026-02-15-how-to-automate-social-media-posting-schedules-with-ai-with-pictory.md`
  - `content/articles/2026-02-15-guide-to-personalize-email-marketing-campaigns-using-ai-insights-with-otter.md`

### Re-fill (to be run by you)
No prompt or `check_output_contract` changes were made. To actually fill the two articles and get them to `filled`:

1. Ensure **`OPENAI_API_KEY`** is set in the environment.
2. Run fill with quality gate and QA, once per slug (or run with a slug filter that matches only these):

   ```bash
   python scripts/fill_articles.py --quality_gate --quality_retries 2 --qa --write --force --slug_contains "how-to-automate-social-media-posting-schedules-with-ai-with-pictory" --limit 1
   python scripts/fill_articles.py --quality_gate --quality_retries 2 --qa --write --force --slug_contains "guide-to-personalize-email-marketing-campaigns-using-ai-insights-with-otter" --limit 1
   ```

3. After each run, check:
   - Article frontmatter has `status: filled` (or at least not `blocked`).
   - No new entries in `logs/errors.log` for that slug (once the file exists).

If you use `--block_on_fail`, a failed quality gate or QA will set status back to `blocked` and append to `logs/errors.log`. Creating the `logs/` directory and ensuring the script can write `logs/errors.log` will help with future audits.

---

## 3. Final status after fixes (unblock only)

- **Monitor** (after changing status to draft): **25 total, 25 production**, 0 todo, 0 recent errors.
- **Blocked articles**: **0** (both previously blocked articles are now `draft`).

---

## 4. Lessons learned / recommendations

- **Ensure `logs/errors.log` exists for future runs**: The fill script writes block reasons there when using `--block_on_fail`. If the log file or directory is missing, create it (or run fill once with write) so future blockages are auditable.
- **Re-fill**: The two articles are still **draft with empty bodies**. Running the fill commands above (with API key) is required to get them to `filled` and production-ready.
- **Placeholders**: Both articles still have `secondary_tool: "{{SECONDARY_TOOL}}"`. The fill prompt or a pre-step should replace this where possible; otherwise QA may keep flagging it.
- No changes were made to **prompts** or **`check_output_contract`** in this audit; if re-fill still blocks, the next step is to inspect `logs/errors.log` and then consider prompt or contract tweaks (e.g. clarifying required sections for how-to/guide, or relaxing a specific marker requirement if justified).
