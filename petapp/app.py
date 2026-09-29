import json
import os
import queue
import random
import time
import tkinter as tk
import traceback
from datetime import datetime

from . import config
from .config import (BREAK_MIN, DISPLAY_SIZES, FOCUS_MIN, GENERIC_CHATTER, HUNGRY_LINES, MAX_REMINDER_TEXT,
                     MAX_REMINDERS, MAX_SETTINGS_BYTES, PETS, PLAYDATE_SEC, SLEEP_AFTER_SEC, TICK_MS,
                     WELLNESS_LINES, WELLNESS_MIN)
from .log import log_error
from .menu import build_menu, refresh_menu
from .overlays import FloatingSprite, ReminderDialog, Treat
from .pet import Pet
from .services import Notifier, PetStats, SoundPlayer, WeatherService
from .show import Show
from .sprites import SpriteLibrary
from .util import clamp, finite, fmt_clock, fmt_duration, greeting
from .platforms import already_running, enable_dpi_awareness, is_startup_enabled, message_box, set_startup, work_area_at

FLAGS = {"gravity": True, "chase": False, "wellness": False, "sound": True}


class App:
    def __init__(self):
        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.report_callback_exception = self._report
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96)
        self.quitting, self._last_error = False, ""
        data = self._load_settings()
        now = time.time()
        self.first_run = not data
        self.size = data.get("size") if data.get("size") in DISPLAY_SIZES else "Medium"
        key = data.get("pet") if data.get("pet") in PETS else "Dalmatian"
        self.pet_var, self.size_var = tk.StringVar(value=key), tk.StringVar(value=self.size)
        self.flags = {k: tk.BooleanVar(value=bool(data.get(k, v))) for k, v in FLAGS.items()}
        self.startup_var = tk.BooleanVar(value=is_startup_enabled())
        self.sprites, self.sound, self.results = SpriteLibrary(self.scale), SoundPlayer(), queue.Queue()
        self.sound.enabled = self.flag("sound")
        self.weather = WeatherService(self.results)
        saved = data.get("stats") if isinstance(data.get("stats"), dict) else {}
        self.stats = {k: PetStats.from_dict(saved.get(k)) for k in PETS}
        for stats in self.stats.values():
            stats.decay(clamp((now - finite(data.get("saved_at"), now)) / 60, 0, 24 * 60))
        self.reminders = self._load_reminders(data, now)
        self.focus = self.playdate = self.friend = self.treat = self.dialog = self.show = None
        self.last_interaction = self._last_decay = self._last_save = now
        self.next_chatter, self.next_wellness, self.wellness_index = now + random.uniform(90, 240), now + WELLNESS_MIN * 60, 0
        box = self.sprites.pet(PETS[key], self.size).box
        x, y = finite(data.get("x")), finite(data.get("y"))
        if x is None or y is None or max(abs(x), abs(y)) > 100000:
            area = self.work_area_at(self.root.winfo_screenwidth() / 2, self.root.winfo_screenheight() / 2)
            x, y = area.right - box[2] - 80, area.bottom - box[3]
        self.pet = Pet(self, key, x, y)
        self.menu = build_menu(self)
        self._loop(TICK_MS, self._tick)
        self._loop(1000, self._slow_tick)
        self.root.after(700, lambda: self.react(self.pet, f"{self.pet.spec.word} {greeting()}"
                                                + ("\n(Right-click me for options)" if self.first_run else ""), 5000, hop=0))

    @staticmethod
    def _load_settings():
        try:
            if config.SETTINGS_FILE.stat().st_size > MAX_SETTINGS_BYTES:
                log_error("Settings file is unexpectedly large; starting fresh.")
                return {}
            data = json.loads(config.SETTINGS_FILE.read_text("utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, RecursionError):
            return {}

    @staticmethod
    def _load_reminders(data, now):
        reminders = []
        for r in (data.get("reminders") if isinstance(data.get("reminders"), list) else [])[:MAX_REMINDERS * 2]:
            due, rid = (finite(r.get("due")), finite(r.get("id"))) if isinstance(r, dict) else (None, None)
            if due is not None and rid is not None and isinstance(r.get("text"), str) and len(reminders) < MAX_REMINDERS:
                reminders.append({"id": int(rid), "text": r["text"][:MAX_REMINDER_TEXT], "due": due})
        for i, r in enumerate(reminders):
            if r["due"] < now:
                r["missed"], r["due"] = True, now + 4 + i
        return reminders

    def save(self):
        self._last_save = time.time()
        data = {"pet": self.pet.key, "x": int(self.pet.x), "y": int(self.pet.y), "size": self.size,
                **{k: v.get() for k, v in self.flags.items()}, "reminders": self.reminders, "saved_at": time.time(),
                "stats": {k: {"food": round(s.food, 1), "happy": round(s.happy, 1)} for k, s in self.stats.items()}}
        try:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = config.SETTINGS_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), "utf-8")
            os.replace(tmp, config.SETTINGS_FILE)
        except OSError as e:
            log_error(f"Could not save settings: {e!r}")

    def run(self):
        self.root.mainloop()

    def quit(self):
        self.save()
        self.quitting = True
        self.root.destroy()

    def _report(self, *exc):
        message = "".join(traceback.format_exception(*exc))
        if message != self._last_error:
            self._last_error = message
            log_error(message)

    def _loop(self, ms, fn):
        def run():
            if self.quitting:
                return
            try:
                fn(time.time())
            except Exception as e:
                self._report(type(e), e, e.__traceback__)
            self.root.after(ms, run)
        self.root.after(ms, run)

    def _tick(self, now):
        while not self.results.empty():
            callback, value = self.results.get_nowait()
            callback(value)
        for pet in self.pets():
            pet.tick(now)
        if self.treat:
            self.treat.tick()

    def _slow_tick(self, now):
        for stats in self.stats.values():
            stats.decay((now - self._last_decay) / 60)
        self._last_decay = now
        due = [r for r in self.reminders if r["due"] <= now]
        if due:
            self.reminders = [r for r in self.reminders if r["due"] > now]
            self.save()
            for r in due:
                self.alert(("Reminder! (while I was away)" if r.get("missed") else "Reminder!"), r["text"], 5.0, 20000,
                           f"Reminder from your {self.pet.spec.name}")
        self._check_focus(now)
        self._check_wellness(now)
        self._check_chatter(now)
        if self.playdate and now > self.playdate["until"]:
            self.end_playdate()
        if now - self._last_save > 30:
            self.save()

    def flag(self, name):
        return self.flags[name].get()

    def pets(self):
        return [self.pet] + ([self.friend] if self.friend else [])

    def work_area_at(self, x, y):
        return work_area_at(x, y, self.root)

    def touch(self):
        self.last_interaction = time.time()

    def stats_for(self, pet):
        return self.stats[pet.key]

    def speed_factor(self, pet):
        stats = self.stats_for(pet)
        return 1.0 if pet.friend else 0.55 if stats.food < 25 else 1.15 if stats.happy > 80 else 1.0

    def focus_phase(self):
        return self.focus["phase"] if self.focus else None

    def should_sleep(self, now):
        hour = datetime.now().hour
        return not (self.focus or self.playdate or self.treat or self.show) and (
            now - self.last_interaction > SLEEP_AFTER_SEC or ((hour >= 23 or hour < 6) and random.random() < 0.25))

    def rouse(self, pet=None):
        pet = pet or self.pet
        self.touch()
        if pet.state == "sleep":
            pet.wake(greet=False)
        return pet

    def react(self, pet, rows, ms=3000, hop=0.8, sound=True):
        if hop and not pet.airborne:
            pet.set_state("action", hop)
        if sound:
            self.sound.play(pet.spec)
        return pet.say(rows, ms)

    def alert(self, title, body, seconds, ms, toast):
        self.touch()
        self.pet.airborne = False
        self.pet.set_state("alert", seconds)
        self.pet.say([("title", title), body], ms)
        self.sound.play(self.pet.spec, times=2)
        Notifier.notify(toast, body)

    def show_menu(self, event):
        self.touch()
        refresh_menu(self)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def on_toggle(self):
        self.touch()
        self.sound.enabled = self.flag("sound")
        if self.pet.state == "sleep" and self.flag("chase"):
            self.pet.wake()
        self.save()

    def on_startup_toggle(self):
        wanted = self.startup_var.get()
        try:
            set_startup(wanted)
            self.pet.say("I'll be here when you log in!" if wanted else "Okay, I won't start when you log in.", 3000)
        except OSError as e:
            log_error(f"Changing the startup setting failed: {e!r}")
            self.startup_var.set(not wanted)
            self.pet.say("Hmm, I couldn't change the startup setting.", 3000)

    def _check_chatter(self, now):
        pet = self.pet
        if now < self.next_chatter:
            return
        self.next_chatter = now + random.uniform(150, 420)
        if pet.state in ("idle", "walk") and not (pet.bubble.visible or self.focus_phase() == "focus" or self.playdate or self.show):
            roll = random.random()
            pool = HUNGRY_LINES if self.stats_for(pet).food < 25 else pet.spec.facts if roll < 0.5 else GENERIC_CHATTER
            pet.say(greeting() if roll > 0.85 else random.choice(pool), 6000)

    def _check_wellness(self, now):
        if not self.flag("wellness"):
            self.next_wellness = now + WELLNESS_MIN * 60
        elif now >= self.next_wellness and self.focus_phase() != "focus" and self.pet.state != "sleep":
            self.next_wellness = now + WELLNESS_MIN * 60
            self.wellness_index += 1
            self.react(self.pet, WELLNESS_LINES[self.wellness_index % len(WELLNESS_LINES)], 12000, hop=1.0)

    def _check_focus(self, now):
        if not self.focus or now < self.focus["until"]:
            return
        if self.focus["phase"] == "focus":
            self.focus.update(phase="break", until=now + BREAK_MIN * 60)
            title, body = f"Break time! Round {self.focus['round']} done.", f"Stretch and relax for {BREAK_MIN} minutes."
        else:
            self.focus.update(phase="focus", until=now + FOCUS_MIN * 60, round=self.focus["round"] + 1)
            title, body = "Break's over!", "Back to focus. You've got this."
        self.alert(title, body, 2.5, 10000, "Focus timer")

    def start_focus(self):
        self.rouse()
        self.focus = {"phase": "focus", "until": time.time() + FOCUS_MIN * 60, "round": 1}
        self.pet.set_state("sit")
        self.react(self.pet, [("title", f"Focus time! {FOCUS_MIN} minutes."), "I'll sit quietly and guard your desk."], 4500, hop=0)

    def stop_focus(self):
        self.focus = None
        self.pet.finish_state()
        self.pet.say("Focus timer stopped. Nice work!", 3000)

    def on_pet_click(self, pet):
        self.touch()
        if pet.state == "sleep":
            return pet.wake()
        if pet.spec.swims:
            self.bubbles(pet, 4)
        if pet.friend:
            return self.react(pet, f"{pet.spec.word} Hi! Thanks for having me over!", 3500, hop=1.2)
        self.stats_for(pet).add(happy=2)
        now = datetime.now()
        head = [("title", f"{pet.spec.word}  It's {fmt_clock(now)}"), ("text", f"{now:%A, %d %B}")]
        if self.focus:
            left = max(0, int(self.focus["until"] - time.time()))
            phase = "Focus" if self.focus["phase"] == "focus" else "Break"
            return self.react(pet, head + [("text", f"{phase}: {left // 60:02d}:{left % 60:02d} left")], 6000, hop=1.2)
        token = self.react(pet, head + [("text", "Sniffing the weather...")], 9000, hop=1.2)
        self.weather.request(lambda text: pet.alive and pet.bubble.visible and pet.bubble.token == token
                             and pet.say(head + [f"Weather: {text}"], 8000))

    def on_pet_petted(self, pet):
        self.rouse(pet)
        if not pet.friend:
            self.stats_for(pet).add(happy=8)
        self.hearts(pet, 3)
        if pet.spec.swims:
            self.bubbles(pet, 3)
        self.react(pet, random.choice(pet.spec.petted), 2500, hop=0 if pet.state in ("alert", "eat") else 0.8, sound=False)

    def spray(self, pet, name, count, origin, size, rise, ms, drift=(0, 0), gap=(170, 170)):
        delay = 0
        for _ in range(count):
            self.root.after(delay, lambda: pet.alive and FloatingSprite(
                self.root, self.sprites.image(name, self.size, round(random.uniform(*size), 2)), *origin(),
                rise=random.uniform(*rise) * pet.unit, ms=random.randint(*ms), drift=random.uniform(*drift) * pet.unit))
            delay += random.randint(*gap)

    def hearts(self, pet, count):
        self.spray(pet, "fx/heart", count, lambda: (pet.cx + random.uniform(-0.3, 0.3) * pet.body_w,
                                                    pet.top - pet.hop + pet.body_w * 0.15), (0.16, 0.24), (80, 80), (1300, 1300))

    def bubbles(self, pet, count):
        self.spray(pet, "fx/bubble", count, lambda: pet.mouth, (0.05, 0.12), (130, 230), (2200, 3400), (-14, 14), (120, 380))

    def float_z(self, pet):
        if pet.spec.swims:
            return self.bubbles(pet, 1)
        self.spray(pet, "fx/z", 1, lambda: (pet.cx + pet.facing * pet.body_w * 0.3, pet.top + pet.body_w * 0.2),
                   (0.11, 0.17), (60, 60), (2200, 2200), (12 * pet.facing, 12 * pet.facing))

    def on_bite(self, pet):
        self.sound.play(pet.spec, kind="eat")
        if not pet.spec.crumb:
            return self.bubbles(pet, random.randint(1, 2))
        x, y = pet.bite_point
        self.spray(pet, pet.spec.crumb, random.randint(2, 3), lambda: (x + random.uniform(-8, 8) * pet.unit, y),
                   (0.08, 0.12), (-12, -4), (500, 800), (-26, 26), (0, 0))

    def show_stats(self):
        pet, stats = self.pet, self.stats_for(self.pet)
        pet.say([("title", pet.spec.name), ("bar", "Fullness", stats.food, (242, 153, 58, 255)),
                 ("bar", "Happiness", stats.happy, (255, 92, 122, 255)), ("text", f"Mood: {stats.mood}")], 7000)

    def toggle_show(self):
        self.touch()
        if self.show:
            self.show.stop()
        else:
            self.show = Show(self)

    def show_finished(self):
        self.show = None

    def switch_pet(self):
        self.touch()
        key = self.pet_var.get()
        if key == self.pet.key:
            return
        if self.friend and self.friend.key == key:
            self.end_playdate()
        self.pet.set_pet(key)
        self.pet.finish_state()
        self.react(self.pet, f"{self.pet.spec.word} {self.pet.spec.name} reporting for duty!", hop=0)
        self.save()

    def set_size(self):
        self.size = self.size_var.get()
        for pet in self.pets():
            pet.set_pet(pet.key)
        self.save()

    def invite_friend(self):
        if self.friend:
            return
        pet = self.rouse()
        key = random.choice([k for k in PETS if k != pet.key])
        box = self.sprites.pet(PETS[key], self.size).box
        area = self.work_area_at(pet.cx, pet.cy)
        from_left = pet.cx > (area.left + area.right) / 2
        x = area.left - box[0] if from_left else area.right - box[2]
        self.friend = Pet(self, key, x, pet.y + pet.box[3] - box[3], friend=True)
        self.friend.facing = 1 if from_left else -1
        self.friend.say(f"{self.friend.spec.word} Hi {pet.spec.name}! Wanna play tag?", 3500)
        pet.say("Yay, a friend!", 2500)
        self.playdate = {"a": pet, "b": self.friend, "it": self.friend, "until": time.time() + PLAYDATE_SEC,
                         "pause_until": time.time() + 2.5}

    def tag(self, chaser, caught):
        self.playdate.update(it=caught, pause_until=time.time() + 1.6)
        caught.set_state("action", 1.0)
        self.react(chaser, random.choice(("Tag! You're it!", "Gotcha!", "Tag!")), 1500, hop=1.0, sound=random.random() < 0.4)
        self.hearts(chaser, 1)
        self.stats_for(self.pet).add(happy=3)

    def end_playdate(self):
        self.playdate, friend = None, self.friend
        if friend and not friend.leaving:
            area = self.work_area_at(friend.cx, friend.cy)
            friend.leaving, friend.leave_deadline = True, time.time() + 25
            friend.facing = -1 if friend.cx < (area.left + area.right) / 2 else 1
            friend.set_state("walk")
            friend.say("That was fun! Bye bye!", 2500)
            self.pet.say("Bye! Come back soon!", 2500)
        self.pet.finish_state()

    def remove_friend(self):
        if self.friend:
            self.friend.destroy()
            self.friend = None

    def feed(self, force=False):
        pet = self.rouse()
        if self.treat or (self.stats_for(pet).food >= 95 and not force):
            return pet.say("One treat at a time!" if self.treat else "I'm stuffed! Maybe later.", 2500)
        area = self.work_area_at(pet.cx, pet.cy)
        frames = self.sprites.treat_frames(pet.spec.treat, self.size, 0.36)
        w, h = frames[0].width, frames[0].height
        x = clamp(pet.cx + random.choice((-1, 1)) * random.uniform(0.8, 2.2) * pet.body_w - w / 2, area.left, area.right - w)
        top = max(area.top, pet.top - (160 if pet.spec.swims else 200) * pet.unit)
        if pet.spec.swims:
            floor = clamp(pet.bite_point[1], top + 2 * h, area.bottom - h) + h / 2
        else:
            floor = area.bottom if pet.grounded else pet.y + pet.box[3]
        self.treat = pet.treat = Treat(self.root, frames, x, top, floor, pet.unit, sink=pet.spec.swims)
        pet.say(f"Ooh, {pet.spec.treat_label}!", 2000)

    def finish_eating(self, pet):
        if self.treat:
            self.treat.destroy()
        self.treat = pet.treat = None
        self.sound.play(pet.spec, kind="eat")
        self.stats_for(pet).add(food=35, happy=6)
        self.hearts(pet, 2)
        pet.say(pet.spec.eat_line, 2500)

    def open_reminder_dialog(self):
        self.touch()
        if self.dialog and self.dialog.exists():
            return self.dialog.top.focus_force()
        self.dialog = ReminderDialog(self, self.pet.cx, self.pet.top, self.add_reminder)

    def add_reminder(self, text, minutes):
        if len(self.reminders) >= MAX_REMINDERS:
            return self.pet.say(f"I can only keep {MAX_REMINDERS} reminders at once!", 3000)
        text = text[:MAX_REMINDER_TEXT]
        self.reminders.append({"id": int(time.time() * 1000), "text": text, "due": time.time() + minutes * 60})
        self.save()
        self.react(self.rouse(), [("title", f"Got it! In {fmt_duration(minutes * 60)}:"), f"\"{text}\""], 4000)

    def cancel_reminder(self, reminder_id=None):
        self.reminders = [r for r in self.reminders if reminder_id is not None and r["id"] != reminder_id]
        self.save()
        self.pet.say("Reminder cancelled." if reminder_id is not None else "All reminders cancelled.", 2000)


def main():
    if already_running():
        message_box("Desktop Pet is already running. Look for me on your desktop!")
        return
    App().run()
