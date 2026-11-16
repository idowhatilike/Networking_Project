import ctypes
import time

from shared.schemas import _LASTINPUTINFO

from .. import state


def getWindowsInputInfo() -> tuple[int , float] | None :
    #Đọc mốc thao tác và số giây không thao tác từ Windows.
    try :
        #Đọc thời điểm thao tác cuối từ Windows.
        input_info = _LASTINPUTINFO()
        input_info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(input_info)) :
            #Tính số giây từ thao tác cuối, xử lý bộ đếm mili giây quay vòng.
            tick_now = ctypes.windll.kernel32.GetTickCount()
            elapsed_ms = (tick_now - input_info.dwTime) & 0xFFFFFFFF
            return int(input_info.dwTime) , max(0.0 , elapsed_ms / 1000.0)
    except Exception :
        pass
    return None


def getIdleSeconds(now_mono : float | None = None) -> float :
    #Tính số giây không thao tác.
    now_mono = time.monotonic() if now_mono is None else now_mono
    win_info = getWindowsInputInfo()
    if win_info is not None :
        #Khởi tạo hoặc cập nhật mốc khi Windows báo thao tác mới.
        input_tick , idle_sec = win_info
        if state.last_input_mono is None or now_mono < state.last_input_mono or input_tick != state._last_win_input_tick :
            state.last_input_mono = now_mono - idle_sec
        state._last_win_input_tick = input_tick
    elif state.last_input_mono is None or now_mono < state.last_input_mono :
        #Thiếu dữ liệu Windows: giữ Idle nếu trước đó đã Idle.
        idle_sec = state.IDLE_THRESHOLD_SEC if state.dev_status_cur == "idle" else 0
        state.last_input_mono = now_mono - idle_sec
    return max(0.0 , now_mono - state.last_input_mono)
