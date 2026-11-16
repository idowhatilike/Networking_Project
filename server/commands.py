from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4

from fastapi import HTTPException

from shared import clock
from shared.schemas import (
    Cmd , CmdAck , CmdRequest , CommandType , ControlState , HeartbeatResponse , TargetType
)

from . import state
from .quota import getDeviceBaseQuota
from .storage import saveQuotaState


_STORENAMES = (
    "command_sessions" , "device_quota_store" , "device_used_store" ,
    "device_quota_date_store" , "device_policy_store" , "app_bonus_store" ,
    "web_bonus_store" , "device_states"
)


@contextmanager
def commandTransaction() :
    with state.command_lock :
        saved = {name : deepcopy(getattr(state , name)) for name in _STORENAMES}
        try :
            yield
            saveQuotaState()
        except Exception :
            for name , value in saved.items() :
                setattr(state , name , value)
            raise


def controlData(value) :
    fields = ControlState.model_fields
    if hasattr(value , "model_dump") :
        value = value.model_dump(mode = "json")
    return ControlState(**{name : value[name] for name in fields}).model_dump(mode = "json")


def syncStores(deviceId , session) :
    control = session["control"]
    state.device_quota_store[deviceId] = control["device_quota"]
    state.device_used_store[deviceId] = control["device_used"]
    state.device_quota_date_store[deviceId] = control["device_quota_date"]
    state.app_bonus_store[deviceId] = dict(control["app_bonus_time"])
    state.web_bonus_store[deviceId] = dict(control["web_bonus_time"])


def newSession(deviceId , policyId = None , control = None) :
    if policyId is not None :
        state.device_policy_store[deviceId] = policyId
    if deviceId in state.command_sessions :
        return state.command_sessions[deviceId]
    today = clock.getVnNow().strftime("%Y-%m-%d")
    if control is None :
        control = ControlState(
            command_seq = 0 ,
            device_quota_date = state.device_quota_date_store.get(deviceId , today) ,
            device_quota = state.device_quota_store.get(deviceId , getDeviceBaseQuota(deviceId)) ,
            device_used = state.device_used_store.get(deviceId , 0) ,
            app_bonus_time = state.app_bonus_store.get(deviceId , {}) ,
            web_bonus_time = state.web_bonus_store.get(deviceId , {})
        )
    policy = state.policies_store.get(state.device_policy_store.get(deviceId))
    data = controlData(control)
    session = {
        "control" : data , "next_seq" : data["command_seq"] + 1 ,
        "queue" : [] , "inflight" : None , "requests" : {} ,
        "last_policy_base" : getDeviceBaseQuota(deviceId) ,
        "last_policy_version" : policy.policy_version if policy is not None else 0 ,
        "scheduled_date" : data["device_quota_date"] ,
        "scheduled_policy_base" : getDeviceBaseQuota(deviceId) ,
        "scheduled_policy_version" : policy.policy_version if policy is not None else 0
    }
    state.command_sessions[deviceId] = session
    syncStores(deviceId , session)
    return session


def ensureSession(deviceId , policyId = None , control = None) :
    with commandTransaction() :
        return newSession(deviceId , policyId , control)


def appendEntry(session , entry) :
    session["queue"].append(entry)


def scheduleUpdates(deviceId , session) :
    today = clock.getVnNow().strftime("%Y-%m-%d")
    policy = state.policies_store.get(state.device_policy_store.get(deviceId))
    version = policy.policy_version if policy is not None else 0
    base = getDeviceBaseQuota(deviceId)
    if today > session["scheduled_date"] :
        appendEntry(session , {
            "request_id" : str(uuid4()) , "reason" : "day" ,
            "device_quota_date" : today , "policy_base" : getDeviceBaseQuota(deviceId) ,
            "policy_version" : version
        })
        session["scheduled_date"] = today
        session["scheduled_policy_version"] = version
        session["scheduled_policy_base"] = base
        entry = session["queue"].pop()
        session["queue"].insert(1 if session["inflight"] is not None else 0 , entry)
    elif version > session["scheduled_policy_version"] or (
        base != session.get("scheduled_policy_base" , session["last_policy_base"])
    ) :
        appendEntry(session , {
            "request_id" : str(uuid4()) , "reason" : "policy" ,
            "policy_base" : getDeviceBaseQuota(deviceId) , "policy_version" : version
        })
        session["scheduled_policy_version"] = version
        session["scheduled_policy_base"] = base
        entry = session["queue"].pop()
        session["queue"].insert(1 if session["inflight"] is not None else 0 , entry)


