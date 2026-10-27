# Haber-Takip

Haber sitelerini ve RSS akışlarını izleyip yeni haberleri tek ekranda gösteren tarayıcı eklentisi ve yerel hizmeti.

- **Eklenti** (kök klasör): Manifest V3; Chrome, Edge, Brave, Opera, Vivaldi ve Chromium (116+). Mobil tarayıcılarda çalışmaz.
- **Hizmet** (`hizmet/`): siteleri arka planda tarayan, yalnızca `http://127.0.0.1:18765` üzerinden erişilen Python programı. Yalnızca standart kütüphaneyi kullanır.
- **Kurulum araçları** (`kurulum/`): Windows, macOS ve Linux için hizmeti kurup otomatik başlatan, eklentiyi erişim anahtarıyla hazırlayan araçlar.

## Kurulum
[Releases](../../releases) sayfasından `haber-takip-kurulum-<sürüm>.zip` dosyasını indirip açın:

| Sistem | Komut |
|---|---|
| Windows 10/11 | `kur-windows.bat` dosyasına çift tıklayın |
| macOS | `bash ~/Downloads/HaberTakip/kur-macos.command` |
| Linux | `bash ~/Downloads/HaberTakip/kur-linux.sh` |

Ardından tarayıcıda `chrome://extensions` → **Geliştirici modu** → **Paketlenmemiş öğe yükle** → `~/HaberTakip/eklenti` klasörünü seçin. Ayrıntılar paketteki `BENIOKU.txt` dosyasında.

## Otomatik güncelleme
Kurulu hizmet 15 dakikada bir bu deponun son Release'ini denetler. Yeni sürümü indirip SHA-256 özetini doğrular, kendini ve eklenti dosyalarını günceller. Eklenti de kendini yeniden yükler. Hizmet Release'leri herkese açık adresten indirir; depo gizliyse hizmet klasörüne okuma yetkili bir GitHub anahtarı içeren `github-token` dosyası konmalıdır.

## Geliştirme
```sh
python3 -m unittest discover -s hizmet   # hizmet testleri
./paketle.sh                             # dist/ altına yayın paketlerini üretir
```
Her gönderimde CI, kurulum paketini gerçek Windows, macOS ve Linux makinelerinde kurar, gerçek haber siteleriyle dener ve kaldırır.

## Yeni sürüm yayınlama
1. `manifest.json` ve `hizmet/haber_takip_hizmeti.py` içindeki `VERSION` değerini artırın; `CHANGELOG.md`'ye aynı sürüm başlığıyla bölüm ekleyin.
2. GitHub'da **Actions → Release → Run workflow**. Kurulu tüm hizmetler en geç 15 dakika içinde yeni sürüme geçer.

Değişiklikler için [CHANGELOG.md](CHANGELOG.md).
