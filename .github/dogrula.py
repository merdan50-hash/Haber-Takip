"""Kurulum testinden sonra çalışan hizmeti gerçek haber siteleriyle doğrular (CI için).

Kullanım: python dogrula.py <hizmet-klasörü> <eklenti-klasörü>
"""
import json
import os
import re
import sys
import time
import urllib.request

data_dir, extension_dir = sys.argv[1], sys.argv[2]
token = open(os.path.join(data_dir, "token"), encoding="utf-8-sig").read().strip()
config = open(os.path.join(extension_dir, "bridge-config.js"), encoding="utf-8").read()
assert token in config, "eklentiye yazılan anahtar hizmetinkiyle aynı olmalı"
assert os.path.exists(os.path.join(extension_dir, "manifest.json")), "eklenti dosyaları kopyalanmamış"
base = json.loads(re.search(r"HABER_BRIDGE = (\{.*\});", config).group(1))["url"]
expected = os.environ.get("BEKLENEN_PORT")
assert not expected or base.endswith(":" + expected), "beklenen bağlantı noktası %s, kurulan %s" % (expected, base)
with open("port.txt", "w") as stream:  # kaldırma adımı bu bağlantı noktasının kapandığını denetler
    stream.write(base.rsplit(":", 1)[1])
print("Hizmet adresi:", base)


def call(path, method="GET", body=None):
    request = urllib.request.Request(base + path, method=method,
                                     data=None if body is None else json.dumps(body).encode("utf-8"),
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


app = open(os.path.join(os.path.dirname(__file__), "..", "app.js"), encoding="utf-8").read()
defaults = re.findall(r'"(https?://[^"]+)"', app[app.index("const DEFAULT"):app.index("];")])
print("Varsayılan siteler içe aktarılıyor:", len(defaults))
call("/api/import", "POST", {"sites": defaults, "poll": 60, "articles": []})

deadline = time.time() + 150
while time.time() < deadline:
    status = call("/api/status")
    if all(source["lastSuccess"] or source["errors"] for source in status["sources"]):
        break
    time.sleep(5)

status = call("/api/status")
print("\nHizmet %s · eklenti %s · güncelleme: %s" % (status["version"], status["extensionVersion"], status["update"]))
print("%-32s %6s  %s" % ("KAYNAK", "HABER", "DURUM"))
for source in status["sources"]:
    state = "akış: %s" % source["feed"] if source["lastSuccess"] else "HATA: %s" % source["error"]
    print("%-32s %6d  %s" % (source["url"][:32], source["count"], state))
for item in call("/api/articles?limit=5")["articles"]:
    print("  -", item["site"], "|", item["title"][:80])

working = sum(1 for source in status["sources"] if source["count"] > 0)
assert status["extensionVersion"], "hizmet eklenti sürümünü okuyamadı (--extension-dir)"
assert working >= len(defaults) // 2, "sitelerin yarısından azı okunabildi (%d/%d)" % (working, len(defaults))
print("\nTAMAM: %d/%d sitede haber bulundu." % (working, len(defaults)))
