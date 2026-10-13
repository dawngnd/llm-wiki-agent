# Wiki Page Templates

## Source Summary Page

Location: `wiki/sources/`

```yaml
---
type: sources
tags: [relevant, tags]
sources: [original-filename.md]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

```markdown
# Title (Tiêu đề tài liệu nguồn)

**Source (Tài liệu nguồn):** original-filename.md
**Date Ingested (Ngày nạp):** YYYY-MM-DD
**Type (Loại):** article | paper | transcript | notes

## Summary (Tóm tắt)

Tóm tắt cấu trúc của nội dung tài liệu nguồn.

## Key Claims (Các khẳng định chính)

- Khẳng định 1
- Khẳng định 2

## Entities Mentioned (Thực thể được nhắc đến)

- [[entity-name]] — ngữ cảnh tóm tắt

## Concepts Covered (Khái niệm được đề cập)

- [[concept-name]] — ngữ cảnh tóm tắt

## Questions (Câu hỏi mở)

- Vấn đề hoặc câu hỏi chưa được làm rõ trong tài liệu nguồn
```

## Entity Page

Location: `wiki/entities/`

```yaml
---
type: entities
tags: [relevant, tags]
sources: [source-1.md, source-2.md]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

```markdown
# Entity Name (Tên thực thể)

## Overview (Tổng quan)

Mô tả thực thể.

## Context (Ngữ cảnh)

Mô tả bối cảnh entity xuất hiện, vai trò trong hệ thống hoặc mối liên kết nghiệp vụ.

## Key Facts (Thông tin chính)

- Fact 1 (from [[source-1]])
- Fact 2 (from [[source-2]])

## Related (Liên quan)

- [[related-entity]]
- [[related-concept]]
```

## Concept Page

Location: `wiki/concepts/`

```yaml
---
type: concepts
tags: [relevant, tags]
sources: [source-1.md, source-2.md]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

```markdown
# Concept Name (Tên khái niệm)

## Definition (Định nghĩa)

Định nghĩa rõ ràng.

## Key Points (Điểm chính)

- Điểm 1
- Điểm 2

## Examples (Ví dụ)

- Ví dụ minh họa thực tế cho khái niệm này.

## Related (Liên quan)

- [[related-entity]]
- [[related-concept]]
```

## Synthesis Page

Location: `wiki/synthesis/`

```yaml
---
type: synthesis
tags: [relevant, tags]
sources: [page-1.md, page-2.md]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

```markdown
# Analysis Title (Tiêu đề phân tích)

## Context (Bối cảnh)

Tại sao phân tích này quan trọng.

## Analysis (Phân tích)

Phân tích chi tiết với trích dẫn.

## Conclusions (Kết luận)

Các điểm rút ra chính.

## Sources (Nguồn tham khảo)

- [[source-1]] — relevance
- [[source-2]] — relevance
```
