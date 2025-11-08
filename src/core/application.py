"""
Main application logic and event loop.
"""
import os
import sys
import json
import cv2
from typing import List, Optional, Set
from src.capture.mss_capture import MSSCapture
from src.capture.base_capture import Region
from src.detector.template_matcher import TemplateMatcher
from src.detector.library_matcher import LibraryMatcher
from src.ui.hud import BuffHUD
from src.ui.icon_mirrors import IconMirrorsOverlay
from src.ui.overlay import OverlayHighlighter
from src.ui.roi_selector import select_roi
from src.ui.tray import TrayIcon
from src.utils.settings import load_settings, save_settings
from src.i18n.locale import t

ALLOWED_PROCESSES_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "allowed_processes.json")
)

# Windows API for checking active process
if sys.platform.startswith('win'):
    import ctypes
    from ctypes import wintypes


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
        self.allowed_processes: Set[str] = self._load_allowed_processes()
        self.allowed_processes.update(self._get_self_process_names())
        self._focus_required = bool(self.settings.get("require_game_focus", True))
        
        # Initialize components
        self.capture: MSSCapture = None
        self.matcher: TemplateMatcher = None
        self.lib_matcher: LibraryMatcher = None
        self.hud: BuffHUD = None
        self.overlay: OverlayHighlighter = None
        self.mirrors: IconMirrorsOverlay = None
        self.tray: TrayIcon = None
        
        # State
        self.roi: Region = None
        self.last_found: List[str] = []
        self.overlay_enabled_last = False
        self.positioning_enabled_last = False
        self._scan_user_requested = False
        self._copy_user_requested = False
        self._focus_state_last: Optional[bool] = None
        
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
        templates_dir = self.settings.get("templates_dir", "assets/templates")
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
        )
        
        self.hud.set_roi_info(roi.left, roi.top, roi.width, roi.height)
        
        # Initialize overlays
        self.overlay = OverlayHighlighter(self.hud.get_root())
        self.mirrors = IconMirrorsOverlay(self.hud.get_root())
        self.mirrors.set_copy_enabled(self.hud.get_copy_area_enabled())
        
        # Initialize tray
        self.tray = TrayIcon()
        self.tray.start()
        
        # Save initial ROI snapshot
        self._save_roi_snapshot()

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
        defaults = {
            'pathofexile.exe',
            'pathofexilesteam.exe',
            'pathofexile2steam.exe',
        }
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

        if not processes:
            processes = defaults
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

        try:
            current = get_foreground_process_name()
            if current:
                names.add(current.strip().lower())
        except Exception:
            pass

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

    def _save_roi_snapshot(self) -> None:
        """Save ROI snapshot for debugging."""
        try:
            frame_bgr = self.capture.grab(self.roi)
            if frame_bgr is not None:
                os.makedirs('debug', exist_ok=True)
                snap_path = os.path.join('debug', 'roi_snapshot.png')
                cv2.imwrite(snap_path, frame_bgr)
                print(f"Снимок ROI сохранён: {snap_path}")
        except Exception:
            pass
            
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
                    self._restore_allowed_focus()
                    skip_frame_processing = True

                if self.tray.is_exit_requested():
                    break

                focus_active = game_in_focus or not self._focus_required

                self._apply_focus_policy(game_in_focus)

                if refresh_copy:
                    self._refresh_copy_overlays()

                # Allow positioning toggles even when the game is unfocused
                self._handle_positioning_toggle()

                if skip_frame_processing:
                    if not focus_active:
                        self._clear_results()
                    continue

                if not focus_active:
                    self._clear_results()
                    continue

                self._handle_overlay_toggle()

                if self._scan_user_requested:
                    self._scan_frame()
                else:
                    self._clear_results()

        finally:
            self._cleanup()
            
    def _handle_overlay_toggle(self) -> None:
        """Handle overlay enable/disable."""
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

        if not self._focus_required:
            if self._focus_state_last is False:
                self.hud.set_status_message('')
            self.mirrors.set_copy_enabled(self._copy_user_requested)
            self._focus_state_last = True
            return

        if game_in_focus:
            if self._focus_state_last is False:
                self.hud.set_status_message('')

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
            self.tray.stop()
        except Exception:
            pass
            
        self.capture.close()

