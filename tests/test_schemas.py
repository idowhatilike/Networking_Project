#Kiểm thử dữ liệu và hạn mức DEVICE/APP/WEB.
import json
import os
import time
import uuid
from unittest.mock import Mock , patch

import pytest
from fastapi import HTTPException, WebSocketDisconnect

import agent
import agent.storage
import server
from test_protocol import (
    drainResponse , execRequest , makeHeartbeat , proposeRequest
)
from agent.helpers import enrollment
from shared.schemas import (
    AppRule,
    BlockReason,
    CmdRequest as Cmd,
    ControlState,
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
)


@pytest.fixture(autouse = True)
def isolated_quota_state(monkeypatch , tmp_path) :
    #Mỗi test dùng trạng thái và file riêng, không đọc/ghi quota của lần chạy khác.
    monkeypatch.setattr(server.state , "QUOTA_STATE_FILE" , tmp_path / "server_quota.json")
    monkeypatch.setattr(agent.state , "AGENT_STATE_FILE" , tmp_path / "agent_quota.json")
    for name in (
        "device_tokens", "device_states", "policies_store", "command_sessions",
        "device_quota_store", "device_used_store", "device_quota_date_store",
        "device_policy_store", "app_bonus_store", "web_bonus_store",
        "active_ws_connections",
    ) :
        monkeypatch.setattr(server.state , name , {})
    for name , value in {
        "device_id": None, "access_token": None, "policy_id": None,
        "cur_policy": None, "dev_status_cur": "active",
        "device_quota": 0.0, "device_used": 0.0,
        "device_quota_date": "", "last_mono_ts": None,
        "last_wall_ts": None, "last_input_mono": None, "_last_win_input_tick": None,
        "is_manual_locked": False, "quota_used": {}, "app_bonus_time": {},
        "manual_locked_apps": set(), "manual_locked_domains": set(),
        "web_bonus_time": {}, "app_block_reasons": {}, "domain_block_reasons": {},
        "command_seq": 0, "online": False, "event_buffer": [],
        "last_cmd_ack": None, "storage_loaded": True, "needs_sync": True,
    }.items() :
        monkeypatch.setattr(agent.state , name , value)
    monkeypatch.setattr(agent.quota.user_input , "getWindowsInputInfo" , lambda : None)
    monkeypatch.setattr(
        agent , "requestPolicy" , lambda : server.state.policies_store[agent.state.policy_id]
    )


def runSyncCoro(coro) :
    #Chạy coroutine không chờ tác vụ ngoài.
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


@pytest.mark.parametrize("requestType" , ["policy" , "heartbeat"])
@pytest.mark.parametrize("requestedPolicy" , ["policy_a" , "policy_b" , "missing"])
def testPolicyMustMatchDevice(monkeypatch , requestType , requestedPolicy) :
    policy = Policy(
        policy_id = "policy_a" , policy_version = 1 ,
        weekday_quota = 1800 , weekend_quota = 1800 ,
        schedule_7x48 = [[True] * 48 for _ in range(7)] , signature = "unsigned"
    )
    server.state.device_tokens["device_a"] = "test_token_a"
    server.state.policies_store["policy_a"] = policy
    server.state.policies_store["policy_b"] = policy.model_copy(
        update = {"policy_id" : "policy_b"}
    )
    server.ensureDeviceDailyQuota("device_a" , "policy_a")
    saveQuota = Mock()
    monkeypatch.setattr(server , "saveQuotaState" , saveQuota)

    def sendRequest() :
        if requestType == "policy" :
            return server.responsePolicy("device_a" , "test_token_a" , requestedPolicy)
        return server.responseHeartbeat(HeartbeatRequest(
            device_id = "device_a" , access_token = "test_token_a" ,
            policy_id = requestedPolicy , dev_status_cur = "active" ,
            quota_used = {"__device__" : 60} , cur_policy_version = 1 ,
            control = ControlState(
                device_quota = 1800 , device_used = 60 ,
                device_quota_date = server.state.device_quota_date_store["device_a"]
            )
        ))

    if requestedPolicy == "policy_a" :
        response = sendRequest()
        if requestType == "policy" :
            assert response.policy_id == "policy_a"
        else :
            assert server.state.device_used_store["device_a"] == 60
    else :
        with pytest.raises(HTTPException) as error :
            sendRequest()
        assert error.value.status_code == 403
        assert server.state.device_states == {}
        assert server.state.device_used_store["device_a"] == 0
        saveQuota.assert_not_called()
    assert server.state.device_policy_store["device_a"] == "policy_a"


