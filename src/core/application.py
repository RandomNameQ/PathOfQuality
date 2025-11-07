"""
Main application logic and event loop.
"""
import os
import sys
import cv2
from typing import List, Optional
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
    
    # Allowed process names for scanning
    ALLOWED_PROCESSES = {
        'PathOfExile.exe',
        'PathOfExileSteam.exe', 
        'PathOfExile2Steam.exe',
    }
    
    def __init__(self, settings_path: str = 'settings.json'):
        """
        Initialize application.
        
        Args:
            settings_path: Path to settings file
        """
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        
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
        self.hud = BuffHUD(
            templates=self.matcher.get_template_infos(),
            keep_on_top=bool(ui_cfg.get("keep_on_top", False)),
            alpha=float(ui_cfg.get("alpha", 1.0)),
            grab_anywhere=bool(ui_cfg.get("grab_anywhere", True)),
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
        self.hud.set_status_message('')
        
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
                game_is_active = self._is_allowed_process_active()

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

                if self.tray.is_exit_requested():
                    break

                self._apply_focus_policy(game_is_active)

                if refresh_copy:
                    self._refresh_copy_overlays()

                # Allow positioning toggles even when the game is unfocused
                self._handle_positioning_toggle()

                if skip_frame_processing:
                    if not game_is_active:
                        self._clear_results()
                    continue

                if not game_is_active:
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

    def _apply_focus_policy(self, game_is_active: bool) -> None:
        """Pause or resume application features based on foreground focus."""
        if game_is_active:
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

        self._focus_state_last = game_is_active
    
    def _is_allowed_process_active(self) -> bool:
        """Check if one of the allowed game processes is in foreground (focus)."""
        foreground_process = get_foreground_process_name()
        
        if foreground_process is None:
            # Can't determine - assume not active
            return False
        
        is_game_focused = foreground_process in self.ALLOWED_PROCESSES
        
        # Debug: print when state changes
        if not hasattr(self, '_last_foreground') or self._last_foreground != foreground_process:
            if is_game_focused:
                print(f"[Game Focus] Game in focus: {foreground_process}")
            else:
                print(f"[Game Focus] Other window focused: {foreground_process}")
            self._last_foreground = foreground_process
        
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

