"""Kiểm thử cơ sở cho lược đồ sự kiện và cơ chế Quota (Device, App, Web, Restart, Mất kết nối)."""
import json
import os
import time
import uuid
from unittest.mock import patch
from fastapi import HTTPException , WebSocketDisconnect
import pytest
from shared.schemas import (
    AppRule,
    BlockReason,
    CommandType,
    DomainCategory,
    DomainRule,
    EnrollmentRequest,
    EventRecord,
    EventType,
    HeartbeatRequest,
    HeartbeatResponse,
    PairingCode,
    Policy,
    TargetType,
    UrgentCmd,
)
import server
import agent


def runSyncCoro(coro) :
    #Coroutine: hàm bất đồng bộ (async def); chạy trực tiếp bước send(None) để không cần khởi tạo socket loop trên Windows
    try :
        coro.send(None)
    except StopIteration as stop :
        return stop.value
    finally :
        coro.close()


def test_event_record_schema() :
    rec = EventRecord(
        idempotency_key = "550e8400-e29b-41d4-a716-446655440000" ,
        ts = 1730000000 ,
        device_id = "dev-01" ,
        child_id = "child-01" ,
        type = EventType.DOMAIN_QUERY ,
        subject = "example.edu.vn" ,
        duration_sec = 0 ,
        policy_id = "pol-v1" ,
    )
    assert rec.type == EventType.DOMAIN_QUERY
    assert rec.subject == "example.edu.vn"


def test_device_app_web_quota_and_block_reasons() :
    #Khởi tạo Policy mẫu với App/Web bị cấm bởi Policy và App/Web có quota riêng
    agent.cur_policy = Policy(
        policy_id = "plcid_test" ,
        policy_version = 1 ,
        weekday_quota = 3600 ,
        weekend_quota = 7200 ,
        schedule_7x48 = [[True] * 48 for _ in range(7)] ,
        app_rules = [
            AppRule(exe_name = "banned.exe" , sha256 = "a" * 64 , allowed = False , quota = 0) ,
            AppRule(exe_name = "roblox.exe" , sha256 = "b" * 64 , allowed = True , quota = 600) ,
        ] ,
        domain_rules = [
            DomainRule(domain = "bad.example" , category = DomainCategory.INAPPROPRIATE , allowed = False , quota = 0) ,
            DomainRule(domain = "youtube.com" , category = DomainCategory.ENTERTAINMENT , allowed = True , quota = 900) ,
        ] ,
        signature = "unsigned"
    )
    agent.quota_used = {"roblox.exe" : 600 , "youtube.com" : 900} #Cả app và web đều đã dùng hết quota gốc
    agent.app_bonus_time = {}
    agent.web_bonus_time = {}
    agent.device_unlocked_until = int(time.time()) + 1800
    agent.is_manual_locked = False

    with patch("agent.psutil.process_iter" , return_value = []) :
        #1.Kiểm tra phân biệt nguyên nhân chặn: POLICY vs APP_QUOTA vs WEB_QUOTA
        agent.applyPolicy()
        assert agent.status_cur == "active" #Thiết bị vẫn mở khi chỉ hết App/Web Quota
        assert agent.device_block_reason == BlockReason.NONE
        assert agent.app_block_reasons["banned.exe"] == BlockReason.POLICY
        assert agent.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
        assert agent.domain_block_reasons["bad.example"] == BlockReason.POLICY
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA
        assert "youtube.com" in agent.blocked_domains

        #2.ADD_TIME cho APP: chỉ mở lại roblox.exe, không ảnh hưởng youtube.com hay Policy gốc
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            bonus_time = 300
        ))
        assert agent.cur_policy.app_rules[1].quota == 600
        assert agent.getAppRemainingQuota("roblox.exe") == 300
        assert agent.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA

        #3.ADD_TIME cho WEB: chỉ mở lại youtube.com, giữ nguyên Policy gốc
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            bonus_time = 450
        ))
        assert agent.cur_policy.domain_rules[1].quota == 900
        assert agent.getWebRemainingQuota("youtube.com") == 450
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.NONE
        assert "youtube.com" not in agent.blocked_domains

        #4.Hết hạn Device-level quota (device_unlocked_until) -> khóa toàn bộ thiết bị
        agent.device_unlocked_until = int(time.time()) - 10
        agent.applyPolicy()
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #5.ADD_TIME cho DEVICE -> cộng trực tiếp vào device_unlocked_until và mở lại thiết bị
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.DEVICE ,
            bonus_time = 900
        ))
        assert agent.status_cur == "active"
        assert agent.device_block_reason == BlockReason.NONE

        #6.Ngoài khung giờ Schedule 7x48 -> khóa thiết bị với nguyên nhân SCHEDULE
        agent.cur_policy.schedule_7x48 = [[False] * 48 for _ in range(7)]
        agent.applyPolicy()
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.SCHEDULE


