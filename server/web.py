#Giao diện web Dashboard phụ huynh (Jinja2 + HTMX đọc dữ liệu mẫu).

import json
from urllib.parse import parse_qs

from fastapi import APIRouter , FastAPI , Request
from fastapi.responses import HTMLResponse , RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.ui import kid_router
from shared.ui.paths import resolveResourcePath

web_router = APIRouter()

templates = Jinja2Templates(
    directory = [
        str(resolveResourcePath("server/templates")) ,
        str(resolveResourcePath("shared/ui/templates"))
    ]
)

DAY_NAMES = ["Thứ 2" , "Thứ 3" , "Thứ 4" , "Thứ 5" , "Thứ 6" , "Thứ 7" , "Chủ nhật"]


def buildTimeSlots() -> list[dict] :
    #Tạo danh sách 48 khung giờ 30 phút trong ngày (00:00 đến 24:00).
    slots : list[dict] = []
    for idx in range(48) :
        start_h = idx // 2
        start_m = (idx % 2) * 30
        end_idx = idx + 1
        end_h = end_idx // 2
        end_m = (end_idx % 2) * 30
        start_str = f"{start_h:02d}:{start_m:02d}"
        end_str = f"{end_h:02d}:{end_m:02d}"
        slots.append({
            "idx" : idx ,
            "start_str" : start_str ,
            "end_str" : end_str ,
            "label" : f"{start_str}–{end_str}"
        })
    return slots


TIME_SLOTS = buildTimeSlots()


def loadFixture(fixture_name : str) -> dict :
    #Đọc dữ liệu mẫu JSON phục vụ hiển thị giao diện.
    fixture_path = resolveResourcePath(f"data/fixtures/{fixture_name}")
    text = fixture_path.read_text(encoding = "utf-8")
    return json.loads(text)


def loadChildDetail(child_id : str) -> dict | None :
    #Lấy dữ liệu chi tiết của một trẻ từ bộ mẫu children_detail.json.
    detail_data = loadFixture("children_detail.json")
    children_map = detail_data.get("children" , {})
    return children_map.get(child_id)


def getReportForChild(child_id : str , range_key : str = "today") -> dict :
    #Hàm dùng chung lấy dữ liệu báo cáo cho cả phụ huynh và giao diện trẻ (NT5).
    admin_data = loadFixture("reports_and_admin.json")
    reports_by_child = admin_data.get("reports" , {}).get(child_id , {})
    return reports_by_child.get(range_key) or reports_by_child.get("today" , {})


def baseNavContext(active_nav : str , notice : str = "" , theme : str = "parent") -> dict :
    #Dựng ngữ cảnh chung cho thanh điều hướng của Dashboard phụ huynh.
    overview_data = loadFixture("overview.json")
    return {
        "parent_name" : overview_data.get("parent_name" , "Mẹ") ,
        "pending_requests_count" : overview_data.get("pending_requests_count" , 0) ,
        "active_nav" : active_nav ,
        "hide_nav" : False ,
        "notice" : notice ,
        "theme" : theme
    }


async def parseFormFields(request : Request) -> dict[str , str] :
    #Tách các trường dữ liệu từ body form URL-encoded.
    raw_body = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw_body , keep_blank_values = True)
    return {key : values[-1] if values else "" for key , values in parsed.items()}


def parseNonNegativeInt(rawValue : str) -> int | None :
    if not rawValue.isascii() or not rawValue.isdecimal() :
        return None
    try :
        return int(rawValue)
    except ValueError :
        return None


@web_router.get("/" , response_class = HTMLResponse)
async def overviewPage(request : Request) :
    #Hiển thị trang Tổng quan gia đình từ dữ liệu mẫu.
    overview_data = loadFixture("overview.json")
    context = {
        **baseNavContext("overview") ,
        "d" : overview_data
    }
    return templates.TemplateResponse(request , "pages/overview.html" , context)