def testMachineUuidIsRetriedAfterFailure(monkeypatch) :
    machineUuid = "550e8400-e29b-41d4-a716-446655440000"
    wmi = Mock()
    wmi.ExecQuery.return_value = [Mock(UUID = machineUuid)]
    getWmi = Mock(side_effect = [OSError("WMI unavailable") , wmi])
    monkeypatch.setattr(enrollment.win32com.client , "GetObject" , getWmi)

    assert enrollment.getMachineGuid() == machineUuid
    assert getWmi.call_count == 2


@pytest.mark.parametrize("queryResult" , [[] , [Mock(UUID = "")] , [Mock(UUID = None)]])
def testEmptyMachineUuidIsRetried(monkeypatch , queryResult) :
    machineUuid = "550e8400-e29b-41d4-a716-446655440000"
    wmi = Mock()
    wmi.ExecQuery.side_effect = [queryResult , [Mock(UUID = machineUuid)]]
    monkeypatch.setattr(enrollment.win32com.client , "GetObject" , Mock(return_value = wmi))

    assert enrollment.getMachineGuid() == machineUuid
    assert wmi.ExecQuery.call_count == 2


def testMachineUuidFailureStopsEnrollment(monkeypatch) :
    getWmi = Mock(side_effect = OSError("WMI unavailable"))
    sendEnrollment = Mock()
    monkeypatch.setattr(enrollment.win32com.client , "GetObject" , getWmi)
    monkeypatch.setattr(agent , "getPairingCode" , lambda : "12345678")
    monkeypatch.setattr(agent.httpx , "post" , sendEnrollment)

    with pytest.raises(RuntimeError , match = "UUID") :
        agent.requestEnroll()
    assert getWmi.call_count == 3
    sendEnrollment.assert_not_called()


def test_device_app_web_quota_and_block_reasons() :
    #Khởi tạo Policy mẫu với App/Web bị cấm bởi Policy và App/Web có quota riêng
    agent.state.cur_policy = Policy(
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
    agent.state.quota_used = {"roblox.exe" : 600 , "youtube.com" : 900} #Cả app và web đều đã dùng hết quota gốc
    agent.state.app_bonus_time = {}
    agent.state.web_bonus_time = {}
    agent.state.device_quota = agent.state.device_used + 1800
    agent.state.is_manual_locked = False

    with patch("agent.quota.psutil.process_iter" , return_value = []) :
        #1.Kiểm tra phân biệt nguyên nhân chặn: POLICY vs APP_QUOTA vs WEB_QUOTA
        agent.applyPolicy()
        assert agent.state.dev_status_cur == "active" #Thiết bị vẫn mở khi chỉ hết App/Web Quota
        assert agent.state.device_block_reason == BlockReason.NONE
        assert agent.state.app_block_reasons["banned.exe"] == BlockReason.POLICY
        assert agent.state.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
        assert agent.state.domain_block_reasons["bad.example"] == BlockReason.POLICY
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA
        assert "youtube.com" in agent.state.blocked_domains

        #2.ADD_TIME cho APP: chỉ mở lại roblox.exe, không ảnh hưởng youtube.com hay Policy gốc
        execRequest(Cmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            bonus_time = 300
        ))
        assert agent.state.cur_policy.app_rules[1].quota == 600
        assert agent.state.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA

        #3.ADD_TIME cho WEB: chỉ mở lại youtube.com, giữ nguyên Policy gốc
        execRequest(Cmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            bonus_time = 450
        ))
        assert agent.state.cur_policy.domain_rules[1].quota == 900
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.NONE
        assert "youtube.com" not in agent.state.blocked_domains

        #4.Hết hạn Device-level quota (device_quota <= device_used) -> khóa toàn bộ thiết bị
        agent.state.device_quota = 0
        agent.applyPolicy()
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.DEVICE_QUOTA

        #5.ADD_TIME cho DEVICE -> cập nhật device_quota và mở lại thiết bị
        execRequest(Cmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.DEVICE ,
            bonus_time = 900
        ))
        assert agent.state.dev_status_cur == "active"
        assert agent.state.device_block_reason == BlockReason.NONE

        #6.Ngoài khung giờ Schedule 7x48 -> khóa thiết bị với nguyên nhân SCHEDULE
        agent.state.cur_policy.schedule_7x48 = [[False] * 48 for _ in range(7)]
        agent.applyPolicy()
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.SCHEDULE


