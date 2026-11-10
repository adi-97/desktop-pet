# Desktop Pet on Windows

Works on Windows 10 and 11.

## Run the ready-made app

Download `DesktopPet.exe` and double-click it. You don't need to install Python or anything else.

- The first time you run it, Windows SmartScreen may warn about an unknown publisher, because the exe isn't code-signed. Click **More info**, then **Run anyway**.
- The exe unpacks itself to a temp folder when it starts, so the first launch takes a second or two.

## Run from source

Requires Python 3.10 or newer, from [python.org](https://www.python.org) with the tcl/tk option ticked (it is on by default).

```powershell
pip install -r requirements.txt
python desktop_pet.py
```

To run it without a console window, use `pythonw desktop_pet.py`.

## Build the exe

```powershell
packaging\windows\build.bat
```

This installs the pinned dependencies and runs PyInstaller. It creates `dist\DesktopPet.exe`, about 24 MB, with no console window. The temporary `build\` folder is deleted afterwards.

## Where things are kept

| What | Where |
|---|---|
| Settings, stats, pending reminders | `%APPDATA%\DesktopPet\settings.json` |
| Error log | `%APPDATA%\DesktopPet\error.log` |
| Start with Windows | a `DesktopPet` value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |

To reset the pet, exit it and delete the `%APPDATA%\DesktopPet` folder.

## Troubleshooting

- **"Desktop Pet is already running"**: only one copy can run at a time. Look for the pet on your screen, or end `DesktopPet.exe` in Task Manager.
- **No notifications**: check that notifications are allowed for the app in Windows Settings > System > Notifications, and that Focus Assist or Do Not Disturb is off. If notifications fail, the pet shows a message box instead.
- **Weather says "my best guess, I'm offline"**: wttr.in couldn't be reached, so the pet shows sample weather.
