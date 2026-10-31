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
from datetime import datetime, timezone
from enum import StrEnum
import win32com.client
import httpx

app = FastAPI()

curCode : PairingCode | None = None

#Bộ nhớ trên Server
device_tokens : dict[str , str] = {}
device_states : dict[str , dict] = {}
policies_store : dict[str , Policy] = {}
pending_cmds_store : dict[str , list[str]] = {}
active_ws_connections : dict[str , WebSocket] = {} #Quản lý kết nối WebSocket theo device_id
urgent_acks_store : dict[str , list[dict]] = {} #Lưu lịch sử ACK của lệnh khẩn từ Agent

#Quản lý thời điểm hết hạn thiết bị và bonus time từng app/web độc lập với Policy gốc
device_unlocked_store : dict[str , int] = {} #device_id -> device_unlocked_until (timestamp)
app_bonus_store : dict[str , dict[str , int]] = {} #device_id -> {process_name : bonus_sec}
web_bonus_store : dict[str , dict[str , int]] = {} #device_id -> {domain : bonus_sec}
QUOTA_STATE_FILE = Path("quota_state.json")


def saveQuotaState() :
    #Lưu bền vững trạng thái quota/bonus trên Server xuống file
    try :
        data = {
            "device_unlocked" : device_unlocked_store ,
            "app_bonus" : app_bonus_store ,
            "web_bonus" : web_bonus_store
        }
        QUOTA_STATE_FILE.write_text(json.dumps(data) , encoding = "utf-8")
    except Exception :
        pass


def loadQuotaState() :
    #Khôi phục trạng thái quota/bonus đã lưu bền vững trên Server
    global device_unlocked_store , app_bonus_store , web_bonus_store
    if QUOTA_STATE_FILE.exists() :
        try :
            data = json.loads(QUOTA_STATE_FILE.read_text(encoding = "utf-8"))
            device_unlocked_store = {k : int(v) for k , v in data.get("device_unlocked" , {}).items()}
            app_bonus_store = {
                k : {ak : int(av) for ak , av in v.items()}
                for k , v in data.get("app_bonus" , {}).items()
            }
            web_bonus_store = {
                k : {wk : int(wv) for wk , wv in v.items()}
                for k , v in data.get("web_bonus" , {}).items()
            }
        except Exception :
            pass


loadQuotaState()


@app.post("/api/v1/enroll" , response_model = EnrollmentResponse)
def responseEnroll(payload : EnrollmentRequest) :
    #Kiểm tra hạn và tính hợp lệ 
    if curCode is None or payload.pairing_code != curCode.pairing_code or time.time() > curCode.expires_at :
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "Ma ghep doi khong hop le hoac da het han",
        )
    
    uuid_device = payload.device_fingerprint
    dev_id = f"di_{uuid_device}"
    acc_token = f"at_{uuid_device}"
    plc_id = f"plcid_{uuid_device}"

    #Lưu token tương ứng cho thiết bị
    device_tokens[dev_id] = acc_token

    #Tạo Policy mặc định
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

    #Khởi tạo device_unlocked_until, app_bonus_time và web_bonus_time độc lập với Policy gốc
    if dev_id not in device_unlocked_store :
        plc = policies_store[plc_id]
        base_quota = plc.weekend_quota if datetime.now().weekday() >= 5 else plc.weekday_quota
        device_unlocked_store[dev_id] = int(time.time()) + base_quota
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
    #1.Check device_id và access_token hợp lệ
    if device_tokens.get(payload.device_id) != payload.access_token :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID",
        )

    #2.Ghi trạng thái và usage của Agent
    device_states[payload.device_id] = {
        "status_cur": payload.status_cur,
        "quota_used": payload.quota_used,
    }

    #3.Lấy policy tương ứng
    policy = policies_store.get(payload.policy_id)
    latest_ver = policy.policy_version if policy else payload.cur_policy_version

    #4.Xử lý xác nhận (ACK) và xuất vector lệnh chờ (không xóa ngay để tự retry nếu rớt mạng)
    #Bổ sung chống cơ chế Data Integrity cho vector <cmd>
    cur_cmds = pending_cmds_store.get(payload.device_id , []) #Lấy danh sách lệnh đang lưu của thiết bị
    if payload.acked_commands : #Nếu Agent gửi kèm danh sách lệnh đã nhận thành công
        cur_cmds = [c for c in cur_cmds if c not in payload.acked_commands] #Lọc bỏ các lệnh đã được Agent xác nhận
        pending_cmds_store[payload.device_id] = cur_cmds #Lưu lại phần lệnh chưa được xác nhận để gửi tiếp

    #5.Trả về kèm trạng thái device_unlocked_until, app_bonus_time, web_bonus_time để đồng bộ
    return HeartbeatResponse(
        latest_policy_version = latest_ver ,
        pending_commands = cur_cmds ,
        device_unlocked_until = device_unlocked_store.get(payload.device_id , 0) ,
        app_bonus_time = app_bonus_store.get(payload.device_id , {}) ,
        web_bonus_time = web_bonus_store.get(payload.device_id , {})
    )


