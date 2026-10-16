---
name: wiki-research
description: >-
  This skill should be used when the user asks to "research a topic",
  "deep dive into", "nghiên cứu sâu", "tìm hiểu về",
  "analyze knowledge gaps", "phân tích lỗ hổng kiến thức",
  "explore connections about", "what does the wiki say about",
  or wants to perform deep research on a topic by reading
  and cross-referencing multiple wiki pages from the filesystem.
version: 1.0.0
---

# Wiki Research

Conduct deep research on a topic by reading, cross-referencing, and synthesizing knowledge from wiki files on the filesystem. Unlike `wiki-query` (which answers a single question), this skill performs multi-phase investigative research: broad discovery, deep reading, graph exploration, cross-referencing, gap analysis, and structured synthesis.

## 1. Scoping Phase (Xác định Phạm vi)

Clarify the research question before searching. Ask the user about:

- **Specific aspects of interest** — the full topic or a narrow facet?
- **Desired output format** — quick summary, synthesis page, comparison table, or full research report?
- **Depth level** — quick scan (skim index + top pages) vs. deep dive (read every related page, follow all links)?

**Decision tree for scoping:**

- User provides a broad topic (e.g., "research caching") → ask which aspects matter most: architecture, implementation patterns, performance benchmarks, specific services?
- User provides a specific question (e.g., "what caching strategies do we use?") → treat as focused research, narrow search terms accordingly.
- User asks for gap analysis specifically → skip to Phase 6 after a quick broad discovery.
- User wants a comparison → plan output as a structured comparison table from the start.

Confirm scope before proceeding. A well-scoped question saves reading dozens of irrelevant pages.

## 2. Broad Discovery (Khám phá Tổng quan)

Cast a wide net across all wiki directories. Execute searches in this order:

### Index scan

Read `wiki/index.md` first. Scan all category sections (Sources, Entities, Concepts, Synthesis) for entries related to the topic. Note candidate pages and their categories.

### Keyword search

```bash
# Search for topic keywords across entire wiki
grep -rl "keyword1\|keyword2\|keyword3" wiki/ --include="*.md" | sort -u

# Search with context to evaluate relevance before full read
grep -rn "keyword1\|keyword2" wiki/ --include="*.md" -B1 -A2

# Fuzzy/partial matching for compound words or variants
grep -rli "cach\|cache\|caching" wiki/ --include="*.md" | sort -u

# Search filenames for topic-related pages
find wiki/ -name "*keyword*" -type f
```

### Handle search outcomes

- **Many results (10+):** Prioritize by directory — read `wiki/concepts/` and `wiki/entities/` pages first (they contain synthesized knowledge), then `wiki/sources/` for raw details.
- **Few results (1-3):** Expand search terms — try synonyms, abbreviations, Vietnamese equivalents, related concepts.
- **Zero results:** Topic may not exist in the wiki. Report immediately to the user and skip to Phase 6 (Gap Analysis) and Phase 7 (External Source Scan).

## 3. Deep Reading (Đọc Sâu)

For each relevant page identified in broad discovery, execute a systematic deep read.

**Per-page process:**
1. Read the full page content — extract key claims, facts, dates, and figures.
2. Note the page's `type`, `category`, `tags`, `sources` from frontmatter — these indicate provenance, domain, and reliability.
3. Extract all `[[wikilinks]]` from the page.
4. Classify each linked page as: directly relevant (read next), tangentially related (read if time permits), or unrelated (skip).

**Link-following depth:** Follow wikilinks up to 3 levels deep from the original result set. Track which pages have been read to avoid re-reading.

- **Level 0:** Pages found by keyword search.
- **Level 1:** Pages linked from Level 0 pages.
- **Level 2:** Pages linked from Level 1 pages that are directly relevant.
- **Level 3:** Only follow if the topic is under-covered and more context is needed.

**Build a citation map** while reading: for each key claim or fact, record which page it came from. This map drives the cross-referencing and synthesis phases.

