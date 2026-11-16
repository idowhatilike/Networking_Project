#Dữ liệu trao đổi giữa Server và Agent.


import ctypes
import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EventType(StrEnum) :
    #Phân loại sự kiện phát sinh trên Agent
    APP_START = "app_start"
    APP_STOP = "app_stop"
    DOMAIN_QUERY = "domain_query"
    BLOCKED_APP = "blocked_app"
    BLOCKED_DOMAIN = "blocked_domain"
    QUOTA_WARNING = "quota_warning"
    LOCKED = "locked"
    UNLOCK_REQUEST = "unlock_request"
    OVERRIDE_GRANTED = "override_granted" #Quyền ghi đè tạm thời do phụ huynh cấp


class DomainCategory(StrEnum) :
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    SOCIAL = "social"
    GAMING = "gaming"
    INAPPROPRIATE = "inappropriate"
    UNCATEGORIZED = "uncategorized"


class UserRole(StrEnum) :
    PARENT = "parent"
    CHILD_VIEW = "child-view"
    ADMIN = "admin"


class BlockReason(StrEnum) :
    #Nguyên nhân chặn thiết bị, ứng dụng hoặc website
    NONE = "none"
    POLICY = "policy"             #Bị Policy cấm hoặc bị phụ huynh khóa thủ công
    SCHEDULE = "schedule"         #Ngoài khung giờ cho phép trong lịch tuần 7x48 (7 ngày x 48 khung 30 phút)
    DEVICE_QUOTA = "device_quota" #Thiết bị đã dùng hết hạn mức thời gian
    APP_QUOTA = "app_quota"       #Hết hạn mức thời gian (Quota) của ứng dụng
    WEB_QUOTA = "web_quota"       #Hết hạn mức thời gian của website/domain


class TargetType(StrEnum) :
    #Đối tượng nhận lệnh.
    DEVICE = "device"
    APP = "app"
    WEB = "web"


class EventState(BaseModel) :
    ts: int = Field(... , description = "Unix thời gian (seconds)")
    device_id: str
    child_id: str
    type: EventType
    subject: str = Field(... , description = "Tên Obj")
    duration_sec: int = Field(default = 0 , ge = 0)
    policy_id: str
    idempotency_key: str = Field(... , description = "Chống trùng khi đồng bộ")


EventRecord = EventState


class PairingCode(BaseModel) :
    #Mã ghép đôi và thời hạn.
    pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ghép đôi gồm 8 ký tự")
    created_at : int
    expires_at : int

class EnrollmentRequest(BaseModel) :
    pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ghép đôi gồm 8 ký tự")
    #Device fingerprint: mã định danh phần cứng thiết bị (lấy từ UUID trên BIOS/UEFI)
    device_fingerprint : str 


class EnrollmentResponse(BaseModel) : 
    device_id : str
    access_token : str
    refresh_token : str
    policy_id : str


class ControlState(BaseModel) :
    model_config = {"allow_inf_nan" : False , "extra" : "forbid"}

    command_seq : int = Field(default = 0 , ge = 0)
    #Ngày lịch (YYYY-MM-DD) của chu kỳ DEVICE quota hiện tại
    device_quota_date : str = ""
    device_quota : float = Field(default = 0 , ge = 0)
    device_used : float = Field(default = 0 , ge = 0)
    is_manual_locked : bool = False
    manual_locked_apps : set[str] = Field(default_factory = set)
    manual_locked_domains : set[str] = Field(default_factory = set)
    #Số giây điều chỉnh có dấu.
    app_bonus_time : dict[str , int] = Field(default_factory = dict)
    web_bonus_time : dict[str , int] = Field(default_factory = dict)


class CmdAck(ControlState) :
    result : Literal["applied" , "not_applied" , "resync"] = "applied"
    reason : str = ""
    dev_status_cur : Literal["active" , "idle" , "locked"] = "active"


class HeartbeatRequest(BaseModel) : 
    #Báo cáo định kỳ của Agent.
    device_id : str
    access_token : str
    policy_id : str
    dev_status_cur : Literal["active", "idle", "locked"]
    quota_used : dict[str, int]
    cur_policy_version : int
    device_quota_date : str = ""
    #Lệnh đã xử lý, chờ gửi xác nhận.
    cmd_ack : CmdAck | None = None
    control : ControlState | None = None
    reconcile : bool = False
    
    
class HeartbeatResponse(BaseModel) :
    model_config = {"extra" : "forbid"}
    latest_policy_version : int
    command : "Cmd | None" = None
    reconcile : ControlState | None = None


class CommandType(StrEnum) :
    LOCK = "lock"
    UNLOCK = "unlock"
    ADD_TIME = "add_time"
    SUB_TIME = "sub_time"


class CmdRequest(BaseModel) :
    request_id : str = Field(default_factory = lambda : str(uuid.uuid4()) , min_length = 1)
    cmd_type : CommandType
    target_type : TargetType = TargetType.DEVICE
    subject : str = "" #Tên tiến trình (khi APP) hoặc tên miền (khi WEB)
    bonus_time : int = Field(default = 0 , ge = 0)
    sub_time : int = Field(default = 0 , ge = 0)

    @model_validator(mode = "after")
    def validateSubject(self) :
        #Kiểm tra và chuẩn hóa đối tượng APP/WEB.
        if self.target_type != TargetType.DEVICE :
            self.subject = self.subject.lower().strip()
            if not self.subject :
                raise ValueError("APP/WEB phai co subject")
        return self


class Cmd(ControlState , CmdRequest) :
    #Dữ liệu của một lệnh gửi từ Server tới Agent
    command_seq : int = Field(... , ge = 1)
    cmd_type : CommandType | None = None
    reason : Literal["command" , "day" , "policy" , "sync"] = "command"

class AppRule(BaseModel) :
    exe_name : str
    sha256 : str
    allowed : bool
    quota : int = 0 #Hạn mức gốc (giây, 0 = không giới hạn riêng)


class DomainRule(BaseModel) :
    domain : str
    category : DomainCategory
    allowed : bool
    quota : int = 0


class Policy(BaseModel) :
    policy_id : str
    policy_version : int
    weekday_quota : int
    weekend_quota : int
    schedule_7x48 : list[list[bool]]
    app_rules : list[AppRule] = []
    domain_rules : list[DomainRule] = []
    signature : str


class _LASTINPUTINFO(ctypes.Structure) :
    _fields_ = [
        ("cbSize" , ctypes.c_uint) ,
        ("dwTime" , ctypes.c_uint) ,
    ]


HeartbeatResponse.model_rebuild()
