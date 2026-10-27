#!/bin/bash
# Haber Takip — Linux kaldırma aracı.
set -uo pipefail

HIZMET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/haber-takip"
UNIT="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/haber-takip.service"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now haber-takip.service >/dev/null 2>&1 || true
fi
rm -f "$UNIT" "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/haber-takip.desktop"
command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload >/dev/null 2>&1 || true
pkill -f "haber_takip_hizmeti.py --data $HIZMET_DIR" >/dev/null 2>&1 || true
echo "Hizmet durduruldu ve otomatik başlatma kaldırıldı."

CEVAP="${HABER_TAKIP_SIL:-}"
[ -n "$CEVAP" ] || read -r -p "Kaynak listesi ve haber kayıtları da silinsin mi? [e/H] " CEVAP
case "$CEVAP" in
  [eE]*) rm -rf "$HIZMET_DIR" "$HOME/HaberTakip"
         echo "Kayıtlar ve eklenti klasörü silindi." ;;
  *)     rm -f "$HIZMET_DIR/haber_takip_hizmeti.py"
         echo "Kayıtlar korundu: $HIZMET_DIR" ;;
esac
echo "Son olarak tarayıcının eklentiler sayfasından Haber Takip eklentisini kaldırın."
