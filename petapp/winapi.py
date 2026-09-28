import ctypes
import os
import struct
import sys
import winreg
from ctypes import c_long, c_uint, c_void_p, wintypes
from pathlib import Path
from typing import NamedTuple

from .config import APP_NAME, RUN_KEY


class Rect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int


def _windows_path(getter):
    buffer = ctypes.create_unicode_buffer(260)
    if not 0 < getter(buffer, len(buffer)) < len(buffer):
        raise OSError("Could not resolve a Windows directory")
    return Path(buffer.value)


SYSTEM_DIR = _windows_path(ctypes.windll.kernel32.GetSystemDirectoryW)
FONTS_DIR = _windows_path(ctypes.windll.kernel32.GetWindowsDirectoryW) / "Fonts"


def system_dll(name):
    return ctypes.WinDLL(os.fspath(SYSTEM_DIR / name), use_last_error=True)


def system_font(name):
    return FONTS_DIR / name if (FONTS_DIR / name).is_file() else None


user32, gdi32, kernel32 = system_dll("user32.dll"), system_dll("gdi32.dll"), system_dll("kernel32.dll")
for dll, name, restype, args in (
        (user32, "MonitorFromPoint", c_void_p, [wintypes.POINT, c_uint]), (user32, "GetMonitorInfoW", c_long, [c_void_p, c_void_p]),
        (user32, "GetDC", c_void_p, [c_void_p]), (user32, "ReleaseDC", c_long, [c_void_p, c_void_p]),
        (user32, "GetWindowLongW", c_long, [c_void_p, c_long]), (user32, "SetWindowLongW", c_long, [c_void_p, c_long, c_long]),
        (user32, "UpdateLayeredWindow", c_long, [c_void_p] * 6 + [c_uint, c_void_p, c_uint]),
        (user32, "MessageBoxW", c_long, [c_void_p, wintypes.LPCWSTR, wintypes.LPCWSTR, c_uint]),
        (gdi32, "CreateCompatibleDC", c_void_p, [c_void_p]), (gdi32, "SelectObject", c_void_p, [c_void_p, c_void_p]),
        (gdi32, "CreateDIBSection", c_void_p, [c_void_p, c_void_p, c_uint, ctypes.POINTER(c_void_p), c_void_p, c_uint]),
        (gdi32, "DeleteObject", c_long, [c_void_p]), (gdi32, "DeleteDC", c_long, [c_void_p]),
        (kernel32, "CreateMutexW", c_void_p, [c_void_p, c_long, wintypes.LPCWSTR])):
    getattr(dll, name).restype, getattr(dll, name).argtypes = restype, args


def work_area_at(x, y, root):
    info = (c_long * 10)(40)
    if user32.GetMonitorInfoW(user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2), ctypes.byref(info)):
        return Rect(*info[5:9])
    return Rect(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())


def enable_dpi_awareness():
    try:
        system_dll("shcore.dll").SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


class Bitmap:
    def __init__(self, width, height, bgra):
        self.width, self.height, bits = width, height, c_void_p()
        header = ctypes.create_string_buffer(struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0))
        self.handle = gdi32.CreateDIBSection(None, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, bgra, len(bgra))

    def free(self):
        if self.handle:
            gdi32.DeleteObject(self.handle)
            self.handle = None


def make_layered(hwnd):
    user32.SetWindowLongW(hwnd, -20, user32.GetWindowLongW(hwnd, -20) | 0x00080000 | 0x00000080)


def update_layered(hwnd, bitmap, alpha=255):
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    previous = gdi32.SelectObject(memory, bitmap.handle)
    size, origin, blend = wintypes.SIZE(bitmap.width, bitmap.height), wintypes.POINT(0, 0), ctypes.c_uint32(alpha << 16 | 1 << 24)
    user32.UpdateLayeredWindow(hwnd, screen, None, ctypes.byref(size), memory, ctypes.byref(origin), 0, ctypes.byref(blend), 2)
    gdi32.SelectObject(memory, previous)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(None, screen)


def already_running():
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}_single_instance")
    return ctypes.get_last_error() == 183


def message_box(text, title="Desktop Pet"):
    user32.MessageBoxW(None, text, title, 0x40 | 0x40000)


def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw if pythonw.exists() else sys.executable}" "{Path(sys.argv[0]).resolve()}"'


def is_startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, APP_NAME))
    except OSError:
        return False


def set_startup(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
