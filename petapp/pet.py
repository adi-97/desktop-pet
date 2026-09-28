import math
import random
import time

from .config import (ANIM_MS, CLICK_SLOP, DOUBLE_CLICK_MS, FRAMESET, GRAVITY, HUNGRY_LINES, PETS, TICK_MS,
                     TIMED_STATES, WALK_SPEED)
from .overlays import AlphaWindow, SpeechBubble
from .util import clamp, sign


class Pet:
    def __init__(self, app, key, x, y, friend=False):
        self.app, self.friend, self.alive = app, friend, True
        self.x, self.y, self.vx, self.vy, self.hop = float(x), float(y), 0.0, 0.0, 0.0
        self.facing, self.airborne, self.leaving = -1 if friend else 1, False, False
        self.chase_until = self.pounce_ready = self.next_zzz = self.eat_start = self.leave_deadline = self.swim_dy = 0.0
        self.next_bubble = time.time() + 2
        self.treat = self.run_target = self.drag = self._click = self._frame = None
        self._ignore_release, self._rub = False, [None, 0, [], 0.0]
        self.window = AlphaWindow(app.root, cursor="hand2")
        self.set_pet(key, anchor=False)
        self.keep_on_screen()
        self.bubble = SpeechBubble(self)
        for event, handler in (("<ButtonPress-1>", self._on_press), ("<B1-Motion>", self._on_drag),
                               ("<ButtonRelease-1>", self._on_release), ("<Double-Button-1>", self._on_double),
                               ("<Button-3>", app.show_menu), ("<Motion>", self._on_hover),
                               ("<Leave>", lambda e: self._rub.__setitem__(0, None))):
            self.window.win.bind(event, handler)
        self.set_state("idle", random.uniform(1, 3))
        self._animate(time.time())
        self._render()

    @property
    def box(self):
        return self.sprites.box

    @property
    def cx(self):
        return self.x + (self.box[0] + self.box[2]) / 2

    @property
    def cy(self):
        return self.y + (self.box[1] + self.box[3]) / 2

    @property
    def top(self):
        return self.y + self.box[1]

    @property
    def body_w(self):
        return self.box[2] - self.box[0]

    @property
    def unit(self):
        return self.sprites.height / 150

    @property
    def grounded(self):
        return self.app.flag("gravity") and not self.spec.swims

    @property
    def mouth(self):
        if self.state == "eat":
            return self.bite_point
        return self.x + self.sprites.width * (0.93 if self.facing == 1 else 0.07), self.y - self.hop + self.sprites.height * 0.51

    def bite_offset(self, facing):
        fx, fy = self.spec.bite
        return self.sprites.width * (fx if facing == 1 else 1 - fx), self.sprites.height * fy

    @property
    def bite_point(self):
        ox, oy = self.bite_offset(self.facing)
        return self.x + ox, self.y - self.hop + oy

    def bounds(self, area):
        return area.left - self.box[0], area.right - self.box[2], area.top - self.box[1], area.bottom - self.box[3]

    def keep_on_screen(self, area=None):
        x0, x1, y0, y1 = self.bounds(area or self.app.work_area_at(self.cx, self.cy))
        self.x, self.y = clamp(self.x, x0, x1), clamp(self.y, y0, y1)

    def set_pet(self, key, anchor=True):
        bottom, center = (self.y + self.box[3], self.cx) if anchor else (0, 0)
        self.key, self.spec = key, PETS[key]
        self.sprites = self.app.sprites.pet(self.spec, self.app.size)
        if anchor:
            self.x, self.y = center - (self.box[0] + self.box[2]) / 2, bottom - self.box[3]
            self.keep_on_screen()
        self.frame_i, self.next_frame = -1, 0.0

    def set_state(self, state, seconds=None):
        self.state, self.state_until = state, time.time() + seconds if seconds else 0.0
        self.frame_i, self.next_frame = -1, 0.0
        if state != "alert":
            self.hop = 0.0

    def _ensure(self, state):
        if self.state != state:
            self.set_state(state)

    def finish_state(self):
        rest = "sit" if not self.friend and self.app.focus_phase() == "focus" else "idle"
        self.set_state(rest, random.uniform(1.5, 4.0))

    def say(self, rows, ms=4000):
        return self.bubble.show(rows, ms)

    def sleep(self):
        self.set_state("sleep")
        self.next_zzz = time.time() + 1

    def wake(self, greet=True):
        self.finish_state()
        if greet:
            self.say(random.choice(("*yaaawn*... Oh, hi!", "Mmm... was I asleep? Definitely not.")), 3000)

    def destroy(self):
        self.alive = False
        self.bubble.destroy()
        self.window.destroy()

    def _on_press(self, e):
        self.app.touch()
        self.drag = {"ox": e.x_root - self.x, "oy": e.y_root - self.y, "sx": e.x_root, "sy": e.y_root,
                     "moved": False, "samples": [(time.time(), e.x_root, e.y_root)]}

    def _on_drag(self, e):
        d = self.drag
        if d is None or (not d["moved"] and abs(e.x_root - d["sx"]) + abs(e.y_root - d["sy"]) < CLICK_SLOP):
            return
        if not d["moved"]:
            d["moved"], self.airborne = True, False
            self.set_state("drag")
        self.x, self.y = e.x_root - d["ox"], e.y_root - d["oy"]
        self.keep_on_screen(self.app.work_area_at(e.x_root, e.y_root))
        d["samples"] = (d["samples"] + [(time.time(), e.x_root, e.y_root)])[-8:]
        self._render()

    def _on_release(self, e):
        d, self.drag = self.drag, None
        if self._ignore_release or d is None:
            self._ignore_release = False
        elif d["moved"]:
            self._throw(d["samples"])
        else:
            if self._click:
                self.window.win.after_cancel(self._click)
            self._click = self.window.win.after(DOUBLE_CLICK_MS, lambda: (setattr(self, "_click", None), self.app.on_pet_click(self)))

    def _on_double(self, e):
        if self._click:
            self.window.win.after_cancel(self._click)
        self._click, self.drag, self._ignore_release = None, None, True
        self.app.on_pet_petted(self)

    def _on_hover(self, e):
        last, direction, marks, cooldown = self._rub
        now, dx = time.time(), e.x_root - (last if last is not None else e.x_root)
        if last is None or abs(dx) >= 4:
            self._rub[0] = e.x_root
        if last is not None and abs(dx) >= 4 and sign(dx) != direction:
            self._rub[1:3] = [sign(dx), [t for t in marks if now - t < 1.2] + [now]]
            if len(self._rub[2]) >= 5 and now > cooldown:
                self._rub[2:] = [[], now + 2.5]
                self.app.on_pet_petted(self)

    def _throw(self, samples):
        now = time.time()
        recent = [s for s in samples if now - s[0] <= 0.12]
        ticks = (recent[-1][0] - recent[0][0]) * 1000 / TICK_MS if len(recent) >= 2 else 0
        if not self.grounded:
            return self.finish_state()
        cap = 40 * self.unit
        self.vx = clamp((recent[-1][1] - recent[0][1]) / ticks, -cap, cap) if ticks else 0.0
        self.vy = clamp((recent[-1][2] - recent[0][2]) / ticks, -cap, cap) if ticks else 0.0
        self.airborne = True
        self.set_state("fall")
        if math.hypot(self.vx, self.vy) > 14 * self.unit:
            self.say(random.choice(("Wheee!", "Weeeee!", "I can fly!")), 1500)

    def tick(self, now):
        if not self.alive:
            return
        if not (self.drag and self.drag["moved"]):
            area = self.app.work_area_at(self.cx, self.cy)
            self._physics(area) if self.airborne else self._behave(now, area)
            if not self.alive:
                return
        self._animate(now)
        self._render()

    def _physics(self, area):
        x0, x1, y0, floor = self.bounds(area)
        self.vy += GRAVITY * self.unit
        self.x, self.y = self.x + self.vx, max(y0, self.y + self.vy)
        if not x0 <= self.x <= x1:
            self.x, self.vx = clamp(self.x, x0, x1), -self.vx * 0.5
        if self.y >= floor:
            self.y = floor
            if self.vy > 6 * self.unit:
                self.vy, self.vx = -self.vy * 0.42, self.vx * 0.7
            else:
                self.vx = self.vy = 0.0
                self.airborne = False
                self.finish_state()
        if abs(self.vx) > 0.5:
            self.facing = sign(self.vx)

    def _walk(self, direction, mult, area=None):
        self.facing = direction
        self.x += direction * WALK_SPEED * self.unit * mult * self.app.speed_factor(self)
        if area is None:
            return False
        x0, x1, _, _ = self.bounds(area)
        hit = not x0 < self.x < x1
        self.x = clamp(self.x, x0, x1)
        return hit

    def _step_to(self, dx, dy, mult, area, face=None):
        step = WALK_SPEED * self.unit * mult * self.app.speed_factor(self)
        self.facing = face or sign(dx) or self.facing
        backing = 0.5 if sign(dx) not in (0, self.facing) else 1.0
        self.x += clamp(dx, -step, step) * backing
        self.y += clamp(dy, -step, step)
        self.keep_on_screen(area)
        return abs(dx) <= step and abs(dy) <= step

    def _behave(self, now, area):
        app, state = self.app, self.state
        if self.grounded and not self.leaving:
            floor = self.bounds(area)[3]
            if self.y < floor - 1:
                self.airborne, self.vx, self.vy = True, 0.0, 0.0
                return self.set_state("fall")
            self.y = floor
        if self.spec.swims:
            if state != "alert":
                self.hop = math.sin(now * 2.2) * 3 * self.unit
            if state != "sleep" and now >= self.next_bubble:
                self.next_bubble = now + random.uniform(3, 8)
                app.bubbles(self, random.randint(1, 3))
        if state in TIMED_STATES:
            if state == "alert":
                self.hop = abs(math.sin(now * 13)) * 12 * self.unit
            if state == "eat" and self.treat is not None:
                self._chew(now)
            if now >= self.state_until:
                if state == "eat":
                    app.finish_eating(self)
                self.finish_state()
        elif state == "sleep":
            if now >= self.next_zzz:
                self.next_zzz = now + 2.4
                app.float_z(self)
        elif self.leaving:
            self._ensure("walk")
            self._walk(self.facing, 1.6)
            if now > self.leave_deadline or self.x > area.right + 5 or self.x + self.sprites.width < area.left - 5:
                app.remove_friend()
        elif self.run_target is not None:
            self._ensure("walk")
            if self._step_to(self.run_target - self.cx, 0, 4, area) or self._walk(self.facing, 0, area):
                self.run_target = None
                self.finish_state()
        elif app.playdate and self in (app.playdate["a"], app.playdate["b"]):
            self._play(now, area, app.playdate)
        elif self.treat is not None:
            self._go_to_treat(area)
        elif not self.friend and (app.flag("chase") or now < self.chase_until):
            self._chase(now, area)
        elif state == "walk":
            self._wander(now, area)
        elif state != "sit" and now >= self.state_until:
            self._decide(now)

    def _wander(self, now, area):
        if self._walk(self.facing, 1.0, area):
            self.facing = -self.facing
        if self.spec.swims and self.swim_dy:
            _, _, y0, y1 = self.bounds(area)
            self.y += self.swim_dy * self.unit
            if not y0 < self.y < y1:
                self.swim_dy = -self.swim_dy
            self.keep_on_screen(area)
        if now >= self.state_until:
            self.finish_state()

    def _decide(self, now):
        app, roll = self.app, random.random()
        if not self.friend:
            stats = app.stats_for(self)
            if app.should_sleep(now):
                return self.sleep()
            if stats.food < 25 and roll < 0.12 and not self.bubble.visible:
                self.say(random.choice(HUNGRY_LINES), 3500)
            if stats.happy > 70 and roll > 0.9:
                self.set_state("action", 0.9)
                return app.hearts(self, 2)
            if 0.55 <= roll < 0.6:
                self.chase_until = now + 8
                return
        if roll < 0.55:
            self.facing, self.swim_dy = random.choice((-1, 1)), random.choice((-0.8, 0.0, 0.8))
            self.set_state("walk", random.uniform(2, 6))
        else:
            self.set_state("idle", random.uniform(2, 6))

    def _go_to_treat(self, area):
        treat = self.treat
        face = sign(treat.cx - self.cx) or self.facing
        ox, oy = self.bite_offset(face)
        dy = treat.cy - oy - self.y if self.spec.swims else 0.0
        arrived = self._step_to(treat.cx - ox - self.x, dy, 1.3, area, face)
        if not (arrived and treat.landed):
            return self._ensure("walk" if not arrived or self.spec.swims else "idle")
        self.eat_start = time.time()
        self.set_state("eat", self.spec.eat_secs)
        if not self.spec.swims:
            self.say("*sniff sniff*", 1200)

    def _chew(self, now):
        count = len(self.treat.frames)
        stage = min(count - 1, int((now - self.eat_start) / self.spec.eat_secs * count))
        if stage > self.treat.stage:
            self.treat.set_stage(stage)
            self.treat.nudge(self.facing)
            self.app.on_bite(self)

    def _chase(self, now, area):
        px, py = self.window.win.winfo_pointerxy()
        dx, dy = px - self.cx, 0 if self.grounded else py - self.cy
        if math.hypot(dx, dy) > self.body_w * 0.45:
            self._ensure("walk")
            return self._step_to(dx, dy, 1.5, area)
        self.facing = sign(dx) or self.facing
        if now < self.pounce_ready:
            return self._ensure("idle")
        self.pounce_ready = now + 2.5
        if random.random() < 0.35:
            self.say(random.choice(("Got you!", "Pounce!", "Mine!")), 1200)
        if self.grounded:
            self.airborne, self.vx, self.vy = True, 0.0, -9 * self.unit
            self.set_state("fall")
        else:
            self.set_state("action", 0.6)

    def _play(self, now, area, playdate):
        other = playdate["b"] if self is playdate["a"] else playdate["a"]
        dx = other.cx - self.cx
        if now < playdate["pause_until"] or other.drag or other.airborne:
            self._ensure("idle")
            self.facing = sign(dx) or self.facing
        elif playdate["it"] is self and abs(dx) < (self.body_w + other.body_w) * 0.3:
            self.app.tag(self, other)
        else:
            self._ensure("walk")
            chasing = playdate["it"] is self
            self._walk((sign(dx) or 1) * (1 if chasing else -1), 1.7 if chasing else 1.3, area)

    def _animate(self, now):
        frames = self.sprites.frames[FRAMESET.get(self.state, self.state)][self.facing]
        if now >= self.next_frame:
            self.frame_i = (self.frame_i + 1) % len(frames)
            speed = self.app.speed_factor(self) * (3 if self.run_target is not None else 1) if self.state == "walk" else 1
            self.next_frame = now + ANIM_MS[self.state] / 1000 / speed
        self._frame = frames[self.frame_i % len(frames)]

    def _render(self):
        self.window.show(self._frame)
        old = self.window.pos
        self.window.move(self.x, self.y - self.hop)
        if self.window.pos != old:
            self.bubble.reposition()
