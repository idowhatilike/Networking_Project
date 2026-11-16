# Agent giao tiếp và xử lý tiếp hàng lệnh

## Ghép đôi và chuẩn bị

`requestEnroll()` gửi mã 8 ký tự và UUID tới POST `/api/v1/enroll`.
UUID được đọc lại tối đa 3 lần khi WMI lỗi/trống; vẫn lỗi thì không gửi enrollment.
Agent nhận mã thiết bị, mã Policy và token. `policy_id` hiện được nhận lúc ghép đôi,
không thay từ Heartbeat.

`ensureStateLoaded()` đọc trạng thái đã lưu trước khi bắt đầu giao tiếp.
Đọc file lỗi được báo lên caller, không coi là trạng thái rỗng.

## Heartbeat và ACK HTTP

`requestHeartbeat()` gọi `applyPolicy()`, lấy bản dữ liệu trong khóa bảo vệ rồi
POST `/api/v1/heartbeat`. Khi chờ HTTP, khóa đã được thả.
Bản tin gồm báo cáo used, ControlState, ACK lưu gần nhất và cờ cần đối chiếu.

`HeartbeatResponseHanlder()` lấy Policy mới nếu cần, xử lý trạng thái đối chiếu
và chuyển Cmd cho `execCmd()`. Quota/bonus không còn được gán từ field riêng của
Heartbeat. Phản hồi đối chiếu cũ có seq thấp hơn không lùi Agent đang chạy bình thường;
đối chiếu đầu phiên được phép đưa Agent về seq chuẩn của Server.

`drainResponses()` gửi ACK ngay qua POST `/api/v1/command-ack`, áp dụng Cmd tiếp
theo trong response rồi tiếp tục cho tới khi không còn lệnh. Chỉ lúc đó vòng
`requestHeartbeatLoop()` mới nghỉ 60 giây. Nếu cùng một bước lặp mãi mà không tiến,
hàm báo lỗi để đối chiếu lại thay vì quay vòng vô hạn.

Timeout các request Policy/Heartbeat/ACK được đặt 3,6 giây. Lỗi mạng giữ ACK đã lưu,
đánh dấu offline và yêu cầu đối chiếu ở lần kết nối tiếp theo.

## WebSocket

`UrgentCmdHandler()` nhận cùng envelope HeartbeatResponse qua `/ws/urgent`.
Khi kết nối lại, Agent gửi ACK còn lưu nếu có, rồi gửi trạng thái để đối chiếu.
Nhận Cmd thì gọi cùng hàm áp dụng như HTTP và gửi envelope ACK ngay.

Server trả/đẩy lệnh kế tiếp ngay sau ACK, không phụ thuộc nhịp Heartbeat.
Mất kết nối được thử lại với backoff như trước. `await` nhường quyền chờ mạng;
khóa bảo vệ trạng thái mới là phần ngăn hai đường nhận áp dụng lệnh xen nhau.

Source: [network](../../agent/__init__.py), [áp dụng lệnh](../../agent/commands.py).
