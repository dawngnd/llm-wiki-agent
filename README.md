# LLM Wiki Agent Plugin

> Biến coding agent (Claude Code, Codex, Antigravity CLI) thành wiki ingest/maintenance agent — truy cập filesystem trực tiếp, tách biệt hoàn toàn với MCP llm-wiki.

## Tổng quan

Plugin này cung cấp bộ skills để coding agent có thể duy trì wiki knowledge base bằng cách đọc/ghi files trực tiếp trên filesystem. **Không phụ thuộc** vào LLM Wiki desktop app hay MCP server.

### Capabilities

| Skill | Chức năng |
|-------|-----------|
| `wiki-status` | Thống kê wiki: đếm pages, tìm broken links, hoạt động gần đây |
| `wiki-ingest` | Nạp tài liệu nguồn thành wiki pages có cấu trúc |
| `wiki-query` | Tìm kiếm và tổng hợp kiến thức từ wiki |
| `wiki-lint` | Health check 10 bước: links, orphans, contradictions, frontmatter... |
| `wiki-graph` | Phân tích knowledge graph bằng cách parse wikilinks |
| `wiki-research` | Nghiên cứu sâu: cross-reference, gap analysis, synthesis |
| `wiki-maintenance` | Bảo trì: fix links, merge duplicates, sync index |
| `wiki-autonomous-ops` | Pipeline tự động 6 giai đoạn không cần can thiệp |

## Yêu cầu

- Một wiki project directory với cấu trúc:
  ```
  project/
  ├── wiki/
  │   ├── sources/      # Tóm tắt nguồn
  │   ├── entities/     # Người, tổ chức, sản phẩm
  │   ├── concepts/     # Ý tưởng, framework, pattern
  │   ├── synthesis/    # Phân tích, so sánh
  │   ├── index.md      # Mục lục
  │   └── log.md        # Activity log
  └── raw/              # Tài liệu nguồn chưa xử lý
  ```
- Một coding agent hỗ trợ plugins: Claude Code, Antigravity CLI, hoặc tương đương

## Cách hoạt động

```
Coding Agent
    │
    ▼
Skills (auto-activated by context)
    │
    ▼
Direct Filesystem Access
    ├── Read files (wiki/, raw/)
    ├── Write files (wiki pages)
    ├── grep/find (search & analysis)
    └── Bash scripts (automation)
```

**KHÔNG dùng:** MCP llm-wiki, REST API, LLM Wiki desktop app.

## Skills (Auto-activated)

Skills tự động kích hoạt khi agent nhận diện context phù hợp:

| Skill | Kích hoạt khi user nói... |
|-------|---------------------------|
| `wiki-status` | "kiểm tra wiki", "wiki stats", "bao nhiêu trang" |
| `wiki-ingest` | "nạp tài liệu", "ingest document", "process source" |
| `wiki-query` | "tìm trong wiki", "hỏi wiki", "what do I know about" |
| `wiki-lint` | "lint wiki", "check wiki health", "tìm lỗi wiki" |
| `wiki-graph` | "wiki graph", "show connections", "xem mối quan hệ" |
| `wiki-research` | "nghiên cứu sâu", "deep dive", "explore connections" |
| `wiki-maintenance` | "bảo trì wiki", "fix wiki issues", "dọn dẹp wiki" |
| `wiki-autonomous-ops` | "bảo trì tự động", "auto-maintain", "full wiki cycle" |

## Autonomous Pipeline

Chạy pipeline bảo trì tự động (không cần can thiệp):

```
Stage 1          Stage 2          Stage 3          Stage 4         Stage 5        Stage 6
Pre-flight  →  Source Discovery → Auto-Ingest → Lint Check → Maintenance → Report
(1 min)        (2 min)           (varies)      (5 min)      (5 min)        (1 min)
```

**Safety Guards:**
- Không bao giờ xóa content
- Không auto-resolve contradictions
- Max 5 sources/cycle
- Files >50KB flagged cho manual review
- Toàn bộ audit trail trong `wiki/log.md`

Chạy bằng: trigger skill `wiki-autonomous-ops` hoặc dùng `/goal`, `/schedule`.

## Quy ước Wiki

- **Ngôn ngữ:** Tiếng Việt, headers song ngữ `## Summary (Tóm tắt)`
- **Thuật ngữ:** Format song ngữ `Cache (Bộ nhớ đệm)`
- **Tên file:** kebab-case `.md` (`api-standard.md`)
- **Wikilinks:** `[[kebab-case-name]]` (không `.md`)
- **Tags:** `open-spec` (từ changelogs), `urd` (từ raw)
- **Source pages trùng tên:** thêm `-source` suffix

## So sánh với plugin llm-wiki (cũ)

| | llm-wiki (cũ) | llm-wiki-agent (mới) |
|---|---|---|
| Approach | Filesystem trực tiếp | Filesystem trực tiếp |
| Components | 3 skills | 8 skills + 4 references |
| Commands | 0 | 0 (tất cả là skills) |
| MCP dependency | Không | Không |
| Desktop app dependency | Không | Không |
| Autonomous mode | Không | 6-stage pipeline |
| Graph analysis | Không | Có (parse wikilinks) |
| Deep research | Không | Có |
| Quality checklists | Không | Có (references/) |

## License

MIT
