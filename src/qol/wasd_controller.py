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
from typing import Callable, Dict, List, Optional, Set, Tuple


# Hook/message constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
PM_NOREMOVE = 0x0000
PM_REMOVE = 0x0001
LLKHF_INJECTED = 0x00000010

# Keyboard VK codes
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_MBUTTON = 0x04
VK_XBUTTON1 = 0x05
VK_XBUTTON2 = 0x06
VK_OEM_3 = 0xC0
SM_CXSCREEN = 0
SM_CYSCREEN = 1

_SKILL_CURSOR_IGNORED_VKS = {
    VK_LBUTTON,
    VK_RBUTTON,
    VK_MBUTTON,
    VK_XBUTTON1,
    VK_XBUTTON2,
    VK_SHIFT,
    VK_CONTROL,
    VK_LSHIFT,
    VK_RSHIFT,
    VK_LCONTROL,
    VK_RCONTROL,
}

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
KEYEVENTF_KEYUP = 0x0002

# System cursor constants
SPI_SETCURSORS = 0x0057
OCR_NORMAL = 32512
OCR_IBEAM = 32513
OCR_WAIT = 32514
OCR_CROSS = 32515
OCR_UP = 32516
OCR_SIZENWSE = 32642
OCR_SIZENESW = 32643
OCR_SIZEWE = 32644
OCR_SIZENS = 32645
OCR_SIZEALL = 32646
OCR_NO = 32648
OCR_HAND = 32649
OCR_APPSTARTING = 32650
OCR_HELP = 32651

CURSOR_IDS_TO_HIDE = (
    OCR_NORMAL,
    OCR_IBEAM,
    OCR_WAIT,
    OCR_CROSS,
    OCR_UP,
    OCR_SIZENWSE,
    OCR_SIZENESW,
    OCR_SIZEWE,
    OCR_SIZENS,
    OCR_SIZEALL,
    OCR_NO,
    OCR_HAND,
    OCR_APPSTARTING,
    OCR_HELP,
)

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

user32.CreateCursor.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
user32.CreateCursor.restype = wintypes.HANDLE

user32.DestroyCursor.argtypes = [wintypes.HANDLE]
user32.DestroyCursor.restype = wintypes.BOOL

user32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
user32.SetSystemCursor.restype = wintypes.BOOL

user32.SystemParametersInfoW.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    wintypes.UINT,
]
user32.SystemParametersInfoW.restype = wintypes.BOOL

user32.GetAsyncKeyState.argtypes = [wintypes.INT]
user32.GetAsyncKeyState.restype = wintypes.SHORT
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ULONG_PTR]
user32.keybd_event.restype = None

SendInput = user32.SendInput
SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
SendInput.restype = wintypes.UINT


