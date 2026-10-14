---
name: wiki-status
description: >-
  This skill should be used when the user asks to "check wiki status",
  "kiểm tra wiki", "wiki health", "wiki stats", "thống kê wiki",
  "how many pages", "bao nhiêu trang", or wants to see the current
  state of their wiki knowledge base including page counts, directory
  structure, and recent activity.
version: 1.0.0
---

# Wiki Status — Kiểm tra trạng thái Wiki

Scan the wiki filesystem to produce a comprehensive health report. Cover page counts, content metrics, wikilink integrity, index consistency, recent activity, and actionable recommendations. All operations are filesystem-based — read files directly, never call an API.

## 1. Prerequisites / Directory Verification — Kiểm tra thư mục

Verify the required directory structure exists before any analysis. The wiki requires exactly 4 content directories plus core files:

```bash
# Check all required directories
for dir in wiki/sources wiki/entities wiki/concepts wiki/synthesis raw; do
  if [ -d "$dir" ]; then
    echo "✅ $dir exists"
  else
    echo "❌ $dir MISSING"
  fi
done
```

Check core files:

```bash
# Verify core wiki files
for f in wiki/index.md wiki/log.md; do
  if [ -f "$f" ]; then
    echo "✅ $f exists ($(wc -l < "$f") lines)"
  else
    echo "❌ $f MISSING"
  fi
done
```

**Edge case — Empty wiki:** If `wiki/` does not exist at all, report that no wiki has been initialized. Suggest running the wiki-init skill or creating the structure manually. Do NOT proceed with further checks — stop and report immediately.

**Edge case — Partial structure:** If some directories exist but others are missing, report which ones are missing and continue checking the directories that do exist. Flag missing directories as actionable items in the final dashboard.

## 2. Page Inventory — Thống kê trang

Count `.md` files in each wiki subdirectory. Exclude `wiki/index.md` and `wiki/log.md` from content page counts since they are structural files.

```bash
# Count pages per directory
SOURCES=$(find wiki/sources/ -name "*.md" 2>/dev/null | wc -l)
ENTITIES=$(find wiki/entities/ -name "*.md" 2>/dev/null | wc -l)
CONCEPTS=$(find wiki/concepts/ -name "*.md" 2>/dev/null | wc -l)
SYNTHESIS=$(find wiki/synthesis/ -name "*.md" 2>/dev/null | wc -l)
TOTAL=$((SOURCES + ENTITIES + CONCEPTS + SYNTHESIS))

echo "sources:   $SOURCES"
echo "entities:  $ENTITIES"
echo "concepts:  $CONCEPTS"
echo "synthesis: $SYNTHESIS"
echo "total:     $TOTAL"

# Count pages per category
echo -e "\n=== By Category ==="
for f in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null); do
  grep "^category:" "$f" | awk '{print $2}'
done | sort | uniq -c | sort -rn
```

Calculate the percentage distribution across directories:

```bash
# Show distribution (avoid division by zero)
if [ "$TOTAL" -gt 0 ]; then
  echo "sources:   $((SOURCES * 100 / TOTAL))%"
  echo "entities:  $((ENTITIES * 100 / TOTAL))%"
  echo "concepts:  $((CONCEPTS * 100 / TOTAL))%"
  echo "synthesis: $((SYNTHESIS * 100 / TOTAL))%"
fi
```

Detect empty directories — any content directory with 0 pages is notable. Flag it as a potential gap in the wiki.

## 3. Source Inventory — Thống kê nguồn

Count raw sources available for processing, then compare against `wiki/log.md` to estimate how many remain unprocessed.

```bash
# Count all raw source files (exclude assets subdirectory)
RAW_COUNT=$(find raw/ -name "*.md" -not -path "raw/assets/*" 2>/dev/null | wc -l)
echo "Raw sources available: $RAW_COUNT"
```

Extract ingested source filenames from the log:

```bash
# Count unique ingest entries from log
INGESTED=$(grep -ci "ingest\|nhập\|import\|added source" wiki/log.md 2>/dev/null || echo "0")
echo "Ingest log entries: $INGESTED"
```

Calculate a rough processing rate. If `RAW_COUNT` is significantly higher than the number of `wiki/sources/` pages, there are likely unprocessed sources. Report the delta: `UNPROCESSED = RAW_COUNT - SOURCES` (approximate, since some raw files may produce entities or concepts rather than source pages).

**Edge case — No raw/ directory:** Report that no raw sources directory exists. This is normal if the user manages sources externally.

**Edge case — Missing wiki/log.md:** Cannot determine processing history. Report raw count only and note that log-based comparison is unavailable.

## 4. Content Metrics — Chỉ số nội dung

