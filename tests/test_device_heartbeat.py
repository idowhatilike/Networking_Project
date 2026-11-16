#Kiểm chứng hạn mức và đồng bộ Agent–Server.
import json
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

import agent
import agent.storage
import server
from test_protocol import (
    drainResponse , execRequest , installHttpTransport ,
    proposeRequest , seedAgentSession
)
from shared import clock as vn_clock
from shared.schemas import (
    AppRule,
    BlockReason,
    CmdRequest as Cmd,
    CommandType,
    DomainCategory,
    DomainRule,
    EventType,
    HeartbeatRequest,
    HeartbeatResponse,
    Policy,
    TargetType,
)


@pytest.fixture
def quota_session(monkeypatch, tmp_path):
    clock = {"wall": 1793520000.0, "mono": 10000.0}
    monkeypatch.setattr(agent.time, "time", lambda: clock["wall"])
    monkeypatch.setattr(agent.time, "monotonic", lambda: clock["mono"])
    monkeypatch.setattr(agent.quota.user_input, "getWindowsInputInfo", lambda: None)
    monkeypatch.setattr(agent.quota.psutil, "process_iter", lambda *args: [])
    monkeypatch.setattr(agent, "requestPolicy", lambda: server.state.policies_store[agent.state.policy_id])
    policy = Policy(
        policy_id="policy_hb", policy_version=1,
        weekday_quota=1800, weekend_quota=1800,
        schedule_7x48=[[True] * 48 for _ in range(7)], signature="unsigned",
    )
    for name in (
        "device_tokens", "device_states", "policies_store", "command_sessions",
        "device_quota_store", "device_used_store", "device_quota_date_store",
        "device_policy_store", "app_bonus_store", "web_bonus_store",
        "active_ws_connections",
    ):
        monkeypatch.setattr(server.state, name, {})
    monkeypatch.setattr(server.state, "QUOTA_STATE_FILE", tmp_path / "server_quota.json")
    monkeypatch.setattr(agent.state, "AGENT_STATE_FILE", tmp_path / "agent_quota.json")
    server.state.device_tokens["device_hb"] = "token_hb"
    server.state.policies_store[policy.policy_id] = policy
    server.ensureDeviceDailyQuota("device_hb", policy.policy_id)
    values = {
        "device_id": "device_hb", "access_token": "token_hb",
        "policy_id": policy.policy_id, "cur_policy": policy,
        "device_quota": 1800.0,
        "device_used": 0.0,
        "device_quota_date": vn_clock.getVnNow().strftime("%Y-%m-%d"),
        "last_mono_ts": clock["mono"], "last_wall_ts": clock["wall"],
        "last_input_mono": clock["mono"], "_last_win_input_tick": None,
        "dev_status_cur": "active", "is_manual_locked": False,
        "manual_locked_apps": set(), "manual_locked_domains": set(),
        "quota_used": {}, "app_bonus_time": {}, "web_bonus_time": {},
        "command_seq": 0, "online": False, "event_buffer": [],
        "last_cmd_ack": None, "storage_loaded": True, "needs_sync": True,
        "app_block_reasons": {}, "domain_block_reasons": {}, "blocked_domains": set(),
    }
    for name, value in values.items():
        monkeypatch.setattr(agent.state, name, value)

    installHttpTransport(monkeypatch)
    return clock


def runSyncCoro(coro):
    try:
        coro.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coro.close()


def advance(clock, seconds):
    clock["wall"] += seconds
    clock["mono"] += seconds


@pytest.mark.parametrize("status", ["active", "idle", "locked"])
def test_heartbeat_reports_only_new_active_usage(quota_session, status):
    agent.state.dev_status_cur = status
    agent.state.is_manual_locked = status == "locked"
    if status == "idle":
        agent.state.last_input_mono -= 600
    seedAgentSession(reset = True)
    for step in range(1, 4):
        advance(quota_session, 60)
        response = agent.requestHeartbeat()
        expected_used = 60 * step if status == "active" else 0
        assert server.state.device_quota_store["device_hb"] == 1800
        assert server.state.device_used_store["device_hb"] == expected_used
        agent.HeartbeatResponseHanlder(response)
        assert agent.state.device_quota == 1800
        assert agent.state.device_used == expected_used
        assert agent.state.dev_status_cur == status
        assert "__device__" not in agent.state.quota_used
        agent.HeartbeatResponseHanlder(agent.requestHeartbeat())
        assert server.state.device_used_store["device_hb"] == expected_used