def test_agent_restart_and_disconnect_sync(monkeypatch) :
    monkeypatch.setattr(agent.time , "monotonic" , lambda : 10000.0)
    now_ts = int(time.time())
    server.state.current_pairing_code = PairingCode(
        pairing_code = "12345678" , created_at = now_ts , expires_at = now_ts + 600
    )

    #1.Enroll thiết bị
    enrolled = server.responseEnroll(
        EnrollmentRequest(pairing_code = "12345678" , device_fingerprint = "fp_test_01")
    )
    dev_id = enrolled.device_id
    acc_token = enrolled.access_token
    plc_id = enrolled.policy_id
    init_remaining = server.state.device_quota_store[dev_id]
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok

    #2.Giả lập mất kết nối WebSocket khi phụ huynh gửi ADD_TIME cho DEVICE, APP và WEB
    for target , subject , amount in (
        (TargetType.DEVICE , "" , 900) ,
        (TargetType.APP , "roblox.exe" , 600) ,
        (TargetType.WEB , "youtube.com" , 300)
    ) :
        runSyncCoro(server.sendUrgentCmd(
            dev_id , Cmd(cmd_type = CommandType.ADD_TIME , target_type = target ,
                         subject = subject , bonus_time = amount) ,
            parent_token = parent_tok
        ))

    #Kiểm tra Server đã lưu bền vững và không làm thay đổi Policy gốc
    assert server.state.QUOTA_STATE_FILE.exists()
    assert server.state.policies_store[plc_id].weekday_quota == 5400
    server.loadQuotaState()

    #3.Giả lập Agent restart (mất hết biến trong RAM) rồi gửi Heartbeat lên Server để khôi phục
    agent.state.device_id = dev_id
    agent.state.access_token = acc_token
    agent.state.policy_id = plc_id
    agent.state.device_quota = 0
    agent.state.app_bonus_time = {}
    agent.state.web_bonus_time = {}
    agent.state.is_manual_locked = False
    agent.state.cur_policy = server.state.policies_store[plc_id]
    agent.state.device_quota_date = server.state.device_quota_date_store[dev_id]

    with patch("agent.quota.psutil.process_iter" , return_value = []) :
        hb_data = server.responseHeartbeat(makeHeartbeat(reconcile = True))
        drainResponse(hb_data)

    assert max(0 , agent.state.device_quota - agent.state.device_used) == init_remaining + 900
    assert agent.state.app_bonus_time["roblox.exe"] == 600
    assert agent.state.web_bonus_time["youtube.com"] == 300
    assert server.state.device_quota_store[dev_id] == init_remaining + 900
    assert server.state.app_bonus_store[dev_id]["roblox.exe"] == 600
    assert server.state.web_bonus_store[dev_id]["youtube.com"] == 300

    #Dọn file tạm sau khi kiểm thử
    if server.state.QUOTA_STATE_FILE.exists() :
        server.state.QUOTA_STATE_FILE.unlink()


def test_urgent_auth_and_device_validation_s1() :
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok
    server.state.device_tokens["di_valid"] = "at_valid"
    server.state.device_quota_store["di_valid"] = 1800
    cmd = Cmd(cmd_type = CommandType.LOCK)

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
    assert "di_nonexistent" not in server.state.command_sessions

    #3.Cho phép khi parent_token và device_id hợp lệ
    res = runSyncCoro(server.sendUrgentCmd("di_valid" , cmd , parent_token = parent_tok))
    assert res["device_id"] == "di_valid"
    assert res["cmd_type"] == CommandType.LOCK