Measure content depth across all wiki pages using word counts.

```bash
# Word count per page, sorted by size
find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null | while read f; do
  words=$(wc -w < "$f")
  echo "$words $f"
done | sort -rn
```

Compute aggregate metrics:

```bash
# Average, min, max word counts
find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null -exec wc -w {} + | tail -1
```

Identify the shortest page (potential stub) and the longest page (potential candidate for splitting). Pages under 50 words are likely stubs — flag them.

Check for pages missing YAML frontmatter:

```bash
# Pages without frontmatter (first line is not ---)
find wiki/ -name "*.md" -not -name "index.md" -not -name "log.md" | while read f; do
  head -1 "$f" | grep -q "^---" || echo "⚠️  No frontmatter: $f"
done
```

Pages without frontmatter may cause issues with tagging (`open-spec`, `urd`) and should be flagged for correction.

## 5. Wikilink Health — Sức khỏe liên kết

Extract all `[[wikilinks]]` from wiki pages, compare against actual page basenames, and report broken links.

```bash
# Extract unique wikilinks (strip [[ and ]])
grep -roh '\[\[[^]]*\]\]' wiki/ 2>/dev/null | \
  sed 's/\[\[//g; s/\]\]//g' | sort -u > /tmp/wiki-links.txt

# Extract all page basenames (without .md)
find wiki/ -name "*.md" -exec basename {} .md \; | sort -u > /tmp/wiki-pages.txt

# Find broken links (links pointing to non-existent pages)
BROKEN=$(comm -23 /tmp/wiki-links.txt /tmp/wiki-pages.txt | wc -l)
VALID=$(comm -12 /tmp/wiki-links.txt /tmp/wiki-pages.txt | wc -l)
TOTAL_LINKS=$(wc -l < /tmp/wiki-links.txt)

echo "Total unique wikilinks: $TOTAL_LINKS"
echo "Valid links:   $VALID"
echo "Broken links:  $BROKEN"
```

List the actual broken links so they can be fixed:

```bash
# Show broken link targets
comm -23 /tmp/wiki-links.txt /tmp/wiki-pages.txt
```

Calculate link density — average number of wikilink occurrences per page:

```bash
LINK_OCCURRENCES=$(grep -roh '\[\[[^]]*\]\]' wiki/ 2>/dev/null | wc -l)
if [ "$TOTAL" -gt 0 ]; then
  echo "Link density: ~$((LINK_OCCURRENCES / TOTAL)) links/page"
fi
```

Low link density (< 1 link/page) indicates pages are poorly interconnected. High broken link count indicates naming inconsistencies or deleted pages.

## 6. Index Consistency — Tính nhất quán của Index

Check `wiki/index.md` for completeness. Every content page should appear in the index, and every index entry should point to an existing page.

```bash
# Extract page references from index.md (wikilinks)
grep -oh '\[\[[^]]*\]\]' wiki/index.md 2>/dev/null | \
  sed 's/\[\[//g; s/\]\]//g' | sort -u > /tmp/index-refs.txt

# Find pages NOT in index
comm -23 /tmp/wiki-pages.txt /tmp/index-refs.txt | \
  grep -v "^index$\|^log$" > /tmp/missing-from-index.txt

# Find stale index entries (point to deleted pages)
comm -23 /tmp/index-refs.txt /tmp/wiki-pages.txt > /tmp/stale-index.txt

MISSING=$(wc -l < /tmp/missing-from-index.txt)
STALE=$(wc -l < /tmp/stale-index.txt)

echo "Pages missing from index: $MISSING"
echo "Stale index entries:      $STALE"
```

If `MISSING > 0`, list the page names so the user can add them. If `STALE > 0`, list the broken entries so they can be removed.

**Edge case — No index.md:** Skip this check entirely. Report that no index exists and recommend creating one.

## 7. Recent Activity — Hoạt động gần đây

Parse `wiki/log.md` to show the latest activity timeline. Read the last 10 entries.

```bash
# Show last 20 lines of log (typically covers ~10 entries)
tail -20 wiki/log.md 2>/dev/null
```

Categorize log entries by type:

```bash
INGEST_COUNT=$(grep -ci "ingest\|nhập\|import\|add" wiki/log.md 2>/dev/null || echo 0)
LINT_COUNT=$(grep -ci "lint\|fix\|sửa\|repair" wiki/log.md 2>/dev/null || echo 0)
MAINT_COUNT=$(grep -ci "maintain\|update\|reorgan\|clean" wiki/log.md 2>/dev/null || echo 0)
STATUS_COUNT=$(grep -ci "status\|check\|kiểm tra" wiki/log.md 2>/dev/null || echo 0)

echo "Ingest entries:      $INGEST_COUNT"
echo "Lint/fix entries:    $LINT_COUNT"
echo "Maintenance entries: $MAINT_COUNT"
echo "Status entries:      $STATUS_COUNT"
```

