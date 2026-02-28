import ctypes
from ctypes import wintypes

class INPUT1(ctypes.Structure): pass
class INPUT2(ctypes.Structure): pass

# global instance
SendInputGlobal = ctypes.windll.user32.SendInput
SendInputGlobal.argtypes = [ctypes.POINTER(INPUT1)]

# new instance
user32_new = ctypes.WinDLL("user32")
SendInputNew = user32_new.SendInput
SendInputNew.argtypes = [ctypes.POINTER(INPUT2)]

print("Global expected:", SendInputGlobal.argtypes)
print("New expected:", SendInputNew.argtypes)

print("Same function object?", SendInputGlobal is SendInputNew)
