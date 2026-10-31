#Agent máy trẻ

from fastapi import FastAPI, HTTPException, Depends
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from shared.schemas import (
    BlockReason,
    CommandType,
    HeartbeatResponse,
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
import asyncio
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
import hashlib
import psutil

SERVER_URL = "http://192.168.1.10:8000"
DEFAULT_DEVICE_FINGERPRINT = "0000-0000-0000-0000-000000000000"

# device fingerprint = UUID = Id trên chip BIOS/UEFI
def getMachineGuid() -> str :
    try :
        #Connect WMI
        wmi = win32com.client.GetObject("winmgmts:")
        #Yêu cầu lấy mỗi UUID từ class Win32_ComputerSystemProduct 
        result = wmi.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")
        return next(iter(result)).UUID;
    except Exception :
        return DEFAULT_DEVICE_FINGERPRINT
cdId = getMachineGuid() #current_deviced_fingerprint


def getPairingCode(prompt : str = "Ma ghep enroll: " , max_attempts : int = 5) -> str :
    for __ in range(max_attempts) :
        code = input(prompt).strip()
        if len(code) == 8 :
            return code
        print("Ma ghep phai dung 8 ky tu")
    raise ValueError("Nhap ma ghep that bai")

device_id = None
access_token = None
refresh_token = None
policy_id = None

ENROLL_URL = f"{SERVER_URL}/api/v1/enroll"

def requestEnroll() :
    #Gửi dữ liệu bằng http method post 
    code = getPairingCode()
    response =  httpx.post(
        ENROLL_URL , 
        json = {
            "pairing_code" : code ,
            "device_fingerprint" :  cdId 
        }   
    )

    #Nếu gặp lỗi
    response.raise_for_status()

    #Nếu thành công
    global device_id, access_token, refresh_token, policy_id
    if response.status_code == 200 :
        data = response.json()   
        device_id = data["device_id"]
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        policy_id = data["policy_id"]


#Kiểm tra kết nối với server
def checkServerConnection() -> bool :
    try:
        httpx.get(f"{SERVER_URL}/health", timeout = 3.6)
        return True
    except httpx.RequestError :
        return False

HEARTBEAT_URL = f"{SERVER_URL}/api/v1/heartbeat"
POLICY_URL = f"{SERVER_URL}/api/v1/policy"

status_cur = "active"
quota_used : dict[str , int] = {} #Thời gian đã dùng của từng process_name / domain
device_unlocked_until : int = 0 #Thời điểm hết hạn dùng toàn thiết bị (Device-level quota)
app_bonus_time : dict[str , int] = {} #Bonus time riêng từng ứng dụng (độc lập với Policy gốc)
web_bonus_time : dict[str , int] = {} #Bonus time riêng từng website/domain (độc lập với Policy gốc)

device_block_reason : BlockReason = BlockReason.NONE #Nguyên nhân khóa toàn thiết bị
app_block_reasons : dict[str , BlockReason] = {} #Nguyên nhân chặn của từng ứng dụng
domain_block_reasons : dict[str , BlockReason] = {} #Nguyên nhân chặn của từng website/domain

cur_policy_version = 0
cur_policy : Policy | None = None
blocked_domains : set[str] = set()
acked_commands : list[str] = [] #Danh sách lệnh chờ báo xác nhận (ACK) về Server
executed_cmds : set[str] = set() #Tập hợp lưu các lệnh đã chạy để chống thực thi trùng


def getAppRemainingQuota(process_name : str) -> int :
    #Tính quota còn lại của ứng dụng = quota gốc + bonus time - usage
    if cur_policy is None :
        return 0
    a_name = process_name.lower().strip()
    for r in cur_policy.app_rules :
        if r.exe_name.lower() == a_name :
            bonus = app_bonus_time.get(a_name , 0)
            used = quota_used.get(a_name , 0)
            return r.quota + bonus - used
    return 0


def getWebRemainingQuota(domain : str) -> int :
    #Tính quota còn lại của website = quota gốc + bonus time - usage
    if cur_policy is None :
        return 0
    d_name = domain.lower().strip()
    for r in cur_policy.domain_rules :
        if r.domain.lower() == d_name :
            bonus = web_bonus_time.get(d_name , 0)
            used = quota_used.get(d_name , 0)
            return r.quota + bonus - used
    return 0


def applyPolicy() :
    global status_cur , blocked_domains , device_unlocked_until
    global device_block_reason , app_block_reasons , domain_block_reasons
    if cur_policy is None :
        return

    #1.Kiểm tra Web-level quota: phân biệt chặn do Policy hay hết Web Quota
    blocked_domains = set()
    for r in cur_policy.domain_rules :
        d_name = r.domain.lower()
        if not r.allowed :
            domain_block_reasons[d_name] = BlockReason.POLICY #Bị cấm trực tiếp trong Policy
            blocked_domains.add(d_name)
        elif r.quota > 0 :
            remaining = r.quota + web_bonus_time.get(d_name , 0) - quota_used.get(d_name , 0)
            if remaining <= 0 :
                domain_block_reasons[d_name] = BlockReason.WEB_QUOTA #Hết quota riêng của website
                blocked_domains.add(d_name)
            else :
                domain_block_reasons[d_name] = BlockReason.NONE
        else :
            domain_block_reasons[d_name] = BlockReason.NONE

    #2.Kiểm tra App-level quota (theo process name): phân biệt chặn do Policy hay hết App Quota
    blocked_names = set()
    for r in cur_policy.app_rules :
        a_name = r.exe_name.lower()
        if not r.allowed :
            app_block_reasons[a_name] = BlockReason.POLICY #Bị cấm trực tiếp trong Policy
            blocked_names.add(a_name)
        elif r.quota > 0 :
            remaining = r.quota + app_bonus_time.get(a_name , 0) - quota_used.get(a_name , 0)
            if remaining <= 0 :
                app_block_reasons[a_name] = BlockReason.APP_QUOTA #Hết quota riêng của ứng dụng
                blocked_names.add(a_name)
            else :
                app_block_reasons[a_name] = BlockReason.NONE
        else :
            app_block_reasons[a_name] = BlockReason.NONE

    #Chỉ chặn ứng dụng vi phạm (không khóa toàn thiết bị khi chỉ hết App Quota)
    if blocked_names :
        for proc in psutil.process_iter(["name"]) :
            try :
                p_name = (proc.info["name"] or "").lower()
                if p_name in blocked_names :
                    proc.kill()
            except Exception :
                continue

    #3.Kiểm tra Schedule (7x48) và Device-level quota (device_unlocked_until)
    now_dt = datetime.now() #Lấy giờ hệ thống hiện tại
    day_idx = now_dt.weekday() #Thứ trong tuần: 0(Thứ 2)->4(Thứ 6), 5(Thứ 7), 6(CN)
    slot_idx = now_dt.hour * 2 + (now_dt.minute // 30) #Khung 30p thứ mấy trong 48 khung (0->47)
    limit_sec = cur_policy.weekend_quota if day_idx >= 5 else cur_policy.weekday_quota #Quota thiết bị gốc từ Policy

    #Khởi tạo device_unlocked_until lần đầu nếu chưa được đặt
    if device_unlocked_until == 0 :
        device_unlocked_until = int(time.time()) + limit_sec

    if not cur_policy.schedule_7x48[day_idx][slot_idx] : #Ngoài khung giờ lịch tuần
        status_cur = "locked"
        device_block_reason = BlockReason.SCHEDULE
    elif time.time() >= device_unlocked_until : #Hết hạn thời gian toàn thiết bị
        status_cur = "locked"
        device_block_reason = BlockReason.DEVICE_QUOTA
    else :
        status_cur = "active"
        device_block_reason = BlockReason.NONE


def requestPolicy() :
    response = httpx.get(
        POLICY_URL ,
        params = {
            "device_id" : device_id ,
            "access_token" : access_token ,
            "policy_id" : policy_id
        } ,
        timeout = 3.6
    )
    response.raise_for_status()
    return Policy(**response.json())


def requestHeartbeat() :
    response = httpx.post(
        HEARTBEAT_URL , 
        json = {
            "device_id" : device_id ,
            "access_token" : access_token ,
            "policy_id" : policy_id ,
            "status_cur" : status_cur ,
            "quota_used" : quota_used ,
            "cur_policy_version" : cur_policy_version ,
            "acked_commands" : acked_commands #Gửi danh sách lệnh đã nhận để Server xóa khỏi hàng chờ
        } ,
        timeout = 3.6
    )
    
    response.raise_for_status() #Nếu mất mạng/lỗi sẽ dừng tại đây, acked_commands vẫn còn để nhịp sau retry
    acked_commands.clear() #Gửi thành công lên Server thì làm trống danh sách chờ xác nhận
    return HeartbeatResponse(**response.json())

def HeartbeatResponseHanlder(data : HeartbeatResponse) :
    global cur_policy , cur_policy_version , status_cur , device_unlocked_until
    global app_bonus_time , web_bonus_time , device_block_reason
    #1.Đồng bộ trạng thái quota/bonus từ Server (hỗ trợ khôi phục khi Agent restart hoặc rớt WebSocket)
    if data.device_unlocked_until > 0 :
        device_unlocked_until = data.device_unlocked_until
    if data.app_bonus_time :
        app_bonus_time = dict(data.app_bonus_time)
    if data.web_bonus_time :
        web_bonus_time = dict(data.web_bonus_time)

    #2.Cập nhật Policy mới nếu lệch version (không ghi đè bonus time)
    if data.latest_policy_version > cur_policy_version :
        cur_policy = requestPolicy()
        cur_policy_version = cur_policy.policy_version

    if cur_policy is not None :
        applyPolicy()

    #3.Xử lý lệnh chờ (lưu ACK, retry khi lỗi và chống thực thi trùng)
    for cmd in data.pending_commands :
        if cmd not in executed_cmds : #Kiểm tra biến chống trùng: chỉ chạy nếu lệnh này chưa từng chạy
            if cmd == "lock" or cmd.endswith(":lock") :
                status_cur = "locked"
                device_block_reason = BlockReason.POLICY
            elif cmd == "unlock" or cmd.endswith(":unlock") :
                status_cur = "active"
                device_block_reason = BlockReason.NONE
            executed_cmds.add(cmd) #Ghi vào biến chống trùng để nếu Server gửi lại cũng không chạy lần 2

        if cmd not in acked_commands : #Đưa lệnh vào danh sách chờ báo xác nhận (ACK) ở nhịp Heartbeat sau
            acked_commands.append(cmd)


def requestHeartbeatLoop(interval : int = 60) : #Tránh magic number :! Chisikudo advice
    while True :
        try :
            if checkServerConnection() :
                response = requestHeartbeat()
                HeartbeatResponseHanlder(response)
        except Exception as e :
            print(f"Loi : {e}")
        time.sleep(interval)


#Thực thi lệnh khẩn (tách riêng khỏi logic nhận WebSocket)
def executeUrgentCmd(cmd : UrgentCmd) :
    global status_cur , device_unlocked_until , app_bonus_time , web_bonus_time , device_block_reason
    #1.Khóa toàn bộ thiết bị ngay
    if cmd.cmd_type == CommandType.LOCK :
        status_cur = "locked"
        device_block_reason = BlockReason.POLICY
        return
    #2.Mở khóa thiết bị
    elif cmd.cmd_type == CommandType.UNLOCK :
        status_cur = "active"
        device_block_reason = BlockReason.NONE
        return

    #3.Cộng thêm thời gian (ADD_TIME) cho DEVICE, APP hoặc WEB độc lập với Policy gốc
    if cmd.cmd_type == CommandType.ADD_TIME :
        if cmd.target_type == TargetType.DEVICE :
            if device_unlocked_until == 0 :
                device_unlocked_until = int(time.time())
            device_unlocked_until += cmd.bonus_time
        elif cmd.target_type == TargetType.APP and cmd.subject :
            a_name = cmd.subject.lower().strip()
            app_bonus_time[a_name] = app_bonus_time.get(a_name , 0) + cmd.bonus_time
        elif cmd.target_type == TargetType.WEB and cmd.subject :
            d_name = cmd.subject.lower().strip()
            web_bonus_time[d_name] = web_bonus_time.get(d_name , 0) + cmd.bonus_time
        applyPolicy()

    #4.Trừ bớt thời gian (SUB_TIME) của DEVICE, APP hoặc WEB độc lập với Policy gốc
    elif cmd.cmd_type == CommandType.SUB_TIME :
        if cmd.target_type == TargetType.DEVICE :
            device_unlocked_until = max(0 , device_unlocked_until - cmd.sub_time)
        elif cmd.target_type == TargetType.APP and cmd.subject :
            a_name = cmd.subject.lower().strip()
            app_bonus_time[a_name] = max(0 , app_bonus_time.get(a_name , 0) - cmd.sub_time)
        elif cmd.target_type == TargetType.WEB and cmd.subject :
            d_name = cmd.subject.lower().strip()
            web_bonus_time[d_name] = max(0 , web_bonus_time.get(d_name , 0) - cmd.sub_time)
        applyPolicy()


#Nhận lệnh khẩn qua WebSocket và gửi ACK (có chống chạy trùng, tự kết nối lại với exponential backoff và dừng an toàn)
WS_URGENT_URL = SERVER_URL.replace("http" , "ws") + "/ws/urgent"
ws_handler_running : bool = False

async def UrgentCmdHandler(
    stop_event : asyncio.Event | None = None ,
    max_retries : int | None = None ,
    base_delay : float = 1.0 ,
    max_delay : float = 30.0
) :
    global ws_handler_running
    #Ngăn chặn khởi chạy trùng nhiều UrgentCmdHandler cùng lúc
    if ws_handler_running :
        print("UrgentCmdHandler dang chay, bo qua khoi tao trung")
        return

    ws_handler_running = True
    attempt = 0
    try :
        while stop_event is None or not stop_event.is_set() :
            ws_url = f"{WS_URGENT_URL}?device_id={device_id}&access_token={access_token}"
            try :
                #1.Thiết lập kết nối WebSocket với Server
                async with websockets.connect(ws_url) as websocket :
                    attempt = 0 #Reset bộ đếm retry khi đã kết nối thành công
                    while stop_event is None or not stop_event.is_set() :
                        #2.Nhận gói tin, parse JSON và validate bằng UrgentCmd
                        data = await websocket.recv()
                        try :
                            cmd = UrgentCmd(**json.loads(data))
                        except Exception as parse_err :
                            print(f"Loi goi tin UrgentCmd : {parse_err}")
                            continue

                        #3.Gọi hàm thực thi riêng
                        executeUrgentCmd(cmd)

                        #4.Gửi ACK báo kết quả thực thi về Server
                        ack_payload = {
                            "status" : "ack" ,
                            "cmd_type" : cmd.cmd_type ,
                            "target_type" : cmd.target_type ,
                            "subject" : cmd.subject ,
                            "status_cur" : status_cur ,
                            "device_unlocked_until" : device_unlocked_until ,
                            "app_bonus_time" : app_bonus_time ,
                            "web_bonus_time" : web_bonus_time
                        }
                        await websocket.send(json.dumps(ack_payload))
            except asyncio.CancelledError :
                raise
            except Exception as conn_err :
                attempt += 1
                print(f"Loi ket noi WebSocket urgent (lan {attempt}) : {conn_err}")
                if max_retries is not None and attempt > max_retries :
                    break
                if stop_event is not None and stop_event.is_set() :
                    break
                delay = min(max_delay , base_delay * (2 ** (attempt - 1)))
                await asyncio.sleep(delay)
    finally :
        ws_handler_running = False
