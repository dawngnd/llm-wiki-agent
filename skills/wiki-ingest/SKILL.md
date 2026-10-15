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
│   ├── assets/       # Images, SVGs, diagrams referenced by wiki pages
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
for dir in "$PROJECT_PATH"/wiki/{.meta,assets,sources,entities,concepts,synthesis}; do
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
5. **Handling images, SVGs, and diagrams:** Scan the source for **all** media references and preserve them in the wiki.

#### Image & SVG Discovery

Scan the source file for all image references and inline SVGs:

```bash
# Find all markdown image references: ![alt](path)
grep -oP '!\[([^\]]*)\]\(([^)]+)\)' "$SOURCE_FILE"

# Find all HTML img tags: <img src="...">
grep -oP '<img[^>]+src="([^"]+)"' "$SOURCE_FILE"

# Find inline SVG blocks: <svg>...</svg>
grep -cP '<svg[\s>]' "$SOURCE_FILE"
```

Classify each reference:
- **Local file reference** (`![](./images/arch.png)`, `![](../diagrams/flow.svg)`) — resolve path relative to source file location.
- **Absolute path reference** (`![](/home/user/img.png)`) — use as-is.
- **URL reference** (`![](https://example.com/img.png)`) — preserve URL as-is, do NOT download.
- **Inline SVG** (`<svg>...</svg>` embedded directly in markdown) — extract and save as file.

#### Asset Copying (Sao chép tài nguyên media)

For each **local or absolute** image/SVG reference found:

```bash
ASSETS_DIR="$PROJECT_PATH/wiki/assets"

# Resolve the image path relative to the source file's directory
SOURCE_DIR=$(dirname "$SOURCE_FILE")
IMG_REF="path-from-markdown"  # e.g., ./images/arch.png
IMG_PATH=$(realpath -m "$SOURCE_DIR/$IMG_REF" 2>/dev/null || echo "$IMG_REF")

if [ -f "$IMG_PATH" ]; then
  BASENAME=$(basename "$IMG_PATH")
  DEST="$ASSETS_DIR/$BASENAME"

  # Avoid collision: if same name exists with different content, prefix with hash
  if [ -f "$DEST" ]; then
    EXISTING_HASH=$(sha256sum "$DEST" | awk '{print $1}')
    NEW_HASH=$(sha256sum "$IMG_PATH" | awk '{print $1}')
    if [ "$EXISTING_HASH" != "$NEW_HASH" ]; then
      SHORT_HASH=$(echo "$NEW_HASH" | cut -c1-8)
      DEST="$ASSETS_DIR/${SHORT_HASH}-${BASENAME}"
    fi
  fi

  cp "$IMG_PATH" "$DEST"
  echo "🖼️ Copied asset: $BASENAME → $DEST"
else
  echo "⚠️ Missing asset: $IMG_PATH (referenced in source but file not found)"
fi
```

For **inline SVGs** (`<svg>...</svg>` blocks embedded in the markdown):
1. Extract each SVG block.
2. Generate a descriptive filename based on surrounding context (e.g., `architecture-diagram.svg`, `flow-chart.svg`).
3. Save to `wiki/assets/<descriptive-name>.svg`.
4. Replace the inline SVG block with a markdown image reference: `![description](../assets/<descriptive-name>.svg)`.

#### Path Rewriting in Wiki Pages (Cập nhật đường dẫn)

When writing wiki pages (source summary, entity, concept pages), **rewrite all image paths** to point to `wiki/assets/`:

| Original reference in source | Rewritten reference in wiki page |
|---|---|
| `![arch](./images/arch.png)` | `![arch](../assets/arch.png)` |
| `![flow](../diagrams/flow.svg)` | `![flow](../assets/flow.svg)` |
| `![diagram](/absolute/path/to/img.png)` | `![diagram](../assets/img.png)` |
| `<img src="./img.png">` | `![img](../assets/img.png)` |
| `<svg>...</svg>` (inline) | `![description](../assets/descriptive-name.svg)` |
| `![ext](https://example.com/img.png)` | `![ext](https://example.com/img.png)` *(unchanged)* |

