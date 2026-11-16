#Kiểm thử giao diện Bước 1: /login, /register, / và quy tắc tĩnh HTML/CSS.

from urllib.parse import urlencode

import server
from scripts.verify_ui_rules import scanUiFiles
from shared.ui.paths import resolveResourcePath


def callAsgi(method : str , path : str , form : dict[str , str] | None = None) :
    #Gọi trực tiếp ứng dụng ASGI trong bộ nhớ để kiểm tra status code và HTML.
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
        "query_string" : b"" ,
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


def testLoginAndRegisterRoutesReturn200() :
    #Kiểm tra route /login và /register trả về 200 và yêu cầu mật khẩu >= 10 ký tự.
    login_status , login_html = callAsgi("GET" , "/login")
    assert login_status == 200
    assert 'minlength="10"' in login_html
    assert "Đăng nhập dành cho Phụ huynh" in login_html

    reg_status , reg_html = callAsgi("GET" , "/register")
    assert reg_status == 200
    assert 'minlength="10"' in reg_html
    assert "Đăng ký tài khoản Phụ huynh" in reg_html

    bad_status , bad_html = callAsgi(
        "POST" ,
        "/register" ,
        {
            "display_name" : "Mẹ" ,
            "email" : "me@example.com" ,
            "password" : "ngan" ,
            "password_confirm" : "ngan"
        }
    )
    assert bad_status == 400
    assert "10 ký tự" in bad_html


def testOverviewRouteReturns200WithProgressAndChildren() :
    #Kiểm tra trang Tổng quan / trả về 200 và dùng thẻ <progress value max>.
    status_code , html = callAsgi("GET" , "/")
    assert status_code == 200
    assert "Bé Bi" in html
    assert "Bé Bống" in html
    assert "<progress" in html
    assert "Khóa ngay" in html
    assert "+15 phút" in html
    assert "Mở khóa" in html
    assert "Yêu cầu của con" in html


def testUiStaticRulesPass() :
    #Đảm bảo không có link CDN ngoài, không dùng |safe và không dùng inline style.
    project_root = resolveResourcePath(".")
    violations = scanUiFiles(project_root)
    assert violations == []
