import math
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 256
SS = 3
GROUND = 246
FRAMES = {"idle": 24, "walk": 16, "action": 14, "sleep": 12, "eat": 12}


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


LIGHT = unit([-0.45, -0.7, 0.75])
HALF = unit(LIGHT + np.array([0.0, 0.0, 1.0]))


def rgb(hex_color):
    return np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], float) / 255


@dataclass(frozen=True)
class Mat:
    color: str
    layers: tuple = ()
    spec: float = 0.1
    shine: float = 16.0
    ambient: float = 0.42
    wrap: float = 0.45
    rim: float = 0.16
    cast: float = 0.22
    opacity: float = 1.0
    fade: object = None
    cuts: tuple = ()
    cut_rim: str = None
    rim_width: float = 3.0
    fur: float = 0.0

    def but(self, **kw):
        return replace(self, **kw)


def strands(size=SIZE * SS, length=9, seed=5):
    rng = np.random.default_rng(seed)
    raw = rng.random((size, size))
    streak = sum(np.roll(raw, (s, s // 3), axis=(0, 1)) for s in range(length)) / length
    return np.clip(0.5 + (streak - 0.5) * 3.2, 0, 1)


NOISE = strands()


def plush(color, layers=(), fur=1.0, **kw):
    return Mat(color, layers=layers, fur=fur, **{**dict(spec=0.035, shine=8, ambient=0.46, wrap=0.62, rim=0.2), **kw})


def normalize(nx, ny, nz):
    length = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-9
    return np.stack([nx / length, ny / length, nz / length], axis=-1)


class Ellipsoid:
    def __init__(self, c, r, rot=0.0, depth=None):
        self.cx, self.cy = c
        self.rx, self.ry = max(r[0], 0.5), max(r[1], 0.5)
        self.rot = rot
        self.rz = depth or min(self.rx, self.ry)

    def box(self):
        big = max(self.rx, self.ry)
        return self.cx - big, self.cy - big, self.cx + big, self.cy + big

    def eval(self, x, y):
        c, s = math.cos(self.rot), math.sin(self.rot)
        dx, dy = x - self.cx, y - self.cy
        u = (dx * c + dy * s) / self.rx
        v = (-dx * s + dy * c) / self.ry
        d2 = u * u + v * v
        w = np.sqrt(np.clip(1 - d2, 0, 1))
        nu, nv = u / self.rx, v / self.ry
        return d2 < 1, normalize(nu * c - nv * s, nu * s + nv * c, w / self.rz)


class Capsule:
    def __init__(self, a, b, ra, rb=None):
        self.a, self.b = np.asarray(a, float), np.asarray(b, float)
        self.ra, self.rb = ra, ra if rb is None else rb

    def box(self):
        big = max(self.ra, self.rb)
        lo, hi = np.minimum(self.a, self.b) - big, np.maximum(self.a, self.b) + big
        return lo[0], lo[1], hi[0], hi[1]

    def eval(self, x, y):
        ex, ey = self.b - self.a
        length2 = ex * ex + ey * ey or 1e-9
        t = np.clip(((x - self.a[0]) * ex + (y - self.a[1]) * ey) / length2, 0, 1)
        px, py = x - (self.a[0] + t * ex), y - (self.a[1] + t * ey)
        r = self.ra + t * (self.rb - self.ra)
        q = np.sqrt(px * px + py * py) / r
        return q < 1, normalize(px / r, py / r, np.sqrt(np.clip(1 - q * q, 0, 1)))


class Puffy:
    def __init__(self, inside, box, bevel):
        self.inside, self.bounds, self.bevel = inside, box, bevel

    def box(self):
        return self.bounds

    def eval(self, x, y):
        mask = self.inside(x, y)
        img = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(self.bevel * SS))
        h = np.asarray(img, float) / 255
        gy, gx = np.gradient(h)
        k = 2.4 * self.bevel * SS
        return mask, normalize(-gx * k, -gy * k, np.ones_like(h))


def polygon(points, bevel):
    pts = np.asarray(points, float)

    def inside(x, y):
        result = np.zeros(x.shape, bool)
        for (x1, y1), (x2, y2) in zip(np.roll(pts, 1, axis=0), pts):
            dy = y2 - y1 if abs(y2 - y1) > 1e-9 else 1e-9
            result ^= ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / dy + x1)
        return result

    lo, hi = pts.min(0), pts.max(0)
    return Puffy(inside, (lo[0], lo[1], hi[0], hi[1]), bevel)


class Loft:
    def __init__(self, tail_x, nose_x, height, center, depth=0.85):
        self.x0, self.x1 = tail_x, nose_x
        self.length = nose_x - tail_x
        self.height, self.center, self.depth = height, center, depth

    def u(self, x):
        return (self.x1 - x) / self.length

    def v(self, x, y):
        return (y - self.center(x)) / np.maximum(self.height(np.clip(self.u(x), 0, 1)), 1e-6)

    def box(self):
        xs = np.linspace(self.x0, self.x1, 64)
        h = self.height(np.clip(self.u(xs), 0, 1))
        yc = self.center(xs)
        return self.x0, float((yc - h).min()), self.x1, float((yc + h).max())

    def eval(self, x, y):
        eps = 0.5
        u = self.u(x)
        h = self.height(np.clip(u, 0, 1))
        dh = (self.height(np.clip(self.u(x + eps), 0, 1)) - self.height(np.clip(self.u(x - eps), 0, 1))) / (2 * eps)
        dyc = (self.center(x + eps) - self.center(x - eps)) / (2 * eps)
        v = (y - self.center(x)) / np.maximum(h, 1e-6)
        w = np.sqrt(np.clip(1 - v * v, 0, 1))
        mask = (u >= 0) & (u <= 1) & (np.abs(v) < 1) & (h > 0.3)
        return mask, normalize(-(v * dyc + dh), v, w / self.depth)


def shade(n, base, mat):
    diffuse = np.clip((n @ LIGHT + mat.wrap) / (1 + mat.wrap), 0, 1)
    light = mat.ambient + (1 - mat.ambient) * diffuse + 0.06 * np.clip(-n[..., 1], 0, 1)
    col = base * light[..., None]
    spec = np.clip(n @ HALF, 0, 1) ** mat.shine * mat.spec
    rim = (1 - np.clip(n[..., 2], 0, 1)) ** 3 * mat.rim
    return np.clip(col + spec[..., None] + rim[..., None] * np.array([0.85, 0.9, 1.0]), 0, 1)


def bite_edge(x, y, cuts):
    edge = np.full(x.shape, np.inf)
    for cx, cy, r in cuts:
        angle = np.arctan2(y - cy, x - cx)
        ragged = r + 1.1 * np.sin(angle * 11 + cx) + 0.6 * np.sin(angle * 23 + cy)
        edge = np.minimum(edge, np.hypot(x - cx, y - cy) - ragged)
    return edge


class Canvas:
    def __init__(self, w=SIZE, h=SIZE):
        self.w, self.h = w, h
        self.P = np.zeros((h * SS, w * SS, 3))
        self.A = np.zeros((h * SS, w * SS))

    def draw(self, shape, mat):
        margin = 14 if mat.cast else 1
        x0, y0, x1, y1 = shape.box()
        i0, i1 = max(0, int((x0 - margin) * SS)), min(self.w * SS, int(math.ceil((x1 + margin) * SS)))
        j0, j1 = max(0, int((y0 - margin) * SS)), min(self.h * SS, int(math.ceil((y1 + margin) * SS)))
        if i0 >= i1 or j0 >= j1:
            return
        x, y = np.meshgrid((np.arange(i0, i1) + 0.5) / SS, (np.arange(j0, j1) + 0.5) / SS)
        mask, n = shape.eval(x, y)
        edge = bite_edge(x, y, mat.cuts) if mat.cuts else None
        if edge is not None:
            mask = mask & (edge > 0)
        noise = NOISE[j0:j1, i0:i1] if mat.fur else None
        if mat.fur:
            mask = mask & (n[..., 2] > mat.fur * 0.32 * noise)
        if not mask.any():
            return
        sl = (slice(j0, j1), slice(i0, i1))
        if mat.cast:
            self._cast(sl, mask, mat.cast)
        base = np.broadcast_to(rgb(mat.color), x.shape + (3,)).copy()
        for color, fn in mat.layers:
            w = np.clip(np.asarray(fn(x, y), float), 0, 1)[..., None]
            base = base * (1 - w) + rgb(color) * w
        if mat.fur:
            base = base * (1 + mat.fur * 0.22 * (noise - 0.5))[..., None]
        if edge is not None and mat.cut_rim:
            w = np.clip(1 - edge / mat.rim_width, 0, 1)[..., None]
            base = base * (1 - w) + rgb(mat.cut_rim) * w
        op = mask * mat.opacity
        if mat.fade:
            op = op * np.clip(mat.fade(x, y), 0, 1)
        op = op[..., None]
        self.P[sl] = shade(n, base, mat) * op + self.P[sl] * (1 - op)
        self.A[sl] = op[..., 0] + self.A[sl] * (1 - op[..., 0])

    def _cast(self, sl, mask, strength):
        img = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4 * SS))
        blur = np.asarray(img, float) / 255
        ox, oy = 3 * SS, 5 * SS
        shifted = np.zeros_like(blur)
        shifted[oy:, ox:] = blur[:-oy, :-ox]
        self.P[sl] *= (1 - strength * shifted)[..., None]

    def image(self):
        p = self.P.reshape(self.h, SS, self.w, SS, 3).mean((1, 3))
        a = self.A.reshape(self.h, SS, self.w, SS).mean((1, 3))
        c = p / np.maximum(a, 1e-5)[..., None]
        rgba = np.dstack([np.clip(c, 0, 1), np.clip(a, 0, 1)])
        return Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")


