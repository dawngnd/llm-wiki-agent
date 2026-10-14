# Báo Cáo Benchmark wiki-ingest: Đo Lường Sai Lệch Reasoning LLM

> **Reasoning Stability Index (RSI):** `70.97%` (🟡 KHÁ / TRUNG BÌNH)
> **Số lượt chạy độc lập (Runs):** 3 lượt

## 1. Bảng Chỉ Số Toàn Diện (Stability, Coverage & Faithfulness)

| Chỉ số | Kết quả | Ý nghĩa & Đánh giá |
|---|---|---|
| **Chỉ số Ổn định Tổng hợp (RSI)** | **`70.97%`** | Điểm trung bình trọng số toàn diện |
| **Độ bao phủ Nguồn (Source Coverage)** | `None%` | Tránh bỏ sót các phần, số liệu trong source |
| **Độ trung thực (Faithfulness)** | `None%` | Tránh LLM tự bịa kiến thức không có trong source |
| **Trùng khớp Thực thể (Entity Jaccard)** | `55.56%` | Tính ổn định nhận diện thực thể qua các run |
| **Trùng khớp Khái niệm (Concept Jaccard)** | `77.78%` | Tính ổn định nhận diện khái niệm qua các run |
| **Trùng khớp Mạng lưới Wikilinks (Graph Jaccard)** | `54.87%` | Tính bền vững của đồ thị liên kết chéo |
| **Điểm Tuân thủ Quy chuẩn (Quality Score)** | `100.0/100` | Frontmatter, song ngữ, 0 broken link |

## 2. Thống Kê Chi Tiết Từng Lượt Chạy (Per-Run Overview)

| Run ID | Pages | Entities | Concepts | Coverage | Faithfulness | Missed Units | Bịa đặt / Ungrounded | Quality |
|---|---|---|---|---|---|---|---|---|
| `run_1` | 6 | 1 | 4 | N/A | N/A | 0 | 0 | 100.0/100 |
| `run_2` | 6 | 1 | 4 | N/A | N/A | 0 | 0 | 100.0/100 |
| `run_3` | 10 | 3 | 6 | N/A | N/A | 0 | 0 | 100.0/100 |

## 3. Phân Tích Thực Thể & Khái Niệm: Cốt Lõi vs Chập Chờn

- **Entities Cốt lõi (100% các run đều có):** `1` — `transformer`
- **Entities Chập chờn (Flaky):** `2` — `agent, decoder-only`

- **Concepts Cốt lõi (100% các run đều có):** `4` — `attention-mechanism, kv-cache, query-key-value, softmax`
- **Concepts Chập chờn (Flaky):** `2` — `causal-heatmap, scaled-dot-product-attention`
