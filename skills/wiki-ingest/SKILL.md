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
version: 1.4.0
---

# Wiki Ingest

Process source documents into structured, interlinked wiki pages by reading and writing files directly on the filesystem, tracking state via SHA256 hashes, maximizing knowledge capture, and enforcing strict language conventions.

## Prerequisites & Project Resolution

The user specifies the target project path when invoking this skill. The wiki structure must follow:

```
<project_root>/
├── raw/
│   └── sources/     # Archive of ingested source files (auto-copied from external paths)
├── wiki/
│   ├── .meta/        # Metadata & hash registry (ingest-hashes.json)
│   ├── sources/      # Source summary pages
│   ├── entities/     # Entity pages (people, orgs, products, services)
│   ├── concepts/     # Concept pages (ideas, frameworks, patterns)
│   ├── synthesis/    # Analysis and comparison pages
│   ├── index.md      # Master index of all pages
│   └── log.md        # Activity log
└── [other sources]   # Source documents specified by user (may be external)
```

Ensure required directories exist:

```bash
PROJECT_PATH="<path-specified-by-user>"
for dir in "$PROJECT_PATH"/wiki/{.meta,sources,entities,concepts,synthesis}; do
  mkdir -p "$dir"
done

# Ensure raw/sources/ exists for archiving external source files
mkdir -p "$PROJECT_PATH/raw/sources"

# Initialize index, log, and hash registry if absent
touch "$PROJECT_PATH/wiki/index.md" "$PROJECT_PATH/wiki/log.md"
if [ ! -f "$PROJECT_PATH/wiki/.meta/ingest-hashes.json" ]; then
  echo '{"_version": 1, "entries": {}}' > "$PROJECT_PATH/wiki/.meta/ingest-hashes.json"
fi
```

Abort if the specified path does not exist or cannot be initialized.

---

## Input Modes & Source Discovery

Operate in one of three modes depending on user intent:

1. **Mode `file` (Single file):** User specifies a direct file path (e.g., `ingest /path/to/doc.md`).
2. **Mode `dir` (Directory batch):** User specifies a folder. Scan for all `.md` files and process them **serially** (one-by-one).
3. **Mode `auto` (Hash-detected unprocessed):** Scan candidate directory for `.md` files whose SHA256 hashes are not in `wiki/.meta/ingest-hashes.json`.

### Hash Verification

Before processing any file, compute its SHA256 hash:

```bash
FILE_HASH=$(sha256sum "$SOURCE_FILE" | awk '{print $1}')
```

Check against `wiki/.meta/ingest-hashes.json`:
- If the hash is already present in `entries`: Inform the user that the file content was already ingested on the recorded date, show associated pages, and ask if they wish to re-ingest (force) or skip.
- If not present: Proceed with the ingest pipeline.

### Source Archiving (Lưu trữ file nguồn)

When the source file is located **outside** the project's `raw/` directory, automatically copy it into `raw/sources/` to preserve a local archive:

```bash
RAW_DIR="$PROJECT_PATH/raw"
ARCHIVE_DIR="$PROJECT_PATH/raw/sources"

# Check if source file is outside raw/
case "$SOURCE_FILE" in
  "$RAW_DIR"/*)
    # File already inside raw/ — no copy needed
    ;;
  *)
    # File is external — copy to raw/sources/
    BASENAME=$(basename "$SOURCE_FILE")
    DEST="$ARCHIVE_DIR/$BASENAME"
    # If a file with the same name already exists, append hash prefix to avoid collision
    if [ -f "$DEST" ]; then
      SHORT_HASH=$(echo "$FILE_HASH" | cut -c1-8)
      DEST="$ARCHIVE_DIR/${SHORT_HASH}-${BASENAME}"
    fi
    cp "$SOURCE_FILE" "$DEST"
    echo "📁 Đã copy source vào: $DEST"
    ;;
esac
```

**Rules:**
- **Chỉ copy, không di chuyển** — file gốc giữ nguyên tại vị trí ban đầu.
- **Tránh trùng tên:** Nếu `raw/sources/` đã có file cùng tên nhưng nội dung khác (hash khác), thêm prefix `<8-char-hash>-` vào tên file.
- **Ghi nhận path lưu trữ** vào `ingest-hashes.json` ở trường `archived_path` (bên cạnh `original_path`).

---

## Ingest Pipeline

Execute each phase in strict order for every file. When processing multiple files, complete all phases and confirmations for one file before proceeding to the next.

