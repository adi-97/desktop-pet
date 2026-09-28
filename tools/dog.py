import math

from engine import GROUND, Canvas, Capsule, Ellipsoid, Head, Mat, Xf, eye, finish, leg, motion, spots_fn


def dalmatian(state, t):
    cv = Canvas()
    m = motion(state, t)
    white, black = "#f8f6f1", "#262424"
    if state == "sleep":
        return dalmatian_sleep(cv, m, white, black)
    xf = Xf(m["sx"], m["sy"], m["lift"])
    eating = m.get("eat", False)
    b = 3.0 if eating else m["bob"]
    hd = Head(190, 190 + m["nod"], 0.72 + 0.03 * m["jaw"]) if eating else Head(182, 116 + b + m["head"])
    spots = [(*xf.p(x, y + b), xf.k(r), q) for x, y, r, q in
             ((98, 158, 9, 0.85), (126, 184, 7, 1.0), (142, 155, 6, 0.9), (80, 176, 7, 1.1), (112, 196, 5, 1.0),
              (154, 186, 5, 1.0), (66, 162, 5, 1.0))]
    head_spots = [(*xf.p(*hd.p(x, y)), xf.k(r), q) for x, y, r, q in ((-14, -22, 6, 0.9), (24, 12, 3.5, 1.0), (4, 26, 4, 1.0))]
    leg_spots = [(*xf.p(x, y), xf.k(4.5), 1.0) for x, y in ((158, 212), (90, 222), (168, 230))]
    fur = Mat(white, layers=((black, spots_fn(spots + leg_spots)),), spec=0.08, shine=12)
    far = fur.but(color="#dcd9d2", layers=((black, spots_fn(leg_spots)),))
    head_fur = fur.but(layers=((black, spots_fn(head_spots)),))
    ear = Mat("#2c2a2a", spec=0.12, shine=14)
    paw = Mat(white, spec=0.06)

    tail = m["tail"]
    a1 = -2.25 + tail
    p0 = (66, 160 + b)
    p1 = (p0[0] + 24 * math.cos(a1), p0[1] + 24 * math.sin(a1))
    p2 = (p1[0] + 20 * math.cos(a1 + 0.45), p1[1] + 20 * math.sin(a1 + 0.45))
    cv.draw(Capsule(xf.p(*p0), xf.p(*p1), xf.k(8.5), xf.k(6.5)), fur)
    cv.draw(Capsule(xf.p(*p1), xf.p(*p2), xf.k(6.5), xf.k(4.2)), fur.but(layers=()))

    leg(cv, xf, (106, 186), 0, m, far, paw.but(color="#dcd9d2"))
    leg(cv, xf, (172, 184), math.pi, m, far, paw.but(color="#dcd9d2"))
    cv.draw(Ellipsoid(xf.p(84, 174 + b), xf.r(34, 33)), fur)
    cv.draw(Ellipsoid(xf.p(122, 172 + b), xf.r(58, 36)), fur)
    cv.draw(Ellipsoid(xf.p(158, 168 + b), xf.r(32, 35)), fur)
    leg(cv, xf, (92, 188), math.pi, m, fur, paw)
    leg(cv, xf, (158, 188), 0, m, fur, paw)

    collar = Mat("#d8342c", spec=0.35, shine=30)
    tag = Mat("#f4c430", spec=0.9, shine=60, cast=0.15)
    if eating:
        neck_a, neck_b = (158, 152 + b), hd.p(-6, -4)
        cv.draw(Capsule(xf.p(*neck_a), xf.p(*neck_b), xf.k(27), xf.k(24)), fur.but(layers=()))
        cv.draw(Ellipsoid(xf.p(*hd.p(23, -34)), xf.r(12, 21), rot=-0.45 + hd.angle), ear)
        angle = math.atan2(neck_b[1] - neck_a[1], neck_b[0] - neck_a[0])
        cx, cy = neck_a[0] + 0.35 * (neck_b[0] - neck_a[0]), neck_a[1] + 0.35 * (neck_b[1] - neck_a[1])
        cv.draw(Ellipsoid(xf.p(cx, cy), xf.r(9, 29), rot=angle), collar)
        cv.draw(Ellipsoid(xf.p(cx - 4, cy + 24), xf.r(6.5, 6.5)), tag)
    else:
        cv.draw(Ellipsoid(xf.p(*hd.p(23, -34)), xf.r(12, 21), rot=-0.45), ear)
        cv.draw(Ellipsoid(xf.p(160, 150 + b), xf.r(9, 30), rot=0.4), collar)
        cv.draw(Ellipsoid(xf.p(166, 178 + b), xf.r(6.5, 6.5)), tag)
    cv.draw(Ellipsoid(xf.p(*hd.p(0, 0)), xf.r(47, 43), rot=hd.angle), head_fur)
    cv.draw(Ellipsoid(xf.p(*hd.p(-24, 4)), xf.r(15, 31), rot=0.28 + hd.angle + 0.06 * math.sin(m["phase"] * 2)), ear)
    eye(cv, xf, hd.p(39, -12), (5.2, 7.5), m)
    cv.draw(Ellipsoid(xf.p(*hd.p(35, 15)), xf.r(25, 18), rot=hd.angle), head_fur.but(cast=0.3))
    jaw = m.get("jaw", 1.0 if m["mouth"] else 0.0)
    if jaw > 0.12:
        cv.draw(Ellipsoid(xf.p(*hd.p(40, 30 + 2 * jaw)), xf.r(15, 4 + 5 * jaw), rot=hd.angle), Mat("#5a1a1a", spec=0.3, cast=0.1))
        cv.draw(Ellipsoid(xf.p(*hd.p(42, 34 + 2 * jaw)), xf.r(9, 3 + 3 * jaw), rot=hd.angle), Mat("#f07f93", spec=0.5, shine=30, cast=0))
    cv.draw(Ellipsoid(xf.p(*hd.p(56, 7)), xf.r(9, 7.5), rot=hd.angle), Mat("#1b1b1b", spec=0.9, shine=60, cast=0.2))
    eye(cv, xf, hd.p(11, -8), (6.8, 9.2), m)
    return finish(cv.image(), ("#2e2e2e", 0.55), (128, GROUND + 1, 80 * (1 - 0.35 * m["tuck"]), 9, 0.3 * (1 - 0.5 * m["tuck"])))


