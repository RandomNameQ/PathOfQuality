"""Global hotkey listener utilities for quick craft."""
from __future__ import annotations

import ctypes
import threading
import queue
import time
from ctypes import wintypes
from typing import List, Optional

# Windows constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012

# Structures
try:
    ULONG_PTR = wintypes.ULONG_PTR  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for some Python builds
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

try:
    LRESULT = wintypes.LRESULT  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback
    LRESULT = ctypes.c_long


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(LRESULT, wintypes.INT, wintypes.WPARAM, wintypes.LPARAM)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def normalize_hotkey_name(name: str) -> str:
    """Normalize hotkey name into canonical uppercase representation."""
    token = (name or '').strip()
    if not token:
        return ''
    token = token.upper().replace(' ', '_')
    return token


def format_hotkey_display(name: str) -> str:
    """Format normalized hotkey name for UI display."""
    token = (name or '').strip()
    if not token:
        return ''
    token = token.replace('_', ' ').title()
    return token


def keysym_to_hotkey(keysym: str) -> Optional[str]:
    """Map Tk keysym to the same token format as vk_to_hotkey/HotkeyListener."""
    if not keysym:
        return None
    k = keysym
    # Standardize case like Tk emits
    base = k.upper()
    # Function keys and simple A-Z / 0-9
    if base.startswith('F') and base[1:].isdigit():
        try:
            n = int(base[1:])
            if 1 <= n <= 24:
                return f'F{n}'
        except Exception:
            pass
    if len(base) == 1 and base.isalnum():
        return base

    remap = {
        'ESCAPE': 'ESC',
        'RETURN': 'ENTER',
        'SPACE': 'SPACE',
        'TAB': 'TAB',
        'BACKSPACE': 'BACKSPACE',
        'HOME': 'HOME',
        'END': 'END',
        'LEFT': 'LEFT',
        'RIGHT': 'RIGHT',
        'UP': 'UP',
        'DOWN': 'DOWN',
        'DELETE': 'DELETE',
        'INSERT': 'INSERT',
        'PRIOR': 'PAGE_UP',  # PageUp
        'NEXT': 'PAGE_DOWN',  # PageDown
        'CAPS_LOCK': 'CAPS_LOCK',
        'CONTROL_L': 'CTRL',
        'CONTROL_R': 'CTRL',
        'SHIFT_L': 'SHIFT',
        'SHIFT_R': 'SHIFT',
        'ALT_L': 'ALT',
        'ALT_R': 'ALT',
        'MINUS': 'MINUS',
        'EQUAL': 'EQUAL',
        'COMMA': 'COMMA',
        'PERIOD': 'PERIOD',
        'SLASH': 'SLASH',
        'GRAVE': 'GRAVE',
        'BRACKETLEFT': 'LBRACKET',
        'BRACKETRIGHT': 'RBRACKET',
        'BACKSLASH': 'BACKSLASH',
        'QUOTERIGHT': 'QUOTE',
        'APOSTROPHE': 'QUOTE',
    }
    if base in remap:
        return remap[base]
    return normalize_hotkey_name(base)


def vk_to_hotkey(vk_code: int) -> Optional[str]:
    """Convert virtual-key code to normalized string."""
    if 0x30 <= vk_code <= 0x39:  # digits
        return chr(vk_code)
    if 0x41 <= vk_code <= 0x5A:  # letters
        return chr(vk_code)
    if 0x70 <= vk_code <= 0x7B:  # F1-F12
        return f"F{vk_code - 0x6F}"

    mapping = {
        0x08: 'BACKSPACE',
        0x09: 'TAB',
        0x0D: 'ENTER',
        0x13: 'PAUSE',
        0x14: 'CAPS_LOCK',
        0x1B: 'ESC',
        0x20: 'SPACE',
        0x21: 'PAGE_UP',
        0x22: 'PAGE_DOWN',
        0x23: 'END',
        0x24: 'HOME',
        0x25: 'LEFT',
        0x26: 'UP',
        0x27: 'RIGHT',
        0x28: 'DOWN',
        0x2D: 'INSERT',
        0x2E: 'DELETE',
        0x5B: 'WIN',
        0x5C: 'WIN',
        0x60: 'NUMPAD0',
        0x61: 'NUMPAD1',
        0x62: 'NUMPAD2',
        0x63: 'NUMPAD3',
        0x64: 'NUMPAD4',
        0x65: 'NUMPAD5',
        0x66: 'NUMPAD6',
        0x67: 'NUMPAD7',
        0x68: 'NUMPAD8',
        0x69: 'NUMPAD9',
        0x6A: 'NUMPAD_MULTIPLY',
        0x6B: 'NUMPAD_ADD',
        0x6D: 'NUMPAD_SUBTRACT',
        0x6E: 'NUMPAD_DECIMAL',
        0x6F: 'NUMPAD_DIVIDE',
        0xA0: 'SHIFT',
        0xA1: 'SHIFT',
        0xA2: 'CTRL',
        0xA3: 'CTRL',
        0xA4: 'ALT',
        0xA5: 'ALT',
        0xBA: 'SEMICOLON',
        0xBB: 'EQUAL',
        0xBC: 'COMMA',
        0xBD: 'MINUS',
        0xBE: 'PERIOD',
        0xBF: 'SLASH',
        0xC0: 'GRAVE',
        0xDB: 'LBRACKET',
        0xDC: 'BACKSLASH',
        0xDD: 'RBRACKET',
        0xDE: 'QUOTE',
    }
    name = mapping.get(vk_code)
    if name:
        return name

    scan = user32.MapVirtualKeyW(vk_code, 0)
    if scan:
        buffer = ctypes.create_unicode_buffer(64)
        made = user32.GetKeyNameTextW((scan << 16), buffer, 64)
        if made > 0:
            return normalize_hotkey_name(buffer.value)
    return None


class HotkeyListener:
    """Low-level global listener for keyboard key presses."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._keyboard_hook = None
        self._keyboard_proc = LowLevelKeyboardProc(self._keyboard_callback)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._last_emit: dict[str, float] = {}
        self._start()

    def _start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=1.0)

    def poll(self) -> List[str]:
        items: List[str] = []
        try:
            while True:
                items.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        return items

    def _emit(self, token: str) -> None:
        now = time.time()
        last = self._last_emit.get(token, 0.0)
        if now - last < 0.15:  # debounce repeats
            return
        self._last_emit[token] = now
        self._queue.put(token)

    def _keyboard_callback(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode == 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            kb_struct = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            hotkey = vk_to_hotkey(kb_struct.vkCode)
            if hotkey:
                self._emit(normalize_hotkey_name(hotkey))
        return user32.CallNextHookEx(self._keyboard_hook, nCode, wParam, lParam)

    def _loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        module_handle = kernel32.GetModuleHandleW(None)

        self._keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._keyboard_proc, module_handle, 0)

        msg = wintypes.MSG()
        while not self._stop_event.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
            self._keyboard_hook = None


__all__ = [
    'HotkeyListener',
    'normalize_hotkey_name',
    'format_hotkey_display',
    'keysym_to_hotkey',
]
