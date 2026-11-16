import json
import secrets
from urllib.parse import parse_qs
from fastapi import APIRouter , Depends , FastAPI , HTTPException , Request
from fastapi.responses import HTMLResponse , RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment , FileSystemLoader , select_autoescape

from agent.ui.port80 import renderPort80BlockedHtml
from shared.ui.paths import resolveResourcePath


def _createKidTemplates() -> Jinja2Templates :
    #Khởi tạo Jinja2Templates cho giao diện trẻ em kèm thư mục dùng chung.
    tpl_dirs = [
        str(resolveResourcePath("agent/ui/templates")) ,
        str(resolveResourcePath("server/templates")) ,
        str(resolveResourcePath("shared/ui/templates"))
    ]
    jinja_env = Environment(
        loader = FileSystemLoader(tpl_dirs) ,
        autoescape = select_autoescape(["html" , "xml"])
    )
    return Jinja2Templates(env = jinja_env)


kid_templates = _createKidTemplates()
valid_tickets : set[str] = set()
valid_sessions : set[str] = set()
_runtime_requests : list[dict] = []


def issueBootstrapTicket(custom_ticket : str = "") -> str :
    #Cấp một vé một lần (one-time ticket) để mở giao diện cục bộ từ khay hệ thống.
    ticket_val = custom_ticket or secrets.token_urlsafe(24)
    valid_tickets.add(ticket_val)
    return ticket_val


async def requireKidSession(request : Request) -> None :
    #Kiểm tra cookie phiên cục bộ hợp lệ cho mọi route được bảo vệ dưới /kid.
    session_token = request.cookies.get("ogk_local_session" , "").strip()
    if not session_token or session_token not in valid_sessions :
        raise HTTPException(
            status_code = 401 ,
            detail = "Phiên giao diện trẻ không hợp lệ hoặc chưa qua vé khay hệ thống."
        )


kid_public_router = APIRouter()
kid_protected_router = APIRouter(dependencies = [Depends(requireKidSession)])
kid_router = APIRouter()


def loadKidFixture(filename : str) -> dict :
    #Đọc tệp dữ liệu mẫu JSON cho giao diện trẻ em.
    file_path = resolveResourcePath(f"data/fixtures/{filename}")
    with file_path.open("r" , encoding = "utf-8") as file_obj :
        return json.load(file_obj)


def getKidState() -> dict :
    #Trả về trạng thái hiển thị của trẻ kèm danh sách yêu cầu đã gửi.
    kid_data = loadKidFixture("kid_view.json")
    if _runtime_requests :
        kid_data["my_requests"] = _runtime_requests + kid_data.get("my_requests" , [])
    return kid_data


async def _parseKidForm(request : Request) -> dict[str , str] :
    #Đọc dữ liệu biểu mẫu urlencoded mà không cần thư viện ngoài.
    raw_bytes = await request.body()
    parsed = parse_qs(raw_bytes.decode("utf-8") , keep_blank_values = True)
    return {key : vals[-1] if vals else "" for key , vals in parsed.items()}


@kid_public_router.get("/auth/bootstrap" , response_class = HTMLResponse)
async def bootstrapLocalSession(ticket : str = "") :
    #Đổi vé một lần thành cookie phiên cục bộ ngẫu nhiên và hủy vé ngay lập tức.
    clean_ticket = ticket.strip()
    if not clean_ticket or clean_ticket not in valid_tickets :
        return HTMLResponse(
            "Vé truy cập một lần không hợp lệ hoặc đã hết hiệu lực." ,
            status_code = 403
        )
    valid_tickets.discard(clean_ticket)
    session_token = secrets.token_urlsafe(32)
    valid_sessions.add(session_token)
    redirect_resp = RedirectResponse(url = "/kid" , status_code = 302)
    redirect_resp.set_cookie(
        key = "ogk_local_session" ,
        value = session_token ,
        httponly = True ,
        samesite = "strict"
    )
    return redirect_resp


@kid_protected_router.get("/kid" , response_class = HTMLResponse)
async def kidTodayPage(request : Request , notice : str = "") :
    #Hiển thị trang Hôm nay của em kèm số phút còn lại và thông báo minh bạch.
    context = {
        "kid" : getKidState() ,
        "kid_tab" : "today" ,
        "notice" : notice
    }
    return kid_templates.TemplateResponse(request , "today.html" , context)


