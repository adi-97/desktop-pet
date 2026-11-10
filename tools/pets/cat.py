import math

import numpy as np

from engine import GROUND, Canvas, Capsule, Ellipsoid, Head, Mat, Xf, eye, finish, leg, motion, plush, polygon, shadow

FELINES = {
    "orange_cat": dict(coat="#f0963a", far="#d6802f", stripe="#b4521a", cream="#fbe6cc", iris="#b9c247", lid="#4a2a12",
                       nose="#e5818f", ear_in="#f2a6b0", outline=("#6b3310", 0.3), freq=0.21, thresh=0.3, ink=0.8,
                       head=(48, 44), legs=dict(radii=(10.5, 8.5), paw_r=(11.5, 7.5)), pupil=(7.0, 8.2), round_ears=False,
                       marks=None),
    "tiger": dict(coat="#ea8a2a", far="#c9701f", stripe="#1f1813", cream="#fbf5ea", iris="#e2aa3a", lid="#1f1813",
                  nose="#d98f8a", ear_in="#fbf5ea", outline=("#3f2210", 0.32), freq=0.25, thresh=0.5, ink=0.95,
                  head=(51, 46), legs=dict(radii=(12.5, 10.5), paw_r=(13.5, 8.5)), pupil=(7.0, 7.8), round_ears=True,
                  marks="#fbf5ea"),
}
WHISKERS = (((46, 16), (72, 8)), ((46, 20), (73, 21)), ((44, 24), (68, 32)))


def face(cv, xf, hd, sp, m, flick=0.0, ear_y=0.0, jaw=0.0, closed=False):
    hp = lambda dx, dy: xf.p(*hd.p(dx, dy))
    head_c = xf.frame(hd)
    coat, dark = plush(sp["coat"]), plush(sp["stripe"], fur=0.6)
    inner = plush(sp["ear_in"], fur=0.8, cast=0)
    rw, rh = sp["head"]

    def markings(x, y):
        lx, ly = head_c.local(x, y)
        m_mark = (np.abs(np.sin(lx * 0.3)) > 0.72) & (ly < -rh * 0.5) & (np.abs(lx + 6) < 20)
        cheek = (np.sin(ly * 0.42 + lx * 0.1) > 0.55) & (lx < -14) & (ly > -12) & (ly < 18)
        return (m_mark | cheek) * sp["ink"]

    def white(x, y):
        lx, ly = head_c.local(x, y)
        brows = np.clip(1.6 - np.hypot((lx - 14) / 9, (ly + 21) / 4.5) * 1.6, 0, 1)
        jowl = np.clip((ly - 6) / 10, 0, 1) * np.clip((lx + 30) / 10, 0, 1)
        return np.maximum(brows, jowl) * 0.95

    layers = ((sp["marks"], white), (sp["stripe"], markings)) if sp["marks"] else ((sp["stripe"], markings),)
    if sp["round_ears"]:
        for c, r in (((22, -42 + ear_y), 13), ((-24 - flick, -40 + ear_y + 0.4 * flick), 15)):
            cv.draw(Ellipsoid(hp(*c), xf.r(r, r)), dark)
        cv.draw(Ellipsoid(hp(-21 - flick, -41 + ear_y + 0.4 * flick), xf.r(9, 8)), inner)
        cv.draw(Ellipsoid(hp(0, 0), xf.r(rw, rh), rot=hd.angle), coat.but(layers=layers))
    else:
        cv.draw(polygon([hp(8, -32 + ear_y), hp(32 - 0.6 * flick, -66 + ear_y + 0.3 * flick), hp(40, -22)], 5), coat)
        cv.draw(Ellipsoid(hp(0, 0), xf.r(rw, rh), rot=hd.angle), coat.but(layers=layers))
        cv.draw(polygon([hp(-36, -22), hp(-27 - flick, -68 + ear_y + 0.4 * flick), hp(2, -38)], 5), coat)
        cv.draw(polygon([hp(-28, -29), hp(-24 - 0.8 * flick, -57 + ear_y + 0.3 * flick), hp(-7, -38)], 3), inner)
    cream = plush(sp["cream"], fur=0.7, cast=0.22)
    cv.draw(Ellipsoid(hp(31, 25), xf.r(9, 5.5), rot=hd.angle), cream)
    if jaw > 0.12:
        cv.draw(Ellipsoid(hp(39, 21 + 2 * jaw), xf.r(6 + jaw, 2.5 + 3 * jaw), rot=hd.angle), Mat("#5a1a1a", spec=0.3, cast=0))
        cv.draw(Ellipsoid(hp(40, 24 + 2 * jaw), xf.r(4.5, 1.5 + 1.5 * jaw), rot=hd.angle), Mat("#f07f93", cast=0))
    for c, r in (((26, 16), (10.5, 8.5)), ((37, 15.5), (9.5, 8))):
        cv.draw(Ellipsoid(hp(*c), xf.r(*r), rot=hd.angle), cream)
    for a, c in (((41, 11), (41, 14)), ((41, 14), (38.5, 16.5)), ((38.5, 16.5), (35.5, 15.5)),
                 ((41, 14), (43.5, 16.5)), ((43.5, 16.5), (46.5, 15.5))):
        cv.draw(Capsule(hp(*a), hp(*c), xf.k(0.75)), Mat("#6a4a40", cast=0, ambient=0.8))
    cv.draw(polygon([hp(35, 5), hp(47, 5), hp(41, 11.5)], 2.2), Mat(sp["nose"], spec=0.45, shine=35, cast=0.12))
    state, look = dict(m, closed=closed), dict(lid=sp["lid"], ring=1.07, glow_k=0.3)
    eye(cv, xf, hd.p(39, -4), (6, 8), state, iris=sp["iris"], pupil_r=(sp["pupil"][0] * 0.68, sp["pupil"][1] * 0.8), **look)
    eye(cv, xf, hd.p(14, -3), (9.5, 10.5), state, iris=sp["iris"], pupil_r=sp["pupil"], **look)
    for a, c in WHISKERS:
        cv.draw(Capsule(hp(*a), hp(*c), 0.9, 0.45), Mat("#fffaf2", ambient=0.9, spec=0, rim=0, cast=0))