def finish(char, outline=None, shadow=None):
    out = Image.new("RGBA", char.size, (0, 0, 0, 0))
    if shadow:
        cx, cy, rx, ry, alpha = shadow
        layer = Image.new("RGBA", char.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(25, 18, 12, int(255 * alpha)))
        out = Image.alpha_composite(out, layer.filter(ImageFilter.GaussianBlur(6)))
    if outline:
        color, strength = outline
        a = char.getchannel("A").filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(0.8))
        layer = Image.new("RGBA", char.size, tuple(int(v * 255) for v in rgb(color)) + (0,))
        layer.putalpha(a.point(lambda v: int(v * strength)))
        out = Image.alpha_composite(out, layer)
    return Image.alpha_composite(out, char)


class Xf:
    def __init__(self, sx=1.0, sy=1.0, lift=0.0, ax=128.0, ay=GROUND):
        self.sx, self.sy, self.lift, self.ax, self.ay = sx, sy, lift, ax, ay

    def p(self, x, y):
        return self.ax + (x - self.ax) * self.sx, self.ay + (y - self.ay) * self.sy - self.lift

    def r(self, rx, ry):
        return rx * self.sx, ry * self.sy

    def k(self, v):
        return v * (self.sx + self.sy) / 2

    def frame(self, f):
        return Head(*self.p(f.cx, f.cy), f.angle)


