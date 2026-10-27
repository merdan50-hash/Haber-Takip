# Haber Takip — Değişiklikler

## 1.4.1
- **Kurulum, 18765 numaralı bağlantı noktası başka bir programdayken artık yarıda kesilmiyor.** O programın adını gösterip 18766–18799 arasında boş bir bağlantı noktası seçiyor ve eklentiye o adresi yazıyor. Seçilen numara sonraki kurulumlarda da korunuyor.
- Eklenti, kurulum aracının hazırladığı klasörden yüklenmediğinde hangi klasörün yükleneceğini açıkça söylüyor; başlıkta "Kurulum tamamlanmamış" yazıyor.

## 1.4.0
- **Windows, macOS ve Linux desteği.** Tek kurulum paketi üç işletim sistemi için de araç içerir:
  - Windows 10/11: `kur-windows.bat` (çift tıklama). Python yoksa winget ile yükler. Hizmet, Görev Zamanlayıcı ile oturum açılışında arka planda başlar.
  - macOS: `kur-macos.command` (launchd ile otomatik başlatma).
  - Linux: `kur-linux.sh` (systemd kullanıcı hizmeti; yoksa masaüstü otomatik başlatma).
- **GitHub'dan otomatik güncelleme.** Hizmet 15 dakikada bir son Release'i denetler. Yeni sürümü indirir, SHA-256 özetini doğrular, kendini ve eklenti dosyalarını günceller ve yeniden başlar. Eklenti yeni sürümü görünce kendini yeniden yükler ve sekmesini geri açar.
- Hizmet Windows'ta konsol penceresi açmadan çalışır ve günlüğünü `hizmet.log` dosyasına yazar.
- Kurulum her sürümde GitHub Actions üzerinde gerçek Windows, macOS ve Linux makinelerinde kurulup gerçek haber siteleriyle denenir.

## 1.3.0
- **Yerel Haber Takip hizmeti eklendi** (`hizmet/haber_takip_hizmeti.py`). Yalnızca Python standart kütüphanesini kullanır, ek kurulum gerektirmez.
  - Sitelerin RSS/Atom akışını kendisi bulur; akışı olmayan sitelerde ana sayfadaki haber başlıklarını izler.
  - Erişilemeyen sitelerde bekleme süresini artırarak yeniden dener.
  - Haberler ve kaynak listesi bilgisayarda saklanır, 30 günden eski okunmuş haberler temizlenir.
  - Yalnızca 127.0.0.1 üzerinden ve erişim anahtarıyla çalışır.
  - Eski eklenti kayıtları yalnızca ilk açılışta aktarılır; silinen kaynaklar geri gelmez.
- **macOS kurulum aracı** (`kur.command`): hizmeti kurar, oturum açılışında otomatik başlatır, erişim anahtarını üretip eklentiye yazar. Güncelleme için yeniden çalıştırılabilir. Kaldırmak için `kaldir.command`.
- Release artık iki paket içerir: yalnızca eklenti ve macOS için eksiksiz paket.

## 1.2.1
- Uygulama sekmesi artık `chrome.runtime.getContexts` ile bulunuyor. Eski kod `chrome.tabs.query({url})` kullanıyordu; bu çağrı `tabs` izni olmadan URL ile eşleşmediği için simgeye her tıklamada yeni sekme açılıyordu.
- Chrome Web Mağazası için gereken simgeler (16/32/48/128 px) eklendi.
- Eklenti sayfalarına sıkı bir içerik güvenlik politikası (CSP) eklendi: bağlantılar yalnızca `http://127.0.0.1` adresine yapılabiliyor.
- Erişim anahtarı yalnızca yerel hizmete (127.0.0.1) gönderiliyor; başka bir adres yazılırsa uygulama bağlanmayı reddediyor.
- Aramaya 250 ms gecikme eklendi; her tuş vuruşunda hizmete istek gitmiyor.
- "Kaynak eklendi" gibi işlem bildirimleri 6 saniye sonra kendiliğinden kayboluyor; bağlantı hataları sorun sürdükçe görünür kalıyor.
- Sürüm numarası artık tek bir yerden (`manifest.json`) okunuyor.
- En düşük Chrome sürümü: 116.
