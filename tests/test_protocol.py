from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
import json

import pytest
from fastapi import HTTPException , WebSocketDisconnect

import agent
import agent.storage
import server
from shared import clock as vn_clock
from shared.schemas import (
    CmdAck , CmdRequest , CommandType , HeartbeatRequest ,
    HeartbeatResponse , Policy , TargetType
)


def runSyncCoro(coro) :
    try :
        coro.send(None)
    except StopIteration as result :
        return result.value
    finally :
        coro.close()


def seedAgentSession(reset = False) :
    deviceId = agent.state.device_id or "device_local"
    policy = agent.state.cur_policy or Policy(
        policy_id = "policy_local" , policy_version = 1 ,
        weekday_quota = 1800 , weekend_quota = 1800 ,
        schedule_7x48 = [[True] * 48 for _ in range(7)] , signature = "unsigned"
    )
    agent.state.device_id = deviceId
    agent.state.access_token = agent.state.access_token or "test-token"
    agent.state.policy_id = policy.policy_id
    if not agent.state.device_quota_date :
        agent.state.device_quota_date = vn_clock.getVnNow().strftime("%Y-%m-%d")
    server.state.device_tokens[deviceId] = agent.state.access_token
    server.state.policies_store[policy.policy_id] = policy
    server.state.device_policy_store[deviceId] = policy.policy_id
    if reset :
        server.state.command_sessions.pop(deviceId , None)
    server.commands.ensureSession(deviceId , policy.policy_id , agent.getControlState())
    return deviceId


def makeHeartbeat(**updates) :
    data = {
        "device_id" : agent.state.device_id , "access_token" : agent.state.access_token ,
        "policy_id" : agent.state.policy_id , "dev_status_cur" : agent.state.dev_status_cur ,
        "quota_used" : {**agent.state.quota_used , "__device__" : int(agent.state.device_used)} ,
        "cur_policy_version" : (
            agent.state.cur_policy.policy_version if agent.state.cur_policy is not None else 0
        ) ,
        "device_quota_date" : agent.state.device_quota_date ,
        "control" : agent.getControlState()
    }
    data.update(updates)
    return HeartbeatRequest(**data)


def drainResponse(response) :
    for _ in range(50) :
        ack = agent.HeartbeatResponseHanlder(response)
        if ack is None :
            return response
        response = server.commands.acknowledgeCmd(agent.state.device_id , ack)
    raise AssertionError("Hàng lệnh không kết thúc trong 50 bước")


def proposeRequest(request , reset = False) :
    agent.applyPolicy()
    deviceId = seedAgentSession(reset = reset)
    drainResponse(server.commands.reconcileDevice(deviceId , agent.getControlState()))
    server.commands.enqueueCmd(deviceId , request)
    response = server.commands.getCommandResponse(deviceId)
    assert response.command is not None
    return response.command


def execRequest(request) :
    cmd = proposeRequest(request , reset = True)
    ack = agent.execCmd(cmd)
    drainResponse(server.commands.acknowledgeCmd(agent.state.device_id , ack))
    return ack


def installHttpTransport(monkeypatch) :
    def post(url , * , json , timeout , params = None) :
        if url.endswith("/command-ack") :
            response = server.commands.acknowledgeCmd(
                params["device_id"] , CmdAck.model_validate(json)
            )
        else :
            response = server.responseHeartbeat(HeartbeatRequest.model_validate(json))
        return Mock(raise_for_status = Mock() , json = lambda : response.model_dump(mode = "json"))

    monkeypatch.setattr(agent.httpx , "post" , post)


