#Agent máy trẻ

import asyncio
import json
import time

import httpx
import websockets

from shared.schemas import CmdAck , HeartbeatResponse , Policy

from . import state
from .commands import applyControlState , getControlState
from .helpers.enrollment import getMachineGuid , getPairingCode
from .quota import applyPolicy , execCmd
from .storage import loadAgentQuotaState , saveAgentQuotaState

SERVER_URL = "http://192.168.1.10:8000"
ENROLL_URL = f"{SERVER_URL}/api/v1/enroll"
HEARTBEAT_URL = f"{SERVER_URL}/api/v1/heartbeat"
POLICY_URL = f"{SERVER_URL}/api/v1/policy"
_ACK_URL = f"{SERVER_URL}/api/v1/command-ack"
WS_URGENT_URL = SERVER_URL.replace("http" , "ws") + "/ws/urgent"
ws_handler_running : bool = False


def ensureStateLoaded() :
    with state.control_lock :
        if not state.storage_loaded :
            loadAgentQuotaState()


def requestEnroll() :
    #Đăng ký thiết bị bằng mã ghép đôi.
    pairing_code = getPairingCode()
    response = httpx.post(
        ENROLL_URL ,
        json = {
            "pairing_code" : pairing_code ,
            "device_fingerprint" : getMachineGuid()
        }
    )
    response.raise_for_status()
    if response.status_code == 200 :
        data = response.json()
        state.device_id = data["device_id"]
        state.access_token = data["access_token"]
        state.refresh_token = data["refresh_token"]
        state.policy_id = data["policy_id"]


def requestPolicy() :
    #Lấy chính sách của thiết bị.
    response = httpx.get(
        POLICY_URL ,
        params = {
            "device_id" : state.device_id ,
            "access_token" : state.access_token ,
            "policy_id" : state.policy_id
        } ,
        timeout = 3.6
    )
    response.raise_for_status()
    return Policy(**response.json())


def requestHeartbeat() :
    #Gửi trạng thái thiết bị và xác nhận lệnh đã xử lý.
    ensureStateLoaded()
    with state.control_lock :
        applyPolicy()
        payload = {
            "device_id" : state.device_id ,
            "access_token" : state.access_token ,
            "policy_id" : state.policy_id ,
            "dev_status_cur" : state.dev_status_cur ,
            "quota_used" : {**state.quota_used , "__device__" : int(state.device_used)} ,
            "cur_policy_version" : (
                state.cur_policy.policy_version if state.cur_policy is not None else 0
            ) ,
            "device_quota_date" : state.device_quota_date ,
            "control" : getControlState().model_dump(mode = "json") ,
            "cmd_ack" : (
                state.last_cmd_ack.model_dump(mode = "json")
                if state.last_cmd_ack is not None else None
            ) ,
            "reconcile" : state.needs_sync
        }
    try :
        response = httpx.post(HEARTBEAT_URL , json = payload , timeout = 3.6)
        response.raise_for_status()
        return HeartbeatResponse.model_validate(response.json())
    except Exception :
        state.online = False
        state.needs_sync = True
        raise


def requestCmdAck(ack : CmdAck) -> HeartbeatResponse :
    try :
        response = httpx.post(
            _ACK_URL ,
            params = {"device_id" : state.device_id , "access_token" : state.access_token} ,
            json = ack.model_dump(mode = "json") , timeout = 3.6
        )
        response.raise_for_status()
        return HeartbeatResponse.model_validate(response.json())
    except Exception :
        state.online = False
        state.needs_sync = True
        raise