def spots_fn(spots, ragged=0.0):
    def fn(x, y):
        w = np.zeros(x.shape)
        for sx, sy, r, sq in spots:
            a = np.arctan2(y - sy, x - sx)
            rr = r * (1 + ragged * (0.6 * np.sin(3 * a + sx) + 0.4 * np.sin(5 * a + sy)))
            w = np.maximum(w, ((x - sx) / rr) ** 2 + ((y - sy) / (rr * sq)) ** 2 < 1)
        return w
    return fn


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def pulse(t, start, end):
    return math.sin(math.pi * ease((t - start) / (end - start))) if start <= t <= end else 0.0


def blink_at(t, count, frame):
    return {frame - 1: 0.55, frame: 1.0, frame + 1: 0.55}.get(round(t * count), 0.0)


def jump(t):
    if t < 0.18:
        return 0.0, 1 - 0.13 * ease(t / 0.18)
    if t < 0.78:
        u = (t - 0.18) / 0.6
        return math.sin(math.pi * u), 1 + 0.12 * abs(math.cos(math.pi * u))
    return 0.0, 1 - 0.15 * (1 - (t - 0.78) / 0.22) ** 1.6


def motion(state, t):
    tau = 2 * math.pi * t
    m = dict(bob=0.0, breath=math.sin(tau), tail=0.22 * math.sin(2 * tau), head=1.4 * math.sin(tau), tilt=0.0,
             ear=0.0, legs=None, mouth=0.0, blink=0.0, sx=1.0, sy=1.0, lift=0.0, tuck=0.0, phase=tau)
    if state == "idle":
        breath = math.sin(2 * tau)
        m.update(blink=blink_at(t, FRAMES["idle"], 19), sy=1 + 0.012 * breath, sx=1 - 0.006 * breath,
                 head=1.2 * math.sin(tau), tilt=-0.07 * pulse(t, 0.25, 0.7) + 0.04 * pulse(t, 0.72, 0.95),
                 tail=0.16 * math.sin(2 * tau) + 0.3 * pulse(t, 0.05, 0.22) * math.sin(6 * tau),
                 ear=0.3 * pulse(t, 0.55, 0.62) - 0.15 * pulse(t, 0.62, 0.7))
    elif state == "walk":
        m.update(bob=2.0 * math.cos(2 * tau), tail=0.3 * math.sin(tau) + 0.08 * math.sin(2 * tau),
                 head=1.2 * math.cos(2 * tau + 0.7), tilt=0.025 * math.sin(2 * tau), ear=0.14 * math.sin(2 * tau - 1.1),
                 legs=tau)
    elif state == "action":
        h, sy = jump(t)
        m.update(lift=36 * h, sy=sy, sx=1 / math.sqrt(sy), tail=0.55 * math.sin(4 * tau),
                 mouth=1.0 if 0.18 < t < 0.85 else 0.0, tuck=min(1.0, 1.8 * h), head=-2 * h, tilt=-0.08 * h,
                 ear=0.55 * h - 0.25 * pulse(t, 0.78, 1.0))
    elif state == "sleep":
        m.update(ear=0.25 * pulse(t, 0.5, 0.6), tail=0.12 * pulse(t, 0.7, 0.9))
    elif state == "eat":
        chew = math.sin(3 * tau)
        m.update(eat=True, jaw=max(0.0, chew), nod=2.5 * chew, tug=4.5 * max(0.0, -chew),
                 tail=0.45 * math.sin(2 * tau), head=0.0, ear=0.1 * chew)
    return m


