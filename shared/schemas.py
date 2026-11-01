#Giao thức và cấu trúc dữ liệu dùng chung giữa Server và Agent (Obj = Ứng dụng/Website)

from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field


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
    POLICY = "policy"             #Chặn theo luật cấm hoặc lệnh khóa thủ công của phụ huynh
    SCHEDULE = "schedule"         #Ngoài khung giờ cho phép trong lịch tuần 7x48 (7 ngày x 48 khung 30 phút)
    DEVICE_QUOTA = "device_quota" #Hết hạn thời gian sử dụng toàn thiết bị (device_unlocked_until)
    APP_QUOTA = "app_quota"       #Hết hạn mức thời gian (Quota) của ứng dụng
    WEB_QUOTA = "web_quota"       #Hết hạn mức thời gian của website/domain


class TargetType(StrEnum) :
    #Phạm vi tác động của lệnh điều chỉnh thời gian
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
    #Idempotency key: mã định danh duy nhất giúp chống ghi nhận trùng sự kiện khi đồng bộ lại
    idempotency_key: str = Field(... , description = "Chống trùng khi đồng bộ")


EventRecord = EventState


class PairingCode(BaseModel) :
    #Pairing code: mã ghép đôi 8 ký tự dùng một lần để đăng ký Agent với Server
    pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ký tự 8 ký tự")
    created_at : int
    expires_at : int

class EnrollmentRequest(BaseModel) :
    pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ký tự 8 ký tự")
    #Device fingerprint: mã định danh phần cứng thiết bị (lấy từ UUID trên BIOS/UEFI)
    device_fingerprint : str 


class EnrollmentResponse(BaseModel) : 
    device_id : str
    access_token : str
    refresh_token : str
    policy_id : str


class HeartbeatRequest(BaseModel) : 
    #Heartbeat: gói tin định kỳ Agent gửi lên Server để báo trạng thái, mức sử dụng và đồng bộ lệnh/Policy
    device_id : str
    access_token : str
    policy_id : str
    status_cur : Literal["active", "idle", "locked"]
    quota_used : dict[str, int]
    cur_policy_version : int
    #ACK (Acknowledgment): thông báo xác nhận Agent đã xử lý lệnh để Server xóa khỏi hàng chờ
    acked_commands : list[str] = []
    
    
class HeartbeatResponse(BaseModel) :
    latest_policy_version : int
    pending_commands : list[str] = []
    device_unlocked_until : int | None = None
    #Ngày lịch (YYYY-MM-DD) của chu kỳ DEVICE quota hiện tại, dùng để reset hạn mức thiết bị lúc 00:00 mỗi ngày
    device_quota_date : str = ""
    #Bonus time: thời gian phụ huynh cộng/trừ thêm, lưu độc lập với hạn mức gốc trong Policy
    app_bonus_time : dict[str , int] = {}
    web_bonus_time : dict[str , int] = {}


class CommandType(StrEnum) :
    LOCK = "lock"
    UNLOCK = "unlock"
    ADD_TIME = "add_time"
    SUB_TIME = "sub_time"


class UrgentCmd(BaseModel) :
    cmd_type : CommandType
    target_type : TargetType = TargetType.DEVICE
    subject : str = "" #Tên tiến trình (khi APP) hoặc tên miền (khi WEB)
    bonus_time : int = Field(default = 0 , ge = 0)
    sub_time : int = Field(default = 0 , ge = 0)

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
