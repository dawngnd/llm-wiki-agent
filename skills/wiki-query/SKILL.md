---
name: wiki-query
description: >-
  This skill should be used when the user asks a question about their
  wiki knowledge base, says "what do I know about X", "tìm trong wiki",
  "search wiki", "hỏi wiki", "tra cứu", "wiki có gì về",
  "tìm kiếm kiến thức", "search my knowledge base",
  "tìm thông tin", "look up in wiki", or wants to search and
  synthesize knowledge from wiki files on the filesystem.
version: 1.0.0
---

# Wiki Query

Answer questions by searching and synthesizing knowledge directly from wiki files on the filesystem. This is the primary "read" interface to the wiki — accept a natural-language question, locate relevant pages, and return a cited, well-structured answer.

## Overview

Wiki-query turns the flat collection of markdown files under `wiki/` into a queryable knowledge base. No server, no database — only `grep`, `find`, file reads, and `[[wikilinks]]`. The workflow always follows the same four layers of search, executed in order, stopping as soon as sufficient information is gathered.

The wiki has four content directories, each serving a different purpose:

| Directory | Contains | Priority |
|-----------|----------|----------|
| `wiki/entities/` | Named things: people, products, teams, services | High |
| `wiki/concepts/` | Abstract ideas, patterns, principles | High |
| `wiki/synthesis/` | Cross-cutting analysis, comparisons, insights | Highest |
| `wiki/sources/` | Summaries of ingested documents | Medium |

Always prefer synthesized and entity/concept pages over raw source summaries — they contain higher-level, already-integrated knowledge.

## Query Classification — Phân Loại Câu Hỏi

Before searching, classify the user query to determine the optimal search and answer strategy.

| Type | Signal Phrases | Search Focus | Answer Shape |
|------|---------------|--------------|--------------|
| **Factual** | "X là gì?", "what is X?", "define" | Exact keyword in entities/concepts | Concise paragraph + citation |
| **Relational** | "X liên quan gì đến Y?", "how does X relate to Y?" | Both terms, then wikilink overlap | Connection map with link chain |
| **Comparative** | "so sánh X và Y", "X vs Y", "compare" | Parallel search for both subjects | Side-by-side table |
| **Exploratory** | "tell me about X", "cho tôi biết về X" | Broad keyword + wikilink traversal | Structured narrative summary |
| **Gap** | "wiki thiếu gì về X?", "what's missing?" | Search + coverage audit | Coverage assessment with recommendations |

If the query is ambiguous or spans multiple types, default to **exploratory** and provide a broad answer with suggestions for follow-up questions.

## Layer 1: Keyword Search — Tìm Theo Từ Khóa

Start with `grep`-based full-text search across all wiki files. Use multiple keyword strategies depending on the query.

```bash
# Exact phrase match (best for specific terms)
grep -rl "microservice architecture" wiki/ --include="*.md"

# Case-insensitive search (handles Vietnamese capitalization variance)
grep -rli "kiến trúc" wiki/ --include="*.md"

# Multi-keyword union — find pages mentioning any keyword
grep -rln "authentication\|authorization\|OAuth" wiki/ --include="*.md" | sort | uniq -c | sort -rn

# Search with surrounding context to evaluate relevance before full read
grep -rn "event sourcing" wiki/ --include="*.md" -B2 -A2

# Regex for partial/variant matching (useful for Vietnamese diacritics)
grep -rliP "micro.?service|vi.?d.?ch.?v.?" wiki/ --include="*.md"
```

**Keyword extraction rules:**

- Strip stop words (là, của, the, is, and, với, trong, về).
- Keep domain-specific terms intact (e.g., "event sourcing" as a phrase).
- For Vietnamese queries with diacritics, also search the non-diacritic variant: `grep -rli "kiến trúc\|kien truc"`.

**Handle result volume:**

- **0 results** → Broaden keywords, try partial matches, move to Layer 2.
- **1–10 results** → Good. Proceed to read and synthesize.
- **10+ results** → Narrow by searching specific directories first (`wiki/entities/`, `wiki/concepts/`), or add more keywords to intersect results.

## Layer 2: Filename/Path Search — Tìm Theo Tên Trang

Search for wiki pages whose filenames match query terms. Page names in the wiki follow `kebab-case` convention, so convert query terms accordingly.

```bash
# Find pages by name
find wiki/ -name "*.md" | grep -i "api-gateway\|api.gateway"

# Search index.md for page entries (fastest orientation step)
grep -i "api gateway\|api-gateway" wiki/index.md

# List all pages in a specific directory for browsing
find wiki/entities/ -name "*.md" -printf "%f\n" | sort
```

Always check `wiki/index.md` early — it is the master registry of all wiki pages organized by category. A quick scan of the index often locates the right page faster than a full-text grep across hundreds of files.

## Layer 3: Wikilink Traversal — Duyệt Liên Kết Wiki

After identifying relevant pages from Layers 1–2, follow `[[wikilinks]]` to pull in related context. This is where the wiki's internal graph structure becomes valuable.

```bash
# Extract all wikilinks from a page
grep -oP '\[\[([^\]]+)\]\]' wiki/entities/api-gateway.md | sed 's/\[\[//;s/\]\]//' | sort -u

# Find all pages that link TO a specific page (backlinks)
grep -rl '\[\[api-gateway\]\]' wiki/ --include="*.md"
```

**Traversal procedure:**

1. Read each page identified in Layers 1–2.
2. Extract all `[[wikilinks]]` from those pages.
3. Filter links that appear related to the query (by keyword overlap with the question).
4. Read those linked pages — this is depth level 1.
5. If information is still insufficient, extract links from depth-1 pages and read selectively — depth level 2.
6. **Stop at depth 2.** Going deeper risks reading the entire wiki and losing focus.

