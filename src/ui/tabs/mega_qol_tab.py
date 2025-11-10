"""Mega QoL tab: mouse wheel to key sequence configuration."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from src.i18n.locale import t
from src.ui.styles import BG_COLOR, FG_COLOR


class MegaQolTab:
    """Tab for configuring wheel→keys emulation."""

    def __init__(
        self,
        parent: tk.Frame,
        enabled: bool = False,
        sequence: str = "1,2,3,4",
        delay_ms: int = 50,
        double_ctrl_click_enabled: bool = False,
    ) -> None:
        self.frame = parent
        self._on_change: Callable[[], None] | None = None

        self._enabled_var = tk.BooleanVar(value=bool(enabled))
        self._sequence_var = tk.StringVar(value=sequence)
        self._delay_var = tk.IntVar(value=int(delay_ms))
        self._double_ctrl_var = tk.BooleanVar(value=bool(double_ctrl_click_enabled))

        self._create_widgets()

    def _create_widgets(self) -> None:
        container = tk.Frame(self.frame, bg=BG_COLOR)
        container.pack(fill='both', expand=True, padx=12, pady=12)

        # Section: Wheel → Keys
        wheel_group = ttk.LabelFrame(container, text=t('mega_qol.section_wheel', 'Wheel → Keys'), padding=(12, 8))
        wheel_group.pack(fill='x', pady=(0, 8))

        self._chk_enable = ttk.Checkbutton(
            wheel_group,
            text=t('mega_qol.enable', 'Enable wheel down → key sequence'),
            variable=self._enabled_var,
            command=self._notify_change,
            style='Toggle.TCheckbutton',
        )
        self._chk_enable.pack(anchor='w')

        row = ttk.Frame(wheel_group, padding=(0, 8))
        row.pack(fill='x')

        lbl_seq = tk.Label(
            row,
            text=t('mega_qol.sequence', 'Sequence (comma-separated)'),
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=('Segoe UI', 9),
        )
        lbl_seq.pack(side='left', padx=(0, 8))

        ent_seq = ttk.Entry(row, textvariable=self._sequence_var, width=30)
        ent_seq.pack(side='left', fill='x', expand=True)
        ent_seq.bind('<FocusOut>', lambda e: self._notify_change())
        ent_seq.bind('<Return>', lambda e: self._notify_change())

        row2 = ttk.Frame(wheel_group, padding=(0, 8))
        row2.pack(fill='x')

        lbl_delay = tk.Label(
            row2,
            text=t('mega_qol.delay', 'Delay per key (ms)'),
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=('Segoe UI', 9),
        )
        lbl_delay.pack(side='left', padx=(0, 8))

        spn_delay = ttk.Spinbox(row2, from_=0, to=1000, increment=10, textvariable=self._delay_var, width=8)
        spn_delay.pack(side='left')
        spn_delay.bind('<FocusOut>', lambda e: self._notify_change())
        spn_delay.bind('<Return>', lambda e: self._notify_change())

        help_lbl = ttk.Label(
            wheel_group,
            text=t('mega_qol.help', 'On scroll down, sends keys in order. Example: 1,2,3,4 or Q,W,E,R'),
            style='Prompt.TLabel',
            wraplength=520,
            justify='left',
        )
        help_lbl.pack(fill='x', pady=(4, 0))

        ttk.Separator(container, orient='horizontal').pack(fill='x', pady=(8, 8))

        # Section: Double Ctrl click emulation
        ctrl_group = ttk.LabelFrame(container, text=t('mega_qol.section_ctrl', 'Double Ctrl Click'), padding=(12, 8))
        ctrl_group.pack(fill='x')

        self._chk_double_ctrl = ttk.Checkbutton(
            ctrl_group,
            text=t('settings.double_ctrl_click', 'Double Ctrl click emulation'),
            variable=self._double_ctrl_var,
            command=self._notify_change,
            style='Toggle.TCheckbutton',
        )
        self._chk_double_ctrl.pack(anchor='w')

        ctrl_help = ttk.Label(
            ctrl_group,
            text=t('mega_qol.ctrl_help', 'Press Ctrl twice quickly and keep holding to emulate left-click until released.'),
            style='Prompt.TLabel',
            wraplength=520,
            justify='left',
        )
        ctrl_help.pack(fill='x', pady=(4, 0))

    def _notify_change(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def set_change_handler(self, callback: Callable[[], None]) -> None:
        self._on_change = callback

    def get_enabled_var(self) -> tk.BooleanVar:
        return self._enabled_var

    def get_sequence(self) -> str:
        return self._sequence_var.get().strip()

    def get_delay_ms(self) -> int:
        try:
            return int(self._delay_var.get())
        except Exception:
            return 50

    def get_double_ctrl_var(self) -> tk.BooleanVar:
        return self._double_ctrl_var

    def refresh_texts(self) -> None:
        try:
            self._chk_enable.configure(text=t('mega_qol.enable', 'Enable wheel down → key sequence'))
            self._chk_double_ctrl.configure(text=t('settings.double_ctrl_click', 'Double Ctrl click emulation'))
        except Exception:
            pass
