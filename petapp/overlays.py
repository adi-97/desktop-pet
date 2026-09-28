import math
import time
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import GRAVITY
from .sprites import Frame
from .util import clamp
from .winapi import make_layered, system_font, update_layered

OFFSCREEN = -32000
INK, MUTED, TRACK = (34, 34, 40, 255), (90, 94, 104, 255), (228, 231, 236, 255)
_fonts = {}


class AlphaWindow:
    def __init__(self, root, cursor=None):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"1x1+{OFFSCREEN}+{OFFSCREEN}")
        self.win.configure(cursor=cursor or "")
        self.win.update_idletasks()
        self.hwnd = int(self.win.wm_frame(), 16)
        make_layered(self.hwnd)
        self.frame, self.alpha, self.size, self.pos = None, 255, (1, 1), None

    def show(self, frame, alpha=255):
        if frame is not self.frame or alpha != self.alpha:
            self.frame, self.alpha = frame, alpha
            if (frame.width, frame.height) != self.size:
                self.size = (frame.width, frame.height)
                self.win.geometry(f"{frame.width}x{frame.height}")
            update_layered(self.hwnd, frame.bitmap, alpha)

    def move(self, x, y):
        pos = (int(round(x)), int(round(y)))
        if pos != self.pos:
            self.pos = pos
            self.win.geometry(f"+{pos[0]}+{pos[1]}")

    def hide(self):
        self.move(OFFSCREEN, OFFSCREEN)

    def destroy(self):
        self.win.destroy()


def font(px, bold=False):
    if (px, bold) not in _fonts:
        paths = [p for p in (system_font("segoeuib.ttf" if bold else "segoeui.ttf"), system_font("arial.ttf")) if p]
        _fonts[px, bold] = ImageFont.truetype(str(paths[0]), px) if paths else ImageFont.load_default(px)
    return _fonts[px, bold]


def wrap(text, fnt, width):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            trial = f"{line} {word}".strip()
            if line and fnt.getlength(trial) > width:
                lines.append(line)
                trial = word
            line = trial
        lines.append(line)
    return lines


