import json
import os
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


LIB_PATH = os.path.join('assets', 'buffs.json')


@dataclass
class BuffEntry:
    id: str
    type: str  # 'buff' or 'debuff'
    name: Dict[str, str]  # localized: {"en": "...", "ru": "..."}
    image_path: str
    description: Dict[str, str]
    sound_on: Optional[str]
    sound_off: Optional[str]
    position: Dict[str, int]  # {"left": int, "top": int}
    size: Dict[str, int]      # {"width": int, "height": int}
    transparency: float       # 0.0..1.0
    active: bool
    extend_bottom: int        # extra pixels to extend capture/output downward


def _ensure_file():
    os.makedirs('assets', exist_ok=True)
    if not os.path.isfile(LIB_PATH):
        with open(LIB_PATH, 'w', encoding='utf-8') as f:
            json.dump({"buffs": [], "debuffs": []}, f, ensure_ascii=False, indent=2)


def load_library() -> Dict[str, List[Dict]]:
    _ensure_file()
    try:
        with open(LIB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"buffs": [], "debuffs": []}
        data.setdefault('buffs', [])
        data.setdefault('debuffs', [])
        # миграция полей по умолчанию
        for bucket in ('buffs', 'debuffs'):
            for item in data.get(bucket, []):
                if 'active' not in item:
                    item['active'] = False
                item.setdefault('position', {"left": 0, "top": 0})
                # По умолчанию размер 64x64
                item.setdefault('size', {"width": 64, "height": 64})
                item.setdefault('transparency', 1.0)
                # Новое поле: дополнительная высота снизу
                item.setdefault('extend_bottom', 0)
        return data
    except Exception:
        return {"buffs": [], "debuffs": []}


def save_library(data: Dict[str, List[Dict]]) -> None:
    try:
        with open(LIB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def add_entry(entry: BuffEntry) -> None:
    lib = load_library()
    bucket = 'buffs' if entry.type == 'buff' else 'debuffs'
    lib[bucket].append(asdict(entry))
    save_library(lib)


def update_entry(entry_id: str, entry_type: str, updates: Dict) -> bool:
    """Update an existing entry by id.

    Returns True if updated, False if not found.
    """
    lib = load_library()
    bucket = 'buffs' if entry_type == 'buff' else 'debuffs'
    arr = lib.get(bucket, [])
    for i, item in enumerate(arr):
        if item.get('id') == entry_id:
            # keep id and type, update other fields
            item['name'] = updates.get('name') or item.get('name', {})
            item['image_path'] = updates.get('image_path') or item.get('image_path', '')
            item['description'] = updates.get('description') or item.get('description', {})
            item['sound_on'] = updates.get('sound_on')
            item['sound_off'] = updates.get('sound_off')
            item['position'] = {
                'left': int(updates.get('left', item.get('position', {}).get('left', 0))),
                'top': int(updates.get('top', item.get('position', {}).get('top', 0))),
            }
            item['size'] = {
                'width': int(updates.get('width', item.get('size', {}).get('width', 0))),
                'height': int(updates.get('height', item.get('size', {}).get('height', 0))),
            }
            item['transparency'] = float(updates.get('transparency', item.get('transparency', 1.0)))
            item['extend_bottom'] = int(updates.get('extend_bottom', item.get('extend_bottom', 0)))
            if 'active' in updates:
                item['active'] = bool(updates.get('active'))
            arr[i] = item
            lib[bucket] = arr
            save_library(lib)
            return True
    return False


def make_entry(
    entry_type: str,
    name_en: str,
    image_path: str,
    description_en: str = '',
    sound_on: Optional[str] = None,
    sound_off: Optional[str] = None,
    left: int = 0,
    top: int = 0,
    width: int = 64,
    height: int = 64,
    transparency: float = 1.0,
    extend_bottom: int = 0,
) -> BuffEntry:
    return BuffEntry(
        id=str(uuid.uuid4()),
        type='buff' if entry_type == 'buff' else 'debuff',
        name={"en": name_en},
        image_path=image_path,
        description={"en": description_en},
        sound_on=sound_on,
        sound_off=sound_off,
        position={"left": int(left), "top": int(top)},
        size={"width": int(width), "height": int(height)},
        transparency=float(transparency),
        active=False,
        extend_bottom=int(extend_bottom),
    )