> **Note:** Use relative paths (`../assets/`) from the wiki page's directory to `wiki/assets/`. Adjust depth if the page is nested deeper.

#### Rules (Quy tắc xử lý media)

- **Không bao giờ bỏ sót ảnh/SVG:** Mọi image reference trong source PHẢI được bảo toàn trong wiki page output.
- **Ảnh phục vụ nội dung:** Nếu ảnh chứa dữ liệu có cấu trúc (kiến trúc hệ thống, flowchart, schema, biểu đồ), mô tả nội dung ảnh bằng text trong phần phân tích (Phase 1b) **ngoài việc** giữ lại link ảnh.
- **Alt text bắt buộc:** Mọi ảnh trong wiki page phải có alt text mô tả (`![Kiến trúc hệ thống X](../assets/arch.png)`), không để trống (`![](...)`) .
- **Naming convention:** File ảnh trong `wiki/assets/` giữ nguyên tên gốc. Nếu tên gốc không rõ ràng (e.g., `image1.png`), đổi thành tên mô tả kebab-case.
- **Broken image check:** Sau khi ghi wiki page, kiểm tra mọi image reference trỏ tới file thực tế tồn tại (tương tự broken wikilink check ở Phase 5).

6. **Handling structured content (Bảo toàn nội dung có cấu trúc):** Scan và lập danh sách toàn bộ structured content blocks trong source. Các nội dung này PHẢI được bảo toàn nguyên vẹn trong wiki pages — **không được tóm tắt, lược bỏ, hay diễn giải lại**.

#### Structured Content Inventory (Kiểm kê nội dung có cấu trúc)

Scan source file và phân loại mỗi structured block tìm được:

| Content type | Detection pattern | Ví dụ |
|---|---|---|
| **Code blocks** | ` ```language ... ``` ` hoặc indented 4 spaces | Code examples, config snippets, CLI commands |
| **Inline code** | `` `code` `` | Tên hàm, biến, class, lệnh ngắn |
| **Math formulas (LaTeX)** | `$$...$$` (block) hoặc `$...$` (inline), `\[...\]`, `\(...\)` | Công thức toán học, phương trình |
| **Tables** | `\| ... \| ... \|` markdown tables | Bảng so sánh, bảng dữ liệu, ma trận |
| **Mermaid diagrams** | ` ```mermaid ... ``` ` | Flowcharts, sequence diagrams, state diagrams |
| **Blockquotes** | `> ...` lines (trích dẫn có ý nghĩa nội dung) | Trích dẫn quan trọng, định nghĩa chính thức |
| **Ordered/numbered lists** | Multi-level numbered lists mô tả quy trình/thuật toán | Steps, algorithms, procedures |
| **ASCII art / text diagrams** | Pre-formatted text blocks mô tả cấu trúc | Architecture layouts, tree structures |

```bash
# Count structured content blocks in source
echo "=== Structured Content Inventory ==="
echo "Code blocks: $(grep -c '^\`\`\`' "$SOURCE_FILE" | awk '{print int($1/2)}')"
echo "Math blocks ($$): $(grep -c '^\$\$' "$SOURCE_FILE" | awk '{print int($1/2)}')"
echo "Inline math ($): $(grep -oP '(?<!\$)\$(?!\$)[^$]+\$(?!\$)' "$SOURCE_FILE" | wc -l)"
echo "Tables: $(grep -c '^|.*|.*|$' "$SOURCE_FILE")"
echo "Mermaid blocks: $(grep -c '^\`\`\`mermaid' "$SOURCE_FILE")"
echo "Blockquotes: $(grep -c '^>' "$SOURCE_FILE")"
```

#### Preservation Rules (Quy tắc bảo toàn)

**🔒 Quy tắc tối thượng: Không bao giờ mất nội dung structured.**

