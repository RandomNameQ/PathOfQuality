"""
PathOfQuality - Buff HUD Application
Refactored version with modular architecture.
"""
from src.i18n.locale import set_lang
from src.utils.settings import load_settings
from src.utils.screen import get_screen_size
from src.utils.roi import compute_roi
from src.core.application import Application


def main():
    """Main application entry point."""
    # Load settings
    settings = load_settings('settings.json')
    set_lang(settings.get('language', 'en'))
    
    # Compute ROI
    screen_w, screen_h = get_screen_size()
    roi = compute_roi(settings, screen_w, screen_h)
    
    # Create and run application
    app = Application(settings_path='settings.json')
    app.initialize(roi)
    app.run()


if __name__ == '__main__':
    main()

