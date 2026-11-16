#Kiểm thử giao diện Bước 3: Báo cáo 2 theme (NT5), Yêu cầu, Thiết bị, Audit, Settings, Privacy.

from urllib.parse import urlencode

import server
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


def testReportsParentAndKidViewShareDataAndTemplate() :
    #Kiểm tra báo cáo phụ huynh và chế độ Xem như con thấy khớp số liệu (NT5).
    p_status , p_html = callAsgi(
        "GET" , "/children/child-bi/reports" , query = {"range" : "today"}
    )
    assert p_status == 200
    assert 'data-theme="parent"' in p_html
    assert "vioedu.vn" in p_html
    assert "code.exe" in p_html
    assert "Chúng tôi chỉ ghi tên ứng dụng, tên miền và thời lượng." in p_html

    k_status , k_html = callAsgi(
        "GET" ,
        "/children/child-bi/reports" ,
        query = {"range" : "today" , "view" : "kid"}
    )
    assert k_status == 200
    assert 'data-theme="kid"' in k_html
    assert "Hôm nay em đã dùng gì" in k_html
    assert "vioedu.vn" in k_html
    assert "code.exe" in k_html


def testRequestsAndDevicesEnrollmentConsent() :
    #Kiểm tra hộp thư yêu cầu /requests và tạo mã ghép đôi bắt buộc đồng ý NĐ13.
    req_status , req_html = callAsgi("GET" , "/requests")
    assert req_status == 200
    assert "Được, 15 phút nhé" in req_html

    dev_status , dev_html = callAsgi("GET" , "/devices")
    assert dev_status == 200
    assert "PC-Bi" in dev_html

    bad_status , bad_html = callAsgi(
        "POST" , "/enroll-codes" , form = {"child_id" : "child-bi"}
    )
    assert bad_status == 400
    assert "Nghị định 13/2023" in bad_html

    ok_status , ok_html = callAsgi(
        "POST" ,
        "/enroll-codes" ,
        form = {
            "child_id" : "child-bi" ,
            "consent" : "true" ,
            "consent_version" : "NĐ13-v1.0"
        }
    )
    assert ok_status == 200
    assert "OGK82941" in ok_html
    assert 'data-countdown-sec="600"' in ok_html


def testAuditSettingsDeleteAndPrivacyPages() :
    #Kiểm tra trang /audit, /settings (xóa dữ liệu) và /privacy.
    audit_status , audit_html = callAsgi("GET" , "/audit")
    assert audit_status == 200
    assert "192.168.1.25" in audit_html
    assert "Giảm hạn mức ngày thường" in audit_html or "giảm hạn mức ngày thường" in audit_html

    set_status , set_html = callAsgi("GET" , "/settings")
    assert set_status == 200
    assert "Xóa toàn bộ dữ liệu của con tôi" in set_html

    wrong_del_status , _ = callAsgi(
        "POST" ,
        "/settings/delete-child-data" ,
        form = {"child_id" : "child-bi" , "confirm_name" : "Sai Tên"}
    )
    assert wrong_del_status == 400

    ok_del_status , ok_del_html = callAsgi(
        "POST" ,
        "/settings/delete-child-data" ,
        form = {"child_id" : "child-bi" , "confirm_name" : "Bé Bi"}
    )
    assert ok_del_status == 200
    assert "Máy chủ: [Đã xóa" in ok_del_html
    assert "PC-Bi: [Đã xóa" in ok_del_html

    priv_status , priv_html = callAsgi("GET" , "/privacy")
    assert priv_status == 200
    assert "idempotency_key" in priv_html
    assert "duration_sec" in priv_html


def testStep3StaticRulesPass() :
    #Đảm bảo toàn bộ file HTML/CSS sau Bước 3 đều pass verify_ui_rules.py.
    project_root = resolveResourcePath(".")
    assert scanUiFiles(project_root) == []
