# Shared: hợp đồng dữ liệu giữa Agent và Server

[schemas.py](../shared/schemas.py) khai báo model/enum/struct.
[clock.py](../shared/clock.py) lấy giờ UTC+7; [storage.py](../shared/storage.py)
cung cấp ghi JSON qua file tạm rồi thay file đích.

| Model | Vai trò |
| --- | --- |
| `CmdRequest` | Yêu cầu nghiệp vụ: loại thao tác, target, subject, số giây và request_id |
| `ControlState` | Seq và toàn bộ trạng thái điều khiển của một thiết bị |
| `Cmd` | ControlState sau tính toán, kèm thông tin yêu cầu và lý do cập nhật |
| `CmdAck` | Trạng thái Agent đã chốt, kết quả xử lý và seq |
| `HeartbeatRequest/Response` | Báo cáo/ACK, lệnh kế tiếp và trạng thái dùng khi đối chiếu |

[Ghép đôi](shared/ENROLLMENT.md), [Heartbeat](shared/HEARTBEAT.md),
[lệnh/ACK](shared/COMMANDS_ACK.md), [Policy](shared/POLICY.md) và
[trạng thái/sự kiện](shared/RUNTIME.md) giải thích các nhóm dữ liệu.

Bốn loại CommandType và ba TargetType giữ nguyên; không thêm enum value.
Quota/used thiết bị dùng giây có phần lẻ, đặc biệt trong ACK và dữ liệu khôi phục.
