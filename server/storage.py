import json
import time
import warnings

from shared.schemas import Cmd , ControlState , Policy
from shared.storage import writeJsonAtomic

from . import state


def saveQuotaState() :
    #Lưu hạn mức và điều chỉnh thời gian.
    data = {
        "device_quota" : state.device_quota_store ,
        "device_used" : state.device_used_store ,
        "device_quota_date" : state.device_quota_date_store ,
        "device_policy" : state.device_policy_store ,
        "app_bonus" : state.app_bonus_store ,
        "web_bonus" : state.web_bonus_store ,
        "command_sessions" : state.command_sessions ,
        "policies" : {
            key : policy.model_dump(mode = "json")
            for key , policy in state.policies_store.items()
        }
    }
    with state.command_lock :
        writeJsonAtomic(state.QUOTA_STATE_FILE , data)


def loadQuotaState() :
    #Khôi phục hạn mức và cập nhật ngày áp dụng.
    try :
        text = state.QUOTA_STATE_FILE.read_text(encoding = "utf-8")
    except FileNotFoundError :
        return
    try :
        data = json.loads(text)
        migrated = "device_quota" not in data
        used = {key : max(0 , float(value)) for key , value in data.get("device_used" , {}).items()}
        if "device_quota" in data :
            quota = {
                key : max(0 , float(value)) for key , value in data["device_quota"].items()
            }
        else :
            if "device_remaining" in data :
                remaining = data["device_remaining"]
            else :
                #Dữ liệu cũ không đủ để phục hồi thời gian Idle đã mất; chỉ chuyển đổi một lần.
                remaining = {
                    key : max(0 , float(value) - time.time())
                    for key , value in data.get("device_unlocked" , {}).items()
                }
                warnings.warn(
                    "Migrating legacy quota deadlines; lost idle time cannot be recovered." ,
                    RuntimeWarning
                )
            quota = {
                key : max(0 , float(value)) + used.get(key , 0)
                for key , value in remaining.items()
            }
        dates = {key : str(value) for key , value in data.get("device_quota_date" , {}).items()}
        policies = {key : str(value) for key , value in data.get("device_policy" , {}).items()}
        appBonus = {
            key : {subject : int(value) for subject , value in bonus.items()}
            for key , bonus in data.get("app_bonus" , {}).items()
        }
        webBonus = {
            key : {subject : int(value) for subject , value in bonus.items()}
            for key , bonus in data.get("web_bonus" , {}).items()
        }
        sessions = data.get("command_sessions" , {})
        if not isinstance(sessions , dict) :
            raise ValueError("Invalid command_sessions")
        for session in sessions.values() :
            session["control"] = ControlState.model_validate(session["control"]).model_dump(
                mode = "json"
            )
            currentSeq = session["control"]["command_seq"]
            sequences = [entry["command_seq"] for entry in session["queue"]
                         if "command_seq" in entry]
            if sequences and sequences != [currentSeq + 1] :
                raise ValueError("Command queue has a sequence gap")
            highestSeq = sequences[-1] if sequences else currentSeq
            if session["next_seq"] <= highestSeq :
                raise ValueError("Command sequence counter moved backwards")
            if session["inflight"] is not None :
                command = Cmd.model_validate(session["inflight"])
                if not sequences or command.command_seq != sequences[0] :
                    raise ValueError("Inflight command does not match queue")
                session["inflight"] = command.model_dump(mode = "json")
        policyModels = {
            key : Policy.model_validate(value) for key , value in data.get("policies" , {}).items()
        }
    except (OSError , ValueError , TypeError , AttributeError , KeyError) as error :
        raise RuntimeError("Cannot load Server quota or command state") from error
    with state.command_lock :
        state.device_quota_store = quota
        state.device_used_store = used
        state.device_quota_date_store = dates
        state.device_policy_store = policies
        state.app_bonus_store = appBonus
        state.web_bonus_store = webBonus
        state.command_sessions = sessions
        state.policies_store.update(policyModels)
        for deviceId , session in sessions.items() :
            control = session["control"]
            state.device_quota_store[deviceId] = control["device_quota"]
            state.device_used_store[deviceId] = control["device_used"]
            state.device_quota_date_store[deviceId] = control["device_quota_date"]
            state.app_bonus_store[deviceId] = dict(control["app_bonus_time"])
            state.web_bonus_store[deviceId] = dict(control["web_bonus_time"])
        if migrated :
            saveQuotaState()
