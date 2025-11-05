from dataclasses import dataclass
from typing import Protocol, Optional
import numpy as np


@dataclass
class Region:
    left: int
    top: int
    width: int
    height: int


class ScreenCapture(Protocol):
    def grab(self, region: Region) -> Optional[np.ndarray]:
        ...

    def close(self) -> None:
        ...