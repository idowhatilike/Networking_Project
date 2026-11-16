# Khung trang, hệ màu và bộ macro

Giao diện dùng chung một bộ CSS và macro Jinja2 để giữ thống nhất giữa màn hình
phụ huynh và màn hình của trẻ, đồng thời hoạt động tốt trên cả máy tính lẫn điện thoại.

## Đường dẫn và CSS
- [paths.py](../../shared/ui/paths.py): `resolveResourcePath()` ưu tiên `sys._MEIPASS`
  (khi đóng gói PyInstaller) trước khi lấy thư mục gốc `Project/`.
- [tokens.css](../../shared/ui/static/tokens.css): đặt màu chủ đạo xanh ngọc `#0F766E`.
  Chế độ `[data-theme='kid']` tăng cỡ chữ và độ bo góc cho trẻ 6–11 tuổi.
- [components.css](../../shared/ui/static/components.css) và [base.css](../../server/static/css/base.css):
  trên màn hình $\le 900\text{px}$, thanh menu bên trái tự chuyển thành thanh 4 mục ở đáy;
  trên màn hình $\le 640\text{px}$, bảng dữ liệu tự xếp thành từng thẻ dọc.

## Khung `base.html` và Macro
[base.html](../../server/templates/base.html) nạp CSS/JS nội bộ từ `/static/` và
`/static/shared/`. Khi truyền `hide_nav=True` (như trang đăng nhập/đăng ký), khung ẩn
menu điều hướng và căn giữa biểu mẫu.

[macros.html](../../server/templates/components/macros.html) cung cấp các khối dựng sẵn:
- `card`, `stat`, `empty_state`, `toast`, `data_table`, `form_field`.
- `status_badge`: luôn hiển thị kèm ký hiệu (`●`, `✓`, `▲`, `○`) và chữ, không chỉ dùng màu.
- `progress`: dùng thẻ `<progress value max>` thay cho thuộc tính `style="width:..."`.
- `modal` và `confirm_dialog`: dùng thẻ `<dialog>` chuẩn của trình duyệt, đóng/mở qua
  [app.js](../../server/static/js/app.js).
- `command_chip`: hiển thị tiến trình lệnh (`Đã áp dụng` hoặc `Đã xếp hàng`).
