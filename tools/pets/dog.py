import math

import numpy as np

from engine import GROUND, Canvas, Capsule, Ellipsoid, Head, Mat, Xf, eye, finish, leg, motion, plush, shadow, spots_fn

GAIT = (((106, 186), math.pi, -1), ((172, 184), 1.5 * math.pi, 1), ((92, 188), 0.0, -1), ((158, 188), 0.5 * math.pi, 1))
WHITE, BLACK, SHADE, EAR = "#f7f4ee", "#2a2725", "#d9d4cb", "#34302d"
IRIS, NOSE, TOES, OUTLINE = "#6b3a1a", "#1d1b1a", "#b9b1a5", ("#57504a", 0.32)
_rng = np.random.default_rng(4)
BODY_SPOTS = list(zip(_rng.uniform(48, 186, 34), _rng.uniform(140, 204, 34), _rng.uniform(2.4, 5.6, 34), _rng.uniform(0.8, 1.15, 34)))
HEAD_SPOTS = ((-22, -26, 5.5, 0.9), (-6, -36, 3.2, 1.0), (-30, -4, 4, 1.1), (30, 8, 1.4, 1.0), (36, 14, 1.3, 1.0),
              (27, 15, 1.2, 1.0), (40, 6, 1.1, 1.0))
SLEEP_SPOTS = list(zip(_rng.uniform(50, 180, 30), _rng.uniform(190, 236, 30), _rng.uniform(2.2, 6, 30), _rng.uniform(0.8, 1.2, 30)))


def ear_pose(hd, swing):
    ox, oy = -8, 30
    c, s = math.cos(swing), math.sin(swing)
    return hd.p(-20 + ox * c - oy * s, -26 + ox * s + oy * c), 0.26 + hd.angle + swing


def muzzle(cv, xf, hd, fur, jaw):
    hp = lambda dx, dy: xf.p(*hd.p(dx, dy))
    cv.draw(Ellipsoid(hp(30, 24), xf.r(17, 11), rot=hd.angle), fur.but(cast=0.25))
    if jaw > 0.12:
        cv.draw(Ellipsoid(hp(44, 30 + 2 * jaw), xf.r(14, 4 + 5 * jaw), rot=hd.angle), Mat("#5a1a1a", spec=0.3, cast=0.1))
        cv.draw(Ellipsoid(hp(46, 34 + 2 * jaw), xf.r(9, 3 + 3 * jaw), rot=hd.angle), Mat("#f07f93", spec=0.5, shine=30, cast=0))
    cv.draw(Ellipsoid(hp(40, 15), xf.r(25, 16), rot=hd.angle - 0.05), fur.but(cast=0.3))
    cv.draw(Capsule(hp(44, 25), hp(54, 22), xf.k(0.9), xf.k(0.7)), Mat("#6b605a", cast=0, ambient=0.8))
    cv.draw(Ellipsoid(hp(59, 6), xf.r(10, 7.5), rot=hd.angle), Mat(NOSE, spec=0.75, shine=45, cast=0.2))
    cv.draw(Ellipsoid(hp(63, 8), xf.r(2.6, 1.8), rot=hd.angle), Mat("#050505", spec=0, cast=0))
    cv.draw(Capsule(hp(60, 9), hp(59, 18), xf.k(0.8)), Mat("#3a3330", cast=0))


