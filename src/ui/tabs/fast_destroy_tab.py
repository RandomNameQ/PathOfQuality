"""Fast destroy tab configuration."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from src.i18n.locale import t
from src.ui.styles import BG_COLOR


class FastDestroyTab:
    """Tab for configuring fast destroy mode."""

    def __init__(
        self,
        parent: tk.Frame,
        enabled: bool = False,
        warning_overlay: bool = True,
        activation_hotkey_hint: str = "Alt+Alt",
        deactivation_hotkey_hint: str = "Alt",
    ) -> None:
        self.frame = parent
        self._on_change: Callable[[], None] | None = None
        self._activation_hotkey_hint = str(activation_hotkey_hint)
        self._deactivation_hotkey_hint = str(deactivation_hotkey_hint)

        self._enabled_var = tk.BooleanVar(value=bool(enabled))
        self._warning_overlay_var = tk.BooleanVar(value=bool(warning_overlay))

        self._create_widgets()

    def _create_widgets(self) -> None:
        container = tk.Frame(self.frame, bg=BG_COLOR)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        self._group = ttk.LabelFrame(
            container,
            text=t("tab.fast_destroy", "Fast destroy"),
            padding=(12, 8),
        )
        self._group.pack(fill="x")

        self._chk_enabled = ttk.Checkbutton(
            self._group,
            text=t("fast_destroy.enable_fast_delete", "Enable fast delete"),
            variable=self._enabled_var,
            command=self._notify_change,
            style="ToggleGray.TCheckbutton",
        )
        self._chk_enabled.pack(anchor="w")

        self._chk_warning = ttk.Checkbutton(
            self._group,
            text=t("fast_destroy.enable_warning_overlay", "Enable warning overlay"),
            variable=self._warning_overlay_var,
            command=self._notify_change,
            style="ToggleGray.TCheckbutton",
        )
        self._chk_warning.pack(anchor="w", pady=(6, 0))

        self._help_lbl = ttk.Label(
            self._group,
            text=self._build_hotkeys_text(),
            style="Prompt.TLabel",
            wraplength=520,
            justify="left",
        )
        self._help_lbl.pack(fill="x", pady=(8, 0))

    def _build_hotkeys_text(self) -> str:
        raw_text = t(
            "desc.fast_destroy_hotkeys",
            "Activation: {activation_hotkey}. Deactivation: {deactivation_hotkey}.",
        )
        try:
            return raw_text.format(
                activation_hotkey=self._activation_hotkey_hint,
                deactivation_hotkey=self._deactivation_hotkey_hint,
            )
        except Exception:
            safe_text = str(raw_text)
            safe_text = safe_text.replace(
                "{activation_hotkey}", self._activation_hotkey_hint
            )
            safe_text = safe_text.replace(
                "{deactivation_hotkey}", self._deactivation_hotkey_hint
            )
            return safe_text

    def _notify_change(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def set_change_handler(self, callback: Callable[[], None]) -> None:
        self._on_change = callback

    def get_enabled(self) -> bool:
        return bool(self._enabled_var.get())

    def get_warning_overlay_enabled(self) -> bool:
        return bool(self._warning_overlay_var.get())

    def refresh_texts(self) -> None:
        try:
            self._group.configure(text=t("tab.fast_destroy", "Fast destroy"))
            self._chk_enabled.configure(
                text=t("fast_destroy.enable_fast_delete", "Enable fast delete")
            )
            self._chk_warning.configure(
                text=t(
                    "fast_destroy.enable_warning_overlay",
                    "Enable warning overlay",
                )
            )
            self._help_lbl.configure(text=self._build_hotkeys_text())
        except Exception:
            pass
