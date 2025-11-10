"""
Simplified main HUD window using modular tab components.
"""
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple, Optional
from src.i18n.locale import t, get_lang, set_lang
from src.buffs.library import (
    load_library,
    update_entry,
    add_entry,
    make_entry,
    add_copy_area_entry,
    update_copy_area_entry,
    make_copy_area_entry,
)
from src.currency.library import (
    load_currencies,
    add_currency_entry,
    update_currency_entry,
    delete_currency_entry,
    make_currency_entry,
)
from src.quickcraft.library import load_positions as load_quickcraft_positions, update_hotkey as update_quickcraft_hotkey, load_global_hotkey, save_global_hotkey
from src.quickcraft.hotkeys import normalize_hotkey_name
from src.ui.styles import configure_modern_styles, BG_COLOR
from src.ui.components.control_dock import ControlDock
from src.ui.tabs.monitoring_tab import MonitoringTab
from src.ui.tabs.settings_tab import SettingsTab
from src.ui.tabs.library_tab import LibraryTab
from src.ui.tabs.copy_area_tab import CopyAreaTab
from src.ui.tabs.quickcraft_tab import QuickCraftTab
from src.ui.tabs.currency_tab import CurrencyTab
from src.ui.tabs.mega_qol_tab import MegaQolTab
from src.ui.dialogs.buff_editor import BuffEditorDialog
from src.ui.dialogs.copy_area_editor import CopyAreaEditorDialog
from src.ui.dialogs.currency_editor import CurrencyEditorDialog
from src.ui.roi_selector import select_roi


