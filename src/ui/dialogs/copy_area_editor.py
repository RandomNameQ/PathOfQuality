"""Dialog for creating or editing copy area entries."""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Optional

from src.buffs.library import load_library, copy_image_to_library
from src.i18n.locale import t, get_lang
from src.ui.roi_selector import select_roi

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


class CopyAreaEditorDialog:
    def __init__(self, master: tk.Tk, initial: Optional[dict] = None) -> None:
        self._master = master
        self._initial = initial or {}
        self._name_texts: Dict[str, str] = {}
        if isinstance(self._initial.get('name'), dict):
            self._name_texts.update(self._initial.get('name', {}))

        refs = self._initial.get('references', {}) or {}
        self._initial_buffs = set(refs.get('buffs', []))
        self._initial_debuffs = set(refs.get('debuffs', []))

        self._initial_capture = self._initial.get('capture', {}) or {}
        self._initial_topmost = bool(self._initial.get('topmost', True))
        self._initial_transparency = float(self._initial.get('transparency', 1.0))

        self._result: Optional[dict] = None
        self._img_preview_photo = None
        self._buff_ids: List[str] = []
        self._debuff_ids: List[str] = []

    def show(self) -> Optional[dict]:
        dlg = tk.Toplevel(self._master)
        dlg.title(t('tab.copy_area', 'Copy Areas'))
        dlg.transient(self._master)
        dlg.grab_set()
        dlg.resizable(False, False)

        self._buff_ids.clear()
        self._debuff_ids.clear()

        try:
            w, h = 720, 720
            sw = dlg.winfo_screenwidth()
            sh = dlg.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            dlg.geometry(f'{w}x{h}+{x}+{y}')
        except Exception:
            pass

        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill='both', expand=True)

        # Name with localization
        name_row = ttk.Frame(frm)
        name_row.pack(fill='x', pady=(0, 8))
        ttk.Label(name_row, text=t('copy_area.name', 'Name')).pack(side='left')

        current_lang = get_lang()
        init_name = self._name_texts.get(current_lang) or self._name_texts.get('en', '')
        name_var = tk.StringVar(value=init_name)
        name_entry = ttk.Entry(name_row, textvariable=name_var)
        name_entry.pack(side='left', fill='x', expand=True, padx=(8, 8))

        loc_btn = ttk.Button(
            name_row,
            text=t('dialog.localize', 'Localize'),
            command=lambda: self._open_localize(self._name_texts, name_var),
        )
        loc_btn.pack(side='left')

        # Image path + picker
        img_row = ttk.Frame(frm)
        img_row.pack(fill='x', pady=(0, 8))
        ttk.Label(img_row, text=t('copy_area.image', 'Image')).pack(side='left')
        img_var = tk.StringVar(value=self._initial.get('image_path', ''))
        img_entry = ttk.Entry(img_row, textvariable=img_var)
        img_entry.pack(side='left', fill='x', expand=True, padx=(8, 8))

        def choose_image() -> None:
            path = filedialog.askopenfilename(
                parent=dlg,
                filetypes=[('Images', '*.png;*.jpg;*.jpeg')],
            )
            if path:
                # Copy image to library
                copied_path = copy_image_to_library(path)
                if copied_path:
                    img_var.set(copied_path)
                else:
                    # Fallback to original path if copy failed
                    img_var.set(path)

        ttk.Button(img_row, text='...', width=3, command=choose_image).pack(side='left')

        # Preview
        preview_frame = ttk.LabelFrame(frm, text=t('copy_area.preview', 'Preview'))
        preview_frame.pack(fill='x', pady=(0, 12))
        preview_label = tk.Label(preview_frame, relief='sunken')
        preview_label.pack(anchor='w', padx=8, pady=8)

        def update_preview(path: str) -> None:
            try:
                if not path or not os.path.isfile(path):
                    preview_label.configure(image='', text='')
                    self._img_preview_photo = None
                    return
                if Image is None or ImageTk is None:
                    photo = tk.PhotoImage(file=path)
                    self._img_preview_photo = photo
                    preview_label.configure(image=photo)
                    return
                img = Image.open(path).convert('RGBA')
                img.thumbnail((160, 160), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._img_preview_photo = photo
                preview_label.configure(image=photo)
            except Exception:
                preview_label.configure(image='', text='')
                self._img_preview_photo = None

        img_var.trace_add('write', lambda *_: update_preview(img_var.get().strip()))
        update_preview(img_var.get().strip())

        # Capture area (source)
        capture_frame = ttk.LabelFrame(frm, text=t('copy_area.capture', 'Capture area'))
        capture_frame.pack(fill='x', pady=(0, 12))

        capture_row = ttk.Frame(capture_frame)
        capture_row.pack(fill='x', pady=(4, 4))

        capture_left_var = tk.IntVar(value=int(self._initial_capture.get('left', 0)))
        capture_top_var = tk.IntVar(value=int(self._initial_capture.get('top', 0)))
        capture_width_var = tk.IntVar(value=int(self._initial_capture.get('width', 0)))
        capture_height_var = tk.IntVar(value=int(self._initial_capture.get('height', 0)))

        btn_select_capture = tk.Button(
            capture_row,
            text=t('copy_area.select_area', 'Select area'),
            command=lambda: select_capture_area(),
            bg='#10b981',
            fg='#ffffff',
            activebackground='#059669',
            activeforeground='#ffffff',
            relief='flat',
            borderwidth=0,
            font=('Segoe UI', 9, 'bold'),
            padx=14,
            pady=4,
            cursor='hand2',
        )
        btn_select_capture.pack(side='left', padx=(0, 12))

        ttk.Label(capture_row, text='Left').pack(side='left')
        ttk.Entry(capture_row, textvariable=capture_left_var, width=8).pack(side='left', padx=(4, 12))
        ttk.Label(capture_row, text='Top').pack(side='left')
        ttk.Entry(capture_row, textvariable=capture_top_var, width=8).pack(side='left', padx=(4, 12))
        ttk.Label(capture_row, text='W').pack(side='left')
        ttk.Entry(capture_row, textvariable=capture_width_var, width=8).pack(side='left', padx=(4, 12))
        ttk.Label(capture_row, text='H').pack(side='left')
        ttk.Entry(capture_row, textvariable=capture_height_var, width=8).pack(side='left', padx=(4, 0))

        def select_capture_area() -> None:
            selected = select_roi(self._master)
            if selected is None:
                return
            left_sel, top_sel, width_sel, height_sel = selected
            capture_left_var.set(int(left_sel))
            capture_top_var.set(int(top_sel))
            capture_width_var.set(int(width_sel))
            capture_height_var.set(int(height_sel))
            if width_var.get() <= 0:
                width_var.set(int(width_sel))
            if height_var.get() <= 0:
                height_var.set(int(height_sel))

        # References
        refs_frame = ttk.LabelFrame(frm, text=t('copy_area.targets', 'Linked buffs / debuffs'))
        refs_frame.pack(fill='both', expand=True, pady=(0, 12))

        lists_container = ttk.Frame(refs_frame)
        lists_container.pack(fill='both', expand=True)

        data = load_library()

        buff_col = ttk.Frame(lists_container)
        buff_col.pack(side='left', fill='both', expand=True, padx=(0, 8))
        ttk.Label(buff_col, text=t('tab.buffs', 'Buffs')).pack(anchor='w')
        buff_list = tk.Listbox(buff_col, selectmode='multiple', exportselection=False, height=10)
        buff_list.pack(fill='both', expand=True, pady=(4, 0))

        for idx, item in enumerate(data.get('buffs', [])):
            iid = item.get('id')
            if not iid:
                continue
            label = self._format_name(item)
            self._buff_ids.append(iid)
            buff_list.insert('end', label)
            if iid in self._initial_buffs:
                buff_list.selection_set(idx)

        debuff_col = ttk.Frame(lists_container)
        debuff_col.pack(side='left', fill='both', expand=True, padx=(8, 0))
        ttk.Label(debuff_col, text=t('tab.debuffs', 'Debuffs')).pack(anchor='w')
        debuff_list = tk.Listbox(debuff_col, selectmode='multiple', exportselection=False, height=10)
        debuff_list.pack(fill='both', expand=True, pady=(4, 0))

        for idx, item in enumerate(data.get('debuffs', [])):
            iid = item.get('id')
            if not iid:
                continue
            label = self._format_name(item)
            self._debuff_ids.append(iid)
            debuff_list.insert('end', label)
            if iid in self._initial_debuffs:
                debuff_list.selection_set(idx)

        # Position and size
        coords_frame = ttk.Frame(frm)
        coords_frame.pack(fill='x', pady=(0, 8))

        ttk.Label(coords_frame, text=t('copy_area.position', 'Position')).pack(side='left')
        left_var = tk.IntVar(value=int(self._initial.get('position', {}).get('left', 0)))
        top_var = tk.IntVar(value=int(self._initial.get('position', {}).get('top', 0)))
        ttk.Label(coords_frame, text='Left').pack(side='left', padx=(8, 2))
        ttk.Entry(coords_frame, textvariable=left_var, width=8).pack(side='left')
        ttk.Label(coords_frame, text='Top').pack(side='left', padx=(8, 2))
        ttk.Entry(coords_frame, textvariable=top_var, width=8).pack(side='left')

        size_frame = ttk.Frame(frm)
        size_frame.pack(fill='x', pady=(0, 12))
        ttk.Label(size_frame, text=t('copy_area.size', 'Size')).pack(side='left')
        width_var = tk.IntVar(value=int(self._initial.get('size', {}).get('width', 64)))
        height_var = tk.IntVar(value=int(self._initial.get('size', {}).get('height', 64)))
        ttk.Label(size_frame, text='W').pack(side='left', padx=(8, 2))
        ttk.Entry(size_frame, textvariable=width_var, width=8).pack(side='left')
        ttk.Label(size_frame, text='H').pack(side='left', padx=(8, 2))
        ttk.Entry(size_frame, textvariable=height_var, width=8).pack(side='left')

        transparency_frame = ttk.Frame(frm)
        transparency_frame.pack(fill='x', pady=(0, 12))
        transparency_frame.columnconfigure(1, weight=1)

        ttk.Label(transparency_frame, text=t('copy_area.transparency', 'Transparency')).grid(row=0, column=0, sticky='w')
        transparency_var = tk.DoubleVar(value=self._initial_transparency)
        tr_scale = ttk.Scale(transparency_frame, variable=transparency_var, from_=0.0, to=1.0, orient='horizontal')
        tr_scale.grid(row=0, column=1, sticky='ew', padx=(8, 8))
        tr_value_var = tk.StringVar(value=f"{self._initial_transparency:.2f}")

        def _update_tr_label(*_args) -> None:
            try:
                value = max(0.0, min(1.0, float(transparency_var.get())))
            except Exception:
                value = 1.0
            tr_value_var.set(f"{value:.2f}")

        tr_label = ttk.Label(transparency_frame, textvariable=tr_value_var, width=6, anchor='e')
        tr_label.grid(row=0, column=2, sticky='e')
        transparency_var.trace_add('write', _update_tr_label)
        _update_tr_label()

        topmost_var = tk.BooleanVar(value=self._initial_topmost)
        topmost_check = ttk.Checkbutton(
            size_frame,
            text=t('copy_area.topmost', 'Topmost'),
            variable=topmost_var,
            style='Toggle.TCheckbutton',
        )
        topmost_check.pack(side='left', padx=(12, 0))

        # Buttons
        btns = ttk.Frame(frm)
        btns.pack(fill='x', pady=(0, 8))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        def on_save() -> None:
            name_text = name_var.get().strip()
            if name_text:
                self._name_texts[current_lang] = name_text
            if not self._name_texts:
                messagebox.showerror(parent=dlg, title='Error', message=t('error.name_required', 'Name is required'))
                return
            image_path = img_var.get().strip()
            if not image_path:
                messagebox.showerror(parent=dlg, title='Error', message=t('error.image_required', 'Image is required'))
                return

            selected_buffs = [self._buff_ids[i] for i in buff_list.curselection()]
            selected_debuffs = [self._debuff_ids[i] for i in debuff_list.curselection()]

            self._result = {
                'name': dict(self._name_texts),
                'image_path': image_path,
                'references': {
                    'buffs': selected_buffs,
                    'debuffs': selected_debuffs,
                },
                'capture': {
                    'left': int(capture_left_var.get()),
                    'top': int(capture_top_var.get()),
                    'width': int(capture_width_var.get()),
                    'height': int(capture_height_var.get()),
                },
                'left': int(left_var.get()),
                'top': int(top_var.get()),
                'width': int(width_var.get()),
                'height': int(height_var.get()),
                'topmost': bool(topmost_var.get()),
                'transparency': float(transparency_var.get()),
            }
            dlg.destroy()

        def on_cancel() -> None:
            self._result = None
            dlg.destroy()

        save_btn = tk.Button(
            btns,
            text=t('dialog.save', 'Save') if self._initial else t('dialog.create', 'Create'),
            command=on_save,
            bg='#10b981',
            fg='#ffffff',
            font=('Segoe UI', 10, 'bold'),
            padx=20,
            pady=10,
            relief='flat',
            borderwidth=0,
            activebackground='#059669',
            activeforeground='#ffffff',
            cursor='hand2',
        )
        save_btn.grid(row=0, column=0, sticky='w', padx=(0, 8))

        cancel_btn = tk.Button(
            btns,
            text=t('dialog.cancel', 'Cancel'),
            command=on_cancel,
            bg='#ef4444',
            fg='#ffffff',
            font=('Segoe UI', 10, 'bold'),
            padx=20,
            pady=10,
            relief='flat',
            borderwidth=0,
            activebackground='#dc2626',
            activeforeground='#ffffff',
            cursor='hand2',
        )
        cancel_btn.grid(row=0, column=1, sticky='e')

        dlg.wait_window()
        return self._result

    def _format_name(self, item: Dict) -> str:
        lang = get_lang()
        name = item.get('name', {})
        return name.get(lang) or name.get('en') or item.get('id', '')

    def _open_localize(self, store: Dict[str, str], var: tk.StringVar) -> None:
        from src.ui.dialogs.localize_dialog import open_localize_dialog

        res = open_localize_dialog(self._master, store)
        if res is None:
            return
        lang, text = res
        store[lang] = text
        if lang == get_lang():
            var.set(text)


