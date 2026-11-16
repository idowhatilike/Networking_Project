# Trạng thái, sự kiện và hai loại đồng hồ

Các kiểu dữ liệu trong [schemas.py](../../shared/schemas.py) giúp Agent mô tả kết quả xử lý. Chúng không tự thay đổi trạng thái hoặc ghi sự kiện.

## Trạng thái và nguyên nhân chặn

`dev_status_cur` nhận một trong ba chuỗi: `active`, `idle`, `locked`. Trạng thái này nói về máy. `BlockReason` giải thích vì sao máy hoặc một APP/WEB bị chặn:

| Giá trị | Ý nghĩa |
| --- | --- |
| `none` | Không bị chặn |
| `policy` | Bị rule cấm hoặc khóa thủ công |
| `schedule` | Ngoài lịch sử dụng |
| `device_quota`, `app_quota`, `web_quota` | Hết hạn mức tương ứng |

`DomainCategory` phân nhóm tên miền: `education`, `entertainment`, `social`, `gaming`, `inappropriate`, `uncategorized`. `UserRole` định nghĩa `parent`, `child-view`, `admin`; các hàm Server đã đọc vẫn xác thực theo token, chưa dùng đầy đủ ba vai trò này.

## Sự kiện được ghi thế nào?

`EventRecord = EventState`: hai tên trỏ tới cùng model. Các field bắt buộc là `ts: int` (Unix giây), mã thiết bị `device_id`, mã trẻ `child_id`, `type: EventType`, `subject: str`, `policy_id: str`, `idempotency_key: str`. `duration_sec` là số giây liên quan, mặc định 0 và không âm.

`EventType` định nghĩa: `app_start`, `app_stop`, `domain_query`, `blocked_app`, `blocked_domain`, `quota_warning`, `locked`, `unlock_request`, `override_granted`.

Trong luồng hiện tại, `applyPolicy()` tạo `quota_warning` khi giờ hệ thống lệch tiến/lùi trên 30 giây so với thời gian monotonic đã đo. Subject ghi hướng lệch, `duration_sec` ghi độ lệch; bản ghi được thêm vào `event_buffer` trong RAM. Chưa có luồng gửi/lưu/xóa buffer này, và `idempotency_key` chưa có nơi kiểm tra chống trùng.

## Đo elapsed khác với xét ngày

`time.monotonic()` trên Agent đo khoảng thời gian giữa hai lần tính. [getVnNow()](../../shared/clock.py) lấy giờ hệ thống theo UTC+7 để xét ngày và lịch. Việc ghi sự kiện lệch giờ chưa ngăn ngày/lịch bị ảnh hưởng khi giờ hệ thống thay đổi.

Với input Windows, `_LASTINPUTINFO` là struct dùng qua ctypes: `cbSize` chứa kích thước struct, `dwTime` nhận tick của thao tác cuối tính bằng mili giây; cả hai là `c_uint`. [Input helper](../../agent/helpers/input.py) truyền struct này cho `GetLastInputInfo` rồi tính thời gian không thao tác. Struct này không được gửi dưới dạng JSON.
