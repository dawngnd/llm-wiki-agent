---
name: wiki-ingest
description: >-
  This skill should be used when the user asks to "ingest a document",
  "add source to wiki", "process raw sources", "nạp tài liệu",
  "thêm nguồn vào wiki", "process this article", "ingest this",
  "I added something to raw/", "xử lý tài liệu mới",
  "import document to knowledge base", "process new sources",
  "có file mới trong raw/", or mentions ingesting/processing
  new content into the wiki knowledge base. Works by reading source
  files directly from the filesystem and writing wiki pages.
version: 1.0.0
---

# Wiki Ingest

Process raw source documents into structured, interlinked wiki pages by reading and writing files directly on the filesystem.

## Prerequisites

Verify the wiki directory structure before ingesting:

```
project/
├── wiki/
│   ├── sources/      # Source summary pages
│   ├── entities/     # Entity pages (people, orgs, products)
│   ├── concepts/     # Concept pages (ideas, frameworks, patterns)
│   ├── synthesis/    # Analysis and comparison pages
│   ├── index.md      # Master index of all pages
│   └── log.md        # Activity log
└── raw/              # Unprocessed source documents
```

```bash
# Check and create missing directories
for dir in wiki/sources wiki/entities wiki/concepts wiki/synthesis; do
  mkdir -p "$dir"
done

# Create index and log if absent
touch wiki/index.md wiki/log.md
```

Abort if `wiki/` does not exist at all — prompt the user to initialize the wiki first.

## Source Discovery

Determine which files need ingestion using one of three methods:

**Method 1: User-specified files.** Process the file(s) the user names. Verify each path exists and is a readable text file before proceeding.

**Method 2: Auto-detect unprocessed files.**

```bash
# List raw sources (excluding assets and binary files)
find raw/ -name "*.md" -not -path "raw/assets/*" 2>/dev/null

# List changelogs if base_knowledge exists
find ../base_knowledge/changelogs/ -name "*.md" 2>/dev/null

# Quick check for binary files that should be skipped
file raw/* | grep -v "text" | grep -v "empty"
```

Read `wiki/log.md` and extract filenames from `ingest` entries. Compare against the file listings. Any file not mentioned in the log is unprocessed.

**Method 3: No files found.** Inform the user that all sources have been processed. If `raw/` is empty, state explicitly: "The raw/ directory contains no source documents."