def test_agent_restart_and_disconnect_sync() :
    now_ts = int(time.time())
    server.curCode = PairingCode(
        pairing_code = "12345678" ,
        created_at = now_ts ,
        expires_at = now_ts + 600
    )

    #1.Enroll thiết bị
    enroll_data = server.responseEnroll(
        EnrollmentRequest(pairing_code = "12345678" , device_fingerprint = "fp_test_01")
    )
    dev_id = enroll_data.device_id
    acc_token = enroll_data.access_token
    plc_id = enroll_data.policy_id

    init_until = server.device_unlocked_store[dev_id]
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok

    #2.Giả lập mất kết nối WebSocket khi phụ huynh gửi ADD_TIME cho DEVICE, APP và WEB
    res_dev = runSyncCoro(server.sendUrgentCmd(
        dev_id ,
        UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.DEVICE , bonus_time = 900) ,
        parent_token = parent_tok
    ))
    assert res_dev["via"] == "heartbeat_sync"

    runSyncCoro(server.sendUrgentCmd(
        dev_id ,
        UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.APP , subject = "roblox.exe" , bonus_time = 600) ,
        parent_token = parent_tok
    ))
    runSyncCoro(server.sendUrgentCmd(
        dev_id ,
        UrgentCmd(cmd_type = CommandType.ADD_TIME , target_type = TargetType.WEB , subject = "youtube.com" , bonus_time = 300) ,
        parent_token = parent_tok
    ))

    #Kiểm tra Server đã lưu bền vững và không làm thay đổi Policy gốc
    assert server.device_unlocked_store[dev_id] == init_until + 900
    assert server.app_bonus_store[dev_id]["roblox.exe"] == 600
    assert server.web_bonus_store[dev_id]["youtube.com"] == 300
    assert server.policies_store[plc_id].weekday_quota == 5400

    #3.Giả lập Agent restart (mất hết biến trong RAM) rồi gửi Heartbeat lên Server để khôi phục
    agent.device_unlocked_until = 0
    agent.app_bonus_time = {}
    agent.web_bonus_time = {}
    agent.is_manual_locked = False
    agent.cur_policy = server.policies_store[plc_id]
    agent.cur_policy_version = 1

    hb_data = server.responseHeartbeat(HeartbeatRequest(
        device_id = dev_id ,
        access_token = acc_token ,
        policy_id = plc_id ,
        status_cur = "active" ,
        quota_used = {"roblox.exe" : 120 , "youtube.com" : 60} ,
        cur_policy_version = 1 ,
        acked_commands = []
    ))

    with patch("agent.psutil.process_iter" , return_value = []) :
        agent.HeartbeatResponseHanlder(hb_data)

    assert agent.device_unlocked_until == init_until + 900
    assert agent.app_bonus_time["roblox.exe"] == 600
    assert agent.web_bonus_time["youtube.com"] == 300

    #Dọn file tạm sau khi kiểm thử
    if server.QUOTA_STATE_FILE.exists() :
        server.QUOTA_STATE_FILE.unlink()


def test_urgent_auth_and_device_validation_s1() :
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok
    server.device_tokens["di_valid"] = "at_valid"
    server.device_unlocked_store["di_valid"] = int(time.time()) + 1800
    cmd = UrgentCmd(cmd_type = CommandType.LOCK)

    #1.Từ chối khi thiếu hoặc sai parent_token (401)
    with pytest.raises(HTTPException) as exc_unauth :
        runSyncCoro(server.sendUrgentCmd("di_valid" , cmd , parent_token = "wrong_token"))
    assert exc_unauth.value.status_code == 401

    with pytest.raises(HTTPException) as exc_missing :
        runSyncCoro(server.sendUrgentCmd("di_valid" , cmd))
    assert exc_missing.value.status_code == 401

    #2.Từ chối khi device_id không tồn tại trong device_tokens (404)
    with pytest.raises(HTTPException) as exc_notfound :
        runSyncCoro(server.sendUrgentCmd("di_nonexistent" , cmd , parent_token = parent_tok))
    assert exc_notfound.value.status_code == 404
    assert "di_nonexistent" not in server.pending_cmds_store

    #3.Cho phép khi parent_token và device_id hợp lệ
    res = runSyncCoro(server.sendUrgentCmd("di_valid" , cmd , parent_token = parent_tok))
    assert res["device_id"] == "di_valid"
    assert res["cmd_type"] == CommandType.LOCK


