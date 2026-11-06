# Proje notları

## Kararlar (2026-11-06)
- Vade: birkaç günlük / haftalık swing.
- Emir: aracı kurum API'si yok. Uygulama sadece analiz ve öneri üretir, emirler Midas'tan elle girilir.
  Bu yüzden planın Faz 6'sı (otomatik emir) çıkarıldı.
- Yapay zekâ: OpenAI (ChatGPT) API.
- Kullanıcı Python bilmiyor. Arayüz basit, modern ve çift tıkla açılır olmalı; tasarımı kullanıcı çıktıya bakarak yönlendirecek.
- Hisse evreni: varsayılan olarak KAP'taki tüm şirketler, `data/universe.txt` ile daraltılabilir.

- Model: iki aşamada da gpt-5-mini (kullanıcının açık isteği).
- Maliyet sıkılaştırması (2026-11-06, ilk gerçek çalıştırma 400 bin token):
  - Rutin KAP konuları (devre kesici, finansal rapor kapağı vb.) yapay zekâya gitmiyor → `config.KAP_SKIP_SUBJECTS`.
  - "Pay Alım Satım Bildirimi" kullanıcının isteğiyle takipte (atlama listesinden çıkarıldı). Analiz talimatına
    yönetici/ortak alımı = hafif +, satışı = hafif − kuralı eklendi.
  - KAP PDF ekleri okunuyor: ana metni 800 karakterden kısa ve PDF eki olan bildirimlerde ilk 2 PDF'nin
    metni (pypdf) analize ekleniyor (`kap._attachment_texts`). İşlem yönü/miktarı böylece görülüyor.
    Taranmış (resim) PDF'ler ve Excel ekleri henüz okunmuyor.
  - Kalan KAP özel durum açıklamaları ön elemeyi atlayıp doğrudan analize gidiyor (ön eleme bunları fazla katı eliyordu).
  - Ön eleme sadece RSS için; daha sıkı talimat + `reasoning_effort=minimal`.
  - Aynı gün için tahmini kullanım ~80 bin token (yaklaşık %80 daha az).

## Doğruluk optimizasyonu (2026-11-06)
- **Finansal raporlar:** KAP Excel dışa aktarımından (`/tr/api/notification/export/excel/<id>`) gelir tablosu + bilanço özeti. Yüzde değişimleri kod hesaplıyor (`financials.py`).
- **Ekler:** Metin kısa olduğunda ya da "ekte/sunum" dediğinde PDF ekler okunuyor (en fazla 10 sayfa).
- **Haber siteleri:** Ön elemeyi geçen haberlerin tam metni okunuyor (trafilatura). RSS sadece kısa özet veriyordu; beklenti/konsensüs bilgisi tam metinde.
- **Şirket büyüklüğü:** Piyasa değeri ve son fiyat (yfinance, günlük önbellek) yapay zekâya veriliyor.
- **İkinci görüş:** Etkisi ≥3 ya da güveni düşük yönlü kararlar ikinci, bağımsız bir analizle kontrol ediliyor. Yön çelişirse nötrleniyor; etkide anlaşamazlarsa küçük olan alınıyor. Panelde ✅/⚠️ olarak görünüyor.
- **Çift sayım:** Aynı hisse + aynı olay türü 2 gün içinde birden çok kaynaktan gelirse en güçlüsü sayılıyor (içeriden alım-satım hariç).
- **Doğrulama:** KAP bildirimini yapan şirket her zaman listede yer alıyor; model yorum yapmazsa "yorumsuz ⚠️".
- Analizde `reasoning_effort=high`. Bugünkü 54 haber: ~294 bin token, ~7 dakika.
- Sınır: İkinci görüş aynı modelden geliyor; rastgele hataları yakalar, modelin sistematik yanılgısını yakalamaz. Asıl kalibrasyon için backtest (Faz 4) gerekli.

