#!/bin/bash
# Arranca DECODE-VIDEO (versión web local) y abre el navegador
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
(sleep 1.5; open "http://127.0.0.1:5055") &
exec .venv/bin/python -m decode_video
