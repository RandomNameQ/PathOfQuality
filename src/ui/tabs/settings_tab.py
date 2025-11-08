"""
Settings tab UI component.
"""
import tkinter as tk
from tkinter import ttk
from src.i18n.locale import t, get_lang
from src.ui.styles import BG_COLOR, FG_COLOR


class SettingsTab:
    """Settings tab for ROI selection and application configuration."""
    
    def __init__(self, parent: tk.Frame, keep_on_top: bool = False, focus_required: bool = True) -> None:
        """
        Initialize settings tab.
        
        Args:
            parent: Parent frame
            keep_on_top: Initial "always on top" setting
        """
        self.frame = parent
        self._overlay_var = tk.BooleanVar(value=False)
        self._topmost_var = tk.BooleanVar(value=keep_on_top)
        self._focus_required_var = tk.BooleanVar(value=focus_required)
        self._lang_var = tk.StringVar(value=get_lang())
        
        self._create_widgets()
        
    def _create_widgets(self) -> None:
        """Create settings tab widgets."""
        # Controls frame
        controls = tk.Frame(self.frame, bg=BG_COLOR)
        controls.pack(fill='x', padx=12, pady=12)
        
        # Select ROI button
        self._btn_select = ttk.Button(
            controls, 
            text=t('settings.select_zone', 'Select Area'),
            style='Modern.TButton'
        )
        self._btn_select.pack(side='left', padx=(0, 12))
        
        # Show overlay checkbox
        self._chk_overlay = ttk.Checkbutton(
            controls, 
            text=t('settings.show_analysis', 'Show Analysis Area'),
            variable=self._overlay_var,
            style='Toggle.TCheckbutton'
        )
        self._chk_overlay.pack(side='left')
        
        # Always on top checkbox
        self._chk_topmost = ttk.Checkbutton(
            controls, 
            text=t('settings.always_on_top', 'Always on top'),
            variable=self._topmost_var,
            style='Toggle.TCheckbutton'
        )
        self._chk_topmost.pack(side='left', padx=(12, 0))

        self._chk_focus_required = ttk.Checkbutton(
            controls,
            text=t('settings.require_game_focus', 'Run only when the game is focused'),
            variable=self._focus_required_var,
            style='Toggle.TCheckbutton'
        )
        self._chk_focus_required.pack(side='left', padx=(12, 0))

        self._btn_reset_dock = ttk.Button(
            controls,
            text=t('settings.reset_dock', 'Reset panel position'),
            style='Action.TButton'
        )
        self._btn_reset_dock.pack(side='left', padx=(12, 0))
        
        # Language selector
        lang_controls = tk.Frame(self.frame, bg=BG_COLOR)
        lang_controls.pack(fill='x', padx=12, pady=(0, 12))
        
        self._lbl_language = tk.Label(
            lang_controls, 
            text=t('settings.language', 'Language'),
            bg=BG_COLOR, 
            fg=FG_COLOR, 
            font=('Segoe UI', 9)
        )
        self._lbl_language.pack(side='left', padx=(0, 8))
        
        self._lang_cmb = ttk.Combobox(
            lang_controls, 
            textvariable=self._lang_var,
            values=['en', 'ru'],
            state='readonly',
            width=6,
            font=('Segoe UI', 9)
        )
        self._lang_cmb.pack(side='left')
        
        # ROI info label
        self._roi_label = tk.Label(
            self.frame, 
            text=f"{t('settings.roi', 'ROI')}: —",
            bg=BG_COLOR, 
            fg=FG_COLOR, 
            font=('Segoe UI', 9)
        )
        self._roi_label.pack(padx=12, pady=(0, 12))
        
    def set_roi_info(self, left: int, top: int, width: int, height: int) -> None:
        """
        Update ROI info display.
        
        Args:
            left: ROI left coordinate
            top: ROI top coordinate
            width: ROI width
            height: ROI height
        """
        self._roi_label.configure(
            text=f"ROI: left={left}, top={top}, width={width}, height={height}"
        )
        
    def set_select_command(self, command) -> None:
        """Set select ROI button command callback."""
        self._btn_select.configure(command=command)
        
    def set_topmost_command(self, command) -> None:
        """Set topmost checkbox command callback."""
        self._chk_topmost.configure(command=command)

    def set_focus_required_command(self, command) -> None:
        """Set focus-required checkbox command callback."""
        self._chk_focus_required.configure(command=command)

    def set_reset_dock_command(self, command) -> None:
        """Set reset dock button command callback."""
        self._btn_reset_dock.configure(command=command)
        
    def set_language_command(self, command) -> None:
        """Set language combobox command callback."""
        self._lang_cmb.bind('<<ComboboxSelected>>', command)
        
    def get_overlay_var(self) -> tk.BooleanVar:
        """Get overlay checkbox variable."""
        return self._overlay_var
        
    def get_topmost_var(self) -> tk.BooleanVar:
        """Get topmost checkbox variable."""
        return self._topmost_var

    def get_focus_required_var(self) -> tk.BooleanVar:
        """Get focus-required checkbox variable."""
        return self._focus_required_var
        
    def get_lang_var(self) -> tk.StringVar:
        """Get language selection variable."""
        return self._lang_var
        
    def refresh_texts(self) -> None:
        """Refresh all translatable texts."""
        try:
            self._btn_select.configure(text=t('settings.select_zone', 'Select Area'))
            self._chk_overlay.configure(text=t('settings.show_analysis', 'Show Analysis Area'))
            self._chk_topmost.configure(text=t('settings.always_on_top', 'Always on top'))
            self._chk_focus_required.configure(text=t('settings.require_game_focus', 'Run only when the game is focused'))
            self._btn_reset_dock.configure(text=t('settings.reset_dock', 'Reset panel position'))
            self._lbl_language.configure(text=t('settings.language', 'Language'))
            
            # Update ROI prefix
            txt = self._roi_label.cget('text')
            if ':' in txt:
                self._roi_label.configure(
                    text=f"{t('settings.roi', 'ROI')}:" + txt.split(':', 1)[1]
                )
            else:
                self._roi_label.configure(text=f"{t('settings.roi', 'ROI')}: —")
        except Exception:
            pass

