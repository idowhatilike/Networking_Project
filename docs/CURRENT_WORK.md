# Hiện trạng sau khi thống nhất cơ chế lệnh

Ngày 15/11/2026. LOCK, UNLOCK, ADD_TIME và SUB_TIME cho DEVICE/APP/WEB đã chuyển
sang cùng Cmd có seq; HTTP và WS không còn tự thực hiện hai phép tính độc lập.

## Các phần đã triển khai

| Bước | Kết quả |
| --- | --- |
| 1. Schema | CmdRequest, ControlState, Cmd, CmdAck và envelope Heartbeat mới |
| 2. Server | Một hàng theo thiết bị, request_id chống retry, tính từng lệnh và giữ tới ACK |
| 3. Agent | Một hàm áp dụng có khóa, chống lặp/thiếu seq và nhận bảng rỗng đúng nghĩa |
| 4. ACK | Trả và đẩy lệnh kế ngay; Agent drain cả hàng mà không chờ Heartbeat 60 giây |
| 5. Khôi phục | Lưu atomic, báo lỗi I/O, rollback RAM; lấy seq/control Server làm chuẩn và max used cùng ngày |
| 6. Ngày/Policy | Mọi thay đổi quota Server trong phiên đi qua Cmd seq mới sau lệnh đang chờ |
| 7. Kiểm chứng/docs | Migrate test theo giao thức mới, giữ invariant cũ và bài used lệch; thêm concurrency, I/O, recovery và HTTP/WS thật |

Trường hợp quota 80, Server used 60, Agent used 100 vẫn được ADD ngay:
Cmd Server tính quota 140; Agent bảo đảm quota 160, ACK used 100/quota 160 về Server.
Bản lặp không cộng tiếp. Phần giây lẻ được giữ trong ACK và file.

21 bài tái hiện cũ được chuyển vào `tests/test_protocol.py`; file audit ngoài
Project gọi lại đúng các bài đó. Giao thức/dữ liệu test được đổi, không bỏ assertion
nghiệp vụ. Riêng lỗi số 4 vẫn giữ Server used 60, Agent used 100 và yêu cầu cộng 60
phải còn đủ 60.

## Những gì vẫn còn ngoài phạm vi

| Việc | Mức quan trọng | Độ dễ |
| --- | --- | --- |
| Hoàn thiện token/xác thực: token vẫn dựng từ fingerprint, ở RAM và chưa có refresh endpoint | Cao | Trung bình–khó |
| Kiểm tra lịch Policy đúng 7×48 và các ràng buộc quota đầu vào | Cao | Dễ |
| Bộ đo used APP/WEB, khóa màn hình Windows và chặn DNS | Cao | Khó |
| Hỗ trợ nhiều Server process và recovery khi mất điện/mất toàn bộ file | Tùy cách triển khai | Khó |

Server restart đã khôi phục được phiên lệnh và Policy từ JSON; token vẫn cần được
cấp/nạp theo cơ chế xác thực hiện có trước khi giao tiếp lại. Các bài recovery lệnh
không được hiểu là đã hoàn thiện vòng đời thông tin đăng nhập.

Offline Agent vẫn xét Policy đang giữ và có thể reset ngày local. Khi có mạng,
bước đối chiếu đưa control về chuẩn Server trước khi tiếp tục hàng lệnh.
Độ trễ polling theo Heartbeat và cách chia khoảng Active–Idle vẫn như phạm vi đã
chấp nhận, không bổ sung worker đếm riêng.

## Comment cũ được giữ nguyên

Theo yêu cầu giữ comment, một số dòng trong `agent/__init__.py` vẫn nói đến
chuỗi timestamp/lock-unlock và chờ Heartbeat sau để ACK. Các dòng này đã lỗi thời:
source mới đọc Cmd có cấu trúc và gửi ACK ngay. Comment khôi phục Server còn nhắc
cập nhật ngày, trong khi quota của phiên hiện được cập nhật bằng Cmd mới sau load.
Không tự viết lại các comment đó trong lần triển khai này.

## Tra cứu và kiểm chứng

[Đồng bộ lệnh](design/QUOTA_SYNC.md), [Agent](AGENT.md), [Server](SERVER.md),
[Shared](SHARED.md) mô tả code hiện tại. Các báo cáo review và ghi chú trước đây
giữ làm lịch sử, không thay cho giao thức mới.

Kết quả kiểm chứng cuối được ghi tại Mục 13 của [ghi chú](OGK_ENGINEERING_LEARNINGS.md).
Bài HTTP/WS thật chỉ mở Server tạm ở localhost với dữ liệu giả, không gọi Server
của người dùng. Việc mất điện, Windows lock và DNS blocker chưa được kiểm chứng.
