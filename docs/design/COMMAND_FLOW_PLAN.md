# Kế hoạch thống nhất gửi, nhận và xác nhận lệnh

Ngày 15/11/2026 — **Đã được duyệt và triển khai theo bốn điểm chốt bổ sung.**

Nội dung bên dưới giữ kế hoạch gốc để đối chiếu. Các điểm bổ sung về ADD khi used
lệch, trả lệnh kế tiếp bắt buộc, khôi phục theo Server và seq mới cho ngày/Policy
được mô tả theo code thực tế tại [đồng bộ lệnh](QUOTA_SYNC.md). Kết quả kiểm chứng
nằm ở [hiện trạng](../CURRENT_WORK.md) và phần cuối ghi chú lịch sử.

## Mục tiêu và phạm vi

LOCK, UNLOCK, ADD_TIME và SUB_TIME dùng chung một cơ chế cho thiết bị, APP và WEB.
Server quyết định thay đổi; Agent đo thời gian đã dùng, nhận kết quả và xét trạng thái.
Heartbeat và WebSocket chỉ là hai đường chuyển cùng một lệnh.

Người dùng đề xuất thêm số thứ tự và chỉ xóa lệnh sau ACK. Kế hoạch này giải quyết
các lỗi cùng một thiết kế, không vá riêng từng nhánh HTTP/WS.

Phạm vi gồm giao thức lệnh, cập nhật quota/khóa, ACK, chống lặp và lưu trạng thái
cần để khôi phục lệnh. Không thêm bộ đo APP/WEB, khóa màn hình, DNS blocker,
worker đếm mới hoặc đổi cơ chế token/Policy trong lần này.

## Những chỗ trong source cần thay

| Nơi xử lý hiện tại | Vấn đề |
| --- | --- |
| [sendUrgentCmd()](../../server/__init__.py) | Tính quota rồi gửi lệnh cộng/trừ; gửi WS xong là trả thành công, chưa giữ đủ lệnh chờ ACK |
| [responseHeartbeat()](../../server/__init__.py) | Gửi quota/bonus bằng đường riêng, ngoài lệnh WS |
| [HeartbeatResponseHanlder()](../../agent/__init__.py) | Gán quota/bonus, rồi còn gọi thực thi lệnh; bảng bonus rỗng bị bỏ qua |
| [UrgentCmdHandler()](../../agent/__init__.py) | Nhận Cmd và tự thực hiện, chưa kiểm tra thứ tự chung với Heartbeat |
| [execCmd()](../../agent/quota.py) | Agent tính lại phép cộng/trừ mà Server đã xử lý |
| [Schemas](../../shared/schemas.py) và storage hai phía | Chưa có seq/ACK có cấu trúc và dữ liệu khôi phục chung với trạng thái điều khiển |

21 trường hợp tái hiện trong `.skill-work/test_basic_command_audit.py` và kết quả
rà soát đã ghi tại [CURRENT_WORK.md](../CURRENT_WORK.md). Chúng là bằng chứng của
source hiện tại, không phải kiểm chứng cho thiết kế đề xuất này.

## 1. Một hàng lệnh cho mỗi thiết bị

Server nhận yêu cầu, kiểm tra quyền/đối tượng rồi lưu theo thứ tự vào hàng chờ.
Khi xử lý yêu cầu đầu hàng, Server tính kết quả và cấp `command_seq` tăng dần.
Cả DEVICE, APP và WEB dùng chung thứ tự lệnh của thiết bị đó.
Seq không quay lại 0 khi đổi ngày, reconnect hoặc ghép đôi lại cùng thiết bị.

**Server chỉ tính kết quả lệnh tiếp theo sau ACK lệnh trước.** Các yêu cầu phía sau
được giữ theo thứ tự, chưa tính sẵn quota từ số used cũ. Mỗi thiết bị có tối đa
một lệnh đã tính đang chờ xác nhận; thiết bị khác có hàng riêng.

Yêu cầu từ phụ huynh có `request_id`: retry cùng ID trả lại trạng thái yêu cầu đã có;
cùng ID nhưng nội dung khác bị từ chối. Thao tác mới dùng ID mới. Request ID nhận
diện yêu cầu gửi lại, còn command_seq quyết định thứ tự gửi xuống Agent.

## 2. Gửi kết quả đã tính qua cả HTTP và WS

Đề xuất tách dữ liệu đầu vào `CmdRequest` khỏi `Cmd` Server gửi xuống. Các model
vẫn khai báo trong `shared/schemas.py`; không tạo model riêng trong handler.