**Edge case — single page covers the topic:** If only one page exists, read it thoroughly, follow all its wikilinks, and note this in the gap analysis. A single-source topic is inherently fragile.

## 4. Graph Exploration (Khám phá Đồ thị)

Parse wikilinks around the topic to map connection topology. Determine which entities relate, which concepts connect, and whether unexpected connections exist.

```bash
# Extract all wikilinks from pages known to be topic-relevant
for f in wiki/concepts/relevant-page.md wiki/entities/related-entity.md; do
  page=$(basename "$f" .md)
  links=$(grep -oh '\[\[[^]]*\]\]' "$f" | sed 's/\[\[//g; s/\]\]//g' | sort -u)
  echo "$page -> $links"
done

# Find all pages that link TO a specific topic page (inbound links)
grep -rl "\[\[topic-page-name\]\]" wiki/ --include="*.md"
```

**Analysis to perform:**
- **Direct connections:** Pages that link to or from the topic pages.
- **Shared neighbors:** Two topic-related pages that both link to a third page — this third page may contain bridging information.
- **Unexpected connections:** Pages from unrelated domains that link to the topic — these often reveal non-obvious relationships worth investigating.
- **Connection density:** Is the topic well-connected (many cross-links) or isolated (few links)?

Draw a local subgraph: list the topic page(s) at center, direct connections one level out, and shared neighbors annotated with their connection type (entity, concept, source).

## 5. Cross-Referencing (Đối chiếu Chéo)

Compare claims across the pages read during deep reading. Build a fact table:

| Claim | Source Page | Date | Confidence |
|-------|------------|------|------------|
| Service uses Redis for caching | [[service-architecture]] | 2024-03 | High (primary source) |
| Service uses Memcached | [[legacy-migration-source]] | 2023-06 | Medium (may be outdated) |

**What to look for:**
- **Agreements:** Multiple pages confirm the same fact — high confidence.
- **Contradictions:** Pages disagree on facts, dates, or figures. Flag both sources, note which is more recent, and report to user.
- **Complementary info:** Different pages cover different aspects of the same topic — these combine well in synthesis.
- **Conflicting dates/figures:** When two pages give different numbers, check the `updated` frontmatter date. Prefer the more recently updated page, but flag the discrepancy.

**Edge case — contradicting sources:** Never silently pick one side. Always present both claims with their sources and dates, and let the user decide which is authoritative.

## 6. Gap Analysis (Phân tích Lỗ hổng)

Compare the wiki's current coverage against what a thorough treatment of the topic would require.

Classify each subtopic into one of four categories:

- **Covered (Đầy đủ):** Has a dedicated page with substantive content and cross-links.
- **Shallow (Sơ lược):** Mentioned in one or more pages but lacks a dedicated page or deep treatment.
- **Missing (Thiếu):** Expected subtopic with no coverage at all in the wiki.
- **Stale (Lỗi thời):** Page exists but `updated` date is old, content may be outdated, or contradicts newer sources.

**Create a coverage matrix:**

```markdown
| Subtopic | Domain | Category | Status | Wiki Page | Notes |
|----------|--------|----------|--------|-----------|-------|
| Core architecture | system-design | system-design | Covered | [[service-architecture]] | Comprehensive |
| Caching strategy | system-design | system-design | Shallow | mentioned in [[service-architecture]] | No dedicated page |
| Performance metrics | system-design | system-design | Missing | — | Expected but absent |
| Legacy migration | system-design | system-design | Stale | [[legacy-migration-source]] | Updated 2023-06, likely outdated |
```

This matrix becomes the actionable output of the research — it tells the user exactly where to invest effort next.

## 7. External Source Scan (Quét Nguồn Ngoài)

Check for unprocessed sources related to the topic that could fill identified gaps.

```bash
# Search raw/ for unprocessed sources mentioning the topic
grep -rl "keyword1\|keyword2" raw/ --include="*.md" 2>/dev/null

# Search filenames in raw/ for topic-related documents
find raw/ -name "*keyword*" -type f 2>/dev/null

# Check if base_knowledge has relevant uningest content
find ../base_knowledge/ -name "*.md" 2>/dev/null | xargs grep -l "keyword" 2>/dev/null
```

