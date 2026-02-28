"""WASD-driven cursor/mouse controller for Windows.

Tracks held W/A/S/D with a low-level keyboard hook and, while active,
holds left mouse button and pins the cursor to the foreground window center
plus a directional offset.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable, Dict, Optional, Set, Tuple


# Hook/message constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000
PM_REMOVE = 0x0001

# Keyboard VK codes
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_OEM_3 = 0xC0

_TOKEN_TO_VK = {
    "SHIFT": VK_SHIFT,
    "CTRL": VK_CONTROL,
    "CONTROL": VK_CONTROL,
    "ALT": VK_MENU,
    "MENU": VK_MENU,
    "GRAVE": VK_OEM_3,
    "TILDE": VK_OEM_3,
    "OEM_3": VK_OEM_3,
}

DEFAULT_MOVEMENT_KEYS = {
    "up": "W",
    "left": "A",
    "down": "S",
    "right": "D",
}
DEFAULT_TOGGLE_HOTKEY = ["GRAVE"]

# SendInput constants
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

try:
    ULONG_PTR = wintypes.ULONG_PTR  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    ULONG_PTR = (
        ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
    )

try:
    LRESULT = wintypes.LRESULT  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    LRESULT = ctypes.c_long

try:
    HHOOK = wintypes.HHOOK  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    HHOOK = wintypes.HANDLE


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.INT, wintypes.WPARAM, wintypes.LPARAM
)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT

SendInput = user32.SendInput
SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
SendInput.restype = wintypes.UINT


class WasdController:
    def __init__(
        self,
        is_target_active: Optional[Callable[[], bool]] = None,
        offset_pixels: int = 100,
        tick_hz: float = 60.0,
        on_toggle: Optional[Callable[[], None]] = None,
        movement_keys: Optional[Dict[str, str]] = None,
        toggle_hotkey: Optional[list[str]] = None,
    ) -> None:
        self._on_toggle = on_toggle
        self._is_target_active = is_target_active or (lambda: True)
        self._offset_pixels = int(offset_pixels)
        self._tick_interval = 1.0 / max(1.0, float(tick_hz))
        self._top_offset = 0
        self._bot_offset = 0
        self._left_offset = 0
        self._right_offset = 0

        self._enabled = True
        self._pressed_vks: Set[int] = set()
        self._held_vks: Set[int] = set()
        self._pressed_lock = threading.Lock()

        self._movement_bindings: Dict[str, int] = {}
        self._movement_tokens: Dict[str, str] = {}
        self._movement_vks: Set[int] = set()
        self._toggle_main_vk = VK_OEM_3
        self._toggle_mod_vks: Set[int] = set()
        self._toggle_main_down = False
        self.configure_bindings(movement_keys, toggle_hotkey)

        self._stop_event = threading.Event()
        self._hook_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._hook_thread_id: Optional[int] = None
        self._hook_queue_ready = threading.Event()

        self._keyboard_hook = None
        self._keyboard_proc = LowLevelKeyboardProc(self._keyboard_callback)

        self._mouse_held = False
        self._moving_active = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_active(self) -> bool:
        return self._moving_active

    @property
    def pressed_keys(self) -> Set[str]:
        with self._pressed_lock:
            vks = set(self._pressed_vks)
        names = []
        if self._movement_bindings.get("up") in vks:
            names.append(self._movement_tokens.get("up", "W"))
        if self._movement_bindings.get("left") in vks:
            names.append(self._movement_tokens.get("left", "A"))
        if self._movement_bindings.get("down") in vks:
            names.append(self._movement_tokens.get("down", "S"))
        if self._movement_bindings.get("right") in vks:
            names.append(self._movement_tokens.get("right", "D"))
        return set(names)

    def configure_bindings(
        self,
        movement_keys: Optional[Dict[str, str]] = None,
        toggle_hotkey: Optional[list[str]] = None,
    ) -> None:
        movement_src = movement_keys or DEFAULT_MOVEMENT_KEYS
        parsed_movement: Dict[str, int] = {}
        parsed_tokens: Dict[str, str] = {}
        for direction in ("up", "left", "down", "right"):
            token = (
                str(movement_src.get(direction) or DEFAULT_MOVEMENT_KEYS[direction])
                .strip()
                .upper()
            )
            vk = self._token_to_vk(token)
            if vk is None:
                token = DEFAULT_MOVEMENT_KEYS[direction]
                vk = self._token_to_vk(token)
            if vk is None:
                continue
            parsed_movement[direction] = vk
            parsed_tokens[direction] = token

        if len(parsed_movement) < 4:
            parsed_movement = {
                "up": self._token_to_vk("W") or 0x57,
                "left": self._token_to_vk("A") or 0x41,
                "down": self._token_to_vk("S") or 0x53,
                "right": self._token_to_vk("D") or 0x44,
            }
            parsed_tokens = dict(DEFAULT_MOVEMENT_KEYS)

        toggle_tokens = toggle_hotkey or DEFAULT_TOGGLE_HOTKEY
        normalized_toggle: list[str] = []
        for token in toggle_tokens:
            normalized = str(token).strip().upper()
            if normalized:
                normalized_toggle.append(normalized)

        toggle_main = self._toggle_main_vk
        toggle_mods: Set[int] = set()
        for token in normalized_toggle:
            vk = self._token_to_vk(token)
            if vk is None:
                continue
            if token in ("SHIFT", "CTRL", "CONTROL", "ALT", "MENU"):
                toggle_mods.add(vk)
            else:
                toggle_main = vk

        if not normalized_toggle:
            toggle_main = VK_OEM_3
            toggle_mods = set()

        with self._pressed_lock:
            self._movement_bindings = parsed_movement
            self._movement_tokens = parsed_tokens
            self._movement_vks = set(parsed_movement.values())
            self._toggle_main_vk = toggle_main
            self._toggle_mod_vks = toggle_mods
            self._toggle_main_down = False
            self._pressed_vks = {
                vk for vk in self._pressed_vks if vk in self._movement_vks
            }

    def _token_to_vk(self, token: str) -> Optional[int]:
        tkn = str(token or "").strip().upper()
        if not tkn:
            return None
        if len(tkn) == 1 and "A" <= tkn <= "Z":
            return ord(tkn)
        if len(tkn) == 1 and "0" <= tkn <= "9":
            return ord(tkn)
        return _TOKEN_TO_VK.get(tkn)

    def start(self) -> None:
        if self._hook_thread is not None or self._worker_thread is not None:
            return

        self._stop_event.clear()

        self._hook_thread = threading.Thread(target=self._hook_loop, daemon=True)
        self._hook_thread.start()

        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._hook_thread_id is not None:
            if self._hook_queue_ready.is_set():
                user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)

        if self._hook_thread is not None:
            self._hook_thread.join(timeout=1.0)
            self._hook_thread = None

        if self._worker_thread is not None:
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None

        self._hook_thread_id = None
        self._hook_queue_ready.clear()
        self._moving_active = False

        with self._pressed_lock:
            self._pressed_vks.clear()
            self._held_vks.clear()

        self._release_mouse_once()

    def set_offsets(self, top: int, bot: int, left: int, right: int) -> None:
        self._top_offset = top
        self._bot_offset = bot
        self._left_offset = left
        self._right_offset = right

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self._moving_active = False
            self._release_mouse_once()

    def _keyboard_callback(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode == 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP):
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = int(kb.vkCode)

            is_keydown = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            with self._pressed_lock:
                if is_keydown:
                    self._held_vks.add(vk)
                else:
                    self._held_vks.discard(vk)

                if vk == self._toggle_main_vk:
                    if is_keydown:
                        if not self._toggle_main_down and self._toggle_mod_vks.issubset(
                            self._held_vks
                        ):
                            self._toggle_main_down = True
                            if self._on_toggle:
                                self._on_toggle()
                            return 1
                    else:
                        self._toggle_main_down = False

                if vk in self._movement_vks:
                    if is_keydown:
                        self._pressed_vks.add(vk)
                    else:
                        self._pressed_vks.discard(vk)
                    if self._enabled and self._safe_is_target_active():
                        return 1

        hook_handle = self._keyboard_hook or 0
        return user32.CallNextHookEx(hook_handle, nCode, wParam, lParam)

    def _hook_loop(self) -> None:
        self._hook_thread_id = kernel32.GetCurrentThreadId()
        module_handle = kernel32.GetModuleHandleW(None)
        msg = wintypes.MSG()

        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, PM_NOREMOVE)
        self._hook_queue_ready.set()

        self._keyboard_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._keyboard_proc, module_handle, 0
        )
        if not self._keyboard_hook:
            self._keyboard_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._keyboard_proc, 0, 0
            )

        try:
            while not self._stop_event.is_set():
                while user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, PM_REMOVE):
                    if msg.message == WM_QUIT:
                        self._stop_event.set()
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.005)
        finally:
            self._hook_queue_ready.clear()
            if self._keyboard_hook:
                user32.UnhookWindowsHookEx(self._keyboard_hook)
                self._keyboard_hook = None

    def _worker_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                dx, dy = self._compute_offset()
                has_input = (dx != 0) or (dy != 0)
                target_active = self._safe_is_target_active()
                should_move = self._enabled and target_active and has_input

                if should_move:
                    if not self._moving_active:
                        self._hold_mouse_once()
                        self._moving_active = True

                    center = self._get_foreground_window_center()
                    if center is not None:
                        x = int(center[0] + dx)
                        y = int(center[1] + dy)
                        user32.SetCursorPos(x, y)
                else:
                    if self._moving_active:
                        self._release_mouse_once()
                        self._moving_active = False

                time.sleep(self._tick_interval)
        finally:
            self._release_mouse_once()
            self._moving_active = False

    def _compute_offset(self) -> Tuple[int, int]:
        with self._pressed_lock:
            vks = set(self._pressed_vks)

        vertical = 0
        horizontal = 0

        if self._movement_bindings.get("up") in vks:
            vertical -= 1
        if self._movement_bindings.get("down") in vks:
            vertical += 1
        if self._movement_bindings.get("left") in vks:
            horizontal -= 1
        if self._movement_bindings.get("right") in vks:
            horizontal += 1

        return horizontal * self._offset_pixels, vertical * self._offset_pixels

    def _safe_is_target_active(self) -> bool:
        try:
            return bool(self._is_target_active())
        except Exception:
            return False

    def _get_foreground_window_center(self) -> Optional[Tuple[int, int]]:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None

        cx = (int(rect.left) + int(rect.right)) // 2
        cy = (int(rect.top) + int(rect.bottom)) // 2
        cx += self._right_offset - self._left_offset
        cy += self._bot_offset - self._top_offset
        return cx, cy

    def _hold_mouse_once(self) -> None:
        if self._mouse_held:
            return
        down = INPUT()
        down.type = INPUT_MOUSE
        down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        self._mouse_held = True

    def _release_mouse_once(self) -> None:
        if not self._mouse_held:
            return
        up = INPUT()
        up.type = INPUT_MOUSE
        up.mi.dwFlags = MOUSEEVENTF_LEFTUP
        SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        self._mouse_held = False


__all__ = ["WasdController"]
