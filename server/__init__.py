#Server

from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from shared.schemas import (
    CommandType,
    EnrollmentRequest,
    EnrollmentResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    PairingCode,
    Policy,
    TargetType,
    UrgentCmd,
)
from sqlalchemy import create_engine, String, ForeignKey
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
    Session
)
import sqlite3
import httpx
import websockets
import os
import uuid
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from enum import StrEnum
import win32com.client
import httpx

app = FastAPI()

#Múi giờ Việt Nam (UTC+7) dùng cho Wall clock để xác định ngày lịch, ngày thường/cuối tuần và mốc reset 00:00
VN_TZ = timezone(timedelta(hours = 7))

curCode : PairingCode | None = None

#Bộ nhớ trên Server
device_tokens : dict[str , str] = {}
device_states : dict[str , dict] = {}
policies_store : dict[str , Policy] = {}
pending_cmds_store : dict[str , list[str]] = {}
#WebSocket: kênh kết nối duy trì liên tục để Server đẩy lệnh khẩn xuống Agent ngay lập tức
active_ws_connections : dict[str , WebSocket] = {}
#ACK (Acknowledgment): thông báo xác nhận Agent đã xử lý lệnh
urgent_acks_store : dict[str , list[dict]] = {}

#Quota & Bonus time: hạn mức thời điểm mở khóa thiết bị, ngày chu kỳ quota (YYYY-MM-DD) và điều chỉnh thời gian App/Web
device_unlocked_store : dict[str , int] = {}
device_used_store : dict[str , int] = {}
device_quota_date_store : dict[str , str] = {}
device_policy_store : dict[str , str] = {}
app_bonus_store : dict[str , dict[str , int]] = {}
web_bonus_store : dict[str , dict[str , int]] = {}
QUOTA_STATE_FILE = Path("quota_state.json")


def getVnNow() -> datetime :
    return datetime.fromtimestamp(time.time() , tz = VN_TZ)


def getTodayDateStr() -> str :
    return getVnNow().strftime("%Y-%m-%d")


def getDeviceBaseQuota(device_id : str , policy_id : str | None = None) -> int :
    now_dt = getVnNow()
    is_weekend = now_dt.weekday() >= 5
    plc_id = policy_id or device_policy_store.get(device_id)
    if not plc_id and device_id.startswith("di_") :
        plc_id = f"plcid_{device_id[3:]}"
    plc = policies_store.get(plc_id) if plc_id else None
    if plc is None and len(policies_store) == 1 :
        plc = next(iter(policies_store.values()))
    if plc is not None :
        return plc.weekend_quota if is_weekend else plc.weekday_quota
    return 7200 if is_weekend else 5400


def ensureDeviceDailyQuota(device_id : str , policy_id : str | None = None) :
    #Chu kỳ DEVICE quota theo ngày lịch VN (00:00 UTC+7): giữ nguyên nếu cùng ngày, chỉ reset một lần khi qua ngày mới
    today_str = getTodayDateStr()
    if policy_id :
        device_policy_store[device_id] = policy_id
    saved_date = device_quota_date_store.get(device_id)
    if saved_date is not None and today_str <= saved_date and device_id in device_unlocked_store :
        return
    if saved_date is None and device_id in device_unlocked_store :
        device_quota_date_store[device_id] = today_str
        saveQuotaState()
        return
    base_quota = getDeviceBaseQuota(device_id , policy_id)
    device_unlocked_store[device_id] = int(time.time()) + base_quota
    device_used_store[device_id] = 0
    device_quota_date_store[device_id] = today_str
    saveQuotaState()


def saveQuotaState() :
    #Lưu trạng thái quota, ngày chu kỳ và điều chỉnh thời gian xuống file để bảo toàn khi Server khởi động lại
    try :
        data = {
            "device_unlocked" : device_unlocked_store ,
            "device_used" : device_used_store ,
            "device_quota_date" : device_quota_date_store ,
            "device_policy" : device_policy_store ,
            "app_bonus" : app_bonus_store ,
            "web_bonus" : web_bonus_store
        }
        QUOTA_STATE_FILE.write_text(json.dumps(data) , encoding = "utf-8")
    except Exception :
        pass


