# Hệ Thống Benchmark & Kiểm Thử Độ Ổn Định Reasoning (wiki-ingest)

> Bộ công cụ kiểm thử tự động đo lường chất lượng, độ nhất quán và phát hiện **sai lệch reasoning (Reasoning Drift / Non-determinism)** khi LLM thực thi skill `wiki-ingest`.

---

## 1. Vấn đề: Sai lệch của LLM khi Ingest tài liệu

Khi sử dụng Large Language Models (LLM) để đọc hiểu, trích xuất thực thể và xây dựng kiến thức tự động (Personal Knowledge Base / Wiki), các lỗi suy luận phổ biến xuất hiện qua các lần chạy gồm:

1. **Phân mảnh Tên gọi (Slug Fragmentation / Naming Drift):**
   - Cùng một khái niệm nhưng mỗi lần chạy LLM lại đặt slug khác nhau. Ví dụ:
     - Lần 1: `[[query-key-value]]`
     - Lần 2: `[[qkv-attention]]`
     - Lần 3: `[[ba-vector-qkv]]`
   - **Hậu quả:** Hệ thống tạo ra nhiều trang rời rạc, không thể gom cụm và làm hỏng mạng liên kết (knowledge graph).
2. **Thực thể & Khái niệm Chập chờn (Flaky / Flickering Entities):**
   - Một số thực thể quan trọng chỉ được phát hiện ở 1 trong 3 lần chạy (chỉ số Jaccard thấp).
   - Ngược lại, xuất hiện những thực thể "rác" hoặc "ảo giác" (hallucinated) do LLM tự suy diễn từ tri thức nền mà văn bản gốc không hề đề cập.
3. **Bỏ sót Nội dung & Số liệu Nguồn (Source Omission / Missed Content):**
   - LLM tự ý đánh giá một số phần là "không quan trọng" và bỏ qua (ví dụ: các ràng buộc kỹ thuật `Timeout 3500ms`, `p99 latency 300ms`, các mục con hoặc ca sử dụng cụ thể).
4. **Bịa đặt Nội dung / Tri thức Ngoại lai (Hallucination / Ungrounded Claims):**
   - LLM tự ý đưa kiến thức đã học từ bên ngoài (pre-training priors) vào wiki mà tài liệu nguồn không hề đề cập (ví dụ: tự ý thêm RabbitMQ, Redis Sentinel, MongoDB, hoặc các số liệu tự chế).
5. **Trôi dạt Quy chuẩn Định dạng (Format & Schema Drift):**
   - Không tuân thủ tiêu đề song ngữ (`## Summary (Tóm tắt)`).
   - Thiếu các phần bắt buộc: `## Context (Ngữ cảnh)` trong Entities, `## Examples (Ví dụ)` trong Concepts.
   - Tạo ra broken wikilinks do trích dẫn sai tên slug.

---

## 2. Kiến trúc Hệ thống Kiểm thử

Hệ thống kiểm thử bao gồm các thành phần chính:

```
benchmark/
├── fixtures/                           # Bộ tài liệu chuẩn hóa
│   ├── qkv-attention.md                # Bài toán kỹ thuật toán học & kiến trúc sâu
│   ├── banking-drift-test.md           # Bài toán hệ thống ngân hàng (entities, số liệu, mâu thuẫn)
│   └── expected_golden.json            # Ground truth kỳ vọng: entities, concepts, metrics, bẫy ảo giác
├── run_eval.py                         # CLI Runner đa năng (đánh giá đơn lẻ + so sánh multi-run)
├── content_faithfulness.py             # Engine đo Coverage (tránh bỏ sót) & Faithfulness (tránh bịa đặt)
├── benchmark_ingest.py                 # Core analysis engine đo Jaccard, graph overlap, slug alias
├── test_eval_suite.py                  # Self-test tự động bảo đảm tính toàn vẹn của engine
└── README.md                           # Tài liệu hướng dẫn
```

---

## 3. Các Chỉ Số Đo Lường (Benchmark Metrics)

Hệ thống tính toán các chỉ số định lượng khách quan:

| Chỉ số | Cách tính | Ý nghĩa phát hiện lỗi LLM |
|---|---|---|
| **Reasoning Stability Index (RSI)** | Trọng số: `25% J_ent + 25% J_cpt + 15% J_graph + 15% Quality + 10% Coverage + 10% Faithfulness` | Điểm tổng hợp độ ổn định qua các lần chạy (0 - 100%) |
| **Độ bao phủ Nguồn (Source Coverage)** | $\frac{\text{Số IUs source có trong wiki}}{\text{Tổng số IUs của source}}$ | **Tránh bỏ sót:** Kiểm tra xem mọi section, số liệu, ràng buộc có được đưa vào wiki không |
| **Độ trung thực (Faithfulness)** | $\frac{\text{Số claims có căn cứ trong source}}{\text{Tổng claims trong wiki}} - \text{Penalties}$ | **Tránh bịa đặt:** Phát hiện các câu, thuật ngữ, số liệu ngoại lai không có trong source |
| **Entity Jaccard ($J_{ent}$)** | $\frac{\|E_1 \cap E_2\|}{\|E_1 \cup E_2\|}$ | Mức độ đồng thuận trích xuất thực thể giữa các run |
| **Concept Jaccard ($J_{cpt}$)** | $\frac{\|C_1 \cap C_2\|}{\|C_1 \cup C_2\|}$ | Mức độ đồng thuận trích xuất khái niệm giữa các run |
| **Graph Edge Jaccard ($J_{graph}$)** | $\frac{\|Edges_1 \cap Edges_2\|}{\|Edges_1 \cup Edges_2\|}$ | Độ bền vững của mạng lưới liên kết wikilinks |
| **Quality Checklist Score** | 10 tiêu chí kiểm tra tự động | Đảm bảo frontmatter, song ngữ, tiếng Việt, 0 broken link |
| **Slug Aliases Cluster** | Đo khoảng cách Levenshtein & Token Overlap | Phát hiện hiện tượng phân mảnh tên gọi |

