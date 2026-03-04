"""
Monitoring tab UI component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple, Optional
from src.i18n.locale import t, get_lang
from src.ui.styles import BG_COLOR, FG_COLOR
from src.ui import theme
from src.utils.settings import resource_path


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
        self._language_var = tk.StringVar(value=get_lang())
        self._language_callback = None
        self._language_buttons: Dict[str, tk.Button] = {}
        self._language_icons: Dict[str, Optional[tk.PhotoImage]] = {}
        self._scan_dots_phase = 0
        self._scan_dots_after_id: Optional[str] = None

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create monitoring tab widgets."""
        # Header
        header = ttk.Label(self.frame, text="Path Of Quality", style="Title.TLabel")
        header.pack(padx=12, pady=(16, 4))

        # Language switcher (overview)
        lang_frame = tk.Frame(self.frame, bg=BG_COLOR)
        lang_frame.pack(anchor="e", padx=12, pady=(0, 4))

        for code, icon_name in (("ru", "ru.png"), ("en", "en.png")):
            icon: Optional[tk.PhotoImage]
            try:
                icon = tk.PhotoImage(file=resource_path(icon_name))
                max_side = max(icon.width(), icon.height())
                target_side = 20
                scale = max(1, (max_side + target_side - 1) // target_side)
                if scale > 1:
                    icon = icon.subsample(scale, scale)
            except Exception:
                icon = None
            self._language_icons[code] = icon

            if icon is not None:
                btn = tk.Button(
                    lang_frame,
                    image=icon,
                    text="",
                    compound="center",
                    bg=BG_COLOR,
                    activebackground=BG_COLOR,
                    fg=FG_COLOR,
                    relief="flat",
                    bd=1,
                    highlightthickness=1,
                    highlightbackground=theme.BORDER_PRIMARY,
                    highlightcolor=theme.BORDER_PRIMARY,
                    cursor="hand2",
                    command=lambda c=code: self._on_language_click(c),
                )
            else:
                btn = tk.Button(
                    lang_frame,
                    text=code.upper(),
                    compound="center",
                    bg=BG_COLOR,
                    activebackground=BG_COLOR,
                    fg=FG_COLOR,
                    relief="flat",
                    bd=1,
                    highlightthickness=1,
                    highlightbackground=theme.BORDER_PRIMARY,
                    highlightcolor=theme.BORDER_PRIMARY,
                    cursor="hand2",
                    command=lambda c=code: self._on_language_click(c),
                )
            btn.pack(side="left", padx=(4, 0))
            self._language_buttons[code] = btn

        self.set_active_language(get_lang())

        # Status message
        self._status_label = ttk.Label(self.frame, text="", style="Subtitle.TLabel")
        self._status_label.pack(padx=12, pady=(0, 12))

        # Card container for controls
        card = ttk.Frame(self.frame, style="Card.TFrame", padding=(16, 16))
        card.pack(padx=16, pady=8, fill="x")

        # Position library overlay toggle
        self._btn_positioning = ttk.Checkbutton(
            card,
            text=t("monitoring.positioning", "Position library overlay"),
            variable=self._positioning_var,
            style="ToggleGray.TCheckbutton",
        )
        self._btn_positioning.grid(row=0, column=0, sticky="w")

        # Copy area enable toggle with indicator
        self._copy_area_var = tk.BooleanVar(value=False)
        self._copy_area_callback = None
        self._btn_copy_area = ttk.Button(
            card,
            text=t("monitoring.copy_area_disable", "Disable copy area"),
            style="Action.TButton",
            command=self._on_copy_area_click,
        )
        self._btn_copy_area.grid(row=1, column=0, pady=(8, 0), sticky="w")

        self._copy_canvas = tk.Canvas(
            card, width=14, height=14, highlightthickness=0, bg=theme.BG_TERTIARY
        )
        self._copy_canvas.grid(row=1, column=1, padx=(8, 0), pady=(10, 0), sticky="w")
        self._copy_circle = self._copy_canvas.create_oval(
            2, 2, 12, 12, fill=theme.ACCENT_GREEN, outline=theme.BORDER_PRIMARY
        )

        # Scan button and status indicator
        self._btn_scan = ttk.Button(
            card, text=t("monitoring.scan", "Scan"), style="Modern.TButton"
        )
        self._btn_scan.grid(row=2, column=0, pady=(12, 0), sticky="w")
        self._scan_canvas = tk.Canvas(
            card, width=14, height=14, highlightthickness=0, bg=theme.BG_TERTIARY
        )
        self._scan_canvas.grid(row=2, column=1, padx=(8, 0), pady=(14, 0), sticky="w")
        self._scan_circle = self._scan_canvas.create_oval(
            2, 2, 12, 12, fill=theme.ACCENT_RED, outline=theme.BORDER_PRIMARY
        )

        for i in range(2):
            try:
                card.grid_columnconfigure(i, weight=0)
            except Exception:
                pass

        # Icons frame for detected buffs
        self._icons_frame = tk.Frame(self.frame, bg=BG_COLOR)
        self._icons_frame.pack(padx=12, pady=8)

        # Exit button removed as requested

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
                    fg="white",
                    bg="#333333",
                    padx=8,
                    pady=4,
                )
            lbl.pack(side="left")
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
                if lbl.winfo_manager() == "":
                    lbl.pack(side="left")
            else:
                if lbl.winfo_manager() != "":
                    lbl.pack_forget()

        # Update indicators
        try:
            color = "#10b981" if self._scanning_var.get() else "#ef4444"
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

    def set_language_change_command(self, command) -> None:
        """Set language button click callback."""
        self._language_callback = command

    # Exit button removed; no setter

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
        color = "#10b981" if scanning else "#ef4444"
        try:
            self._scan_canvas.itemconfig(self._scan_circle, fill=color)
        except Exception:
            pass

        self.update_copy_area_status()

    def update_copy_area_status(self) -> None:
        """Update copy area indicator color."""
        try:
            copy_color = "#10b981" if self._copy_area_var.get() else "#ef4444"
            self._copy_canvas.itemconfig(self._copy_circle, fill=copy_color)
        except Exception:
            pass

        try:
            if self._copy_area_var.get():
                text = t("monitoring.copy_area_disable", "Disable copy area")
            else:
                text = t("monitoring.copy_area_enable", "Enable copy area")
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
        self._scan_dots_after_id = root.after(
            500, lambda: self._animate_scan_dots(root)
        )

    def refresh_texts(self) -> None:
        """Refresh all translatable texts."""
        try:
            self._btn_positioning.configure(
                text=t("monitoring.positioning", "Position library overlay")
            )
            self._btn_scan.configure(text=t("monitoring.scan", "Scan"))
            self.update_copy_area_status()
            self.set_active_language(get_lang())
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

    def set_active_language(self, lang: str) -> None:
        """Update selected language visual state."""
        selected = lang if lang in ("en", "ru") else "en"
        self._language_var.set(selected)

        for code, btn in self._language_buttons.items():
            is_selected = code == selected
            btn.configure(
                relief="solid" if is_selected else "flat",
                highlightbackground=(
                    theme.ACCENT_GREEN if is_selected else theme.BORDER_PRIMARY
                ),
                highlightcolor=(
                    theme.ACCENT_GREEN if is_selected else theme.BORDER_PRIMARY
                ),
            )

    def _on_language_click(self, lang: str) -> None:
        self.set_active_language(lang)
        callback = self._language_callback
        if callable(callback):
            callback(lang)

    def set_status(self, message: str = "", level: str = "info") -> None:
        """Set status message displayed on the monitoring tab."""
        colors = {
            "info": "#6b7280",
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }
        text = message or ""
        color = colors.get(level, FG_COLOR)
        try:
            self._status_label.configure(text=text, foreground=color)
        except Exception:
            pass