def test_websocket_cleanup_and_reconnection_s2() :
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok
    dev_id = "di_ws_test"
    acc_tok = "at_ws_test"
    server.device_tokens[dev_id] = acc_tok

    class DummyServerWS :
        def __init__(self , events) :
            self.events = list(events)
            self.accepted = False
            self.fail_send = False

        async def accept(self) :
            self.accepted = True

        async def receive_json(self) :
            ev = self.events.pop(0)
            if isinstance(ev , Exception) :
                raise ev
            return ev

        async def send_json(self , payload) :
            if self.fail_send :
                raise RuntimeError("Stale socket")

    #1.Kiểm tra urgentWebsocketEndpoint dọn kết nối khi gặp lỗi bất kỳ (không riêng WebSocketDisconnect)
    ws_old = DummyServerWS([RuntimeError("Unexpected JSON error")])
    runSyncCoro(server.urgentWebsocketEndpoint(ws_old , dev_id , acc_tok))
    assert dev_id not in server.active_ws_connections

    #2.Kiểm tra kết nối cũ đóng muộn không xóa nhầm kết nối mới hơn của cùng device_id
    ws_newer = DummyServerWS([])
    class LateCleanupWS(DummyServerWS) :
        async def receive_json(self) :
            #Giả lập kết nối mới đã ghi đè vào active_ws_connections trước khi kết nối cũ thoát
            server.active_ws_connections[dev_id] = ws_newer
            raise WebSocketDisconnect()

    ws_stale = LateCleanupWS([])
    runSyncCoro(server.urgentWebsocketEndpoint(ws_stale , dev_id , acc_tok))
    assert server.active_ws_connections.get(dev_id) is ws_newer

    #3.Kiểm tra sendUrgentCmd tự dọn kết nối stale khi send_json lỗi và fallback sang heartbeat_sync
    ws_newer.fail_send = True
    res = runSyncCoro(server.sendUrgentCmd(
        dev_id ,
        UrgentCmd(cmd_type = CommandType.LOCK) ,
        parent_token = parent_tok
    ))
    assert res["sent"] is False
    assert res["via"] == "heartbeat_sync"
    assert dev_id not in server.active_ws_connections

    #4.Kiểm tra Agent UrgentCmdHandler tự kết nối lại với backoff, bỏ qua gói JSON lỗi và chặn chạy trùng
    sleeps : list[float] = []
    sent_acks : list[dict] = []
    connect_calls = 0

    class DummyClientWS :
        def __init__(self , messages) :
            self.messages = list(messages)

        async def __aenter__(self) :
            return self

        async def __aexit__(self , exc_type , exc , tb) :
            return False

        async def recv(self) :
            if not self.messages :
                raise ConnectionError("Connection lost")
            return self.messages.pop(0)

        async def send(self , data : str) :
            sent_acks.append(json.loads(data))

    def fake_connect(url : str) :
        nonlocal connect_calls
        connect_calls += 1
        if connect_calls <= 2 :
            raise ConnectionError(f"Initial connection failed #{connect_calls}")
        if connect_calls == 3 :
            return DummyClientWS([
                "not-valid-json" ,
                json.dumps({"cmd_type" : "lock" , "target_type" : "device"})
            ])
        raise ConnectionError("Disconnected after work")

    async def fake_sleep(delay : float) :
        sleeps.append(delay)

    agent.ws_handler_running = False
    with patch("agent.websockets.connect" , side_effect = fake_connect) , patch("agent.asyncio.sleep" , side_effect = fake_sleep) :
        runSyncCoro(agent.UrgentCmdHandler(max_retries = 2 , base_delay = 2.0 , max_delay = 5.0))

    assert connect_calls == 5
    assert sleeps == [2.0 , 4.0 , 2.0 , 4.0] #Tăng theo hàm mũ (2.0 -> 4.0), reset về 2.0 sau khi kết nối lần 3 thành công
    assert len(sent_acks) == 1
    assert sent_acks[0]["cmd_type"] == "lock"
    assert agent.status_cur == "locked"
    assert agent.ws_handler_running is False

    #Kiểm tra chặn khởi chạy trùng khi ws_handler_running đang True
    agent.ws_handler_running = True
    try :
        with patch("agent.websockets.connect" , side_effect = AssertionError("Should not connect")) :
            runSyncCoro(agent.UrgentCmdHandler(max_retries = 0))
    finally :
        agent.ws_handler_running = False
        agent.is_manual_locked = False

    if server.QUOTA_STATE_FILE.exists() :
        server.QUOTA_STATE_FILE.unlink()


