#Server

import os
import time

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from shared.schemas import (
    CmdAck , CmdRequest , ControlState , EnrollmentRequest , EnrollmentResponse ,
    HeartbeatRequest , HeartbeatResponse , Policy
)

from . import commands , state
from .quota import ensureDeviceDailyQuota
from .storage import loadQuotaState , saveQuotaState
from .web import setupWeb

app = FastAPI()
loadQuotaState()
setupWeb(app)


@app.post("/api/v1/enroll" , response_model = EnrollmentResponse)
def responseEnroll(payload : EnrollmentRequest) :
    #Đăng ký thiết bị và cấp chính sách ban đầu.
    if (
        state.current_pairing_code is None
        or payload.pairing_code != state.current_pairing_code.pairing_code
        or time.time() > state.current_pairing_code.expires_at
    ) :
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST ,
            detail = "Ma ghep doi khong hop le hoac da het han"
        )

    uuid_device = payload.device_fingerprint
    dev_id = f"di_{uuid_device}"
    acc_token = f"at_{uuid_device}"
    plc_id = f"plcid_{uuid_device}"

    state.device_tokens[dev_id] = acc_token

    if plc_id not in state.policies_store :
        state.policies_store[plc_id] = Policy(
            policy_id = plc_id ,
            policy_version = 1 ,
            weekday_quota = 5400 ,
            weekend_quota = 7200 ,
            schedule_7x48 = [[True] * 48 for _ in range(7)] ,
            app_rules = [] ,
            domain_rules = [] ,
            signature = "unsigned"
        )

    ensureDeviceDailyQuota(dev_id , plc_id)
    state.app_bonus_store.setdefault(dev_id , {})
    state.web_bonus_store.setdefault(dev_id , {})
    commands.ensureSession(dev_id , plc_id)
    saveQuotaState()

    return EnrollmentResponse(
        device_id = dev_id ,
        access_token = acc_token ,
        refresh_token = f"rt_{uuid_device}" ,
        policy_id = plc_id
    )


def validateDevice(deviceId , accessToken , policyId = None) :
    if state.device_tokens.get(deviceId) != accessToken :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED ,
            detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID"
        )
    if policyId is not None and state.device_policy_store.get(deviceId) != policyId :
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN , detail = "Policy khong thuoc thiet bi"
        )


def responseHeartbeat(payload : HeartbeatRequest) :
    #Nhận báo cáo thiết bị và trả dữ liệu đồng bộ.
    validateDevice(payload.device_id , payload.access_token , payload.policy_id)
    return commands.processHeartbeat(payload)


async def pushResponse(deviceId , response) :
    websocket = state.active_ws_connections.get(deviceId)
    if websocket is None :
        return False
    try :
        await websocket.send_json(response.model_dump(mode = "json"))
        return True
    except Exception as error :
        print(f"Loi gui WebSocket urgent ({deviceId}) : {error}")
        if state.active_ws_connections.get(deviceId) is websocket :
            state.active_ws_connections.pop(deviceId , None)
        return False


@app.post("/api/v1/heartbeat" , response_model = HeartbeatResponse)
async def heartbeatEndpoint(payload : HeartbeatRequest) :
    response = responseHeartbeat(payload)
    if response.command is not None or response.reconcile is not None :
        await pushResponse(payload.device_id , response)
    return response


@app.post("/api/v1/command-ack" , response_model = HeartbeatResponse)
async def responseCommandAck(device_id : str , access_token : str , ack : CmdAck) :
    validateDevice(device_id , access_token)
    response = commands.acknowledgeCmd(device_id , ack)
    await pushResponse(device_id , response)
    return response


@app.get("/api/v1/policy" , response_model = Policy)
def responsePolicy(device_id : str , access_token : str , policy_id : str) :
    #Trả chính sách được yêu cầu.
    validateDevice(device_id , access_token , policy_id)
    policy = state.policies_store.get(policy_id)
    if policy is None :
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND ,
            detail = "Khong tim thay Policy"
        )
    return policy


@app.websocket("/ws/urgent")
async def urgentWebsocketEndpoint(websocket : WebSocket , device_id : str , access_token : str) :
    #Giữ kết nối điều khiển và nhận xác nhận của Agent.
    try :
        validateDevice(device_id , access_token)
    except HTTPException :
        await websocket.close(code = status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    state.active_ws_connections[device_id] = websocket

    try :
        while True :
            message = await websocket.receive_json()
            if not isinstance(message , dict) :
                continue
            if message.get("type") == "ack" :
                ack = CmdAck.model_validate(message["data"])
                response = commands.acknowledgeCmd(device_id , ack)
            elif message.get("type") == "sync" :
                control = ControlState.model_validate(message["data"])
                response = commands.reconcileDevice(device_id , control)
            else :
                continue
            await pushResponse(device_id , response)
    except WebSocketDisconnect :
        pass
    except Exception as error :
        print(f"Loi WebSocket urgent ({device_id}) : {error}")
    finally :
        #Giữ kết nối mới nếu kết nối cũ đóng muộn.
        if state.active_ws_connections.get(device_id) is websocket :
            state.active_ws_connections.pop(device_id , None)


@app.post("/api/v1/urgent")
async def sendUrgentCmd(
    device_id : str ,
    cmd : CmdRequest ,
    parent_token : str | None = Header(default = None , alias = "X-Parent-Token")
) :
    #Gửi lệnh điều khiển tới thiết bị.
    expected_token = os.environ.get("PARENT_TOKEN")
    if not expected_token or not isinstance(parent_token , str) or parent_token != expected_token :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED ,
            detail = "Khong co quyen thuc thi lenh khan"
        )
    if device_id not in state.device_tokens :
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND , detail = "Thiet bi khong ton tai"
        )

    #Điều chỉnh âm trừ vào hạn mức gốc.
    result = commands.enqueueCmd(device_id , cmd)
    sent = await pushResponse(device_id , commands.getCommandResponse(device_id))
    result.update(
        device_id = device_id , cmd_type = cmd.cmd_type , sent = sent ,
        via = "websocket" if sent else "heartbeat_sync"
    )
    return result
