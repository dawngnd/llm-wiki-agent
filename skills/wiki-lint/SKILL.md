---
name: wiki-lint
description: >-
  This skill should be used when the user asks to "lint the wiki",
  "check wiki health", "kiểm tra sức khỏe wiki", "wiki lint",
  "find wiki issues", "tìm lỗi wiki", "broken links",
  "orphan pages", "check wikilinks", "wiki có lỗi gì không",
  "kiểm tra wiki", "health check wiki", or wants to perform a
  comprehensive health check on the wiki knowledge base by
  scanning the filesystem for structural and content issues.
version: 1.0.0
---

# Wiki Lint

Run a comprehensive 10-point health check on the wiki by scanning the filesystem directly. Identify errors, warnings, and improvement opportunities. Produce a severity-scored report and offer auto-fixes.

## Pre-Lint Setup

Before running checks, verify the wiki exists and build a page inventory.

### Edge Case: Empty or Missing Wiki

```bash
# Abort if wiki/ does not exist
[ ! -d "wiki/" ] && echo "ERROR: wiki/ directory not found. Run wiki-ingest first." && exit 1

# Abort if index.md is missing
[ ! -f "wiki/index.md" ] && echo "ERROR: wiki/index.md not found. Create index before linting."

# Count total pages — if zero, report empty wiki and skip checks
PAGE_COUNT=$(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null | wc -l)
[ "$PAGE_COUNT" -eq 0 ] && echo "WARNING: Wiki is empty — no pages to lint."
```

### Build Page Inventory

```bash
# Build list of all wiki pages (filename without .md)
find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null | while read f; do
  basename "$f" .md
done | sort -u > /tmp/wiki-all-pages.txt

# Build list of all wikilinks used across wiki
grep -roh '\[\[[^]]*\]\]' wiki/ --include="*.md" | \
  sed 's/\[\[//g; s/\]\]//g' | sort -u > /tmp/wiki-all-links.txt
```

These two lists are the foundation for most checks below.

## 10-Point Health Check

### Check 1: Broken Wikilinks (ERROR) — Severity: 10 pts each

For each wikilink in `/tmp/wiki-all-links.txt`, verify the target page exists in `/tmp/wiki-all-pages.txt`.

```bash
# Find broken links
comm -23 /tmp/wiki-all-links.txt /tmp/wiki-all-pages.txt
```

Also detect convention violations:
- **Title Case:** `[[Cache Standard]]` → should be `[[cache-standard]]`
- **PascalCase:** `[[CoreBankClient]]` → should be `[[core-bank-client]]`
- **With extension:** `[[page.md]]` → should be `[[page]]`
- **Spaces instead of hyphens:** `[[my page]]` → should be `[[my-page]]`

```bash
# Detect links with uppercase characters (convention violation)
grep -rn '\[\[[^]]*[A-Z][^]]*\]\]' wiki/ --include="*.md"

# Detect links with .md extension
grep -rn '\[\[[^]]*\.md\]\]' wiki/ --include="*.md"
```

**Auto-fix:** Replace convention-violating links in-place: convert to kebab-case, strip `.md` extension. For truly broken links (target does not exist), suggest creating a stub or removing the link.

Report each broken link with: the source file containing it, the broken `[[link]]` text, and the suggested fix.

### Check 2: Orphan Pages (WARNING) — Severity: 3 pts each

Find pages with **zero inbound links** — no other page references them via `[[wikilink]]`.

For each page in `/tmp/wiki-all-pages.txt`:
```bash
# Check if any page links to this one
grep -rl "\[\[page-name\]\]" wiki/ --include="*.md" | grep -v "page-name.md"
```

If no results, the page is orphaned. Exclude `wiki/index.md` and `wiki/log.md` from this check (they are structural, not content pages).

```bash
# Batch orphan detection
while read page; do
  COUNT=$(grep -rl "\[\[$page\]\]" wiki/ --include="*.md" | grep -cv "$page.md" 2>/dev/null)
  [ "$COUNT" -eq 0 ] && echo "ORPHAN: $page"
done < /tmp/wiki-all-pages.txt
```

**Auto-fix:** Add orphaned pages to `wiki/index.md` under the appropriate section. Suggest `[[wikilink]]` additions to related pages based on tag or topic overlap.

