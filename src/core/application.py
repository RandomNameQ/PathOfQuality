"""
Main application logic and event loop.
"""
import os
import sys
import json
import cv2
import time
from typing import Dict, List, Optional, Set
from src.capture.mss_capture import MSSCapture
from src.capture.base_capture import Region
from src.detector.template_matcher import TemplateMatcher
from src.detector.library_matcher import LibraryMatcher
from src.ui.hud import BuffHUD
from src.ui.icon_mirrors import IconMirrorsOverlay
from src.ui.overlay import OverlayHighlighter
from src.ui.currency_overlay import CurrencyOverlay
from src.ui.roi_selector import select_roi
from src.ui.tray import TrayIcon
from src.utils.settings import load_settings, save_settings, resource_path
from src.i18n.locale import t
from src.currency.library import load_currencies
from src.quickcraft.library import load_positions as load_quickcraft_positions, save_positions as save_quickcraft_positions, load_global_hotkey

ALLOWED_PROCESSES_FILE = resource_path(os.path.join("assets", "allowed_processes.json"))

# Windows API for checking active process and mouse simulation
if sys.platform.startswith('win'):
    import ctypes
    from ctypes import wintypes
    import win32api
    import win32con
    from src.quickcraft.hotkeys import HotkeyListener, normalize_hotkey_name
    from src.qol.mouse_listener import MouseListener

    # Define ULONG_PTR type with fallback for environments where wintypes lacks it
    try:
        ULONG_PTR = wintypes.ULONG_PTR  # type: ignore[attr-defined]
    except AttributeError:
        # Determine pointer size to choose correct underlying type
        ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    # Define SendInput structures
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        _anonymous_ = ("_input",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("_input", _INPUT),
        ]

    # Constants for SendInput
    INPUT_MOUSE = 0
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MOVE = 0x0001

    # Load SendInput function
    SendInput = ctypes.windll.user32.SendInput
    SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    SendInput.restype = wintypes.UINT
else:
    HotkeyListener = None  # type: ignore

    def normalize_hotkey_name(name: str) -> str:  # type: ignore
        return ''


def get_foreground_process_name() -> Optional[str]:
    """Get the name of the process that owns the foreground window."""
    if not sys.platform.startswith('win'):
        return None
    
    try:
        # Get foreground window handle
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        
        # Get process ID from window handle
        process_id = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        
        # Open process to get executable name
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_process = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, 
            False, 
            process_id.value
        )
        
        if not h_process:
            return None
        
        try:
            # Get executable path
            exe_path = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, exe_path, ctypes.byref(size)):
                # Extract filename from path
                full_path = exe_path.value
                return os.path.basename(full_path)
        finally:
            ctypes.windll.kernel32.CloseHandle(h_process)
    except Exception:
        pass
    
    return None


