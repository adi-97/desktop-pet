import math
from datetime import datetime
from typing import NamedTuple


class Rect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def finite(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def sign(value):
    return 1 if value > 0 else -1 if value < 0 else 0


def fmt_clock(dt):
    return dt.strftime("%I:%M %p").lstrip("0")


def fmt_duration(seconds):
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds} sec"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def greeting():
    hour = datetime.now().hour
    if not 5 <= hour < 22:
        return "It's late... don't forget to sleep."
    return next(text for end, text in ((12, "Good morning!"), (17, "Good afternoon!"), (22, "Good evening!")) if hour < end)
