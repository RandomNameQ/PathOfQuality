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


def make_entry(
    entry_type: str,
    name_en: str,
    image_path: str,
    description_en: str = '',
    sound_on: Optional[str] = None,
    sound_off: Optional[str] = None,
    left: int = 0,
    top: int = 0,
    width: int = 0,
    height: int = 0,
    transparency: float = 1.0,
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
    )