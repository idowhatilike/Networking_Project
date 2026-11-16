#Kiểm thử giao diện Bước 2: Hồ sơ con, Lịch tuần 7x48, Hạn mức, Ứng dụng và Website.

from urllib.parse import urlencode
from copy import deepcopy
from html import unescape
import re

import pytest

import server
from server import web
from scripts.verify_ui_rules import scanUiFiles
from shared.ui.paths import resolveResourcePath


def callAsgi(
    method : str ,
    path : str ,
    query : dict[str , str] | None = None ,
    form : dict[str , str] | None = None
) :
    #Gọi trực tiếp ứng dụng ASGI trong bộ nhớ để kiểm tra status code và HTML.
    query_bytes = urlencode(query).encode("utf-8") if query else b""
    body_bytes = urlencode(form).encode("utf-8") if form else b""
    headers = [(b"host" , b"localhost")]
    if form is not None :
        headers.append(
            (b"content-type" , b"application/x-www-form-urlencoded")
        )
    scope = {
        "type" : "http" ,
        "asgi" : {"version" : "3.0"} ,
        "http_version" : "1.1" ,
        "method" : method.upper() ,
        "scheme" : "http" ,
        "path" : path ,
        "raw_path" : path.encode("utf-8") ,
        "query_string" : query_bytes ,
        "headers" : headers ,
        "client" : ("127.0.0.1" , 12345) ,
        "server" : ("localhost" , 80)
    }
    sent_events : list[dict] = []
    request_delivered = False

    async def receive() :
        nonlocal request_delivered
        if not request_delivered :
            request_delivered = True
            return {
                "type" : "http.request" ,
                "body" : body_bytes ,
                "more_body" : False
            }
        return {"type" : "http.disconnect"}

    async def send(message : dict) :
        sent_events.append(message)

    coro = server.app(scope , receive , send)
    try :
        while True :
            coro.send(None)
    except StopIteration :
        pass
    finally :
        coro.close()

    status_code = sent_events[0]["status"]
    body_text = b"".join(
        evt.get("body" , b"") for evt in sent_events if evt["type"] == "http.response.body"
    ).decode("utf-8")
    return status_code , body_text


def testChildrenAndTodayPagesReturn200() :
    #Kiểm tra trang danh sách con /children và tab Hôm nay /children/child-bi.
    list_status , list_html = callAsgi("GET" , "/children")
    assert list_status == 200
    assert "Bé Bi" in list_html
    assert "Bé Bống" in list_html

    today_status , today_html = callAsgi("GET" , "/children/child-bi")
    assert today_status == 200
    assert "Hoạt động gần đây trong ngày" in today_html
    assert "vioedu.vn" in today_html


def testScheduleMatrix336SlotsAndValidation() :
    #Kiểm tra lưới 7x48 có 336 nút slot, lưu tăng policy_version và bắt lỗi 422.
    status_code , html = callAsgi("GET" , "/children/child-bi/schedule")
    assert status_code == 200
    assert html.count('class="slot"') == 336
    assert 'aria-pressed="true"' in html

    valid_form = {f"row_{idx}" : "1" * 48 for idx in range(7)}
    save_status , save_html = callAsgi(
        "POST" , "/children/child-bi/schedule" , form = valid_form
    )
    assert save_status == 200
    assert "Đã lưu phiên bản 13" in save_html

    bad_form = {f"row_{idx}" : "1" * 47 for idx in range(7)}
    bad_status , bad_html = callAsgi(
        "POST" , "/children/child-bi/schedule" , form = bad_form
    )
    assert bad_status == 422
    assert "48 ký tự" in bad_html


def testLimitsAndClearAdjustments() :
    #Kiểm tra trang hạn mức và xóa sạch điều chỉnh nhóm về {}.
    get_status , get_html = callAsgi("GET" , "/children/child-bi/limits")
    assert get_status == 200
    assert "Hạn mức tổng theo ngày" in get_html

    clear_status , clear_html = callAsgi(
        "POST" ,
        "/children/child-bi/limits" ,
        form = {"action" : "clear_adjustments"}
    )
    assert clear_status == 200
    assert "{}" in clear_html


