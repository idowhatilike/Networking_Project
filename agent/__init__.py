#Agent máy trẻ

from fastapi import FastAPI, HTTPException, Depends
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from shared.schemas import (
    BlockReason,
    CommandType,
    EventRecord,
    EventType,
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
import ctypes
from pathlib import Path
from datetime import datetime, timezone, timedelta
from enum import StrEnum
import win32com.client
import hashlib
import psutil

SERVER_URL = "http://192.168.1.10:8000"
DEFAULT_DEVICE_FINGERPRINT = "0000-0000-0000-0000-000000000000"

#Múi giờ Việt Nam (UTC+7) dùng cho Wall clock để xác định ngày lịch, ngày thường/cuối tuần và mốc reset 00:00
VN_TZ = timezone(timedelta(hours = 7))
IDLE_THRESHOLD_SEC = 300
CLOCK_TAMPER_THRESHOLD_SEC = 30
AGENT_STATE_FILE = Path("agent_quota_state.json")

#Device fingerprint: mã định danh phần cứng thiết bị (lấy từ UUID trên BIOS/UEFI)
def getMachineGuid() -> str :
    try :
        #WMI (Windows Management Instrumentation): giao diện quản trị Windows dùng để truy vấn thông tin phần cứng
        wmi = win32com.client.GetObject("winmgmts:")
        result = wmi.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")
        return next(iter(result)).UUID;
    except Exception :
        return DEFAULT_DEVICE_FINGERPRINT
cdId = getMachineGuid()


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
    #Enroll: đăng ký thiết bị lần đầu với Server bằng mã ghép đôi (pairing_code) để nhận token và policy_id
    code = getPairingCode()
    response =  httpx.post(
        ENROLL_URL , 
        json = {
            "pairing_code" : code ,
            "device_fingerprint" :  cdId 
        }   
    )

    response.raise_for_status()

    global device_id, access_token, refresh_token, policy_id
    if response.status_code == 200 :
        data = response.json()   
        device_id = data["device_id"]
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        policy_id = data["policy_id"]


def checkServerConnection() -> bool :
    try:
        httpx.get(f"{SERVER_URL}/health", timeout = 3.6)
        return True
    except httpx.RequestError :
        return False

HEARTBEAT_URL = f"{SERVER_URL}/api/v1/heartbeat"
POLICY_URL = f"{SERVER_URL}/api/v1/policy"

status_cur = "active"
#Quota: hạn mức thời gian sử dụng (giây); Bonus time: thời gian cộng/trừ thêm độc lập với Policy gốc
quota_used : dict[str , int] = {}
device_unlocked_until : int = 0
_last_synced_unlocked_until : int = 0
device_remaining_sec : float = 0.0
device_quota_used : float = 0.0
device_quota_date : str = "" #Ngày lịch VN (YYYY-MM-DD) của chu kỳ DEVICE quota hiện tại
app_bonus_time : dict[str , int] = {}
web_bonus_time : dict[str , int] = {}

#Monotonic clock: đo thời gian sử dụng và thời gian Idle độc lập với đồng hồ hệ thống (wall clock)
last_mono_ts : float | None = None
last_wall_ts : float | None = None
last_input_mono : float | None = None
_last_win_input_tick : int | None = None
event_buffer : list[EventRecord] = []

is_manual_locked : bool = False #Cờ bảo toàn trạng thái khóa thủ công của phụ huynh (chỉ gỡ khi nhận lệnh UNLOCK)
device_block_reason : BlockReason = BlockReason.NONE
app_block_reasons : dict[str , BlockReason] = {}
domain_block_reasons : dict[str , BlockReason] = {}

cur_policy_version = 0
cur_policy : Policy | None = None
blocked_domains : set[str] = set()
#ACK (Acknowledgment): thông báo xác nhận Agent đã xử lý lệnh để Server xóa khỏi hàng chờ
acked_commands : list[str] = []
executed_cmds : set[str] = set() #Tập lưu mã lệnh đã chạy để chống thực thi trùng khi Server gửi lại


class _LASTINPUTINFO(ctypes.Structure) :
    _fields_ = [
        ("cbSize" , ctypes.c_uint) ,
        ("dwTime" , ctypes.c_uint) ,
    ]


def getVnNow() -> datetime :
    return datetime.fromtimestamp(time.time() , tz = VN_TZ)


def getTodayDateStr() -> str :
    return getVnNow().strftime("%Y-%m-%d")


def getWindowsInputInfo() -> tuple[int , float] | None :
    #Đọc mốc input cuối cùng từ Windows (GetLastInputInfo) để phát hiện thao tác bàn phím/chuột mới
    try :
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)) :
            tick_now = ctypes.windll.kernel32.GetTickCount()
            elapsed_ms = (tick_now - lii.dwTime) & 0xFFFFFFFF
            return int(lii.dwTime) , max(0.0 , elapsed_ms / 1000.0)
    except Exception :
        pass
    return None


