from typing import Optional
import numpy as np
import mss

from .base_capture import Region


class MSSCapture:
    def __init__(self) -> None:
        self._sct = mss.mss()

    def grab(self, region: Region) -> Optional[np.ndarray]:
        try:
            sct_img = self._sct.grab({
                'left': int(region.left),
                'top': int(region.top),
                'width': int(region.width),
                'height': int(region.height),
            })
            arr = np.array(sct_img)
            # BGRA -> BGR
            return arr[:, :, :3]
        except Exception:
            return None

    def close(self) -> None:
        # mss не требует закрытия, но оставим для совместимости
        try:
            self._sct.close()
        except Exception:
            pass