| Dữ liệu | Nội dung chính |
| --- | --- |
| CmdRequest | request_id; loại lệnh; target/subject; số giây cộng/trừ |
| Cmd | command_seq; ngày áp dụng quota; kết quả đầy đủ sau khi Server xử lý |
| CmdAck | command_seq đã xử lý; kết quả applied/not_applied và lý do; ngày của used; device_used Agent vừa chốt |

Kết quả đầy đủ gồm quota thiết bị, cờ khóa thủ công thiết bị, tập APP/WEB bị khóa
thủ công và hai bảng điều chỉnh APP/WEB. Không gửi `active` để ép máy mở: Agent
vẫn xét lịch, quota và Idle sau khi nhận dữ liệu.

Kết quả đang chờ nằm trong Cmd; chưa được coi là trạng thái Agent đã áp dụng.
Server chỉ chốt trạng thái đã áp dụng sau ACK tương ứng, rồi mới tính yêu cầu sau.
WS và Heartbeat chuyển **đúng cùng bản Cmd**. Đã gửi thì nội dung bản đó không đổi;
retry không tính lại. Agent không nhận thêm một bản quota/bonus không có seq để
ghi đè dữ liệu bên ngoài cơ chế lệnh.

Khi bản đầy đủ có `{}` hoặc tập rỗng, Agent thay bảng/tập cũ bằng giá trị rỗng.
Số 0 cũng phải được áp dụng. Không dùng kiểm tra truthy để quyết định có cập nhật.
Used Agent được đo riêng; không bị Cmd chép lùi.

## 3. Agent chỉ có một hàm áp dụng

Cả handler Heartbeat và WS chuyển Cmd đến cùng một hàm xử lý:

- Seq đúng số kế tiếp và đúng ngày: chốt thời gian đã dùng, nhận kết quả, xét lại
  Policy, lưu trạng thái cùng seq đã xử lý và kết quả applied, sau đó ACK.
- Seq đã xử lý: không thực hiện lại thay đổi; báo seq cuối đã xử lý và kết quả
  đi kèm đang lưu. Không gán kết quả lệnh mới cho một seq cũ.
- Seq vượt số kế tiếp: chưa áp dụng; báo số đang giữ để Server gửi bù/đối chiếu.
  Không bỏ qua khoảng thiếu rồi coi các lệnh đó đã xong.

Một cơ chế bảo vệ dùng chung cho kiểm tra seq, dữ liệu điều khiển và mốc tính used
ngăn hai handler cập nhật xen nhau. Không giữ khóa trong lúc chờ HTTP/WS.
Sau khi chuyển đổi, bỏ cách chống lặp bằng danh sách chuỗi và tập mã tăng mãi;
Agent chỉ cần giữ seq cuối cùng cùng trạng thái và kết quả xử lý đã lưu.

## 4. Chỉ ACK mới hoàn tất việc giao lệnh

Server giữ lệnh dù `send_json()` thành công. ACK phải đúng thiết bị và đúng seq
đang chờ; ACK cũ không lùi tiến độ, ACK vượt số đã gửi không được xóa hàng chờ.
Lưu kết quả ACK trước khi bỏ lệnh khỏi phần đang chờ giao. Kết quả not_applied
không được hiển thị như đã thực hiện; cách xử lý lệch ngày nêu ở mục 6.

Agent gửi ACK sau khi cập nhật và lưu thành công, không phải ngay khi đọc được
bản tin. Lỗi xử lý/ghi file thì chưa xác nhận hoàn tất. Mất ACK: Server gửi lại
Cmd cũ; Agent nhận ra seq đã áp dụng và xác nhận lại, không cộng/trừ lần nữa.

WS gửi ACK ngay. Nếu nhận Cmd qua Heartbeat, Agent gửi lượt xác nhận ngay sau
xử lý, không chờ hết khoảng nghỉ 60 giây. Khi không có lệnh, giữ nhịp hiện tại.
Server có thể trả lệnh kế tiếp trong phản hồi nhận ACK.

HTTP nhận yêu cầu phụ huynh trả request_id và trạng thái đã xếp hàng; có seq khi
Cmd đã được tạo. Không báo đã áp dụng chỉ vì gửi WS thành công. Kết quả áp dụng
được xác định từ ACK.

## 5. Thống nhất phép tính và used

Chỉ Server tính thay đổi khi xử lý yêu cầu điều khiển:

| Thao tác | Quy tắc |
| --- | --- |
| Cộng X giây thiết bị | quota = max(quota, used đã biết đúng theo tiến độ ACK) + X |
| Trừ X giây thiết bị | quota = max(0, quota - X); giữ used |
| Cộng/trừ APP hoặc WEB | Điều chỉnh bảng tương ứng theo subject; giá trị có thể âm |
| LOCK/UNLOCK | Bật/tắt khóa thủ công đúng đối tượng; không tự bỏ qua lịch hoặc quota |

