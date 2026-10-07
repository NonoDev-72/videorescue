#!/bin/bash
# Genera dist/DECODE-VIDEO.app y dist/DECODE-VIDEO.dmg (ejecutar en macOS)
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements-build.txt
[ -f assets/icon.icns ] || .venv/bin/python tools/make_icon.py
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --windowed --name DECODE-VIDEO \
  --icon assets/icon.icns --paths . \
  --add-data "decode_video/static:decode_video/static" \
  --collect-all imageio_ffmpeg packaging/entry.py
STAGE=$(mktemp -d)
cp -R dist/DECODE-VIDEO.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "DECODE-VIDEO" -srcfolder "$STAGE" -ov -format UDZO dist/DECODE-VIDEO.dmg
rm -rf "$STAGE"
echo "Listo: dist/DECODE-VIDEO.dmg"
