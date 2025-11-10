"""UI tab for managing currency entries."""
import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from src.currency.library import load_currencies
from src.i18n.locale import t
from src.ui.styles import BG_COLOR, FG_COLOR

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageTk = None


class CurrencyTab:
    """Tab responsible for displaying and controlling currencies."""

    def __init__(
        self,
        parent: tk.Frame,
        on_add: Callable[[], None],
        on_edit: Callable[[], None],
        on_delete: Callable[[], None],
        on_toggle_active: Callable[[str, tk.BooleanVar], None],
    ) -> None:
        self.frame = parent
        self._on_add = on_add
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_toggle_active = on_toggle_active

        self._search_var = tk.StringVar(value='')
        self._tree_images: Dict[str, tk.PhotoImage] = {}
        self._row_controls: Dict[str, tuple] = {}
        self._active_vars: Dict[str, tk.BooleanVar] = {}

        self._create_widgets()

    def _create_widgets(self) -> None:
        # Description
        try:
            ttk.Label(self.frame, text=t('desc.currency', 'Manage currency definitions and capture areas used by overlays.'), style='Subtitle.TLabel').pack(anchor='w', padx=12, pady=(8, 4))
        except Exception:
            pass
        controls = tk.Frame(self.frame, bg=BG_COLOR)
        controls.pack(fill='x', padx=12, pady=12)

        self._btn_add = ttk.Button(
            controls,
            text=t('currency.add', 'Add currency'),
            command=self._on_add,
            style='Modern.TButton',
        )
        self._btn_add.pack(side='left')

        self._btn_edit = ttk.Button(
            controls,
            text=t('currency.edit', 'Edit'),
            command=self._on_edit,
            style='Action.TButton',
        )
        self._btn_edit.pack(side='left', padx=(8, 0))

        self._btn_delete = ttk.Button(
            controls,
            text=t('currency.delete', 'Delete'),
            command=self._on_delete,
            style='Action.TButton',
        )
        self._btn_delete.pack(side='left', padx=(8, 0))

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

        tree_frame = tk.Frame(self.frame, bg=BG_COLOR)
        tree_frame.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        self._tree = ttk.Treeview(
            tree_frame,
            columns=('preview', 'name', 'interface', 'capture', 'activate'),
            show='tree headings',
            style='Currency.Treeview',
        )

        self._tree.heading('#0', text='')
        self._tree.heading('preview', text='')
        self._tree.heading('name', text=t('currency.name', 'Name'))
        self._tree.heading('interface', text=t('currency.interface', 'Interface'))
        self._tree.heading('capture', text=t('currency.area', 'Area'))
        self._tree.heading('activate', text=t('actions.activate', 'Activate'))

        self._tree.column('#0', width=0, stretch=False)
        self._tree.column('preview', width=70, stretch=False)
        self._tree.column('name', width=220, stretch=False)
        self._tree.column('interface', width=160, stretch=False)
        self._tree.column('capture', width=200, stretch=True)
        self._tree.column('activate', width=120, stretch=False, anchor='center')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical')

        def on_scroll(*args) -> None:
            try:
                vsb.set(*args)
            finally:
                self._position_row_controls()

        self._tree.configure(yscrollcommand=on_scroll)
        try:
            vsb.configure(command=self._tree.yview)
        except Exception:
            pass

        self._tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._tree.bind('<Double-1>', lambda _: self._on_edit())
        self._tree.bind('<Configure>', lambda _: self._position_row_controls())

    def get_search_var(self) -> tk.StringVar:
        return self._search_var

    def get_tree(self) -> ttk.Treeview:
        return self._tree

    def get_selected_id(self) -> str:
        selection = self._tree.selection()
        return selection[0] if selection else ''

    def reload(self, search_query: str = '') -> None:
        self._clear_tree()

        items = load_currencies()
        query = search_query.strip().lower()

        for item in items:
            if query:
                haystack = f"{item.get('name', '')} {item.get('interface', '')}".lower()
                if query not in haystack:
                    continue

            iid = item.get('id')
            if not iid:
                continue

            capture = item.get('capture', {}) or {}
            capture_text = (
                f"L:{int(capture.get('left', 0))} "
                f"T:{int(capture.get('top', 0))} "
                f"W:{int(capture.get('width', 0))} "
                f"H:{int(capture.get('height', 0))}"
            )

            image = self._make_thumbnail(item.get('image_path'))
            if image is not None:
                self._tree_images[iid] = image

            values = ('', item.get('name', ''), item.get('interface', ''), capture_text, '')
            self._tree.insert('', 'end', iid=iid, values=values, image=self._tree_images.get(iid))

            idx = len(self._tree.get_children(''))
            tag = 'odd' if (idx % 2 == 1) else 'even'
            try:
                self._tree.item(iid, tags=(tag,))
                self._tree.tag_configure('odd', background='#f9fafb')
                self._tree.tag_configure('even', background='#ffffff')
            except Exception:
                pass

            var = tk.BooleanVar(value=bool(item.get('active', False)))
            chk = ttk.Checkbutton(
                self._tree,
                variable=var,
                command=lambda entry_id=iid, state=var: self._on_toggle_active(entry_id, state),
                style='Toggle.TCheckbutton',
            )

            thumb = None
            if self._tree_images.get(iid) is not None:
                try:
                    thumb = tk.Label(self._tree, image=self._tree_images[iid], borderwidth=0, relief='flat')
                except Exception:
                    thumb = None

            if thumb is not None:
                self._row_controls[iid] = (chk, thumb)
            else:
                self._row_controls[iid] = (chk,)

            self._active_vars[iid] = var

        self._position_row_controls()

    def refresh_texts(self) -> None:
        try:
            self._btn_add.configure(text=t('currency.add', 'Add currency'))
            self._btn_edit.configure(text=t('currency.edit', 'Edit'))
            self._btn_delete.configure(text=t('currency.delete', 'Delete'))
            self._lbl_search.configure(text=t('currency.search', 'Search'))
            self._btn_clear.configure(text=t('button.clear', 'Clear'))
            self._tree.heading('name', text=t('currency.name', 'Name'))
            self._tree.heading('interface', text=t('currency.interface', 'Interface'))
            self._tree.heading('capture', text=t('currency.area', 'Area'))
            self._tree.heading('activate', text=t('actions.activate', 'Activate'))
        except Exception:
            pass

    def _clear_tree(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        for widgets in self._row_controls.values():
            for widget in widgets:
                try:
                    widget.place_forget()
                    widget.destroy()
                except Exception:
                    pass

        self._row_controls.clear()
        self._active_vars.clear()
        self._tree_images.clear()

    def _position_row_controls(self) -> None:
        for iid, widgets in self._row_controls.items():
            try:
                tags = self._tree.item(iid, 'tags')
                bg = '#f9fafb' if ('odd' in tags) else '#ffffff'

                # Preview image
                if len(widgets) > 1:
                    thumb = widgets[1]
                    bbox_preview = self._tree.bbox(iid, 'preview')
                    if bbox_preview:
                        x, y, width, height = bbox_preview
                        tw = thumb.winfo_reqwidth() or 64
                        th = thumb.winfo_reqheight() or 64
                        thumb.configure(bg=bg)
                        thumb.place(
                            x=x + max(0, (width - tw) // 2),
                            y=y + max(2, (height - th) // 2),
                        )
                    else:
                        thumb.place_forget()

                # Activate checkbox
                chk = widgets[0]
                bbox_activate = self._tree.bbox(iid, 'activate')
                if bbox_activate:
                    x, y, width, height = bbox_activate
                    chk_w = chk.winfo_reqwidth() or 90
                    chk_h = chk.winfo_reqheight() or 24
                    chk.place(
                        x=x + max(0, (width - chk_w) // 2),
                        y=y + max(4, (height - chk_h) // 2),
                    )
                else:
                    chk.place_forget()
            except Exception:
                for widget in widgets:
                    try:
                        widget.place_forget()
                    except Exception:
                        pass

    def _make_thumbnail(self, path: Optional[str]) -> Optional[tk.PhotoImage]:
        if not path:
            return None

        try:
            if not os.path.isfile(path):
                return None

            if Image is None or ImageTk is None:
                image = tk.PhotoImage(file=path)
                try:
                    width = image.width()
                    height = image.height()
                    max_side = max(width, height)
                    if max_side > 64:
                        factor = max(1, max_side // 64)
                        image = image.subsample(factor, factor)
                except Exception:
                    pass
                return image

            img = Image.open(path).convert('RGBA')
            img.thumbnail((64, 64), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None
