import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import cv2
import numpy as np

from src.buffs.library import load_library
from src.utils.settings import resource_path


@dataclass
class LibTemplate:
    id: str
    type: str
    path: str
    gray: np.ndarray
    width: int
    height: int


class LibraryMatcher:
    """
    Матчит активированные записи из библиотеки по их image_path.
    Возвращает результаты в виде списка словарей:
    {"id": <entry_id>, "score": float, "x": int, "y": int, "w": int, "h": int}
    Координаты x,y — относительные к ROI.
    """
    def __init__(self, threshold: float = 0.9) -> None:
        self.threshold = float(threshold)
        self.templates: List[LibTemplate] = []
        self.refresh()

    def refresh(self) -> None:
        """Перезагружает активные записи из библиотеки и собирает шаблоны."""
        self.templates.clear()
        data = load_library()
        for bucket in ("buffs", "debuffs"):
            for item in data.get(bucket, []):
                # Учитываем флаг активности как bool, чтобы строки типа "false" не считались активными
                if not bool(item.get("active", True)):
                    continue
                raw_path = item.get("image_path") or ""
                if not raw_path:
                    continue
                # Разрешаем путь к ресурсу надёжно и кросс-режимно (dev/pyinstaller)
                path = resource_path(raw_path) if not os.path.isabs(raw_path) else raw_path
                if not os.path.isfile(path):
                    continue
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                h, w = img.shape[:2]
                self.templates.append(LibTemplate(
                    id=item.get("id"),
                    type=item.get("type", bucket[:-1]),
                    path=path,
                    gray=img,
                    width=w,
                    height=h,
                ))

    def match(self, gray_frame: np.ndarray) -> List[Dict[str, int]]:
        """
        Матчит все активные шаблоны в переданном сером кадре (ROI).
        Возвращает список результатов по порогу.
        """
        # Если шаблоны ещё не загружены (или список пуст), попробуем обновиться перед матчингом
        if not self.templates:
            try:
                self.refresh()
            except Exception:
                pass
        results: List[Dict[str, int]] = []
        for t in self.templates:
            try:
                res = cv2.matchTemplate(gray_frame, t.gray, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                if max_val >= self.threshold:
                    x, y = int(max_loc[0]), int(max_loc[1])
                    results.append({
                        "id": t.id,
                        "score": float(max_val),
                        "x": x,
                        "y": y,
                        "w": t.width,
                        "h": t.height,
                    })
            except Exception:
                continue
        return results