@web_router.get("/partials/children/{child_id}/card" , response_class = HTMLResponse)
async def childCardPartial(request : Request , child_id : str) :
    #Trả về mảnh HTMX thẻ trạng thái của một trẻ khi tự làm mới.
    overview_data = loadFixture("overview.json")
    children = overview_data.get("children" , [])
    child_item = next(
        (item for item in children if item["id"] == child_id) ,
        children[0]
    )
    return templates.TemplateResponse(
        request , "partials/child_card_partial.html" , {"child" : child_item}
    )


@web_router.get("/login" , response_class = HTMLResponse)
async def loginPage(request : Request , notice : str = "") :
    #Hiển thị màn hình đăng nhập của phụ huynh.
    context = {
        "hide_nav" : True ,
        "notice" : notice ,
        "error" : "" ,
        "email" : ""
    }
    return templates.TemplateResponse(request , "pages/login.html" , context)


@web_router.post("/login" , response_class = HTMLResponse)
async def loginSubmit(request : Request) :
    #Kiểm tra độ dài mật khẩu tối thiểu 10 ký tự trên form đăng nhập.
    form_data = await parseFormFields(request)
    email = form_data.get("email" , "").strip()
    password = form_data.get("password" , "")
    if len(password) < 10 :
        context = {
            "hide_nav" : True ,
            "notice" : "" ,
            "error" : "Mật khẩu phải có ít nhất 10 ký tự." ,
            "email" : email
        }
        return templates.TemplateResponse(
            request , "pages/login.html" , context , status_code = 400
        )
    return RedirectResponse(url = "/" , status_code = 303)


@web_router.get("/register" , response_class = HTMLResponse)
async def registerPage(request : Request) :
    #Hiển thị màn hình đăng ký tài khoản phụ huynh.
    context = {
        "hide_nav" : True ,
        "notice" : "" ,
        "error" : "" ,
        "display_name" : "" ,
        "email" : ""
    }
    return templates.TemplateResponse(request , "pages/register.html" , context)


@web_router.post("/register" , response_class = HTMLResponse)
async def registerSubmit(request : Request) :
    #Kiểm tra mật khẩu tối thiểu 10 ký tự và khớp xác nhận khi đăng ký.
    form_data = await parseFormFields(request)
    display_name = form_data.get("display_name" , "").strip()
    email = form_data.get("email" , "").strip()
    password = form_data.get("password" , "")
    password_confirm = form_data.get("password_confirm" , "")
    error_msg = ""
    if len(password) < 10 :
        error_msg = "Mật khẩu đăng ký phải có từ 10 ký tự trở lên."
    elif password != password_confirm :
        error_msg = "Mật khẩu nhập lại không khớp."
    if error_msg :
        context = {
            "hide_nav" : True ,
            "notice" : "" ,
            "error" : error_msg ,
            "display_name" : display_name ,
            "email" : email
        }
        return templates.TemplateResponse(
            request , "pages/register.html" , context , status_code = 400
        )
    return RedirectResponse(url = "/login" , status_code = 303)


@web_router.post("/logout")
async def logoutSubmit() :
    #Điều hướng về trang đăng nhập khi bấm Đăng xuất.
    return RedirectResponse(url = "/login" , status_code = 303)


@web_router.get("/children" , response_class = HTMLResponse)
async def childrenListPage(request : Request , notice : str = "") :
    #Hiển thị danh sách hồ sơ các con của phụ huynh.
    detail_data = loadFixture("children_detail.json")
    children_list = list(detail_data.get("children" , {}).values())
    context = {
        **baseNavContext("children" , notice) ,
        "children" : children_list
    }
    return templates.TemplateResponse(request , "pages/children.html" , context)


@web_router.post("/children" , response_class = HTMLResponse)
async def childrenCreateSubmit(request : Request) :
    #Hiển thị thông báo sau khi thêm hồ sơ con trên giao diện.
    form_data = await parseFormFields(request)
    child_name = form_data.get("name" , "Bé mới").strip() or "Bé mới"
    detail_data = loadFixture("children_detail.json")
    children_list = list(detail_data.get("children" , {}).values())
    notice_msg = f"Đã tạo hồ sơ cho {child_name}."
    context = {
        **baseNavContext("children" , notice_msg) ,
        "children" : children_list
    }
    return templates.TemplateResponse(request , "pages/children.html" , context)


