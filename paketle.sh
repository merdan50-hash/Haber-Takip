#!/bin/bash
# Yayın paketlerini dist/ klasörüne üretir:
#   haber-takip-<sürüm>.zip        yalnızca Chrome eklentisi
#   haber-takip-mac-<sürüm>.zip    macOS için eklenti + yerel hizmet + kurulum aracı
set -euo pipefail
cd "$(dirname "$0")"
SURUM="$(python3 -c 'import json; print(json.load(open("manifest.json"))["version"])')"
EKLENTI=(manifest.json background.js app.html app.js bridge-config.js icons)
rm -rf dist && mkdir -p dist/HaberTakip/eklenti dist/HaberTakip/hizmet

zip -qr -X "dist/haber-takip-$SURUM.zip" "${EKLENTI[@]}"

cp -R "${EKLENTI[@]}" dist/HaberTakip/eklenti/
cp hizmet/haber_takip_hizmeti.py dist/HaberTakip/hizmet/
cp macos/kur.command macos/kaldir.command macos/BENIOKU.txt dist/HaberTakip/
chmod +x dist/HaberTakip/*.command
(cd dist && zip -qr -X "haber-takip-mac-$SURUM.zip" HaberTakip)
echo "dist/haber-takip-$SURUM.zip"
echo "dist/haber-takip-mac-$SURUM.zip"
