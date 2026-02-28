import ctypes
from ctypes import wintypes

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong),
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT),
    ]

user32 = ctypes.windll.user32
SendInput = user32.SendInput
SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
SendInput.restype = wintypes.UINT

down = INPUT()
down.type = 0
down.mi.dwFlags = 0x0002

try:
    SendInput(1, ctypes.cast(ctypes.byref(down), ctypes.POINTER(INPUT)), ctypes.sizeof(INPUT))
    print("cast worked")
except Exception as e:
    print(f"cast error: {type(e).__name__}: {e}")

try:
    SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    print("byref worked")
except Exception as e:
    print(f"byref error: {type(e).__name__}: {e}")
