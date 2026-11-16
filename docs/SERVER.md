# Server: một hàng lệnh cho mỗi thiết bị

Server nhận `CmdRequest`, giữ yêu cầu theo thứ tự và tính một Cmd đang chờ ACK.
Heartbeat và WS dùng cùng kết quả. Gửi thành công chưa phải đã thực hiện xong.

| File | Trách nhiệm |
| --- | --- |
| `server/__init__.py` | Xác thực, endpoint HTTP/WS và đẩy phản hồi xuống Agent |
| `server/commands.py` | Request ID, hàng chờ, seq, phép tính, ACK và đối chiếu |
| `server/quota.py` | Chọn hạn mức từ Policy; yêu cầu cập nhật qua seq khi phiên đã có |
| `server/state.py`, `storage.py` | Store RAM và JSON lưu phiên lệnh/Policy |

[Endpoint](server/API.md), [quota](server/QUOTA.md) và [lưu file](server/STATE_STORAGE.md)
giải thích luồng cụ thể. FastAPI app vẫn là `server:app`.

Một khóa bảo vệ dùng chung bao quanh thay đổi trạng thái và ghi file; việc chờ mạng
ở ngoài phần được bảo vệ. Thiết kế hiện dành cho một Server process, chưa hỗ trợ
nhiều worker cùng dùng store RAM/JSON.
