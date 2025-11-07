"""
Simplified main HUD window using modular tab components.
"""
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple, Optional
from src.i18n.locale import t, get_lang, set_lang
from src.buffs.library import load_library, update_entry, add_entry, make_entry
from src.ui.styles import configure_modern_styles, BG_COLOR
from src.ui.tabs.monitoring_tab import MonitoringTab
from src.ui.tabs.settings_tab import SettingsTab
from src.ui.tabs.library_tab import LibraryTab
from src.ui.dialogs.buff_editor import BuffEditorDialog


class BuffHUD:
    """Main HUD window for buff monitoring and management."""
    
    def __init__(
        self, 
        templates: List[Tuple[str, str]], 
        keep_on_top: bool = True,
        alpha: float = 1.0,
        grab_anywhere: bool = True
    ) -> None:
        """
        Initialize BuffHUD.
        
        Args:
            templates: List of (name, path) template tuples
            keep_on_top: Whether window should stay on top
            alpha: Window transparency (0.0 to 1.0)
            grab_anywhere: Whether to enable drag-from-anywhere
        """
        self._root = tk.Tk()
        self._root.title('Buff HUD')
        self._root.resizable(False, False)
        
        try:
            self._root.attributes('-topmost', keep_on_top)
            self._root.attributes('-alpha', float(alpha))
        except Exception:
            pass
            
        # Center window on screen
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
        self._events: List[str] = []
        
        # Configure modern styles
        configure_modern_styles(self._root)
        
        # Create notebook (tabs)
        self._notebook = ttk.Notebook(self._root, style='TNotebook')
        self._notebook.pack(fill='both', expand=True, padx=6, pady=6)
        
        # Create tab frames
        self._tab_monitor_frame = tk.Frame(self._notebook, bg=BG_COLOR)
        self._tab_settings_frame = tk.Frame(self._notebook, bg=BG_COLOR)
        self._tab_buffs_frame = tk.Frame(self._notebook, bg=BG_COLOR)
        self._tab_debuffs_frame = tk.Frame(self._notebook, bg=BG_COLOR)
        
        # Initialize tab components
        self._monitoring_tab = MonitoringTab(self._tab_monitor_frame)
        self._settings_tab = SettingsTab(self._tab_settings_frame, keep_on_top)
        self._buffs_tab = LibraryTab(
            self._tab_buffs_frame,
            'buff',
            on_add=lambda: self._on_add_entry('buff'),
            on_edit=lambda: self._on_edit_entry('buff'),
            on_toggle_active=self._on_toggle_active
        )
        self._debuffs_tab = LibraryTab(
            self._tab_debuffs_frame,
            'debuff',
            on_add=lambda: self._on_add_entry('debuff'),
            on_edit=lambda: self._on_edit_entry('debuff'),
            on_toggle_active=self._on_toggle_active
        )
        
        # Add tabs to notebook
        self._notebook.add(self._tab_monitor_frame, text=t('tab.monitoring', 'Monitoring'))
        self._notebook.add(self._tab_settings_frame, text=t('tab.settings', 'Settings'))
        self._notebook.add(self._tab_buffs_frame, text=t('tab.buffs', 'Buffs'))
        self._notebook.add(self._tab_debuffs_frame, text=t('tab.debuffs', 'Debuffs'))
        
        # Load templates into monitoring tab
        self._monitoring_tab.load_templates(templates)
        
        # Set up callbacks
        self._monitoring_tab.set_scan_command(self._on_toggle_scan)
        self._monitoring_tab.set_positioning_command(self._on_toggle_positioning)
        self._monitoring_tab.set_exit_command(self._on_exit)
        
        self._settings_tab.set_select_command(self._on_select_roi)
        self._settings_tab.set_topmost_command(self._on_topmost_changed)
        self._settings_tab.set_language_command(self._on_lang_changed)
        
        # Bind search events
        self._buffs_tab.get_tree_view().get_search_var().trace_add(
            'write', 
            lambda *args: self._reload_library()
        )
        self._debuffs_tab.get_tree_view().get_search_var().trace_add(
            'write', 
            lambda *args: self._reload_library()
        )
        
        # Load library
        self._reload_library()
        
        # Enable grab-anywhere if requested
        if grab_anywhere:
            for widget in (self._root, self._tab_monitor_frame, self._tab_settings_frame,
                          self._tab_buffs_frame, self._tab_debuffs_frame):
                widget.bind('<ButtonPress-1>', self._start_move)
                widget.bind('<B1-Motion>', self._on_motion)
                
        self._root.protocol('WM_DELETE_WINDOW', self._on_exit)
        
    def _on_exit(self) -> None:
        """Handle exit request."""
        self._exit_requested = True
        
    def _start_move(self, event) -> None:
        """Start window dragging."""
        self._click_x = event.x_root
        self._click_y = event.y_root
        self._win_x = self._root.winfo_x()
        self._win_y = self._root.winfo_y()
        
    def _on_motion(self, event) -> None:
        """Handle window dragging."""
        dx = event.x_root - self._click_x
        dy = event.y_root - self._click_y
        new_x = self._win_x + dx
        new_y = self._win_y + dy
        self._root.geometry(f'+{new_x}+{new_y}')
        
    def _on_select_roi(self) -> None:
        """Handle ROI selection request."""
        self._select_roi_requested = True
        
    def _on_topmost_changed(self) -> None:
        """Handle topmost checkbox change."""
        try:
            self._root.attributes('-topmost', bool(self._settings_tab.get_topmost_var().get()))
        except Exception:
            pass
            
    def _on_lang_changed(self, event=None) -> None:
        """Handle language change."""
        set_lang(self._settings_tab.get_lang_var().get())
        self._refresh_texts()
        self._reload_library()
        
    def _on_toggle_scan(self) -> None:
        """Handle scan button toggle."""
        scan_var = self._monitoring_tab.get_scanning_var()
        scan_var.set(not scan_var.get())
        self._events.append('SCAN_ON' if scan_var.get() else 'SCAN_OFF')
        
        self._monitoring_tab.update_scan_status(scan_var.get())
        
        if scan_var.get():
            self._monitoring_tab.start_scan_animation(self._root)
        else:
            self._monitoring_tab.stop_scan_animation(self._root)
            
    def _on_toggle_positioning(self) -> None:
        """Handle positioning mode toggle."""
        self._events.append(
            'POSITIONING_ON' if self._monitoring_tab.get_positioning_var().get() 
            else 'POSITIONING_OFF'
        )
        
    def _on_toggle_active(self, entry_id: str, entry_type: str, var: tk.BooleanVar) -> None:
        """Handle entry active toggle."""
        try:
            update_entry(entry_id, entry_type, {'active': bool(var.get())})
            self._events.append('LIBRARY_UPDATED')
        except Exception:
            pass
            
    def _on_add_entry(self, entry_type: str) -> None:
        """Handle add entry request."""
        dlg = BuffEditorDialog(self._root, entry_type=entry_type)
        res = dlg.show()
        if res is None:
            return
            
        # Create entry
        entry = make_entry(
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
            extend_bottom=int(res.get('extend_bottom', 0)),
        )
        
        # Update localizations
        entry.name.update(res['name'])
        entry.description.update(res['description'])
        
        add_entry(entry)
        self._reload_library()
        
    def _on_edit_entry(self, entry_type: str) -> None:
        """Handle edit entry request."""
        tab = self._buffs_tab if entry_type == 'buff' else self._debuffs_tab
        entry_id = tab.get_selected_id()
        
        if not entry_id:
            try:
                messagebox.showinfo(
                    title='Info', 
                    message=t('info.select_item', 'Select an item to edit')
                )
            except Exception:
                pass
            return
            
        # Find entry in library
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
            
        res['id'] = entry_id
        res['type'] = entry_type
        update_entry(entry_id, entry_type, res)
        self._reload_library()
        
    def _reload_library(self) -> None:
        """Reload library data in tabs."""
        buffs_query = self._buffs_tab.get_tree_view().get_search_var().get()
        debuffs_query = self._debuffs_tab.get_tree_view().get_search_var().get()
        
        self._buffs_tab.reload_library(buffs_query)
        self._debuffs_tab.reload_library(debuffs_query)
        
    def _refresh_texts(self) -> None:
        """Refresh all translatable texts."""
        try:
            self._notebook.tab(self._tab_monitor_frame, text=t('tab.monitoring', 'Monitoring'))
            self._notebook.tab(self._tab_settings_frame, text=t('tab.settings', 'Settings'))
            self._notebook.tab(self._tab_buffs_frame, text=t('tab.buffs', 'Buffs'))
            self._notebook.tab(self._tab_debuffs_frame, text=t('tab.debuffs', 'Debuffs'))
        except Exception:
            pass
            
        self._monitoring_tab.refresh_texts()
        self._settings_tab.refresh_texts()
        self._buffs_tab.refresh_texts()
        self._debuffs_tab.refresh_texts()
        
    def read(self, timeout: int = 0) -> Optional[str]:
        """
        Read events from the UI.
        
        Args:
            timeout: Timeout in milliseconds
            
        Returns:
            Event string or None
        """
        try:
            self._root.update_idletasks()
            self._root.update()
        except tk.TclError:
            self._exit_requested = True
            
        if timeout and timeout > 0:
            time.sleep(timeout / 1000.0)
            
        if self._exit_requested:
            return 'EXIT'
            
        if self._events:
            return self._events.pop(0)
            
        if self._select_roi_requested:
            self._select_roi_requested = False
            return 'SELECT_ROI'
            
        return None
        
    def update(self, found_names: List[str]) -> None:
        """
        Update found buffs display.
        
        Args:
            found_names: List of found buff names
        """
        self._monitoring_tab.update_found(found_names)
        
    def get_overlay_enabled(self) -> bool:
        """Check if overlay is enabled."""
        return bool(self._settings_tab.get_overlay_var().get())
        
    def get_positioning_enabled(self) -> bool:
        """Check if positioning mode is enabled."""
        return bool(self._monitoring_tab.get_positioning_var().get())
        
    def get_scanning_enabled(self) -> bool:
        """Check if scanning is enabled."""
        return bool(self._monitoring_tab.get_scanning_var().get())
        
    def set_roi_info(self, left: int, top: int, width: int, height: int) -> None:
        """
        Set ROI info display.
        
        Args:
            left: ROI left coordinate
            top: ROI top coordinate  
            width: ROI width
            height: ROI height
        """
        self._settings_tab.set_roi_info(left, top, width, height)
        
    def get_root(self) -> tk.Tk:
        """Get root window."""
        return self._root
        
    def close(self) -> None:
        """Close the HUD window."""
        try:
            self._root.destroy()
        except Exception:
            pass

