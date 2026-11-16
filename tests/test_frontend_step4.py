#Kiểm thử giao diện Bước 4: Phiên giao diện trẻ, vé một lần, màn hình /kid/* và cổng 80.

import re
from urllib.parse import urlencode

import server
from agent.ui import issueBootstrapTicket
from agent.ui.port80 import renderPort80BlockedHtml
from scripts.verify_ui_rules import scanUiFiles
from shared.ui.paths import resolveResourcePath


_SESSION_COOKIE_RE = re.compile(r"ogk_local_session=([^;\s]+)")


def callAsgiFull(
    method : str ,
    path : str ,
    query : dict[str , str] | None = None ,
    form : dict[str , str] | None = None ,
    host_header : str = "localhost" ,
    cookie_header : str = ""
) -> tuple[int , dict[str , str] , str] :
    #Gọi ứng dụng ASGI và trả về bộ (status_code, headers_dict, body_text).
    query_bytes = urlencode(query).encode("utf-8") if query else b""
    body_bytes = urlencode(form).encode("utf-8") if form else b""
    headers = [(b"host" , host_header.encode("utf-8"))]
    if cookie_header :
        headers.append((b"cookie" , cookie_header.encode("utf-8")))
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
        "server" : ("127.0.0.1" , 80)
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
    resp_headers = {
        k.decode("latin1").lower() : v.decode("latin1")
        for k , v in sent_events[0].get("headers" , [])
    }
    body_text = b"".join(
        evt.get("body" , b"")
        for evt in sent_events
        if evt["type"] == "http.response.body"
    ).decode("utf-8")
    return status_code , resp_headers , body_text


def _bootstrapKidSessionCookie() -> str :
    #Cấp vé một lần và đổi lấy chuỗi header Cookie chứa token phiên ngẫu nhiên.
    ticket_val = issueBootstrapTicket()
    status_code , resp_headers , _ = callAsgiFull(
        "GET" , "/auth/bootstrap" , query = {"ticket" : ticket_val}
    )
    assert status_code == 302
    set_cookie_val = resp_headers.get("set-cookie" , "")
    match_obj = _SESSION_COOKIE_RE.search(set_cookie_val)
    assert match_obj is not None
    return f"ogk_local_session={match_obj.group(1)}"


def testKidRoutesRejectMissingFakeCookieAndDefaultTicket() :
    #Chặn truy cập /kid và /kid/* khi thiếu cookie, dùng cookie giả hoặc vé mặc định cũ.
    demo_status , _ , _ = callAsgiFull(
        "GET" , "/auth/bootstrap" , query = {"ticket" : "demo-ticket-once"}
    )
    assert demo_status == 403

    protected_gets = [
        "/kid" ,
        "/kid/warning" ,
        "/kid/blocked" ,
        "/kid/lock-overlay" ,
        "/kid/report" ,
        "/kid/requests" ,
        "/kid/requests/req-101/status" ,
        "/kid/rules" ,
        "/kid/about"
    ]
    for route_path in protected_gets :
        no_cookie_code , _ , _ = callAsgiFull("GET" , route_path)
        assert no_cookie_code == 401
        fake_cookie_code , _ , _ = callAsgiFull(
            "GET" ,
            route_path ,
            cookie_header = "ogk_local_session=forged-random-token"
        )
        assert fake_cookie_code == 401

    post_no_cookie , _ , _ = callAsgiFull(
        "POST" ,
        "/kid/requests" ,
        form = {"kind" : "add_time" , "reason" : "Thử gửi không cookie"}
    )
    assert post_no_cookie == 401

    post_fake_cookie , _ , _ = callAsgiFull(
        "POST" ,
        "/kid/requests" ,
        form = {"kind" : "add_time" , "reason" : "Thử gửi cookie giả"} ,
        cookie_header = "ogk_local_session=kid-session-authenticated"
    )
    assert post_fake_cookie == 401

    p80_status , _ , p80_html = callAsgiFull(
        "GET" , "/kid/port80-preview" , query = {"host" : "roblox.com"}
    )
    assert p80_status == 200
    assert "roblox.com" in p80_html


def testOneTimeBootstrapTicketAndRandomSessionCookie() :
    #Vé một lần sinh token phiên ngẫu nhiên mỗi lần dùng, dùng lại trả 403.
    ticket_1 = issueBootstrapTicket()
    status_1 , headers_1 , _ = callAsgiFull(
        "GET" , "/auth/bootstrap" , query = {"ticket" : ticket_1}
    )
    assert status_1 == 302
    assert headers_1.get("location") == "/kid"
    cookie_1 = headers_1.get("set-cookie" , "")
    assert "HttpOnly" in cookie_1
    assert "SameSite=strict" in cookie_1
    token_1 = _SESSION_COOKIE_RE.search(cookie_1).group(1)
    assert token_1 != "kid-session-authenticated"
    assert len(token_1) >= 32

    reuse_status , _ , _ = callAsgiFull(
        "GET" , "/auth/bootstrap" , query = {"ticket" : ticket_1}
    )
    assert reuse_status == 403

    ticket_2 = issueBootstrapTicket()
    status_2 , headers_2 , _ = callAsgiFull(
        "GET" , "/auth/bootstrap" , query = {"ticket" : ticket_2}
    )
    assert status_2 == 302
    token_2 = _SESSION_COOKIE_RE.search(headers_2.get("set-cookie" , "")).group(1)
    assert token_1 != token_2


