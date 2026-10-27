# Mağaza başvurusu metinleri

Chrome Web Mağazası ve Edge Eklentileri başvuru formlarına buradaki metinleri kopyalayın.

## Ad
Haber Takip

## Kısa açıklama (en çok 132 karakter)
Haber sitelerini ve RSS akışlarını izler, yeni haberleri tek ekranda gösterir. Kurulum ve hesap gerektirmez.

## Kategori
Haberler ve Hava Durumu (News & Weather). Listede yoksa: Verimlilik → Araçlar.

## Dil
Türkçe

## Ayrıntılı açıklama
Haber Takip, takip ettiğiniz haber sitelerindeki yeni haberleri tek bir sayfada, zaman sırasıyla toplar.

• Site adresini yazmanız yeterli: eklenti sitenin RSS/Atom akışını kendisi bulur; akışı olmayan sitelerde ana sayfadaki haber başlıklarını izler.
• Yeni çıkan haberler vurgulanır; okunmamış haber sayısı araç çubuğu simgesinde görünür. İsterseniz sesli uyarı verir.
• Sayfa kapalıyken de arka planda taramaya devam eder. Tarama aralığını 5 saniye ile 5 dakika arasında seçebilirsiniz.
• Haberlerde arama yapabilir, siteye göre süzebilir, yalnızca okunmamışları görebilirsiniz.
• Açık ve koyu temayı destekler.

Gizlilik: Hesap, kayıt veya sunucu yoktur. Kaynak listeniz ve haberler yalnızca kendi tarayıcınızda saklanır; hiçbir veri toplanmaz, satılmaz veya üçüncü taraflarla paylaşılmaz. Eklenti yalnızca sizin eklediğiniz sitelere bağlanır.

Açık kaynak: https://github.com/merdan50-hash/Haber-Takip

## Görseller (bu klasörde)
- Simge: ../icons/icon128.png (128×128); Edge mağaza logosu: logo-300x300.png (300×300)
- Ekran görüntüleri (1280×800): ekran-1-acik.png, ekran-2-koyu.png
- Küçük tanıtım kutusu (440×280): tanitim-440x280.png
- Büyük tanıtım görseli (1400×560): tanitim-1400x560.png

## Gizlilik politikası adresi
https://github.com/merdan50-hash/Haber-Takip/blob/main/magaza/gizlilik.md

## Tek amaç (Single purpose)
Kullanıcının seçtiği haber sitelerini ve RSS akışlarını izleyip yeni haberleri tek bir listede göstermek.

## İzin gerekçeleri
- **storage**: Kullanıcının eklediği site listesini, tarama aralığını ve çekilen haber başlıklarını tarayıcıda saklamak için.
- **unlimitedStorage**: Haber geçmişi (en çok 5000 başlık, 30 gün) tarayıcının varsayılan depolama sınırını aşabildiği için.
- **alarms**: Uygulama sayfası kapalıyken de seçilen aralıkta yeni haberleri denetlemek için.
- **Ana makine izinleri (http://\*/\*, https://\*/\*)**: Kullanıcı herhangi bir haber sitesini veya RSS adresini ekleyebildiği için eklentinin o siteden akışı indirebilmesi gerekir. Eklenti yalnızca kullanıcının eklediği sitelere ve sürüm denetimi için GitHub'a istek yapar; sayfalara kod eklemez, sayfa içeriğini okumaz ve değiştirmez.

## Uzaktan kod
Hayır. Eklentinin bütün kodu pakettedir; uzaktan kod indirilip çalıştırılmaz. İndirilen akışlar yalnızca metin olarak ayrıştırılır.

## Veri kullanımı beyanı
Hiçbir kullanıcı verisi toplanmıyor. (Formdaki bütün veri türü kutucuklarını boş bırakın ve üç onay kutusunu işaretleyin.)
