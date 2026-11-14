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
- **Yeni sürüme güncellemek:** yeni **Halley_Kurulum.exe**'yi çalıştırın. Halley kuruluysa program bunu görür ve
  **Güncelle** der (yeniden kurmaz, aynı klasörün üstüne yazar, kısayollar çoğalmaz). Açık Halley kendiliğinden
  kapatılır. **Verileriniz silinmez:** haberler, analizler, işlem günlüğü, takip listesi, ayarlar ve API/Telegram
  anahtarları korunur; güncellemeden önce ayrıca `app\data\yedek\guncelleme_oncesi_…` klasörüne yedeklenir (son 3
  yedek tutulur) ve güncellemeden sonra denetlenir. Aynı sürüm zaten kuruluysa "zaten güncel" der.
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
| **📊 Dashboard** | Tek bakışta: BIST 100, olumlu/olumsuz haber sayısı, **✅ hazır fırsatlar** (önce), bekleyen fırsatlar, piyasa durumu, bekçi durumu ve son olaylar, takip listenizdeki aktif senaryolar, açık işlemler, önümüzdeki 15 işlem gününün piyasa takvimi. |
| **🎯 Fırsatlar** | Önce **✅ Hazır Fırsatlar** (tam işlem planı kartları, yapay zekâ haber kontrolü düğmeleri), altında **⏳ Bekleyen Fırsatlar**: haberi olan hisseler (olumlu / olumsuz / zayıf), haber skoru ve teknik durum. Her satırda **🔍 Analiz** (ayrıntı ekranı) ve **➕ Takibe Al**. Detaylı listeyi CSV olarak indirme. |
| **🔍 Hisse Analizi** | Seçilen hissenin tüm analizi: giriş senaryoları (kırılım, geri çekilme, destekten tepki), referans senaryo, teknik göstergeler, sektör, bilanço ve şirket takvimi, finansal özet, haberler. Haberi olmayan hissede senaryolar yalnız fiyattan hesaplanır. **➕ Takibe Al** düğmesi burada da var. |
| **⭐ Takip Listem** | Takibe aldığınız hisseler, senaryoları ve durumları, senaryo ve bildirim türü seçimleri, son olaylar, takip senaryolarının sonuçları. |
| **🛡️ Bekçi** | **🌅 Sabah analizi** / **🌙 Akşam analizi** ve yapay zekâ seçenekleri, takip bekçisinin durumu ve tüm olayları (Telegram'a gidip gitmediği), sabah/akşam rapor arşivi (sonradan değişmez; .md ve .json indirilebilir). |
| **📰 Haberler** | 🔬 Haber analizi (bekleyenleri seçerek analiz, derin yeniden inceleme, tahmini maliyet ve bütçe) ve son analiz edilen 50 haber. |
| **📒 İşlem Günlüğü** | Önerilen senaryolar **sanal işlem** olarak izlenir. Gerçekten aldıysanız **✍️ Bu işleme girdim** ile alış günü ve fiyatını kaydedin. Portföy/sektör riski, kayma ölçümü. |
| **🏁 Performans** | **Hazır fırsatların gerçek sonuçları** (ayrı ölçüm), takip senaryolarının strateji türüne göre TP1/TP2/SL oranları; sanal işlemlerin stratejiye, haber kaynağına, olay türüne ve riske göre başarısı; filtre analizi; **onayınızı bekleyen öneriler** (onay hiçbir ayarı kendiliğinden değiştirmez). |
| **⚙️ Ayarlar** | Ayarlar ve 📨 Telegram; **💾 Veri ve gelişmiş** (veri aktarma, durum, 📅 takvim kontrolü, 📥 KAP geçmişi, 🧪 ucuz test, geçmiş veri pilotu); ❓ Kılavuz (bu metin). |

## Fırsat sayısı neden değişir? (🎯 Fırsatlar → üstteki kutu)

- Uygun fırsat listesi kayıtlı veriden **her açılışta yeniden hesaplanır**. Haber skoru haber eskidikçe azalır (1,50'nin
  altına inen hisse listeden çıkar), fiyatlar ve yeni analizler geldikçe senaryolar değişir. Bu yüzden sayı gün içinde
  kendiliğinden değişebilir (ör. 20 → 19).
- Kutuda **son değişiklik** yazar: hangi hisse eklendi, hangisi çıktı.
- **🔄 Fırsatları şimdi yeniden kontrol et**: listeyi elle yeniden hesaplar. "Fiyatları da güncelle" işaretlenirse önce
  olumlu haberli hisselerin fiyatı indirilir (ücretsiz, birkaç saniye).
- **📋 Tüm adaylar — elle kontrol**: olumlu haberli her hisse için ✅ uygun ya da ❌ neden uygun değil, en uygun senaryo
  ve seviyeleri; eşiğin hemen altındaki hisseler; **liste değişiklikleri** tablosu (çıkan hisse ve nedeni).
- Hisse aramaları Türkçe karakterleri tanır: "aksigorta", "sise cam", "şişe" yazmanız yeterli.

## Senaryo kartını okumak

- **Giriş türleri:** *Kırılım* (direnç üstünde kapanış → ertesi gün alım; fiyat alarmı kurun), *Geri çekilme* (yükseliş
  trendinde ortalamaya limit emir), *Destekten tepki* (önceden oluşmuş destek yakınında limit emir).
- **SL** zarar durdur, **TP1/TP2** hedefler. Günlükte TP1'de yarısı satılır, stop girişe çekilir; kalanı TP2'ye.
- **Risk seviyesi** düşük/orta/yüksek; nedenleri kartta yazar (likidite, haberin fiyatlanması, bilanço, temettü,
  makro olay…).
- **İki farklı risk var, karıştırmayın:**
  - **Senaryo riski** (🎯 Fırsatlar, Dashboard, analizde "Senaryo riski"): fiyat gösterilen **giriş koşuluna gelince**
    alırsanız geçerli risk. Halley'in önerdiği plan budur.
  - **Risk (şimdi alınırsa)** (analizde "Mevcut fiyattan girilirse" bölümü): hisseyi **hemen şimdi**, son fiyattan
    alırsanız geçerli risk. Genelde daha yüksektir, çünkü zarar durdur uzak ya da hedef yakın olabilir.
  - Örnek (9 Kasım): AKSGY'de kırılım senaryosu (9,58 TL üstünde kapanınca al) risk **düşük**, ama şimdi 9,12'den almak
    risk **yüksek** (olası kazanç olası zarardan küçük). Çelişki değil; iki ayrı alım planı.
- **"Uygun giriş senaryosu yok"** da bir sonuçtur: koşullar elverişli değildir.
- Haber skoru zamanla azalır (eski haberin etkisi söner); 1,50'nin altında senaryo üretilmez.

## 📒 İşlem Günlüğü nasıl okunur?

- **Ne işe yarar?** Halley'in önerdiği senaryoların gerçekte işe yarayıp yaramadığını **ölçer**. Para yatırılmaz, emir
  verilmez; sonraki günlerin gerçek fiyatlarıyla "bu senaryoya uyulsaydı ne olurdu" hesaplanır.
- **Sanal işlem:** bir hisse fırsatlarda "uygun" görünce Halley en uygun senaryoyu kendiliğinden kayda alır ve izler.
  **Siz almadınız**; bu, Halley'in kendi karnesidir.
- **Gerçek işlem:** Midas'tan gerçekten aldıysanız **✍️ Bu işleme girdim** bölümüne alış gününü ve fiyatını yazın;
  aynı seviyelerle ayrıca izlenir, kendi sonuçlarınız ayrı ölçülür.
- **Durum:** *bekliyor* = fiyat giriş seviyesine gelmedi · *açık* = giriş gerçekleşti · *açık (TP1 görüldü)* = ilk
  hedefe ulaştı, yarısı satıldı sayılır, stop girişe çekilir · *kapandı* = TP2, SL, başabaş ya da 30 işlem günü dolması
  · *iptal* = geçerlilik süresinde giriş olmadı (para kaybı yok).
- **Sütunlar:** *Net %* komisyon ve kayma düşülmüş getiri · *R* kazancın planlanan zarara oranı (+1R = planlanan zarar
  kadar kazanç, −1R = planlanan zarar kadar kayıp). Tablo başlığının üstüne gelince her sütunun açıklaması çıkar.
- **Ölçüler:** kazanma oranı, ortalama net, ortalama R, kâr faktörü (toplam kazanç / toplam zarar; 1'in üstü kârlı),
  maks. düşüş, Sharpe. En az 30 kapanan işlemden önce bu oranlar rastlantı olabilir.

## 🤖 Yapay zekâ kullanımı (⚙️ Ayarlar → 🤖 Yapay zekâ kullanımı)

- Halley'in ana işleri (tarama, teknik analiz, fırsatlar, bekçi, raporlar, Telegram) yapay zekâ kullanmaz. Yapay zekâ
  yalnız sizin başlattığınız işlemlerde çağrılır (🔄 Haberleri güncelle, 📰 Haberler → 🔬 analiz, isteğe bağlı rapor
  yorumu, açtığınız haber kontrolü düğmeleri).
- Bu sekme her çağrıyı gösterir: bugün / bu ay çağrı sayısı ve tahmini maliyet, haber analizi bütçesinden kalan, hangi
  özelliğin ne kadar kullandığı, son 30 günün günlük maliyeti, hatalar ve son 30 çağrı.
- **Aynı haber bir daha ücretlendirilmez:** içeriği (başlık + metin) daha önce analiz edilmiş bir haber farklı numarayla
  gelse de yapay zekâya gönderilmez; haber sitelerinde aynı başlık 3 gün içinde başka siteden geldiyse de tekrar
  sayılır ("Tekrarlanan haber"). Aynı metni iki farklı şirket yayımladıysa ikisi de analiz edilir.

## Ayarlar (⚙️ Ayarlar)

- **Komisyon ve kayma:** Midas'ın gerçek oranını girin; net kâr/zarar buna göre hesaplanır.
- **Sermaye ve işlem başına risk (%):** girilirse kartta kaç adet alınabileceği ve azami kayıp, raporlarda TL
  karşılıkları görünür. 0 bırakılırsa bu hesaplar gösterilmez.
- **Bekçi yapay zekâ yorumu aylık bütçesi ($).**

## ✅ Hazır Fırsatlar (önce bunlar) ve ⏳ Bekleyen Fırsatlar

- **Hazır Fırsat:** giriş koşulu analiz anında **zaten sağlanmış**, son kapanışa yakın fiyattan **ertesi işlem günü
  açılışında** uygulanabilir plan. Dört tür: *Kırılım (gerçekleşmiş)* · *Geri çekilme (bölgede)* · *Destekten tepki
  (başlamış)* · *Mevcut fiyattan*. Şartlar: olumlu haber (skor ≥ 1,50), risk/getiri en az 1:2, teknik skor en az
  5/10, risk seviyesi yüksek değil, fiyat verisi ve likidite sorunsuz. **En fazla 5 hisse; uygun yoksa liste boş
  kalır** (sırf dolsun diye hisse önerilmez).
- **Her planda:** kapanış, giriş aralığı, **azami giriş** (bunun üstünde ALMAYIN), zarar durdur, TP1, TP2,
  risk/getiri, tahmini getiri, tahmini tutma süresi, haber skoru, teknik skor (0–10), risk seviyesi, gerekçe ve
  geçerlilik (yalnız giriş günü).
- **Bekleyen Fırsat:** henüz koşulu oluşmamış senaryolar ("şu seviyeyi kırarsa", "desteğe gelirse"). Ayrı bölümde
  gösterilir; takibe alırsanız bekçi koşulu izler.
- **Akşam analizi** (kapanıştan ~20 dk sonra, Halley açıksa kendiliğinden): ertesi gün için hazır listeyi hazırlar.
  Akşam kaçırılırsa ertesi sabah 09:30'a kadar yapılır; seans başladıysa yapılmaz (yarım gün fiyatıyla liste olmaz).
- **Sabah kontrolü** (08:30–09:55, kendiliğinden): akşam listesini yeniden değerlendirir; akşamdan sonra olumsuz
  haber gelen ya da planı bozulan fırsatı **iptal eder**, seviyeleri güncel veriyle yeniler, yeni uygun çıkan varsa
  ekler (toplam en fazla 5). Açılıştan sonra yapılırsa yeni öneri eklenmez.
- **🤖 Sabah haber kontrolü (varsayılan KAPALI):** açarsanız sabah kontrolü, yalnız hazır listedeki 1–5 hissenin
  akşamdan bu yana gelen KAP haberlerini yapay zekâyla analiz eder (haber başına ~0,013 $, aylık bütçe içinde).
  Kapalıyken yalnız önceden analiz edilmiş haberler kontrol edilir. Ayrıca **"Yeni haberlerini şimdi analiz et"**
  düğmesiyle istediğiniz an bir kez çalıştırabilirsiniz. Düğmeler: 🎯 Fırsatlar → Hazır Fırsatlar ve ⚙️ Ayarlar.
- **Açılış kontrolü** (10:05'ten sonra, kendiliğinden; Yahoo verisi ~15 dk gecikmeli): açılış fiyatı azami girişin
  üstündeyse fırsat iptal edilir ve Telegram'dan "eski fiyattan ALMAYIN" uyarısı gelir; altındaysa "plan geçerli".
  Açılış fiyatı açılıştan önce bilinemez: Midas'ta azami giriş fiyatıyla limitli emir vermek bu riski sınırlar.
- **"🔄 Şimdi yeniden hesapla (kaydetmeden)":** kuralı o an çalıştırıp sonucu gösterir; kaydedilmez, performansa
  girmez. "Neden diğerleri hazır değil?" tablosu her hissenin elenme nedenini yazar.
- **Ölçüm (🏁 Performans):** her önerinin önerildiği fiyat, gerçek giriş (giriş günü açılışı), TP1/TP2/SL sonucu,
  net getiri ve kaç işlem günü sürdüğü ayrı tabloda; bekleyen senaryolardan ayrı ölçülür. Açılış azami girişin
  üstündeyse "giriş olmadı" sayılır.
- Hazır fırsat kuralları **yeni ve henüz sınanmadı**; mevcut eşikler değişmedi. En az 30 kapanmış öneriden önce
  sonuçlar rastlantı olabilir.

## ⭐ Takip Listem ve bekçi

Halley bütün BIST'i taramaya devam eder; ama **Telegram'a yalnız takibe aldığınız hisselerin olayları gider.**

- **Takibe almak:** 🎯 Fırsatlar satırındaki ya da 🔍 Hisse Analizi ekranındaki **➕ Takibe Al** düğmesi ya da **⭐ Takip Listem** ekranında hisse seçip
  **➕ Takibe Al**. Halley o hissenin fiyatını tazeler ve uygun her senaryoyu (kırılım, geri çekilme, destekten
  tepki) **ayrı ayrı** kaydeder. Takip listesindeki hisse için haber şartı yoktur; fiyat verisi sorunluysa ya da
  likidite çok düşükse senaryo üretilmez (nedeni yazılır).
- **Bekçi kendisi izler** (siz görev vermezsiniz). Halley açıkken arka planda çalışır:
  - **Seans içinde ~5 dakikada bir** (Yahoo verisi ~15 dakika gecikmeli): fiyatın giriş seviyesine gelmesi, kırılım
    denemesi, SL / TP1 / TP2'ye değmesi, hacim artışı. Bunlar "gün içi, kapanışla teyit edilmedi" diye yazılır.
  - **Kapanıştan 20 dakika sonra** (günlük mum kesinleşince): giriş gerçekleşti, kırılım teyidi, TP1, TP2, SL,
    başabaş stop, süresi doldu / geçersiz, alt fitil + yükselen kapanış teyidi, destek / direnç kırılımı, hacim
    artışı, trend değişikliği, yeni senaryo. Halley o saatte kapalıysa, açıldığı ilk anda yapılır.
  - **Önemli yeni haber:** işlem günlerinde 08:00–19:30 arası 30 dakikada bir KAP listesine bakılır ve takip
    ettiğiniz hisselerin yeni bildirimlerinin metni okunur (ücretsiz). Analiz edilmiş haberlerden etkisi 3/5 ve üzeri
    olumlu/olumsuz olanlar bildirilir (yalnız hisseyi takibe aldıktan sonra yayımlananlar). **Bekçi yapay zekâyı
    kendiliğinden çağırmaz (varsayılan kapalı):** yeni haberlerin bekçi tarafından otomatik analiz edilmesini
    isterseniz ⚙️ Ayarlar → "yeni KAP haberlerini otomatik analiz et" düğmesini açın (haber başına ~0,013 $, aylık
    haber analizi bütçesi içinde). Kapalıyken haberler 🔄 Haberleri güncelle ya da 📰 Haberler → 🔬 ile elle analiz
    edilir.
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
