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
version: 1.1.0
---

# Wiki Ingest

Process source documents into structured, interlinked wiki pages by reading and writing files directly on the filesystem, tracking state via SHA256 hashes, maximizing knowledge capture, and enforcing strict language conventions.

## Prerequisites & Project Resolution

The user specifies the target project path when invoking this skill. The wiki structure must follow:

```
<project_root>/
├── wiki/
│   ├── .meta/        # Metadata & hash registry (ingest-hashes.json)
│   ├── sources/      # Source summary pages
│   ├── entities/     # Entity pages (people, orgs, products, services)
│   ├── concepts/     # Concept pages (ideas, frameworks, patterns)
│   ├── synthesis/    # Analysis and comparison pages
│   ├── index.md      # Master index of all pages
│   └── log.md        # Activity log
└── [sources/raw/...] # Source documents specified by user
```

Ensure required directories exist:

```bash
PROJECT_PATH="<path-specified-by-user>"
for dir in "$PROJECT_PATH"/wiki/{.meta,sources,entities,concepts,synthesis}; do
  mkdir -p "$dir"
done

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

Extract core information with a **maximization policy** (atomic notes):
- **3-5 Key Takeaways:** Core points and thesis of the document.
- **Entities:** All people, organizations, tools, products, APIs, services mentioned. **Every entity mentioned, even once, warrants an entity page** (stubs are welcomed and encouraged).
- **Concepts:** All ideas, frameworks, architectural patterns, theories, workflows. **Every concept mentioned warrants a concept page**.
- **Questions & Gaps:** Open issues, ambiguities, or unanswered points raised in the source.
- **Potential Wikilinks:** Map extracted terms to existing pages in the wiki.

### 🔒 Confirmation Gate 1

Present the extraction summary to the user:
```markdown
### Phân tích tài liệu: [Tên file]
- **Loại tài liệu:** [Type]
- **Ngôn ngữ gốc:** [Lang]
- **Key Takeaways:** [3-5 điểm]
- **Entities phát hiện:** [Danh sách - đánh dấu mới vs cập nhật]
- **Concepts phát hiện:** [Danh sách - đánh dấu mới vs cập nhật]
- **Cơ hội liên kết (Wikilinks):** [Danh sách]
```
Ask:
> "Bạn có muốn nhấn mạnh, điều chỉnh danh sách entities/concepts, hoặc bỏ qua phần nào trước khi ghi vào wiki không?"

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

For **every** identified entity → write/update in `wiki/entities/`.
For **every** identified concept → write/update in `wiki/concepts/`.

**Template Requirements:**
- **Entity pages:** Must include `## Context (Ngữ cảnh)` describing the role/system context in addition to `Overview` and `Key Facts`.
- **Concept pages:** Must include `## Examples (Ví dụ)` providing concrete illustrations in addition to `Definition` and `Key Points`.

**Update & Contradiction Strategy:**
1. Append new source to `sources:` array in frontmatter.
2. Add new facts with citations `(from [[source-slug]])`. Never delete existing valid facts.
3. **Contradictions:** Never silently overwrite. When a claim conflicts with existing knowledge, append to or create:
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
