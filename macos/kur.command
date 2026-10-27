#!/bin/bash
# Haber Takip — macOS kurulum aracı.
# Hizmeti kurar, her oturum açılışında otomatik başlatır ve eklentiyi erişim anahtarıyla hazırlar.
# Yeniden çalıştırmak güvenlidir: güncelleme için de aynı komut kullanılır, kayıtlar ve anahtar korunur.
set -euo pipefail

LABEL="com.habertakip.hizmet"
PORT=18765
PAKET="$(cd "$(dirname "$0")" && pwd)"
HIZMET_DIR="$HOME/Library/Application Support/HaberTakip"
EKLENTI_DIR="$HOME/HaberTakip/eklenti"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/HaberTakip"

hata() { printf '\n\033[31mHATA:\033[0m %s\n' "$1" >&2; exit 1; }
adim() { printf '\033[1m• %s\033[0m\n' "$1"; }

[ "$(uname)" = "Darwin" ] || hata "Bu kurulum aracı yalnızca macOS içindir."
[ -f "$PAKET/hizmet/haber_takip_hizmeti.py" ] && [ -f "$PAKET/eklenti/manifest.json" ] \
  || hata "Kurulum dosyaları eksik. Zip dosyasını tamamen açıp kur.command'ı klasörün içinden çalıştırın."

adim "Python 3 denetleniyor"
PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
  xcode-select --install >/dev/null 2>&1 || true
  hata "Python 3 bulunamadı. Açılan pencereden \"Komut Satırı Geliştirici Araçları\"nı yükleyin, bitince bu komutu yeniden çalıştırın."
fi
PY="$("$PY" -c 'import sys; print(sys.executable)')"

adim "Eski hizmet durduruluyor (varsa)"
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
for _ in 1 2 3 4 5 6 7 8 9 10; do
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
  sleep 0.5
done
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  hata "$PORT numaralı bağlantı noktasını başka bir program kullanıyor: $(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN | awk 'NR==2{print $1}')"
fi

adim "Hizmet kuruluyor: $HIZMET_DIR"
mkdir -p "$HIZMET_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents"
cp "$PAKET/hizmet/haber_takip_hizmeti.py" "$HIZMET_DIR/"
if [ ! -s "$HIZMET_DIR/token" ]; then
  (umask 077; "$PY" -c 'import secrets; print(secrets.token_urlsafe(32))' > "$HIZMET_DIR/token")
fi
chmod 600 "$HIZMET_DIR/token"

adim "Eklenti hazırlanıyor: $EKLENTI_DIR"
mkdir -p "$EKLENTI_DIR"
find "$EKLENTI_DIR" -mindepth 1 -delete
cp -R "$PAKET/eklenti/." "$EKLENTI_DIR/"
xattr -dr com.apple.quarantine "$EKLENTI_DIR" >/dev/null 2>&1 || true
"$PY" - "$HIZMET_DIR/token" "$EKLENTI_DIR/bridge-config.js" "$PORT" <<'PYEOF'
import json, sys
token = open(sys.argv[1]).read().strip()
config = {"url": "http://127.0.0.1:%s" % sys.argv[3], "token": token}
with open(sys.argv[2], "w") as stream:
    stream.write("// Kurulum aracı bu dosyaya yalnız bu kuruluma ait bağlantıyı yazar.\n")
    stream.write("globalThis.HABER_BRIDGE = %s;\n" % json.dumps(config))
PYEOF

adim "Otomatik başlatma ayarlanıyor"
"$PY" - "$PLIST" "$LABEL" "$PY" "$HIZMET_DIR" "$PORT" "$LOG_DIR" <<'PYEOF'
import plistlib, sys
path, label, python, data, port, logs = sys.argv[1:]
with open(path, "wb") as stream:
    plistlib.dump({
        "Label": label,
        "ProgramArguments": [python, data + "/haber_takip_hizmeti.py", "--data", data, "--port", port],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "StandardOutPath": logs + "/hizmet.log",
        "StandardErrorPath": logs + "/hizmet.log",
    }, stream)
PYEOF
launchctl bootstrap "gui/$(id -u)" "$PLIST" || hata "Hizmet başlatılamadı. Ayrıntı: $LOG_DIR/hizmet.log"

adim "Hizmetin açılması bekleniyor"
TOKEN="$(cat "$HIZMET_DIR/token")"
for _ in $(seq 1 40); do
  if curl -fsS --max-time 2 -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1; then
    HAZIR=1; break
  fi
  sleep 0.5
done
[ "${HAZIR:-}" = 1 ] || hata "Hizmet yanıt vermedi. Ayrıntı: $LOG_DIR/hizmet.log"

printf '\n\033[32mHizmet çalışıyor.\033[0m Bilgisayar her açıldığında kendiliğinden başlar.\n\n'
cat <<MSG
Son adım — eklentiyi Chrome'a ekleyin (yalnızca ilk kurulumda gerekir):
  1. Chrome'da adres çubuğuna  chrome://extensions  yazın.
  2. Sağ üstteki "Geliştirici modu"nu açın.
  3. "Paketlenmemiş öğe yükle"ye basın ve şu klasörü seçin:
       $EKLENTI_DIR
     (Finder açıldı; seçim penceresinde Cmd+Shift+G ile bu yolu yapıştırabilirsiniz.)
  4. Araç çubuğundaki yapboz simgesinden Haber Takip'i sabitleyip tıklayın.

Güncelleme yaptıysanız: chrome://extensions sayfasında Haber Takip kartındaki ↻ simgesine basmanız yeterli.
MSG
printf '%s' "$EKLENTI_DIR" | pbcopy 2>/dev/null && echo "(Klasör yolu panoya kopyalandı.)"
open "$HOME/HaberTakip" >/dev/null 2>&1 || true
open -a "Google Chrome" >/dev/null 2>&1 || true
