import os
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np


@dataclass
class Template:
    name: str
    path: str
    gray: np.ndarray
    width: int
    height: int


class TemplateMatcher:
    def __init__(self, templates_dir: str, threshold: float = 0.9) -> None:
        self.templates_dir = templates_dir
        self.threshold = threshold
        self.templates: List[Template] = []
        self._load_templates()

    def _load_templates(self) -> None:
        if not os.path.isdir(self.templates_dir):
            return
        for fname in os.listdir(self.templates_dir):
            if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            path = os.path.join(self.templates_dir, fname)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            h, w = img.shape[:2]
            self.templates.append(Template(
                name=os.path.splitext(fname)[0],
                path=path,
                gray=img,
                width=w,
                height=h,
            ))

    def get_template_infos(self) -> List[Tuple[str, str]]:
        # (name, path) для HUD
        return [(t.name, t.path) for t in self.templates]

    def match(self, gray_frame: np.ndarray) -> List[str]:
        found: List[str] = []
        for t in self.templates:
            try:
                res = cv2.matchTemplate(gray_frame, t.gray, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val >= self.threshold:
                    found.append(t.name)
            except Exception:
                # если размеры/вход некорректный — пропускаем, чтобы не падать
                continue
        return found