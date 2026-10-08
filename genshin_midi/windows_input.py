from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", wintypes.DWORD), ("value", _INPUTUNION)]


def key_to_virtual_key(key: str) -> int:
    if len(key) != 1 or not key.isascii() or not key.isalpha():
        raise ValueError(f"Expected a single ASCII letter key, got {key!r}.")
    return ord(key.upper())


class WindowsKeySink:
    def __init__(self):
        if os.name != "nt":
            raise OSError("WindowsKeySink is only available on Windows.")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
        self._user32.SendInput.restype = wintypes.UINT

    def key_down(self, key: str) -> None:
        self._send(key, False)

    def key_up(self, key: str) -> None:
        self._send(key, True)

    def _send(self, key: str, is_key_up: bool) -> None:
        flags = KEYEVENTF_KEYUP if is_key_up else 0
        event = _INPUT(
            type=INPUT_KEYBOARD,
            ki=_KEYBDINPUT(key_to_virtual_key(key), 0, flags, 0, 0),
        )
        sent = self._user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_INPUT))
        if sent != 1:
            raise ctypes.WinError(ctypes.get_last_error())
