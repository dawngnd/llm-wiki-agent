---
name: wiki-graph
description: >-
  This skill should be used when the user asks to "explore wiki graph",
  "show connections", "knowledge graph", "xem mối quan hệ",
  "wiki graph", "wikilink map", "show links between pages",
  "tìm connections", or wants to analyze the wikilink-based
  knowledge graph by parsing links from the filesystem.
version: 1.0.0
---

# Wiki Graph

Explore the knowledge graph by parsing `[[wikilinks]]` directly from wiki files. Build adjacency lists, compute graph metrics, detect clusters, find bridges and orphans, and produce actionable recommendations — all from the filesystem.

## 1. Graph Building

### 1.1 Extract All Wikilinks

Scan every `.md` file in the four wiki directories to produce raw edge data. Each edge is a pair `(source_page, target_page)`.

```bash
# Build raw edge list: source_page → target_page (one edge per line)
for f in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null); do
  page=$(basename "$f" .md)
  grep -oh '\[\[[^]]*\]\]' "$f" | sed 's/\[\[//g; s/\]\]//g' | while read target; do
    echo "$page -> $target"
  done
done > /tmp/wiki-edges.txt
```

**Edge case — empty wiki:** If `find` returns zero files, report "Wiki has no pages. Nothing to analyze." and stop.

**Edge case — no wikilinks at all:** If `/tmp/wiki-edges.txt` is empty after scanning, report "N pages found but zero wikilinks. The wiki is completely disconnected."

### 1.2 Build Adjacency Lists

From the raw edge file, build two views:

- **Outbound links** — for each page, which pages it links TO.
- **Inbound links (backlinks)** — for each page, which pages link TO it.

```bash
# Outbound: page → [targets]
awk -F' -> ' '{a[$1]=a[$1] ? a[$1]","$2 : $2} END {for (p in a) print p": "a[p]}' \
  /tmp/wiki-edges.txt | sort > /tmp/wiki-outbound.txt

# Inbound: page → [sources linking to it]
awk -F' -> ' '{a[$2]=a[$2] ? a[$2]","$1 : $1} END {for (p in a) print p": "a[p]}' \
  /tmp/wiki-edges.txt | sort > /tmp/wiki-inbound.txt
```

### 1.3 Build Node Inventory

Create a complete list of all wiki pages (not just those with links). This ensures orphan pages with zero links still appear in the analysis.

```bash
find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null | while read f; do
  basename "$f" .md
done | sort -u > /tmp/wiki-all-nodes.txt
```

**Edge case — single page wiki:** If only one page exists, report its link counts (likely zero) and skip cluster/bridge analysis since they require at least 3 nodes to be meaningful.

## 2. Graph Metrics

Compute four fundamental metrics from the edge and node data:

| Metric | Formula | Meaning |
|--------|---------|---------|
| Total nodes | `wc -l < /tmp/wiki-all-nodes.txt` | Number of wiki pages |
| Total edges | `wc -l < /tmp/wiki-edges.txt` | Number of wikilinks |
| Link density | edges ÷ nodes | Average links per page (overall) |
| Average degree | (inbound + outbound) ÷ nodes | Mean connections per page |

```bash
nodes=$(wc -l < /tmp/wiki-all-nodes.txt)
edges=$(wc -l < /tmp/wiki-edges.txt)
density=$(echo "scale=2; $edges / $nodes" | bc 2>/dev/null || echo "N/A")
echo "Nodes: $nodes | Edges: $edges | Density: $density"
```

**Interpretation guide:**
- Density < 1.0 → most pages have fewer than one link on average. Wiki is under-connected.
- Density 1.0–3.0 → healthy range for a growing wiki.
- Density > 5.0 → very dense graph, possibly over-linked or pages are acting as indices.

Report these metrics at the top of every graph analysis.

## 3. Central Node Analysis

Rank pages by **total degree** (inbound count + outbound count). This reveals which pages are structurally most important.

```bash
# Compute degree for each node
{
  awk -F' -> ' '{print $1}' /tmp/wiki-edges.txt  # outbound contributes 1
  awk -F' -> ' '{print $2}' /tmp/wiki-edges.txt  # inbound contributes 1
} | sort | uniq -c | sort -rn > /tmp/wiki-degree.txt
```

Present the **top 10** (or top 20 for large wikis with 50+ pages) most connected pages in a ranked table.

### Hub vs Authority Classification

Distinguish two types of central pages:

- **Hub pages** (high outbound, lower inbound) — pages that link TO many others. These serve as navigation or index pages. Typical examples: `wiki/index.md`, synthesis pages, topic overview pages.
- **Authority pages** (high inbound, lower outbound) — pages that many other pages link TO. These are foundational knowledge pages that the wiki heavily depends on.

