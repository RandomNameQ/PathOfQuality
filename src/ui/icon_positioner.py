import os
import tkinter as tk
from typing import Optional, Tuple

from PIL import Image, ImageTk


def position_icon(master: tk.Tk, image_path: str,
                  initial_left: int, initial_top: int,
                  initial_width: int, initial_height: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Полноэкранный оверлей для позиционирования иконки.
    - ЛКМ: перетаскивание
    - ПКМ: изменение размера (гориз/верт тянем угол)
    - Колесо мыши: масштаб
    - ESC: отмена
    - Enter/Double-Click: сохранить

    Возвращает (left, top, width, height) или None.
    """
    overlay = tk.Toplevel(master)
    overlay.overrideredirect(True)
    try:
        overlay.attributes('-topmost', True)
        overlay.attributes('-alpha', 0.25)
    except Exception:
        pass
    screen_w = master.winfo_screenwidth()
    screen_h = master.winfo_screenheight()
    overlay.geometry(f"{screen_w}x{screen_h}+0+0")
    overlay.configure(bg='black')

    # Загружаем изображение
    img = None
    try:
        if image_path and os.path.isfile(image_path):
            base_img = Image.open(image_path).convert('RGBA')
        else:
            # Пустой прозрачный квадрат, если картинки нет
            base_img = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    except Exception:
        base_img = Image.new('RGBA', (96, 96), (0, 0, 0, 0))

    size_w = int(initial_width or base_img.width)
    size_h = int(initial_height or base_img.height)
    if size_w <= 0:
        size_w = base_img.width
    if size_h <= 0:
        size_h = base_img.height

    def make_photo(w: int, h: int) -> ImageTk.PhotoImage:
        im = base_img.resize((max(8, w), max(8, h)), Image.LANCZOS)
        return ImageTk.PhotoImage(im)

    photo = make_photo(size_w, size_h)

    # Окно самой иконки
    icon_win = tk.Toplevel(master)
    icon_win.overrideredirect(True)
    try:
        icon_win.attributes('-topmost', True)
        icon_win.attributes('-alpha', 1.0)
    except Exception:
        pass
    left = int(initial_left or (screen_w - size_w) // 2)
    top = int(initial_top or (screen_h - size_h) // 2)
    icon_win.geometry(f"{size_w}x{size_h}+{left}+{top}")

    lbl = tk.Label(icon_win, image=photo, bg='black')
    lbl.pack(fill='both', expand=True)
    lbl._photo = photo  # удерживаем ссылку

    state = {
        'drag': False,
        'resize': False,
        'start_x': 0,
        'start_y': 0,
        'win_x': left,
        'win_y': top,
        'w': size_w,
        'h': size_h,
    }

    def on_press_l(event):
        state['drag'] = True
        state['start_x'] = event.x_root
        state['start_y'] = event.y_root
        state['win_x'] = icon_win.winfo_x()
        state['win_y'] = icon_win.winfo_y()

    def on_drag_l(event):
        if not state['drag']:
            return
        dx = event.x_root - state['start_x']
        dy = event.y_root - state['start_y']
        icon_win.geometry(f"+{state['win_x'] + dx}+{state['win_y'] + dy}")

    def on_release_l(event):
        state['drag'] = False

    def on_press_r(event):
        state['resize'] = True
        state['start_x'] = event.x_root
        state['start_y'] = event.y_root
        state['w'] = icon_win.winfo_width()
        state['h'] = icon_win.winfo_height()

    def on_drag_r(event):
        if not state['resize']:
            return
        dx = event.x_root - state['start_x']
        dy = event.y_root - state['start_y']
        new_w = max(8, state['w'] + dx)
        new_h = max(8, state['h'] + dy)
        new_photo = make_photo(new_w, new_h)
        lbl.configure(image=new_photo)
        lbl._photo = new_photo
        icon_win.geometry(f"{new_w}x{new_h}+{icon_win.winfo_x()}+{icon_win.winfo_y()}")

    def on_release_r(event):
        state['resize'] = False

    def on_wheel(event):
        delta = 60 if (getattr(event, 'delta', 0) > 0) else -60
        new_w = max(8, icon_win.winfo_width() + delta)
        new_h = max(8, icon_win.winfo_height() + int(delta * (icon_win.winfo_height() / max(1, icon_win.winfo_width()))))
        new_photo = make_photo(new_w, new_h)
        lbl.configure(image=new_photo)
        lbl._photo = new_photo
        icon_win.geometry(f"{new_w}x{new_h}+{icon_win.winfo_x()}+{icon_win.winfo_y()}")

    def finalize_and_close():
        res_left = icon_win.winfo_x()
        res_top = icon_win.winfo_y()
        res_w = icon_win.winfo_width()
        res_h = icon_win.winfo_height()
        try:
            icon_win.destroy()
        except Exception:
            pass
        try:
            overlay.destroy()
        except Exception:
            pass
        return (res_left, res_top, res_w, res_h)

    result = {'val': None}

    def on_escape(event):
        result['val'] = None
        try:
            icon_win.destroy()
        except Exception:
            pass
        try:
            overlay.destroy()
        except Exception:
            pass

    def on_enter(event):
        result['val'] = finalize_and_close()

    def on_double_click(event):
        result['val'] = finalize_and_close()

    # Привязки
    lbl.bind('<ButtonPress-1>', on_press_l)
    lbl.bind('<B1-Motion>', on_drag_l)
    lbl.bind('<ButtonRelease-1>', on_release_l)
    lbl.bind('<ButtonPress-3>', on_press_r)
    lbl.bind('<B3-Motion>', on_drag_r)
    lbl.bind('<ButtonRelease-3>', on_release_r)
    lbl.bind('<MouseWheel>', on_wheel)
    overlay.bind('<Escape>', on_escape)
    overlay.bind('<Return>', on_enter)
    lbl.bind('<Double-Button-1>', on_double_click)

    overlay.grab_set()
    overlay.focus_set()
    overlay.wait_window(icon_win)
    return result['val']