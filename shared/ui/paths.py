#Phân giải đường dẫn tài nguyên giao diện cho mã nguồn và bản đóng gói PyInstaller.

import sys
from pathlib import Path


def resolveResourcePath(rel_path : str) -> Path :
    #Trả về đường dẫn tuyệt đối tới thư mục hoặc tệp tài nguyên trong Project.
    base_dir = Path(
        getattr(sys , "_MEIPASS" , Path(__file__).resolve().parents[2])
    )
    return (base_dir / rel_path).resolve()