### Phase 1a: Structural Analysis

1. Read the full source file content.
2. Identify document type: article, paper, transcript, meeting notes, changelog, architecture spec.
3. Construct a structural section map (hierarchy of headings, logical flow).
4. Identify the original document language.
5. **Handling images and diagrams:** If the source references images (`![...](...)`), read them if they contain structured data (system architectures, flowcharts, schemas). Incorporate extracted data into analysis. Preserve referenced image links.

### Phase 1b: Semantic Analysis & Entity Extraction

Extract core information with a **controlled granularity policy** — create standalone pages for significant knowledge units, inline minor mentions:

- **3-5 Key Takeaways:** Core points and thesis of the document.
- **Entities:** All people, organizations, tools, products, APIs, services mentioned. Apply **Entity Granularity Rules** (see below) to decide standalone page vs inline mention.
- **Concepts:** All ideas, frameworks, architectural patterns, theories, workflows. Apply **Concept Granularity Rules** (see below) to decide standalone page vs inline mention.
- **Questions & Gaps:** Open issues, ambiguities, or unanswered points raised in the source.
- **Potential Wikilinks:** Map extracted terms to existing pages in the wiki.

#### 🔒 Granularity Rules (Quy tắc Tách / Gộp Knowledge)

> These rules ensure **deterministic, stable output** across independent runs. When in doubt, **prefer gộp (inline)** over tách (standalone page).

**Entity Granularity Rules:**

| Condition | Action | Example |
|---|---|---|
| Source provides **≥3 distinct facts** about the entity | ✅ Create standalone entity page | "Transformer" with architecture details, training, variants |
| Entity is the **primary subject** of the source document | ✅ Create standalone entity page | A paper reviewing "GPT-4" in depth |
| Entity is **mentioned ≤2 times** with no dedicated analysis | ❌ Inline mention only — use `[[wikilink]]` if page exists, plain text if not | "Agent" mentioned once in passing |
| Entity is a **variant/subtype** of an existing entity | ❌ Inline within parent entity page | "Decoder-only" is a variant of "Transformer" → describe in `transformer.md` |

**Concept Granularity Rules:**

| Condition | Action | Example |
|---|---|---|
| Source provides a **standalone definition** + **≥2 key points** distinct from parent concept | ✅ Create standalone concept page | "KV Cache" with its own mechanism, complexity analysis |
| Concept is a **sub-step** within a larger process/pipeline already described in a parent concept | ❌ Inline within parent concept page | "Scaled dot-product" is Step 1 of "Attention Mechanism" → describe inline |
| Concept is a **visualization/artifact** of another concept, not an independent idea | ❌ Inline within parent concept page | "Causal Heatmap" is a visualization of the attention mask → describe inline |
| Concept has **independent utility** — can be understood and applied without the parent | ✅ Create standalone concept page | "Softmax" is used across many contexts beyond attention |

**Decision Flowchart:**

```
For each extracted entity/concept:
  1. Does the source provide ≥3 distinct facts OR dedicated analysis? → YES → standalone page (full)
  2. Is it a sub-step, variant, or visualization of an existing page? → YES → inline in parent + stub page
  3. Is it mentioned only in passing (≤2 mentions, no analysis)? → YES → inline mention only + stub page
  4. Default when ambiguous → inline in the most relevant parent page + stub page
```

#### 📄 Stub Page Policy (Chính sách trang Stub)

> **Mọi entity/concept được trích xuất đều PHẢI có page riêng trong wiki**, kể cả khi được phân loại là `[INLINE]`. Sự khác biệt giữa STANDALONE và INLINE chỉ nằm ở **mức độ chi tiết của nội dung**, không phải việc có tạo page hay không.

| Classification | Page created? | Content depth |
|---|---|---|
| `[STANDALONE]` | ✅ Full page | Đầy đủ: Overview, Context/Definition, Key Facts/Points, Examples, Related |
| `[INLINE in <parent>]` | ✅ **Stub page** | Tối thiểu: frontmatter + 1-2 câu mô tả + link đến parent page + tag `stub: true` |

