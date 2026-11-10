import math
import os
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engine import SS, Canvas, Capsule, Ellipsoid, Loft, Mat, Puffy, finish, polygon

W, H = 96, 56


def bone_treat(cv, stage):
    bone = Mat("#f3e6c8", spec=0.25, shine=20, cast=0.2)
    gnawed = bone.but(color="#e6d3aa")
    ends = {0: 68, 1: 60, 2: 46, 3: 31}[stage]
    cv.draw(Capsule((28, 28), (ends, 28), 8.5), bone)
    for x, y in ((22, 20), (22, 36)):
        cv.draw(Ellipsoid((x, y), (10 - stage * 0.6, 10 - stage * 0.6)), bone)
    if stage == 0:
        for x, y in ((74, 20), (74, 36)):
            cv.draw(Ellipsoid((x, y), (10, 10)), bone)
        return
    for dx, dy, r in ((1, -5, 5.5), (3, 1, 5), (0, 6, 4.5)):
        cv.draw(Ellipsoid((ends + dx, 28 + dy), (r, r * 0.9)), gnawed)
    for dx, dy in ((-3, -3), (1, 4), (-5, 5)):
        cv.draw(Ellipsoid((ends + dx, 28 + dy), (1.6, 1.3)), Mat("#b8a27a", cast=0))


def fish_treat(cv, stage):
    tail_x, nose_x, half, cy = 24, 86, 11.5, 30
    length = nose_x - tail_x

    def center(x):
        return cy + 1.2 * np.sin(np.clip((nose_x - x) / length, 0, 1) * math.pi)

    def height(u):
        front = np.sqrt(np.clip(1 - (1 - np.clip(u / 0.28, 0, 1)) ** 2, 0, 1))
        back = 1 - 0.8 * np.clip((u - 0.42) / 0.58, 0, 1) ** 1.2
        return half * front * back

    body = Loft(tail_x, nose_x, height, center, depth=0.7)
    cuts = ((), ((89, 30, 7),), ((88, 30, 14),), ((86, 30, 21),), ((80, 30, 29),), ((70, 30, 42),))[stage]

    bone = Mat("#efe9dc", spec=0.45, shine=30, cast=0.1)
    cv.draw(Capsule((tail_x + 2, cy), (nose_x - 8, cy), 1.4, 1.1), bone)
    for x in range(32, 78, 5):
        for sign in (-1, 1):
            cv.draw(Capsule((x, cy), (x + 3.5, cy + sign * (7.5 + 2.5 * math.sin((x - 32) / 46 * math.pi))), 0.75, 0.45), bone)
    skull = bone.but(color="#d8cdb8", spec=0.25)
    cv.draw(Ellipsoid((nose_x - 5, cy), (8, 6.5), rot=0.1), skull)
    cv.draw(Capsule((nose_x - 9, cy - 4), (nose_x - 9, cy + 4), 1.2), bone.but(color="#c7bba4", cast=0))
    cv.draw(Capsule((nose_x - 3, cy + 1), (nose_x + 2, cy + 3), 1.4, 0.9), skull.but(cast=0))

    fin = Mat("#8fa1ad", spec=0.4, shine=30, ambient=0.55, rim=0.3, cast=0.08, opacity=0.85)
    cv.draw(polygon([(tail_x + 3, cy - 3), (tail_x - 12, cy - 13), (tail_x - 6, cy),
                          (tail_x - 12, cy + 13), (tail_x + 3, cy + 3)], 1.2), fin)
    if stage < 5:
        cv.draw(polygon([(46, cy - 10), (52, cy - 17), (60, cy - 11)], 1.0), fin.but(cuts=cuts))

    def band(lo, hi):
        return lambda x, y: np.clip((body.v(x, y) - lo) / (hi - lo), 0, 1)

    def bars(x, y):
        v = body.v(x, y)
        return 0.75 * (np.sin(x * 0.55 + 3 * np.sin(y * 0.4)) > 0.45) * (v < -0.25)

    def scales(x, y):
        return 0.12 * ((np.sin(x * 1.3) * np.sin(y * 1.3 + x * 0.6)) > 0.4)

    def gill(x, y):
        u, v = body.u(x), body.v(x, y)
        return 0.6 * (np.abs(u - 0.2 - 0.05 * v * v) < 0.014) * (np.abs(v) < 0.8)

    skin = Mat("#b9c6cf", layers=(("#35536a", lambda x, y: 1 - band(-0.85, -0.05)(x, y)), ("#1c2c38", bars),
                                  ("#f3f5f6", band(0.25, 0.8)), ("#6e8594", scales), ("#4c5f6c", gill)),
               spec=0.85, shine=60, ambient=0.46, rim=0.35, cast=0.2, cuts=cuts, cut_rim="#e89a8c", rim_width=3.2)
    cv.draw(body, skin)
    cv.draw(polygon([(66, cy + 4), (58, cy + 10), (63, cy + 5)], 0.8), fin.but(cuts=cuts))
    if stage < 2:
        cv.draw(Ellipsoid((nose_x - 8, cy - 2.5), (3.6, 3.6)), Mat("#d8dde0", spec=0.7, shine=50, cast=0))
        cv.draw(Ellipsoid((nose_x - 7.6, cy - 2.4), (2.2, 2.2)), Mat("#0e0e0e", spec=0.9, shine=80, ambient=0.7, cast=0))
        cv.draw(Ellipsoid((nose_x - 8.6, cy - 3.6), (0.8, 0.8)), Mat("#ffffff", ambient=1, wrap=0, rim=0, spec=0, cast=0))
    if stage == 0:
        cv.draw(Capsule((nose_x - 5, cy + 3), (nose_x, cy + 2), 0.7), Mat("#5b6670", cast=0))


