"""
Path Of Quality application entry point.
Refactored version with modular architecture.
"""

import sys
import os

# Fix console encoding for Windows
if sys.platform.startswith("win"):
    try:
        # Set console to UTF-8
        _ = os.system("chcp 65001 > nul 2>&1")
        stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(stdout_reconfigure):
            stdout_reconfigure(encoding="utf-8")
        stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
        if callable(stderr_reconfigure):
            stderr_reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.i18n.locale import set_lang
from src.utils.settings import load_settings
from src.utils.screen import get_screen_size
from src.utils.roi import compute_roi
from src.core.application import Application


def main():
    """Main application entry point."""
    # Load settings
    settings = load_settings("settings.json")
    set_lang(settings.get("language", "en"))

    print("Path Of Quality")

    # Compute ROI
    screen_w, screen_h = get_screen_size()
    roi = compute_roi(settings, screen_w, screen_h)

    # Create and run application
    app = Application(settings_path="settings.json")
    app.initialize(roi)
    app.run()


if __name__ == "__main__":
    main()
