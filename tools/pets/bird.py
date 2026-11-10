import math

import numpy as np

from engine import GROUND, Canvas, Capsule, Ellipsoid, Head, Mat, Xf, eye, finish, motion, plush, polygon, shadow

GREEN, LIGHT, DARK = "#3daa3c", "#8fd862", "#2a8636"
RED, YELLOW, BLUE = "#e2372c", "#f4d23c", "#2f62c4"
BEAK, BEAK_TIP, FEET, IRIS = "#ece0c8", "#8f8578", "#8d8a86", "#e8892a"
OUTLINE = ("#1f4a1c", 0.3)

def smooth(points, rounds=3):
    pts = list(points)
    for _ in range(rounds):
        pairs = zip(pts, pts[1:] + pts[:1])
        pts = [p for (x0, y0), (x1, y1) in pairs
               for p in ((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))]
    return pts


BODY = smooth([(x * 0.92, y) for x, y in ((0, -66), (18, -60), (32, -38), (38, -8), (36, 20), (26, 46), (6, 60),
                                           (-14, 62), (-30, 50), (-36, 22), (-34, -10), (-24, -42), (-10, -62))])
FOLDED = smooth([(x * 0.85, y) for x, y in ((26, -34), (34, -8), (30, 22), (10, 52), (-8, 78), (-22, 74), (-30, 40),
                                             (-26, 2), (-8, -30))])
FLAP = ((0, 8), (0.3, 10), (0.62, 8), (0.9, 2), (1.0, -6), (0.86, -14), (0.72, -11), (0.6, -20), (0.44, -15),
        (0.3, -22), (0.14, -17), (0, -12))
TAIL = ((-8, -10), (54, -9), (62, -4), (58, 1), (62, 6), (54, 10), (-8, 10))
BEAK_UP = ((16, -14), (30, -15), (42, -6), (47, 8), (44, 22), (39, 12), (30, 8), (18, 4))
POSES = {
    "perch": ((124, 162), 0.12, 0.0, 2.45),
    "fly": ((122, 140), 1.3, 0.1, 3.2),
    "peck": ((116, 172), 0.7, 0.85, 3.5),
    "sleep": ((124, 168), 0.05, 0.3, 2.45),
}


def feather(color, layers=()):
    return plush(color, layers, fur=0.45, spec=0.07, shine=12)


def scallops(frame, weight):
    def fn(x, y):
        lx, ly = frame.local(x, y)
        a, b = lx / 8, ly / 6
        a = a + 0.5 * (np.floor(b) % 2)
        return weight * ((b % 1) + 1.6 * ((a % 1) - 0.5) ** 2 > 0.85)
    return fn


def flap_wing(cv, xf, shoulder, beta, length, color=GREEN):
    up = math.sin(beta)
    span, side = length * max(0.22, abs(up)), 1 if up >= 0 else -1
    frame = Head(*shoulder, -1.9 if side > 0 else 1.8)
    sx, sy = xf.p(*shoulder)
    reach = lambda x, y: np.hypot(x - sx, y - sy) / max(span, 1)
    layers = ((BLUE, lambda x, y: np.clip((reach(x, y) - 0.55) / 0.25, 0, 1) * 0.95),
              (RED, lambda x, y: 0.85 * (np.abs(reach(x, y) - 0.45) < 0.06)))
    cv.draw(polygon([xf.p(*frame.p(u * span, side * w)) for u, w in FLAP], 2.2), feather(color, layers))


