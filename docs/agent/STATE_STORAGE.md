# Agent: dữ liệu đang dùng và dữ liệu khôi phục

`agent.state` giữ một bộ dữ liệu dùng chung, được bảo vệ bằng RLock.
`getControlState()` lấy bản sao để giao tiếp hoặc lưu file.

| Dữ liệu | Ý nghĩa |
| --- | --- |
| `command_seq`, `last_cmd_ack` | Số cuối đã xử lý và kết quả đã chốt để ACK lại khi nhận bản lặp |
| `device_quota`, `device_used`, `device_quota_date` | Hạn mức, thời gian đã dùng và ngày của máy |
| `is_manual_locked`, `manual_locked_apps/domains` | Khóa thủ công đúng đối tượng |
| `app_bonus_time`, `web_bonus_time` | Giây điều chỉnh có dấu; bảng rỗng cũng là dữ liệu hợp lệ |
| `cur_policy` | Nội dung Policy đang áp dụng |
| `online`, `needs_sync`, `storage_loaded` | Trạng thái kết nối, nhu cầu đối chiếu và việc đã đọc file đầu phiên |
| Các mốc đồng hồ/input và block reason | Tính used và giải thích trạng thái; không dùng làm seq |

`quota_used` vẫn là bảng used APP/WEB theo tên. Bản tin Heartbeat thêm phần tử
DEVICE từ `device_used`; ACK giữ nguyên phần giây lẻ.
Mã định danh/token vẫn ở RAM, không ghi trong file quota.

`saveAgentQuotaState()` ghi ControlState, ACK, Policy và bảng used APP/WEB vào
`agent_quota_state.json` theo working directory. Ghi file tạm, flush/fsync rồi
replace; lỗi ghi đi lên caller. Hàm áp dụng lệnh khôi phục RAM trước lệnh nếu
không lưu được, nên không tiến seq hoặc trả ACK thành công.

`loadAgentQuotaState()` kiểm tra toàn bộ dữ liệu trước khi gán vào RAM.
Corrupt JSON, dữ liệu sai hoặc I/O error không được bỏ qua. File chưa có là lần chạy
mới; các mốc monotonic/input luôn được tạo lại. Sau load, Agent đối chiếu với Server.

File cũ remaining/used vẫn được đọc bằng quota = remaining + used.
Atomic replace giúp tránh file ghi dở, không bảo đảm tuyệt đối khi máy mất điện.

Source: [state](../../agent/state.py), [storage](../../agent/storage.py).
