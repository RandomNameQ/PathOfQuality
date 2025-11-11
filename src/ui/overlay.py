import sys
import ctypes
import tkinter as tk
from typing import Optional, Tuple


class OverlayHighlighter:
    """
    Небольшой верхний оверлей, который подсвечивает текущую зону анализа (ROI).
    """
    def __init__(self, master: tk.Tk) -> None:
        self._master = master
        self._top = tk.Toplevel(master)
        self._top.withdraw()
        self._top.overrideredirect(True)
        try:
            self._top.attributes('-topmost', True)
            self._top.attributes('-alpha', 0.20)
        except Exception:
            pass
        self._apply_window_styles()
        self._canvas = tk.Canvas(self._top, highlightthickness=0)
        self._canvas.pack(fill='both', expand=True)
        self._rect_id: Optional[int] = None
        self._roi: Optional[Tuple[int, int, int, int]] = None

    def _apply_window_styles(self) -> None:
        if not sys.platform.startswith('win'):
            return
        try:
            self._top.update_idletasks()
            hwnd = int(self._top.winfo_id())
            if not hwnd:
                return
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_APPWINDOW = 0x00040000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            style &= ~WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

            # Keep on top without activation
            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            )
        except Exception:
            pass

    def show(self, roi: Tuple[int, int, int, int]) -> None:
        self._roi = roi
        left, top, width, height = roi
        self._top.geometry(f"{width}x{height}+{left}+{top}")
        self._canvas.configure(width=width, height=height)
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
        self._rect_id = self._canvas.create_rectangle(1, 1, width - 2, height - 2, outline='red', width=2)
        self._top.deiconify()

    def update(self, roi: Tuple[int, int, int, int]) -> None:
        if self._top.state() == 'withdrawn':
            # Если скрыт, просто обновим внутреннее состояние
            self._roi = roi
            return
        self.show(roi)

    def hide(self) -> None:
        self._top.withdraw()

    def close(self) -> None:
        try:
            self._top.destroy()
        except Exception:
            pass