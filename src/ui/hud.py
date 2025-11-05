from typing import List, Tuple, Optional
import time
import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from src.i18n.locale import t, get_lang
from src.buffs.library import load_library, save_library, make_entry, add_entry, update_entry
from src.ui.dialogs.buff_editor import BuffEditorDialog
try:
    from PIL import Image, ImageTk, ImageOps
except Exception:
    Image = None
    ImageTk = None
    ImageOps = None


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
        self._events: List[str] = []

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

        # Глобальный режим позиционирования активных иконок
        try:
            ttk.Style(self._root).configure('Toggle.TCheckbutton', padding=6)
        except Exception:
            pass
        self._positioning_var = tk.BooleanVar(value=False)
        self._btn_positioning = ttk.Checkbutton(
            self._tab_monitor,
            text=t('monitoring.positioning', 'Positioning'),
            variable=self._positioning_var,
            style='Toggle.TCheckbutton',
            command=self._on_toggle_positioning,
        )
        self._btn_positioning.pack(padx=6, pady=(0, 6))

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

        # Always on top toggle
        self._topmost_var = tk.BooleanVar(value=keep_on_top)
        self._chk_topmost = ttk.Checkbutton(controls, text=t('settings.always_on_top', 'Always on top'), variable=self._topmost_var)
        def _on_topmost_changed():
            try:
                self._root.attributes('-topmost', bool(self._topmost_var.get()))
            except Exception:
                pass
        self._chk_topmost.configure(command=_on_topmost_changed)
        self._chk_topmost.pack(side='left', padx=(8, 0))

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
            # Перезаполним списки библиотеки локализованными значениями
            try:
                self._reload_library()
            except Exception:
                pass
        lang_cmb.bind('<<ComboboxSelected>>', _on_lang_changed)

        self._roi_label = ttk.Label(self._tab_settings, text=f"{t('settings.roi', 'ROI')}: —")
        self._roi_label.pack(padx=6, pady=(6, 6))

        # ===== Баффы =====
        buffs_controls = ttk.Frame(self._tab_buffs)
        buffs_controls.pack(fill='x', padx=6, pady=6)
        # Улучшенные стили для кнопок
        try:
            style.configure('Action.TButton', padding=(8, 4), font=('Segoe UI', 9))
        except Exception:
            pass
        self._btn_add_buff = ttk.Button(buffs_controls, text=t('buffs.add', 'Add'), 
                                        command=lambda: self._on_add_entry('buff'), style='Action.TButton')
        self._btn_add_buff.pack(side='left')
        self._btn_edit_buff = ttk.Button(buffs_controls, text=t('buffs.edit', 'Edit'), 
                                         command=lambda: self._on_edit_entry('buff'), style='Action.TButton')
        self._btn_edit_buff.pack(side='left', padx=(6, 0))
        # Поиск по имени (всем языкам)
        buffs_search = ttk.Frame(self._tab_buffs)
        buffs_search.pack(fill='x', padx=6, pady=(0, 6))
        self._lbl_search_buffs = ttk.Label(buffs_search, text=t('buffs.search', 'Search'), font=('Segoe UI', 9))
        self._lbl_search_buffs.pack(side='left', padx=(0, 4))
        self._search_var_buffs = tk.StringVar(value='')
        buffs_search_entry = ttk.Entry(buffs_search, textvariable=self._search_var_buffs, font=('Segoe UI', 9))
        buffs_search_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        self._btn_clear_search_buffs = ttk.Button(buffs_search, text=t('button.clear', 'Clear'), 
                                                 command=lambda: self._search_var_buffs.set(''), style='Action.TButton')
        self._btn_clear_search_buffs.pack(side='left')
        def _on_search_buffs(*args):
            self._reload_library()
        self._search_var_buffs.trace_add('write', _on_search_buffs)

        # Дерево с прокруткой и увеличенной высотой строк
        buffs_tree_frame = ttk.Frame(self._tab_buffs)
        buffs_tree_frame.pack(fill='both', expand=True, padx=6, pady=(0, 6))
        style = ttk.Style(self._root)
        try:
            # Высота строки под размер иконки: 64px
            style.configure('BuffTree.Treeview', rowheight=64, background='#ffffff', 
                          fieldbackground='#ffffff', foreground='#333333')
            # Стиль заголовков
            style.configure('BuffTree.Treeview.Heading', font=('Segoe UI', 9, 'bold'),
                          background='#f0f0f0', foreground='#2c3e50', relief='flat')
            # Hover эффект для строк
            style.map('BuffTree.Treeview', background=[('selected', '#e3f2fd')])
        except Exception:
            pass
        # Структура: icon (слева) -> name -> activate (справа) -> desc
        self._buffs_tree = ttk.Treeview(buffs_tree_frame, style='BuffTree.Treeview', columns=('icon', 'name', 'activate', 'desc'), show='tree headings')
        self._buffs_tree.heading('#0', text='')  # Скрываем tree column, используем name
        self._buffs_tree.heading('icon', text='')
        self._buffs_tree.heading('name', text=t('buffs.name', 'Name'))
        self._buffs_tree.heading('activate', text='')
        self._buffs_tree.heading('desc', text=t('buffs.description', 'Description'))
        self._buffs_tree.column('#0', width=0, stretch=False, minwidth=0)  # Скрываем tree column
        self._buffs_tree.column('icon', width=70, stretch=False, anchor='center')
        self._buffs_tree.column('name', width=200, stretch=False)
        self._buffs_tree.column('activate', width=120, stretch=False, anchor='center')
        self._buffs_tree.column('desc', width=380, stretch=True)
        vsb_b = ttk.Scrollbar(buffs_tree_frame, orient='vertical')
        def _on_buffs_scroll(*args):
            try:
                vsb_b.set(*args)
            except Exception:
                pass
            try:
                self._position_row_controls(self._buffs_tree, self._row_controls_buffs)
            except Exception:
                pass
        self._buffs_tree.configure(yscrollcommand=_on_buffs_scroll)
        try:
            vsb_b.configure(command=self._buffs_tree.yview)
        except Exception:
            pass
        self._buffs_tree.pack(side='left', fill='both', expand=True)
        vsb_b.pack(side='right', fill='y')
        self._buffs_tree.bind('<Double-1>', lambda e: self._on_edit_entry('buff'))
        self._buffs_tree.bind('<Configure>', lambda e: self._position_row_controls(self._buffs_tree, self._row_controls_buffs))

        # ===== Дебаффы =====
        debuffs_controls = ttk.Frame(self._tab_debuffs)
        debuffs_controls.pack(fill='x', padx=6, pady=6)
        self._btn_add_debuff = ttk.Button(debuffs_controls, text=t('buffs.add', 'Add'), 
                                          command=lambda: self._on_add_entry('debuff'), style='Action.TButton')
        self._btn_add_debuff.pack(side='left')
        self._btn_edit_debuff = ttk.Button(debuffs_controls, text=t('buffs.edit', 'Edit'), 
                                           command=lambda: self._on_edit_entry('debuff'), style='Action.TButton')
        self._btn_edit_debuff.pack(side='left', padx=(6, 0))
        # Поиск
        debuffs_search = ttk.Frame(self._tab_debuffs)
        debuffs_search.pack(fill='x', padx=6, pady=(0, 6))
        self._lbl_search_debuffs = ttk.Label(debuffs_search, text=t('buffs.search', 'Search'), font=('Segoe UI', 9))
        self._lbl_search_debuffs.pack(side='left', padx=(0, 4))
        self._search_var_debuffs = tk.StringVar(value='')
        debuffs_search_entry = ttk.Entry(debuffs_search, textvariable=self._search_var_debuffs, font=('Segoe UI', 9))
        debuffs_search_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        self._btn_clear_search_debuffs = ttk.Button(debuffs_search, text=t('button.clear', 'Clear'), 
                                                    command=lambda: self._search_var_debuffs.set(''), style='Action.TButton')
        self._btn_clear_search_debuffs.pack(side='left')
        def _on_search_debuffs(*args):
            self._reload_library()
        self._search_var_debuffs.trace_add('write', _on_search_debuffs)

        # Дерево с прокруткой и увеличенной высотой строк
        debuffs_tree_frame = ttk.Frame(self._tab_debuffs)
        debuffs_tree_frame.pack(fill='both', expand=True, padx=6, pady=(0, 6))
        try:
            # Высота строки под размер иконки: 64px
            style.configure('DebuffTree.Treeview', rowheight=64, background='#ffffff',
                          fieldbackground='#ffffff', foreground='#333333')
            # Стиль заголовков
            style.configure('DebuffTree.Treeview.Heading', font=('Segoe UI', 9, 'bold'),
                          background='#f0f0f0', foreground='#2c3e50', relief='flat')
            # Hover эффект для строк
            style.map('DebuffTree.Treeview', background=[('selected', '#ffebee')])
        except Exception:
            pass
        # Структура: icon (слева) -> name -> activate (справа) -> desc
        self._debuffs_tree = ttk.Treeview(debuffs_tree_frame, style='DebuffTree.Treeview', columns=('icon', 'name', 'activate', 'desc'), show='tree headings')
        self._debuffs_tree.heading('#0', text='')  # Скрываем tree column, используем name
        self._debuffs_tree.heading('icon', text='')
        self._debuffs_tree.heading('name', text=t('buffs.name', 'Name'))
        self._debuffs_tree.heading('activate', text='')
        self._debuffs_tree.heading('desc', text=t('buffs.description', 'Description'))
        self._debuffs_tree.column('#0', width=0, stretch=False, minwidth=0)  # Скрываем tree column
        self._debuffs_tree.column('icon', width=70, stretch=False, anchor='center')
        self._debuffs_tree.column('name', width=200, stretch=False)
        self._debuffs_tree.column('activate', width=120, stretch=False, anchor='center')
        self._debuffs_tree.column('desc', width=380, stretch=True)
        vsb_d = ttk.Scrollbar(debuffs_tree_frame, orient='vertical')
        def _on_debuffs_scroll(*args):
            try:
                vsb_d.set(*args)
            except Exception:
                pass
            try:
                self._position_row_controls(self._debuffs_tree, self._row_controls_debuffs)
            except Exception:
                pass
        self._debuffs_tree.configure(yscrollcommand=_on_debuffs_scroll)
        try:
            vsb_d.configure(command=self._debuffs_tree.yview)
        except Exception:
            pass
        self._debuffs_tree.pack(side='left', fill='both', expand=True)
        vsb_d.pack(side='right', fill='y')
        self._debuffs_tree.bind('<Double-1>', lambda e: self._on_edit_entry('debuff'))
        self._debuffs_tree.bind('<Configure>', lambda e: self._position_row_controls(self._debuffs_tree, self._row_controls_debuffs))

        # Контролы строк (чекбоксы Активировать + кнопка Позиционировать)
        self._row_controls_buffs = {}
        self._active_vars_buffs = {}
        self._row_controls_debuffs = {}
        self._active_vars_debuffs = {}

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
        # Публикуем очередь событий (например, LIBRARY_UPDATED)
        if self._events:
            return self._events.pop(0)
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
        # clear trees
        try:
            for child in self._buffs_tree.get_children():
                self._buffs_tree.delete(child)
            for child in self._debuffs_tree.get_children():
                self._debuffs_tree.delete(child)
        except Exception:
            pass
        # убрать старые контролы
        try:
            for cid, ctrls in list(self._row_controls_buffs.items()):
                for w in ctrls:
                    try:
                        w.place_forget()
                        w.destroy()
                    except Exception:
                        pass
            self._row_controls_buffs.clear()
            self._active_vars_buffs.clear()
            for cid, ctrls in list(self._row_controls_debuffs.items()):
                for w in ctrls:
                    try:
                        w.place_forget()
                        w.destroy()
                    except Exception:
                        pass
            self._row_controls_debuffs.clear()
            self._active_vars_debuffs.clear()
        except Exception:
            pass
        # prepare thumbnails storage
        if not hasattr(self, '_entry_thumbs'):
            self._entry_thumbs = {}
        lang = get_lang()
        def _mk_thumb(path: str):
            try:
                if not path or not os.path.isfile(path):
                    return None
                if Image is None or ImageTk is None:
                    # Fallback: use Tk PhotoImage and subsample to ~64px
                    photo = tk.PhotoImage(file=path)
                    try:
                        w = photo.width()
                        h = photo.height()
                        max_side = max(w, h)
                        if max_side > 64:
                            k = max(1, max_side // 64)
                            photo = photo.subsample(k, k)
                    except Exception:
                        pass
                    return photo
                img = Image.open(path).convert('RGBA')
                img.thumbnail((64, 64), Image.LANCZOS)
                # Без дополнительных отступов: разместим миниатюру отдельным Label справа
                if ImageOps is not None:
                    try:
                        img = ImageOps.expand(img, border=(0, 0, 0, 0), fill=(0, 0, 0, 0))
                    except Exception:
                        img = ImageOps.expand(img, border=(0, 0, 0, 0), fill='#ffffff')
                return ImageTk.PhotoImage(img)
            except Exception:
                return None
        for item in data.get('buffs', []):
            # фильтрация по поиску (всем языкам)
            query = (self._search_var_buffs.get() or '').strip().lower()
            if query:
                nm = item.get('name', {})
                found = any(query in str(v).lower() for v in nm.values())
                if not found:
                    continue
            name = item.get('name', {}).get(lang) or item.get('name', {}).get('en') or '—'
            desc = item.get('description', {}).get(lang) or item.get('description', {}).get('en') or ''
            # Обрезаем длинное описание до 100 символов, стараясь не разрывать слова
            if len(desc) > 100:
                truncated = desc[:97]
                # Пытаемся обрезать по последнему пробелу или переносу строки
                last_space = max(truncated.rfind(' '), truncated.rfind('\n'))
                if last_space > 80:  # Если пробел найден достаточно близко к концу
                    desc = truncated[:last_space] + '...'
                else:
                    desc = truncated + '...'
            thumb = _mk_thumb(item.get('image_path', ''))
            if thumb is not None:
                self._entry_thumbs[item.get('id')] = thumb
            iid = item.get('id')
            # Вставляем: icon (пусто, виджет), name, activate (пусто, виджет), desc
            self._buffs_tree.insert('', 'end', iid=iid, text='', values=('', name, '', desc))
            # Полосатый фон для отделения элементов с улучшенными цветами
            try:
                idx = len(self._buffs_tree.get_children(''))
                tag = 'odd' if (idx % 2 == 1) else 'even'
                self._buffs_tree.item(iid, tags=(tag,))
                # Более мягкие и современные цвета
                self._buffs_tree.tag_configure('odd', background='#f8f9fa')
                self._buffs_tree.tag_configure('even', background='#ffffff')
            except Exception:
                pass
            # Контролы строки: только «Активировать» (кнопку позиционирования убираем)
            var = tk.BooleanVar(value=bool(item.get('active', False)))
            chk = ttk.Checkbutton(self._buffs_tree, text=t('actions.activate', 'Activate'), variable=var,
                                  command=lambda i=iid, v=var: self._on_toggle_active(i, 'buff', v))
            # Миниатюра как отдельный виджет для колонки icon
            thumb_lbl = None
            try:
                ph = self._entry_thumbs.get(iid)
                if ph is not None:
                    # Фон будет соответствовать фону строки (через tag)
                    bg_color = '#f8f9fa' if (len(self._buffs_tree.get_children('')) % 2 == 1) else '#ffffff'
                    thumb_lbl = tk.Label(self._buffs_tree, image=ph, bg=bg_color, relief='flat', borderwidth=0)
            except Exception:
                thumb_lbl = None
            self._row_controls_buffs[iid] = (chk, thumb_lbl) if thumb_lbl is not None else (chk,)
            self._active_vars_buffs[iid] = var
        for item in data.get('debuffs', []):
            query = (self._search_var_debuffs.get() or '').strip().lower()
            if query:
                nm = item.get('name', {})
                found = any(query in str(v).lower() for v in nm.values())
                if not found:
                    continue
            name = item.get('name', {}).get(lang) or item.get('name', {}).get('en') or '—'
            desc = item.get('description', {}).get(lang) or item.get('description', {}).get('en') or ''
            # Обрезаем длинное описание до 100 символов, стараясь не разрывать слова
            if len(desc) > 100:
                truncated = desc[:97]
                # Пытаемся обрезать по последнему пробелу или переносу строки
                last_space = max(truncated.rfind(' '), truncated.rfind('\n'))
                if last_space > 80:  # Если пробел найден достаточно близко к концу
                    desc = truncated[:last_space] + '...'
                else:
                    desc = truncated + '...'
            thumb = _mk_thumb(item.get('image_path', ''))
            if thumb is not None:
                self._entry_thumbs[item.get('id')] = thumb
            iid = item.get('id')
            # Вставляем: icon (пусто, виджет), name, activate (пусто, виджет), desc
            self._debuffs_tree.insert('', 'end', iid=iid, text='', values=('', name, '', desc))
            try:
                idx = len(self._debuffs_tree.get_children(''))
                tag = 'odd' if (idx % 2 == 1) else 'even'
                self._debuffs_tree.item(iid, tags=(tag,))
                # Более мягкие и современные цвета
                self._debuffs_tree.tag_configure('odd', background='#f8f9fa')
                self._debuffs_tree.tag_configure('even', background='#ffffff')
            except Exception:
                pass
            var = tk.BooleanVar(value=bool(item.get('active', False)))
            chk = ttk.Checkbutton(self._debuffs_tree, text=t('actions.activate', 'Activate'), variable=var,
                                  command=lambda i=iid, v=var: self._on_toggle_active(i, 'debuff', v))
            thumb_lbl = None
            try:
                ph = self._entry_thumbs.get(iid)
                if ph is not None:
                    # Фон будет соответствовать фону строки (через tag)
                    bg_color = '#f8f9fa' if (len(self._debuffs_tree.get_children('')) % 2 == 1) else '#ffffff'
                    thumb_lbl = tk.Label(self._debuffs_tree, image=ph, bg=bg_color, relief='flat', borderwidth=0)
            except Exception:
                thumb_lbl = None
            self._row_controls_debuffs[iid] = (chk, thumb_lbl) if thumb_lbl is not None else (chk,)
            self._active_vars_debuffs[iid] = var

        # Расставим контролы по позициям строк
        try:
            self._position_row_controls(self._buffs_tree, self._row_controls_buffs)
        except Exception:
            pass
        try:
            self._position_row_controls(self._debuffs_tree, self._row_controls_debuffs)
        except Exception:
            pass

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

    def get_positioning_enabled(self) -> bool:
        return bool(self._positioning_var.get())

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
            self._chk_topmost.configure(text=t('settings.always_on_top', 'Always on top'))
            self._lbl_language.configure(text=t('settings.language', 'Language'))
            self._btn_exit.configure(text=t('button.exit', 'Exit'))
            self._btn_add_buff.configure(text=t('buffs.add', 'Add'))
            self._btn_edit_buff.configure(text=t('buffs.edit', 'Edit'))
            self._btn_add_debuff.configure(text=t('buffs.add', 'Add'))
            self._btn_edit_debuff.configure(text=t('buffs.edit', 'Edit'))
            self._lbl_search_buffs.configure(text=t('buffs.search', 'Search'))
            self._lbl_search_debuffs.configure(text=t('buffs.search', 'Search'))
            self._btn_clear_search_buffs.configure(text=t('button.clear', 'Clear'))
            self._btn_clear_search_debuffs.configure(text=t('button.clear', 'Clear'))
            try:
                self._btn_positioning.configure(text=t('monitoring.positioning', 'Positioning'))
            except Exception:
                pass
            try:
                self._buffs_tree.heading('name', text=t('buffs.name', 'Name'))
                self._buffs_tree.heading('desc', text=t('buffs.description', 'Description'))
                self._debuffs_tree.heading('name', text=t('buffs.name', 'Name'))
                self._debuffs_tree.heading('desc', text=t('buffs.description', 'Description'))
            except Exception:
                pass
            # обновим префикс у ROI
            txt = self._roi_label.cget('text')
            if ':' in txt:
                self._roi_label.configure(text=f"{t('settings.roi', 'ROI')}:" + txt.split(':', 1)[1])
            else:
                self._roi_label.configure(text=f"{t('settings.roi', 'ROI')}: —")
        except Exception:
            pass

    def _on_edit_entry(self, entry_type: str) -> None:
        # choose proper tree
        tree = self._buffs_tree if entry_type == 'buff' else self._debuffs_tree
        sel = tree.selection()
        if not sel:
            try:
                messagebox.showinfo(title='Info', message=t('info.select_item', 'Select an item to edit'))
            except Exception:
                pass
            return
        entry_id = sel[0]
        data = load_library()
        bucket = 'buffs' if entry_type == 'buff' else 'debuffs'
        item = None
        for it in data.get(bucket, []):
            if it.get('id') == entry_id:
                item = it
                break
        if item is None:
            return
        dlg = BuffEditorDialog(self._root, entry_type=entry_type, initial=item)
        res = dlg.show()
        if res is None:
            return
        from src.buffs.library import update_entry
        res['id'] = entry_id
        res['type'] = entry_type
        update_entry(entry_id, entry_type, res)
        self._reload_library()

    # ==== Дополнительно: позиционирование контролов в строках =====
    def _position_row_controls(self, tree: ttk.Treeview, controls_map: dict) -> None:
        # Иконка в колонке icon (слева), чекбокс в колонке activate (справа)
        for iid, ctrls in controls_map.items():
            try:
                # Проверяем видимость строки
                bbox_icon = tree.bbox(iid, 'icon')
                if not bbox_icon:
                    # невидимая строка — прячем все контролы
                    for w in ctrls:
                        w.place_forget()
                    continue
                
                # Получаем теги для цвета фона
                tags = tree.item(iid, 'tags')
                bg_color = '#f8f9fa' if 'odd' in tags else '#ffffff'
                
                # Иконка в колонке icon (слева)
                if len(ctrls) > 1 and ctrls[1] is not None:
                    thumb = ctrls[1]
                    try:
                        xi, yi, wi, hi = bbox_icon
                        tw = thumb.winfo_reqwidth() or 64
                        th = thumb.winfo_reqheight() or 64
                        # Центрируем иконку в колонке icon
                        tx = xi + (wi - tw) // 2
                        ty = yi + max(2, (hi - th) // 2)
                        thumb.configure(bg=bg_color)
                        thumb.place(x=tx, y=ty)
                    except Exception:
                        thumb.place_forget()
                
                # Чекбокс в колонке activate (справа)
                chk = ctrls[0]
                try:
                    bbox_activate = tree.bbox(iid, 'activate')
                    if bbox_activate:
                        xa, ya, wa, ha = bbox_activate
                        chk_w = chk.winfo_reqwidth() if chk.winfo_ismapped() else 100
                        chk_h = chk.winfo_reqheight() if chk.winfo_ismapped() else 24
                        # Центрируем чекбокс в колонке activate
                        chk_x = xa + (wa - chk_w) // 2
                        chk_y = ya + max(4, (ha - chk_h) // 2)
                        chk.place(x=chk_x, y=chk_y)
                    else:
                        chk.place_forget()
                except Exception:
                    chk.place_forget()
            except Exception:
                # защитимся от возможных ошибок при скролле
                try:
                    for w in ctrls:
                        w.place_forget()
                except Exception:
                    pass

    def _on_toggle_positioning(self) -> None:
        # Сообщим приложению о переключении режима позиционирования
        try:
            self._events.append('POSITIONING_ON' if self._positioning_var.get() else 'POSITIONING_OFF')
        except Exception:
            pass

    def _on_toggle_active(self, entry_id: str, entry_type: str, var: tk.BooleanVar) -> None:
        try:
            update_entry(entry_id, entry_type, {'active': bool(var.get())})
            # отправим событие, чтобы перезагрузить матчеры слоем приложения
            self._events.append('LIBRARY_UPDATED')
        except Exception:
            pass

    def _on_position_entry_by_id(self, entry_id: str, entry_type: str) -> None:
        # Найдём запись в библиотеке
        data = load_library()
        bucket = 'buffs' if entry_type == 'buff' else 'debuffs'
        item = None
        for it in data.get(bucket, []):
            if it.get('id') == entry_id:
                item = it
                break
        if item is None:
            return
        path = item.get('image_path') or ''
        pos = item.get('position', {'left': 0, 'top': 0})
        size = item.get('size', {'width': 96, 'height': 96})
        try:
            from src.ui.icon_positioner import position_icon
            result = position_icon(self._root, path, int(pos.get('left', 0)), int(pos.get('top', 0)), int(size.get('width', 96)), int(size.get('height', 96)))
        except Exception:
            result = None
        if result is None:
            return
        left, top, width, height = result
        try:
            update_entry(entry_id, entry_type, {
                'left': int(left),
                'top': int(top),
                'width': int(width),
                'height': int(height),
            })
            self._events.append('LIBRARY_UPDATED')
        except Exception:
            pass