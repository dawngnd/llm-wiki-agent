# Ingest Quality Checklist

## Pre-Ingest
- [ ] Project path validated (chứa thư mục `wiki/`)
- [ ] Metadata directory `wiki/.meta/` tồn tại, `ingest-hashes.json` đã sẵn sàng
- [ ] Source file readable and text-based (Markdown)
- [ ] Hash (SHA256) của source file đã được tính và kiểm tra (chưa ingest hoặc force)
- [ ] Searched existing wiki pages for duplicates (grep / filename scan)

## During Ingest
- [ ] Phase 1a & 1b: Phân tích cấu trúc & ngữ nghĩa thành công
- [ ] Confirmation Gate: User đã duyệt danh sách takeaways, entities, concepts
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
- [ ] `wiki/.meta/ingest-hashes.json` đã ghi nhận SHA256 và danh sách pages ảnh hưởng
- [ ] Broken links check: Toàn bộ wikilinks mới trỏ tới các file thực tế tồn tại
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