def flake_treat(cv, stage):
    rng = np.random.default_rng(7)
    for i in range(7):
        x, y = 14 + i * 11 + rng.uniform(-3, 3), 20 + rng.uniform(-6, 18)
        pts = [(x + 7 * math.cos(a), y + 5 * math.sin(a)) for a in sorted(rng.uniform(0, 2 * math.pi, 4))]
        if i < 7 - 2 * stage:
            color = ("#e8712a", "#c9392b", "#f2b134")[i % 3]
            cv.draw(polygon(pts, 1.5), Mat(color, spec=0.4, cast=0.15))


def seed_treat(cv, stage):
    rng = np.random.default_rng(9)
    seeds = []
    for i in range(28):
        x = 48 + float(np.clip(rng.normal(0, 10), -24, 24))
        y = 47 - 22 * max(0.0, 1 - ((x - 48) / 26) ** 2) * rng.random() ** 0.7
        seeds.append((y, x, rng.uniform(-0.8, 0.8), i % 6 == 0, ("#e6cf8f", "#d8b56a", "#c99d50")[i % 3]))
    seeds.sort(reverse=True)
    stripe = lambda x, y: 0.8 * (np.sin(x * 2.2 + y * 0.8) > 0.6)
    for y, x, rot, sunflower, color in seeds[:len(seeds) - stage * 7]:
        if sunflower:
            cv.draw(Ellipsoid((x, y), (6.5, 3), rot=rot), Mat("#3a3530", layers=(("#ece6d8", stripe),), spec=0.4, cast=0.2))
        else:
            cv.draw(Ellipsoid((x, y), (4.4, 3.4), rot=rot), Mat(color, spec=0.35, shine=24, cast=0.2))


def meat_treat(cv, stage):
    bone = Mat("#f1e6cc", spec=0.3, shine=24, cast=0.2)
    cv.draw(Capsule((16, 28), (52, 28), 4.5), bone)
    for y in (23, 33):
        cv.draw(Ellipsoid((12, y), (5.5, 5.5)), bone)
    cuts = ((), ((90, 22, 9),), ((88, 28, 17),), ((80, 28, 25),))[stage]
    crust = lambda x, y: 0.35 * np.clip(np.sin(x * 0.3 + np.sin(y * 0.25) * 2), 0, 1)
    cv.draw(Ellipsoid((64, 28), (27, 17)), Mat("#c47236", layers=(("#8e4a1e", crust),), spec=0.45, shine=30, cast=0.25,
                                               cuts=cuts, cut_rim="#f2b694", rim_width=4))


