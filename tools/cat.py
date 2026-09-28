import math

import numpy as np

from engine import GROUND, Canvas, Capsule, Ellipsoid, Head, Mat, Xf, eye, finish, leg, motion, polygon

ORANGE, DARK, CREAM = "#f39a3b", "#c95f1c", "#fbe4c6"
LEGS = dict(radii=(10.5, 8.5), paw_r=(11.5, 7.5))


def orange_cat(state, t):
    cv, m = Canvas(), motion(state, t)
    if state == "sleep":
        return cat_sleep(cv, m)
    xf = Xf(m["sx"], m["sy"], m["lift"])
    eating = m.get("eat", False)
    if eating:
        m = dict(m, bob=12.0)
        tug = m["tug"]
        hd = Head(184 - tug, 204 + 0.6 * m["nod"] - 0.6 * tug, 0.62 + 0.02 * m["jaw"] - 0.03 * tug)
    else:
        hd = Head(180, 122 + m["bob"] + m["head"])
    b = m["bob"]
    bx, by = xf.p(118, 178 + b)
    head_xf = Head(*xf.p(hd.cx, hd.cy), hd.angle)
    stripes = lambda x, y: (np.sin((x - bx) * 0.21) > 0.35) & (y < by + 8)
    belly = lambda x, y: np.clip((y - by - 12) / 8, 0, 1)

    def head_stripes(x, y):
        lx, ly = head_xf.local(x, y)
        return (np.abs(np.sin(lx * 0.3)) > 0.75) & (ly < -22) & (np.abs(lx + 6) < 20)

    plain = Mat(ORANGE, spec=0.1, shine=14)
    fur = plain.but(layers=((DARK, stripes), (CREAM, belly)))
    paw = Mat(CREAM, spec=0.06)

    seg, ang = xf.p(66, 168 + b), (-2.75 if eating else -2.0) + m["tail"] * 0.6
    for i in range(5):
        ang += (0.12 if eating else 0.28) + (m["tail"] * 0.35 if i > 1 else 0)
        nxt = (seg[0] + xf.k(17) * math.cos(ang), seg[1] + xf.k(17) * math.sin(ang))
        cv.draw(Capsule(seg, nxt, xf.k(7.5 - i * 0.6), xf.k(6.9 - i * 0.6)), plain.but(color=DARK if i % 2 else ORANGE))
        seg = nxt

    for hip, phase in (((104, 190), 0), ((166, 190), math.pi)):
        leg(cv, xf, hip, phase, m, plain.but(color="#d98232"), paw.but(color="#e8cfae"), **LEGS)
    for c, r, mat in (((84, 178), (30, 29), fur), ((118, 178), (55, 30), fur), ((154, 174), (28, 31), fur.but(layers=((CREAM, belly),)))):
        cv.draw(Ellipsoid(xf.p(c[0], c[1] + b), xf.r(*r)), mat)
    for hip, phase in (((92, 192), math.pi), ((152, 192), 0)):
        leg(cv, xf, hip, phase, m, plain, paw, **LEGS)

    hp = lambda dx, dy: xf.p(*hd.p(dx, dy))
    if eating:
        cv.draw(Capsule(xf.p(150, 170 + b), hp(-8, -2), xf.k(24), xf.k(21)), plain)
    ear_y = 6 * m["tuck"]
    cv.draw(polygon([hp(8, -32 + ear_y), hp(32, -64 + ear_y), hp(40, -22)], 5), plain)
    cv.draw(Ellipsoid(hp(0, 0), xf.r(45, 41), rot=hd.angle), plain.but(layers=((DARK, head_stripes),)))
    cv.draw(polygon([hp(-34, -24), hp(-26, -66 + ear_y), hp(2, -38)], 5), plain)
    cv.draw(polygon([hp(-27, -30), hp(-23, -56 + ear_y), hp(-7, -38)], 3), Mat("#f3a7b3", spec=0.2, cast=0))
    cv.draw(Ellipsoid(hp(26, 18), xf.r(24, 17), rot=hd.angle), Mat(CREAM, spec=0.08, cast=0.25))
    eye(cv, xf, hd.p(38, -7), (6.6, 9), m, iris="#79c24f", pupil_r=(2.4, 7))
    eye(cv, xf, hd.p(10, -6), (8.6, 11), m, iris="#79c24f", pupil_r=(3, 8.6))
    cv.draw(Ellipsoid(hp(41, 8), xf.r(5.5, 4.2), rot=hd.angle), Mat("#e27f8f", spec=0.6, shine=40, cast=0.1))
    jaw = m.get("jaw", 1.0 if m["mouth"] else 0.0)
    if jaw > 0.12:
        cv.draw(Ellipsoid(hp(39, 20 + 2 * jaw), xf.r(6 + jaw, 3 + 3 * jaw), rot=hd.angle), Mat("#5a1a1a", spec=0.3, cast=0))
        cv.draw(Ellipsoid(hp(40, 23 + 2 * jaw), xf.r(4.5, 1.5 + 1.5 * jaw), rot=hd.angle), Mat("#f07f93", cast=0))
    for a, c in (((46, 16), (72, 8)), ((46, 20), (73, 21)), ((44, 24), (68, 32))):
        cv.draw(Capsule(hp(*a), hp(*c), 1.0, 0.5), Mat("#fffaf2", ambient=0.9, spec=0, rim=0, cast=0))
    return finish(cv.image(), ("#6b3310", 0.5), (128, GROUND + 1, 74 * (1 - 0.35 * m["tuck"]), 8, 0.3 * (1 - 0.5 * m["tuck"])))


def cat_sleep(cv, m):
    br = 1.5 * m["breath"]
    fur = Mat(ORANGE, layers=((DARK, lambda x, y: (np.sin((x - 120) * 0.21) > 0.35) & (y < 206)),), spec=0.1, shine=14)
    plain = Mat(ORANGE, spec=0.1, shine=14)
    cv.draw(Ellipsoid((82, 214 - br / 2), (36, 30 + br / 2)), fur)
    cv.draw(Ellipsoid((124, 212 - br / 2), (60, 32 + br / 2)), fur)
    for i, (a, b) in enumerate((((40, 238), (80, 244)), ((80, 244), (130, 245)), ((130, 245), (172, 240)))):
        cv.draw(Capsule(a, b, 8 - i, 7 - i), plain.but(color=DARK if i % 2 else ORANGE))
    cv.draw(polygon([(198, 180), (212, 154), (224, 190)], 4.5), plain)
    cv.draw(Ellipsoid((186, 206), (40, 35)), plain)
    cv.draw(polygon([(152, 186), (158, 152), (182, 176)], 4.5), plain)
    cv.draw(polygon([(158, 182), (161, 162), (176, 176)], 2.5), Mat("#f3a7b3", cast=0))
    cv.draw(Ellipsoid((208, 220), (22, 15)), Mat(CREAM, spec=0.08, cast=0.25))
    cv.draw(Ellipsoid((222, 212), (5, 4)), Mat("#e27f8f", spec=0.6, shine=40))
    eye(cv, Xf(), (188, 204), (8, 10), dict(m, closed=True))
    eye(cv, Xf(), (214, 200), (6, 8), dict(m, closed=True))
    cv.draw(Ellipsoid((196, 240), (22, 7)), Mat(CREAM, spec=0.06))
    return finish(cv.image(), ("#6b3310", 0.5), (132, GROUND + 1, 100, 8, 0.3))
