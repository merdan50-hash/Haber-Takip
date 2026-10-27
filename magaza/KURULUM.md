# Otomatik güncelleme kurulumu (bir kerelik)

Tarayıcılar eklentileri yalnızca **mağazadan** yüklendiklerinde kendiliğinden günceller. Aşağıdaki adımlar bir kez yapılır. Sonrasında her yeni sürümde GitHub'da **Actions → Release → Run workflow** demeniz yeterlidir: iş akışı yeni sürümü mağazalara yükler, mağaza incelemesinden (genellikle birkaç saat–birkaç gün) sonra bütün kullanıcıların tarayıcısı güncellemeyi kendiliğinden alır.

İki mağazadan birini ya da ikisini birden kurabilirsiniz. Edge Eklentileri ücretsizdir; Chrome Web Mağazası bir kerelik 5 ABD doları kayıt ücreti ister. Chrome kullanıcıları için Chrome Web Mağazası gerekir.

Paket: GitHub Releases sayfasındaki `haber-takip-<sürüm>-magaza.zip` dosyası. Başvuru metinleri ve görseller: [aciklama.md](aciklama.md).

---

## A. Chrome Web Mağazası

### 1. İlk yayın (elle, bir kez)
1. https://chrome.google.com/webstore/devconsole adresinde Google hesabınızla geliştirici kaydı yapın (5 $).
2. **Yeni öğe** → `haber-takip-<sürüm>-magaza.zip` dosyasını yükleyin.
3. **Mağaza girişi**, **Gizlilik** ve **Dağıtım** sekmelerini [aciklama.md](aciklama.md)'deki metinler ve bu klasördeki görsellerle doldurun. Görünürlük: Herkese açık.
4. **İncelemeye gönder**.
5. Şu iki değeri not edin:
   - **Öğe kimliği (Item ID)**: öğenin sayfasında, 32 harflik kimlik → `CWS_EXTENSION_ID`
   - **Yayıncı kimliği (Publisher ID)**: Geliştirici panosu → Hesap → `CWS_PUBLISHER_ID`

### 2. API erişimi
1. https://console.cloud.google.com adresinde yeni bir proje açın.
2. **API'ler ve Hizmetler → Kitaplık** → "Chrome Web Store API" → **Etkinleştir**.
3. **OAuth izin ekranı**: Kullanıcı türü **Harici**, uygulama adı "Haber Takip Yayın". Kaydettikten sonra yayın durumunu **Üretimde (In production)** yapın. "Test" durumunda kalırsa yenileme anahtarı 7 günde geçersiz olur.
4. **Kimlik bilgileri → Kimlik bilgisi oluştur → OAuth istemci kimliği**: Uygulama türü **Web uygulaması**. Yetkili yönlendirme URI'si: `https://developers.google.com/oauthplayground`. Oluşan **İstemci kimliği** → `CWS_CLIENT_ID`, **İstemci gizli anahtarı** → `CWS_CLIENT_SECRET`.
5. https://developers.google.com/oauthplayground adresini açın:
   - Sağ üstteki ⚙ → **Use your own OAuth credentials** → istemci kimliği ve gizli anahtarı girin.
   - Soldaki kutuya `https://www.googleapis.com/auth/chromewebstore` yazın → **Authorize APIs** → geliştirici hesabınızla izin verin.
   - **Exchange authorization code for tokens** → çıkan **Refresh token** → `CWS_REFRESH_TOKEN`.

---

## B. Microsoft Edge Eklentileri (ücretsiz)

1. https://partner.microsoft.com/dashboard/microsoftedge/overview adresinde ücretsiz geliştirici kaydı yapın.
2. **Yeni uzantı oluştur** → `haber-takip-<sürüm>-magaza.zip` dosyasını yükleyin, [aciklama.md](aciklama.md)'deki metinlerle formu doldurup yayınlayın.
3. Uzantının **Genel bakış** sayfasındaki **Ürün kimliği (Product ID)** → `EDGE_PRODUCT_ID`.
4. Sol menüde **Publish API** → **Create API credentials** → **İstemci kimliği** → `EDGE_CLIENT_ID`, **API anahtarı** → `EDGE_API_KEY`. API anahtarlarının süresi dolar; Partner Center uyarınca yenileyip gizli değeri güncelleyin.

---

## C. Değerleri GitHub'a ekleme

https://github.com/merdan50-hash/Haber-Takip/settings/secrets/actions → **New repository secret** ile yukarıda not ettiğiniz her değeri aynı adla ekleyin:

| Ad | Nereden |
|---|---|
| `CWS_CLIENT_ID` | A.2.4 |
| `CWS_CLIENT_SECRET` | A.2.4 |
| `CWS_REFRESH_TOKEN` | A.2.5 |
| `CWS_PUBLISHER_ID` | A.1.5 |
| `CWS_EXTENSION_ID` | A.1.5 |
| `EDGE_CLIENT_ID` | B.4 |
| `EDGE_API_KEY` | B.4 |
| `EDGE_PRODUCT_ID` | B.3 |

Bu değerler gizlidir; kimseyle paylaşmayın, sohbetlere yapıştırmayın. Yalnızca kurduğunuz mağazanın değerlerini eklemeniz yeterlidir; iş akışı eksik olan mağazayı atlar.

## Mevcut kullanıcılar
"Paketlenmemiş öğe yükle" ile yüklenmiş sürüm mağaza sürümüne kendiliğinden dönüşmez. Mağaza sürümünü bir kez yükleyip eski kartı kaldırın; mağaza sürümü bundan sonra kendiliğinden güncellenir. Kaynak listesi yeniden eklenmelidir.
