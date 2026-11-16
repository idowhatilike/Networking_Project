# Server lưu hàng lệnh và trạng thái thế nào?

`command_sessions` giữ phiên theo device_id: trạng thái đã xác nhận, hàng yêu cầu,
một Cmd đang chờ ACK, số seq tiếp theo và kết quả theo request_id.
Hàng sau chưa được tính sẵn. Các store quota/used/ngày/bonus cũ được đồng bộ
từ trạng thái đã xác nhận, đồng thời phục vụ đọc dữ liệu định dạng cũ.

`policies_store` giữ nội dung Policy; `device_policy_store` giữ mã Policy được gắn.
`device_tokens` xác thực thiết bị và `active_ws_connections` giữ kết nối ở RAM.

`commandTransaction()` bảo vệ cập nhật bằng một RLock. Nó chụp trạng thái trước,
ghi JSON sau thay đổi và phục hồi RAM nếu ghi lỗi. Không trả thành công hay tiến seq
khi ghi thất bại. Phần gửi HTTP/WS diễn ra sau transaction.

`saveQuotaState()` ghi phiên lệnh, quota/used/ngày/bonus, mã Policy và nội dung Policy
vào `quota_state.json`. Hàm dùng ghi file tạm/replace chung với Agent.
`loadQuotaState()` đọc và kiểm tra toàn bộ trước khi gán: seq hàng chờ phải nối tiếp,
Cmd đang gửi phải khớp đầu hàng, số cấp tiếp không được lùi. File cũ remaining/deadline
được chuyển sang quota/used. Lỗi đọc/ghi được báo lên caller.

Token không ghi vào JSON. Vì vậy sau Server restart vẫn cần xác thực/ghép đôi theo
cơ chế hiện có trước khi đối chiếu lệnh; thay đổi này không hoàn thiện vòng đời token.
Không coi mô phỏng tải lại state là kiểm chứng đầy đủ khởi động dịch vụ thật với
mọi thông tin đăng nhập đã mất.

Mô hình hiện là một Server process. Không dùng JSON/store RAM này cho nhiều worker
cùng ghi. Atomic replace không thay thế transaction giữa nhiều process hoặc bảo đảm
khôi phục tuyệt đối sau mất điện.

Source: [state](../../server/state.py), [storage](../../server/storage.py).