class BuffHUD:
    """Main HUD window for buff monitoring and management."""
    
    def __init__(
        self,
        templates: List[Tuple[str, str]],
        keep_on_top: bool = True,
        alpha: float = 1.0,
        grab_anywhere: bool = True,
        focus_required: bool = True,
        dock_position: Optional[Tuple[int, int]] = None,
        triple_ctrl_click_enabled: bool = False,
        mega_qol_enabled: bool = False,
        mega_qol_sequence: str = '1,2,3,4',
        mega_qol_delay_ms: int = 50,
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
        self._root.resizable(True, True)
        
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
        self._control_dock: Optional[ControlDock] = None
        self._dock_position: Optional[Tuple[int, int]] = dock_position
        self._dock_locked: bool = True
        self._dock_visible: bool = False
        self._dock_has_focus: bool = False
        self._last_dock_interaction: float = 0.0
        self._dock_visible: bool = True
        
        # Configure modern styles
        configure_modern_styles(self._root)
        
        # Create notebook (tabs)
        # Root-level notebook (grouped tabs)
        self._root_notebook = ttk.Notebook(self._root, style='TNotebook')
        self._root_notebook.pack(fill='both', expand=True, padx=6, pady=6)
        
        # Create tab frames
        # Group containers
        self._tab_overview_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)
        self._tab_settings_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)
        self._tab_library_group_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)
        self._tab_tools_group_frame = tk.Frame(self._root_notebook, bg=BG_COLOR)

        # Inner notebooks for groups
        self._library_nb = ttk.Notebook(self._tab_library_group_frame, style='TNotebook')
        self._library_nb.pack(fill='both', expand=True)
        self._tools_nb = ttk.Notebook(self._tab_tools_group_frame, style='TNotebook')
        self._tools_nb.pack(fill='both', expand=True)

        # Actual tab frames
        self._tab_monitor_frame = tk.Frame(self._tab_overview_frame, bg=BG_COLOR)
        self._tab_monitor_frame.pack(fill='both', expand=True)
        self._tab_buffs_frame = tk.Frame(self._library_nb, bg=BG_COLOR)
        self._tab_debuffs_frame = tk.Frame(self._library_nb, bg=BG_COLOR)
        self._tab_currency_frame = tk.Frame(self._tools_nb, bg=BG_COLOR)
        self._tab_quickcraft_frame = tk.Frame(self._tools_nb, bg=BG_COLOR)
        self._tab_copy_frame = tk.Frame(self._library_nb, bg=BG_COLOR)
        self._tab_mega_qol_frame = tk.Frame(self._tools_nb, bg=BG_COLOR)
        
        # Initialize tab components
        self._monitoring_tab = MonitoringTab(self._tab_monitor_frame)
        # Settings description
        try:
            ttk.Label(self._tab_settings_frame, text=t('desc.settings', 'Configure ROI, focus policy, dock and language.'), style='Prompt.TLabel').pack(anchor='w', padx=12, pady=(8, 4))
        except Exception:
            pass
        self._settings_tab = SettingsTab(self._tab_settings_frame, keep_on_top, focus_required, triple_ctrl_click_enabled)
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
        self._currency_tab = CurrencyTab(
            self._tab_currency_frame,
            on_add=self._on_add_currency,
            on_edit=self._on_edit_currency,
            on_delete=self._on_delete_currency,
            on_toggle_active=self._on_toggle_currency_active,
        )
        self._quickcraft_tab = QuickCraftTab(
            self._tab_quickcraft_frame,
            on_toggle_positioning=self._on_toggle_currency_positioning,
            on_set_hotkey=self._on_quickcraft_set_hotkey,
            on_clear_hotkey=self._on_quickcraft_clear_hotkey,
            on_reset_position=self._on_quickcraft_reset_position,
        )
        self._copy_tab = CopyAreaTab(
            self._tab_copy_frame,
            on_add=self._on_add_copy_area,
            on_edit=self._on_edit_copy_area,
            on_toggle_active=self._on_toggle_copy_active,
        )
        self._mega_qol_tab = MegaQolTab(
            self._tab_mega_qol_frame,
            enabled=mega_qol_enabled,
            sequence=mega_qol_sequence,
            delay_ms=mega_qol_delay_ms,
            double_ctrl_click_enabled=triple_ctrl_click_enabled,
        )
        self._mega_qol_tab.set_change_handler(self._on_mega_qol_changed)
        
        # Add tabs to notebook
        # Add grouped tabs to notebooks
        # Overview description
        try:
            ttk.Label(self._tab_overview_frame, text=t('desc.overview', 'Start/stop scanning and positioning; view detected templates.'), style='Prompt.TLabel').pack(anchor='w', padx=12, pady=(8, 4))
        except Exception:
            pass
        self._root_notebook.add(self._tab_overview_frame, text=t('tab.overview', 'Overview'))
        self._root_notebook.add(self._tab_library_group_frame, text=t('tab.library_group', 'Library'))
        self._root_notebook.add(self._tab_tools_group_frame, text=t('tab.tools_group', 'Tools'))
        self._root_notebook.add(self._tab_settings_frame, text=t('tab.settings', 'Settings'))

        # Group descriptions
        try:
            ttk.Label(self._tab_library_group_frame, text=t('desc.library', 'Maintain items: Buffs, Debuffs, Copy Areas.'), style='Prompt.TLabel').pack(anchor='w', padx=12, pady=(8, 4))
        except Exception:
            pass
        try:
            ttk.Label(self._tab_tools_group_frame, text=t('desc.tools', 'Runtime tools: Currency overlay, Quick Craft, Mega QoL.'), style='Prompt.TLabel').pack(anchor='w', padx=12, pady=(8, 4))
        except Exception:
            pass

        # Add inner tabs (Copy Areas to Library; Currency to Tools)
        self._library_nb.add(self._tab_buffs_frame, text=t('tab.buffs', 'Buffs'))
        self._library_nb.add(self._tab_debuffs_frame, text=t('tab.debuffs', 'Debuffs'))
        self._library_nb.add(self._tab_copy_frame, text=t('tab.copy_area', 'Copy Areas'))
        self._tools_nb.add(self._tab_currency_frame, text=t('tab.currency', 'Currency'))
        self._tools_nb.add(self._tab_quickcraft_frame, text=t('tab.quickcraft', 'Quick Craft'))
        self._tools_nb.add(self._tab_mega_qol_frame, text=t('tab.mega_qol', 'Mega QoL'))

        
        # Load templates into monitoring tab
        self._monitoring_tab.load_templates(templates)
        
        # Set up callbacks
        self._monitoring_tab.set_scan_command(self._on_toggle_scan)
        self._monitoring_tab.set_positioning_command(self._on_toggle_positioning)
        self._monitoring_tab.set_copy_area_command(self._on_toggle_copy_area_enabled)
        # Exit button removed from overview
        self._monitoring_tab.update_copy_area_status()
        
        self._settings_tab.set_select_command(self._on_select_roi)
        self._settings_tab.set_topmost_command(self._on_topmost_changed)
        self._settings_tab.set_focus_required_command(self._on_focus_required_changed)
        self._settings_tab.set_dock_visible_command(self._on_dock_visible_changed)
        self._settings_tab.set_reset_dock_command(self._on_reset_dock_position)
        # Double-ctrl emulation moved to Mega QoL tab
        self._settings_tab.set_language_command(self._on_lang_changed)
        # Mega QoL changes are wired via its own change/test handlers
        
        # Bind search events
        self._buffs_tab.get_tree_view().get_search_var().trace_add(
            'write', 
            lambda *args: self._reload_library()
        )
        self._debuffs_tab.get_tree_view().get_search_var().trace_add(
            'write', 
            lambda *args: self._reload_library()
        )
        self._quickcraft_tab.get_search_var().trace_add(
            'write',
            lambda *args: self._reload_library()
        )
        self._currency_tab.get_search_var().trace_add(
            'write',
            lambda *args: self._reload_library()
        )
        self._copy_tab.get_search_var().trace_add(
            'write',
            lambda *args: self._reload_library()
        )
        
        # Load library
        self._reload_library()
        
        # Enable grab-anywhere if requested
        if grab_anywhere:
            for widget in (self._root, self._tab_overview_frame, self._tab_settings_frame,
                           self._tab_library_group_frame, self._tab_tools_group_frame,
                           self._tab_monitor_frame, self._tab_buffs_frame, self._tab_debuffs_frame,
                           self._tab_copy_frame):
                widget.bind('<ButtonPress-1>', self._start_move)
                widget.bind('<B1-Motion>', self._on_motion)
                
        # Floating control dock
        self._control_dock = ControlDock(
            master=self._root,
            on_toggle_scan=self._on_dock_toggle_scan,
            on_toggle_copy=lambda: self._on_toggle_copy_area_enabled(),
            on_open_main=self._on_dock_open_main,
            initial_position=self._dock_position,
            grid_size=24,
            on_position_changed=self._on_dock_position_changed,
            on_focus_change=self._on_dock_focus_change,
            # Do not request focus restoration on any dock button action
            on_button_action=lambda: self._mark_dock_interaction(restore=False),
            on_lock_change=self._on_dock_lock_change,
            locked=self._dock_locked,
        )
        self._control_dock.set_scanning_active(self.get_scanning_enabled())
        self._control_dock.set_copy_active(self.get_copy_area_enabled())
        self._control_dock.set_click_active(False)
        self._control_dock.set_topmost(True)
        self._dock_position = self._control_dock.get_position()
        self._dock_visible = True
        
        # Sync dock visibility checkbox with actual state
        self._settings_tab.get_dock_visible_var().set(True)

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
        if self._control_dock is not None:
            self._control_dock.set_topmost(True)

    def _on_focus_required_changed(self) -> None:
        """Handle focus policy checkbox change."""
        self._events.append('FOCUS_POLICY_CHANGED')

    def _on_dock_visible_changed(self) -> None:
        """Handle dock visibility checkbox change."""
        visible = bool(self._settings_tab.get_dock_visible_var().get())
        self.set_dock_visible(visible)
            
    def _on_lang_changed(self, event=None) -> None:
        """Handle language change."""
        set_lang(self._settings_tab.get_lang_var().get())
        self._refresh_texts()
        self._reload_library()
        
    def _on_toggle_scan(self) -> None:
        """Handle scan button toggle."""
        new_state = not bool(self._monitoring_tab.get_scanning_var().get())
        self.set_scanning_state(new_state, notify=True)
            
    def _on_toggle_positioning(self) -> None:
        """Handle positioning mode toggle."""
        self._events.append(
            'POSITIONING_ON' if self._monitoring_tab.get_positioning_var().get() 
            else 'POSITIONING_OFF'
        )
        
    def _on_toggle_copy_area_enabled(self, state: Optional[bool] = None) -> None:
        """Handle copy area toggle."""
        if state is None:
            new_state = not bool(self._monitoring_tab.get_copy_area_var().get())
        else:
            new_state = bool(state)

        self.set_copy_area_state(new_state)
        self._events.append('COPY_AREA_TOGGLE')
        # Do not alter window focus on copy area toggle

    def _on_toggle_currency_positioning(self, enabled: bool) -> None:
        """Handle currency positioning toggle from quick craft tab."""
        self._events.append('CURRENCY_POSITIONING_ON' if enabled else 'CURRENCY_POSITIONING_OFF')

    def _on_dock_toggle_scan(self) -> None:
        """Handle scan toggle from floating dock."""
        self._mark_dock_interaction(restore=True)
        self._on_toggle_scan()

    def _on_dock_open_main(self) -> None:
        """Bring main window to front from dock."""
        self._mark_dock_interaction()
        try:
            self._root.deiconify()
            self._root.state('normal')
            self._root.lift()
            self._root.focus_force()
        except Exception:
            pass
        if self._control_dock is not None:
            self._control_dock.lift()

    def _on_dock_position_changed(self, x: int, y: int) -> None:
        """Handle floating dock position changes."""
        self._dock_position = (int(x), int(y))
        self._events.append('DOCK_MOVED')
        self._mark_dock_interaction()

    def _on_dock_focus_change(self, focused: bool) -> None:
        """Track floating dock focus state."""
        self._dock_has_focus = bool(focused)
        if focused:
            self._mark_dock_interaction()

    def _on_dock_lock_change(self, locked: bool) -> None:
        """Track lock state changes."""
        self._dock_locked = bool(locked)
        self._mark_dock_interaction()

    def _on_reset_dock_position(self) -> None:
        """Reset floating dock position to default."""
        if self._control_dock is None:
            return
        self._control_dock.reset_position()
        self._control_dock.lift()
        self._dock_position = self._control_dock.get_position()

    def _on_triple_ctrl_click_changed(self) -> None:
        """Handle triple ctrl click checkbox change."""
        self._events.append('TRIPLE_CTRL_CLICK_CHANGED')

    def _on_mega_qol_changed(self) -> None:
        self._events.append('MEGA_QOL_CHANGED')

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
        
    def _on_add_currency(self) -> None:
        dlg = CurrencyEditorDialog(self._root)
        res = dlg.show()
        if res is None:
            return

        entry = make_currency_entry(
            name=res.get('name', ''),
            interface=res.get('interface', ''),
            image_path=res.get('image_path', ''),
            capture=res.get('capture'),
            active=True,
        )
        add_currency_entry(entry)
        self._events.append('CURRENCY_UPDATED')
        self._reload_library()

    def _on_edit_currency(self) -> None:
        entry_id = self._currency_tab.get_selected_id()
        if not entry_id:
            try:
                messagebox.showinfo(
                    title='Info',
                    message=t('currency.select_delete', 'Select an item to delete'),
                )
            except Exception:
                pass
            return

        current = None
        for item in load_currencies():
            if item.get('id') == entry_id:
                current = item
                break

        if current is None:
            return

        dlg = CurrencyEditorDialog(self._root, initial=current)
        res = dlg.show()
        if res is None:
            return

        success = update_currency_entry(
            entry_id,
            {
                'name': res.get('name'),
                'interface': res.get('interface'),
                'image_path': res.get('image_path'),
                'capture': res.get('capture'),
            },
        )
        if not success:
            try:
                messagebox.showerror(title='Error', message=t('error.save_failed', 'Unable to save changes'))
            except Exception:
                pass
            return

        self._events.append('CURRENCY_UPDATED')
        self._reload_library()

    def _on_delete_currency(self) -> None:
        entry_id = self._currency_tab.get_selected_id()
        if not entry_id:
            try:
                messagebox.showinfo(
                    title='Info',
                    message=t('info.select_item', 'Select an item to edit'),
                )
            except Exception:
                pass
            return

        try:
            confirm = messagebox.askyesno(
                title='Confirm',
                message=t('currency.confirm_delete', 'Delete selected currency?'),
            )
        except Exception:
            confirm = True

        if not confirm:
            return

        if not delete_currency_entry(entry_id):
            try:
                messagebox.showerror(title='Error', message=t('error.delete_failed', 'Unable to delete selected item'))
            except Exception:
                pass
            return

        self._events.append('CURRENCY_UPDATED')
        self._reload_library()

    def _on_toggle_currency_active(self, entry_id: str, var: tk.BooleanVar) -> None:
        if not entry_id:
            return

        desired = bool(var.get())
        if not update_currency_entry(entry_id, {'active': desired}):
            var.set(not desired)
            return

        self._events.append('CURRENCY_UPDATED')

    def _on_quickcraft_set_hotkey(self, _currency_id: str) -> None:
        # Capture GLOBAL hotkey for all currencies
        self._quickcraft_tab.start_hotkey_capture(lambda token: self._apply_global_hotkey(token))

    def _on_quickcraft_clear_hotkey(self, _currency_id: str) -> None:
        save_global_hotkey('')
        self._events.append('QUICKCRAFT_UPDATED')
        self._reload_library()

    def _on_quickcraft_reset_position(self, currency_id: str) -> None:
        from src.quickcraft.library import update_position
        if not currency_id:
            return
        try:
            update_position(currency_id, 0, 0)
        except Exception:
            pass
        self._events.append('QUICKCRAFT_UPDATED')
        self._reload_library()

    def _apply_global_hotkey(self, token: str) -> None:
        normalized = token.strip().upper().replace(' ', '_')
        save_global_hotkey(normalized)
        self._events.append('QUICKCRAFT_UPDATED')
        self._reload_library()

    def _reload_library(self) -> None:
        """Reload library data in tabs."""
        buffs_query = self._buffs_tab.get_tree_view().get_search_var().get()
        debuffs_query = self._debuffs_tab.get_tree_view().get_search_var().get()
        copy_query = self._copy_tab.get_search_var().get()
        currency_query = self._currency_tab.get_search_var().get()
        quick_query = self._quickcraft_tab.get_search_var().get()

        self._buffs_tab.reload_library(buffs_query)
        self._debuffs_tab.reload_library(debuffs_query)
        self._currency_tab.reload(currency_query)

        currencies = load_currencies()
        quickcraft_cfg = load_quickcraft_positions()
        global_hotkey = load_global_hotkey()
        if quick_query:
            q = quick_query.strip().lower()
            filtered = []
            for entry in currencies:
                haystack = f"{entry.get('name', '')} {entry.get('interface', '')}".lower()
                if q in haystack:
                    filtered.append(entry)
            self._quickcraft_tab.reload(filtered, quickcraft_cfg)
        else:
            self._quickcraft_tab.reload(currencies, quickcraft_cfg)

        # Show global hotkey text
        try:
            self._quickcraft_tab.set_global_hotkey_label(global_hotkey)
        except Exception:
            pass

        self._copy_tab.reload(copy_query)
        
    def _refresh_texts(self) -> None:
        """Refresh all translatable texts."""
        try:
            self._root_notebook.tab(self._tab_overview_frame, text=t('tab.overview', 'Overview'))
            self._root_notebook.tab(self._tab_library_group_frame, text=t('tab.library_group', 'Library'))
            self._root_notebook.tab(self._tab_tools_group_frame, text=t('tab.tools_group', 'Tools'))
            self._root_notebook.tab(self._tab_settings_frame, text=t('tab.settings', 'Settings'))

            self._library_nb.tab(self._tab_buffs_frame, text=t('tab.buffs', 'Buffs'))
            self._library_nb.tab(self._tab_debuffs_frame, text=t('tab.debuffs', 'Debuffs'))
            self._library_nb.tab(self._tab_currency_frame, text=t('tab.currency', 'Currency'))
            self._tools_nb.tab(self._tab_quickcraft_frame, text=t('tab.quickcraft', 'Quick Craft'))
            self._tools_nb.tab(self._tab_copy_frame, text=t('tab.copy_area', 'Copy Areas'))
            self._tools_nb.tab(self._tab_mega_qol_frame, text=t('tab.mega_qol', 'Mega QoL'))
        except Exception:
            pass
            
        self._monitoring_tab.refresh_texts()
        self._settings_tab.refresh_texts()
        self._buffs_tab.refresh_texts()
        self._debuffs_tab.refresh_texts()
        self._currency_tab.refresh_texts()
        self._quickcraft_tab.refresh_texts()
        self._copy_tab.refresh_texts()
        self._copy_tab.reload(self._copy_tab.get_search_var().get())
        try:
            self._mega_qol_tab.refresh_texts()
        except Exception:
            pass

    def _on_add_copy_area(self) -> None:
        dlg = CopyAreaEditorDialog(self._root)
        res = dlg.show()
        if res is None:
            return

        name_en = res['name'].get('en') or res['name'].get(get_lang(), '')
        if not name_en:
            name_en = next(iter(res['name'].values()), '')

        capture_cfg = res.get('capture') or {}
        cap_w = int(capture_cfg.get('width', 0))
        cap_h = int(capture_cfg.get('height', 0))

        display_w = int(res.get('width', 0)) or cap_w or 200
        display_h = int(res.get('height', 0)) or cap_h or 200
        display_w = max(50, display_w)
        display_h = max(50, display_h)

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        default_left = max(0, (screen_w - display_w) // 2)
        default_top = max(0, (screen_h - display_h) // 2)

        left = int(res.get('left', 0))
        top = int(res.get('top', 0))
        if left == 0 and top == 0:
            left, top = default_left, default_top

        entry = make_copy_area_entry(
            name_en=name_en,
            image_path=res['image_path'],
            references=res.get('references'),
            capture=capture_cfg,
            left=left,
            top=top,
            width=display_w,
            height=display_h,
            topmost=res.get('topmost', True),
        )
        entry.name.update(res['name'])
        entry.active = True
        add_copy_area_entry(entry)
        self._events.append('COPY_UPDATED')
        self._reload_library()

    def _on_edit_copy_area(self) -> None:
        area_id = self._copy_tab.get_selected_id()
        if not area_id:
            try:
                messagebox.showinfo(
                    title='Info',
                    message=t('info.select_item', 'Select an item to edit'),
                )
            except Exception:
                pass
            return

        library = load_library()
        current = None
        for item in library.get('copy_areas', []):
            if item.get('id') == area_id:
                current = item
                break

        if current is None:
            return

        dlg = CopyAreaEditorDialog(self._root, initial=current)
        res = dlg.show()
        if res is None:
            return

        update_copy_area_entry(
            area_id,
            {
                'name': res['name'],
                'image_path': res['image_path'],
                'references': res['references'],
                'capture': res['capture'],
                'left': res['left'],
                'top': res['top'],
                'width': res['width'],
                'height': res['height'],
                'topmost': res.get('topmost', True),
            },
        )
        self._events.append('COPY_UPDATED')
        self._reload_library()

    def _on_toggle_copy_active(self, entry_id: str, var: tk.BooleanVar) -> None:
        try:
            update_copy_area_entry(entry_id, {'active': bool(var.get())})
        except Exception:
            pass

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

    def set_status_message(self, message: str = '', level: str = 'info') -> None:
        """Set status message on the monitoring tab."""
        self._monitoring_tab.set_status(message, level)

    def set_scanning_state(self, enabled: bool, notify: bool = False) -> None:
        """Programmatically update scanning toggle state."""
        scan_var = self._monitoring_tab.get_scanning_var()
        current = bool(scan_var.get())
        if current == enabled:
            return

        scan_var.set(enabled)
        self._monitoring_tab.update_scan_status(enabled)
        if self._control_dock is not None:
            self._control_dock.set_scanning_active(enabled)

        if enabled:
            self._monitoring_tab.start_scan_animation(self._root)
        else:
            self._monitoring_tab.stop_scan_animation(self._root)

        if notify:
            self._events.append('SCAN_ON' if enabled else 'SCAN_OFF')

    def set_copy_area_state(self, enabled: bool, notify: bool = False) -> None:
        """Programmatically update copy area toggle state."""
        copy_var = self._monitoring_tab.get_copy_area_var()
        current = bool(copy_var.get())
        if current == enabled:
            return

        copy_var.set(enabled)
        self._monitoring_tab.update_copy_area_status()
        if self._control_dock is not None:
            self._control_dock.set_copy_active(enabled)

        if notify:
            self._events.append('COPY_AREA_TOGGLE')

    def set_currency_positioning(self, enabled: bool) -> None:
        """Update quick craft positioning checkbox state."""
        self._quickcraft_tab.set_positioning(enabled)

    # No runtime active UI marker required

    def set_click_emulation_state(self, enabled: bool) -> None:
        """Update click emulation indicator state."""
        if self._control_dock is not None:
            self._control_dock.set_click_active(enabled)
        
    def get_overlay_enabled(self) -> bool:
        """Check if overlay is enabled."""
        return bool(self._settings_tab.get_overlay_var().get())
        
    def get_positioning_enabled(self) -> bool:
        """Check if positioning mode is enabled."""
        return bool(self._monitoring_tab.get_positioning_var().get())
        
    def get_scanning_enabled(self) -> bool:
        """Check if scanning is enabled."""
        return bool(self._monitoring_tab.get_scanning_var().get())

    def get_copy_area_enabled(self) -> bool:
        """Check if copy area overlay is enabled."""
        return bool(self._monitoring_tab.get_copy_area_var().get())
        
    def get_dock_position(self) -> Optional[Tuple[int, int]]:
        """Get current floating dock position."""
        return self._dock_position
        
    def set_dock_visible(self, visible: bool) -> None:
        """Show or hide the floating dock."""
        if self._control_dock is None:
            return
        desired = bool(visible)
        if desired == self._dock_visible:
            return
        if desired:
            self._control_dock.show()
            self._control_dock.lift()
            self._mark_dock_interaction()
        else:
            self._control_dock.hide()
            self._dock_has_focus = False
        self._dock_visible = desired
        
    def is_application_active(self) -> bool:
        """Check if HUD or floating dock currently has focus."""
        if self._dock_has_focus:
            return True
        if self._recent_dock_interaction():
            return True
        try:
            widget = self._root.focus_get()
        except Exception:
            widget = None
        return widget is not None
        
    def get_focus_required(self) -> bool:
        """Check if game focus is required."""
        return bool(self._settings_tab.get_focus_required_var().get())

    def get_triple_ctrl_click_enabled(self) -> bool:
        """Check if triple ctrl click is enabled."""
        # Value sourced from Mega QoL tab now
        return bool(self._mega_qol_tab.get_double_ctrl_var().get())

    def get_mega_qol_config(self) -> dict:
        return {
            'enabled': bool(self._mega_qol_tab.get_enabled_var().get()),
            'sequence': self._mega_qol_tab.get_sequence(),
            'delay_ms': int(self._mega_qol_tab.get_delay_ms()),
        }
        
    def is_dock_locked(self) -> bool:
        """Check if floating dock is locked from moving."""
        return self._dock_locked
        
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
        if self._control_dock is not None:
            self._control_dock.close()
            self._dock_visible = False
            self._dock_has_focus = False
        try:
            self._root.destroy()
        except Exception:
            pass

    def _mark_dock_interaction(self, restore: bool = False) -> None:
        self._last_dock_interaction = time.time()
        if restore and 'DOCK_INTERACTION' not in self._events:
            self._events.append('DOCK_INTERACTION')

    def _recent_dock_interaction(self, timeout: float = 1.0) -> bool:
        if self._last_dock_interaction <= 0.0:
            return False
        return (time.time() - self._last_dock_interaction) <= timeout

