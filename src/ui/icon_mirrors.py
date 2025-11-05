import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple
import sys
try:
    import ctypes  # для click-through окна сетки на Windows
except Exception:
    ctypes = None

import cv2
from PIL import Image, ImageTk

from src.buffs.library import load_library, update_entry


class _Mirror:
    def __init__(self, master: tk.Tk) -> None:
        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)
        try:
            self.top.attributes('-topmost', True)
        except Exception:
            pass
        # Простая метка без рамки — только перетаскивание
        self.label = tk.Label(self.top, bg='black')
        self.label.pack(fill='both', expand=True)
        self.photo: Optional[ImageTk.PhotoImage] = None
        self.visible = False
        # Для режима позиционирования
        self._base_img: Optional[Image.Image] = None
        self._dragging = False
        self._start_x = 0
        self._start_y = 0
        self._win_x = 0
        self._win_y = 0
        self._on_snap: Optional[Callable[[int, int, int, int], Tuple[int, int]]] = None

    def show(self, left: int, top: int, width: int, height: int, alpha: float = 1.0):
        self.top.geometry(f"{width}x{height}+{left}+{top}")
        try:
            self.top.attributes('-alpha', float(alpha))
            # Переутверждаем topmost каждый показ, чтобы окна оставались сверху
            self.top.attributes('-topmost', True)
        except Exception:
            pass
        if not self.visible:
            self.top.deiconify()
            self.visible = True

    def update_image(self, img: Image.Image):
        self.photo = ImageTk.PhotoImage(img)
        self.label.configure(image=self.photo)

    def hide(self):
        if self.visible:
            self.top.withdraw()
            self.visible = False

    def close(self):
        try:
            self.top.destroy()
        except Exception:
            pass

    # ====== Режим позиционирования (перетаскивание и масштаб колесом) ======
    def enable_positioning(self, base_img: Image.Image, width: int, height: int, on_snap: Optional[Callable[[int, int, int, int], Tuple[int, int]]] = None) -> None:
        self._base_img = base_img
        self._on_snap = on_snap
        try:
            scaled = base_img.resize((max(8, int(width)), max(8, int(height))), Image.LANCZOS)
        except Exception:
            scaled = base_img
        self.update_image(scaled)

        def on_press_l(event):
            self._dragging = True
            self._start_x = event.x_root
            self._start_y = event.y_root
            self._win_x = self.top.winfo_x()
            self._win_y = self.top.winfo_y()

        def on_drag_l(event):
            if not self._dragging:
                return
            dx = event.x_root - self._start_x
            dy = event.y_root - self._start_y
            new_x = self._win_x + dx
            new_y = self._win_y + dy
            if self._on_snap is not None:
                try:
                    new_x, new_y = self._on_snap(int(new_x), int(new_y), int(self.top.winfo_width()), int(self.top.winfo_height()))
                except Exception:
                    pass
            self.top.geometry(f"+{new_x}+{new_y}")

        def on_release_l(event):
            self._dragging = False

        # Колесо отключено — без изменения размеров

        # Привязки
        try:
            self.label.bind('<ButtonPress-1>', on_press_l)
            self.label.bind('<B1-Motion>', on_drag_l)
            self.label.bind('<ButtonRelease-1>', on_release_l)
        except Exception:
            pass

    def disable_positioning(self) -> None:
        try:
            self.label.unbind('<ButtonPress-1>')
            self.label.unbind('<B1-Motion>')
            self.label.unbind('<ButtonRelease-1>')
        except Exception:
            pass
        self._base_img = None
        self._on_snap = None

    def get_geometry(self) -> Tuple[int, int, int, int]:
        return (
            int(self.top.winfo_x()),
            int(self.top.winfo_y()),
            int(self.top.winfo_width()),
            int(self.top.winfo_height()),
        )