### Check 3: Contradictions (ERROR) — Severity: 15 pts each

Read pages that share common entities or concepts. Apply these detection heuristics:

1. **Numeric disagreement:** Extract numbers near the same keyword across pages. Flag when two sources cite different figures for the same metric (e.g., "latency: 50ms" vs. "latency: 200ms").
2. **Temporal conflict:** One page says event X happened in 2023, another says 2024.
3. **Definitional clash:** Two concept pages define the same term differently — look for "là" / "is" / "means" patterns near entity names.
4. **Negation reversal:** One page says "X hỗ trợ Y" (X supports Y) while another says "X không hỗ trợ Y" (X does not support Y). Search for `không` / `not` / `no longer` near shared keywords.
5. **Entity-source mismatch:** An entity page states a fact not supported (or contradicted) by its listed `sources:` when reading those source summaries.

```bash
# Find pages sharing the same entity reference for pairwise comparison
for entity in $(cat /tmp/wiki-all-pages.txt | grep -f <(ls wiki/entities/ 2>/dev/null | sed 's/.md//')); do
  grep -rl "\[\[$entity\]\]" wiki/ --include="*.md" | sort
done
```

Report each contradiction with both pages cited, the specific conflicting claims quoted, and a recommendation on which source is more authoritative (prefer newer `created:` date).

### Check 4: Stale Claims (WARNING) — Severity: 5 pts each

Cross-reference source `created:` dates in frontmatter with wiki content.

```bash
# Extract updated dates and flag pages older than 90 days
TODAY=$(date +%s)
for f in $(find wiki/ -name "*.md"); do
  UPDATED=$(grep "^updated:" "$f" | head -1 | awk '{print $2}')
  [ -z "$UPDATED" ] && echo "NO DATE: $f" && continue
  UPDATED_TS=$(date -d "$UPDATED" +%s 2>/dev/null)
  [ -z "$UPDATED_TS" ] && continue
  AGE_DAYS=$(( (TODAY - UPDATED_TS) / 86400 ))
  [ "$AGE_DAYS" -gt 90 ] && echo "STALE ($AGE_DAYS days): $f"
done
```

Additional staleness signals:
- Concept pages citing only old sources when newer sources on the same topic exist — compare `sources:` array entries against `wiki/sources/` files sorted by `created:` date.
- Entity pages not updated despite newer sources mentioning that entity.

**Auto-fix:** Add a `⚠️ Có thể đã lỗi thời` (may be outdated) admonition to stale pages. List newer sources that should be reviewed.

### Check 5: Missing Pages (WARNING) — Severity: 5 pts each

Broken wikilinks (from Check 1) that point to topics **deserving their own page**. Assess each missing link:
- Referenced by ≥2 pages? → Likely warrants a page. Suggest creating a stub.
- Referenced by 1 page with rich context? → Suggest creating a page.
- One-off mention with no context? → Suggest removing the wikilink and keeping plain text.

```bash
# Count how many pages reference each broken link
while read broken; do
  COUNT=$(grep -rl "\[\[$broken\]\]" wiki/ --include="*.md" | wc -l)
  echo "$COUNT references: $broken"
done < <(comm -23 /tmp/wiki-all-links.txt /tmp/wiki-all-pages.txt)
```

### Check 6: Missing Cross-References (INFO) — Severity: 1 pt each

Find pages discussing the same topics but not linking to each other. Apply these entity-to-concept linking patterns:

**Pattern A — Entity mentions concept keyword:**
```bash
# For each concept page, check if entity pages mention it without linking
for concept in $(ls wiki/concepts/ 2>/dev/null | sed 's/.md//'); do
  KEYWORD=$(echo "$concept" | tr '-' ' ')
  grep -rl "$KEYWORD" wiki/entities/ --include="*.md" | while read f; do
    grep -q "\[\[$concept" "$f" || echo "MISSING LINK: $f should link to [[$concept]]"
  done
done
```