If `wiki/log.md` is missing or empty, report no activity history available.

## 8. Comparison with Previous Status — So sánh với lần kiểm tra trước

Search `wiki/log.md` for previous status entries to detect trends. Look for lines containing status metrics from earlier runs.

```bash
# Find previous status entries
grep -n "status\|📊\|total.*pages" wiki/log.md 2>/dev/null | tail -5
```

If a previous status report is found, compare key metrics:
- **Pages added** since last check: `current_total - previous_total`
- **Broken links delta**: did broken link count increase or decrease?
- **Processing rate**: are raw sources being ingested faster than they accumulate?

Present the trend with directional indicators:
- `📈` metrics improved (more pages, fewer broken links)
- `📉` metrics degraded (more broken links, stale entries growing)
- `➡️` no change

If no previous status is found, skip comparison and note this is the first recorded status check.

## 9. Dashboard Output — Bảng tổng hợp

Format all collected metrics into a clean, scannable dashboard. Use emoji indicators for severity:

```
📊 Wiki Status Dashboard
═══════════════════════════════════════════
📁 Directory Structure
   ✅ wiki/sources/   ✅ wiki/entities/
   ✅ wiki/concepts/  ✅ wiki/synthesis/

📄 Page Inventory
   sources:    N pages  (XX%)
   entities:   N pages  (XX%)
   concepts:   N pages  (XX%)
   synthesis:  N pages  (XX%)
   ─────────────────────
   total:      N pages

📂 By Category
    ai:             N pages
    system-design:  N pages
    finance:        N pages
    ...

📦 Sources
   raw available:  N
   unprocessed:    ~N

📏 Content Metrics
   avg words/page: N
   shortest:       filename (N words) ⚠️ stub?
   longest:        filename (N words)
   missing frontmatter: N pages

🔗 Wikilink Health
   total unique links: N
   ✅ valid:   N
   ❌ broken:  N
   link density: ~N links/page

📑 Index Consistency
   missing from index: N
   stale entries:      N

📝 Recent Activity (last 10 entries)
   ingest: N | lint: N | maintenance: N

📈 Trend (vs. previous check)
   pages: +N | broken links: -N
═══════════════════════════════════════════
```

Use `⚠️` for warning-level issues (stubs, empty directories, low link density). Use `❌` for error-level issues (broken links, stale index entries, missing frontmatter). Use `✅` for healthy metrics.

Include a severity summary at the bottom:

```
Severity: ❌ N errors | ⚠️ N warnings | ✅ N healthy
```

## 10. Post-Status Actions — Hành động tiếp theo

Based on the findings, suggest specific next actions. Use a decision tree:

- **Broken links > 0** → Suggest running wiki-lint skill to fix broken wikilinks.
- **Unprocessed raw sources > 0** → Suggest running wiki-ingest skill to process remaining sources.
- **Pages missing from index > 0** → Suggest updating `wiki/index.md` to include missing pages.
- **Stale index entries > 0** → Suggest cleaning `wiki/index.md` to remove dead references.
- **Pages without frontmatter > 0** → Suggest adding YAML frontmatter with appropriate tags (`open-spec` for sources, `urd` for raw-derived content).
- **Empty directories exist** → Suggest creating content for the empty category or verifying whether the category is needed.
- **Stub pages (< 50 words)** → Suggest expanding stub pages with more detail.
- **Link density < 1** → Suggest adding more cross-references between related pages.

Present these as a prioritized action list, ordered by severity (errors first, then warnings).

If no issues are found, report the wiki as healthy: `✅ Wiki is in good shape — no actions required.`

## 11. Log Entry — Ghi nhật ký

After completing the status check, append a summary entry to `wiki/log.md`. Follow the existing log format.

```markdown
## YYYY-MM-DD — Wiki Status Check

- **Total pages:** N (sources: N, entities: N, concepts: N, synthesis: N)
- **Broken links:** N
- **Index issues:** N missing, N stale
- **Unprocessed sources:** ~N
- **Severity:** N errors, N warnings
```

Use the current date. Keep the entry concise — the dashboard is for display, the log entry is for historical tracking and future comparisons (see Section 8).

**Edge case — log.md does not exist:** Create `wiki/log.md` with a header `# Wiki Log` before appending the entry.

**Edge case — log.md is read-only or in unexpected format:** Warn the user that the log entry could not be appended. Display the entry content so the user can add it manually.
