"""
Positioning logic for snap-to-grid and window alignment.
"""
from typing import Dict, Tuple, Callable


class PositioningHelper:
    """Helper for window positioning with grid snapping."""
    
    def __init__(self, grid_size: int = 16, snap_threshold: int = 8) -> None:
        """
        Initialize positioning helper.
        
        Args:
            grid_size: Size of snap grid in pixels
            snap_threshold: Distance threshold for snapping in pixels
        """
        self.grid_size = grid_size
        self.snap_threshold = snap_threshold
        
    def create_snapper(
        self, 
        my_id: str,
        all_windows: Dict[str, any]
    ) -> Callable[[int, int, int, int], Tuple[int, int]]:
        """
        Create snap function for a specific window.
        
        Args:
            my_id: ID of the window being positioned
            all_windows: Dictionary of all mirror windows
            
        Returns:
            Snap function that takes (x, y, w, h) and returns (x, y)
        """
        def snap(x: int, y: int, w: int, h: int) -> Tuple[int, int]:
            # Snap to grid
            try:
                gx = round(x / self.grid_size) * self.grid_size
                gy = round(y / self.grid_size) * self.grid_size
            except Exception:
                gx, gy = x, y
                
            sx, sy = int(gx), int(gy)
            
            # Snap to neighboring windows
            try:
                th = self.snap_threshold
                for k, m in all_windows.items():
                    if k == my_id:
                        continue
                        
                    try:
                        mx = int(m.top.winfo_x())
                        my = int(m.top.winfo_y())
                        mw = int(m.top.winfo_width())
                        mh = int(m.top.winfo_height())
                    except Exception:
                        continue
                        
                    # Horizontal edges
                    if abs(sx - mx) <= th:
                        sx = mx
                    if abs(sx - (mx + mw)) <= th:
                        sx = mx + mw
                        
                    right = sx + w
                    if abs(right - mx) <= th:
                        sx = mx - w
                    if abs(right - (mx + mw)) <= th:
                        sx = mx + mw - w
                        
                    # Vertical edges
                    if abs(sy - my) <= th:
                        sy = my
                    if abs(sy - (my + mh)) <= th:
                        sy = my + mh
                        
                    bottom = sy + h
                    if abs(bottom - my) <= th:
                        sy = my - h
                    if abs(bottom - (my + mh)) <= th:
                        sy = my + mh - h
            except Exception:
                pass
                
            return int(sx), int(sy)
            
        return snap

