"""Low-level global mouse listener for left-button down (Windows)."""
from __future__ import annotations

import ctypes
import threading
import queue
from ctypes import wintypes
from typing import List, Optional

# Windows constants
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_QUIT = 0x0012

try:
    ULONG_PTR = wintypes.ULONG_PTR  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

try:
    LRESULT = wintypes.LRESULT  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    LRESULT = ctypes.c_long


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


LowLevelMouseProc = ctypes.WINFUNCTYPE(LRESULT, wintypes.INT, wintypes.WPARAM, wintypes.LPARAM)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class QuickMouseListener:
    """Low-level global listener for left mouse button down."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._mouse_hook = None
        self._mouse_proc = LowLevelMouseProc(self._mouse_callback)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
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
        self._queue.put(token)

    def _mouse_callback(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode == 0 and wParam == WM_LBUTTONDOWN:
            # Emit left button down event
            self._emit('LBUTTON_DOWN')
        return user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)

    def _loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        module_handle = kernel32.GetModuleHandleW(None)
        self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc, module_handle, 0)
        if not self._mouse_hook:
            # Fallback with NULL hMod
            self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc, 0, 0)

        msg = wintypes.MSG()
        while not self._stop_event.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None

__all__ = [
    'QuickMouseListener',
]