def test_websocket_cleanup_and_reconnection_s2() :
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok
    dev_id = "di_ws_test"
    acc_tok = "at_ws_test"
    server.state.device_tokens[dev_id] = acc_tok

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
    assert dev_id not in server.state.active_ws_connections

    #2.Kiểm tra kết nối cũ đóng muộn không xóa nhầm kết nối mới hơn của cùng device_id
    ws_newer = DummyServerWS([])
    class LateCleanupWS(DummyServerWS) :
        async def receive_json(self) :
            #Giả lập kết nối mới đã ghi đè vào active_ws_connections trước khi kết nối cũ thoát
            server.state.active_ws_connections[dev_id] = ws_newer
            raise WebSocketDisconnect()

    ws_stale = LateCleanupWS([])
    runSyncCoro(server.urgentWebsocketEndpoint(ws_stale , dev_id , acc_tok))
    assert server.state.active_ws_connections.get(dev_id) is ws_newer

    #3.Kiểm tra sendUrgentCmd tự dọn kết nối stale khi send_json lỗi và fallback sang heartbeat_sync
    ws_newer.fail_send = True
    res = runSyncCoro(server.sendUrgentCmd(
        dev_id ,
        Cmd(cmd_type = CommandType.LOCK) ,
        parent_token = parent_tok
    ))
    assert res["sent"] is False
    assert res["via"] == "heartbeat_sync"
    assert dev_id not in server.state.active_ws_connections

    #4.Kiểm tra Agent UrgentCmdHandler tự kết nối lại với backoff, bỏ qua gói JSON lỗi và chặn chạy trùng
    sleeps : list[float] = []
    sent_acks : list[dict] = []
    connect_calls = 0
    wireCmd = proposeRequest(Cmd(cmd_type = CommandType.LOCK) , reset = True)

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
                HeartbeatResponse(latest_policy_version = 1 , command = wireCmd).model_dump_json()
            ])
        raise ConnectionError("Disconnected after work")

    async def fake_sleep(delay : float) :
        sleeps.append(delay)

    agent.ws_handler_running = False
    with patch("agent.websockets.connect" , side_effect = fake_connect) , patch("agent.asyncio.sleep" , side_effect = fake_sleep) :
        runSyncCoro(agent.UrgentCmdHandler(max_retries = 2 , base_delay = 2.0 , max_delay = 5.0))

    assert connect_calls == 5
    assert sleeps == [2.0 , 4.0 , 2.0 , 4.0] #Tăng theo hàm mũ (2.0 -> 4.0), reset về 2.0 sau khi kết nối lần 3 thành công
    appliedAcks = [message["data"] for message in sent_acks if message["type"] == "ack"]
    assert len(appliedAcks) == 1
    assert appliedAcks[0]["command_seq"] == wireCmd.command_seq
    assert appliedAcks[0]["result"] == "applied"
    assert agent.state.dev_status_cur == "locked"
    assert agent.ws_handler_running is False

    #Kiểm tra chặn khởi chạy trùng khi ws_handler_running đang True
    agent.ws_handler_running = True
    try :
        with patch("agent.websockets.connect" , side_effect = AssertionError("Should not connect")) :
            runSyncCoro(agent.UrgentCmdHandler(max_retries = 0))
    finally :
        agent.ws_handler_running = False
        agent.state.is_manual_locked = False

    if server.state.QUOTA_STATE_FILE.exists() :
        server.state.QUOTA_STATE_FILE.unlink()


