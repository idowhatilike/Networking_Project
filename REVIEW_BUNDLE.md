# INDEPENDENT CODE REVIEW AUDIT BUNDLE (`REVIEW_BUNDLE.md`)

> Tài liệu này được đóng gói tự động và độc lập để phục vụ **Independent Code Review Audit** (bởi Gemini hoặc Reviewer độc lập) mà không cần truy cập trực tiếp vào repository.
> Bản bundle này phản ánh trạng thái repository ngay sau khi khắc phục **S-1**, **S-2** và thực hiện lượt `/review-all` lần 2.

---

## PHẦN 1: METADATA

### 1.1. Thông tin định danh & Thời gian
- **Repository Root:** `c:\Users\Trieu\Computer_Networking\Project`
- **Git Commit Hash hiện tại (`HEAD`):** `4754a6a1d79b5b55489b104c35ad9afa0523c1a8`
- **Thời điểm tạo Bundle:** `2026-10-31T12:36:35+07:00` (ISO 8601)

### 1.2. Danh sách các file đã được Antigravity Review
1. `.gitignore` *(Unstaged modified — 71 dòng)*
2. `agent/__init__.py` *(Unstaged modified — 397 dòng)*
3. `server/__init__.py` *(Unstaged modified — 289 dòng)*
4. `shared/schemas.py` *(Unstaged modified — 155 dòng)*
5. `tests/test_schemas.py` *(Unstaged modified — 347 dòng)*
6. `pyproject.toml` *(Unmodified dependency context — 40 dòng)*

### 1.3. Trạng thái Git Working Tree (`git status --porcelain=v1 -uall`)
```text
 M .gitignore
 M agent/__init__.py
 M server/__init__.py
 M shared/schemas.py
 M tests/test_schemas.py
?? REVIEW_BUNDLE.md
```
*(Ghi chú: Staged changes = 0 file; Unstaged changes = 5 file; Untracked = `REVIEW_BUNDLE.md`)*

### 1.4. Danh sách các file/thư mục bị loại trừ khỏi Bundle & Lý do
- `.venv/`, `__pycache__/`, `.pytest_cache/`: Môi trường ảo Python, bytecode và bộ nhớ đệm kiểm thử (build/dependency caches — loại trừ theo quy tắc).
- `.agents/` và `scripts/get_review_context.py`: Các file cấu hình skill nội bộ của IDE đã được đưa vào `.gitignore`, không phải mã nguồn ứng dụng của dự án.
- Không phát hiện thấy file `.env`, private keys, chứng chỉ số hay thông tin nhạy cảm (credentials/secrets) nào trong working tree.

---

## PHẦN 2: ORIGINAL REVIEW (`REVIEW_SUMMARY.md`)

Dưới đây là toàn bộ nội dung nguyên bản của file `REVIEW_SUMMARY.md` (từ lượt `/review-all` lần 2):

````markdown
# BÁO CÁO TỔNG HỢP CODE REVIEW (`/review-all` — Lần 2 sau khi sửa S-1 & S-2)

> **Thời gian thực hiện:** 2026-10-31  
> **Cơ chế thực thi:** Orchestrator + 3 Sub-agent chạy song song (`correctness-reviewer`, `security-reviewer`, `performance-reviewer`) ở chế độ **Read-Only** (`EnableWriteTools: false`, `EnableSubagentTools: false`).  
> **Cam kết nguyên trạng:** Không chỉnh sửa bất kỳ file source code nào; không thay đổi trạng thái Git staging/commit.

---

## 1. Phạm vi Review & Tình trạng Khắc phục so với Lần 1

