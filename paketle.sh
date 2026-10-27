#!/bin/bash
# Yayın paketlerini üretir:
#   dist/haber-takip-<sürüm>.zip         açılıp "Paketlenmemiş öğe yükle" ile yüklenir (içinde haber-takip/ klasörü)
#   dist/haber-takip-<sürüm>-magaza.zip  Chrome Web Mağazası ve Edge Eklentileri için (manifest kökte)
set -euo pipefail
cd "$(dirname "$0")"
SURUM="$(node -p 'require("./manifest.json").version')"
rm -rf dist && mkdir -p dist/haber-takip
cp -R manifest.json background.js motor.js app.html app.js icons dist/haber-takip/
(cd dist && zip -qr -X "haber-takip-$SURUM.zip" haber-takip)
(cd dist/haber-takip && zip -qr -X "../haber-takip-$SURUM-magaza.zip" .)
echo "dist/haber-takip-$SURUM.zip"
echo "dist/haber-takip-$SURUM-magaza.zip"
