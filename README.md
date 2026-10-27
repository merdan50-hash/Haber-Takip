# Haber-Takip

Yerel Haber Takip hizmetinin topladığı haberleri tek ekranda gösteren Chrome eklentisi (Manifest V3).

- Masaüstü Chrome 116 veya üstü gerekir. Android'deki Chrome eklenti çalıştırmaz.
- Eklenti, bu bilgisayarda çalışan Haber Takip hizmetine (`http://127.0.0.1:18765`) bağlanır. Hizmetin kendisi bu depoda yoktur.

## Kurulum (geliştirici modu)
1. `chrome://extensions` sayfasını açın ve **Geliştirici modu**nu açın.
2. **Paketlenmemiş öğe yükle** ile bu klasörü seçin.
3. Hizmetin kurulum aracı `bridge-config.js` dosyasına adresi ve erişim anahtarını yazar. Anahtar boşsa uygulama "bağlantı ayarlanmamış" uyarısı gösterir.

## Yayın paketi
```sh
zip -qr -X haber-takip-$(node -p "require('./manifest.json').version").zip \
  manifest.json background.js app.html app.js bridge-config.js icons
```

Değişiklikler için [CHANGELOG.md](CHANGELOG.md) dosyasına bakın.