def pollWindowsInput(now_mono : float) :
    #Đồng bộ thao tác input mới từ Windows sang mốc monotonic clock để đo khoảng thời gian Idle
    global last_input_mono , _last_win_input_tick
    win_info = getWindowsInputInfo()
    if last_input_mono is None or now_mono < last_input_mono :
        last_input_mono = now_mono
        if win_info is not None :
            _last_win_input_tick = win_info[0]
        return
    if win_info is not None :
        dw_time , age_sec = win_info
        if _last_win_input_tick is None :
            _last_win_input_tick = dw_time
        elif dw_time != _last_win_input_tick :
            _last_win_input_tick = dw_time
            last_input_mono = max(last_input_mono , now_mono - age_sec)


def getIdleSeconds(now_mono : float | None = None) -> float :
    m_now = time.monotonic() if now_mono is None else now_mono
    pollWindowsInput(m_now)
    if last_input_mono is None :
        return 0.0
    return max(0.0 , m_now - last_input_mono)


def recordUserInput(mono_ts : float | None = None) :
    #Ghi nhận thao tác người dùng: chốt thời gian trước đó, cập nhật mốc input và chuyển sang Active ngay nếu máy không khóa
    global last_input_mono , last_mono_ts , _last_win_input_tick
    m_now = time.monotonic() if mono_ts is None else mono_ts
    if cur_policy is not None and last_input_mono is not None and m_now >= last_input_mono :
        if status_cur == "active" and (m_now - last_input_mono) < IDLE_THRESHOLD_SEC :
            applyPolicy()
        else :
            last_mono_ts = m_now
    last_input_mono = m_now
    win_info = getWindowsInputInfo()
    if win_info is not None :
        _last_win_input_tick = win_info[0]
    if cur_policy is not None :
        applyPolicy()


def saveAgentQuotaState() :
    #Lưu trạng thái quota ngày hiện tại xuống đĩa (không lưu mốc monotonic vì không còn hiệu lực sau reboot)
    try :
        data = {
            "device_quota_date" : device_quota_date ,
            "device_remaining_sec" : device_remaining_sec ,
            "device_quota_used" : device_quota_used ,
            "device_unlocked_until" : device_unlocked_until ,
            "is_manual_locked" : is_manual_locked ,
            "app_bonus_time" : app_bonus_time ,
            "web_bonus_time" : web_bonus_time
        }
        AGENT_STATE_FILE.write_text(json.dumps(data) , encoding = "utf-8")
    except Exception :
        pass


