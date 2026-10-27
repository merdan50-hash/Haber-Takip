#!/bin/bash
# Yayın paketlerini dist/ klasörüne üretir:
#   haber-takip-eklenti-<sürüm>.zip   yalnızca tarayıcı eklentisi
#   haber-takip-kurulum-<sürüm>.zip   Windows, macOS ve Linux için eklenti + yerel hizmet + kurulum araçları
#                                     (hizmetin otomatik güncellemesi de bu paketi kullanır)
set -euo pipefail
cd "$(dirname "$0")"
SURUM="$(python3 -c 'import json; print(json.load(open("manifest.json"))["version"])')"
HIZMET_SURUM="$(python3 -c 'import re; print(re.search(r"^VERSION = \"(.+)\"", open("hizmet/haber_takip_hizmeti.py", encoding="utf-8").read(), re.M).group(1))')"
[ "$SURUM" = "$HIZMET_SURUM" ] || { echo "Sürümler uyuşmuyor: manifest $SURUM, hizmet $HIZMET_SURUM" >&2; exit 1; }
EKLENTI=(manifest.json background.js app.html app.js bridge-config.js icons)
rm -rf dist && mkdir -p dist/HaberTakip/eklenti dist/HaberTakip/hizmet

zip -qr -X "dist/haber-takip-eklenti-$SURUM.zip" "${EKLENTI[@]}"

cp -R "${EKLENTI[@]}" dist/HaberTakip/eklenti/
cp hizmet/haber_takip_hizmeti.py dist/HaberTakip/hizmet/
cp kurulum/* dist/HaberTakip/
chmod +x dist/HaberTakip/*.command dist/HaberTakip/*.sh
(cd dist && zip -qr -X "haber-takip-kurulum-$SURUM.zip" HaberTakip)
echo "dist/haber-takip-eklenti-$SURUM.zip"
echo "dist/haber-takip-kurulum-$SURUM.zip"