**Code blocks & examples:**
- Copy **nguyên vẹn** vào wiki page phù hợp — giữ đúng ngôn ngữ (` ```python `, ` ```java `, ...), indentation, comments.
- Đặt code trong section phù hợp nhất: `## Examples (Ví dụ)` cho concept pages, `## Key Facts (Thông tin chính)` cho entity pages, hoặc inline trong phần nội dung liên quan.
- Nếu code block **minh họa một concept cụ thể** → đặt trong concept page tương ứng.
- Nếu code block **demo một entity/tool** → đặt trong entity page tương ứng.
- Nếu code block **chung cho toàn bộ tài liệu** → đặt trong source summary page.
- **Thêm ngữ cảnh tiếng Việt** trước mỗi code block để giải thích mục đích:
  ```markdown
  Ví dụ triển khai Attention mechanism bằng PyTorch:

  ```python
  import torch
  ...
  ```
  ```

**Math formulas (Công thức toán học):**
- Copy **nguyên vẹn** cả block math (`$$...$$`) và inline math (`$...$`).
- Giữ đúng cú pháp LaTeX/KaTeX gốc — không chuyển đổi format.
- **Thêm giải thích tiếng Việt** sau mỗi công thức quan trọng:
  ```markdown
  $$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

  Trong đó: $Q$ là Query, $K$ là Key, $V$ là Value, $d_k$ là chiều (dimension) của Key vector.
  ```
- Nếu source dùng dạng khác (HTML MathML, image-based math), chuyển sang LaTeX `$$` nếu có thể, hoặc giữ nguyên dạng gốc.

**Tables (Bảng biểu):**
- Copy **nguyên vẹn** markdown tables. Giữ đúng alignment (`:---`, `:---:`, `---:`).
- Nếu table > 8 cột hoặc > 20 hàng, giữ nguyên nhưng thêm caption tiếng Việt phía trên.
- Nếu source dùng HTML `<table>`, chuyển sang markdown table khi có thể. Nếu table quá phức tạp (merged cells, colspan), giữ nguyên HTML.

**Mermaid diagrams:**
- Copy **nguyên vẹn** ` ```mermaid ` blocks.
- Thêm caption tiếng Việt phía trên diagram:
  ```markdown
  Quy trình xử lý request trong hệ thống:

  ```mermaid
  flowchart TD
    A[Request] --> B{Auth?}
    ...
  ```
  ```

**Blockquotes (Trích dẫn):**
- Phân loại: **Trích dẫn nội dung** (chứa kiến thức/định nghĩa) vs **Trích dẫn tu từ** (chỉ mang tính decorative).
- Trích dẫn nội dung → bảo toàn nguyên vẹn trong wiki page + thêm attribution nếu có.
- Trích dẫn tu từ → có thể lược bỏ nếu không mang kiến thức mới.

**ASCII art / Text diagrams:**
- Wrap trong ` ``` ` code block (không language tag) để bảo toàn formatting.
- Thêm caption tiếng Việt giải thích nội dung diagram.

#### Placement Strategy (Chiến lược phân bổ nội dung)

Khi tạo wiki pages, phân bổ structured content theo quy tắc:

| Structured content | Target page | Target section |
|---|---|---|
| Code example minh họa concept X | `wiki/concepts/x.md` | `## Examples (Ví dụ)` |
| Code example demo entity/tool Y | `wiki/entities/y.md` | `## Key Facts (Thông tin chính)` hoặc tạo `## Code Examples (Ví dụ mã nguồn)` |
| Math formula định nghĩa concept X | `wiki/concepts/x.md` | `## Definition (Định nghĩa)` hoặc `## Key Points (Điểm chính)` |
| Table so sánh nhiều entities | `wiki/sources/source.md` | `## Key Claims (Các khẳng định chính)` |
| Table thuộc tính của 1 entity | `wiki/entities/entity.md` | `## Key Facts (Thông tin chính)` |
| Mermaid diagram quy trình concept X | `wiki/concepts/x.md` | `## Definition (Định nghĩa)` hoặc `## Key Points (Điểm chính)` |
| General-purpose code/math/diagram | `wiki/sources/source.md` | Section phù hợp nhất |