**Pattern B — Concept mentions entity name:**
```bash
# For each entity page, check if concept pages mention it without linking
for entity in $(ls wiki/entities/ 2>/dev/null | sed 's/.md//'); do
  KEYWORD=$(echo "$entity" | tr '-' ' ')
  grep -rl "$KEYWORD" wiki/concepts/ --include="*.md" | while read f; do
    grep -q "\[\[$entity" "$f" || echo "MISSING LINK: $f should link to [[$entity]]"
  done
done
```

**Pattern C — Source-to-source on same topic:** Two source summaries sharing ≥3 common wikilinks but not linking to each other.

**Auto-fix:** Insert `[[wikilinks]]` at the first mention of each unlinked term.

### Check 7: Index Consistency (ERROR) — Severity: 8 pts each

Verify `wiki/index.md` is complete and accurate:

```bash
# Pages in filesystem but not in index
for page in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" -exec basename {} .md \;); do
  grep -q "\[\[$page\]\]" wiki/index.md || echo "MISSING from index: $page"
done

# Index entries pointing to deleted pages
grep -oh '\[\[[^]]*\]\]' wiki/index.md | sed 's/\[\[//;s/\]\]//' | while read slug; do
  find wiki/ -name "${slug}.md" | grep -q . || echo "STALE index entry: $slug"
done
```

**Edge case:** If `wiki/index.md` does not exist at all, report as a critical error and offer to generate it from the current page inventory.

**Auto-fix:** Append missing pages to the correct section in `wiki/index.md`. Remove stale entries.

### Check 8: Data Gaps (INFO) — Severity: 1 pt each

Based on the wiki's current coverage, identify content gaps using topic frequency analysis:

```bash
# Extract all wikilinks and count frequency — high-frequency links without
# their own page indicate a gap
grep -roh '\[\[[^]]*\]\]' wiki/ --include="*.md" | \
  sed 's/\[\[//g; s/\]\]//g' | sort | uniq -c | sort -rn | head -20
```

Interpret frequency data:
- **≥5 references, no dedicated page:** Strong signal for a missing concept or entity page.
- **≥3 references, page exists but is short (<10 lines of body):** The page is a stub and needs expansion.
- Topics clustered in sources but absent from `wiki/concepts/` suggest a synthesis opportunity.

Also flag:
- Questions the wiki cannot answer well based on current content.
- Areas where additional raw sources would strengthen coverage.

### Check 9: YAML Frontmatter Validation (ERROR) — Severity: 8 pts each

Verify every page has valid YAML frontmatter:
- `type` field exists and matches the directory (`sources`, `entities`, `concepts`, `synthesis`)
- `category` field exists and is a valid kebab-case string (e.g., `ai`, `system-design`, `java-programming`)
- `created` and `updated` dates present and in `YYYY-MM-DD` format
- `tags` array present
- `sources` array present on entity/concept pages

```bash
# Check for pages with no frontmatter at all (no leading ---)
for f in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ -name "*.md" 2>/dev/null); do
  head -1 "$f" | grep -q "^---" || echo "NO FRONTMATTER: $f"
done

# Check type matches directory
for dir in sources entities concepts synthesis; do
  for f in wiki/$dir/*.md; do
    [ ! -f "$f" ] && continue
    type_val=$(grep "^type:" "$f" | head -1 | awk '{print $2}')
    [ -z "$type_val" ] && echo "MISSING TYPE: $f" && continue
    [ "$type_val" != "$dir" ] && echo "TYPE MISMATCH: $f (got $type_val, expected $dir)"
  done
done

# Check category field exists and is valid kebab-case
for f in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ -name "*.md" 2>/dev/null); do
  cat_val=$(grep "^category:" "$f" | head -1 | awk '{print $2}')
  [ -z "$cat_val" ] && echo "MISSING CATEGORY: $f" && continue
  echo "$cat_val" | grep -qP '^[a-z0-9]+(-[a-z0-9]+)*$' || echo "INVALID CATEGORY FORMAT: $f (got $cat_val, expected kebab-case)"
done

# Check for missing dates
for f in $(find wiki/ -path "wiki/log.md" -prune -o -path "wiki/index.md" -prune -o -name "*.md" -print); do
  grep -q "^created:" "$f" || echo "MISSING created: $f"
  grep -q "^updated:" "$f" || echo "MISSING updated: $f"
done
```