**Stub page rules:**
1. **Luôn tạo file** trong `wiki/entities/` hoặc `wiki/concepts/` dù chỉ có thông tin tối thiểu.
2. **Frontmatter bắt buộc thêm `stub: true`** để dễ tìm và bổ sung sau.
3. **Nội dung tối thiểu:** 1-2 câu mô tả ngắn gọn về entity/concept + wikilink đến parent page nơi có thông tin chi tiết hơn.
4. **Wikilinks:** Mọi inline mention trong source/parent pages sử dụng `[[slug]]` — vì page luôn tồn tại, link luôn resolve.
5. **Khi bổ sung sau:** Khi có thêm thông tin từ ingest mới, stub page được nâng cấp thành full page và xóa `stub: true`.

**Confirmation Gate Integration:** During Confirmation Gate 1, explicitly label each entity/concept as `[STANDALONE]` or `[INLINE in <parent>] + stub` so the user can override before writing.

### 🔒 Confirmation Gate 1

Present the extraction summary to the user, **including granularity decisions**:
```markdown
### Phân tích tài liệu: [Tên file]
- **Loại tài liệu:** [Type]
- **Ngôn ngữ gốc:** [Lang]
- **Key Takeaways:** [3-5 điểm]
- **Entities phát hiện:**
  - `[STANDALONE]` entity-name — Lý do: ≥3 facts / primary subject → full page
  - `[INLINE in parent-page] + stub` entity-name — Lý do: ≤2 mentions / variant of parent → stub page + inline in parent
- **Concepts phát hiện:**
  - `[STANDALONE]` concept-name — Lý do: standalone definition + ≥2 key points → full page
  - `[INLINE in parent-concept] + stub` concept-name — Lý do: sub-step / visualization → stub page + inline in parent
- **Cơ hội liên kết (Wikilinks):** [Danh sách]
```
Ask:
> "Bạn có muốn điều chỉnh quyết định STANDALONE/INLINE+stub, thêm/bớt entities/concepts, hoặc bỏ qua phần nào trước khi ghi vào wiki không?"

**Wait for confirmation before writing any files.**

---

### Phase 2: Search Existing Context

Search existing wiki pages to prevent redundant creations and identify merge targets:

```bash
# Search for entity/concept variations
grep -rli "entity-name" "$PROJECT_PATH/wiki/" --include="*.md"
find "$PROJECT_PATH/wiki/" -name "*entity-name*.md"
```

Match rules:
- Exact or clear semantic match → **Update** existing page.
- Duplicate pages found → Flag to user and plan merge.
- No match → **Create** new page.

---

### Phase 3: Create Source Summary Page

Write to `wiki/sources/<slugified-source-name>.md`.

**Strict Language Rule:**
Even if the original document is in English or another language, **all wiki page content must be written in Vietnamese with bilingual headers and technical terms**.

Naming rules:
- Kebab-case only (`my-source-summary.md`), lowercase, no diacritics, max 60 chars.
- If colliding with a concept/entity name, append `-source` (e.g. `api-gateway-source.md`).

Structure: Consult `references/page-templates.md`. Must include:
- Frontmatter with `title: "..."`, `type: sources`, `tags: [...]`, `sources: [filename]`, `created`, `updated`
- `# Title (Tiêu đề)`
- `## Summary (Tóm tắt)`
- `## Key Claims (Các khẳng định chính)`
- `## Entities Mentioned (Thực thể được nhắc đến)`
- `## Concepts Covered (Khái niệm được đề cập)`
- `## Questions (Câu hỏi mở)`

---

### Phase 4: Create or Update Entity and Concept Pages

For each entity/concept extracted in Phase 1b, create or update pages based on classification:

**`[STANDALONE]` items → Full page:**
- Write/update in `wiki/entities/` or `wiki/concepts/` with complete content.
- **Entity pages:** Must include `## Context (Ngữ cảnh)` describing the role/system context in addition to `Overview` and `Key Facts`.
- **Concept pages:** Must include `## Examples (Ví dụ)` providing concrete illustrations in addition to `Definition` and `Key Points`.

**`[INLINE]` items → Stub page + inline content in parent:**
1. **Create stub page** in `wiki/entities/` or `wiki/concepts/` using the stub template (see `references/page-templates.md`):
   - Frontmatter with `stub: true`
   - 1-2 câu mô tả ngắn gọn dựa trên thông tin có được từ source
   - Wikilink đến parent page: `Xem chi tiết tại [[parent-page-slug]]`
   - Related links nếu có
2. **Incorporate inline content** into the designated parent page's relevant sections (Context, Key Facts, Key Points, or Examples).
3. **Use `[[wikilink]]` syntax** cho mọi mention — vì stub page luôn tồn tại, tất cả links đều resolve.