def test_manual_lock_preservation_and_shared_cmd_semantics_c1() :
    agent.state.cur_policy = Policy(
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
    agent.state.quota_used = {}
    agent.state.app_bonus_time = {}
    agent.state.web_bonus_time = {}
    agent.state.is_manual_locked = False
    agent.state.device_quota = agent.state.device_used + 1800

    with patch("agent.quota.psutil.process_iter" , return_value = []) :
        #1.Khóa thủ công qua WebSocket (execCmd): bảo toàn khóa khi applyPolicy chạy lại hoặc khi cộng giờ cho App
        execRequest(Cmd(cmd_type = CommandType.LOCK))
        assert agent.state.is_manual_locked is True
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.POLICY

        agent.applyPolicy()
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.POLICY

        execRequest(Cmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            bonus_time = 300
        ))
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.POLICY

        #2.Gỡ khóa thủ công qua WebSocket khi lịch và quota thiết bị đều hợp lệ -> mở khóa máy
        execRequest(Cmd(cmd_type = CommandType.UNLOCK))
        assert agent.state.is_manual_locked is False
        assert agent.state.dev_status_cur == "active"
        assert agent.state.device_block_reason == BlockReason.NONE

        #3.Khóa thủ công qua kênh Heartbeat (pending_commands): dùng chung ngữ nghĩa và giữ khóa qua các nhịp Heartbeat kế tiếp
        lockCmd = proposeRequest(Cmd(cmd_type = CommandType.LOCK) , reset = True)
        lockAck = agent.HeartbeatResponseHanlder(HeartbeatResponse(
            latest_policy_version = 1 , command = lockCmd
        ))
        assert agent.state.is_manual_locked is True
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.POLICY
        assert lockAck.command_seq == lockCmd.command_seq
        assert lockAck.result == "applied"

        #Nhịp Heartbeat tiếp theo (không còn lệnh mới) chạy lại applyPolicy nhưng không được ghi đè khóa thủ công
        agent.HeartbeatResponseHanlder(HeartbeatResponse(latest_policy_version = 1))
        assert agent.state.is_manual_locked is True
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.POLICY

        #4.Gỡ khóa thủ công (UNLOCK) nhưng thiết bị đã hết hạn DEVICE_QUOTA -> không được bỏ qua DEVICE_QUOTA
        agent.state.device_quota = 0
        unlockCmd = proposeRequest(Cmd(cmd_type = CommandType.UNLOCK) , reset = True)
        agent.HeartbeatResponseHanlder(HeartbeatResponse(
            latest_policy_version = 1 , command = unlockCmd
        ))
        assert agent.state.is_manual_locked is False
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.DEVICE_QUOTA

        #5.Khóa thủ công khi đang ngoài khung giờ SCHEDULE, sau đó UNLOCK -> phải giữ nguyên khóa do SCHEDULE
        agent.state.device_quota = agent.state.device_used + 1800
        agent.state.cur_policy.schedule_7x48 = [[False] * 48 for _ in range(7)]
        execRequest(Cmd(cmd_type = CommandType.LOCK))
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.POLICY

        execRequest(Cmd(cmd_type = CommandType.UNLOCK))
        assert agent.state.is_manual_locked is False
        assert agent.state.dev_status_cur == "locked"
        assert agent.state.device_block_reason == BlockReason.SCHEDULE

        #Khi khung giờ SCHEDULE cho phép trở lại -> thiết bị mới chuyển sang active
        agent.state.cur_policy.schedule_7x48 = [[True] * 48 for _ in range(7)]
        agent.applyPolicy()
        assert agent.state.dev_status_cur == "active"
        assert agent.state.device_block_reason == BlockReason.NONE