@app.get("/api/v1/policy" , response_model = Policy)
def responsePolicy(device_id : str , access_token : str , policy_id : str) :
    #1.Check device_id và access_token
    if device_tokens.get(device_id) != access_token :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED ,
            detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID" ,
        )

    #2.Lấy policy
    policy = policies_store.get(policy_id)
    if policy is None :
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND ,
            detail = "Khong tim thay Policy" ,
        )

    return policy


#WebSocket kênh lệnh khẩn
@app.websocket("/ws/urgent")
async def urgentWebsocketEndpoint(websocket : WebSocket , device_id : str , access_token : str) :
    #1.Xác thực Agent bằng device_id và access_token
    if device_tokens.get(device_id) != access_token :
        await websocket.close(code = status.WS_1008_POLICY_VIOLATION)
        return

    #2.Chấp nhận kết nối và lưu theo device_id
    await websocket.accept()
    active_ws_connections[device_id] = websocket

    #3.Lắng nghe ACK trả về từ Agent và luôn dọn kết nối an toàn trong finally
    try :
        while True :
            ack_data = await websocket.receive_json() #Nhận gói ACK từ Agent
            if isinstance(ack_data , dict) :
                urgent_acks_store.setdefault(device_id , []).append(ack_data) #Ghi nhận kết quả ACK
                if "status_cur" in ack_data and device_id in device_states :
                    device_states[device_id]["status_cur"] = ack_data["status_cur"] #Đồng bộ ngay trạng thái mới
    except WebSocketDisconnect :
        pass
    except Exception as e :
        print(f"Loi WebSocket urgent ({device_id}) : {e}")
    finally :
        #Chỉ xóa nếu kết nối đang lưu đúng là kết nối hiện tại (không xóa nhầm kết nối mới hơn của cùng device_id)
        if active_ws_connections.get(device_id) is websocket :
            active_ws_connections.pop(device_id , None)


@app.post("/api/v1/urgent")
async def sendUrgentCmd(
    device_id : str ,
    cmd : UrgentCmd ,
    parent_token : str | None = Header(default = None , alias = "X-Parent-Token")
) :
    #0.Xác thực quyền Parent/Admin qua biến môi trường PARENT_TOKEN và kiểm tra device_id đã đăng ký
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

    #1.Cập nhật bonus/hạn mức cho DEVICE, APP hoặc WEB độc lập với Policy gốc và lưu bền vững
    if cmd.cmd_type == CommandType.ADD_TIME :
        if cmd.target_type == TargetType.DEVICE :
            cur_until = device_unlocked_store.get(device_id , int(time.time()))
            device_unlocked_store[device_id] = cur_until + cmd.bonus_time
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
            cur_until = device_unlocked_store.get(device_id , int(time.time()))
            device_unlocked_store[device_id] = max(0 , cur_until - cmd.sub_time)
        elif cmd.target_type == TargetType.APP and cmd.subject :
            app_name = cmd.subject.lower().strip()
            dev_bonus = app_bonus_store.setdefault(device_id , {})
            dev_bonus[app_name] = max(0 , dev_bonus.get(app_name , 0) - cmd.sub_time)
        elif cmd.target_type == TargetType.WEB and cmd.subject :
            domain_name = cmd.subject.lower().strip()
            dev_web_bonus = web_bonus_store.setdefault(device_id , {})
            dev_web_bonus[domain_name] = max(0 , dev_web_bonus.get(domain_name , 0) - cmd.sub_time)
        saveQuotaState()

    #2.Nếu Agent đang mở WebSocket thì đẩy lệnh khẩn ngay; nếu kết nối stale/lỗi thì dọn dẹp và chuyển sang heartbeat_sync
    ws = active_ws_connections.get(device_id)
    if ws is not None :
        try :
            await ws.send_json(cmd.model_dump())
            return {"sent" : True , "via" : "websocket" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
        except Exception as e :
            print(f"Loi gui WebSocket urgent ({device_id}) : {e}")
            if active_ws_connections.get(device_id) is ws :
                active_ws_connections.pop(device_id , None)

    #3.Nếu mất kết nối WebSocket: lưu lệnh LOCK/UNLOCK vào hàng chờ Heartbeat (quota đã lưu ở bước 1)
    if cmd.cmd_type in (CommandType.LOCK , CommandType.UNLOCK) :
        cmd_id = f"{int(time.time())}:{cmd.cmd_type}"
        pending_cmds_store.setdefault(device_id , []).append(cmd_id)

    return {"sent" : False , "via" : "heartbeat_sync" , "device_id" : device_id , "cmd_type" : cmd.cmd_type}
