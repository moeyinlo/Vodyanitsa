from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter


WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
HOTKEYS = ((1, 0x76, "F7"), (2, 0x77, "F8"), (3, 0x78, "F9"))


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class GlobalHotkeys(QAbstractNativeEventFilter):
    def __init__(self, callbacks: dict[str, Callable[[], None]]):
        super().__init__()
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.RegisterHotKey.argtypes = (
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        )
        self._user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        self._user32.UnregisterHotKey.restype = wintypes.BOOL
        self._callbacks = {hotkey_id: callbacks[name] for hotkey_id, _, name in HOTKEYS}
        self._registered: list[int] = []
        self.error: str | None = None
        self._register()

    def _register(self) -> None:
        for hotkey_id, virtual_key, name in HOTKEYS:
            if not self._user32.RegisterHotKey(None, hotkey_id, MOD_NOREPEAT, virtual_key):
                self.error = f"Could not register {name}; it may be in use by another app."
                self.unregister()
                return
            self._registered.append(hotkey_id)

    def nativeEventFilter(self, event_type, message):
        if not self._registered or event_type != b"windows_generic_MSG":
            return False, 0
        msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
        callback = self._callbacks.get(int(msg.wParam)) if msg.message == WM_HOTKEY else None
        if callback is None:
            return False, 0
        callback()
        return True, 0

    def unregister(self) -> None:
        for hotkey_id in reversed(self._registered):
            self._user32.UnregisterHotKey(None, hotkey_id)
        self._registered.clear()