ACK phải mang used sau lần Agent chốt thời gian và áp dụng lệnh, đúng ngày.
Giữ phần giây lẻ trong ACK và dữ liệu khôi phục; không cắt thành int rồi tuyên bố
phần giờ cộng đã chính xác. Đơn vị quota/used vẫn là giây ở cả hai phía.

Ví dụ lệnh trừ làm quota còn 80 khi Agent đã dùng 100: Agent khóa và ACK used 100.
Server nhận ACK đó rồi mới tính cộng 60 thành quota 160. Nếu tính sẵn lệnh cộng
trước ACK, thêm seq vẫn không sửa được lỗi used cũ.

Lý do không cần hỏi used riêng trước mọi ADD: nếu used vẫn dưới quota, Agent chỉ
đếm tối đa tới quota; Server cộng vào quota cũ vẫn cấp thêm X. Nếu quota đã thấp
hơn used vì lệnh trước, ACK đã báo used thực tế và Agent hết quota nên used đứng
yên. Điều này chỉ đúng khi hai phía đã đồng bộ ban đầu, cùng ngày và không có
đường khác sửa quota ngoài cơ chế chung.

Vì vậy trước khi tính lệnh ở lần kết nối đầu/khôi phục, phải đối chiếu seq, ngày,
trạng thái điều khiển và used Agent. Trạng thái quota 80/Server used 60/Agent used
100 chưa được đối chiếu không được dùng để tính ADD ngay.

## 6. Lưu, khôi phục và đổi ngày

Chọn mở rộng JSON hiện có trước, không thêm DB/dependency. Server lưu hàng chờ,
seq và trạng thái điều khiển nhất quán trước khi gửi. Agent lưu trạng thái và seq
nhất quán trước ACK. Ghi qua file tạm rồi thay atomic; lỗi ghi phải đến được caller.
Atomic replace không đồng nghĩa bảo đảm tuyệt đối khi máy mất điện.

Kế hoạch giả định Server chạy một process, đúng mô hình store RAM hiện tại.
Các cập nhật và ghi JSON dùng cùng khóa bảo vệ; không tuyên bố hỗ trợ nhiều worker.
Nếu mất file chứa seq hoặc trạng thái hai phía không đối chiếu được, báo lỗi khôi
phục, không tự đặt seq về 0 rồi tiếp tục. Không đổi cơ chế lưu token trong phạm vi này.

Seq và ngày có trách nhiệm riêng: seq không reset; used/quota được reset theo ngày.
Reset ngày, cập nhật Policy làm đổi hạn mức và khôi phục phiên phải đi qua bước
đồng bộ trạng thái, không tự ghi đè quota song song với hàng lệnh. Offline Agent
vẫn xét Policy đang giữ; khi kết nối lại phải đối chiếu trước lệnh điều khiển tiếp.
ACK gửi lại cho Cmd cũ vẫn phải ghi đúng ngày của used hiện tại; không gắn used
hôm nay vào ngày của Cmd hôm qua. Server có thể hoàn tất seq cũ nhưng không được
trộn số used giữa hai ngày.

**Quy tắc qua ngày đề xuất để duyệt:** cộng/trừ gắn với ngày yêu cầu, không âm thầm
cấp sang hôm sau. LOCK/UNLOCK vẫn có hiệu lực cho tới lệnh thay thế.

Cmd cũ chưa được xử lý mà đến sau reset ngày: Agent không chép bất cứ phần nào
của bản đầy đủ đó, kể cả khi loại lệnh là LOCK/UNLOCK. Agent lưu seq đã xử lý với
kết quả not_applied/day_changed và ACK rõ kết quả này. Server chỉ bỏ bản giao cũ
sau ACK, rồi đối chiếu trạng thái/ngày hiện tại. Yêu cầu ADD/SUB hết hạn được ghi
nhận là không áp dụng. Yêu cầu LOCK/UNLOCK được tính lại thành Cmd mới, seq mới,
trước khi xử lý yêu cầu phía sau. Điều này không gây đảo thứ tự vì các yêu cầu
phía sau chưa được cấp seq. Retry request_id vẫn là cùng yêu cầu đang chờ.

Nếu Cmd đã được áp dụng trước đổi ngày nhưng chỉ mất ACK, Agent xác nhận applied
theo kết quả đã lưu; không thực hiện lại hoặc tạo thêm lần cộng giờ. Lỗi ghi/xử lý
không phải hết hạn: chưa tiến seq và chưa ACK hoàn tất. Quy tắc ngày trên là đề xuất
nghiệp vụ cần được duyệt cùng kế hoạch, không phải hành vi đã có.

