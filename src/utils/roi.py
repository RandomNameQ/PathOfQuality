"""
Region of Interest (ROI) utilities.
"""
from typing import Dict, Any
from src.capture.base_capture import Region


def compute_roi(settings: Dict[str, Any], screen_w: int, screen_h: int) -> Region:
    """
    Compute ROI region based on settings and screen dimensions.
    
    Args:
        settings: Application settings dictionary
        screen_w: Screen width in pixels
        screen_h: Screen height in pixels
        
    Returns:
        Region object with computed coordinates
    """
    roi_cfg = settings.get("roi", {})
    mode = roi_cfg.get("mode", "top_right")
    width = int(roi_cfg.get("width", 400))
    height = int(roi_cfg.get("height", 180))
    top = int(roi_cfg.get("top", 0))
    left = int(roi_cfg.get("left", 0))

    if mode == "top_right":
        left = max(0, screen_w - width)
        top = max(0, top)
    elif mode == "absolute":
        left = max(0, left)
        top = max(0, top)
    else:
        # fallback to top_right
        left = max(0, screen_w - width)
        top = max(0, top)

    width = min(width, screen_w)
    height = min(height, screen_h)
    
    return Region(left=left, top=top, width=width, height=height)

