"""Persistence helpers for quick craft positioning."""
import json
import os
from typing import Dict, Optional


POSITIONS_FILE = os.path.join('assets', 'library', 'quick_craft_positions.json')
GLOBAL_KEY = '__global__'


def _ensure_directory() -> None:
    directory = os.path.dirname(POSITIONS_FILE)
    os.makedirs(directory, exist_ok=True)


def _load_raw() -> Dict:
    try:
        with open(POSITIONS_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def load_positions() -> Dict[str, Dict[str, object]]:
    """Load stored quick craft configurations."""

    data = _load_raw()

    cleaned: Dict[str, Dict[str, object]] = {}
    for key, value in data.items():
        if key == GLOBAL_KEY:
            continue
        if not isinstance(value, dict):
            continue
        try:
            left = int(value.get('left', 0))
            top = int(value.get('top', 0))
            hotkey = value.get('hotkey')
            if hotkey is None:
                hotkey = ''
            else:
                hotkey = str(hotkey).strip()
            cleaned[str(key)] = {'left': left, 'top': top, 'hotkey': hotkey}
        except Exception:
            continue
    return cleaned


def save_positions(positions: Dict[str, Dict[str, object]]) -> None:
    """Persist provided quick craft configurations."""

    payload: Dict[str, Dict[str, object]] = {}
    for key, value in positions.items():
        if not isinstance(value, dict):
            continue
        try:
            payload[str(key)] = {
                'left': int(value.get('left', 0)),
                'top': int(value.get('top', 0)),
                'hotkey': str(value.get('hotkey', '') or '').strip(),
            }
        except Exception:
            continue

    # Preserve global section if present
    existing = _load_raw()
    if isinstance(existing.get(GLOBAL_KEY), dict):
        payload[GLOBAL_KEY] = existing[GLOBAL_KEY]

    _ensure_directory()
    with open(POSITIONS_FILE, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def update_position(currency_id: str, left: int, top: int) -> None:
    """Update single currency position and persist it."""

    if not currency_id:
        return
    positions = load_positions()
    cfg = positions.get(str(currency_id), {})
    cfg['left'] = int(left)
    cfg['top'] = int(top)
    cfg['hotkey'] = str(cfg.get('hotkey', '') or '').strip()
    positions[str(currency_id)] = cfg
    save_positions(positions)


def update_hotkey(currency_id: str, hotkey: Optional[str]) -> None:
    """Update stored hotkey for currency."""

    if not currency_id:
        return
    positions = load_positions()
    cfg = positions.get(str(currency_id), {})
    cfg['left'] = int(cfg.get('left', 0))
    cfg['top'] = int(cfg.get('top', 0))
    cfg['hotkey'] = str(hotkey or '').strip()
    positions[str(currency_id)] = cfg
    save_positions(positions)


def remove_position(currency_id: str) -> None:
    """Remove stored position for currency."""

    if not currency_id:
        return
    positions = load_positions()
    if str(currency_id) in positions:
        positions.pop(str(currency_id), None)
        save_positions(positions)


def load_global_hotkey() -> str:
    data = _load_raw()
    try:
        hot = str((data.get(GLOBAL_KEY) or {}).get('hotkey', '') or '').strip()
    except Exception:
        hot = ''
    return hot


def save_global_hotkey(hotkey: str) -> None:
    data = _load_raw()
    data[GLOBAL_KEY] = {'hotkey': str(hotkey or '').strip()}
    _ensure_directory()
    with open(POSITIONS_FILE, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