**Auto-fix:** Add missing `type:` field based on directory. Add missing `category:` field with value inferred from page `tags` and content. Add `created:` / `updated:` using file modification time as fallback. Add empty `tags: []` and `sources: []` arrays where missing.

### Check 10: Language Consistency (WARNING) — Severity: 3 pts each

Verify all wiki pages follow the bilingual convention:
- Natural text written in Vietnamese
- Technical terms in bilingual format: `Cache (Bộ nhớ đệm)`
- Major headers in bilingual format: `## Summary (Tóm tắt)`
- Code definitions, parameters, and identifiers may remain in English

```bash
# Heuristic: flag pages where Vietnamese characters are absent entirely
for f in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ -name "*.md" 2>/dev/null); do
  grep -Pq '[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]' "$f" \
    || echo "NO VIETNAMESE: $f"
done
```

Flag pages written entirely in English. Suggest bilingual header rewrites.

## Severity Scoring System

Calculate a total wiki health score after all checks complete:

| Check | Severity per issue | Category |
|-------|-------------------|----------|
| 1. Broken Wikilinks | 10 pts | ERROR |
| 2. Orphan Pages | 3 pts | WARNING |
| 3. Contradictions | 15 pts | ERROR |
| 4. Stale Claims | 5 pts | WARNING |
| 5. Missing Pages | 5 pts | WARNING |
| 6. Missing Cross-Refs | 1 pt | INFO |
| 7. Index Consistency | 8 pts | ERROR |
| 8. Data Gaps | 1 pt | INFO |
| 9. Frontmatter Errors | 8 pts | ERROR |
| 10. Language Issues | 3 pts | WARNING |

**Health Score** = max(0, 100 − total_penalty_points)

| Score | Rating |
|-------|--------|
| 90–100 | 🟢 Excellent — wiki is healthy |
| 70–89 | 🟡 Good — minor issues to address |
| 50–69 | 🟠 Fair — several issues need attention |
| 0–49 | 🔴 Poor — critical issues require immediate fixes |

## Report Format

Present findings grouped by severity:

**Errors (must fix):**
- Broken wikilinks (Check 1)
- Contradictions (Check 3)
- Stale index entries (Check 7)
- Frontmatter errors (Check 9)

**Warnings (should fix):**
- Orphan pages (Check 2)
- Stale claims (Check 4)
- Missing pages for frequently referenced topics (Check 5)
- Language violations (Check 10)

**Info (nice to fix):**
- Missing cross-references (Check 6)
- Data gaps (Check 8)

For each finding include: **What** (the issue), **Where** (specific file and line), **Fix** (actionable suggestion).

End the report with the health score and rating.

## Post-Report Actions

Ask the user:
> "Wiki health score: **N/100** (Rating). Found N errors, N warnings, and N info items. Want me to auto-fix what I can?"

**Auto-fixable items** (apply without confirmation if user agrees):
- Check 1: Rewrite convention-violating wikilinks to kebab-case
- Check 2: Add orphan pages to `wiki/index.md`
- Check 6: Insert missing `[[wikilinks]]` at first keyword mention
- Check 7: Add missing pages to index, remove stale entries
- Check 9: Add missing frontmatter fields with sensible defaults

**Require confirmation per item:**
- Check 3: Contradiction resolution (must choose which claim to keep)
- Check 4: Marking pages as stale (adds admonition banner)
- Check 5: Creating stub pages for missing topics
- Check 10: Rewriting headers to bilingual format

After applying fixes, append to `wiki/log.md`:

```markdown
## [YYYY-MM-DD] lint | Health check
Score: N/100 (Rating). Found N errors, N warnings, N info items. Fixed: [list].
```

## Lint Frequency

- **After every 10 ingests** — catches cross-reference gaps and broken links while the new content is fresh. Ingesting in batches without linting leads to compounding orphans and missing links.
- **Monthly at minimum** — catches stale claims (90-day threshold in Check 4) and orphan pages that accumulate over time. Also surfaces data gaps as the wiki grows.
- **Before major queries** — ensures wiki health before relying on it for analysis or synthesis. A poor-health wiki produces unreliable query results.
- **After bulk deletes or restructuring** — catches stale index entries and broken links caused by page removals or renames.
