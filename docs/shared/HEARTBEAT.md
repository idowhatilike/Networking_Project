# Heartbeat và phản hồi ACK

[HeartbeatRequest](../../shared/schemas.py) vẫn gửi device_id, access_token, policy_id,
dev_status_cur, quota_used và cur_policy_version.
`quota_used` là bảng giây theo obj, không cộng các phần tử thành used thiết bị.

| Field mới trong request | Công dụng |
| --- | --- |
| `control: ControlState` | Seq, quota/used/ngày và trạng thái Agent đang giữ |
| `cmd_ack: CmdAck` hoặc None | Xác nhận gần nhất đã được lưu trên Agent |
| `reconcile: bool` | Yêu cầu đối chiếu đầu phiên/kết nối lại |

`device_quota_date` còn được gửi cùng bảng used để phân biệt ngày của báo cáo cũ.
Phần giây lẻ thiết bị được giữ trong ControlState/CmdAck, không lấy từ số nguyên
`quota_used["__device__"]` nếu đã có ControlState.

HeartbeatResponse chỉ có phiên bản Policy, `command: Cmd | None` và
`reconcile: ControlState | None`. Không còn quota/used/bonus riêng để handler gán
ngoài cơ chế seq. Reconcile là bản trạng thái chuẩn của Server để phục hồi; used
cùng ngày lấy max(Server, Agent). Những thay đổi quota mới do ngày/Policy vẫn phải
là Cmd có seq mới, không dùng reconcile để cấp ngầm.

POST `/api/v1/command-ack` và phản hồi WS dùng cùng HeartbeatResponse.
Ngay sau ACK, lệnh kế tiếp bắt buộc nằm trong response nếu còn yêu cầu xử lý.
Agent gửi ACK ngay và tiếp tục tới khi hết hàng, không chờ nhịp 60 giây.

Chi tiết áp dụng bản trùng, thiếu seq và kết quả not_applied:
[lệnh và ACK](COMMANDS_ACK.md).