Build a **relevance-ordered reading list**: pages with more inbound links from already-relevant pages rank higher. A page referenced by three relevant pages is almost certainly important.

## Layer 4: Content Reading and Synthesis — Đọc và Tổng Hợp

Read matched pages in priority order: synthesis > entities/concepts > sources. For each page:

1. Read frontmatter `tags` and `type` to confirm relevance.
2. Scan headers (`##`) to locate relevant sections — avoid reading entire long pages when only one section matters.
3. Extract key claims, data points, and relationships.
4. Note which page each piece of information came from (for citation).

**Raw source fallback:** Only check `raw/` directory files as a last resort if wiki pages lack the needed detail. The wiki should already contain all extracted knowledge.

## Answer Formatting — Định Dạng Câu Trả Lời

Select the format based on query classification:

**Factual → Concise answer with citation:**
> **API Gateway** là thành phần trung gian điều phối request giữa client và microservices ([[api-gateway]]). Hệ thống hiện dùng Kong làm gateway chính ([[kong-setup-source]]).

**Relational → Connection map:**
> [[service-mesh]] kết nối với [[api-gateway]] thông qua sidecar proxy. Cả hai đều implement pattern trong [[circuit-breaker]], tạo thành bộ ba resilience layer.

**Comparative → Side-by-side table:**

| Tiêu chí | [[kong-gateway]] | [[envoy-proxy]] |
|-----------|-------------------|-----------------|
| Protocol | HTTP/gRPC | HTTP/gRPC/TCP |
| Config | YAML/API | xDS API |

**Exploratory → Structured summary** with headers grouping subtopics, each citing its source page.

**Gap → Coverage assessment:**
> Wiki hiện có 3 trang về authentication ([[oauth-flow]], [[jwt-tokens]], [[sso-setup-source]]) nhưng thiếu thông tin về: authorization policies, RBAC model, token rotation strategy. Gợi ý ingest thêm tài liệu về authorization.

## Multi-Page Synthesis — Tổng Hợp Đa Trang

When the answer draws from multiple pages:

- **Merge complementary information** into a coherent narrative rather than listing page-by-page summaries.
- **Handle contradictions** by citing both pages and flagging the conflict: "Theo [[page-a]], timeout là 30s. Tuy nhiên [[page-b]] ghi nhận timeout 60s. Cần xác minh giá trị hiện tại."
- **Authority ranking**: synthesis pages > entity/concept pages > source pages. When in conflict, prefer the page with a more recent `updated` date in frontmatter.
- **Cross-reference check**: if a claim appears in multiple independent pages, note the convergence — it increases confidence.

## No Results Handling — Xử Lý Không Có Kết Quả

When the wiki contains no relevant content for a query:

1. **State clearly** that the wiki does not cover this topic.
2. **Suggest related topics** that the wiki does cover — search for partially matching terms and list the closest pages.
3. **Recommend ingestion**: "Có thể ingest tài liệu về chủ đề này bằng wiki-ingest để bổ sung kiến thức."
4. **Offer web research**: "Hoặc dùng wiki-research để tìm hiểu chủ đề này từ internet và lưu vào wiki."

Never fabricate answers from outside the wiki. If information is not in the wiki, say so.

**Edge case — empty wiki:** If `wiki/index.md` does not exist or the wiki directory has no `.md` files, inform the user: "Wiki hiện chưa có nội dung. Dùng wiki-ingest để bắt đầu xây dựng knowledge base."

## Query Log — Ghi Nhật Ký Truy Vấn

After answering, optionally append to `wiki/log.md` to track query patterns:

```markdown
## [YYYY-MM-DD] query | Tóm tắt câu hỏi
Searched N pages, synthesized answer from [[page-1]], [[page-2]].
Coverage: full | partial | none.
```

Log entries help identify knowledge gaps over time — frequently asked topics with "partial" or "none" coverage are high-priority ingestion candidates.

If the answer produces a valuable new synthesis — a comparison table, a novel connection, a structured analysis — offer to save it as a page in `wiki/synthesis/`:

1. Create the page with proper frontmatter (`type: synthesis`, `tags`, `sources`, `created`, `updated`).
2. Add an entry to `wiki/index.md` under the Synthesis section.
3. Log the synthesis creation in `wiki/log.md`.

## Performance Tips — Mẹo Hiệu Suất

- **Start with `wiki/index.md`** — scanning the index is always faster than a blind grep across the entire tree.
- **Use `grep -l` before `grep -n`** — get the file list first, then read selectively. Avoid dumping hundreds of lines of context.
- **Narrow by directory** — for large wikis (100+ pages), search `wiki/entities/` and `wiki/concepts/` first. Only fall back to `wiki/sources/` if needed.
- **Read entity/concept pages before source pages** — they contain pre-synthesized, higher-level information that answers questions more directly.
- **Check file count before broad grep** to estimate scope:
  ```bash
  find wiki/ -name "*.md" | wc -l
  ```
- **For repeated queries on the same topic**, check if a synthesis page already exists before re-reading all source pages.

## Conventions — Quy Ước

- **Search wiki first.** Only fall back to `raw/` sources if wiki pages lack the answer.
- **Cite every claim.** Every factual statement links to its source page using `[[wikilinks]]`.
- **Never fabricate.** If information is not in the wiki, state that explicitly.
- **Valuable answers compound.** Offer to save good analyses back into the wiki as synthesis pages.
- **Answer in Vietnamese** following the wiki's bilingual convention, with technical terms kept in English where appropriate.
- **Use `[[wikilinks]]`** for all internal references. Never expose raw file paths in the answer.
