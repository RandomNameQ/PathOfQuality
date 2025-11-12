"""Dialog for creating and editing currency entries."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional

from src.buffs.library import copy_image_to_library
from src.ui.dialogs.capture_utils import capture_area_to_library
from src.i18n.locale import t
from src.ui.roi_selector import select_roi

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageTk = None


class CurrencyEditorDialog:
    """Modal dialog that captures all currency fields."""

    def __init__(self, master: tk.Tk, initial: Optional[Dict] = None) -> None:
        self._master = master
        self._initial = initial or {}
        self._result: Optional[Dict] = None
        self._preview_photo = None

    def show(self) -> Optional[Dict]:
        """Show dialog and return collected form data."""

        dlg = tk.Toplevel(self._master)
        dlg.title(t('tab.currency', 'Currency'))
        dlg.transient(self._master)
        dlg.grab_set()
        dlg.resizable(False, False)

        try:
            w, h = 560, 520
            sw = dlg.winfo_screenwidth()
            sh = dlg.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            dlg.geometry(f'{w}x{h}+{x}+{y}')
        except Exception:
            pass

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill='both', expand=True)

        # Interface
        interface_row = ttk.Frame(frame)
        interface_row.pack(fill='x', pady=(0, 8))
        interface_row.pack_propagate(False)
        ttk.Label(interface_row, text=t('currency.interface', 'Interface')).pack(side='left')
        interface_var = tk.StringVar(value=str(self._initial.get('interface', '')))
        ttk.Entry(interface_row, textvariable=interface_var).pack(side='left', fill='x', expand=True, padx=(8, 0))

        # Name
        name_row = ttk.Frame(frame)
        name_row.pack(fill='x', pady=(0, 8))
        ttk.Label(name_row, text=t('currency.name', 'Name')).pack(side='left')
        name_var = tk.StringVar(value=str(self._initial.get('name', '')))
        ttk.Entry(name_row, textvariable=name_var).pack(side='left', fill='x', expand=True, padx=(8, 0))

        capture_btn_row = ttk.Frame(frame)
        capture_btn_row.pack(fill='x', pady=(0, 8))
        take_area_btn = tk.Button(
            capture_btn_row,
            text=t('button.take_area', 'Take area'),
            command=lambda: None,
            bg='#10b981',
            fg='#ffffff',
            font=('Segoe UI', 9, 'bold'),
            padx=16,
            pady=6,
            relief='flat',
            borderwidth=0,
            activebackground='#059669',
            activeforeground='#ffffff',
            cursor='hand2',
        )
        take_area_btn.pack(anchor='w')

        # Image selection
        image_row = ttk.Frame(frame)
        image_row.pack(fill='x', pady=(0, 8))
        ttk.Label(image_row, text=t('currency.image', 'Image')).pack(side='left')
        image_var = tk.StringVar(value=str(self._initial.get('image_path', '')))
        image_entry = ttk.Entry(image_row, textvariable=image_var)
        image_entry.pack(side='left', fill='x', expand=True, padx=(8, 8))

        def choose_image() -> None:
            path = filedialog.askopenfilename(
                parent=dlg,
                filetypes=[('Images', '*.png;*.jpg;*.jpeg;*.bmp;*.gif')],
            )
            if not path:
                return
            copied = copy_image_to_library(path)
            image_var.set(copied or path)

        ttk.Button(image_row, text='...', width=4, command=choose_image).pack(side='left')

        # Preview
        preview_group = ttk.LabelFrame(frame, text=t('currency.preview', 'Preview'))
        preview_group.pack(fill='x', pady=(0, 12))
        preview_label = tk.Label(preview_group, relief='sunken')
        preview_label.pack(anchor='w', padx=8, pady=8)

        def update_preview(path: str) -> None:
            try:
                if not path or not os.path.isfile(path):
                    preview_label.configure(image='', text='')
                    self._preview_photo = None
                    return
                if Image is None or ImageTk is None:
                    photo = tk.PhotoImage(file=path)
                    self._preview_photo = photo
                    preview_label.configure(image=photo)
                    return
                img = Image.open(path).convert('RGBA')
                img.thumbnail((160, 160), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._preview_photo = photo
                preview_label.configure(image=photo)
            except Exception:
                preview_label.configure(image='', text='')
                self._preview_photo = None

        image_var.trace_add('write', lambda *_: update_preview(image_var.get().strip()))
        update_preview(image_var.get().strip())

        def on_take_area() -> None:
            result = capture_area_to_library(self._master)
            if not result:
                return
            path, (_left_sel, _top_sel, width_sel, height_sel) = result
            image_var.set(path)
            capture_width.set(int(width_sel))
            capture_height.set(int(height_sel))

        take_area_btn.configure(command=on_take_area)

        # Capture section
        capture_group = ttk.LabelFrame(frame, text=t('currency.capture', 'Capture area'))
        capture_group.pack(fill='x', pady=(0, 12))

        capture_left = tk.IntVar(value=int(self._initial.get('capture', {}).get('left', 0)))
        capture_top = tk.IntVar(value=int(self._initial.get('capture', {}).get('top', 0)))
        capture_width = tk.IntVar(value=int(self._initial.get('capture', {}).get('width', 0)))
        capture_height = tk.IntVar(value=int(self._initial.get('capture', {}).get('height', 0)))

        capture_row = ttk.Frame(capture_group)
        capture_row.pack(fill='x', pady=4)

        def on_select_capture() -> None:
            selected = select_roi(self._master)
            if selected is None:
                return
            left, top, width, height = selected
            capture_left.set(int(left))
            capture_top.set(int(top))
            capture_width.set(int(width))
            capture_height.set(int(height))

        select_btn = tk.Button(
            capture_row,
            text=t('currency.select_area', 'Select area'),
            command=on_select_capture,
            bg='#10b981',
            fg='#ffffff',
            font=('Segoe UI', 9, 'bold'),
            activebackground='#059669',
            activeforeground='#ffffff',
            relief='flat',
            borderwidth=0,
            padx=16,
            pady=6,
            cursor='hand2',
        )
        select_btn.pack(side='left', padx=(0, 12))

        for label_text, var in (
            ('L', capture_left),
            ('T', capture_top),
            ('W', capture_width),
            ('H', capture_height),
        ):
            ttk.Label(capture_row, text=label_text).pack(side='left', padx=(0, 4))
            ttk.Entry(capture_row, textvariable=var, width=8).pack(side='left', padx=(0, 8))

        # Buttons
        button_row = ttk.Frame(frame)
        button_row.pack(fill='x', pady=(12, 0))

        def on_save() -> None:
            name = name_var.get().strip()
            interface = interface_var.get().strip()
            image = image_var.get().strip()

            if not name:
                messagebox.showerror(parent=dlg, title='Error', message=t('error.name_required', 'Name is required'))
                return
            if not image:
                messagebox.showerror(parent=dlg, title='Error', message=t('error.image_required', 'Image is required'))
                return

            if not interface:
                interface = name
                interface_var.set(interface)
            if not interface:
                messagebox.showerror(parent=dlg, title='Error', message=t('error.interface_required', 'Interface is required'))
                return

            self._result = {
                'name': name,
                'interface': interface,
                'image_path': image,
                'capture': {
                    'left': int(capture_left.get()),
                    'top': int(capture_top.get()),
                    'width': int(capture_width.get()),
                    'height': int(capture_height.get()),
                },
            }
            dlg.destroy()

        def on_cancel() -> None:
            self._result = None
            dlg.destroy()

        save_btn = tk.Button(
            button_row,
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
        save_btn.pack(side='left', padx=(0, 8))

        cancel_btn = tk.Button(
            button_row,
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
        cancel_btn.pack(side='right')

        dlg.wait_window()
        return self._result
