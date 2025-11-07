"""
Individual mirror window for displaying icon.
"""
import sys
import tkinter as tk
from typing import Optional, Callable, Tuple
from PIL import Image, ImageTk
import ctypes


class _POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MirrorWindow:
    """Single mirror window for displaying a detected icon."""
    
    def __init__(self, master: tk.Tk) -> None:
        """
        Initialize mirror window.
        
        Args:
            master: Parent Tk window
        """
        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)
        
        try:
            self.top.attributes('-topmost', True)
        except Exception:
            pass
            
        self.label = tk.Label(self.top, bg='black')
        self.label.pack(fill='both', expand=True)
        
        self.photo: Optional[ImageTk.PhotoImage] = None
        self.visible = False
        self._positioning_enabled = False
        
        # For positioning mode
        self._base_img: Optional[Image.Image] = None
        self._dragging = False
        self._start_x = 0
        self._start_y = 0
        self._win_x = 0
        self._win_y = 0
        self._on_snap: Optional[Callable[[int, int, int, int], Tuple[int, int]]] = None
        self._clickthrough_supported = False
        self._hwnd: Optional[int] = None
        self._current_alpha: float = 1.0
        self._hover_hidden = False
        self._hover_prev_alpha = 1.0
        self._hover_poll_job: Optional[str] = None
        self._hover_active = False
        self._base_size: Tuple[int, int] = (1, 1)
        self._scale: float = 1.0
        self._position_width: int = 0
        self._position_height: int = 0

        self._init_clickthrough()
        self._apply_clickthrough(True)
        self._bind_hover_events()
        self._start_hover_detection()

    def _bind_hover_events(self) -> None:
        try:
            self.label.bind('<Enter>', self._on_pointer_enter)
            self.label.bind('<Leave>', self._on_pointer_leave)
        except Exception:
            pass

    def _start_hover_detection(self) -> None:
        if not sys.platform.startswith('win'):
            return

        self._schedule_hover_poll()

    def _schedule_hover_poll(self) -> None:
        try:
            if self._hover_poll_job is not None:
                self.top.after_cancel(self._hover_poll_job)
        except Exception:
            pass

        try:
            self._hover_poll_job = self.top.after(60, self._hover_poll)
        except Exception:
            self._hover_poll_job = None

    def _init_clickthrough(self) -> None:
        if not sys.platform.startswith('win'):
            return

        try:
            # Ensure window is created before retrieving handle
            self.top.update_idletasks()
            hwnd = int(self.top.winfo_id())
            if hwnd:
                self._hwnd = hwnd
                self._clickthrough_supported = True
        except Exception:
            self._clickthrough_supported = False

    def _apply_clickthrough(self, enable: bool) -> None:
        if not self._clickthrough_supported or self._hwnd is None:
            return

        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        LWA_ALPHA = 0x00000002

        try:
            style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            if enable:
                style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            else:
                style |= WS_EX_LAYERED
                style &= ~WS_EX_TRANSPARENT

            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style)
            self._update_layered_alpha(LWA_ALPHA)
        except Exception:
            pass

    def _update_layered_alpha(self, flag: int = 0x00000002) -> None:
        if not self._clickthrough_supported or self._hwnd is None:
            return

        try:
            alpha_byte = max(0, min(255, int(self._current_alpha * 255)))
            ctypes.windll.user32.SetLayeredWindowAttributes(
                self._hwnd,
                0,
                alpha_byte,
                flag
            )
        except Exception:
            pass
        
    def show(self, left: int, top: int, width: int, height: int, alpha: float = 1.0, topmost: bool = True) -> None:
        """
        Show mirror window at specified position.
        
        Args:
            left: X coordinate
            top: Y coordinate
            width: Window width
            height: Window height
            alpha: Transparency (0.0 to 1.0)
        """
        self.top.geometry(f"{width}x{height}+{left}+{top}")
        
        try:
            self.top.attributes('-alpha', float(alpha))
            self.top.attributes('-topmost', bool(topmost))
        except Exception:
            pass

        try:
            self._current_alpha = float(alpha)
        except Exception:
            self._current_alpha = 1.0

        self._update_layered_alpha()
            
        if not self._positioning_enabled:
            self._apply_clickthrough(True)

        if not self.visible:
            self.top.deiconify()
            self.visible = True
            
    def update_image(self, img: Image.Image) -> None:
        """
        Update displayed image.
        
        Args:
            img: PIL Image to display
        """
        self.photo = ImageTk.PhotoImage(img)
        self.label.configure(image=self.photo)
        
    def hide(self) -> None:
        """Hide mirror window."""
        if self.visible:
            self.top.withdraw()
            self.visible = False
            self._hover_hidden = False
            self._hover_prev_alpha = 1.0
            
    def close(self) -> None:
        """Close and destroy window."""
        try:
            if self._hover_poll_job is not None:
                self.top.after_cancel(self._hover_poll_job)
        except Exception:
            pass

        try:
            self.top.destroy()
        except Exception:
            pass
            
    def enable_positioning(
        self, 
        base_img: Image.Image, 
        width: int, 
        height: int,
        on_snap: Optional[Callable[[int, int, int, int], Tuple[int, int]]] = None
    ) -> None:
        """
        Enable positioning mode with drag support.
        
        Args:
            base_img: Base image to display
            width: Display width
            height: Display height
            on_snap: Optional snap callback function
        """
        self._base_img = base_img
        self._on_snap = on_snap
        self._positioning_enabled = True
        self._apply_clickthrough(False)

        base_w = max(1, int(base_img.width))
        base_h = max(1, int(base_img.height))
        self._base_size = (base_w, base_h)
        width = max(8, int(width))
        height = max(8, int(height))
        try:
            self._scale = width / float(base_w)
        except Exception:
            self._scale = 1.0
        self._position_width = width
        self._position_height = height
        
        try:
            scaled = base_img.resize(
                (width, height), 
                Image.LANCZOS
            )
        except Exception:
            scaled = base_img
            
        self.update_image(scaled)

        def _apply_resize(new_w: int, new_h: int) -> None:
            new_w = max(8, int(new_w))
            new_h = max(8, int(new_h))
            self._position_width = new_w
            self._position_height = new_h
            try:
                resized = self._base_img.resize((new_w, new_h), Image.LANCZOS)
            except Exception:
                resized = self._base_img
            if resized is not None:
                self.update_image(resized)
            try:
                left = self.top.winfo_x()
                top = self.top.winfo_y()
                self.top.geometry(f"{new_w}x{new_h}+{left}+{top}")
            except Exception:
                pass

        def _adjust_scale(direction: int) -> None:
            if self._base_img is None:
                return
            base_w, base_h = self._base_size
            if base_w <= 0 or base_h <= 0:
                return
            step = 0.1
            try:
                new_scale = self._scale * (1.0 + step * direction)
            except Exception:
                new_scale = self._scale
            new_scale = max(0.1, min(5.0, new_scale))
            self._scale = new_scale
            new_w = int(base_w * new_scale)
            new_h = int(base_h * new_scale)
            _apply_resize(new_w, new_h)

        def on_wheel(event) -> None:
            delta = getattr(event, 'delta', 0)
            if delta == 0:
                return
            direction = 1 if delta > 0 else -1
            _adjust_scale(direction)

        def on_button4(_event) -> None:
            _adjust_scale(1)

        def on_button5(_event) -> None:
            _adjust_scale(-1)
        
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
                    new_x, new_y = self._on_snap(
                        int(new_x), 
                        int(new_y),
                        int(self.top.winfo_width()),
                        int(self.top.winfo_height())
                    )
                except Exception:
                    pass
                    
            self.top.geometry(f"+{new_x}+{new_y}")
            
        def on_release_l(event):
            self._dragging = False
            
        try:
            self.label.bind('<ButtonPress-1>', on_press_l)
            self.label.bind('<B1-Motion>', on_drag_l)
            self.label.bind('<ButtonRelease-1>', on_release_l)
            self.label.bind('<MouseWheel>', on_wheel)
            self.label.bind('<Button-4>', on_button4)
            self.label.bind('<Button-5>', on_button5)
        except Exception:
            pass
            
    def disable_positioning(self) -> None:
        """Disable positioning mode."""
        try:
            self.label.unbind('<ButtonPress-1>')
            self.label.unbind('<B1-Motion>')
            self.label.unbind('<ButtonRelease-1>')
            self.label.unbind('<MouseWheel>')
            self.label.unbind('<Button-4>')
            self.label.unbind('<Button-5>')
        except Exception:
            pass
            
        self._base_img = None
        self._on_snap = None
        self._positioning_enabled = False
        self._apply_clickthrough(True)
        
    def get_geometry(self) -> Tuple[int, int, int, int]:
        """
        Get window geometry.
        
        Returns:
            Tuple of (left, top, width, height)
        """
        return (
            int(self.top.winfo_x()),
            int(self.top.winfo_y()),
            int(self.top.winfo_width()),
            int(self.top.winfo_height()),
        )

    def _on_pointer_enter(self, _event) -> None:
        self._set_hover_hidden(True)

    def _on_pointer_leave(self, _event) -> None:
        self._set_hover_hidden(False)

    def _set_hover_hidden(self, hidden: bool) -> None:
        if self._positioning_enabled:
            hidden = False

        self._hover_active = hidden

        if hidden:
            if self._hover_hidden:
                return

            self._hover_prev_alpha = self._current_alpha
            self._hover_hidden = True

            try:
                self.top.attributes('-alpha', 0.0)
            except Exception:
                pass

            self._current_alpha = 0.0
            self._update_layered_alpha()
            self._apply_clickthrough(True)
        else:
            if not self._hover_hidden:
                return

            try:
                self.top.attributes('-alpha', float(self._hover_prev_alpha))
            except Exception:
                pass

            self._current_alpha = self._hover_prev_alpha
            self._update_layered_alpha()
            self._hover_hidden = False

    def _hover_poll(self) -> None:
        if not sys.platform.startswith('win'):
            return

        inside = False
        if self.visible and not self._positioning_enabled and self._hwnd:
            try:
                cursor = _POINT()
                rect = _RECT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor)):
                    if ctypes.windll.user32.GetWindowRect(self._hwnd, ctypes.byref(rect)):
                        inside = (
                            rect.left <= cursor.x < rect.right and
                            rect.top <= cursor.y < rect.bottom
                        )
            except Exception:
                inside = False

        self._set_hover_hidden(inside)
        self._schedule_hover_poll()

    def is_hovered(self) -> bool:
        return self._hover_active

