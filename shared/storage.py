import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def writeJsonAtomic(path : Path , data) :
    tempPath = None
    try :
        #File cùng thư mục để thay thế không đi qua filesystem khác.
        with NamedTemporaryFile(
            mode = "w" , encoding = "utf-8" , dir = path.parent , delete = False
        ) as stream :
            tempPath = Path(stream.name)
            json.dump(data , stream , ensure_ascii = False , allow_nan = False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tempPath , path)
    finally :
        if tempPath is not None :
            tempPath.unlink(missing_ok = True)