@pytest.mark.parametrize("local_update_during_request", [False, True])
def test_response_delay_is_counted_once(quota_session, monkeypatch, local_update_during_request):
    original_post = agent.httpx.post

    def delayed_post(*args, **kwargs):
        response = original_post(*args, **kwargs)
        advance(quota_session, 2)
        if local_update_during_request:
            agent.applyPolicy()
        return response

    monkeypatch.setattr(agent.httpx, "post", delayed_post)
    advance(quota_session, 60)
    response = agent.requestHeartbeat()
    assert server.state.device_used_store["device_hb"] == 60
    agent.HeartbeatResponseHanlder(response)
    assert agent.state.device_quota == 1800
    assert agent.state.device_used == 62
    monkeypatch.setattr(agent.httpx, "post", original_post)
    agent.HeartbeatResponseHanlder(agent.requestHeartbeat())
    assert server.state.device_used_store["device_hb"] == 62
    assert agent.state.device_used == 62


def test_restart_recovers_quota_and_reported_usage(quota_session):
    advance(quota_session, 60)
    agent.HeartbeatResponseHanlder(agent.requestHeartbeat())
    server.state.device_quota_store.clear()
    server.state.device_used_store.clear()
    advance(quota_session, 600)
    server.loadQuotaState()
    assert server.state.device_quota_store["device_hb"] == 1800
    assert server.state.device_used_store["device_hb"] == 60
    agent.state.cur_policy = None
    agent.state.device_used = 0
    agent.state.last_mono_ts = None
    agent.state.last_wall_ts = None
    agent.state.last_input_mono = None
    response = agent.requestHeartbeat()
    agent.state.cur_policy = server.state.policies_store["policy_hb"]
    agent.HeartbeatResponseHanlder(response)
    assert agent.state.device_used == 60
    advance(quota_session, 30)
    agent.HeartbeatResponseHanlder(agent.requestHeartbeat())
    assert agent.state.device_used == 90


def test_old_cycle_report_and_response_do_not_overwrite_new_day(quota_session):
    oldDate = agent.state.device_quota_date
    oldCmd = proposeRequest(Cmd(cmd_type=CommandType.SUB_TIME, sub_time=1800))
    agent.state.device_used = 1800
    agent.state.dev_status_cur = "locked"
    advance(quota_session, 86400)
    agent.state.last_input_mono = quota_session["mono"]
    ack = agent.execCmd(oldCmd)
    assert ack.result == "not_applied"
    drainResponse(server.commands.acknowledgeCmd("device_hb", ack))
    assert agent.state.device_used == 0
    assert agent.state.device_quota == 1800
    response = server.responseHeartbeat(HeartbeatRequest(
        device_id="device_hb", access_token="token_hb", policy_id="policy_hb",
        dev_status_cur="locked", quota_used={"__device__": 1800},
        cur_policy_version=1, device_quota_date=oldDate,
    ))
    drainResponse(response)
    assert server.state.device_used_store["device_hb"] == 0
    agent.execCmd(oldCmd)
    assert agent.state.device_used == 0
    assert agent.state.device_quota == 1800


def test_zero_quota_is_not_reissued_on_same_day_or_restart(quota_session):
    execRequest(Cmd(cmd_type=CommandType.SUB_TIME, sub_time=2000))
    assert agent.state.dev_status_cur == "locked"
    agent.applyPolicy()
    assert agent.state.device_quota == 0
    assert agent.state.dev_status_cur == "locked"
    agent.storage.saveAgentQuotaState()
    agent.state.device_quota = 1800
    agent.storage.loadAgentQuotaState()
    agent.applyPolicy()
    assert agent.state.device_quota == 0
    assert agent.state.dev_status_cur == "locked"
    server.state.device_quota_store["device_hb"] = 0
    server.saveQuotaState()
    server.state.device_quota_store.clear()
    server.loadQuotaState()
    assert server.state.device_quota_store["device_hb"] == 0


