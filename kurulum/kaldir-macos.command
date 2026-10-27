#!/bin/bash
# Haber Takip — macOS kaldırma aracı.
set -uo pipefail

LABEL="com.habertakip.hizmet"
HIZMET_DIR="$HOME/Library/Application Support/HaberTakip"

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Hizmet durduruldu ve otomatik başlatma kaldırıldı."

CEVAP="${HABER_TAKIP_SIL:-}"
[ -n "$CEVAP" ] || read -r -p "Kaynak listesi ve haber kayıtları da silinsin mi? [e/H] " CEVAP
case "$CEVAP" in
  [eE]*) rm -rf "$HIZMET_DIR" "$HOME/Library/Logs/HaberTakip" "$HOME/HaberTakip"
         echo "Kayıtlar ve eklenti klasörü silindi." ;;
  *)     rm -f "$HIZMET_DIR/haber_takip_hizmeti.py"
         echo "Kayıtlar korundu: $HIZMET_DIR" ;;
esac
echo "Son olarak chrome://extensions sayfasından Haber Takip eklentisini kaldırın."