def testKidScreensAndLockOverlayExemptions() :
    #Kiểm tra các màn hình của trẻ, cảnh báo 60s ân hạn và màn hình khóa (111).
    kid_cookie = _bootstrapKidSessionCookie()
    today_status , _ , today_html = callAsgiFull(
        "GET" , "/kid" , cookie_header = kid_cookie
    )
    assert today_status == 200
    assert 'data-theme="kid"' in today_html
    assert "Còn 38 phút" in today_html
    assert "Giờ trên máy vừa thay đổi" in today_html

    warn_status , _ , warn_html = callAsgiFull(
        "GET" ,
        "/kid/warning" ,
        query = {"level" : "1"} ,
        cookie_header = kid_cookie
    )
    assert warn_status == 200
    assert 'data-countdown-sec="60"' in warn_html

    blk_status , _ , blk_html = callAsgiFull(
        "GET" ,
        "/kid/blocked" ,
        query = {"kind" : "app"} ,
        cookie_header = kid_cookie
    )
    assert blk_status == 200
    assert "robloxplayerbeta.exe" in blk_html

    lock_status , _ , lock_html = callAsgiFull(
        "GET" , "/kid/lock-overlay" , cookie_header = kid_cookie
    )
    assert lock_status == 200
    assert "111" in lock_html
    assert "*.edu.vn" in lock_html
    assert "vioedu.vn" in lock_html


def testKidReportRulesWithoutIpAndAboutPrivacy() :
    #Kiểm tra trang báo cáo NT5, nhật ký luật không lộ IP phụ huynh và trang About.
    kid_cookie = _bootstrapKidSessionCookie()
    rep_status , _ , rep_html = callAsgiFull(
        "GET" , "/kid/report" , cookie_header = kid_cookie
    )
    assert rep_status == 200
    assert "Hôm nay em đã dùng gì" in rep_html
    assert "vioedu.vn" in rep_html
    assert "code.exe" in rep_html

    rules_status , _ , rules_html = callAsgiFull(
        "GET" , "/kid/rules" , cookie_header = kid_cookie
    )
    assert rules_status == 200
    assert "192.168.1.25" not in rules_html
    assert "Mẹ" in rules_html

    about_status , _ , about_html = callAsgiFull(
        "GET" , "/kid/about" , cookie_header = kid_cookie
    )
    assert about_status == 200
    assert "idempotency_key" in about_html
    assert "KHÔNG chụp màn hình" in about_html


def testKidRequestsSubmitAndPollingStopsWhenResolved() :
    #Gửi yêu cầu mới với phiên hợp lệ, kiểm tra pending hỏi 3s và ngừng hỏi khi xong.
    kid_cookie = _bootstrapKidSessionCookie()
    post_status , _ , post_html = callAsgiFull(
        "POST" ,
        "/kid/requests" ,
        form = {
            "kind" : "unblock_domain" ,
            "subject" : "scratch.mit.edu" ,
            "reason" : "Con cần mở trang học Tin học ạ"
        } ,
        cookie_header = kid_cookie
    )
    assert post_status == 200
    assert "scratch.mit.edu" in post_html

    pend_status , _ , pend_html = callAsgiFull(
        "GET" , "/kid/requests/req-101/status" , cookie_header = kid_cookie
    )
    assert pend_status == 200
    assert 'hx-trigger="every 3s"' in pend_html

    done_status , _ , done_html = callAsgiFull(
        "GET" , "/kid/requests/req-099/status" , cookie_header = kid_cookie
    )
    assert done_status == 200
    assert "hx-trigger" not in done_html
    assert "Được, 15 phút nhé" in done_html


def testUnknownKidRequestReturns404() :
    kidCookie = _bootstrapKidSessionCookie()
    statusCode , _ , responseHtml = callAsgiFull(
        "GET" , "/kid/requests/req-khong-ton-tai/status" , cookie_header = kidCookie
    )
    assert statusCode == 404
    assert "Không tìm thấy yêu cầu." in responseHtml
    assert "đồng ý" not in responseHtml.lower()


def testPort80StaticBlockedPageEscapesMaliciousHost() :
    #Kiểm tra trang cổng 80 giải thích chặn và thoát hoàn toàn ký tự độc hại ở Host.
    blk_code , blk_html = renderPort80BlockedHtml("roblox.com")
    assert blk_code == 200
    assert "roblox.com" in blk_html
    assert "Con nghĩ trang này bị chặn nhầm" in blk_html

    xss_1_code , xss_1_html = renderPort80BlockedHtml("<script>alert(1)</script>")
    assert xss_1_code == 404
    assert "<script>alert(1)</script>" not in xss_1_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in xss_1_html

    xss_2_code , xss_2_html = renderPort80BlockedHtml('"><img src=x onerror=alert(1)>')
    assert xss_2_code == 404
    assert "<img src=x onerror=alert(1)>" not in xss_2_html
    assert "&lt;img src=x onerror=alert(1)&gt;" in xss_2_html


def testStep4StaticRulesPass() :
    #Đảm bảo toàn bộ file HTML/CSS của cả dự án đều pass verify_ui_rules.py.
    project_root = resolveResourcePath(".")
    assert scanUiFiles(project_root) == []
