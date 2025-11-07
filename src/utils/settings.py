"""
Settings management utilities.
"""
import os
import json
from typing import Dict, Any


def get_default_settings() -> Dict[str, Any]:
    """Return default application settings."""
    return {
        "capture": {"provider": "mss"},
        "roi": {"mode": "top_right", "width": 400, "height": 180, "top": 0, "left": 0},
        "threshold": 0.9,
        "scan_interval_ms": 50,
        "ui": {"keep_on_top": False, "alpha": 1.0, "grab_anywhere": True},
        "language": "en",
        "templates_dir": "assets/templates",
    }


def merge_dict(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge overlay dict into base dict."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_dict(base[key], value)
        else:
            base[key] = value
    return base


def load_settings(path: str) -> Dict[str, Any]:
    """
    Load settings from JSON file, merging with defaults.
    
    Args:
        path: Path to settings file
        
    Returns:
        Settings dictionary
    """
    defaults = get_default_settings()
    
    if not os.path.exists(path):
        return defaults
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return merge_dict(defaults, data)
    except Exception:
        return defaults


def save_settings(path: str, settings: Dict[str, Any]) -> None:
    """
    Save settings to JSON file.
    
    Args:
        path: Path to settings file
        settings: Settings dictionary to save
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