class Head:
    def __init__(self, cx, cy, angle=0.0):
        self.cx, self.cy, self.angle = cx, cy, angle
        self.c, self.s = math.cos(angle), math.sin(angle)

    def p(self, dx, dy):
        return self.cx + dx * self.c - dy * self.s, self.cy + dx * self.s + dy * self.c

    def local(self, x, y):
        dx, dy = x - self.cx, y - self.cy
        return dx * self.c + dy * self.s, -dx * self.s + dy * self.c


def leg(cv, xf, hip, phase, m, mat, paw, radii=(12.5, 10.0), paw_r=(13.0, 8.5), reach=0.42, knee=1, toes=None):
    hx, hy = hip
    if m["legs"] is not None:
        angle = reach * math.sin(m["legs"] + phase)
        raised = max(0.0, math.cos(m["legs"] + phase)) ** 1.4
        foot_y = GROUND - 9 - 12 * raised
        foot_x = hx + (foot_y - hy) * math.tan(angle)
        bend = 2 + 9 * raised
    else:
        raised = m["tuck"]
        foot_y = GROUND - 9 - 22 * raised
        foot_x = hx - 7 * raised
        bend = 2 + 10 * raised
    hy += m["bob"]
    joint = ((hx + foot_x) / 2 + knee * bend, (hy + foot_y) / 2)
    mid = (radii[0] + radii[1]) / 2
    cv.draw(Capsule(xf.p(hx, hy), xf.p(*joint), xf.k(radii[0]), xf.k(mid)), mat)
    cv.draw(Capsule(xf.p(*joint), xf.p(foot_x, foot_y), xf.k(mid), xf.k(radii[1])), mat)
    cv.draw(Ellipsoid(xf.p(foot_x + 4, foot_y + 2), xf.r(*paw_r), rot=-knee * 0.45 * raised), paw)
    if toes and raised < 0.3:
        for dx in (paw_r[0] * 0.25, paw_r[0] * 0.6):
            cv.draw(Capsule(xf.p(foot_x + 4 + dx, foot_y + 2 + paw_r[1] * 0.1), xf.p(foot_x + 5 + dx, foot_y + 2 + paw_r[1] * 0.85),
                            xf.k(0.7), xf.k(0.5)), Mat(toes, cast=0, ambient=0.8))


