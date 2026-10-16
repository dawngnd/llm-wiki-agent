---
name: wiki-autonomous-ops
description: >-
  This skill should be used when the user asks to "run autonomous wiki maintenance",
  "auto-maintain wiki", "scheduled wiki ops", "wiki automation",
  "chạy bảo trì tự động wiki", "tự động duy trì wiki",
  "wiki autonomous pipeline", "full wiki cycle", or wants the
  coding agent to independently perform a full cycle of wiki
  operations: source discovery, ingest, lint, maintenance, and
  knowledge gap analysis — all via direct filesystem access.
version: 1.0.0
---

# Wiki Autonomous Operations

Run a complete, hands-off wiki maintenance cycle by operating directly on the filesystem: preflight → discover → ingest → lint → maintain → graph → report.

## Overview

Autonomous operations enable a coding agent to independently maintain the wiki knowledge base without user interaction. Design the full pipeline for `/goal` or `/schedule` execution — overnight batch runs, daily maintenance sweeps, or weekly deep cycles.

The pipeline consists of seven sequential stages. Each stage produces results consumed by later stages. If any stage fails, skip it, log the error, and continue to the next — partial success is always preferable to a full abort.

**Full pipeline flow:** Pre-flight Check → Source Discovery → Auto-Ingest → Lint Sweep → Maintenance Pass → Graph Health → Report Generation.

## Stage 1: Pre-flight Check

Verify the wiki directory structure and core files exist before any operations begin. Run this check unconditionally at the start of every cycle.

```bash
# Verify required directories
for dir in wiki/sources wiki/entities wiki/concepts wiki/synthesis raw; do
  [ -d "$dir" ] && echo "✅ $dir" || echo "❌ $dir MISSING"
done

# Verify required files
for f in wiki/index.md wiki/log.md; do
  [ -f "$f" ] && echo "✅ $f" || echo "❌ $f MISSING"
done
```

**Decision tree for missing items:**

- `wiki/` directory missing entirely → **abort the cycle**. The project has no wiki. Log this and exit.
- `wiki/` exists but subdirectories missing → **create them**. Run `mkdir -p wiki/sources wiki/entities wiki/concepts wiki/synthesis`.
- `wiki/index.md` missing → **create it** with a skeleton header (`# Wiki Index`) and empty category sections for Sources, Entities, Concepts, Synthesis.
- `wiki/log.md` missing → **create it** with a header (`# Wiki Operations Log`).
- `raw/` missing → **create it**. Proceed to Stage 2 (which will find zero sources — that is fine).

**First-run scenario:** If the wiki is completely empty (zero `.md` files in subdirectories), note this in the report as "Initial wiki setup completed" and continue. An empty wiki is valid — the pipeline will simply have nothing to ingest, lint, or maintain.

## Stage 2: Source Discovery

Identify unprocessed source files that need ingestion.

```bash
# Step 1: List raw sources (excluding assets)
find raw/ -name "*.md" -not -path "raw/assets/*" 2>/dev/null | sort > /tmp/raw-sources.txt

# Step 2: List base_knowledge changelogs if available
find ../base_knowledge/changelogs/ -name "*.md" 2>/dev/null | sort >> /tmp/raw-sources.txt

# Step 3: Extract already-processed filenames from log
grep -oP '(?<=Processed |ingest \| )[\w\-\.]+\.md' wiki/log.md 2>/dev/null | sort -u > /tmp/processed.txt

# Step 4: Compute unprocessed list
comm -23 <(xargs -I{} basename {} < /tmp/raw-sources.txt | sort -u) /tmp/processed.txt > /tmp/unprocessed.txt
```

**Edge cases:**

- `raw/` empty or nonexistent → no sources to discover. Log "No new sources found" and skip to Stage 4.
- `wiki/log.md` does not exist or is empty → treat all sources as unprocessed.
- Duplicate filenames across `raw/` and `base_knowledge/` → process the `raw/` version. Note the duplicate in the report for manual review.

**Prioritization order:** Sort unprocessed files by modification date (newest first), then by file size (smallest first). Newer, smaller files yield the most immediate value with the least processing risk.

If no unprocessed sources remain, skip directly to Stage 4 (Lint Sweep).

## Stage 3: Auto-Ingest

Process up to **5 unprocessed sources** per cycle. For each source file, execute the full ingest sub-pipeline inline.

**Per-source steps:**

