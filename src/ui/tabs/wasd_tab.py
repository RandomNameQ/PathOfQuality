"""WASD Movement tab: enable/disable WASD movement emulation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from src.i18n.locale import t
from src.ui.styles import BG_COLOR


class WasdTab:
    """Tab for configuring WASD movement."""

    def __init__(
        self,
        parent: tk.Frame,
        enabled: bool = False,
        top_offset: int = 0,
        bot_offset: int = 0,
        left_offset: int = 0,
        right_offset: int = 0,
        movement_hint: str = "W/A/S/D",
        toggle_hint: str = "~",
    ) -> None:
        self.frame = parent
        self._on_change: Callable[[], None] | None = None
        self._on_open_config: Callable[[], None] | None = None
        self._movement_hint = str(movement_hint or "W/A/S/D")
        self._toggle_hint = str(toggle_hint or "~")

        self._enabled_var = tk.BooleanVar(value=bool(enabled))
        self._top_var = tk.IntVar(value=int(top_offset))
        self._bot_var = tk.IntVar(value=int(bot_offset))
        self._left_var = tk.IntVar(value=int(left_offset))
        self._right_var = tk.IntVar(value=int(right_offset))

        self._create_widgets()

    def _create_widgets(self) -> None:
        container = tk.Frame(self.frame, bg=BG_COLOR)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # Section: WASD Movement
        self._wasd_group = ttk.LabelFrame(
            container, text=t("tab.wasd", "WASD"), padding=(12, 8)
        )
        self._wasd_group.pack(fill="x", pady=(0, 8))

        self._chk_enable = ttk.Checkbutton(
            self._wasd_group,
            text=t("wasd.enable", "Enable WASD movement"),
            variable=self._enabled_var,
            command=self._notify_change,
            style="ToggleGray.TCheckbutton",
        )
        self._chk_enable.pack(anchor="w")

        self._help_lbl = ttk.Label(
            self._wasd_group,
            text=t(
                "desc.wasd",
                "Hold {movement_keys} to move (emulates mouse move + Mouse1 hold).\nPress {toggle_hotkey} to toggle WASD OFF/ON.",
            ),
            style="Prompt.TLabel",
            wraplength=520,
            justify="left",
        )
        self._help_lbl.pack(fill="x", pady=(4, 0))

        self._btn_open_config = ttk.Button(
            self._wasd_group,
            text=t("wasd.open_config", "Open settings config location"),
            command=self._open_config,
            style="Modern.TButton",
        )
        self._btn_open_config.pack(anchor="w", pady=(8, 0))

        # Offsets
        offsets_frame = ttk.Frame(self._wasd_group)
        offsets_frame.pack(fill="x", pady=(8, 0), padx=4)

        ttk.Label(offsets_frame, text=t("wasd.top", "Top Offset:")).grid(
            row=0, column=0, sticky="e", padx=2, pady=2
        )
        top_spin = ttk.Spinbox(
            offsets_frame,
            from_=-5000,
            to=5000,
            width=5,
            textvariable=self._top_var,
            command=self._notify_change,
        )
        top_spin.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        top_spin.bind("<KeyRelease>", lambda e: self._notify_change())

        ttk.Label(offsets_frame, text=t("wasd.bot", "Bottom Offset:")).grid(
            row=1, column=0, sticky="e", padx=2, pady=2
        )
        bot_spin = ttk.Spinbox(
            offsets_frame,
            from_=-5000,
            to=5000,
            width=5,
            textvariable=self._bot_var,
            command=self._notify_change,
        )
        bot_spin.grid(row=1, column=1, sticky="w", padx=2, pady=2)
        bot_spin.bind("<KeyRelease>", lambda e: self._notify_change())

        ttk.Label(offsets_frame, text=t("wasd.left", "Left Offset:")).grid(
            row=0, column=2, sticky="e", padx=2, pady=2
        )
        left_spin = ttk.Spinbox(
            offsets_frame,
            from_=-5000,
            to=5000,
            width=5,
            textvariable=self._left_var,
            command=self._notify_change,
        )
        left_spin.grid(row=0, column=3, sticky="w", padx=2, pady=2)
        left_spin.bind("<KeyRelease>", lambda e: self._notify_change())

        ttk.Label(offsets_frame, text=t("wasd.right", "Right Offset:")).grid(
            row=1, column=2, sticky="e", padx=2, pady=2
        )
        right_spin = ttk.Spinbox(
            offsets_frame,
            from_=-5000,
            to=5000,
            width=5,
            textvariable=self._right_var,
            command=self._notify_change,
        )
        right_spin.grid(row=1, column=3, sticky="w", padx=2, pady=2)
        right_spin.bind("<KeyRelease>", lambda e: self._notify_change())

    def _notify_change(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def set_change_handler(self, callback: Callable[[], None]) -> None:
        self._on_change = callback

    def set_open_config_handler(self, callback: Callable[[], None]) -> None:
        self._on_open_config = callback

    def set_hotkey_hints(self, movement_hint: str, toggle_hint: str) -> None:
        self._movement_hint = str(movement_hint or "W/A/S/D")
        self._toggle_hint = str(toggle_hint or "~")
        self.refresh_texts()

    def _open_config(self) -> None:
        if self._on_open_config:
            try:
                self._on_open_config()
            except Exception:
                pass

    def _build_help_text(self) -> str:
        template = t(
            "desc.wasd",
            "Hold {movement_keys} to move (emulates mouse move + Mouse1 hold).\nPress {toggle_hotkey} to toggle WASD OFF/ON.",
        )
        try:
            return template.format(
                movement_keys=self._movement_hint,
                toggle_hotkey=self._toggle_hint,
            )
        except Exception:
            return f"Hold {self._movement_hint} to move (emulates mouse move + Mouse1 hold).\nPress {self._toggle_hint} to toggle WASD OFF/ON."

    def is_enabled(self) -> bool:
        """Returns True if WASD movement is enabled."""
        return self._enabled_var.get()

    def get_enabled(self) -> bool:
        """Alias for is_enabled to match some existing tab conventions."""
        return self.is_enabled()

    def get_top_offset(self) -> int:
        try:
            return self._top_var.get()
        except Exception:
            return 0

    def get_bot_offset(self) -> int:
        try:
            return self._bot_var.get()
        except Exception:
            return 0

    def get_left_offset(self) -> int:
        try:
            return self._left_var.get()
        except Exception:
            return 0

    def get_right_offset(self) -> int:
        try:
            return self._right_var.get()
        except Exception:
            return 0

    def refresh_texts(self) -> None:
        """Refresh UI texts using i18n."""
        try:
            self._wasd_group.configure(text=t("tab.wasd", "WASD"))
            self._chk_enable.configure(text=t("wasd.enable", "Enable WASD movement"))
            self._help_lbl.configure(text=self._build_help_text())
            self._btn_open_config.configure(
                text=t("wasd.open_config", "Open settings config location")
            )
        except Exception:
            pass

        try:
            self._help_lbl.configure(text=self._build_help_text())
        except Exception:
            pass
