import shutil
import sys
import wave
from pathlib import Path

from PIL import Image, PngImagePlugin

import sounds
from engine import FRAMES
from pets import PETS
from props import FX, TREATS, crumb, fx, treat_stages

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def save_strip(images, path):
    w, h = images[0].size
    strip = Image.new("RGBA", (w * len(images), h))
    for i, image in enumerate(images):
        strip.paste(image, (i * w, 0))
    info = PngImagePlugin.PngInfo()
    info.add_text("frames", str(len(images)))
    path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(path, optimize=True, pnginfo=info)


def save_wav(path, pcm):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sounds.RATE)
        f.writeframes(pcm.tobytes())


def render_pet(folder):
    out = ASSETS / folder
    shutil.rmtree(out, ignore_errors=True)
    for state, count in FRAMES.items():
        save_strip([PETS[folder](state, i / count) for i in range(count)], out / f"{state}.png")
    for kind, clips in sounds.clips(folder).items():
        for i, pcm in enumerate(clips, start=1):
            save_wav(out / f"{kind}{i}.wav", pcm)
    print(f"{folder}: {sum(FRAMES.values())} frames, sounds")


def render_props():
    for name in ("treats", "fx"):
        shutil.rmtree(ASSETS / name, ignore_errors=True)
        (ASSETS / name).mkdir(parents=True)
    for kind, (_, _, _, crumbs) in TREATS.items():
        save_strip(treat_stages(kind), ASSETS / "treats" / f"{kind}.png")
        if crumbs:
            crumb(kind).save(ASSETS / "fx" / f"crumb_{kind}.png", optimize=True)
    for kind in FX:
        fx(kind).save(ASSETS / "fx" / f"{kind}.png", optimize=True)
    print("treats and fx")


def main(only):
    for folder in PETS:
        if not only or folder in only:
            render_pet(folder)
    render_props()


if __name__ == "__main__":
    main(set(sys.argv[1:]))