Cross-reference results against `wiki/log.md` ingest entries. If a raw file has not been ingested (its filename does not appear in any `ingest` log entry), report it as a potential source to process.

Present findings as:
- **Unprocessed raw sources:** Files in `raw/` matching the topic that have not been ingested.
- **Base knowledge sources:** Files in `../base_knowledge/` with relevant content.
- **Recommendation:** Which sources to ingest first based on gap analysis priorities.

## 8. Synthesis Report (Báo cáo Tổng hợp)

Create a structured research output using this template:

```markdown
# Research: [Topic] (Nghiên cứu: [Topic])

## What We Know (Kiến thức Hiện có)
[Structured summary organized by subtopic, every claim cited with [[wikilink]]]

## Key Connections (Mối Quan hệ Chính)
[Relationships between entities/concepts discovered during graph exploration]
[Unexpected connections and bridging pages]

## Cross-Reference Results (Kết quả Đối chiếu)
[Fact table with agreements, contradictions, complementary findings]

## Knowledge Gaps (Lỗ hổng Kiến thức)
[Coverage matrix from gap analysis]
[Prioritized list of missing/shallow/stale subtopics]

## Contradictions Found (Mâu thuẫn Phát hiện)
[Each contradiction with both sources cited and dates noted]
[Recommendation for which source to trust, or flag for user decision]

## Recommendations (Khuyến nghị)
- Sources to ingest: [list from external source scan]
- Pages to create: [list from gap analysis — missing items]
- Pages to update: [list from gap analysis — stale items]
- Cross-references to add: [list from graph exploration]
```

Present this report to the user. All claims must be cited with `[[wikilinks]]`. No unsupported assertions.

## 9. Save or Act (Lưu trữ hoặc Hành động)

After presenting the synthesis report, offer a decision tree:

- **Save as synthesis page:** Write the report to `wiki/synthesis/research-[topic].md` with proper frontmatter (`type: synthesis`, `domain: <inferred-domain>`, `category`, `tags`, `sources` listing all cited pages, `created`/`updated` dates). The agent determines `domain` autonomously by analyzing the domains of cited source pages — use the most frequent domain among cited pages, or the domain most relevant to the research topic. Add an entry to `wiki/index.md` under the Synthesis section. Append to `wiki/log.md`:
  ```markdown
  ## [YYYY-MM-DD] research | Topic Name
  Deep research on [topic]. Read N pages, found M connections, identified K gaps.
  Saved as [[research-topic]]. Contradictions: [count]. Sources to ingest: [count].
  ```
- **Ingest suggested sources:** Hand off to `wiki-ingest` skill for each recommended raw source.
- **Create missing pages:** For each gap marked "Missing," create a stub page in the appropriate directory with frontmatter (including `domain` inferred from the research topic and cited sources) and a placeholder body.
- **Add cross-references:** For each suggested cross-link from graph exploration, add `[[wikilinks]]` to the relevant pages.

Confirm with the user before executing any write operation.

## 10. Research Quality Checklist (Kiểm tra Chất lượng)

Before finalizing, verify:

- [ ] All factual claims cite their source page with `[[wikilinks]]`
- [ ] No unsupported assertions — if a claim has no wiki source, label it clearly as inference or external knowledge
- [ ] Knowledge gaps identified with actionable next steps (which sources to ingest, which pages to create)
- [ ] Contradictions flagged with both sources cited, dates noted, and resolution recommendation
- [ ] Coverage matrix complete — every expected subtopic classified as Covered, Shallow, Missing, or Stale
- [ ] Graph connections documented — direct links, shared neighbors, and unexpected connections noted
- [ ] Output format matches user's original request (summary, comparison, full report)
- [ ] Bilingual headers used throughout the synthesis report

If any checklist item fails, go back to the relevant phase and complete it before delivering the report.
