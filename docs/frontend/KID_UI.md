# Giao diện phía Trẻ em (`agent/ui/` — `child-view`)

Gói [agent/ui/__init__.py](../../agent/ui/__init__.py) và [agent/ui/port80.py](../../agent/ui/port80.py)
cung cấp giao diện cục bộ dành cho trẻ 6–11 tuổi (`data-theme="kid"`), lắng nghe trên
`127.0.0.1` và cũng được gắn vào `server.app` dưới tiền tố `/kid` để kiểm thử.

## 1. Vé truy cập một lần & Kiểm tra phiên (`requireKidSession`)
- `GET /auth/bootstrap?ticket=<one-time-ticket>`: đối chiếu vé một lần do `issueBootstrapTicket()`
  cấp, hủy vé ngay sau lần dùng đầu tiên (dùng lại trả `403`), sinh token phiên ngẫu nhiên
  (`secrets.token_urlsafe(32)`) lưu vào `valid_sessions`, đặt cookie `ogk_local_session`
  (`HttpOnly`, `SameSite=strict`) và chuyển hướng `302` về `/kid`.
- Mọi route `/kid` và `/kid/*` (trừ `/auth/bootstrap` và `/kid/port80-preview`) đều gắn
  dependency `requireKidSession`: thiếu cookie hoặc dùng cookie giả đều trả `401`.
- Tra cứu yêu cầu không tồn tại trả `404` và thông báo “Không tìm thấy yêu cầu.”,
  không tự tạo kết quả đồng ý.

## 2. Danh sách màn hình của trẻ

| Đường dẫn | Template | Nội dung và nguyên tắc đạo đức |
| --- | --- | --- |
| `GET /kid` | [today.html](../../agent/ui/templates/today.html) | Thời gian còn lại chữ lớn, thông báo minh bạch (`NT1`), cảnh báo đổi giờ máy và nút *Xin thêm giờ* |
| `GET /kid/warning?level=10\|5\|1` | [warning_popup.html](../../agent/ui/templates/warning_popup.html) | Nhắc trước 10, 5, 1 phút; mốc 1 phút có 60 giây ân hạn đếm ngược (`data-countdown-sec="60"`) |
| `GET /kid/blocked?kind=app\|web` | [blocked_explain.html](../../agent/ui/templates/blocked_explain.html) | Giải thích rõ tên luật, người đặt, ngày đặt (`NT4`) và nút *Con nghĩ trang này bị chặn nhầm* (`NT3`) |
| `GET /kid/lock-overlay` | [lock_overlay.html](../../agent/ui/templates/lock_overlay.html) | Màn hình nghỉ ngơi kèm biểu mẫu *Xin thêm giờ*, số tổng đài `111` và miền trường học miễn chặn (`NT6`) |
| `GET /kid/report` | [report_kid.html](../../agent/ui/templates/report_kid.html) | Nhúng cùng [report_content.html](../../shared/ui/templates/report_content.html) như phụ huynh (`NT5`) |
| `GET/POST /kid/requests` | [my_requests.html](../../agent/ui/templates/my_requests.html) | Gửi yêu cầu và tự hỏi `GET /kid/requests/{id}/status` mỗi 3 giây cho tới khi khác `pending` |
| `GET /kid/rules` | [rules_history.html](../../agent/ui/templates/rules_history.html) | Tóm tắt quy tắc dễ hiểu và lịch sử thay đổi (đã loại bỏ hoàn toàn cột IP phụ huynh) |
| `GET /kid/about` | [about.html](../../agent/ui/templates/about.html) | Giải thích quyền riêng tư cho trẻ và nhúng [privacy_table.html](../../shared/ui/templates/privacy_table.html) (`NT2`) |
| `GET /kid/port80-preview` | [port80_blocked.html](../../agent/ui/templates/port80_blocked.html) | Trang tĩnh cổng 80 (`renderPort80BlockedHtml`) tự động thoát ký tự HTML từ header `Host` |
