"""
Main application logic and event loop.
"""
import os
import cv2
from typing import List
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
        
        # Initialize tray
        self.tray = TrayIcon()
        self.tray.start()
        
        # Save initial ROI snapshot
        self._save_roi_snapshot()
        
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
                
                if event == 'EXIT' or self.tray.is_exit_requested():
                    break
                    
                if event == 'LIBRARY_UPDATED':
                    try:
                        self.lib_matcher.refresh()
                    except Exception:
                        pass
                        
                # Handle overlay toggle
                self._handle_overlay_toggle()
                
                # Handle positioning mode toggle
                self._handle_positioning_toggle()
                
                # Handle ROI selection
                if event == 'SELECT_ROI':
                    self._handle_roi_selection()
                    
                # Scan for buffs if enabled
                if self.hud.get_scanning_enabled():
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

