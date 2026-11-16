# Agent tính used và áp dụng hạn mức

`applyPolicy()` đo elapsed bằng monotonic và xét quyền dùng máy.
`execCmd()` chuyển Cmd cho một hàm áp dụng trong `agent/commands.py`;
không tự tính lại phép cộng/trừ Server đã thực hiện.

## Dữ liệu thiết bị

`device_quota` là tổng giây được phép dùng; `device_used` là số giây đã dùng;
`device_quota_date` là ngày áp dụng theo UTC+7.
Remaining = `max(0, device_quota - device_used)`.

Used chỉ tăng `min(elapsed, remaining)` khi trạng thái trước là Active và lần xét
hiện tại không nhận diện Idle, khóa thủ công, lịch cấm hoặc hết quota.
Idle được xét từ 300 giây không thao tác; điều kiện khóa có ưu tiên cao hơn Idle.
Quota thấp hơn used là hợp lệ: máy bị khóa, không giảm used để làm khớp quota.

## Nhận Cmd

Một khóa chung bảo vệ seq, used và control. Cmd đúng số kế tiếp được áp dụng;
bản đã xử lý được ACK lại bằng kết quả đã lưu; thiếu số thì đối chiếu.
Cmd chứa quota, khóa thủ công và bảng điều chỉnh đầy đủ, nên 0 hoặc bảng rỗng
phải thay giá trị cũ. Sau áp dụng, Agent xét Policy và lưu trước ACK.

Riêng ADD thiết bị, nếu used local cao hơn mốc Server đã tính, Agent lấy
`max(cmd.device_quota, agent_used + cmd.bonus_time)`. Ví dụ Cmd quota 140,
mốc Server used 60, Agent used 100 và cộng 60 thì Agent giữ quota 160,
ACK cả quota/used về Server. Đây là quy tắc bù đã chốt, không phải chạy lại lệnh ADD.

LOCK/UNLOCK chỉ đổi khóa thủ công đúng đối tượng. Sau UNLOCK máy vẫn có thể
Idle, ngoài lịch hoặc hết quota. APP/WEB dùng `max(0, rule.quota + adjustment - used)`;
rule quota 0 là không giới hạn riêng, allowed=False vẫn cấm.

## Online, offline và thực thi

Online, Agent nhận quota mới qua Cmd. Offline, ngày tăng thì dùng quota ngày
thường/cuối tuần từ Policy local, reset used và bỏ elapsed qua lần reset.
Ngày lùi không cấp lại. Kết nối lại phải đối chiếu với Server.

Các mốc monotonic/input không khôi phục từ file. Lệch giờ hệ thống trên 30 giây
so với elapsed tạo sự kiện trong RAM nhưng chưa ngăn chỉnh ngày/lịch.
Cách tính theo polling chưa chia chính xác mọi khoảng Active–Idle giữa hai lần đọc.

APP bị chặn được kết thúc theo tên process; WEB được đưa vào blocked_domains.
Bộ đo APP/WEB, đối chiếu hash, khóa màn hình Windows và DNS blocker chưa hoàn chỉnh.
Source: [quota](../../agent/quota.py), [commands](../../agent/commands.py),
[input](../../agent/helpers/input.py).