def makeCommand(session , entry) :
    data = deepcopy(session["control"])
    data["command_seq"] = entry["command_seq"]
    reason = entry.get("reason" , "command")
    if reason == "day" :
        data["device_quota_date"] = entry["device_quota_date"]
        data["device_quota"] = entry["policy_base"]
        data["device_used"] = session.get("reported_usage" , {}).get(
            entry["device_quota_date"] , 0
        )
    elif reason == "policy" :
        data["device_quota"] = max(
            0 , data["device_quota"] + entry["policy_base"] - session["last_policy_base"]
        )
    else :
        cmdType = CommandType(entry["cmd_type"])
        if cmdType in (CommandType.ADD_TIME , CommandType.SUB_TIME) and (
            entry.get("request_date" , data["device_quota_date"]) < data["device_quota_date"]
        ) :
            data["device_quota_date"] = entry["request_date"]
        target = TargetType(entry["target_type"])
        subject = entry.get("subject" , "")
        if cmdType in (CommandType.LOCK , CommandType.UNLOCK) :
            locked = cmdType == CommandType.LOCK
            if target == TargetType.DEVICE :
                data["is_manual_locked"] = locked
            else :
                field = (
                    "manual_locked_apps" if target == TargetType.APP else "manual_locked_domains"
                )
                subjects = set(data[field])
                if locked :
                    subjects.add(subject)
                else :
                    subjects.discard(subject)
                data[field] = sorted(subjects)
        elif target == TargetType.DEVICE :
            if cmdType == CommandType.ADD_TIME :
                data["device_quota"] = max(
                    data["device_quota"] , data["device_used"]
                ) + entry["bonus_time"]
            else :
                data["device_quota"] = max(0 , data["device_quota"] - entry["sub_time"])
        else :
            field = "app_bonus_time" if target == TargetType.APP else "web_bonus_time"
            adjustment = entry["bonus_time"] if cmdType == CommandType.ADD_TIME else (
                -entry["sub_time"]
            )
            data[field][subject] = data[field].get(subject , 0) + adjustment
    return Cmd(
        **data , request_id = entry["request_id"] , reason = reason ,
        cmd_type = entry.get("cmd_type") , target_type = entry.get("target_type" , "device") ,
        subject = entry.get("subject" , "") , bonus_time = entry.get("bonus_time" , 0) ,
        sub_time = entry.get("sub_time" , 0)
    )


def nextCommand(session) :
    if session["inflight"] is None and session["queue"] :
        entry = session["queue"][0]
        entry["command_seq"] = session["next_seq"]
        session["next_seq"] += 1
        session["inflight"] = makeCommand(session , entry).model_dump(mode = "json")
        record = session["requests"].get(entry["request_id"])
        if record is not None :
            record["status"] = "inflight"
            record["command_seq"] = entry["command_seq"]
    if session["inflight"] is not None :
        return Cmd.model_validate(session["inflight"])
    return None


def responseData(deviceId , session , reconcile = None) :
    policy = state.policies_store.get(state.device_policy_store.get(deviceId))
    return HeartbeatResponse(
        latest_policy_version = policy.policy_version if policy is not None else 0 ,
        command = nextCommand(session) , reconcile = reconcile
    )


def enqueueCmd(deviceId , request) :
    if not isinstance(request , CmdRequest) :
        request = CmdRequest.model_validate(request)
    with commandTransaction() :
        session = newSession(deviceId)
        data = request.model_dump(mode = "json")
        record = session["requests"].get(request.request_id)
        if record is not None :
            if record["request"] != data :
                raise HTTPException(status_code = 409 , detail = "request_id khac noi dung")
        else :
            scheduleUpdates(deviceId , session)
            entry = dict(
                data , reason = "command" ,
                request_date = clock.getVnNow().strftime("%Y-%m-%d")
            )
            appendEntry(session , entry)
            record = {
                "request" : data , "command_seq" : None , "status" : "queued"
            }
            session["requests"][request.request_id] = record
        command = nextCommand(session)
        return {
            "request_id" : request.request_id , "status" : record["status"] ,
            "command" : command.model_dump(mode = "json") if command is not None else None
        }


def recordUsage(session , control = None , date = "" , used = 0) :
    if control is not None :
        date = control.device_quota_date
        used = control.device_used
    current = session["control"]
    if not date :
        date = current["device_quota_date"]
    reported = session.setdefault("reported_usage" , {})
    reported[date] = max(reported.get(date , 0) , max(0 , float(used)))
    if date == current["device_quota_date"] :
        current["device_used"] = max(current["device_used"] , reported[date])