def test_manual_lock_preservation_and_shared_cmd_semantics_c1() :
    agent.cur_policy = Policy(
        policy_id = "plcid_c1" ,
        policy_version = 1 ,
        weekday_quota = 3600 ,
        weekend_quota = 7200 ,
        schedule_7x48 = [[True] * 48 for _ in range(7)] ,
        app_rules = [
            AppRule(exe_name = "roblox.exe" , sha256 = "b" * 64 , allowed = True , quota = 600) ,
        ] ,
        domain_rules = [] ,
        signature = "unsigned"
    )
    agent.cur_policy_version = 1
    agent.quota_used = {}
    agent.app_bonus_time = {}
    agent.web_bonus_time = {}
    agent.executed_cmds = set()
    agent.acked_commands = []
    agent.is_manual_locked = False
    agent.device_unlocked_until = int(time.time()) + 1800

    with patch("agent.psutil.process_iter" , return_value = []) :
        #1.Khóa thủ công qua WebSocket (execCmd): bảo toàn khóa khi applyPolicy chạy lại hoặc khi cộng giờ cho App
        agent.execCmd(UrgentCmd(cmd_type = CommandType.LOCK))
        assert agent.is_manual_locked is True
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.POLICY

        agent.applyPolicy()
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.POLICY

        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            bonus_time = 300
        ))
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.POLICY

        #2.Gỡ khóa thủ công qua WebSocket khi lịch và quota thiết bị đều hợp lệ -> mở khóa máy
        agent.execCmd(UrgentCmd(cmd_type = CommandType.UNLOCK))
        assert agent.is_manual_locked is False
        assert agent.status_cur == "active"
        assert agent.device_block_reason == BlockReason.NONE

        #3.Khóa thủ công qua kênh Heartbeat (pending_commands): dùng chung ngữ nghĩa và giữ khóa qua các nhịp Heartbeat kế tiếp
        agent.HeartbeatResponseHanlder(HeartbeatResponse(
            latest_policy_version = 1 ,
            pending_commands = ["1730000100:lock"] ,
            device_unlocked_until = agent.device_unlocked_until
        ))
        assert agent.is_manual_locked is True
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.POLICY
        assert "1730000100:lock" in agent.acked_commands

        #Nhịp Heartbeat tiếp theo (không còn lệnh mới) chạy lại applyPolicy nhưng không được ghi đè khóa thủ công
        agent.HeartbeatResponseHanlder(HeartbeatResponse(
            latest_policy_version = 1 ,
            pending_commands = [] ,
            device_unlocked_until = agent.device_unlocked_until
        ))
        assert agent.is_manual_locked is True
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.POLICY

        #4.Gỡ khóa thủ công (UNLOCK) nhưng thiết bị đã hết hạn DEVICE_QUOTA -> không được bỏ qua DEVICE_QUOTA
        agent.device_unlocked_until = int(time.time()) - 30
        agent.HeartbeatResponseHanlder(HeartbeatResponse(
            latest_policy_version = 1 ,
            pending_commands = ["1730000200:unlock"] ,
            device_unlocked_until = 0
        ))
        assert agent.is_manual_locked is False
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #5.Khóa thủ công khi đang ngoài khung giờ SCHEDULE, sau đó UNLOCK -> phải giữ nguyên khóa do SCHEDULE
        agent.device_unlocked_until = int(time.time()) + 1800
        agent.cur_policy.schedule_7x48 = [[False] * 48 for _ in range(7)]
        agent.execCmd(UrgentCmd(cmd_type = CommandType.LOCK))
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.POLICY

        agent.execCmd(UrgentCmd(cmd_type = CommandType.UNLOCK))
        assert agent.is_manual_locked is False
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.SCHEDULE

        #Khi khung giờ SCHEDULE cho phép trở lại -> thiết bị mới chuyển sang active
        agent.cur_policy.schedule_7x48 = [[True] * 48 for _ in range(7)]
        agent.applyPolicy()
        assert agent.status_cur == "active"
        assert agent.device_block_reason == BlockReason.NONE