@kid_protected_router.get("/kid/warning" , response_class = HTMLResponse)
async def kidWarningPage(request : Request , level : str = "1") :
    #Hiển thị cửa sổ cảnh báo sớm 10, 5 hoặc 1 phút kèm 60 giây ân hạn.
    kid_data = getKidState()
    presets = kid_data.get("warning_presets" , {})
    level_key = level if level in presets else "1"
    context = {
        "kid" : kid_data ,
        "kid_tab" : "warning" ,
        "level" : level_key ,
        "preset" : presets[level_key]
    }
    return kid_templates.TemplateResponse(request , "warning_popup.html" , context)


@kid_protected_router.get("/kid/blocked" , response_class = HTMLResponse)
async def kidBlockedExplainPage(request : Request , kind : str = "app") :
    #Hiển thị thẻ giải thích lý do tạm chặn ứng dụng hoặc trang web (NT4).
    kid_data = getKidState()
    examples = kid_data.get("blocked_examples" , {})
    block_kind = "web" if kind == "web" else "app"
    context = {
        "kid" : kid_data ,
        "kid_tab" : "blocked" ,
        "kind" : block_kind ,
        "item" : examples[block_kind]
    }
    return kid_templates.TemplateResponse(request , "blocked_explain.html" , context)


@kid_protected_router.get("/kid/lock-overlay" , response_class = HTMLResponse)
async def kidLockOverlayPage(request : Request) :
    #Hiển thị màn hình khóa kèm số tổng đài 111 và danh sách miền trường học.
    context = {
        "kid" : getKidState() ,
        "kid_tab" : "lock"
    }
    return kid_templates.TemplateResponse(request , "lock_overlay.html" , context)


@kid_protected_router.get("/kid/report" , response_class = HTMLResponse)
async def kidReportPage(request : Request , range : str = "today") :
    #Hiển thị trang Hôm nay em đã dùng gì từ cùng mẫu report_content.html (NT5).
    kid_data = getKidState()
    admin_data = loadKidFixture("reports_and_admin.json")
    range_key = "7d" if range == "7d" else "today"
    child_reports = admin_data.get("reports" , {}).get(kid_data["child_id"] , {})
    report_data = child_reports.get(range_key , {})
    context = {
        "kid" : kid_data ,
        "kid_tab" : "report" ,
        "range_key" : range_key ,
        "report" : report_data
    }
    return kid_templates.TemplateResponse(request , "report_kid.html" , context)


@kid_protected_router.get("/kid/requests" , response_class = HTMLResponse)
async def kidRequestsPage(
    request : Request ,
    kind : str = "add_time" ,
    subject : str = "" ,
    notice : str = ""
) :
    #Hiển thị trang gửi yêu cầu Xin thêm giờ hoặc Báo chặn nhầm và danh sách theo dõi.
    selected_kind = "unblock_domain" if kind == "unblock_domain" else "add_time"
    default_subj = subject or (
        "roblox.com" if selected_kind == "unblock_domain" else "+15 phút dùng máy"
    )
    context = {
        "kid" : getKidState() ,
        "kid_tab" : "requests" ,
        "selected_kind" : selected_kind ,
        "default_subject" : default_subj ,
        "notice" : notice
    }
    return kid_templates.TemplateResponse(request , "my_requests.html" , context)


