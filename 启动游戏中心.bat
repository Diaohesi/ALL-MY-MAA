@echo off
setlocal
cd /d "%~dp0"

if exist "GameHub.exe" (
    start "" "GameHub.exe"
    exit /b 0
)

set "PYW="
for %%P in (pythonw.exe) do set "PYW=%%~$PATH:P"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
if not defined PYW if exist "%ProgramFiles%\Python313\pythonw.exe" set "PYW=%ProgramFiles%\Python313\pythonw.exe"

if not defined PYW (
    echo [GameHub] Python not found.
    echo Please install Python 3 ^(tick "Add python.exe to PATH"^), or use the packaged GameHub.exe.
    pause
    exit /b 1
)

start "" "%PYW%" "%~dp0hub.pyw"
exit /b 0