def acceptAck(session , ack) :
    current = session["control"]
    pending = session["inflight"]
    if ack.result == "resync" :
        recordUsage(session , ack)
        return False
    if ack.command_seq <= current["command_seq"] :
        recordUsage(session , ack)
        return True
    if pending is None or ack.command_seq != pending["command_seq"] :
        return False
    expired = (
        ack.result == "not_applied" and ack.reason == "day_changed"
        and pending["device_quota_date"] < clock.getVnNow().strftime("%Y-%m-%d")
    )
    if expired :
        received = deepcopy(current)
        received["command_seq"] = ack.command_seq
        session["control"] = received
        recordUsage(session , ack)
        entry = session["queue"].pop(0)
        if entry.get("cmd_type") in (CommandType.LOCK , CommandType.UNLOCK) :
            entry.pop("command_seq" , None)
            position = next((
                index + 1 for index , item in enumerate(session["queue"])
                if item.get("reason") == "day"
            ) , 0)
            session["queue"].insert(position , entry)
        record = session["requests"].get(entry["request_id"])
        if record is not None :
            record["status"] = "queued" if entry in session["queue"] else "not_applied"
            record["result"] = ack.model_dump(mode = "json")
        session["inflight"] = None
        return True
    if ack.result != "applied" :
        return False
    expected = controlData(pending)
    received = controlData(ack)
    permittedQuota = expected["device_quota"]
    if pending["cmd_type"] == CommandType.ADD_TIME and (
        pending["target_type"] == TargetType.DEVICE
    ) :
        permittedQuota = max(permittedQuota , received["device_used"] + pending["bonus_time"])
    for name in expected :
        if name in ("device_used" , "device_quota") :
            continue
        if name in ("manual_locked_apps" , "manual_locked_domains") :
            if set(received[name]) != set(expected[name]) :
                return False
        elif received[name] != expected[name] :
            return False
    if not expected["device_quota"] <= received["device_quota"] <= permittedQuota :
        return False
    received["device_used"] = max(received["device_used"] , expected["device_used"])
    session["control"] = received
    recordUsage(session , ack)
    entry = session["queue"].pop(0)
    if entry.get("reason") in ("day" , "policy") :
        session["last_policy_base"] = entry["policy_base"]
        session["last_policy_version"] = entry["policy_version"]
    record = session["requests"].get(entry["request_id"])
    if record is not None :
        record["status"] = "applied"
        record["result"] = received
    session["inflight"] = None
    return True


def acknowledgeCmd(deviceId , ack) :
    if not isinstance(ack , CmdAck) :
        ack = CmdAck.model_validate(ack)
    with commandTransaction() :
        session = newSession(deviceId)
        pending = session["inflight"]
        fresh = pending is not None and ack.command_seq == pending["command_seq"]
        accepted = acceptAck(session , ack)
        if accepted and fresh and ack.result == "applied" :
            state.device_states.setdefault(deviceId , {})["dev_status_cur"] = ack.dev_status_cur
        syncStores(deviceId , session)
        scheduleUpdates(deviceId , session)
        baseline = None if accepted else ControlState.model_validate(session["control"])
        return responseData(deviceId , session , baseline)


def reconcileDevice(deviceId , control) :
    if not isinstance(control , ControlState) :
        control = ControlState.model_validate(control)
    with commandTransaction() :
        session = newSession(deviceId)
        recordUsage(session , control)
        syncStores(deviceId , session)
        scheduleUpdates(deviceId , session)
        baseline = ControlState.model_validate(session["control"])
        return responseData(deviceId , session , baseline)


def getCommandResponse(deviceId) :
    with commandTransaction() :
        session = newSession(deviceId)
        scheduleUpdates(deviceId , session)
        return responseData(deviceId , session)


def refreshDeviceQuota(deviceId , policyId = None) :
    with commandTransaction() :
        session = newSession(deviceId , policyId)
        previous = len(session["queue"])
        scheduleUpdates(deviceId , session)
        return len(session["queue"]) != previous


def processHeartbeat(payload) :
    with commandTransaction() :
        session = newSession(payload.device_id)
        accepted = True
        if payload.cmd_ack is not None :
            accepted = acceptAck(session , payload.cmd_ack)
        recordUsage(
            session , payload.control , payload.device_quota_date ,
            payload.quota_used.get("__device__" , 0)
        )
        state.device_states[payload.device_id] = {
            "dev_status_cur" : payload.dev_status_cur , "quota_used" : payload.quota_used
        }
        syncStores(payload.device_id , session)
        scheduleUpdates(payload.device_id , session)
        baseline = None
        if payload.reconcile or not accepted or (
            payload.control is not None
            and (
                payload.control.command_seq != session["control"]["command_seq"]
                or (
                    payload.control.device_quota_date == session["control"]["device_quota_date"]
                    and payload.control.device_used < session["control"]["device_used"]
                )
            )
        ) :
            baseline = ControlState.model_validate(session["control"])
        return responseData(payload.device_id , session , baseline)