@pytest.fixture
def protocol_session(monkeypatch , tmp_path) :
    testClock = {"wall" : 1793520000.0 , "mono" : 10000.0}
    monkeypatch.setattr(agent.time , "time" , lambda : testClock["wall"])
    monkeypatch.setattr(agent.time , "monotonic" , lambda : testClock["mono"])
    monkeypatch.setattr(agent.quota.user_input , "getWindowsInputInfo" , lambda : None)
    monkeypatch.setattr(agent.quota.psutil , "process_iter" , lambda *args : [])
    monkeypatch.setattr(
        agent , "requestPolicy" , lambda : server.state.policies_store[agent.state.policy_id]
    )
    for name in (
        "device_tokens" , "device_states" , "policies_store" , "command_sessions" ,
        "device_quota_store" , "device_used_store" , "device_quota_date_store" ,
        "device_policy_store" , "app_bonus_store" , "web_bonus_store" ,
        "active_ws_connections"
    ) :
        monkeypatch.setattr(server.state , name , {})
    monkeypatch.setattr(server.state , "QUOTA_STATE_FILE" , tmp_path / "server_quota.json")
    monkeypatch.setattr(agent.state , "AGENT_STATE_FILE" , tmp_path / "agent_quota.json")
    policy = Policy(
        policy_id = "policy_hb" , policy_version = 1 , weekday_quota = 1800 ,
        weekend_quota = 1800 , schedule_7x48 = [[True] * 48 for _ in range(7)] ,
        signature = "unsigned"
    )
    values = {
        "device_id" : "device_hb" , "access_token" : "token_hb" ,
        "policy_id" : policy.policy_id , "cur_policy" : policy , "command_seq" : 0 ,
        "device_quota" : 1800.0 , "device_used" : 0.0 ,
        "device_quota_date" : vn_clock.getVnNow().strftime("%Y-%m-%d") ,
        "last_mono_ts" : testClock["mono"] , "last_wall_ts" : testClock["wall"] ,
        "last_input_mono" : testClock["mono"] , "_last_win_input_tick" : None ,
        "dev_status_cur" : "active" , "is_manual_locked" : False ,
        "manual_locked_apps" : set() , "manual_locked_domains" : set() ,
        "quota_used" : {} , "app_bonus_time" : {} , "web_bonus_time" : {} ,
        "event_buffer" : [] , "app_block_reasons" : {} , "domain_block_reasons" : {} ,
        "blocked_domains" : set() , "online" : True , "needs_sync" : True ,
        "storage_loaded" : True , "last_cmd_ack" : None
    }
    for name , value in values.items() :
        monkeypatch.setattr(agent.state , name , value)
    seedAgentSession()
    drainResponse(server.commands.reconcileDevice("device_hb" , agent.getControlState()))
    installHttpTransport(monkeypatch)
    monkeypatch.setenv("PARENT_TOKEN" , "audit-parent")
    return testClock


def captureWs(monkeypatch) :
    messages = []

    async def sendJson(payload) :
        messages.append(HeartbeatResponse.model_validate(payload))

    server.state.active_ws_connections["device_hb"] = Mock(send_json = sendJson)
    return messages


def sendCmd(request) :
    return runSyncCoro(server.sendUrgentCmd(
        "device_hb" , request , parent_token = "audit-parent"
    ))


def heartbeat() :
    return drainResponse(agent.requestHeartbeat())


def isManuallyLocked(target , subject) :
    if target == TargetType.DEVICE :
        return agent.state.is_manual_locked
    if target == TargetType.APP :
        return subject in agent.state.manual_locked_apps
    return subject in agent.state.manual_locked_domains


@pytest.mark.parametrize("target,subject" , [
    (TargetType.DEVICE , "") , (TargetType.APP , "notepad.exe") ,
    (TargetType.WEB , "example.com")
])
@pytest.mark.parametrize("commandType" , [CommandType.ADD_TIME , CommandType.SUB_TIME])
def testOneAdjustmentMustNotApplyTwice(protocol_session , monkeypatch , target , subject ,
                                     commandType) :
    agent.state.device_quota = 120
    agent.state.device_used = 20
    seedAgentSession(reset = True)
    drainResponse(server.commands.reconcileDevice("device_hb" , agent.getControlState()))
    messages = captureWs(monkeypatch)
    request = CmdRequest(
        cmd_type = commandType , target_type = target , subject = subject ,
        bonus_time = 60 , sub_time = 60
    )
    sendCmd(request)
    first = server.commands.getCommandResponse("device_hb")
    ack = agent.HeartbeatResponseHanlder(first)
    duplicateAck = agent.HeartbeatResponseHanlder(messages[0])
    assert duplicateAck.command_seq == ack.command_seq
    drainResponse(server.commands.acknowledgeCmd("device_hb" , ack))
    if target == TargetType.DEVICE :
        expected = 180 if commandType == CommandType.ADD_TIME else 60
        assert agent.state.device_quota == expected
        assert server.state.device_quota_store["device_hb"] == expected
    else :
        expected = 60 if commandType == CommandType.ADD_TIME else -60
        agentBonus = agent.state.app_bonus_time if target == TargetType.APP else (
            agent.state.web_bonus_time
        )
        assert agentBonus[subject] == expected