> **Quy tắc nhân bản:** Nếu một code block/formula phục vụ nhiều pages, đặt bản đầy đủ ở page chính (most relevant) và tham chiếu từ các pages khác: `Xem ví dụ code tại [[concept-slug#examples]]`.

### Phase 1b: Semantic Analysis & Entity Extraction

Extract core information with a **controlled granularity policy** — create standalone pages for significant knowledge units, inline minor mentions:

- **3-5 Key Takeaways:** Core points and thesis of the document.
- **Entities:** All people, organizations, tools, products, APIs, services mentioned. Apply **Entity Granularity Rules** (see below) to decide standalone page vs inline mention.
- **Concepts:** All ideas, frameworks, architectural patterns, theories, workflows. Apply **Concept Granularity Rules** (see below) to decide standalone page vs inline mention.
- **Category determination:** Xác định lĩnh vực kiến thức chính (category) của tài liệu dựa trên nội dung và chủ đề. Giá trị category là chuỗi kebab-case, ví dụ: `ai`, `ai-agent`, `system-design`, `java-programming`, `finance`, `economics`, `data-analyst`, `devops`. Nếu tài liệu thuộc nhiều lĩnh vực, chọn lĩnh vực **chính** (primary domain).
- **Questions & Gaps:** Open issues, ambiguities, or unanswered points raised in the source.
- **Potential Wikilinks:** Map extracted terms to existing pages in the wiki.
- **Structured Content Mapping:** Cho mỗi structured block đã kiểm kê ở Phase 1a step 6, xác định target page và section cụ thể nơi nó sẽ được đặt. Đảm bảo mọi code block, math formula, table, mermaid diagram đều có "chủ sở hữu" — không block nào bị bỏ lại.

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
- **Category đề xuất:** [category-value] — Lý do: [giải thích ngắn]
- **Key Takeaways:** [3-5 điểm]
- **Entities phát hiện:**
  - `[STANDALONE]` entity-name — Lý do: ≥3 facts / primary subject → full page
  - `[INLINE in parent-page] + stub` entity-name — Lý do: ≤2 mentions / variant of parent → stub page + inline in parent
- **Concepts phát hiện:**
  - `[STANDALONE]` concept-name — Lý do: standalone definition + ≥2 key points → full page
  - `[INLINE in parent-concept] + stub` concept-name — Lý do: sub-step / visualization → stub page + inline in parent
- **Media assets (Ảnh/SVG):**
  - 🖼️ `N` ảnh/SVG tìm thấy → sẽ copy vào `wiki/assets/`
  - ✅ Tìm thấy: `image1.png`, `diagram.svg`, ...
  - ⚠️ Không tìm thấy file: `missing-image.png` (path không tồn tại)
  - 🔗 URL references (giữ nguyên): `https://...`
- **Structured content (Nội dung có cấu trúc):**
  - 📝 Code blocks: `N` blocks (Python: X, Java: Y, ...) → sẽ đặt tại [target pages]
  - 📐 Math formulas: `N` block + `M` inline → sẽ đặt tại [target pages]
  - 📊 Tables: `N` bảng → sẽ đặt tại [target pages]
  - 📈 Mermaid diagrams: `N` diagrams → sẽ đặt tại [target pages]
  - 💬 Blockquotes: `N` trích dẫn nội dung (bỏ qua `M` trích dẫn tu từ)
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
- Frontmatter with `title: "..."`, `type: sources`, `category: <category-value>`, `tags: [...]`, `sources: [filename]`, `created`, `updated`
- `# Title (Tiêu đề)`
- `## Summary (Tóm tắt)`
- `## Key Claims (Các khẳng định chính)` — bao gồm tables/diagrams liên quan nếu có
- `## Key Formulas (Công thức chính)` — *tùy chọn, chỉ khi source chứa math formulas*
- `## Code Examples (Ví dụ mã nguồn)` — *tùy chọn, chỉ khi source chứa code blocks chung*
- `## Entities Mentioned (Thực thể được nhắc đến)`
- `## Concepts Covered (Khái niệm được đề cập)`
- `## Questions (Câu hỏi mở)`