def test_sub_time_negative_adjustment_and_policy_update_c2() :
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok
    dev_id = "di_c2_test"
    acc_tok = "at_c2_test"
    plc_id = "plcid_c2_test"
    server.device_tokens[dev_id] = acc_tok
    server.device_unlocked_store[dev_id] = int(time.time()) + 3600
    server.app_bonus_store[dev_id] = {}
    server.web_bonus_store[dev_id] = {}

    server.policies_store[plc_id] = Policy(
        policy_id = plc_id ,
        policy_version = 1 ,
        weekday_quota = 3600 ,
        weekend_quota = 7200 ,
        schedule_7x48 = [[True] * 48 for _ in range(7)] ,
        app_rules = [
            AppRule(exe_name = "roblox.exe" , sha256 = "b" * 64 , allowed = True , quota = 600) ,
        ] ,
        domain_rules = [
            DomainRule(domain = "youtube.com" , category = DomainCategory.ENTERTAINMENT , allowed = True , quota = 600) ,
        ] ,
        signature = "unsigned"
    )

    agent.cur_policy = server.policies_store[plc_id].model_copy(deep = True)
    agent.cur_policy_version = 1
    agent.quota_used = {"roblox.exe" : 100 , "youtube.com" : 100}
    agent.app_bonus_time = {}
    agent.web_bonus_time = {}
    agent.is_manual_locked = False
    agent.device_unlocked_until = int(time.time()) + 3600

    with patch("agent.psutil.process_iter" , return_value = []) :
        #1.SUB_TIME vượt bonus hiện có (0s) khiến adjustment âm (-250s) và trừ trực tiếp vào ngân sách quota gốc
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            sub_time = 250
        ))
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            sub_time = 250
        ))
        assert agent.app_bonus_time["roblox.exe"] == -250
        assert agent.web_bonus_time["youtube.com"] == -250
        #remain = max(0, 600 + (-250) - 100) = 250
        assert agent.getAppRemainingQuota("roblox.exe") == 250
        assert agent.getWebRemainingQuota("youtube.com") == 250
        assert agent.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.NONE

        #2.SUB_TIME vượt toàn bộ phần còn lại -> adjustment tiếp tục giảm (-650s), nhưng remain được chặn ở 0 (không âm)
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            sub_time = 400
        ))
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            sub_time = 400
        ))
        assert agent.app_bonus_time["roblox.exe"] == -650
        assert agent.web_bonus_time["youtube.com"] == -650
        assert agent.getAppRemainingQuota("roblox.exe") == 0
        assert agent.getWebRemainingQuota("youtube.com") == 0
        assert agent.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA
        assert "youtube.com" in agent.blocked_domains

        #3.ADD_TIME sau khi adjustment đang âm (-650 + 300 = -350): tính lại chính xác remain = max(0, 600 - 350 - 100) = 150
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            bonus_time = 300
        ))
        agent.execCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            bonus_time = 300
        ))
        assert agent.app_bonus_time["roblox.exe"] == -350
        assert agent.web_bonus_time["youtube.com"] == -350
        assert agent.getAppRemainingQuota("roblox.exe") == 150
        assert agent.getWebRemainingQuota("youtube.com") == 150
        assert agent.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.NONE
        assert "youtube.com" not in agent.blocked_domains

        #4.Policy cập nhật tăng/giảm quota: giữ nguyên adjustment (-350) và used_time (100), không mất hoặc tính trùng used_time
        updated_policy_high = Policy(
            policy_id = plc_id ,
            policy_version = 2 ,
            weekday_quota = 3600 ,
            weekend_quota = 7200 ,
            schedule_7x48 = [[True] * 48 for _ in range(7)] ,
            app_rules = [
                AppRule(exe_name = "roblox.exe" , sha256 = "b" * 64 , allowed = True , quota = 900) ,
            ] ,
            domain_rules = [
                DomainRule(domain = "youtube.com" , category = DomainCategory.ENTERTAINMENT , allowed = True , quota = 900) ,
            ] ,
            signature = "unsigned"
        )
        with patch("agent.requestPolicy" , return_value = updated_policy_high) :
            agent.HeartbeatResponseHanlder(HeartbeatResponse(latest_policy_version = 2))
        assert agent.quota_used == {"roblox.exe" : 100 , "youtube.com" : 100}
        assert agent.app_bonus_time["roblox.exe"] == -350
        assert agent.web_bonus_time["youtube.com"] == -350
        #remain = max(0, 900 - 350 - 100) = 450
        assert agent.getAppRemainingQuota("roblox.exe") == 450
        assert agent.getWebRemainingQuota("youtube.com") == 450

        updated_policy_low = Policy(
            policy_id = plc_id ,
            policy_version = 3 ,
            weekday_quota = 3600 ,
            weekend_quota = 7200 ,
            schedule_7x48 = [[True] * 48 for _ in range(7)] ,
            app_rules = [
                AppRule(exe_name = "roblox.exe" , sha256 = "b" * 64 , allowed = True , quota = 400) ,
            ] ,
            domain_rules = [
                DomainRule(domain = "youtube.com" , category = DomainCategory.ENTERTAINMENT , allowed = True , quota = 400) ,
            ] ,
            signature = "unsigned"
        )
        with patch("agent.requestPolicy" , return_value = updated_policy_low) :
            agent.HeartbeatResponseHanlder(HeartbeatResponse(latest_policy_version = 3))
        assert agent.quota_used == {"roblox.exe" : 100 , "youtube.com" : 100}
        assert agent.app_bonus_time["roblox.exe"] == -350
        assert agent.web_bonus_time["youtube.com"] == -350
        #remain = max(0, 400 - 350 - 100) = 0
        assert agent.getAppRemainingQuota("roblox.exe") == 0
        assert agent.getWebRemainingQuota("youtube.com") == 0
        assert agent.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA

        #5.Kiểm tra Server persistence & Heartbeat sync bảo toàn adjustment âm cho cả APP và WEB
        runSyncCoro(server.sendUrgentCmd(
            dev_id ,
            UrgentCmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.APP , subject = "roblox.exe" , sub_time = 200) ,
            parent_token = parent_tok
        ))
        runSyncCoro(server.sendUrgentCmd(
            dev_id ,
            UrgentCmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.WEB , subject = "youtube.com" , sub_time = 200) ,
            parent_token = parent_tok
        ))
        server.loadQuotaState()
        assert server.app_bonus_store[dev_id]["roblox.exe"] == -200
        assert server.web_bonus_store[dev_id]["youtube.com"] == -200

        hb_resp = server.responseHeartbeat(HeartbeatRequest(
            device_id = dev_id ,
            access_token = acc_tok ,
            policy_id = plc_id ,
            status_cur = "active" ,
            quota_used = agent.quota_used ,
            cur_policy_version = 3 ,
            acked_commands = []
        ))
        agent.HeartbeatResponseHanlder(hb_resp)
        assert agent.app_bonus_time["roblox.exe"] == -200
        assert agent.web_bonus_time["youtube.com"] == -200

    if server.QUOTA_STATE_FILE.exists() :
        server.QUOTA_STATE_FILE.unlink()