@web_router.get("/children/{child_id}" , response_class = HTMLResponse)
async def childTodayPage(request : Request , child_id : str) :
    #Hiển thị tab Hôm nay của một trẻ.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    context = {
        **baseNavContext("children") ,
        "child" : child_data ,
        "active_tab" : "today"
    }
    return templates.TemplateResponse(request , "pages/child_today.html" , context)


def countScheduleHours(schedule_strings : list[str]) -> str :
    #Tính tổng số giờ mở trong tuần từ 7 chuỗi 48 ký tự 0/1.
    total_slots = sum(row.count("1") for row in schedule_strings)
    total_hours = total_slots * 0.5
    if total_hours.is_integer() :
        return str(int(total_hours))
    return f"{total_hours:.1f}"


@web_router.get("/children/{child_id}/schedule" , response_class = HTMLResponse)
async def childSchedulePage(request : Request , child_id : str) :
    #Hiển thị tab Lịch tuần 7x48 của trẻ.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    rows = child_data.get("schedule_strings" , ["0" * 48 for _ in range(7)])
    context = {
        **baseNavContext("children") ,
        "child" : child_data ,
        "active_tab" : "schedule" ,
        "day_names" : DAY_NAMES ,
        "time_slots" : TIME_SLOTS ,
        "total_allowed_hours" : countScheduleHours(rows) ,
        "error" : ""
    }
    return templates.TemplateResponse(request , "pages/child_schedule.html" , context)


@web_router.post("/children/{child_id}/schedule" , response_class = HTMLResponse)
async def childScheduleSubmit(request : Request , child_id : str) :
    #Kiểm tra định dạng 7x48 ký tự 0/1 và hiển thị phiên bản chính sách mới.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    form_data = await parseFormFields(request)
    new_rows : list[str] = []
    for day_idx in range(7) :
        row_str = form_data.get(f"row_{day_idx}" , "")
        if len(row_str) != 48 or any(ch not in ("0" , "1") for ch in row_str) :
            context = {
                **baseNavContext("children") ,
                "child" : child_data ,
                "active_tab" : "schedule" ,
                "day_names" : DAY_NAMES ,
                "time_slots" : TIME_SLOTS ,
                "total_allowed_hours" : countScheduleHours(child_data["schedule_strings"]) ,
                "error" : "Lịch tuần phải gồm đúng 7 chuỗi × 48 ký tự '0' hoặc '1'."
            }
            return templates.TemplateResponse(
                request , "pages/child_schedule.html" , context , status_code = 422
            )
        new_rows.append(row_str)

    child_data["schedule_strings"] = new_rows
    new_ver = int(child_data.get("latest_policy_version" , 12)) + 1
    child_data["latest_policy_version"] = new_ver
    dev_name = child_data.get("device_name" , "máy của con")
    notice_msg = (
        f"Đã lưu phiên bản {new_ver} · máy {dev_name} sẽ cập nhật trong tối đa 60 giây."
    )
    context = {
        **baseNavContext("children" , notice_msg) ,
        "child" : child_data ,
        "active_tab" : "schedule" ,
        "day_names" : DAY_NAMES ,
        "time_slots" : TIME_SLOTS ,
        "total_allowed_hours" : countScheduleHours(new_rows) ,
        "error" : ""
    }
    return templates.TemplateResponse(request , "pages/child_schedule.html" , context)


@web_router.get("/children/{child_id}/limits" , response_class = HTMLResponse)
async def childLimitsPage(request : Request , child_id : str) :
    #Hiển thị tab Hạn mức ngày thường, cuối tuần và ngân sách nhóm.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    context = {
        **baseNavContext("children") ,
        "child" : child_data ,
        "active_tab" : "limits"
    }
    return templates.TemplateResponse(request , "pages/child_limits.html" , context)