## 7. Các bước triển khai

1. Chốt schema CmdRequest/Cmd/CmdAck, thứ tự và quy tắc ngày; cập nhật hợp đồng HTTP/WS.
2. Làm một nơi xử lý hàng lệnh trên Server: cấp seq, chống retry, tính kết quả và
   giữ tới ACK. `sendUrgentCmd()` chỉ tiếp nhận/chuyển giao; Heartbeat và WS dùng chung.
3. Làm một nơi áp dụng trên Agent: kiểm tra seq, chốt used, nhận kết quả và ACK.
   Thay đường tính lại trong `execCmd()` và đường gán quota không có seq.
4. Nối lưu/khôi phục và bảo vệ cập nhật đồng thời; đổi ngày/khởi động phải đối chiếu
   trước khi chạy tiếp. Không tự xóa dữ liệu/hàng chờ cũ để chuyển giao thức.
5. Đưa test tái hiện vào suite tương ứng, cập nhật docs theo code cuối và xóa các
   đường xử lý cũ trong phạm vi đã duyệt. Giữ nguyên comment cũ; comment bị lệch
   trách nhiệm phải được báo để người dùng quyết định, không tự viết lại.

File dự kiến: `shared/schemas.py`; `server/__init__.py`, `state.py`, `storage.py`
và phần quota liên quan; `agent/__init__.py`, `quota.py`, `state.py`, `storage.py`;
hai file test đang có. Chỉ tách file xử lý lệnh nếu cần để handler không chứa lại
nghiệp vụ; không thêm framework queue hoặc lớp quản lý tổng quát.

## 8. Kiểm chứng khi triển khai

- Chạy bốn thao tác cho DEVICE/APP/WEB, gồm lịch cấm, Idle, hết quota và khóa thủ công.
- Cùng Cmd tới qua WS rồi HB, hoặc HB rồi WS: kết quả chỉ áp dụng một lần.
- LOCK/UNLOCK liên tiếp; bản cũ, bản lặp và thiếu seq không đảo ngược lệnh mới.
- WS gửi được nhưng Agent chưa xử lý; ACK mất; ACK giả/vượt số; retry cùng request_id.
- SUB xuống dưới used rồi ADD; hai yêu cầu đến sát nhau; used có giây lẻ; used lệch đầu phiên.
- Bảng/tập rỗng, số 0, điều chỉnh âm đều được áp dụng đúng.
- Đổi ngày khi đang chờ ACK, offline/reconnect, restart và lỗi ghi trước/sau ACK.
- Kiểm tra hai handler cùng chạy, không chỉ test gọi tuần tự; bổ sung smoke test HTTP/WS.

Lệnh lấy từ cấu hình pytest và công cụ đã có của dự án: `.venv/Scripts/python.exe
-m pytest -q -p no:cacheprovider`; Ruff nhóm F/E9 cho file sửa; `git diff --check`.
Việc nhỏ/tài liệu kiểm tra tối đa 5 phút tổng cộng. Đây là thay đổi giao thức và
state nên khi triển khai phải chọn test theo rủi ro thực tế, ghi rõ phần chưa chạy.

## Lựa chọn và đánh đổi

Gửi delta nhưng thực thi tuần tự sẽ sửa ít hơn, song vẫn để Agent tính lại nghiệp
vụ. Chỉ gửi trạng thái mới nhất không đợi ACK nhanh hơn, nhưng có thể bỏ qua lệnh
trung gian và vẫn phải xử lý used chưa được chốt.

Chọn **kết quả tuyệt đối, chung seq và hoàn tất từng lệnh** vì giữ đúng trách nhiệm
đã thống nhất và xử lý cùng gốc lỗi. Đánh đổi: lệnh sau của cùng thiết bị phải chờ
ACK lệnh trước; không thể bảo đảm độ trễ nếu kết nối/Agent đang lỗi.

Chưa chạy test cho giao thức mới vì chưa có implementation. Bản này chỉ là kế hoạch;
cần người dùng duyệt trước khi sửa code, schema hoặc file dữ liệu hiện có.

Kiểm tra tài liệu ngày lập kế hoạch: các liên kết tương đối trỏ tới file có thật;
66 trường hợp số học phù hợp với công thức ADD dưới invariant ACK ở mục 5.
Đây không phải kiểm chứng chạy thực tế cho thứ tự lệnh, lưu file hoặc mạng.
