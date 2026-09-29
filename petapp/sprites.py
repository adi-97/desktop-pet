from PIL import Image, ImageOps, ImageSequence

from .config import DISPLAY_SIZES, resource_path
from .log import log_error
from .platforms import Bitmap

MAX_SIDE, MAX_FILE_BYTES = 2048, 8 * 1024 * 1024
FALLBACK = {"walk": "idle", "action": "idle", "sleep": "idle", "eat": "action"}


def open_image(path):
    if path.stat().st_size > MAX_FILE_BYTES:
        raise OSError(f"{path.name} is larger than {MAX_FILE_BYTES} bytes")
    image = Image.open(path, formats=("PNG", "GIF"))
    if max(image.size) > MAX_SIDE:
        image.close()
        raise OSError(f"{path.name} is larger than {MAX_SIDE}px")
    return image


def read_frames(folder, state):
    paths = sorted(p for p in (folder / state).glob("*.*") if p.suffix.lower() in (".png", ".gif")) if (folder / state).is_dir() else []
    paths = paths or [p for p in [folder / f"{state}.gif"] if p.is_file()]
    images = []
    for path in paths:
        try:
            with open_image(path) as image:
                images += [f.convert("RGBA") for _, f in zip(range(240), ImageSequence.Iterator(image))]
        except (OSError, Image.DecompressionBombError) as e:
            log_error(f"Could not load {path}: {e}")
    return images


def scale(image, factor):
    size = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    return image if abs(factor - 1) < 0.01 else image.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")


class Frame:
    def __init__(self, image):
        self.image, (self.width, self.height), self._bitmap = image, image.size, None

    @property
    def bitmap(self):
        if self._bitmap is None:
            self._bitmap = Bitmap(self.width, self.height, self.image.tobytes("raw", "BGRa"))
        return self._bitmap

    def free(self):
        if self._bitmap:
            self._bitmap.free()
            self._bitmap = None


class SpriteSet:
    def __init__(self, frames):
        self.frames = frames
        idle = frames["idle"][1]
        self.width, self.height = idle[0].width, idle[0].height
        boxes = [b for b in (f.image.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox() for f in idle) if b]
        boxes = boxes or [(0, 0, self.width, self.height)]
        self.box = tuple(f(b[i] for b in boxes) for i, f in enumerate((min, min, max, max)))


class SpriteLibrary:
    def __init__(self, dpi_scale):
        self.dpi_scale, self._cache = dpi_scale, {}

    def pixels(self, size):
        return round(DISPLAY_SIZES[size] * self.dpi_scale)

    def _cached(self, key, build):
        if key not in self._cache:
            self._cache[key] = build()
        return self._cache[key]

    def pet(self, spec, size):
        return self._cached((spec.folder, size), lambda: self._load_pet(spec.folder, self.pixels(size)))

    def image(self, name, size, fraction):
        def build():
            with open_image(resource_path(f"assets/{name}.png")) as source:
                image = source.convert("RGBA")
            return Frame(scale(image, self.pixels(size) * fraction / image.width))
        return self._cached((name, size, round(fraction, 2)), build)

    def treat_frames(self, kind, size, fraction):
        frames = [self.image(f"treats/{kind}", size, fraction)]
        while len(frames) < 12 and resource_path(f"assets/treats/{kind}_{len(frames)}.png").is_file():
            frames.append(self.image(f"treats/{kind}_{len(frames)}", size, fraction))
        return frames

    def _load_pet(self, folder_name, target):
        folder = resource_path("assets") / folder_name
        raw = {state: read_frames(folder, state) for state in ("idle",) + tuple(FALLBACK)}
        for state, fallback in FALLBACK.items():
            raw[state] = raw[state] or raw[fallback]
        if not raw["idle"]:
            raise FileNotFoundError(f"No sprite frames found in {folder}")
        factor = target / max(raw["idle"][0].size)
        sets = {}
        for state, images in raw.items():
            right = [Frame(scale(image, factor)) for image in (images if state != "sleep" or images is not raw["idle"] else images[:1])]
            sets[state] = {1: right, -1: [Frame(ImageOps.mirror(f.image)) for f in right]}
        return SpriteSet(sets)