def loadQuotaState() :
    #Khôi phục trạng thái quota khi khởi động: cùng ngày thì giữ nguyên, sang ngày mới (00:00 UTC+7) thì reset theo Policy
    global device_unlocked_store , device_used_store , device_quota_date_store , device_policy_store
    global app_bonus_store , web_bonus_store
    if QUOTA_STATE_FILE.exists() :
        try :
            data = json.loads(QUOTA_STATE_FILE.read_text(encoding = "utf-8"))
            device_unlocked_store = {k : int(v) for k , v in data.get("device_unlocked" , {}).items()}
            device_used_store = {k : int(v) for k , v in data.get("device_used" , {}).items()}
            device_quota_date_store = {k : str(v) for k , v in data.get("device_quota_date" , {}).items()}
            device_policy_store = {k : str(v) for k , v in data.get("device_policy" , {}).items()}
            app_bonus_store = {
                k : {ak : int(av) for ak , av in v.items()}
                for k , v in data.get("app_bonus" , {}).items()
            }
            web_bonus_store = {
                k : {wk : int(wv) for wk , wv in v.items()}
                for k , v in data.get("web_bonus" , {}).items()
            }
            today_str = getTodayDateStr()
            state_changed = False
            for dev_id , unlocked_val in list(device_unlocked_store.items()) :
                saved_date = device_quota_date_store.get(dev_id)
                if saved_date is None :
                    #Tương thích dữ liệu chưa có ngày chu kỳ: giá trị 0 là đã cạn quota trong ngày nên không cấp lại
                    if unlocked_val == 0 :
                        device_quota_date_store[dev_id] = today_str
                        state_changed = True
                    else :
                        unlocked_date = datetime.fromtimestamp(unlocked_val , tz = VN_TZ).strftime("%Y-%m-%d")
                        if unlocked_date >= today_str :
                            device_quota_date_store[dev_id] = today_str
                            state_changed = True
                        else :
                            device_unlocked_store[dev_id] = int(time.time()) + getDeviceBaseQuota(dev_id)
                            device_used_store[dev_id] = 0
                            device_quota_date_store[dev_id] = today_str
                            state_changed = True
                elif today_str > saved_date :
                    device_unlocked_store[dev_id] = int(time.time()) + getDeviceBaseQuota(dev_id)
                    device_used_store[dev_id] = 0
                    device_quota_date_store[dev_id] = today_str
                    state_changed = True
            if state_changed :
                saveQuotaState()
        except Exception :
            pass


loadQuotaState()


@app.post("/api/v1/enroll" , response_model = EnrollmentResponse)
def responseEnroll(payload : EnrollmentRequest) :
    #Enroll: đăng ký thiết bị lần đầu bằng mã ghép đôi (pairing_code), cấp token và khởi tạo Policy mặc định
    if curCode is None or payload.pairing_code != curCode.pairing_code or time.time() > curCode.expires_at :
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "Ma ghep doi khong hop le hoac da het han",
        )
    
    uuid_device = payload.device_fingerprint
    dev_id = f"di_{uuid_device}"
    acc_token = f"at_{uuid_device}"
    plc_id = f"plcid_{uuid_device}"

    device_tokens[dev_id] = acc_token

    if plc_id not in policies_store :
        policies_store[plc_id] = Policy(
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
    app_bonus_store.setdefault(dev_id , {})
    web_bonus_store.setdefault(dev_id , {})
    saveQuotaState()

    return EnrollmentResponse(
        device_id = dev_id,
        access_token = acc_token,
        refresh_token = f"rt_{uuid_device}",
        policy_id = plc_id
    )


@app.post("/api/v1/heartbeat" , response_model = HeartbeatResponse)
def responseHeartbeat(payload : HeartbeatRequest) :
    #Heartbeat: nhận báo cáo định kỳ từ Agent, xóa các lệnh chờ đã có ACK và trả về dữ liệu đồng bộ
    if device_tokens.get(payload.device_id) != payload.access_token :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID",
        )

    device_states[payload.device_id] = {
        "status_cur": payload.status_cur,
        "quota_used": payload.quota_used,
    }

    policy = policies_store.get(payload.policy_id)
    latest_ver = policy.policy_version if policy else payload.cur_policy_version
    ensureDeviceDailyQuota(payload.device_id , payload.policy_id)

    #Đồng bộ thời gian sử dụng thực tế của thiết bị do Agent đo bằng monotonic clock
    if "__device__" in payload.quota_used :
        reported_used = max(0 , int(payload.quota_used["__device__"]))
        prev_used = device_used_store.get(payload.device_id , 0)
        if reported_used > prev_used :
            used_delta = reported_used - prev_used
            device_used_store[payload.device_id] = reported_used
            cur_until = device_unlocked_store.get(payload.device_id , 0)
            if cur_until > 0 :
                new_until = max(0 , cur_until - used_delta)
                if new_until <= int(time.time()) :
                    new_until = 0
                device_unlocked_store[payload.device_id] = new_until
            saveQuotaState()

    #Giữ lệnh trong hàng chờ cho đến khi Agent gửi ACK xác nhận đã thực thi
    cur_cmds = pending_cmds_store.get(payload.device_id , [])
    if payload.acked_commands :
        cur_cmds = [c for c in cur_cmds if c not in payload.acked_commands]
        pending_cmds_store[payload.device_id] = cur_cmds

    return HeartbeatResponse(
        latest_policy_version = latest_ver ,
        pending_commands = cur_cmds ,
        device_unlocked_until = device_unlocked_store.get(payload.device_id , 0) ,
        device_quota_date = device_quota_date_store.get(payload.device_id , getTodayDateStr()) ,
        app_bonus_time = app_bonus_store.get(payload.device_id , {}) ,
        web_bonus_time = web_bonus_store.get(payload.device_id , {})
    )


@app.get("/api/v1/policy" , response_model = Policy)
def responsePolicy(device_id : str , access_token : str , policy_id : str) :
    if device_tokens.get(device_id) != access_token :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED ,
            detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID" ,
        )

    policy = policies_store.get(policy_id)
    if policy is None :
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND ,
            detail = "Khong tim thay Policy" ,
        )

    return policy