def feline(kind):
    sp = FELINES[kind]

    def render(state, t):
        cv, m = Canvas(), motion(state, t)
        if state == "sleep":
            return sleep(cv, m)
        xf = Xf(m["sx"], m["sy"], m["lift"])
        eating = m.get("eat", False)
        if eating:
            m = dict(m, bob=12.0)
            tug = m["tug"]
            hd = Head(184 - tug, 204 + 0.6 * m["nod"] - 0.6 * tug, 0.62 + 0.02 * m["jaw"] - 0.03 * tug)
        else:
            hd = Head(180, 120 + m["bob"] + m["head"], m["tilt"])
        b = m["bob"]
        bx, by = xf.p(118, 178 + b)

        def stripes(x, y):
            wave = np.sin((x - bx) * sp["freq"] + 2.0 * np.sin((y - by) * 0.08) + 0.6 * np.sin(x * 0.05))
            return (wave > sp["thresh"] + 0.4 * np.clip((y - by) / 30 + 0.2, 0, 1)) * (y < by + 14) * sp["ink"]

        belly = lambda x, y: np.clip((y - by - 10) / 8, 0, 1)
        bands = lambda x, y: (np.sin(y * 0.32 + x * 0.05) > 0.55) * sp["ink"] * 0.7
        plain = plush(sp["coat"])
        fur = plush(sp["coat"], ((sp["stripe"], stripes), (sp["cream"], belly)))
        limb, far = plush(sp["coat"], ((sp["stripe"], bands),)), plush(sp["far"], ((sp["stripe"], bands),))
        paw = plush(sp["cream"], fur=0.5)

        seg, ang = xf.p(66, 168 + b), (-2.75 if eating else -2.0) + m["tail"] * 0.6
        thick = sp["legs"]["radii"][0] / 10.5
        for i in range(5):
            ang += (0.12 if eating else 0.28) + (m["tail"] * 0.35 if i > 1 else 0)
            nxt = (seg[0] + xf.k(17) * math.cos(ang), seg[1] + xf.k(17) * math.sin(ang))
            ring = sp["stripe"] if i % 2 or (i == 4 and sp["round_ears"]) else sp["coat"]
            cv.draw(Capsule(seg, nxt, xf.k((7.5 - i * 0.6) * thick), xf.k((6.9 - i * 0.6) * thick)), plush(ring, fur=0.7))
            seg = nxt

        for hip, phase, knee in (((104, 190), math.pi, -1), ((166, 190), 1.5 * math.pi, 1)):
            leg(cv, xf, hip, phase, m, far, paw.but(color="#e3cfb2"), knee=knee, toes="#b59a80", **sp["legs"])
        for c, r, mat in (((84, 178), (30, 29), fur), ((118, 178), (55, 30), fur), ((154, 174), (28, 31), fur.but(layers=((sp["cream"], belly),)))):
            cv.draw(Ellipsoid(xf.p(c[0], c[1] + b), xf.r(*r)), mat)
        for hip, phase, knee in (((92, 192), 0.0, -1), ((152, 192), 0.5 * math.pi, 1)):
            leg(cv, xf, hip, phase, m, limb, paw, knee=knee, toes="#b59a80", **sp["legs"])

        if eating:
            cv.draw(Capsule(xf.p(150, 170 + b), xf.p(*hd.p(-8, -2)), xf.k(24), xf.k(21)), plain)
        face(cv, xf, hd, sp, m, 14 * m["ear"], 6 * m["tuck"], m.get("jaw", 1.0 if m["mouth"] else 0.0))
        return finish(cv.image(), sp["outline"], shadow(m, 128, 74, 8, 0.3))

    def sleep(cv, m):
        br = 1.5 * m["breath"]
        stripes = lambda x, y: (np.sin((x - 120) * sp["freq"] + 2 * np.sin(y * 0.08)) > sp["thresh"] + 0.2) * (y < 206) * sp["ink"]
        fur = plush(sp["coat"], ((sp["stripe"], stripes),))
        cv.draw(Ellipsoid((82, 214 - br / 2), (36, 30 + br / 2)), fur)
        cv.draw(Ellipsoid((124, 212 - br / 2), (60, 32 + br / 2)), fur)
        for i, (a, b) in enumerate((((40, 238 - 40 * m["tail"]), (80, 244)), ((80, 244), (130, 245)), ((130, 245), (172, 240)))):
            cv.draw(Capsule(a, b, 8 - i, 7 - i), plush(sp["stripe"] if i % 2 else sp["coat"], fur=0.7))
        face(cv, Xf(), Head(184, 202, 0.12), sp, m, 10 * m["ear"], closed=True)
        cv.draw(Ellipsoid((198, 240), (22, 7)), plush(sp["cream"], fur=0.5))
        return finish(cv.image(), sp["outline"], (132, GROUND + 1, 100, 8, 0.3))

    return render


orange_cat = feline("orange_cat")
tiger = feline("tiger")
