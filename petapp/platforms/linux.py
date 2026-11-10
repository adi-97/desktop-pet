import ctypes
import ctypes.util
import fcntl
import os
import shutil
import subprocess
import sys
import time
from ctypes import POINTER, byref, c_char_p, c_int, c_uint, c_ulong, c_void_p
from functools import lru_cache
from pathlib import Path

from PIL import Image

from .. import config
from ..config import APP_NAME
from ..util import Rect

__all__ = ["Rect", "Bitmap", "STARTUP_LABEL", "ui_font", "work_area_at", "enable_dpi_awareness", "toplevel_options",
           "make_layered", "update_layered", "play_sound", "already_running", "message_box", "is_startup_enabled",
           "set_startup"]

STARTUP_LABEL = "Start at login"
FONT_DIRS = ("/usr/share/fonts", "/usr/local/share/fonts")
FONTS = {False: ("DejaVuSans.ttf", "NotoSans-Regular.ttf", "LiberationSans-Regular.ttf", "Ubuntu-R.ttf"),
         True: ("DejaVuSans-Bold.ttf", "NotoSans-Bold.ttf", "LiberationSans-Bold.ttf", "Ubuntu-B.ttf")}
AUTOSTART = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart" / f"{APP_NAME}.desktop"
REVERSED_BITS = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))


class XImage(ctypes.Structure):
    _fields_ = [("width", c_int), ("height", c_int), ("xoffset", c_int), ("format", c_int), ("data", c_void_p),
                ("byte_order", c_int), ("bitmap_unit", c_int), ("bitmap_bit_order", c_int), ("bitmap_pad", c_int),
                ("depth", c_int), ("bytes_per_line", c_int), ("bits_per_pixel", c_int), ("red_mask", c_ulong),
                ("green_mask", c_ulong), ("blue_mask", c_ulong), ("obdata", c_void_p), ("funcs", c_void_p * 6)]


def _library(name):
    path = ctypes.util.find_library(name)
    if not path:
        raise OSError(f"lib{name} is not installed")
    return ctypes.CDLL(path)


xlib, xext = _library("X11"), _library("Xext")
for lib, name, restype, args in (
        (xlib, "XOpenDisplay", c_void_p, [c_char_p]), (xlib, "XDefaultScreen", c_int, [c_void_p]),
        (xlib, "XRootWindow", c_ulong, [c_void_p, c_int]), (xlib, "XInternAtom", c_ulong, [c_void_p, c_char_p, c_int]),
        (xlib, "XGetSelectionOwner", c_ulong, [c_void_p, c_ulong]),
        (xlib, "XGetWindowProperty", c_int, [c_void_p, c_ulong, c_ulong, ctypes.c_long, ctypes.c_long, c_int, c_ulong,
                                             POINTER(c_ulong), POINTER(c_int), POINTER(c_ulong), POINTER(c_ulong),
                                             POINTER(c_void_p)]),
        (xlib, "XFree", c_int, [c_void_p]), (xlib, "XCreateGC", c_void_p, [c_void_p, c_ulong, c_ulong, c_void_p]),
        (xlib, "XFreeGC", c_int, [c_void_p, c_void_p]), (xlib, "XInitImage", c_int, [POINTER(XImage)]),
        (xlib, "XPutImage", c_int, [c_void_p, c_ulong, c_void_p, POINTER(XImage)] + [c_int] * 4 + [c_uint] * 2),
        (xlib, "XCreateBitmapFromData", c_ulong, [c_void_p, c_ulong, c_char_p, c_uint, c_uint]),
        (xlib, "XFreePixmap", c_int, [c_void_p, c_ulong]), (xlib, "XFlush", c_int, [c_void_p]),
        (xext, "XShapeCombineMask", None, [c_void_p, c_ulong, c_int, c_int, c_int, c_ulong, c_int])):
    getattr(lib, name).restype, getattr(lib, name).argtypes = restype, args

display = xlib.XOpenDisplay(None)
if not display:
    raise OSError("Could not open the X display (is DISPLAY set?)")
screen_root = xlib.XRootWindow(display, xlib.XDefaultScreen(display))
_area = (0.0, None)


def _atom(name):
    return xlib.XInternAtom(display, name.encode(), False)


@lru_cache(maxsize=2)
def ui_font(bold=False):
    found = {}
    for top in FONT_DIRS:
        for folder, _, files in os.walk(top):
            for name in files:
                found.setdefault(name, Path(folder) / name)
    return next((found[n] for n in FONTS[bold] if n in found), None)


def work_area_at(x, y, root):
    global _area
    if time.time() - _area[0] > 2:
        kind, fmt, count, after, data = c_ulong(), c_int(), c_ulong(), c_ulong(), c_void_p()
        rect = None
        if xlib.XGetWindowProperty(display, screen_root, _atom("_NET_WORKAREA"), 0, 4, False, 6, byref(kind), byref(fmt),
                                   byref(count), byref(after), byref(data)) == 0 and data.value:
            if fmt.value == 32 and count.value >= 4:
                left, top, width, height = ctypes.cast(data, POINTER(ctypes.c_long))[:4]
                rect = Rect(left, top, left + width, top + height) if width > 0 and height > 0 else None
            xlib.XFree(data)
        _area = (time.time(), rect or Rect(0, 0, root.winfo_screenwidth(), root.winfo_screenheight()))
    return _area[1]