def test_new_day_reset_occurs_once_and_survives_restart(quota_session):
    execRequest(Cmd(cmd_type=CommandType.SUB_TIME, sub_time=2000))
    assert agent.state.device_quota == 0
    advance(quota_session, 86400)
    agent.state.last_input_mono = quota_session["mono"]
    beforeSeq = agent.state.command_seq
    drainResponse(agent.requestHeartbeat())
    assert agent.state.command_seq > beforeSeq
    assert agent.state.device_quota == 1800
    assert agent.state.device_used == 0
    execRequest(Cmd(cmd_type=CommandType.SUB_TIME, sub_time=600))
    server.saveQuotaState()
    server.loadQuotaState()
    drainResponse(agent.requestHeartbeat())
    assert agent.state.device_quota == 1200
    assert server.state.device_quota_store["device_hb"] == 1200


def test_exhaustion_caps_used_and_added_time_is_fully_usable(quota_session):
    agent.state.device_quota = 67
    for _ in range(2):
        advance(quota_session, 60)
        agent.applyPolicy()
    assert agent.state.device_used == 67
    assert agent.state.dev_status_cur == "locked"
    advance(quota_session, 60)
    agent.applyPolicy()
    assert agent.state.device_used == 67
    execRequest(Cmd(cmd_type=CommandType.ADD_TIME, bonus_time=60))
    assert agent.state.device_quota == 127
    assert agent.state.device_used == 67
    assert agent.state.dev_status_cur == "active"


@pytest.mark.parametrize("side", ["agent", "server"])
def test_lower_quota_preserves_used_and_add_covers_the_gap(quota_session, monkeypatch, side):
    sub = Cmd(cmd_type=CommandType.SUB_TIME, sub_time=60)
    add = Cmd(cmd_type=CommandType.ADD_TIME, bonus_time=60)
    if side == "agent":
        agent.state.device_quota = 140
        agent.state.device_used = 100
        execRequest(sub)
        assert agent.state.device_quota == 80
        assert agent.state.device_used == 100
        assert agent.state.dev_status_cur == "locked"
        execRequest(add)
        assert agent.state.device_quota == 160
        assert agent.state.device_used == 100
        assert agent.state.dev_status_cur == "active"
    else:
        monkeypatch.setenv("PARENT_TOKEN", "test-parent")
        server.state.device_quota_store["device_hb"] = 140
        server.state.device_used_store["device_hb"] = 100
        agent.state.device_quota = 140
        agent.state.device_used = 100
        seedAgentSession(reset = True)
        runSyncCoro(server.sendUrgentCmd("device_hb", sub, parent_token="test-parent"))
        drainResponse(server.commands.getCommandResponse("device_hb"))
        assert server.state.device_quota_store["device_hb"] == 80
        assert server.state.device_used_store["device_hb"] == 100
        runSyncCoro(server.sendUrgentCmd("device_hb", add, parent_token="test-parent"))
        drainResponse(server.commands.getCommandResponse("device_hb"))
        assert server.state.device_quota_store["device_hb"] == 160
        assert server.state.device_used_store["device_hb"] == 100


def test_wall_clock_skew_and_reboot_do_not_consume_quota(quota_session):
    advance(quota_session, 120)
    agent.applyPolicy()
    quota_session["wall"] -= 10800
    advance(quota_session, 60)
    agent.state.last_input_mono = quota_session["mono"]
    agent.applyPolicy()
    assert agent.state.device_used == 180
    assert any(event.type == EventType.QUOTA_WARNING and event.subject == "Giờ hệ thống lệch lùi" for event in agent.state.event_buffer)
    agent.storage.saveAgentQuotaState()
    quota_session["mono"] = 5
    advance(quota_session, 30)
    agent.storage.loadAgentQuotaState()
    agent.applyPolicy()
    assert agent.state.device_used == 180
    advance(quota_session, 20)
    agent.applyPolicy()
    assert agent.state.device_used == 200


