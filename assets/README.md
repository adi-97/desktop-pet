# Pet art

The frames in this folder are rendered by `tools/render_sprites.py`. To change a pet's
look or animation, edit that script and run it again:

```
pip install -r tools/requirements.txt
python tools/render_sprites.py                  # all pets, treats and effects
python tools/render_sprites.py goldfish         # just one pet
python tools/render_sounds.py                   # bark, meow and bubble sounds
```

You can drop real recordings in as `sound1.wav`, `sound2.wav` and so on to replace the synthesized ones.

To use your own art instead, replace a pet's frames with PNG or GIF files:

```
assets/<pet>/
  idle/     000.png, 001.png, ...   (standing / breathing loop)
  walk/     000.png, ...            (walking or swimming, facing right)
  action/   000.png, ...            (bark / meow / blub and jump; also used for alerts)
  sleep/    000.png, ...            (optional: first idle frame if missing)
  eat/      000.png, ...            (head down chewing; falls back to action)
  eat1.wav, eat2.wav, ...           (chomp played on each bite)
  sound1.wav, sound2.wav, ...       (one is picked at random each time; made by tools/render_sounds.py)
treats/  bone.png, bone_1.png, bone_2.png ...   (whole -> almost gone; any number of stages, fish has 6)
fx/      heart.png, z.png, bubble.png, crumb_bone.png, crumb_fish.png
```

- Frames play in file-name order. Instead of a folder, you can use one animated GIF per state,
  for example `idle.gif`.
- Draw every frame facing right; the app mirrors them when the pet turns left.
- Use square canvases with the feet touching the bottom edge. The rendered frames are 256×256
  and get scaled to the chosen size.
- Full alpha transparency is supported, including soft edges and shadows.

Rebuild the app after changing art (`packaging/windows/build.bat` or `packaging/linux/build.sh`), because the assets are bundled inside it.
