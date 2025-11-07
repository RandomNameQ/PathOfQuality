"""
Monitoring tab UI component.
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple, Optional
from src.i18n.locale import t
from src.ui.styles import BG_COLOR, FG_COLOR


class MonitoringTab:
    """Monitoring tab showing scan status and detected buffs."""
    
    def __init__(self, parent: tk.Frame) -> None:
        """
        Initialize monitoring tab.
        
        Args:
            parent: Parent frame
        """
        self.frame = parent
        self._photos: Dict[str, tk.PhotoImage] = {}
        self._labels: Dict[str, tk.Label] = {}
        self._scanning_var = tk.BooleanVar(value=False)
        self._positioning_var = tk.BooleanVar(value=False)
        self._scan_dots_phase = 0
        self._scan_dots_after_id: Optional[str] = None
        
        self._create_widgets()
        
    def _create_widgets(self) -> None:
        """Create monitoring tab widgets."""
        # Header
        header = tk.Label(
            self.frame, 
            text='Buff HUD', 
            font=('Segoe UI', 16, 'bold'), 
            bg=BG_COLOR, 
            fg=FG_COLOR
        )
        header.pack(padx=12, pady=(12, 8))
        
        # Positioning mode toggle
        self._btn_positioning = ttk.Checkbutton(
            self.frame,
            text=t('monitoring.positioning', 'Positioning'),
            variable=self._positioning_var,
            style='Toggle.TCheckbutton',
        )
        self._btn_positioning.pack(padx=12, pady=(0, 12))

        # Copy area enable toggle
        copy_frame = tk.Frame(self.frame, bg=BG_COLOR)
        copy_frame.pack(padx=12, pady=(0, 12))

        self._copy_area_var = tk.BooleanVar(value=False)
        self._copy_area_callback = None
        self._btn_copy_area = ttk.Button(
            copy_frame,
            text=t('monitoring.copy_area_disable', 'Disable copy area'),
            style='Action.TButton',
            command=self._on_copy_area_click,
        )
        self._btn_copy_area.pack(side='left')

        self._copy_canvas = tk.Canvas(
            copy_frame,
            width=16,
            height=16,
            highlightthickness=0,
            bg=BG_COLOR,
        )
        self._copy_canvas.pack(side='left', padx=(8, 0))
        self._copy_circle = self._copy_canvas.create_oval(
            2,
            2,
            14,
            14,
            fill='#10b981',
            outline='#9ca3af',
        )
        
        # Icons frame for detected buffs
        self._icons_frame = tk.Frame(self.frame, bg=BG_COLOR)
        self._icons_frame.pack(padx=12, pady=8)
        
        # Scan button and status indicator
        scan_frame = tk.Frame(self.frame, bg=BG_COLOR)
        scan_frame.pack(padx=12, pady=(8, 8))
        
        self._btn_scan = ttk.Button(
            scan_frame, 
            text=t('monitoring.scan', 'Scan'),
            style='Modern.TButton'
        )
        self._btn_scan.pack(side='left')
        
        # Status circle
        self._scan_canvas = tk.Canvas(
            scan_frame, 
            width=16, 
            height=16, 
            highlightthickness=0, 
            bg=BG_COLOR
        )
        self._scan_canvas.pack(side='left', padx=(8, 0))
        self._scan_circle = self._scan_canvas.create_oval(
            2, 2, 14, 14, 
            fill='#ef4444', 
            outline='#9ca3af'
        )
        
        # Status text
        self._scan_status = None
        self._status = None
        
        # Exit button
        self._btn_exit = ttk.Button(
            self.frame, 
            text=t('button.exit', 'Exit'),
            style='Modern.TButton'
        )
        self._btn_exit.pack(padx=12, pady=(8, 12))

        self.update_copy_area_status()

        # Sync indicator colors
        self.update_copy_area_status()
        
    def load_templates(self, templates: List[Tuple[str, str]]) -> None:
        """
        Load template images for display.
        
        Args:
            templates: List of (name, path) tuples
        """
        for name, path in templates:
            photo = None
            try:
                photo = tk.PhotoImage(file=path)
            except Exception:
                photo = None
                
            if photo is not None:
                self._photos[name] = photo
                lbl = tk.Label(self._icons_frame, image=photo)
            else:
                lbl = tk.Label(
                    self._icons_frame, 
                    text=name, 
                    fg='white', 
                    bg='#333333', 
                    padx=8, 
                    pady=4
                )
            lbl.pack(side='left')
            lbl.pack_forget()
            self._labels[name] = lbl
            
    def update_found(self, found_names: List[str]) -> None:
        """
        Update displayed found buffs.
        
        Args:
            found_names: List of found buff names
        """
        for name, lbl in self._labels.items():
            should_show = name in found_names
            if should_show:
                if lbl.winfo_manager() == '':
                    lbl.pack(side='left')
            else:
                if lbl.winfo_manager() != '':
                    lbl.pack_forget()
                    
        # Update indicators
        try:
            color = '#10b981' if self._scanning_var.get() else '#ef4444'
            self._scan_canvas.itemconfig(self._scan_circle, fill=color)
        except Exception:
            pass

        self.update_copy_area_status()
            
    def set_scan_command(self, command) -> None:
        """Set scan button command callback."""
        self._btn_scan.configure(command=command)
        
    def set_positioning_command(self, command) -> None:
        """Set positioning toggle command callback."""
        self._btn_positioning.configure(command=command)

    def set_copy_area_command(self, command) -> None:
        """Set copy area toggle command callback."""
        self._copy_area_callback = command
        
    def set_exit_command(self, command) -> None:
        """Set exit button command callback."""
        self._btn_exit.configure(command=command)
        
    def get_scanning_var(self) -> tk.BooleanVar:
        """Get scanning state variable."""
        return self._scanning_var
        
    def get_positioning_var(self) -> tk.BooleanVar:
        """Get positioning state variable."""
        return self._positioning_var

    def get_copy_area_var(self) -> tk.BooleanVar:
        """Get copy area state variable."""
        return self._copy_area_var
        
    def update_scan_status(self, scanning: bool) -> None:
        """Update scan status display."""
        color = '#10b981' if scanning else '#ef4444'
        try:
            self._scan_canvas.itemconfig(self._scan_circle, fill=color)
        except Exception:
            pass

        self.update_copy_area_status()

    def update_copy_area_status(self) -> None:
        """Update copy area indicator color."""
        try:
            copy_color = '#10b981' if self._copy_area_var.get() else '#ef4444'
            self._copy_canvas.itemconfig(self._copy_circle, fill=copy_color)
        except Exception:
            pass

        try:
            if self._copy_area_var.get():
                text = t('monitoring.copy_area_disable', 'Disable copy area')
            else:
                text = t('monitoring.copy_area_enable', 'Enable copy area')
            self._btn_copy_area.configure(text=text)
        except Exception:
            pass
            
    def start_scan_animation(self, root: tk.Tk) -> None:
        """Start scanning animation."""
        if self._scan_dots_after_id is not None:
            return
        self._animate_scan_dots(root)
        
    def stop_scan_animation(self, root: tk.Tk) -> None:
        """Stop scanning animation."""
        if self._scan_dots_after_id is not None:
            try:
                root.after_cancel(self._scan_dots_after_id)
            except Exception:
                pass
            self._scan_dots_after_id = None
        self._scan_dots_phase = 0
        
    def _animate_scan_dots(self, root: tk.Tk) -> None:
        """Animate scanning dots."""
        if not self._scanning_var.get():
            return
        # Animation removed - status label no longer exists
        self._scan_dots_phase = (self._scan_dots_phase + 1) % 4
        self._scan_dots_after_id = root.after(500, lambda: self._animate_scan_dots(root))
        
    def refresh_texts(self) -> None:
        """Refresh all translatable texts."""
        try:
            self._btn_positioning.configure(text=t('monitoring.positioning', 'Positioning'))
            self._btn_scan.configure(text=t('monitoring.scan', 'Scan'))
            self._btn_exit.configure(text=t('button.exit', 'Exit'))
            self.update_copy_area_status()
        except Exception:
            pass

    def _on_copy_area_click(self) -> None:
        new_state = not self._copy_area_var.get()
        self._copy_area_var.set(new_state)
        self.update_copy_area_status()
        callback = self._copy_area_callback
        if callable(callback):
            try:
                callback(new_state)
            except TypeError:
                callback()

