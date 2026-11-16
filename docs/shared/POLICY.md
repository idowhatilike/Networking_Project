# Policy quy định quyền sử dụng như thế nào?

`Policy` là bộ chính sách Agent lấy qua GET `/api/v1/policy`. Nó cho biết máy được dùng bao lâu, vào khung giờ nào, và APP/WEB nào được phép dùng.

Khai báo nằm trong [shared/schemas.py](../../shared/schemas.py):

| Field | Kiểu, mặc định | Ý nghĩa |
| --- | --- | --- |
| `policy_id`, `policy_version` | `str`, `int`; bắt buộc | Mã định danh và phiên bản Policy |
| `weekday_quota`, `weekend_quota` | `int`, bắt buộc | Số giây cấp cho máy trong ngày thường/cuối tuần trước cộng/trừ |
| `schedule_7x48` | `list[list[bool]]`, bắt buộc | Lịch 7 ngày, mỗi ngày 48 khung 30 phút |
| `app_rules` | `list[AppRule]`, mặc định rỗng | Quyền và hạn mức riêng từng APP |
| `domain_rules` | `list[DomainRule]`, mặc định rỗng | Quyền và hạn mức riêng từng WEB |
| `signature` | `str`, bắt buộc | Trường dành cho chữ ký kiểm tra toàn vẹn Policy |

Ví dụ `weekday_quota=1800` cho máy 30 phút/ngày thường trước điều chỉnh; đó không phải số đã dùng hoặc số còn lại. Agent đọc lịch theo hàng thứ Hai = 0 và cột `hour * 2 + minute // 30`. Giá trị True cho phép dùng.

## Rule APP/WEB

| Model | Trường | Công dụng |
| --- | --- | --- |
| `AppRule` | `exe_name: str`, `sha256: str` | Tên tệp thực thi và hash nhận diện |
| `AppRule` | `allowed: bool`, `quota: int = 0` | Quyền dùng và hạn mức riêng, đơn vị giây |
| `DomainRule` | `domain: str`, `category: DomainCategory` | Tên miền và nhóm phân loại |
| `DomainRule` | `allowed: bool`, `quota: int = 0` | Quyền dùng và hạn mức riêng, đơn vị giây |

Các field không có mặc định đều bắt buộc. Rule quota 0 nghĩa không giới hạn riêng, còn `allowed=False` vẫn cấm. Với quota hữu hạn, Agent tính `max(0, rule.quota + adjustment - used)`.

Agent hiện chặn process theo tên, chưa đối chiếu `sha256` hoặc xác minh `signature`. Schema cũng chưa kiểm tra lịch đúng kích thước 7×48 hay quota Policy/rule không âm. Lịch thiếu hàng/cột vẫn có thể qua model rồi gây lỗi khi `applyPolicy()` đọc lịch; đây là phần kiểm tra đầu vào còn thiếu.

Khi Policy đổi hạn mức ngày, Server tạo Cmd reason=policy có seq mới sau lệnh đang
chờ ACK. Cùng ngày, quota đổi theo chênh lệch hạn mức gốc mới/cũ, giữ used và phần
cộng/trừ đã có. Agent lấy nội dung Policy mới nhưng không tự cấp lại quota online
bên ngoài Cmd. Quy tắc triển khai nằm tại [đồng bộ lệnh](../design/QUOTA_SYNC.md).
