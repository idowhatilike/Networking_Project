# Trang hiển thị và các route HTMX

[server/web.py](../../server/web.py) gắn các route giao diện vào `server.app` qua
`setupWeb(app)`, đọc dữ liệu mẫu từ `data/fixtures/` và tái sử dụng template chung tại
`shared/ui/templates/`.

## 1. Tổng quan, Hồ sơ con và Cấu hình (Bước 1 & 2)

| Đường dẫn | Mục đích và hành vi |
| --- | --- |
| `GET/POST /login`, `/register` | Đăng nhập ([login.html](../../server/templates/pages/login.html)) và đăng ký ([register.html](../../server/templates/pages/register.html)); mật khẩu $\ge 10$ ký tự |
| `GET /` | Trang Tổng quan ([overview.html](../../server/templates/pages/overview.html)): cảnh báo toàn vẹn, thẻ từng trẻ, thanh `<progress>` và hộp yêu cầu chờ duyệt |
| `GET/POST /children`, `/children/{id}` | Danh sách con ([children.html](../../server/templates/pages/children.html)) và tab **Hôm nay** ([child_today.html](../../server/templates/pages/child_today.html)) |
| `GET/POST /children/{id}/schedule` | Tab **Lịch tuần 7×48** ([child_schedule.html](../../server/templates/pages/child_schedule.html)) đồng bộ qua [schedule-grid.js](../../server/static/js/schedule-grid.js); kiểm tra 7 chuỗi $\times$ 48 ký tự `'0'/'1'` (`422` nếu sai) |
| `GET/POST /children/{id}/limits` | Tab **Hạn mức** ([child_limits.html](../../server/templates/pages/child_limits.html)): hạn mức ngày thường/cuối tuần, ngân sách nhóm và xóa điều chỉnh về `{}` |
| `GET/POST /children/{id}/apps`, `/web` | Tab **Ứng dụng** ([child_apps.html](../../server/templates/pages/child_apps.html)) và **Website** ([child_web.html](../../server/templates/pages/child_web.html)) kèm danh mục 210 tên miền |

Form Hạn mức và Ứng dụng chỉ nhận số nguyên không âm, kể cả `0`. Dữ liệu sai hoặc
rỗng trả `422`, giữ nguyên nội dung đã nhập và hiển thị lỗi dưới từng trường;
Server kiểm tra toàn bộ trước khi cập nhật. Các ô dùng `text` với `inputmode="numeric"`
và mẫu chữ số để trình duyệt không xóa nội dung sai khi hiện lại form.
Nút xóa điều chỉnh có `formnovalidate`; thao tác này bỏ qua các trường số.

## 2. Báo cáo, Yêu cầu, Thiết bị, Kiểm toán và Quyền riêng tư (Bước 3)

| Đường dẫn | Mục đích và hành vi |
| --- | --- |
| `GET /children/{id}/reports` | Tab **Báo cáo** ([child_reports.html](../../server/templates/pages/child_reports.html)): nhúng [report_content.html](../../shared/ui/templates/report_content.html); hỗ trợ `?view=kid` bật `data-theme="kid"` (“Xem như con thấy” — `NT5`) |
| `GET /requests` | Hộp thư yêu cầu ([requests.html](../../server/templates/pages/requests.html)): lọc chưa trả lời/đã trả lời, gợi ý câu nhắn mẫu (`NT3`) |
| `GET /devices`, `POST /enroll-codes` | Quản lý thiết bị ([devices.html](../../server/templates/pages/devices.html)): bắt buộc chọn trẻ + tick đồng ý Nghị định 13 trước khi sinh mã 8 ký tự đếm ngược 10 phút |
| `GET /audit` | Nhật ký thay đổi ([audit.html](../../server/templates/pages/audit.html)): lọc theo trẻ và phân trang bằng `cursor` |
| `GET /settings`, `POST /settings/delete-child-data` | Cài đặt ([settings.html](../../server/templates/pages/settings.html)): xem bản ghi đồng ý Nghị định 13 và xóa dữ liệu khi gõ đúng tên con (`F3`) |
| `GET /privacy` | Quyền riêng tư ([privacy.html](../../server/templates/pages/privacy.html)): nhúng bảng ánh xạ [privacy_table.html](../../shared/ui/templates/privacy_table.html) (`NT2`) |

## 3. Kiểm chứng
Các route Bước 1–4 được kiểm chứng tự động qua ASGI tại
[test_frontend_step1.py](../../tests/test_frontend_step1.py),
[test_frontend_step2.py](../../tests/test_frontend_step2.py),
[test_frontend_step3.py](../../tests/test_frontend_step3.py) và
[test_frontend_step4.py](../../tests/test_frontend_step4.py).
Chi tiết các route phía trẻ em xem tại [KID_UI.md](KID_UI.md).
