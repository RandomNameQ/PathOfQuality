import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple
from src.i18n.locale import t


def open_localize_dialog(master: tk.Tk, current_texts: dict) -> Optional[Tuple[str, str]]:
    dlg = tk.Toplevel(master)
    dlg.title(t('dialog.localize', 'Localize'))
    dlg.transient(master)
    dlg.grab_set()
    dlg.resizable(False, False)
    try:
        w, h = 600, 400
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        dlg.geometry(f'{w}x{h}+{x}+{y}')
    except Exception:
        pass

    frm = ttk.Frame(dlg, padding=8)
    frm.pack(fill='both', expand=True)

    ttk.Label(frm, text=t('dialog.choose_language', 'Choose Language')).pack(anchor='w')
    lang_var = tk.StringVar(value='en')
    langs = ['en', 'ru']
    cmb = ttk.Combobox(frm, textvariable=lang_var, values=langs, state='readonly')
    cmb.pack(fill='x')

    def on_lang_change(event):
        text_widget.delete('1.0', 'end')
        text_widget.insert('1.0', current_texts.get(lang_var.get(), ''))
    ttk.Label(frm, text='').pack()
    text_widget = tk.Text(frm, height=5, wrap='word')
    text_widget.pack(fill='both', expand=True)
    text_widget.insert('1.0', current_texts.get(lang_var.get(), ''))
    cmb.bind('<<ComboboxSelected>>', on_lang_change)

    btns = ttk.Frame(frm)
    btns.pack(fill='x', pady=(8, 0))

    result: Optional[Tuple[str, str]] = None

    def on_save():
        nonlocal result
        text = text_widget.get('1.0', 'end').strip()
        result = (lang_var.get(), text)
        dlg.destroy()

    def on_cancel():
        dlg.destroy()

    ttk.Button(btns, text=t('dialog.save', 'Save'), command=on_save).pack(side='left')
    ttk.Button(btns, text=t('dialog.cancel', 'Cancel'), command=on_cancel).pack(side='right')

    dlg.wait_window()
    return result