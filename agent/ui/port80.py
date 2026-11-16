import json
import re
from jinja2 import Environment , FileSystemLoader , select_autoescape

from shared.ui.paths import resolveResourcePath


_HOST_PORT_RE = re.compile(r"^([a-zA-Z0-9.-]+):\d+$")


def _createPort80JinjaEnv() -> Environment :
    #Khởi tạo môi trường Jinja2 bật autoescape cho trang chặn tĩnh cổng 80.
    tpl_dirs = [
        str(resolveResourcePath("agent/ui/templates")) ,
        str(resolveResourcePath("server/templates")) ,
        str(resolveResourcePath("shared/ui/templates"))
    ]
    return Environment(
        loader = FileSystemLoader(tpl_dirs) ,
        autoescape = select_autoescape(["html" , "xml"])
    )


def renderPort80BlockedHtml(host_header : str) -> tuple[int , str] :
    #Kết xuất HTML tĩnh giải thích chặn tên miền với cơ chế tự động thoát ký tự.
    raw_host = (host_header or "").strip()
    port_match = _HOST_PORT_RE.match(raw_host)
    if port_match :
        clean_host = port_match.group(1).lower()
    else :
        clean_host = raw_host
    catalog_path = resolveResourcePath("data/fixtures/domain_catalog.json")
    with catalog_path.open("r" , encoding = "utf-8") as file_obj :
        catalog_data = json.load(file_obj)
    lower_host = clean_host.lower()
    matched_rule = next(
        (
            item for item in catalog_data.get("domains" , [])
            if not item.get("allowed" , True)
            and (
                lower_host == item["domain"]
                or lower_host.endswith("." + item["domain"])
            )
        ) ,
        None
    )
    is_blocked = matched_rule is not None
    status_code = 200 if is_blocked else 404
    jinja_env = _createPort80JinjaEnv()
    template_obj = jinja_env.get_template("port80_blocked.html")
    rendered_html = template_obj.render(
        host_domain = clean_host or "unknown" ,
        is_blocked = is_blocked ,
        rule_info = matched_rule
    )
    return status_code , rendered_html