def dalmatian_sleep(cv, m, white, black):
    br = 1.6 * m["breath"]
    spots = [(x, y, r, 1.0) for x, y, r in ((96, 206, 8), (124, 222, 6), (146, 200, 6), (70, 214, 6), (110, 236, 4))]
    fur = Mat(white, layers=((black, spots_fn(spots)),), spec=0.08, shine=12)
    ear = Mat("#2c2a2a", spec=0.12)
    cv.draw(Capsule((44, 232), (100, 242), 8, 5), fur)
    cv.draw(Ellipsoid((78, 216 - br / 2), (38, 30 + br / 2)), fur)
    cv.draw(Ellipsoid((122, 214 - br / 2), (62, 30 + br / 2)), fur)
    cv.draw(Ellipsoid((178, 202), (44, 38)), fur.but(layers=((black, spots_fn([(170, 184, 6, 1.0)])),)))
    cv.draw(Ellipsoid((152, 208), (14, 28), rot=0.5), ear)
    cv.draw(Ellipsoid((212, 216), (24, 16)), fur.but(layers=(), cast=0.3))
    cv.draw(Ellipsoid((232, 210), (8.5, 7)), Mat("#1b1b1b", spec=0.9, shine=60))
    eye(cv, Xf(), (190, 198), (7, 9), dict(m, closed=True))
    for x in (196, 222):
        cv.draw(Ellipsoid((x, 238), (15, 8.5)), fur.but(layers=()))
    return finish(cv.image(), ("#2e2e2e", 0.55), (138, GROUND + 1, 104, 9, 0.3))