def enable_dpi_awareness():
    pass


def composited():
    return bool(xlib.XGetSelectionOwner(display, _atom(f"_NET_WM_CM_S{xlib.XDefaultScreen(display)}")))


def toplevel_options(root):
    if composited() and ("truecolor", 32) in root.winfo_visualsavailable():
        return {"visual": "truecolor 32", "colormap": "new", "background": "black"}
    return {}


class Bitmap:
    def __init__(self, width, height, bgra):
        self.width, self.height, self.data = width, height, ctypes.create_string_buffer(bgra, len(bgra))
        self.masks = {}

    def mask(self, threshold):
        if threshold not in self.masks:
            alpha = Image.frombytes("L", (self.width, self.height), self.data.raw[3::4])
            bits = alpha.point(lambda v: 255 if v > threshold else 0, "1").tobytes().translate(REVERSED_BITS)
            self.masks[threshold] = xlib.XCreateBitmapFromData(display, screen_root, bits, self.width, self.height)
        return self.masks[threshold]

    def free(self):
        for pixmap in self.masks.values():
            xlib.XFreePixmap(display, pixmap)
        self.masks.clear()


class Layer:
    def __init__(self, win):
        self.win, self.window, self.frame = win, win.winfo_id(), int(win.wm_frame(), 16)
        self.depth = win.winfo_depth()
        self.threshold = 0 if self.depth == 32 else 127
        self.gc = xlib.XCreateGC(display, self.window, 0, None)
        self.bitmap, self.size, self.alpha, self.raised = None, None, 255, 0.0
        win.bind("<Expose>", lambda e: self.draw(), add="+")
        win.bind("<Destroy>", lambda e: self.close() if e.widget is win else None, add="+")

    def paint(self, bitmap, alpha):
        if (bitmap.width, bitmap.height) != self.size:
            self.size = (bitmap.width, bitmap.height)
            self.win.update_idletasks()
        if alpha != self.alpha:
            self.alpha = alpha
            self.win.attributes("-alpha", alpha / 255)
        self.bitmap = bitmap
        xext.XShapeCombineMask(display, self.frame, 0, 0, 0, bitmap.mask(self.threshold), 0)
        self.draw()
        if time.time() - self.raised > 1 and not self.win.grab_current():
            self.raised = time.time()
            self.win.lift()

    def draw(self):
        bitmap = self.bitmap
        if not bitmap or not self.gc:
            return
        image = XImage(width=bitmap.width, height=bitmap.height, format=2, data=ctypes.addressof(bitmap.data),
                       bitmap_unit=32, bitmap_pad=32, depth=self.depth, bytes_per_line=bitmap.width * 4,
                       bits_per_pixel=32, red_mask=0xFF0000, green_mask=0xFF00, blue_mask=0xFF)
        xlib.XInitImage(byref(image))
        xlib.XPutImage(display, self.window, self.gc, byref(image), 0, 0, 0, 0, bitmap.width, bitmap.height)
        xlib.XFlush(display)

    def close(self):
        if self.gc:
            xlib.XFreeGC(display, self.gc)
            self.gc = None


def make_layered(win):
    return Layer(win)


def update_layered(layer, bitmap, alpha=255):
    layer.paint(bitmap, alpha)


@lru_cache(maxsize=1)
def _player():
    return next((p for p in (shutil.which(n) for n in ("paplay", "pw-play", "aplay")) if p), None)


_sound = None


def play_sound(path):
    global _sound
    if _player():
        if _sound and _sound.poll() is None:
            _sound.terminate()
        _sound = subprocess.Popen([_player(), os.fspath(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def already_running():
    global _lock
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _lock = open(config.DATA_DIR / "instance.lock", "w")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


def message_box(text, title="Desktop Pet"):
    for command in (["zenity", "--info", f"--title={title}", f"--text={text}"], ["notify-send", title, text]):
        if shutil.which(command[0]):
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return
    print(f"{title}: {text}", file=sys.stderr)


def _quote(arg):
    return '"' + "".join("\\" + c if c in '"`$\\' else c for c in str(arg)) + '"'


def is_startup_enabled():
    return AUTOSTART.is_file()


def set_startup(enabled):
    if not enabled:
        AUTOSTART.unlink(missing_ok=True)
        return
    command = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, Path(sys.argv[0]).resolve()]
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text("[Desktop Entry]\nType=Application\nName=Desktop Pet\n"
                         f"Exec={' '.join(_quote(a) for a in command)}\nX-GNOME-Autostart-enabled=true\n", "utf-8")