TREATS = {
    "bone": (bone_treat, 4, ("#5a4630", 0.5), ("#eadbb8", "#d9c49a")),
    "fish": (fish_treat, 6, ("#27333c", 0.45), ("#b9c6cf", "#e89a8c")),
    "flakes": (flake_treat, 4, ("#5a2410", 0.35), None),
    "seeds": (seed_treat, 4, ("#5a4426", 0.4), ("#d9bf85", "#8b6b3e")),
    "meat": (meat_treat, 4, ("#4a2410", 0.45), ("#c47236", "#f2b694")),
}


def treat_stages(kind):
    draw, stages, outline, _ = TREATS[kind]
    frames = []
    for stage in range(stages):
        cv = Canvas(W, H)
        draw(cv, stage)
        frames.append(finish(cv.image(), outline))
    left, top, right, bottom = frames[0].getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    box = (max(0, left - 2), max(0, top - 2), min(W, right + 2), min(H, bottom + 1))
    return [f.crop(box) for f in frames]


def crumb(kind):
    cv = Canvas(24, 24)
    rng = np.random.default_rng(zlib.crc32(kind.encode()))
    colors = TREATS[kind][3]
    for i in range(3):
        x, y = 7 + i * 5 + rng.uniform(-1.5, 1.5), 14 + rng.uniform(-4, 4)
        pts = [(x + 3.2 * math.cos(a), y + 2.6 * math.sin(a)) for a in sorted(rng.uniform(0, 2 * math.pi, 5))]
        cv.draw(polygon(pts, 1.0), Mat(colors[i % 2], spec=0.3, cast=0))
    return finish(cv.image(), ("#5a4630", 0.35))


def heart(cv):
    def inside(x, y):
        u, v = (x - 24) / 17, -(y - 25) / 17
        return (u * u + v * v - 0.3) ** 3 - u * u * v ** 3 < 0
    cv.draw(Puffy(inside, (4, 4, 44, 44), 4), Mat("#ff3b5c", spec=0.8, shine=40, ambient=0.5, rim=0.3, cast=0))
    return finish(cv.image(), ("#7a0f24", 0.4))


def bubble(cv):
    shell = lambda x, y: 0.12 + 0.88 * np.clip(np.hypot(x - 24, y - 24) / 19, 0, 1) ** 5
    cv.draw(Ellipsoid((24, 24), (19, 19)), Mat("#d8f0ff", ambient=0.95, spec=0.9, shine=60, rim=0.8, cast=0, fade=shell))
    glint = Mat("#ffffff", ambient=1, wrap=0, spec=0, rim=0, cast=0)
    cv.draw(Ellipsoid((16, 15), (6, 3.6), rot=-0.7), glint.but(opacity=0.95))
    cv.draw(Ellipsoid((32, 33), (3, 1.8), rot=-0.7), glint.but(opacity=0.55))
    return cv.image()


def snooze(cv):
    font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf"), 34 * SS)
    mask_img = Image.new("L", (48 * SS, 48 * SS), 0)
    ImageDraw.Draw(mask_img).text((24 * SS, 24 * SS), "Z", font=font, fill=255, anchor="mm")
    mask = np.asarray(mask_img) > 127
    inside = lambda x, y: mask[(y * SS).astype(int).clip(0, 48 * SS - 1), (x * SS).astype(int).clip(0, 48 * SS - 1)]
    cv.draw(Puffy(inside, (0, 0, 48, 48), 2.5), Mat("#9ecbff", spec=0.6, shine=30, ambient=0.6, cast=0))
    return finish(cv.image(), ("#2b4a73", 0.5))


FX = {"heart": heart, "bubble": bubble, "z": snooze}


def fx(kind):
    return FX[kind](Canvas(48, 48))
