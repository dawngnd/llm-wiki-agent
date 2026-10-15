# Ingest Quality Checklist

## Pre-Ingest
- [ ] Project path validated (chứa thư mục `wiki/`)
- [ ] Metadata directory `wiki/.meta/` tồn tại, `ingest-hashes.json` đã sẵn sàng
- [ ] Source file readable and text-based (Markdown)
- [ ] Hash (SHA256) của source file đã được tính và kiểm tra (chưa ingest hoặc force)
- [ ] Searched existing wiki pages for duplicates (grep / filename scan)

## During Ingest
- [ ] Phase 1a & 1b: Phân tích cấu trúc & ngữ nghĩa thành công
- [ ] **Image/SVG Discovery:** Đã scan toàn bộ image references (`![](...)`, `<img>`, inline `<svg>`) trong source
- [ ] **Asset Copying:** Ảnh/SVG local đã được copy vào `wiki/assets/`, đường dẫn đã được rewrite
- [ ] **Inline SVG:** Các block `<svg>...</svg>` đã được extract thành file `.svg` riêng trong `wiki/assets/`
- [ ] **Missing assets flagged:** Ảnh referenced nhưng file không tồn tại đã được báo cáo cho user
- [ ] **Structured Content Inventory:** Đã scan và đếm toàn bộ code blocks, math formulas, tables, mermaid diagrams, blockquotes trong source
- [ ] **Structured Content Mapping:** Mỗi structured block đã được gán target page và section cụ thể
- [ ] **Code blocks preserved:** Tất cả code blocks (` ```lang `) giữ nguyên vẹn — đúng language tag, indentation, comments
- [ ] **Math formulas preserved:** Tất cả `$$...$$` block math và `$...$` inline math giữ nguyên vẹn cú pháp LaTeX
- [ ] **Tables preserved:** Tất cả markdown tables giữ nguyên vẹn — đúng alignment, số cột/hàng
- [ ] **Mermaid/diagrams preserved:** Tất cả ` ```mermaid ` và text diagrams giữ nguyên vẹn
- [ ] **Vietnamese context added:** Mỗi structured block có caption/giải thích tiếng Việt kèm theo
- [ ] Confirmation Gate: User đã duyệt danh sách takeaways, entities, concepts, media assets, structured content
- [ ] **Language Rule:** Nội dung wiki hoàn toàn bằng Tiếng Việt với bilingual headers/technical terms (bất kể ngôn ngữ file gốc)
- [ ] Source summary page tạo trong `wiki/sources/` có mục `## Questions (Câu hỏi mở)`
- [ ] Tối đa hóa entity & concept: Mọi thực thể/khái niệm được nhắc đến đều có page (kể cả stub)
- [ ] Entity page có section `## Context (Ngữ cảnh)`
- [ ] Concept page có section `## Examples (Ví dụ)`
- [ ] Synthesis opportunity check (Phase 4.5): Đã đối chiếu nếu có ≥2 sources cùng chủ đề
- [ ] Wikilinks hai chiều (bidirectional) đầy đủ
- [ ] Naming conventions tuân thủ: kebab-case cho filename và wikilinks
- [ ] Không có mâu thuẫn (contradictions) bị bỏ qua hay ghi đè âm thầm

## Post-Ingest
- [ ] `wiki/index.md` đã cập nhật các trang mới
- [ ] `wiki/log.md` đã ghi nhận hoạt động ingest
- [ ] `wiki/.meta/ingest-hashes.json` đã ghi nhận SHA256, danh sách pages ảnh hưởng, và `assets_copied`
- [ ] Broken links check: Toàn bộ wikilinks mới trỏ tới các file thực tế tồn tại
- [ ] **Broken image check:** Toàn bộ image references trong wiki pages mới trỏ tới file thực tế tồn tại
- [ ] Báo cáo kết quả đầy đủ và gợi ý các bước kế tiếp (`wiki-lint`, `wiki-research`, `wiki-graph`)

## Quality Gates
- [ ] Source page chỉ nêu sự thật khách quan (không tự diễn giải/phán xét)
- [ ] Ngôn ngữ tuân thủ 100% chuẩn song ngữ Việt - Anh của wiki
- [ ] Mỗi wikilink target file phải tồn tại trên ổ đĩa
- [ ] Frontmatter chứa đầy đủ các trường bắt buộc (`title`, `type`, `category`, `created`, `updated`, `tags`, `sources`)
- [ ] Frontmatter `type` field khớp với tên thư mục chứa
- [ ] Frontmatter `category` field tồn tại và có giá trị kebab-case hợp lệ
- [ ] Không có PascalCase hay Title Case trong wikilinks
- [ ] Hash SHA256 được lưu chính xác trong registry
- [ ] **Zero structured content loss:** Số lượng code blocks, math formulas, tables trong wiki pages ≥ số lượng trong source (cho phép nhân bản, không cho phép mất)
- [ ] **Code blocks nguyên vẹn:** Không tự ý sửa code, thêm/bớt dòng, thay đổi indentation hay language tag
- [ ] **Math formulas nguyên vẹn:** Không tự ý đơn giản hóa, chuyển đổi format, hay lược bỏ công thức
