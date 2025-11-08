"""
Floating control dock for quick access actions.
"""
import sys
import ctypes
import tkinter as tk
from typing import Callable, Dict, Optional, Tuple


class ControlDock:
    """Small overlay with circular buttons to control scanning and copy areas."""

    ACTIVE_COLOR = "#10b981"
    INACTIVE_COLOR = "#4b5563"
    BG_COLOR = "#111827"
    BTN_SIZE = 44
    BTN_PADDING = 6

    def __init__(
        self,
        master: tk.Tk,
        on_toggle_scan: Callable[[], None],
        on_toggle_copy: Callable[[], None],
        on_open_main: Callable[[], None],
        *,
        initial_position: Optional[Tuple[int, int]] = None,
        grid_size: int = 20,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
        on_focus_change: Optional[Callable[[bool], None]] = None,
        on_button_action: Optional[Callable[[], None]] = None,
    ) -> None:
        self._master = master
        self._on_toggle_scan = on_toggle_scan
        self._on_toggle_copy = on_toggle_copy
        self._on_open_main = on_open_main
        self._on_position_changed = on_position_changed
        self._on_focus_change = on_focus_change
        self._on_button_action = on_button_action
        self._grid_size = max(1, int(grid_size))

        self._window = tk.Toplevel(master)
        self._window.overrideredirect(True)
        self._window.configure(bg="", highlightthickness=0, bd=0)

        try:
            self._window.attributes("-topmost", True)
            self._window.attributes("-transparentcolor", "")
        except Exception:
            pass

        self._container = tk.Frame(
            self._window,
            bg=self.BG_COLOR,
            bd=0,
            relief="flat",
            highlightthickness=0,
        )
        self._container.pack(padx=10, pady=8)

        self._buttons: Dict[str, Dict[str, int]] = {}
        self._position: Tuple[int, int] = (0, 0)
        self._drag_origin: Optional[Tuple[int, int]] = None
        self._drag_window_origin: Optional[Tuple[int, int]] = None
        self._drag_active = False
        self._drag_moved = False
        self._visible = True
        self._has_focus = False

        self._window.bind("<FocusIn>", lambda _e: self._notify_focus(True), add="+")
        self._window.bind("<FocusOut>", lambda _e: self._notify_focus(False), add="+")

        self._buttons["scan"] = self._create_circle_button(
            text="▶",
            command=self._on_toggle_scan,
            font=("Segoe UI Symbol", 14, "bold"),
        )
        self._buttons["copy"] = self._create_circle_button(
            text="⧉",
            command=self._on_toggle_copy,
            font=("Segoe UI Symbol", 14),
        )
        self._buttons["gear"] = self._create_circle_button(
            text="⚙",
            command=self._on_open_main,
            font=("Segoe UI Symbol", 16),
        )

        for widget in (self._window, self._container):
            widget.bind("<ButtonPress-1>", self._start_drag, add="+")
            widget.bind("<B1-Motion>", self._on_drag, add="+")
            widget.bind("<ButtonRelease-1>", self._stop_drag, add="+")

        self._window.update_idletasks()
        if initial_position is not None:
            self.set_position(initial_position[0], initial_position[1], notify=False)
        else:
            self._reposition(notify=False)

        self._master.bind("<Configure>", self._on_master_configure, add="+")
        self._apply_window_styles()

    def _create_circle_button(
        self,
        text: str,
        command: Callable[[], None],
        font: tuple,
    ) -> Dict[str, int]:
        canvas = tk.Canvas(
            self._container,
            width=self.BTN_SIZE,
            height=self.BTN_SIZE,
            bg=self.BG_COLOR,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(side="left", padx=self.BTN_PADDING)

        circle = canvas.create_oval(
            2,
            2,
            self.BTN_SIZE - 2,
            self.BTN_SIZE - 2,
            fill=self.INACTIVE_COLOR,
            outline="",
        )
        label = canvas.create_text(
            self.BTN_SIZE // 2,
            self.BTN_SIZE // 2,
            text=text,
            fill="#ffffff",
            font=font,
        )

        canvas.bind("<ButtonPress-1>", self._start_drag, add="+")
        canvas.bind("<B1-Motion>", self._on_drag, add="+")
        canvas.bind(
            "<ButtonRelease-1>",
            lambda event, cmd=command: self._handle_button_release(event, cmd),
            add="+",
        )
        canvas.bind("<Enter>", lambda _e: canvas.configure(cursor="hand2"))
        canvas.bind("<Leave>", lambda _e: canvas.configure(cursor=""))
        canvas.bind("<FocusIn>", lambda _e: self._notify_focus(True), add="+")
        canvas.bind("<FocusOut>", lambda _e: self._notify_focus(False), add="+")

        return {"canvas": canvas, "circle": circle, "label": label}

    def _handle_button_release(self, _event, command: Callable[[], None]) -> None:
        if self._drag_moved:
            return
        try:
            command()
        except Exception:
            pass
        if self._on_button_action is not None:
            try:
                self._on_button_action()
            except Exception:
                pass

    def _start_drag(self, event) -> None:
        if getattr(event, "num", 1) != 1:
            return
        self._drag_origin = (event.x_root, event.y_root)
        self._drag_window_origin = (self._window.winfo_x(), self._window.winfo_y())
        self._drag_active = False
        self._drag_moved = False

    def _on_drag(self, event) -> None:
        if self._drag_origin is None or self._drag_window_origin is None:
            return

        dx = event.x_root - self._drag_origin[0]
        dy = event.y_root - self._drag_origin[1]

        if not self._drag_active and (abs(dx) > 2 or abs(dy) > 2):
            self._drag_active = True
            self._drag_moved = True
            for widget in (self._window, self._container):
                widget.configure(cursor="fleur")

        if not self._drag_active:
            return

        new_x = self._drag_window_origin[0] + dx
        new_y = self._drag_window_origin[1] + dy
        self.set_position(new_x, new_y, notify=False)

    def _stop_drag(self, _event) -> None:
        if self._drag_origin is None or self._drag_window_origin is None:
            return

        if self._drag_active and self._on_position_changed:
            self._on_position_changed(*self._position)

        self._drag_origin = None
        self._drag_window_origin = None
        self._drag_active = False
        for widget in (self._window, self._container):
            widget.configure(cursor="")

    def _apply_position(self, x: int, y: int) -> None:
        try:
            self._window.update_idletasks()
            width = self._window.winfo_width() or self._window.winfo_reqwidth()
            height = self._window.winfo_height() or self._window.winfo_reqheight()
            screen_w = self._window.winfo_screenwidth()
            screen_h = self._window.winfo_screenheight()
        except Exception:
            return

        snap = self._grid_size
        snapped_x = int(round(x / snap) * snap)
        snapped_y = int(round(y / snap) * snap)

        snapped_x = max(0, min(snapped_x, screen_w - width))
        snapped_y = max(0, min(snapped_y, screen_h - height))

        try:
            self._window.geometry(f"{width}x{height}+{snapped_x}+{snapped_y}")
            self._position = (snapped_x, snapped_y)
            self._apply_window_styles(no_move=True)
        except Exception:
            pass

    def _reposition(self, notify: bool = True) -> None:
        try:
            self._window.update_idletasks()
            width = self._window.winfo_reqwidth()
            height = self._window.winfo_reqheight()
            screen_w = self._window.winfo_screenwidth()
            x = max(0, (screen_w - width) // 2)
            y = 10
        except Exception:
            return

        self.set_position(x, y, notify=notify)

    def _on_master_configure(self, _event) -> None:
        self._window.after(0, lambda: self.set_position(*self._position, notify=False))

    def set_position(self, x: int, y: int, *, notify: bool = True) -> None:
        self._apply_position(int(x), int(y))
        if notify and self._on_position_changed:
            self._on_position_changed(*self._position)

    def reset_position(self) -> None:
        self._reposition(notify=True)

    def get_position(self) -> Tuple[int, int]:
        return self._position

    def set_scanning_active(self, active: bool) -> None:
        btn = self._buttons.get("scan")
        if not btn:
            return
        color = self.ACTIVE_COLOR if active else self.INACTIVE_COLOR
        text = "■" if active else "▶"
        canvas = btn["canvas"]
        canvas.itemconfigure(btn["circle"], fill=color)
        canvas.itemconfigure(btn["label"], text=text)

    def set_copy_active(self, active: bool) -> None:
        btn = self._buttons.get("copy")
        if not btn:
            return
        color = self.ACTIVE_COLOR if active else self.INACTIVE_COLOR
        canvas = btn["canvas"]
        canvas.itemconfigure(btn["circle"], fill=color)

    def set_topmost(self, enabled: bool) -> None:
        try:
            self._window.attributes("-topmost", bool(enabled))
        except Exception:
            pass

    def show(self) -> None:
        if self._visible:
            return
        try:
            self._window.deiconify()
            self._visible = True
            self._notify_focus(self._has_focus)
            self._apply_window_styles(no_move=True)
        except Exception:
            pass

    def hide(self) -> None:
        if not self._visible:
            return
        try:
            self._window.withdraw()
            self._visible = False
            self._notify_focus(False)
        except Exception:
            pass

    def lift(self) -> None:
        try:
            self._window.lift()
            self._apply_window_styles(no_move=True)
        except Exception:
            pass

    def has_focus(self) -> bool:
        return self._has_focus

    def close(self) -> None:
        try:
            self._window.destroy()
        except Exception:
            pass
        self._visible = False
        self._notify_focus(False)

    def _apply_window_styles(self, no_move: bool = False) -> None:
        if not sys.platform.startswith('win'):
            return
        try:
            hwnd = int(self._window.winfo_id())
            if not hwnd:
                return
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOACTIVATE = 0x0010
            flags = SWP_NOSIZE | SWP_NOACTIVATE
            if no_move:
                flags |= SWP_NOMOVE
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                flags,
            )
        except Exception:
            pass

    def _notify_focus(self, focused: bool) -> None:
        new_state = bool(focused)
        if self._has_focus == new_state:
            return
        self._has_focus = new_state
        if self._on_focus_change is not None:
            try:
                self._on_focus_change(self._has_focus)
            except Exception:
                pass