---

## 4. Hướng Dẫn Sử Dụng (Workflow Khi Chỉnh Sửa Skill)

Mỗi khi bạn hoặc agent thực hiện refactor hoặc chỉnh sửa prompt trong `skills/wiki-ingest/SKILL.md`, hãy thực hiện 3 bước sau:

### Bước 1: Khởi tạo Sandbox sạch cho các lượt chạy
```bash
python3 benchmark/run_eval.py --init-sandbox /tmp/wiki_eval --runs 3
```
Lệnh này tạo 3 thư mục độc lập:
- `/tmp/wiki_eval/run_1/wiki/`
- `/tmp/wiki_eval/run_2/wiki/`
- `/tmp/wiki_eval/run_3/wiki/`

### Bước 2: Thực thi Ingest trên cùng một tài liệu Fixture
Cho Agent thực hiện ingest tài liệu `benchmark/fixtures/banking-drift-test.md` (hoặc `qkv-attention.md`) vào từng thư mục:
- Lần 1: Ingest vào `/tmp/wiki_eval/run_1`
- Lần 2: Ingest vào `/tmp/wiki_eval/run_2`
- Lần 3: Ingest vào `/tmp/wiki_eval/run_3`

*(Mỗi lần chạy bắt đầu từ ngữ cảnh độc lập để loại trừ bias)*

### Bước 3: Đánh giá Đơn Lẻ (Single Run Eval) đối chiếu Golden Truth
Kiểm tra xem một lần chạy có đạt chuẩn và khớp với Ground Truth hay không:
```bash
python3 benchmark/run_eval.py \
  --eval /tmp/wiki_eval/run_1 \
  --fixture banking-drift-test.md
```
Kết quả hiển thị:
- Điểm checklist quy chuẩn (Frontmatter, bilingual, 0 broken link).
- Entity Recall & Concept Recall so với ground truth.
- Cảnh báo ảo giác (phát hiện các thuật ngữ không có trong tài liệu).

### Bước 4: So Sánh Đa Lượt (Multi-Run Comparison) để đo Drift
Chạy phân tích so sánh giữa 3 lần chạy để xuất báo cáo Markdown:
```bash
python3 benchmark/run_eval.py \
  --compare /tmp/wiki_eval/run_1 /tmp/wiki_eval/run_2 /tmp/wiki_eval/run_3 \
  --report /tmp/benchmark_report.md
```

Hệ thống sẽ chỉ ra chính xác:
- **RSI Score:** Có bị sụt giảm không?
- **Danh sách Flaky Entities:** Các thực thể trôi dạt xuất hiện ở run này nhưng mất ở run kia.
- **Slug Aliases:** Danh sách các biến thể slug bị đặt tên khác nhau.

---

## 5. Các Kỹ Thuật Giúp "Harden" Skill Giảm Thiểu Sai Lệch Reasoning

Nếu điểm RSI < 80% hoặc xuất hiện nhiều Flaky Entities / Slug Aliases, hãy áp dụng các nguyên tắc sau vào `SKILL.md`:

1. **Quy tắc Chuẩn hóa Slug (Canonical Slug Rules):**
   - Luôn sử dụng danh từ số ít (singular).
   - Giữ nguyên định danh tiếng Anh kỹ thuật theo chuẩn ngành (ví dụ: `kv-cache`, không dịch thành `bo-nho-dem-kv`).
   - Thứ tự từ trong cụm: `[chủ_thể]-[chức_năng]` (ví dụ: `redis-cache`, `kafka-cluster`).
2. **Ngưỡng Nhận Diện Khái Niệm (Concept Qualification Threshold):**
   - Không biến mọi danh từ thành concept. Chỉ tạo trang concept nếu nó là một kiến trúc, giải thuật, giao thức hoặc mẫu thiết kế có từ 2 liên kết trở lên.
3. **Neo Sự Thật (Factual Anchoring):**
   - Yêu cầu mọi Key Claim phải dẫn xuất trực tiếp từ các đoạn trích/số liệu có trong bài, cấm tự ý bổ sung kiến thức ngoại lai.
4. **Xác thực Mạng Lưới Wikilink Tức thì (Immediate Link Resolution):**
   - Mỗi khi nhắc đến một `[[wikilink]]`, bắt buộc kiểm tra và tạo ngay trang stub tương ứng để loại trừ hoàn toàn broken link.
