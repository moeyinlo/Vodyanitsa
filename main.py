from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

from PyQt6.QtWidgets import QApplication

from genshin_midi.app import MainWindow


def _build_elevation_parameters(script_path: str, arguments: list[str]) -> str:
    return subprocess.list2cmdline([script_path, *arguments])


def _ensure_elevated() -> int | None:
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.IsUserAnAdmin.argtypes = ()
    shell32.IsUserAnAdmin.restype = wintypes.BOOL
    if shell32.IsUserAnAdmin():
        return None

    shell_execute = shell32.ShellExecuteW
    shell_execute.argtypes = (
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_int,
    )
    shell_execute.restype = ctypes.c_void_p
    result = shell_execute(
        None,
        "runas",
        sys.executable,
        _build_elevation_parameters(os.path.abspath(__file__), sys.argv[1:]),
        os.getcwd(),
        1,
    )
    if result is None or result <= 32:
        print("管理员权限启动失败，或已取消 UAC 确认。", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if os.name != "nt":
        print("This application requires Windows.", file=sys.stderr)
        return 1
    elevation_exit_code = _ensure_elevated()
    if elevation_exit_code is not None:
        return elevation_exit_code

    app = QApplication(sys.argv)
    app.setApplicationName("Teyvat MIDI Player")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