class BubbleLayout:
    def __init__(self, rows, s):
        self.s, self.font, self.bold = s, font(round(14 * s)), font(round(14 * s), bold=True)
        self.pad, self.margin, self.tail, self.line_h, self.bar_w = (round(v * s) for v in (12, 10, 12, 20, 120))
        self.rows = [r for row in rows for r in ([("text", l) for l in wrap(row, self.font, 240 * s)] if isinstance(row, str) else [row])]
        self.label_w = max([self.font.getlength(r[1]) for r in self.rows if r[0] == "bar"] or [0])
        widths = [self.font.getlength(r[1]) if r[0] != "bar" else self.label_w + self.bar_w + 56 * s for r in self.rows]
        self.box_w = round(max(widths + [40 * s])) + 2 * self.pad
        self.box_h = len(self.rows) * self.line_h + 2 * self.pad
        self.width, self.height = self.box_w + 2 * self.margin, self.box_h + self.tail + 2 * self.margin

    def render(self, tail_x):
        k, s, m, bh = 2, self.s, self.margin, self.box_h
        shape = Image.new("L", (self.width * k, self.height * k), 0)
        d = ImageDraw.Draw(shape)
        d.rounded_rectangle((m * k, m * k, (m + self.box_w) * k, (m + bh) * k), radius=round(14 * s * k), fill=255)
        d.polygon([((tail_x - 10 * s) * k, (m + bh - 2) * k), ((tail_x + 10 * s) * k, (m + bh - 2) * k),
                   ((tail_x - 2 * s) * k, (m + bh + self.tail) * k)], fill=255)
        shape = shape.resize((self.width, self.height), Image.LANCZOS)
        shadow = Image.new("RGBA", shape.size, (20, 24, 32, 0))
        shadow.putalpha(shape.point(lambda v: v * 70 // 255).transform(shape.size, Image.AFFINE, (1, 0, 0, 0, 1, -round(3 * s)))
                        .filter(ImageFilter.GaussianBlur(5 * s)))
        body = Image.new("RGBA", shape.size, (255, 255, 255, 0))
        body.putalpha(shape)
        out = Image.alpha_composite(shadow, body)
        d = ImageDraw.Draw(out)
        x0 = m + self.pad
        for i, (kind, text, *bar) in enumerate(self.rows):
            cy = m + self.pad + (i + 0.5) * self.line_h
            d.text((x0, cy), text, font=self.bold if kind == "title" else self.font, fill=INK, anchor="lm")
            if kind == "bar":
                value, color = bar
                bx, r = x0 + self.label_w + 10 * s, 5 * s
                d.rounded_rectangle((bx, cy - r, bx + self.bar_w, cy + r), radius=r, fill=TRACK)
                if value > 1:
                    d.rounded_rectangle((bx, cy - r, bx + self.bar_w * value / 100, cy + r), radius=r, fill=color)
                d.text((bx + self.bar_w + 8 * s, cy), f"{value:.0f}%", font=self.font, fill=MUTED, anchor="lm")
        return out


class SpeechBubble:
    def __init__(self, pet):
        self.pet, self.window = pet, AlphaWindow(pet.app.root)
        self.window.win.bind("<Button-1>", lambda e: self.hide())
        self.visible, self.token, self.tail_x, self.width, self.height, self.margin = False, 0, 0, 0, 0, 0
        self._frame = self._hide_job = None

    def show(self, rows, ms=6000):
        layout, pet = BubbleLayout([rows] if isinstance(rows, str) else rows, self.pet.app.scale), self.pet
        self.width, self.height, self.margin = layout.width, layout.height, layout.margin
        area = pet.app.work_area_at(pet.cx, pet.cy)
        edge = layout.margin + 20 * layout.s
        self.tail_x = int(clamp(pet.cx - clamp(pet.cx - self.width / 2, area.left, area.right - self.width), edge, self.width - edge))
        if self._frame:
            self._frame.free()
        self._frame = Frame(layout.render(self.tail_x))
        self.window.show(self._frame)
        self.visible, self.token = True, self.token + 1
        self.reposition()
        self.window.win.lift()
        if self._hide_job:
            self.window.win.after_cancel(self._hide_job)
        self._hide_job = self.window.win.after(ms, self.hide)
        return self.token

    def reposition(self):
        if self.visible:
            pet = self.pet
            area = pet.app.work_area_at(pet.cx, pet.cy)
            self.window.move(clamp(pet.cx - self.tail_x, area.left - self.margin, area.right - self.width + self.margin),
                             max(area.top - self.margin, pet.top - pet.hop - self.height + self.margin + 4))

    def hide(self):
        self._hide_job, self.visible = None, False
        self.window.hide()

    def destroy(self):
        if self._frame:
            self._frame.free()
        self.window.destroy()


class FloatingSprite:
    def __init__(self, root, frame, x, y, rise=70, ms=1400, drift=0.0):
        self.frame, self.rise, self.ms, self.drift = frame, rise, ms, drift
        self.x0, self.y0, self.start = x - frame.width / 2, y - frame.height / 2, time.time()
        self.window = AlphaWindow(root)
        self._step()

    def _step(self):
        t = (time.time() - self.start) * 1000 / self.ms
        if t >= 1:
            return self.window.destroy()
        self.window.show(self.frame, max(0, int(255 * min(1.0, t / 0.12, (1 - t) / 0.4))))
        self.window.move(self.x0 + math.sin(t * math.pi * 2) * 6 + self.drift * t, self.y0 - self.rise * (1 - (1 - t) ** 2))
        self.window.win.after(30, self._step)


class Treat:
    def __init__(self, root, frames, x, top, floor, unit, sink=False):
        self.frames, self.unit, self.sink, self.stage, self.landed = frames, unit, sink, 0, False
        self.w, self.h = frames[0].width, frames[0].height
        self.x0, self.x, self.y, self.vy, self.floor = x, x, top, 0.0, floor - self.h
        self.born, self.shake_dir, self.shake_until = time.time(), 0, 0.0
        self.window = AlphaWindow(root)
        self.window.show(frames[0])
        self.window.move(x, top)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def set_stage(self, stage):
        self.stage = min(stage, len(self.frames) - 1)
        self.window.show(self.frames[self.stage])

    def nudge(self, direction):
        self.shake_dir, self.shake_until = direction, time.time() + 0.28

    def tick(self):
        shift = 0.0
        if self.landed:
            left = max(0.0, self.shake_until - time.time())
            shift = self.shake_dir * math.sin(left * 34) * 3 * self.unit * left / 0.28
        elif self.sink:
            self.vy = min(self.vy + 0.06 * self.unit, 1.4 * self.unit)
            self.x = self.x0 + math.sin((time.time() - self.born) * 2.4) * 6 * self.unit
        else:
            self.vy += GRAVITY * self.unit
        if not self.landed:
            self.y += self.vy
            if self.y >= self.floor:
                bounce = not self.sink and self.vy > 4 * self.unit
                self.y, self.vy, self.landed = self.floor, -self.vy * 0.35 if bounce else 0.0, not bounce
        self.window.move(self.x + shift, self.y - abs(shift) * 0.4)

    def destroy(self):
        self.window.destroy()


class ReminderDialog:
    def __init__(self, app, anchor_x, anchor_y, on_submit):
        self.on_submit, top = on_submit, tk.Toplevel(app.root)
        self.top = top
        top.withdraw()
        top.title("Set a reminder")
        top.attributes("-toolwindow", True, "-topmost", True)
        top.resizable(False, False)
        frame = ttk.Frame(top, padding=14)
        frame.pack(fill="both", expand=True)
        self.text_var, self.minutes_var = tk.StringVar(), tk.StringVar(value="10")
        ttk.Label(frame, text="What should I remind you to do?").grid(row=0, column=0, columnspan=6, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.text_var, width=38)
        entry.grid(row=1, column=0, columnspan=6, sticky="we", pady=(4, 10))
        ttk.Label(frame, text="In how many minutes?").grid(row=2, column=0, columnspan=6, sticky="w")
        ttk.Entry(frame, textvariable=self.minutes_var, width=8).grid(row=3, column=0, sticky="w", pady=(4, 0))
        for i, minutes in enumerate((5, 15, 30, 60), start=1):
            ttk.Button(frame, text=str(minutes), width=4, command=lambda m=minutes: self.minutes_var.set(str(m))
                       ).grid(row=3, column=i, padx=(4, 0), pady=(4, 0))
        self.error = ttk.Label(frame, text="", foreground="#c0392b")
        self.error.grid(row=4, column=0, columnspan=6, sticky="w", pady=(6, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=6, sticky="e", pady=(6, 0))
        ttk.Button(buttons, text="Cancel", command=top.destroy).pack(side="right")
        ttk.Button(buttons, text="Remind me", command=self.submit).pack(side="right", padx=(0, 6))
        top.bind("<Return>", lambda e: self.submit())
        top.bind("<Escape>", lambda e: top.destroy())
        top.update_idletasks()
        w, h, area = top.winfo_reqwidth(), top.winfo_reqheight(), app.work_area_at(anchor_x, anchor_y)
        top.geometry(f"+{clamp(int(anchor_x - w / 2), area.left, area.right - w)}+{clamp(int(anchor_y - h - 30), area.top, area.bottom - h)}")
        top.deiconify()
        top.focus_force()
        entry.focus_set()

    def exists(self):
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    def submit(self):
        text = self.text_var.get().strip()
        try:
            minutes = float(self.minutes_var.get().strip().replace(",", "."))
        except ValueError:
            minutes = -1
        if not text or not 0 < minutes <= 7 * 24 * 60:
            return self.error.configure(text="Please type something for me to remember." if not text
                                        else "Minutes must be a number between 0.1 and 10080.")
        self.top.destroy()
        self.on_submit(text, minutes)

    def close(self):
        self.top.destroy()