def test_sub_time_negative_adjustment_and_policy_update_c2() :
    parent_tok = uuid.uuid4().hex
    os.environ["PARENT_TOKEN"] = parent_tok
    dev_id = "di_c2_test"
    acc_tok = "at_c2_test"
    plc_id = "plcid_c2_test"
    server.state.device_tokens[dev_id] = acc_tok
    server.state.device_policy_store[dev_id] = plc_id
    server.state.device_quota_store[dev_id] = 3600
    server.state.app_bonus_store[dev_id] = {}
    server.state.web_bonus_store[dev_id] = {}

    server.state.policies_store[plc_id] = Policy(
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

    agent.state.cur_policy = server.state.policies_store[plc_id].model_copy(deep = True)
    agent.state.device_id = dev_id
    agent.state.access_token = acc_tok
    agent.state.policy_id = plc_id
    agent.state.quota_used = {"roblox.exe" : 100 , "youtube.com" : 100}
    agent.state.app_bonus_time = {}
    agent.state.web_bonus_time = {}
    agent.state.is_manual_locked = False
    agent.state.device_quota = agent.state.device_used + 3600

    with patch("agent.quota.psutil.process_iter" , return_value = []) :
        #1.SUB_TIME vượt bonus hiện có (0s) khiến adjustment âm (-250s) và trừ trực tiếp vào ngân sách quota gốc
        execRequest(Cmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            sub_time = 250
        ))
        execRequest(Cmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            sub_time = 250
        ))
        assert agent.state.app_bonus_time["roblox.exe"] == -250
        assert agent.state.web_bonus_time["youtube.com"] == -250
        #remain = max(0, 600 + (-250) - 100) = 250
        assert agent.state.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.NONE

        #2.SUB_TIME vượt toàn bộ phần còn lại -> adjustment tiếp tục giảm (-650s), nhưng remain được chặn ở 0 (không âm)
        execRequest(Cmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            sub_time = 400
        ))
        execRequest(Cmd(
            cmd_type = CommandType.SUB_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            sub_time = 400
        ))
        assert agent.state.app_bonus_time["roblox.exe"] == -650
        assert agent.state.web_bonus_time["youtube.com"] == -650
        assert agent.state.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA
        assert "youtube.com" in agent.state.blocked_domains

        #3.ADD_TIME sau khi adjustment đang âm (-650 + 300 = -350): tính lại chính xác remain = max(0, 600 - 350 - 100) = 150
        execRequest(Cmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.APP ,
            subject = "roblox.exe" ,
            bonus_time = 300
        ))
        execRequest(Cmd(
            cmd_type = CommandType.ADD_TIME ,
            target_type = TargetType.WEB ,
            subject = "youtube.com" ,
            bonus_time = 300
        ))
        assert agent.state.app_bonus_time["roblox.exe"] == -350
        assert agent.state.web_bonus_time["youtube.com"] == -350
        assert agent.state.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.NONE
        assert "youtube.com" not in agent.state.blocked_domains

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
        assert agent.state.quota_used == {"roblox.exe" : 100 , "youtube.com" : 100}
        assert agent.state.app_bonus_time["roblox.exe"] == -350
        assert agent.state.web_bonus_time["youtube.com"] == -350
        #remain = max(0, 900 - 350 - 100) = 450
        assert agent.state.app_block_reasons["roblox.exe"] == BlockReason.NONE
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.NONE

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
        assert agent.state.quota_used == {"roblox.exe" : 100 , "youtube.com" : 100}
        assert agent.state.app_bonus_time["roblox.exe"] == -350
        assert agent.state.web_bonus_time["youtube.com"] == -350
        #remain = max(0, 400 - 350 - 100) = 0
        assert agent.state.app_block_reasons["roblox.exe"] == BlockReason.APP_QUOTA
        assert agent.state.domain_block_reasons["youtube.com"] == BlockReason.WEB_QUOTA

        #5.Kiểm tra Server persistence & Heartbeat sync bảo toàn adjustment âm cho cả APP và WEB
        server.state.command_sessions.pop(dev_id , None)
        baseline = agent.getControlState().model_copy(update = {
            "app_bonus_time" : {} , "web_bonus_time" : {}
        })
        server.commands.ensureSession(dev_id , plc_id , baseline)
        drainResponse(server.commands.reconcileDevice(dev_id , agent.getControlState()))
        runSyncCoro(server.sendUrgentCmd(
            dev_id ,
            Cmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.APP , subject = "roblox.exe" , sub_time = 200) ,
            parent_token = parent_tok
        ))
        drainResponse(server.commands.getCommandResponse(dev_id))
        runSyncCoro(server.sendUrgentCmd(
            dev_id ,
            Cmd(cmd_type = CommandType.SUB_TIME , target_type = TargetType.WEB , subject = "youtube.com" , sub_time = 200) ,
            parent_token = parent_tok
        ))
        drainResponse(server.commands.getCommandResponse(dev_id))
        server.loadQuotaState()
        assert server.state.app_bonus_store[dev_id]["roblox.exe"] == -200
        assert server.state.web_bonus_store[dev_id]["youtube.com"] == -200

        hb_resp = server.responseHeartbeat(makeHeartbeat(cur_policy_version = 3))
        drainResponse(hb_resp)
        assert agent.state.app_bonus_time["roblox.exe"] == -200
        assert agent.state.web_bonus_time["youtube.com"] == -200

    if server.state.QUOTA_STATE_FILE.exists() :
        server.state.QUOTA_STATE_FILE.unlink()
