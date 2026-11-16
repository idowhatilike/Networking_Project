import json

from shared.schemas import CmdAck , ControlState , Policy
from shared.storage import writeJsonAtomic

from . import state


def saveAgentQuotaState() :
    #Lưu hạn mức và khóa thủ công.
    from .commands import getControlState

    with state.control_lock :
        data = getControlState().model_dump(mode = "json")
        data["quota_used"] = dict(state.quota_used)
        data["last_cmd_ack"] = (
            state.last_cmd_ack.model_dump(mode = "json")
            if state.last_cmd_ack is not None else None
        )
        data["policy"] = (
            state.cur_policy.model_dump(mode = "json") if state.cur_policy is not None else None
        )
        writeJsonAtomic(state.AGENT_STATE_FILE , data)


def loadAgentQuotaState() :
    #Khôi phục hạn mức và khóa thủ công.
    with state.control_lock :
        try :
            text = state.AGENT_STATE_FILE.read_text(encoding = "utf-8")
        except FileNotFoundError :
            state.storage_loaded = True
            return
        data = json.loads(text)
        used = max(0.0 , float(data.get("device_used" , data.get("device_quota_used" , 0))))
        if "device_quota" in data :
            quota = max(0.0 , float(data["device_quota"]))
        else :
            quota = used + max(0.0 , float(data.get("device_remaining_sec" , 0)))
        fields = {name : data[name] for name in ControlState.model_fields if name in data}
        fields.update(device_quota = quota , device_used = used)
        control = ControlState(**fields)
        usedByObj = {
            str(key) : int(value) for key , value in data.get("quota_used" , {}).items()
            if key != "__device__"
        }
        ack = CmdAck.model_validate(data["last_cmd_ack"]) if data.get("last_cmd_ack") else None
        policy = Policy.model_validate(data["policy"]) if data.get("policy") else None
        if ack is not None and ack.command_seq != control.command_seq :
            raise ValueError("ACK và trạng thái lưu không cùng seq")
        for name in ControlState.model_fields :
            setattr(state , name , getattr(control , name))
        state.quota_used = usedByObj
        state.last_cmd_ack = ack
        if policy is not None :
            state.cur_policy = policy
        state.last_mono_ts = None
        state.last_wall_ts = None
        state.last_input_mono = None
        state._last_win_input_tick = None
        state.needs_sync = True
        state.online = False
        state.storage_loaded = True