@pytest.mark.parametrize("target,subject" , [
    (TargetType.DEVICE , "") , (TargetType.APP , "notepad.exe") ,
    (TargetType.WEB , "example.com")
])
@pytest.mark.parametrize("oldType" , [CommandType.LOCK , CommandType.UNLOCK])
def testOldQueuedLockMustNotOverrideNewWsCommand(protocol_session , monkeypatch , target ,
                                               subject , oldType) :
    if oldType == CommandType.UNLOCK :
        execRequest(CmdRequest(cmd_type = CommandType.LOCK , target_type = target ,
                               subject = subject))
    sendCmd(CmdRequest(cmd_type = oldType , target_type = target , subject = subject))
    oldResponse = server.commands.getCommandResponse("device_hb")
    captureWs(monkeypatch)
    newType = CommandType.UNLOCK if oldType == CommandType.LOCK else CommandType.LOCK
    sendCmd(CmdRequest(cmd_type = newType , target_type = target , subject = subject))
    ack = agent.HeartbeatResponseHanlder(oldResponse)
    response = server.commands.acknowledgeCmd("device_hb" , ack)
    drainResponse(response)
    agent.HeartbeatResponseHanlder(oldResponse)
    assert isManuallyLocked(target , subject) == (newType == CommandType.LOCK)


@pytest.mark.parametrize("target,subject" , [
    (TargetType.DEVICE , "") , (TargetType.APP , "notepad.exe") ,
    (TargetType.WEB , "example.com")
])
@pytest.mark.parametrize("commandType" , [CommandType.LOCK , CommandType.UNLOCK])
def testUnreceivedWsLockMustRemainDeliverable(protocol_session , monkeypatch , target ,
                                           subject , commandType) :
    if commandType == CommandType.UNLOCK :
        execRequest(CmdRequest(cmd_type = CommandType.LOCK , target_type = target ,
                               subject = subject))
    captureWs(monkeypatch)
    sendCmd(CmdRequest(cmd_type = commandType , target_type = target , subject = subject))
    assert server.commands.getCommandResponse("device_hb").command is not None
    heartbeat()
    assert isManuallyLocked(target , subject) == (commandType == CommandType.LOCK)
    assert server.commands.getCommandResponse("device_hb").command is None


@pytest.mark.parametrize("target,subject" , [
    (TargetType.APP , "notepad.exe") , (TargetType.WEB , "example.com")
])
def testEmptyServerBonusMustClearOldAgentBonus(protocol_session , target , subject) :
    agentBonus = agent.state.app_bonus_time if target == TargetType.APP else (
        agent.state.web_bonus_time
    )
    agentBonus[subject] = -60
    response = server.commands.reconcileDevice("device_hb" , agent.getControlState())
    drainResponse(response)
    currentBonus = agent.state.app_bonus_time if target == TargetType.APP else (
        agent.state.web_bonus_time
    )
    assert currentBonus == {}


def testAddedTimeMustBeFullyUsableAfterQuotaLowered(protocol_session) :
    agent.state.device_quota = 80
    agent.state.device_used = 100
    seedAgentSession(reset = True)
    server.state.device_used_store["device_hb"] = 60
    server.state.command_sessions["device_hb"]["control"]["device_used"] = 60
    sendCmd(CmdRequest(cmd_type = CommandType.ADD_TIME , bonus_time = 60))
    proposal = server.commands.getCommandResponse("device_hb").command
    assert proposal.device_used == 60
    assert proposal.device_quota == 140
    heartbeat()
    assert max(0 , agent.state.device_quota - agent.state.device_used) == 60
    assert server.state.device_quota_store["device_hb"] == 160


def testAckMustReturnAndPushNextCommand(protocol_session , monkeypatch) :
    messages = captureWs(monkeypatch)
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    sendCmd(CmdRequest(cmd_type = CommandType.UNLOCK))
    first = server.commands.getCommandResponse("device_hb").command
    ack = agent.execCmd(first)
    assert ack.dev_status_cur == "locked"
    response = runSyncCoro(server.responseCommandAck("device_hb" , "token_hb" , ack))
    assert server.state.device_states["device_hb"]["dev_status_cur"] == "locked"
    assert response.command.command_seq == first.command_seq + 1
    assert response.command.cmd_type == CommandType.UNLOCK
    assert messages[-1].command == response.command
    drainResponse(response)
    assert not agent.state.is_manual_locked


