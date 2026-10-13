---
name: wiki-maintenance
description: >-
  This skill should be used when the user asks to "maintain the wiki",
  "fix wiki issues", "clean up wiki", "dọn dẹp wiki",
  "sửa lỗi wiki", "bảo trì wiki", "update index",
  "fix broken links", "merge duplicate pages",
  "sync wiki index", "fix frontmatter", "sửa index",
  "wiki cleanup", or wants to perform systematic maintenance
  tasks on the wiki by reading and writing files directly.
version: 1.0.0
---

# Wiki Maintenance / Bảo Trì Wiki

Perform systematic maintenance on the wiki knowledge base by reading and writing files directly on the filesystem. Maintenance means fixing structural issues found by lint, improving existing content quality, and ensuring consistency across all wiki pages. All operations are filesystem-based — no API calls, no servers.

## Overview / Tổng Quan

Wiki maintenance covers three categories of work:

1. **Structural fixes** — Broken wikilinks, missing index entries, malformed frontmatter. These are auto-fixable with bash and file edits.
2. **Content improvements** — Missing cross-references, content gaps, stub pages. These require reading page content and making informed additions.
3. **Conflict resolution** — Contradictions between pages, duplicate topics. These require human judgment and must be presented to the user for decision.

Always assess the wiki state first, then proceed from auto-fixable issues (fast, safe) to manual issues (slower, needs user input).

## Issue Triage / Phân Loại Vấn Đề

Start every maintenance session by scanning the wiki filesystem to build an issue inventory:

```bash
# Full inventory scan
echo "=== Page Count ==="
echo "Sources:   $(find wiki/sources/ -name '*.md' 2>/dev/null | wc -l)"
echo "Entities:  $(find wiki/entities/ -name '*.md' 2>/dev/null | wc -l)"
echo "Concepts:  $(find wiki/concepts/ -name '*.md' 2>/dev/null | wc -l)"
echo "Synthesis: $(find wiki/synthesis/ -name '*.md' 2>/dev/null | wc -l)"

echo -e "\n=== Broken Wikilinks ==="
grep -roh '\[\[[^]]*\]\]' wiki/ | sed 's/\[\[//;s/\]\]//' | sort -u | while read slug; do
  find wiki/ -name "${slug}.md" 2>/dev/null | grep -q . || echo "  BROKEN: $slug"
done

echo -e "\n=== Missing from Index ==="
for page in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" -exec basename {} .md \;); do
  grep -q "\[\[$page\]\]" wiki/index.md 2>/dev/null || echo "  MISSING: $page"
done

echo -e "\n=== Orphan Pages (no inbound links) ==="
for page in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" -exec basename {} .md \;); do
  inbound=$(grep -rl "\[\[$page\]\]" wiki/ --include="*.md" 2>/dev/null | grep -v "$page.md" | wc -l)
  [ "$inbound" -eq 0 ] && echo "  ORPHAN: $page"
done
```

Categorize issues by severity and effort:

| Severity | Type | Auto-fixable? | Effort |
|----------|------|---------------|--------|
| **Error** | Broken wikilink | Yes (most cases) | Low |
| **Error** | Missing frontmatter `type` | Yes | Low |
| **Warning** | Missing from index | Yes | Low |
| **Warning** | Missing dates in frontmatter | Yes | Low |
| **Warning** | Missing cross-references | Semi-auto | Medium |
| **Info** | Orphan page | Manual | Medium |
| **Info** | Content gap / stub | Manual | High |
| **Info** | Contradiction | Manual | High |

**Priority order for fixing:** Error → Warning → Info. Within each severity, tackle auto-fixable issues first.

## Auto-Fix: Broken Wikilinks / Sửa Wikilinks Hỏng

Most broken wikilinks result from naming convention violations. The wiki uses `kebab-case` filenames, but wikilinks often appear in Title Case, PascalCase, or with `.md` extensions.

**Pattern detection and fix rules:**

```bash
# Find all unique wikilink targets and check each
grep -roh '\[\[[^]]*\]\]' wiki/ --include="*.md" | sed 's/\[\[//;s/\]\]//' | sort -u | while read slug; do
  # Skip if target page exists
  find wiki/ -name "${slug}.md" 2>/dev/null | grep -q . && continue

  # Try kebab-case conversion: "Title Case Words" → "title-case-words"
  kebab=$(echo "$slug" | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
  if find wiki/ -name "${kebab}.md" 2>/dev/null | grep -q .; then
    echo "FIX: [[$slug]] → [[$kebab]]  (Title Case→kebab)"
    continue
  fi

  # Try PascalCase conversion: "CoreBankClient" → "core-bank-client"
  kebab_pascal=$(echo "$slug" | sed 's/\([a-z]\)\([A-Z]\)/\1-\2/g' | tr '[:upper:]' '[:lower:]')
  if find wiki/ -name "${kebab_pascal}.md" 2>/dev/null | grep -q .; then
    echo "FIX: [[$slug]] → [[$kebab_pascal]]  (PascalCase→kebab)"
    continue
  fi

  # Try removing .md extension: "some-page.md" → "some-page"
  no_ext=$(echo "$slug" | sed 's/\.md$//')
  if [ "$no_ext" != "$slug" ] && find wiki/ -name "${no_ext}.md" 2>/dev/null | grep -q .; then
    echo "FIX: [[$slug]] → [[$no_ext]]  (remove .md extension)"
    continue
  fi

  # Try removing special characters: diacritics, underscores
  clean=$(echo "$slug" | sed 's/_/-/g' | tr '[:upper:]' '[:lower:]')
  if find wiki/ -name "${clean}.md" 2>/dev/null | grep -q .; then
    echo "FIX: [[$slug]] → [[$clean]]  (special chars)"
    continue
  fi

  echo "MANUAL: [[$slug]] — no matching page found"
done
```

