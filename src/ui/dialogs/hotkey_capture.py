"""Dialog for selecting a hotkey from predefined keys."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.quickcraft.hotkeys import normalize_hotkey_name, format_hotkey_display


AVAILABLE_KEYS = {
    'Function keys': ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'],
    'Numbers': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
    'Letters': list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    'Navigation': ['UP', 'DOWN', 'LEFT', 'RIGHT', 'HOME', 'END', 'PAGE_UP', 'PAGE_DOWN', 'INSERT', 'DELETE'],
    'Controls': ['SPACE', 'TAB', 'ENTER', 'ESC', 'SHIFT', 'CTRL', 'ALT', 'CAPS_LOCK'],
}


class HotkeyCaptureDialog:
    """Modal dialog prompting user to select a hotkey button."""

    def __init__(self, master: tk.Tk) -> None:
        self._master = master
        self._result: Optional[str] = None
        self._dialog: Optional[tk.Toplevel] = None

    def show(self) -> Optional[str]:
        dlg = tk.Toplevel(self._master)
        self._dialog = dlg
        dlg.title('Select Hotkey')
        dlg.transient(self._master)
        dlg.grab_set()
        dlg.resizable(False, False)
        try:
            dlg.attributes('-topmost', True)
        except Exception:
            pass

        try:
            w, h = 440, 460
            sw = dlg.winfo_screenwidth()
            sh = dlg.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            dlg.geometry(f'{w}x{h}+{x}+{y}')
        except Exception:
            pass

        frame = ttk.Frame(dlg, padding=16)
        frame.pack(fill='both', expand=True)

        label = ttk.Label(
            frame,
            text='Click a button to assign a hotkey.',
            font=('Segoe UI', 10),
        )
        label.pack(pady=(0, 12))

        self._display_var = tk.StringVar(value='Select a key below.')
        ttk.Label(
            frame,
            textvariable=self._display_var,
            font=('Segoe UI', 11, 'bold'),
            justify='center',
        ).pack(pady=(0, 12))

        canvas = tk.Canvas(frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')),
        )

        canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        for group_name, keys in AVAILABLE_KEYS.items():
            group = ttk.LabelFrame(inner, text=group_name, padding=(12, 8))
            group.pack(fill='x', expand=True, pady=(0, 8))
            for idx, key in enumerate(keys):
                btn = ttk.Button(
                    group,
                    text=key,
                    width=6,
                    command=lambda value=key: self._choose(value),
                    style='Action.TButton',
                )
                btn.grid(row=idx // 6, column=idx % 6, padx=4, pady=4, sticky='nsew')
            for col in range(6):
                group.columnconfigure(col, weight=1)

        ttk.Label(
            frame,
            text='Press Esc to cancel.',
            font=('Segoe UI', 9),
        ).pack(pady=(8, 0))

        cancel_btn = ttk.Button(
            frame,
            text='Cancel',
            command=self._on_cancel,
            style='Action.TButton',
            width=12,
        )
        cancel_btn.pack(pady=(8, 0))

        dlg.bind('<Escape>', self._on_cancel)
        dlg.protocol('WM_DELETE_WINDOW', self._on_cancel)

        dlg.wait_window()
        return self._result

    def _choose(self, token: str) -> None:
        normalized = normalize_hotkey_name(token)
        if not normalized:
            return
        self._display_var.set(f'Selected: {format_hotkey_display(normalized)}')
        self._finish(normalized)

    def _finish(self, token: str) -> None:
        self._result = token
        if self._dialog is not None:
            self._dialog.destroy()

    def _on_cancel(self, _event=None) -> None:
        self._result = None
        if self._dialog is not None:
            self._dialog.destroy()
