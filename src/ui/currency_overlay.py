"""Overlay for positioning currency captures."""
import tkinter as tk
from typing import Dict, List, Optional

import cv2
from PIL import Image

from src.capture.base_capture import Region
from src.capture.mss_capture import MSSCapture
from src.ui.mirror_window import MirrorWindow
from src.ui.positioning import PositioningHelper


class CurrencyOverlay:
    """Manages overlay windows for currency captures."""

    def __init__(self, master: tk.Tk) -> None:
        self._master = master
        self._windows: Dict[str, MirrorWindow] = {}
        self._capture: Optional[MSSCapture] = None
        self._positioning_helper = PositioningHelper(grid_size=16, snap_threshold=8)
        self._active_ids: List[str] = []
        self._positioning_enabled = False
        self._active_currencies: Dict[str, Dict] = {}
        self._runtime_active: Dict[str, Dict] = {}
        self._runtime_positions: Dict[str, Dict[str, int]] = {}

    def _ensure_capture(self) -> MSSCapture:
        if self._capture is None:
            self._capture = MSSCapture()
        return self._capture

    def _grab_capture(self, currency: Dict) -> Image.Image:
        capture_cfg = currency.get('capture', {}) or {}
        left = int(capture_cfg.get('left', 0))
        top = int(capture_cfg.get('top', 0))
        width = max(1, int(capture_cfg.get('width', 0)))
        height = max(1, int(capture_cfg.get('height', 0)))

        try:
            region = Region(left=left, top=top, width=width, height=height)
            frame = self._ensure_capture().grab(region)
        except Exception:
            frame = None

        if frame is None:
            return Image.new('RGBA', (width, height), (16, 185, 129, 160))

        try:
            rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            img = Image.fromarray(rgba)
        except Exception:
            img = Image.new('RGBA', (width, height), (16, 185, 129, 160))
        return img

    def enable_positioning(self, currencies: List[Dict], positions: Dict[str, Dict[str, int]]) -> None:
        """Enable positioning overlays for the provided currencies."""

        self.deactivate_runtime()
        self._active_ids.clear()
        self._active_currencies.clear()
        used_ids: List[str] = []

        for currency in currencies:
            if not bool(currency.get('active', False)):
                continue

            currency_id = currency.get('id')
            if not currency_id:
                continue

            preview = self._grab_capture(currency)
            width = max(1, int(preview.width))
            height = max(1, int(preview.height))

            window = self._windows.get(currency_id)
            if window is None:
                window = MirrorWindow(self._master)
                self._windows[currency_id] = window

            window.enable_positioning(
                preview,
                width,
                height,
                on_snap=self._positioning_helper.create_snapper(currency_id, self._windows),
            )

            position = positions.get(currency_id, {})
            left = int(position.get('left', currency.get('capture', {}).get('left', 0)))
            top = int(position.get('top', currency.get('capture', {}).get('top', 0)))

            window.show(left, top, width, height, alpha=1.0, topmost=True)
            used_ids.append(currency_id)
            self._active_currencies[currency_id] = currency

        # hide unused windows
        for currency_id, window in self._windows.items():
            if currency_id not in used_ids:
                window.hide()

        self._active_ids = used_ids
        self._positioning_enabled = True

    def disable_positioning(self, save_changes: bool = True) -> Dict[str, Dict[str, int]]:
        """Disable positioning and optionally return updated positions."""

        if not self._positioning_enabled:
            return {}

        updated: Dict[str, Dict[str, int]] = {}

        for currency_id, window in list(self._windows.items()):
            if window is None:
                continue

            if currency_id in self._active_ids:
                left, top, width, height = window.get_geometry()
                updated[currency_id] = {'left': int(left), 'top': int(top)}

            window.disable_positioning()
            window.hide()

        self._active_ids.clear()
        self._active_currencies.clear()
        self._positioning_enabled = False
        return updated if save_changes else updated

    def activate_runtime(self, currencies: List[Dict], positions: Dict[str, Dict[str, int]]) -> None:
        """Show runtime overlays for selected currencies."""

        self.disable_positioning(save_changes=False)

        self._runtime_active.clear()
        self._runtime_positions = {}

        used_ids: List[str] = []
        for currency in currencies:
            if not bool(currency.get('active', True)):
                continue

            currency_id = currency.get('id')
            if not currency_id:
                continue

            preview = self._grab_capture(currency)
            width = max(1, int(preview.width))
            height = max(1, int(preview.height))

            window = self._windows.get(currency_id)
            if window is None:
                window = MirrorWindow(self._master)
                self._windows[currency_id] = window

            try:
                window.disable_positioning()
            except Exception:
                pass

            position = positions.get(currency_id, {}) or {}
            left = int(position.get('left', currency.get('capture', {}).get('left', 0)))
            top = int(position.get('top', currency.get('capture', {}).get('top', 0)))

            try:
                window.update_image(preview)
            except Exception:
                pass

            window.show(left, top, width, height, alpha=1.0, topmost=True)

            used_ids.append(currency_id)
            self._runtime_active[currency_id] = currency
            self._runtime_positions[currency_id] = {
                'left': left,
                'top': top,
                'width': width,
                'height': height,
            }

        for currency_id, window in self._windows.items():
            if currency_id not in used_ids and currency_id not in self._active_ids:
                window.hide()

    def deactivate_runtime(self) -> None:
        """Hide runtime overlays."""

        if not self._runtime_active:
            return

        for currency_id in list(self._runtime_active.keys()):
            window = self._windows.get(currency_id)
            if window is not None:
                window.hide()

        self._runtime_active.clear()
        self._runtime_positions.clear()

    def close(self) -> None:
        self.deactivate_runtime()
        for window in list(self._windows.values()):
            try:
                window.close()
            except Exception:
                pass
        self._windows.clear()
        if self._capture is not None:
            try:
                self._capture.close()
            except Exception:
                pass
            self._capture = None

    def refresh(self) -> None:
        """Refresh active currency previews with new captures."""

        if self._positioning_enabled:
            for currency_id, currency in list(self._active_currencies.items()):
                window = self._windows.get(currency_id)
                if window is None or not window.visible:
                    continue

                if not bool(currency.get('active', False)):
                    window.hide()
                    continue

                preview = self._grab_capture(currency)
                if preview is None:
                    continue

                try:
                    width = max(1, int(window.top.winfo_width()))
                    height = max(1, int(window.top.winfo_height()))
                    if preview.width != width or preview.height != height:
                        preview = preview.resize((width, height), Image.LANCZOS)
                except Exception:
                    pass

                try:
                    window.update_image(preview)
                except Exception:
                    pass
            return

        if not self._runtime_active:
            return

        for currency_id, currency in list(self._runtime_active.items()):
            window = self._windows.get(currency_id)
            if window is None or not window.visible:
                continue

            preview = self._grab_capture(currency)
            if preview is None:
                continue

            pos = self._runtime_positions.get(currency_id, {})
            left = int(pos.get('left', currency.get('capture', {}).get('left', 0)))
            top = int(pos.get('top', currency.get('capture', {}).get('top', 0)))
            width = max(1, int(pos.get('width', preview.width)))
            height = max(1, int(pos.get('height', preview.height)))

            try:
                if preview.width != width or preview.height != height:
                    preview = preview.resize((width, height), Image.LANCZOS)
            except Exception:
                pass

            try:
                window.update_image(preview)
            except Exception:
                pass

            window.show(left, top, width, height, alpha=1.0, topmost=True)

        for currency_id in list(self._runtime_positions.keys()):
            if currency_id in self._runtime_active:
                continue
            window = self._windows.get(currency_id)
            if window is not None:
                window.hide()