@app.websocket("/ws/urgent")
async def urgentWebsocketEndpoint(websocket : WebSocket , device_id : str , access_token : str) :
    if device_tokens.get(device_id) != access_token :
        await websocket.close(code = status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    active_ws_connections[device_id] = websocket

    try :
        while True :
            ack_data = await websocket.receive_json()
            if isinstance(ack_data , dict) :
                urgent_acks_store.setdefault(device_id , []).append(ack_data)
                if "status_cur" in ack_data and device_id in device_states :
                    device_states[device_id]["status_cur"] = ack_data["status_cur"]
    except WebSocketDisconnect :
        pass
    except Exception as e :
        print(f"Loi WebSocket urgent ({device_id}) : {e}")
    finally :
        #Chỉ xóa nếu kết nối đang lưu đúng là kết nối hiện tại (tránh xóa nhầm kết nối mới hơn của cùng device_id)
        if active_ws_connections.get(device_id) is websocket :
            active_ws_connections.pop(device_id , None)


@app.post("/api/v1/urgent")
async def sendUrgentCmd(
    device_id : str ,
    cmd : UrgentCmd ,
    parent_token : str | None = Header(default = None , alias = "X-Parent-Token")
) :
    #Xác thực quyền phụ huynh qua PARENT_TOKEN và kiểm tra thiết bị đã đăng ký
    expected_token = os.environ.get("PARENT_TOKEN")
    if not expected_token or not isinstance(parent_token , str) or parent_token != expected_token :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED ,
            detail = "Khong co quyen thuc thi lenh khan" ,
        )
    if device_id not in device_tokens :
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND ,
            detail = "Thiet bi khong ton tai" ,
        )

    #1.Cập nhật thời gian cho DEVICE, APP hoặc WEB và lưu xuống file
    if cmd.cmd_type == CommandType.ADD_TIME :
        if cmd.target_type == TargetType.DEVICE :
            ensureDeviceDailyQuota(device_id)
            cur_until = device_unlocked_store.get(device_id , int(time.time()))
            if cur_until == 0 :
                cur_until = int(time.time())
            device_unlocked_store[device_id] = cur_until + cmd.bonus_time
            device_quota_date_store[device_id] = getTodayDateStr()
        elif cmd.target_type == TargetType.APP and cmd.subject :
            app_name = cmd.subject.lower().strip()
            dev_bonus = app_bonus_store.setdefault(device_id , {})
            dev_bonus[app_name] = dev_bonus.get(app_name , 0) + cmd.bonus_time
        elif cmd.target_type == TargetType.WEB and cmd.subject :
            domain_name = cmd.subject.lower().strip()
            dev_web_bonus = web_bonus_store.setdefault(device_id , {})
            dev_web_bonus[domain_name] = dev_web_bonus.get(domain_name , 0) + cmd.bonus_time
        saveQuotaState()

    elif cmd.cmd_type == CommandType.SUB_TIME :
        if cmd.target_type == TargetType.DEVICE :
            ensureDeviceDailyQuota(device_id)
            cur_until = device_unlocked_store.get(device_id , int(time.time()))
            device_unlocked_store[device_id] = max(0 , cur_until - cmd.sub_time)
            device_quota_date_store[device_id] = getTodayDateStr()
        elif cmd.target_type == TargetType.APP and cmd.subject :
            app_name = cmd.subject.lower().strip()
            dev_bonus = app_bonus_store.setdefault(device_id , {})
            #Cho phép tổng điều chỉnh (total_adjustment) âm khi SUB_TIME vượt phần cộng thêm để trừ vào quota gốc
            dev_bonus[app_name] = dev_bonus.get(app_name , 0) - cmd.sub_time
        elif cmd.target_type == TargetType.WEB and cmd.subject :
            domain_name = cmd.subject.lower().strip()
            dev_web_bonus = web_bonus_store.setdefault(device_id , {})
            dev_web_bonus[domain_name] = dev_web_bonus.get(domain_name , 0) - cmd.sub_time
        saveQuotaState()

    #2.Ưu tiên đẩy lệnh qua WebSocket; nếu kết nối đứt ngầm (stale) thì dọn bỏ và chuyển sang đồng bộ qua Heartbeat
    ws = active_ws_connections.get(device_id)
    if ws is not None :
        try :
            await ws.send_json(cmd.model_dump())
            return {"sent" : True , "via" : "websocket" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
        except Exception as e :
            print(f"Loi gui WebSocket urgent ({device_id}) : {e}")
            if active_ws_connections.get(device_id) is ws :
                active_ws_connections.pop(device_id , None)

    #3.Khi không có WebSocket, xếp lệnh LOCK/UNLOCK vào hàng chờ Heartbeat
    if cmd.cmd_type in (CommandType.LOCK , CommandType.UNLOCK) :
        cmd_id = f"{int(time.time())}:{cmd.cmd_type}"
        pending_cmds_store.setdefault(device_id , []).append(cmd_id)

    return {"sent" : False , "via" : "heartbeat_sync" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
