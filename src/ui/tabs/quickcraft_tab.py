"""Quick craft tab for positioning currency captures."""
import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from src.i18n.locale import t
from src.ui.styles import BG_COLOR, FG_COLOR
from src.quickcraft.hotkeys import format_hotkey_display, normalize_hotkey_name, keysym_to_hotkey

_HOTKEY_GROUPS = {
    'Function keys': ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'],
    'Numbers': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
    'Letters': list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    'Navigation': ['UP', 'DOWN', 'LEFT', 'RIGHT', 'HOME', 'END', 'PAGE_UP', 'PAGE_DOWN', 'INSERT', 'DELETE'],
    'Controls': ['SPACE', 'TAB', 'ENTER', 'ESC', 'SHIFT', 'CTRL', 'ALT', 'CAPS_LOCK'],
}

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageTk = None


class QuickCraftTab:
    """Tab responsible for quick craft currency positioning."""

    def __init__(
        self,
        parent: tk.Frame,
        on_toggle_positioning: Callable[[bool], None],
        on_set_hotkey: Callable[[str], None],
        on_clear_hotkey: Callable[[str], None],
        on_reset_position: Callable[[str], None],
    ) -> None:
        self.frame = parent
        self._on_toggle_positioning = on_toggle_positioning
        self._on_set_hotkey = on_set_hotkey
        self._on_clear_hotkey = on_clear_hotkey
        self._on_reset_position = on_reset_position

        self._search_var = tk.StringVar(value='')
        self._positioning_var = tk.BooleanVar(value=False)
        self._tree_images: Dict[str, tk.PhotoImage] = {}
        self._row_controls: Dict[str, tk.Label] = {}
        self._prompt_frame: tk.Frame | None = None
        self._prompt_var = tk.StringVar(value='')
        self._selector_frame: Optional[tk.Frame] = None
        self._selector_callback: Optional[Callable[[str], None]] = None
        self._selector_cancel_btn: Optional[ttk.Button] = None
        self._selector_canvas: Optional[tk.Canvas] = None
        self._selector_window_id: Optional[int] = None
        self._capture_active: bool = False
        self._capture_callback: Optional[Callable[[str], None]] = None
        self._capture_top: Optional[tk.Tk] = None

        self._create_widgets()
        

    def _create_widgets(self) -> None:
        # Description
        try:
            ttk.Label(self.frame, text=t('desc.quickcraft', 'Position currency overlay windows and set a global hotkey for showing them near the cursor.'), style='Subtitle.TLabel').pack(anchor='w', padx=12, pady=(8, 4))
        except Exception:
            pass

        controls = tk.Frame(self.frame, bg=BG_COLOR)
        controls.pack(fill='x', padx=12, pady=12)

        self._chk_positioning = ttk.Checkbutton(
            controls,
            text=t('quickcraft.currency_positioning', 'Currency positioning'),
            variable=self._positioning_var,
            command=lambda: self._on_toggle_positioning(bool(self._positioning_var.get())),
            style='ToggleGray.TCheckbutton',
        )
        self._chk_positioning.pack(side='left')

        btn_spacer = tk.Frame(controls, bg=BG_COLOR)
        btn_spacer.pack(side='left', padx=(12, 0))

        self._btn_set_hotkey = ttk.Button(
            controls,
            text=t('quickcraft.set_hotkey', 'Set hotkey'),
            command=self._invoke_set_hotkey,
            style='Action.TButton',
        )
        self._btn_set_hotkey.pack(side='left')

        self._btn_clear_hotkey = ttk.Button(
            controls,
            text=t('quickcraft.clear_hotkey', 'Clear hotkey'),
            command=self._invoke_clear_hotkey,
            style='Action.TButton',
        )
        self._btn_clear_hotkey.pack(side='left', padx=(8, 0))

        self._btn_reset_pos = ttk.Button(
            controls,
            text=t('quickcraft.reset_position', 'Reset position'),
            command=self._invoke_reset_position,
            style='Action.TButton',
        )
        self._btn_reset_pos.pack(side='left', padx=(8, 0))

        self._lbl_global_hotkey_var = tk.StringVar(value='')
        self._lbl_global_hotkey = ttk.Label(
            controls,
            textvariable=self._lbl_global_hotkey_var,
            style='Prompt.TLabel',
        )
        self._lbl_global_hotkey.pack(side='left', padx=(12, 0))

        search_frame = tk.Frame(self.frame, bg=BG_COLOR)
        search_frame.pack(fill='x', padx=12, pady=(0, 12))

        self._lbl_search = tk.Label(
            search_frame,
            text=t('currency.search', 'Search'),
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=('Segoe UI', 9),
        )
        self._lbl_search.pack(side='left', padx=(0, 8))

        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        search_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))

        self._btn_clear = ttk.Button(
            search_frame,
            text=t('button.clear', 'Clear'),
            command=lambda: self._search_var.set(''),
            style='Action.TButton',
        )
        self._btn_clear.pack(side='left')

        self._aux_container = tk.Frame(self.frame, bg=BG_COLOR)
        self._aux_container.pack(fill='x', padx=12, pady=(0, 12))

        prompt = ttk.Frame(self._aux_container, padding=(12, 8), style='Prompt.TFrame')
        prompt.pack(fill='x', pady=(0, 8))
        self._prompt_frame = prompt

        ttk.Label(
            prompt,
            textvariable=self._prompt_var,
            style='Prompt.TLabel',
            wraplength=480,
            justify='left',
        ).pack(anchor='w')

        prompt.pack_forget()
        self._create_selector_panel()

        tree_frame = tk.Frame(self.frame, bg=BG_COLOR)
        tree_frame.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        self._tree = ttk.Treeview(
            tree_frame,
            columns=('preview', 'name', 'interface', 'hotkey', 'active'),
            show='tree headings',
            selectmode='browse',
            style='Currency.Treeview',
        )

        self._tree.heading('#0', text='')
        self._tree.heading('preview', text='')
        self._tree.heading('name', text=t('currency.name', 'Name'))
        self._tree.heading('interface', text=t('currency.interface', 'Interface'))
        self._tree.heading('hotkey', text=t('quickcraft.hotkey', 'Hotkey'))
        self._tree.heading('active', text=t('actions.activate', 'Activate'))

        self._tree.column('#0', width=0, stretch=False)
        self._tree.column('preview', width=70, stretch=False)
        self._tree.column('name', width=220, stretch=False)
        self._tree.column('interface', width=160, stretch=False)
        self._tree.column('hotkey', width=140, stretch=False)
        self._tree.column('active', width=100, stretch=False, anchor='center')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical')

        def on_scroll(*args) -> None:
            try:
                vsb.set(*args)
            finally:
                self._position_row_controls()

        self._tree.configure(yscrollcommand=on_scroll)
        vsb.configure(command=self._tree.yview)

        self._tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._tree.bind('<Configure>', lambda _: self._position_row_controls())


    def get_search_var(self) -> tk.StringVar:
        return self._search_var

    def get_positioning_var(self) -> tk.BooleanVar:
        return self._positioning_var

    def set_positioning(self, enabled: bool) -> None:
        self._positioning_var.set(bool(enabled))

    def reload(self, currencies: List[Dict], positions: Dict[str, Dict[str, object]]) -> None:
        query = self._search_var.get().strip().lower()
        for item in self._tree.get_children():
            self._tree.delete(item)

        for label in self._row_controls.values():
            try:
                label.place_forget()
                label.destroy()
            except Exception:
                pass
        self._row_controls.clear()
        self._tree_images.clear()

        for entry in currencies:
            if query:
                haystack = f"{entry.get('name', '')} {entry.get('interface', '')}".lower()
                if query not in haystack:
                    continue

            iid = entry.get('id')
            if not iid:
                continue

            capture = entry.get('capture', {}) or {}
            # Global hotkey only: do not show per-item hotkeys in the list
            hotkey_display = ''
            preview = self._make_preview(entry.get('image_path'), capture)
            if preview is not None:
                self._tree_images[iid] = preview

            values = (
                '',
                entry.get('name', ''),
                entry.get('interface', ''),
                hotkey_display,
                '✔' if entry.get('active') else '✖',
            )
            self._tree.insert('', 'end', iid=iid, values=values, image='')

            idx = len(self._tree.get_children(''))
            tag = 'odd' if (idx % 2 == 1) else 'even'
            try:
                self._tree.item(iid, tags=(tag,))
                self._tree.tag_configure('odd', background='#f9fafb')
                self._tree.tag_configure('even', background='#ffffff')
            except Exception:
                pass

            if preview is not None:
                label = tk.Label(self._tree, image=preview, borderwidth=0, relief='flat')
                self._row_controls[iid] = label

            # No extra visuals over images

        self._position_row_controls()

    def refresh_texts(self) -> None:
        try:
            self._chk_positioning.configure(text=t('quickcraft.currency_positioning', 'Currency positioning'))
            self._lbl_search.configure(text=t('currency.search', 'Search'))
            self._btn_clear.configure(text=t('button.clear', 'Clear'))
            self._btn_set_hotkey.configure(text=t('quickcraft.set_hotkey', 'Set hotkey'))
            self._btn_clear_hotkey.configure(text=t('quickcraft.clear_hotkey', 'Clear hotkey'))
            self._btn_reset_pos.configure(text=t('quickcraft.reset_position', 'Reset position'))
            self._tree.heading('name', text=t('currency.name', 'Name'))
            self._tree.heading('interface', text=t('currency.interface', 'Interface'))
            self._tree.heading('hotkey', text=t('quickcraft.hotkey', 'Hotkey'))
            self._tree.heading('active', text=t('actions.activate', 'Activate'))
            if self._prompt_frame is not None and self._prompt_frame.winfo_ismapped():
                self._prompt_var.set(t('quickcraft.hotkey_prompt', 'Click a button to assign a hotkey.'))
            if self._selector_cancel_btn is not None:
                self._selector_cancel_btn.configure(text=t('button.cancel', 'Cancel'))
        except Exception:
            pass

    def _position_row_controls(self) -> None:
        for iid, label in list(self._row_controls.items()):
            try:
                bbox = self._tree.bbox(iid, 'preview')
                if not bbox:
                    label.place_forget()
                    continue

                x, y, width, height = bbox
                lw = label.winfo_reqwidth() or 64
                lh = label.winfo_reqheight() or 64
                tags = self._tree.item(iid, 'tags')
                bg = '#f9fafb' if ('odd' in tags) else '#ffffff'
                label.configure(bg=bg)
                label.place(
                    x=x + max(0, (width - lw) // 2),
                    y=y + max(2, (height - lh) // 2),
                )

                # No extra overlays to position
            except Exception:
                try:
                    label.place_forget()
                except Exception:
                    pass

    def _invoke_set_hotkey(self) -> None:
        # Ensure a row is selected; auto-select first if none
        iid = self.get_selected_id()
        if not iid:
            children = self._tree.get_children('')
            if children:
                iid = children[0]
                try:
                    self._tree.selection_set(iid)
                    self._tree.focus(iid)
                except Exception:
                    pass
        if iid and callable(self._on_set_hotkey):
            self._on_set_hotkey(iid)
        elif not iid:
            self.show_hotkey_prompt(t('quickcraft.no_items', 'No items to assign. Add a currency first.'))

    def _invoke_clear_hotkey(self) -> None:
        # Clear GLOBAL hotkey regardless of selection
        if callable(self._on_clear_hotkey):
            self._on_clear_hotkey('')

    def _invoke_reset_position(self) -> None:
        iid = self.get_selected_id()
        if iid and callable(self._on_reset_position):
            self._on_reset_position(iid)

    def get_selected_id(self) -> str:
        selection = self._tree.selection()
        return selection[0] if selection else ''

    def show_hotkey_prompt(self, message: str) -> None:
        if self._prompt_frame is None:
            return
        self._prompt_var.set(message)
        if not self._prompt_frame.winfo_ismapped():
            try:
                self._prompt_frame.pack(fill='x', pady=(0, 8))
            except Exception:
                pass

    def hide_hotkey_prompt(self) -> None:
        if self._prompt_frame is None:
            return
        try:
            self._prompt_frame.pack_forget()
            self._prompt_var.set('')
        except Exception:
            pass
        self.hide_hotkey_selector()

    def start_hotkey_capture(self, callback: Callable[[str], None]) -> None:
        """Begin capture of the next key press and call callback with normalized token."""
        self.hide_hotkey_selector()
        self.show_hotkey_prompt(t('quickcraft.press_key', 'Press a key...'))
        self._capture_callback = callback
        self._capture_active = True
        try:
            self._capture_top = self.frame.winfo_toplevel()
        except Exception:
            self._capture_top = None
        top = self._capture_top
        if top is not None:
            try:
                top.bind_all('<KeyPress>', self._on_capture_key, add='+')
                top.bind_all('<Escape>', self._on_capture_cancel, add='+')
            except Exception:
                pass

    def _on_capture_key(self, event) -> str:
        if not self._capture_active:
            return ''
        keysym = getattr(event, 'keysym', '')
        if not keysym:
            return 'break'
        token = keysym_to_hotkey(keysym) or ''
        display = format_hotkey_display(token)
        if display:
            try:
                self._prompt_var.set(f"Captured: {display}")
            except Exception:
                pass
        cb = self._capture_callback
        self._stop_hotkey_capture()
        if cb:
            try:
                cb(token)
            except Exception:
                pass
        return 'break'

    def _on_capture_cancel(self, _event=None) -> str:
        if not self._capture_active:
            return ''
        self._stop_hotkey_capture()
        return 'break'

    def _stop_hotkey_capture(self) -> None:
        top = self._capture_top
        if top is not None:
            try:
                top.unbind_all('<KeyPress>')
                top.unbind_all('<Escape>')
            except Exception:
                pass
        self._capture_active = False
        self._capture_callback = None

    def _create_selector_panel(self) -> None:
        parent = getattr(self, '_aux_container', self.frame)
        container = ttk.Frame(parent, padding=(12, 4), style='Prompt.TFrame')
        container.pack(fill='x')
        try:
            container.pack_propagate(False)
        except Exception:
            pass
        canvas = tk.Canvas(container, height=220, highlightthickness=0, borderwidth=0, bg=BG_COLOR)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        content = ttk.Frame(canvas, style='Prompt.TFrame')

        def _on_content_configure(event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox('all'))
            except Exception:
                pass

        content.bind('<Configure>', _on_content_configure)
        window_id = canvas.create_window((0, 0), window=content, anchor='nw')

        def _on_canvas_configure(ev):
            try:
                canvas.itemconfigure(window_id, width=ev.width)
            except Exception:
                pass
        canvas.bind('<Configure>', _on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set, yscrollincrement=24)

        for group_name, keys in _HOTKEY_GROUPS.items():
            group = ttk.LabelFrame(content, text=group_name, padding=(12, 8))
            group.pack(fill='x', pady=(0, 8))
            for idx, key in enumerate(keys):
                btn = ttk.Button(
                    group,
                    text=key,
                    width=6,
                    command=lambda value=key: self._on_hotkey_choice(value),
                    style='Action.TButton',
                )
                btn.grid(row=idx // 6, column=idx % 6, padx=4, pady=4, sticky='nsew')
            for col in range(6):
                group.columnconfigure(col, weight=1)

        control_row = ttk.Frame(content, padding=(0, 4), style='Prompt.TFrame')
        control_row.pack(fill='x')
        cancel_btn = ttk.Button(
            control_row,
            text=t('button.cancel', 'Cancel'),
            command=self.cancel_hotkey_selector,
            style='Action.TButton',
            width=12,
        )
        cancel_btn.pack(side='right', padx=(4, 0))

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        container.pack_forget()

        self._selector_frame = container
        self._selector_cancel_btn = cancel_btn
        self._selector_canvas = canvas
        self._selector_window_id = window_id

        # Mouse wheel handling (Windows / X11)
        def _mw(event):
            delta = 0
            if hasattr(event, 'delta') and event.delta:
                delta = int(event.delta)
            elif getattr(event, 'num', None) in (4, 5):
                delta = 120 if event.num == 4 else -120
            units = -1 if delta > 0 else 1
            try:
                canvas.yview_scroll(units, 'units')
            except Exception:
                pass
            return 'break'

        def _bind_wheel(_=None):
            try:
                canvas.bind_all('<MouseWheel>', _mw, add='+')
                canvas.bind_all('<Button-4>', _mw, add='+')
                canvas.bind_all('<Button-5>', _mw, add='+')
            except Exception:
                pass

        def _unbind_wheel(_=None):
            try:
                canvas.unbind_all('<MouseWheel>')
                canvas.unbind_all('<Button-4>')
                canvas.unbind_all('<Button-5>')
            except Exception:
                pass

        content.bind('<Enter>', _bind_wheel)
        content.bind('<Leave>', _unbind_wheel)
        canvas.bind('<Enter>', _bind_wheel)
        canvas.bind('<Leave>', _unbind_wheel)

    def show_hotkey_selector(self, callback: Callable[[str], None]) -> None:
        self._selector_callback = callback
        if self._selector_frame is None:
            return
        try:
            self._selector_frame.pack(fill='x', pady=(0, 12))
        except Exception:
            pass

    def hide_hotkey_selector(self) -> None:
        if self._selector_frame is None:
            return
        try:
            self._selector_frame.pack_forget()
        except Exception:
            pass
        self._selector_callback = None

    def cancel_hotkey_selector(self) -> None:
        self.hide_hotkey_selector()
        self.hide_hotkey_prompt()

    def _on_hotkey_choice(self, token: str) -> None:
        if not token:
            return
        if self._selector_callback:
            self._selector_callback(token)
        self.hide_hotkey_selector()
        self.hide_hotkey_prompt()

    # No runtime active markers needed

    def set_global_hotkey_label(self, hotkey: str) -> None:
        hotkey_display = format_hotkey_display(hotkey)
        if hotkey_display:
            self._lbl_global_hotkey_var.set(f"Global: {hotkey_display}")
        else:
            self._lbl_global_hotkey_var.set(t('quickcraft.no_global', 'Global: —'))

    def _make_preview(self, image_path: str, capture: Dict) -> tk.PhotoImage | None:
        path = (image_path or '').strip()
        if path and os.path.isfile(path):
            if Image is not None and ImageTk is not None:
                try:
                    img = Image.open(path).convert('RGBA')
                    img.thumbnail((64, 64), Image.LANCZOS)
                    return ImageTk.PhotoImage(img)
                except Exception:
                    pass
            try:
                photo = tk.PhotoImage(file=path)
                # Downscale large images using subsample if available
                try:
                    width = photo.width()
                    height = photo.height()
                    max_side = max(width, height)
                    if max_side > 64:
                        factor = max(1, max_side // 64)
                        photo = photo.subsample(factor, factor)
                except Exception:
                    pass
                return photo
            except Exception:
                pass

        width = max(1, int(capture.get('width', 32)))
        height = max(1, int(capture.get('height', 32)))
        try:
            img = tk.PhotoImage(width=width, height=height)
            img.put('#10B981', to=(0, 0, width, height))
            return img
        except Exception:
            return None
