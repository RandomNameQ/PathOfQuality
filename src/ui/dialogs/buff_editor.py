import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict
from src.i18n.locale import t, get_lang


class BuffEditorDialog:
    def __init__(self, master: tk.Tk, entry_type: str = 'buff') -> None:
        self._master = master
        self._type = 'buff' if entry_type == 'buff' else 'debuff'
        self._name_texts: Dict[str, str] = {}
        self._desc_texts: Dict[str, str] = {}

        self._result: Optional[dict] = None

    def show(self) -> Optional[dict]:
        dlg = tk.Toplevel(self._master)
        dlg.title(t('tab.buffs', 'Buffs') if self._type == 'buff' else t('tab.debuffs', 'Debuffs'))
        dlg.transient(self._master)
        dlg.grab_set()
        dlg.resizable(False, False)
        try:
            w, h = 800, 600
            sw = dlg.winfo_screenwidth()
            sh = dlg.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            dlg.geometry(f'{w}x{h}+{x}+{y}')
        except Exception:
            pass

        frm = ttk.Frame(dlg, padding=8)
        frm.pack(fill='both', expand=True)

        # Name + localization
        name_row = ttk.Frame(frm)
        name_row.pack(fill='x', pady=(0, 4))
        ttk.Label(name_row, text=t('buffs.name', 'Name')).pack(side='left')
        name_var = tk.StringVar(value='')
        name_entry = ttk.Entry(name_row, textvariable=name_var)
        name_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        loc_btn1 = ttk.Button(name_row, text=t('dialog.localize', 'Localize'), command=lambda: self._open_loc(self._name_texts, name_var))
        loc_btn1.pack(side='left')

        # Image path
        img_row = ttk.Frame(frm)
        img_row.pack(fill='x', pady=(0, 4))
        ttk.Label(img_row, text=t('buffs.image', 'Image')).pack(side='left')
        img_var = tk.StringVar(value='')
        img_entry = ttk.Entry(img_row, textvariable=img_var)
        img_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        def choose_img():
            path = filedialog.askopenfilename(parent=dlg, filetypes=[('Images', '*.png;*.jpg;*.jpeg')])
            if path:
                img_var.set(path)
        ttk.Button(img_row, text='...', width=3, command=choose_img).pack(side='left')

        # Description (multiline) + localization
        desc_row = ttk.Frame(frm)
        desc_row.pack(fill='both', expand=True, pady=(0, 4))
        ttk.Label(desc_row, text=t('buffs.description', 'Description')).pack(anchor='w')
        text_frame = ttk.Frame(desc_row)
        text_frame.pack(fill='both', expand=True)
        desc_text = tk.Text(text_frame, height=5, wrap='word')
        desc_text.pack(side='left', fill='both', expand=True, padx=(0, 6))
        scroll = ttk.Scrollbar(text_frame, orient='vertical', command=desc_text.yview)
        scroll.pack(side='right', fill='y')
        desc_text.configure(yscrollcommand=scroll.set)
        loc_btn2 = ttk.Button(desc_row, text=t('dialog.localize', 'Localize'), command=lambda: self._open_loc_text(self._desc_texts, desc_text))
        loc_btn2.pack(anchor='e', pady=(6, 0))

        # Sounds
        sound_on_row = ttk.Frame(frm)
        sound_on_row.pack(fill='x', pady=(0, 4))
        ttk.Label(sound_on_row, text=t('buffs.sound_on', 'Appear Sound')).pack(side='left')
        sound_on_var = tk.StringVar(value='')
        ttk.Entry(sound_on_row, textvariable=sound_on_var).pack(side='left', fill='x', expand=True, padx=(6, 6))
        def choose_sound_on():
            path = filedialog.askopenfilename(parent=dlg, filetypes=[('Audio', '*.wav;*.mp3;*.ogg')])
            if path:
                sound_on_var.set(path)
        ttk.Button(sound_on_row, text='...', width=3, command=choose_sound_on).pack(side='left')

        sound_off_row = ttk.Frame(frm)
        sound_off_row.pack(fill='x', pady=(0, 4))
        ttk.Label(sound_off_row, text=t('buffs.sound_off', 'Disappear Sound')).pack(side='left')
        sound_off_var = tk.StringVar(value='')
        ttk.Entry(sound_off_row, textvariable=sound_off_var).pack(side='left', fill='x', expand=True, padx=(6, 6))
        def choose_sound_off():
            path = filedialog.askopenfilename(parent=dlg, filetypes=[('Audio', '*.wav;*.mp3;*.ogg')])
            if path:
                sound_off_var.set(path)
        ttk.Button(sound_off_row, text='...', width=3, command=choose_sound_off).pack(side='left')

        # Location (left, top)
        loc_row = ttk.Frame(frm)
        loc_row.pack(fill='x', pady=(0, 4))
        ttk.Label(loc_row, text=t('buffs.location', 'Location')).pack(side='left')
        left_var = tk.IntVar(value=0)
        top_var = tk.IntVar(value=0)
        ttk.Label(loc_row, text='Left').pack(side='left', padx=(6, 2))
        ttk.Entry(loc_row, textvariable=left_var, width=8).pack(side='left')
        ttk.Label(loc_row, text='Top').pack(side='left', padx=(6, 2))
        ttk.Entry(loc_row, textvariable=top_var, width=8).pack(side='left')

        # Size (width, height)
        size_row = ttk.Frame(frm)
        size_row.pack(fill='x', pady=(0, 4))
        ttk.Label(size_row, text=t('buffs.size', 'Size')).pack(side='left')
        width_var = tk.IntVar(value=0)
        height_var = tk.IntVar(value=0)
        ttk.Label(size_row, text='W').pack(side='left', padx=(6, 2))
        ttk.Entry(size_row, textvariable=width_var, width=8).pack(side='left')
        ttk.Label(size_row, text='H').pack(side='left', padx=(6, 2))
        ttk.Entry(size_row, textvariable=height_var, width=8).pack(side='left')

        # Transparency
        tr_row = ttk.Frame(frm)
        tr_row.pack(fill='x', pady=(0, 8))
        ttk.Label(tr_row, text=t('buffs.transparency', 'Transparency')).pack(side='left')
        tr_var = tk.DoubleVar(value=1.0)
        ttk.Scale(tr_row, variable=tr_var, from_=0.0, to=1.0, orient='horizontal').pack(side='left', fill='x', expand=True, padx=(6, 6))

        # Buttons
        btns = ttk.Frame(frm)
        btns.pack(fill='x')
        def on_create():
            # validation
            curr_lang = get_lang()
            name_text = name_var.get().strip()
            if name_text:
                self._name_texts[curr_lang] = name_text
            img_path = img_var.get().strip()
            if not self._name_texts.get('en') and not self._name_texts.get(curr_lang):
                messagebox.showerror(title='Error', message=t('error.name_required', 'Name is required'))
                return
            if not img_path:
                messagebox.showerror(title='Error', message=t('error.image_required', 'Image is required'))
                return
            # collect description from textarea
            desc_val = desc_text.get('1.0', 'end').strip()
            if desc_val:
                self._desc_texts[curr_lang] = desc_val
            self._result = {
                'type': self._type,
                'name': dict(self._name_texts),
                'image_path': img_path,
                'description': dict(self._desc_texts),
                'sound_on': sound_on_var.get().strip() or None,
                'sound_off': sound_off_var.get().strip() or None,
                'left': int(left_var.get()),
                'top': int(top_var.get()),
                'width': int(width_var.get()),
                'height': int(height_var.get()),
                'transparency': float(tr_var.get()),
            }
            dlg.destroy()

        def on_cancel():
            self._result = None
            dlg.destroy()

        ttk.Button(btns, text=t('dialog.create', 'Create'), command=on_create).pack(side='left')
        ttk.Button(btns, text=t('dialog.cancel', 'Cancel'), command=on_cancel).pack(side='right')

        dlg.wait_window()
        return self._result

    def _open_loc(self, store: Dict[str, str], var: tk.StringVar):
        from src.ui.dialogs.localize_dialog import open_localize_dialog
        res = open_localize_dialog(self._master, store)
        if res is None:
            return
        lang, text = res
        store[lang] = text
        # если изменяем текущий язык — обновим поле
        if lang == get_lang():
            var.set(text)

    def _open_loc_text(self, store: Dict[str, str], widget: tk.Text):
        from src.ui.dialogs.localize_dialog import open_localize_dialog
        res = open_localize_dialog(self._master, store)
        if res is None:
            return
        lang, text = res
        store[lang] = text
        if lang == get_lang():
            widget.delete('1.0', 'end')
            widget.insert('1.0', text)