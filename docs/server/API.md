# HTTP và WebSocket trên Server

| Đường dẫn | Hàm xử lý |
| --- | --- |
| POST `/api/v1/enroll` | `responseEnroll()`: cấp mã thiết bị/Policy và token |
| GET `/api/v1/policy` | `responsePolicy()`: xác thực và trả Policy được gắn |
| POST `/api/v1/urgent` | `sendUrgentCmd()`: nhận CmdRequest, xếp hàng và đẩy Cmd đang chờ |
| POST `/api/v1/heartbeat` | `heartbeatEndpoint()` gọi `responseHeartbeat()`, rồi đẩy WS nếu cần |
| POST `/api/v1/command-ack` | `responseCommandAck()`: nhận CmdAck, trả và đẩy lệnh kế tiếp |
| WS `/ws/urgent` | `urgentWebsocketEndpoint()`: nhận ACK hoặc yêu cầu đối chiếu |

Heartbeat/GET Policy kiểm tra token và mã Policy được gắn cho thiết bị:
token sai trả 401, mã Policy không khớp trả 403.
ACK dùng query `device_id`, `access_token` và body CmdAck.
Urgent dùng query `device_id`, header `X-Parent-Token` và body CmdRequest.

Urgent trả request_id, trạng thái queued/inflight/applied và Cmd đang chờ nếu có.
Các field sent/via chỉ mô tả lần gửi socket; chúng không xác nhận đã áp dụng.
Retry cùng request_id/nội dung không tạo thêm thao tác; đổi nội dung với cùng ID trả 409.
Client phải dùng lại ID khi gửi lại; nếu bỏ ID, model tạo ID mới cho yêu cầu mới.

ACK hợp lệ được lưu rồi mới bỏ lệnh đang chờ. Nếu còn yêu cầu, Server tính ngay
Cmd tiếp, đưa vào response và đẩy WS. Khi WS gửi lỗi, kết nối stale được dọn nhưng
lệnh vẫn còn để Heartbeat gửi lại.

WS nhận `{"type":"ack","data":...}` hoặc `{"type":"sync","data":...}`.
Dữ liệu gửi xuống là envelope HeartbeatResponse giống HTTP.
Khóa trạng thái không được giữ qua lời gọi await gửi mạng.

Cơ chế token/ghép đôi giữ nguyên; token chưa được lưu bền vững qua Server restart.
Source: [endpoint](../../server/__init__.py), [hàng lệnh](../../server/commands.py).
