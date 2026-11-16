from copy import deepcopy

from shared import clock
from shared.schemas import Cmd , CmdAck , CommandType , ControlState , TargetType

from . import state


_STATE_FIELDS = tuple(ControlState.model_fields) + (
    "last_cmd_ack" , "online" , "needs_sync" , "dev_status_cur" ,
    "device_block_reason" , "app_block_reasons" , "domain_block_reasons" ,
    "blocked_domains" , "last_mono_ts" , "last_wall_ts" , "event_buffer" ,
    "last_input_mono" , "_last_win_input_tick"
)


def getControlState() -> ControlState :
    with state.control_lock :
        return ControlState(**{
            name : deepcopy(getattr(state , name)) for name in ControlState.model_fields
        })


def makeAck(result = "applied" , reason = "") -> CmdAck :
    return CmdAck(
        **getControlState().model_dump() , result = result , reason = reason ,
        dev_status_cur = state.dev_status_cur
    )


def restoreValues(values) :
    for name , value in values.items() :
        setattr(state , name , value)


def setControlValues(control : ControlState , used : float) :
    if control.device_quota_date != state.device_quota_date :
        state.last_mono_ts = None
        state.last_wall_ts = None
    for name in ControlState.model_fields :
        setattr(state , name , deepcopy(getattr(control , name)))
    state.device_used = used


def applyControlState(control : ControlState) :
    from .quota import applyPolicy
    from .storage import saveAgentQuotaState

    with state.control_lock :
        before = {name : deepcopy(getattr(state , name)) for name in _STATE_FIELDS}
        try :
            applyPolicy()
            used = control.device_used
            if control.device_quota_date == state.device_quota_date :
                used = max(used , state.device_used)
            setControlValues(control , used)
            state.online = True
            state.needs_sync = False
            state.last_cmd_ack = None
            applyPolicy()
            saveAgentQuotaState()
        except Exception :
            restoreValues(before)
            raise


def applyCommand(cmd : Cmd) -> CmdAck :
    from .quota import applyPolicy
    from .storage import saveAgentQuotaState

    with state.control_lock :
        if cmd.command_seq <= state.command_seq :
            if state.last_cmd_ack is None :
                return makeAck("resync" , "missing_result")
            return state.last_cmd_ack.model_copy(deep = True)
        if cmd.command_seq != state.command_seq + 1 :
            state.needs_sync = True
            return makeAck("resync" , "sequence_gap")

        before = {name : deepcopy(getattr(state , name)) for name in _STATE_FIELDS}
        try :
            #Chốt thời gian sử dụng trước khi đổi trạng thái hoặc hạn mức.
            applyPolicy()
            today = clock.getVnNow().strftime("%Y-%m-%d")
            result = "applied"
            reason = ""
            if cmd.device_quota_date and cmd.device_quota_date < today :
                result = "not_applied"
                reason = "day_changed"
                state.command_seq = cmd.command_seq
            else :
                used = cmd.device_used
                if cmd.device_quota_date == state.device_quota_date :
                    used = max(used , state.device_used)
                quota = cmd.device_quota
                if (
                    cmd.cmd_type == CommandType.ADD_TIME
                    and cmd.target_type == TargetType.DEVICE
                    and used > cmd.device_used
                ) :
                    quota = max(quota , used + cmd.bonus_time)
                #Cộng/trừ hạn mức thiết bị, giữ nguyên thời gian đã dùng.
                setControlValues(cmd , used)
                state.device_quota = quota
                #Thêm hoặc gỡ khóa thủ công của đúng đối tượng.
                #Cộng/trừ thời gian của ứng dụng hoặc website.
                #Điều chỉnh âm trừ vào hạn mức gốc.
                state.online = True
                state.needs_sync = False
                #Xét lại trạng thái sau lệnh.
                applyPolicy()
            state.last_cmd_ack = makeAck(result , reason)
            saveAgentQuotaState()
            return state.last_cmd_ack.model_copy(deep = True)
        except Exception :
            restoreValues(before)
            raise
