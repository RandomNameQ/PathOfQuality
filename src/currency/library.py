"""Persistence helpers for currency tab entries."""
import json
import os
import uuid
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


CURRENCY_DIR = os.path.join('assets', 'library', 'currencies')


@dataclass
class CurrencyEntry:
    """Serialized structure for a currency entry."""

    id: str
    name: str
    interface: str
    image_path: str
    capture: Dict[str, int]
    active: bool = True


def _ensure_directory() -> None:
    """Make sure the storage directory exists."""

    os.makedirs(CURRENCY_DIR, exist_ok=True)


def _entry_path(entry_id: str) -> str:
    """Return absolute path to entry json file."""

    safe_id = str(entry_id).strip()
    return os.path.join(CURRENCY_DIR, f"{safe_id}.json")


def _normalize_capture(capture: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Build a capture dict with sane defaults."""

    data = capture or {}
    return {
        'left': int(data.get('left', 0)),
        'top': int(data.get('top', 0)),
        'width': max(0, int(data.get('width', 0))),
        'height': max(0, int(data.get('height', 0))),
    }


def load_currencies() -> List[Dict]:
    """Load all stored currencies."""

    _ensure_directory()
    items: List[Dict] = []

    try:
        for filename in os.listdir(CURRENCY_DIR):
            if not filename.lower().endswith('.json'):
                continue
            path = os.path.join(CURRENCY_DIR, filename)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    continue
                data.setdefault('id', os.path.splitext(filename)[0])
                data['name'] = str(data.get('name', '')).strip()
                data['interface'] = str(data.get('interface', '')).strip()
                data['image_path'] = str(data.get('image_path', '')).strip()
                data['capture'] = _normalize_capture(data.get('capture'))
                data['active'] = bool(data.get('active', False))
                items.append(data)
            except Exception:
                continue
    except FileNotFoundError:
        return []

    # Sort alphabetically by name for stable ordering
    items.sort(key=lambda item: (item.get('name') or '').lower())
    return items


def make_currency_entry(
    name: str,
    interface: str,
    image_path: str,
    capture: Optional[Dict[str, int]] = None,
    active: bool = True,
) -> CurrencyEntry:
    """Factory helper for new entries."""

    return CurrencyEntry(
        id=str(uuid.uuid4()),
        name=str(name or '').strip(),
        interface=str(interface or '').strip(),
        image_path=str(image_path or '').strip(),
        capture=_normalize_capture(capture),
        active=bool(active),
    )


def add_currency_entry(entry: CurrencyEntry) -> None:
    """Persist a newly created entry."""

    _ensure_directory()
    _save_entry(asdict(entry))


def update_currency_entry(entry_id: str, updates: Dict) -> bool:
    """Patch an existing entry with provided values."""

    if not entry_id:
        return False

    path = _entry_path(entry_id)
    if not os.path.isfile(path):
        return False

    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            data = {'id': entry_id}
    except Exception:
        data = {'id': entry_id}

    data['id'] = entry_id

    if 'name' in updates:
        data['name'] = str(updates.get('name', data.get('name', ''))).strip()
    if 'interface' in updates:
        data['interface'] = str(updates.get('interface', data.get('interface', ''))).strip()
    if 'image_path' in updates:
        data['image_path'] = str(updates.get('image_path', data.get('image_path', ''))).strip()
    if 'capture' in updates:
        data['capture'] = _normalize_capture(updates.get('capture'))
    else:
        data['capture'] = _normalize_capture(data.get('capture'))
    if 'active' in updates:
        data['active'] = bool(updates.get('active'))
    else:
        data['active'] = bool(data.get('active', False))

    return _save_entry(data)


def delete_currency_entry(entry_id: str) -> bool:
    """Remove entry file from disk."""

    if not entry_id:
        return False

    path = _entry_path(entry_id)
    try:
        if os.path.isfile(path):
            os.remove(path)
        return True
    except Exception:
        return False


def _save_entry(payload: Dict) -> bool:
    """Write payload to json file."""

    entry_id = str(payload.get('id') or '').strip()
    if not entry_id:
        return False

    payload['capture'] = _normalize_capture(payload.get('capture'))
    payload['name'] = str(payload.get('name', '')).strip()
    payload['interface'] = str(payload.get('interface', '')).strip()
    payload['image_path'] = str(payload.get('image_path', '')).strip()
    payload['active'] = bool(payload.get('active', False))

    path = _entry_path(entry_id)

    try:
        _ensure_directory()
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