@web_router.post("/children/{child_id}/limits" , response_class = HTMLResponse)
async def childLimitsSubmit(request : Request , child_id : str) :
    #Cập nhật hạn mức hoặc xóa sạch điều chỉnh nhóm về trạng thái rỗng {}.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    form_data = await parseFormFields(request)
    action = form_data.get("action" , "save")
    if action == "clear_adjustments" :
        child_data["category_budgets"] = {}
        child_data["bonus_min"] = 0
        notice_msg = "Đã xóa sạch điều chỉnh giờ thưởng và ngân sách nhóm về {}."
    else :
        fieldLabels = {
            "weekday_quota_min" : "Ngày thường" ,
            "weekend_quota_min" : "Cuối tuần" ,
            "budget_gaming" : "Nhóm Trò chơi" ,
            "budget_entertainment" : "Nhóm Giải trí" ,
            "budget_education" : "Nhóm Giáo dục"
        }
        quotaValues = {
            name : parseNonNegativeInt(form_data.get(name , "")) for name in fieldLabels
        }
        fieldErrors = {
            name : f"{label} phải là số nguyên không âm."
            for name , label in fieldLabels.items() if quotaValues[name] is None
        }
        if fieldErrors :
            return templates.TemplateResponse(
                request , "pages/child_limits.html" , {
                    **baseNavContext("children") , "child" : child_data ,
                    "active_tab" : "limits" , "formValues" : form_data ,
                    "fieldErrors" : fieldErrors ,
                    "error" : "Vui lòng sửa các trường được đánh dấu bên dưới."
                } , status_code = 422
            )
        child_data["weekday_quota_min"] = quotaValues["weekday_quota_min"]
        child_data["weekend_quota_min"] = quotaValues["weekend_quota_min"]
        child_data["category_budgets"] = {
            "gaming" : quotaValues["budget_gaming"] ,
            "entertainment" : quotaValues["budget_entertainment"] ,
            "education" : quotaValues["budget_education"]
        }
        new_ver = int(child_data.get("latest_policy_version" , 12)) + 1
        child_data["latest_policy_version"] = new_ver
        notice_msg = f"Đã lưu hạn mức mới (phiên bản v{new_ver})."
    context = {
        **baseNavContext("children" , notice_msg) ,
        "child" : child_data ,
        "active_tab" : "limits"
    }
    return templates.TemplateResponse(request , "pages/child_limits.html" , context)


@web_router.get("/children/{child_id}/apps" , response_class = HTMLResponse)
async def childAppsPage(request : Request , child_id : str) :
    #Hiển thị tab Quản lý ứng dụng theo tên và mã băm SHA-256.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    context = {
        **baseNavContext("children") ,
        "child" : child_data ,
        "active_tab" : "apps"
    }
    return templates.TemplateResponse(request , "pages/child_apps.html" , context)


@web_router.post("/children/{child_id}/apps" , response_class = HTMLResponse)
async def childAppsSubmit(request : Request , child_id : str) :
    #Thêm luật ứng dụng từ danh sách ứng dụng đã thấy trên máy của trẻ.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    form_data = await parseFormFields(request)
    exe_name = form_data.get("exe_name" , "notepad.exe").strip()
    allowed = form_data.get("allowed" , "allow") == "allow"
    quota_min = parseNonNegativeInt(form_data.get("quota_min" , ""))
    if quota_min is None :
        return templates.TemplateResponse(
            request , "pages/child_apps.html" , {
                **baseNavContext("children") , "child" : child_data ,
                "active_tab" : "apps" , "formValues" : form_data ,
                "fieldErrors" : {"quota_min" : "Hạn mức riêng phải là số nguyên không âm."} ,
                "error" : "Vui lòng sửa các trường được đánh dấu bên dưới."
            } , status_code = 422
        )
    observed = next(
        (item for item in child_data.get("observed_apps" , []) if item["exe_name"] == exe_name) ,
        {
            "exe_name" : exe_name ,
            "display_name" : exe_name ,
            "sha256" : "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2" ,
            "sha256_short" : "a1b2c3d4"
        }
    )
    child_data.setdefault("apps" , []).append({
        "exe_name" : observed["exe_name"] ,
        "display_name" : observed["display_name"] ,
        "sha256" : observed["sha256"] ,
        "sha256_short" : observed["sha256_short"] ,
        "category" : "Tùy chỉnh" ,
        "allowed" : allowed ,
        "quota_min" : quota_min ,
        "set_by" : "Mẹ" ,
        "set_at" : "15/11/2026"
    })
    notice_msg = f"Đã thêm luật cho ứng dụng {observed['display_name']}."
    context = {
        **baseNavContext("children" , notice_msg) ,
        "child" : child_data ,
        "active_tab" : "apps"
    }
    return templates.TemplateResponse(request , "pages/child_apps.html" , context)