**Update & Contradiction Strategy:**
1. Append new source to `sources:` array in frontmatter.
2. Add new facts with citations `(from [[source-slug]])`. Never delete existing valid facts.
3. **Stub → Full upgrade:** If an existing stub page receives ≥3 new facts from the current source, upgrade it to a full page and remove `stub: true` from frontmatter.
4. **Contradictions:** Never silently overwrite. When a claim conflicts with existing knowledge, append to or create:
   ```markdown
   ## Contradictions (Mâu thuẫn)
   - **Chủ đề:** [[source-a]] nêu rằng X, nhưng [[source-b]] nêu rằng Y. Cần xác minh thêm.
   ```
   Retain both claims.

---

### Phase 4.5: Synthesis Opportunity Detection

Check if the newly ingested source shares significant themes or references (≥2 sources touching the same cluster of entities/concepts).

If detected, identify the synthesis opportunity:
> "Phát hiện chủ đề [[topic]] đã có 2+ nguồn tài liệu liên quan ([[source-1]], [[source-2]]). Có cơ hội tạo trang tổng hợp so sánh (synthesis page)."

Note this opportunity in the ingest report and suggest running `wiki-research` or creating a synthesis page.

---

### Phase 5: Cross-linking (Bidirectional)

Ensure all connections are **bidirectional**:
- Source links to entities/concepts: `[[entity-name]]`
- Entity/concept links back to source: `[[source-slug]]`
- Format: `[[kebab-case-slug]]` (never use spaces, uppercase, or `.md` extension).

Verify all wikilinks resolve to actual files:
```bash
grep -roh '\[\[[^]]*\]\]' "$PROJECT_PATH/wiki/sources/new-page.md" | sed 's/\[\[//;s/\]\]//' | while read slug; do
  find "$PROJECT_PATH/wiki/" -name "${slug}.md" | grep -q . || echo "BROKEN LINK: [[$slug]]"
done
```
Resolve any broken links immediately by generating the stub page or fixing the slug.

---

### Phase 6: Update Index, Log & Hash Registry

1. **Update `wiki/index.md`:** Add newly created pages under `## Sources`, `## Entities`, `## Concepts` with a concise summary (<120 chars).
2. **Append to `wiki/log.md`:**
   ```markdown
   ## [YYYY-MM-DD] ingest | Source Title
   Processed `source-filename.md` (SHA256: `abcd1234...`).
   Created N pages, updated M pages.
   Entities: [[entity-1]], [[entity-2]]. Concepts: [[concept-1]].
   ```
3. **Update `wiki/.meta/ingest-hashes.json`:**
   Register the file hash, filepath, ingest date, and affected pages:
   ```json
   "hash_value": {
     "filename": "source-file.md",
     "original_path": "/path/to/source-file.md",
     "archived_path": "raw/sources/source-file.md",
     "ingest_date": "YYYY-MM-DD",
     "pages_created": ["source-slug", "entity-1"],
     "pages_updated": ["concept-2"]
   }
   ```

---

### Phase 7: Report Results & Cross-Skill Suggestions

Present a clean summary to the user:
- Pages created & updated (with clickable wikilinks)
- Contradictions recorded (if any)
- Broken links verified/fixed
- **Cross-Skill Next Steps:**
  - 🔍 **wiki-lint:** Gợi ý chạy kiểm tra sức khỏe nếu đã ingest ≥ 10 tài liệu kể từ lần lint trước.
  - 🔬 **wiki-research:** Gợi ý đào sâu hoặc tạo synthesis page nếu Phase 4.5 phát hiện cơ hội tổng hợp.
  - 🕸️ **wiki-graph:** Gợi ý xem đồ thị quan hệ để trực quan hóa các kết nối mới hình thành.

---

## Content & Language Conventions

- **Ngôn ngữ bắt buộc:** Tiếng Việt là ngôn ngữ chủ đạo cho toàn bộ nội dung wiki.
- **Bilingual Headers & Terms:** Các tiêu đề lớn và thuật ngữ kỹ thuật sử dụng định dạng song ngữ: `## Summary (Tóm tắt)`, `Cache (Bộ nhớ đệm)`.
- **Tên biến, mã nguồn, định danh API:** Giữ nguyên dạng gốc tiếng Anh.
- **File gốc trong raw/sources:** Giữ nguyên vẹn, không bao giờ tự ý xóa hoặc di chuyển file nguồn gốc.
