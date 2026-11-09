# Halley — Kullanım kılavuzu

Halley, KAP bildirimlerini ve ekonomi haberlerini okur, hisseler için alım senaryosu (giriş, zarar durdur, hedef)
hazırlar ve sonuçları takip eder. **Emir vermez:** alım-satımı siz Midas'tan elle yaparsınız. Hiçbir çıktı yatırım
tavsiyesi değildir.

## Açmak

- **`baslat.bat`** dosyasına çift tıklayın. Tarayıcıda panel açılır. Kapatmak için siyah pencereyi kapatın.
- İlk açılışta üstteki kutuya OpenAI API anahtarını bir kez girin (yalnız bu bilgisayarda saklanır).
- Arka planda bir "okuyucu" çalışır: KAP sayfalarını kendiliğinden tamamlar. Panelin üstündeki
  **📥 KAP sayfaları** kutusu ilerlemeyi gösterir; bir şey yapmanız gerekmez.

## Her işlem günü (önerilen akış)

| Ne zaman | Ne yapılır |
|---|---|
| **Sabah, 09:40'tan önce** | **🛡️ Piyasa bekçisi → 🌅 Sabah analizi**. Gece gelen haberler toplanır, tüm BIST'in fiyatı güncellenir, açık işlemler kontrol edilir, günün fırsatları ve takip listesi raporlanır. İlk çalıştırma ~4 dakika, sonrakiler ~1,5 dakika. |
| Gün içinde (isteğe bağlı) | **🔄 Haberleri güncelle**: yeni haberleri toplar ve analiz eder. |
| **Akşam, 18:10'dan sonra** | **🌙 Akşam analizi**. Günün fiyatlarıyla işlem günlüğü (TP1/TP2/SL), günlük ve toplam kâr/zarar, kaçırılan fırsatlar ve öneriler raporlanır. |

- Saat uygun değilse (hafta sonu, tatil, seans açıkken) panel uyarır ama yine de çalıştırır; uyarı rapora yazılır.
- Yarım günlerde seans 12:40'ta kapanır.

## Maliyet (OpenAI kredisi)

- **Sabah analizinde "yeni haberleri yapay zekâ ile de analiz et"** kutusu kapalıysa analiz ücretsizdir.
  Açıksa Ayarlar'daki adet kadar haber analiz edilir (haber başına yaklaşık 0,013 $); tahmini maliyet kutunun
  altında görünür.
- **🤖 Raporu yapay zekâ ile yorumla** ve **🤖 Kaçırılan fırsatları yapay zekâ ile açıkla** kutuları isteğe bağlıdır (varsayılan
  kapalı). Ayarlar'daki aylık bütçeyi (varsayılan 10 $) aşacak çağrı yapılmaz. Ölçülen maliyet: rapor yorumu
  yaklaşık 0,002 $.
- **🧪 Ücretsiz dene**: haberleri toplar ama yapay zekâyı çağırmaz; bir sonraki güncellemenin maliyetini gösterir.
- Fiyat, takvim ve tüm hesaplar ücretsizdir (yapay zekâ kullanılmaz).

## Sekmeler

| Sekme | İçerik |
|---|---|
| **📈 Bugünün listesi** | Haberi olan hisseler, haber skoru, teknik durum ve giriş senaryoları. Bir hisseye tıklayınca haber, gerekçe, takvim (bilanço, genel kurul, temettü) ve riskler açılır. |
| **📒 İşlem günlüğü** | Önerilen senaryolar burada **sanal işlem** olarak izlenir. Gerçekten aldıysanız **✍️ Bu işleme girdim** bölümünden alış günü ve fiyatını kaydedin; gerçek işleminiz ayrıca izlenir. |
| **📋 Raporlar** | Tüm sabah/akşam raporlarının arşivi. Raporlar sonradan değişmez; .md ve .json olarak indirilebilir. |
| **🧭 Gelişim** | Strateji, haber kaynağı, olay türü ve risk seviyesine göre başarı; hangi filtrenin sonradan yükselen hisseleri elediği; haftalık performans. **Onayınızı bekleyen öneriler** burada; onay hiçbir ayarı kendiliğinden değiştirmez. |
| **📰 Haberler** | Son analiz edilen 50 haber: hangi hisseyi hangi yönde etkilediği ve haberin kaynağına bağlantı. |
| **🔧 Gelişmiş** | Durum bilgisi, 📅 takvimi resmi kaynaklardan kontrol, 📥 KAP geçmişini tamamlama, 🧪 ucuz test, geçmiş veri pilotu. |

## Senaryo kartını okumak

- **Giriş türleri:** *Kırılım* (direnç üstünde kapanış → ertesi gün alım; fiyat alarmı kurun), *Geri çekilme* (yükseliş
  trendinde ortalamaya limit emir), *Destekten tepki* (önceden oluşmuş destek yakınında limit emir).
- **SL** zarar durdur, **TP1/TP2** hedefler. Günlükte TP1'de yarısı satılır, stop girişe çekilir; kalanı TP2'ye.
- **Risk seviyesi** düşük/orta/yüksek; nedenleri kartta yazar (likidite, haberin fiyatlanması, bilanço, temettü,
  makro olay…).
- **"Uygun giriş senaryosu yok"** da bir sonuçtur: koşullar elverişli değildir.
- Haber skoru zamanla azalır (eski haberin etkisi söner); 1,50'nin altında senaryo üretilmez.

## Ayarlar (⚙️ Ayarlar)

- **Komisyon ve kayma:** Midas'ın gerçek oranını girin; net kâr/zarar buna göre hesaplanır.
- **Sermaye ve işlem başına risk (%):** girilirse kartta kaç adet alınabileceği ve azami kayıp, raporlarda TL
  karşılıkları görünür. 0 bırakılırsa bu hesaplar gösterilmez.
- **Bekçi yapay zekâ yorumu aylık bütçesi ($).**

## Bilinmesi gerekenler

- Fiyatlar Yahoo'dan gelir ve gecikmelidir; gün içinde son mum yarım olabilir (panel "yarım veri" uyarısı verir).
- Teknik kurallar tek başına avantaj sağlamaz (geçmiş testte ölçüldü); asıl katkının haberden gelip gelmediği,
  biriken sanal işlemlerle zamanla görülecek. **Örnek az iken oranlar güvenilir değildir** (panel bunu yazar).
- **Kaçırılan fırsatlar** ancak bekçi o gün çalıştırıldıysa ve sonrasında 5 işlem günü geçtiyse tam değerlendirilir.
- Bir hata mesajı görürseniz (ör. "adresine bağlanılamadı") internet bağlantısını kontrol edip birkaç dakika sonra
  yeniden deneyin. KAP çok sık isteğe sınır koyar; okuyucu bunu kendisi bekler.