def testHeartbeatDrainsEveryCommandWithoutSleeping(protocol_session , monkeypatch) :
    for kind in (CommandType.LOCK , CommandType.UNLOCK , CommandType.ADD_TIME) :
        sendCmd(CmdRequest(cmd_type = kind , bonus_time = 60))
    post = Mock(wraps = agent.httpx.post)
    monkeypatch.setattr(agent.httpx , "post" , post)
    sleep = Mock(side_effect = AssertionError("Không được chờ Heartbeat tiếp theo"))
    monkeypatch.setattr(agent.time , "sleep" , sleep)
    agent.drainResponses(agent.requestHeartbeat())
    assert sum(call.args[0].endswith("/command-ack") for call in post.call_args_list) == 3
    assert agent.state.command_seq == 3
    assert not server.state.command_sessions["device_hb"]["queue"]
    sleep.assert_not_called()


def testWsAckPushesNextWithoutHeartbeat(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    sendCmd(CmdRequest(cmd_type = CommandType.UNLOCK))
    first = server.commands.getCommandResponse("device_hb").command
    ack = agent.execCmd(first)
    messages = []
    incoming = [{"type" : "ack" , "data" : ack.model_dump(mode = "json")}]

    async def accept() :
        return None

    async def receive() :
        if not incoming :
            raise WebSocketDisconnect()
        return incoming.pop(0)

    async def send(payload) :
        messages.append(HeartbeatResponse.model_validate(payload))

    websocket = Mock(accept = accept , receive_json = receive , send_json = send)
    runSyncCoro(server.urgentWebsocketEndpoint(websocket , "device_hb" , "token_hb"))
    assert messages[0].command.command_seq == first.command_seq + 1
    assert messages[0].command.cmd_type == CommandType.UNLOCK


def testGapReconcilesAndContinues(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    cmd = server.commands.getCommandResponse("device_hb").command
    gap = cmd.model_copy(update = {"command_seq" : 4})
    ack = agent.execCmd(gap)
    assert ack.result == "resync"
    assert agent.state.command_seq == 0
    response = server.commands.acknowledgeCmd("device_hb" , ack)
    assert response.reconcile is not None
    drainResponse(response)
    assert agent.state.command_seq == 1
    assert agent.state.is_manual_locked


def testRetryIdDoesNotCreateAnotherOperation(protocol_session) :
    request = CmdRequest(request_id = "same-request" , cmd_type = CommandType.ADD_TIME ,
                         bonus_time = 60)
    sendCmd(request)
    sendCmd(request)
    session = server.state.command_sessions["device_hb"]
    assert len(session["queue"]) == 1
    with pytest.raises(HTTPException) as error :
        sendCmd(request.model_copy(update = {"bonus_time" : 120}))
    assert error.value.status_code == 409
    heartbeat()
    assert agent.state.device_quota == 1860


def testConcurrentReceiversApplyOnlyOnce(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.ADD_TIME , bonus_time = 60))
    cmd = server.commands.getCommandResponse("device_hb").command
    with ThreadPoolExecutor(max_workers = 2) as executor :
        acks = list(executor.map(agent.execCmd , [cmd , cmd]))
    assert acks[0] == acks[1]
    assert agent.state.device_quota == 1860
    assert agent.state.command_seq == 1


def testConcurrentRequestsKeepSequenceAndQueue(protocol_session) :
    requests = [CmdRequest(cmd_type = CommandType.ADD_TIME , bonus_time = 60)
                for _ in range(4)]
    with ThreadPoolExecutor(max_workers = 4) as executor :
        list(executor.map(lambda request : server.commands.enqueueCmd("device_hb" , request) ,
                          requests))
    heartbeat()
    assert agent.state.device_quota == 2040
    assert agent.state.command_seq == 4


def testFractionalUsedCorrectionAndAck(protocol_session) :
    agent.state.device_quota = 80
    agent.state.device_used = 100.75
    seedAgentSession(reset = True)
    session = server.state.command_sessions["device_hb"]
    session["control"]["device_used"] = 60.25
    sendCmd(CmdRequest(cmd_type = CommandType.ADD_TIME , bonus_time = 60))
    cmd = server.commands.getCommandResponse("device_hb").command
    assert cmd.device_quota == 140
    assert cmd.device_used == 60.25
    ack = agent.execCmd(cmd)
    assert ack.device_quota == 160.75
    assert ack.device_used == 100.75
    response = server.commands.acknowledgeCmd("device_hb" , ack)
    assert response.command is None
    assert server.state.device_quota_store["device_hb"] == 160.75
    assert agent.execCmd(cmd) == ack
    assert agent.state.device_quota - agent.state.device_used == 60


def testRestartAfterApplyBeforeAckDoesNotAddAgain(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.ADD_TIME , bonus_time = 60))
    cmd = server.commands.getCommandResponse("device_hb").command
    ack = agent.execCmd(cmd)
    agent.state.command_seq = 0
    agent.state.device_quota = 0
    agent.state.last_cmd_ack = None
    agent.storage.loadAgentQuotaState()
    assert agent.state.last_cmd_ack == ack
    heartbeat()
    assert agent.state.device_quota == 1860
    assert not server.state.command_sessions["device_hb"]["queue"]