1. Read the entire source file content.
2. Analyze content: extract key takeaways, entities (people, orgs, products), concepts (ideas, frameworks, patterns), and potential wikilinks.
3. Search existing wiki pages for related content using `grep -rl "term" wiki/ --include="*.md"` to decide whether to update or create pages.
4. Create a source summary page in `wiki/sources/` with proper frontmatter (`type: sources`, `domain: <inferred-from-content>`, `category: <inferred-from-content>`, tags: `open-spec` for base_knowledge sources, `urd` for raw sources).
5. Create or update entity pages in `wiki/entities/` and concept pages in `wiki/concepts/`. Always prefer **updating** an existing page over creating a new one.
6. Add `[[wikilinks]]` between all related pages. Format: `[[kebab-case-name]]` — no `.md` extension.
7. Add entries to `wiki/index.md` under the correct category for each new page.
8. Append an ingest entry to `wiki/log.md`.

**Auto-ingest rules:**

- **Maximum 5 sources per cycle** — prevents quality degradation from processing too many files at once.
- **Skip files larger than 50KB** — flag them for manual review. Large files often need human judgment on how to decompose.
- **Prefer updates over new pages** — check for existing entity/concept pages before creating. A single source typically touches 10-15 existing pages.
- **Note all contradictions** — when new source information conflicts with existing wiki content, note both claims and cite both sources. Never silently overwrite.
- **Write in Vietnamese** with bilingual headers (`## Summary (Tóm tắt)`) and bilingual technical terms (`Cache (Bộ nhớ đệm)`).

**Error handling:** If a source file is unreadable (binary, corrupted encoding), skip it and log the filename with error reason. If disk space is critically low (< 10MB free), halt ingestion immediately and flag in the report. Continue to Stage 4 regardless.

## Stage 4: Lint Sweep

Run the 10-point health check from `wiki-lint` logic. Categorize each check as auto-fixable or report-only.

**Auto-fixable checks (apply fixes immediately):**

- **Broken wikilinks from naming conventions** — convert `[[Cache Standard]]` to `[[cache-standard]]`, `[[CoreBankClient]]` to `[[core-bank-client]]`, `[[page.md]]` to `[[page]]`.
- **Missing index entries** — add entries to `wiki/index.md` for pages that exist on disk but are not listed.
- **Frontmatter type mismatches** — correct `type:` field to match directory name.
- **Missing dates** — add `created:` using file modification date, `updated:` using today's date.
- **Missing category** — infer `category:` from page `tags` and content keywords.
- **Missing domain** — infer `domain:` from page `category`, `tags`, content keywords, and related sources.

**Report-only checks (flag for user):**

- **Contradictions** — conflicting claims across pages require human judgment.
- **Orphan pages** — pages with zero inbound links may be intentionally standalone.
- **Language consistency** — pages written entirely in English instead of Vietnamese.
- **Stale claims** — pages not updated despite newer sources existing.
- **Data gaps** — topics mentioned frequently but lacking dedicated pages.

```bash
# Auto-fix broken links: convert Title Case to kebab-case
grep -rn '\[\[[A-Z][^]]*\]\]' wiki/ --include="*.md" | while IFS=: read file line match; do
  slug=$(echo "$match" | sed 's/\[\[//;s/\]\]//' | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
  find wiki/ -name "${slug}.md" -print -quit | grep -q . && \
    sed -i "${line}s|${match}|[[${slug}]]|" "$file"
done
```

## Stage 5: Maintenance Pass

Apply safe, non-destructive auto-fixes from `wiki-maintenance` logic. Every fix in this stage is **additive** — it adds or corrects content, never removes it.

**Safe fixes (apply without confirmation):**

- **Kebab-case link conversion** — normalize all wikilinks to kebab-case. Use `sed` to transform PascalCase and Title Case in-place.
- **Index entry addition** — append missing page entries to `wiki/index.md` under the correct category header with a one-line summary.
- **Frontmatter patching** — add missing `type`, `created`, `updated` fields. Correct `type` values that don't match the parent directory.
- **Date addition** — fill in missing `created:` dates from `stat -c %y` output, missing `updated:` dates as today.
- **Category addition** — add missing `category:` field inferred from page `tags` and content keywords.
- **Domain addition** — add missing `domain:` field inferred from page `category`, `tags`, content keywords, and related source pages' domains. The agent decides the domain value autonomously during autonomous ops.

**Unsafe fixes (skip, report only):**

- **Duplicate page merging** — requires content comparison and user judgment on which page is canonical.
- **Orphan page linking** — requires understanding context to determine correct link targets.
- **Missing `sources:` arrays** — requires knowledge of which sources informed the page.
- **Content rewriting** — any modification to page body text beyond link formatting.

Log every fix applied with the file path and the nature of the change.

## Stage 6: Graph Health

Perform a quick knowledge graph analysis from `wiki-graph` logic. Focus on trend metrics rather than exhaustive analysis.

**Key metrics to compute:**

- **Orphan count** — pages with zero inbound links. Compare against previous run (if data exists in `wiki/log.md`) to detect trend direction.
- **Link density** — total wikilinks divided by total pages. A healthy wiki has 5+ links per page on average.
- **New cluster detection** — identify groups of 3+ pages that link densely to each other but weakly to the rest. New clusters may indicate emerging knowledge areas.
- **Hub pages** — top 5 pages by total connections (inbound + outbound).

