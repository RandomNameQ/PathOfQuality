"""
Copy-specific mirror window to avoid impacting other overlays.
Uses the same base behavior as MirrorWindow with no additional hover effects.
"""
from __future__ import annotations

from src.ui.mirror_window import MirrorWindow


class CopyMirrorWindow(MirrorWindow):
    """Dedicated mirror window class for Copy Areas.

    Uses parent hover-hide behavior so copy areas disappear while hovered,
    enabling easy selection of the underlying UI.
    """
    pass
