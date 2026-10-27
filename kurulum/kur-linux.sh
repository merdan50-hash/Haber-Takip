#!/bin/bash
# Haber Takip — Linux kurulum aracı.
# Hizmeti kurar, oturum açılışında otomatik başlatır (systemd kullanıcı hizmeti; yoksa masaüstü otomatik başlatma)
# ve eklentiyi erişim anahtarıyla hazırlar. Yeniden çalıştırmak güvenlidir; kayıtlar ve anahtar korunur.
# Sonraki sürümler GitHub'dan kendiliğinden kurulur.
set -euo pipefail

VARSAYILAN_PORT=18765
PAKET="$(cd "$(dirname "$0")" && pwd)"
HIZMET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/haber-takip"
EKLENTI_DIR="$HOME/HaberTakip/eklenti"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/haber-takip.desktop"
LOG="$HIZMET_DIR/hizmet.log"

hata() { printf '\n\033[31mHATA:\033[0m %s\n' "$1" >&2; exit 1; }
adim() { printf '\033[1m• %s\033[0m\n' "$1"; }

[ "$(uname)" = "Linux" ] || hata "Bu kurulum aracı Linux içindir."
[ -f "$PAKET/hizmet/haber_takip_hizmeti.py" ] && [ -f "$PAKET/eklenti/manifest.json" ] \
  || hata "Kurulum dosyaları eksik. Zip dosyasını tamamen açıp kur-linux.sh dosyasını klasörün içinden çalıştırın."

adim "Python 3 denetleniyor"
PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
  hata "Python 3.8 veya üstü gerekli. Örneğin Ubuntu/Debian: sudo apt install python3  ·  Fedora: sudo dnf install python3"
fi

systemd_var() { command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; }
dolu() {
  "$PY" - "$1" <<'PYEOF'
import socket, sys
s = socket.socket()
s.settimeout(1)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PYEOF
}

adim "Eski hizmet durduruluyor (varsa)"
if systemd_var; then systemctl --user stop haber-takip.service >/dev/null 2>&1 || true; fi
pkill -f "haber_takip_hizmeti.py --data $HIZMET_DIR" >/dev/null 2>&1 || true
TERCIH="$(cat "$HIZMET_DIR/port" 2>/dev/null || echo "$VARSAYILAN_PORT")"
for _ in $(seq 1 10); do dolu "$TERCIH" || break; sleep 0.5; done

