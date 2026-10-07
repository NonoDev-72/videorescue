@echo off
REM Genera dist\DECODE-VIDEO\DECODE-VIDEO.exe (ejecutar en Windows con Python 3)
cd /d "%~dp0\.."
if not exist .venv python -m venv .venv
.venv\Scripts\pip install -q -r requirements-build.txt
if not exist assets\icon.ico .venv\Scripts\python tools\make_icon.py
rmdir /s /q build dist 2>nul
.venv\Scripts\pyinstaller --noconfirm --windowed --name DECODE-VIDEO --icon assets\icon.ico --paths . --add-data "decode_video\static;decode_video\static" --collect-all imageio_ffmpeg packaging\entry.py
echo Listo: dist\DECODE-VIDEO\DECODE-VIDEO.exe
