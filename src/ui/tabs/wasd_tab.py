"""WASD Movement tab: simple enable/disable toggle."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from src.i18n.locale import t
from src.ui.styles import BG_COLOR


class WasdTab:
    """Tab for configuring WASD movement."""

    frame: tk.Frame
    _on_change: Callable[[], None] | None
    _on_open_config: Callable[[], None] | None
    _enabled_var: tk.BooleanVar
    _top_offset: int
    _bot_offset: int
    _left_offset: int
    _right_offset: int
    _movement_hint: str
    _toggle_hint: str
    _wasd_group: ttk.LabelFrame
    _chk_enable: ttk.Checkbutton
    _help_lbl: ttk.Label

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
        self._on_change = None
        self._on_open_config = None

        self._enabled_var = tk.BooleanVar(value=bool(enabled))
        self._top_offset = int(top_offset)
        self._bot_offset = int(bot_offset)
        self._left_offset = int(left_offset)
        self._right_offset = int(right_offset)
        self._movement_hint = str(movement_hint)
        self._toggle_hint = str(toggle_hint)

        self._create_widgets()

    def _create_widgets(self) -> None:
        container = tk.Frame(self.frame, bg=BG_COLOR)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        self._wasd_group = ttk.LabelFrame(
            container, text=t("tab.wasd", "WASD"), padding=(12, 8)
        )
        self._wasd_group.pack(fill="x")

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
            text=self._build_help_text(),
            style="Prompt.TLabel",
            wraplength=520,
            justify="left",
        )
        self._help_lbl.pack(fill="x", pady=(4, 0))

    def _build_help_text(self) -> str:
        raw_text = t(
            "desc.wasd",
            "Use {movement_keys} to move while the feature holds left click. Toggle with {toggle_hotkey}.",
        )
        try:
            return raw_text.format(
                movement_keys=self._movement_hint,
                toggle_hotkey=self._toggle_hint,
            )
        except Exception:
            safe_text = str(raw_text)
            safe_text = safe_text.replace("{movement_keys}", self._movement_hint)
            safe_text = safe_text.replace("{toggle_hotkey}", self._toggle_hint)
            return safe_text

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
        self._movement_hint = str(movement_hint)
        self._toggle_hint = str(toggle_hint)
        self.refresh_texts()

    def _open_config(self) -> None:
        if self._on_open_config:
            try:
                self._on_open_config()
            except Exception:
                pass

    def is_enabled(self) -> bool:
        return bool(self._enabled_var.get())

    def get_enabled(self) -> bool:
        return self.is_enabled()

    def get_top_offset(self) -> int:
        return int(self._top_offset)

    def get_bot_offset(self) -> int:
        return int(self._bot_offset)

    def get_left_offset(self) -> int:
        return int(self._left_offset)

    def get_right_offset(self) -> int:
        return int(self._right_offset)

    def refresh_texts(self) -> None:
        try:
            _ = self._wasd_group.configure(text=t("tab.wasd", "WASD"))
            _ = self._chk_enable.configure(
                text=t("wasd.enable", "Enable WASD movement")
            )
            _ = self._help_lbl.configure(text=self._build_help_text())
        except Exception:
            pass
