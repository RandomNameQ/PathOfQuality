"""
Library tab for managing buffs or debuffs.
"""
import tkinter as tk
from typing import Callable
from src.buffs.library import load_library
from src.ui.components.library_tree import LibraryTreeView


class LibraryTab:
    """Tab for managing buff or debuff library."""
    
    def __init__(
        self, 
        parent: tk.Frame, 
        entry_type: str,
        on_add: Callable,
        on_edit: Callable,
        on_toggle_active: Callable
    ) -> None:
        """
        Initialize library tab.
        
        Args:
            parent: Parent frame
            entry_type: Either 'buff' or 'debuff'
            on_add: Callback for add button
            on_edit: Callback for edit button
            on_toggle_active: Callback for active toggle
        """
        self.frame = parent
        self.entry_type = entry_type
        
        self._tree_view = LibraryTreeView(
            parent=parent,
            entry_type=entry_type,
            on_add=on_add,
            on_edit=on_edit,
            on_toggle_active=on_toggle_active
        )
        
    def reload_library(self, search_query: str = '') -> None:
        """
        Reload library data and refresh tree view.
        
        Args:
            search_query: Optional search filter
        """
        data = load_library()
        bucket = 'buffs' if self.entry_type == 'buff' else 'debuffs'
        
        self._tree_view.clear()
        
        for item in data.get(bucket, []):
            # Filter by search query
            if search_query:
                query = search_query.strip().lower()
                nm = item.get('name', {})
                found = any(query in str(v).lower() for v in nm.values())
                if not found:
                    continue
                    
            self._tree_view.add_item(item)
            
        # Position controls after adding all items
        self._tree_view.position_controls()
        
    def get_tree_view(self) -> LibraryTreeView:
        """Get the tree view component."""
        return self._tree_view
        
    def get_selected_id(self) -> str:
        """Get selected entry ID or empty string."""
        tree = self._tree_view.get_tree()
        sel = tree.selection()
        return sel[0] if sel else ''
        
    def refresh_texts(self) -> None:
        """Refresh all translatable texts."""
        self._tree_view.refresh_texts()