**Edge cases:**
- **Binary files** (PDFs, images, .docx) in `raw/` — skip with a warning. Only `.md` files are ingestible.
- **Empty files** — skip with a note: "source-file.md is empty, skipping."
- **Very large files** (>500 lines) — process normally but warn the user that analysis may be lengthy. Consider chunking the read if the file exceeds 2000 lines.
- **Subdirectories in raw/** — recurse into them: `find raw/ -name "*.md" -type f`.

## Ingest Pipeline

Execute each phase in order for every source file.

### Phase 1: Read and Analyze

Read the entire source file. Identify the document type (article, paper, transcript, notes, changelog).

**Handling images and diagrams:** If the source references images (`![...](...)`), read them separately when they contain structured data — architecture diagrams, flowcharts, data tables, or screenshots with visible text. Extract key information from visuals and incorporate into the analysis. For decorative images, note their existence but do not extract content. Copy referenced images to `raw/assets/` if not already there, preserving relative paths.

Extract from the content:
- **3-5 key takeaways** — the most important ideas
- **Entities** — people, organizations, products, tools, services
- **Concepts** — ideas, frameworks, theories, patterns, architectures
- **Potential wikilinks** — names that match or relate to existing wiki pages

Present the analysis to the user in a structured summary. Ask:
> "Key takeaways from [source] are listed above. Emphasize any particular aspects? Skip any topics?"

Wait for confirmation before proceeding to the next phase.

### Phase 2: Search Existing Context

Before creating any new pages, search for existing related content to avoid duplicates:

```bash
# Exact match search for each entity/concept name across wiki
grep -rli "entity-name" wiki/ --include="*.md"

# Fuzzy matching: search for partial names and common variations
grep -rli "entity" wiki/ --include="*.md"
grep -rli "ent-name" wiki/ --include="*.md"

# Check for similar filenames (handles abbreviations, alternate slugs)
find wiki/ -name "*entity*" -o -name "*concept*"

# Example: searching for "CoreBankClient" should also try:
grep -rli "core-bank-client" wiki/ --include="*.md"
grep -rli "core bank" wiki/ --include="*.md"
grep -rli "CoreBank" wiki/ --include="*.md"
```

**Decision tree for matches:**

| Scenario | Action |
|---|---|
| Exact filename match in correct directory | **Update** existing page |
| Exact filename match in wrong directory (e.g., entity filed as concept) | **Update** in place, do not move — note the miscategorization for later cleanup |
| Content match but different filename | Read the matched file. If it covers the same topic → **update** it. If different topic with same keyword → **create** new page |
| Partial/fuzzy match only | Read the matched file to verify. Same topic → **update**. Different topic → **create** new page |
| No match at all | **Create** new page |
| **Duplicate entities** — two existing pages cover the same topic | Flag to user: "Found potential duplicates: [[page-a]] and [[page-b]]. Recommend merging." Update the more complete page and add a redirect note to the other |

### Phase 3: Create Source Summary Page

Create a new file in `wiki/sources/` with the slugified source name.

**Naming rules:**
- Filename MUST be kebab-case with `.md` extension
- If the source document covers an entity/concept that will also have its own page, append `-source` to avoid collision. Example: `api-standard-source.md` (because `api-standard.md` will exist in `wiki/concepts/`)
- PascalCase names MUST be split: `CoreBankClient` → `core-bank-client.md`
- Acronyms stay lowercase: `API Gateway` → `api-gateway.md`
- Version numbers use hyphens: `Release v2.1` → `release-v2-1.md`
- Vietnamese diacritics MUST be stripped: `Tổng quan` → `tong-quan.md`
- Consecutive hyphens collapse: `my--file` → `my-file.md`
- Maximum filename length: 60 characters (truncate meaningfully, do not cut mid-word)

**Frontmatter template:**

```yaml
---
type: sources
tags: [relevant, tags]
sources: [original-filename.md]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

**Tags rule:** Use `open-spec` for sources from `../base_knowledge/changelogs/`, `urd` for sources from `raw/`.

Content sections: Summary, Key Claims, Entities Mentioned, Concepts Covered. Consult `references/page-templates.md` for the full template structure including bilingual headers.

**Critical:** Source pages are **factual only**. No interpretation, analysis, or opinion. Save that for concept or synthesis pages. If the source contains the author's opinions, attribute them clearly: "Theo [author], ..." (According to [author], ...).

### Phase 4: Create or Update Entity and Concept Pages

For **each entity** (person, org, product, tool) mentioned:
- If page exists → read it, merge new information, add source to `sources:` frontmatter, update `updated:` date
- If no page exists → create in `wiki/entities/` with frontmatter and focused content

For **each concept** (idea, framework, theory, pattern):
- Same logic, but create in `wiki/concepts/`

**Update merge strategy — when updating existing pages:**

1. **Read the existing page completely** before making any changes.
2. **Frontmatter merge:** Append the new source filename to `sources: [...]` array. Update `updated:` date. Preserve all existing tags, add new ones if relevant.
3. **Content merge:** Add new facts under existing sections. Do NOT delete or overwrite existing content. If the new source provides more detail on an existing point, expand inline with a source citation: `(from [[new-source]])`.
4. **Contradiction handling:** If the new source contradicts existing content, do NOT silently overwrite. Instead, add a `## Contradictions (Mâu thuẫn)` section (or append to it if one exists):
   ```markdown
   ## Contradictions (Mâu thuẫn)
   - **Topic:** [[source-a]] states X, but [[source-b]] states Y. Requires resolution.
   ```
   Preserve both claims. Never pick a winner without user instruction.
5. **Related links:** Merge new `[[wikilinks]]` into the Related section, avoiding duplicates.

**Volume expectation:** A single source typically touches **10-15 wiki pages**. This is normal. Prefer updating existing pages over creating new ones. If a source mentions an entity/concept only in passing (one sentence, no substantive info), add a brief mention to the existing page or skip creating a new page — not every mention deserves its own page.

### Phase 5: Cross-linking

Add `[[wikilinks]]` between all related pages:
- Source pages link to entities and concepts they mention
- Entity pages link to related entities, concepts, and sources
- Concept pages link to related concepts, entities, and sources

**Wikilink format:** `[[kebab-case-name]]` — no `.md` extension, always kebab-case.

**Bidirectional link strategy:** Every link must be bidirectional. When adding `[[entity-a]]` to a source page, also open `entity-a.md` and add a backlink to the source page. Build a link map before writing:

```
source-page.md  → [[entity-a]], [[concept-b]]
entity-a.md     → [[source-page]], [[concept-b]]
concept-b.md    → [[source-page]], [[entity-a]]
```

**Link validation step:** After adding all links, verify every target exists on disk:

```bash
# Extract all wikilinks from recently created/updated files
grep -oP '\[\[([^\]]+)\]\]' wiki/sources/new-page.md | tr -d '[]' | sort -u | while read slug; do
  if ! find wiki/ -name "${slug}.md" | grep -q .; then
    echo "BROKEN LINK: [[${slug}]] — target file not found"
  fi
done
```

Fix broken links immediately: either create the missing page (if the entity/concept is substantive enough) or remove the link. Never leave broken wikilinks.

### Phase 6: Update Index and Log

**Index update:** Add one entry per new page to `wiki/index.md` under the correct category header (`## Sources`, `## Entities`, `## Concepts`). If the category header does not exist, create it:

```markdown
- [[page-name]] — one-line summary (under 120 characters)
```

Do NOT add duplicate entries. Check before appending:

```bash
grep -q "page-name" wiki/index.md
```

**Log entry:** Append to `wiki/log.md`:

```markdown
## [YYYY-MM-DD] ingest | Source Title
Processed source-filename.md. Created N new pages, updated M existing pages.
New entities: [[entity-1]], [[entity-2]]. New concepts: [[concept-1]].
```

Use today's date. One log entry per source file processed.

### Phase 7: Report Results

Present to the user:
- Pages created (with `[[wikilinks]]` and full paths)
- Pages updated (what changed — new sections, added facts, updated frontmatter)
- Entities and concepts identified (distinguish new vs. updated)
- Contradictions found (if any, cite both sources and quote the conflicting claims)
- Broken links fixed or remaining (if any)
- Suggest running `wiki-lint` if more than 10 sources have been ingested since last lint

## Content Conventions

- **Language:** Vietnamese with bilingual headers (`## Summary (Tóm tắt)`)
- **Technical terms:** Bilingual format (`Cache (Bộ nhớ đệm)`)
- **Contradictions:** Always note them, cite both sources, never silently overwrite
- **Pages location:** ALL pages MUST be in `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, or `wiki/synthesis/`
- **Images:** Store in `raw/assets/`. Reference from wiki pages using relative paths. Do not embed base64 images in markdown.
- **Large documents:** If a single source generates more than 20 new pages, pause after Phase 4 and confirm with the user before cross-linking.

## Additional Resources

### Reference Files

For detailed templates and checklists, consult these files bundled with this skill:
- **`references/page-templates.md`** — Complete frontmatter and content templates for all four page types (sources, entities, concepts, synthesis). Use these templates as the starting point for every new page. Contains bilingual header format and section structure.
- **`references/ingest-checklist.md`** — Pre/during/post-ingest quality checklist with quality gates. Run through this checklist after completing Phase 6 to catch missing frontmatter fields, broken wikilinks, miscategorized pages, and naming violations before reporting results to the user.