def buildWebPageContext(
    child_data : dict , q : str = "" , page : int = 1 , notice : str = ""
) -> dict :
    #Chuẩn bị dữ liệu phân trang danh mục 200+ tên miền cho trang Website.
    catalog_data = loadFixture("domain_catalog.json")
    all_domains = catalog_data.get("domains" , [])
    query_str = q.strip().lower()
    if query_str :
        filtered = [
            item for item in all_domains
            if query_str in item["domain"].lower()
            or query_str in item["category_label"].lower()
        ]
    else :
        filtered = all_domains
    page_size = 20
    total_items = len(filtered)
    total_pages = max(1 , (total_items + page_size - 1) // page_size)
    cur_page = max(1 , min(page , total_pages))
    start_idx = (cur_page - 1) * page_size
    page_items = filtered[start_idx : start_idx + page_size]
    return {
        **baseNavContext("children" , notice) ,
        "child" : child_data ,
        "active_tab" : "web" ,
        "catalog_items" : page_items ,
        "catalog_total" : total_items ,
        "page" : cur_page ,
        "total_pages" : total_pages ,
        "q" : q ,
        "result" : None
    }


@web_router.get("/children/{child_id}/web" , response_class = HTMLResponse)
async def childWebPage(
    request : Request , child_id : str , q : str = "" , page : int = 1
) :
    #Hiển thị tab Lọc Website (6 nhóm, DoH, SafeSearch và danh mục >= 200 miền).
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    context = buildWebPageContext(child_data , q = q , page = page)
    return templates.TemplateResponse(request , "pages/child_web.html" , context)


@web_router.post("/children/{child_id}/web" , response_class = HTMLResponse)
async def childWebSubmit(request : Request , child_id : str) :
    #Xử lý lưu 6 nhóm nội dung, áp dụng mẫu 6–11 tuổi hoặc xóa sạch ngoại lệ.
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    form_data = await parseFormFields(request)
    action = form_data.get("action" , "save_categories")
    if action == "clear_exceptions" :
        child_data["web_settings"]["domain_exceptions"] = []
        notice_msg = "Đã xóa sạch danh sách ngoại lệ tên miền về {}."
    elif action == "apply_preset_6_11" :
        for cat in child_data["web_settings"].get("categories" , []) :
            cat["allowed"] = cat["key"] in ("education" , "entertainment")
        notice_msg = "Đã áp dụng mẫu cấu hình an toàn cho lứa tuổi 6–11 tuổi."
    else :
        for cat in child_data["web_settings"].get("categories" , []) :
            val = form_data.get(f"cat_{cat['key']}" , "allow")
            cat["allowed"] = val == "allow"
        notice_msg = "Đã lưu cấu hình 6 nhóm nội dung Website."
    context = buildWebPageContext(child_data , notice = notice_msg)
    return templates.TemplateResponse(request , "pages/child_web.html" , context)


@web_router.get("/domains/check" , response_class = HTMLResponse)
async def checkDomainRule(request : Request , name : str = "") :
    #Tra cứu nhóm, quyết định và lời giải thích luật (NT4) cho một tên miền.
    clean_name = name.strip().lower()
    catalog_data = loadFixture("domain_catalog.json")
    all_domains = catalog_data.get("domains" , [])
    matched = next(
        (
            item for item in all_domains
            if clean_name == item["domain"] or clean_name.endswith("." + item["domain"])
        ) ,
        None
    )
    if matched is None :
        matched = {
            "domain" : clean_name or "unknown.example" ,
            "category" : "uncategorized" ,
            "category_label" : "Chưa phân loại" ,
            "allowed" : True ,
            "rule_id" : "16" ,
            "set_by" : "Mẹ" ,
            "set_at" : "12/11/2026" ,
            "reason" : "Tên miền chưa nằm trong danh sách hạn chế"
        }
    else :
        matched = {**matched , "domain" : clean_name}
    return templates.TemplateResponse(
        request , "partials/domain_check_partial.html" , {"result" : matched}
    )


@web_router.get("/children/{child_id}/reports" , response_class = HTMLResponse)
async def childReportsPage(
    request : Request , child_id : str , range : str = "today" , view : str = "parent"
) :
    #Hiển thị báo cáo sử dụng và chế độ Xem như con thấy (dùng chung template NT5).
    child_data = loadChildDetail(child_id)
    if child_data is None :
        return HTMLResponse("Không tìm thấy hồ sơ trẻ" , status_code = 404)
    range_key = "7d" if range == "7d" else "today"
    view_mode = "kid" if view == "kid" else "parent"
    report_data = getReportForChild(child_id , range_key)
    context = {
        **baseNavContext("children" , theme = view_mode) ,
        "child" : child_data ,
        "active_tab" : "reports" ,
        "range_key" : range_key ,
        "view_mode" : view_mode ,
        "report" : report_data
    }
    return templates.TemplateResponse(request , "pages/child_reports.html" , context)


@web_router.get("/requests" , response_class = HTMLResponse)
async def requestsInboxPage(request : Request , status : str = "pending") :
    #Hiển thị hộp thư yêu cầu của con theo bộ lọc trạng thái.
    admin_data = loadFixture("reports_and_admin.json")
    all_reqs = admin_data.get("requests" , [])
    if status == "pending" :
        filtered = [r for r in all_reqs if r["status"] == "pending"]
    elif status == "resolved" :
        filtered = [r for r in all_reqs if r["status"] != "pending"]
    else :
        filtered = all_reqs
    context = {
        **baseNavContext("requests") ,
        "status_filter" : status ,
        "requests_list" : filtered
    }
    return templates.TemplateResponse(request , "pages/requests.html" , context)


@web_router.get("/devices" , response_class = HTMLResponse)
async def devicesPage(request : Request , notice : str = "") :
    #Hiển thị danh sách thiết bị và hộp thoại tạo mã ghép đôi 8 ký tự.
    admin_data = loadFixture("reports_and_admin.json")
    detail_data = loadFixture("children_detail.json")
    context = {
        **baseNavContext("devices" , notice) ,
        "devices" : admin_data.get("devices" , []) ,
        "children_list" : list(detail_data.get("children" , {}).values()) ,
        "generated_code" : None ,
        "error" : ""
    }
    return templates.TemplateResponse(request , "pages/devices.html" , context)


@web_router.post("/enroll-codes" , response_class = HTMLResponse)
async def createEnrollCodeSubmit(request : Request) :
    #Kiểm tra chọn trẻ + đồng ý Nghị định 13 và sinh mã ghép đôi 8 ký tự.
    form_data = await parseFormFields(request)
    child_id = form_data.get("child_id" , "").strip()
    consent = form_data.get("consent" , "")
    consent_version = form_data.get("consent_version" , "NĐ13-v1.0").strip()
    admin_data = loadFixture("reports_and_admin.json")
    detail_data = loadFixture("children_detail.json")
    children_map = detail_data.get("children" , {})
    children_list = list(children_map.values())
    if not child_id or child_id not in children_map or consent != "true" :
        context = {
            **baseNavContext("devices") ,
            "devices" : admin_data.get("devices" , []) ,
            "children_list" : children_list ,
            "generated_code" : None ,
            "error" : "Bắt buộc chọn hồ sơ con và tick đồng ý Nghị định 13/2023/NĐ-CP."
        }
        return templates.TemplateResponse(
            request , "pages/devices.html" , context , status_code = 400
        )
    child_name = children_map[child_id]["name"]
    generated = {
        "code" : "OGK82941" ,
        "child_id" : child_id ,
        "child_name" : child_name ,
        "expires_in_sec" : 600 ,
        "consent_version" : consent_version
    }
    notice_msg = f"Đã tạo mã ghép đôi 8 ký tự cho {child_name} và ghi nhận vào nhật ký kiểm toán."
    context = {
        **baseNavContext("devices" , notice_msg) ,
        "devices" : admin_data.get("devices" , []) ,
        "children_list" : children_list ,
        "generated_code" : generated ,
        "error" : ""
    }
    return templates.TemplateResponse(request , "pages/devices.html" , context)


@web_router.post("/devices/{device_id}/revoke" , response_class = HTMLResponse)
async def revokeDeviceSubmit(request : Request , device_id : str) :
    #Thu hồi quyền kết nối của một thiết bị trên giao diện.
    admin_data = loadFixture("reports_and_admin.json")
    detail_data = loadFixture("children_detail.json")
    devices = [
        d for d in admin_data.get("devices" , []) if d["device_id"] != device_id
    ]
    notice_msg = f"Đã thu hồi thiết bị {device_id}."
    context = {
        **baseNavContext("devices" , notice_msg) ,
        "devices" : devices ,
        "children_list" : list(detail_data.get("children" , {}).values()) ,
        "generated_code" : None ,
        "error" : ""
    }
    return templates.TemplateResponse(request , "pages/devices.html" , context)


@web_router.get("/audit" , response_class = HTMLResponse)
async def auditLogPage(
    request : Request , child_id : str = "" , cursor : str = ""
) :
    #Hiển thị nhật ký kiểm toán thay đổi chính sách kèm lọc theo trẻ và cursor.
    admin_data = loadFixture("reports_and_admin.json")
    logs = admin_data.get("audit_logs" , [])
    if child_id :
        logs = [item for item in logs if item["child_id"] == child_id]
    if cursor :
        logs = [item for item in logs if item["id"] < cursor]
    page_items = logs[:3]
    next_cursor = page_items[-1]["id"] if len(logs) > 3 else ""
    context = {
        **baseNavContext("audit") ,
        "audit_items" : page_items ,
        "child_filter" : child_id ,
        "next_cursor" : next_cursor
    }
    return templates.TemplateResponse(request , "pages/audit.html" , context)


@web_router.get("/settings" , response_class = HTMLResponse)
async def settingsPage(request : Request , notice : str = "") :
    #Hiển thị trang Cài đặt, bản ghi đồng ý Nghị định 13 và vùng xóa dữ liệu.
    admin_data = loadFixture("reports_and_admin.json")
    detail_data = loadFixture("children_detail.json")
    context = {
        **baseNavContext("settings" , notice) ,
        "consent_records" : admin_data.get("consent_records" , []) ,
        "children_list" : list(detail_data.get("children" , {}).values()) ,
        "delete_progress" : None ,
        "error" : ""
    }
    return templates.TemplateResponse(request , "pages/settings.html" , context)


@web_router.post("/settings/delete-child-data" , response_class = HTMLResponse)
async def deleteChildDataSubmit(request : Request) :
    #Xác nhận tên con và hiển thị tiến độ xóa dữ liệu trên Server + máy con.
    form_data = await parseFormFields(request)
    child_id = form_data.get("child_id" , "").strip()
    confirm_name = form_data.get("confirm_name" , "").strip()
    admin_data = loadFixture("reports_and_admin.json")
    detail_data = loadFixture("children_detail.json")
    children_map = detail_data.get("children" , {})
    child_obj = children_map.get(child_id)
    if child_obj is None or confirm_name != child_obj["name"] :
        context = {
            **baseNavContext("settings") ,
            "consent_records" : admin_data.get("consent_records" , []) ,
            "children_list" : list(children_map.values()) ,
            "delete_progress" : None ,
            "error" : "Tên xác nhận không khớp với tên của con. Vui lòng nhập chính xác."
        }
        return templates.TemplateResponse(
            request , "pages/settings.html" , context , status_code = 400
        )
    progress = {
        "child_name" : child_obj["name"] ,
        "device_name" : child_obj["device_name"] ,
        "online" : child_obj["online"]
    }
    notice_msg = f"Đã thực thi xóa toàn bộ dữ liệu hoạt động của {child_obj['name']}."
    context = {
        **baseNavContext("settings" , notice_msg) ,
        "consent_records" : admin_data.get("consent_records" , []) ,
        "children_list" : list(children_map.values()) ,
        "delete_progress" : progress ,
        "error" : ""
    }
    return templates.TemplateResponse(request , "pages/settings.html" , context)


@web_router.get("/privacy" , response_class = HTMLResponse)
async def privacyPage(request : Request) :
    #Hiển thị trang Quyền riêng tư từ bảng dùng chung privacy_table.html.
    context = baseNavContext("privacy")
    return templates.TemplateResponse(request , "pages/privacy.html" , context)


@web_router.post("/children/{child_id}/commands" , response_class = HTMLResponse)
async def triggerQuickCommand(request : Request , child_id : str) :
    #Trả về mảnh HTMX hiển thị trạng thái lệnh khẩn trên thẻ của trẻ.
    form_data = await parseFormFields(request)
    cmd_type = form_data.get("cmd_type" , "add_time")
    overview_data = loadFixture("overview.json")
    target_child = next(
        (item for item in overview_data.get("children" , []) if item["id"] == child_id) ,
        None
    )
    is_online = bool(target_child and target_child.get("online"))
    cmd_labels = {
        "lock" : "Khóa ngay" ,
        "unlock" : "Mở khóa" ,
        "add_time" : "+15 phút"
    }
    action_text = cmd_labels.get(cmd_type , cmd_type)
    if is_online :
        state_val = "applied"
        label_val = f"Đã áp dụng: {action_text} (1 giây)"
        detail_val = "Máy đã gửi ACK xác nhận"
    else :
        state_val = "queued"
        label_val = "Đã xếp hàng (Sẽ áp dụng ngay khi máy bật mạng)"
        detail_val = f"Lệnh: {action_text}"
    context = {
        "chip_id" : f"cmd-chip-{child_id}" ,
        "state" : state_val ,
        "label" : label_val ,
        "detail" : detail_val ,
        "is_online" : is_online
    }
    return templates.TemplateResponse(
        request , "partials/command_chip_partial.html" , context
    )


@web_router.post("/requests/{req_id}/decision" , response_class = HTMLResponse)
async def decideChildRequest(request : Request , req_id : str) :
    #Trả về dòng bảng HTMX sau khi phụ huynh duyệt hoặc từ chối yêu cầu.
    form_data = await parseFormFields(request)
    decision = form_data.get("decision" , "approve")
    message = form_data.get("message" , "Đã phản hồi").strip()
    overview_data = loadFixture("overview.json")
    matched = next(
        (r for r in overview_data.get("pending_requests" , []) if r["id"] == req_id) ,
        None
    )
    summary = matched["summary"] if matched else f"Yêu cầu {req_id}"
    context = {
        "req_id" : req_id ,
        "summary" : summary ,
        "decision" : decision ,
        "message" : message
    }
    return templates.TemplateResponse(
        request , "partials/request_row_partial.html" , context
    )


def setupWeb(app : FastAPI) :
    #Gắn static files và router giao diện vào ứng dụng FastAPI.
    shared_tpl_dir = resolveResourcePath("shared/ui/templates")
    shared_tpl_dir.mkdir(parents = True , exist_ok = True)
    app.mount(
        "/static/shared" ,
        StaticFiles(directory = str(resolveResourcePath("shared/ui/static"))) ,
        name = "static_shared"
    )
    app.mount(
        "/static" ,
        StaticFiles(directory = str(resolveResourcePath("server/static"))) ,
        name = "static"
    )
    app.mount(
        "/kid-static" ,
        StaticFiles(directory = str(resolveResourcePath("agent/ui/static"))) ,
        name = "kid_static"
    )
    app.include_router(web_router)
    app.include_router(kid_router)
