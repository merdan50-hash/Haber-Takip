#!/bin/bash
# Yayın paketini üretir: dist/haber-takip-<sürüm>.zip (açılıp Chrome'a "Paketlenmemiş öğe" olarak yüklenir;
# aynı dosya Chrome Web Mağazası'na da yüklenebilir).
set -euo pipefail
cd "$(dirname "$0")"
SURUM="$(node -p 'require("./manifest.json").version')"
rm -rf dist && mkdir -p dist/haber-takip
cp -R manifest.json background.js motor.js app.html app.js icons dist/haber-takip/
(cd dist && zip -qr -X "haber-takip-$SURUM.zip" haber-takip)
echo "dist/haber-takip-$SURUM.zip"
