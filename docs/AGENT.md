# Agent: đo thời gian, áp dụng kết quả và xác nhận

Agent quản lý máy đang chạy nó. Server tính kết quả điều khiển; Agent đo used,
áp dụng kết quả theo seq, xét lại Policy và xác nhận sau khi lưu thành công.

| File | Trách nhiệm |
| --- | --- |
| `agent/__init__.py` | HTTP/WS, lấy Policy, gửi ACK và xử lý lệnh kế tiếp |
| `agent/commands.py` | Áp dụng Cmd, đối chiếu trạng thái và chống thực hiện lặp |
| `agent/quota.py` | Tính used, xét Idle/lịch/quota và chặn APP theo tên |
| `agent/state.py`, `storage.py` | Dữ liệu RAM, seq/ACK đã lưu và JSON khôi phục |

[Luồng giao tiếp](agent/COMMUNICATION.md), [quota/trạng thái](agent/QUOTA.md),
[dữ liệu/lưu file](agent/STATE_STORAGE.md) mô tả chi tiết từng phần.

UNLOCK chỉ gỡ khóa thủ công; máy vẫn có thể Idle hoặc Locked vì lịch/quota.
Locked hiện là trạng thái logic; khóa màn hình Windows và chặn DNS chưa thuộc
phần đã triển khai.
