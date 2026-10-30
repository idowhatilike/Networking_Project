#Server

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from shared.schemas import (
    EnrollmentRequest,
    EnrollmentResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    PairingCode,
    Policy,
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

#Bộ nhớ tạm trên Server
device_tokens : dict[str , str] = {}
device_states : dict[str , dict] = {}
policies_store : dict[str , Policy] = {}
pending_cmds_store : dict[str , list[str]] = {}

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

    return EnrollmentResponse(
        device_id = dev_id,
        access_token = acc_token,
        refresh_token = f"rt_{uuid_device}",
        policy_id = plc_id
    )


@app.post("/api/v1/heartbeat" , response_model = HeartbeatResponse)
def responseHeartbeat(payload : HeartbeatRequest) : #4 bước - Code bởi antigravity
    #1.Check device_id và access_token hợp lệ
    if device_tokens.get(payload.device_id) != payload.access_token :
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "ACCESS_TOKEN khong tuong ung voi DEVICE_ID",
        )

    #2.Ghi trạng thái của Agent
    device_states[payload.device_id] = {
        "status_cur": payload.status_cur,
        "quota_used": payload.quota_used,
    }

    #3.Lấy policy tương ứng
    policy = policies_store.get(payload.policy_id)
    latest_ver = policy.policy_version if policy else payload.cur_policy_version

    #4.Lấy danh sách lệnh
    cmds = pending_cmds_store.pop(payload.device_id, [])

    return HeartbeatResponse(
        latest_policy_version = latest_ver ,
        pending_commands = cmds
    )


@app.get("/api/v1/policy" , response_model = Policy)
def responsePolicy(device_id : str , access_token : str , policy_id : str) : #Code bởi antigravity
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