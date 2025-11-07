import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict
from src.i18n.locale import t, get_lang
from src.buffs.library import copy_image_to_library
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


class BuffEditorDialog:
    def __init__(self, master: tk.Tk, entry_type: str = 'buff', initial: Optional[dict] = None) -> None:
        self._master = master
        self._type = 'buff' if entry_type == 'buff' else 'debuff'
        self._name_texts: Dict[str, str] = {}
        self._desc_texts: Dict[str, str] = {}
        self._initial = initial or {}

        # preload localized texts if initial provided
        if isinstance(self._initial.get('name'), dict):
            self._name_texts.update(self._initial.get('name'))
        if isinstance(self._initial.get('description'), dict):
            self._desc_texts.update(self._initial.get('description'))

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

        # Настраиваем стили для кнопок Save (яркая зелёная) и Cancel (яркая красная)
        style = ttk.Style(dlg)
        try:
            # Яркая зелёная кнопка Save с жирным белым текстом
            style.configure('Save.TButton',
                          padding=[20, 10],
                          font=('Segoe UI', 10, 'bold'),  # Жирный шрифт для лучшей видимости
                          background='#10b981',  # Яркий зелёный
                          foreground='#ffffff',  # Яркий белый текст
                          borderwidth=0,
                          focuscolor='none')
            style.map('Save.TButton',
                     background=[('active', '#059669'), ('pressed', '#047857')],
                     foreground=[('active', '#ffffff'), ('pressed', '#ffffff')])
            
            # Яркая красная кнопка Cancel с жирным белым текстом
            style.configure('Cancel.TButton',
                          padding=[20, 10],
                          font=('Segoe UI', 10, 'bold'),  # Жирный шрифт для лучшей видимости
                          background='#ef4444',  # Яркий красный
                          foreground='#ffffff',  # Яркий белый текст
                          borderwidth=0,
                          focuscolor='none')
            style.map('Cancel.TButton',
                     background=[('active', '#dc2626'), ('pressed', '#b91c1c')],
                     foreground=[('active', '#ffffff'), ('pressed', '#ffffff')])
        except Exception:
            pass

        frm = ttk.Frame(dlg, padding=8)
        frm.pack(fill='both', expand=True)

        # Name + localization
        name_row = ttk.Frame(frm)
        name_row.pack(fill='x', pady=(0, 4))
        ttk.Label(name_row, text=t('buffs.name', 'Name')).pack(side='left')
        curr_lang = get_lang()
        init_name = ''
        try:
            init_name = self._name_texts.get(curr_lang) or self._name_texts.get('en', '')
        except Exception:
            init_name = ''
        name_var = tk.StringVar(value=init_name)
        name_entry = ttk.Entry(name_row, textvariable=name_var)
        name_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        loc_btn1 = ttk.Button(name_row, text=t('dialog.localize', 'Localize'), command=lambda: self._open_loc(self._name_texts, name_var))
        loc_btn1.pack(side='left')

        # Image path
        img_row = ttk.Frame(frm)
        img_row.pack(fill='x', pady=(0, 4))
        ttk.Label(img_row, text=t('buffs.image', 'Image')).pack(side='left')
        img_var = tk.StringVar(value=self._initial.get('image_path', ''))
        img_entry = ttk.Entry(img_row, textvariable=img_var)
        img_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        def choose_img():
            path = filedialog.askopenfilename(parent=dlg, filetypes=[('Images', '*.png;*.jpg;*.jpeg')])
            if path:
                # Copy image to library
                copied_path = copy_image_to_library(path)
                if copied_path:
                    img_var.set(copied_path)
                else:
                    # Fallback to original path if copy failed
                    img_var.set(path)
        ttk.Button(img_row, text='...', width=3, command=choose_img).pack(side='left')

        # Preview under image field
        preview_row = ttk.Frame(frm)
        preview_row.pack(fill='x', pady=(0, 6))
        preview_label = tk.Label(preview_row, relief='sunken')
        preview_label.pack(anchor='w')

        self._img_preview_photo = None
        def update_preview(path: str):
            try:
                if not path or not os.path.isfile(path):
                    preview_label.configure(image='', text='')
                    self._img_preview_photo = None
                    return
                if Image is None or ImageTk is None:
                    # Fallback: try Tk PhotoImage (PNG only)
                    photo = tk.PhotoImage(file=path)
                    self._img_preview_photo = photo
                    preview_label.configure(image=photo)
                    return
                img = Image.open(path)
                img = img.convert('RGBA')
                # Fit into 128x128 thumbnail keeping aspect
                img.thumbnail((128, 128), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._img_preview_photo = photo
                preview_label.configure(image=photo)
            except Exception:
                preview_label.configure(image='', text='')
                self._img_preview_photo = None

        def _on_img_path_change(*args):
            update_preview(img_var.get().strip())
        img_var.trace_add('write', _on_img_path_change)
        update_preview(img_var.get().strip())

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
        try:
            init_desc = self._desc_texts.get(curr_lang) or self._desc_texts.get('en', '')
            if init_desc:
                desc_text.insert('1.0', init_desc)
        except Exception:
            pass
        loc_btn2 = ttk.Button(desc_row, text=t('dialog.localize', 'Localize'), command=lambda: self._open_loc_text(self._desc_texts, desc_text))
        loc_btn2.pack(anchor='e', pady=(6, 0))

        # Sounds
        sound_on_row = ttk.Frame(frm)
        sound_on_row.pack(fill='x', pady=(0, 4))
        ttk.Label(sound_on_row, text=t('buffs.sound_on', 'Appear Sound')).pack(side='left')
        sound_on_var = tk.StringVar(value=self._initial.get('sound_on') or '')
        ttk.Entry(sound_on_row, textvariable=sound_on_var).pack(side='left', fill='x', expand=True, padx=(6, 6))
        def choose_sound_on():
            path = filedialog.askopenfilename(parent=dlg, filetypes=[('Audio', '*.wav;*.mp3;*.ogg')])
            if path:
                sound_on_var.set(path)
        ttk.Button(sound_on_row, text='...', width=3, command=choose_sound_on).pack(side='left')

        sound_off_row = ttk.Frame(frm)
        sound_off_row.pack(fill='x', pady=(0, 4))
        ttk.Label(sound_off_row, text=t('buffs.sound_off', 'Disappear Sound')).pack(side='left')
        sound_off_var = tk.StringVar(value=self._initial.get('sound_off') or '')
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
        left_var = tk.IntVar(value=int(self._initial.get('position', {}).get('left', 0)))
        top_var = tk.IntVar(value=int(self._initial.get('position', {}).get('top', 0)))
        ttk.Label(loc_row, text='Left').pack(side='left', padx=(6, 2))
        ttk.Entry(loc_row, textvariable=left_var, width=8).pack(side='left')
        ttk.Label(loc_row, text='Top').pack(side='left', padx=(6, 2))
        ttk.Entry(loc_row, textvariable=top_var, width=8).pack(side='left')

        # Size (width, height)
        size_row = ttk.Frame(frm)
        size_row.pack(fill='x', pady=(0, 4))
        ttk.Label(size_row, text=t('buffs.size', 'Size')).pack(side='left')
        width_var = tk.IntVar(value=int(self._initial.get('size', {}).get('width', 0)))
        height_var = tk.IntVar(value=int(self._initial.get('size', {}).get('height', 0)))
        ttk.Label(size_row, text='W').pack(side='left', padx=(6, 2))
        ttk.Entry(size_row, textvariable=width_var, width=8).pack(side='left')
        ttk.Label(size_row, text='H').pack(side='left', padx=(6, 2))
        ttk.Entry(size_row, textvariable=height_var, width=8).pack(side='left')

        # Transparency
        tr_row = ttk.Frame(frm)
        tr_row.pack(fill='x', pady=(0, 8))
        ttk.Label(tr_row, text=t('buffs.transparency', 'Transparency')).pack(side='left')
        tr_var = tk.DoubleVar(value=float(self._initial.get('transparency', 1.0)))
        ttk.Scale(tr_row, variable=tr_var, from_=0.0, to=1.0, orient='horizontal').pack(side='left', fill='x', expand=True, padx=(6, 6))

        # Extend bottom (pixels)
        ext_row = ttk.Frame(frm)
        ext_row.pack(fill='x', pady=(0, 8))
        ttk.Label(ext_row, text=t('buffs.extend_bottom', 'Extend bottom (px)')).pack(side='left')
        extend_var = tk.IntVar(value=int(self._initial.get('extend_bottom', 0)))
        ttk.Entry(ext_row, textvariable=extend_var, width=8).pack(side='left', padx=(6, 0))

        # Buttons
        btns = ttk.Frame(frm)
        btns.pack(fill='x')
        def on_create():
            # validation
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
                'extend_bottom': int(extend_var.get()),
            }
            dlg.destroy()

        def on_cancel():
            self._result = None
            dlg.destroy()

        # Button text: Save if editing, Create otherwise
        btn_text = t('dialog.save', 'Save') if self._initial else t('dialog.create', 'Create')
        # Используем обычные tk.Button для гарантированного отображения цветов
        save_btn = tk.Button(btns, text=btn_text, command=on_create, 
                            bg='#10b981', fg='#ffffff', font=('Segoe UI', 10, 'bold'),
                            padx=20, pady=10, relief='flat', borderwidth=0,
                            activebackground='#059669', activeforeground='#ffffff',
                            cursor='hand2')
        save_btn.pack(side='left', padx=(0, 8))
        
        cancel_btn = tk.Button(btns, text=t('dialog.cancel', 'Cancel'), command=on_cancel,
                              bg='#ef4444', fg='#ffffff', font=('Segoe UI', 10, 'bold'),
                              padx=20, pady=10, relief='flat', borderwidth=0,
                              activebackground='#dc2626', activeforeground='#ffffff',
                              cursor='hand2')
        cancel_btn.pack(side='right')

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

        # Initialize description widget with current language from initial
        try:
            curr_lang = get_lang()
            init_desc = self._desc_texts.get(curr_lang) or self._desc_texts.get('en', '')
            if init_desc:
                widget.delete('1.0', 'end')
                widget.insert('1.0', init_desc)
        except Exception:
            pass