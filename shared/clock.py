import time
from datetime import datetime, timedelta, timezone

#Múi giờ Việt Nam.
VN_TZ = timezone(timedelta(hours = 7))


def getVnNow() -> datetime :
    #Lấy thời gian hiện tại theo giờ Việt Nam.
    return datetime.fromtimestamp(time.time() , tz = VN_TZ)
