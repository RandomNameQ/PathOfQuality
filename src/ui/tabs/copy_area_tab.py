"""
Tab for managing copy area definitions.
"""
import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from src.buffs.library import load_library
from src.i18n.locale import t, get_lang
from src.ui.styles import BG_COLOR, FG_COLOR

try:
    from PIL import Image, ImageTk, ImageOps
except Exception:
    Image = None
    ImageTk = None
    ImageOps = None


class CopyAreaTab:
    """UI tab for managing copy areas."""

    def __init__(
        self,
        parent: tk.Frame,
        on_add: Callable[[], None],
        on_edit: Callable[[], None],
        on_toggle_active: Callable[[str, tk.BooleanVar], None],
    ) -> None:
        self.frame = parent
        self._on_add = on_add
        self._on_edit = on_edit
        self._on_toggle_active = on_toggle_active

        self._search_var = tk.StringVar(value='')
        self._tree_images: Dict[str, tk.PhotoImage] = {}
        self._row_controls: Dict[str, tuple] = {}
        self._active_vars: Dict[str, tk.BooleanVar] = {}

        self._create_widgets()

    def _create_widgets(self) -> None:
        controls = tk.Frame(self.frame, bg=BG_COLOR)
        controls.pack(fill='x', padx=12, pady=12)

        self._btn_add = ttk.Button(
            controls,
            text=t('copy_area.add', 'Add copy area'),
            command=self._on_add,
            style='Modern.TButton',
        )
        self._btn_add.pack(side='left')

        self._btn_edit = ttk.Button(
            controls,
            text=t('copy_area.edit', 'Edit'),
            command=self._on_edit,
            style='Action.TButton',
        )
        self._btn_edit.pack(side='left', padx=(8, 0))

        search = tk.Frame(self.frame, bg=BG_COLOR)
        search.pack(fill='x', padx=12, pady=(0, 12))

        self._lbl_search = tk.Label(
            search,
            text=t('copy_area.search', 'Search'),
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=('Segoe UI', 9),
        )
        self._lbl_search.pack(side='left', padx=(0, 8))

        search_entry = ttk.Entry(
            search,
            textvariable=self._search_var,
            font=('Segoe UI', 9),
            width=30,
        )
        search_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))

        self._btn_clear = ttk.Button(
            search,
            text=t('button.clear', 'Clear'),
            command=lambda: self._search_var.set(''),
            style='Action.TButton',
        )
        self._btn_clear.pack(side='left')

        tree_frame = tk.Frame(self.frame, bg=BG_COLOR)
        tree_frame.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        self._tree = ttk.Treeview(
            tree_frame,
            columns=('name', 'links', 'activate', 'position', 'size'),
            show='tree headings',
            style='CopyArea.Treeview',
        )

        self._tree.heading('#0', text='')
        self._tree.heading('name', text=t('copy_area.name', 'Name'))
        self._tree.heading('links', text=t('copy_area.links', 'Linked items'))
        self._tree.heading('activate', text=t('actions.activate', 'Activate'))
        self._tree.heading('position', text=t('copy_area.position', 'Position'))
        self._tree.heading('size', text=t('copy_area.size', 'Size'))

        self._tree.column('#0', width=70, stretch=False, minwidth=60)
        self._tree.column('name', width=220, stretch=False)
        self._tree.column('links', width=280, stretch=True)
        self._tree.column('activate', width=120, stretch=False, anchor='center')
        self._tree.column('position', width=120, stretch=False)
        self._tree.column('size', width=120, stretch=False)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical')

        def on_scroll(*args):
            try:
                vsb.set(*args)
            except Exception:
                pass
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

    def reload(self, search_query: str = '') -> None:
        data = load_library()
        buff_names = self._build_name_map(data.get('buffs', []))
        debuff_names = self._build_name_map(data.get('debuffs', []))

        self._clear_tree()

        query = search_query.strip().lower()

        for idx, area in enumerate(data.get('copy_areas', [])):
            if query and not self._matches(area, query):
                continue

            iid = area.get('id')
            name = self._get_localized(area.get('name', {}))
            refs = area.get('references', {})
            buff_labels = [buff_names.get(bid, bid) for bid in refs.get('buffs', [])]
            debuff_labels = [debuff_names.get(did, did) for did in refs.get('debuffs', [])]

            links_parts: List[str] = []
            if buff_labels:
                links_parts.append(t('tab.buffs', 'Buffs') + ': ' + ', '.join(buff_labels))
            if debuff_labels:
                links_parts.append(t('tab.debuffs', 'Debuffs') + ': ' + ', '.join(debuff_labels))
            links_text = '\n'.join(links_parts) if links_parts else '—'

            position = area.get('position', {})
            size = area.get('size', {})
            pos_text = f"L:{int(position.get('left', 0))} / T:{int(position.get('top', 0))}"
            size_text = f"{int(size.get('width', 64))}×{int(size.get('height', 64))}"

            thumb = self._make_thumbnail(area.get('image_path'))
            if thumb is not None and iid:
                self._tree_images[iid] = thumb

            values = (name or '—', links_text, '', pos_text, size_text)
            self._tree.insert(
                '',
                'end',
                iid=iid,
                text='',
                image=self._tree_images.get(iid),
                values=values,
            )

            try:
                tag = 'odd' if ((len(self._tree.get_children('')) % 2) == 1) else 'even'
                self._tree.item(iid, tags=(tag,))
                self._tree.tag_configure('odd', background='#f9fafb')
                self._tree.tag_configure('even', background='#ffffff')
            except Exception:
                pass

            var = tk.BooleanVar(value=bool(area.get('active', False)))
            chk = ttk.Checkbutton(
                self._tree,
                variable=var,
                command=lambda i=iid, v=var: self._on_toggle_active(i, v),
                style='Toggle.TCheckbutton',
                text='',
            )
            self._active_vars[iid] = var
            self._row_controls[iid] = (chk,)

        self._position_row_controls()

    def _matches(self, area: Dict, query: str) -> bool:
        names = area.get('name', {})
        for value in names.values():
            if query in str(value).lower():
                return True
        return False

    def _build_name_map(self, items: List[Dict]) -> Dict[str, str]:
        lang = get_lang()
        mapping: Dict[str, str] = {}
        for item in items:
            iid = item.get('id')
            if not iid:
                continue
            name = item.get('name', {})
            label = name.get(lang) or name.get('en') or iid
            mapping[iid] = label
        return mapping

    def _get_localized(self, data: Dict[str, str]) -> str:
        lang = get_lang()
        return data.get(lang) or data.get('en') or next(iter(data.values()), '')

    def _make_thumbnail(self, path: Optional[str]) -> Optional[tk.PhotoImage]:
        try:
            if not path or not os.path.isfile(path):
                return None
            if Image is None or ImageTk is None:
                return tk.PhotoImage(file=path)
            img = Image.open(path).convert('RGBA')
            img.thumbnail((64, 64), Image.LANCZOS)
            if ImageOps is not None:
                try:
                    img = ImageOps.expand(img, border=0, fill=(0, 0, 0, 0))
                except Exception:
                    pass
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _clear_tree(self) -> None:
        for child in self._tree.get_children():
            self._tree.delete(child)
        for ctrls in list(self._row_controls.values()):
            for widget in ctrls:
                try:
                    widget.place_forget()
                    widget.destroy()
                except Exception:
                    pass
        self._row_controls.clear()
        self._active_vars.clear()
        self._tree_images.clear()

    def _position_row_controls(self) -> None:
        for iid, ctrls in self._row_controls.items():
            try:
                bbox = self._tree.bbox(iid, 'activate')
                if not bbox:
                    for widget in ctrls:
                        widget.place_forget()
                    continue

                tags = self._tree.item(iid, 'tags')
                bg_color = '#f9fafb' if ('odd' in tags) else '#ffffff'

                chk = ctrls[0]
                try:
                    chk.configure(style='Toggle.TCheckbutton')
                except Exception:
                    pass
                chk.configure(takefocus=0)

                x, y, w, h = bbox
                chk_w = chk.winfo_reqwidth() or 90
                chk_h = chk.winfo_reqheight() or 24
                chk_x = x + max(4, (w - chk_w) // 2)
                chk_y = y + max(4, (h - chk_h) // 2)
                try:
                    chk.configure(background=bg_color)
                except Exception:
                    pass
                chk.place(x=chk_x, y=chk_y)
            except Exception:
                try:
                    for widget in ctrls:
                        widget.place_forget()
                except Exception:
                    pass

    def position_controls(self) -> None:
        self._position_row_controls()

    def get_search_var(self) -> tk.StringVar:
        return self._search_var

    def get_tree(self) -> ttk.Treeview:
        return self._tree

    def get_selected_id(self) -> str:
        sel = self._tree.selection()
        return sel[0] if sel else ''

    def refresh_texts(self) -> None:
        try:
            self._btn_add.configure(text=t('copy_area.add', 'Add copy area'))
            self._btn_edit.configure(text=t('copy_area.edit', 'Edit'))
            self._lbl_search.configure(text=t('copy_area.search', 'Search'))
            self._btn_clear.configure(text=t('button.clear', 'Clear'))
            self._tree.heading('name', text=t('copy_area.name', 'Name'))
            self._tree.heading('links', text=t('copy_area.links', 'Linked items'))
            self._tree.heading('activate', text=t('actions.activate', 'Activate'))
            self._tree.heading('position', text=t('copy_area.position', 'Position'))
            self._tree.heading('size', text=t('copy_area.size', 'Size'))
        except Exception:
            pass


