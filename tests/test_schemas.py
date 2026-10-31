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
    PairingCode,
    Policy,
    TargetType,
    UrgentCmd,
)
import server
import agent


def runSyncCoro(coro) :
    #Chạy coroutine không cần tạo ProactorEventLoop socket trên Windows
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
        agent.executeUrgentCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            bonus_time = 300
        ))
        assert agent.cur_policy.app_rules[1].quota == 600 #Policy gốc giữ nguyên
        assert agent.getAppRemainingQuota("roblox.exe") == 300
        assert agent.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA #Web vẫn bị chặn

        #3.ADD_TIME cho WEB: chỉ mở lại youtube.com, giữ nguyên Policy gốc
        agent.executeUrgentCmd(UrgentCmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            bonus_time = 450
        ))
        assert agent.cur_policy.domain_rules[1].quota == 900 #Policy gốc giữ nguyên
        assert agent.getWebRemainingQuota("youtube.com") == 450
        assert agent.domain_block_reasons["youtube.com"] == BlockReason.NONE
        assert "youtube.com" not in agent.blocked_domains

        #4.Hết hạn Device-level quota (device_unlocked_until) -> khóa toàn bộ thiết bị
        agent.device_unlocked_until = int(time.time()) - 10
        agent.applyPolicy()
        assert agent.status_cur == "locked"
        assert agent.device_block_reason == BlockReason.DEVICE_QUOTA

        #5.ADD_TIME cho DEVICE -> cộng trực tiếp vào device_unlocked_until và mở lại thiết bị
        agent.executeUrgentCmd(UrgentCmd(
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

    if server.QUOTA_STATE_FILE.exists() :
        server.QUOTA_STATE_FILE.unlink()
