from PIL import Image, ImageOps, ImageSequence

from .config import DISPLAY_SIZES, resource_path
from .log import log_error
from .platforms import Bitmap

MAX_SIDE, MAX_FILE_BYTES, MAX_FRAMES = 2048, 8 * 1024 * 1024, 240
FALLBACK = {"walk": "idle", "action": "idle", "sleep": "idle", "eat": "action"}


def strip_count(image):
    try:
        count = int(image.info.get("frames", 1))
    except (TypeError, ValueError):
        return 1
    return count if 1 <= count <= MAX_FRAMES and image.width % count == 0 else 1


def open_image(path):
    if path.stat().st_size > MAX_FILE_BYTES:
        raise OSError(f"{path.name} is larger than {MAX_FILE_BYTES} bytes")
    image = Image.open(path, formats=("PNG", "GIF"))
    if max(image.width // strip_count(image), image.height) > MAX_SIDE:
        image.close()
        raise OSError(f"{path.name} has frames larger than {MAX_SIDE}px")
    return image


def load_frames(path):
    with open_image(path) as image:
        if getattr(image, "n_frames", 1) > 1:
            return [f.convert("RGBA") for _, f in zip(range(MAX_FRAMES), ImageSequence.Iterator(image))]
        count, sheet = strip_count(image), image.convert("RGBA")
    w = sheet.width // count
    return [sheet.crop((i * w, 0, i * w + w, sheet.height)) for i in range(count)]


def read_frames(folder, state):
    for path in (folder / f"{state}.png", folder / f"{state}.gif"):
        if path.is_file():
            try:
                return load_frames(path)
            except (OSError, Image.DecompressionBombError) as e:
                log_error(f"Could not load {path}: {e}")
    return []


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

    def strip(self, name, size, fraction):
        def build():
            images = load_frames(resource_path(f"assets/{name}.png"))
            factor = self.pixels(size) * fraction / images[0].width
            return [Frame(scale(image, factor)) for image in images]
        return self._cached((name, size, round(fraction, 2)), build)

    def image(self, name, size, fraction):
        return self.strip(name, size, fraction)[0]

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