def dalmatian(state, t):
    cv = Canvas()
    m = motion(state, t)
    if state == "sleep":
        return dalmatian_sleep(cv, m)
    xf = Xf(m["sx"], m["sy"], m["lift"])
    eating = m.get("eat", False)
    b = 3.0 if eating else m["bob"]
    hd = Head(190, 188 + m["nod"], 0.72 + 0.03 * m["jaw"]) if eating else Head(182, 112 + b + m["head"], m["tilt"])
    spots = [(*xf.p(x, y + b), xf.k(r), q) for x, y, r, q in BODY_SPOTS]
    head_spots = [(*xf.p(*hd.p(x, y)), xf.k(r), q) for x, y, r, q in HEAD_SPOTS]
    fur = plush(WHITE, ((BLACK, spots_fn(spots, 0.1)),))
    plain = plush(WHITE)
    far = plush(SHADE, ((BLACK, spots_fn(spots, 0.1)),))
    head_fur = plush(WHITE, ((BLACK, spots_fn(head_spots, 0.2)),))
    ear = plush(EAR, fur=0.6)
    paw, far_paw = plush(WHITE, fur=0.5), plush(SHADE, fur=0.5)

    a1 = -2.25 + m["tail"]
    p0 = (66, 160 + b)
    p1 = (p0[0] + 24 * math.cos(a1), p0[1] + 24 * math.sin(a1))
    p2 = (p1[0] + 20 * math.cos(a1 + 0.45), p1[1] + 20 * math.sin(a1 + 0.45))
    cv.draw(Capsule(xf.p(*p0), xf.p(*p1), xf.k(8.5), xf.k(6.5)), fur)
    cv.draw(Capsule(xf.p(*p1), xf.p(*p2), xf.k(6.5), xf.k(3.6)), plain)

    for hip, phase, knee in GAIT[:2]:
        leg(cv, xf, hip, phase, m, far, far_paw, knee=knee, toes=TOES)
    cv.draw(Ellipsoid(xf.p(84, 174 + b), xf.r(34, 33)), fur)
    cv.draw(Ellipsoid(xf.p(122, 172 + b), xf.r(58, 36)), fur)
    cv.draw(Ellipsoid(xf.p(158, 168 + b), xf.r(32, 35)), fur)
    for hip, phase, knee in GAIT[2:]:
        leg(cv, xf, hip, phase, m, fur, paw, knee=knee, toes=TOES)

    collar = Mat("#d8342c", spec=0.2, shine=20)
    tag = Mat("#f4c430", spec=0.9, shine=60, cast=0.15)
    far_ear = (xf.p(*hd.p(26, -38)), xf.r(12, 21), -0.45 + hd.angle + 0.6 * m["ear"])
    if eating:
        neck_a, neck_b = (158, 152 + b), hd.p(-6, -4)
        cv.draw(Capsule(xf.p(*neck_a), xf.p(*neck_b), xf.k(27), xf.k(25)), plain)
        cv.draw(Ellipsoid(far_ear[0], far_ear[1], rot=far_ear[2]), ear)
        angle = math.atan2(neck_b[1] - neck_a[1], neck_b[0] - neck_a[0])
        cx, cy = neck_a[0] + 0.35 * (neck_b[0] - neck_a[0]), neck_a[1] + 0.35 * (neck_b[1] - neck_a[1])
        cv.draw(Ellipsoid(xf.p(cx, cy), xf.r(9, 29), rot=angle), collar)
        cv.draw(Ellipsoid(xf.p(cx - 4, cy + 24), xf.r(6.5, 6.5)), tag)
    else:
        cv.draw(Ellipsoid(far_ear[0], far_ear[1], rot=far_ear[2]), ear)
        cv.draw(Ellipsoid(xf.p(160, 150 + b), xf.r(9, 30), rot=0.4), collar)
        cv.draw(Ellipsoid(xf.p(166, 178 + b + 1.5 * math.sin(m["phase"] * 2 - 1)), xf.r(6.5, 6.5)), tag)
    cv.draw(Ellipsoid(xf.p(*hd.p(0, 0)), xf.r(51, 47), rot=hd.angle), head_fur)
    ear_c, ear_rot = ear_pose(hd, m["ear"] + 0.05 * math.sin(m["phase"] * 2))
    cv.draw(Ellipsoid(xf.p(*ear_c), xf.r(16, 32), rot=ear_rot), ear)
    eye(cv, xf, hd.p(42, -12), (6.4, 8.4), m, iris=IRIS, pupil_r=(3.8, 5))
    muzzle(cv, xf, hd, head_fur, m.get("jaw", 1.0 if m["mouth"] else 0.0))
    eye(cv, xf, hd.p(14, -8), (9, 10.5), m, iris=IRIS, pupil_r=(5.2, 6.4))
    return finish(cv.image(), OUTLINE, shadow(m, 128, 80, 9, 0.3))


def dalmatian_sleep(cv, m):
    br = 1.6 * m["breath"]
    fur = plush(WHITE, ((BLACK, spots_fn(SLEEP_SPOTS, 0.1)),))
    plain = plush(WHITE)
    cv.draw(Capsule((44, 232 - 40 * m["tail"]), (100, 242), 8, 5), fur)
    cv.draw(Ellipsoid((78, 216 - br / 2), (38, 30 + br / 2)), fur)
    cv.draw(Ellipsoid((122, 214 - br / 2), (62, 30 + br / 2)), fur)
    cv.draw(Ellipsoid((180, 200), (47, 41)), plush(WHITE, ((BLACK, spots_fn([(166, 180, 5.5, 0.9), (184, 172, 3, 1.0)], 0.2)),)))
    cv.draw(Ellipsoid((152 - 4 * m["ear"], 208 - 6 * m["ear"]), (15, 29), rot=0.5 + m["ear"]), plush(EAR, fur=0.6))
    cv.draw(Ellipsoid((214, 217), (24, 15)), plain.but(cast=0.3))
    cv.draw(Ellipsoid((234, 210), (9, 7)), Mat(NOSE, spec=0.75, shine=45))
    eye(cv, Xf(), (192, 198), (8, 9), dict(m, closed=True))
    for x in (196, 222):
        cv.draw(Ellipsoid((x, 238), (15, 8.5)), plush(WHITE, fur=0.5))
    return finish(cv.image(), OUTLINE, (138, GROUND + 1, 104, 9, 0.3))