def test_idle_input_and_manual_lock_keep_usage_consistent(quota_session, monkeypatch):
    tick = [1000]
    monkeypatch.setattr(agent.quota.user_input, "getWindowsInputInfo", lambda: (tick[0], 0))
    agent.applyPolicy()
    advance(quota_session, 100)
    tick[0] += 100000
    agent.applyPolicy()
    assert agent.state.device_used == 100
    advance(quota_session, 305)
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "idle"
    assert agent.state.device_used == 100
    advance(quota_session, 600)
    agent.applyPolicy()
    assert agent.state.device_used == 100
    tick[0] += 5000
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "active"
    advance(quota_session, 50)
    execRequest(Cmd(cmd_type=CommandType.LOCK))
    assert agent.state.device_used == 150
    advance(quota_session, 400)
    tick[0] += 20000
    agent.applyPolicy()
    assert agent.state.device_used == 150
    assert agent.state.device_block_reason == BlockReason.POLICY
    execRequest(Cmd(cmd_type=CommandType.UNLOCK))
    advance(quota_session, 30)
    agent.applyPolicy()
    assert agent.state.device_used == 180


def test_heartbeat_loop_accounts_before_failed_request(quota_session, monkeypatch):
    advance(quota_session, 60)
    post = Mock(side_effect=agent.httpx.ConnectError("offline"))
    monkeypatch.setattr(agent.httpx, "post", post)
    monkeypatch.setattr(agent.time, "sleep", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        agent.requestHeartbeatLoop()
    post.assert_called_once()
    assert post.call_args.kwargs["json"]["quota_used"]["__device__"] == 60
    assert agent.state.device_used == 60


@pytest.mark.parametrize("legacy", ["remaining", "deadline"])
@pytest.mark.parametrize("remaining", [0, 900])
def test_server_migrates_old_quota_files(quota_session, legacy, remaining):
    key = "device_remaining" if legacy == "remaining" else "device_unlocked"
    value = remaining if legacy == "remaining" else int(quota_session["wall"]) + remaining if remaining else 0
    server.state.QUOTA_STATE_FILE.write_text(json.dumps({
        key: {"device_hb": value}, "device_used": {"device_hb": 60},
        "device_quota_date": {"device_hb": agent.state.device_quota_date},
    }), encoding="utf-8")
    if legacy == "deadline":
        with pytest.warns(RuntimeWarning, match="Migrating legacy"):
            server.loadQuotaState()
    else:
        server.loadQuotaState()
    assert server.state.device_quota_store["device_hb"] == remaining + 60
    assert server.state.device_used_store["device_hb"] == 60
    saved = json.loads(server.state.QUOTA_STATE_FILE.read_text(encoding="utf-8"))
    assert saved["device_quota"]["device_hb"] == remaining + 60
    assert key not in saved


def test_agent_migrates_old_remaining_and_restores_app_web_usage(quota_session):
    agent.state.AGENT_STATE_FILE.write_text(json.dumps({
        "device_quota_date": agent.state.device_quota_date,
        "device_remaining_sec": 900, "device_quota_used": 60,
        "is_manual_locked": True,
    }), encoding="utf-8")
    agent.storage.loadAgentQuotaState()
    assert agent.state.device_quota == 960
    assert agent.state.device_used == 60
    agent.state.quota_used = {"notepad.exe": 10, "example.com": 20}
    agent.storage.saveAgentQuotaState()
    agent.state.quota_used = {}
    agent.storage.loadAgentQuotaState()
    assert agent.state.quota_used == {"notepad.exe": 10, "example.com": 20}
    assert agent.state.is_manual_locked


def test_heartbeat_lock_is_applied_once_until_acked(quota_session, monkeypatch):
    cmd = proposeRequest(Cmd(cmd_type=CommandType.LOCK))
    response = HeartbeatResponse(latest_policy_version=1, command=cmd)
    first = agent.HeartbeatResponseHanlder(response)
    duplicate = agent.HeartbeatResponseHanlder(response)
    assert first == duplicate
    assert agent.state.command_seq == cmd.command_seq
    assert agent.state.is_manual_locked
    assert server.commands.getCommandResponse("device_hb").command is not None
    server.commands.acknowledgeCmd("device_hb", duplicate)
    assert server.commands.getCommandResponse("device_hb").command is None


def test_invalid_response_keeps_pending_acks(quota_session, monkeypatch):
    ack = agent.execCmd(proposeRequest(Cmd(cmd_type=CommandType.LOCK)))
    monkeypatch.setattr(agent.httpx, "post", lambda *args, **kwargs: Mock(
        raise_for_status=Mock(), json=dict
    ))
    with pytest.raises(ValueError):
        agent.requestHeartbeat()
    assert agent.state.last_cmd_ack == ack


@pytest.mark.parametrize("date,expected", [("2026-10-30", 1200), ("2026-10-31", 2400)])
def test_daily_reset_selects_weekday_or_weekend_quota(quota_session, date, expected):
    agent.state.cur_policy.weekday_quota = 1200
    agent.state.cur_policy.weekend_quota = 2400
    server.state.policies_store["policy_hb"] = agent.state.cur_policy
    now = datetime.fromisoformat(date).replace(hour=12, tzinfo=vn_clock.VN_TZ)
    quota_session["wall"] = now.timestamp()
    oldDate = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    agent.state.device_quota_date = oldDate
    agent.state.device_quota = 0
    agent.state.last_mono_ts = quota_session["mono"]
    server.state.command_sessions.clear()
    seedAgentSession()
    beforeSeq = agent.state.command_seq
    drainResponse(agent.requestHeartbeat())
    assert agent.state.device_quota == expected
    assert server.state.device_quota_store["device_hb"] == expected
    assert agent.state.command_seq > beforeSeq
    assert agent.state.device_used == 0


def test_manual_unlock_without_policy_preserves_command_behavior(quota_session):
    agent.state.cur_policy = None
    execRequest(Cmd(cmd_type=CommandType.LOCK))
    assert agent.state.is_manual_locked
    assert agent.state.dev_status_cur == "locked"
    execRequest(Cmd(cmd_type=CommandType.UNLOCK))
    assert not agent.state.is_manual_locked
    assert agent.state.dev_status_cur == "active"


def test_heartbeat_openapi_uses_quota_used_schema():
    schema = server.app.openapi()
    properties = schema["components"]["schemas"]["HeartbeatResponse"]["properties"]
    assert {"command", "reconcile"} <= properties.keys()
    assert "device_quota" not in properties
    cmdProperties = schema["components"]["schemas"]["Cmd"]["properties"]
    assert {"command_seq", "device_quota", "device_used"} <= cmdProperties.keys()
    assert "/api/v1/command-ack" in schema["paths"]


def test_startup_uses_existing_windows_idle(quota_session, monkeypatch):
    agent.state.last_input_mono = None
    monkeypatch.setattr(agent.quota.user_input, "getWindowsInputInfo", lambda: (1234, 600))
    advance(quota_session, 60)
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "idle"
    assert agent.state.device_used == 0
    advance(quota_session, 60)
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "idle"
    assert agent.state.device_used == 0


@pytest.mark.parametrize("has_policy", [False, True])
@pytest.mark.parametrize("command_type", list(CommandType))
def test_commands_keep_idle_until_new_input(quota_session, monkeypatch, has_policy, command_type):
    agent.state.dev_status_cur = "idle"
    agent.state.last_input_mono = None
    if not has_policy:
        agent.state.cur_policy = None
    execRequest(Cmd(cmd_type=command_type, bonus_time=60, sub_time=60))
    if command_type == CommandType.LOCK:
        assert agent.state.dev_status_cur == "locked"
        execRequest(Cmd(cmd_type=CommandType.UNLOCK))
    assert agent.state.dev_status_cur == "idle"
    advance(quota_session, 60)
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "idle"
    assert agent.state.device_used == 0
    monkeypatch.setattr(agent.quota.user_input, "getWindowsInputInfo", lambda: (5678, 0))
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "active"
    assert agent.state.device_used == 0


def test_input_clock_reset_keeps_idle_without_windows_info(quota_session):
    agent.state.dev_status_cur = "idle"
    agent.state.last_input_mono = quota_session["mono"] + 100
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "idle"
    assert agent.state.device_used == 0


@pytest.mark.parametrize("target,subject", [(TargetType.APP, "notepad.exe"), (TargetType.WEB, "example.com")])
@pytest.mark.parametrize("has_policy", [False, True])
def test_subject_lock_survives_policy_and_storage_without_locking_device(quota_session, monkeypatch, target, subject, has_policy):
    if not has_policy:
        agent.state.cur_policy = None
    process = Mock(info={"name": "notepad.exe"})
    monkeypatch.setattr(agent.quota.psutil, "process_iter", lambda *args: [process])
    execRequest(Cmd(cmd_type=CommandType.LOCK, target_type=target, subject=f" {subject.upper()} "))
    assert not agent.state.is_manual_locked
    assert agent.state.dev_status_cur == "active"
    agent.applyPolicy()
    agent.storage.saveAgentQuotaState()
    agent.state.manual_locked_apps.clear()
    agent.state.manual_locked_domains.clear()
    agent.storage.loadAgentQuotaState()
    agent.applyPolicy()
    if target == TargetType.APP:
        assert agent.state.app_block_reasons[subject] == BlockReason.POLICY
        assert subject in agent.state.manual_locked_apps
        assert process.kill.called
    else:
        assert subject in agent.state.blocked_domains
        assert agent.state.domain_block_reasons[subject] == BlockReason.POLICY
    process.kill.reset_mock()
    unlockCmd = proposeRequest(Cmd(
        cmd_type=CommandType.UNLOCK, target_type=target, subject=subject
    ))
    process.kill.reset_mock()
    ack = agent.execCmd(unlockCmd)
    drainResponse(server.commands.acknowledgeCmd(agent.state.device_id, ack))
    agent.applyPolicy()
    assert not agent.state.manual_locked_apps
    assert not agent.state.manual_locked_domains
    assert subject not in agent.state.blocked_domains
    assert subject not in agent.state.app_block_reasons
    assert subject not in agent.state.domain_block_reasons
    if target == TargetType.APP:
        process.kill.assert_called_once()
    else:
        process.kill.assert_not_called()


@pytest.mark.parametrize("target,subject", [(TargetType.APP, "notepad.exe"), (TargetType.WEB, "example.com")])
@pytest.mark.parametrize("allowed,used,reason", [(False, 0, BlockReason.POLICY), (True, 60, None), (True, 0, BlockReason.NONE)])
def test_subject_unlock_still_applies_policy_and_quota(quota_session, target, subject, allowed, used, reason):
    if target == TargetType.APP:
        agent.state.cur_policy.app_rules = [AppRule(exe_name=subject, sha256="", allowed=allowed, quota=60)]
    else:
        agent.state.cur_policy.domain_rules = [DomainRule(domain=subject, category=DomainCategory.UNCATEGORIZED, allowed=allowed, quota=60)]
    agent.state.quota_used[subject] = used
    execRequest(Cmd(cmd_type=CommandType.LOCK, target_type=target, subject=subject))
    agent.state.cur_policy = agent.state.cur_policy.model_copy(deep=True)
    agent.applyPolicy()
    execRequest(Cmd(cmd_type=CommandType.UNLOCK, target_type=target, subject=subject))
    reasons = agent.state.app_block_reasons if target == TargetType.APP else agent.state.domain_block_reasons
    quota_reason = BlockReason.APP_QUOTA if target == TargetType.APP else BlockReason.WEB_QUOTA
    assert reasons[subject] == (quota_reason if reason is None else reason)
    assert agent.state.dev_status_cur == "active"


@pytest.mark.parametrize("target,subject", [(TargetType.APP, "notepad.exe"), (TargetType.WEB, "example.com")])
def test_heartbeat_keeps_target_and_distinguishes_commands(quota_session, monkeypatch, target, subject):
    monkeypatch.setenv("PARENT_TOKEN", "test-parent-token")
    for commandType in (CommandType.LOCK, CommandType.UNLOCK, CommandType.LOCK):
        runSyncCoro(server.sendUrgentCmd(
            "device_hb", Cmd(cmd_type=commandType, target_type=target, subject=subject),
            parent_token="test-parent-token",
        ))
    session = server.state.command_sessions["device_hb"]
    assert len(session["queue"]) == 3
    beforeSeq = agent.state.command_seq
    agent.drainResponses(agent.requestHeartbeat())
    assert agent.state.command_seq == beforeSeq + 3
    locked = agent.state.manual_locked_apps if target == TargetType.APP else agent.state.manual_locked_domains
    assert subject in locked
    assert agent.state.dev_status_cur == "active"
    assert not session["queue"]


@pytest.mark.parametrize("target", [TargetType.APP, TargetType.WEB])
@pytest.mark.parametrize("command_type", list(CommandType))
def test_subject_commands_require_nonempty_subject(target, command_type):
    with pytest.raises(ValueError, match="subject"):
        Cmd(cmd_type=command_type, target_type=target, subject="   ")


def test_unknown_heartbeat_command_is_not_acked(quota_session):
    with pytest.raises(ValueError):
        HeartbeatResponse.model_validate({
            "latest_policy_version": 1, "command": {"command_seq": 1, "cmd_type": "unknown"}
        })
    assert agent.state.last_cmd_ack is None
    assert agent.state.command_seq == 0


def test_device_and_subject_locks_are_independent(quota_session):
    for target, subject in ((TargetType.DEVICE, ""), (TargetType.APP, "notepad.exe"), (TargetType.WEB, "example.com")):
        execRequest(Cmd(cmd_type=CommandType.LOCK, target_type=target, subject=subject))
    execRequest(Cmd(cmd_type=CommandType.UNLOCK, target_type=TargetType.APP, subject="notepad.exe"))
    assert agent.state.dev_status_cur == "locked"
    assert not agent.state.manual_locked_apps
    assert agent.state.manual_locked_domains == {"example.com"}
    execRequest(Cmd(cmd_type=CommandType.UNLOCK))
    assert agent.state.dev_status_cur == "active"
    assert agent.state.blocked_domains == {"example.com"}


@pytest.mark.parametrize("reason", [BlockReason.SCHEDULE, BlockReason.DEVICE_QUOTA])
def test_missing_policy_keeps_existing_restriction(quota_session, reason):
    agent.state.cur_policy = None
    agent.state.dev_status_cur = "locked"
    agent.state.device_block_reason = reason
    agent.applyPolicy()
    assert agent.state.dev_status_cur == "locked"
    assert agent.state.device_block_reason == reason


@pytest.mark.parametrize("offset_sec", [-300, -31, -30, 0, 30, 31, 300])
@pytest.mark.parametrize("locked", [False, True])
def test_clock_offset_direction_and_threshold(quota_session, offset_sec, locked):
    agent.state.is_manual_locked = locked
    if locked:
        agent.state.dev_status_cur = "locked"
    quota_session["wall"] += offset_sec
    advance(quota_session, 60)
    agent.applyPolicy()
    assert agent.state.device_used == (0 if locked else 60)
    if abs(offset_sec) > 30:
        assert len(agent.state.event_buffer) == 1
        event = agent.state.event_buffer[0]
        assert event.subject == ("Giờ hệ thống lệch tiến" if offset_sec > 0 else "Giờ hệ thống lệch lùi")
        assert event.duration_sec == abs(offset_sec)
        agent.applyPolicy()
        assert len(agent.state.event_buffer) == 1
    else:
        assert not agent.state.event_buffer
