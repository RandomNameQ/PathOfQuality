"""Utilities for capturing screen regions into library images."""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import tkinter as tk

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency
    Image = None

from src.capture.base_capture import Region
from src.capture.mss_capture import MSSCapture
from src.buffs.library import save_image_to_library
from src.ui.roi_selector import select_roi, get_last_roi_snapshot


def _array_to_image(arr: np.ndarray) -> Optional["Image.Image"]:
    if Image is None or arr is None:
        return None
    try:
        # mss provides pixels in BGR; convert to RGB
        if arr.shape[-1] >= 3:
            rgb = arr[:, :, :3][:, :, ::-1]
        else:
            rgb = arr
        return Image.fromarray(rgb)
    except Exception:
        return None


def capture_area_to_library(master: tk.Tk) -> Optional[Tuple[str, Tuple[int, int, int, int]]]:
    """Prompt user to select an area and store captured image into library.

    Returns:
        Tuple of (relative image path, (left, top, width, height)) on success, otherwise None.
    """
    roi = select_roi(master)
    if roi is None:
        return None

    left, top, width, height = roi
    if width <= 0 or height <= 0:
        return None

    snapshot = get_last_roi_snapshot(clear=True)
    image = None
    if snapshot is not None and Image is not None:
        try:
            snap_w, snap_h = snapshot.size
            bbox = (
                max(0, min(left, snap_w)),
                max(0, min(top, snap_h)),
                max(0, min(left + width, snap_w)),
                max(0, min(top + height, snap_h)),
            )
            image = snapshot.crop(bbox)
        except Exception:
            image = None

    if image is None:
        capture = MSSCapture()
        try:
            raw = capture.grab(Region(left=left, top=top, width=width, height=height))
        finally:
            capture.close()

        if raw is None:
            return None

        image = _array_to_image(raw)
        if image is None:
            return None

    saved_path = save_image_to_library(image)
    if not saved_path:
        return None

    return saved_path, (left, top, width, height)
