@echo off
setlocal
cd /d "%~dp0.."

echo [GameHub] Installing PyInstaller (needs internet) ...
python -m pip install --upgrade pyinstaller pillow
if errorlevel 1 goto :fail

echo [GameHub] Building GameHub.exe ...
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --name GameHub ^
    --icon "assets\hub.ico" --add-data "assets;assets" hub.pyw
if errorlevel 1 goto :fail

echo.
echo [GameHub] Done: dist\GameHub.exe
echo Copy dist\GameHub.exe into the GameHub folder, then double-click 启动游戏中心.bat.
pause
exit /b 0

:fail
echo [GameHub] Build failed.
pause
exit /b 1