def HeartbeatResponseHanlder(data : HeartbeatResponse) :
    #Cập nhật dữ liệu và thực thi lệnh từ Server.
    #Lấy Policy khi Server có phiên bản mới hơn.
    policyVersion = state.cur_policy.policy_version if state.cur_policy is not None else 0
    if data.latest_policy_version > policyVersion :
        policy = requestPolicy()
        with state.control_lock :
            state.cur_policy = policy
    with state.control_lock :
        state.online = True
        #Bỏ qua số liệu thiết bị thuộc ngày cũ; vẫn nhận phản hồi không ghi ngày.
        if data.reconcile is not None and (
            state.needs_sync or data.reconcile.command_seq >= state.command_seq
        ) :
            #Đổi ngày: bỏ số đã dùng và mốc đo của ngày trước.
            #Nhận hạn mức; giữ số đã dùng lớn hơn giữa Agent và Server.
            #Nhận điều chỉnh thời gian APP/WEB.
            applyControlState(data.reconcile)
        #Tính thời gian và xét trạng thái theo dữ liệu vừa nhận.
        applyPolicy()
        #Thực thi mỗi mã lệnh một lần và chờ gửi xác nhận ở Heartbeat sau.
        if data.command is not None :
            #Tách mã lệnh khỏi nội dung; vẫn đọc chuỗi không có mã.
            #Đọc JSON mới hoặc tên lệnh lock/unlock theo định dạng cũ.
            #Chỉ đánh dấu đã xử lý khi thực thi thành công.
            return execCmd(data.command)
        #Lệnh nhận lại vẫn được xác nhận, nhưng không thực thi lần nữa.
        saveAgentQuotaState()
    return None


def drainResponses(response) :
    previous = None
    while True :
        ack = HeartbeatResponseHanlder(response)
        if ack is None :
            return response
        progress = (ack.command_seq , ack.result , ack.reason)
        if progress == previous :
            state.needs_sync = True
            raise RuntimeError("Lệnh không tiến sau ACK; cần đối chiếu lại trạng thái")
        previous = progress
        response = requestCmdAck(ack)


def requestHeartbeatLoop(interval : int = 60) :
    #Gửi và xử lý báo cáo định kỳ.
    ensureStateLoaded()
    while True :
        try :
            drainResponses(requestHeartbeat())
        except Exception as e :
            print(f"Loi : {e}")
        time.sleep(interval)


async def UrgentCmdHandler(
    stop_event : asyncio.Event | None = None ,
    max_retries : int | None = None ,
    base_delay : float = 1.0 ,
    max_delay : float = 6.7
) :
    #Nhận và thực thi lệnh qua WebSocket.
    global ws_handler_running
    if ws_handler_running :
        print("UrgentCmdHandler dang chay, bo qua khoi tao trung")
        return

    ensureStateLoaded()
    ws_handler_running = True
    attempt = 0
    try :
        while stop_event is None or not stop_event.is_set() :
            ws_url = (
                f"{WS_URGENT_URL}?device_id={state.device_id}"
                f"&access_token={state.access_token}"
            )
            try :
                async with websockets.connect(ws_url) as websocket :
                    attempt = 0
                    with state.control_lock :
                        state.needs_sync = True
                        initialAck = state.last_cmd_ack
                        control = getControlState()
                    if initialAck is not None :
                        await websocket.send(json.dumps({
                            "type" : "ack" , "data" : initialAck.model_dump(mode = "json")
                        }))
                    await websocket.send(json.dumps({
                        "type" : "sync" , "data" : control.model_dump(mode = "json")
                    }))
                    while stop_event is None or not stop_event.is_set() :
                        data = await websocket.recv()
                        try :
                            response = HeartbeatResponse.model_validate_json(data)
                        except Exception as parse_err :
                            print(f"Loi goi tin Cmd : {parse_err}")
                            continue
                        ack = HeartbeatResponseHanlder(response)
                        if ack is not None :
                            await websocket.send(json.dumps({
                                "type" : "ack" , "data" : ack.model_dump(mode = "json")
                            }))
            except asyncio.CancelledError :
                raise
            except Exception as conn_err :
                state.online = False
                state.needs_sync = True
                attempt += 1
                print(f"Loi ket noi WebSocket urgent (lan {attempt}) : {conn_err}")
                if max_retries is not None and attempt > max_retries :
                    break
                if stop_event is not None and stop_event.is_set() :
                    break
                #Tăng thời gian chờ khi kết nối tiếp tục lỗi.
                delay = min(max_delay , base_delay * (2 ** (attempt - 1)))
                await asyncio.sleep(delay)
    finally :
        ws_handler_running = False
