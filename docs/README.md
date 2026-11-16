# OGK: luồng điều khiển thiết bị

Agent chạy trên máy Windows, đo thời gian đã dùng và xét trạng thái Active/Idle/Locked.
Server giữ Policy và xử lý yêu cầu khóa, mở, cộng hoặc trừ giờ.
Shared khai báo dữ liệu hai phía trao đổi.

## Một cơ chế chung cho bốn thao tác

Phụ huynh gửi `CmdRequest`. Server xếp yêu cầu theo thiết bị, chỉ tính lệnh đầu hàng
và cấp `command_seq`. Kết quả `Cmd` chứa đầy đủ hạn mức và khóa thủ công, được gửi
giống nhau qua Heartbeat và WebSocket.

Agent chỉ áp dụng lệnh đúng số kế tiếp, lưu kết quả rồi gửi `CmdAck`. Server chỉ
bỏ lệnh chờ sau ACK hợp lệ; ngay lúc đó tính và trả lệnh tiếp theo, đồng thời đẩy WS
nếu có. Khi nhận qua Heartbeat, Agent cũng gửi ACK ngay để xử lý hết hàng chờ,
không đợi 60 giây giữa các lệnh.

Quota là tổng số giây được phép dùng trong ngày; used là số giây đã dùng.
Remaining = `max(0, quota - used)`. Nhận báo cáo used không làm Server trừ quota lại.

| Nội dung | Tài liệu |
| --- | --- |
| Agent gửi/nhận và áp dụng lệnh | [Agent](AGENT.md) |
| Server xếp lệnh, xử lý ACK, cấp hạn mức | [Server](SERVER.md) |
| Cấu trúc dữ liệu và ý nghĩa field | [Shared](SHARED.md) |
| Giao diện phụ huynh và trẻ em (Frontend) | [Frontend](FRONTEND.md), [lộ trình](design/FRONTEND_PLAN.md) |
| Thiết kế đã triển khai, thứ tự và khôi phục | [Đồng bộ lệnh](design/QUOTA_SYNC.md) |
| Kết quả kiểm tra và việc còn lại | [Hiện trạng](CURRENT_WORK.md) |
| Kế hoạch đã duyệt và lịch sử | [Kế hoạch](design/COMMAND_FLOW_PLAN.md), [ghi chú](OGK_ENGINEERING_LEARNINGS.md) |

Giao thức cũ gồm Cmd cộng/trừ riêng qua WS và quota riêng qua Heartbeat đã được thay.
Agent và Server phải cập nhật cùng phiên bản.
