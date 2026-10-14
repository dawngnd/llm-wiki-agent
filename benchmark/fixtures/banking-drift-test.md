# Tài liệu Thiết kế Kỹ thuật: Hệ thống Xử lý Giao dịch Thanh toán V2

- **Mã hệ thống:** PAY-SVC-2026
- **Tác giả:** Đội ngũ Kiến trúc Hệ thống
- **Trạng thái:** Dự thảo chuyển đổi kiến trúc

---

## 1. Tổng quan & Mục tiêu

Hệ thống thanh toán cốt lõi xử lý các giao dịch chuyển tiền liên ngân hàng và thanh toán hóa đơn.
Phiên bản hiện tại (V1) sử dụng mô hình đồng bộ REST API kết hợp cơ sở dữ liệu quan hệ Oracle Database, dẫn đến nghẽn cổ chai tại thời điểm cao điểm (peak traffic) với TPS tối đa chỉ đạt 450 TPS và thời gian phản hồi (latency p99) lên tới 2500ms.

Kiến trúc V2 đặt mục tiêu:
1. Nâng thông lượng lên tối thiểu 3000 TPS.
2. Giảm độ trễ p99 xuống dưới 300ms.
3. Đảm bảo tính nhất quán cuối cùng (Eventual Consistency) mà không làm mất mát giao dịch.

---

## 2. Các Thành phần Hệ thống & Thực thể (Entities)

Hệ thống bao gồm các thành phần dịch vụ chính sau:
- **PaymentGateway**: Cổng tiếp nhận yêu cầu từ ứng dụng di động iPay Client và đối tác bên ngoài.
- **TransactionEngine**: Dịch vụ điều phối luồng nghiệp vụ thanh toán và hạch toán.
- **CoreBanking**: Hệ thống ngân hàng lõi của ngân hàng thương mại, quản lý tài khoản nguồn và số dư.
- **KafkaCluster**: Hệ thống hàng đợi phân tán (Event Bus) đóng vai trò xương sống truyền tải sự kiện giữa các microservices.
- **RedisCache**: Cụm bộ nhớ đệm phân tán dùng để lưu trữ trạng thái phiên và khóa phân tán (Distributed Lock).

---

## 3. Các Mẫu Thiết kế & Khái niệm Cốt lõi (Concepts)

### 3.1. Outbox Pattern
Để đảm bảo tính nguyên tử giữa thao tác ghi cơ sở dữ liệu cục bộ và phát sự kiện vào KafkaCluster, hệ thống áp dụng Outbox Pattern. Khi lưu giao dịch vào bảng `payment_order`, bản ghi sự kiện đồng thời được ghi vào bảng `outbox_events` trong cùng một Database Transaction. Một Debezium CDC Connector sẽ đọc Transaction Log của PostgreSQL để đẩy vào KafkaCluster với bảo đảm ít nhất một lần (At-least-once delivery).

### 3.2. Idempotency Key (Khóa Idempotent)
Mỗi yêu cầu thanh toán từ Client bắt buộc phải đính kèm một `Idempotency-Key` (chuỗi UUIDv4 duy nhất trong header). PaymentGateway sử dụng RedisCache để kiểm tra khóa này với TTL là 86400 giây (24 giờ). Nếu khóa đã tồn tại trong RedisCache và giao dịch đang xử lý hoặc đã hoàn tất, hệ thống trả về kết quả đã cache mà không kích hoạt xử lý trùng lặp.

### 3.3. Saga Orchestration Pattern
Do giao dịch liên quan đến nhiều dịch vụ độc lập (trừ tiền tại CoreBanking, tích điểm tại LoyaltyService, thông báo tại NotificationService), kiến trúc V2 loại bỏ giao thức Two-Phase Commit (2PC) truyền thống vì nguy cơ khóa tài nguyên và tắc nghẽn mạng. Thay vào đó, TransactionEngine đóng vai trò Saga Orchestrator thực hiện chuỗi giao dịch bù (Compensating Transactions) khi có bất kỳ bước nào thất bại.

---

## 4. Các Thông số Kỹ thuật & Ràng buộc (Technical Constraints)

1. **Timeout kết nối:** Timeout tối đa khi gọi sang CoreBanking là 3500ms; sau thời gian này hệ thống tự động ngắt mạch (Circuit Breaker tripping).
2. **Số lần thử lại (Retry Policy):** Tối đa 3 lần với thuật toán Exponential Backoff và Jitter ngẫu nhiên.
3. **Mâu thuẫn kiến trúc với tài liệu V1:** Tài liệu V1 quy định giao dịch phải bảo đảm tính toàn vẹn ACID thông qua Two-Phase Commit (2PC), tuy nhiên tài liệu V2 này bác bỏ 2PC và bắt buộc sử dụng Saga Orchestration. Cần lưu ý sự đối nghịch này khi tích hợp các dịch vụ cũ.
