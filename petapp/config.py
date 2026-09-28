import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "DesktopPet"
TICK_MS, WALK_SPEED, GRAVITY, CLICK_SLOP, DOUBLE_CLICK_MS = 40, 2.4, 1.1, 5, 280
DISPLAY_SIZES = {"Small": 110, "Medium": 150, "Large": 210}
WEATHER_CITY, USE_MOCK_WEATHER, WEATHER_CACHE_SEC = "", False, 10 * 60
SLEEP_AFTER_SEC, FOCUS_MIN, BREAK_MIN, WELLNESS_MIN, PLAYDATE_SEC = 10 * 60, 25, 5, 45, 60
FOOD_DECAY_PER_MIN, HAPPY_DECAY_PER_MIN = 1 / 3, 1 / 4
ANIM_MS = {"idle": 110, "sit": 140, "walk": 70, "action": 55, "alert": 35, "eat": 85, "sleep": 250, "fall": 60, "drag": 60}
FRAMESET = {"sit": "idle", "alert": "action", "fall": "action", "drag": "action"}
TIMED_STATES = ("action", "alert", "eat", "fall", "drag")

DATA_DIR = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
SETTINGS_FILE, LOG_FILE = DATA_DIR / "settings.json", DATA_DIR / "error.log"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MAX_SETTINGS_BYTES, MAX_LOG_BYTES, MAX_REMINDERS, MAX_REMINDER_TEXT = 256 * 1024, 512 * 1024, 50, 200

GENERIC_CHATTER = ("Don't forget to blink!", "You're doing great today.", "Psst... right-click me for tricks.",
                   "Move your mouse back and forth over me for scritches!", "Try tossing me! Drag fast and let go.",
                   "I believe in you!", "Is it snack o'clock yet?")
HUNGRY_LINES = ("My tummy is rumbling... (right-click > Feed a treat)", "Is it snack o'clock? I think it's snack o'clock.",
                "I'm hungry...")
WELLNESS_LINES = ("Hydration check! Have a sip of water.", "Stand up and stretch for a minute!",
                  "Rest your eyes: look at something far away for 20 seconds.", "Roll your shoulders back and check your posture!")


@dataclass(frozen=True)
class PetSpec:
    name: str
    word: str
    treat: str
    treat_label: str
    petted: tuple
    facts: tuple
    bite: tuple
    eat_secs: float
    eat_line: str
    crumb: str = None
    swims: bool = False

    @property
    def folder(self):
        return self.name.lower().replace(" ", "_")


PETS = {spec.name: spec for spec in (
    PetSpec("Dalmatian", "Woof!", "bone", "a bone", ("*happy tail wag*", "Who's a good pup? Me!", "More scritches please!"),
            ("Dalmatian puppies are born completely white!", "Dalmatians used to run alongside horse carriages.",
             "No two Dalmatians have the same spots.", "A dog's nose print is as unique as a fingerprint.",
             "I can hear sounds four times farther away than you!"),
            (0.84, 0.94), 3.4, "*licks lips* Yum!", "fx/crumb_bone"),
    PetSpec("Orange Cat", "Meow!", "fish", "a fish", ("Purrrrr...", "*slow blink*", "Right there. Yes. There."),
            ("Cats sleep 12-16 hours a day. Goals.", "About 80% of orange cats are boys!", "A group of cats is called a clowder.",
             "I can jump up to six times my body length.", "Cats have 32 muscles in each ear."),
            (0.82, 0.94), 3.8, "*licks paw* Delicious.", "fx/crumb_fish"),
    PetSpec("Goldfish", "Blub!", "flakes", "fish flakes", ("*happy bubbles*", "Blub blub!", "*does a little flip*"),
            ("Goldfish can recognise their owner's face!", "My memory lasts months, not 3 seconds. Rude.",
             "Goldfish can see ultraviolet light.", "Goldfish don't have a stomach!", "A group of fish is a school. I'm homeschooled."),
            (0.9, 0.58), 2.6, "*gulp* Tasty flakes!", swims=True),
)}


def resource_path(relative):
    return Path(getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent) / relative