def shadow(m, cx, rx, ry, alpha):
    fade = max(0.35, 1 - m["lift"] / 70)
    return cx, GROUND + 1, rx * fade, ry, alpha * fade


def eye(cv, xf, c, r, m, iris=None, pupil_r=None, lid="#2a1d18", cover=None, ring=1.14, glow_k=0.6):
    x, y = c
    if m["blink"] >= 0.99 or m.get("closed"):
        pts = [xf.p(x + r[0] * 1.1 * u, y + 2.5 * (1 - u * u)) for u in (-1, -0.5, 0, 0.5, 1)]
        for a, b in zip(pts, pts[1:]):
            cv.draw(Capsule(a, b, xf.k(1.6)), Mat(lid, cast=0))
        return
    ry = r[1] * (1 - 0.75 * m["blink"])
    cv.draw(Ellipsoid(xf.p(x, y + 0.4), xf.r(r[0] * ring, ry * (ring - 0.02) + 0.6)), Mat(lid, spec=0.1, cast=0.25))
    glossy = Mat("#0d0b0a", spec=0.9, shine=70, ambient=0.7, rim=0.05, cast=0)
    if iris:
        (cx, cy), (rx, rr) = xf.p(x, y), xf.r(r[0], ry)
        ring = lambda px, py: np.clip((np.hypot((px - cx) / rx, (py - cy) / rr) - 0.6) / 0.4, 0, 1) * 0.75
        glow = lambda px, py: np.clip(1 - np.hypot((px - cx - rx * 0.25) / rx, (py - cy - rr * 0.45) / rr) * 1.6, 0, 1) * glow_k
        cv.draw(Ellipsoid(xf.p(x, y), xf.r(r[0], ry)), Mat(iris, layers=(("#ffffff", glow), ("#1a120c", ring)),
                                                          spec=0.7, shine=50, ambient=0.62, cast=0))
        cv.draw(Ellipsoid(xf.p(x + r[0] * 0.12, y), xf.r(pupil_r[0], pupil_r[1] * (ry / r[1]))), glossy)
    else:
        cv.draw(Ellipsoid(xf.p(x, y), xf.r(r[0], ry)), glossy)
    if ry > 3:
        shine = Mat("#ffffff", ambient=1, wrap=0, rim=0, spec=0, cast=0)
        cv.draw(Ellipsoid(xf.p(x - r[0] * 0.32, y - ry * 0.38), xf.r(r[0] * 0.36, r[0] * 0.36)), shine)
        cv.draw(Ellipsoid(xf.p(x + r[0] * 0.34, y + ry * 0.36), xf.r(r[0] * 0.17, r[0] * 0.17)), shine.but(opacity=0.85))
    if cover:
        top, half_w, half_h = y - ry * 1.32, r[0] * 1.6, ry * 0.78
        cv.draw(Ellipsoid(xf.p(x, top), xf.r(half_w, half_h)), Mat(cover, spec=0.03, ambient=0.5, wrap=0.6, cast=0))
        pts = [xf.p(x + half_w * u, top + half_h * math.sqrt(max(0.0, 1 - u * u))) for u in (-0.62, -0.31, 0, 0.31, 0.62)]
        for a, b in zip(pts, pts[1:]):
            cv.draw(Capsule(a, b, xf.k(0.9)), Mat(lid, cast=0))
