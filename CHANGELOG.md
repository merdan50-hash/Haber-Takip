# Haber Takip — Değişiklikler

## 1.2.1
- Uygulama sekmesi artık `chrome.runtime.getContexts` ile bulunuyor. Eski kod `chrome.tabs.query({url})` kullanıyordu; bu çağrı `tabs` izni olmadan URL ile eşleşmediği için simgeye her tıklamada yeni sekme açılıyordu.
- Chrome Web Mağazası için gereken simgeler (16/32/48/128 px) eklendi.
- Eklenti sayfalarına sıkı bir içerik güvenlik politikası (CSP) eklendi: bağlantılar yalnızca `http://127.0.0.1` adresine yapılabiliyor.
- Erişim anahtarı yalnızca yerel hizmete (127.0.0.1) gönderiliyor; başka bir adres yazılırsa uygulama bağlanmayı reddediyor.
- Aramaya 250 ms gecikme eklendi; her tuş vuruşunda hizmete istek gitmiyor.
- "Kaynak eklendi" gibi işlem bildirimleri 6 saniye sonra kendiliğinden kayboluyor; bağlantı hataları sorun sürdükçe görünür kalıyor.
- Sürüm numarası artık tek bir yerden (`manifest.json`) okunuyor.
- En düşük Chrome sürümü: 116.

## Kurulum notu
`bridge-config.js` içindeki `token` boş gelir; yerel Haber Takip hizmetinin kurulum aracı bu dosyaya adres ve anahtarı yazar. Anahtar dosyada yoksa uygulama "bağlantı ayarlanmamış" uyarısı gösterir.