def test_device_quota_daily_cycle_and_zero_handling_c3() :
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok
    now_ts = int(time.time())
    server.curCode = PairingCode(
        pairing_code = "87654321" ,
        created_at = now_ts ,
        expires_at = now_ts + 600
    )

    enroll_data = server.responseEnroll(
        EnrollmentRequest(pairing_code = "87654321" , device_fingerprint = "fp_c3_device")
    )
    dev_id = enroll_data.device_id
    acc_tok = enroll_data.access_token
    plc_id = enroll_data.policy_id
    today_str = server.getTodayDateStr()

    agent.cur_policy = server.policies_store[plc_id].model_copy(deep = True)
    agent.cur_policy_version = 1
    agent.quota_used = {}
    agent.app_bonus_time = {}
    agent.web_bonus_time = {}
    agent.is_manual_locked = False
    agent.device_unlocked_until = server.device_unlocked_store[dev_id]
    agent.device_quota_date = today_str

    with patch("agent.psutil.process_iter" , return_value = []) :
        #1.DEVICE hết quota (cả khi quá hạn thông thường lẫn khi SUB_TIME đưa device_unlocked_until == 0) -> phải giữ khóa trong cùng ngày
        runSyncCoro(server.sendUrgentCmd(
            dev_id ,
            UrgentCmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.DEVICE , sub_time = 7200) ,
            parent_token = parent_tok
        ))
        agent.execCmd(UrgentCmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.DEVICE , sub_time = 7200))
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #Trường hợp SUB_TIME lớn đưa device_unlocked_until chạm mốc 0 -> không được tự cấp lại quota
        full_sub = server.device_unlocked_store[dev_id] + 100
        runSyncCoro(server.sendUrgentCmd(
            dev_id ,
            UrgentCmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.DEVICE , sub_time = full_sub) ,
            parent_token = parent_tok
        ))
        agent.execCmd(UrgentCmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.DEVICE , sub_time = full_sub))
        assert server.device_unlocked_store[dev_id] == 0
        assert agent.device_unlocked_until == 0
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #Gọi lại applyPolicy nhiều lần trong cùng ngày khi device_unlocked_until == 0 không được tự cấp lại quota
        agent.applyPolicy()
        assert agent.device_unlocked_until == 0
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #2.Server restart trong cùng ngày (loadQuotaState) -> khôi phục đúng trạng thái hết quota (0), không cấp lại
        server.device_unlocked_store.clear()
        server.device_quota_date_store.clear()
        server.loadQuotaState()
        assert server.device_unlocked_store[dev_id] == 0
        assert server.device_quota_date_store[dev_id] == today_str

        #3.Agent restart trong cùng ngày (RAM về 0 / rỗng) -> cả trước và sau Heartbeat đều không tự cấp lại quota
        agent.device_unlocked_until = 0
        agent.device_quota_date = ""
        agent.applyPolicy()
        assert agent.device_unlocked_until == 0
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #Ngay cả khi Agent có giá trị cũ khác 0 trước đó, Heartbeat từ Server trả về 0 vẫn đồng bộ khóa máy chính xác
        agent.device_unlocked_until = int(time.time()) + 1800
        hb_same_day = server.responseHeartbeat(HeartbeatRequest(
            device_id = dev_id ,
            access_token = acc_tok ,
            policy_id = plc_id ,
            status_cur = "locked" ,
            quota_used = {} ,
            cur_policy_version = 1 ,
            acked_commands = []
        ))
        assert hb_same_day.device_unlocked_until == 0
        assert hb_same_day.device_quota_date == today_str
        agent.HeartbeatResponseHanlder(hb_same_day)
        assert agent.device_unlocked_until == 0
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #4.Qua ngày mới (00:00 -> ngày lịch mới): DEVICE được cấp lại quota theo Policy hiện tại (trên cả Agent và Server)
        yesterday_str = "2026-10-31"
        new_day_str = "2026-11-01"
        agent.device_unlocked_until = 0
        agent.device_quota_date = yesterday_str
        agent.applyPolicy()
        assert agent.device_unlocked_until > int(time.time())
        assert agent.device_quota_date == today_str
        assert agent.status_cur == "active"

        #Gọi lại applyPolicy trong cùng ngày mới chỉ giữ nguyên mốc vừa cấp, không reset lần thứ hai
        agent_custom_until = agent.device_unlocked_until - 600
        agent.device_unlocked_until = agent_custom_until
        agent.applyPolicy()
        assert agent.device_unlocked_until == agent_custom_until

        server.device_unlocked_store[dev_id] = 0
        server.device_quota_date_store[dev_id] = yesterday_str
        server.saveQuotaState()
        agent.device_unlocked_until = 0
        agent.device_quota_date = yesterday_str

        with patch("server.getTodayDateStr" , return_value = new_day_str) :
            #Server khởi động / đồng bộ trong ngày mới -> reset DEVICE quota theo Policy
            server.loadQuotaState()
            first_new_day_until = server.device_unlocked_store[dev_id]
            assert first_new_day_until > int(time.time())
            assert server.device_quota_date_store[dev_id] == new_day_str

            #5.Restart lần nữa sau 00:00 trong cùng ngày mới -> chỉ reset đúng 1 lần, bảo toàn quota đã trừ/sử dụng
            reduced_until = first_new_day_until - 1200
            server.device_unlocked_store[dev_id] = reduced_until
            server.saveQuotaState()

            server.device_unlocked_store.clear()
            server.device_quota_date_store.clear()
            server.loadQuotaState()
            assert server.device_unlocked_store[dev_id] == reduced_until
            assert server.device_quota_date_store[dev_id] == new_day_str

            hb_new_day = server.responseHeartbeat(HeartbeatRequest(
                device_id = dev_id ,
                access_token = acc_tok ,
                policy_id = plc_id ,
                status_cur = "locked" ,
                quota_used = {} ,
                cur_policy_version = 1 ,
                acked_commands = []
            ))
            assert hb_new_day.device_unlocked_until == reduced_until
            assert hb_new_day.device_quota_date == new_day_str
            agent.HeartbeatResponseHanlder(hb_new_day)
            assert agent.device_unlocked_until == reduced_until
            assert agent.device_quota_date == new_day_str
            assert agent.status_cur == "active"
            assert agent.device_block_reason == BlockReason.NONE

    if server.QUOTA_STATE_FILE.exists() :
        server.QUOTA_STATE_FILE.unlink()
    if agent.AGENT_STATE_FILE.exists() :
        agent.AGENT_STATE_FILE.unlink()


