import json
import os
import uuid
import shutil
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from pathlib import Path


# New structure: each object is a separate JSON file
LIBRARY_ROOT = os.path.join('assets', 'library')
BUFFS_DIR = os.path.join(LIBRARY_ROOT, 'buffs')
DEBUFFS_DIR = os.path.join(LIBRARY_ROOT, 'debuffs')
COPY_AREAS_DIR = os.path.join(LIBRARY_ROOT, 'copy_areas')
IMAGES_DIR = os.path.join(LIBRARY_ROOT, 'images')

# Old path for migration
OLD_LIB_PATH = os.path.join('assets', 'buffs.json')


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


def _ensure_directories():
    """Create library directories if they don't exist."""
    os.makedirs(BUFFS_DIR, exist_ok=True)
    os.makedirs(DEBUFFS_DIR, exist_ok=True)
    os.makedirs(COPY_AREAS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)


def copy_image_to_library(source_path: str) -> Optional[str]:
    """
    Copy image to library images directory.
    
    Args:
        source_path: Path to source image
        
    Returns:
        Relative path to copied image or None if failed
    """
    if not source_path or not os.path.isfile(source_path):
        return None
    
    try:
        _ensure_directories()
        
        # Generate unique filename using UUID
        ext = os.path.splitext(source_path)[1].lower()
        if not ext:
            ext = '.png'
        
        new_filename = f"{uuid.uuid4()}{ext}"
        dest_path = os.path.join(IMAGES_DIR, new_filename)
        
        # Copy file
        shutil.copy2(source_path, dest_path)
        
        # Return relative path from project root
        return os.path.join('assets', 'library', 'images', new_filename)
    except Exception:
        return None


def _load_json_from_directory(directory: str) -> List[Dict]:
    """Load all JSON files from a directory."""
    items = []
    if not os.path.isdir(directory):
        return items
    
    try:
        for filename in os.listdir(directory):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    item = json.load(f)
                    if isinstance(item, dict):
                        items.append(item)
            except Exception:
                continue
    except Exception:
        pass
    
    return items


def _migrate_from_old_format():
    """Migrate data from old buffs.json to new structure."""
    if not os.path.isfile(OLD_LIB_PATH):
        return
    
    try:
        with open(OLD_LIB_PATH, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        _ensure_directories()
        
        # Migrate buffs
        for item in old_data.get('buffs', []):
            item_id = item.get('id', str(uuid.uuid4()))
            filepath = os.path.join(BUFFS_DIR, f"{item_id}.json")
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(item, f, ensure_ascii=False, indent=2)
        
        # Migrate debuffs
        for item in old_data.get('debuffs', []):
            item_id = item.get('id', str(uuid.uuid4()))
            filepath = os.path.join(DEBUFFS_DIR, f"{item_id}.json")
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(item, f, ensure_ascii=False, indent=2)
        
        # Migrate copy_areas
        for item in old_data.get('copy_areas', []):
            item_id = item.get('id', str(uuid.uuid4()))
            filepath = os.path.join(COPY_AREAS_DIR, f"{item_id}.json")
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(item, f, ensure_ascii=False, indent=2)
        
        # Rename old file to backup
        backup_path = OLD_LIB_PATH + '.old'
        if not os.path.exists(backup_path):
            os.rename(OLD_LIB_PATH, backup_path)
    except Exception:
        pass


def load_library() -> Dict[str, List[Dict]]:
    """Load library from separate JSON files."""
    _ensure_directories()
    _migrate_from_old_format()
    
    try:
        data = {
            'buffs': _load_json_from_directory(BUFFS_DIR),
            'debuffs': _load_json_from_directory(DEBUFFS_DIR),
            'copy_areas': _load_json_from_directory(COPY_AREAS_DIR),
        }
        
        # Apply default values
        for bucket in ('buffs', 'debuffs'):
            for item in data.get(bucket, []):
                if 'active' not in item:
                    item['active'] = False
                item.setdefault('position', {"left": 0, "top": 0})
                item.setdefault('size', {"width": 64, "height": 64})
                item.setdefault('transparency', 1.0)
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


def _save_item_to_file(item: Dict, directory: str) -> bool:
    """Save individual item to its JSON file."""
    try:
        item_id = item.get('id')
        if not item_id:
            return False
        
        _ensure_directories()
        filepath = os.path.join(directory, f"{item_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _delete_item_file(item_id: str, directory: str) -> bool:
    """Delete item's JSON file."""
    try:
        filepath = os.path.join(directory, f"{item_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        return True
    except Exception:
        return False


def add_entry(entry: BuffEntry) -> None:
    """Add a new buff/debuff entry."""
    directory = BUFFS_DIR if entry.type == 'buff' else DEBUFFS_DIR
    item_dict = asdict(entry)
    _save_item_to_file(item_dict, directory)


def update_entry(entry_id: str, entry_type: str, updates: Dict) -> bool:
    """Update an existing entry by id.

    Returns True if updated, False if not found.
    """
    directory = BUFFS_DIR if entry_type == 'buff' else DEBUFFS_DIR
    filepath = os.path.join(directory, f"{entry_id}.json")
    
    if not os.path.exists(filepath):
        return False
    
    try:
        # Load existing item
        with open(filepath, 'r', encoding='utf-8') as f:
            item = json.load(f)
        
        # Update fields
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
        
        # Save updated item
        return _save_item_to_file(item, directory)
    except Exception:
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
    """Add a new copy area entry."""
    item_dict = asdict(entry)
    _save_item_to_file(item_dict, COPY_AREAS_DIR)


def update_copy_area_entry(entry_id: str, updates: Dict) -> bool:
    """Update an existing copy area entry by id.
    
    Returns True if updated, False if not found.
    """
    filepath = os.path.join(COPY_AREAS_DIR, f"{entry_id}.json")
    
    if not os.path.exists(filepath):
        return False
    
    try:
        # Load existing item
        with open(filepath, 'r', encoding='utf-8') as f:
            item = json.load(f)
        
        # Update fields
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
        
        # Save updated item
        return _save_item_to_file(item, COPY_AREAS_DIR)
    except Exception:
        return False