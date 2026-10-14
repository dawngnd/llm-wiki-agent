# Hội thoại nghiên cứu chuyên sâu: Ba Vectơ (Query, Key, Value) trong Cơ chế Chú ý

- **Thời gian**: 2026-08-25
- **Chủ đề**: Giải thích chi tiết mục ## Ba vectơ trong wiki attention-mechanism, bản chất đại số tuyến tính, luồng tính toán 3 bước và ý nghĩa đối với kiến trúc Transformer & Agent.

---

## 1. Bản chất & Sự phân vai của Ba Vectơ (Query, Key, Value)

Trong kiến trúc Transformer, mỗi token đầu vào sau khi được chuyển thành vector nhúng không gian $X \in \mathbb{R}^{d_{model}}$ sẽ không được dùng trực tiếp trong phép tính tương đồng một cách đơn lẻ. Thay vào đó, mô hình sử dụng 3 ma trận trọng số có thể học được:
- $W_Q \in \mathbb{R}^{d_{model} \times d_k}$
- $W_K \in \mathbb{R}^{d_{model} \times d_k}$
- $W_V \in \mathbb{R}^{d_{model} \times d_v}$

Từ đó ánh xạ $X$ thành ba không gian chức năng chuyên biệt:
- **Query ($Q = X W_Q$)**: Đại diện cho "Yêu cầu tìm kiếm" do token hiện tại phát ra. Token tự hỏi: *"Tôi cần thông tin ngữ cảnh từ những token nào trong quá khứ để hoàn thiện ý nghĩa hoặc dự đoán token tiếp theo?"*
- **Key ($K = X W_K$)**: Đại diện cho "Thẻ định danh / Nhãn mô tả" của từng token trong ngữ cảnh. Dùng để đối sánh mức độ liên quan với truy vấn $Q$.
- **Value ($V = X W_V$)**: Đại diện cho "Nội dung thực tế" mà token đó mang lại. Khi $Q$ và $K$ khớp nhau, thông tin ngữ nghĩa chứa trong $V$ sẽ được trích xuất và tổng hợp.

### Tại sao cần tách thành 3 vector riêng biệt?
Nếu chỉ sử dụng một vector đại diện duy nhất $X$, một token sẽ bị ép phải đồng nhất:
1. Cách nó tìm kiếm thông tin khác.
2. Cách nó tự giới thiệu bản thân cho các token khác tìm kiếm.
3. Nội dung thông tin mà nó truyền tải cho downstream layers.

Việc phân tách qua 3 ma trận chiếu $W_Q, W_K, W_V$ giúp tăng bậc tự do biểu diễn, cho phép một token linh hoạt đóng các vai trò khác nhau tùy thuộc vào vị trí và ngữ cảnh.

---

## 2. Quy trình Tính toán Chú ý qua 3 Bước Toán học

### Bước 1: Tính điểm khớp (Attention Score)
Sử dụng tích vô hướng giữa Query hiện tại và Key của tất cả các token trước đó, chia cho hệ số co giãn $\sqrt{d_k}$ (để tránh bão hòa gradient tại vùng cực trị của Softmax):
$$\text{Score}_i = \frac{Q \cdot K_i^T}{\sqrt{d_k}}$$

### Bước 2: Chuẩn hóa xác suất phân phối (Attention Weights)
Áp dụng hàm Softmax để chuyển các điểm số thô thành phân phối xác suất hợp lệ có tổng bằng 1.0 (100%):
$$\alpha_i = \text{Softmax}(\text{Score}_i) = \frac{\exp(\text{Score}_i)}{\sum_j \exp(\text{Score}_j)}$$
Trọng số $\alpha_i \in [0, 1]$ thể hiện tỷ lệ phần trăm mức độ chú ý mà token hiện tại dành cho token thứ $i$.

### Bước 3: Tổng hợp có trọng số các Vector Giá trị (Weighted Sum)
Trộn thông tin ngữ nghĩa từ các vector $V$ theo tỷ lệ trọng số $\alpha$:
$$\text{Attention}(Q, K, V) = \sum_{i} \alpha_i V_i$$
Kết quả là một vector ngữ cảnh mới tích hợp thông tin liên quan từ toàn bộ chuỗi lịch sử.

---

## 3. Phân tích Ví dụ Minh họa: "Thời tiết ở Bắc Kinh thế nào?"

Xét chuỗi: `["Thời tiết", "ở", "Bắc Kinh", "thế nào"]` khi mô hình đang ở bước xử lý token `"thế nào"`:
1. **Phát sinh Query:** `"thế nào"` tạo ra vector $Q_{\text{"thế nào"}}$ mang ý nghĩa: *"Tìm từ nào chứa thông tin trạng thái/chủ thể cần được hỏi"*.
2. **Đối chiếu với các Key:**
   - So khớp với $K_{\text{"thời tiết"}}$ (nhãn khí hậu/trạng thái) $\rightarrow$ điểm cao nhất, trọng số $\alpha \approx 0.55$.
   - So khớp với $K_{\text{"Bắc Kinh"}}$ (nhãn địa danh) $\rightarrow$ điểm cao thứ nhì, trọng số $\alpha \approx 0.35$.
   - So khớp với $K_{\text{"ở"}}$ (hư từ/giới từ) $\rightarrow$ điểm rất thấp, trọng số $\alpha \approx 0.05$.
   - So khớp với chính nó $K_{\text{"thế nào"}}$ $\rightarrow$ tự chú ý thấp, trọng số $\alpha \approx 0.05$.
3. **Trích xuất Giá trị:**
   $$\text{Output} = 0.55 V_{\text{"thời tiết"}} + 0.35 V_{\text{"Bắc Kinh"}} + 0.05 V_{\text{"ở"}} + 0.05 V_{\text{"thế nào"}}$$
   Vector kết quả đại diện cho sự kết hợp ngữ nghĩa giữa "thời tiết" và "Bắc Kinh", tạo cơ sở cho việc dự đoán token kế tiếp mang thông tin dự báo thời tiết.

---

## 4. Ý nghĩa Kiến trúc & Liên kết Hệ thống

1. **Bản đồ nhiệt nhân quả (Causal Heatmap):**
   Trong kiến trúc Decoder-only autoregressive, token $i$ chỉ được phép chú ý đến các token $j \le i$. Vì vậy ma trận tương tác $Q \times K^T$ có cấu trúc tam giác dưới (lower triangular matrix).
2. **Cơ sở vật lý của KV Cache:**
   Khi sinh token mới $t+1$, các vector $K$ và $V$ của các token cũ $1 \dots t$ không hề thay đổi. Do đó, hệ thống chỉ cần tính $Q_{t+1}, K_{t+1}, V_{t+1}$, sau đó ghép $K_{t+1}, V_{t+1}$ vào bộ nhớ đệm KV Cache để tái sử dụng, giúp việc sinh token có độ phức tạp tính toán giảm từ $O(t^2)$ xuống $O(t)$.