def loadAgentQuotaState() :
    #Khôi phục trạng thái sau khi Agent/OS khởi động lại: bỏ mốc monotonic cũ và đối chiếu ngày lịch VN (00:00 UTC+7)
    global device_quota_date , device_remaining_sec , device_quota_used , device_unlocked_until
    global _last_synced_unlocked_until , is_manual_locked , app_bonus_time , web_bonus_time
    global last_mono_ts , last_wall_ts , last_input_mono , _last_win_input_tick
    last_mono_ts = None
    last_wall_ts = None
    last_input_mono = None
    _last_win_input_tick = None
    if not AGENT_STATE_FILE.exists() :
        return
    try :
        data = json.loads(AGENT_STATE_FILE.read_text(encoding = "utf-8"))
        saved_date = str(data.get("device_quota_date" , ""))
        today_str = getTodayDateStr()
        is_manual_locked = bool(data.get("is_manual_locked" , False))
        app_bonus_time = {str(k) : int(v) for k , v in data.get("app_bonus_time" , {}).items()}
        web_bonus_time = {str(k) : int(v) for k , v in data.get("web_bonus_time" , {}).items()}

        if saved_date and today_str > saved_date and cur_policy is not None :
            now_dt = getVnNow()
            limit_sec = cur_policy.weekend_quota if now_dt.weekday() >= 5 else cur_policy.weekday_quota
            device_remaining_sec = float(limit_sec)
            device_quota_used = 0.0
            quota_used.pop("__device__" , None)
            device_unlocked_until = int(time.time()) + limit_sec
            _last_synced_unlocked_until = device_unlocked_until
            device_quota_date = today_str
            saveAgentQuotaState()
        else :
            device_quota_date = saved_date or today_str
            device_remaining_sec = max(0.0 , float(data.get("device_remaining_sec" , 0.0)))
            device_quota_used = max(0.0 , float(data.get("device_quota_used" , 0.0)))
            if device_quota_used > 0 :
                quota_used["__device__"] = int(round(device_quota_used))
            if device_remaining_sec <= 0 :
                device_unlocked_until = 0
            else :
                device_unlocked_until = int(time.time()) + int(round(device_remaining_sec))
            _last_synced_unlocked_until = device_unlocked_until
    except Exception :
        pass


def getAppRemainingQuota(process_name : str) -> int :
    #Thời gian còn lại: remain = max(0, policy_quota + total_adjustment - used_time)
    if cur_policy is None :
        return 0
    a_name = process_name.lower().strip()
    for r in cur_policy.app_rules :
        if r.exe_name.lower() == a_name :
            if not r.allowed :
                return 0
            total_adj = app_bonus_time.get(a_name , 0)
            used = quota_used.get(a_name , 0)
            return max(0 , r.quota + total_adj - used)
    return 0


def getWebRemainingQuota(domain : str) -> int :
    if cur_policy is None :
        return 0
    d_name = domain.lower().strip()
    for r in cur_policy.domain_rules :
        if r.domain.lower() == d_name :
            if not r.allowed :
                return 0
            total_adj = web_bonus_time.get(d_name , 0)
            used = quota_used.get(d_name , 0)
            return max(0 , r.quota + total_adj - used)
    return 0


