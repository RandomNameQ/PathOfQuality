"""Settings and resource path utilities (works in dev and PyInstaller onefile)."""
import os
import sys
import json
from typing import Dict, Any


def get_default_settings() -> Dict[str, Any]:
    """Return default application settings."""
    return {
        "capture": {"provider": "mss"},
        "roi": {"mode": "top_right", "width": 400, "height": 180, "top": 0, "left": 0},
        "threshold": 0.9,
        "scan_interval_ms": 50,
        "require_game_focus": True,
        "ui": {
            "keep_on_top": False,
            "alpha": 1.0,
            "grab_anywhere": True,
            "dock_position": {"left": None, "top": None},
        },
        "language": "en",
        "templates_dir": "assets/templates",
        "triple_ctrl_click_enabled": False,
        "mega_qol": {
            "wheel_down_enabled": False,
            "wheel_down_sequence": "1,2,3,4",
            "wheel_down_delay_ms": 50,
        },
    }


def merge_dict(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge overlay dict into base dict."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_dict(base[key], value)
        else:
            base[key] = value
    return base


def _app_base_dir() -> str:
    """Directory for external, writable files (next to the executable in frozen mode)."""
    if getattr(sys, 'frozen', False):  # PyInstaller
        return os.path.dirname(sys.executable)
    # Dev: project root (two levels up from this file)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def resource_path(rel_path: str) -> str:
    """Resolve bundled resource path (MEIPASS in frozen, project root in dev)."""
    base = getattr(sys, '_MEIPASS', None)
    if not base:
        base = _app_base_dir()
    return os.path.abspath(os.path.join(base, rel_path.replace('/', os.sep)))


def load_settings(path: str) -> Dict[str, Any]:
    """
    Load settings from JSON file, merging with defaults.
    
    Args:
        path: Path to settings file
        
    Returns:
        Settings dictionary
    """
    defaults = get_default_settings()

    # Normalize relative paths to live next to the executable
    target_path = path
    if not os.path.isabs(target_path):
        target_path = os.path.join(_app_base_dir(), target_path)

    # If user settings exist externally, load them
    if os.path.exists(target_path):
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return merge_dict(defaults, data)
        except Exception:
            return defaults

    # If not, try to load bundled default and also copy it out for persistence
    bundled = resource_path(path)
    try:
        if os.path.exists(bundled):
            with open(bundled, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Persist a copy externally for user edits
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
            except Exception:
                pass
            try:
                with open(target_path, 'w', encoding='utf-8') as wf:
                    json.dump(data, wf, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return merge_dict(defaults, data)
    except Exception:
        pass

    # Fallback to hardcoded defaults
    return defaults


def save_settings(path: str, settings: Dict[str, Any]) -> None:
    """
    Save settings to JSON file.
    
    Args:
        path: Path to settings file
        settings: Settings dictionary to save
    """
    try:
        # Save next to the executable by default
        target_path = path
        if not os.path.isabs(target_path):
            target_path = os.path.join(_app_base_dir(), target_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


