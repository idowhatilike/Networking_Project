# Dữ liệu lệnh và ý nghĩa ACK

Các model đều khai báo trong [schemas.py](../../shared/schemas.py).

`CmdRequest` chứa cmd_type, target_type, subject, bonus_time/sub_time và request_id.
Bốn loại lệnh vẫn là lock/unlock/add_time/sub_time; target là device/app/web.
APP/WEB phải có subject; tên được bỏ khoảng trắng đầu/cuối và chuyển chữ thường.
Request ID phải được giữ nguyên khi retry; thao tác mới dùng ID mới.

`ControlState` gồm command_seq, quota/used/ngày thiết bị, cờ khóa máy,
tập APP/WEB khóa thủ công và hai bảng điều chỉnh thời gian.
`Cmd` chứa toàn bộ ControlState sau khi tính, thông tin yêu cầu và reason:
command, day, policy hoặc sync. Seq của Cmd phải lớn hơn 0.

`CmdAck` chứa ControlState thực tế đã chốt, `dev_status_cur`, result và reason.
ACK mới hợp lệ cập nhật ngay trạng thái thiết bị trên Server; ACK lặp cũ không
ghi đè trạng thái đã báo mới hơn.

| Result | Ý nghĩa |
| --- | --- |
| applied | Agent đã áp dụng và lưu thành công |
| not_applied/day_changed | Lệnh ngày cũ chưa được áp dụng; Agent đã lưu kết quả kết thúc seq đó |
| resync | Thiếu seq hoặc thiếu kết quả lưu; cần đối chiếu, chưa được xóa lệnh như applied |

Một seq dùng chung cho DEVICE/APP/WEB của mỗi thiết bị. Agent chỉ áp dụng số kế tiếp.
Bản lặp được ACK bằng kết quả đã lưu, không tính lại, kể cả sau restart.

Server giữ Cmd tới ACK hợp lệ. ACK vượt số đang gửi hoặc sai kết quả không làm
mất hàng chờ. Sau ACK, Server chốt kết quả, tính Cmd kế tiếp, trả trong response
và đẩy qua WS nếu có. HTTP 200 hoặc sent=true không thay cho ACK applied.

ACK không xác nhận đã khóa màn hình Windows; phần thực thi đó chưa được cài đặt.
Async chỉ nhường quyền khi chờ mạng. Khóa bảo vệ và seq mới giữ đúng thứ tự xử lý.

Xem [thiết kế hiện tại](../design/QUOTA_SYNC.md).
