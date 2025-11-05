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
        self._canvas = tk.Canvas(self._top, highlightthickness=0)
        self._canvas.pack(fill='both', expand=True)
        self._rect_id: Optional[int] = None
        self._roi: Optional[Tuple[int, int, int, int]] = None

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