def testServerRestartKeepsPendingCommand(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    sendCmd(CmdRequest(cmd_type = CommandType.UNLOCK))
    first = server.commands.getCommandResponse("device_hb").command
    server.state.command_sessions.clear()
    server.loadQuotaState()
    assert server.commands.getCommandResponse("device_hb").command == first
    heartbeat()
    assert agent.state.command_seq == 2
    assert not agent.state.is_manual_locked


@pytest.mark.parametrize("agentSeq" , [0 , 99])
def testRecoveryUsesServerStateAndMaxUsage(protocol_session , agentSeq) :
    execRequest(CmdRequest(cmd_type = CommandType.LOCK))
    agent.state.command_seq = agentSeq
    agent.state.is_manual_locked = False
    agent.state.device_used = 100.75
    session = server.state.command_sessions["device_hb"]
    session["control"]["device_used"] = 60
    agent.state.needs_sync = True
    response = server.commands.reconcileDevice("device_hb" , agent.getControlState())
    drainResponse(response)
    assert agent.state.command_seq == session["control"]["command_seq"]
    assert agent.state.is_manual_locked
    assert agent.state.device_used == 100.75
    assert server.state.device_used_store["device_hb"] == 100.75
    sendCmd(CmdRequest(cmd_type = CommandType.UNLOCK))
    heartbeat()
    assert not agent.state.is_manual_locked


def testPolicyUpdateWaitsForAckAndHasNewSequence(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.SUB_TIME , sub_time = 100))
    first = server.commands.getCommandResponse("device_hb").command
    policy = server.state.policies_store["policy_hb"]
    policy.policy_version += 1
    policy.weekday_quota = 2400
    policy.weekend_quota = 2400
    response = server.commands.getCommandResponse("device_hb")
    assert response.command == first
    ack = agent.execCmd(first)
    response = server.commands.acknowledgeCmd("device_hb" , ack)
    assert response.command.reason == "policy"
    assert response.command.command_seq == first.command_seq + 1
    assert response.command.device_quota == 2300
    drainResponse(response)
    assert agent.state.device_quota == 2300


@pytest.mark.parametrize("commandType" , list(CommandType))
def testDayChangeWithInflightCommandDoesNotBlock(protocol_session , commandType) :
    sendCmd(CmdRequest(cmd_type = commandType , bonus_time = 60 , sub_time = 60))
    first = server.commands.getCommandResponse("device_hb").command
    protocol_session["wall"] += 86400
    protocol_session["mono"] += 86400
    agent.state.last_input_mono = protocol_session["mono"]
    response = server.commands.getCommandResponse("device_hb")
    assert response.command == first
    ack = agent.execCmd(first)
    assert ack.result == "not_applied"
    response = server.commands.acknowledgeCmd("device_hb" , ack)
    assert response.command.reason == "day"
    assert response.command.command_seq > first.command_seq
    drainResponse(response)
    assert agent.state.device_quota == 1800
    assert agent.state.device_used == 0
    assert agent.state.is_manual_locked == (commandType == CommandType.LOCK)
    assert not server.state.command_sessions["device_hb"]["queue"]