## Fazlar
| Faz | Durum |
|---|---|
| 0 Kapsam ve altyapı | ✅ prototip |
| 1 Veri toplama (KAP, RSS, fiyat) | ✅ prototip |
| 2 LLM analiz (iki aşama, yapılandırılmış çıktı) | ✅ prototip |
| 3 Skorlama ve sinyal | 🟡 basit sürüm var, kalibre edilmedi |
| 4 Backtest ve paper trading | 🟡 bütçeli olay pilotu var; tam kalibrasyon ve paper trading yapılmadı |
| 5 Arayüz | 🟡 Streamlit paneli var |
| 6 Emir | ❌ gerek yok (Midas'tan elle) |

## Dipnotlar ve koddaki karşılıkları
1. **Hisse listesi:** Endeks bileşimi değişir, backtest'te o tarihteki liste kullanılmalı (survivorship bias). → `data/universe.txt`
2. **KAP erişimi:** Resmi API yok, sitenin uç noktaları okunuyor. KAP hızlı isteklerde HTTP 429 veriyor; 1 sn bekleme ve yeniden deneme var. → `kap.py`
3. **Hisse eşleme:** Takma adlar ve büyük harfli kodlar yakalanıyor, LLM'in eklediği kodlar evrende yoksa atılıyor. Zıt yönlü etki destekleniyor. → `universe.py`, `aliases.csv`
4. **LLM tutarlılığı:** temperature=0 (model destekliyorsa), sabit ölçek, örnekli prompt, her haber bir kez analiz ediliyor. → `analyzer.py`
5. **Ağırlıklar:** Yarılanma süreleri ve eşikler tahmin; backtest ile belirlenecek. → `report.py`
6. **Geçmiş haber verisi:** Geçmiş KAP arşivi çekilebilir (`collect --days N`, aynı yıl kısıtı kodda çözülüyor). Toplu analizde OpenAI Batch API düşünülmeli.
7. **Look-ahead bias:** `effective_date`: 18:00 sonrası veya hafta sonu gelen haber ertesi iş gününe sayılıyor. Tatiller henüz yok. LLM'e yayın tarihinden sonraki bilgiyi kullanmaması söyleniyor.
8. **Arayüz:** Streamlit. → `app.py`, `baslat.bat`
9. **Broker API:** Yok, emirler Midas'tan elle.
10. **Güvenlik:** Anahtar `.env` dosyasında tutuluyor ve `.gitignore`'da.

## Ek riskler
- Bireysel sistem saniyeler içindeki ilk fiyat tepkisini yakalayamaz; orta vadeli etkiye odaklanılmalı.
- Öneriler yalnızca kişisel kullanım için. Başkalarına tavsiye vermek SPK lisansı gerektirir.
- KAP "Finansal Rapor" ana metni rakam içermiyor; HTML tablo dışa aktarımından özet okunuyor (`financials.py`).
  Resim PDF ve genel Excel ekleri ayrı bir eksik olmaya devam ediyor.

## Doğruluk / düşük maliyet ve Faz 4 pilotu (2026-11-06)

Kullanıcı doğruluğu önceliklendirdi; model gpt-5-mini kalacak ve gider düşük tutulacak.
Önerilen altyapı + en fazla 5 USD pilot kapsamına devam edildi. Geniş çalışma ayrı onay gerektirir.

### Günlük akışta düzeltmeler
- **Kritik veri kaybı:** `fetch_missing_bodies` altı saatten eski kayıtları metin çekmeden boş gövdeyle
  analize bırakıyordu. Bu kestirme kaldırıldı; boş metin bekler, başlıkla sessiz analiz yapılmaz.
  Eski kestirmenin henüz analiz edilmemiş kayıtları yeniden metin çekimine alınır.
  Önceki sürümde metinsiz analiz edilmiş KAP kayıtları silinmez/yeniden ücretlendirilmez;
  skora katılmaz, panel bunların sayısını uyarır. Sonradan ayrıca gözden geçirilmelidir.
- **KAP liste tamlığı:** gerçek aylık sorgu 2000 kayıt döndürdü. Bu sınıra ulaşan aralıklar ikiye bölünür;
  tek gün hâlâ sınıra ulaşıyorsa tamlık doğrulanamadığı için işlem durur. Liste POST isteklerine de
  1.5 sn bekleme ve 429 yeniden deneme eklendi. Eylül 2026 yeniden sorgusu 7606 kayıt döndürdü.
- Etki 1–5 ve güven 0–1 şema sınırlarıyla doğrulanır. Her şirket/dönem için TMS 29 varsayımı kaldırıldı.
- Önceden kaydedilmiş analizler otomatik yeniden ücretlendirilmez. Skor eşikleri ve yarılanma süreleri değiştirilmedi.

### Pilotun kapsamı ve maliyet koruması
- `backtest.py` + `backtest_ui.py`; panelden belge → fiyat → ücretli analiz akışı.
- Ayrı `data/backtest/pilot.db`; klasör, istek kayıtları ve tüm veriler Git dışında.
- 100/200 KAP bildirimi, kimliklerinin sabit hash sırasıyla seçilir. Bu örnek tam günlük skor oluşturmaz.
- PDF dışı/okunamayan/kesilmiş ekler, eksik finansal özet ve kısa/uzun metinler işaretlenir;
  sorunlu belgeye ve 10 işlem günlük fiyatı olmayan olaya ücretli analiz yapılmaz.
- Bugünkü piyasa değeri ve güncel şirket listesi kullanılmaz. İhraççı kodları eski bildirimden alınır.
  Bu, tarihsel kotasyon listesinin doğrulanmasının yerini tutmaz. Dolaylı etkiler pilot dışındadır.
- Yüksek düşünme ve büyük/belirsiz etkiye ikinci görüş korunur. Her iki görüşün ham yanıtı ayrı saklanır.
- Önbellek anahtarı: belge/mesaj, talimat, model, şema, düşünme ayarı, çıktı sınırı, bildirim ve görüş.
  İlk yanıt önbelleği ikinci görüş sayılmaz. Belge denetim hash'i analiz öncesi tekrar kontrol edilir.
- Güncel 1 USD tavan (ilk sürümde 5 USD) tüm pilot veritabanına uygulanır; tarih değişimi/panel açılışıyla sıfırlanmaz.
  Çağrıdan önce ihtiyatlı girdi+çıktı maliyeti ayrılır, gerçek kullanım gelince kesinleşir.
  SDK otomatik yeniden denemeleri kapalıdır; bağlantı kopması/yarım yanıtta rezerv tutulur ve
  otomatik ücretli tekrar engellenir. Çıktı sınırı 16000 token; kesilme başarı veya nötr sinyal sayılmaz.
  Belirsiz çağrıların tekrar açılması geliştiricinin kullanım kaydını incelemesini gerektirir.
- Hesap varsayımı: 1M girdi 0.25 USD, çıktı (düşünme dahil) 2 USD; önbellek indirimi sayılmaz.
  Kaynak: https://developers.openai.com/api/docs/models/gpt-5-mini (2026-11-06).
  Bu ilk pilot standart API kullanır; Batch henüz uygulanmadı.

### Sonuçların anlamı ve kalan işler
- Yayın gününden sonraki ilk endeks işlem günü açılışı → giriş dahil 1/3/5/10. işlem günü kapanışı.
  Alış+satış maliyeti senaryosu, endekse göre fark ve dönem içindeki en düşük fiyat gösterilir.
  Negatif olayda açığa satış kârı hesaplanmaz. Eksik fiyat ileriki güne kaydırılmaz ve tabloda korunur.
- Tarihsel evren, resmi tatil/yarım gün takvimi ve yfinance fiyat düzeltmeleri bağımsız doğrulanmadı.
  Endeks fiyat tarihleri takvim vekili; veri eksikleri tatille karışabilir. Ham/özsermaye işlemi
  düzeltmeleri ve gerçek uygulanabilir alış fiyatı ayrıca doğrulanmalı.
- Eksik belge/fiyat nedeniyle dışarıda kalanlar, modelin geçmiş olay bilgisi, aynı hisseye ait yakın
  haberler ve örtüşen vadeler yanlılık yaratabilir. Betimleyici oranlar bağımsız işlem başarısı değildir.
- **Tam Faz 4 bitmedi:** tarihli şirket büyüklüğü, doğrulanmış evren/takvim, tam haber penceresi,
  birleşik skorun tarih tarih yeniden kurulması, zaman sıralı kalibrasyon/doğrulama/final dönemleri,
  bölüm sınırlarında 10 günlük sonuç taşmasını engelleme ve ileriye dönük takip gerekiyor.
- Yetersiz örnekte eşik seçilmeyecek. Test edilen eşik ailesi küçük tutulacak; son dönem tekrar tekrar
  ayar yapmak için kullanılmayacak. Geniş veri/model çalışması öncesi yeni maliyet sunulacak.

### Doğrulama
- Python 3.9.13 ortamında ücretsiz `unittest` regresyonları ve Streamlit AppTest kullanılıyor.
- **32 ücretsiz test geçti:** günlük collect → dry-run → sahte model analizi → report akışı,
  eski/boş metin kurtarma ve skordan çıkarma, liste sınırı, 429, PDF/Excel/kesilme,
  belge hash'i, önbellek/ikinci görüş, bütçe/bağlantı hatası, eksik fiyat/tarih ve
  boş/dolu Streamlit pilot ekranı. `compileall` Python 3.9 ile başarılı.
- **Gerçek veri kontrolü:** 1–30 Eylül 2026, 7606 KAP kaydı, atlama/ihraççı kuralları sonrası
  2563 uygun kayıttan 100 örnek. KAP 429 nedeniyle ikinci hazırlık turu durdu:
  27 belgenin denetimi temiz, 7 belge sorunlu, 66 belge henüz denetlenmedi.
  yfinance yenilemesi 3750 OHLC satırı verdi; 12 olayın 10 işlem günlük fiyat kapsamı eksik.
  Hem belge hem fiyatı hazır 26 olay var. Eksik kodlar otomatik 'borsadan çıktı' sayılmadı;
  veri kaynağı kodu desteklemiyor da olabilir. Günlük veritabanına gerçek veri yazılmadı.
- **Hazırlık tamamlanmadı:** KAP engeli kalkınca panelden 'Belgeleri hazırla / eksikleri yeniden dene'
  ile sürdürülmeli, sonra fiyatlar yenilenmeli. Mevcut tam belgeler yeniden indirilmez.
- Çalışma kopyasında API anahtarı yok; gerçek model çağrısı, ücret ve getiri başarısı henüz ölçülmedi.
  API testleri sahte istemciyle bütçe/önbellek/hata davranışını doğrular; model kalitesini doğrulamaz.

## Kullanıcının ek maliyet kısıtı (2026-11-06)
- Kullanıcı pilotun olabildiğince ucuz olmasını istedi. Toplam tavan **5 USD'den 1 USD'ye** indirildi.
  Önceki harcama ve belirsiz çağrı rezervleri korunur; limit altında yeni alan açmak için geçmiş silinmez.
- Her düğme basışında / analiz çağrısında **en fazla 10 hazır bildirim** işlenir; sonraki grup otomatik başlamaz.
  Bu sınır arka uçta da uygulanır. Daha küçük tur istenebilir, 10'dan büyük tur reddedilir.
- gpt-5-mini, high düşünme, mevcut ikinci görüş koşulları, metin sınırları ve belge/fiyat denetimi korundu.
  Harcama analizi kısarak değil, küçük turlarla ve mevcut önbellekle kontrol ediliyor.
- 10 olayla başarı oranı veya eşik kalibrasyonu yapılmaz; küçük tur yalnızca akış ve analiz denetimi içindir.
- Bu değişiklikte ücretli çağrı başlatılmadı. Yeni limitin uygulanması için açık panel yeniden başlatılmalı;
  daha önce başlamış bir çağrı yeni sürüm tarafından geriye dönük durdurulamaz.
- Doğrulama: Python 3.9 üzerinde **35 ücretsiz test geçti**. Yeni kontroller 11 hazır olayda ilk turun
  10'da durmasını, sonraki turun kalan 1 olayı işlemesini, ikinci görüş/high ayarının korunmasını,
  eski 1 USD üzeri kullanımın silinmeden yeni çağrıyı engellemesini ve büyük tur isteğinin reddini kapsar.

## Pilot indirmeleri düzeltmesi (2026-11-06)
- Kullanıcının `halley_pilot.csv` dosyası başarıyla indirilmiş: 10 farklı bildirim × 4 vade = 40 satır,
  fiyat sonucu eksik satır yok. Eski indirme düğmesi yalnızca ana sonuçları içeriyordu;
  pozitif özet ve belge eksikleri için indirme eklenmemişti.
- `pilot_export.py` ile ekrandaki özet ve indirmeler aynı veri kaynağından oluşturuluyor.
  Dört çıktı: `halley_pilot.csv`, `halley_pozitif_ozet.csv`, `halley_belge_eksikleri.csv`, `halley_yontem.txt`.
  Ayrı indirme düğmeleri ve tümünü içeren ZIP düğmesi eklendi. CSV'ler UTF-8 BOM içerir;
  özetin vade alanı CSV'de de korunur. Boş tabloda bile sütun başlıkları indirilir.
- Belge listesinde yinelenen note/JSON sütunları yerine bildirim, başlık ve okunur eksik açıklaması var.
  Denetlenmemiş belge açıkça belirtilir. Sonuçlardaki eksik sayısı ile belge eksikleri ayrımı panelde/yöntemde yazılı.
- İndirme ve paketleme yalnızca yerel hesaplama yapar; model, bütçe, 10 bildirim sınırı ve analizler değişmez.
  Kullanıcının CSV'si ve oluşturulan gerçek raporlar GitHub'a eklenmez.

## BloombergHT / Uzmanpara canlı haber akışı (2026-11-06)
- Kullanıcı KAP dışında BloombergHT ve Uzmanpara haberlerinin de alınmasını istedi.
- BloombergHT zaten tanımlıydı; yönlendirdiği doğrudan adres ayarlandı:
  `https://www.bloomberght.com/rss/tum-haberler.xml`.
  Uzmanpara eklendi: `https://uzmanpara.milliyet.com.tr/haber_rss/`.
  Kamuya açık iki akış gerçek HTTP isteğinde 200 verdi; ilk kontrolde 50 ve 20 haber ayrıştırıldı.
  Diğer mevcut kaynaklar korunur. RSS ön eleme, tam metin alma, hisse eşleme ve tekrar eleme akışı ortak.
- RSS içindeki content:encoded alanı özetten daha ayrıntılıysa saklanır. Tarihsiz habere bugünün tarihi
  uydurulmaz; ileri tarihli kayıt da işlenmez. Geçersiz/HTML dönen akışın hatası görünür, diğer kaynak sürer.
- Panelde son taramanın kaynak bazında görülen/yeni/tarih sorunlu kayıt sayıları ve hata durumu görünür.
- Ek kaynakların kontrolsüz analiz gideri yaratmaması için panelde günlük güncelleme başına 1/3/5/10 haber
  seçilir, varsayılan 10. KAP ve RSS birlikte bu adede dahildir; kalanı bekler. Arka uç 10 üzerini reddeder.
  Bu günlük akışta adet sınırıdır; 1 USD bütçe yalnızca pilotta geçerlidir. Komut satırı analyze akışı değişmedi.
- RSS listeleri tarihsel arşiv değildir. Yayın anındaki metin ve kapsamı doğrulanmadan geçmiş KAP pilotuna
  eklenmez; yeni kaynaklar canlı haber akışı içindir. Model ve kalite ayarları değiştirilmedi.
- **Saat tuzağı:** Uzmanpara RSS'sinde yerel saat GMT etiketiyle görünebiliyor. Yayın zamanı her yeni
  Uzmanpara haberinde kendi sayfasındaki açık saat dilimli datePublished meta alanından doğrulanır.
  Tahminen üç saat çıkarılmaz; doğrulanamayan/çelişen/saat dilimsiz tarih işlenmez. dateModified kullanılmaz.
- **Son doğrulama:** Python 3.9 üzerinde **50 ücretsiz test geçti**. ZIP/CSV içerikleri, Türkçe karakterler,
  boş tablolar, fiyat eksiği/belge eksiği ayrımı, beş indirme düğmesi, yeni kaynaklar, tekrarlar,
  tarih doğrulaması ve günlük analiz sınırı kapsandı. Python 3.9 derleme kontrolü de başarılı.
- Gerçek iki kaynaklı toplamada BloombergHT 50 kayıt, Uzmanpara 20 kayıt verdi; 1 tekrar elendi,
  19 Uzmanpara kaydı yayın sayfasından doğrulanmış saatle kaydedildi. Bu kontrol geçici bellekte yapıldı.
  Birer tam metin örneği 2756 ve 792 karakter olarak alınabildi. Başka haberlerde erişim başarısı garanti değildir.
- Kullanıcının 40 satırlık CSV'siyle ve mevcut 22 belge eksiğiyle dört dosyalı gerçek ZIP hazırlandı,
  arşiv bütünlüğü doğrulandı. Gerçek CSV/raporlar yalnızca çalışma alanındaki outputs klasöründedir.
  Bu çalışmada yeni ücretli model çağrısı veya günlük veritabanına gerçek haber yazımı yapılmadı.

## Claude'a devir (2026-11-06)
- Kullanıcı projenin Claude'a aktarılması için depoda bir devir belgesi ve sohbetten başlangıç promptu istedi.
  `DEVIR.md` eklendi; README'nin devam edecek kişi bölümünden bağlantı verildi.
- Devir; güncel 1 USD pilot bütçesini, günlük adet sınırının dolar tavanı olmadığını, 50 testin kapsamını,
  gerçek veride yapılan/yapılmayan kontrolleri, son raporları, RSS saat tuzağını ve tam Faz 4'ün eksiklerini kapsar.
- Önceki hazırlık notlarındaki "API anahtarı yok / pilot henüz çalışmadı" tarihsel bir gözlemdir.
  Kullanıcı daha sonra anahtarı bağladı ve 10 bildirimlik / 40 satırlık gerçek pilot çıktısı paylaştı.
  Bu dosyadaki ilk hazırlığa ait sayaçlar ve sıfır harcama ifadeleri güncel kullanım defteri yerine geçmez.
- Claude geliştirici asistan olacak; uygulamanın API modeli gpt-5-mini kalacak.
  Yalnızca dokümantasyon değiştirildi; yeni model çağrısı başlatılmadı.

## Claude incelemesi: mevcut pilot çıktısı, ücretsiz (2026-11-06)

Yeni model çağrısı yapılmadı ve kod değiştirilmedi. Kullanıcının yerel `pilot.db` dosyası kopyalanarak
salt okunur incelendi; CSV/rapor dosyaları depoya eklenmedi. GitHub'daki güncel kodla 50 test bu makinede de geçti.

### Maliyet defteri
- 11 çağrı (10 ilk görüş + 1 ikinci görüş), hepsi `done`; açık/belirsiz rezerv yok.
- Toplam harcama ≈ **0.081 USD** (1 USD tavanın ~%8'i). Bildirim başına ortalama ≈ 0.008 USD.
- Kalan 68 temiz belgenin hepsi analiz edilirse kabaca +0.55 USD (toplam ≈ 0.64 USD) tahmin ediliyor;
  bu tahmin belge uzunluğu ve ikinci görüş sıklığına göre değişir.

### Fiyat hesapları: doğrulandı
- 40 satırın tamamı ham `pilot_bars` verisinden bağımsız olarak yeniden hesaplandı; giriş/çıkış tarihleri,
  brüt/net getiri, endekse göre fark ve dönem içi en düşük değer **birebir** tuttu (0 fark).
- `endekse_göre_%` = **net** getiri (%0.2 maliyet düşülmüş) − endeks getirisi. Yöntem metninde açıkça yazılmalı.
- Büyük 10 günlük düşüşler (−%15…−%41) bölünme/bedelsiz düzeltme hatası değil; gerçek ardışık düşüşler.
- **Yeni risk:** Bazı günlerde açılış = en yüksek = en düşük = kapanış (tavan/taban kilidi; örnekte 2 olayda
  9 gün). Bu günlerde fiilen alım/satım yapılamamış olabilir. Backtest şu an bunu işaretlemiyor;
  kilitli giriş/çıkış günü olan sonuçlar "uygulanamaz olabilir" diye işaretlenmeli.

### Model yorumlarının belgeyle karşılaştırılması (10 olay, el ile)
- 6 olay makul (rutin bildirimlere nötr/küçük etki).
- **Yön veren 5 karardan 4'ü sorunlu.** Tekrarlayan hata türleri:
  1. **Güncelleme bildirimi:** Eski olumsuz olay (sözleşmenin askıya alınması) yeni bilgi gibi yeniden
     cezalandırıldı; yeni bilgi aslında yenileme görüşmelerinin başlamasıydı.
  2. **Kümülatif ve dönemsel rakam karışması:** Aylık rutin satış raporunda, yıllar içinde biriken toplam
     tutar yeni haber gibi büyük pozitif (etki 3) sayıldı; asıl yeni bilgi yalnızca bir aylık satıştı.
  3. **Finansal sıkıntı sinyalini kaçırma:** "Finansal yükümlülüklerin yerine getirilmesini teminen"
     yapılan işten çıkarma, maliyet tasarrufu diye pozitif yorumlandı; metin sıkıntıya işaret ediyordu.
  4. **Şirket büyüklüğü bilgisi yok:** Çok büyük bir şirketin küçük bir uzlaşma tutarı, bir soruşturmanın
     ihlalsiz kapanmasına rağmen negatif etki 2 aldı. Pilot bilerek güncel piyasa değeri kullanmıyor.
- Bu 10 olay ve el ile yapılan değerlendirme istatistiksel kanıt değildir; ama hata türleri somut ve düzeltilebilir.

### Belge eksikleri (22) ve seçilim yanlılığı
- Sorun türleri: PDF metni uzun (11), okunamayan sayfa (10), ek sayısı sınırı (7), sayfa sınırı (5),
  analiz metni sınırı (4), PDF hiç okunamadı (2), metin yok (1). Bir belgede birden çok sorun olabilir.
- Önem sınıflaması (konuya göre):
  - **Önemli, mutlaka okunmalı:** Pay alım teklifi (2) ve birleşme (3).
  - **Orta:** Pay geri alım (4), olağanüstü genel kurul (4), değerleme raporu (1), bedelsiz tadil (1).
  - **Düşük/rutin:** Bilgilendirme politikası, esas sözleşme, haftalık rapor, ihraç tavanı (2), izahname ekleri (2).
- **Yanlılık:** Önemli olaylar uzun belgeli olduğu için eksik listesinde yoğunlaşıyor. Pilot bu hâliyle rutin
  bildirimlere kayıyor; sonuçlar "tüm önemli haberler" için geçerli sayılmamalı.
- Örneğin %22'si pay geri alım bildirimi, %5'i borsa yatırım fonu piyasa yapıcılığı (tamamen rutin;
  analiz edilen 10'un 2'si bu türdendi, ücret boşa gitti).

### Önerilen düzeltmeler (onay bekliyor, henüz uygulanmadı)
Hepsi ücretsiz kod değişikliği; gpt-5-mini, high düşünme ve ikinci görüş korunur.
1. **Talimat:** Güncelleme/düzeltme bildirimlerinde yalnızca önceki açıklamaya göre yeni bilgiyi değerlendir;
   kümülatif değil dönemsel rakama odaklan; finansal sıkıntı ifadelerini negatif işaret say.
2. **Rutin konu atlama:** "Piyasa Yapıcılığı Kapsamında Gerçekleştirilen İşlemler", "Likidite Sağlayıcılık",
   "Bilgilendirme Politikası", "Haftalık Rapor", "Sürdürülebilirlik Raporu" vb. hem günlük akışta hem pilotta atlansın.
3. **İngilizce tekrarını çıkar:** KAP metinlerinin çoğu Türkçe + İngilizce çeviri; çeviri kısmı atılırsa metin
   yaklaşık yarıya iner, bilgi kaybı olmaz, uzunluk sınırı sorunlarının bir kısmı ücretsiz çözülür.
4. **Ek seçimi:** Hazirun, vekaletname, imza sirküleri gibi ekler isimden tanınıp atlansın; ek sayısı
   sınırı önemli eklere kalsın. Yalnızca son sayfa (imza/kaşe) okunamıyorsa engelleme yerine uyarı.
5. **Tarihli şirket büyüklüğü:** Olay tarihindeki fiyat (pilot_bars) × o tarihteki pay sayısı ile yaklaşık piyasa
   değeri; pay sayısı kaynağı (KAP sermaye bilgisi) ayrıca doğrulanmalı.
6. **Kilitli gün işareti:** Tavan/taban kilidi olan giriş/çıkış günleri sonuç tablosunda işaretlensin.
- Bu düzeltmeler önceki 10 analizi değiştirmez (önbellek). Etkisini görmek için aynı 10 olayın yeniden analizi
  ~0.08 USD tutar ve yalnızca kullanıcı onayıyla yapılmalı. Eşikler hâlâ değiştirilmemeli.
