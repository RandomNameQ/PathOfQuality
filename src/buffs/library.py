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


@dataclass
class CopyAreaEntry:
    id: str
    name: Dict[str, str]
    image_path: str
    references: Dict[str, List[str]]  # {"buffs": [...], "debuffs": [...]}
    capture: Dict[str, int]           # {"left": int, "top": int, "width": int, "height": int}
    position: Dict[str, int]
    size: Dict[str, int]
    active: bool
    transparency: float
    topmost: bool


def _ensure_file():
    os.makedirs('assets', exist_ok=True)
    if not os.path.isfile(LIB_PATH):
        with open(LIB_PATH, 'w', encoding='utf-8') as f:
            json.dump({"buffs": [], "debuffs": [], "copy_areas": []}, f, ensure_ascii=False, indent=2)


def load_library() -> Dict[str, List[Dict]]:
    _ensure_file()
    try:
        with open(LIB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"buffs": [], "debuffs": []}
        data.setdefault('buffs', [])
        data.setdefault('debuffs', [])
        data.setdefault('copy_areas', [])
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
        for item in data.get('copy_areas', []):
            item.setdefault('name', {"en": ""})
            item.setdefault('image_path', '')
            refs = item.setdefault('references', {})
            refs.setdefault('buffs', [])
            refs.setdefault('debuffs', [])
            item.setdefault('capture', {"left": 0, "top": 0, "width": 0, "height": 0})
            item.setdefault('position', {"left": 0, "top": 0})
            item.setdefault('size', {"width": 64, "height": 64})
            item.setdefault('active', False)
            item.setdefault('transparency', 1.0)
            item.setdefault('topmost', True)
        return data
    except Exception:
        return {"buffs": [], "debuffs": [], "copy_areas": []}


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


def make_copy_area_entry(
    name_en: str,
    image_path: str,
    references: Optional[Dict[str, List[str]]]=None,
    capture: Optional[Dict[str, int]]=None,
    left: int = 0,
    top: int = 0,
    width: int = 64,
    height: int = 64,
    transparency: float = 1.0,
    topmost: bool = True,
) -> CopyAreaEntry:
    refs = references or {}
    capture_cfg = capture or {}
    return CopyAreaEntry(
        id=str(uuid.uuid4()),
        name={"en": name_en},
        image_path=image_path,
        references={
            'buffs': list(refs.get('buffs', [])),
            'debuffs': list(refs.get('debuffs', [])),
        },
        capture={
            'left': int(capture_cfg.get('left', 0)),
            'top': int(capture_cfg.get('top', 0)),
            'width': int(capture_cfg.get('width', 0)),
            'height': int(capture_cfg.get('height', 0)),
        },
        position={"left": int(left), "top": int(top)},
        size={"width": int(width), "height": int(height)},
        active=False,
        transparency=float(transparency),
        topmost=bool(topmost),
    )


def add_copy_area_entry(entry: CopyAreaEntry) -> None:
    lib = load_library()
    lib.setdefault('copy_areas', [])
    lib['copy_areas'].append(asdict(entry))
    save_library(lib)


def update_copy_area_entry(entry_id: str, updates: Dict) -> bool:
    lib = load_library()
    areas = lib.setdefault('copy_areas', [])
    for idx, item in enumerate(areas):
        if item.get('id') == entry_id:
            name = updates.get('name')
            if name:
                item['name'] = name
            image_path = updates.get('image_path')
            if image_path is not None:
                item['image_path'] = image_path
            refs = updates.get('references') or {}
            item['references'] = {
                'buffs': list(refs.get('buffs', item.get('references', {}).get('buffs', []))),
                'debuffs': list(refs.get('debuffs', item.get('references', {}).get('debuffs', []))),
            }
            capture_cfg = updates.get('capture')
            if capture_cfg:
                item['capture'] = {
                    'left': int(capture_cfg.get('left', item.get('capture', {}).get('left', 0))),
                    'top': int(capture_cfg.get('top', item.get('capture', {}).get('top', 0))),
                    'width': int(capture_cfg.get('width', item.get('capture', {}).get('width', 0))),
                    'height': int(capture_cfg.get('height', item.get('capture', {}).get('height', 0))),
                }
            item['position'] = {
                'left': int(updates.get('left', item.get('position', {}).get('left', 0))),
                'top': int(updates.get('top', item.get('position', {}).get('top', 0))),
            }
            item['size'] = {
                'width': int(updates.get('width', item.get('size', {}).get('width', 64))),
                'height': int(updates.get('height', item.get('size', {}).get('height', 64))),
            }
            if 'active' in updates:
                item['active'] = bool(updates.get('active'))
            if 'transparency' in updates:
                item['transparency'] = float(updates.get('transparency', item.get('transparency', 1.0)))
            if 'topmost' in updates:
                item['topmost'] = bool(updates.get('topmost'))
            areas[idx] = item
            lib['copy_areas'] = areas
            save_library(lib)
            return True
    return False