# pyright: reportAny=false, reportExplicitAny=false, reportUnannotatedClassAttribute=false

import ctypes
import os
import sys
from ctypes import wintypes
from typing import Any


ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167
_FORCE_UNAVAILABLE_ENV = "POQ_XINPUT_FORCE_UNAVAILABLE"
_DLL_CANDIDATES = ("XInput1_4.dll", "XInput1_3.dll", "XInput9_1_0.dll")
_DEFAULT_AXIS_DEADZONE = 7849
_DEFAULT_AXIS_EVENT_THRESHOLD = 0.05

_BUTTON_BIT_NAMES: tuple[tuple[int, str], ...] = (
    (0x1000, "A"),
    (0x2000, "B"),
    (0x4000, "X"),
    (0x8000, "Y"),
    (0x0100, "LB"),
    (0x0200, "RB"),
    (0x0020, "Back"),
    (0x0010, "Start"),
    (0x0040, "LS"),
    (0x0080, "RS"),
    (0x0001, "DPadUp"),
    (0x0002, "DPadDown"),
    (0x0004, "DPadLeft"),
    (0x0008, "DPadRight"),
)

_AXIS_NAMES: tuple[str, ...] = ("thumb_lx", "thumb_ly", "thumb_rx", "thumb_ry")


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", wintypes.SHORT),
        ("sThumbLY", wintypes.SHORT),
        ("sThumbRX", wintypes.SHORT),
        ("sThumbRY", wintypes.SHORT),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


_xinput_get_state: Any = None
_xinput_dll_name: str | None = None
_xinput_initialized = False


def _is_force_unavailable() -> bool:
    return os.environ.get(_FORCE_UNAVAILABLE_ENV) == "1"


def normalize_axis(raw: int, deadzone: int) -> float:
    clamped_raw = max(-32768, min(32767, int(raw)))
    clamped_deadzone = max(0, min(32767, int(deadzone)))

    if abs(clamped_raw) < clamped_deadzone:
        return 0.0

    if clamped_raw == -32768:
        raw_normalized = -1.0
    else:
        raw_normalized = float(clamped_raw) / 32767.0

    deadzone_normalized = float(clamped_deadzone) / 32767.0
    scale = max(1e-9, 1.0 - deadzone_normalized)
    magnitude = (abs(raw_normalized) - deadzone_normalized) / scale
    magnitude = max(0.0, min(1.0, magnitude))
    normalized = magnitude if clamped_raw >= 0 else -magnitude
    return max(-1.0, min(1.0, normalized))


def decode_button_bits(buttons: int) -> dict[str, bool]:
    decoded: dict[str, bool] = {}
    button_mask = int(buttons)
    for bit, name in _BUTTON_BIT_NAMES:
        decoded[name] = bool(button_mask & bit)
    return decoded


def build_snapshot(
    raw_state: dict[str, Any], axis_deadzone: int = _DEFAULT_AXIS_DEADZONE
) -> dict[str, Any]:
    status = str(raw_state.get("status", "unavailable"))
    connected = bool(raw_state.get("connected", False))
    buttons_raw = int(raw_state.get("buttons", 0))
    axes_raw = {
        axis_name: int(raw_state.get(axis_name, 0)) for axis_name in _AXIS_NAMES
    }

    return {
        "index": int(raw_state.get("index", -1)),
        "status": status,
        "connected": connected,
        "dll": raw_state.get("dll"),
        "packet_number": int(raw_state.get("packet_number", 0)),
        "buttons_raw": buttons_raw,
        "buttons": decode_button_bits(buttons_raw),
        "triggers": {
            "left": int(raw_state.get("left_trigger", 0)),
            "right": int(raw_state.get("right_trigger", 0)),
        },
        "axes_raw": axes_raw,
        "axes": {
            axis_name: normalize_axis(raw_value, axis_deadzone)
            for axis_name, raw_value in axes_raw.items()
        },
    }


def diff_snapshot_events(
    previous_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any],
    axis_threshold: float = _DEFAULT_AXIS_EVENT_THRESHOLD,
) -> list[str]:
    if previous_snapshot is None:
        return []

    events: list[str] = []
    previous_buttons = previous_snapshot.get("buttons", {})
    current_buttons = current_snapshot.get("buttons", {})
    for _bit, name in _BUTTON_BIT_NAMES:
        was_down = bool(previous_buttons.get(name, False))
        is_down = bool(current_buttons.get(name, False))
        if was_down != is_down:
            events.append(f"{name} {'down' if is_down else 'up'}")

    previous_axes = previous_snapshot.get("axes", {})
    current_axes = current_snapshot.get("axes", {})
    clamped_threshold = max(0.0, float(axis_threshold))
    for axis_name in _AXIS_NAMES:
        previous_value = float(previous_axes.get(axis_name, 0.0))
        current_value = float(current_axes.get(axis_name, 0.0))
        if abs(current_value - previous_value) > clamped_threshold:
            events.append(f"{axis_name} {previous_value:.2f} -> {current_value:.2f}")

    return events


