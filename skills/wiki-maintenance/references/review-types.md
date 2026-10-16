# Review Types Guide

## Broken Wikilink

**Description:** A `[[wikilink]]` points to a page that doesn't exist on disk.

**Detection:** `grep` for `[[slug]]`, then `find wiki/ -name "slug.md"` returns nothing.

**Resolution:**
1. Read the page containing the broken wikilink
2. Check if it's a naming issue (grep for similar names)
3. Decision:
   - **Typo/case issue** → fix the wikilink text to kebab-case
   - **Page should exist** → create it with minimal content from context
   - **Stale reference** → remove the wikilink

## Self-referential Link

**Description:** A page contains a `[[wikilink]]` pointing to its own slug, creating a self-loop in the knowledge graph.

**Detection:** In `slug.md`, grep for `\[\[${slug}(\]\]|\||#)`.

**Resolution:**
1. Check context of the self-link:
   - **Citation pattern:** `(from [[slug]])` in a source summary page → remove the entire `(from [[slug]])` clause.
   - **Aliased link:** `[[slug|alias]]` → replace with plain `alias`.
   - **Bare link:** `[[slug]]` → replace with plain `slug` (remove wikilink brackets).
2. Save file and verify no self-links remain.

## Orphan Page

**Description:** A page with zero inbound links from other wiki pages.

**Detection:** For each `.md` file, grep all other wiki files for `[[page-name]]`.

**Resolution:**
1. Read the orphan page content
2. Identify related pages by topic
3. Add `[[wikilinks]]` from related pages to the orphan
4. If page is truly irrelevant, flag for user deletion decision

## Duplicate Content

**Description:** Two pages covering the same topic.

**Detection:** Similar filenames across directories, or grep reveals overlapping claims.

**Resolution:**
1. Read both pages completely
2. Compare content and sources
3. Options:
   - **Merge** into primary page, redirect wikilinks
   - **Differentiate** by clarifying distinct scope of each

## Contradiction

**Description:** Two pages make conflicting claims about the same fact.

**Detection:** Found during ingest or manual review.

**Resolution (requires human judgment):**
1. Read both pages
2. Check source dates and reliability
3. Present both viewpoints to user
4. Apply user's decision

## Stale Content

**Description:** Page references only old sources when newer ones exist.

**Detection:** Compare source dates in frontmatter.

**Resolution:**
1. Identify newer sources covering the same topic
2. Update page with latest information
3. Note both old and new sources

## Missing Cross-Reference

**Description:** Pages discuss the same topic but don't link to each other.

**Detection:** Grep for shared keywords across pages that lack mutual wikilinks.

**Resolution:**
1. Add `[[wikilinks]]` between related pages
2. Update index if needed
