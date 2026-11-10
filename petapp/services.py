import random
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from . import config
from .log import log_error
from .platforms import message_box, play_sound
from .util import clamp, finite

MOODS = ((80, "Over the moon"), (55, "Happy"), (30, "Okay"), (0, "Lonely... pet me!"))
MOCK_WEATHER = ("Sunny, 24°C", "Partly cloudy, 19°C", "Light rain, 16°C", "Clear skies, 21°C", "Breezy, 18°C")


class SoundPlayer:
    enabled = True

    def play(self, spec, times=1, kind="sound"):
        clips = sorted((config.resource_path("assets") / spec.folder).glob(f"{kind}*.wav"))
        if self.enabled and clips:
            play_sound(random.choice(clips))


class Notifier:
    @staticmethod
    def notify(title, message):
        threading.Thread(target=Notifier._send, args=(title[:63], message[:250]), daemon=True).start()

    @staticmethod
    def _send(title, message):
        try:
            from plyer import notification
            notification.notify(title=title, message=message, app_name="Desktop Pet", timeout=10)
        except Exception as e:
            log_error(f"Toast failed, falling back to a message box: {e!r}")
            message_box(message, title)


class WeatherService:
    def __init__(self, results):
        self.results, self._cache = results, None

    def request(self, callback):
        if config.USE_MOCK_WEATHER:
            self.results.put((callback, random.choice(MOCK_WEATHER)))
        elif self._cache and time.time() - self._cache[0] < config.WEATHER_CACHE_SEC:
            self.results.put((callback, self._cache[1]))
        else:
            threading.Thread(target=self._fetch, args=(callback,), daemon=True).start()

    def _fetch(self, callback):
        try:
            url = f"https://wttr.in/{urllib.parse.quote(config.WEATHER_CITY)}?format=%C+%t"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "curl/8.0"}), timeout=4) as response:
                if response.status != 200:
                    raise ValueError(f"weather HTTP {response.status}")
                text = "".join(ch for ch in response.read(256).decode("utf-8", "replace") if ch.isprintable()).strip()
            if not text or len(text) > 60 or "°" not in text:
                raise ValueError(f"unexpected weather reply: {text[:80]!r}")
            text = re.sub(r"\+(?=\d)", "", text)
            self._cache = (time.time(), text)
        except Exception as e:
            log_error(f"Weather lookup failed: {e!r}")
            text = random.choice(MOCK_WEATHER) + " (my best guess, I'm offline)"
        self.results.put((callback, text))


@dataclass
class PetStats:
    food: float = 80.0
    happy: float = 80.0

    @classmethod
    def from_dict(cls, data):
        food, happy = (finite(data.get("food")), finite(data.get("happy"))) if isinstance(data, dict) else (None, None)
        return cls() if food is None or happy is None else cls(clamp(food, 0, 100), clamp(happy, 0, 100))

    def decay(self, minutes):
        self.food = max(0.0, self.food - config.FOOD_DECAY_PER_MIN * minutes)
        self.happy = max(0.0, self.happy - config.HAPPY_DECAY_PER_MIN * (2 if self.food < 25 else 1) * minutes)

    def add(self, food=0.0, happy=0.0):
        self.food, self.happy = clamp(self.food + food, 0.0, 100.0), clamp(self.happy + happy, 0.0, 100.0)

    @property
    def mood(self):
        return "Hungry!" if self.food < 25 else next(label for limit, label in MOODS if self.happy >= limit)