@kid_protected_router.post("/kid/requests" , response_class = HTMLResponse)
async def kidRequestsSubmit(request : Request) :
    #Tạo yêu cầu mới từ biểu mẫu của trẻ và đưa vào danh sách chờ phản hồi.
    form_data = await _parseKidForm(request)
    kind = form_data.get("kind" , "add_time")
    subject = form_data.get("subject" , "+15 phút dùng máy").strip()
    reason = form_data.get("reason" , "Con xin phép dùng thêm một chút ạ").strip()
    kind_label = (
        "Báo trang chặn nhầm" if kind == "unblock_domain" else "Xin thêm 15 phút"
    )
    new_req = {
        "id" : f"req-new-{len(_runtime_requests) + 1}" ,
        "kind" : kind ,
        "kind_label" : kind_label ,
        "subject" : subject or "+15 phút dùng máy" ,
        "reason" : reason ,
        "requested_at" : "Vừa xong" ,
        "status" : "pending" ,
        "status_step" : "Đã gửi → Đang chờ Bố/Mẹ xem" ,
        "parent_message" : ""
    }
    _runtime_requests.insert(0 , new_req)
    notice_msg = "Đã gửi yêu cầu cho Bố/Mẹ! Màn hình sẽ tự cập nhật khi có phản hồi."
    context = {
        "kid" : getKidState() ,
        "kid_tab" : "requests" ,
        "selected_kind" : kind ,
        "default_subject" : subject ,
        "notice" : notice_msg
    }
    return kid_templates.TemplateResponse(request , "my_requests.html" , context)


@kid_protected_router.get(
    "/kid/requests/{req_id}/status" , response_class = HTMLResponse
)
async def kidRequestStatusPartial(request : Request , req_id : str) :
    #Trả về dòng trạng thái yêu cầu cho HTMX (tự ngừng hỏi khi khác pending).
    kid_data = getKidState()
    matched = next(
        (item for item in kid_data.get("my_requests" , []) if item["id"] == req_id) ,
        None
    )
    if matched is None :
        return HTMLResponse("Không tìm thấy yêu cầu." , status_code = 404)
    return kid_templates.TemplateResponse(
        request , "partials/kid_request_row.html" , {"r" : matched}
    )


@kid_protected_router.get("/kid/rules" , response_class = HTMLResponse)
async def kidRulesHistoryPage(request : Request) :
    #Hiển thị quy tắc hiện tại và nhật ký thay đổi (loại bỏ hoàn toàn IP phụ huynh).
    kid_data = getKidState()
    admin_data = loadKidFixture("reports_and_admin.json")
    raw_logs = admin_data.get("audit_logs" , [])
    sanitized_logs = [
        {
            "id" : item["id"] ,
            "ts" : item["ts"] ,
            "actor" : item["who"] ,
            "action_label" : (
                f"{item['field']} ({item['old_val']} → {item['new_val']})"
            ) ,
            "diff_summary" : item["sentence"]
        }
        for item in raw_logs
        if item.get("child_id") in (kid_data["child_id"] , "all")
    ]
    context = {
        "kid" : kid_data ,
        "kid_tab" : "rules" ,
        "audit_items" : sanitized_logs
    }
    return kid_templates.TemplateResponse(request , "rules_history.html" , context)


@kid_protected_router.get("/kid/about" , response_class = HTMLResponse)
async def kidAboutPage(request : Request) :
    #Hiển thị trang Về OpenGuard và bảng ánh xạ quyền riêng tư PRIVACY.md.
    context = {
        "kid" : getKidState() ,
        "kid_tab" : "about"
    }
    return kid_templates.TemplateResponse(request , "about.html" , context)


@kid_public_router.get("/kid/port80-preview" , response_class = HTMLResponse)
async def kidPort80Preview(request : Request , host : str = "") :
    #Hiển thị trang chặn tĩnh cổng 80 theo tham số host hoặc header Host.
    target_host = host or request.headers.get("host" , "")
    status_code , rendered_html = renderPort80BlockedHtml(target_host)
    return HTMLResponse(content = rendered_html , status_code = status_code)


kid_router.include_router(kid_public_router)
kid_router.include_router(kid_protected_router)


def createKidApp() -> FastAPI :
    #Tạo ứng dụng FastAPI cục bộ lắng nghe trên 127.0.0.1 cho Agent.
    local_app = FastAPI(title = "OpenGuard Kids Local Agent UI")
    local_app.mount(
        "/static/shared" ,
        StaticFiles(directory = str(resolveResourcePath("shared/ui/static"))) ,
        name = "static_shared"
    )
    local_app.mount(
        "/static" ,
        StaticFiles(directory = str(resolveResourcePath("server/static"))) ,
        name = "static"
    )
    local_app.mount(
        "/kid-static" ,
        StaticFiles(directory = str(resolveResourcePath("agent/ui/static"))) ,
        name = "kid_static"
    )
    local_app.include_router(kid_router)
    return local_app
