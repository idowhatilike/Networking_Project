# Frontend: giao diện phụ huynh và trẻ em

Frontend dựng màn hình hiển thị bằng Jinja2, HTMX và CSS tự host. Giai đoạn hiện tại
đọc dữ liệu mẫu từ `data/fixtures/`, tách biệt với xử lý lệnh của Backend.

| File / Thư mục | Trách nhiệm |
| --- | --- |
| `shared/ui/paths.py` | Tìm đường dẫn `templates/`, `static/`, `fixtures/` khi chạy code hoặc `.exe` |
| `shared/ui/static/` | Biến màu (`tokens.css`) và kiểu dáng khối dùng chung (`components.css`) |
| `shared/ui/templates/` | Mẫu báo cáo (`report_content.html`) và bảng quyền riêng tư (`privacy_table.html`) dùng chung |
| `server/web.py`, `server/templates/` | Route HTML/HTMX và các màn hình Dashboard của phụ huynh (`data-theme="parent"`) |
| `agent/ui/`, `agent/ui/templates/` | Màn hình trẻ em (`data-theme="kid"`), vé một lần `/auth/bootstrap` và trang tĩnh cổng 80 |
| `scripts/verify_ui_rules.py` | Quét `.html`/`.css` để chặn CDN ngoài, `|safe`, `on*=` và inline `style=` |

Chi tiết từng phần:
- [Khung trang và bộ macro](frontend/LAYOUT_COMPONENTS.md)
- [Trang hiển thị và route phụ huynh](frontend/PAGES_ROUTES.md)
- [Giao diện phía Trẻ em (`agent/ui/`)](frontend/KID_UI.md)
- [Quy tắc an toàn giao diện](frontend/UI_RULES.md)
- [Lộ trình 4 bước](design/FRONTEND_PLAN.md)