def testAppliedBeforeDayChangeAckIsNotAppliedAgain(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    cmd = server.commands.getCommandResponse("device_hb").command
    ack = agent.execCmd(cmd)
    protocol_session["wall"] += 86400
    protocol_session["mono"] += 86400
    assert agent.execCmd(cmd) == ack
    drainResponse(server.commands.acknowledgeCmd("device_hb" , ack))
    assert agent.state.is_manual_locked
    assert agent.state.device_quota_date == vn_clock.getVnNow().strftime("%Y-%m-%d")


def testAgentWriteFailureDoesNotAdvanceSequence(protocol_session , monkeypatch) :
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    cmd = server.commands.getCommandResponse("device_hb").command
    previous = agent.getControlState()
    monkeypatch.setattr(agent.storage , "writeJsonAtomic" , Mock(side_effect = OSError("disk")))
    with pytest.raises(OSError) :
        agent.execCmd(cmd)
    assert agent.getControlState() == previous
    assert agent.state.last_cmd_ack is None
    assert server.commands.getCommandResponse("device_hb").command == cmd


def testServerWriteFailureDoesNotLoseAckOrQueue(protocol_session , monkeypatch) :
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    sendCmd(CmdRequest(cmd_type = CommandType.UNLOCK))
    cmd = server.commands.getCommandResponse("device_hb").command
    ack = agent.execCmd(cmd)
    writer = server.commands.saveQuotaState
    monkeypatch.setattr(server.commands , "saveQuotaState" , Mock(side_effect = OSError("disk")))
    with pytest.raises(OSError) :
        server.commands.acknowledgeCmd("device_hb" , ack)
    session = server.state.command_sessions["device_hb"]
    assert session["control"]["command_seq"] == 0
    assert session["inflight"]["command_seq"] == 1
    assert len(session["queue"]) == 2
    monkeypatch.setattr(server.commands , "saveQuotaState" , writer)
    response = server.commands.acknowledgeCmd("device_hb" , ack)
    assert response.command.command_seq == 2
    drainResponse(response)
    assert not agent.state.is_manual_locked


@pytest.mark.parametrize("side" , ["agent" , "server"])
@pytest.mark.parametrize("data" , ["{" , "null"])
def testCorruptStorageDoesNotChangeMemory(protocol_session , side , data) :
    if side == "agent" :
        before = agent.getControlState()
        agent.state.AGENT_STATE_FILE.write_text(data , encoding = "utf-8")
        with pytest.raises((ValueError , AttributeError , TypeError)) :
            agent.storage.loadAgentQuotaState()
        assert agent.getControlState() == before
    else :
        before = json.loads(json.dumps(server.state.command_sessions))
        server.state.QUOTA_STATE_FILE.write_text(data , encoding = "utf-8")
        with pytest.raises(RuntimeError) :
            server.loadQuotaState()
        assert server.state.command_sessions == before


def testAtomicWriteFailureKeepsOldFile(protocol_session , monkeypatch) :
    from shared import storage

    agent.storage.saveAgentQuotaState()
    path = agent.state.AGENT_STATE_FILE
    previous = path.read_bytes()
    monkeypatch.setattr(storage.os , "replace" , Mock(side_effect = OSError("replace")))
    with pytest.raises(OSError) :
        agent.storage.saveAgentQuotaState()
    assert path.read_bytes() == previous


def testForgedAckCannotConsumeQueue(protocol_session) :
    sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    cmd = server.commands.getCommandResponse("device_hb").command
    ack = CmdAck(**agent.getControlState().model_dump())
    ack.command_seq = cmd.command_seq + 10
    response = server.commands.acknowledgeCmd("device_hb" , ack)
    assert response.reconcile is not None
    assert response.command == cmd
    assert len(server.state.command_sessions["device_hb"]["queue"]) == 1


@pytest.mark.parametrize("side" , ["agent" , "server"])
def testReadIoFailureDoesNotChangeSequence(protocol_session , monkeypatch , side) :
    from pathlib import Path

    beforeAgent = agent.getControlState()
    beforeServer = json.loads(json.dumps(server.state.command_sessions))
    original = Path.read_text
    target = agent.state.AGENT_STATE_FILE if side == "agent" else server.state.QUOTA_STATE_FILE

    def read(path , *args , **kwargs) :
        if path == target :
            raise OSError("read failed")
        return original(path , *args , **kwargs)

    monkeypatch.setattr(Path , "read_text" , read)
    with pytest.raises(OSError) :
        if side == "agent" :
            agent.storage.loadAgentQuotaState()
        else :
            server.loadQuotaState()
    assert agent.getControlState() == beforeAgent
    assert server.state.command_sessions == beforeServer


def testEnqueueWriteFailureDoesNotAllocateSequence(protocol_session , monkeypatch) :
    previous = json.loads(json.dumps(server.state.command_sessions))
    monkeypatch.setattr(server.commands , "saveQuotaState" , Mock(side_effect = OSError("disk")))
    with pytest.raises(OSError) :
        sendCmd(CmdRequest(cmd_type = CommandType.LOCK))
    assert server.state.command_sessions == previous
