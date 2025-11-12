"""Utility helpers for configuring Tk windows on Windows."""
import sys
import ctypes
import tkinter as tk

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
LWA_ALPHA = 0x00000002


def apply_toolwindow_style(
    window: tk.Toplevel,
    *,
    no_activate: bool = True,
    layered: bool = False,
    transparent: bool = False,
    alpha: int = 255,
) -> None:
    """Apply WS_EX_TOOLWINDOW style to hide a Tk window from Alt+Tab/taskbar."""
    if not sys.platform.startswith('win'):
        return
    try:
        window.update_idletasks()
        hwnd = int(window.winfo_id())
        if not hwnd:
            return

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TOOLWINDOW
        style &= ~WS_EX_APPWINDOW
        if no_activate:
            style |= WS_EX_NOACTIVATE
        if layered:
            style |= WS_EX_LAYERED
            if transparent:
                style |= WS_EX_TRANSPARENT

        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        if layered:
            ctypes.windll.user32.SetLayeredWindowAttributes(
                hwnd,
                0,
                max(0, min(255, int(alpha))),
                LWA_ALPHA,
            )
    except Exception:
        pass