def testAppsWebAndDomainCheckerEscapeXss() :
    #Kiểm tra trang Ứng dụng, Website, công cụ kiểm tra miền và chống XSS.
    apps_status , apps_html = callAsgi("GET" , "/children/child-bi/apps")
    assert apps_status == 200
    assert "9f86d081" in apps_html
    assert "Hệ thống so sánh theo mã băm" in apps_html

    web_status , web_html = callAsgi("GET" , "/children/child-bi/web")
    assert web_status == 200
    assert "SafeSearch: Đang bật" in web_html
    assert "Chặn DNS-over-HTTPS (DoH): Đang bật" in web_html
    assert "210 mục" in web_html

    edu_status , edu_html = callAsgi(
        "GET" , "/domains/check" , query = {"name" : "vioedu.vn"}
    )
    assert edu_status == 200
    assert "Giáo dục" in edu_html
    assert "#11" in edu_html

    doh_status , doh_html = callAsgi(
        "GET" , "/domains/check" , query = {"name" : "dns.google"}
    )
    assert doh_status == 200
    assert "Điểm cuối DoH" in doh_html

    xss_payload = "<img src=x onerror=alert(1)>"
    xss_status , xss_html = callAsgi(
        "GET" , "/domains/check" , query = {"name" : xss_payload}
    )
    assert xss_status == 200
    assert xss_payload not in xss_html
    assert "&lt;img" in xss_html


_NUMBER_FIELDS = {
    "weekday_quota_min" : "Ngày thường" ,
    "weekend_quota_min" : "Cuối tuần" ,
    "budget_gaming" : "Nhóm Trò chơi" ,
    "budget_entertainment" : "Nhóm Giải trí" ,
    "budget_education" : "Nhóm Giáo dục" ,
    "quota_min" : "Hạn mức riêng"
}


@pytest.mark.parametrize("fieldName" , _NUMBER_FIELDS)
@pytest.mark.parametrize("invalidValue" , ["abc" , "-10" , "5.5" , ""])
def testInvalidQuotaFieldsReturn422(monkeypatch , fieldName , invalidValue) :
    childData = web.loadChildDetail("child-bi")
    originalData = deepcopy(childData)
    monkeypatch.setattr(web , "loadChildDetail" , lambda childId : childData)
    formValues = {name : "17" for name in _NUMBER_FIELDS if name != "quota_min"}
    pageName = "limits"
    if fieldName == "quota_min" :
        pageName = "apps"
        formValues = {"quota_min" : "17" , "exe_name" : "notepad.exe" , "allowed" : "block"}
    formValues[fieldName] = invalidValue
    statusCode , responseHtml = callAsgi(
        "POST" , f"/children/child-bi/{pageName}" , form = formValues
    )
    assert statusCode == 422
    assert _NUMBER_FIELDS[fieldName] in responseHtml
    assert f'id="field-{fieldName}-error"' in responseHtml
    for name , value in formValues.items() :
        if name not in _NUMBER_FIELDS :
            continue
        inputTag = next(
            tag for tag in re.findall(r"<input\b[^>]*>" , responseHtml)
            if f'name="{name}"' in tag
        )
        assert unescape(re.search(r'value="([^"]*)"' , inputTag).group(1)) == value
    assert childData == originalData


@pytest.mark.parametrize("pageName" , ["limits" , "apps"])
def testZeroQuotaIsAccepted(pageName) :
    formValues = {name : "0" for name in _NUMBER_FIELDS}
    statusCode , _ = callAsgi(
        "POST" , f"/children/child-bi/{pageName}" , form = formValues
    )
    assert statusCode == 200


def testAllQuotaErrorsAreShownAndEscaped() :
    invalidValue = '\"><img src=x onerror=alert(1)>'
    formValues = {name : invalidValue for name in _NUMBER_FIELDS if name != "quota_min"}
    statusCode , responseHtml = callAsgi(
        "POST" , "/children/child-bi/limits" , form = formValues
    )
    assert statusCode == 422
    assert invalidValue not in responseHtml
    assert "&lt;img" in responseHtml
    for name in formValues :
        assert f'id="field-{name}-error"' in responseHtml


@pytest.mark.parametrize("invalidValue" , ["abc" , ""])
def testClearAdjustmentsSkipsQuotaValidation(invalidValue) :
    formValues = {name : invalidValue for name in _NUMBER_FIELDS}
    formValues["action"] = "clear_adjustments"
    statusCode , responseHtml = callAsgi(
        "POST" , "/children/child-bi/limits" , form = formValues
    )
    assert statusCode == 200
    assert "{}" in responseHtml
    clearButton = re.search(r'<button[^>]*value="clear_adjustments"[^>]*>' , responseHtml)
    assert "formnovalidate" in clearButton.group(0)


def testStep2StaticRulesPass() :
    #Đảm bảo mọi file HTML/CSS mới của Bước 2 đều tuân thủ verify_ui_rules.py.
    project_root = resolveResourcePath(".")
    assert scanUiFiles(project_root) == []
