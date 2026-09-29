# Desktop Pet on Linux

> **Status:** the Linux support has been written but not yet tested on a real Linux machine. If something goes wrong, please report it with your distro, your desktop environment, whether the session is Wayland or X11 (`echo $XDG_SESSION_TYPE`), and the terminal output.

## Requirements

- A graphical session running X11, or Wayland with XWayland (the default on GNOME and KDE Plasma).
- A compositor is recommended, for soft edges and shadows. GNOME and KDE have one built in. On lighter window managers (i3, Openbox and so on), run `picom`.
- These system packages (Debian/Ubuntu names; other distros use similar names):

```sh
sudo apt install python3 python3-pip python3-tk libx11-6 libxext6 pulseaudio-utils libnotify-bin
```

- `python3-tk` is Tkinter.
- `libx11-6` and `libxext6` draw the transparent pet window.
- `pulseaudio-utils` provides `paplay` for sound. `pw-play` (PipeWire) or `aplay` also work.
- `libnotify-bin` provides desktop notifications.

## Run from source

```sh
git clone <repo-url> pet-friends
cd pet-friends
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 desktop_pet.py
```

## Build a single binary

```sh
packaging/linux/build.sh
```

This creates `dist/DesktopPet`. Other people can run it without Python or the repo:

```sh
chmod +x DesktopPet
./DesktopPet
```

- Build on the oldest distro you want to support (for example Ubuntu 22.04). A binary built against a newer glibc won't start on older systems.
- The machine running the binary still needs the X11, sound and notification packages listed above. Most desktop installs already have them.

## Where things are kept

| What | Where |
|---|---|
| Settings, stats, pending reminders | `~/.config/DesktopPet/settings.json` |
| Error log | `~/.config/DesktopPet/error.log` |
| Single-instance lock | `~/.config/DesktopPet/instance.lock` |
| Start at login | `~/.config/autostart/DesktopPet.desktop` |

To reset the pet, exit it and delete `~/.config/DesktopPet`.

## How it differs from Windows

- **Transparency:** with a compositor, the pet uses a 32-bit ARGB window, giving the same soft edges and shadows as on Windows. Without one, it falls back to a hard-edged X11 shape, so edges look sharper and the ground shadow is cut off.
- **Staying on top:** the pet re-raises itself about once a second, except while the right-click menu is open.
- **Speech bubbles:** they fade out only when a compositor is running. Otherwise they just disappear.
- **Screen edges:** the pet uses the desktop's `_NET_WORKAREA`, which spans all monitors. With monitors of different sizes, the pet can wander into parts of the screen that don't exist.

## Troubleshooting

- **`Could not open the X display`**: start it from a graphical session, not over plain SSH. On Wayland, check that XWayland is enabled.
- **`libX11 is not installed` / `libXext is not installed`**: install `libx11-6` and `libxext6`.
- **The pet shows a black box around it**: no compositor is running, but a 32-bit visual was requested anyway. Start a compositor, or report it with the details from the status note at the top.
- **No sound**: install `pulseaudio-utils`, or make sure `pw-play` or `aplay` is on your `PATH`.
- **No notifications**: install `libnotify-bin`. If notifications still fail, the pet opens a `zenity` dialog when zenity is installed.
