#!/bin/sh
set -e
cd "$(dirname "$0")/../.."
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --noconfirm --onefile --name DesktopPet --workpath build --specpath build \
    --add-data "$PWD/assets:assets" --hidden-import plyer.platforms.linux.notification \
    --exclude-module numpy desktop_pet.py
rm -rf build
echo
echo "Done! Your pet is at dist/DesktopPet"
