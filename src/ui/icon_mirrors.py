"""
Icon mirrors overlay - refactored version.
Displays detected buff/debuff icons as overlay windows.
"""
import tkinter as tk
import cv2
from typing import Dict, List, Tuple, Optional, Set
from PIL import Image
from src.buffs.library import load_library, update_entry, update_copy_area_entry
from src.capture.base_capture import Region
from src.capture.mss_capture import MSSCapture
from src.ui.mirror_window import MirrorWindow
from src.ui.copy_mirror_window import CopyMirrorWindow
from src.ui.positioning import PositioningHelper


class IconMirrorsOverlay:
    """Manages overlay windows for displaying detected icons."""
    
    def __init__(self, master: tk.Tk) -> None:
        """
        Initialize icon mirrors overlay.
        
        Args:
            master: Parent Tk window
        """
        self._master = master
        self._mirrors: Dict[str, MirrorWindow] = {}
        self._last_ids: List[str] = []
        self._positioning: bool = False
        self._entry_types: Dict[str, str] = {}
        self._positioning_helper = PositioningHelper(grid_size=16, snap_threshold=8)
        self._copy_capture: Optional[MSSCapture] = None
        self._copy_enabled: bool = True
        
    def _get_or_create(self, entry_id: str) -> MirrorWindow:
        """Get existing or create new mirror window."""
        m = self._mirrors.get(entry_id)
        if m is None:
            m = MirrorWindow(self._master)
            self._mirrors[entry_id] = m
        return m

    def _get_or_create_copy(self, entry_id: str) -> MirrorWindow:
        """Get existing or create new copy-area mirror window (separate class)."""
        m = self._mirrors.get(entry_id)
        if m is None or not isinstance(m, CopyMirrorWindow):
            m = CopyMirrorWindow(self._master)
            self._mirrors[entry_id] = m
        return m

    def set_copy_enabled(self, enabled: bool) -> None:
        """Enable or disable copy area rendering."""
        self._copy_enabled = bool(enabled)

    def _ensure_copy_capture(self) -> MSSCapture:
        if self._copy_capture is None:
            self._copy_capture = MSSCapture()
        return self._copy_capture

    def _grab_copy_region(self, left: int, top: int, width: int, height: int):
        if width <= 0 or height <= 0:
            return None
        try:
            capture = self._ensure_copy_capture()
            region = Region(left=int(left), top=int(top), width=int(width), height=int(height))
            return capture.grab(region)
        except Exception:
            return None

    def _build_copy_preview(self, item: Dict) -> Image.Image:
        capture_cfg = item.get('capture', {}) or {}
        left = int(capture_cfg.get('left', 0))
        top = int(capture_cfg.get('top', 0))
        width = int(capture_cfg.get('width', 0))
        height = int(capture_cfg.get('height', 0))

        frame = self._grab_copy_region(left, top, width, height)
        if frame is None:
            base_w = max(1, int(item.get('size', {}).get('width', max(64, width))))
            base_h = max(1, int(item.get('size', {}).get('height', max(64, height))))
            placeholder = Image.new('RGBA', (base_w, base_h), (0, 255, 0, 90))
            return placeholder

        try:
            rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            img = Image.fromarray(rgba)
        except Exception:
            img = Image.new('RGBA', (max(1, width), max(1, height)), (0, 0, 0, 0))

        size_cfg = item.get('size', {}) or {}
        out_w = int(size_cfg.get('width', img.width))
        out_h = int(size_cfg.get('height', img.height))
        out_w = max(1, out_w)
        out_h = max(1, out_h)

        try:
            img = img.resize((out_w, out_h), Image.LANCZOS)
        except Exception:
            pass

        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img

    def _update_copy_areas(
        self,
        copy_areas: List[Dict],
        visible_ids: Set[str],
        show_ids: List[str],
        topmost_filter: Optional[bool] = None,
    ) -> List[str]:
        """Update copy areas and return list of IDs that should be lifted."""
        if not self._copy_enabled and not self._positioning:
            return []

        lifted_ids: List[str] = []
        for area in copy_areas:
            # Filter by topmost flag if specified
            if topmost_filter is not None:
                area_topmost = bool(area.get('topmost', True))
                if area_topmost != topmost_filter:
                    continue
            area_id = area.get('id')
            if not area_id:
                continue

            m = self._mirrors.get(area_id)

            if not bool(area.get('active', False)):
                if m is not None:
                    m.hide()
                continue
            # Ensure copy areas use dedicated window class
            m = self._get_or_create_copy(area_id)
            if m.is_hovered():
                show_ids.append(area_id)
                continue

            refs = area.get('references', {}) or {}
            linked_ids: Set[str] = set()
            linked_ids.update(str(x) for x in refs.get('buffs', []))
            linked_ids.update(str(x) for x in refs.get('debuffs', []))

            if not self._positioning and linked_ids and linked_ids & visible_ids:
                if m is not None:
                    m.hide()
                continue

            capture_cfg = area.get('capture', {}) or {}
            cap_left = int(capture_cfg.get('left', 0))
            cap_top = int(capture_cfg.get('top', 0))
            cap_width = int(capture_cfg.get('width', 0))
            cap_height = int(capture_cfg.get('height', 0))

            frame = self._grab_copy_region(cap_left, cap_top, cap_width, cap_height)
            if frame is None:
                img = self._build_copy_preview(area)
            else:
                try:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb)
                except Exception:
                    img = self._build_copy_preview(area)

            size_cfg = area.get('size', {}) or {}
            out_w = int(size_cfg.get('width', 0))
            out_h = int(size_cfg.get('height', 0))
            if out_w <= 0:
                out_w = 64
            if out_h <= 0:
                out_h = 64

            try:
                img = img.resize((out_w, out_h), Image.LANCZOS)
            except Exception:
                pass

            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            pos_cfg = area.get('position', {}) or {}
            alpha = float(area.get('transparency', 1.0))

            m = self._get_or_create_copy(area_id)
            if m.is_hovered():
                show_ids.append(area_id)
                continue

            m.update_image(img)
            m.show(
                int(pos_cfg.get('left', 0)),
                int(pos_cfg.get('top', 0)),
                int(img.width),
                int(img.height),
                alpha=alpha,
                topmost=bool(topmost_filter),
            )
            show_ids.append(area_id)
            # Track IDs that should be lifted (topmost=True copy areas)
            if topmost_filter is True:
                lifted_ids.append(area_id)
        
        return lifted_ids
        
    def update(
        self, 
        results: List[Dict], 
        frame_bgr,
        roi: Tuple[int, int, int, int]
    ) -> None:
        """
        Update mirror windows with detection results.
        
        Args:
            results: List of detection result dictionaries
            frame_bgr: BGR frame from capture
            roi: ROI tuple (left, top, width, height)
        """
        # Don't update in positioning mode
        if self._positioning:
            return
            
        # Load library settings
        lib = load_library()
        entries: Dict[str, Dict] = {}
        for bucket in ("buffs", "debuffs"):
            for it in lib.get(bucket, []):
                entries[it.get('id')] = it
                
        show_ids: List[str] = []
        visible_ids: Set[str] = set()
        
        # First pass: show copy areas with topmost=False (they should be below buffs/debuffs)
        _ = self._update_copy_areas(lib.get('copy_areas', []), visible_ids, show_ids, topmost_filter=False)
        
        # Process buffs/debuffs
        for r in results:
            entry_id = r.get('id')
            show_ids.append(entry_id)
            visible_ids.add(entry_id)  # Track visible buffs/debuffs
            
            item = entries.get(entry_id) or {}
            pos = item.get('position', {"left": 0, "top": 0})
            size = item.get('size', {"width": 64, "height": 64})
            alpha = float(item.get('transparency', 1.0))
            extend_bottom = int(item.get('extend_bottom', 0))
            if extend_bottom < 0:
                extend_bottom = 0

            m = self._get_or_create(entry_id)
            if m.is_hovered():
                continue
                
            # Extract detected region from frame
            x, y, w, h = (
                int(r.get('x', 0)), 
                int(r.get('y', 0)),
                int(r.get('w', 0)),
                int(r.get('h', 0))
            )
            
            try:
                frame_h, frame_w = frame_bgr.shape[:2]
                x0 = max(0, x)
                y0 = max(0, y)
                x1 = min(x + w, frame_w)
                y1 = min(y + h + extend_bottom, frame_h)
                
                if x1 <= x0 or y1 <= y0:
                    continue
                    
                crop_bgr = frame_bgr[y0:y1, x0:x1]
                crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            except Exception:
                continue
                
            try:
                img = Image.fromarray(crop_rgb)
                
                # Resize to configured output size
                out_w = int(size.get('width', 64))
                out_h = int(size.get('height', 64))
                if out_w <= 0:
                    out_w = 64
                if out_h <= 0:
                    out_h = 64
                out_h = max(1, out_h + extend_bottom)
                
                img = img.resize((out_w, out_h), Image.LANCZOS)
            except Exception:
                continue
                
            m.update_image(img)
            m.show(
                int(pos.get('left', 0)),
                int(pos.get('top', 0)),
                int(img.width),
                int(img.height),
                alpha=alpha,
                topmost=True,
            )
        
        # Second pass: show copy areas with topmost=True (they should be above buffs/debuffs)
        topmost_copy_ids = self._update_copy_areas(lib.get('copy_areas', []), visible_ids, show_ids, topmost_filter=True)
        
        # Lift topmost copy areas, but only if window state changed
        if set(show_ids) != set(self._last_ids):
            for copy_id in topmost_copy_ids:
                m = self._mirrors.get(copy_id)
                if m and m.visible:
                    try:
                        m.top.lift()
                    except Exception:
                        pass

        # Hide windows not in current results
        for k, m in list(self._mirrors.items()):
            if k not in show_ids:
                m.hide()
                
        self._last_ids = show_ids
        
    def reload_library(self) -> None:
        """Reload library settings."""
        # Settings will be reloaded on next update()
        pass
        
    def enable_positioning_mode(self) -> None:
        """Enable positioning mode for active icons."""
        lib = load_library()
        self._entry_types.clear()
        active_items: List[Dict] = []
        
        for bucket in ("buffs", "debuffs"):
            for it in lib.get(bucket, []):
                if bool(it.get('active', False)):
                    active_items.append(it)
                    self._entry_types[it.get('id')] = (
                        'buff' if bucket == 'buffs' else 'debuff'
                    )

        for it in lib.get('copy_areas', []):
            # copy areas доступны для позиционирования всегда,
            # даже если ещё не активированы в общем режиме
            active_items.append(it)
            self._entry_types[it.get('id')] = 'copy'
                    
        for it in active_items:
            entry_id = it.get('id')
            pos = it.get('position', {"left": 0, "top": 0})
            size = it.get('size', {"width": 64, "height": 64})
            alpha = float(it.get('transparency', 1.0))
            entry_type = self._entry_types.get(entry_id, 'buff')

            if entry_type == 'copy':
                base_img = self._build_copy_preview(it)
                size_w = max(1, int(size.get('width', base_img.width)))
                size_h = max(1, int(size.get('height', base_img.height)))
            else:
                path = it.get('image_path') or ''

                try:
                    base_img = Image.open(path).convert('RGBA') if path else \
                              Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                except Exception:
                    base_img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))

                size_w = max(64, int(size.get('width', 64)))
                size_h = max(64, int(size.get('height', 64)))
            
            m = self._get_or_create(entry_id)
            m.enable_positioning(
                base_img,
                size_w,
                size_h,
                on_snap=self._positioning_helper.create_snapper(entry_id, self._mirrors)
            )
            m.show(
                int(pos.get('left', 0)),
                int(pos.get('top', 0)),
                size_w,
                size_h,
                alpha=alpha,
                topmost=True
            )
                
        self._positioning = True
        
    def disable_positioning_mode(self, save_changes: bool = True) -> None:
        """
        Disable positioning mode.
        
        Args:
            save_changes: Whether to save position changes to library
        """
        if not self._positioning:
            return
            
        if save_changes:
            for entry_id, m in list(self._mirrors.items()):
                left, top, width, height = m.get_geometry()
                entry_type = self._entry_types.get(entry_id) or 'buff'
                
                try:
                    if entry_type == 'copy':
                        update_copy_area_entry(entry_id, {
                            'left': int(left),
                            'top': int(top),
                            'width': int(width),
                            'height': int(height),
                        })
                    else:
                        update_entry(entry_id, entry_type, {
                            'left': int(left),
                            'top': int(top),
                            'width': int(width),
                            'height': int(height),
                        })
                except Exception:
                    pass
                    
        # Disable interaction
        for m in list(self._mirrors.values()):
            m.disable_positioning()
            m.hide()
            
        self._positioning = False
        
    def close(self) -> None:
        """Close all mirror windows."""
        for m in list(self._mirrors.values()):
            m.close()
        self._mirrors.clear()
        if self._copy_capture is not None:
            try:
                self._copy_capture.close()
            except Exception:
                pass
            self._copy_capture = None

