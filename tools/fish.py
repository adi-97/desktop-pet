import math

import numpy as np
from PIL import Image

from engine import FRAMES, Canvas, Capsule, Ellipsoid, Loft, Mat, Xf, eye, finish, polygon


def goldfish(state, t):
    cv = Canvas()
    tau = 2 * math.pi * t
    speed = {"idle": 1, "walk": 2, "action": 4, "sleep": 1, "eat": 2}[state]
    amp = {"idle": 1.6, "walk": 4.5, "action": 5.5, "sleep": 0.6, "eat": 1.8}[state]
    rise = 9 * math.sin(math.pi * t) if state == "action" else 0
    cy = 124 - rise + (10 if state == "sleep" else 0) + 1.5 * math.sin(tau)
    tail_x, nose_x, half = 92, 236, 33
    length = nose_x - tail_x
    wave = speed * tau

    def center(x):
        s = np.clip((nose_x - x) / length, 0, 1.6)
        return cy + amp * s ** 2 * np.sin(2.2 * s * math.pi - wave) + (6 * s if state == "sleep" else 0)

    def height(u):
        front = np.sqrt(np.clip(1 - (1 - np.clip(u / 0.36, 0, 1)) ** 2, 0, 1))
        back = 1 - 0.78 * np.clip((u - 0.42) / 0.58, 0, 1) ** 1.3
        return half * front * back

    body = Loft(tail_x, nose_x, height, center)

    def at(u, v):
        x = nose_x - u * length
        return x, float(center(x) + v * height(np.array(u)))

    def bend(points, pivot, amount):
        px, py = pivot
        out = []
        for x, y in points:
            r = math.hypot(x - px, y - py)
            a = amount * (r / 70) ** 1.3
            c, s = math.cos(a), math.sin(a)
            out.append((px + (x - px) * c - (y - py) * s, py + (x - px) * s + (y - py) * c))
        return out

    def fin_mat(base, reach, rays=14, strength=0.95):
        bx, by = base

        def ray_lines(x, y):
            return 0.4 * (np.sin(np.arctan2(y - by, x - bx) * rays) > 0.55)

        def tips(x, y):
            return np.clip(np.hypot(x - bx, y - by) / reach - 0.45, 0, 1) * 0.7

        def fade(x, y):
            return strength - 0.55 * np.clip(np.hypot(x - bx, y - by) / reach, 0, 1)

        return Mat("#ff7b35", layers=(("#c0431a", ray_lines), ("#ffd6b0", tips)), spec=0.35, shine=26,
                   ambient=0.55, rim=0.25, cast=0.1, fade=fade)

    flutter = math.sin(speed * tau + 1.3)
    root_top, root_bottom = at(1.0, -1), at(1.0, 1)
    pivot = at(1.0, 0)
    sweep = -amp * 0.06 * math.sin(wave - 2.2 * math.pi)
    tail_pts = [root_top]
    for theta in np.linspace(0.95, -0.95, 23):
        r = 74 * (0.52 + 0.48 * abs(math.sin(theta * 1.65)) ** 0.8) + 2.5 * math.sin(theta * 7 + wave)
        tail_pts.append((pivot[0] - r * math.cos(theta), pivot[1] - r * math.sin(theta)))
    tail_pts.append(root_bottom)
    tail_pts = bend(tail_pts, pivot, sweep + 0.12 * flutter * (amp / 4))
    cv.draw(polygon(tail_pts, 2.2), fin_mat(pivot, 74, rays=18))

    top = [at(0.3, -0.92), at(0.36, -1.9 - 0.05 * flutter), at(0.47, -2.05), at(0.64, -1.35), at(0.7, -0.9)]
    cv.draw(polygon(top, 2), fin_mat(at(0.5, -0.9), 40, rays=12))
    anal = [at(0.66, 0.85), at(0.74, 1.75 + 0.1 * flutter), at(0.83, 1.5), at(0.84, 0.85)]
    cv.draw(polygon(anal, 1.8), fin_mat(at(0.75, 0.85), 26, rays=9))
    pelvic = [at(0.44, 0.9), at(0.54, 1.85 + 0.15 * flutter), at(0.58, 1.55), at(0.55, 0.9)]
    cv.draw(polygon(pelvic, 1.8), fin_mat(at(0.49, 0.9), 26, rays=9))

    def band(lo, hi):
        return lambda x, y: np.clip((body.v(x, y) - lo) / (hi - lo), 0, 1)

    def scales(x, y):
        u, v = body.u(x), body.v(x, y)
        a, b = (x - tail_x) / 7.5, v * height(np.clip(u, 0, 1)) / 6.5
        row = np.floor(b)
        a = a + 0.5 * (row % 2)
        dx, dy = a - np.floor(a) - 0.5, b - row - 0.5
        ring = np.abs(np.hypot(dx, dy) - 0.5) < 0.1
        return 0.3 * (ring & (dx < 0.05) & (u > 0.3) & (u < 0.93) & (np.abs(v) < 0.8))

    def gill(x, y):
        u, v = body.u(x), body.v(x, y)
        return 0.55 * (np.abs(u - 0.27 - 0.06 * v * v) < 0.011) * (np.abs(v) < 0.75)

    skin = Mat("#f2932c", layers=(("#d6461b", lambda x, y: 1 - band(-0.75, 0.05)(x, y)), ("#fde2ae", band(0.3, 0.85)),
                                  ("#b24a17", scales), ("#a8401a", gill)),
               spec=0.6, shine=34, ambient=0.46, rim=0.3, cast=0.22)
    cv.draw(body, skin)

    pectoral_base = at(0.31, 0.45)
    pectoral = [pectoral_base, at(0.36, 0.2), at(0.52, 0.85 + 0.25 * flutter), at(0.47, 1.2 + 0.2 * flutter)]
    cv.draw(polygon(bend(pectoral, pectoral_base, 0.15 * flutter), 1.5),
            fin_mat(pectoral_base, 26, rays=8, strength=0.85))

    ex, ey = at(0.13, -0.22)
    cv.draw(Ellipsoid((ex, ey), (10.5, 10.5)), Mat("#8a4a14", spec=0.4, cast=0.25))
    cv.draw(Ellipsoid((ex + 0.5, ey), (9, 9)), Mat("#d9a441", spec=0.7, shine=50, ambient=0.6, cast=0))
    cv.draw(Ellipsoid((ex + 1.5, ey + 0.5), (6.2, 6.4)), Mat("#0e0e0e", spec=0.9, shine=80, ambient=0.7, cast=0))
    glint = Mat("#ffffff", ambient=1, wrap=0, rim=0, spec=0, cast=0)
    cv.draw(Ellipsoid((ex - 2.5, ey - 3.5), (2.6, 2.2)), glint)
    cv.draw(Ellipsoid((ex + 3.5, ey + 3), (1.1, 1.1)), glint.but(opacity=0.7))
    mx, my = at(0.012, 0.18)
    gape = (state == "action" and 0.15 < t < 0.8) or (state == "eat" and math.sin(3 * tau) > 0.1)
    cv.draw(Ellipsoid((mx, my), (4.5, 4.5) if gape else (3.5, 2.4)),
            Mat("#6e2414" if gape else "#d47856", spec=0.4, cast=0.1))
    image = finish(cv.image(), ("#7a3410", 0.28))
    return image.rotate(-18, resample=Image.BICUBIC, center=(160, 124)) if state == "eat" else image