Dữ liệu thu thập tự động từ Context Collector ([scripts/get_review_context.py](file:///c:/Users/Trieu/Computer_Networking/Project/scripts/get_review_context.py)):

- **Repository Root:** `C:/Users/Trieu/Computer_Networking/Project`
- **Trạng thái Git:** `Has Initial Commit: True`, `Batch: 1 / 1` (thu thập 100% diff, không cắt cụt).
  - **Staged Files (0):** Không có.
  - **Unstaged Files (5):** [.gitignore](file:///c:/Users/Trieu/Computer_Networking/Project/.gitignore), [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py), [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py), [shared/schemas.py](file:///c:/Users/Trieu/Computer_Networking/Project/shared/schemas.py), [tests/test_schemas.py](file:///c:/Users/Trieu/Computer_Networking/Project/tests/test_schemas.py).
  - **Untracked Files (1):** [REVIEW_BUNDLE.md](file:///c:/Users/Trieu/Computer_Networking/Project/REVIEW_BUNDLE.md).

### Xác nhận các mục đã được khắc phục từ Lần 1:
- **`[S-1]` (Đã khắc phục):** Endpoint [`/api/v1/urgent`](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L225-L244) đã xác thực `X-Parent-Token` qua biến môi trường `PARENT_TOKEN` (`401`) và kiểm tra `device_id in device_tokens` (`404`).
- **`[S-2]` (Đã khắc phục):** [`urgentWebsocketEndpoint()`](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L197-L222) đã dọn kết nối an toàn trong `finally` với điều kiện `if active_ws_connections.get(device_id) is websocket:`; [`sendUrgentCmd()`](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L276-L284) đã bọc `try...except` để xóa stale socket và fallback sang `heartbeat_sync`; [`UrgentCmdHandler()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L340-L396) đã có cờ chống chạy trùng `ws_handler_running`, bắt lỗi parse JSON riêng và vòng lặp tự kết nối lại.

---

## 2. Thống kê Verification Gate (Cổng xác minh của Orchestrator)

| Nguồn Sub-agent | Số Finding ban đầu | Gộp trùng (Deduplicated) | Loại bỏ (Ngoài phạm vi Enroll/Heartbeat cũ) | Giữ lại sau xác minh |
| :--- | :---: | :---: | :---: | :---: |
| **`correctness-reviewer`** | 4 *(nhóm gộp)* | 1 | 0 | **5** *(tách rõ từng lỗi C-1..C-5)* |
| **`security-reviewer`** | 6 | 0 | 3 *(Enroll token, Policy IDOR & Query token cũ)* | **3** |
| **`performance-reviewer`** | 5 | 2 | 1 *(Health check Heartbeat cũ)* | **2** |
| **Tổng cộng** | **15** | **3** | **4** | **9 Findings cần lưu ý** |

---

## 3. Chi tiết các Findings đã qua Verification Gate

### Nhóm A — Tính đúng đắn Logic & Đồng bộ Quota/Command (`Correctness`)

---

#### [C-1] `applyPolicy()` tự động ghi đè làm mất lệnh khóa máy (`LOCK`) của phụ huynh & trùng lặp `CmdHandler` giữa Heartbeat và WebSocket
- **Mức độ (Severity):** `Critical`
- **Vị trí:** [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L206-L214), [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L266-L281), [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L296-L333)
- **Mô tả (Dễ hiểu):**
  1. Khi phụ huynh gửi lệnh `LOCK` (khóa khẩn cấp), Agent đổi `status_cur = "locked"` và `device_block_reason = BlockReason.POLICY`. Tuy nhiên, Agent không lưu cờ ghi nhớ *"Máy đang bị phụ huynh khóa cưỡng bức"*. Khi [`applyPolicy()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L206-L214) chạy lại (ở nhịp Heartbeat kế tiếp hoặc khi phụ huynh cộng/trừ giờ cho 1 App/Web), hàm thấy máy vẫn trong khung giờ lịch tuần và chưa hết `device_unlocked_until` nên tự động chạy vào nhánh `else` và **mở khóa lại máy (`status_cur = "active"`)**.
  2. Đoạn code xử lý lệnh `LOCK`/`UNLOCK` đang bị viết lặp lại ở 2 nơi: bên trong [`HeartbeatResponseHanlder()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L270-L278) và bên trong [`executeUrgentCmd()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L299-L307).
- **Bằng chứng trong code:**
  ```python
  # agent/__init__.py (L299-L302 - trong executeUrgentCmd)
  if cmd.cmd_type == CommandType.LOCK :
      status_cur = "locked"
      device_block_reason = BlockReason.POLICY
      return

  # agent/__init__.py (L206-L214 - trong applyPolicy)
  if not cur_policy.schedule_7x48[day_idx][slot_idx] :
      status_cur = "locked"
      device_block_reason = BlockReason.SCHEDULE
  elif time.time() >= device_unlocked_until :
      status_cur = "locked"
      device_block_reason = BlockReason.DEVICE_QUOTA
  else :
      status_cur = "active" # <-- Tự động mở khóa lại máy!
      device_block_reason = BlockReason.NONE
  ```
- **Đề xuất sửa lỗi:**
  - Thêm cờ `is_manual_locked : bool = False`. Khi nhận lệnh `LOCK` thì bật `is_manual_locked = True`; chỉ khi nhận `UNLOCK` mới tắt `is_manual_locked = False`. Trong kiểm tra thiết bị, ưu tiên kiểm tra `if is_manual_locked:` đầu tiên để giữ trạng thái khóa.
  - Gom toàn bộ việc xử lý lệnh từ cả Heartbeat và WebSocket về gọi chung **1 hàm thực thi lệnh duy nhất**.

---

#### [C-2] Lệnh trừ giờ (`SUB_TIME`) cho `APP` và `WEB` bị chặn ở mức `0`, không thể trừ lẹm vào Quota gốc
- **Mức độ (Severity):** `High`
- **Vị trí:** [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L327-L332) và [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L263-L270)
- **Mô tả (Dễ hiểu):**
  - Với `DEVICE`, khi phụ huynh bấm `SUB_TIME` (trừ giờ), hệ thống trừ thẳng vào mốc hết hạn `device_unlocked_until`.
  - Nhưng với `APP` và `WEB`, code hiện chỉ trừ vào `app_bonus_time` / `web_bonus_time` rồi chặn dưới ở `0` bằng hàm `max(0, ...)`. Nếu ứng dụng `roblox.exe` có quota gốc 600 giây và chưa được thưởng thêm phút nào (`bonus = 0`), lệnh `SUB_TIME` 300 giây sẽ tính `max(0, 0 - 300) = 0`, khiến thời gian còn lại không hề giảm.
- **Bằng chứng trong code:**
  ```python
  # agent/__init__.py (L327-L332)
  elif cmd.target_type == TargetType.APP and cmd.subject :
      a_name = cmd.subject.lower().strip()
      app_bonus_time[a_name] = max(0 , app_bonus_time.get(a_name , 0) - cmd.sub_time)
  elif cmd.target_type == TargetType.WEB and cmd.subject :
      d_name = cmd.subject.lower().strip()
      web_bonus_time[d_name] = max(0 , web_bonus_time.get(d_name , 0) - cmd.sub_time)
  ```
- **Đề xuất sửa lỗi:**
  - Bỏ `max(0, ...)` khi trừ `sub_time` cho `APP` và `WEB` trên cả Server và Agent (cho phép `app_bonus_time` / `web_bonus_time` nhận giá trị âm để bù trừ trực tiếp vào `r.quota + bonus - used`).

---

#### [C-3] Lỗi giá trị `0` của `device_unlocked_until`: Khi trừ hết sạch giờ thiết bị về `0`, máy không khóa mà lại tự cấp mới toàn bộ Quota từ đầu
- **Mức độ (Severity):** `High`
- **Vị trí:** [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L202-L204), [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L254-L259), [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L325-L326) và [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L261-L262)
- **Mô tả (Dễ hiểu):**
  1. Trong [`applyPolicy()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L203-L204): Có dòng `if device_unlocked_until == 0 : device_unlocked_until = int(time.time()) + limit_sec`. Nếu `SUB_TIME` trừ mạnh tay làm `device_unlocked_until = max(0, ...) = 0`, ngay dòng sau `applyPolicy()` tưởng là máy mới bật lần đầu nên tự động cấp mới lại nguyên vẹn `limit_sec` (5400 giây).
  2. Trong [`HeartbeatResponseHanlder()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L254-L259): Điều kiện `if data.device_unlocked_until > 0:` và `if data.app_bonus_time:` khiến Agent bỏ qua không đồng bộ nếu giá trị trên Server bị giảm về `0` hoặc xóa về `{}`.
- **Bằng chứng trong code:**
  ```python
  # agent/__init__.py (L326 & L203-L204)
  device_unlocked_until = max(0 , device_unlocked_until - cmd.sub_time)
  ...
  if device_unlocked_until == 0 :
      device_unlocked_until = int(time.time()) + limit_sec
  ```
- **Đề xuất sửa lỗi:**
  - Khi trừ `SUB_TIME` cho `DEVICE`, giới hạn dưới ở `1` hoặc `int(time.time())` thay vì `0`: `device_unlocked_until = max(int(time.time()) , device_unlocked_until - cmd.sub_time)`.
  - Trong `HeartbeatResponseHanlder()`, gán trực tiếp `app_bonus_time = dict(data.app_bonus_time)` và `web_bonus_time = dict(data.web_bonus_time)`.

---

#### [C-4] Lỗi trùng mã lệnh (`cmd_id`) khi gửi nhiều lệnh trong cùng 1 giây qua hàng chờ Heartbeat
- **Mức độ (Severity):** `High`
- **Vị trí:** [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L160-L163), [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L285-L287) và [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L270-L281)
- **Mô tả (Dễ hiểu):**
  Khi mất kết nối WebSocket, [`sendUrgentCmd()`](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L286) tạo mã lệnh bằng giây nguyên: `cmd_id = f"{int(time.time())}:{cmd.cmd_type}"`. Nếu trong cùng 1 giây phụ huynh bấm `LOCK` $\rightarrow$ `UNLOCK` $\rightarrow$ `LOCK`, lệnh `LOCK` thứ hai trùng chuỗi `cmd_id` với lệnh đầu và bị tập chống trùng `executed_cmds` trên Agent bỏ qua.
- **Đề xuất sửa lỗi:**
  - Dùng `uuid.uuid4().hex[:8]` để tạo mã lệnh duy nhất: `cmd_id = f"{uuid.uuid4().hex[:8]}:{cmd.cmd_type}"`.

---

#### [C-5] Cộng thêm thời gian (`ADD_TIME`) cho `DEVICE` khi máy đã khóa từ lâu không mở lại được máy
- **Mức độ (Severity):** `Medium`
- **Vị trí:** [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L311-L314) và [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L246-L248)
- **Mô tả (Dễ hiểu):**
  Nếu máy đã hết hạn từ 2 tiếng trước (`device_unlocked_until < time.time()`) và phụ huynh cộng thêm 15 phút (`bonus_time = 900`), code hiện tại cộng thẳng 900 giây vào mốc quá khứ khiến mốc mới vẫn nhỏ hơn giờ hiện tại, máy tiếp tục bị khóa.
- **Đề xuất sửa lỗi:**
  - Tính mốc cộng thêm từ `max(device_unlocked_until , int(time.time())) + cmd.bonus_time` trên cả Server và Agent.

---

### Nhóm B — Hiệu năng & Cơ chế cập nhật nhẹ (`Performance`)

---

#### [P-1] Gọi lại toàn bộ `applyPolicy()` (quét toàn bộ tiến trình Windows) mỗi khi chỉ cộng/trừ giờ cho 1 đối tượng
- **Mức độ (Severity):** `High`
- **Vị trí:** [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L146-L215), [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L310-L333)
- **Mô tả (Dễ hiểu):**
  Trong [`executeUrgentCmd()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L321-L333), mỗi khi nhận `ADD_TIME` hoặc `SUB_TIME` cho `DEVICE`, 1 `WEB` hoặc 1 `APP`, Agent đều gọi lại toàn bộ [`applyPolicy()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L146-L215), kéo theo việc duyệt lại toàn bộ `domain_rules`, `app_rules`, quét toàn bộ tiến trình hệ điều hành qua `psutil.process_iter(["name"])` ngay trên luồng sự kiện `async` của `UrgentCmdHandler`.
- **Đề xuất sửa lỗi:**
  - Tách hàm cập nhật nhẹ theo đúng `target_type` (`updateDeviceStatus()`, `updateOneApp(app_name)`, `updateOneWeb(domain)`). Chỉ quét `psutil` khi `SUB_TIME` làm ứng dụng đó hết quota (`<= 0`).

---

#### [P-2] `UrgentCmdHandler()` reset `attempt = 0` trước khi `recv()` thành công và chưa giới hạn kích thước `executed_cmds` / `urgent_acks_store`
- **Mức độ (Severity):** `Medium`
- **Vị trí:** [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L117), [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L359-L364) và [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L48), [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L212)
- **Mô tả (Dễ hiểu):**
  1. Trong [`UrgentCmdHandler()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L360), biến `attempt = 0` đang được đặt ngay khi vừa mở `websockets.connect(ws_url)`, trước lệnh `data = await websocket.recv()` ([dòng 363](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L363)). Nếu Server đóng kết nối ngay sau khi bắt tay (ví dụ do sai `access_token` ở `urgentWebsocketEndpoint`), `recv()` văng lỗi ngay nhưng `attempt` đã bị reset về `0`, khiến lần thử lại tiếp theo luôn tính `attempt = 1` (`delay = base_delay`) và không dừng ở `max_retries`.
  2. Tập `executed_cmds` trên Agent và `urgent_acks_store` trên Server chưa có giới hạn số lượng phần tử tối đa trong RAM.
- **Bằng chứng trong code:**
  ```python
  # agent/__init__.py (L359-L363)
  async with websockets.connect(ws_url) as websocket :
      attempt = 0 # <-- Reset trước khi recv() thành công
      while stop_event is None or not stop_event.is_set() :
          data = await websocket.recv()
  ```
- **Đề xuất sửa lỗi:**
  - Di chuyển dòng `attempt = 0` xuống **ngay sau** dòng `data = await websocket.recv()`.
  - Giới hạn số phần tử lưu trong `urgent_acks_store[device_id]` và `executed_cmds`.

---

### Nhóm C — Bảo mật & An toàn Hệ thống (`Security & Safety`)

---

#### [S-3] An toàn khi tắt tiến trình bằng `proc.kill()` trong `applyPolicy()`, ghi file `quota_state.json` không nguyên tử và so sánh `parent_token`
- **Mức độ (Severity):** `Medium`
- **Vị trí:** [agent/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L187-L194) và [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L57-L67), [server/__init__.py](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L233)
- **Mô tả (Dễ hiểu):**
  1. Trong [`applyPolicy()`](file:///c:/Users/Trieu/Computer_Networking/Project/agent/__init__.py#L187-L194), vòng lặp `proc.kill()` chưa kiểm tra `proc.pid != os.getpid()` và danh sách tiến trình cốt lõi của Windows (`csrss.exe`, `svchost.exe`, `explorer.exe`...).
  2. Hàm [`saveQuotaState()`](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L57-L67) ghi đè trực tiếp `QUOTA_STATE_FILE.write_text(...)` thay vì ghi qua file tạm rồi `os.replace`.
  3. Tại [`sendUrgentCmd()`](file:///c:/Users/Trieu/Computer_Networking/Project/server/__init__.py#L233), phép đối chiếu `parent_token != expected_token` nên dùng `not secrets.compare_digest(parent_token, expected_token)` để chống rò rỉ thời gian so sánh chuỗi.

---

#### [S-4] File `REVIEW_BUNDLE.md` chưa được đưa vào `.gitignore`
- **Mức độ (Severity):** `Low`
- **Vị trí:** [.gitignore](file:///c:/Users/Trieu/Computer_Networking/Project/.gitignore#L63-L71)
- **Mô tả (Dễ hiểu):**
  File `REVIEW_BUNDLE.md` mới tạo ở bước trước đang xuất hiện là Untracked file trong Git (`?? REVIEW_BUNDLE.md`). Cần thêm `REVIEW_BUNDLE.md` vào `.gitignore` cùng với `REVIEW_SUMMARY.md` để tránh vô tình commit file bundle lên Git.

---

## 4. Những phần chưa thể xác minh (Unverified / Out-of-Scope)

1. **Cơ chế chặn tên miền (`blocked_domains`) ở tầng mạng thực tế (DNS / Hosts / Firewall):** Hiện mới lưu trong tập hợp `blocked_domains` trên RAM của Agent.
2. **Bộ đếm thời gian sử dụng thực tế (`quota_used`):** Hiện được đồng bộ qua Heartbeat và kiểm thử qua dữ liệu giả lập, chưa gắn với vòng lặp đo thời gian chạy thực tế của từng process/domain.
3. **Xác thực chữ ký số (`signature`) và mã băm `getFileSha256`:** Tác giả chủ đích để phần mật mã học (crypto) triển khai ở giai đoạn cuối.
````

---

## PHẦN 3: GIT DIFF

### 3.1. Staged Diff (`git diff --cached -M`)
*(Không có thay đổi nào trong vùng Staged)*

### 3.2. Unstaged Diff (`git diff -M`)
```diff
diff --git a/.gitignore b/.gitignore
index 1470d0a..21abe7a 100644
--- a/.gitignore
+++ b/.gitignore
@@ -59,3 +59,13 @@ Desktop.ini
 .idea/
 *.swp
 *.swo
+
+# Local AI review, debug & runtime state files
+.agents/
+.agent/
+_agents/
+_agent/
+scripts/
+REVIEW_SUMMARY.md
+quota_state.json
+*.tmp
diff --git a/agent/__init__.py b/agent/__init__.py
index 4368213..f7f3336 100644
--- a/agent/__init__.py
+++ b/agent/__init__.py
@@ -3,7 +3,14 @@
 from fastapi import FastAPI, HTTPException, Depends
 from fastapi import WebSocket, WebSocketDisconnect
 from pydantic import BaseModel
-from shared.schemas import HeartbeatResponse , Policy
+from shared.schemas import (
+    BlockReason,
+    CommandType,
+    HeartbeatResponse,
+    Policy,
+    TargetType,
+    UrgentCmd,
+)
 from sqlalchemy import create_engine, String, ForeignKey
 from sqlalchemy.orm import (
     DeclarativeBase,
@@ -13,6 +20,7 @@ from sqlalchemy.orm import (
     Session
 )
 import sqlite3
+import asyncio
 import httpx
 import websockets
 import os
@@ -32,7 +40,7 @@ DEFAULT_DEVICE_FINGERPRINT = "0000-0000-0000-0000-000000000000"
 # device fingerprint = UUID = Id trên chip BIOS/UEFI
 def getMachineGuid() -> str :
     try :
-        #Connect WMI - Windows Management Instrumentation
+        #Connect WMI
         wmi = win32com.client.GetObject("winmgmts:")
         #Yêu cầu lấy mỗi UUID từ class Win32_ComputerSystemProduct 
         result = wmi.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")
@@ -42,12 +50,10 @@ def getMachineGuid() -> str :
 cdId = getMachineGuid() #current_deviced_fingerprint
 
 
-pairing_time_count = 0
 def getPairingCode(prompt : str = "Ma ghep enroll: " , max_attempts : int = 5) -> str :
     for __ in range(max_attempts) :
         code = input(prompt).strip()
         if len(code) == 8 :
-            pairing_time_count = time.time()
             return code
         print("Ma ghep phai dung 8 ky tu")
     raise ValueError("Nhap ma ghep that bai")
@@ -95,54 +101,134 @@ HEARTBEAT_URL = f"{SERVER_URL}/api/v1/heartbeat"
 POLICY_URL = f"{SERVER_URL}/api/v1/policy"
 
 status_cur = "active"
-quota_used : dict[str , int] = {}
+quota_used : dict[str , int] = {} #Thời gian đã dùng của từng process_name / domain
+device_unlocked_until : int = 0 #Thời điểm hết hạn dùng toàn thiết bị (Device-level quota)
+app_bonus_time : dict[str , int] = {} #Bonus time riêng từng ứng dụng (độc lập với Policy gốc)
+web_bonus_time : dict[str , int] = {} #Bonus time riêng từng website/domain (độc lập với Policy gốc)
+
+device_block_reason : BlockReason = BlockReason.NONE #Nguyên nhân khóa toàn thiết bị
+app_block_reasons : dict[str , BlockReason] = {} #Nguyên nhân chặn của từng ứng dụng
+domain_block_reasons : dict[str , BlockReason] = {} #Nguyên nhân chặn của từng website/domain
+
 cur_policy_version = 0
 cur_policy : Policy | None = None
 blocked_domains : set[str] = set()
+acked_commands : list[str] = [] #Danh sách lệnh chờ báo xác nhận (ACK) về Server
+executed_cmds : set[str] = set() #Tập hợp lưu các lệnh đã chạy để chống thực thi trùng
+
+
+def getAppRemainingQuota(process_name : str) -> int :
+    #Tính quota còn lại của ứng dụng = quota gốc + bonus time - usage
+    if cur_policy is None :
+        return 0
+    a_name = process_name.lower().strip()
+    for r in cur_policy.app_rules :
+        if r.exe_name.lower() == a_name :
+            bonus = app_bonus_time.get(a_name , 0)
+            used = quota_used.get(a_name , 0)
+            return r.quota + bonus - used
+    return 0
+
+
+def getWebRemainingQuota(domain : str) -> int :
+    #Tính quota còn lại của website = quota gốc + bonus time - usage
+    if cur_policy is None :
+        return 0
+    d_name = domain.lower().strip()
+    for r in cur_policy.domain_rules :
+        if r.domain.lower() == d_name :
+            bonus = web_bonus_time.get(d_name , 0)
+            used = quota_used.get(d_name , 0)
+            return r.quota + bonus - used
+    return 0
 
 
-def applyPolicy() : #Code bởi antigravity
-    global status_cur , blocked_domains
+def applyPolicy() :
+    global status_cur , blocked_domains , device_unlocked_until
+    global device_block_reason , app_block_reasons , domain_block_reasons
     if cur_policy is None :
         return
 
-    #1.Cập nhật danh sách web bị chặn
-    blocked_domains = {r.domain.lower() for r in cur_policy.domain_rules if not r.allowed}
+    #1.Kiểm tra Web-level quota: phân biệt chặn do Policy hay hết Web Quota
+    blocked_domains = set()
+    for r in cur_policy.domain_rules :
+        d_name = r.domain.lower()
+        if not r.allowed :
+            domain_block_reasons[d_name] = BlockReason.POLICY #Bị cấm trực tiếp trong Policy
+            blocked_domains.add(d_name)
+        elif r.quota > 0 :
+            remaining = r.quota + web_bonus_time.get(d_name , 0) - quota_used.get(d_name , 0)
+            if remaining <= 0 :
+                domain_block_reasons[d_name] = BlockReason.WEB_QUOTA #Hết quota riêng của website
+                blocked_domains.add(d_name)
+            else :
+                domain_block_reasons[d_name] = BlockReason.NONE
+        else :
+            domain_block_reasons[d_name] = BlockReason.NONE
 
-    #2.Quét và tắt app bị chặn theo tên
-    blocked_names = {r.exe_name.lower() for r in cur_policy.app_rules if not r.allowed}
-    for proc in psutil.process_iter(["name"]) :
-        try :
-            p_name = (proc.info["name"] or "").lower()
-            if p_name in blocked_names :
-                proc.kill()
-        except Exception :
-            continue
-
-    #3.Kiểm tra lịch tuần 7x48 và hạn mức ngày
-    now = datetime.now() #Lấy giờ hệ thống hiện tại
-    day_idx = now.weekday() #Thứ trong tuần: 0(Thứ 2)->4(Thứ 6), 5(Thứ 7), 6(CN)
-    slot_idx = now.hour * 2 + (now.minute // 30) #Khung 30p thứ mấy trong 48 khung (0->47)
-    limit_sec = cur_policy.weekend_quota if day_idx >= 5 else cur_policy.weekday_quota #Chọn quota cuối tuần hoặc ngày thường
-    total_used = sum(quota_used.values()) #Tổng số giây đã dùng của mọi app/web
-    if not cur_policy.schedule_7x48[day_idx][slot_idx] or total_used >= limit_sec : #Ngoài khung giờ hoặc hết quota
+    #2.Kiểm tra App-level quota (theo process name): phân biệt chặn do Policy hay hết App Quota
+    blocked_names = set()
+    for r in cur_policy.app_rules :
+        a_name = r.exe_name.lower()
+        if not r.allowed :
+            app_block_reasons[a_name] = BlockReason.POLICY #Bị cấm trực tiếp trong Policy
+            blocked_names.add(a_name)
+        elif r.quota > 0 :
+            remaining = r.quota + app_bonus_time.get(a_name , 0) - quota_used.get(a_name , 0)
+            if remaining <= 0 :
+                app_block_reasons[a_name] = BlockReason.APP_QUOTA #Hết quota riêng của ứng dụng
+                blocked_names.add(a_name)
+            else :
+                app_block_reasons[a_name] = BlockReason.NONE
+        else :
+            app_block_reasons[a_name] = BlockReason.NONE
+
+    #Chỉ chặn ứng dụng vi phạm (không khóa toàn thiết bị khi chỉ hết App Quota)
+    if blocked_names :
+        for proc in psutil.process_iter(["name"]) :
+            try :
+                p_name = (proc.info["name"] or "").lower()
+                if p_name in blocked_names :
+                    proc.kill()
+            except Exception :
+                continue
+
+    #3.Kiểm tra Schedule (7x48) và Device-level quota (device_unlocked_until)
+    now_dt = datetime.now() #Lấy giờ hệ thống hiện tại
+    day_idx = now_dt.weekday() #Thứ trong tuần: 0(Thứ 2)->4(Thứ 6), 5(Thứ 7), 6(CN)
+    slot_idx = now_dt.hour * 2 + (now_dt.minute // 30) #Khung 30p thứ mấy trong 48 khung (0->47)
+    limit_sec = cur_policy.weekend_quota if day_idx >= 5 else cur_policy.weekday_quota #Quota thiết bị gốc từ Policy
+
+    #Khởi tạo device_unlocked_until lần đầu nếu chưa được đặt
+    if device_unlocked_until == 0 :
+        device_unlocked_until = int(time.time()) + limit_sec
+
+    if not cur_policy.schedule_7x48[day_idx][slot_idx] : #Ngoài khung giờ lịch tuần
         status_cur = "locked"
+        device_block_reason = BlockReason.SCHEDULE
+    elif time.time() >= device_unlocked_until : #Hết hạn thời gian toàn thiết bị
+        status_cur = "locked"
+        device_block_reason = BlockReason.DEVICE_QUOTA
+    else :
+        status_cur = "active"
+        device_block_reason = BlockReason.NONE
 
 
-def requestPolicy() : #Code bởi antigravity
+def requestPolicy() :
     response = httpx.get(
         POLICY_URL ,
         params = {
             "device_id" : device_id ,
             "access_token" : access_token ,
             "policy_id" : policy_id
-        }
+        } ,
+        timeout = 3.6
     )
     response.raise_for_status()
     return Policy(**response.json())
 
 
-def requestHeartbeat() : 
+def requestHeartbeat() :
     response = httpx.post(
         HEARTBEAT_URL , 
         json = {
@@ -151,30 +237,51 @@ def requestHeartbeat() :
             "policy_id" : policy_id ,
             "status_cur" : status_cur ,
             "quota_used" : quota_used ,
-            "cur_policy_version" : cur_policy_version
-        }
+            "cur_policy_version" : cur_policy_version ,
+            "acked_commands" : acked_commands #Gửi danh sách lệnh đã nhận để Server xóa khỏi hàng chờ
+        } ,
+        timeout = 3.6
     )
     
-    response.raise_for_status()
+    response.raise_for_status() #Nếu mất mạng/lỗi sẽ dừng tại đây, acked_commands vẫn còn để nhịp sau retry
+    acked_commands.clear() #Gửi thành công lên Server thì làm trống danh sách chờ xác nhận
     return HeartbeatResponse(**response.json())
 
-def HeartbeatResponseHanlder(data : HeartbeatResponse) : #Code bởi antigravity
-    global cur_policy , cur_policy_version , status_cur
-    #1.Cập nhật và áp dụng Policy mới nếu lệch version
+def HeartbeatResponseHanlder(data : HeartbeatResponse) :
+    global cur_policy , cur_policy_version , status_cur , device_unlocked_until
+    global app_bonus_time , web_bonus_time , device_block_reason
+    #1.Đồng bộ trạng thái quota/bonus từ Server (hỗ trợ khôi phục khi Agent restart hoặc rớt WebSocket)
+    if data.device_unlocked_until > 0 :
+        device_unlocked_until = data.device_unlocked_until
+    if data.app_bonus_time :
+        app_bonus_time = dict(data.app_bonus_time)
+    if data.web_bonus_time :
+        web_bonus_time = dict(data.web_bonus_time)
+
+    #2.Cập nhật Policy mới nếu lệch version (không ghi đè bonus time)
     if data.latest_policy_version > cur_policy_version :
         cur_policy = requestPolicy()
         cur_policy_version = cur_policy.policy_version
+
+    if cur_policy is not None :
         applyPolicy()
 
-    #2.Xử lý lệnh chờ
+    #3.Xử lý lệnh chờ (lưu ACK, retry khi lỗi và chống thực thi trùng)
     for cmd in data.pending_commands :
-        if cmd == "lock" :
-            status_cur = "locked"
-        elif cmd == "unlock" :
-            status_cur = "active"
+        if cmd not in executed_cmds : #Kiểm tra biến chống trùng: chỉ chạy nếu lệnh này chưa từng chạy
+            if cmd == "lock" or cmd.endswith(":lock") :
+                status_cur = "locked"
+                device_block_reason = BlockReason.POLICY
+            elif cmd == "unlock" or cmd.endswith(":unlock") :
+                status_cur = "active"
+                device_block_reason = BlockReason.NONE
+            executed_cmds.add(cmd) #Ghi vào biến chống trùng để nếu Server gửi lại cũng không chạy lần 2
 
+        if cmd not in acked_commands : #Đưa lệnh vào danh sách chờ báo xác nhận (ACK) ở nhịp Heartbeat sau
+            acked_commands.append(cmd)
 
-def requestHeartbeat_loop(interval : int = 60) : #Tránh magic number :! Chisikudo advice
+
+def requestHeartbeatLoop(interval : int = 60) : #Tránh magic number :! Chisikudo advice
     while True :
         try :
             if checkServerConnection() :
@@ -184,3 +291,107 @@ def requestHeartbeat_loop(interval : int = 60) : #Tránh magic number :! Chisiku
             print(f"Loi : {e}")
         time.sleep(interval)
 
+
+#Thực thi lệnh khẩn (tách riêng khỏi logic nhận WebSocket)
+def executeUrgentCmd(cmd : UrgentCmd) :
+    global status_cur , device_unlocked_until , app_bonus_time , web_bonus_time , device_block_reason
+    #1.Khóa toàn bộ thiết bị ngay
+    if cmd.cmd_type == CommandType.LOCK :
+        status_cur = "locked"
+        device_block_reason = BlockReason.POLICY
+        return
+    #2.Mở khóa thiết bị
+    elif cmd.cmd_type == CommandType.UNLOCK :
+        status_cur = "active"
+        device_block_reason = BlockReason.NONE
+        return
+
+    #3.Cộng thêm thời gian (ADD_TIME) cho DEVICE, APP hoặc WEB độc lập với Policy gốc
+    if cmd.cmd_type == CommandType.ADD_TIME :
+        if cmd.target_type == TargetType.DEVICE :
+            if device_unlocked_until == 0 :
+                device_unlocked_until = int(time.time())
+            device_unlocked_until += cmd.bonus_time
+        elif cmd.target_type == TargetType.APP and cmd.subject :
+            a_name = cmd.subject.lower().strip()
+            app_bonus_time[a_name] = app_bonus_time.get(a_name , 0) + cmd.bonus_time
+        elif cmd.target_type == TargetType.WEB and cmd.subject :
+            d_name = cmd.subject.lower().strip()
+            web_bonus_time[d_name] = web_bonus_time.get(d_name , 0) + cmd.bonus_time
+        applyPolicy()
+
+    #4.Trừ bớt thời gian (SUB_TIME) của DEVICE, APP hoặc WEB độc lập với Policy gốc
+    elif cmd.cmd_type == CommandType.SUB_TIME :
+        if cmd.target_type == TargetType.DEVICE :
+            device_unlocked_until = max(0 , device_unlocked_until - cmd.sub_time)
+        elif cmd.target_type == TargetType.APP and cmd.subject :
+            a_name = cmd.subject.lower().strip()
+            app_bonus_time[a_name] = max(0 , app_bonus_time.get(a_name , 0) - cmd.sub_time)
+        elif cmd.target_type == TargetType.WEB and cmd.subject :
+            d_name = cmd.subject.lower().strip()
+            web_bonus_time[d_name] = max(0 , web_bonus_time.get(d_name , 0) - cmd.sub_time)
+        applyPolicy()
+
+
+#Nhận lệnh khẩn qua WebSocket và gửi ACK (có chống chạy trùng, tự kết nối lại với exponential backoff và dừng an toàn)
+WS_URGENT_URL = SERVER_URL.replace("http" , "ws") + "/ws/urgent"
+ws_handler_running : bool = False
+
+async def UrgentCmdHandler(
+    stop_event : asyncio.Event | None = None ,
+    max_retries : int | None = None ,
+    base_delay : float = 1.0 ,
+    max_delay : float = 30.0
+) :
+    global ws_handler_running
+    #Ngăn chặn khởi chạy trùng nhiều UrgentCmdHandler cùng lúc
+    if ws_handler_running :
+        print("UrgentCmdHandler dang chay, bo qua khoi tao trung")
+        return
+
+    ws_handler_running = True
+    attempt = 0
+    try :
+        while stop_event is None or not stop_event.is_set() :
+            ws_url = f"{WS_URGENT_URL}?device_id={device_id}&access_token={access_token}"
+            try :
+                #1.Thiết lập kết nối WebSocket với Server
+                async with websockets.connect(ws_url) as websocket :
+                    attempt = 0 #Reset bộ đếm retry khi đã kết nối thành công
+                    while stop_event is None or not stop_event.is_set() :
+                        #2.Nhận gói tin, parse JSON và validate bằng UrgentCmd
+                        data = await websocket.recv()
+                        try :
+                            cmd = UrgentCmd(**json.loads(data))
+                        except Exception as parse_err :
+                            print(f"Loi goi tin UrgentCmd : {parse_err}")
+                            continue
+
+                        #3.Gọi hàm thực thi riêng
+                        executeUrgentCmd(cmd)
+
+                        #4.Gửi ACK báo kết quả thực thi về Server
+                        ack_payload = {
+                            "status" : "ack" ,
+                            "cmd_type" : cmd.cmd_type ,
+                            "target_type" : cmd.target_type ,
+                            "subject" : cmd.subject ,
+                            "status_cur" : status_cur ,
+                            "device_unlocked_until" : device_unlocked_until ,
+                            "app_bonus_time" : app_bonus_time ,
+                            "web_bonus_time" : web_bonus_time
+                        }
+                        await websocket.send(json.dumps(ack_payload))
+            except asyncio.CancelledError :
+                raise
+            except Exception as conn_err :
+                attempt += 1
+                print(f"Loi ket noi WebSocket urgent (lan {attempt}) : {conn_err}")
+                if max_retries is not None and attempt > max_retries :
+                    break
+                if stop_event is not None and stop_event.is_set() :
+                    break
+                delay = min(max_delay , base_delay * (2 ** (attempt - 1)))
+                await asyncio.sleep(delay)
+    finally :
+        ws_handler_running = False
diff --git a/server/__init__.py b/server/__init__.py
index eb893b5..767ef53 100644
--- a/server/__init__.py
+++ b/server/__init__.py
@@ -1,15 +1,18 @@
 #Server
 
-from fastapi import FastAPI, HTTPException, Depends, status
+from fastapi import FastAPI, HTTPException, Depends, Header, status
 from fastapi import WebSocket, WebSocketDisconnect
 from pydantic import BaseModel
 from shared.schemas import (
+    CommandType,
     EnrollmentRequest,
     EnrollmentResponse,
     HeartbeatRequest,
     HeartbeatResponse,
     PairingCode,
     Policy,
+    TargetType,
+    UrgentCmd,
 )
 from sqlalchemy import create_engine, String, ForeignKey
 from sqlalchemy.orm import (
@@ -36,11 +39,55 @@ app = FastAPI()
 
 curCode : PairingCode | None = None
 
-#Bộ nhớ tạm trên Server
+#Bộ nhớ trên Server
 device_tokens : dict[str , str] = {}
 device_states : dict[str , dict] = {}
 policies_store : dict[str , Policy] = {}
 pending_cmds_store : dict[str , list[str]] = {}
+active_ws_connections : dict[str , WebSocket] = {} #Quản lý kết nối WebSocket theo device_id
+urgent_acks_store : dict[str , list[dict]] = {} #Lưu lịch sử ACK của lệnh khẩn từ Agent
+
+#Quản lý thời điểm hết hạn thiết bị và bonus time từng app/web độc lập với Policy gốc
+device_unlocked_store : dict[str , int] = {} #device_id -> device_unlocked_until (timestamp)
+app_bonus_store : dict[str , dict[str , int]] = {} #device_id -> {process_name : bonus_sec}
+web_bonus_store : dict[str , dict[str , int]] = {} #device_id -> {domain : bonus_sec}
+QUOTA_STATE_FILE = Path("quota_state.json")
+
+
+def saveQuotaState() :
+    #Lưu bền vững trạng thái quota/bonus trên Server xuống file
+    try :
+        data = {
+            "device_unlocked" : device_unlocked_store ,
+            "app_bonus" : app_bonus_store ,
+            "web_bonus" : web_bonus_store
+        }
+        QUOTA_STATE_FILE.write_text(json.dumps(data) , encoding = "utf-8")
+    except Exception :
+        pass
+
+
+def loadQuotaState() :
+    #Khôi phục trạng thái quota/bonus đã lưu bền vững trên Server
+    global device_unlocked_store , app_bonus_store , web_bonus_store
+    if QUOTA_STATE_FILE.exists() :
+        try :
+            data = json.loads(QUOTA_STATE_FILE.read_text(encoding = "utf-8"))
+            device_unlocked_store = {k : int(v) for k , v in data.get("device_unlocked" , {}).items()}
+            app_bonus_store = {
+                k : {ak : int(av) for ak , av in v.items()}
+                for k , v in data.get("app_bonus" , {}).items()
+            }
+            web_bonus_store = {
+                k : {wk : int(wv) for wk , wv in v.items()}
+                for k , v in data.get("web_bonus" , {}).items()
+            }
+        except Exception :
+            pass
+
+
+loadQuotaState()
+
 
 @app.post("/api/v1/enroll" , response_model = EnrollmentResponse)
 def responseEnroll(payload : EnrollmentRequest) :
@@ -72,6 +119,15 @@ def responseEnroll(payload : EnrollmentRequest) :
             signature = "unsigned"
         )
 
+    #Khởi tạo device_unlocked_until, app_bonus_time và web_bonus_time độc lập với Policy gốc
+    if dev_id not in device_unlocked_store :
+        plc = policies_store[plc_id]
+        base_quota = plc.weekend_quota if datetime.now().weekday() >= 5 else plc.weekday_quota
+        device_unlocked_store[dev_id] = int(time.time()) + base_quota
+    app_bonus_store.setdefault(dev_id , {})
+    web_bonus_store.setdefault(dev_id , {})
+    saveQuotaState()
+
     return EnrollmentResponse(
         device_id = dev_id,
         access_token = acc_token,
@@ -81,7 +137,7 @@ def responseEnroll(payload : EnrollmentRequest) :
 
 
 @app.post("/api/v1/heartbeat" , response_model = HeartbeatResponse)
-def responseHeartbeat(payload : HeartbeatRequest) : #4 bước - Code bởi antigravity
+def responseHeartbeat(payload : HeartbeatRequest) :
     #1.Check device_id và access_token hợp lệ
     if device_tokens.get(payload.device_id) != payload.access_token :
         raise HTTPException(
@@ -89,7 +145,7 @@ def responseHeartbeat(payload : HeartbeatRequest) : #4 bước - Code bởi anti
             detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID",
         )
 
-    #2.Ghi trạng thái của Agent
+    #2.Ghi trạng thái và usage của Agent
     device_states[payload.device_id] = {
         "status_cur": payload.status_cur,
         "quota_used": payload.quota_used,
@@ -99,17 +155,25 @@ def responseHeartbeat(payload : HeartbeatRequest) : #4 bước - Code bởi anti
     policy = policies_store.get(payload.policy_id)
     latest_ver = policy.policy_version if policy else payload.cur_policy_version
 
-    #4.Lấy danh sách lệnh
-    cmds = pending_cmds_store.pop(payload.device_id, [])
+    #4.Xử lý xác nhận (ACK) và xuất vector lệnh chờ (không xóa ngay để tự retry nếu rớt mạng)
+    #Bổ sung chống cơ chế Data Integrity cho vector <cmd>
+    cur_cmds = pending_cmds_store.get(payload.device_id , []) #Lấy danh sách lệnh đang lưu của thiết bị
+    if payload.acked_commands : #Nếu Agent gửi kèm danh sách lệnh đã nhận thành công
+        cur_cmds = [c for c in cur_cmds if c not in payload.acked_commands] #Lọc bỏ các lệnh đã được Agent xác nhận
+        pending_cmds_store[payload.device_id] = cur_cmds #Lưu lại phần lệnh chưa được xác nhận để gửi tiếp
 
+    #5.Trả về kèm trạng thái device_unlocked_until, app_bonus_time, web_bonus_time để đồng bộ
     return HeartbeatResponse(
         latest_policy_version = latest_ver ,
-        pending_commands = cmds
+        pending_commands = cur_cmds ,
+        device_unlocked_until = device_unlocked_store.get(payload.device_id , 0) ,
+        app_bonus_time = app_bonus_store.get(payload.device_id , {}) ,
+        web_bonus_time = web_bonus_store.get(payload.device_id , {})
     )
 
 
 @app.get("/api/v1/policy" , response_model = Policy)
-def responsePolicy(device_id : str , access_token : str , policy_id : str) : #Code bởi antigravity
+def responsePolicy(device_id : str , access_token : str , policy_id : str) :
     #1.Check device_id và access_token
     if device_tokens.get(device_id) != access_token :
         raise HTTPException(
@@ -125,4 +189,101 @@ def responsePolicy(device_id : str , access_token : str , policy_id : str) : #Co
             detail = "Khong tim thay Policy" ,
         )
 
-    return policy
\ No newline at end of file
+    return policy
+
+
+#WebSocket kênh lệnh khẩn
+@app.websocket("/ws/urgent")
+async def urgentWebsocketEndpoint(websocket : WebSocket , device_id : str , access_token : str) :
+    #1.Xác thực Agent bằng device_id và access_token
+    if device_tokens.get(device_id) != access_token :
+        await websocket.close(code = status.WS_1008_POLICY_VIOLATION)
+        return
+
+    #2.Chấp nhận kết nối và lưu theo device_id
+    await websocket.accept()
+    active_ws_connections[device_id] = websocket
+
+    #3.Lắng nghe ACK trả về từ Agent và luôn dọn kết nối an toàn trong finally
+    try :
+        while True :
+            ack_data = await websocket.receive_json() #Nhận gói ACK từ Agent
+            if isinstance(ack_data , dict) :
+                urgent_acks_store.setdefault(device_id , []).append(ack_data) #Ghi nhận kết quả ACK
+                if "status_cur" in ack_data and device_id in device_states :
+                    device_states[device_id]["status_cur"] = ack_data["status_cur"] #Đồng bộ ngay trạng thái mới
+    except WebSocketDisconnect :
+        pass
+    except Exception as e :
+        print(f"Loi WebSocket urgent ({device_id}) : {e}")
+    finally :
+        #Chỉ xóa nếu kết nối đang lưu đúng là kết nối hiện tại (không xóa nhầm kết nối mới hơn của cùng device_id)
+        if active_ws_connections.get(device_id) is websocket :
+            active_ws_connections.pop(device_id , None)
+
+
+@app.post("/api/v1/urgent")
+async def sendUrgentCmd(
+    device_id : str ,
+    cmd : UrgentCmd ,
+    parent_token : str | None = Header(default = None , alias = "X-Parent-Token")
+) :
+    #0.Xác thực quyền Parent/Admin qua biến môi trường PARENT_TOKEN và kiểm tra device_id đã đăng ký
+    expected_token = os.environ.get("PARENT_TOKEN")
+    if not expected_token or not isinstance(parent_token , str) or parent_token != expected_token :
+        raise HTTPException(
+            status_code = status.HTTP_401_UNAUTHORIZED ,
+            detail = "Khong co quyen thuc thi lenh khan" ,
+        )
+    if device_id not in device_tokens :
+        raise HTTPException(
+            status_code = status.HTTP_404_NOT_FOUND ,
+            detail = "Thiet bi khong ton tai" ,
+        )
+
+    #1.Cập nhật bonus/hạn mức cho DEVICE, APP hoặc WEB độc lập với Policy gốc và lưu bền vững
+    if cmd.cmd_type == CommandType.ADD_TIME :
+        if cmd.target_type == TargetType.DEVICE :
+            cur_until = device_unlocked_store.get(device_id , int(time.time()))
+            device_unlocked_store[device_id] = cur_until + cmd.bonus_time
+        elif cmd.target_type == TargetType.APP and cmd.subject :
+            app_name = cmd.subject.lower().strip()
+            dev_bonus = app_bonus_store.setdefault(device_id , {})
+            dev_bonus[app_name] = dev_bonus.get(app_name , 0) + cmd.bonus_time
+        elif cmd.target_type == TargetType.WEB and cmd.subject :
+            domain_name = cmd.subject.lower().strip()
+            dev_web_bonus = web_bonus_store.setdefault(device_id , {})
+            dev_web_bonus[domain_name] = dev_web_bonus.get(domain_name , 0) + cmd.bonus_time
+        saveQuotaState()
+
+    elif cmd.cmd_type == CommandType.SUB_TIME :
+        if cmd.target_type == TargetType.DEVICE :
+            cur_until = device_unlocked_store.get(device_id , int(time.time()))
+            device_unlocked_store[device_id] = max(0 , cur_until - cmd.sub_time)
+        elif cmd.target_type == TargetType.APP and cmd.subject :
+            app_name = cmd.subject.lower().strip()
+            dev_bonus = app_bonus_store.setdefault(device_id , {})
+            dev_bonus[app_name] = max(0 , dev_bonus.get(app_name , 0) - cmd.sub_time)
+        elif cmd.target_type == TargetType.WEB and cmd.subject :
+            domain_name = cmd.subject.lower().strip()
+            dev_web_bonus = web_bonus_store.setdefault(device_id , {})
+            dev_web_bonus[domain_name] = max(0 , dev_web_bonus.get(domain_name , 0) - cmd.sub_time)
+        saveQuotaState()
+
+    #2.Nếu Agent đang mở WebSocket thì đẩy lệnh khẩn ngay; nếu kết nối stale/lỗi thì dọn dẹp và chuyển sang heartbeat_sync
+    ws = active_ws_connections.get(device_id)
+    if ws is not None :
+        try :
+            await ws.send_json(cmd.model_dump())
+            return {"sent" : True , "via" : "websocket" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
+        except Exception as e :
+            print(f"Loi gui WebSocket urgent ({device_id}) : {e}")
+            if active_ws_connections.get(device_id) is ws :
+                active_ws_connections.pop(device_id , None)
+
+    #3.Nếu mất kết nối WebSocket: lưu lệnh LOCK/UNLOCK vào hàng chờ Heartbeat (quota đã lưu ở bước 1)
+    if cmd.cmd_type in (CommandType.LOCK , CommandType.UNLOCK) :
+        cmd_id = f"{int(time.time())}:{cmd.cmd_type}"
+        pending_cmds_store.setdefault(device_id , []).append(cmd_id)
+
+    return {"sent" : False , "via" : "heartbeat_sync" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
diff --git a/shared/schemas.py b/shared/schemas.py
index 440ad7d..33477f0 100644
--- a/shared/schemas.py
+++ b/shared/schemas.py
@@ -1,4 +1,9 @@
-"Giao thức và đối tượng chung . Tuân thủ NT (Obj = Ứng dụng/Website)"
+#Giao thức và đối tượng chung . Tuân thủ NT (Obj = Ứng dụng/Website)
+
+#Note : Ký hiệu chuẩn 
+#ACK = Acknowledgment - Thông điệp xác nhận
+#WMI = Windows Management Instrumentation - Quản trị windows
+
 from enum import StrEnum
 from typing import Literal
 from pydantic import BaseModel, Field
@@ -34,6 +39,23 @@ class UserRole(StrEnum) :
     ADMIN = "admin"
 
 
+class BlockReason(StrEnum) :
+    #Phân biệt 5 nguyên nhân chặn
+    NONE = "none"
+    POLICY = "policy"             #Bị cấm trực tiếp trong Policy (allowed == False)
+    SCHEDULE = "schedule"         #Ngoài khung giờ lịch tuần 7x48
+    DEVICE_QUOTA = "device_quota" #Hết hạn thời gian toàn thiết bị (device_unlocked_until)
+    APP_QUOTA = "app_quota"       #Hết quota của riêng ứng dụng
+    WEB_QUOTA = "web_quota"       #Hết quota của riêng website/domain
+
+
+class TargetType(StrEnum) :
+    #3 phạm vi tác động của lệnh thời gian
+    DEVICE = "device"
+    APP = "app"
+    WEB = "web"
+
+
 class EventState(BaseModel) :
     #Event state
     ts: int = Field(... , description = "Unix thời gian (seconds)")
@@ -46,6 +68,10 @@ class EventState(BaseModel) :
     idempotency_key: str = Field(... , description = "Chống trùng khi đồng bộ")
 
 
+#Alias tương thích với test
+EventRecord = EventState
+
+
 #Agent gửi request , server xử lý và gửi trả response 
 #Các class sau hỗ trợ giao tiếp 
 
@@ -74,24 +100,45 @@ class HeartbeatRequest(BaseModel) :
     status_cur : Literal["active", "idle", "locked"]
     quota_used : dict[str, int]# Sửa : Kiểm soát hàng loạt chứ không chỉ 1 web/app
     cur_policy_version : int
+    acked_commands : list[str] = [] #Danh sách lệnh Agent xác nhận đã nhận . 
     
     
 class HeartbeatResponse(BaseModel) :
     latest_policy_version : int
     pending_commands : list[str] = []
+    device_unlocked_until : int = 0 #Đồng bộ thời điểm hết hạn thiết bị từ Server
+    app_bonus_time : dict[str , int] = {} #Đồng bộ bonus time từng app độc lập với Policy gốc
+    web_bonus_time : dict[str , int] = {} #Đồng bộ bonus time từng web/domain độc lập với Policy gốc
+
+
+#Lệnh khẩn
+class CommandType(StrEnum) :
+    LOCK = "lock"
+    UNLOCK = "unlock"
+    ADD_TIME = "add_time"
+    SUB_TIME = "sub_time"
+
 
+class UrgentCmd(BaseModel) :
+    cmd_type : CommandType
+    target_type : TargetType = TargetType.DEVICE #Chọn tác động lên DEVICE, APP hoặc WEB
+    subject : str = "" #Tên process_name (khi APP) hoặc domain (khi WEB)
+    bonus_time : int = Field(default = 0 , ge = 0)#Time unit : Second
+    sub_time : int = Field(default = 0 , ge = 0)#Time unit : Second
 
 #Luật (gồm luật cho app , web - thông qua domain , policy (id , version) , lịch , hạn mức)
 class AppRule(BaseModel) :
     exe_name : str
     sha256 : str
-    allowed : bool
+    allowed : bool #False = bị cấm bởi Policy, True = được phép
+    quota : int = 0 #Quota gốc của riêng ứng dụng (giây, 0 = không giới hạn riêng)
 
 
 class DomainRule(BaseModel) :
     domain : str
     category : DomainCategory
-    allowed : bool
+    allowed : bool #False = bị cấm bởi Policy, True = được phép
+    quota : int = 0 #Quota gốc của riêng website/domain (giây, 0 = không giới hạn riêng)
 
 
 class Policy(BaseModel) :
diff --git a/tests/test_schemas.py b/tests/test_schemas.py
index c726cbf..f8ad16f 100644
--- a/tests/test_schemas.py
+++ b/tests/test_schemas.py
@@ -1,17 +1,347 @@
-"""Kiểm thử cơ sở cho lược đồ sự kiện (F3, NT2)."""
-from shared.schemas import EventRecord , EventType
+"""Kiểm thử cơ sở cho lược đồ sự kiện và cơ chế Quota (Device, App, Web, Restart, Mất kết nối)."""
+import json
+import os
+import time
+import uuid
+from unittest.mock import patch
+from fastapi import HTTPException , WebSocketDisconnect
+import pytest
+from shared.schemas import (
+    AppRule,
+    BlockReason,
+    CommandType,
+    DomainCategory,
+    DomainRule,
+    EnrollmentRequest,
+    EventRecord,
+    EventType,
+    HeartbeatRequest,
+    PairingCode,
+    Policy,
+    TargetType,
+    UrgentCmd,
+)
+import server
+import agent
 
 
-def test_event_record_schema():
+def runSyncCoro(coro) :
+    #Chạy coroutine không cần tạo ProactorEventLoop socket trên Windows
+    try :
+        coro.send(None)
+    except StopIteration as stop :
+        return stop.value
+    finally :
+        coro.close()
+
+
+def test_event_record_schema() :
     rec = EventRecord(
-        idempotency_key="550e8400-e29b-41d4-a716-446655440000",
-        ts=1730000000,
-        device_id="dev-01",
-        child_id="child-01",
-        type=EventType.DOMAIN_QUERY,
-        subject="example.edu.vn",
-        duration_sec=0,
-        policy_id="pol-v1",
+        idempotency_key = "550e8400-e29b-41d4-a716-446655440000" ,
+        ts = 1730000000 ,
+        device_id = "dev-01" ,
+        child_id = "child-01" ,
+        type = EventType.DOMAIN_QUERY ,
+        subject = "example.edu.vn" ,
+        duration_sec = 0 ,
+        policy_id = "pol-v1" ,
     )
     assert rec.type == EventType.DOMAIN_QUERY
     assert rec.subject == "example.edu.vn"
+
+
+def test_device_app_web_quota_and_block_reasons() :
+    #Khởi tạo Policy mẫu với App/Web bị cấm bởi Policy và App/Web có quota riêng
+    agent.cur_policy = Policy(
+        policy_id = "plcid_test" ,
+        policy_version = 1 ,
+        weekday_quota = 3600 ,
+        weekend_quota = 7200 ,
+        schedule_7x48 = [[True] * 48 for _ in range(7)] ,
+        app_rules = [
+            AppRule(exe_name = "banned.exe" , sha256 = "a" * 64 , allowed = False , quota = 0) ,
+            AppRule(exe_name = "roblox.exe" , sha256 = "b" * 64 , allowed = True , quota = 600) ,
+        ] ,
+        domain_rules = [
+            DomainRule(domain = "bad.example" , category = DomainCategory.INAPPROPRIATE , allowed = False , quota = 0) ,
+            DomainRule(domain = "youtube.com" , category = DomainCategory.ENTERTAINMENT , allowed = True , quota = 900) ,
+        ] ,
+        signature = "unsigned"
+    )
+    agent.quota_used = {"roblox.exe" : 600 , "youtube.com" : 900} #Cả app và web đều đã dùng hết quota gốc
+    agent.app_bonus_time = {}
+    agent.web_bonus_time = {}
+    agent.device_unlocked_until = int(time.time()) + 1800
+
+    with patch("agent.psutil.process_iter" , return_value = []) :
+        #1.Kiểm tra phân biệt nguyên nhân chặn: POLICY vs APP_QUOTA vs WEB_QUOTA
+        agent.applyPolicy()
+        assert agent.status_cur == "active" #Thiết bị vẫn mở khi chỉ hết App/Web Quota
+        assert agent.device_block_reason == BlockReason.NONE
+        assert agent.app_block_reasons["banned.exe"] == BlockReason.POLICY
+        assert agent.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
+        assert agent.domain_block_reasons["bad.example"] == BlockReason.POLICY
+        assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA
+        assert "youtube.com" in agent.blocked_domains
+
+        #2.ADD_TIME cho APP: chỉ mở lại roblox.exe, không ảnh hưởng youtube.com hay Policy gốc
+        agent.executeUrgentCmd(UrgentCmd(
+            cmd_type = CommandType.ADD_TIME ,
+            target_type = TargetType.APP ,
+            subject = "roblox.exe" ,
+            bonus_time = 300
+        ))
+        assert agent.cur_policy.app_rules[1].quota == 600 #Policy gốc giữ nguyên
+        assert agent.getAppRemainingQuota("roblox.exe") == 300
+        assert agent.app_block_reasons["roblox.exe"] == BlockReason.NONE
+        assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA #Web vẫn bị chặn
+
+        #3.ADD_TIME cho WEB: chỉ mở lại youtube.com, giữ nguyên Policy gốc
+        agent.executeUrgentCmd(UrgentCmd(
+            cmd_type = CommandType.ADD_TIME ,
+            target_type = TargetType.WEB ,
+            subject = "youtube.com" ,
+            bonus_time = 450
+        ))
+        assert agent.cur_policy.domain_rules[1].quota == 900 #Policy gốc giữ nguyên
+        assert agent.getWebRemainingQuota("youtube.com") == 450
+        assert agent.domain_block_reasons["youtube.com"] == BlockReason.NONE
+        assert "youtube.com" not in agent.blocked_domains
+
+        #4.Hết hạn Device-level quota (device_unlocked_until) -> khóa toàn bộ thiết bị
+        agent.device_unlocked_until = int(time.time()) - 10
+        agent.applyPolicy()
+        assert agent.status_cur == "locked"
+        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA
+
+        #5.ADD_TIME cho DEVICE -> cộng trực tiếp vào device_unlocked_until và mở lại thiết bị
+        agent.executeUrgentCmd(UrgentCmd(
+            cmd_type = CommandType.ADD_TIME ,
+            target_type = TargetType.DEVICE ,
+            bonus_time = 900
+        ))
+        assert agent.status_cur == "active"
+        assert agent.device_block_reason == BlockReason.NONE
+
+        #6.Ngoài khung giờ Schedule 7x48 -> khóa thiết bị với nguyên nhân SCHEDULE
+        agent.cur_policy.schedule_7x48 = [[False] * 48 for _ in range(7)]
+        agent.applyPolicy()
+        assert agent.status_cur == "locked"
+        assert agent.device_block_reason == BlockReason.SCHEDULE
+
+
+def test_agent_restart_and_disconnect_sync() :
+    now_ts = int(time.time())
+    server.curCode = PairingCode(
+        pairing_code = "12345678" ,
+        created_at = now_ts ,
+        expires_at = now_ts + 600
+    )
+
+    #1.Enroll thiết bị
+    enroll_data = server.responseEnroll(
+        EnrollmentRequest(pairing_code = "12345678" , device_fingerprint = "fp_test_01")
+    )
+    dev_id = enroll_data.device_id
+    acc_token = enroll_data.access_token
+    plc_id = enroll_data.policy_id
+
+    init_until = server.device_unlocked_store[dev_id]
+    parent_tok = uuid.uuid4().hex
+    os.environ["PARENT_TOKEN"] = parent_tok
+
+    #2.Giả lập mất kết nối WebSocket khi phụ huynh gửi ADD_TIME cho DEVICE, APP và WEB
+    res_dev = runSyncCoro(server.sendUrgentCmd(
+        dev_id ,
+        UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.DEVICE , bonus_time = 900) ,
+        parent_token = parent_tok
+    ))
+    assert res_dev["via"] == "heartbeat_sync"
+
+    runSyncCoro(server.sendUrgentCmd(
+        dev_id ,
+        UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.APP , subject = "roblox.exe" , bonus_time = 600) ,
+        parent_token = parent_tok
+    ))
+    runSyncCoro(server.sendUrgentCmd(
+        dev_id ,
+        UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.WEB , subject = "youtube.com" , bonus_time = 300) ,
+        parent_token = parent_tok
+    ))
+
+    #Kiểm tra Server đã lưu bền vững và không làm thay đổi Policy gốc
+    assert server.device_unlocked_store[dev_id] == init_until + 900
+    assert server.app_bonus_store[dev_id]["roblox.exe"] == 600
+    assert server.web_bonus_store[dev_id]["youtube.com"] == 300
+    assert server.policies_store[plc_id].weekday_quota == 5400
+
+    #3.Giả lập Agent restart (mất hết biến trong RAM) rồi gửi Heartbeat lên Server để khôi phục
+    agent.device_unlocked_until = 0
+    agent.app_bonus_time = {}
+    agent.web_bonus_time = {}
+    agent.cur_policy = server.policies_store[plc_id]
+    agent.cur_policy_version = 1
+
+    hb_data = server.responseHeartbeat(HeartbeatRequest(
+        device_id = dev_id ,
+        access_token = acc_token ,
+        policy_id = plc_id ,
+        status_cur = "active" ,
+        quota_used = {"roblox.exe" : 120 , "youtube.com" : 60} ,
+        cur_policy_version = 1 ,
+        acked_commands = []
+    ))
+
+    with patch("agent.psutil.process_iter" , return_value = []) :
+        agent.HeartbeatResponseHanlder(hb_data)
+
+    assert agent.device_unlocked_until == init_until + 900
+    assert agent.app_bonus_time["roblox.exe"] == 600
+    assert agent.web_bonus_time["youtube.com"] == 300
+
+    #Dọn file tạm sau khi kiểm thử
+    if server.QUOTA_STATE_FILE.exists() :
+        server.QUOTA_STATE_FILE.unlink()
+
+
+def test_urgent_auth_and_device_validation_s1() :
+    parent_tok = uuid.uuid4().hex
+    os.environ["PARENT_TOKEN"] = parent_tok
+    server.device_tokens["di_valid"] = "at_valid"
+    server.device_unlocked_store["di_valid"] = int(time.time()) + 1800
+    cmd = UrgentCmd(cmd_type = CommandType.LOCK)
+
+    #1.Từ chối khi thiếu hoặc sai parent_token (401)
+    with pytest.raises(HTTPException) as exc_unauth :
+        runSyncCoro(server.sendUrgentCmd("di_valid" , cmd , parent_token = "wrong_token"))
+    assert exc_unauth.value.status_code == 401
+
+    with pytest.raises(HTTPException) as exc_missing :
+        runSyncCoro(server.sendUrgentCmd("di_valid" , cmd))
+    assert exc_missing.value.status_code == 401
+
+    #2.Từ chối khi device_id không tồn tại trong device_tokens (404)
+    with pytest.raises(HTTPException) as exc_notfound :
+        runSyncCoro(server.sendUrgentCmd("di_nonexistent" , cmd , parent_token = parent_tok))
+    assert exc_notfound.value.status_code == 404
+    assert "di_nonexistent" not in server.pending_cmds_store
+
+    #3.Cho phép khi parent_token và device_id hợp lệ
+    res = runSyncCoro(server.sendUrgentCmd("di_valid" , cmd , parent_token = parent_tok))
+    assert res["device_id"] == "di_valid"
+    assert res["cmd_type"] == CommandType.LOCK
+
+
+def test_websocket_cleanup_and_reconnection_s2() :
+    parent_tok = uuid.uuid4().hex
+    os.environ["PARENT_TOKEN"] = parent_tok
+    dev_id = "di_ws_test"
+    acc_tok = "at_ws_test"
+    server.device_tokens[dev_id] = acc_tok
+
+    class DummyServerWS :
+        def __init__(self , events) :
+            self.events = list(events)
+            self.accepted = False
+            self.fail_send = False
+
+        async def accept(self) :
+            self.accepted = True
+
+        async def receive_json(self) :
+            ev = self.events.pop(0)
+            if isinstance(ev , Exception) :
+                raise ev
+            return ev
+
+        async def send_json(self , payload) :
+            if self.fail_send :
+                raise RuntimeError("Stale socket")
+
+    #1.Kiểm tra urgentWebsocketEndpoint dọn kết nối khi gặp lỗi bất kỳ (không riêng WebSocketDisconnect)
+    ws_old = DummyServerWS([RuntimeError("Unexpected JSON error")])
+    runSyncCoro(server.urgentWebsocketEndpoint(ws_old , dev_id , acc_tok))
+    assert dev_id not in server.active_ws_connections
+
+    #2.Kiểm tra kết nối cũ đóng muộn không xóa nhầm kết nối mới hơn của cùng device_id
+    ws_newer = DummyServerWS([])
+    class LateCleanupWS(DummyServerWS) :
+        async def receive_json(self) :
+            #Giả lập kết nối mới đã ghi đè vào active_ws_connections trước khi kết nối cũ thoát
+            server.active_ws_connections[dev_id] = ws_newer
+            raise WebSocketDisconnect()
+
+    ws_stale = LateCleanupWS([])
+    runSyncCoro(server.urgentWebsocketEndpoint(ws_stale , dev_id , acc_tok))
+    assert server.active_ws_connections.get(dev_id) is ws_newer
+
+    #3.Kiểm tra sendUrgentCmd tự dọn kết nối stale khi send_json lỗi và fallback sang heartbeat_sync
+    ws_newer.fail_send = True
+    res = runSyncCoro(server.sendUrgentCmd(
+        dev_id ,
+        UrgentCmd(cmd_type = CommandType.LOCK) ,
+        parent_token = parent_tok
+    ))
+    assert res["sent"] is False
+    assert res["via"] == "heartbeat_sync"
+    assert dev_id not in server.active_ws_connections
+
+    #4.Kiểm tra Agent UrgentCmdHandler tự kết nối lại với backoff, bỏ qua gói JSON lỗi và chặn chạy trùng
+    sleeps : list[float] = []
+    sent_acks : list[dict] = []
+    connect_calls = 0
+
+    class DummyClientWS :
+        def __init__(self , messages) :
+            self.messages = list(messages)
+
+        async def __aenter__(self) :
+            return self
+
+        async def __aexit__(self , exc_type , exc , tb) :
+            return False
+
+        async def recv(self) :
+            if not self.messages :
+                raise ConnectionError("Connection lost")
+            return self.messages.pop(0)
+
+        async def send(self , data : str) :
+            sent_acks.append(json.loads(data))
+
+    def fake_connect(url : str) :
+        nonlocal connect_calls
+        connect_calls += 1
+        if connect_calls <= 2 :
+            raise ConnectionError(f"Initial connection failed #{connect_calls}")
+        if connect_calls == 3 :
+            return DummyClientWS([
+                "not-valid-json" ,
+                json.dumps({"cmd_type" : "lock" , "target_type" : "device"})
+            ])
+        raise ConnectionError("Disconnected after work")
+
+    async def fake_sleep(delay : float) :
+        sleeps.append(delay)
+
+    agent.ws_handler_running = False
+    with patch("agent.websockets.connect" , side_effect = fake_connect) , patch("agent.asyncio.sleep" , side_effect = fake_sleep) :
+        runSyncCoro(agent.UrgentCmdHandler(max_retries = 2 , base_delay = 2.0 , max_delay = 5.0))
+
+    assert connect_calls == 5
+    assert sleeps == [2.0 , 4.0 , 2.0 , 4.0] #Tăng theo hàm mũ (2.0 -> 4.0), reset về 2.0 sau khi kết nối lần 3 thành công
+    assert len(sent_acks) == 1
+    assert sent_acks[0]["cmd_type"] == "lock"
+    assert agent.status_cur == "locked"
+    assert agent.ws_handler_running is False
+
+    #Kiểm tra chặn khởi chạy trùng khi ws_handler_running đang True
+    agent.ws_handler_running = True
+    try :
+        with patch("agent.websockets.connect" , side_effect = AssertionError("Should not connect")) :
+            runSyncCoro(agent.UrgentCmdHandler(max_retries = 0))
+    finally :
+        agent.ws_handler_running = False
+
+    if server.QUOTA_STATE_FILE.exists() :
+        server.QUOTA_STATE_FILE.unlink()
```

---

## PHẦN 4: SOURCE SNAPSHOT (ĐẦY ĐỦ NỘI DUNG CÁC FILE KÈM SỐ DÒNG)

> Tất cả các file dưới đây được trích xuất nguyên trạng 100% kèm số thứ tự dòng (`1: ...`) để Reviewer có thể đối chiếu trực tiếp với mọi số dòng (`line`) được nêu trong `REVIEW_SUMMARY.md`.

### 4.1. File: `shared/schemas.py` (155 dòng)
```python
1: #Giao thức và đối tượng chung . Tuân thủ NT (Obj = Ứng dụng/Website)
2: 
3: #Note : Ký hiệu chuẩn 
4: #ACK = Acknowledgment - Thông điệp xác nhận
5: #WMI = Windows Management Instrumentation - Quản trị windows
6: 
7: from enum import StrEnum
8: from typing import Literal
9: from pydantic import BaseModel, Field
10: 
11: 
12: class EventType(StrEnum) :
13:     #Phân loại sự kiện
14:     APP_START = "app_start"
15:     APP_STOP = "app_stop"
16:     DOMAIN_QUERY = "domain_query"
17:     BLOCKED_APP = "blocked_app"
18:     BLOCKED_DOMAIN = "blocked_domain"
19:     QUOTA_WARNING = "quota_warning"
20:     LOCKED = "locked"
21:     UNLOCK_REQUEST = "unlock_request"
22:     OVERRIDE_GRANTED = "override_granted" # Quyền ghi đè
23: 
24: 
25: class DomainCategory(StrEnum) :
26:     #Phân loại Obj
27:     EDUCATION = "education"
28:     ENTERTAINMENT = "entertainment"
29:     SOCIAL = "social"
30:     GAMING = "gaming"
31:     INAPPROPRIATE = "inappropriate"
32:     UNCATEGORIZED = "uncategorized"
33: 
34: 
35: class UserRole(StrEnum) :
36:     #User Role
37:     PARENT = "parent"
38:     CHILD_VIEW = "child-view"
39:     ADMIN = "admin"
40: 
41: 
42: class BlockReason(StrEnum) :
43:     #Phân biệt 5 nguyên nhân chặn
44:     NONE = "none"
45:     POLICY = "policy"             #Bị cấm trực tiếp trong Policy (allowed == False)
46:     SCHEDULE = "schedule"         #Ngoài khung giờ lịch tuần 7x48
47:     DEVICE_QUOTA = "device_quota" #Hết hạn thời gian toàn thiết bị (device_unlocked_until)
48:     APP_QUOTA = "app_quota"       #Hết quota của riêng ứng dụng
49:     WEB_QUOTA = "web_quota"       #Hết quota của riêng website/domain
50: 
51: 
52: class TargetType(StrEnum) :
53:     #3 phạm vi tác động của lệnh thời gian
54:     DEVICE = "device"
55:     APP = "app"
56:     WEB = "web"
57: 
58: 
59: class EventState(BaseModel) :
60:     #Event state
61:     ts: int = Field(... , description = "Unix thời gian (seconds)")
62:     device_id: str
63:     child_id: str
64:     type: EventType
65:     subject: str = Field(... , description = "Tên Obj")
66:     duration_sec: int = Field(default = 0 , ge = 0)
67:     policy_id: str
68:     idempotency_key: str = Field(... , description = "Chống trùng khi đồng bộ")
69: 
70: 
71: #Alias tương thích với test
72: EventRecord = EventState
73: 
74: 
75: #Agent gửi request , server xử lý và gửi trả response 
76: #Các class sau hỗ trợ giao tiếp 
77: 
78: class PairingCode(BaseModel) : #Bổ sung mã code hiện tại gồm : Mã ; Thời gian
79:     pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ký tự 8 ký tự")
80:     created_at : int
81:     expires_at : int
82:     #Sửa đổi : Biến đếm thời gian -> Cố định thời gian đầu/cuối
83: 
84: class EnrollmentRequest(BaseModel) :
85:     pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ký tự 8 ký tự")
86:     device_fingerprint : str 
87: 
88: 
89: class EnrollmentResponse(BaseModel) : 
90:     device_id : str
91:     access_token : str
92:     refresh_token : str
93:     policy_id : str #Thêm : Cho server biết cần truy cập policy nào cho device nào
94: 
95: 
96: class HeartbeatRequest(BaseModel) : 
97:     device_id : str
98:     access_token : str
99:     policy_id : str
100:     status_cur : Literal["active", "idle", "locked"]
101:     quota_used : dict[str, int]# Sửa : Kiểm soát hàng loạt chứ không chỉ 1 web/app
102:     cur_policy_version : int
103:     acked_commands : list[str] = [] #Danh sách lệnh Agent xác nhận đã nhận . 
104:     
105:     
106: class HeartbeatResponse(BaseModel) :
107:     latest_policy_version : int
108:     pending_commands : list[str] = []
109:     device_unlocked_until : int = 0 #Đồng bộ thời điểm hết hạn thiết bị từ Server
110:     app_bonus_time : dict[str , int] = {} #Đồng bộ bonus time từng app độc lập với Policy gốc
111:     web_bonus_time : dict[str , int] = {} #Đồng bộ bonus time từng web/domain độc lập với Policy gốc
112: 
113: 
114: #Lệnh khẩn
115: class CommandType(StrEnum) :
116:     LOCK = "lock"
117:     UNLOCK = "unlock"
118:     ADD_TIME = "add_time"
119:     SUB_TIME = "sub_time"
120: 
121: 
122: class UrgentCmd(BaseModel) :
123:     cmd_type : CommandType
124:     target_type : TargetType = TargetType.DEVICE #Chọn tác động lên DEVICE, APP hoặc WEB
125:     subject : str = "" #Tên process_name (khi APP) hoặc domain (khi WEB)
126:     bonus_time : int = Field(default = 0 , ge = 0)#Time unit : Second
127:     sub_time : int = Field(default = 0 , ge = 0)#Time unit : Second
128: 
129: #Luật (gồm luật cho app , web - thông qua domain , policy (id , version) , lịch , hạn mức)
130: class AppRule(BaseModel) :
131:     exe_name : str
132:     sha256 : str
133:     allowed : bool #False = bị cấm bởi Policy, True = được phép
134:     quota : int = 0 #Quota gốc của riêng ứng dụng (giây, 0 = không giới hạn riêng)
135: 
136: 
137: class DomainRule(BaseModel) :
138:     domain : str
139:     category : DomainCategory
140:     allowed : bool #False = bị cấm bởi Policy, True = được phép
141:     quota : int = 0 #Quota gốc của riêng website/domain (giây, 0 = không giới hạn riêng)
142: 
143: 
144: class Policy(BaseModel) :
145:     policy_id : str
146:     policy_version : int
147:     weekday_quota : int
148:     weekend_quota : int
149:     schedule_7x48 : list[list[bool]]
150:     app_rules : list[AppRule] = []
151:     domain_rules : list[DomainRule] = []
152:     signature : str
153: 
154: 
155: #Obj cho SQL 
```

---

### 4.2. File: `server/__init__.py` (289 dòng)
```python
1: #Server
2: 
3: from fastapi import FastAPI, HTTPException, Depends, Header, status
4: from fastapi import WebSocket, WebSocketDisconnect
5: from pydantic import BaseModel
6: from shared.schemas import (
7:     CommandType,
8:     EnrollmentRequest,
9:     EnrollmentResponse,
10:     HeartbeatRequest,
11:     HeartbeatResponse,
12:     PairingCode,
13:     Policy,
14:     TargetType,
15:     UrgentCmd,
16: )
17: from sqlalchemy import create_engine, String, ForeignKey
18: from sqlalchemy.orm import (
19:     DeclarativeBase,
20:     Mapped,
21:     mapped_column,
22:     sessionmaker,
23:     Session
24: )
25: import sqlite3
26: import httpx
27: import websockets
28: import os
29: import uuid
30: import json
31: import time
32: from pathlib import Path
33: from datetime import datetime, timezone
34: from enum import StrEnum
35: import win32com.client
36: import httpx
37: 
38: app = FastAPI()
39: 
40: curCode : PairingCode | None = None
41: 
42: #Bộ nhớ trên Server
43: device_tokens : dict[str , str] = {}
44: device_states : dict[str , dict] = {}
45: policies_store : dict[str , Policy] = {}
46: pending_cmds_store : dict[str , list[str]] = {}
47: active_ws_connections : dict[str , WebSocket] = {} #Quản lý kết nối WebSocket theo device_id
48: urgent_acks_store : dict[str , list[dict]] = {} #Lưu lịch sử ACK của lệnh khẩn từ Agent
49: 
50: #Quản lý thời điểm hết hạn thiết bị và bonus time từng app/web độc lập với Policy gốc
51: device_unlocked_store : dict[str , int] = {} #device_id -> device_unlocked_until (timestamp)
52: app_bonus_store : dict[str , dict[str , int]] = {} #device_id -> {process_name : bonus_sec}
53: web_bonus_store : dict[str , dict[str , int]] = {} #device_id -> {domain : bonus_sec}
54: QUOTA_STATE_FILE = Path("quota_state.json")
55: 
56: 
57: def saveQuotaState() :
58:     #Lưu bền vững trạng thái quota/bonus trên Server xuống file
59:     try :
60:         data = {
61:             "device_unlocked" : device_unlocked_store ,
62:             "app_bonus" : app_bonus_store ,
63:             "web_bonus" : web_bonus_store
64:         }
65:         QUOTA_STATE_FILE.write_text(json.dumps(data) , encoding = "utf-8")
66:     except Exception :
67:         pass
68: 
69: 
70: def loadQuotaState() :
71:     #Khôi phục trạng thái quota/bonus đã lưu bền vững trên Server
72:     global device_unlocked_store , app_bonus_store , web_bonus_store
73:     if QUOTA_STATE_FILE.exists() :
74:         try :
75:             data = json.loads(QUOTA_STATE_FILE.read_text(encoding = "utf-8"))
76:             device_unlocked_store = {k : int(v) for k , v in data.get("device_unlocked" , {}).items()}
77:             app_bonus_store = {
78:                 k : {ak : int(av) for ak , av in v.items()}
79:                 for k , v in data.get("app_bonus" , {}).items()
80:             }
81:             web_bonus_store = {
82:                 k : {wk : int(wv) for wk , wv in v.items()}
83:                 for k , v in data.get("web_bonus" , {}).items()
84:             }
85:         except Exception :
86:             pass
87: 
88: 
89: loadQuotaState()
90: 
91: 
92: @app.post("/api/v1/enroll" , response_model = EnrollmentResponse)
93: def responseEnroll(payload : EnrollmentRequest) :
94:     #Kiểm tra hạn và tính hợp lệ 
95:     if curCode is None or payload.pairing_code != curCode.pairing_code or time.time() > curCode.expires_at :
96:         raise HTTPException(
97:             status_code = status.HTTP_400_BAD_REQUEST,
98:             detail = "Ma ghep doi khong hop le hoac da het han",
99:         )
100:     
101:     uuid_device = payload.device_fingerprint
102:     dev_id = f"di_{uuid_device}"
103:     acc_token = f"at_{uuid_device}"
104:     plc_id = f"plcid_{uuid_device}"
105: 
106:     #Lưu token tương ứng cho thiết bị
107:     device_tokens[dev_id] = acc_token
108: 
109:     #Tạo Policy mặc định
110:     if plc_id not in policies_store :
111:         policies_store[plc_id] = Policy(
112:             policy_id = plc_id ,
113:             policy_version = 1 ,
114:             weekday_quota = 5400 ,
115:             weekend_quota = 7200 ,
116:             schedule_7x48 = [[True] * 48 for _ in range(7)] ,
117:             app_rules = [] ,
118:             domain_rules = [] ,
119:             signature = "unsigned"
120:         )
121: 
122:     #Khởi tạo device_unlocked_until, app_bonus_time và web_bonus_time độc lập với Policy gốc
123:     if dev_id not in device_unlocked_store :
124:         plc = policies_store[plc_id]
125:         base_quota = plc.weekend_quota if datetime.now().weekday() >= 5 else plc.weekday_quota
126:         device_unlocked_store[dev_id] = int(time.time()) + base_quota
127:     app_bonus_store.setdefault(dev_id , {})
128:     web_bonus_store.setdefault(dev_id , {})
129:     saveQuotaState()
130: 
131:     return EnrollmentResponse(
132:         device_id = dev_id,
133:         access_token = acc_token,
134:         refresh_token = f"rt_{uuid_device}",
135:         policy_id = plc_id
136:     )
137: 
138: 
139: @app.post("/api/v1/heartbeat" , response_model = HeartbeatResponse)
140: def responseHeartbeat(payload : HeartbeatRequest) :
141:     #1.Check device_id và access_token hợp lệ
142:     if device_tokens.get(payload.device_id) != payload.access_token :
143:         raise HTTPException(
144:             status_code = status.HTTP_401_UNAUTHORIZED,
145:             detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID",
146:         )
147: 
148:     #2.Ghi trạng thái và usage của Agent
149:     device_states[payload.device_id] = {
150:         "status_cur": payload.status_cur,
151:         "quota_used": payload.quota_used,
152:     }
153: 
154:     #3.Lấy policy tương ứng
155:     policy = policies_store.get(payload.policy_id)
156:     latest_ver = policy.policy_version if policy else payload.cur_policy_version
157: 
158:     #4.Xử lý xác nhận (ACK) và xuất vector lệnh chờ (không xóa ngay để tự retry nếu rớt mạng)
159:     #Bổ sung chống cơ chế Data Integrity cho vector <cmd>
160:     cur_cmds = pending_cmds_store.get(payload.device_id , []) #Lấy danh sách lệnh đang lưu của thiết bị
161:     if payload.acked_commands : #Nếu Agent gửi kèm danh sách lệnh đã nhận thành công
162:         cur_cmds = [c for c in cur_cmds if c not in payload.acked_commands] #Lọc bỏ các lệnh đã được Agent xác nhận
163:         pending_cmds_store[payload.device_id] = cur_cmds #Lưu lại phần lệnh chưa được xác nhận để gửi tiếp
164: 
165:     #5.Trả về kèm trạng thái device_unlocked_until, app_bonus_time, web_bonus_time để đồng bộ
166:     return HeartbeatResponse(
167:         latest_policy_version = latest_ver ,
168:         pending_commands = cur_cmds ,
169:         device_unlocked_until = device_unlocked_store.get(payload.device_id , 0) ,
170:         app_bonus_time = app_bonus_store.get(payload.device_id , {}) ,
171:         web_bonus_time = web_bonus_store.get(payload.device_id , {})
172:     )
173: 
174: 
175: @app.get("/api/v1/policy" , response_model = Policy)
176: def responsePolicy(device_id : str , access_token : str , policy_id : str) :
177:     #1.Check device_id và access_token
178:     if device_tokens.get(device_id) != access_token :
179:         raise HTTPException(
180:             status_code = status.HTTP_401_UNAUTHORIZED ,
181:             detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID" ,
182:         )
183: 
184:     #2.Lấy policy
185:     policy = policies_store.get(policy_id)
186:     if policy is None :
187:         raise HTTPException(
188:             status_code = status.HTTP_404_NOT_FOUND ,
189:             detail = "Khong tim thay Policy" ,
190:         )
191: 
192:     return policy
193: 
194: 
195: #WebSocket kênh lệnh khẩn
196: @app.websocket("/ws/urgent")
197: async def urgentWebsocketEndpoint(websocket : WebSocket , device_id : str , access_token : str) :
198:     #1.Xác thực Agent bằng device_id và access_token
199:     if device_tokens.get(device_id) != access_token :
200:         await websocket.close(code = status.WS_1008_POLICY_VIOLATION)
201:         return
202: 
203:     #2.Chấp nhận kết nối và lưu theo device_id
204:     await websocket.accept()
205:     active_ws_connections[device_id] = websocket
206: 
207:     #3.Lắng nghe ACK trả về từ Agent và luôn dọn kết nối an toàn trong finally
208:     try :
209:         while True :
210:             ack_data = await websocket.receive_json() #Nhận gói ACK từ Agent
211:             if isinstance(ack_data , dict) :
212:                 urgent_acks_store.setdefault(device_id , []).append(ack_data) #Ghi nhận kết quả ACK
213:                 if "status_cur" in ack_data and device_id in device_states :
214:                     device_states[device_id]["status_cur"] = ack_data["status_cur"] #Đồng bộ ngay trạng thái mới
215:     except WebSocketDisconnect :
216:         pass
217:     except Exception as e :
218:         print(f"Loi WebSocket urgent ({device_id}) : {e}")
219:     finally :
220:         #Chỉ xóa nếu kết nối đang lưu đúng là kết nối hiện tại (không xóa nhầm kết nối mới hơn của cùng device_id)
221:         if active_ws_connections.get(device_id) is websocket :
222:             active_ws_connections.pop(device_id , None)
223: 
224: 
225: @app.post("/api/v1/urgent")
226: async def sendUrgentCmd(
227:     device_id : str ,
228:     cmd : UrgentCmd ,
229:     parent_token : str | None = Header(default = None , alias = "X-Parent-Token")
230: ) :
231:     #0.Xác thực quyền Parent/Admin qua biến môi trường PARENT_TOKEN và kiểm tra device_id đã đăng ký
232:     expected_token = os.environ.get("PARENT_TOKEN")
233:     if not expected_token or not isinstance(parent_token , str) or parent_token != expected_token :
234:         raise HTTPException(
235:             status_code = status.HTTP_401_UNAUTHORIZED ,
236:             detail = "Khong co quyen thuc thi lenh khan" ,
237:         )
238:     if device_id not in device_tokens :
239:         raise HTTPException(
240:             status_code = status.HTTP_404_NOT_FOUND ,
241:             detail = "Thiet bi khong ton tai" ,
242:         )
243: 
244:     #1.Cập nhật bonus/hạn mức cho DEVICE, APP hoặc WEB độc lập với Policy gốc và lưu bền vững
245:     if cmd.cmd_type == CommandType.ADD_TIME :
246:         if cmd.target_type == TargetType.DEVICE :
247:             cur_until = device_unlocked_store.get(device_id , int(time.time()))
248:             device_unlocked_store[device_id] = cur_until + cmd.bonus_time
249:         elif cmd.target_type == TargetType.APP and cmd.subject :
250:             app_name = cmd.subject.lower().strip()
251:             dev_bonus = app_bonus_store.setdefault(device_id , {})
252:             dev_bonus[app_name] = dev_bonus.get(app_name , 0) + cmd.bonus_time
253:         elif cmd.target_type == TargetType.WEB and cmd.subject :
254:             domain_name = cmd.subject.lower().strip()
255:             dev_web_bonus = web_bonus_store.setdefault(device_id , {})
256:             dev_web_bonus[domain_name] = dev_web_bonus.get(domain_name , 0) + cmd.bonus_time
257:         saveQuotaState()
258: 
259:     elif cmd.cmd_type == CommandType.SUB_TIME :
260:         if cmd.target_type == TargetType.DEVICE :
261:             cur_until = device_unlocked_store.get(device_id , int(time.time()))
262:             device_unlocked_store[device_id] = max(0 , cur_until - cmd.sub_time)
263:         elif cmd.target_type == TargetType.APP and cmd.subject :
264:             app_name = cmd.subject.lower().strip()
265:             dev_bonus = app_bonus_store.setdefault(device_id , {})
266:             dev_bonus[app_name] = max(0 , dev_bonus.get(app_name , 0) - cmd.sub_time)
267:         elif cmd.target_type == TargetType.WEB and cmd.subject :
268:             domain_name = cmd.subject.lower().strip()
269:             dev_web_bonus = web_bonus_store.setdefault(device_id , {})
270:             dev_web_bonus[domain_name] = max(0 , dev_web_bonus.get(domain_name , 0) - cmd.sub_time)
271:         saveQuotaState()
272: 
273:     #2.Nếu Agent đang mở WebSocket thì đẩy lệnh khẩn ngay; nếu kết nối stale/lỗi thì dọn dẹp và chuyển sang heartbeat_sync
274:     ws = active_ws_connections.get(device_id)
275:     if ws is not None :
276:         try :
277:             await ws.send_json(cmd.model_dump())
278:             return {"sent" : True , "via" : "websocket" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
279:         except Exception as e :
280:             print(f"Loi gui WebSocket urgent ({device_id}) : {e}")
281:             if active_ws_connections.get(device_id) is ws :
282:                 active_ws_connections.pop(device_id , None)
283: 
284:     #3.Nếu mất kết nối WebSocket: lưu lệnh LOCK/UNLOCK vào hàng chờ Heartbeat (quota đã lưu ở bước 1)
285:     if cmd.cmd_type in (CommandType.LOCK , CommandType.UNLOCK) :
286:         cmd_id = f"{int(time.time())}:{cmd.cmd_type}"
287:         pending_cmds_store.setdefault(device_id , []).append(cmd_id)
288: 
289:     return {"sent" : False , "via" : "heartbeat_sync" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
```

---

### 4.3. File: `agent/__init__.py` (397 dòng)
```python
1: #Agent máy trẻ
2: 
3: from fastapi import FastAPI, HTTPException, Depends
4: from fastapi import WebSocket, WebSocketDisconnect
5: from pydantic import BaseModel
6: from shared.schemas import (
7:     BlockReason,
8:     CommandType,
9:     HeartbeatResponse,
10:     Policy,
11:     TargetType,
12:     UrgentCmd,
13: )
14: from sqlalchemy import create_engine, String, ForeignKey
15: from sqlalchemy.orm import (
16:     DeclarativeBase,
17:     Mapped,
18:     mapped_column,
19:     sessionmaker,
20:     Session
21: )
22: import sqlite3
23: import asyncio
24: import httpx
25: import websockets
26: import os
27: import uuid
28: import json
29: import time
30: from pathlib import Path
31: from datetime import datetime, timezone
32: from enum import StrEnum
33: import win32com.client
34: import hashlib
35: import psutil
36: 
37: SERVER_URL = "http://192.168.1.10:8000"
38: DEFAULT_DEVICE_FINGERPRINT = "0000-0000-0000-0000-000000000000"
39: 
40: # device fingerprint = UUID = Id trên chip BIOS/UEFI
41: def getMachineGuid() -> str :
42:     try :
43:         #Connect WMI
44:         wmi = win32com.client.GetObject("winmgmts:")
45:         #Yêu cầu lấy mỗi UUID từ class Win32_ComputerSystemProduct 
46:         result = wmi.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")
47:         return next(iter(result)).UUID;
48:     except Exception :
49:         return DEFAULT_DEVICE_FINGERPRINT
50: cdId = getMachineGuid() #current_deviced_fingerprint
51: 
52: 
53: def getPairingCode(prompt : str = "Ma ghep enroll: " , max_attempts : int = 5) -> str :
54:     for __ in range(max_attempts) :
55:         code = input(prompt).strip()
56:         if len(code) == 8 :
57:             return code
58:         print("Ma ghep phai dung 8 ky tu")
59:     raise ValueError("Nhap ma ghep that bai")
60: 
61: device_id = None
62: access_token = None
63: refresh_token = None
64: policy_id = None
65: 
66: ENROLL_URL = f"{SERVER_URL}/api/v1/enroll"
67: 
68: def requestEnroll() :
69:     #Gửi dữ liệu bằng http method post 
70:     code = getPairingCode()
71:     response =  httpx.post(
72:         ENROLL_URL , 
73:         json = {
74:             "pairing_code" : code ,
75:             "device_fingerprint" :  cdId 
76:         }   
77:     )
78: 
79:     #Nếu gặp lỗi
80:     response.raise_for_status()
81: 
82:     #Nếu thành công
83:     global device_id, access_token, refresh_token, policy_id
84:     if response.status_code == 200 :
85:         data = response.json()   
86:         device_id = data["device_id"]
87:         access_token = data["access_token"]
88:         refresh_token = data["refresh_token"]
89:         policy_id = data["policy_id"]
90: 
91: 
92: #Kiểm tra kết nối với server
93: def checkServerConnection() -> bool :
94:     try:
95:         httpx.get(f"{SERVER_URL}/health", timeout = 3.6)
96:         return True
97:     except httpx.RequestError :
98:         return False
99: 
100: HEARTBEAT_URL = f"{SERVER_URL}/api/v1/heartbeat"
101: POLICY_URL = f"{SERVER_URL}/api/v1/policy"
102: 
103: status_cur = "active"
104: quota_used : dict[str , int] = {} #Thời gian đã dùng của từng process_name / domain
105: device_unlocked_until : int = 0 #Thời điểm hết hạn dùng toàn thiết bị (Device-level quota)
106: app_bonus_time : dict[str , int] = {} #Bonus time riêng từng ứng dụng (độc lập với Policy gốc)
107: web_bonus_time : dict[str , int] = {} #Bonus time riêng từng website/domain (độc lập với Policy gốc)
108: 
109: device_block_reason : BlockReason = BlockReason.NONE #Nguyên nhân khóa toàn thiết bị
110: app_block_reasons : dict[str , BlockReason] = {} #Nguyên nhân chặn của từng ứng dụng
111: domain_block_reasons : dict[str , BlockReason] = {} #Nguyên nhân chặn của từng website/domain
112: 
113: cur_policy_version = 0
114: cur_policy : Policy | None = None
115: blocked_domains : set[str] = set()
116: acked_commands : list[str] = [] #Danh sách lệnh chờ báo xác nhận (ACK) về Server
117: executed_cmds : set[str] = set() #Tập hợp lưu các lệnh đã chạy để chống thực thi trùng
118: 
119: 
120: def getAppRemainingQuota(process_name : str) -> int :
121:     #Tính quota còn lại của ứng dụng = quota gốc + bonus time - usage
122:     if cur_policy is None :
123:         return 0
124:     a_name = process_name.lower().strip()
125:     for r in cur_policy.app_rules :
126:         if r.exe_name.lower() == a_name :
127:             bonus = app_bonus_time.get(a_name , 0)
128:             used = quota_used.get(a_name , 0)
129:             return r.quota + bonus - used
130:     return 0
131: 
132: 
133: def getWebRemainingQuota(domain : str) -> int :
134:     #Tính quota còn lại của website = quota gốc + bonus time - usage
135:     if cur_policy is None :
136:         return 0
137:     d_name = domain.lower().strip()
138:     for r in cur_policy.domain_rules :
139:         if r.domain.lower() == d_name :
140:             bonus = web_bonus_time.get(d_name , 0)
141:             used = quota_used.get(d_name , 0)
142:             return r.quota + bonus - used
143:     return 0
144: 
145: 
146: def applyPolicy() :
147:     global status_cur , blocked_domains , device_unlocked_until
148:     global device_block_reason , app_block_reasons , domain_block_reasons
149:     if cur_policy is None :
150:         return
151: 
152:     #1.Kiểm tra Web-level quota: phân biệt chặn do Policy hay hết Web Quota
153:     blocked_domains = set()
154:     for r in cur_policy.domain_rules :
155:         d_name = r.domain.lower()
156:         if not r.allowed :
157:             domain_block_reasons[d_name] = BlockReason.POLICY #Bị cấm trực tiếp trong Policy
158:             blocked_domains.add(d_name)
159:         elif r.quota > 0 :
160:             remaining = r.quota + web_bonus_time.get(d_name , 0) - quota_used.get(d_name , 0)
161:             if remaining <= 0 :
162:                 domain_block_reasons[d_name] = BlockReason.WEB_QUOTA #Hết quota riêng của website
163:                 blocked_domains.add(d_name)
164:             else :
165:                 domain_block_reasons[d_name] = BlockReason.NONE
166:         else :
167:             domain_block_reasons[d_name] = BlockReason.NONE
168: 
169:     #2.Kiểm tra App-level quota (theo process name): phân biệt chặn do Policy hay hết App Quota
170:     blocked_names = set()
171:     for r in cur_policy.app_rules :
172:         a_name = r.exe_name.lower()
173:         if not r.allowed :
174:             app_block_reasons[a_name] = BlockReason.POLICY #Bị cấm trực tiếp trong Policy
175:             blocked_names.add(a_name)
176:         elif r.quota > 0 :
177:             remaining = r.quota + app_bonus_time.get(a_name , 0) - quota_used.get(a_name , 0)
178:             if remaining <= 0 :
179:                 app_block_reasons[a_name] = BlockReason.APP_QUOTA #Hết quota riêng của ứng dụng
180:                 blocked_names.add(a_name)
181:             else :
182:                 app_block_reasons[a_name] = BlockReason.NONE
183:         else :
184:             app_block_reasons[a_name] = BlockReason.NONE
185: 
186:     #Chỉ chặn ứng dụng vi phạm (không khóa toàn thiết bị khi chỉ hết App Quota)
187:     if blocked_names :
188:         for proc in psutil.process_iter(["name"]) :
189:             try :
190:                 p_name = (proc.info["name"] or "").lower()
191:                 if p_name in blocked_names :
192:                     proc.kill()
193:             except Exception :
194:                 continue
195: 
196:     #3.Kiểm tra Schedule (7x48) và Device-level quota (device_unlocked_until)
197:     now_dt = datetime.now() #Lấy giờ hệ thống hiện tại
198:     day_idx = now_dt.weekday() #Thứ trong tuần: 0(Thứ 2)->4(Thứ 6), 5(Thứ 7), 6(CN)
199:     slot_idx = now_dt.hour * 2 + (now_dt.minute // 30) #Khung 30p thứ mấy trong 48 khung (0->47)
200:     limit_sec = cur_policy.weekend_quota if day_idx >= 5 else cur_policy.weekday_quota #Quota thiết bị gốc từ Policy
201: 
202:     #Khởi tạo device_unlocked_until lần đầu nếu chưa được đặt
203:     if device_unlocked_until == 0 :
204:         device_unlocked_until = int(time.time()) + limit_sec
205: 
206:     if not cur_policy.schedule_7x48[day_idx][slot_idx] : #Ngoài khung giờ lịch tuần
207:         status_cur = "locked"
208:         device_block_reason = BlockReason.SCHEDULE
209:     elif time.time() >= device_unlocked_until : #Hết hạn thời gian toàn thiết bị
210:         status_cur = "locked"
211:         device_block_reason = BlockReason.DEVICE_QUOTA
212:     else :
213:         status_cur = "active"
214:         device_block_reason = BlockReason.NONE
215: 
216: 
217: def requestPolicy() :
218:     response = httpx.get(
219:         POLICY_URL ,
220:         params = {
221:             "device_id" : device_id ,
222:             "access_token" : access_token ,
223:             "policy_id" : policy_id
224:         } ,
225:         timeout = 3.6
226:     )
227:     response.raise_for_status()
228:     return Policy(**response.json())
229: 
230: 
231: def requestHeartbeat() :
232:     response = httpx.post(
233:         HEARTBEAT_URL , 
234:         json = {
235:             "device_id" : device_id ,
236:             "access_token" : access_token ,
237:             "policy_id" : policy_id ,
238:             "status_cur" : status_cur ,
239:             "quota_used" : quota_used ,
240:             "cur_policy_version" : cur_policy_version ,
241:             "acked_commands" : acked_commands #Gửi danh sách lệnh đã nhận để Server xóa khỏi hàng chờ
242:         } ,
243:         timeout = 3.6
244:     )
245:     
246:     response.raise_for_status() #Nếu mất mạng/lỗi sẽ dừng tại đây, acked_commands vẫn còn để nhịp sau retry
247:     acked_commands.clear() #Gửi thành công lên Server thì làm trống danh sách chờ xác nhận
248:     return HeartbeatResponse(**response.json())
249: 
250: def HeartbeatResponseHanlder(data : HeartbeatResponse) :
251:     global cur_policy , cur_policy_version , status_cur , device_unlocked_until
252:     global app_bonus_time , web_bonus_time , device_block_reason
253:     #1.Đồng bộ trạng thái quota/bonus từ Server (hỗ trợ khôi phục khi Agent restart hoặc rớt WebSocket)
254:     if data.device_unlocked_until > 0 :
255:         device_unlocked_until = data.device_unlocked_until
256:     if data.app_bonus_time :
257:         app_bonus_time = dict(data.app_bonus_time)
258:     if data.web_bonus_time :
259:         web_bonus_time = dict(data.web_bonus_time)
260: 
261:     #2.Cập nhật Policy mới nếu lệch version (không ghi đè bonus time)
262:     if data.latest_policy_version > cur_policy_version :
263:         cur_policy = requestPolicy()
264:         cur_policy_version = cur_policy.policy_version
265: 
266:     if cur_policy is not None :
267:         applyPolicy()
268: 
269:     #3.Xử lý lệnh chờ (lưu ACK, retry khi lỗi và chống thực thi trùng)
270:     for cmd in data.pending_commands :
271:         if cmd not in executed_cmds : #Kiểm tra biến chống trùng: chỉ chạy nếu lệnh này chưa từng chạy
272:             if cmd == "lock" or cmd.endswith(":lock") :
273:                 status_cur = "locked"
274:                 device_block_reason = BlockReason.POLICY
275:             elif cmd == "unlock" or cmd.endswith(":unlock") :
276:                 status_cur = "active"
277:                 device_block_reason = BlockReason.NONE
278:             executed_cmds.add(cmd) #Ghi vào biến chống trùng để nếu Server gửi lại cũng không chạy lần 2
279: 
280:         if cmd not in acked_commands : #Đưa lệnh vào danh sách chờ báo xác nhận (ACK) ở nhịp Heartbeat sau
281:             acked_commands.append(cmd)
282: 
283: 
284: def requestHeartbeatLoop(interval : int = 60) : #Tránh magic number :! Chisikudo advice
285:     while True :
286:         try :
287:             if checkServerConnection() :
288:                 response = requestHeartbeat()
289:                 HeartbeatResponseHanlder(response)
290:         except Exception as e :
291:             print(f"Loi : {e}")
292:         time.sleep(interval)
293: 
294: 
295: #Thực thi lệnh khẩn (tách riêng khỏi logic nhận WebSocket)
296: def executeUrgentCmd(cmd : UrgentCmd) :
297:     global status_cur , device_unlocked_until , app_bonus_time , web_bonus_time , device_block_reason
298:     #1.Khóa toàn bộ thiết bị ngay
299:     if cmd.cmd_type == CommandType.LOCK :
300:         status_cur = "locked"
301:         device_block_reason = BlockReason.POLICY
302:         return
303:     #2.Mở khóa thiết bị
304:     elif cmd.cmd_type == CommandType.UNLOCK :
305:         status_cur = "active"
306:         device_block_reason = BlockReason.NONE
307:         return
308: 
309:     #3.Cộng thêm thời gian (ADD_TIME) cho DEVICE, APP hoặc WEB độc lập với Policy gốc
310:     if cmd.cmd_type == CommandType.ADD_TIME :
311:         if cmd.target_type == TargetType.DEVICE :
312:             if device_unlocked_until == 0 :
313:                 device_unlocked_until = int(time.time())
314:             device_unlocked_until += cmd.bonus_time
315:         elif cmd.target_type == TargetType.APP and cmd.subject :
316:             a_name = cmd.subject.lower().strip()
317:             app_bonus_time[a_name] = app_bonus_time.get(a_name , 0) + cmd.bonus_time
318:         elif cmd.target_type == TargetType.WEB and cmd.subject :
319:             d_name = cmd.subject.lower().strip()
320:             web_bonus_time[d_name] = web_bonus_time.get(d_name , 0) + cmd.bonus_time
321:         applyPolicy()
322: 
323:     #4.Trừ bớt thời gian (SUB_TIME) của DEVICE, APP hoặc WEB độc lập với Policy gốc
324:     elif cmd.cmd_type == CommandType.SUB_TIME :
325:         if cmd.target_type == TargetType.DEVICE :
326:             device_unlocked_until = max(0 , device_unlocked_until - cmd.sub_time)
327:         elif cmd.target_type == TargetType.APP and cmd.subject :
328:             a_name = cmd.subject.lower().strip()
329:             app_bonus_time[a_name] = max(0 , app_bonus_time.get(a_name , 0) - cmd.sub_time)
330:         elif cmd.target_type == TargetType.WEB and cmd.subject :
331:             d_name = cmd.subject.lower().strip()
332:             web_bonus_time[d_name] = max(0 , web_bonus_time.get(d_name , 0) - cmd.sub_time)
333:         applyPolicy()
334: 
335: 
336: #Nhận lệnh khẩn qua WebSocket và gửi ACK (có chống chạy trùng, tự kết nối lại với exponential backoff và dừng an toàn)
337: WS_URGENT_URL = SERVER_URL.replace("http" , "ws") + "/ws/urgent"
338: ws_handler_running : bool = False
339: 
340: async def UrgentCmdHandler(
341:     stop_event : asyncio.Event | None = None ,
342:     max_retries : int | None = None ,
343:     base_delay : float = 1.0 ,
344:     max_delay : float = 30.0
345: ) :
346:     global ws_handler_running
347:     #Ngăn chặn khởi chạy trùng nhiều UrgentCmdHandler cùng lúc
348:     if ws_handler_running :
349:         print("UrgentCmdHandler dang chay, bo qua khoi tao trung")
350:         return
351: 
352:     ws_handler_running = True
353:     attempt = 0
354:     try :
355:         while stop_event is None or not stop_event.is_set() :
356:             ws_url = f"{WS_URGENT_URL}?device_id={device_id}&access_token={access_token}"
357:             try :
358:                 #1.Thiết lập kết nối WebSocket với Server
359:                 async with websockets.connect(ws_url) as websocket :
360:                     attempt = 0 #Reset bộ đếm retry khi đã kết nối thành công
361:                     while stop_event is None or not stop_event.is_set() :
362:                         #2.Nhận gói tin, parse JSON và validate bằng UrgentCmd
363:                         data = await websocket.recv()
364:                         try :
365:                             cmd = UrgentCmd(**json.loads(data))
366:                         except Exception as parse_err :
367:                             print(f"Loi goi tin UrgentCmd : {parse_err}")
368:                             continue
369: 
370:                         #3.Gọi hàm thực thi riêng
371:                         executeUrgentCmd(cmd)
372: 
373:                         #4.Gửi ACK báo kết quả thực thi về Server
374:                         ack_payload = {
375:                             "status" : "ack" ,
376:                             "cmd_type" : cmd.cmd_type ,
377:                             "target_type" : cmd.target_type ,
378:                             "subject" : cmd.subject ,
379:                             "status_cur" : status_cur ,
380:                             "device_unlocked_until" : device_unlocked_until ,
381:                             "app_bonus_time" : app_bonus_time ,
382:                             "web_bonus_time" : web_bonus_time
383:                         }
384:                         await websocket.send(json.dumps(ack_payload))
385:             except asyncio.CancelledError :
386:                 raise
387:             except Exception as conn_err :
388:                 attempt += 1
389:                 print(f"Loi ket noi WebSocket urgent (lan {attempt}) : {conn_err}")
390:                 if max_retries is not None and attempt > max_retries :
391:                     break
392:                 if stop_event is not None and stop_event.is_set() :
393:                     break
394:                 delay = min(max_delay , base_delay * (2 ** (attempt - 1)))
395:                 await asyncio.sleep(delay)
396:     finally :
397:         ws_handler_running = False
```

---

### 4.4. File: `tests/test_schemas.py` (347 dòng)
```python
1: """Kiểm thử cơ sở cho lược đồ sự kiện và cơ chế Quota (Device, App, Web, Restart, Mất kết nối)."""
2: import json
3: import os
4: import time
5: import uuid
6: from unittest.mock import patch
7: from fastapi import HTTPException , WebSocketDisconnect
8: import pytest
9: from shared.schemas import (
10:     AppRule,
11:     BlockReason,
12:     CommandType,
13:     DomainCategory,
14:     DomainRule,
15:     EnrollmentRequest,
16:     EventRecord,
17:     EventType,
18:     HeartbeatRequest,
19:     PairingCode,
20:     Policy,
21:     TargetType,
22:     UrgentCmd,
23: )
24: import server
25: import agent
26: 
27: 
28: def runSyncCoro(coro) :
29:     #Chạy coroutine không cần tạo ProactorEventLoop socket trên Windows
30:     try :
31:         coro.send(None)
32:     except StopIteration as stop :
33:         return stop.value
34:     finally :
35:         coro.close()
36: 
37: 
38: def test_event_record_schema() :
39:     rec = EventRecord(
40:         idempotency_key = "550e8400-e29b-41d4-a716-446655440000" ,
41:         ts = 1730000000 ,
42:         device_id = "dev-01" ,
43:         child_id = "child-01" ,
44:         type = EventType.DOMAIN_QUERY ,
45:         subject = "example.edu.vn" ,
46:         duration_sec = 0 ,
47:         policy_id = "pol-v1" ,
48:     )
49:     assert rec.type == EventType.DOMAIN_QUERY
50:     assert rec.subject == "example.edu.vn"
51: 
52: 
53: def test_device_app_web_quota_and_block_reasons() :
54:     #Khởi tạo Policy mẫu với App/Web bị cấm bởi Policy và App/Web có quota riêng
55:     agent.cur_policy = Policy(
56:         policy_id = "plcid_test" ,
57:         policy_version = 1 ,
58:         weekday_quota = 3600 ,
59:         weekend_quota = 7200 ,
60:         schedule_7x48 = [[True] * 48 for _ in range(7)] ,
61:         app_rules = [
62:             AppRule(exe_name = "banned.exe" , sha256 = "a" * 64 , allowed = False , quota = 0) ,
63:             AppRule(exe_name = "roblox.exe" , sha256 = "b" * 64 , allowed = True , quota = 600) ,
64:         ] ,
65:         domain_rules = [
66:             DomainRule(domain = "bad.example" , category = DomainCategory.INAPPROPRIATE , allowed = False , quota = 0) ,
67:             DomainRule(domain = "youtube.com" , category = DomainCategory.ENTERTAINMENT , allowed = True , quota = 900) ,
68:         ] ,
69:         signature = "unsigned"
70:     )
71:     agent.quota_used = {"roblox.exe" : 600 , "youtube.com" : 900} #Cả app và web đều đã dùng hết quota gốc
72:     agent.app_bonus_time = {}
73:     agent.web_bonus_time = {}
74:     agent.device_unlocked_until = int(time.time()) + 1800
75: 
76:     with patch("agent.psutil.process_iter" , return_value = []) :
77:         #1.Kiểm tra phân biệt nguyên nhân chặn: POLICY vs APP_QUOTA vs WEB_QUOTA
78:         agent.applyPolicy()
79:         assert agent.status_cur == "active" #Thiết bị vẫn mở khi chỉ hết App/Web Quota
80:         assert agent.device_block_reason == BlockReason.NONE
81:         assert agent.app_block_reasons["banned.exe"] == BlockReason.POLICY
82:         assert agent.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
83:         assert agent.domain_block_reasons["bad.example"] == BlockReason.POLICY
84:         assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA
85:         assert "youtube.com" in agent.blocked_domains
86: 
87:         #2.ADD_TIME cho APP: chỉ mở lại roblox.exe, không ảnh hưởng youtube.com hay Policy gốc
88:         agent.executeUrgentCmd(UrgentCmd(
89:             cmd_type = CommandType.ADD_TIME ,
90:             target_type = TargetType.APP ,
91:             subject = "roblox.exe" ,
92:             bonus_time = 300
93:         ))
94:         assert agent.cur_policy.app_rules[1].quota == 600 #Policy gốc giữ nguyên
95:         assert agent.getAppRemainingQuota("roblox.exe") == 300
96:         assert agent.app_block_reasons["roblox.exe"] == BlockReason.NONE
97:         assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA #Web vẫn bị chặn
98: 
99:         #3.ADD_TIME cho WEB: chỉ mở lại youtube.com, giữ nguyên Policy gốc
100:         agent.executeUrgentCmd(UrgentCmd(
101:             cmd_type = CommandType.ADD_TIME ,
102:             target_type = TargetType.WEB ,
103:             subject = "youtube.com" ,
104:             bonus_time = 450
105:         ))
106:         assert agent.cur_policy.domain_rules[1].quota == 900 #Policy gốc giữ nguyên
107:         assert agent.getWebRemainingQuota("youtube.com") == 450
108:         assert agent.domain_block_reasons["youtube.com"] == BlockReason.NONE
109:         assert "youtube.com" not in agent.blocked_domains
110: 
111:         #4.Hết hạn Device-level quota (device_unlocked_until) -> khóa toàn bộ thiết bị
112:         agent.device_unlocked_until = int(time.time()) - 10
113:         agent.applyPolicy()
114:         assert agent.status_cur == "locked"
115:         assert agent.device_block_reason == BlockReason.DEVICE_QUOTA
116: 
117:         #5.ADD_TIME cho DEVICE -> cộng trực tiếp vào device_unlocked_until và mở lại thiết bị
118:         agent.executeUrgentCmd(UrgentCmd(
119:             cmd_type = CommandType.ADD_TIME ,
120:             target_type = TargetType.DEVICE ,
121:             bonus_time = 900
122:         ))
123:         assert agent.status_cur == "active"
124:         assert agent.device_block_reason == BlockReason.NONE
125: 
126:         #6.Ngoài khung giờ Schedule 7x48 -> khóa thiết bị với nguyên nhân SCHEDULE
127:         agent.cur_policy.schedule_7x48 = [[False] * 48 for _ in range(7)]
128:         agent.applyPolicy()
129:         assert agent.status_cur == "locked"
130:         assert agent.device_block_reason == BlockReason.SCHEDULE
131: 
132: 
133: def test_agent_restart_and_disconnect_sync() :
134:     now_ts = int(time.time())
135:     server.curCode = PairingCode(
136:         pairing_code = "12345678" ,
137:         created_at = now_ts ,
138:         expires_at = now_ts + 600
139:     )
140: 
141:     #1.Enroll thiết bị
142:     enroll_data = server.responseEnroll(
143:         EnrollmentRequest(pairing_code = "12345678" , device_fingerprint = "fp_test_01")
144:     )
145:     dev_id = enroll_data.device_id
146:     acc_token = enroll_data.access_token
147:     plc_id = enroll_data.policy_id
148: 
149:     init_until = server.device_unlocked_store[dev_id]
150:     parent_tok = uuid.uuid4().hex
151:     os.environ["PARENT_TOKEN"] = parent_tok
152: 
153:     #2.Giả lập mất kết nối WebSocket khi phụ huynh gửi ADD_TIME cho DEVICE, APP và WEB
154:     res_dev = runSyncCoro(server.sendUrgentCmd(
155:         dev_id ,
156:         UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.DEVICE , bonus_time = 900) ,
157:         parent_token = parent_tok
158:     ))
159:     assert res_dev["via"] == "heartbeat_sync"
160: 
161:     runSyncCoro(server.sendUrgentCmd(
162:         dev_id ,
163:         UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.APP , subject = "roblox.exe" , bonus_time = 600) ,
164:         parent_token = parent_tok
165:     ))
166:     runSyncCoro(server.sendUrgentCmd(
167:         dev_id ,
168:         UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.WEB , subject = "youtube.com" , bonus_time = 300) ,
169:         parent_token = parent_tok
170:     ))
171: 
172:     #Kiểm tra Server đã lưu bền vững và không làm thay đổi Policy gốc
173:     assert server.device_unlocked_store[dev_id] == init_until + 900
174:     assert server.app_bonus_store[dev_id]["roblox.exe"] == 600
175:     assert server.web_bonus_store[dev_id]["youtube.com"] == 300
176:     assert server.policies_store[plc_id].weekday_quota == 5400
177: 
178:     #3.Giả lập Agent restart (mất hết biến trong RAM) rồi gửi Heartbeat lên Server để khôi phục
179:     agent.device_unlocked_until = 0
180:     agent.app_bonus_time = {}
181:     agent.web_bonus_time = {}
182:     agent.cur_policy = server.policies_store[plc_id]
183:     agent.cur_policy_version = 1
184: 
185:     hb_data = server.responseHeartbeat(HeartbeatRequest(
186:         device_id = dev_id ,
187:         access_token = acc_token ,
188:         policy_id = plc_id ,
189:         status_cur = "active" ,
190:         quota_used = {"roblox.exe" : 120 , "youtube.com" : 60} ,
191:         cur_policy_version = 1 ,
192:         acked_commands = []
193:     ))
194: 
195:     with patch("agent.psutil.process_iter" , return_value = []) :
196:         agent.HeartbeatResponseHanlder(hb_data)
197: 
198:     assert agent.device_unlocked_until == init_until + 900
199:     assert agent.app_bonus_time["roblox.exe"] == 600
200:     assert agent.web_bonus_time["youtube.com"] == 300
201: 
202:     #Dọn file tạm sau khi kiểm thử
203:     if server.QUOTA_STATE_FILE.exists() :
204:         server.QUOTA_STATE_FILE.unlink()
205: 
206: 
207: def test_urgent_auth_and_device_validation_s1() :
208:     parent_tok = uuid.uuid4().hex
209:     os.environ["PARENT_TOKEN"] = parent_tok
210:     server.device_tokens["di_valid"] = "at_valid"
211:     server.device_unlocked_store["di_valid"] = int(time.time()) + 1800
212:     cmd = UrgentCmd(cmd_type = CommandType.LOCK)
213: 
214:     #1.Từ chối khi thiếu hoặc sai parent_token (401)
215:     with pytest.raises(HTTPException) as exc_unauth :
216:         runSyncCoro(server.sendUrgentCmd("di_valid" , cmd , parent_token = "wrong_token"))
217:     assert exc_unauth.value.status_code == 401
218: 
219:     with pytest.raises(HTTPException) as exc_missing :
220:         runSyncCoro(server.sendUrgentCmd("di_valid" , cmd))
221:     assert exc_missing.value.status_code == 401
222: 
223:     #2.Từ chối khi device_id không tồn tại trong device_tokens (404)
224:     with pytest.raises(HTTPException) as exc_notfound :
225:         runSyncCoro(server.sendUrgentCmd("di_nonexistent" , cmd , parent_token = parent_tok))
226:     assert exc_notfound.value.status_code == 404
227:     assert "di_nonexistent" not in server.pending_cmds_store
228: 
229:     #3.Cho phép khi parent_token và device_id hợp lệ
230:     res = runSyncCoro(server.sendUrgentCmd("di_valid" , cmd , parent_token = parent_tok))
231:     assert res["device_id"] == "di_valid"
232:     assert res["cmd_type"] == CommandType.LOCK
233: 
234: 
235: def test_websocket_cleanup_and_reconnection_s2() :
236:     parent_tok = uuid.uuid4().hex
237:     os.environ["PARENT_TOKEN"] = parent_tok
238:     dev_id = "di_ws_test"
239:     acc_tok = "at_ws_test"
240:     server.device_tokens[dev_id] = acc_tok
241: 
242:     class DummyServerWS :
243:         def __init__(self , events) :
244:             self.events = list(events)
245:             self.accepted = False
246:             self.fail_send = False
247: 
248:         async def accept(self) :
249:             self.accepted = True
250: 
251:         async def receive_json(self) :
252:             ev = self.events.pop(0)
253:             if isinstance(ev , Exception) :
254:                 raise ev
255:             return ev
256: 
257:         async def send_json(self , payload) :
258:             if self.fail_send :
259:                 raise RuntimeError("Stale socket")
260: 
261:     #1.Kiểm tra urgentWebsocketEndpoint dọn kết nối khi gặp lỗi bất kỳ (không riêng WebSocketDisconnect)
262:     ws_old = DummyServerWS([RuntimeError("Unexpected JSON error")])
263:     runSyncCoro(server.urgentWebsocketEndpoint(ws_old , dev_id , acc_tok))
264:     assert dev_id not in server.active_ws_connections
265: 
266:     #2.Kiểm tra kết nối cũ đóng muộn không xóa nhầm kết nối mới hơn của cùng device_id
267:     ws_newer = DummyServerWS([])
268:     class LateCleanupWS(DummyServerWS) :
269:         async def receive_json(self) :
270:             #Giả lập kết nối mới đã ghi đè vào active_ws_connections trước khi kết nối cũ thoát
271:             server.active_ws_connections[dev_id] = ws_newer
272:             raise WebSocketDisconnect()
273: 
274:     ws_stale = LateCleanupWS([])
275:     runSyncCoro(server.urgentWebsocketEndpoint(ws_stale , dev_id , acc_tok))
276:     assert server.active_ws_connections.get(dev_id) is ws_newer
277: 
278:     #3.Kiểm tra sendUrgentCmd tự dọn kết nối stale khi send_json lỗi và fallback sang heartbeat_sync
279:     ws_newer.fail_send = True
280:     res = runSyncCoro(server.sendUrgentCmd(
281:         dev_id ,
282:         UrgentCmd(cmd_type = CommandType.LOCK) ,
283:         parent_token = parent_tok
284:     ))
285:     assert res["sent"] is False
286:     assert res["via"] == "heartbeat_sync"
287:     assert dev_id not in server.active_ws_connections
288: 
289:     #4.Kiểm tra Agent UrgentCmdHandler tự kết nối lại với backoff, bỏ qua gói JSON lỗi và chặn chạy trùng
290:     sleeps : list[float] = []
291:     sent_acks : list[dict] = []
292:     connect_calls = 0
293: 
294:     class DummyClientWS :
295:         def __init__(self , messages) :
296:             self.messages = list(messages)
297: 
298:         async def __aenter__(self) :
299:             return self
300: 
301:         async def __aexit__(self , exc_type , exc , tb) :
302:             return False
303: 
304:         async def recv(self) :
305:             if not self.messages :
306:                 raise ConnectionError("Connection lost")
307:             return self.messages.pop(0)
308: 
309:         async def send(self , data : str) :
310:             sent_acks.append(json.loads(data))
311: 
312:     def fake_connect(url : str) :
313:         nonlocal connect_calls
314:         connect_calls += 1
315:         if connect_calls <= 2 :
316:             raise ConnectionError(f"Initial connection failed #{connect_calls}")
317:         if connect_calls == 3 :
318:             return DummyClientWS([
319:                 "not-valid-json" ,
320:                 json.dumps({"cmd_type" : "lock" , "target_type" : "device"})
321:             ])
322:         raise ConnectionError("Disconnected after work")
323: 
324:     async def fake_sleep(delay : float) :
325:         sleeps.append(delay)
326: 
327:     agent.ws_handler_running = False
328:     with patch("agent.websockets.connect" , side_effect = fake_connect) , patch("agent.asyncio.sleep" , side_effect = fake_sleep) :
329:         runSyncCoro(agent.UrgentCmdHandler(max_retries = 2 , base_delay = 2.0 , max_delay = 5.0))
330: 
331:     assert connect_calls == 5
332:     assert sleeps == [2.0 , 4.0 , 2.0 , 4.0] #Tăng theo hàm mũ (2.0 -> 4.0), reset về 2.0 sau khi kết nối lần 3 thành công
333:     assert len(sent_acks) == 1
334:     assert sent_acks[0]["cmd_type"] == "lock"
335:     assert agent.status_cur == "locked"
336:     assert agent.ws_handler_running is False
337: 
338:     #Kiểm tra chặn khởi chạy trùng khi ws_handler_running đang True
339:     agent.ws_handler_running = True
340:     try :
341:         with patch("agent.websockets.connect" , side_effect = AssertionError("Should not connect")) :
342:             runSyncCoro(agent.UrgentCmdHandler(max_retries = 0))
343:     finally :
344:         agent.ws_handler_running = False
345: 
346:     if server.QUOTA_STATE_FILE.exists() :
347:         server.QUOTA_STATE_FILE.unlink()
```

---

### 4.5. File: `.gitignore` (71 dòng)
```gitignore
1: # Byte-compiled / optimized / DLL files
2: __pycache__/
3: *.py[cod]
4: *$py.class
5: 
6: # C extensions & PyInstaller / packaging
7: *.so
8: *.pyd
9: build/
10: dist/
11: *.spec
12: *.manifest
13: 
14: # Virtual environments
15: .venv/
16: venv/
17: ENV/
18: env/
19: 
20: # Databases & local state (SQLite + WAL/SHM)
21: *.db
22: *.sqlite
23: *.sqlite3
24: *.db-wal
25: *.db-shm
26: *.sqlite-wal
27: *.sqlite-shm
28: 
29: # Secrets, environment variables, and TLS certificates/keys
30: .env
31: .env.*
32: !.env.example
33: *.pem
34: *.key
35: *.crt
36: *.csr
37: *.p12
38: *.pfx
39: !tests/fixtures/*.crt
40: 
41: # Logs and runtime artifacts
42: *.log
43: logs/
44: *.pid
45: *.pipe
46: 
47: # Testing & coverage
48: .pytest_cache/
49: .coverage
50: htmlcov/
51: .mypy_cache/
52: .ruff_cache/
53: 
54: # OS & Editor artifacts
55: .DS_Store
56: Thumbs.db
57: Desktop.ini
58: .vscode/
59: .idea/
60: *.swp
61: *.swo
62: 
63: # Local AI review, debug & runtime state files
64: .agents/
65: .agent/
66: _agents/
67: _agent/
68: scripts/
69: REVIEW_SUMMARY.md
70: quota_state.json
71: *.tmp
```

---

### 4.6. File phụ thuộc trực tiếp (Unmodified Context): `pyproject.toml` (40 dòng)
```toml
1: [build-system]
2: requires = ["setuptools>=68.0"]
3: build-backend = "setuptools.build_meta"
4: 
5: [project]
6: name = "ogk-parental-companion"
7: version = "0.1.0"
8: description = "Ứng dụng hỗ trợ quản lý việc sử dụng máy tính của trẻ em - Công cụ đồng hành minh bạch"
9: readme = "README.md"
10: requires-python = ">=3.11"
11: dependencies = [
12:     "fastapi>=0.110.0",
13:     "uvicorn[standard]>=0.27.0",
14:     "sqlalchemy>=2.0.25",
15:     "pydantic>=2.6.0",
16:     "psutil>=5.9.8",
17:     "pywin32>=306; sys_platform == 'win32'",
18:     "passlib[argon2]>=1.7.4",
19:     "cryptography>=42.0.0",
20:     "httpx>=0.27.0",
21:     "websockets>=12.0",
22:     "dnslib>=0.9.24",
23:     "jinja2>=3.1.3",
24: ]
25: 
26: [project.optional-dependencies]
27: dev = [
28:     "pytest>=8.0.0",
29:     "pytest-asyncio>=0.23.5",
30:     "ruff>=0.3.0",
31: ]
32: 
33: [tool.pytest.ini_options]
34: testpaths = ["tests"]
35: asyncio_mode = "auto"
36: 
37: [tool.setuptools.packages.find]
38: where = ["."]
39: include = ["agent*", "server*", "shared*"]
40: exclude = ["data*", "tests*", ".venv*"]
```
