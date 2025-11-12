"""
Reusable tree view component for buffs/debuffs library.
"""
import os
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Callable, Optional, Tuple
from src.i18n.locale import t, get_lang
from src.ui.styles import BG_COLOR, FG_COLOR

try:
    from PIL import Image, ImageTk, ImageOps
except Exception:
    Image = None
    ImageTk = None
    ImageOps = None


class LibraryTreeView:
    """Tree view for displaying and managing buff/debuff entries."""
    
    def __init__(
        self, 
        parent: tk.Frame, 
        entry_type: str,
        on_add: Callable,
        on_edit: Callable,
        on_delete: Callable,
        on_toggle_active: Callable
    ) -> None:
        """
        Initialize library tree view.
        
        Args:
            parent: Parent frame
            entry_type: Either 'buff' or 'debuff'
            on_add: Callback for add button
            on_edit: Callback for edit button
            on_toggle_active: Callback for active toggle
        """
        self.frame = parent
        self.entry_type = entry_type
        self._on_add = on_add
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_toggle_active = on_toggle_active
        
        self._search_var = tk.StringVar(value='')
        self._entry_thumbs: Dict[str, tk.PhotoImage] = {}
        self._row_controls: Dict[str, Tuple] = {}
        self._active_vars: Dict[str, tk.BooleanVar] = {}
        
        self._create_widgets()
        
    def _create_widgets(self) -> None:
        """Create tree view widgets."""
        # Control buttons
        controls = tk.Frame(self.frame, bg=BG_COLOR)
        controls.pack(fill='x', padx=12, pady=12)
        
        self._btn_add = ttk.Button(
            controls, 
            text=t('buffs.add', 'Add'),
            command=self._on_add,
            style='Modern.TButton'
        )
        self._btn_add.pack(side='left')
        
        self._btn_edit = ttk.Button(
            controls, 
            text=t('buffs.edit', 'Edit'),
            command=self._on_edit,
            style='Action.TButton'
        )
        self._btn_edit.pack(side='left', padx=(8, 0))

        self._btn_delete = ttk.Button(
            controls,
            text=t('library.delete', 'Delete'),
            command=self._on_delete,
            style='Action.TButton'
        )
        self._btn_delete.pack(side='left', padx=(8, 0))
        
        # Search box
        search = tk.Frame(self.frame, bg=BG_COLOR)
        search.pack(fill='x', padx=12, pady=(0, 12))
        
        self._lbl_search = tk.Label(
            search, 
            text=t('buffs.search', 'Search'),
            bg=BG_COLOR, 
            fg=FG_COLOR, 
            font=('Segoe UI', 9)
        )
        self._lbl_search.pack(side='left', padx=(0, 8))
        
        search_entry = ttk.Entry(
            search, 
            textvariable=self._search_var,
            font=('Segoe UI', 9),
            width=30
        )
        search_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        
        self._btn_clear_search = ttk.Button(
            search, 
            text=t('button.clear', 'Clear'),
            command=lambda: self._search_var.set(''),
            style='Action.TButton'
        )
        self._btn_clear_search.pack(side='left')
        
        # Tree view
        tree_frame = tk.Frame(self.frame, bg=BG_COLOR)
        tree_frame.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        
        style_name = 'BuffTree.Treeview' if self.entry_type == 'buff' else 'DebuffTree.Treeview'
        self._tree = ttk.Treeview(
            tree_frame, 
            style=style_name,
            columns=('icon', 'name', 'activate', 'desc'),
            show='tree headings'
        )
        
        self._tree.heading('#0', text='')
        self._tree.heading('icon', text='')
        self._tree.heading('name', text=t('buffs.name', 'Name'))
        self._tree.heading('activate', text='')
        self._tree.heading('desc', text=t('buffs.description', 'Description'))
        
        self._tree.column('#0', width=0, stretch=False, minwidth=0)
        self._tree.column('icon', width=70, stretch=False, anchor='center')
        self._tree.column('name', width=200, stretch=False)
        self._tree.column('activate', width=120, stretch=False, anchor='center')
        self._tree.column('desc', width=380, stretch=True)
        
        # Scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient='vertical')
        
        def on_scroll(*args):
            try:
                vsb.set(*args)
            except Exception:
                pass
            try:
                self._position_row_controls()
            except Exception:
                pass
                
        self._tree.configure(yscrollcommand=on_scroll)
        try:
            vsb.configure(command=self._tree.yview)
        except Exception:
            pass
            
        self._tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        # Bind events
        self._tree.bind('<Double-1>', lambda e: self._on_edit())
        self._tree.bind('<Configure>', lambda e: self._position_row_controls())
        
    def get_search_var(self) -> tk.StringVar:
        """Get search text variable."""
        return self._search_var
        
    def get_tree(self) -> ttk.Treeview:
        """Get tree view widget."""
        return self._tree
        
    def clear(self) -> None:
        """Clear all tree items and controls."""
        # Clear tree
        for child in self._tree.get_children():
            self._tree.delete(child)
            
        # Remove old controls
        for cid, ctrls in list(self._row_controls.items()):
            for w in ctrls:
                try:
                    w.place_forget()
                    w.destroy()
                except Exception:
                    pass
                    
        self._row_controls.clear()
        self._active_vars.clear()
        
    def add_item(self, item: Dict) -> None:
        """
        Add an item to the tree.
        
        Args:
            item: Item dictionary from library
        """
        lang = get_lang()
        name = item.get('name', {}).get(lang) or item.get('name', {}).get('en') or '—'
        desc = item.get('description', {}).get(lang) or item.get('description', {}).get('en') or ''
        
        # Truncate long description
        if len(desc) > 100:
            truncated = desc[:97]
            last_space = max(truncated.rfind(' '), truncated.rfind('\n'))
            if last_space > 80:
                desc = truncated[:last_space] + '...'
            else:
                desc = truncated + '...'
                
        # Create thumbnail
        thumb = self._make_thumbnail(item.get('image_path', ''))
        if thumb is not None:
            self._entry_thumbs[item.get('id')] = thumb
            
        iid = item.get('id')
        self._tree.insert('', 'end', iid=iid, text='', values=('', name, '', desc))
        
        # Alternating row colors
        try:
            idx = len(self._tree.get_children(''))
            tag = 'odd' if (idx % 2 == 1) else 'even'
            self._tree.item(iid, tags=(tag,))
            self._tree.tag_configure('odd', background='#f9fafb')
            self._tree.tag_configure('even', background='#ffffff')
        except Exception:
            pass
            
        # Create row controls
        var = tk.BooleanVar(value=bool(item.get('active', False)))
        chk = ttk.Checkbutton(
            self._tree, 
            text=t('actions.activate', 'Activate'),
            variable=var,
            command=lambda i=iid, v=var: self._on_toggle_active(i, self.entry_type, v)
        )
        
        # Thumbnail label
        thumb_lbl = None
        try:
            ph = self._entry_thumbs.get(iid)
            if ph is not None:
                bg_color = '#f9fafb' if (idx % 2 == 1) else '#ffffff'
                thumb_lbl = tk.Label(
                    self._tree, 
                    image=ph, 
                    bg=bg_color, 
                    relief='flat', 
                    borderwidth=0
                )
        except Exception:
            thumb_lbl = None
            
        self._row_controls[iid] = (chk, thumb_lbl) if thumb_lbl is not None else (chk,)
        self._active_vars[iid] = var
        
    def _make_thumbnail(self, path: str) -> Optional[tk.PhotoImage]:
        """Create thumbnail from image path."""
        try:
            if not path or not os.path.isfile(path):
                return None
                
            if Image is None or ImageTk is None:
                # Fallback: use Tk PhotoImage
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
            
            if ImageOps is not None:
                try:
                    img = ImageOps.expand(img, border=(0, 0, 0, 0), fill=(0, 0, 0, 0))
                except Exception:
                    img = ImageOps.expand(img, border=(0, 0, 0, 0), fill='#ffffff')
                    
            return ImageTk.PhotoImage(img)
        except Exception:
            return None
            
    def _position_row_controls(self) -> None:
        """Position row controls (checkboxes and thumbnails)."""
        for iid, ctrls in self._row_controls.items():
            try:
                bbox_icon = self._tree.bbox(iid, 'icon')
                if not bbox_icon:
                    for w in ctrls:
                        w.place_forget()
                    continue
                    
                tags = self._tree.item(iid, 'tags')
                bg_color = '#f9fafb' if 'odd' in tags else '#ffffff'
                
                # Thumbnail in icon column
                if len(ctrls) > 1 and ctrls[1] is not None:
                    thumb = ctrls[1]
                    try:
                        xi, yi, wi, hi = bbox_icon
                        tw = thumb.winfo_reqwidth() or 64
                        th = thumb.winfo_reqheight() or 64
                        tx = xi + (wi - tw) // 2
                        ty = yi + max(2, (hi - th) // 2)
                        thumb.configure(bg=bg_color)
                        thumb.place(x=tx, y=ty)
                    except Exception:
                        thumb.place_forget()
                        
                # Checkbox in activate column
                chk = ctrls[0]
                try:
                    bbox_activate = self._tree.bbox(iid, 'activate')
                    if bbox_activate:
                        xa, ya, wa, ha = bbox_activate
                        chk_w = chk.winfo_reqwidth() if chk.winfo_ismapped() else 100
                        chk_h = chk.winfo_reqheight() if chk.winfo_ismapped() else 24
                        chk_x = xa + (wa - chk_w) // 2
                        chk_y = ya + max(4, (ha - chk_h) // 2)
                        chk.place(x=chk_x, y=chk_y)
                    else:
                        chk.place_forget()
                except Exception:
                    chk.place_forget()
            except Exception:
                try:
                    for w in ctrls:
                        w.place_forget()
                except Exception:
                    pass
                    
    def position_controls(self) -> None:
        """Public method to position controls."""
        self._position_row_controls()
        
    def refresh_texts(self) -> None:
        """Refresh all translatable texts."""
        try:
            self._btn_add.configure(text=t('buffs.add', 'Add'))
            self._btn_edit.configure(text=t('buffs.edit', 'Edit'))
            self._btn_delete.configure(text=t('library.delete', 'Delete'))
            self._lbl_search.configure(text=t('buffs.search', 'Search'))
            self._btn_clear_search.configure(text=t('button.clear', 'Clear'))
            self._tree.heading('name', text=t('buffs.name', 'Name'))
            self._tree.heading('desc', text=t('buffs.description', 'Description'))
        except Exception:
            pass