class IconMirrorsOverlay:
    """
    Создаёт набор окон-зеркал для активированных иконок.
    На каждом обновлении получает результаты матчинга и текущий кадр ROI,
    вырезает область совпадения и отображает её в соответствующем окне
    по сохранённым координатам/размеру из библиотеки.
    """
    def __init__(self, master: tk.Tk) -> None:
        self._master = master
        self._mirrors: Dict[str, _Mirror] = {}
        self._last_ids: List[str] = []
        self._positioning: bool = False
        self._entry_types: Dict[str, str] = {}
        # Параметры сетки и притяжения
        self._grid_size: int = 16
        self._snap_threshold: int = 8
        self._grid_top: Optional[tk.Toplevel] = None
        self._grid_canvas: Optional[tk.Canvas] = None

    def _get_or_create(self, entry_id: str) -> _Mirror:
        m = self._mirrors.get(entry_id)
        if m is None:
            m = _Mirror(self._master)
            self._mirrors[entry_id] = m
        return m

    def update(self, results: List[Dict], frame_bgr, roi: Tuple[int, int, int, int]) -> None:
        # В режиме позиционирования не меняем содержимое окон
        if self._positioning:
            return
        # Загружаем свежие параметры из библиотеки
        lib = load_library()
        entries: Dict[str, Dict] = {}
        for bucket in ("buffs", "debuffs"):
            for it in lib.get(bucket, []):
                entries[it.get('id')] = it

        show_ids: List[str] = []
        for r in results:
            entry_id = r.get('id')
            show_ids.append(entry_id)
            item = entries.get(entry_id) or {}
            pos = item.get('position', {"left": 0, "top": 0})
            size = item.get('size', {"width": 0, "height": 0})
            alpha = float(item.get('transparency', 1.0))

            # Вырезаем найденную область из ROI кадра
            x, y, w, h = r.get('x', 0), r.get('y', 0), r.get('w', 0), r.get('h', 0)
            try:
                crop_bgr = frame_bgr[y:y + h, x:x + w]
                crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            except Exception:
                continue

            try:
                img = Image.fromarray(crop_rgb)
                out_w = int(size.get('width') or w)
                out_h = int(size.get('height') or h)
                if out_w <= 0:
                    out_w = w
                if out_h <= 0:
                    out_h = h
                img = img.resize((out_w, out_h), Image.LANCZOS)
            except Exception:
                continue

            m = self._get_or_create(entry_id)
            m.update_image(img)
            m.show(int(pos.get('left', 0)), int(pos.get('top', 0)), int(img.width), int(img.height), alpha=alpha)

        # Скрываем окна, которых нет в текущих результатах
        for k, m in list(self._mirrors.items()):
            if k not in show_ids:
                m.hide()

        self._last_ids = show_ids

    def reload_library(self) -> None:
        # Параметры позиций/размеров обновятся при следующем update()
        pass

    # ===== Режим глобального позиционирования активных иконок =====
    def enable_positioning_mode(self) -> None:
        lib = load_library()
        self._entry_types.clear()
        active_items: List[Dict] = []
        for bucket in ("buffs", "debuffs"):
            for it in lib.get(bucket, []):
                if bool(it.get('active', False)):
                    active_items.append(it)
                    self._entry_types[it.get('id')] = 'buff' if bucket == 'buffs' else 'debuff'

        # Сетку больше не показываем, чтобы не мешать кликам и фокусу

        for it in active_items:
            entry_id = it.get('id')
            pos = it.get('position', {"left": 0, "top": 0})
            size = it.get('size', {"width": 64, "height": 64})
            alpha = float(it.get('transparency', 1.0))
            path = it.get('image_path') or ''
            try:
                base_img = Image.open(path).convert('RGBA') if path else Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            except Exception:
                base_img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            # Обеспечим минимальный удобный размер окна при входе в режим
            size_w = int(size.get('width', 64))
            size_h = int(size.get('height', 64))
            size_w = max(64, size_w)
            size_h = max(64, size_h)
            m = self._get_or_create(entry_id)
            m.enable_positioning(base_img, size_w, size_h, on_snap=self._make_snapper(entry_id))
            m.show(int(pos.get('left', 0)), int(pos.get('top', 0)), size_w, size_h, alpha=alpha)
            # Обеспечим, что окна останутся поверх обычных окон
            try:
                m.top.lift()
                m.top.attributes('-topmost', True)
            except Exception:
                pass

        self._positioning = True

    def disable_positioning_mode(self, save_changes: bool = True) -> None:
        if not self._positioning:
            return
        if save_changes:
            # Сохраняем актуальные позиции/размеры
            for entry_id, m in list(self._mirrors.items()):
                left, top, width, height = m.get_geometry()
                entry_type = self._entry_types.get(entry_id) or 'buff'
                try:
                    update_entry(entry_id, entry_type, {
                        'left': int(left),
                        'top': int(top),
                        'width': int(width),
                        'height': int(height),
                    })
                except Exception:
                    pass
        # Отключаем интерактив
        for m in list(self._mirrors.values()):
            m.disable_positioning()
            m.hide()
        # Сетка не используется — на всякий случай уничтожим, если была
        self._destroy_grid_overlay()
        self._positioning = False

    # ===== Сетка и притяжение =====
    def _ensure_grid_overlay(self) -> None:
        try:
            if self._grid_top is None:
                self._grid_top = tk.Toplevel(self._master)
                self._grid_top.overrideredirect(True)
                try:
                    self._grid_top.attributes('-topmost', True)
                    self._grid_top.attributes('-alpha', 0.25)
                except Exception:
                    pass
                w = self._master.winfo_screenwidth()
                h = self._master.winfo_screenheight()
                self._grid_top.geometry(f"{w}x{h}+0+0")
                self._grid_canvas = tk.Canvas(self._grid_top, bg='', highlightthickness=0)
                self._grid_canvas.pack(fill='both', expand=True)
                # Нарисуем линии сетки
                color = '#4a4a4a'
                for x in range(0, w, self._grid_size):
                    try:
                        self._grid_canvas.create_line(x, 0, x, h, fill=color)
                    except Exception:
                        pass
                for y in range(0, h, self._grid_size):
                    try:
                        self._grid_canvas.create_line(0, y, w, y, fill=color)
                    except Exception:
                        pass
                # Сделаем оверлей «сквозным» для мыши, чтобы он не блокировал клики
                try:
                    if sys.platform.startswith('win') and ctypes is not None:
                        hwnd = int(self._grid_top.winfo_id())
                        GWL_EXSTYLE = -20
                        WS_EX_LAYERED = 0x00080000
                        WS_EX_TRANSPARENT = 0x00000020
                        user32 = ctypes.windll.user32
                        exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle | WS_EX_LAYERED | WS_EX_TRANSPARENT)
                except Exception:
                    pass
            else:
                self._grid_top.deiconify()
        except Exception:
            pass

    def _destroy_grid_overlay(self) -> None:
        try:
            if self._grid_top is not None:
                self._grid_top.destroy()
        except Exception:
            pass
        self._grid_top = None
        self._grid_canvas = None

    def _make_snapper(self, my_id: str) -> Callable[[int, int, int, int], Tuple[int, int]]:
        def snap(x: int, y: int, w: int, h: int) -> Tuple[int, int]:
            # Снэп к сетке
            try:
                gx = round(x / self._grid_size) * self._grid_size
                gy = round(y / self._grid_size) * self._grid_size
            except Exception:
                gx, gy = x, y
            sx, sy = int(gx), int(gy)
            # Притяжение к соседним окнам
            try:
                th = self._snap_threshold
                for k, m in self._mirrors.items():
                    if k == my_id:
                        continue
                    mx = int(m.top.winfo_x())
                    my = int(m.top.winfo_y())
                    mw = int(m.top.winfo_width())
                    mh = int(m.top.winfo_height())
                    # Горизонтальные края
                    if abs(sx - mx) <= th:
                        sx = mx
                    if abs(sx - (mx + mw)) <= th:
                        sx = mx + mw
                    right = sx + w
                    if abs(right - mx) <= th:
                        sx = mx - w
                    if abs(right - (mx + mw)) <= th:
                        sx = mx + mw - w
                    # Вертикальные края
                    if abs(sy - my) <= th:
                        sy = my
                    if abs(sy - (my + mh)) <= th:
                        sy = my + mh
                    bottom = sy + h
                    if abs(bottom - my) <= th:
                        sy = my - h
                    if abs(bottom - (my + mh)) <= th:
                        sy = my + mh - h
            except Exception:
                pass
            return int(sx), int(sy)
        return snap

    def close(self) -> None:
        for m in list(self._mirrors.values()):
            m.close()
        self._mirrors.clear()