# Server tính quota và cập nhật theo seq

Trong một phiên lệnh, `command_sessions[device_id]` là nguồn trạng thái chuẩn.
Server chỉ tính kết quả yêu cầu đầu hàng; yêu cầu sau đợi ACK của yêu cầu trước.

| Thao tác | Phép tính |
| --- | --- |
| ADD_TIME thiết bị | quota = max(quota, used Server biết) + bonus_time |
| SUB_TIME thiết bị | quota = max(0, quota - sub_time), giữ used |
| ADD/SUB APP/WEB | Tăng/giảm adjustment theo subject, có thể âm |
| LOCK/UNLOCK | Đổi cờ/tập khóa thủ công tương ứng |

Cmd gửi giá trị tuyệt đối, kèm used Server đã dùng để tính và số giây cộng.
Nếu Agent đang có used cao hơn trong lệnh ADD thiết bị, nó bảo đảm quota ít nhất
bằng `max(cmd.device_quota, agent_used + cmd.bonus_time)`.
CmdAck gửi kết quả thực tế để Server chốt lại; không cộng lần nữa khi nhận ACK.

Ví dụ quota 80, Server used 60, Agent used 100: Cmd có quota 140; Agent áp dụng
quota 160 và ACK used 100/quota 160. Bản lặp cùng seq không cấp thêm giờ.

Ngày mới tạo Cmd reason=day, seq mới, lấy hạn mức từ Policy và used báo đúng ngày.
Policy đổi hạn mức tạo Cmd reason=policy, seq mới; cùng ngày giữ used và điều chỉnh
quota theo chênh lệch hạn mức gốc mới/cũ để giữ phần cộng/trừ trước đó.
Cả hai đợi lệnh đang chờ ACK hoàn tất, không ghi quota trực tiếp qua Heartbeat.

Lệnh ADD/SUB chưa áp dụng qua ngày được ghi not_applied. LOCK/UNLOCK chưa áp dụng
được tính lại sau bước đồng bộ ngày, trước yêu cầu sau.
ACK cũ không được dùng làm used cho ngày mới.

`ensureDeviceDailyQuota()` chỉ khởi tạo trực tiếp khi chưa có phiên.
Khi phiên đã tồn tại, hàm yêu cầu hàng lệnh cập nhật bằng seq.
Source: [commands](../../server/commands.py), [quota](../../server/quota.py).