def test_clock_monotonic_elapsed_tamper_and_reboot_recovery_c3() :
    agent.cur_policy = Policy(
        policy_id = "plcid_clock_c3" ,
        policy_version = 1 ,
        weekday_quota = 3600 ,
        weekend_quota = 7200 ,
        schedule_7x48 = [[True] * 48 for _ in range(7)] ,
        app_rules = [] ,
        domain_rules = [] ,
        signature = "unsigned"
    )
    agent.cur_policy_version = 1
    agent.quota_used = {}
    agent.device_quota_used = 0.0
    agent.event_buffer.clear()
    agent.is_manual_locked = False

    base_wall = 1793520000.0
    base_mono = 10000.0
    cur_wall = [base_wall]
    cur_mono = [base_mono]

    with (
        patch("agent.psutil.process_iter" , return_value = []) ,
        patch("agent.time.time" , side_effect = lambda : cur_wall[0]) ,
        patch("agent.time.monotonic" , side_effect = lambda : cur_mono[0]) ,
        patch("agent.getWindowsInputInfo" , return_value = (1000 , 0.0)) ,
    ) :
        agent.device_quota_date = agent.getTodayDateStr()
        agent.device_unlocked_until = int(cur_wall[0]) + 1800
        agent._last_synced_unlocked_until = 0
        agent.last_input_mono = cur_mono[0]
        agent.applyPolicy()
        assert agent.device_remaining_sec == 1800.0
        assert agent.status_cur == "active"

        #1.Đo elapsed time bằng monotonic clock: chỉnh wall clock tăng/giảm nhỏ không làm sai lệch thời gian sử dụng
        cur_mono[0] += 120.0
        cur_wall[0] += 300.0
        agent.last_input_mono = cur_mono[0]
        agent.applyPolicy()
        assert agent.device_quota_used == 120.0
        assert agent.device_remaining_sec == 1680.0

        #2.Lùi đồng hồ hệ thống 3 giờ (-10800s): quota không được tăng trở lại và sự kiện clock_tamper phải được ghi nhận
        cur_mono[0] += 60.0
        cur_wall[0] -= 10800.0
        agent.last_input_mono = cur_mono[0]
        agent.applyPolicy()
        assert agent.device_quota_used == 180.0
        assert agent.device_remaining_sec == 1620.0
        assert any(ev.subject == "clock_tamper" and ev.type == EventType.QUOTA_WARNING for ev in agent.event_buffer)

        #3.Recovery sau reboot: khi monotonic clock của OS reset về số nhỏ (5.0 < 10180.0), không dùng mốc monotonic cũ sai cách
        agent.saveAgentQuotaState()
        cur_mono[0] = 5.0
        cur_wall[0] += 30.0
        agent.loadAgentQuotaState()
        agent.applyPolicy()
        assert agent.device_remaining_sec == 1620.0
        assert agent.device_quota_used == 180.0

        #Sau khi reboot, tiếp tục sử dụng 20s trên mốc monotonic mới -> trừ chính xác 20s (còn 1600s)
        cur_mono[0] = 25.0
        cur_wall[0] += 20.0
        agent.last_input_mono = cur_mono[0]
        agent.applyPolicy()
        assert agent.device_remaining_sec == 1600.0
        assert agent.device_quota_used == 200.0

    if agent.AGENT_STATE_FILE.exists() :
        agent.AGENT_STATE_FILE.unlink()


