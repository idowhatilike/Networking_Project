# Quy tắc an toàn giao diện và kiểm tra tĩnh

Để giao diện chạy được trong mạng nội bộ không có Internet và tránh lỗi chèn mã độc
(XSS) từ tên ứng dụng/tên miền, mọi file `.html` và `.css` tuân thủ 3 quy tắc:

1. **Tự host 100% tài nguyên:** Không gọi link CDN hay Google Fonts bên ngoài
   (`http://`, `https://` ngoài `localhost` và `127.0.0.1`).
2. **Không tắt cơ chế escape của Jinja2:** Không dùng `|safe` hoặc `Markup()`.
3. **Không viết style hoặc sự kiện inline:** Không dùng `style="..."`, thẻ `<style>`,
   hoặc `onclick=`, `onload=`, `onerror=`. Thanh thời gian dùng thẻ `<progress value max>`.
   Trong [app.js](../../server/static/js/app.js), HTMX đặt `allowEval = false` và
   `includeIndicatorStyles = false`.

HTMX **2.0.11** được lưu nguyên bản tại `server/static/vendor/htmx.min.js`, kèm
`HTMX-LICENSE.txt`. Nguồn tải: [tài liệu HTMX](https://htmx.org/docs/#installing).
Giao diện không tải thư viện từ Internet khi chạy. `app.js` hiển thị thông báo bằng
`textContent` khi HTMX nhận `401`, `403`, `404`, `422`, `500` hoặc lỗi kết nối;
nội dung lỗi từ Server không được chèn trực tiếp vào HTML.

Chart.js **4.6.1** UMD được giữ nguyên từ gói phát hành npm chính thức, sau khi
đối chiếu checksum của gói; giấy phép đi kèm là `CHARTJS-LICENSE.md`.
Mỗi canvas chỉ tạo một biểu đồ khi HTMX nạp nội dung. Khi canvas bị thay hoặc xóa,
biểu đồ cũ được hủy để giải phóng tài nguyên. Thay vùng khác không vẽ lại biểu đồ.
Bảng số liệu trong báo cáo phụ huynh và trẻ luôn mở sẵn, kể cả khi JavaScript lỗi.

## Cách chạy kiểm tra

Kiểm chứng trình duyệt dùng Server tạm, dữ liệu mẫu và hồ sơ Chromium riêng:

```powershell
node tests/frontend_browser.cjs step2
node tests/frontend_browser.cjs step3
node tests/frontend_browser.cjs step4
```

Máy cần có Node.js hỗ trợ `fetch` và Chrome. Có thể đặt `OGK_TEST_CHROME` để chọn
đường dẫn Chrome/Chromium khác. Bài kiểm tra rút ngắn nhịp cập nhật trong phản hồi
thử nghiệm; nhịp 30 giây/3 giây trong code sản phẩm được giữ nguyên.

Chạy script [verify_ui_rules.py](../../scripts/verify_ui_rules.py) từ thư mục `Project/`:

```powershell
.\.venv\Scripts\python.exe scripts/verify_ui_rules.py
```

Script quét toàn bộ `.html` và `.css` trong `server/`, `shared/ui/` và `agent/ui/`.
Nếu không có vi phạm, script in `verify_ui_rules: OK` và trả mã thoát `0`.

## 16/11/2026 — Sửa luồng tương tác frontend

Đã kiểm chứng từng bước trước khi chuyển tiếp: yêu cầu không tồn tại trả `404`;
sáu trường số sai trả `422` và giữ nội dung nhập; HTMX thay đúng dòng bảng và tiếp tục
cập nhật; Chart.js vẽ một lần trên mỗi canvas và giải phóng biểu đồ khi thay canvas.

Kết quả hồi quy: **192 test Python** và **14 ca Chromium** pass; Ruff `F,E9`, kiểm tra
cú pháp JavaScript và quy tắc UI pass. Lệnh chạy từ `Project/`:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --tb=short
node tests/frontend_browser.cjs all
```

Các ca Chromium chạy với FastAPI thật và dữ liệu mẫu. Bộ kiểm chứng chỉ thay nhịp
cập nhật và tạo phản hồi lỗi trong môi trường thử; chưa xác minh điều khiển Agent
từ Dashboard vì frontend vẫn đang mô phỏng dữ liệu.