# Bağlantı noktası başka bir programdaysa onu bozmadan boş bir bağlantı noktasına geç.
PORT=""
for ADAY in "$TERCIH" $(seq "$VARSAYILAN_PORT" 18799 | grep -vx "$TERCIH"); do
  if dolu "$ADAY"; then
    SAHIP="$( (command -v ss >/dev/null && ss -ltnpH "sport = :$ADAY" 2>/dev/null | grep -o 'users:(("[^"]*"' | cut -d'"' -f2) || true)"
    printf '  %s numaralı bağlantı noktası dolu%s; başka bir numara deneniyor.\n' "$ADAY" "${SAHIP:+ ($SAHIP)}"
  else
    PORT="$ADAY"; break
  fi
done
[ -n "$PORT" ] || hata "18765–18799 arasında boş bağlantı noktası bulunamadı."

adim "Hizmet kuruluyor: $HIZMET_DIR"
mkdir -p "$HIZMET_DIR"
echo "$PORT" > "$HIZMET_DIR/port"
cp "$PAKET/hizmet/haber_takip_hizmeti.py" "$HIZMET_DIR/"
if [ ! -s "$HIZMET_DIR/token" ]; then
  (umask 077; "$PY" -c 'import secrets; print(secrets.token_urlsafe(32))' > "$HIZMET_DIR/token")
fi
chmod 600 "$HIZMET_DIR/token"

adim "Eklenti hazırlanıyor: $EKLENTI_DIR"
mkdir -p "$EKLENTI_DIR"
find "$EKLENTI_DIR" -mindepth 1 -delete
cp -R "$PAKET/eklenti/." "$EKLENTI_DIR/"
"$PY" - "$HIZMET_DIR/token" "$EKLENTI_DIR/bridge-config.js" "$PORT" <<'PYEOF'
import json, sys
token = open(sys.argv[1], encoding="utf-8").read().strip()
config = {"url": "http://127.0.0.1:%s" % sys.argv[3], "token": token}
with open(sys.argv[2], "w", encoding="utf-8") as stream:
    stream.write("// Kurulum aracı bu dosyaya yalnız bu kuruluma ait bağlantıyı yazar.\n")
    stream.write("globalThis.HABER_BRIDGE = %s;\n" % json.dumps(config))
PYEOF

adim "Otomatik başlatma ayarlanıyor"
KOMUT=("$PY" "$HIZMET_DIR/haber_takip_hizmeti.py" --data "$HIZMET_DIR" --port "$PORT" --log "$LOG" --extension-dir "$EKLENTI_DIR")
if systemd_var; then
  mkdir -p "$UNIT_DIR"
  rm -f "$AUTOSTART"
  "$PY" - "$UNIT_DIR/haber-takip.service" "${KOMUT[@]}" <<'PYEOF'
import sys
path, command = sys.argv[1], sys.argv[2:]
# systemd ExecStart satırında boşluk içeren yollar çift tırnakla, % işaretleri %% olarak yazılır.
exec_start = " ".join('"%s"' % part.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") for part in command)
with open(path, "w", encoding="utf-8") as stream:
    stream.write("[Unit]\nDescription=Haber Takip yerel hizmeti\nAfter=network-online.target\n\n"
                 "[Service]\nExecStart=%s\nRestart=always\nRestartSec=10\n\n"
                 "[Install]\nWantedBy=default.target\n" % exec_start)
PYEOF
  systemctl --user daemon-reload
  systemctl --user enable --now haber-takip.service >/dev/null 2>&1 || hata "Hizmet başlatılamadı. Ayrıntı: journalctl --user -u haber-takip"
  BASLATMA="systemd kullanıcı hizmeti (haber-takip.service)"
else
  mkdir -p "$(dirname "$AUTOSTART")"
  "$PY" - "$AUTOSTART" "${KOMUT[@]}" <<'PYEOF'
import shlex, sys
path, command = sys.argv[1], sys.argv[2:]
with open(path, "w", encoding="utf-8") as stream:
    stream.write("[Desktop Entry]\nType=Application\nName=Haber Takip hizmeti\nNoDisplay=true\n"
                 "X-GNOME-Autostart-enabled=true\nExec=%s\n" % " ".join(shlex.quote(part) for part in command))
PYEOF
  nohup setsid "${KOMUT[@]}" >/dev/null 2>&1 < /dev/null &
  BASLATMA="masaüstü otomatik başlatma ($AUTOSTART)"
fi

adim "Hizmetin açılması bekleniyor"
TOKEN="$(cat "$HIZMET_DIR/token")"
for _ in $(seq 1 40); do
  if "$PY" - "$PORT" "$TOKEN" <<'PYEOF'
import sys, urllib.request
request = urllib.request.Request("http://127.0.0.1:%s/api/status" % sys.argv[1], headers={"Authorization": "Bearer " + sys.argv[2]})
try:
    urllib.request.urlopen(request, timeout=2).read()
except Exception:
    sys.exit(1)
PYEOF
  then HAZIR=1; break; fi
  sleep 0.5
done
[ "${HAZIR:-}" = 1 ] || hata "Hizmet yanıt vermedi. Ayrıntı: $LOG"

printf '\n\033[32mHizmet çalışıyor\033[0m (http://127.0.0.1:%s). Otomatik başlatma: %s\n\n' "$PORT" "$BASLATMA"
cat <<MSG
Son adım — eklentiyi tarayıcıya ekleyin (yalnızca ilk kurulumda gerekir).
Chrome, Chromium, Edge, Brave, Opera ve Vivaldi desteklenir:
  1. Adres çubuğuna  chrome://extensions  yazın (Edge: edge://extensions).
  2. "Geliştirici modu"nu açın.
  3. "Paketlenmemiş öğe yükle"ye basın ve şu klasörü seçin:
       $EKLENTI_DIR
  4. Araç çubuğundaki yapboz simgesinden Haber Takip'i sabitleyip tıklayın.

Yeni sürümler GitHub'dan kendiliğinden kurulur; eklenti de kendini yeniler.
MSG
if [ -z "${HABER_TAKIP_SESSIZ:-}" ] && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$HOME/HaberTakip" >/dev/null 2>&1 || true
fi