After identifying fixes, apply them with `sed` on each affected file. Handle special regex characters in the slug by escaping them. After each fix, verify the wikilink now resolves:

```bash
# Apply a single wikilink fix across all wiki files
old_slug="Cache Standard"
new_slug="cache-standard"
# Escape special chars for sed
old_escaped=$(printf '%s\n' "$old_slug" | sed 's/[][\\/.^$*]/\\&/g')
new_escaped=$(printf '%s\n' "$new_slug" | sed 's/[&/\\]/\\&/g')
grep -rl "\[\[$old_slug\]\]" wiki/ --include="*.md" | while read f; do
  sed -i "s/\[\[$old_escaped\]\]/\[\[$new_escaped\]\]/g" "$f"
  echo "  Fixed in: $f"
done
# Verify
grep -r "\[\[$old_slug\]\]" wiki/ --include="*.md" && echo "STILL BROKEN" || echo "OK"
```

For **Case C (missing page):** If no matching page exists and the topic warrants coverage, create a minimal stub. If the reference is unnecessary, remove the wikilink brackets and keep the text as plain prose. Present ambiguous cases to the user.

## Auto-Fix: Index Consistency / Đồng Bộ Index

Keep `wiki/index.md` accurately reflecting the current page inventory.

**Add missing pages** under the correct category header. Read the page's frontmatter `type` field (or infer from directory path) to determine the section:

```bash
# Detect missing entries and their categories
for dir in sources entities concepts synthesis; do
  find "wiki/$dir/" -name "*.md" -exec basename {} .md \; 2>/dev/null | sort | while read page; do
    if ! grep -q "\[\[$page\]\]" wiki/index.md 2>/dev/null; then
      # Extract first non-empty, non-frontmatter line as summary
      summary=$(sed -n '/^---$/,/^---$/d; /^#/d; /^$/d; p' "wiki/$dir/$page.md" | head -1 | cut -c1-100)
      echo "ADD [$dir]: [[$page]] — $summary"
    fi
  done
done
```

Insert each missing entry under its correct category header in `wiki/index.md`. Maintain alphabetical order within each section.

**Remove stale entries** that point to deleted pages:

```bash
grep -oh '\[\[[^]]*\]\]' wiki/index.md | sed 's/\[\[//;s/\]\]//' | while read slug; do
  find wiki/ -name "${slug}.md" 2>/dev/null | grep -q . || echo "STALE: $slug"
done
```

Remove the entire line containing the stale `[[wikilink]]` from `wiki/index.md`.

**Sort entries** alphabetically within each category section after all additions and removals are complete.

## Auto-Fix: Frontmatter Patching / Sửa Frontmatter

Validate YAML frontmatter on every page and auto-fix what is safe to fix:

| Field | Rule | Auto-fixable? |
|-------|------|---------------|
| `type` | Must match directory: `sources`, `entities`, `concepts`, `synthesis` | Yes |
| `created` | Must exist, format `YYYY-MM-DD` | Yes — use file modification date |
| `updated` | Must exist, format `YYYY-MM-DD` | Yes — use today's date |
| `sources` | Array, required on entity/concept pages | No — needs context |
| `tags` | Array format (not comma-separated string) | Yes — split string to array |

For `type` mismatches, read the page's directory path and set `type` accordingly. For missing dates, use the filesystem as a fallback:

```bash
# Check for pages missing 'created' field
find wiki/ -name "*.md" -path "wiki/*" | while read f; do
  if ! grep -q '^created:' "$f"; then
    # Use file modification date as fallback
    file_date=$(stat -c '%y' "$f" | cut -d' ' -f1)
    echo "MISSING created: $f → will set $file_date"
  fi
done
```

For tag format issues, convert inline strings like `tags: "open-spec, urd"` to proper YAML arrays. Flag missing `sources` arrays on entity/concept pages for user input — these require understanding what source material the page was derived from.

## Auto-Fix: Cross-Reference Addition / Thêm Liên Kết Chéo

Detect pages that mention an entity or concept by name in their body text but do not include a `[[wikilink]]` to that page:

```bash
# For each entity/concept page, search for mentions without wikilinks
for page in $(find wiki/entities/ wiki/concepts/ -name "*.md" -exec basename {} .md \;); do
  # Convert kebab-case to space-separated words for text search
  search_term=$(echo "$page" | sed 's/-/ /g')
  # Find files that mention the term but don't wikilink it
  grep -rli "$search_term" wiki/ --include="*.md" 2>/dev/null | while read f; do
    base=$(basename "$f" .md)
    [ "$base" = "$page" ] && continue  # skip self
    if ! grep -q "\[\[$page\]\]" "$f"; then
      echo "MISSING LINK: $f mentions '$search_term' but lacks [[$page]]"
    fi
  done
done
```

When adding cross-references, insert the `[[wikilink]]` at the first natural mention of the term in the page body. Replace the plain text occurrence with the wikilink form — e.g., replace `cache standard` with `[[cache-standard]]`. Only add the wikilink on the first occurrence; subsequent mentions remain plain text. Avoid inserting wikilinks inside headings or frontmatter.

## Manual Fix: Contradictions / Mâu Thuẫn

When two pages make conflicting claims about the same fact, present both claims to the user with full citations. Never auto-resolve contradictions.

**Template for presenting contradictions:**

```
⚠️ CONTRADICTION DETECTED

Claim A (from [[page-a]], sourced from [[source-x]]):
  "Redis cache TTL mặc định là 300 giây"

Claim B (from [[page-b]], sourced from [[source-y]]):
  "Redis cache TTL mặc định là 600 giây"

Source dates: source-x (2024-01-15), source-y (2024-06-20)

Options:
1. Keep Claim A    2. Keep Claim B
3. Keep both with note    4. Research further
```

Apply the user's decision, update affected pages, and note the resolution in the report.

## Manual Fix: Content Gaps / Trang Thiếu Nội Dung

Identify pages that are too short or lack key sections:

- **Stubs:** Pages with fewer than 100 words of body content (excluding frontmatter)
- **Missing sections:** Entity pages lacking a description or source references; concept pages lacking examples
- **Skeleton pages:** Pages with only frontmatter and a heading, no actual content

Present a prioritized list to the user, sorted by page importance (number of inbound links). Suggest specific actions: expand from existing sources, request new source material, or mark as intentionally minimal.

## Manual Fix: Orphan Integration / Trang Mồ Côi

Orphan pages have zero inbound wikilinks from other wiki pages. Strategies for integration:

1. **Hub page linking:** Identify the most relevant hub or synthesis page and add a reference to the orphan under a "Xem thêm / See Also" section or inline where topically appropriate.
2. **Cross-reference insertion:** Find 2–3 pages that discuss related topics and add `[[wikilinks]]` to the orphan where the topic is mentioned.
3. **Index addition:** Ensure the orphan appears in `wiki/index.md` under the correct category — this provides at least one inbound link.
4. **User decision:** If no logical connection exists to any other page, flag for user decision: keep as standalone, merge into another page, or delete.

Never delete orphan pages without user confirmation.

## Maintenance Report / Báo Cáo Bảo Trì

After completing all fixes, generate a structured summary and append it to `wiki/log.md`:

```markdown
## [YYYY-MM-DD] maintenance | Periodic cleanup

### Auto-fixes applied
- Fixed N broken wikilinks (N title-case, N pascal-case, N extension removals)
- Added N missing pages to wiki/index.md
- Removed N stale entries from wiki/index.md
- Patched frontmatter on N pages (N type fixes, N date additions, N tag format fixes)
- Added N cross-reference wikilinks

### Manual fixes applied
- Resolved N contradictions (per user decision)
- Expanded N stub pages

### Issues flagged for user
- N orphan pages pending integration decision
- N content gaps requiring source material
- N contradictions awaiting resolution

### Stats
- Total pages: N | Broken links remaining: N | Orphans remaining: N
```

Present the report to the user before appending. Include specific file paths for all changes made.

## Maintenance Schedule / Lịch Bảo Trì

Follow this cadence for proactive maintenance:

- **Weekly (~15 min):** Fix broken wikilinks, sync index, check for new orphans, review recent ingests.
- **Monthly (~1 hour):** Full lint pass via `wiki-lint`, stale content check, knowledge gap analysis, graph connectivity review, language consistency, frontmatter validation.
- **Post-ingest (every ~10 ingests):** Run `wiki-lint`, verify cross-references, check for duplicates, review graph for new clusters.

## Reference Files / Tài Liệu Tham Khảo

For detailed guidance beyond this skill, consult:

- **`references/review-types.md`** — Detailed resolution guide for each issue type: broken links, orphans, duplicates, contradictions, stale content, and missing cross-references. Includes decision trees for ambiguous cases.
- **`references/maintenance-checklist.md`** — Complete weekly, monthly, and post-ingest checklists with specific commands and verification steps.
