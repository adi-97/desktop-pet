import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engine import SS, Canvas, Ellipsoid, Mat, Puffy, finish


def fx(kind):
    cv = Canvas(48, 48)
    if kind == "heart":
        def inside(x, y):
            u, v = (x - 24) / 17, -(y - 25) / 17
            return (u * u + v * v - 0.3) ** 3 - u * u * v ** 3 < 0
        cv.draw(Puffy(inside, (4, 4, 44, 44), 4), Mat("#ff3b5c", spec=0.8, shine=40, ambient=0.5, rim=0.3, cast=0))
        return finish(cv.image(), ("#7a0f24", 0.4))
    if kind == "bubble":
        def shell(x, y):
            return 0.12 + 0.88 * np.clip(np.hypot(x - 24, y - 24) / 19, 0, 1) ** 5

        cv.draw(Ellipsoid((24, 24), (19, 19)), Mat("#d8f0ff", ambient=0.95, spec=0.9, shine=60, rim=0.8, cast=0, fade=shell))
        glint = Mat("#ffffff", ambient=1, wrap=0, spec=0, rim=0, cast=0)
        cv.draw(Ellipsoid((16, 15), (6, 3.6), rot=-0.7), glint.but(opacity=0.95))
        cv.draw(Ellipsoid((32, 33), (3, 1.8), rot=-0.7), glint.but(opacity=0.55))
        return cv.image()
    font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf"), 34 * SS)
    mask_img = Image.new("L", (48 * SS, 48 * SS), 0)
    ImageDraw.Draw(mask_img).text((24 * SS, 24 * SS), "Z", font=font, fill=255, anchor="mm")
    mask = np.asarray(mask_img) > 127

    def inside(x, y):
        return mask[(y * SS).astype(int).clip(0, 48 * SS - 1), (x * SS).astype(int).clip(0, 48 * SS - 1)]

    cv.draw(Puffy(inside, (0, 0, 48, 48), 2.5), Mat("#9ecbff", spec=0.6, shine=30, ambient=0.6, cast=0))
    return finish(cv.image(), ("#2b4a73", 0.5))
