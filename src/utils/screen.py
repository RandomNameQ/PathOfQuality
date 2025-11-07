"""
Screen and display utilities.
"""
import ctypes
from typing import Tuple


def get_screen_size() -> Tuple[int, int]:
    """
    Get the primary monitor screen size.
    
    Returns:
        Tuple of (width, height) in pixels
    """
    try:
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        # Fallback for non-Windows platforms
        return 1920, 1080