> **Structured content rule:** Mọi code block, math formula, table, mermaid diagram từ source mà không thuộc riêng entity/concept nào PHẢI được đặt trong source summary page. Không để mất.

---

### Phase 4: Create or Update Entity and Concept Pages

For each entity/concept extracted in Phase 1b, create or update pages based on classification:

**`[STANDALONE]` items → Full page:**
- Write/update in `wiki/entities/` or `wiki/concepts/` with complete content.
- **Entity pages:** Must include `## Context (Ngữ cảnh)` describing the role/system context in addition to `Overview` and `Key Facts`. Thêm `## Code Examples (Ví dụ mã nguồn)` nếu source chứa code examples liên quan đến entity.
- **Concept pages:** Must include `## Examples (Ví dụ)` providing concrete illustrations in addition to `Definition` and `Key Points`. Đặt math formulas trong `## Definition (Định nghĩa)`, code examples trong `## Examples (Ví dụ)`, diagrams/tables trong section phù hợp nhất.

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
2. Verify `category` field exists; if missing, add based on page content and current source's category.
3. Add new facts with citations `(from [[source-slug]])`. Never delete existing valid facts.
4. **Stub → Full upgrade:** If an existing stub page receives ≥3 new facts from the current source, upgrade it to a full page and remove `stub: true` from frontmatter.
5. **Contradictions:** Never silently overwrite. When a claim conflicts with existing knowledge, append to or create:
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

Verify all image references resolve to actual files:
```bash
# Check image references in newly created/updated wiki pages
for page in "$PROJECT_PATH/wiki/sources/new-page.md" "$PROJECT_PATH/wiki/entities/entity.md"; do
  grep -oP '!\[[^\]]*\]\(\K[^)]+' "$page" 2>/dev/null | while read img_ref; do
    # Skip URL references
    echo "$img_ref" | grep -qP '^https?://' && continue
    # Resolve relative path from the page's directory
    PAGE_DIR=$(dirname "$page")
    IMG_PATH=$(realpath -m "$PAGE_DIR/$img_ref" 2>/dev/null || echo "$img_ref")
    [ ! -f "$IMG_PATH" ] && echo "BROKEN IMAGE: $img_ref (in $page)"
  done
done
```
Resolve broken image links by copying the missing asset to `wiki/assets/` or fixing the path.

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
     "pages_updated": ["concept-2"],
     "assets_copied": ["arch-diagram.png", "flow.svg"]
   }
   ```

---

### Phase 7: Report Results & Cross-Skill Suggestions

Present a clean summary to the user:
- Pages created & updated (with clickable wikilinks)
- Assets copied to `wiki/assets/` (list filenames)
- Missing assets not found on disk (⚠️ warnings)
- Broken image references verified/fixed
- Contradictions recorded (if any)
- Broken wikilinks verified/fixed
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
- **Bảo toàn structured content:** Code blocks, math formulas (`$$`, `$`), tables, mermaid diagrams, blockquotes có nội dung kiến thức — PHẢI được giữ nguyên vẹn trong wiki pages. Không tóm tắt code thành prose, không lược bỏ công thức, không bỏ table. Thêm giải thích tiếng Việt bên cạnh nhưng không thay thế nội dung gốc.
- **Ảnh và SVG:** Mọi image reference từ source PHẢI được bảo toàn. Copy ảnh local vào `wiki/assets/`, rewrite paths. Không bao giờ bỏ sót ảnh.
