from typing import List, Tuple, Optional
import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from src.i18n.locale import t, get_lang
from src.buffs.library import load_library, save_library, make_entry, add_entry
from src.ui.dialogs.buff_editor import BuffEditorDialog


class BuffHUD:
    def __init__(self, templates: List[Tuple[str, str]], keep_on_top: bool = True, alpha: float = 1.0, grab_anywhere: bool = True) -> None:
        self._root = tk.Tk()
        self._root.title('Buff HUD')
        self._root.resizable(False, False)
        try:
            self._root.attributes('-topmost', keep_on_top)
        except Exception:
            pass
        try:
            self._root.attributes('-alpha', float(alpha))
        except Exception:
            pass

        # Устанавливаем размер окна 800x800 и центрируем при запуске
        try:
            w, h = 800, 800
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self._root.geometry(f'{w}x{h}+{x}+{y}')
        except Exception:
            pass

        self._exit_requested = False
        self._select_roi_requested = False
        self._overlay_var = tk.BooleanVar(value=False)

        self._photos = {}
        self._labels = {}

        # Notebook (вкладки)
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill='both', expand=True, padx=6, pady=6)

        self._tab_monitor = ttk.Frame(self._notebook)
        self._tab_settings = ttk.Frame(self._notebook)
        self._tab_buffs = ttk.Frame(self._notebook)
        self._tab_debuffs = ttk.Frame(self._notebook)
        self._notebook.add(self._tab_monitor, text=t('tab.monitoring', 'Monitoring'))
        self._notebook.add(self._tab_settings, text=t('tab.settings', 'Settings'))
        self._notebook.add(self._tab_buffs, text=t('tab.buffs', 'Buffs'))
        self._notebook.add(self._tab_debuffs, text=t('tab.debuffs', 'Debuffs'))

        # ===== Мониторинг =====
        header = tk.Label(self._tab_monitor, text='Buff HUD', font=('Segoe UI', 12))
        header.pack(padx=6, pady=(2, 2))

        self._icons_frame = tk.Frame(self._tab_monitor)
        self._icons_frame.pack(padx=6, pady=4)

        for name, path in templates:
            photo = None
            try:
                photo = tk.PhotoImage(file=path)
            except Exception:
                photo = None
            if photo is not None:
                self._photos[name] = photo
                lbl = tk.Label(self._icons_frame, image=photo)
            else:
                lbl = tk.Label(self._icons_frame, text=name, fg='white', bg='#333333', padx=8, pady=4)
            lbl.pack(side='left')
            lbl.pack_forget()
            self._labels[name] = lbl

        self._indicator = tk.Frame(self._tab_monitor, width=220, height=22, bg='red')
        self._indicator.pack(padx=6, pady=(2, 2))
        self._indicator.pack_propagate(False)

        self._status = tk.Label(self._tab_monitor, text='Найдены: —')
        self._status.pack(padx=6, pady=(2, 6))

        self._btn_exit = tk.Button(self._tab_monitor, text=t('button.exit', 'Exit'), command=self._on_exit, width=8)
        self._btn_exit.pack(padx=6, pady=(2, 6))

        # ===== Настройки =====
        controls = ttk.Frame(self._tab_settings)
        controls.pack(fill='x', padx=6, pady=6)

        self._btn_select = ttk.Button(controls, text=t('settings.select_zone', 'Select Area'), command=self._on_select_roi)
        self._btn_select.pack(side='left', padx=(0, 8))

        self._chk_overlay = ttk.Checkbutton(controls, text=t('settings.show_analysis', 'Show Analysis Area'), variable=self._overlay_var)
        self._chk_overlay.pack(side='left')

        # Language switcher
        lang_controls = ttk.Frame(self._tab_settings)
        lang_controls.pack(fill='x', padx=6, pady=(0, 6))
        self._lbl_language = ttk.Label(lang_controls, text=t('settings.language', 'Language'))
        self._lbl_language.pack(side='left', padx=(0, 8))
        self._lang_var = tk.StringVar(value=get_lang())
        lang_cmb = ttk.Combobox(lang_controls, textvariable=self._lang_var, values=['en', 'ru'], state='readonly', width=6)
        lang_cmb.pack(side='left')
        def _on_lang_changed(event=None):
            from src.i18n.locale import set_lang
            set_lang(self._lang_var.get())
            self._refresh_texts()
        lang_cmb.bind('<<ComboboxSelected>>', _on_lang_changed)

        self._roi_label = ttk.Label(self._tab_settings, text=f"{t('settings.roi', 'ROI')}: —")
        self._roi_label.pack(padx=6, pady=(6, 6))

        # ===== Баффы =====
        buffs_controls = ttk.Frame(self._tab_buffs)
        buffs_controls.pack(fill='x', padx=6, pady=6)
        self._btn_add_buff = ttk.Button(buffs_controls, text=t('buffs.add', 'Add'), command=lambda: self._on_add_entry('buff'))
        self._btn_add_buff.pack(side='left')
        self._buffs_list = tk.Listbox(self._tab_buffs)
        self._buffs_list.pack(fill='both', expand=True, padx=6, pady=(0, 6))

        # ===== Дебаффы =====
        debuffs_controls = ttk.Frame(self._tab_debuffs)
        debuffs_controls.pack(fill='x', padx=6, pady=6)
        self._btn_add_debuff = ttk.Button(debuffs_controls, text=t('buffs.add', 'Add'), command=lambda: self._on_add_entry('debuff'))
        self._btn_add_debuff.pack(side='left')
        self._debuffs_list = tk.Listbox(self._tab_debuffs)
        self._debuffs_list.pack(fill='both', expand=True, padx=6, pady=(0, 6))

        # загрузим библиотеку и отобразим списки
        self._reload_library()

        if grab_anywhere:
            for widget in (self._root, self._tab_monitor, self._tab_settings):
                widget.bind('<ButtonPress-1>', self._start_move)
                widget.bind('<B1-Motion>', self._on_motion)
            for widget in (self._tab_buffs, self._tab_debuffs):
                widget.bind('<ButtonPress-1>', self._start_move)
                widget.bind('<B1-Motion>', self._on_motion)

        self._root.protocol('WM_DELETE_WINDOW', self._on_exit)

    def _on_exit(self):
        self._exit_requested = True

    def _start_move(self, event):
        self._click_x = event.x_root
        self._click_y = event.y_root
        self._win_x = self._root.winfo_x()
        self._win_y = self._root.winfo_y()

    def _on_motion(self, event):
        dx = event.x_root - self._click_x
        dy = event.y_root - self._click_y
        new_x = self._win_x + dx
        new_y = self._win_y + dy
        self._root.geometry(f'+{new_x}+{new_y}')

    def read(self, timeout: int = 0) -> Optional[str]:
        try:
            self._root.update_idletasks()
            self._root.update()
        except tk.TclError:
            self._exit_requested = True
        if timeout and timeout > 0:
            time.sleep(timeout / 1000.0)
        if self._exit_requested:
            return 'EXIT'
        if self._select_roi_requested:
            self._select_roi_requested = False
            return 'SELECT_ROI'
        return None

    def update(self, found_names: List[str]) -> None:
        for name, lbl in self._labels.items():
            should_show = name in found_names
            if should_show:
                if lbl.winfo_manager() == '':
                    lbl.pack(side='left')
            else:
                if lbl.winfo_manager() != '':
                    lbl.pack_forget()
        self._status.configure(text=f"Найдены: {', '.join(found_names) if found_names else '—'}")
        try:
            self._indicator.configure(bg=('green' if found_names else 'red'))
        except Exception:
            pass

    def _reload_library(self) -> None:
        data = load_library()
        self._buffs_list.delete(0, 'end')
        self._debuffs_list.delete(0, 'end')
        lang = get_lang()
        for item in data.get('buffs', []):
            name = item.get('name', {}).get(lang) or item.get('name', {}).get('en') or '—'
            self._buffs_list.insert('end', name)
        for item in data.get('debuffs', []):
            name = item.get('name', {}).get(lang) or item.get('name', {}).get('en') or '—'
            self._debuffs_list.insert('end', name)

    def _on_add_entry(self, entry_type: str) -> None:
        dlg = BuffEditorDialog(self._root, entry_type=entry_type)
        res = dlg.show()
        if res is None:
            return
        # валидация уже была в диалоге, здесь создадим запись и сохраним
        from src.buffs.library import BuffEntry
        entry = BuffEntry(
            id='temp',  # заменим ниже на uuid через фабрику
            type=entry_type,
            name=res['name'],
            image_path=res['image_path'],
            description=res['description'],
            sound_on=res['sound_on'],
            sound_off=res['sound_off'],
            position={'left': res['left'], 'top': res['top']},
            size={'width': res['width'], 'height': res['height']},
            transparency=res['transparency'],
        )
        # используем фабрику для корректной генерации id
        from src.buffs.library import make_entry
        entry2 = make_entry(
            entry_type=entry_type,
            name_en=res['name'].get('en', res['name'].get(get_lang(), '')),
            image_path=res['image_path'],
            description_en=res['description'].get('en', res['description'].get(get_lang(), '')),
            sound_on=res['sound_on'],
            sound_off=res['sound_off'],
            left=res['left'],
            top=res['top'],
            width=res['width'],
            height=res['height'],
            transparency=res['transparency'],
        )
        # перенесём локализации, если были не на en
        entry2.name.update(res['name'])
        entry2.description.update(res['description'])
        add_entry(entry2)
        self._reload_library()

    def _on_select_roi(self):
        self._select_roi_requested = True

    def get_overlay_enabled(self) -> bool:
        return bool(self._overlay_var.get())

    def set_roi_info(self, left: int, top: int, width: int, height: int) -> None:
        self._roi_label.configure(text=f"ROI: left={left}, top={top}, width={width}, height={height}")

    def get_root(self) -> tk.Tk:
        return self._root

    def close(self) -> None:
        try:
            self._root.destroy()
        except Exception:
            pass

    def _refresh_texts(self) -> None:
        try:
            self._notebook.tab(self._tab_monitor, text=t('tab.monitoring', 'Monitoring'))
            self._notebook.tab(self._tab_settings, text=t('tab.settings', 'Settings'))
            self._notebook.tab(self._tab_buffs, text=t('tab.buffs', 'Buffs'))
            self._notebook.tab(self._tab_debuffs, text=t('tab.debuffs', 'Debuffs'))
        except Exception:
            pass
        try:
            self._btn_select.configure(text=t('settings.select_zone', 'Select Area'))
            self._chk_overlay.configure(text=t('settings.show_analysis', 'Show Analysis Area'))
            self._lbl_language.configure(text=t('settings.language', 'Language'))
            self._btn_exit.configure(text=t('button.exit', 'Exit'))
            self._btn_add_buff.configure(text=t('buffs.add', 'Add'))
            self._btn_add_debuff.configure(text=t('buffs.add', 'Add'))
            # обновим префикс у ROI
            txt = self._roi_label.cget('text')
            if ':' in txt:
                self._roi_label.configure(text=f"{t('settings.roi', 'ROI')}:" + txt.split(':', 1)[1])
            else:
                self._roi_label.configure(text=f"{t('settings.roi', 'ROI')}: —")
        except Exception:
            pass