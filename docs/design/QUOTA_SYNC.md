# Cơ chế lệnh đã triển khai

Cả bốn thao tác dùng một hàng chờ theo thiết bị. Server tính kết quả, cấp command_seq
khi chuẩn bị Cmd đầu hàng, lưu trước khi gửi. Heartbeat và WS chuyển cùng Cmd;
không có đường cộng/trừ WS độc lập.

Agent chốt used, kiểm tra seq và áp dụng bản đầy đủ. Số 0, bảng/tập rỗng đều thay
giá trị cũ. Agent lưu trạng thái và ACK trước khi xác nhận; lỗi ghi khôi phục RAM.
Server chỉ bỏ Cmd sau xác nhận hợp lệ và xử lý ngay yêu cầu tiếp theo.

## Bốn điểm kỹ thuật đã chốt

1. **Cộng giờ với used lệch:** nếu used Agent cao hơn mốc Server đã dùng để tính,
   ADD thiết bị áp dụng quota = max(cmd.quota, agent_used + số giây cộng).
   ACK mang quota/used thực tế; Server dùng kết quả đó cho lệnh sau.
2. **Xử lý liên tiếp:** ACK HTTP trả lệnh tiếp và đẩy WS; ACK WS cũng đẩy lệnh tiếp.
   Agent nhận qua Heartbeat gửi ACK ngay, không nghỉ 60 giây giữa các lệnh.
3. **Khôi phục:** đọc/ghi lỗi đi lên caller, không tiến seq hay xác nhận thành công.
   Đối chiếu hợp lệ dùng seq và trạng thái Server làm chuẩn; used cùng ngày lấy max.
   Nếu Agent đã áp dụng lệnh và lưu ACK trước restart, ACK đó được gửi lại để không
   cấp giờ lần nữa.
4. **Đổi ngày/Policy:** Server tạo Cmd mới có seq sau khi lệnh đang chờ hoàn tất.
   Cùng ngày Policy đổi hạn mức thì giữ used và phần điều chỉnh đã có.

## Lệnh qua ngày

Cmd cũ chưa được áp dụng không được chép quota hôm qua vào hôm nay. Agent lưu
not_applied/day_changed. Server nhận ACK, tạo cập nhật ngày qua seq, sau đó tính lại
LOCK/UNLOCK trước yêu cầu sau. ADD/SUB thuộc ngày cũ kết thúc không áp dụng.
Lệnh đã áp dụng chỉ mất ACK được xác nhận lại từ bản lưu.

## Giới hạn

Một Server process, JSON ghi atomic và khóa trong process; chưa hỗ trợ multi-worker.
Token vẫn ở RAM như trước. Việc mất điện hoặc mất toàn bộ file không được bảo đảm
phục hồi tuyệt đối. LOCK màn hình và DNS blocker ngoài phạm vi lần này.

[Kế hoạch gốc](COMMAND_FLOW_PLAN.md) giữ lịch sử lựa chọn; các điểm người dùng chốt
sau kế hoạch được thể hiện trong source và tài liệu này.