def applyPolicy() :
    global status_cur , blocked_domains , device_unlocked_until , _last_synced_unlocked_until
    global device_remaining_sec , device_quota_used , device_quota_date
    global last_mono_ts , last_wall_ts , device_block_reason , app_block_reasons , domain_block_reasons
    if cur_policy is None :
        return

    #1.Đánh giá hạn mức Website: phân biệt bị cấm bởi Policy hay hết Web Quota (remain == 0)
    blocked_domains = set()
    for r in cur_policy.domain_rules :
        d_name = r.domain.lower()
        if not r.allowed :
            domain_block_reasons[d_name] = BlockReason.POLICY
            blocked_domains.add(d_name)
        elif r.quota > 0 :
            remain = max(0 , r.quota + web_bonus_time.get(d_name , 0) - quota_used.get(d_name , 0))
            if remain == 0 :
                domain_block_reasons[d_name] = BlockReason.WEB_QUOTA
                blocked_domains.add(d_name)
            else :
                domain_block_reasons[d_name] = BlockReason.NONE
        else :
            domain_block_reasons[d_name] = BlockReason.NONE

    #2.Đánh giá hạn mức Ứng dụng (theo tên tiến trình): chỉ tắt ứng dụng vi phạm, không khóa toàn thiết bị
    blocked_names = set()
    for r in cur_policy.app_rules :
        a_name = r.exe_name.lower()
        if not r.allowed :
            app_block_reasons[a_name] = BlockReason.POLICY
            blocked_names.add(a_name)
        elif r.quota > 0 :
            remain = max(0 , r.quota + app_bonus_time.get(a_name , 0) - quota_used.get(a_name , 0))
            if remain == 0 :
                app_block_reasons[a_name] = BlockReason.APP_QUOTA
                blocked_names.add(a_name)
            else :
                app_block_reasons[a_name] = BlockReason.NONE
        else :
            app_block_reasons[a_name] = BlockReason.NONE

    if blocked_names :
        for proc in psutil.process_iter(["name"]) :
            try :
                p_name = (proc.info["name"] or "").lower()
                if p_name in blocked_names :
                    proc.kill()
            except Exception :
                continue

    #3.Quản lý thời gian thiết bị: dùng Wall clock (UTC+7) cho lịch ngày và Monotonic clock cho thời gian sử dụng
    now_wall = time.time()
    now_mono = time.monotonic()

    #Đồng bộ khi device_unlocked_until được gán mới từ Server hoặc lệnh điều khiển
    if device_unlocked_until != _last_synced_unlocked_until or (device_unlocked_until == 0 and device_remaining_sec > 0) :
        if device_unlocked_until <= 0 or device_unlocked_until <= int(now_wall) :
            device_remaining_sec = 0.0
        else :
            device_remaining_sec = float(device_unlocked_until - int(now_wall))
        _last_synced_unlocked_until = device_unlocked_until
        last_mono_ts = now_mono
        last_wall_ts = now_wall

    #Phát hiện chỉnh lùi đồng hồ hệ thống bất thường: ghi nhận sự kiện và không dùng wall clock để tính elapsed time
    if last_wall_ts is not None and last_mono_ts is not None and now_mono >= last_mono_ts :
        wall_delta = now_wall - last_wall_ts
        mono_delta_check = now_mono - last_mono_ts
        if wall_delta - mono_delta_check < -CLOCK_TAMPER_THRESHOLD_SEC :
            event_buffer.append(EventRecord(
                idempotency_key = str(uuid.uuid4()) ,
                ts = int(now_wall) ,
                device_id = device_id or "unknown_device" ,
                child_id = "child_default" ,
                type = EventType.QUOTA_WARNING ,
                subject = "clock_tamper" ,
                duration_sec = int(abs(wall_delta - mono_delta_check)) ,
                policy_id = cur_policy.policy_id
            ))

    #Nếu vừa khởi động hoặc sau reboot (now_mono < last_mono_ts) thì khởi tạo lại mốc monotonic, không dùng mốc cũ
    if last_mono_ts is None or now_mono < last_mono_ts :
        mono_delta = 0.0
    else :
        mono_delta = now_mono - last_mono_ts
    last_mono_ts = now_mono
    last_wall_ts = now_wall

    now_dt = getVnNow()
    day_idx = now_dt.weekday()
    slot_idx = now_dt.hour * 2 + (now_dt.minute // 30)
    limit_sec = cur_policy.weekend_quota if day_idx >= 5 else cur_policy.weekday_quota
    today_str = now_dt.strftime("%Y-%m-%d")

    #Chỉ reset DEVICE quota một lần khi qua 00:00 giờ Việt Nam sang ngày mới (today_str > device_quota_date)
    if device_quota_date == "" :
        device_quota_date = today_str
    elif today_str > device_quota_date :
        device_remaining_sec = float(limit_sec)
        device_quota_used = 0.0
        quota_used.pop("__device__" , None)
        device_unlocked_until = int(now_wall) + limit_sec
        _last_synced_unlocked_until = device_unlocked_until
        device_quota_date = today_str
        mono_delta = 0.0

    #Xác định trạng thái Idle/Active và chỉ trừ DEVICE quota khi máy đang Active (không khóa và có input trong 5 phút)
    idle_sec = getIdleSeconds(now_mono)
    is_idle_now = idle_sec >= IDLE_THRESHOLD_SEC
    is_schedule_locked = not cur_policy.schedule_7x48[day_idx][slot_idx]
    was_locked = (status_cur == "locked") or is_manual_locked or is_schedule_locked or (device_remaining_sec <= 0)

    if not was_locked and not is_idle_now and status_cur == "active" and mono_delta > 0 :
        consumed = min(device_remaining_sec , mono_delta)
        device_remaining_sec = max(0.0 , device_remaining_sec - consumed)
        device_quota_used += consumed
        quota_used["__device__"] = int(round(device_quota_used))

    if device_remaining_sec <= 0 :
        device_remaining_sec = 0.0
        device_unlocked_until = 0
    else :
        device_unlocked_until = int(now_wall) + int(round(device_remaining_sec))
    _last_synced_unlocked_until = device_unlocked_until

    #Ưu tiên khóa thủ công (POLICY), sau đó đến lịch tuần (SCHEDULE), hết quota (DEVICE_QUOTA), cuối cùng là Idle/Active
    if is_manual_locked :
        status_cur = "locked"
        device_block_reason = BlockReason.POLICY
    elif is_schedule_locked :
        status_cur = "locked"
        device_block_reason = BlockReason.SCHEDULE
    elif device_remaining_sec <= 0 :
        status_cur = "locked"
        device_block_reason = BlockReason.DEVICE_QUOTA
    else :
        device_block_reason = BlockReason.NONE
        status_cur = "idle" if is_idle_now else "active"


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
    #Heartbeat: gửi báo cáo định kỳ kèm danh sách ACK lên Server; chỉ xóa acked_commands khi gửi thành công
    response = httpx.post(
        HEARTBEAT_URL , 
        json = {
            "device_id" : device_id ,
            "access_token" : access_token ,
            "policy_id" : policy_id ,
            "status_cur" : status_cur ,
            "quota_used" : quota_used ,
            "cur_policy_version" : cur_policy_version ,
            "acked_commands" : acked_commands
        } ,
        timeout = 3.6
    )
    
    response.raise_for_status()
    acked_commands.clear()
    return HeartbeatResponse(**response.json())

def HeartbeatResponseHanlder(data : HeartbeatResponse) :
    global cur_policy , cur_policy_version , device_unlocked_until , _last_synced_unlocked_until
    global device_remaining_sec , device_quota_date , app_bonus_time , web_bonus_time
    #1.Đồng bộ trạng thái quota/bonus từ Server (kể cả khi device_unlocked_until == 0 do đã cạn quota trong ngày)
    if data.device_quota_date :
        device_quota_date = data.device_quota_date
    if data.device_unlocked_until is not None :
        device_unlocked_until = data.device_unlocked_until
        now_wall = int(time.time())
        if device_unlocked_until <= 0 or device_unlocked_until <= now_wall :
            device_remaining_sec = 0.0
        else :
            device_remaining_sec = float(device_unlocked_until - now_wall)
        _last_synced_unlocked_until = device_unlocked_until
    if data.app_bonus_time :
        app_bonus_time = dict(data.app_bonus_time)
    if data.web_bonus_time :
        web_bonus_time = dict(data.web_bonus_time)

    #2.Cập nhật Policy mới nếu lệch phiên bản
    if data.latest_policy_version > cur_policy_version :
        cur_policy = requestPolicy()
        cur_policy_version = cur_policy.policy_version

    if cur_policy is not None :
        applyPolicy()

    #3.Xử lý lệnh chờ qua hàm thực thi chung execCmd để đồng nhất ngữ nghĩa với kênh WebSocket
    for cmd in data.pending_commands :
        if cmd not in executed_cmds :
            raw_cmd = cmd.split(":")[-1].strip().lower()
            if raw_cmd in (CommandType.LOCK , CommandType.UNLOCK) :
                execCmd(UrgentCmd(cmd_type = CommandType(raw_cmd)))
            executed_cmds.add(cmd)

        if cmd not in acked_commands :
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


#Thực thi lệnh điều khiển dùng chung cho cả kênh Heartbeat và kênh WebSocket
def execCmd(cmd : UrgentCmd) :
    global status_cur , device_unlocked_until , _last_synced_unlocked_until , device_remaining_sec
    global app_bonus_time , web_bonus_time , device_block_reason , is_manual_locked
    global last_mono_ts , last_wall_ts
    #1.Khóa thủ công toàn thiết bị: chốt thời gian Active trước khi khóa rồi bật cờ is_manual_locked
    if cmd.cmd_type == CommandType.LOCK :
        if cur_policy is not None and status_cur == "active" :
            applyPolicy()
        is_manual_locked = True
        status_cur = "locked"
        device_block_reason = BlockReason.POLICY
        last_mono_ts = time.monotonic()
        last_wall_ts = time.time()
        return
    #2.Gỡ khóa thủ công: đóng khoảng thời gian khóa (không tính quota), tắt cờ is_manual_locked rồi gọi applyPolicy
    elif cmd.cmd_type == CommandType.UNLOCK :
        last_mono_ts = time.monotonic()
        last_wall_ts = time.time()
        is_manual_locked = False
        status_cur = "active"
        device_block_reason = BlockReason.NONE
        applyPolicy()
        return

    #3.Cộng thêm thời gian (ADD_TIME) cho DEVICE, APP hoặc WEB
    if cmd.cmd_type == CommandType.ADD_TIME :
        if cmd.target_type == TargetType.DEVICE :
            if cur_policy is not None and status_cur == "active" :
                applyPolicy()
            device_remaining_sec = max(0.0 , device_remaining_sec) + float(cmd.bonus_time)
            now_wall = int(time.time())
            if device_unlocked_until == 0 or device_unlocked_until < now_wall :
                device_unlocked_until = now_wall + cmd.bonus_time
            else :
                device_unlocked_until += cmd.bonus_time
            _last_synced_unlocked_until = device_unlocked_until
        elif cmd.target_type == TargetType.APP and cmd.subject :
            a_name = cmd.subject.lower().strip()
            app_bonus_time[a_name] = app_bonus_time.get(a_name , 0) + cmd.bonus_time
        elif cmd.target_type == TargetType.WEB and cmd.subject :
            d_name = cmd.subject.lower().strip()
            web_bonus_time[d_name] = web_bonus_time.get(d_name , 0) + cmd.bonus_time
        applyPolicy()

    #4.Trừ bớt thời gian (SUB_TIME): cho phép điều chỉnh âm để trừ trực tiếp vào ngân sách quota gốc
    elif cmd.cmd_type == CommandType.SUB_TIME :
        if cmd.target_type == TargetType.DEVICE :
            if cur_policy is not None and status_cur == "active" :
                applyPolicy()
            device_unlocked_until = max(0 , device_unlocked_until - cmd.sub_time)
            now_wall = int(time.time())
            if device_unlocked_until <= 0 or device_unlocked_until <= now_wall :
                device_remaining_sec = 0.0
            else :
                device_remaining_sec = float(device_unlocked_until - now_wall)
            _last_synced_unlocked_until = device_unlocked_until
        elif cmd.target_type == TargetType.APP and cmd.subject :
            a_name = cmd.subject.lower().strip()
            app_bonus_time[a_name] = app_bonus_time.get(a_name , 0) - cmd.sub_time
        elif cmd.target_type == TargetType.WEB and cmd.subject :
            d_name = cmd.subject.lower().strip()
            web_bonus_time[d_name] = web_bonus_time.get(d_name , 0) - cmd.sub_time
        applyPolicy()


#WebSocket: kênh kết nối duy trì liên tục giúp Agent nhận lệnh khẩn từ Server theo thời gian thực
WS_URGENT_URL = SERVER_URL.replace("http" , "ws") + "/ws/urgent"
ws_handler_running : bool = False

async def UrgentCmdHandler(
    stop_event : asyncio.Event | None = None ,
    max_retries : int | None = None ,
    base_delay : float = 1.0 ,
    max_delay : float = 30.0
) :
    global ws_handler_running
    #Ngăn khởi chạy trùng nhiều trình lắng nghe WebSocket cùng lúc
    if ws_handler_running :
        print("UrgentCmdHandler dang chay, bo qua khoi tao trung")
        return

    ws_handler_running = True
    attempt = 0
    try :
        while stop_event is None or not stop_event.is_set() :
            ws_url = f"{WS_URGENT_URL}?device_id={device_id}&access_token={access_token}"
            try :
                async with websockets.connect(ws_url) as websocket :
                    attempt = 0
                    while stop_event is None or not stop_event.is_set() :
                        data = await websocket.recv()
                        try :
                            cmd = UrgentCmd(**json.loads(data))
                        except Exception as parse_err :
                            print(f"Loi goi tin UrgentCmd : {parse_err}")
                            continue

                        execCmd(cmd)

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
                #Exponential backoff: tăng dần thời gian chờ giữa các lần thử kết nối lại theo lũy thừa
                delay = min(max_delay , base_delay * (2 ** (attempt - 1)))
                await asyncio.sleep(delay)
    finally :
        ws_handler_running = False