def build_snapshot_with_events(
    raw_state: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
    axis_deadzone: int = _DEFAULT_AXIS_DEADZONE,
    axis_threshold: float = _DEFAULT_AXIS_EVENT_THRESHOLD,
) -> tuple[dict[str, Any], list[str]]:
    snapshot = build_snapshot(raw_state, axis_deadzone=axis_deadzone)
    return snapshot, diff_snapshot_events(
        previous_snapshot, snapshot, axis_threshold=axis_threshold
    )


class RingLog:
    def __init__(self, max_items: int):
        self._max_items = max(0, int(max_items))
        self._items: list[Any] = []

    def push(self, item: Any) -> None:
        if self._max_items <= 0:
            return
        self._items.append(item)
        if len(self._items) > self._max_items:
            del self._items[0 : len(self._items) - self._max_items]

    def items(self) -> list[Any]:
        return list(self._items)


def _load_xinput_get_state() -> tuple[Any, str | None]:
    global _xinput_get_state
    global _xinput_dll_name
    global _xinput_initialized

    if _xinput_initialized:
        return _xinput_get_state, _xinput_dll_name

    _xinput_initialized = True

    if sys.platform != "win32":
        return None, None

    for dll_name in _DLL_CANDIDATES:
        try:
            dll = ctypes.WinDLL(dll_name)
            xinput_get_state = dll.XInputGetState
            xinput_get_state.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
            xinput_get_state.restype = wintypes.DWORD
            _xinput_get_state = xinput_get_state
            _xinput_dll_name = dll_name
            return _xinput_get_state, _xinput_dll_name
        except Exception:
            continue

    return None, None


def probe_xinput() -> dict[str, Any]:
    try:
        if _is_force_unavailable():
            return {"status": "unavailable", "reason": "forced_unavailable"}

        if sys.platform != "win32":
            return {"status": "unavailable", "reason": "non_windows"}

        xinput_get_state, dll_name = _load_xinput_get_state()
        if xinput_get_state is None:
            return {"status": "unavailable", "reason": "dll_load_failed"}

        saw_not_connected = False
        for user_index in range(4):
            state = XINPUT_STATE()
            result = int(xinput_get_state(user_index, ctypes.byref(state)))
            if result == ERROR_SUCCESS:
                return {
                    "status": "ok",
                    "dll": dll_name,
                    "index": user_index,
                    "packet_number": int(state.dwPacketNumber),
                }
            if result == ERROR_DEVICE_NOT_CONNECTED:
                saw_not_connected = True

        if saw_not_connected:
            return {"status": "not_connected", "dll": dll_name}

        return {
            "status": "unavailable",
            "reason": "unexpected_error_code",
            "dll": dll_name,
        }
    except Exception as exc:
        return {"status": "unavailable", "reason": "exception", "error": str(exc)}


def poll_controllers() -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []

    if _is_force_unavailable() or sys.platform != "win32":
        for user_index in range(4):
            states.append(
                {
                    "index": user_index,
                    "status": "unavailable",
                    "connected": False,
                    "dll": None,
                }
            )
        return states

    xinput_get_state, dll_name = _load_xinput_get_state()
    if xinput_get_state is None:
        for user_index in range(4):
            states.append(
                {
                    "index": user_index,
                    "status": "unavailable",
                    "connected": False,
                    "dll": None,
                }
            )
        return states

    for user_index in range(4):
        try:
            state = XINPUT_STATE()
            result = int(xinput_get_state(user_index, ctypes.byref(state)))

            if result == ERROR_SUCCESS:
                gamepad = state.Gamepad
                states.append(
                    {
                        "index": user_index,
                        "status": "ok",
                        "connected": True,
                        "dll": dll_name,
                        "packet_number": int(state.dwPacketNumber),
                        "buttons": int(gamepad.wButtons),
                        "left_trigger": int(gamepad.bLeftTrigger),
                        "right_trigger": int(gamepad.bRightTrigger),
                        "thumb_lx": int(gamepad.sThumbLX),
                        "thumb_ly": int(gamepad.sThumbLY),
                        "thumb_rx": int(gamepad.sThumbRX),
                        "thumb_ry": int(gamepad.sThumbRY),
                    }
                )
            elif result == ERROR_DEVICE_NOT_CONNECTED:
                states.append(
                    {
                        "index": user_index,
                        "status": "not_connected",
                        "connected": False,
                        "dll": dll_name,
                    }
                )
            else:
                states.append(
                    {
                        "index": user_index,
                        "status": "unavailable",
                        "connected": False,
                        "dll": dll_name,
                        "error_code": result,
                    }
                )
        except Exception as exc:
            states.append(
                {
                    "index": user_index,
                    "status": "unavailable",
                    "connected": False,
                    "dll": dll_name,
                    "error": str(exc),
                }
            )

    return states
