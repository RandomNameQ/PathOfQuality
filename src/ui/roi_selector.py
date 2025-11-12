import tkinter as tk
from typing import Optional, Tuple

try:
    from PIL import ImageGrab, ImageTk, Image
except Exception:  # pragma: no cover - optional dependency
    ImageGrab = None
    ImageTk = None
    Image = None

_LAST_SNAPSHOT = None


def get_last_roi_snapshot(clear: bool = True):
    global _LAST_SNAPSHOT
    snap = _LAST_SNAPSHOT
    if clear:
        _LAST_SNAPSHOT = None
    if snap is not None and Image is not None:
        try:
            return snap.copy()
        except Exception:
            return snap
    return snap


def select_roi(master: tk.Tk) -> Optional[Tuple[int, int, int, int]]:
    """
    Отображает полноэкранный полупрозрачный оверлей и позволяет мышью выделить прямоугольник.
    Возвращает (left, top, width, height) в координатах экрана или None, если выбор отменён (ESC).
    """
    screen_w = master.winfo_screenwidth()
    screen_h = master.winfo_screenheight()

    overlay = tk.Toplevel(master)
    overlay.attributes('-topmost', True)
    overlay.overrideredirect(True)
    overlay.geometry(f"{screen_w}x{screen_h}+0+0")

    global _LAST_SNAPSHOT
    _LAST_SNAPSHOT = None
    bg_image = None
    if ImageGrab is not None and ImageTk is not None:
        try:
            snapshot = ImageGrab.grab()
            bg_image = ImageTk.PhotoImage(snapshot)
            _LAST_SNAPSHOT = snapshot
        except Exception:
            bg_image = None

    canvas = tk.Canvas(overlay, width=screen_w, height=screen_h, highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    canvas.configure(cursor='crosshair')

    if bg_image is not None:
        canvas.create_image(0, 0, image=bg_image, anchor='nw')
    else:
        overlay.configure(bg='black')
        try:
            overlay.attributes('-alpha', 0.15)
        except Exception:
            pass

    start = {'x': 0, 'y': 0}
    rect_id = {'id': None}
    result = {'roi': None}

    def on_press(event):
        start['x'], start['y'] = event.x, event.y
        if rect_id['id'] is not None:
            canvas.delete(rect_id['id'])
        rect_id['id'] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red', width=2)

    def on_drag(event):
        if rect_id['id'] is None:
            return
        canvas.coords(rect_id['id'], start['x'], start['y'], event.x, event.y)

    def on_release(event):
        x1, y1 = start['x'], start['y']
        x2, y2 = event.x, event.y
        left = int(min(x1, x2))
        top = int(min(y1, y2))
        width = int(abs(x2 - x1))
        height = int(abs(y2 - y1))
        # Защита от нулевой области
        if width < 5 or height < 5:
            result['roi'] = None
        else:
            result['roi'] = (left, top, width, height)
        overlay.destroy()

    def on_escape(event):
        result['roi'] = None
        overlay.destroy()

    overlay.bind('<Escape>', on_escape)
    canvas.bind('<ButtonPress-1>', on_press)
    canvas.bind('<B1-Motion>', on_drag)
    canvas.bind('<ButtonRelease-1>', on_release)
    overlay.grab_set()
    overlay.focus_set()
    overlay.wait_window()
    return result['roi']