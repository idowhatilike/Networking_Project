import win32com.client

def getMachineGuid() -> str :
    #Đọc mã phần cứng của máy.
    for attempt in range(3) :
        try :
            wmi = win32com.client.GetObject("winmgmts:")
            result = wmi.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")
            machine_uuid = next(iter(result)).UUID
            if not isinstance(machine_uuid , str) or not machine_uuid.strip() :
                raise ValueError("UUID trống")
            return machine_uuid.strip()
        except Exception as error :
            if attempt == 2 :
                raise RuntimeError("Không đọc được UUID sau 3 lần thử.") from error


def getPairingCode(prompt : str = "Ma ghep enroll: " , max_attempts : int = 5) -> str :
    #Nhập mã ghép đôi 8 ký tự.
    for __ in range(max_attempts) :
        pairing_code = input(prompt).strip()
        if len(pairing_code) == 8 :
            return pairing_code
        print("Ma ghep phai dung 8 ky tu")
    raise ValueError("Nhap ma ghep that bai")
