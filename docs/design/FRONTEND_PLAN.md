# Lộ trình 4 bước thiết kế Frontend

Kế hoạch dựng giao diện bằng dữ liệu mẫu (`data/fixtures/`), không sửa logic lệnh của Backend.
Chi tiết cấu trúc hiện tại xem tại [FRONTEND.md](../FRONTEND.md).

| Bước | Phạm vi màn hình | Trạng thái |
| --- | --- | --- |
| **1. Khung & Tổng quan** | `tokens.css`, `base.html`, `macros.html`, `/login`, `/register` (mật khẩu $\ge 10$ ký tự), `/` (Tổng quan đọc `overview.json`) và `verify_ui_rules.py` | **Đã xong** |
| **2. Cấu hình của Phụ huynh** | `/children`, `/children/{id}` (Hôm nay), `/limits` (Hạn mức), `/schedule` (Lịch tuần $7 \times 48$ + `schedule-grid.js`), `/apps` và `/web` (kèm hộp kiểm tra tên miền) | **Đã xong** |
| **3. Báo cáo, Yêu cầu & Lịch sử** | `/children/{id}/reports` (dùng chung template + nút “Xem như con thấy”), `/requests`, `/devices` (tạo mã ghép 8 ký tự), `/audit`, `/settings`, `/privacy` | **Đã xong** |
| **4. Giao diện của Trẻ (`agent/ui/`)** | Màn hình trẻ 6–11 tuổi (`data-theme="kid"`): Hôm nay của em, cảnh báo 10/5/1 phút, giải thích chặn, Lock Overlay (kèm số 111), yêu cầu của em, luật & nhật ký | **Đã xong** |

## Quy tắc thực hiện từng bước
- Mỗi bước làm xong đều phải qua `scripts/verify_ui_rules.py` và test route trả mã `200`.
- Dừng lại sau mỗi bước để kiểm tra giao diện trước khi chuyển sang bước tiếp theo.
