import json
import os
from typing import Any, Dict, Optional

_LANG: str = 'en'
_TRANSLATIONS: Dict[str, str] = {}


def set_lang(lang: str) -> None:
    global _LANG, _TRANSLATIONS
    _LANG = 'en' if lang not in ('en', 'ru') else lang
    _TRANSLATIONS = {}
    path = os.path.join('assets', 'i18n', f'{_LANG}.json')
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _TRANSLATIONS = {str(k): str(v) for k, v in data.items()}
        except Exception:
            _TRANSLATIONS = {}


def get_lang() -> str:
    return _LANG


def t(key: str, fallback: Optional[str] = None) -> str:
    return _TRANSLATIONS.get(key, fallback if fallback is not None else key)