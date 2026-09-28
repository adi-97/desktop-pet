import shutil
import sys
from pathlib import Path

from dog import dalmatian
from effects import fx
from engine import FRAMES
from cat import orange_cat
from fish import goldfish
from treats import STAGES, crumb, treat_stages

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PETS = {"dalmatian": dalmatian, "orange_cat": orange_cat, "goldfish": goldfish}


def render_pet(folder, render):
    for state, count in FRAMES.items():
        out = ASSETS / folder / state
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        for i in range(count):
            render(state, i / count).save(out / f"{i:03d}.png", optimize=True)
        print(f"{folder}/{state}: {count} frames")


def render_extras():
    (ASSETS / "treats").mkdir(parents=True, exist_ok=True)
    (ASSETS / "fx").mkdir(parents=True, exist_ok=True)
    for kind in STAGES:
        for old in (ASSETS / "treats").glob(f"{kind}_*.png"):
            old.unlink()
        for stage, image in enumerate(treat_stages(kind)):
            image.save(ASSETS / "treats" / (f"{kind}.png" if stage == 0 else f"{kind}_{stage}.png"), optimize=True)
    for kind in ("bone", "fish"):
        crumb(kind).save(ASSETS / "fx" / f"crumb_{kind}.png", optimize=True)
    for kind in ("heart", "bubble", "z"):
        fx(kind).save(ASSETS / "fx" / f"{kind}.png", optimize=True)
    print("treats and fx done")


def main(only=None):
    for folder, render in PETS.items():
        if not only or folder in only:
            render_pet(folder, render)
    render_extras()


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
