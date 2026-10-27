#!/bin/bash
# Paketi Chrome Web Mağazası'na ve Microsoft Edge Eklentileri'ne yükleyip yayınlar.
# Her mağaza yalnızca ilgili GitHub gizli değerleri (Settings → Secrets → Actions) tanımlıysa denenir.
# Kullanım: magaza-yayinla.sh <mağaza-zip> <sürüm>
set -euo pipefail
ZIP="$1"; SURUM="$2"
YAPILAN=0
# Adresler yalnızca testlerde değiştirilir.
TOKEN_URL="${TOKEN_URL:-https://oauth2.googleapis.com/token}"
CWS_API="${CWS_API:-https://chromewebstore.googleapis.com}"
EDGE_API="${EDGE_API:-https://api.addons.microsoftedge.microsoft.com}"

json() { python3 -c "import json,sys; d=json.load(sys.stdin); print(d$1)"; }

if [ -n "${CWS_CLIENT_ID:-}" ] && [ -n "${CWS_CLIENT_SECRET:-}" ] && [ -n "${CWS_REFRESH_TOKEN:-}" ] \
   && [ -n "${CWS_PUBLISHER_ID:-}" ] && [ -n "${CWS_EXTENSION_ID:-}" ]; then
  echo "== Chrome Web Mağazası"
  TOKEN=$(curl -fsS "$TOKEN_URL" -d client_id="$CWS_CLIENT_ID" -d client_secret="$CWS_CLIENT_SECRET" \
    -d refresh_token="$CWS_REFRESH_TOKEN" -d grant_type=refresh_token | json '["access_token"]')
  ITEM="publishers/$CWS_PUBLISHER_ID/items/$CWS_EXTENSION_ID"
  YANIT=$(curl -sS -H "Authorization: Bearer $TOKEN" -X POST -T "$ZIP" \
    "$CWS_API/upload/v2/$ITEM:upload")
  echo "Yükleme yanıtı: $YANIT"
  DURUM=$(echo "$YANIT" | json '.get("uploadState", "")')
  for _ in $(seq 1 30); do
    [ "$DURUM" = "IN_PROGRESS" ] || [ "$DURUM" = "UPLOAD_IN_PROGRESS" ] || break
    sleep 10
    DURUM=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$CWS_API/v2/$ITEM:fetchStatus" \
      | json '.get("lastAsyncUploadState") or d.get("uploadState", "")' 2>/dev/null || echo "")
  done
  case "$DURUM" in SUCCEEDED|SUCCESS) ;; *) echo "::error::Chrome Web Mağazası yüklemesi başarısız: $DURUM"; exit 1 ;; esac
  YANIT=$(curl -sS -H "Authorization: Bearer $TOKEN" -X POST "$CWS_API/v2/$ITEM:publish")
  echo "Yayın yanıtı: $YANIT"
  echo "$YANIT" | grep -q '"error"' && { echo "::error::Chrome Web Mağazası yayını başarısız."; exit 1; }
  echo "Chrome Web Mağazası: $SURUM incelemeye gönderildi; onaylanınca kullanıcılara kendiliğinden ulaşır."
  YAPILAN=1
else
  echo "Chrome Web Mağazası gizli değerleri tanımlı değil; atlandı."
fi

if [ -n "${EDGE_CLIENT_ID:-}" ] && [ -n "${EDGE_API_KEY:-}" ] && [ -n "${EDGE_PRODUCT_ID:-}" ]; then
  echo "== Microsoft Edge Eklentileri"
  API="$EDGE_API/v1/products/$EDGE_PRODUCT_ID/submissions"
  BASLIK=(-H "Authorization: ApiKey $EDGE_API_KEY" -H "X-ClientID: $EDGE_CLIENT_ID")
  bekle() {  # $1: işlem durumu adresi
    for _ in $(seq 1 60); do
      local durum
      durum=$(curl -fsS "${BASLIK[@]}" "$1" | json '.get("status", "")')
      case "$durum" in Succeeded) return 0 ;; Failed) curl -sS "${BASLIK[@]}" "$1"; return 1 ;; esac
      sleep 10
    done
    return 1
  }
  ISLEM=$(curl -fsS -D - -o /dev/null "${BASLIK[@]}" -H "Content-Type: application/zip" -X POST -T "$ZIP" "$API/draft/package" \
    | tr -d '\r' | awk -F': ' 'tolower($1)=="location"{print $2}' | sed 's|.*/||')
  bekle "$API/draft/package/operations/$ISLEM" || { echo "::error::Edge paket yüklemesi başarısız."; exit 1; }
  ISLEM=$(curl -fsS -D - -o /dev/null "${BASLIK[@]}" -H "Content-Type: application/json" -X POST \
    -d "{\"notes\": \"Haber Takip $SURUM\"}" "$API" | tr -d '\r' | awk -F': ' 'tolower($1)=="location"{print $2}' | sed 's|.*/||')
  bekle "$API/operations/$ISLEM" || { echo "::error::Edge yayını başarısız."; exit 1; }
  echo "Edge Eklentileri: $SURUM incelemeye gönderildi; onaylanınca kullanıcılara kendiliğinden ulaşır."
  YAPILAN=1
else
  echo "Edge Eklentileri gizli değerleri tanımlı değil; atlandı."
fi

[ "$YAPILAN" = 1 ] || echo "::notice::Hiçbir mağaza ayarlı değil; yalnızca GitHub Release yayınlandı. Kurulum için magaza/KURULUM.md."
