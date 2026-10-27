# Microsoft Edge Eklentileri'ne ilk yükleme

Partner Center'daki sırayla, her alana ne yazılacağı. Görseller bu klasörde; paket GitHub Releases'teki `haber-takip-<sürüm>-magaza.zip`.

## 0. Hesap (bir kez, ücretsiz)
1. https://partner.microsoft.com/dashboard/microsoftedge/public/account/signup adresini açın, Microsoft hesabınızla girin.
2. **Hesap türü: Bireysel (Individual)**. Ad, e-posta ve ülke bilgilerini doldurun.
3. **Yayımcı görünen adı**: mağazada görünecek ad (örneğin adınız ya da "Haber Takip").
4. Kaydı bitirin. Hesap doğrulaması birkaç dakika ile birkaç gün sürebilir.

## 1. Yeni uzantı
Microsoft Edge → **Genel bakış** → **Yeni uzantı oluştur** → `haber-takip-<sürüm>-magaza.zip` dosyasını sürükleyin → **Devam**.

## 2. Kullanılabilirlik (Availability)
- **Görünürlük:** Genel (Public)
- **Pazarlar:** Tüm pazarlar (varsayılan)

## 3. Özellikler (Properties)
- **Kategori:** News & weather (Haberler ve hava durumu)
- **Uzantınız kişisel bilgi erişiyor, topluyor veya iletiyor mu?** Hayır
- **Gizlilik ilkesi URL'si:** https://github.com/merdan50-hash/Haber-Takip/blob/main/magaza/gizlilik.md
- **Web sitesi URL'si:** https://github.com/merdan50-hash/Haber-Takip
- **Destek iletişim bilgileri:** https://github.com/merdan50-hash/Haber-Takip/issues
- **Yetişkin içerik:** Hayır

## 4. Mağaza listeleri (Store listings)
**Dil ekle → Türkçe** (isterseniz İngilizce de ekleyin; metni aşağıda). Her dil için:

**Açıklama (Description)**
```
Haber Takip, takip ettiğiniz haber sitelerindeki yeni haberleri tek bir sayfada, zaman sırasıyla toplar.

• Site adresini yazmanız yeterli: eklenti sitenin RSS/Atom akışını kendisi bulur; akışı olmayan sitelerde ana sayfadaki haber başlıklarını izler.
• Yeni çıkan haberler vurgulanır; okunmamış haber sayısı araç çubuğu simgesinde görünür. İsterseniz sesli uyarı verir.
• Sayfa kapalıyken de arka planda taramaya devam eder. Tarama aralığını 5 saniye ile 5 dakika arasında seçebilirsiniz.
• Haberlerde arama yapabilir, siteye göre süzebilir, yalnızca okunmamışları görebilirsiniz.
• Açık ve koyu temayı destekler.

Gizlilik: Hesap, kayıt veya sunucu yoktur. Kaynak listeniz ve haberler yalnızca kendi tarayıcınızda saklanır; hiçbir veri toplanmaz, satılmaz veya üçüncü taraflarla paylaşılmaz. Eklenti yalnızca sizin eklediğiniz sitelere bağlanır.

Açık kaynak: https://github.com/merdan50-hash/Haber-Takip
```

**Kısa açıklama (Short description)**
```
Haber sitelerini ve RSS akışlarını izler, yeni haberleri tek ekranda gösterir. Kurulum ve hesap gerektirmez.
```

**Görseller**
- Mağaza logosu (300×300): `logo-300x300.png`
- Küçük tanıtım kutucuğu (440×280): `tanitim-440x280.png`
- Büyük tanıtım kutucuğu (1400×560): `tanitim-1400x560.png`
- Ekran görüntüleri (1280×800): `ekran-1-acik.png`, `ekran-2-koyu.png`

**Arama terimleri (Search terms)** — her birini ayrı ekleyin:
```
haber
RSS okuyucu
haber takibi
gündem
son dakika
news reader
RSS
```

### İngilizce (isteğe bağlı)
Description:
```
Haber Takip collects the latest news from the sites you follow into a single, time-ordered page.

• Just type a site address: the extension finds its RSS/Atom feed automatically; for sites without a feed it follows the headlines on the home page.
• New stories are highlighted and the unread count is shown on the toolbar icon, with an optional sound alert.
• Keeps checking in the background even when the page is closed; choose an interval from 5 seconds to 5 minutes.
• Search the news, filter by site, or show unread items only. Light and dark themes.

Privacy: no account, no sign-up, no server. Your source list and the news are stored only in your own browser; no data is collected, sold or shared. The extension only connects to the sites you add.

Open source: https://github.com/merdan50-hash/Haber-Takip
```
Short description:
```
Follows news sites and RSS feeds and shows new stories on one screen. No setup, no account.
```

## 5. Gönder
**Yayımla (Publish)**'a basın. **Sertifikasyon notları (Notes for certification)** kutusuna:
```
No account or test credentials are needed. Click the toolbar icon to open the app page; ten sample Turkish news sites are added on first run and their headlines appear within a few seconds. Type any news site (e.g. https://www.theguardian.com/international) into "Site veya RSS adresi" and press "Ekle" to add it. Host permissions are needed because users can add any news site or RSS feed; the extension only fetches feeds from sites the user added (and api.github.com for a version check when not installed from a store). It injects no content scripts and does not read or modify web pages. All code is in the package; no remote code.
```

İnceleme genellikle 1–7 iş günü sürer. Onaylanınca:
- Uzantı sayfasındaki **Ürün kimliği (Product ID)** → GitHub gizli değeri `EDGE_PRODUCT_ID`
- **Publish API** sayfası → **API kimlik bilgileri oluştur** → `EDGE_CLIENT_ID` ve `EDGE_API_KEY`

Bu üç değeri https://github.com/merdan50-hash/Haber-Takip/settings/secrets/actions sayfasına ekleyince sonraki sürümler Edge'e kendiliğinden yüklenir.