class Application:
    """Main application controller."""
    
    def __init__(self, settings_path: str = 'settings.json'):
        """
        Initialize application.
        
        Args:
            settings_path: Path to settings file
        """
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        # Allowed processes are defined strictly in JSON (no implicit additions)
        self.allowed_processes: Set[str] = self._load_allowed_processes()
        self._focus_required = bool(self.settings.get("require_game_focus", True))
        
        # Initialize components
        self.capture: MSSCapture = None
        self.matcher: TemplateMatcher = None
        self.lib_matcher: LibraryMatcher = None
        self.hud: BuffHUD = None
        self.overlay: OverlayHighlighter = None
        self.mirrors: IconMirrorsOverlay = None
        self.currency_overlay: CurrencyOverlay = None
        self.tray: TrayIcon = None
        
        # State
        self.roi: Region = None
        self.last_found: List[str] = []
        self.overlay_enabled_last = False
        self.positioning_enabled_last = False
        self._scan_user_requested = False
        self._copy_user_requested = False
        self._currency_positioning_requested = False
        self._currency_positioning_enabled = False
        self._quickcraft_positions: Dict[str, Dict[str, object]] = load_quickcraft_positions()
        self._quickcraft_hotkey_map: Dict[str, str] = {}
        self._quickcraft_global_hotkey: str = ''
        self._quickcraft_runtime_active: Optional[str] = None
        self._quickcraft_runtime_active_ids: Set[str] = set()
        self._currencies_cache: List[Dict] = []
        self._hotkeys = HotkeyListener() if sys.platform.startswith('win') and HotkeyListener is not None else None
        self._mouse: Optional[MouseListener] = MouseListener() if sys.platform.startswith('win') else None
        self._focus_state_last: Optional[bool] = None
        self._triple_ctrl_click_enabled = bool(self.settings.get("triple_ctrl_click_enabled", False))
        self._triple_ctrl_click_active = False
        # Double Ctrl press detection state
        self._ctrl_press_count: int = 0
        self._last_ctrl_press_time: float = 0.0
        self._ctrl_prev_held: bool = False
        self._register_quickcraft_hotkeys()
        # Fallback polling state for when LL hooks are unavailable
        self._key_down_state: Dict[str, bool] = {}
        self._key_last_emit: Dict[str, float] = {}
        self._anchor_at_hotkey: Optional[tuple[int, int]] = None
        self._last_click_time: float = 0.0
        self._pending_click_currency_id: Optional[str] = None
        # Mega QoL settings
        mq = self.settings.get('mega_qol', {}) or {}
        self._mega_qol_enabled: bool = bool(mq.get('wheel_down_enabled', False))
        self._mega_qol_seq_str: str = str(mq.get('wheel_down_sequence', '1,2,3,4'))
        try:
            self._mega_qol_delay_ms: int = int(mq.get('wheel_down_delay_ms', 50))
        except Exception:
            self._mega_qol_delay_ms = 50
        # Wheel burst suppression: emit once per scroll burst, rearm after 50ms of silence
        self._mega_qol_suppress: bool = False
        self._mega_qol_last_wheel: float = 0.0
        
    def initialize(self, roi: Region) -> None:
        """
        Initialize application components.
        
        Args:
            roi: Initial ROI region
        """
        self.roi = roi
        
        # Initialize capture
        self.capture = MSSCapture()
        
        # Initialize matchers
        raw_templates_dir = self.settings.get("templates_dir", "assets/templates")
        templates_dir = resource_path(raw_templates_dir)
        threshold = float(self.settings.get("threshold", 0.9))
        
        self.matcher = TemplateMatcher(templates_dir=templates_dir, threshold=threshold)
        self.lib_matcher = LibraryMatcher(threshold=threshold)
        
        print(f"Загружено шаблонов: {len(self.matcher.templates)} из '{templates_dir}'")
        if len(self.matcher.templates) > 0:
            print("Список шаблонов:", ", ".join([t[0] for t in self.matcher.get_template_infos()]))
        else:
            print(f"Шаблоны не найдены в каталоге '{templates_dir}'. Добавьте .png/.jpg, вырезанные ровно по иконке.")
            
        # Initialize UI
        ui_cfg = self.settings.get("ui", {})
        dock_cfg = ui_cfg.get("dock_position") or {}
        dock_position = None
        try:
            left = dock_cfg.get("left")
            top = dock_cfg.get("top")
            if left is not None and top is not None:
                dock_position = (int(left), int(top))
        except Exception:
            dock_position = None

        self.hud = BuffHUD(
            templates=self.matcher.get_template_infos(),
            keep_on_top=bool(ui_cfg.get("keep_on_top", False)),
            alpha=float(ui_cfg.get("alpha", 1.0)),
            grab_anywhere=bool(ui_cfg.get("grab_anywhere", True)),
            focus_required=self._focus_required,
            dock_position=dock_position,
            triple_ctrl_click_enabled=self._triple_ctrl_click_enabled,
            mega_qol_enabled=self._mega_qol_enabled,
            mega_qol_sequence=self._mega_qol_seq_str,
            mega_qol_delay_ms=self._mega_qol_delay_ms,
        )
        
        self.hud.set_roi_info(roi.left, roi.top, roi.width, roi.height)
        
        # Initialize overlays
        self.overlay = OverlayHighlighter(self.hud.get_root())
        self.mirrors = IconMirrorsOverlay(self.hud.get_root())
        self.mirrors.set_copy_enabled(self.hud.get_copy_area_enabled())
        self.currency_overlay = CurrencyOverlay(self.hud.get_root())
        self.hud.set_currency_positioning(False)
        self._currencies_cache = load_currencies()
        
        # Initialize tray
        self.tray = TrayIcon()
        self.tray.start()
        

        # Initialize focus-dependent state
        self._scan_user_requested = self.hud.get_scanning_enabled()
        self._copy_user_requested = self.hud.get_copy_area_enabled()
        self._focus_state_last = None
        self._last_allowed_hwnd = None
        self.hud.set_status_message('')
        try:
            self.hud.set_dock_visible(True)
        except Exception:
            pass
        
    def _load_allowed_processes(self) -> Set[str]:
        """Load allowed process names from configuration file."""
        processes: Set[str] = set()

        try:
            with open(ALLOWED_PROCESSES_FILE, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                items = data.get('processes', [])
            else:
                items = data
            for item in items or []:
                name = str(item).strip().lower()
                if name:
                    processes.add(name)
        except Exception:
            processes = set()
        return processes

    def _restore_allowed_focus(self) -> None:
        """Attempt to return focus to the last allowed window."""
        if not sys.platform.startswith('win'):
            return
        hwnd = getattr(self, '_last_allowed_hwnd', None)
        if not hwnd:
            return
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _get_self_process_names(self) -> Set[str]:
        """Return possible executable names for the current process."""
        names: Set[str] = set()

        for candidate in (sys.executable, sys.argv[0]):
            try:
                if not candidate:
                    continue
                name = os.path.basename(candidate).strip().lower()
                if name:
                    names.add(name)
                    if name.endswith('python.exe'):
                        names.add('pythonw.exe')
                    elif name.endswith('pythonw.exe'):
                        names.add('python.exe')
            except Exception:
                continue

        if not names:
            names.add('python.exe')
            names.add('pythonw.exe')

        return names

    
            
    def run(self) -> None:
        """Run main application loop."""
        scan_interval_ms = int(self.settings.get("scan_interval_ms", 50))

        print(f"ROI: left={self.roi.left}, top={self.roi.top}, width={self.roi.width}, height={self.roi.height}")
        print(f"Порог совпадения: {self.matcher.threshold}")
        print(f"Интервал опроса: {scan_interval_ms} мс")

        try:
            while True:
                event = self.hud.read(timeout=scan_interval_ms)
                game_in_focus = self._is_allowed_process_active()

                if event == 'EXIT' or self.tray.is_exit_requested():
                    break

                refresh_copy = False
                skip_frame_processing = False

                if event == 'LIBRARY_UPDATED':
                    try:
                        self.lib_matcher.refresh()
                    except Exception:
                        pass
                    skip_frame_processing = True

                elif event == 'COPY_UPDATED':
                    refresh_copy = True
                    skip_frame_processing = True

                elif event == 'CURRENCY_UPDATED':
                    self._currencies_cache = load_currencies()
                    active_ids = {str(entry.get('id')) for entry in self._currencies_cache if entry.get('id')}
                    self._trim_quickcraft_positions(active_ids)
                    self._register_quickcraft_hotkeys()
                    if self._quickcraft_runtime_active and self._quickcraft_runtime_active not in self._quickcraft_positions:
                        self._hide_quickcraft_overlay()
                    if self._currency_positioning_enabled:
                        self._enable_currency_positioning()
                    if self._quickcraft_runtime_active:
                        self._show_quickcraft_overlay(self._quickcraft_runtime_active, force=True)
                    skip_frame_processing = True

                elif event == 'QUICKCRAFT_UPDATED':
                    self._reload_quickcraft_data()
                    skip_frame_processing = True

                elif event == 'SELECT_ROI':
                    self._handle_roi_selection()
                    skip_frame_processing = True

                elif event == 'SCAN_ON':
                    self._scan_user_requested = True

                elif event == 'SCAN_OFF':
                    self._scan_user_requested = False

                elif event == 'COPY_AREA_TOGGLE':
                    self._copy_user_requested = self.hud.get_copy_area_enabled()
                    refresh_copy = True

                elif event == 'FOCUS_POLICY_CHANGED':
                    self._focus_required = self.hud.get_focus_required()
                    self.settings['require_game_focus'] = self._focus_required
                    save_settings(self.settings_path, self.settings)
                    refresh_copy = True

                elif event == 'DOCK_MOVED':
                    self._update_dock_position_settings()

                elif event == 'DOCK_INTERACTION':
                    # Do not change OS window focus on dock interaction
                    skip_frame_processing = True

                elif event == 'TRIPLE_CTRL_CLICK_CHANGED':
                    self._triple_ctrl_click_enabled = self.hud.get_triple_ctrl_click_enabled()
                    self.settings['triple_ctrl_click_enabled'] = self._triple_ctrl_click_enabled
                    save_settings(self.settings_path, self.settings)
                    # If feature disabled while active, stop emulation
                    if not self._triple_ctrl_click_enabled and self._triple_ctrl_click_active:
                        self._stop_mouse_simulation()

                elif event == 'MEGA_QOL_CHANGED':
                    cfg = self.hud.get_mega_qol_config()
                    self._mega_qol_enabled = bool(cfg.get('enabled'))
                    self._mega_qol_seq_str = str(cfg.get('sequence') or '')
                    try:
                        self._mega_qol_delay_ms = int(cfg.get('delay_ms') or 50)
                    except Exception:
                        self._mega_qol_delay_ms = 50
                    self.settings.setdefault('mega_qol', {})
                    self.settings['mega_qol'].update({
                        'wheel_down_enabled': self._mega_qol_enabled,
                        'wheel_down_sequence': self._mega_qol_seq_str,
                        'wheel_down_delay_ms': int(self._mega_qol_delay_ms),
                    })
                    # Sync double-ctrl emulation from Mega QoL tab
                    self._triple_ctrl_click_enabled = self.hud.get_triple_ctrl_click_enabled()
                    self.settings['triple_ctrl_click_enabled'] = self._triple_ctrl_click_enabled
                    if not self._triple_ctrl_click_enabled and self._triple_ctrl_click_active:
                        self._stop_mouse_simulation()
                    save_settings(self.settings_path, self.settings)


                elif event == 'CURRENCY_POSITIONING_ON':
                    self._currency_positioning_requested = True
                    self._enable_currency_positioning()
                    skip_frame_processing = True

                elif event == 'CURRENCY_POSITIONING_OFF':
                    self._currency_positioning_requested = False
                    self._disable_currency_positioning(save_changes=True)
                    skip_frame_processing = True

                if self.tray.is_exit_requested():
                    break

                focus_active = game_in_focus or not self._focus_required

                self._apply_focus_policy(game_in_focus)

                if refresh_copy:
                    self._refresh_copy_overlays()

                self._update_currency_overlay()
                self._process_hotkeys()

                # Process mega QoL wheel events
                # Mega QoL wheel should only work in allowed processes
                self._process_mega_qol_wheel(game_in_focus)

                # Allow positioning toggles even when the game is unfocused
                self._handle_positioning_toggle()

                if skip_frame_processing:
                    continue

                self._handle_overlay_toggle()

                # Handle triple ctrl click functionality
                if self._triple_ctrl_click_enabled:
                    self._handle_triple_ctrl_click()

                # Scan only when allowed process is focused
                if game_in_focus and self._scan_user_requested:
                    self._scan_frame()
                else:
                    self._clear_results()

        finally:
            self._cleanup()
            
    def _handle_overlay_toggle(self) -> None:
        """Handle overlay enable/disable."""
        # Always hide analysis overlay when a non-allowed process is focused
        if not self._is_allowed_process_active():
            if self.overlay_enabled_last:
                try:
                    self.overlay.hide()
                except Exception:
                    pass
                self.overlay_enabled_last = False
            return

        overlay_enabled_curr = self.hud.get_overlay_enabled()
        if overlay_enabled_curr != self.overlay_enabled_last:
            if overlay_enabled_curr:
                self.overlay.show((self.roi.left, self.roi.top, self.roi.width, self.roi.height))
            else:
                self.overlay.hide()
            self.overlay_enabled_last = overlay_enabled_curr
            
    def _handle_positioning_toggle(self) -> None:
        """Handle positioning mode toggle."""
        positioning_enabled_curr = self.hud.get_positioning_enabled()
        if positioning_enabled_curr != self.positioning_enabled_last:
            try:
                if positioning_enabled_curr:
                    print("[UI] Включён режим позиционирования активных иконок")
                    self.mirrors.enable_positioning_mode()
                else:
                    print("[UI] Выключен режим позиционирования, сохраняю координаты")
                    self.mirrors.disable_positioning_mode(save_changes=True)
            except Exception as e:
                print("[UI] Ошибка переключения позиционирования:", e)
            self.positioning_enabled_last = positioning_enabled_curr
            
    def _handle_roi_selection(self) -> None:
        """Handle ROI selection."""
        selected = select_roi(self.hud.get_root())
        if selected is not None:
            left, top, width, height = selected
            self.roi = Region(left=left, top=top, width=width, height=height)
            
            # Save to settings
            self.settings.setdefault('roi', {})
            self.settings['roi']['mode'] = 'absolute'
            self.settings['roi']['left'] = left
            self.settings['roi']['top'] = top
            self.settings['roi']['width'] = width
            self.settings['roi']['height'] = height
            save_settings(self.settings_path, self.settings)
            
            self.hud.set_roi_info(left, top, width, height)
            
            if self.overlay_enabled_last:
                self.overlay.update((left, top, width, height))
                
    def _scan_frame(self) -> None:
        """Scan current frame for buffs."""
        frame_bgr = self.capture.grab(self.roi)
        if frame_bgr is None:
            self.hud.update([])
            return
            
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        found = self.matcher.match(gray)
        lib_results = self.lib_matcher.match(gray)
        
        self.hud.update(found)
        
        try:
            self.mirrors.update(
                lib_results,
                frame_bgr,
                (self.roi.left, self.roi.top, self.roi.width, self.roi.height)
            )
        except Exception:
            pass
            
        if found != self.last_found:
            print("Найдены шаблоны:", ", ".join(found) if found else "—")
            self.last_found = found
            
    def _clear_results(self) -> None:
        """Clear scan results when scanning is disabled."""
        if self.last_found:
            print("Найдены шаблоны: —")
            self.last_found = []
            
        self.hud.update([])
        
        try:
            self.mirrors.update([], None, (self.roi.left, self.roi.top, self.roi.width, self.roi.height))
        except Exception:
            pass

    def _refresh_copy_overlays(self) -> None:
        """Refresh copy area overlays after configuration changes."""
        try:
            self.mirrors.update(
                [],
                None,
                (self.roi.left, self.roi.top, self.roi.width, self.roi.height)
            )
        except Exception:
            pass

    def _update_currency_overlay(self, block: bool = False) -> None:
        """Refresh quick craft overlay captures when active or positioning."""
        if self.currency_overlay is None:
            return
        try:
            self.currency_overlay.refresh()
        except Exception as exc:
            print(f"[QuickCraft] Refresh failed: {exc}")

    def _trim_quickcraft_positions(self, valid_ids: Set[str]) -> None:
        if not isinstance(valid_ids, set):
            valid_ids = set(valid_ids)
        trimmed: Dict[str, Dict[str, object]] = {}
        for raw_id, cfg in self._quickcraft_positions.items():
            cid = str(raw_id)
            if cid not in valid_ids:
                continue
            try:
                left = int(cfg.get('left', 0))
                top = int(cfg.get('top', 0))
            except Exception:
                left, top = 0, 0
            hotkey = str(cfg.get('hotkey', '') or '').strip()
            trimmed[cid] = {'left': left, 'top': top, 'hotkey': hotkey}
        self._quickcraft_positions = trimmed

    def _register_quickcraft_hotkeys(self) -> None:
        # Per-item hotkeys are disabled; only global hotkey is used
        self._quickcraft_hotkey_map = {}
        try:
            self._quickcraft_global_hotkey = normalize_hotkey_name(load_global_hotkey())
        except Exception:
            self._quickcraft_global_hotkey = ''

    def _reload_quickcraft_data(self) -> None:
        self._quickcraft_positions = load_quickcraft_positions()
        if self._currencies_cache:
            active_ids = {str(entry.get('id')) for entry in self._currencies_cache if entry.get('id')}
            self._trim_quickcraft_positions(active_ids)
        self._register_quickcraft_hotkeys()
        if self._quickcraft_runtime_active:
            active_id = self._quickcraft_runtime_active
            if active_id not in self._quickcraft_positions:
                self._hide_quickcraft_overlay()
            else:
                self._show_quickcraft_overlay(active_id, force=True)

    def _build_position_map(self) -> Dict[str, Dict[str, int]]:
        mapping: Dict[str, Dict[str, int]] = {}
        # Start from saved quickcraft positions
        for cid, cfg in self._quickcraft_positions.items():
            cid = str(cid)
            try:
                left = int(cfg.get('left', 0))
                top = int(cfg.get('top', 0))
            except Exception:
                left, top = 0, 0
            mapping[cid] = {'left': left, 'top': top}

        # Fill missing or zero positions from currency capture defaults
        for item in (self._currencies_cache or []):
            cid = str(item.get('id') or '')
            if not cid:
                continue
            cap = item.get('capture') or {}
            cap_left = int(cap.get('left', 0))
            cap_top = int(cap.get('top', 0))
            if cid not in mapping:
                mapping[cid] = {'left': cap_left, 'top': cap_top}
            else:
                if mapping[cid].get('left', 0) == 0 and mapping[cid].get('top', 0) == 0:
                    mapping[cid] = {'left': cap_left, 'top': cap_top}
        return mapping

    def _build_position_map_from_anchor(self, anchor_left: int, anchor_top: int) -> Dict[str, Dict[str, int]]:
        """Build absolute positions from saved OFFSETS relative to an anchor square."""
        mapping: Dict[str, Dict[str, int]] = {}
        for cid, cfg in self._quickcraft_positions.items():
            cid = str(cid)
            try:
                off_left = int(cfg.get('left', 0))
                off_top = int(cfg.get('top', 0))
            except Exception:
                off_left, off_top = 0, 0
            mapping[cid] = {
                'left': int(anchor_left) + off_left,
                'top': int(anchor_top) + off_top,
            }
        return mapping

    def _get_center_anchor(self) -> tuple[int, int]:
        try:
            sw = int(self.hud.get_root().winfo_screenwidth())
            sh = int(self.hud.get_root().winfo_screenheight())
        except Exception:
            sw, sh = 1920, 1080
        size = 60
        return max(0, (sw - size) // 2), max(0, (sh - size) // 2)

    def _get_currency_by_id(self, currency_id: str) -> Optional[Dict]:
        for item in self._currencies_cache:
            if item.get('id') == currency_id:
                return item
        try:
            self._currencies_cache = load_currencies()
        except Exception:
            self._currencies_cache = []
            return None
        for item in self._currencies_cache:
            if item.get('id') == currency_id:
                return item
        return None

    def _show_quickcraft_overlay(self, currency_id: str, force: bool = False) -> None:
        if self.currency_overlay is None:
            return
        if not force and self._quickcraft_runtime_active == currency_id:
            return

        currency_id = str(currency_id)
        currency = self._get_currency_by_id(currency_id)
        if currency is None:
            return

        position_cfg = self._quickcraft_positions.get(currency_id, {})
        position_map = {
            currency_id: {
                'left': int(position_cfg.get('left', 0)),
                'top': int(position_cfg.get('top', 0)),
            }
        }
        self.currency_overlay.activate_runtime([currency], position_map)
        self._quickcraft_runtime_active = currency_id
        # No per-row UI marker required

    def _hide_quickcraft_overlay(self) -> None:
        if self.currency_overlay is not None:
            self.currency_overlay.deactivate_runtime()
        self._quickcraft_runtime_active = None
        self._quickcraft_runtime_active_ids = set()

    def _handle_quickcraft_hotkey(self, token: str) -> None:
        # Restrict to allowed processes; hide if currently showing and focus lost
        if not self._is_allowed_process_active():
            if self._quickcraft_runtime_active_ids or self._quickcraft_runtime_active:
                self._hide_quickcraft_overlay()
            return
        # Global hotkey takes precedence
        if self._quickcraft_global_hotkey and token == self._quickcraft_global_hotkey:
            # If user presses global hotkey while positioning, save current template first
            if self._currency_positioning_enabled:
                try:
                    self._disable_currency_positioning(save_changes=True)
                except Exception:
                    pass
            self._toggle_quickcraft_global()
            return
        currency_id = self._quickcraft_hotkey_map.get(token)
        if not currency_id:
            return
        if self._quickcraft_runtime_active == currency_id:
            self._hide_quickcraft_overlay()
        else:
            self._show_quickcraft_overlay(currency_id, force=True)

    def _toggle_quickcraft_global(self) -> None:
        if not self._is_allowed_process_active():
            return
        # If anything active -> hide all
        if self._quickcraft_runtime_active_ids:
            self._hide_quickcraft_overlay()
            return

        # Show all active currencies with saved positions
        currencies = [c for c in (self._currencies_cache or load_currencies()) if c.get('active')]
        # Build absolute positions using Win32 mouse coordinates as the center square
        try:
            cur_x, cur_y = win32api.GetCursorPos()
        except Exception:
            cur_x = self.roi.left + self.roi.width // 2
            cur_y = self.roi.top + self.roi.height // 2
        anchor_left = int(cur_x) - 30
        anchor_top = int(cur_y) - 30
        position_map = self._build_position_map_from_anchor(anchor_left, anchor_top)
        show_list = []
        ids: Set[str] = set()
        for c in currencies:
            cid = str(c.get('id'))
            if not cid:
                continue
            show_list.append(c)
            ids.add(cid)

        if not show_list:
            return
        try:
            self.currency_overlay.activate_runtime(show_list, position_map)
            self._quickcraft_runtime_active_ids = ids
            self._quickcraft_runtime_active = None
            self._anchor_at_hotkey = (int(cur_x), int(cur_y))
        except Exception as exc:
            print(f"[QuickCraft] Global show failed: {exc}")

    def _process_hotkeys(self) -> None:
        if self._hotkeys is None:
            # Fallback polling when hooks aren't available
            self._poll_hotkeys_fallback()
            return
        polled = self._hotkeys.poll()
        if polled:
            for token in polled:
                self._handle_quickcraft_hotkey(token)
        else:
            # If hook is installed but no events, also run fallback to support keys Tk may swallow
            self._poll_hotkeys_fallback()
        # Process quick craft click-triggered actions
        self._process_quickcraft_click_action()

    def _token_to_vk(self, token: str) -> Optional[int]:
        if not token:
            return None
        t = token.upper()
        if t.startswith('F') and t[1:].isdigit():
            n = int(t[1:])
            if 1 <= n <= 24:
                return getattr(win32con, f'VK_F{n}', None)
        if len(t) == 1 and 'A' <= t <= 'Z':
            return ord(t)
        if len(t) == 1 and '0' <= t <= '9':
            return ord(t)
        mapping = {
            'ESC': win32con.VK_ESCAPE,
            'ENTER': win32con.VK_RETURN,
            'SPACE': win32con.VK_SPACE,
            'TAB': win32con.VK_TAB,
            'UP': win32con.VK_UP,
            'DOWN': win32con.VK_DOWN,
            'LEFT': win32con.VK_LEFT,
            'RIGHT': win32con.VK_RIGHT,
            'HOME': win32con.VK_HOME,
            'END': win32con.VK_END,
            'PAGE_UP': win32con.VK_PRIOR,
            'PAGE_DOWN': win32con.VK_NEXT,
            'INSERT': win32con.VK_INSERT,
            'DELETE': win32con.VK_DELETE,
            'CTRL': win32con.VK_CONTROL,
            'ALT': win32con.VK_MENU,
            'SHIFT': win32con.VK_SHIFT,
        }
        return mapping.get(t)

    def _poll_hotkeys_fallback(self) -> None:
        if not sys.platform.startswith('win'):
            return
        now = time.time()
        # poll only keys that are mapped
        tokens = set(self._quickcraft_hotkey_map.keys())
        if self._quickcraft_global_hotkey:
            tokens.add(self._quickcraft_global_hotkey)
        for token in list(tokens):
            vk = self._token_to_vk(token)
            if vk is None:
                continue
            state = win32api.GetAsyncKeyState(vk)
            down = (state & 0x8000) != 0
            prev = self._key_down_state.get(token, False)
            if down and not prev:
                last = self._key_last_emit.get(token, 0.0)
                if now - last > 0.2:
                    self._key_last_emit[token] = now
                    self._handle_quickcraft_hotkey(token)
            self._key_down_state[token] = down

    def _move_cursor(self, x: int, y: int) -> None:
        try:
            ctypes.windll.user32.SetCursorPos(int(x), int(y))
        except Exception:
            pass

    def _click(self, left: bool = True) -> None:
        try:
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.mi.dwFlags = MOUSEEVENTF_LEFTDOWN if left else MOUSEEVENTF_RIGHTDOWN
            SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            time.sleep(0.01)
            inp2 = INPUT()
            inp2.type = INPUT_MOUSE
            inp2.mi.dwFlags = MOUSEEVENTF_LEFTUP if left else MOUSEEVENTF_RIGHTUP
            SendInput(1, ctypes.byref(inp2), ctypes.sizeof(INPUT))
        except Exception:
            pass

    def _process_quickcraft_click_action(self) -> None:
        # Only when allowed process is focused
        if not self._is_allowed_process_active():
            self._pending_click_currency_id = None
            return
        if not self._quickcraft_runtime_active_ids:
            self._pending_click_currency_id = None
            return
        now = time.time()
        # Read current left button state
        try:
            state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON)
        except Exception:
            return
        down = (state & 0x8000) != 0

        if self._pending_click_currency_id is None:
            # Waiting for a new click: if left is pressed over an overlay, arm the action
            if not down:
                return
            if now - self._last_click_time < 0.25:
                return
            hovered_id = None
            try:
                hovered_id = self.currency_overlay.get_hovered_currency_id()
            except Exception:
                hovered_id = None
            if not hovered_id:
                return
            self._pending_click_currency_id = str(hovered_id)
            return

        # Pending armed: wait until user releases left before executing
        if down:
            return

        hovered_id = self._pending_click_currency_id
        self._pending_click_currency_id = None
        self._last_click_time = now

        # Determine SOURCE location from the currency's original capture rect (true source)
        cur = self._get_currency_by_id(str(hovered_id)) or {}
        cap = cur.get('capture', {}) if isinstance(cur, dict) else {}
        try:
            src_left = int(cap.get('left', 0))
            src_top = int(cap.get('top', 0))
            w = max(1, int(cap.get('width', 1)))
            h = max(1, int(cap.get('height', 1)))
        except Exception:
            src_left, src_top, w, h = 0, 0, 32, 32
        cx = int(src_left + w // 2)
        cy = int(src_top + h // 2)

        # Original anchor point to return to (F3 press location)
        if self._anchor_at_hotkey is None:
            try:
                ax, ay = win32api.GetCursorPos()
            except Exception:
                ax = self.roi.left + self.roi.width // 2
                ay = self.roi.top + self.roi.height // 2
        else:
            ax, ay = self._anchor_at_hotkey

        # Execute sequence: move to SOURCE, right click, return, left click
        time.sleep(0.02)
        self._move_cursor(cx, cy)
        time.sleep(0.03)
        self._click(left=False)
        time.sleep(0.03)
        self._move_cursor(ax, ay)
        time.sleep(0.03)
        self._click(left=True)

    def _enable_currency_positioning(self) -> None:
        if self.currency_overlay is None:
            return

        intermediate = {}
        if self._currency_positioning_enabled:
            intermediate = self.currency_overlay.disable_positioning(save_changes=False)
        else:
            self._quickcraft_positions = load_quickcraft_positions()

        if intermediate:
            for cid, pos in intermediate.items():
                cid_key = str(cid)
                cfg = self._quickcraft_positions.get(cid_key, {})
                cfg['left'] = int(pos.get('left', 0))
                cfg['top'] = int(pos.get('top', 0))
                cfg['hotkey'] = str(cfg.get('hotkey', '') or '').strip()
                self._quickcraft_positions[cid_key] = cfg

        currencies = load_currencies()
        self._currencies_cache = currencies
        active_ids = {str(entry.get('id')) for entry in currencies if entry.get('id')}
        self._trim_quickcraft_positions(active_ids)

        try:
            # Place windows around center guide using saved OFFSETS
            anchor_left, anchor_top = self._get_center_anchor()
            position_map = self._build_position_map_from_anchor(anchor_left, anchor_top)
            self.currency_overlay.enable_positioning(currencies, position_map)
            self._currency_positioning_enabled = True
            self.hud.set_currency_positioning(True)
        except Exception as exc:
            print(f"[QuickCraft] Failed to enable positioning: {exc}")
            self._currency_positioning_enabled = False
        self._register_quickcraft_hotkeys()

    def _disable_currency_positioning(self, save_changes: bool = True) -> None:
        if self.currency_overlay is None:
            return

        if not self._currency_positioning_enabled and not save_changes:
            return

        updated = {}
        try:
            updated = self.currency_overlay.disable_positioning(save_changes=save_changes)
        except Exception as exc:
            print(f"[QuickCraft] Failed to disable positioning: {exc}")

        if save_changes:
            if updated:
                # Extract center anchor from special window if present
                center = updated.pop('__center__', None)
                if center is not None:
                    try:
                        a_left = int(center.get('left', 0))
                        a_top = int(center.get('top', 0))
                    except Exception:
                        a_left, a_top = self._get_center_anchor()
                else:
                    a_left, a_top = self._get_center_anchor()

                for cid, pos in updated.items():
                    cid_key = str(cid)
                    try:
                        abs_left = int(pos.get('left', 0))
                        abs_top = int(pos.get('top', 0))
                    except Exception:
                        abs_left, abs_top = 0, 0
                    off_left = abs_left - a_left
                    off_top = abs_top - a_top
                    cfg = self._quickcraft_positions.get(cid_key, {})
                    cfg['left'] = int(off_left)
                    cfg['top'] = int(off_top)
                    cfg['hotkey'] = str(cfg.get('hotkey', '') or '').strip()
                    self._quickcraft_positions[cid_key] = cfg
            currencies = load_currencies()
            self._currencies_cache = currencies
            active_ids = {str(entry.get('id')) for entry in currencies if entry.get('id')}
            self._trim_quickcraft_positions(active_ids)
            try:
                save_quickcraft_positions(self._quickcraft_positions)
            except Exception as exc:
                print(f"[QuickCraft] Failed to save positions: {exc}")
            self._register_quickcraft_hotkeys()
            if self._quickcraft_runtime_active and self._quickcraft_runtime_active in self._quickcraft_positions:
                self._show_quickcraft_overlay(self._quickcraft_runtime_active, force=True)

        self._currency_positioning_enabled = False
        self.hud.set_currency_positioning(False)

    def _handle_triple_ctrl_click(self) -> None:
        """Handle double Ctrl press detection and mouse emulation lifecycle.

        Double press (within 300ms) starts emulation. Releasing Ctrl stops it.
        We detect only rising edges (Up -> Down) to avoid auto-repeat while holding Ctrl.
        """
        if not sys.platform.startswith('win'):
            return

        try:
            # Only operate in allowed processes
            if not self._is_allowed_process_active():
                if self._triple_ctrl_click_active:
                    self._stop_mouse_simulation()
                return
            state = win32api.GetAsyncKeyState(win32con.VK_CONTROL)
            ctrl_held = (state & 0x8000) != 0

            # Rising edge detection to avoid typematic repeats while holding
            rising_edge = ctrl_held and not self._ctrl_prev_held
            if rising_edge:
                now = time.time()
                if now - self._last_ctrl_press_time <= 0.3:
                    self._ctrl_press_count += 1
                else:
                    self._ctrl_press_count = 1
                self._last_ctrl_press_time = now

                # Start on double press (do not toggle off here)
                if self._ctrl_press_count >= 2 and not self._triple_ctrl_click_active:
                    self._start_mouse_simulation()
                    print("[Double Ctrl] Mouse simulation started")
                    self._ctrl_press_count = 0

            # Stop when Ctrl is released
            if self._triple_ctrl_click_active and not ctrl_held:
                self._stop_mouse_simulation()
                print("[Double Ctrl] Mouse simulation stopped")

            # Update previous state
            self._ctrl_prev_held = ctrl_held

        except Exception as e:
            print(f"[Double Ctrl] Error: {e}")

    def _start_mouse_simulation(self) -> None:
        """Start simulating continuous left mouse button clicks every 20ms."""
        if not sys.platform.startswith('win'):
            return
        try:
            import threading
            # Set active first to avoid race on thread start
            self._triple_ctrl_click_active = True
            self.hud.set_click_emulation_state(True)
            self._mouse_simulation_thread = threading.Thread(target=self._mouse_click_loop, daemon=True)
            self._mouse_simulation_thread.start()
        except Exception as e:
            print(f"[Double Ctrl] Error starting mouse simulation: {e}")

    def _stop_mouse_simulation(self) -> None:
        """Stop simulating left mouse button clicks."""
        if not sys.platform.startswith('win'):
            return
        try:
            self._triple_ctrl_click_active = False
            self.hud.set_click_emulation_state(False)
            # Wait a bit for the thread to stop
            if hasattr(self, '_mouse_simulation_thread'):
                self._mouse_simulation_thread.join(timeout=0.1)
        except Exception as e:
            print(f"[Double Ctrl] Error stopping mouse simulation: {e}")

    def _mouse_click_loop(self) -> None:
        """Loop that simulates mouse clicks every 50ms using SendInput."""
        while self._triple_ctrl_click_active:
            try:
                # Create mouse down input
                down_input = INPUT()
                down_input.type = INPUT_MOUSE
                down_input.mi.dwFlags = MOUSEEVENTF_LEFTDOWN

                # Create mouse up input
                up_input = INPUT()
                up_input.type = INPUT_MOUSE
                up_input.mi.dwFlags = MOUSEEVENTF_LEFTUP

                # Send mouse down
                SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
                time.sleep(0.01)  # Short press duration

                # Send mouse up
                SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
                time.sleep(0.04)  # Wait before next click (total 50ms)

            except Exception as e:
                print(f"[Double Ctrl] Error in click loop: {e}")
                break

    def _update_dock_position_settings(self) -> None:
        """Persist floating dock position into settings."""
        position = self.hud.get_dock_position()
        if not position:
            return

        try:
            left = int(position[0])
            top = int(position[1])
        except Exception:
            return

        ui_cfg = self.settings.setdefault("ui", {})
        dock_cfg = ui_cfg.setdefault("dock_position", {})
        if dock_cfg.get("left") == left and dock_cfg.get("top") == top:
            return

        dock_cfg["left"] = left
        dock_cfg["top"] = top
        save_settings(self.settings_path, self.settings)

    def _apply_focus_policy(self, game_in_focus: bool) -> None:
        """Pause or resume application features based on foreground focus."""
        # Don't override user's dock visibility setting
        # The dock visibility is controlled by the settings checkbox

        # Copy Areas should only be visible in allowed processes
        if game_in_focus:
            if self._focus_state_last is False:
                self.hud.set_status_message('')
            # Keep user's requested toggles; only apply effective overlay state
            self.mirrors.set_copy_enabled(self._copy_user_requested)
        else:
            if self._focus_state_last in (True, None):
                self.hud.set_status_message(
                    t(
                        'status.game_focus_required',
                        'Focus the Path of Exile window to resume.',
                    ),
                    level='warning',
                )

            if self.overlay_enabled_last:
                try:
                    self.overlay.hide()
                except Exception:
                    pass
                self.overlay_enabled_last = False
            self.mirrors.set_copy_enabled(False)
            # Hide any runtime currency overlays when not allowed
            try:
                self._hide_quickcraft_overlay()
            except Exception:
                pass

        self._focus_state_last = game_in_focus
    
    def _is_allowed_process_active(self) -> bool:
        """Check if one of the allowed game processes is in foreground (focus)."""
        foreground_process = get_foreground_process_name()
        
        if foreground_process is None:
            # Can't determine - assume not active
            return False
        
        normalized = foreground_process.strip().lower()
        is_game_focused = normalized in self.allowed_processes
        
        # Debug: print when state changes
        if not hasattr(self, '_last_foreground') or self._last_foreground != foreground_process:
            if is_game_focused:
                print(f"[Game Focus] Game in focus: {foreground_process}")
            self._last_foreground = foreground_process
        if is_game_focused:
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd:
                    self._last_allowed_hwnd = hwnd
            except Exception:
                pass
        
        return is_game_focused
            
    def _cleanup(self) -> None:
        """Cleanup application resources."""
        try:
            self._disable_currency_positioning(save_changes=True)
        except Exception:
            pass

        try:
            self._hide_quickcraft_overlay()
        except Exception:
            pass

        if self._hotkeys is not None:
            try:
                self._hotkeys.stop()
            except Exception:
                pass

        self.hud.close()
        
        try:
            self.overlay.hide()
            self.overlay.close()
        except Exception:
            pass
            
        try:
            self.mirrors.disable_positioning_mode(save_changes=True)
        except Exception:
            pass
            
        try:
            self.mirrors.close()
        except Exception:
            pass
            
        try:
            if self.currency_overlay is not None:
                self.currency_overlay.close()
        except Exception:
            pass

        try:
            self.tray.stop()
        except Exception:
            pass
            
        self.capture.close()

    def _parse_sequence_tokens(self, seq: str) -> list[str]:
        tokens: list[str] = []
        raw = (seq or '').replace(';', ',').replace(' ', ',')
        for part in raw.split(','):
            tok = part.strip().upper()
            if tok:
                tokens.append(tok)
        return tokens

    def _key_press(self, vk: int) -> None:
        try:
            win32api.keybd_event(int(vk), 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(int(vk), 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    def _run_mega_qol_sequence(self) -> None:
        tokens = self._parse_sequence_tokens(self._mega_qol_seq_str)
        delay = max(0, int(self._mega_qol_delay_ms)) / 1000.0
        for tok in tokens:
            vk = self._token_to_vk(tok)
            if vk is None:
                continue
            self._key_press(vk)
            if delay:
                time.sleep(delay)

    def _process_mega_qol_wheel(self, focus_active: bool) -> None:
        if not sys.platform.startswith('win') or self._mouse is None:
            return
        # Always poll to avoid queue growth even when not focused/disabled
        try:
            events = self._mouse.poll()
        except Exception:
            events = []

        any_down = False
        now = time.time()
        for evt in events:
            if evt == 'WHEEL_DOWN':
                any_down = True
                self._mega_qol_last_wheel = now

        if not self._mega_qol_enabled or not focus_active:
            return

        # Rearm after quiet period
        if self._mega_qol_suppress and (now - self._mega_qol_last_wheel) > 0.05:
            self._mega_qol_suppress = False

        # On first event of a burst, emit once and suppress until quiet
        if any_down and not self._mega_qol_suppress:
            self._mega_qol_suppress = True
            try:
                self._run_mega_qol_sequence()
            except Exception:
                pass