def parrot(state, t):
    cv, m, tau = Canvas(), motion(state, t), 2 * math.pi * t
    pose = {"walk": "fly", "eat": "peck", "sleep": "sleep"}.get(state, "perch")
    (bx, by), rot, head_rot, tail_rot = POSES[pose]
    xf = Xf(m["sx"], m["sy"], m["lift"])
    flap, gape, fluff = None, 0.0, 1.0
    if state == "idle":
        head_rot += 2.2 * m["tilt"]
        tail_rot += 0.5 * m["tail"]
    elif state == "walk":
        flap = 0.25 + 1.1 * math.cos(2 * tau)
        by += 3 * math.cos(2 * tau + 1.3)
        tail_rot += 0.06 * math.sin(2 * tau)
    elif state == "action":
        flap, gape = 0.25 + 1.15 * math.cos(3 * tau), m["mouth"]
        tail_rot += 0.3 * m["tail"]
    elif state == "sleep":
        fluff = 1.06 + 0.025 * m["breath"]
    elif state == "eat":
        tail_rot += 0.1 * math.sin(2 * tau)
    body = Head(bx, by, rot)
    if pose == "peck":
        hx, hy = 168 - 1.5 * m["tug"], 190 + 7 * m["jaw"]
    else:
        hx, hy = body.p(10, -56 if pose == "sleep" else -64)
    hy += m["head"] if state == "idle" else 0
    head = Head(hx, hy, head_rot)
    body_c, head_c = xf.frame(body), xf.frame(head)
    shoulder = body.p(-14, -28)
    bp = lambda dx, dy: xf.p(*body.p(dx * fluff, dy * fluff))
    hp = lambda dx, dy: xf.p(*head.p(dx, dy))

    if flap is not None:
        flap_wing(cv, xf, (shoulder[0] - 6, shoulder[1] - 4), flap, 100, DARK)
    root = Head(*body.p(-14, 50), tail_rot)
    root_c = xf.frame(root)
    tail_tip = lambda x, y: np.clip((root_c.local(x, y)[0] - 36) / 14, 0, 1) * 0.9
    cv.draw(polygon([xf.p(*root.p(u, v)) for u, v in TAIL], 2), feather(GREEN, ((YELLOW, tail_tip),)))

    foot = Mat(FEET, spec=0.2, cast=0.12)
    if state == "walk":
        cv.draw(Capsule(bp(4, 40), bp(-2, 56), 3.4, 2.6), foot)
    else:
        fy = GROUND - 6 - 18 * m["tuck"]
        for dx in (-6, 8):
            fx = bx + dx + (8 if pose == "peck" else 0)
            cv.draw(Capsule(xf.p(fx, by + 40), xf.p(fx + 2, fy), xf.k(4.2), xf.k(3.4)), foot)
            for tx, ty in ((12, 2), (9, 5), (-8, 3), (-6, 5)):
                cv.draw(Capsule(xf.p(fx + 2, fy), xf.p(fx + 2 + tx, fy + ty), xf.k(2.6), xf.k(1.9)), foot)

    chest = lambda x, y: np.clip((body_c.local(x, y)[0] - 2) / 20, 0, 1) * 0.75
    cv.draw(polygon([bp(*p) for p in BODY], 14), feather(GREEN, ((LIGHT, chest), (DARK, scallops(body_c, 0.1)))))
    if flap is None:
        primaries = lambda x, y: np.clip((body_c.local(x, y)[1] - 40) / 10, 0, 1) * 0.95
        speculum = lambda x, y: 0.85 * (np.abs(body_c.local(x, y)[1] - 30) < 4) * (body_c.local(x, y)[0] > -8)
        cv.draw(polygon([bp(*p) for p in FOLDED], 6),
                feather(DARK, ((BLUE, primaries), (RED, speculum), ("#1f6e2a", scallops(body_c, 0.4)))))
    else:
        flap_wing(cv, xf, shoulder, flap, 104)

    def face(x, y):
        lx, ly = head_c.local(x, y)
        return np.clip(1.6 - np.hypot((lx - 6) / 18, (ly - 8) / 13) * 1.6, 0, 1)

    def crown(x, y):
        lx, ly = head_c.local(x, y)
        return np.clip((-ly - 12) / 6, 0, 1) * np.clip((lx + 6) / 8, 0, 1)

    cv.draw(Ellipsoid(hp(0, 0), xf.r(31, 29), rot=head_rot), feather(GREEN, ((YELLOW, face), (RED, crown))))
    if gape > 0:
        cv.draw(Ellipsoid(hp(32, 14), xf.r(8, 7), rot=head_rot), Mat("#3a1414", spec=0.3, cast=0))
    cv.draw(Ellipsoid(hp(30, 16 + 5 * gape), xf.r(10, 6.5), rot=head_rot), Mat(BEAK, spec=0.5, shine=40, cast=0.15))
    tip = lambda x, y: np.clip((head_c.local(x, y)[1] - 6) / 14, 0, 1) * 0.7
    cv.draw(polygon([hp(*p) for p in BEAK_UP], 3), Mat(BEAK, layers=((BEAK_TIP, tip),), spec=0.6, shine=40, cast=0.2))
    cv.draw(Ellipsoid(hp(22, -9), xf.r(1.6, 1.3)), Mat("#4a4038", cast=0))
    if state != "sleep":
        cv.draw(Ellipsoid(hp(10, -6), xf.r(8.6, 8.6)), Mat("#f1efe6", spec=0.1, ambient=0.6, cast=0.1))
    eye(cv, xf, head.p(10, -6), (6, 6.4), dict(m, closed=state == "sleep"), iris=IRIS, pupil_r=(4.6, 5), lid="#2a2a20",
        ring=1.06, glow_k=0.3)

    ground = None if state == "walk" else shadow(m, bx + 4, 46, 6, 0.28)
    return finish(cv.image(), OUTLINE, ground)
