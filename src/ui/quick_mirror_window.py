"""
QuickCraft-specific mirror window to keep overlays non-activating and click-through
without impacting other overlay types.
"""
from __future__ import annotations

import ctypes
import sys
from typing import Optional

from src.ui.mirror_window import MirrorWindow


class QuickMirrorWindow(MirrorWindow):
    """Dedicated mirror window for Quick Craft runtime overlays.

    - Never activates on show/lift (WS_EX_NOACTIVATE)
    - Click-through in runtime (WS_EX_TRANSPARENT)
    - Uses SetWindowPos with SWP_NOACTIVATE to manage z-order
    """

    def _apply_clickthrough(self, enable: bool) -> None:  # override
        if not self._clickthrough_supported or self._hwnd is None or not sys.platform.startswith('win'):
            return

        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_NOACTIVATE = 0x08000000
        LWA_ALPHA = 0x00000002

        try:
            style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            # Always layered, toolwindow and no-activate so this window never steals focus
            style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            # Ensure it does NOT appear in the taskbar
            style &= ~WS_EX_APPWINDOW
            if enable:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT

            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style)
            # Update layered alpha
            try:
                alpha_byte = max(0, min(255, int(self._current_alpha * 255)))
            except Exception:
                alpha_byte = 255
            ctypes.windll.user32.SetLayeredWindowAttributes(self._hwnd, 0, alpha_byte, LWA_ALPHA)

            # Keep on top without activation
            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            )
        except Exception:
            pass

    def show(self, left: int, top: int, width: int, height: int, alpha: float = 1.0, topmost: bool = True) -> None:  # override
        was_visible = self.visible

        # Geometry
        new_geom = (int(width), int(height), int(left), int(top))
        if self._last_geometry != new_geom:
            try:
                self.top.geometry(f"{new_geom[0]}x{new_geom[1]}+{new_geom[2]}+{new_geom[3]}")
            except Exception:
                pass
            self._last_geometry = new_geom

        # Alpha only (avoid toggling Tk -topmost here)
        try:
            self.top.attributes('-alpha', float(alpha))
        except Exception:
            pass
        try:
            self._current_alpha = float(alpha)
        except Exception:
            self._current_alpha = 1.0

        # Ensure click-through in runtime (non-positioning)
        if not self._positioning_enabled:
            self._apply_clickthrough(True)
        else:
            self._apply_clickthrough(False)

        if not self.visible:
            try:
                self.top.deiconify()
                self.visible = True
            except Exception:
                pass

        # Do NOT call lift(); rely on SetWindowPos with NOACTIVATE in _apply_clickthrough
