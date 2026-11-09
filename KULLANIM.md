# Halley — Kullanım kılavuzu

Halley, KAP bildirimlerini ve ekonomi haberlerini okur, hisseler için alım senaryosu (giriş, zarar durdur, hedef)
hazırlar ve sonuçları takip eder. **Emir vermez:** alım-satımı siz Midas'tan elle yaparsınız. Hiçbir çıktı yatırım
tavsiyesi değildir.

## Açmak

- **Kurulum paketiyle (Halley_Kurulum.exe):** masaüstündeki **Halley** simgesine çift tıklayın; Halley kendi penceresinde
  açılır (tarayıcı gerekmez). Kapatmak için pencereyi kapatın; arka plandaki her şey de kapanır. Sayfayı yenilemek için
  **F5**. Haber kaynağı bağlantıları varsayılan tarayıcıda açılır. Kaldırmak: Başlat menüsü → Halley →
  **Halley'i kaldır** (verileri saklamayı sorar). Windows ilk açılışta "Windows bilgisayarınızı korudu" derse:
  **Ek bilgi → Yine de çalıştır** (program imzasız olduğu için çıkan olağan uyarı).
- **Geliştirici klasöründen:** **`baslat.bat`** dosyasına çift tıklayın. Kapatmak için siyah pencereyi kapatın.
- **Ekranlar:** üstteki sabit menüden seçilir — **📊 Dashboard · 🎯 Fırsatlar · 🔍 Hisse Analizi · ⭐ Takip Listem · 🛡️ Bekçi · 📰 Haberler · 📒 İşlem Günlüğü · 🏁 Performans · ⚙️ Ayarlar**. Her ekran ayrıdır; uzun kaydırma yok.
- Sağ üstteki **🌙 Koyu tema** düğmesi koyu/açık görünümü değiştirir (varsayılan koyu); seçim saklanır.
- İlk açılışta üstteki kutuya OpenAI API anahtarını bir kez girin (yalnız bu bilgisayarda saklanır).
- Arka planda bir "okuyucu" çalışır: KAP sayfalarını kendiliğinden tamamlar. Panelin üstündeki
  **📥 KAP sayfaları** kutusu ilerlemeyi gösterir; bir şey yapmanız gerekmez.

## Her işlem günü (önerilen akış)

| Ne zaman | Ne yapılır |
|---|---|
| **Sabah, 09:40'tan önce** | **🛡️ Bekçi → 🌅 Sabah analizi**. Gece gelen haberler toplanır, tüm BIST'in fiyatı güncellenir, açık işlemler kontrol edilir, günün fırsatları ve takip listesi raporlanır. İlk çalıştırma ~4 dakika, sonrakiler ~1,5 dakika. |
| Gün içinde (isteğe bağlı) | Sağ üstteki **🔄 Haberleri güncelle**: yeni haberleri toplar ve analiz eder. Takip listenizdeki hisseleri bekçi kendisi izler. |
| **Akşam, 18:10'dan sonra** | **🛡️ Bekçi → 🌙 Akşam analizi**. Günün fiyatlarıyla işlem günlüğü (TP1/TP2/SL), günlük ve toplam kâr/zarar, kaçırılan fırsatlar ve öneriler raporlanır. |

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

## Ekranlar

