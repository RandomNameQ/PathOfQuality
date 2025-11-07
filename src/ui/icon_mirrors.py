"""
Icon mirrors overlay - refactored version.
Displays detected buff/debuff icons as overlay windows.
"""
import tkinter as tk
import cv2
from typing import Dict, List, Tuple, Optional
from PIL import Image
from src.buffs.library import load_library, update_entry
from src.ui.mirror_window import MirrorWindow
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
        
    def _get_or_create(self, entry_id: str) -> MirrorWindow:
        """Get existing or create new mirror window."""
        m = self._mirrors.get(entry_id)
        if m is None:
            m = MirrorWindow(self._master)
            self._mirrors[entry_id] = m
        return m
        
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
        
        for r in results:
            entry_id = r.get('id')
            show_ids.append(entry_id)
            
            item = entries.get(entry_id) or {}
            pos = item.get('position', {"left": 0, "top": 0})
            size = item.get('size', {"width": 64, "height": 64})
            alpha = float(item.get('transparency', 1.0))
            extend_bottom = int(item.get('extend_bottom', 0))
            if extend_bottom < 0:
                extend_bottom = 0
                
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
                
            m = self._get_or_create(entry_id)
            m.update_image(img)
            m.show(
                int(pos.get('left', 0)),
                int(pos.get('top', 0)),
                int(img.width),
                int(img.height),
                alpha=alpha
            )
            
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
                    
        for it in active_items:
            entry_id = it.get('id')
            pos = it.get('position', {"left": 0, "top": 0})
            size = it.get('size', {"width": 64, "height": 64})
            alpha = float(it.get('transparency', 1.0))
            path = it.get('image_path') or ''
            
            try:
                base_img = Image.open(path).convert('RGBA') if path else \
                          Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            except Exception:
                base_img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                
            # Ensure minimum comfortable size
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
                alpha=alpha
            )
            
            try:
                m.top.lift()
                m.top.attributes('-topmost', True)
            except Exception:
                pass
                
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

