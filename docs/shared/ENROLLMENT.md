# Ghép đôi: từ mã nhập đến mã định danh

Agent chưa có mã định danh/token thì gửi mã ghép đôi người dùng nhập cùng fingerprint phần cứng. Server kiểm tra yêu cầu rồi trả thông tin để những lần giao tiếp sau nhận diện đúng thiết bị.

Các model nằm trong [shared/schemas.py](../../shared/schemas.py). POST `/api/v1/enroll` nối Agent `requestEnroll()` với Server `responseEnroll()`.

| Model | Trường bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `PairingCode` | `pairing_code: str` | Mã 8 ký tự Server đang chấp nhận |
| `PairingCode` | `created_at: int`, `expires_at: int` | Thời điểm tạo và hết hạn, Unix giây |
| `EnrollmentRequest` | `pairing_code: str`, `device_fingerprint: str` | Mã người dùng nhập và mã định danh phần cứng máy |
| `EnrollmentResponse` | `device_id: str` | Mã định danh thiết bị |
| `EnrollmentResponse` | `policy_id: str` | Mã định danh Policy gắn với thiết bị |
| `EnrollmentResponse` | `access_token: str` | Token Agent dùng để Server xác thực |
| `EnrollmentResponse` | `refresh_token: str` | Token dành cho việc cấp access token mới |

`PairingCode` là dữ liệu Server giữ trong `current_pairing_code`, không phải toàn bộ body Agent gửi. Schema yêu cầu mã đúng 8 ký tự; Server đối chiếu giá trị và thời hạn.

Agent lưu bốn trường response vào RAM. `policy_id` chỉ tham chiếu tới Policy; Agent lấy nội dung qua GET `/api/v1/policy`. Refresh token hiện được trả/lưu, nhưng endpoint cấp lại access token chưa được cài đặt.

Agent lấy fingerprint bằng UUID đọc từ WMI. Lỗi đọc hoặc UUID trống được thử lại tối đa 3 lần; nếu vẫn lỗi thì không gửi enrollment. Mã dự phòng chung đã được bỏ để hai máy không bị đăng ký cùng mã khi đọc UUID thất bại.
