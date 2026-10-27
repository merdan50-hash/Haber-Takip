# Haber-Takip

Haber sitelerini ve RSS akışlarını izleyip yeni haberleri tek ekranda gösteren Chrome eklentisi ve yerel hizmeti.

- **Eklenti** (kök klasör): Chrome Manifest V3; masaüstü Chrome 116 veya üstü gerekir. Android'deki Chrome eklenti çalıştırmaz.
- **Hizmet** (`hizmet/`): siteleri arka planda tarayan, yalnızca `http://127.0.0.1:18765` üzerinden erişilen Python programı.
- **macOS kurulumu** (`macos/`): hizmeti kurup otomatik başlatan ve eklentiyi erişim anahtarıyla hazırlayan araç.

## macOS'ta kurulum
1. [Releases](../../releases) sayfasından `haber-takip-mac-<sürüm>.zip` dosyasını indirip açın.
2. Terminal'de çalıştırın:
   ```sh
   bash ~/Downloads/HaberTakip/kur.command
   ```
3. Chrome'da `chrome://extensions` → **Geliştirici modu** → **Paketlenmemiş öğe yükle** → `~/HaberTakip/eklenti` klasörünü seçin.

Ayrıntılar paketteki `BENIOKU.txt` dosyasında. Kaldırmak için `kaldir.command`.

## Geliştirme
```sh
python3 -m unittest discover -s hizmet   # hizmet testleri
./paketle.sh                             # dist/ altına yayın paketlerini üretir
```

## Yeni sürüm yayınlama
1. `manifest.json`'daki sürümü artırın ve `CHANGELOG.md`'ye aynı sürüm başlığıyla bir bölüm ekleyin.
2. GitHub'da **Actions → Release → Run workflow**. Testler geçerse iş akışı etiketi, paketleri ve Release'i oluşturur.

Değişiklikler için [CHANGELOG.md](CHANGELOG.md).