If a previous autonomous-ops report exists in `wiki/log.md`, compare current metrics against it. Flag significant changes: orphan count increasing, link density dropping, new isolated clusters forming.

## Stage 7: Report Generation

Create a comprehensive operations report and append it to `wiki/log.md`.

```markdown
## [YYYY-MM-DD] autonomous-ops | Full Cycle

### Sources (Nguồn)
- Discovered: N new sources
- Ingested: N sources (list filenames)
- Skipped: N (reasons: too large, corrupted, etc.)

### Wiki Changes (Thay đổi)
- Pages created: N (list [[wikilinks]])
- Pages updated: N (list [[wikilinks]])
- Wikilinks added: N

### Lint Results (Kết quả kiểm tra)
- Errors found: N (auto-fixed: N)
- Warnings: N
- Info: N

### Maintenance (Bảo trì)
- Broken links fixed: N
- Index entries added: N
- Frontmatter fixed: N

### Graph Health (Sức khỏe đồ thị)
- Total pages: N | Total links: N
- Link density: N.N links/page
- Orphans: N (trend: ↑/↓/→)

### Flagged for User (Cần xem xét)
- Contradictions: [list with page citations]
- Large sources skipped: [list with sizes]
- Ambiguous decisions: [list]
```

## Safety Guards

Every guard exists for a specific reason. Never bypass these during autonomous execution.

| Guard | Rule | Rationale |
|-------|------|-----------|
| No deletions | Never delete any file or remove content from pages | Autonomous agents lack context for safe deletion. Data loss is irreversible. |
| No contradiction resolution | Note both claims, flag for user | Resolving contradictions requires domain expertise and judgment. |
| Max 5 sources/cycle | Process at most 5 unprocessed sources | Quality degrades with volume. Smaller batches maintain wiki coherence. |
| Large file flag | Skip files > 50KB, flag for manual review | Large files often need human decision on decomposition strategy. |
| Additive only | All changes create or append content | Prevents accidental overwrites or scope creep. |
| Full audit trail | Every action logged to `wiki/log.md` | Enables user review and rollback if needed. |

## Error Recovery

Design every stage to be independently skippable. If a stage fails:

1. **Log the error** — record the stage name, the error message, and the file being processed (if applicable).
2. **Skip the stage** — move to the next stage. Do not retry automatically.
3. **Continue the pipeline** — subsequent stages operate on whatever state exists. Partial success is always acceptable.

**Common failure scenarios:**

- File permission error → log and skip the specific file, continue with remaining files.
- Disk full during write → halt current stage, skip remaining writes, proceed to report generation with whatever was completed.
- Malformed frontmatter in existing page → skip that page's update, log as "frontmatter parse error", continue.
- Empty or corrupted `wiki/log.md` → treat as empty (all sources unprocessed), recreate with header.

**Resuming after failure:** The pipeline is idempotent. Running the same cycle again skips already-ingested sources (tracked via `wiki/log.md`) and re-applies lint/maintenance fixes (which are safe to repeat). Simply re-run the full pipeline.

## Scheduling Recommendations

| Frequency | Scope | Stages |
|-----------|-------|--------|
| **Daily** | Light sweep | Discovery + Lint (Stages 1-2, 4) |
| **Weekly** | Full cycle | All stages (1-7) |
| **Post-ingest** | Health check | Lint + Maintenance after 10 manual ingests (Stages 4-5) |

Use `/schedule` with a cron expression for recurring runs, or `/goal` for one-off autonomous cycles. Example: `/schedule "*/0 2 * * 1" "Run full wiki autonomous cycle"` for weekly Monday 2 AM runs.

## Cross-Skill Integration

Autonomous operations orchestrate logic from four other skills without importing or calling them. The pipeline **reimplements core logic inline** — reading the same files, applying the same rules, producing the same outputs — but operates without user interaction.

| Stage | Source Skill | Logic Reused |
|-------|-------------|--------------|
| Stage 2-3 | `wiki-ingest` | Source discovery, content analysis, page creation, cross-linking, index/log updates |
| Stage 4 | `wiki-lint` | 10-point health check, broken link detection, frontmatter validation, orphan detection |
| Stage 5 | `wiki-maintenance` | Broken link fixing, index sync, frontmatter patching, date addition |
| Stage 6 | `wiki-graph` | Link extraction, adjacency building, orphan counting, cluster detection |

The key difference: interactive skills ask the user for confirmation at decision points. Autonomous ops apply **only safe, reversible fixes** and flag everything else for user review in the report. Consult each skill's SKILL.md for full details on the rules being reimplemented.