| Ekran | İçerik |
|---|---|
| **📊 Dashboard** | Tek bakışta: BIST 100, olumlu/olumsuz haber sayısı, uygun fırsatlar, piyasa durumu, bekçi durumu ve son olaylar, takip listenizdeki aktif senaryolar, açık işlemler, önümüzdeki 15 işlem gününün piyasa takvimi. |
| **🎯 Fırsatlar** | Haberi olan hisseler (olumlu / olumsuz / zayıf), haber skoru ve teknik durum. Her satırda **🔍 Analiz** (ayrıntı ekranı) ve **+ Takibe Al**. Detaylı listeyi CSV olarak indirme. |
| **🔍 Hisse Analizi** | Seçilen hissenin tüm analizi: giriş senaryoları (kırılım, geri çekilme, destekten tepki), referans senaryo, teknik göstergeler, sektör, bilanço ve şirket takvimi, finansal özet, haberler. Haberi olmayan hissede senaryolar yalnız fiyattan hesaplanır. **+ Takibe Al** düğmesi burada da var. |
| **⭐ Takip Listem** | Takibe aldığınız hisseler, senaryoları ve durumları, senaryo ve bildirim türü seçimleri, son olaylar, takip senaryolarının sonuçları. |
| **🛡️ Bekçi** | **🌅 Sabah analizi** / **🌙 Akşam analizi** ve yapay zekâ seçenekleri, takip bekçisinin durumu ve tüm olayları (Telegram'a gidip gitmediği), sabah/akşam rapor arşivi (sonradan değişmez; .md ve .json indirilebilir). |
| **📰 Haberler** | 🔬 Haber analizi (bekleyenleri seçerek analiz, derin yeniden inceleme, tahmini maliyet ve bütçe) ve son analiz edilen 50 haber. |
| **📒 İşlem Günlüğü** | Önerilen senaryolar **sanal işlem** olarak izlenir. Gerçekten aldıysanız **✍️ Bu işleme girdim** ile alış günü ve fiyatını kaydedin. Portföy/sektör riski, kayma ölçümü. |
| **🏁 Performans** | Takip senaryolarının strateji türüne göre TP1/TP2/SL oranları; sanal işlemlerin stratejiye, haber kaynağına, olay türüne ve riske göre başarısı; filtre analizi; **onayınızı bekleyen öneriler** (onay hiçbir ayarı kendiliğinden değiştirmez). |
| **⚙️ Ayarlar** | Ayarlar ve 📨 Telegram; **💾 Veri ve gelişmiş** (veri aktarma, durum, 📅 takvim kontrolü, 📥 KAP geçmişi, 🧪 ucuz test, geçmiş veri pilotu); ❓ Kılavuz (bu metin). |

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

## ⭐ Takip Listem ve bekçi

Halley bütün BIST'i taramaya devam eder; ama **Telegram'a yalnız takibe aldığınız hisselerin olayları gider.**

- **Takibe almak:** 🎯 Fırsatlar satırındaki ya da 🔍 Hisse Analizi ekranındaki **+ Takibe Al** düğmesi ya da **⭐ Takip Listem** ekranında hisse seçip
  **+ Takibe Al**. Halley o hissenin fiyatını tazeler ve uygun her senaryoyu (kırılım, geri çekilme, destekten
  tepki) **ayrı ayrı** kaydeder. Takip listesindeki hisse için haber şartı yoktur; fiyat verisi sorunluysa ya da
  likidite çok düşükse senaryo üretilmez (nedeni yazılır).
- **Bekçi kendisi izler** (siz görev vermezsiniz). Halley açıkken arka planda çalışır:
  - **Seans içinde ~5 dakikada bir** (Yahoo verisi ~15 dakika gecikmeli): fiyatın giriş seviyesine gelmesi, kırılım
    denemesi, SL / TP1 / TP2'ye değmesi, hacim artışı. Bunlar "gün içi, kapanışla teyit edilmedi" diye yazılır.
  - **Kapanıştan 20 dakika sonra** (günlük mum kesinleşince): giriş gerçekleşti, kırılım teyidi, TP1, TP2, SL,
    başabaş stop, süresi doldu / geçersiz, alt fitil + yükselen kapanış teyidi, destek / direnç kırılımı, hacim
    artışı, trend değişikliği, yeni senaryo. Halley o saatte kapalıysa, açıldığı ilk anda yapılır.
  - Tatil ve yarım günler hesaba katılır. **Fiyat verisi gelmezse ya da eskiyse olay üretilmez** (sahte sinyal yok).
  - Aynı olay **bir kez** bildirilir. İnternet kesilirse bildirim 24 saat içinde yeniden denenir.
- **Bildirim ayarları (⭐ Takip Listem):** her hisse için bildirim türlerini seçin (ör. yalnız giriş, SL ve TP);
  her senaryonun **Bildirim** düğmesiyle yalnız istediğiniz senaryoyu açık bırakın. Genel aç/kapa: ⚙️ Ayarlar →
  "Takip listemdeki hisselerin bekçi olaylarını gönder".
- **Takipten çıkarmak:** yeni bildirimler durur; senaryolar, olaylar ve sonuçlar **silinmez**.
- Sabah/akşam analizi Telegram özeti de artık yalnız takip listenizdeki hisseleri yazar (gerçek işlemleriniz her
  zaman yazılır); diğer hisselerin sayısı belirtilir.
- **Takip senaryolarının sonuçları** tablosu strateji türüne göre TP1 / TP2 / SL oranlarını gösterir; 30'dan az
  örnekte oranlar güvenilir değildir.
- Bekçi **Halley kapalıyken çalışmaz.** Takip için Halley'i açık bırakın (pencereyi küçültmek yeterli).

## Telegram bildirimi (⚙️ Ayarlar → 📨 Telegram bildirimi)

Sabah ve akşam analizi bitince özet Telegram'a gelir: önerilen senaryolar (giriş, SL, TP1, TP2, risk), takip
listesi, stopa yaklaşan işlemler, girişi gerçekleşen / TP1'e ulaşan / kapanan işlemler, akşam BIST 100 ve kaçırılan
fırsat sayısı. **Ücretsizdir**, yapay zekâ kullanmaz, emir vermez.

1. Telegram'da **@BotFather**'ı açın, `/newbot` yazın, bota bir ad ve sonu `bot` ile biten bir kullanıcı adı verin.
   Size uzun bir **bot anahtarı** verir (`123456789:ABC...`). Bu anahtarı kimseyle paylaşmayın.
2. Halley'de **⚙️ Ayarlar → Telegram kurulumu**: anahtarı yapıştırın → **💾 Bot anahtarını kaydet**.
3. Bildirim alacak **herkes** Telegram'da yeni botunuzu arayıp açsın ve **/start** yazsın. Birlikte almak için
   botu bir Telegram grubuna da ekleyebilirsiniz (sonra grupta bir mesaj yazın).
4. **🔍 Alıcıları bul** → listeden kişileri/grubu seçin → **💾 Alıcıları kaydet**. Bildirim kendiliğinden açılır.
5. **📨 Deneme mesajı gönder** ile kontrol edin.

- Bildirim yalnız **🌅 Sabah analizi** ve **🌙 Akşam analizi** düğmesine basıldığında gider (Halley kapalıyken
  kendiliğinden analiz yapmaz). Açıp kapatmak: "Sabah ve akşam analizi bitince özetini Telegram'a gönder" düğmesi.
- Gönderilemezse analiz yine tamamlanır, rapor kaydedilir; panelde sarı uyarı çıkar.
- Bot anahtarı yalnız bu bilgisayarda (.env) durur; **veri aktarma dosyasına girmez**. Yeni bilgisayarda aynı anahtarı
  yeniden girip alıcıları bulun (aynı botu iki bilgisayar da kullanabilir).

## Başka bilgisayara taşımak (⚙️ Ayarlar → 💾 Veri ve gelişmiş)

1. **Eski bilgisayarda:** **📦 Veri dosyasını hazırla** → **⬇️ Veri dosyasını indir**. `halley_veri_….zip` dosyası
   İndirilenler klasörüne kaydedilir (haberler, analizler, fiyatlar, işlem günlüğü, raporlar, pilot, ayarlar).
2. Dosyayı USB ile yeni bilgisayara taşıyın. Yeni bilgisayara Halley'i **Halley_Kurulum.exe** ile kurun.
3. **Yeni bilgisayarda:** Halley'i açın, OpenAI API anahtarını girin → **⚙️ Ayarlar → 💾 Veri ve gelişmiş → İçe aktar**:
   dosyayı seçin, özeti kontrol edin, **Anladım** kutusunu işaretleyip **📥 İçe aktar** deyin.
- API anahtarı dosyaya girmez; her bilgisayarda ayrı girilir. İçe aktarmadan önce o bilgisayardaki veriler
  `data\yedek` klasörüne otomatik yedeklenir. Bozuk ya da değiştirilmiş dosya içe aktarılmaz.

## Bilinmesi gerekenler

- Fiyatlar Yahoo'dan gelir ve gecikmelidir; gün içinde son mum yarım olabilir (panel "yarım veri" uyarısı verir).
- Teknik kurallar tek başına avantaj sağlamaz (geçmiş testte ölçüldü); asıl katkının haberden gelip gelmediği,
  biriken sanal işlemlerle zamanla görülecek. **Örnek az iken oranlar güvenilir değildir** (panel bunu yazar).
- **Kaçırılan fırsatlar** ancak bekçi o gün çalıştırıldıysa ve sonrasında 5 işlem günü geçtiyse tam değerlendirilir.
- Bir hata mesajı görürseniz (ör. "adresine bağlanılamadı") internet bağlantısını kontrol edip birkaç dakika sonra
  yeniden deneyin. KAP çok sık isteğe sınır koyar; okuyucu bunu kendisi bekler.
