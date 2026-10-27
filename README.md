# Haber Takip

Haber sitelerini ve RSS akışlarını izleyip yeni haberleri tek ekranda gösteren tarayıcı eklentisi. **Kurulum aracı, program ya da hesap gerektirmez**; her şey eklentinin içinde çalışır ve veriler yalnızca sizin tarayıcınızda saklanır.

- Siteyi yazmanız yeterli: eklenti RSS/Atom akışını kendisi bulur, akışı olmayan sitelerde ana sayfadaki haber başlıklarını izler.
- Yeni haberler sayfada vurgulanır, okunmamış sayısı araç çubuğu simgesinde görünür; isterseniz sesli uyarı verir.
- Sayfa kapalıyken de 30 saniyede bir taramaya devam eder.
- Windows, macOS, Linux ve ChromeOS'ta Chrome, Edge, Brave, Opera ve Vivaldi (Chromium 120+) ile çalışır. Telefon tarayıcıları eklenti desteklemez.

## Yükleme
**Mağazadan (önerilen, kendiliğinden güncellenir):** Chrome Web Mağazası veya Microsoft Edge Eklentileri sayfasında "Ekle"ye basın. *(Mağaza bağlantıları yayın onaylanınca buraya eklenecek.)*

**Elle (geliştirici modu):**
1. [Releases](../../releases/latest) sayfasından `haber-takip-<sürüm>.zip` dosyasını indirip açın.
2. Tarayıcıda `chrome://extensions` (Edge: `edge://extensions`) sayfasını açın, **Geliştirici modu**nu açın.
3. **Paketlenmemiş öğe yükle**'ye basıp açtığınız `haber-takip` klasörünü seçin.
4. Araç çubuğundaki yapboz simgesinden Haber Takip'i sabitleyip tıklayın.

Elle yüklenen sürümde, yeni sürüm çıktığında eklenti sayfasında **Yeni sürüm** bağlantısı görünür. Güncellemek için yeni zip'i aynı klasörün üzerine açıp eklentiler sayfasında ↻ simgesine basın; kaynak listeniz ve haberleriniz korunur.

## Geliştirme
```sh
node --test test/*.test.js        # motor testleri
./paketle.sh                      # dist/haber-takip-<sürüm>.zip
```
Her gönderimde CI, eklentiyi gerçek Chromium'da yükleyip gerçek haber siteleriyle dener.

## Yeni sürüm yayınlama
`manifest.json`'daki sürümü artırın, `CHANGELOG.md`'ye aynı başlıkla bölüm ekleyin, sonra GitHub'da **Actions → Release → Run workflow**. İş akışı GitHub Release'i oluşturur ve ayarlıysa sürümü mağazalara yükler ([magaza/KURULUM.md](magaza/KURULUM.md)).

Değişiklikler için [CHANGELOG.md](CHANGELOG.md).