def test_idle_active_state_transitions_and_quota_accounting_c3() :
    agent.cur_policy = Policy(
        policy_id = "plcid_idle_c3" ,
        policy_version = 1 ,
        weekday_quota = 3600 ,
        weekend_quota = 7200 ,
        schedule_7x48 = [[True] * 48 for _ in range(7)] ,
        app_rules = [] ,
        domain_rules = [] ,
        signature = "unsigned"
    )
    agent.cur_policy_version = 1
    agent.quota_used = {}
    agent.device_quota_used = 0.0
    agent.is_manual_locked = False

    cur_wall = [1793520000.0]
    cur_mono = [5000.0]
    win_tick = [1000]

    with (
        patch("agent.psutil.process_iter" , return_value = []) ,
        patch("agent.time.time" , side_effect = lambda : cur_wall[0]) ,
        patch("agent.time.monotonic" , side_effect = lambda : cur_mono[0]) ,
        patch("agent.getWindowsInputInfo" , side_effect = lambda : (win_tick[0] , 0.0)) ,
    ) :
        agent.device_quota_date = agent.getTodayDateStr()
        agent.device_unlocked_until = int(cur_wall[0]) + 1800
        agent._last_synced_unlocked_until = 0
        agent.last_input_mono = None
        agent._last_win_input_tick = None

        #1.Có input -> trạng thái Active ngay lập tức
        agent.recordUserInput()
        assert agent.status_cur == "active"
        assert agent.device_remaining_sec == 1800.0

        #Sử dụng Active trong 100s (có thao tác chuột/phím mới ở giây thứ 100) -> tiêu thụ đúng 100s
        cur_mono[0] += 100.0
        cur_wall[0] += 100.0
        win_tick[0] += 100000
        agent.recordUserInput()
        assert agent.status_cur == "active"
        assert agent.device_quota_used == 100.0
        assert agent.device_remaining_sec == 1700.0

        #2.Không có input quá 5 phút (305s >= 300s) -> chuyển sang Idle
        cur_mono[0] += 305.0
        cur_wall[0] += 305.0
        agent.applyPolicy()
        assert agent.status_cur == "idle"
        assert agent.device_quota_used == 100.0
        assert agent.device_remaining_sec == 1700.0

        #3.Đang ở trạng thái Idle thêm 600s -> không tiêu thụ quota
        cur_mono[0] += 600.0
        cur_wall[0] += 600.0
        agent.applyPolicy()
        assert agent.status_cur == "idle"
        assert agent.device_quota_used == 100.0
        assert agent.device_remaining_sec == 1700.0

        #4.Có input trở lại sau Idle -> chuyển sang Active ngay lập tức (không có khoảng trễ xác nhận), không mất/trùng quota cũ
        win_tick[0] += 5000
        agent.recordUserInput()
        assert agent.status_cur == "active"
        assert agent.device_quota_used == 100.0
        assert agent.device_remaining_sec == 1700.0

        #Tiếp tục Active thêm 50s rồi khóa máy -> chốt đúng 50s Active trước khi khóa (tổng 150s, còn 1650s)
        cur_mono[0] += 50.0
        cur_wall[0] += 50.0
        agent.execCmd(UrgentCmd(cmd_type = CommandType.LOCK))
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.POLICY
        assert agent.device_quota_used == 150.0
        assert agent.device_remaining_sec == 1650.0

        #5.Máy bị khóa -> không tiêu thụ quota bất kể có thao tác input mới
        cur_mono[0] += 400.0
        cur_wall[0] += 400.0
        win_tick[0] += 20000
        agent.recordUserInput()
        assert agent.status_cur == "locked"
        assert agent.device_quota_used == 150.0
        assert agent.device_remaining_sec == 1650.0

        #6.Gỡ khóa máy rồi dùng thêm 30s Active -> chuyển đổi trạng thái không làm mất hoặc tính trùng thời gian (150 + 30 = 180s)
        agent.execCmd(UrgentCmd(cmd_type = CommandType.UNLOCK))
        assert agent.status_cur == "active"
        assert agent.device_quota_used == 150.0
        assert agent.device_remaining_sec == 1650.0

        cur_mono[0] += 30.0
        cur_wall[0] += 30.0
        agent.applyPolicy()
        assert agent.status_cur == "active"
        assert agent.device_quota_used == 180.0
        assert agent.device_remaining_sec == 1620.0
