#!/bin/bash
# Genera dist/videorescue.app y dist/videorescue.dmg (ejecutar en macOS)
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements-build.txt
[ -f assets/icon.icns ] || .venv/bin/python tools/make_icon.py
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --windowed --name videorescue \
  --icon assets/icon.icns --paths . \
  --add-data "videorescue/static:videorescue/static" \
  --collect-all imageio_ffmpeg packaging/entry.py
STAGE=$(mktemp -d)
cp -R dist/videorescue.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "videorescue" -srcfolder "$STAGE" -ov -format UDZO dist/videorescue.dmg
rm -rf "$STAGE"
echo "Listo: dist/videorescue.dmg"
