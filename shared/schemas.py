"Giao thức và đối tượng chung . Tuân thủ NT (Obj = Ứng dụng/Website)"
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field


class EventType(StrEnum) :
    #Phân loại sự kiện
    APP_START = "app_start"
    APP_STOP = "app_stop"
    DOMAIN_QUERY = "domain_query"
    BLOCKED_APP = "blocked_app"
    BLOCKED_DOMAIN = "blocked_domain"
    QUOTA_WARNING = "quota_warning"
    LOCKED = "locked"
    UNLOCK_REQUEST = "unlock_request"
    OVERRIDE_GRANTED = "override_granted" # Quyền ghi đè


class DomainCategory(StrEnum) :
    #Phân loại Obj
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    SOCIAL = "social"
    GAMING = "gaming"
    INAPPROPRIATE = "inappropriate"
    UNCATEGORIZED = "uncategorized"


class UserRole(StrEnum) :
    #User Role
    PARENT = "parent"
    CHILD_VIEW = "child-view"
    ADMIN = "admin"


class EventState(BaseModel) :
    #Event state
    ts: int = Field(... , description = "Unix thời gian (seconds)")
    device_id: str
    child_id: str
    type: EventType
    subject: str = Field(... , description = "Tên Obj")
    duration_sec: int = Field(default = 0 , ge = 0)
    policy_id: str
    idempotency_key: str = Field(... , description = "Chống trùng khi đồng bộ")


#Agent gửi request , server xử lý và gửi trả response 
#Các class sau hỗ trợ giao tiếp 

class PairingCode(BaseModel) : #Bổ sung mã code hiện tại gồm : Mã ; Thời gian
    pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ký tự 8 ký tự")
    created_at : int
    expires_at : int
    #Sửa đổi : Biến đếm thời gian -> Cố định thời gian đầu/cuối

class EnrollmentRequest(BaseModel) :
    pairing_code : str = Field(... , max_length = 8 , min_length = 8 , description = "Mã ký tự 8 ký tự")
    device_fingerprint : str 


class EnrollmentResponse(BaseModel) : 
    device_id : str
    access_token : str
    refresh_token : str
    policy_id : str #Thêm : Cho server biết cần truy cập policy nào cho device nào


class HeartbeatRequest(BaseModel) : 
    device_id : str
    access_token : str
    policy_id : str
    status_cur : Literal["active", "idle", "locked"]
    quota_used : dict[str, int]# Sửa : Kiểm soát hàng loạt chứ không chỉ 1 web/app
    cur_policy_version : int
    
    
class HeartbeatResponse(BaseModel) :
    latest_policy_version : int
    pending_commands : list[str] = []


#Luật (gồm luật cho app , web - thông qua domain , policy (id , version) , lịch , hạn mức)
class AppRule(BaseModel) :
    exe_name : str
    sha256 : str
    allowed : bool


class DomainRule(BaseModel) :
    domain : str
    category : DomainCategory
    allowed : bool


class Policy(BaseModel) :
    policy_id : str
    policy_version : int
    weekday_quota : int
    weekend_quota : int
    schedule_7x48 : list[list[bool]]
    app_rules : list[AppRule] = []
    domain_rules : list[DomainRule] = []
    signature : str


#Obj cho SQL 
