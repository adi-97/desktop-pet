@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt || goto :error
python -m PyInstaller --noconfirm --onefile --noconsole --name DesktopPet --workpath build --specpath build --add-data "%~dp0assets;assets" --hidden-import plyer.platforms.win.notification --exclude-module numpy --exclude-module win32com --exclude-module win32ui --exclude-module pythoncom --exclude-module pywintypes --exclude-module win32api --exclude-module pythonwin desktop_pet.py || goto :error
rmdir /s /q build
echo.
echo Done! Your pet is at dist\DesktopPet.exe
goto :eof

:error
echo Build failed.
exit /b 1
