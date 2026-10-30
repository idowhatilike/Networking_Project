#Agent máy trẻ

from fastapi import FastAPI, HTTPException, Depends
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from shared.schemas import HeartbeatResponse , Policy
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
import hashlib
import psutil

SERVER_URL = "http://192.168.1.10:8000"
DEFAULT_DEVICE_FINGERPRINT = "0000-0000-0000-0000-000000000000"

# device fingerprint = UUID = Id trên chip BIOS/UEFI
def getMachineGuid() -> str :
    try :
        #Connect WMI - Windows Management Instrumentation
        wmi = win32com.client.GetObject("winmgmts:")
        #Yêu cầu lấy mỗi UUID từ class Win32_ComputerSystemProduct 
        result = wmi.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")
        return next(iter(result)).UUID;
    except Exception :
        return DEFAULT_DEVICE_FINGERPRINT
cdId = getMachineGuid() #current_deviced_fingerprint


pairing_time_count = 0
def getPairingCode(prompt : str = "Ma ghep enroll: " , max_attempts : int = 5) -> str :
    for __ in range(max_attempts) :
        code = input(prompt).strip()
        if len(code) == 8 :
            pairing_time_count = time.time()
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
quota_used : dict[str , int] = {}
cur_policy_version = 0
cur_policy : Policy | None = None
blocked_domains : set[str] = set()


def applyPolicy() : #Code bởi antigravity
    global status_cur , blocked_domains
    if cur_policy is None :
        return

    #1.Cập nhật danh sách web bị chặn
    blocked_domains = {r.domain.lower() for r in cur_policy.domain_rules if not r.allowed}

    #2.Quét và tắt app bị chặn theo tên
    blocked_names = {r.exe_name.lower() for r in cur_policy.app_rules if not r.allowed}
    for proc in psutil.process_iter(["name"]) :
        try :
            p_name = (proc.info["name"] or "").lower()
            if p_name in blocked_names :
                proc.kill()
        except Exception :
            continue

    #3.Kiểm tra lịch tuần 7x48 và hạn mức ngày
    now = datetime.now() #Lấy giờ hệ thống hiện tại
    day_idx = now.weekday() #Thứ trong tuần: 0(Thứ 2)->4(Thứ 6), 5(Thứ 7), 6(CN)
    slot_idx = now.hour * 2 + (now.minute // 30) #Khung 30p thứ mấy trong 48 khung (0->47)
    limit_sec = cur_policy.weekend_quota if day_idx >= 5 else cur_policy.weekday_quota #Chọn quota cuối tuần hoặc ngày thường
    total_used = sum(quota_used.values()) #Tổng số giây đã dùng của mọi app/web
    if not cur_policy.schedule_7x48[day_idx][slot_idx] or total_used >= limit_sec : #Ngoài khung giờ hoặc hết quota
        status_cur = "locked"


def requestPolicy() : #Code bởi antigravity
    response = httpx.get(
        POLICY_URL ,
        params = {
            "device_id" : device_id ,
            "access_token" : access_token ,
            "policy_id" : policy_id
        }
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
            "cur_policy_version" : cur_policy_version
        }
    )
    
    response.raise_for_status()
    return HeartbeatResponse(**response.json())

def HeartbeatResponseHanlder(data : HeartbeatResponse) : #Code bởi antigravity
    global cur_policy , cur_policy_version , status_cur
    #1.Cập nhật và áp dụng Policy mới nếu lệch version
    if data.latest_policy_version > cur_policy_version :
        cur_policy = requestPolicy()
        cur_policy_version = cur_policy.policy_version
        applyPolicy()

    #2.Xử lý lệnh chờ
    for cmd in data.pending_commands :
        if cmd == "lock" :
            status_cur = "locked"
        elif cmd == "unlock" :
            status_cur = "active"


def requestHeartbeat_loop(interval : int = 60) : #Tránh magic number :! Chisikudo advice
    while True :
        try :
            if checkServerConnection() :
                response = requestHeartbeat()
                HeartbeatResponseHanlder(response)
        except Exception as e :
            print(f"Loi : {e}")
        time.sleep(interval)

