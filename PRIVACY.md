# Chính sách Quyền riêng tư và Minh bạch Dữ liệu (PRIVACY.md)

Tài liệu này quy định chi tiết danh mục dữ liệu thu thập bởi hệ thống **OGK (Ứng dụng hỗ trợ quản lý việc sử dụng máy tính của trẻ em)** theo đúng nguyên tắc **NT2 (Tối thiểu dữ liệu)**, **NT5 (Minh bạch hai chiều)** và yêu cầu **F3**.

> **Nguyên tắc cốt lõi:** Mọi trường dữ liệu không giải thích được mục đích đều bị loại bỏ khỏi lược đồ cơ sở dữ liệu. Tuyệt đối không thu thập URL đầy đủ, tiêu đề cửa sổ (window title), nội dung bàn phím (keystroke), ảnh chụp màn hình (screenshot), hoặc nội dung tệp/tin nhắn.

## 1. Bảng ánh xạ lược đồ sự kiện (`events`)

| Trường dữ liệu | Kiểu dữ liệu | Mục đích thu thập | Thời hạn lưu trữ | Đối tượng được xem |
| :--- | :--- | :--- | :--- | :--- |
| `id` / `idempotency_key` | `UUID` / `TEXT` | Chống trùng lặp sự kiện khi đồng bộ ngoại tuyến (offline batch sync). | 90 ngày (hoặc xóa ngay khi phụ huynh yêu cầu) | Hệ thống nội bộ |
| `ts` | `INTEGER` / `ISO-8601` | Xác định thời điểm xảy ra sự kiện để thống kê theo khung giờ/ngày/tuần và kiểm tra tính toàn vẹn thời gian. | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |
| `device_id` | `TEXT` | Định danh thiết bị phát sinh sự kiện (hỗ trợ mô hình $1$ phụ huynh : $n$ trẻ : $m$ thiết bị). | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |
| `child_id` | `TEXT` | Gắn kết hoạt động và hạn mức (quota) với hồ sơ của từng trẻ. | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |
| `type` | `ENUM` (`TEXT`) | Phân loại sự kiện trong 9 loại hợp lệ: `app_start`, `app_stop`, `domain_query`, `blocked_app`, `blocked_domain`, `quota_warning`, `locked`, `unlock_request`, `override_granted`. | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |
| `subject` | `TEXT` | Tên tệp thực thi (ví dụ: `notepad.exe`) hoặc tên miền cấp hai/cấp đăng ký (ví dụ: `example.com`), phục vụ thống kê Top 10 ứng dụng/tên miền và hiển thị lý do chặn. | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |
| `duration_sec` | `INTEGER` | Thời lượng sử dụng thực tế (tính bằng giây, trừ thời gian khóa máy và thời gian không tương tác $> 5$ phút) để khấu trừ hạn mức ngày. | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |
| `policy_id` | `TEXT` | Tham chiếu phiên bản chính sách đã áp dụng tại thời điểm phát sinh sự kiện để giải thích lý do chặn (NT4). | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |

## 2. Bảng ánh xạ dữ liệu kiểm toán và định danh (`audit_logs`, `devices`)

| Trường dữ liệu | Mục đích thu thập | Thời hạn lưu trữ | Đối tượng được xem |
| :--- | :--- | :--- | :--- |
| `actor_id`, `actor_ip`, `action`, `old_val`, `new_val`, `ts` (Bảng `audit_logs`) | Ghi nhận mọi thay đổi chính sách để trẻ và phụ huynh cùng giám sát (NT5, F4). | 90 ngày | Phụ huynh, Trẻ em (`child-view`) |
| `device_fingerprint` (Băm SHA-256) | Định danh thiết bị khi ghép đôi (Enrollment) và chống giả mạo phiên thiết bị. | Đến khi gỡ thiết bị hoặc xóa tài khoản | Phụ huynh, Hệ thống |
| `password_hash` (Argon2id/scrypt) | Xác thực tài khoản phụ huynh an toàn (F5). | Đến khi xóa tài khoản | Hệ thống (không ai xem được bản rõ) |

## 3. Cơ chế xóa dữ liệu (Data Retention & Purge)

1. **Tự động hết hạn (TTL 90 ngày):** Tác vụ nền trên `OGK-Server` và `OGK-Agent` tự động xóa vĩnh viễn các bản ghi `events` và `audit_logs` có `ts` cũ hơn 90 ngày.
2. **Xóa tức thời theo yêu cầu ("Xóa toàn bộ dữ liệu của con tôi"):** Khi phụ huynh kích hoạt nút xóa trên Dashboard:
   - Server xóa toàn bộ bản ghi `events` của `child_id` trong SQLite.
   - Server đẩy lệnh khẩn qua WebSocket (và hàng đợi lệnh Heartbeat) xuống `OGK-Agent` để xóa sạch hàng đợi đệm cục bộ (`local_cache.db`) kèm thực thi `VACUUM`.

## 4. Phạm vi sử dụng hợp pháp

Sản phẩm chỉ được cài đặt và vận hành trên thiết bị thuộc quyền quản lý hợp pháp của phụ huynh/người giám hộ với sự thông báo rõ ràng cho trẻ (hiển thị biểu tượng khay hệ thống bắt buộc theo nguyên tắc NT1). Nghiêm cấm sử dụng để theo dõi lén hoặc cài đặt trên thiết bị của người khác khi chưa có sự đồng ý.