To classify, compare outbound vs inbound ratio per page. If outbound > 2 × inbound → hub. If inbound > 2 × outbound → authority. Otherwise → balanced node.

Present hub and authority lists separately, noting the structural role each plays.

## 4. Cluster Detection

Identify groups of pages that are densely interconnected — pages that link to each other more than to the rest of the graph.

### Iterative Grep-Based Approach

Pure bash cannot perform BFS/DFS graph traversal. Instead, use an iterative seed-expansion approach:

1. **Seed selection** — start from the highest-degree node (from Section 3).
2. **First expansion** — collect all pages directly linked to/from the seed.
3. **Cohesion check** — for each member of the expanded set, count how many other members it links to. Keep only pages linking to ≥ 2 other members.
4. **Mark and repeat** — mark the resulting group as Cluster 1. Remove those pages from the working set. Pick the next highest-degree unassigned node and repeat.

```bash
# Example: expand from a seed page and check cohesion
seed="some-page"
# Get all neighbors of seed
grep "^$seed -> \|-> $seed$" /tmp/wiki-edges.txt | \
  sed "s/^$seed -> //; s/ -> $seed$//" | sort -u > /tmp/wiki-cluster-candidates.txt

# For each candidate, count links to other candidates
while read candidate; do
  links_to_cluster=$(grep "^$candidate -> " /tmp/wiki-edges.txt | \
    awk -F' -> ' '{print $2}' | grep -cFf /tmp/wiki-cluster-candidates.txt)
  echo "$candidate $links_to_cluster"
done < /tmp/wiki-cluster-candidates.txt | sort -k2 -rn
```

**Label each cluster** by examining the directory distribution of its members (e.g., a cluster with 80% entities from `wiki/entities/` might be labeled "Entity cluster — People & Orgs") or by reading member page titles for common themes.

Stop expanding when remaining unassigned pages have degree ≤ 1. Assign those to an "Unclustered" group.

## 5. Bridge Page Identification

Bridge pages connect different clusters. Their removal would weaken inter-cluster connectivity.

**Heuristic approach:** A page is a bridge if it has links to pages in **2 or more different clusters** (from Section 4). Rank bridges by the number of distinct clusters they connect.

Stronger bridges connect clusters that have **no other cross-links** — verify by checking whether removing the bridge page's edges leaves any other path between the two clusters.

Present bridge pages with their cluster connections:

```
bridge-page → connects Cluster 1 (topic-a) ↔ Cluster 3 (topic-c)
```

Bridge pages are high-value targets for maintenance — losing them fragments the knowledge graph.

## 6. Orphan Detection

Find pages with **zero inbound links** — no other page references them via `[[wikilink]]`.

```bash
# Pages with zero inbound links
comm -23 /tmp/wiki-all-nodes.txt \
  <(awk -F' -> ' '{print $2}' /tmp/wiki-edges.txt | sort -u) \
  > /tmp/wiki-orphans.txt
```

**Special handling:**
- `index` is expected to be an orphan (it is the root hub, rarely linked to). Exclude from orphan report.
- `log` is expected to be an orphan. Exclude as well.

**Sort orphans by age:** Extract `created:` date from each orphan's YAML frontmatter and sort oldest-first. Older orphans are more likely forgotten rather than newly created.

Present orphans grouped by directory:
- Orphans in `sources/` → likely missing `[[wikilinks]]` from concept/entity pages
- Orphans in `entities/` or `concepts/` → likely need integration into synthesis or index
- Orphans in `synthesis/` → likely need backlinks from the pages they analyze

## 7. Broken Link Analysis

Find `[[wikilinks]]` pointing to pages that do not exist on the filesystem.

Cross-reference every unique link target from `/tmp/wiki-edges.txt` against `/tmp/wiki-all-nodes.txt`:

```bash
# Extract unique link targets and find those without a matching file
awk -F' -> ' '{print $2}' /tmp/wiki-edges.txt | sort -u | while read target; do
  grep -qx "$target" /tmp/wiki-all-nodes.txt || echo "BROKEN: $target"
done
```

Report broken links in two ways:
- **Per-page:** which pages contain the most broken links (these need attention first)
- **Global count:** total broken links across the wiki

For each broken link, suggest one of:
- **Create the missing page** — if referenced by 2+ pages, it likely warrants its own page
- **Fix the link text** — if it looks like a typo or naming convention violation (PascalCase, spaces, `.md` extension)
- **Remove the link** — if it's a one-off mention of a topic too minor for its own page

## 8. Category Analysis

Analyze the graph structure per wiki directory **and** per knowledge-domain `category` (from frontmatter) to reveal cross-category linking patterns.

### 8.1 By Directory Type

Count edges between all directory-type pairs:

| From ↓ / To → | sources | entities | concepts | synthesis |
|---------------|---------|----------|----------|-----------|
| sources       | N       | N        | N        | N         |
| entities      | N       | N        | N        | N         |
| concepts      | N       | N        | N        | N         |
| synthesis     | N       | N        | N        | N         |

Build this matrix by mapping each page to its category (the subdirectory it lives in) and counting edge directions.

**Interpretation patterns:**
- Sources → entities/concepts should be high (sources reference what they discuss)
- Entities → entities being high suggests organizational/people networks
- Concepts → concepts being high suggests a well-built conceptual framework
- Synthesis → everything should be high (synthesis pages are meant to integrate)
- Any zero cell in the matrix suggests a disconnected category pair worth investigating

### 8.2 By Knowledge Domain (Category)

Group pages by their frontmatter `category` field and count edges between domain pairs:

```bash
# Extract category per page
for f in $(find wiki/sources/ wiki/entities/ wiki/concepts/ wiki/synthesis/ \
  -name "*.md" 2>/dev/null); do
  page=$(basename "$f" .md)
  cat_val=$(grep "^category:" "$f" | head -1 | awk '{print $2}')
  [ -n "$cat_val" ] && echo "$page $cat_val"
done > /tmp/wiki-page-categories.txt

# Cross-reference with edge list to build domain-pair matrix
while IFS=' -> ' read src tgt; do
  src_cat=$(grep "^$src " /tmp/wiki-page-categories.txt | awk '{print $2}')
  tgt_cat=$(grep "^$tgt " /tmp/wiki-page-categories.txt | awk '{print $2}')
  [ -n "$src_cat" ] && [ -n "$tgt_cat" ] && echo "$src_cat -> $tgt_cat"
done < /tmp/wiki-edges.txt | sort | uniq -c | sort -rn
```

**Interpretation:**
- High cross-domain links (e.g., `ai -> system-design`) indicate knowledge areas that naturally overlap.
- Isolated domains with zero outbound links to other domains suggest siloed knowledge — investigate whether cross-references are missing.
- Domains with many pages but low link density may need internal structuring

## 9. Visualization Output

Format all findings into a structured report with these sections:

**Top Connected Pages Table:**

```
Rank | Page               | Inbound | Outbound | Total | Type
   1 | some-concept       |      12 |        5 |    17 | Authority
   2 | index              |       0 |       15 |    15 | Hub
   ...
```

**Cluster Summary:** List each cluster with its label, member count, member page names, and internal edge density.

**Orphan List:** Group by directory, sorted by creation date (oldest first).

**Bridge Pages:** Each bridge with the clusters it connects.

**Cross-Category Matrix:** The 4×4 table from Section 8.

**Graph Health Score:** Synthesize a single qualitative rating based on:
- Orphan ratio (orphans ÷ total nodes) — below 10% is healthy
- Broken link count — zero is ideal
- Link density — 1.0–3.0 is healthy
- Cluster count vs total nodes — having 2–5 clusters for 20–50 pages is healthy

## 10. Suggested Actions

Based on the analysis, produce a prioritized action list:

**Priority 1 — Fix breakage:**
- Fix or remove broken wikilinks (from Section 7)
- Investigate contradictions if a page appears in two clusters claiming different things

**Priority 2 — Connect orphans:**
- For each orphan, suggest 2–3 existing pages that should link to it (find pages discussing similar topics using `grep`)
- If an orphan has no related pages, suggest merging its content into a related page or deleting it

**Priority 3 — Strengthen clusters:**
- For under-connected clusters (internal density < 0.3), suggest specific cross-references between cluster members
- Create hub/index pages for clusters that lack one — a page linking all cluster members

**Priority 4 — Bridge gaps:**
- For category pairs with zero cross-links (Section 8), suggest creating synthesis pages or adding cross-references
- For clusters connected by a single bridge, suggest adding redundant connections

**Priority 5 — Create missing pages:**
- Broken links referenced by 2+ pages → create stub pages with frontmatter and a TODO marker

Ask the user which priority level to act on. Apply changes only after confirmation.

## 11. Log Entry

After completing the analysis, append a summary entry to `wiki/log.md`:

```markdown
## [YYYY-MM-DD] graph | Knowledge graph analysis
Nodes: N, Edges: N, Density: N. Found C clusters, B bridges, O orphans, K broken links.
Top pages: [[page-1]] (degree N), [[page-2]] (degree N), [[page-3]] (degree N).
Health: [healthy|needs-attention|critical].
```

## Analysis Frequency

- **After every 10 ingests** — detect structural drift and emerging clusters early
- **Before synthesis writing** — understand the graph landscape before creating cross-cutting analysis
- **Monthly at minimum** — catch orphans and broken links that accumulate over time
