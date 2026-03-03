"""Overlay tab UI component."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.i18n.locale import t
from src.quickcraft.hotkeys import format_hotkey_display, normalize_hotkey_name
from src.ui import theme
from src.ui.styles import BG_COLOR, FG_COLOR


class OverlayTab:
    """Controls for opening and configuring tab overlay."""

    def __init__(
        self,
        parent: tk.Frame,
        overlay_hotkey: str = "SHIFT",
        use_map_layout_overlay: bool = True,
    ) -> None:
        self.frame = parent
        self._overlay_hotkey_var = tk.StringVar(value="")
        self._overlay_hotkey_display_var = tk.StringVar(value="")
        self._use_map_layout_overlay_var = tk.BooleanVar(
            value=bool(use_map_layout_overlay)
        )
        self._create_widgets()
        self.set_overlay_hotkey(overlay_hotkey)

    def _create_widgets(self) -> None:
        main_container = tk.Frame(self.frame, bg=BG_COLOR)
        main_container.pack(fill="both", expand=True, padx=12, pady=12)

        self._desc_label = ttk.Label(
            main_container,
            text=t(
                "overlay.desc",
                "Open floating overlay window and configure opening hotkey.",
            ),
            style="Prompt.TLabel",
        )
        self._desc_label.pack(anchor="w", pady=(0, 10))

        self._chk_use_map_layout_overlay = tk.Checkbutton(
            main_container,
            text=t("overlay.use_map_layout_overlay", "Use map layout overlay"),
            variable=self._use_map_layout_overlay_var,
            onvalue=True,
            offvalue=False,
            bg=BG_COLOR,
            fg=FG_COLOR,
            activebackground=BG_COLOR,
            activeforeground=FG_COLOR,
            selectcolor=theme.BG_SECONDARY,
            highlightthickness=0,
            bd=0,
            font=theme.FONT_BODY,
        )
        self._chk_use_map_layout_overlay.pack(anchor="w", pady=(0, 12))

        self._btn_open_overlay = ttk.Button(
            main_container,
            text=t("settings.open_overlay", "Open Overlay"),
            style="Modern.TButton",
        )
        self._btn_open_overlay.pack(anchor="w", pady=(0, 12))

        hotkey_row = tk.Frame(main_container, bg=BG_COLOR)
        hotkey_row.pack(anchor="w", fill="x", pady=(0, 8))

        self._lbl_overlay_hotkey = tk.Label(
            hotkey_row,
            text=t("settings.overlay_hotkey", "Overlay hotkey:"),
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=theme.FONT_BODY,
        )
        self._lbl_overlay_hotkey.pack(side="left")

        self._lbl_overlay_hotkey_value = tk.Label(
            hotkey_row,
            textvariable=self._overlay_hotkey_display_var,
            bg=BG_COLOR,
            fg=theme.ACCENT_GOLD,
            font=theme.FONT_HEADER,
            padx=8,
        )
        self._lbl_overlay_hotkey_value.pack(side="left")

        self._btn_set_overlay_hotkey = ttk.Button(
            hotkey_row,
            text=t("settings.set_hotkey", "Set hotkey"),
            style="Action.TButton",
        )
        self._btn_set_overlay_hotkey.pack(side="left", padx=(8, 0))

        self._btn_clear_overlay_hotkey = ttk.Button(
            hotkey_row,
            text=t("settings.clear_hotkey", "Clear hotkey"),
            style="Action.TButton",
        )
        self._btn_clear_overlay_hotkey.pack(side="left", padx=(8, 0))

    def set_open_overlay_command(self, command) -> None:
        self._btn_open_overlay.configure(command=command)

    def set_map_layout_overlay_command(self, command) -> None:
        self._chk_use_map_layout_overlay.configure(command=command)

    def set_set_overlay_hotkey_command(self, command) -> None:
        self._btn_set_overlay_hotkey.configure(command=command)

    def set_clear_overlay_hotkey_command(self, command) -> None:
        self._btn_clear_overlay_hotkey.configure(command=command)

    def get_overlay_hotkey(self) -> str:
        return str(self._overlay_hotkey_var.get()).strip()

    def set_overlay_hotkey(self, token: str) -> None:
        normalized = normalize_hotkey_name(str(token or ""))
        self._overlay_hotkey_var.set(normalized)
        self._overlay_hotkey_display_var.set(
            format_hotkey_display(normalized) if normalized else "-"
        )

    def get_map_layout_overlay_enabled(self) -> bool:
        return bool(self._use_map_layout_overlay_var.get())

    def set_map_layout_overlay_enabled(self, enabled: bool) -> None:
        self._use_map_layout_overlay_var.set(bool(enabled))

    def refresh_texts(self) -> None:
        self._desc_label.configure(
            text=t(
                "overlay.desc",
                "Open floating overlay window and configure opening hotkey.",
            )
        )
        self._chk_use_map_layout_overlay.configure(
            text=t("overlay.use_map_layout_overlay", "Use map layout overlay")
        )
        self._btn_open_overlay.configure(
            text=t("settings.open_overlay", "Open Overlay")
        )
        self._lbl_overlay_hotkey.configure(
            text=t("settings.overlay_hotkey", "Overlay hotkey:")
        )
        self._btn_set_overlay_hotkey.configure(
            text=t("settings.set_hotkey", "Set hotkey")
        )
        self._btn_clear_overlay_hotkey.configure(
            text=t("settings.clear_hotkey", "Clear hotkey")
        )
