"""
Individual mirror window for displaying icon.
"""
import tkinter as tk
from typing import Optional, Callable, Tuple
from PIL import Image, ImageTk


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
        
        # For positioning mode
        self._base_img: Optional[Image.Image] = None
        self._dragging = False
        self._start_x = 0
        self._start_y = 0
        self._win_x = 0
        self._win_y = 0
        self._on_snap: Optional[Callable[[int, int, int, int], Tuple[int, int]]] = None
        
    def show(self, left: int, top: int, width: int, height: int, alpha: float = 1.0) -> None:
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
            self.top.attributes('-topmost', True)
        except Exception:
            pass
            
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
            
    def close(self) -> None:
        """Close and destroy window."""
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
        
        try:
            scaled = base_img.resize(
                (max(8, int(width)), max(8, int(height))), 
                Image.LANCZOS
            )
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
        except Exception:
            pass
            
    def disable_positioning(self) -> None:
        """Disable positioning mode."""
        try:
            self.label.unbind('<ButtonPress-1>')
            self.label.unbind('<B1-Motion>')
            self.label.unbind('<ButtonRelease-1>')
        except Exception:
            pass
            
        self._base_img = None
        self._on_snap = None
        
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

