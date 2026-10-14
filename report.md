# Báo Cáo Benchmark wiki-ingest: Đo Lường Sai Lệch Reasoning LLM

> **Reasoning Stability Index (RSI):** `65.0%` (🟡 KHÁ / TRUNG BÌNH)
> **Số lượt chạy độc lập (Runs):** 3 lượt

## 1. Bảng Chỉ Số Toàn Diện (Stability, Coverage & Faithfulness)

| Chỉ số | Kết quả | Ý nghĩa & Đánh giá |
|---|---|---|
| **Chỉ số Ổn định Tổng hợp (RSI)** | **`65.0%`** | Điểm trung bình trọng số toàn diện |
| **Độ bao phủ Nguồn (Source Coverage)** | `0.0%` | Tránh bỏ sót các phần, số liệu trong source |
| **Độ trung thực (Faithfulness)** | `0.0%` | Tránh LLM tự bịa kiến thức không có trong source |
| **Trùng khớp Thực thể (Entity Jaccard)** | `100.0%` | Tính ổn định nhận diện thực thể qua các run |
| **Trùng khớp Khái niệm (Concept Jaccard)** | `100.0%` | Tính ổn định nhận diện khái niệm qua các run |
| **Trùng khớp Mạng lưới Wikilinks (Graph Jaccard)** | `100.0%` | Tính bền vững của đồ thị liên kết chéo |
| **Điểm Tuân thủ Quy chuẩn (Quality Score)** | `0.0/100` | Frontmatter, song ngữ, 0 broken link |

## 2. Thống Kê Chi Tiết Từng Lượt Chạy (Per-Run Overview)

| Run ID | Pages | Entities | Concepts | Coverage | Faithfulness | Missed Units | Bịa đặt / Ungrounded | Quality |
|---|---|---|---|---|---|---|---|---|
| `run_1` | 0 | 0 | 0 | 0.0% | 0.0% | 42 | 0 | 0.0/100 |
| `run_2` | 0 | 0 | 0 | 0.0% | 0.0% | 42 | 0 | 0.0/100 |
| `run_3` | 0 | 0 | 0 | 0.0% | 0.0% | 42 | 0 | 0.0/100 |

## 3. Phân Tích Thực Thể & Khái Niệm: Cốt Lõi vs Chập Chờn

- **Entities Cốt lõi (100% các run đều có):** `0` — `Không có`
- **Entities Chập chờn (Flaky):** `0` — `Không có`

- **Concepts Cốt lõi (100% các run đều có):** `0` — `Không có`
- **Concepts Chập chờn (Flaky):** `0` — `Không có`

## 5. Phân Tích Nội Dung Bị Bỏ Sót (Source Omission / Missed Content)

Các thông tin hoặc số liệu có trong source nhưng bị LLM bỏ qua:

### Lượt chạy `run_1` bỏ sót (42 mục):
- ❌ Metric: 1
- ❌ Metric: 2
- ❌ Metric: 2026
- ❌ Metric: 24
- ❌ Metric: 2500ms
- ❌ Metric: 3
- ❌ Metric: 3 lần
- ❌ Metric: 3.1
- *(và 34 mục khác...)*

### Lượt chạy `run_2` bỏ sót (42 mục):
- ❌ Metric: 1
- ❌ Metric: 2
- ❌ Metric: 2026
- ❌ Metric: 24
- ❌ Metric: 2500ms
- ❌ Metric: 3
- ❌ Metric: 3 lần
- ❌ Metric: 3.1
- *(và 34 mục khác...)*

### Lượt chạy `run_3` bỏ sót (42 mục):
- ❌ Metric: 1
- ❌ Metric: 2
- ❌ Metric: 2026
- ❌ Metric: 24
- ❌ Metric: 2500ms
- ❌ Metric: 3
- ❌ Metric: 3 lần
- ❌ Metric: 3.1
- *(và 34 mục khác...)*