class WasdController:
    def __init__(
        self,
        is_target_active: Optional[Callable[[], bool]] = None,
        offset_pixels: int = 100,
        enable_skill_cursor: bool = False,
        distance_skill_percent: int = 0,
        skill_cursor_delay_s: float = 0.0,
        input_delay_s: float = 0.0,
        tick_hz: float = 60.0,
        on_toggle: Optional[Callable[[], None]] = None,
        movement_keys: Optional[Dict[str, str]] = None,
        toggle_hotkey: Optional[list[str]] = None,
    ) -> None:
        self._on_toggle = on_toggle
        self._is_target_active = is_target_active or (lambda: True)
        self._offset_pixels = int(offset_pixels)
        self._tick_interval = 1.0 / max(1.0, float(tick_hz))
        self._center_offset_x = 0
        self._center_offset_y = 0
        self._enable_skill_cursor = bool(enable_skill_cursor)
        self._distance_skill_percent = max(0, int(distance_skill_percent))
        self._skill_cursor_delay_s = max(0.0, float(skill_cursor_delay_s))
        self._skill_input_delay_s = max(0.0, float(input_delay_s))
        self._skill_release_deadline = 0.0
        self._pending_skill_inputs: List[Tuple[float, int, int]] = []
        self._suppressed_skill_keyups: Set[int] = set()

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
        self._cursor_hidden = False

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

        try:
            if self._hook_thread_id is not None:
                if self._hook_queue_ready.is_set():
                    user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)

            if self._hook_thread is not None:
                self._hook_thread.join(timeout=1.0)
                self._hook_thread = None

            if self._worker_thread is not None:
                self._worker_thread.join(timeout=1.0)
                self._worker_thread = None
        finally:
            self._hook_thread_id = None
            self._hook_queue_ready.clear()
            self._exit_moving_active()

            with self._pressed_lock:
                self._pressed_vks.clear()
                self._held_vks.clear()
                self._skill_release_deadline = 0.0
                self._pending_skill_inputs.clear()
                self._suppressed_skill_keyups.clear()

    def set_offsets(self, top: int, bot: int, left: int, right: int) -> None:
        self._center_offset_x = int(right) - int(left)
        self._center_offset_y = int(bot) - int(top)

    def set_center_offset(self, offset_x: int, offset_y: int) -> None:
        self._center_offset_x = int(offset_x)
        self._center_offset_y = int(offset_y)

    def set_move_offset_pixels(self, offset_pixels: int) -> None:
        self._offset_pixels = max(0, int(offset_pixels))

    def set_skill_cursor_config(
        self,
        enabled: bool,
        distance_skill_percent: int,
        release_delay_s: float = 0.0,
        input_delay_s: float = 0.0,
    ) -> None:
        self._enable_skill_cursor = bool(enabled)
        self._distance_skill_percent = max(0, int(distance_skill_percent))
        self._skill_cursor_delay_s = max(0.0, float(release_delay_s))
        self._skill_input_delay_s = max(0.0, float(input_delay_s))
        if not self._enable_skill_cursor:
            with self._pressed_lock:
                self._skill_release_deadline = 0.0
                self._pending_skill_inputs.clear()
                self._suppressed_skill_keyups.clear()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self._exit_moving_active()
            with self._pressed_lock:
                self._skill_release_deadline = 0.0
                self._pending_skill_inputs.clear()
                self._suppressed_skill_keyups.clear()

    def _keyboard_callback(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode == 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP):
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = int(kb.vkCode)
            scan_code = int(kb.scanCode)
            flags = int(kb.flags)

            is_keydown = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_injected = bool(flags & LLKHF_INJECTED)
            intercept_skill_keydown = False
            suppress_keyup = False
            trigger_toggle = False
            with self._pressed_lock:
                was_held_before = vk in self._held_vks
                if is_keydown:
                    self._held_vks.add(vk)
                else:
                    self._held_vks.discard(vk)

                if (
                    not is_keydown
                    and not is_injected
                    and vk in self._suppressed_skill_keyups
                ):
                    self._suppressed_skill_keyups.discard(vk)
                    suppress_keyup = True

                if vk == self._toggle_main_vk:
                    if is_keydown:
                        if not self._toggle_main_down and self._toggle_mod_vks.issubset(
                            self._held_vks
                        ):
                            self._toggle_main_down = True
                            trigger_toggle = True
                    else:
                        self._toggle_main_down = False

                if vk in self._movement_vks:
                    if is_keydown:
                        self._pressed_vks.add(vk)
                    else:
                        self._pressed_vks.discard(vk)
                    if self._enabled and self._safe_is_target_active():
                        return 1

                if (
                    is_keydown
                    and not was_held_before
                    and not is_injected
                    and self._enabled
                    and self._enable_skill_cursor
                    and self._distance_skill_percent > 0
                    and bool(self._pressed_vks)
                    and vk not in self._movement_vks
                    and vk not in _SKILL_CURSOR_IGNORED_VKS
                    and vk != self._toggle_main_vk
                    and vk not in self._toggle_mod_vks
                ):
                    self._skill_release_deadline = (
                        time.perf_counter() + self._skill_cursor_delay_s
                    )
                    intercept_skill_keydown = True

            if suppress_keyup:
                return 1

            if trigger_toggle:
                if self._on_toggle:
                    self._on_toggle()
                return 1

            if intercept_skill_keydown and self._safe_is_target_active():
                with self._pressed_lock:
                    self._suppressed_skill_keyups.add(vk)
                self._move_cursor_to_current_target(include_skill=True)
                self._schedule_skill_input(vk, scan_code)
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
                if not self._enabled:
                    self._exit_moving_active()
                    time.sleep(self._tick_interval)
                    continue

                self._flush_pending_skill_inputs()
                dx, dy = self._compute_offset()
                has_input = (dx != 0) or (dy != 0)
                target_active = self._safe_is_target_active()
                should_move = self._enabled and target_active and has_input

                if should_move:
                    if not self._moving_active:
                        self._enter_moving_active()

                    center = self._get_foreground_window_center()
                    if center is not None:
                        skill_jump = self._compute_skill_cursor_jump()
                        x = int(center[0] + dx)
                        y = int(center[1] + dy)
                        if skill_jump is not None:
                            x += int(skill_jump[0])
                            y += int(skill_jump[1])
                        user32.SetCursorPos(x, y)
                else:
                    self._exit_moving_active()

                time.sleep(self._tick_interval)
        finally:
            self._exit_moving_active()

    def _compute_offset(self) -> Tuple[int, int]:
        with self._pressed_lock:
            vks = set(self._pressed_vks)
        horizontal, vertical = self._compute_direction_from_vks(vks)

        return horizontal * self._offset_pixels, vertical * self._offset_pixels

    def _compute_direction_from_vks(self, vks: Set[int]) -> Tuple[int, int]:
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

        return horizontal, vertical

    def _is_skill_cursor_active_locked(self, now: float) -> bool:
        if self._skill_release_deadline <= 0.0:
            return False
        if now < self._skill_release_deadline:
            return True
        self._skill_release_deadline = 0.0
        return False

    def _has_skill_cursor_trigger_key_down(
        self,
        movement_vks: Set[int],
        toggle_main_vk: int,
        toggle_mod_vks: Set[int],
    ) -> bool:
        for vk in range(256):
            if not (int(user32.GetAsyncKeyState(vk)) & 0x8000):
                continue
            if vk in _SKILL_CURSOR_IGNORED_VKS:
                continue
            if vk in movement_vks:
                continue
            if vk == toggle_main_vk:
                continue
            if vk in toggle_mod_vks:
                continue
            return True
        return False

    def _compute_skill_cursor_jump(self) -> Optional[Tuple[int, int]]:
        if not self._enable_skill_cursor or self._distance_skill_percent <= 0:
            return None

        now = time.perf_counter()
        with self._pressed_lock:
            horizontal, vertical = self._compute_direction_from_vks(self._pressed_vks)
            movement_vks = set(self._movement_vks)
            toggle_main_vk = int(self._toggle_main_vk)
            toggle_mod_vks = set(self._toggle_mod_vks)

        if horizontal == 0 and vertical == 0:
            return None

        trigger_key_down = self._has_skill_cursor_trigger_key_down(
            movement_vks,
            toggle_main_vk,
            toggle_mod_vks,
        )

        with self._pressed_lock:
            if trigger_key_down:
                self._skill_release_deadline = now + self._skill_cursor_delay_s
            elif not self._is_skill_cursor_active_locked(now):
                return None

        return self._compute_skill_jump_from_direction(horizontal, vertical)

    def _compute_skill_jump_from_direction(
        self, horizontal: int, vertical: int
    ) -> Optional[Tuple[int, int]]:
        if horizontal == 0 and vertical == 0:
            return None
        screen_w = max(1, int(user32.GetSystemMetrics(SM_CXSCREEN)))
        screen_h = max(1, int(user32.GetSystemMetrics(SM_CYSCREEN)))
        jump_x = int((screen_w * self._distance_skill_percent) / 100.0)
        jump_y = int((screen_h * self._distance_skill_percent) / 100.0)
        return horizontal * jump_x, vertical * jump_y

    def _move_cursor_to_current_target(self, include_skill: bool = False) -> bool:
        dx, dy = self._compute_offset()
        if dx == 0 and dy == 0:
            return False

        center = self._get_foreground_window_center()
        if center is None:
            return False

        x = int(center[0] + dx)
        y = int(center[1] + dy)
        if include_skill:
            with self._pressed_lock:
                horizontal, vertical = self._compute_direction_from_vks(
                    self._pressed_vks
                )
            skill_jump = self._compute_skill_jump_from_direction(horizontal, vertical)
            if skill_jump is not None:
                x += int(skill_jump[0])
                y += int(skill_jump[1])

        user32.SetCursorPos(x, y)
        return True

    def _schedule_skill_input(self, vk: int, scan_code: int) -> None:
        delay_s = max(0.0, float(self._skill_input_delay_s))
        if delay_s <= 0.0:
            self._emit_key_tap(vk, scan_code)
            return

        due_time = time.perf_counter() + delay_s
        with self._pressed_lock:
            self._pending_skill_inputs.append((due_time, int(vk), int(scan_code)))

    def _flush_pending_skill_inputs(self) -> None:
        now = time.perf_counter()
        ready: List[Tuple[int, int]] = []
        with self._pressed_lock:
            if not self._pending_skill_inputs:
                return

            pending: List[Tuple[float, int, int]] = []
            for due_time, vk, scan_code in self._pending_skill_inputs:
                if due_time <= now:
                    ready.append((vk, scan_code))
                else:
                    pending.append((due_time, vk, scan_code))
            self._pending_skill_inputs = pending

        for vk, scan_code in ready:
            self._emit_key_tap(vk, scan_code)

    def _emit_key_tap(self, vk: int, scan_code: int) -> None:
        user32.keybd_event(
            wintypes.BYTE(vk & 0xFF),
            wintypes.BYTE(scan_code & 0xFF),
            wintypes.DWORD(0),
            ULONG_PTR(0),
        )
        user32.keybd_event(
            wintypes.BYTE(vk & 0xFF),
            wintypes.BYTE(scan_code & 0xFF),
            wintypes.DWORD(KEYEVENTF_KEYUP),
            ULONG_PTR(0),
        )

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
        cx += self._center_offset_x
        cy += self._center_offset_y
        return cx, cy

    def _hold_mouse_once(self) -> None:
        if self._mouse_held:
            return
        down = INPUT()
        down.type = INPUT_MOUSE
        down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        SendInput(1, ctypes.pointer(down), ctypes.sizeof(INPUT))
        self._mouse_held = True

    def _release_mouse_once(self) -> None:
        if not self._mouse_held:
            return
        up = INPUT()
        up.type = INPUT_MOUSE
        up.mi.dwFlags = MOUSEEVENTF_LEFTUP
        SendInput(1, ctypes.pointer(up), ctypes.sizeof(INPUT))
        self._mouse_held = False

    def _enter_moving_active(self) -> None:
        self._hide_system_cursors_once()
        self._hold_mouse_once()
        self._moving_active = True

    def _exit_moving_active(self) -> None:
        self._release_mouse_once()
        self._restore_system_cursors_once()
        self._moving_active = False

    def _create_invisible_cursor(self) -> Optional[wintypes.HANDLE]:
        width = 32
        height = 32
        mask_size = (width * height) // 8
        and_mask = (ctypes.c_ubyte * mask_size)(*([0xFF] * mask_size))
        xor_mask = (ctypes.c_ubyte * mask_size)()

        cursor = user32.CreateCursor(
            0,
            0,
            0,
            width,
            height,
            ctypes.cast(and_mask, ctypes.c_void_p),
            ctypes.cast(xor_mask, ctypes.c_void_p),
        )
        if not cursor:
            return None
        return cursor

    def _hide_system_cursors_once(self) -> None:
        if self._cursor_hidden:
            return

        changed_any = False
        for cursor_id in CURSOR_IDS_TO_HIDE:
            cursor = self._create_invisible_cursor()
            if not cursor:
                continue
            if user32.SetSystemCursor(cursor, cursor_id):
                changed_any = True
            else:
                user32.DestroyCursor(cursor)

        self._cursor_hidden = changed_any

    def _restore_system_cursors_once(self) -> None:
        if not self._cursor_hidden:
            return
        user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
        self._cursor_hidden = False


__all__ = ["WasdController"]
