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

## İnceleme düzeltmeleri uygulandı (2026-11-06, Claude)

Kullanıcı onayıyla, önceki bölümdeki 1–4 ve 6. öneriler uygulandı. Ücretli model çağrısı yapılmadı.
gpt-5-mini, high düşünme, ikinci görüş, 1 USD pilot tavanı, 10 bildirim sınırı ve 1.5 sn KAP beklemesi değişmedi.
Skor eşikleri ve yarılanma süreleri değiştirilmedi.

- **Talimat (`analyzer.ANALYSIS_PROMPT`):** "Yeni bilgi mi, eski bilgi mi?" (güncelleme/düzeltme bildiriminde
  yalnızca yeni bilgi; dönemsel raporda kümülatif toplam yeni haber sayılmaz), "Finansal sıkıntı işaretleri"
  ve "Şirket büyüklüğü bilinmiyorsa" bölümleri eklendi. Pilot da aynı talimatı kullanır.
  Uyarı: Kurallar aynı 10 olayın incelemesinden çıktı; aynı olaylarla yeniden deneme yalnızca akıl sağlığı
  kontrolüdür, bağımsız doğrulama sayılmaz.
- **Rutin konular (`config.KAP_SKIP_SUBJECTS`):** Piyasa yapıcılığı, likidite sağlayıcılık, bilgilendirme
  politikası, haftalık rapor, sürdürülebilirlik raporu, kurumsal yönetim bilgi formu eklendi. Günlük akış bunları
  analize göndermez. Pilot mevcut seçimi değiştirmeden bu konuları ücret harcamadan atlar
  (`skipped_routine`), kayıtları silmez. Yeniden "Belgeleri hazırla" yapılırsa örnekleme bu konuları dışlar;
  bu, 100'lük örneğin içeriğini değiştirir (önceki analizler veritabanında kalır).
- **İngilizce çeviri temizliği (`textutil.strip_translation`):** KAP HTML metni ve PDF ek metninden İngilizce
  çeviri satırları atılır. Kelime oranına dayanır; Türkçe harfli özel isim içeren İngilizce satırlar da
  yakalanır. Belge tamamen İngilizceyse dokunulmaz. Pilot belgelerinde toplam metin ~%10 kısaldı (beklenenden az:
  pilot belgelerinin çoğu zaten Türkçe PDF/tablo). Atılan Türkçe harfli 38 satır elle kontrol edildi; hepsi İngilizce.
- **Ek seçimi (`kap.select_attachments`):** Hazirun, vekaletname, imza sirküleri, özgeçmiş, ticaret sicili
  gazetesi, başvuru/talep formu ve Türkçesi de bulunan İngilizce kopyalar (ör. "(ENG)", "Invitation…",
  "Disclosure Policy") ek sınırını doldurmaz. Atlananlar metinde "[ATLANAN RUTİN/ÇEVİRİ EKLER: …]" olarak listelenir.
  Tek PDF hiç atlanmaz; hepsi rutin görünürse ilki yine okunur.
- **İmza sayfası:** Pilotta yalnızca son sayfa boşsa (genelde imza/kaşe) belge engellenmez; modele not düşülür.
  Ortadaki boş sayfa hâlâ engeller.
- **Tavan/taban kilidi (`backtest.evaluate`):** Giriş/çıkış günü açılış=en yüksek=en düşük=kapanış ise yeni
  `uygulanabilirlik` sütunu doldurulur; getiri yine hesaplanır. CSV, yöntem metni ve panel kilitli satır sayısını gösterir.
  Gerçek pilot verisinde 3 satır işaretlendi (elle bulunan günlerle tutarlı). Yöntem metnine `endekse_göre_%`'nin
  net getiriden hesaplandığı da yazıldı.

### Gerçek belgelerle kontrol (KAP isteği, API ücreti yok)
- 22 eksik belge yeni kurallarla yeniden okundu (kullanıcının veritabanına yazılmadı): **3'ü tamamen çözüldü**
  (biri pay alım teklifi). 2'si artık rutin konu olduğu için atlanacak. Birçok belgede sorun sayısı azaldı
  (ör. 4 → 1). Kalan ana engel: "PDF metni uzunluk sınırını aşıyor" (8000 karakter/ek) ve sayfa sınırı (10).
- Bu sınırlar bilerek körlemesine yükseltilmedi. Öneri: yalnızca önemli konularda (pay alım teklifi,
  birleşme, pay geri alım programı) sınırı konuya özel artırmak. Ek girdi maliyeti bildirim başına
  ~0.001–0.003 USD tahmini; kullanıcı onayı gerekiyor.

### Testler
- Yeni `tests/test_review_fixes.py` (15 test): çeviri temizliği, tamamen İngilizce belgenin korunması, ek seçimi,
  imza sayfası, ek sayısı sınırı, rutin konunun ücretsiz atlanması (pilot + günlük), kilitli gün işareti,
  talimat kuralları ve model/kalite/KAP ayarlarının değişmediği.
- Python 3.9.13 ile **65 test geçti**, `compileall` temiz. Streamlit'in `use_container_width` uyarıları önceden de vardı.
- Kullanıcının panel klasörü (`Documents\ChatGPT\…\work\Halley`) git kopyası değil; bu değişiklikler orada
  otomatik görünmez. Panelde görmek için o klasör GitHub'dan güncellenmeli ve panel yeniden başlatılmalı.

## İstenmeden inen ZIP dosyaları düzeltildi (2026-11-06)
- Kullanıcının bilgisayarında Internet Download Manager (IDM) çalışıyor. Pilot sekmesi her açıldığında indirme
  düğmesi için ZIP önceden sayfaya konuyordu; `Downloads\Compressed` altına kullanıcı istemeden 3 ZIP indi
  (16:11'deki ilki geliştiricinin panel ekranını tarayıcı bölmesinde açmasıyla aynı anda).
- Artık indirme dosyaları yalnızca "📦 Raporu indirmeye hazırla" (pilot) ve "⬇️ Listeyi indirmeye hazırla"
  (sinyaller) düğmelerine basınca hazırlanır; "İndirme düğmelerini gizle" ile kaldırılır. Sayfayı açmak hiçbir şey indirmez.
- AppTest: açılışta 0 indirme düğmesi, hazırla sonrası 5, gizle sonrası 0. 65 test geçti.
- Geliştirici notu: Kullanıcının makinesinde panel ekranını tarayıcıda açmak IDM yüzünden dosya indirebilir;
  gerekmedikçe panel sayfası otomatik araçlarla açılmamalı.

## Konuya özel okuma sınırları ve taranmış sayfa tespiti (2026-11-06, Claude)

Kullanıcı onayıyla uygulandı. Model, düşünme düzeyi, ikinci görüş, bütçe, 10 bildirim ve KAP beklemesi aynı.

- **Ölçüm (KAP, API ücreti yok):** Kalan 17 eksik belgenin ekleri indirilip ölçüldü. Pay alım teklifi notu
  8.003 karakter (sınır 8.000), pay geri alım programları 8.5–20.5 bin, bir birleşme belgesi toplam ~42 bin
  karakter; genel kurul eklerinde sorun ek sayısı (2) idi.
- **Gizli eksik bulundu:** SPK onaylı belgeler (onaylı duyuru metni/bilgi formu/ihraç belgesi) taranmış resim;
  her sayfada yalnızca "Doğrulama Kodu … spk.gov.tr" damgası metin olarak okunuyor. Eski kontrol bu sayfaları
  dolu sanıyordu. Mevcut "temiz" pilot belgelerinden 3'ünün ekinde bu durum var (borçlanma aracı ihraç belgeleri).
- **`config.reading_limits(subject)`:** Önemli konular (pay alım teklifi, birleşme, pay geri alım, yeni iş ilişkisi):
  ek 30.000 karakter, 25 sayfa, 4 ek, toplam metin 60.000. Genel kurul: 4 ek, toplam 25.000. Diğerleri değişmedi.
  Günlük okuyucu, pilot belge kontrolü, `document_issues` ve analiz mesajı aynı sınırı kullanır.
- **`textutil.page_is_blank`:** Damga ve kısa sayfa numarası satırları atılınca <40 karakter kalan sayfa boş sayılır.
  Rakam tablosu satırları atılmaz.
- **Taranmış ek kuralı (pilot):** Ek tamamen taranmışsa ve yanında ≥1.000 karakter okunabilir ek varsa belge
  engellenmez; metne "taranmış görüntü, okunamadı" notu eklenir. Okunabilir içerik yoksa belge eskisi gibi engellenir.
  Günlük akışta okunamayan ek sessizce atlanmaz, metne not düşülür. Talimat: böyle notta güven en fazla 0.6.
- Talimat değiştiği için yeni pilot çağrılarının önbellek anahtarı da değişir; önceki 10 analiz etkilenmez.
- **Beklenen etki (henüz gerçek belgeyle sınanmadı):** 17 eksikten ~9'u çözülebilir; ama damga tespiti bazı
  "temiz" belgeleri dürüstçe eksik/notlu hâle getirebilir. Gerçek kontrol KAP isteği gerektirir; kullanıcı izniyle yapılacak.
- **Testler:** 6 yeni test (konu sınırları, uzun teklif belgesinin geçmesi, damga sayfası, taranmış ek kuralı,
  günlük okuyucu notu). Python 3.9.13 ile **71 test geçti**, `compileall` temiz.
- **Maliyet tahmini:** Önemli belgelerde pilot analizi bildirim başına ~0.012–0.02 USD (önceki ortalama 0.008).
  Yeni çözülen ~9 belge için toplam ~0.10–0.18 USD. Günlük akışta ek maliyet günde <0.10 USD tahmini.

### Gerçek belgelerle kontrol sonucu (kullanıcı izniyle, KAP isteği, API ücreti yok)
- İlk 22 eksik belgeden: **6 tamamen temiz** (pay geri alım 4, genel kurul 2), **3 okunabilir + taranmış ek notu**
  (pay alım teklifi 2, genel kurul 1), **2 rutin konu** (atlanır), **11 hâlâ eksik**. Tahmin edilen ~9 çözüm tuttu.
- Hâlâ eksik olanlar: taranmış birleşme sözleşmesi/SPK onaylı metinler (2), bir birleşmede okunamayan büyük PDF
  (5 MB sınırı olabilir; doğrulanmadı), değerleme raporu (109 bin karakter) ve esas sözleşme (30 bin; düşük önem),
  6 ekli genel kurul (ek sayısı + uzunluk), taranmış ihraç/izahname/esas sözleşme tadil ekleri.
- Önceden "temiz" sayılan 3 belge (2 sermaye artırımı tadil eki, 1 ihraç belgesi) artık doğru şekilde
  "okunamayan sayfa" diye engelleniyor. Hiçbiri daha önce ücretli analize girmemişti.
- Kontrol kullanıcının veritabanına yazılmadı.

### Eski kontrollerin yeniden denetimi (`backtest.DOCUMENT_CHECK_VERSION = 2`)
- "Belgeleri hazırla" daha önce temiz işaretlenen belgeleri yeniden denetlemiyordu; gizli taranmış belgeler
  ücretli analize girebilirdi. Pilot veritabanı yeni kodla ilk açıldığında, eski kurallarla temiz sayılan ve
  henüz analiz edilmemiş belgelerden yalnızca etkilenebilecek olanlar (PDF eki okunmuş ya da okuma sınırı değişen
  konu) "yeniden denetlenmeli" diye işaretlenir; analize alınmazlar. Analiz edilmiş belgeler, sonuçlar ve harcama
  kayıtları değişmez. Tek seferliktir (`pilot_meta.document_check_version`).
- Kullanıcının pilot örneğinde (kopya üzerinde denendi): 28 belge yeniden denetime alınır, 40 belge analize hazır
  kalır, 10 analiz / 40 sonuç satırı / 0.081 USD harcama korunur. Kullanıcı panelde aynı tarihlerle (1–30 Eylül 2026)
  "1 · Belgeleri hazırla / eksikleri yeniden dene" düğmesine basmalı (KAP isteği, birkaç dakika, API ücreti yok).
- 1 yeni test; Python 3.9.13 ile **72 test geçti**.

## Yeniden hazırlık sonrası pilot durumu (2026-11-06 17:03 raporu)
- Kullanıcı "Belgeleri hazırla"yı çalıştırdı; KAP istek sınırı 16:50'de durdurdu, 1 belge yeniden denetim bekliyor
  (düğmeye tekrar basınca tamamlanır). Rutin konular dışlandığı için uygun bildirim 2563 → 2337; örnek 100.
- Canlı durum: analize hazır 71 (66'sının 10 günlük fiyatı hazır; 5 yeni hisse için "Fiyatları al" gerekli),
  gerçek belge eksiği 20 (15'i taranmış sayfa), seçimde analiz edilmiş 8. Rutin 2 fon bildiriminin analizi
  veritabanında kaldı ama artık örnekte değil. Harcama değişmedi: 0.081 USD, belirsiz çağrı yok, kalan 0.919 USD.
- Rapor düzeltmeleri: belge eksikleri " | " ile ayrılıyor (mesajların içinde ";" var); yöntem metnindeki
  sabit "40 satır" ifadesi gerçek satır sayısıyla yazılıyor. 1 yeni test; **73 test geçti**.

## Faz 3: ön kayıtlı eşik ayarı aracı (2026-11-06, Claude)

**Rol dağılımı:** Kullanıcı temeli ve geliştirmeleri yapıyor; programı başka birine verecek. O kişi pilotu büyütecek
(ücretli analizleri kendi OpenAI anahtarıyla çalıştıracak) ve geri bildirim gönderecek. Geliştirme bu geri bildirimle sürer.

- **`bist_haber/calibration.py`:** Kurallar veri görülmeden önce yazıldı (modül başındaki 8 madde); sonuçlara
  bakarak değiştirilmemeli. Olay skoru = yön × etki × güven; eşik ailesi 0.5–3.0 (6 değer); seçim vadesi 5 gün;
  ölçüt XU100'e göre net getiri; tavan/taban kilidi şüpheli satırlar hariç; zaman sırasına göre %60 geliştirme /
  %40 doğrulama; geliştirme sonuçlarından doğrulamaya taşanlar ambargo ile atılır; eşik yalnız geliştirmede,
  en az 20 pozitif olay şartıyla seçilir (eşitlikte daha temkinli eşik); doğrulama bir kez ölçülür.
- **Canlı eşikler (`report.THRESHOLDS`) değişmez.** Araç yalnızca öneri raporu üretir; uygulamak kullanıcı onayı ister.
- Panel: pilot sekmesinde "📐 Skor eşiği ayarı (Faz 3)" bölümü. ZIP'e `halley_esik_ayari.txt` eklendi (5 dosya);
  programı kullanan kişi ZIP'i geri bildirim olarak gönderebilir.
- Gerçek pilot verisinde (kopya): 8 ölçülebilir olay → "yetersiz veri; eşik seçilmedi". Beklenen ve doğru sonuç.
- **Yapısal sınır / sonraki geliştirme:** Pilot tek seferde ≤32 günlük tek dönem tutuyor ve yeni hazırlık seçimi
  değiştiriyor. Tek ayda 10 günlük vadeler zaman bölmesine taştığı için geliştirme döneminin 5/10 günlük sonuçlarının
  çoğu ambargoyla düşer. Sağlam ayar için birden çok ayın analiz edilmiş olaylarının birikmesi (çok dönemli pilot) gerekir.
  Kaba hedef: ~400 olay, birkaç ay; maliyet tahmini standart API ile 3–5 USD, Batch ile yaklaşık yarısı (güncel fiyat
  doğrulanmalı). Bu, 1 USD pilot tavanını aşar; ayrı plan ve onay gerektirir.
- Testler: `tests/test_calibration.py` (6 test: küçük örnekte seçim yok, yalnız geliştirmede seçim + temkinli eşitlik,
  doğrulamanın seçimi değiştirememesi, ambargo, kilitli satırların dışlanması, canlı eşiklerin korunması).
  Python 3.9.13 ile **79 test geçti**.

## Arayüz sadeleştirmesi (2026-11-06, Claude)
Kullanıcının onayladığı taslağa göre `app.py` yeniden düzenlendi; iş mantığı değişmedi.
- Kenar çubuğu kaldırıldı. Üstte başlık + tek **🔄 Haberleri güncelle** düğmesi. API anahtarı yoksa üstte giriş kutusu.
- Ayarlar (KAP gün sayısı, güncelleme başına haber, liste dönemi) katlanır **⚙️ Ayarlar** bölümünde.
- 3 özet kutusu: olumlu haber, olumsuz haber, son güncelleme (oturumda yoksa son analiz zamanı).
- 9 sütunlu tablo yerine **olumlu / olumsuz** iki liste; her hisse tıklanınca açılır (kısa neden + ✅/⚠️ etiketi).
  Nötr hisseler varsayılan gizli, anahtarla gösterilir. Ayrıntıda skor, 1/5 günlük fiyat değişimi, haber kartları;
  etki 1–5 yerine "düşük/orta/yüksek", kalıcılık "birkaç gün/hafta/aylar" olarak yazılır.
- Sekmeler 4 → 3: **Bugünün listesi**, **Haberler**, **🔧 Gelişmiş** (durum + geçmiş veri pilotu).
- Liste indirme yine yalnızca "indirmeye hazırla" düğmesiyle (IDM sorunu).
- Ayrı portta kopya veriyle görsel kontrol yapıldı; indirme tetiklenmedi. AppTest güncellendi (3 sekme, ana düğme,
  özet kutuları). Python 3.9.13 ile **79 test geçti**. README kullanım adımları yeni düzene göre güncellendi.

## Ücretsiz deneme düğmesi ve liste indirme (2026-11-06)
- **🧪 Ücretsiz dene** (`pipeline.free_check`): KAP + haber siteleri + fiyatlar toplanır, yapay zekâ HİÇ çağrılmaz
  (`update_all(analyze=False)`); OpenAI kredisi harcanmaz. Sonunda sıradaki haber sayısı ve bir sonraki gerçek
  güncellemenin tahmini maliyeti gösterilir (`estimate_next_run`: girdi metin uzunluğundan, çıktı bu bilgisayardaki
  geçmiş ortalamadan; alt sınır ikinci görüşsüz, üst sınır her habere ikinci görüş).
- Liste CSV'si Türkçe başlıklı (Hisse, Şirket, Sinyal, Kontrol, Skor, Haber sayısı, Son 1/5 gün %, Son haber özeti).
- Düğme sonrası sayfa yenilenmeden önce veritabanı bağlantısı kapatılıyor (önceden her tıklamada açık bağlantı kalıyordu;
  Windows'ta test dosyası silinemiyordu).
- Kullanıcının ilk gerçek güncellemesi (17:34): 10 haber işlendi (4 analiz, 6 ön elemede elendi), ~0.045 USD;
  65 haber sırada. **Gözlem:** Sıra en eski haberden başlıyor; bu turda dünkü BloombergHT haberleri işlendi, bugünkü
  KAP bildirimleri bekliyor. SOKM "pozitif" ama aynı gün fiyat %-10 (taban) — fiyat ters yönde hareket ettiğinde
  uyarı gösterilmesi ileride değerlendirilebilir (eşik/skor değişikliği değil, bilgi notu).
- AppTest: ücretsiz düğme tıklanır, yapay zekâ çağrılırsa test düşer. Python 3.9.13 ile **80 test geçti**.

## Analiz sırası: en yeni haber önce (2026-11-06)
- Kullanıcı isteğiyle `analyzer.pending` artık `ORDER BY published_at DESC` (önce en yeni). Güncelleme başına adet
  sınırı (1/3/5/10) olduğundan eski haberler sırada bekleyebilir; 3 günden eski RSS haberleri zaten atlanır.
  Pilot kendi sorgusunu kullanır, etkilenmez. 1 yeni test; **81 test geçti**.
- Gözlem: Sıradaki bazı KAP kayıtları (ör. "MERKEZİ KAYIT KURULUŞU: DÖNÜŞÜM", "BORSA İSTANBUL: Hak Kullanımı",
  borçlanma aracı ihraç limiti) rutin olabilir; kullanıcı geri bildirimiyle atlama listesine eklenebilir.

## İşlem senaryosu (SL/TP, risk, vade, açıklama) ve teknik analiz doğruluğu (2026-11-07)
Kullanıcı geri bildirimi: haberle seçim → teknik analiz → risk faktörleri → SL/TP → "neden" açıklaması → tahmini vade.
Hepsi **kodla** hesaplanır (yapay zekâ yok, kredi harcamaz). Geçmiş veriyle HENÜZ TEST EDİLMEDİ; panelde "tahmini".

**`tradeplan.py`** (yalnız olumlu haberli hisse için alım senaryosu; açığa satış yok):
- SL: 20 günlük destek 1–3 ATR uzaktaysa desteğin %1 altı, değilse fiyat − 2×ATR; fiyatın %15'inden aşağı inmez.
- TP: fiyatın üstündeki ilk gerçek direnç (20 gün / 60 gün / 52 hafta). Yalnız 20 günlük seviye fiyata 1 ATR'den
  yakınsa "gürültü" sayılıp atlanır; 60 gün ve 52 hafta seviyeleri her zaman dikkate alınır. Daha uzak seviyeye
  ATLANMAZ (aradaki direnç risk/getiriyi iyimser gösterirdi). Üstte direnç yoksa TP = 2R.
- Risk/getiri <1 → "elverişsiz" (uyarı + risk en az "yüksek"); 1–2 → "zayıf".
- Risk faktörleri: oynaklık ≥%5, RSI ≥70, fiyat 50g ort.+%15, hacim oranı <0,7, olumlu haber + düşüş trendi,
  zayıf MACD, haber güveni <0,6, ⚠️ kontrol et, son gün kilit, <200 gün veri, veri uyarıları. Ağırlıklı puan →
  düşük/orta/yüksek (elverişsiz 4, trend çelişkisi ve zayıf r/g 2, diğerleri 1).
- Vade: haber kalıcılığı (kısa 1–5, orta 5–20, uzun 20–60 işlem günü) ve TP mesafesi / (0,5×ATR) ile genişletilir.
- Açıklama "Neden olumlu görünüyor" dilinde; "yatırım tavsiyesi değildir" ibaresi. Program başkasına verildiği için
  kişiye özel "al" tavsiyesi dilinden kaçınıldı (SPK yatırım danışmanlığı kapsamı).
- Panel: hisse ayrıntısında senaryo kutuları (referans, SL, TP, r/g, vade, risk), açıklama, risk faktörleri;
  detaylı CSV'de senaryo sütunları.

**Teknik analiz doğruluğu (`technical.py`):**
- ATR standart Wilder yöntemine, MACD sinyali tüm seri üzerinde 9 EMA'ya çevrildi.
- Veri kontrolleri: fiyat >3 iş günü eskiyse uyarı (>6 kritik); 60 günde >10 günlük boşluk; günlük ±%10 sınırını
  aşan sıçrama (düzeltilmemiş bölünme/bedelsiz/veri hatası şüphesi; son 60 günde ise kritik); 20 günde ≥3 hacimsiz
  ya da tek fiyatlı gün; son 60 günde bedelsiz/bedelli/temettü haberi (seviyeler bozulmuş olabilir). Kritik veride
  SL/TP senaryosu üretilmez. 60 günlük destek/direnç ve son gün kilit bilgisi eklendi.
- Doğrulama: RSI StockCharts referans tablosuyla (tablo ara değerleri yuvarlıyor; sabit ~0,06 fark, algoritma doğru);
  SMA/MACD/sinyal/ATR/RSI/seviyeler pandas ile bağımsız hesapla birebir (sentetik seri). **46 gerçek BIST hissesinde**
  pandas ile fark 0; kritik veri sorunu yok, 2 hissede uyarı. Senaryo dağılımı (aynı varsayımsal haberle): 13 elverişsiz,
  19 zayıf, 14 iyi; medyan r/g ~1:1,4 — iyimser değil.
- Testler: `tests/test_technical_reference.py` (19 test). Python 3.9.13 ile **112 test geçti**.
- Sonraki doğrulama önerisi: geçmiş veri pilotuna "TP mi önce geldi, SL mi?" ölçümü eklenmeli.

## 2026-11-07 — Pilot: SL/TP senaryo testi ("önce TP mi geldi, SL mi?")

**Amaç:** Panelin ürettiği SL/TP senaryosunun geçmiş olaylarda nasıl sonuçlandığını ücretsiz ölçmek (yapay zekâ yok).

**Kurallar (`bist_haber/scenario_test.py`):**
- Senaryo yalnız giriş gününden ÖNCEKİ fiyatlarla hesaplanır (geleceği görmeden). Giriş: yayından sonraki ilk
  işlem gününün açılışı (pilotun olay ölçümüyle aynı).
- Açılış SL'nin altındaysa SL, TP'nin üstündeyse TP açılış fiyatından sayılır. Aynı gün hem SL hem TP görülürse gün
  içi sıra bilinmediği için temkinli olarak SL sayılır. Tavan/taban kilidi (tek fiyatlı gün) sayılır.
- En fazla 30 işlem günü izlenir: ikisine de değmezse "süre doldu"; veri 30 günden kısaysa "devam ediyor".
- Senaryo üretilmeyen olaylar (olumsuz/nötr haber, kritik veri) "senaryo yok" olarak ayrı sayılır. İşlem maliyeti dahil değil.
- Pilot fiyat indirmesi artık seçim başlangıcından 400 gün önce başlıyor (200 günlük ortalama için geçmiş gerekir).
  Pilot barlarında hacim yok; hacimsiz gün kontrolü yalnız hacmi bilinen günleri sayıyor.

**Çıktı:** Pilot sekmesinde "🎯 SL/TP senaryo testi" bölümü; rapor ZIP'i 7 dosya
(`halley_senaryo_testi.csv`, `halley_senaryo_testi.txt` eklendi).

**Gerçek pilot verisinin kopyasında ilk sonuç:** 8 olay; 1'i test edildi (KZBGY: 9. günde SL, %−7,68); diğer 7'de
olumlu sinyal yok → senaryo yok. Bu örnek kanıt değildir; eşik veya kural değiştirilmedi.

**Testler:** `tests/test_scenario_test.py` (önce TP, önce SL, aynı gün ikisi → SL, açılış boşluğu, devam ediyor,
gelecek fiyatların seviyeleri etkilememesi, olumsuz haber test edilmez, özet metni). Python 3.9.13 ile **120 test geçti**.

## 2026-11-07 — Tasarım özeti (PDF) değerlendirmesi ve plan; Parça A1: yeni göstergeler

**Kullanıcı geri bildirimi:** AI Swing Trader tasarım özeti (PDF) + çoklu zaman dilimi + üç giriş senaryosu
(kırılım/geri çekilme/destekten tepki) + yaklaşan olay takvimi. Midas'ta koşullu emir yok: kırılım senaryosu
"fiyat alarmı kur, gelince elle al" olarak yazılacak. Kullanıcının ilkesi: işler parça parça, her parça gerçek
veriyle test edilerek; hata payı en az; uydurma yok.

**Plan (sıra):** A işlem planı (A1 göstergeler ✅, A2 üç giriş senaryosu + TP1/TP2 + teyit/geçersizlik, A3 fiyatlanma
ve likidite kuralları + "bugün fırsat yok") → B olay takvimi (ücretsiz kısım; yapay zekâ kısmı maliyet onayıyla)
→ C işlem günlüğü, koşullu giriş testi, performans metrikleri, pozisyon hesaplayıcı → D saatlik veri kalite testi
sonrası çoklu zaman dilimi, piyasa rejimi, sektör → E bildirimler vb. Teknik veriler birleşik puana ancak işlem
günlüğü/pilot verisiyle test edildikten sonra katılabilir (eşikler değişmedi).

**A1 — eklenen göstergeler (`technical.py`, yalnız gösterim, skora/senaryoya henüz etkisi yok):**
EMA 20/50/200 (SMA tohumlu standart), Wilder ADX14 ve +DI/−DI, Bollinger 20/2 (ddof=0) ve sıkışma (bant son 120
günün en dar %20'sinde), OBV 20 günlük eğilim, XU100'e göre güç 20/60 gün (endeksin iki tarihte de fiyatı yoksa
boş; tahmin edilmez), 20 günlük ortalama işlem hacmi (TL), salınım dibi, haber öncesi 5 gün / haber sonrası hareket
(taban: yayın gününden önceki son kapanış). Fiyat güncellemesi artık XU100'ü de indiriyor.

**Doğrulama:** 44 gerçek BIST hissesinin 1 yıllık verisinde TA-Lib 0.8.1 (referans kütüphane) ile EMA, +DI/−DI,
Bollinger, OBV yönü, endekse göre güç farkı 0; ADX en çok 5e-6 puan (TA-Lib iç yuvarlaması; etkisiz). TA-Lib
değerleri sabit bir seri üzerinde dondurulup `tests/test_indicators_v2.py`'ye kondu (17 test). Canlı veri kopyasında
4 hisse için panel hatasız çizildi. Python 3.9.13 ile **137 test geçti**.

## 2026-11-07 — Parça A2: üç giriş senaryosu (`bist_haber/entries.py`)

Midas'ta koşullu emir yok → kırılım "fiyat alarmı kur, teyit gelince elle al"; geri çekilme ve destekten tepki
limit emir. Mevcut fiyattan giriş planı "referans" olarak kaldı (pilot senaryo testi onu ölçüyor).

**Kurallar (sabitler dosyada; geçmiş sonuca bakılarak ayarlanmadı):**
- Kırılım: en yakın direnç (20g/60g/52h) fiyata ≤2 ATR ise. Alarm = direnç; tahmini alış = direnç + 0,2 ATR; teyit =
  günlük kapanış direnç üstünde (+ hacim); SL = direnç − 1 ATR. Fiyat tüm seviyelerin üstündeyse uygulanamaz.
- Geri çekilme: 20 EMA > 50 EMA (> 200 EMA) ve fiyat 50 EMA üstü. Limit = 20 EMA (fiyat 0,3 ATR içindeyse mevcut
  fiyat); SL = salınım dibi − 0,2 ATR (dip 0,5–3 ATR aşağıdaysa) yoksa giriş − 1,5 ATR; geçersizlik: 50 EMA altı kapanış.
- Destekten tepki: 20g (yoksa 60g) destek fiyata ≤2 ATR. Limit = destek + 0,25 ATR (fiyatın üstüne çıkmaz);
  SL = destek − 0,75 ATR; düşüş trendinde "düşen bıçak" notu.
- Hedefler: TP1 = girişin 0,5 ATR'den fazla üstündeki ilk direnç (yoksa 1:2), TP2 = sonraki (yoksa 1:3). Girişe
  10 ATR'den uzak seviye hedef sayılmaz (≈20 işlem günü; kullanıcının swing vadesi) — FROTO'da 9 ay önceki +%72'lik
  52h zirve TP2 olarak çıkınca eklendi (veri doğruydu, sorun kuraldaydı). Zarar mesafesi >%15 → elverişsiz.
- Kalite: TP1 r/g <1 elverişsiz, 1–2 zayıf, ≥2 iyi. En uygun = en yüksek TP1 r/g (eşitlikte fiyata en yakın).
  Hiçbiri uygun değilse "Uygun giriş senaryosu yok". Her senaryoda teyit, geçersizlik, olumlu/olumsuz senaryo,
  geçerlilik (kırılım/geri çekilme 10, destek 5 işlem günü), kaba TP1/TP2 süresi.

**Gerçek veri testi (44 BIST hissesi, ~2 yıl, 5 günde bir kesim = 4.400 durum, HABER YOK):** tutarlılık ihlali 0
(SL < giriş < TP1 < TP2; limit fiyatın üstünde değil). Emir gerçekleşme oranı %55–63. Gerçekleşenlerde TP1 önce
%33–37, SL önce %57–65; ortalama getiri −0,25…+0,26% (maliyet hariç). Mevcut fiyattan referans: TP1 %30, SL %51,
ort. +0,38%. Sonuç: teknik kurallar tek başına avantaj sağlamıyor (rastgele yürüyüşte 1:2 hedef için beklenen ~%33
ile uyumlu → ölçüm de taraflı değil). Kurallar buna göre değiştirilmedi; panelde bu not aynen gösteriliyor.
Haber sinyalinin katkısı pilotta (Faz C: koşullu giriş testi) ölçülmeli. Test ölçüm kuralları: kırılım = kapanış
seviyenin üstünde → ertesi gün açılış; limit = en düşük ≤ limit; aynı gün SL+TP → SL; limit dolduğu gün TP sayılmaz.

**Panel:** "🧭 Giriş senaryoları" kartı (en uygun senaryo + üçünün tablosu), altında "Mevcut fiyattan girilirse
(referans)". Detaylı CSV'ye en uygun giriş sütunları eklendi. Markdown'da "~" üstü çizili yaptığı için metinlerde
"yaklaşık" kullanıldı; kod metinleri `md()` ile kaçırılıyor. Testler: `tests/test_entries.py` (20). **157 test geçti.**
Not: Yahoo gün içinde son barı yalnız kapanışla (açılış/en yüksek/en düşük boş) verebiliyor; ATR bunu kapanışla
dolduruyor, etkisi küçük.

## 2026-11-07 — Parça A3: fiyatlanma, likidite, "bugün fırsat yok"

**Eşikler gerçek veriyle seçildi (sonuca göre ayarlanmadı):**
- Likidite (20 günlük ort. kapanış × hacim): 630 işlem gören BIST hissesinde %8'i < 2 mn TL, %24'ü < 10 mn TL,
  medyan 28 mn TL. < 2 mn TL → senaryo üretilmez; 2–10 mn TL → "Düşük likidite" riski (2 puan). Hacim bilgisi
  yoksa (pilot barları) uyarı uydurulmaz.
- Fiyatlanma (ATR cinsinden): 44 hissede rastgele günlerin %1–6'sında 1–3 günde ≥ +2 ATR, %3'ünde 5 günde ≥ +3 ATR
  yükseliş → olağandışı. Olumlu haberde: haberden bu yana ≥ +2 ATR → "etkinin önemli kısmı fiyatlanmış olabilir"
  (2 puan); haberden önceki 5 günde ≥ +3 ATR → "beklenti/sızıntı" (1 puan); haberden bu yana ≤ −2 ATR → "haber
  olumlu ama fiyat düştü; kontrol edin" (2 puan). Sonuncusu gerçek veride yakalandı: SOKM bilanço beklentiyi aştı
  ("olumlu", teyitli) ama ertesi gün −%9,8 — önceki kural yalnız yükselişe bakıyordu, risk "düşük" görünüyordu.
- **Düzeltilen hata:** haber öncesi/sonrası taban artık `effective_date` (haberin etki edebileceği ilk işlem günü)
  ile belirleniyor. Önceden yayın günü kullanılıyordu; seans kapanışından sonra (SOKM 22:29) çıkan haberde yayın
  gününün kapanışı yanlışlıkla "haber sonrası" sayılıyordu (−%10,8 yerine doğrusu −%9,8). Pilot senaryo testi de
  aynı ölçümü (yalnız girişten önceki fiyatlarla) kullanıyor.

**"Bugün fırsat" özeti (`tradeplan.opportunity_summary`):** listenin başında; olumlu haberli hisselerden en az bir
giriş senaryosu elverişsiz olmayanlar risk seviyesine göre sıralı. Yoksa "Bugün uygun işlem fırsatı bulunamadı.
Her gün işlem yapmak gerekmez." + neden sayıları (haber zayıf / likidite / veri / senaryolar elverişsiz).

Canlı veri kopyasında: 3 hissede uygun senaryo (SOKM destekten tepki risk orta — çelişki notuyla; FROTO ve ISCTR
kırılım risk orta). Testler: `tests/test_a3_rules.py` (+ etki günü testi). Python 3.9.13 ile **170 test geçti**.

## 2026-11-07 — A1–A3 son kontrol

**Bulunan ve düzeltilenler:**
1. Özette ve senaryo kartında gösterilen risk seviyesi, gösterilen giriş senaryosuna değil "mevcut fiyattan" referans
   planın risk/getirisine dayanıyordu (ör. referans elverişsiz → kırılım iyi olsa da "yüksek"). Artık her giriş
   senaryosunun kendi risk seviyesi var: ortak riskler (referansın r/g maddeleri hariç) + senaryonun r/g'si
   (elverişsiz 4, zayıf 2). Panelde ve CSV'de gösteriliyor.
2. Yahoo gün içinde son günü yalnız kapanışla verebiliyor (canlı veride 4 hissede 2026-11-06 açılış/en yüksek/en
   düşük boştu; sonradan tam geldi: FROTO en yüksek 74,20). Artık veri uyarısı çıkıyor ("seans bitince yeniden
   güncelleyin"); bu uyarı piyasa riski olmadığı için risk puanına katılmıyor. INSERT OR REPLACE bir sonraki
   güncellemede satırı düzeltiyor.
3. Senaryo testi: girişte açılış eksikse "ölçülemedi"; en yüksek/en düşük eksikse kapanış kullanılır (çökme yok).

**Doğrulama:** 5.714 bozulmuş gerçek veri denemesi (eksik OHLC, hacimsiz, 30–252 gün, düz fiyat, boşluk, endeks
yok/eksik) → hata 0, tutarlılık ihlali 0. 4.400 durumluk senaryo testi değişmedi (ihlal 0). Panel canlı veri
kopyasıyla hatasız; CSV hazırlanıyor; pilot senaryo testi aynı. **175 test geçti.**

## 2026-11-07 — Parça B1: makro takvim (`bist_haber/macro_calendar.py`)

B planı: B1 makro takvim ✅ → B2 bilanço yasal son tarih → B3 şirket olayları (genel kurul, temettü hak kullanım,
sermaye artırımı; eldeki KAP bildirimlerinden) → B4 panel "önümüzdeki 15 işlem günü" + "vade içinde olay" riski.

- Tarihler TAHMİN EDİLMEZ; yayımlanmış takvimden elle girildi, kaynakları dosyada. TCMB sitesi otomatik erişime
  kapalı (ECONNRESET / tarayıcı reddi) → PPK 2026 (8 toplantı) ve 21 Ocak 2027 duyuruyu aktaran 4 bağımsız
  kaynakla karşılaştırıldı (Bloomberg HT 28.12.2025, CNBC-e, QNB Invest, 24 Saat; hepsi aynı). Mart/Nisan/Haziran
  2027 yalnız QNB Invest'te → "tek kaynak" işaretli ve panelde öyle yazıyor. TÜFE 2026 (12 tarih): TÜİK 2 Ocak 2026
  takvimi (Foreks aktarımı); Haziran ve Ekim haberlerle doğrulandı; gün adları kaynakla birebir. 2027 TÜFE takvimi
  henüz yok → "takvimde yok".
- Kapsam: TÜFE 2026-12-31'e, PPK 2027-06-30'a kadar bilinir; ötesine düşen pencerede "takvimi bilinmeyen" yazılır.
  Kapsam sonuna 30 günden az kalınca panelde bakım uyarısı (yeni yıl takvimi eklenmeli). Resmi tatiller hesaba
  katılmaz (işlem günü = hafta içi).
- Panel: "Bugünün listesi" başında "📅 Önümüzdeki 15 işlem günü" + sonraki PPK/TÜFE. Bugün (7 Kasım): pencerede olay
  yok; sonraki TÜFE 3 Aralık (19 işlem günü), PPK 10 Aralık (24). 26 Kasım ve 20 Aralık için de denendi.
- Testler: `tests/test_macro_calendar.py` (12; veri tutarlılığı: hafta içi, PPK çarşamba/perşembe, TÜFE ayın ilk
  5 günü ve önceki ayın verisi). **187 test geçti.**

## 2026-11-07 — Takvim genişletme ("önemli olabilecek her detay") ve otomatik takvim kontrolü

**Borsa İstanbul tatil/yarım gün takvimi (`market_calendar.py`):** 2026 listesi Midas destek sayfası ve hisse.net
(06.12.2025) ile birebir; yarım günlerde pay piyasası 12:40'ta kapanır. 2027: yalnız yasayla sabit milli tatiller +
28 Ekim yarım gün; dini bayram kapanışları borsa açıklayınca eklenmeli (aralık 2027'ye taşınca panel uyarır).
Gerçek veriyle doğrulandı: Yahoo XU100 1 Ocak–6 Kasım 2026 seansları (212) listeyle BİREBİR (kapalı günde işlem yok,
açık günde eksik yok); yarım günlerde endeks hacmi medyanın %18–46'sı. Bağlananlar: işlem günü sayımı, haberin etki
günü (`effective_date`: tatil ve 12:40 kapanışı), fiyat güncelliği kontrolü. Eski kayıtlar: canlı DB'de 2 haberin
(23 Nisan, 28 Ekim; ikisi de analiz edilmemiş) kayıtlı etki günü eski kurala göre; pilotta etkilenen yok → veri
değiştirilmedi.

**Makro takvime eklenenler (`macro_calendar.py`):** TCMB Enflasyon Raporu ve Finansal İstikrar Raporu, PPK
toplantı özetleri, Fed (FOMC; resmi site; TR 21:00/22:00 ABD yaz saatine göre; BIST kapandıktan sonra → etki ertesi
işlem günü; projeksiyonlu toplantılar işaretli), Türkiye kredi notu planlı tarihleri 2026 (Moody's, S&P, Fitch; iki
kaynak), VİOP BIST 30 endeks vade sonları (kural: çift ayların son işlem günü, yarım günse önceki iş günü). Bugün
penceresinde: 12 Kasım Enflasyon Raporu, 27 Kasım Finansal İstikrar Raporu.

**Otomatik takvim kontrolü (`calendar_sync.py`, kullanıcı isteği):** Panel açılışında günde bir kez + Gelişmiş →
"📅 Takvimi şimdi kontrol et". Kullanıcının bilgisayarından erişilebilen RESMİ sayfalar okunur: TCMB takvim tablosu
(PPK, özet, Enflasyon Raporu, FİR) ve federalreserve.gov FOMC. Sayfa yapısı/başlıklar beklenenden farklıysa, bir
tarih okunamazsa, hafta sonuna düşerse ya da özet karardan beklenmedik uzaklıktaysa o kaynak için HİÇBİR ŞEY
değişmez ("kontrol edilemedi"); önceki geçerli veri korunur. Resmi veri kapsadığı dönemde yerleşik takvimin önüne
geçer, farklar raporlanır. Otomatik okunamayanlar: Borsa İstanbul (bağlantıyı reddediyor), TÜİK (JavaScript
uygulaması) → "elle kontrol gerekir". Canlı deneme: 4,3 sn, TCMB ve Fed yerleşik takvimle aynı (fark 0). Bu kontrol
TCMB tablosu üzerinden 2027 ilk yarısını ve PPK özetlerini resmi olarak doğruladı ("tek kaynak" işaretleri kalktı).
Gerçek Fed sayfasında 2023 "Jan/Feb 31-1" kısaltması yakalandı ve desteklendi. Sonuç `data/takvim_guncel.json`
(GitHub'a yüklenmez). Testler ağa çıkmaz (`HALLEY_OFFLINE`, kaydedilmiş gerçek sayfalar `tests/fixtures`).
**215 test geçti.**

## 2026-11-07 — Parça B2: bilanço takvimi (`bist_haber/earnings.py`)

Kural: SPK II-14.1 Md. 10–11 (II-14.1.a, Resmî Gazete 3.2.2017 sayı 29968; metin RG PDF'inden okundu). Yıllık 60 /
konsolide 70 gün; ara dönem 30 / 40; sınırlı denetimli ara dönem +10 (6 aylık için varsayıldı → 40 / 50). Son gün
tatil/hafta sonuysa sonraki iş günü. Banka/sigorta/leasing/faktoring/finansman: özel mevzuat daha kısa olabilir
(doğrulanmadı, ekranda not). Konsolide mi: "Sorumluluk Beyanı / Faaliyet Raporu (Konsolide | Konsolide Olmayan)"
bildirimlerinden; bilinmezse iki tarih ve temkinli geç tarih. Açıklandı mı: KAP "Finansal Rapor" bildirimi ya da
haber analizinde "finansal_sonuc" olayı (dönem sonundan sonra; kaynak yazılır); KAP kayıtları dönem başından yoksa
"bilinmiyor". Gerçek veride: SASA, EKGYO, ERBOS, MEGMT KAP'tan; FROTO, TOASO, SOKM, ISCTR Bloomberg HT bilanço
haberlerinden açıklandı (dördü de gerçek 3Ç haberi). 9 aylık konsolide son gün 9 Kasım 2026.
Senaryo riski: son gün 15 işlem günü içinde ve açıklanmadıysa 2 puan; bilinmiyorsa 1 puan. Panel: hisse ayrıntısında
"📑 Bilanço takvimi", CSV'de "Bilanço durumu". Pilot senaryo testine henüz bağlanmadı. **226 test geçti.**
Açık: KAP'tan şirket bazlı rapor durumu sorgusu (KAP isteği gerektirir; onay alınmadı), B3 şirket olayları, B4.

## 2026-11-07 — Parça B3: şirket olayları (`bist_haber/corp_events.py`)

Kaynak: eldeki KAP bildirimlerinin yapılandırılmış form alanları (etiket satırı + altındaki değer); serbest metin
tarihleri kullanılmaz. 22 gerçek bildirim incelendi (canlı + pilot). Alanlar: Genel Kurul Tarihi/Saati/Tipi, katılım
için son pay sahipliği günü, "yapıldı mı", gündemdeki hak süreçleri (eski iki dilli form dahil); kâr payının
görüşüleceği GK tarihi, ödeme şekli, işlem gören grubun brüt TL/pay (taksitliyse TOPLAM); bedelsiz hak kullanım
başlangıcı, rüçhan başlangıç/bitiş (fiyat düzeltme günleri), SPK onay, kayıt, ödeme tarihleri ve artırım türü.
Aynı tür için en son bildirim geçerli. Kâr payı ödeme tablosunun dolu örneği yoktu → tarih geçerse "bildirimi
açın" notuyla, hak kullanım günü varsayılmaz.
**Gerçek veride yakalanan hatalar:** (1) İngilizce etiket atlama kuralı "Evet"/"Yoktur" değerlerini de atlıyordu →
yalnız bilinen İngilizce etiketler; (2) "Bedelli Sermaye Artırımında ..." özet satırı tür sanılıyordu → tam eşleşme.
**Bağımsız doğrulama:** bedelsiz hak kullanım günleri KORDS 14.09, AKFYE 21.09, MEGMT 21.09.2026 → Yahoo bölünme
kayıtlarıyla BİREBİR aynı.
Risk: vade (15 işlem günü) içinde fiyat düzeltmesi 2 puan; kâr payı süreci (brüt TL ve fiyata oranı) ve genel kurul
1'er puan. Panel: hisse ayrıntısında "🗓️ Şirket olayları", CSV "Şirket olayları". Canlı listede (4 hisse) kayıtlı olay
yok. Sınır: yalnız kayıtlı bildirimler (ayar 1 gün → kısa pencere). **237 test geçti.**

## 2026-11-07 — Takvim için KAP geçmişi (kullanıcı onayı) ve TÜİK TÜFE otomatik okuma

**KAP geçmişi (`kap_history.py`):** son 45 gün listelendi (12.899 bildirim, 33 sn). Yalnız takvim konuları
saklandı (1.426): Finansal Rapor, Sorumluluk Beyanı/Faaliyet Raporu (konsolide bilgisi; metin çekilmez) ve olay
bildirimleri (GK, kâr payı, sermaye artırımı; yalnız ana sayfa, EK İNDİRİLMEZ). status='context' → yapay zekâ
kuyruğuna girmez (kuyruk 87 → 87, kredi harcanmadı). Günlük güncelleme aynı bildirimi kendi penceresinde görürse
normal sıraya alır (kap.collect). 213 olay sayfasından 100'ü okundu, sonra KAP istek sınırı uyguladı → tur kuralına
göre bırakıldı; 113 sayfa Gelişmiş → "📥 Takvim için KAP geçmişini al" ile tamamlanacak (kaldığı yerden).
Canlı veriye aktarım: önce yedek `data/yedek/bist_haber_2026-11-07_oncesi_kap_gecmisi.db`; INSERT OR IGNORE ile
+1.420 satır (6'sı zaten vardı), integrity ok.
**Etkisi:** bilanço durumu 761 şirketin 753'ünde "bilinmiyor" iken → 398 açıklandı, 363 açıklanmadı (tam kapsam);
konsolide bilgisi 398 şirkette. 15 iş günü içinde 39 şirket olayı. FROTO: 24.11 olağanüstü GK, 26.11 kâr payı hak
kullanımı (brüt 3,07 TL ≈ fiyatın %4,2'si) → risk "yüksek".
**Kâr payı ödeme tablosu çözüldü:** 6 gerçek dolu örnek; sütunlar teklif/kesinleşen hak kullanım, ödeme, kayıt (boş
hücre düşer). Kural: 3 tarih → (hak, ödeme, kayıt), 4 → kesinleşen; hak ≤ kayıt ≤ ödeme değilse etiketlenmez.
**Doğrulama:** MCARD 23.10.2026 hak kullanımı ve 2,5711 TL brüt → Yahoo temettü kaydıyla birebir. Yakalanan hata:
tek gruplu şirketlerde ("OYAKC, TRA...") tutar okunmuyordu → düzeltildi (25 bildirimde okunamayan tutar kalmadı).

**TÜİK TÜFE otomatik (kullanıcı isteği):** TÜİK ana sitesinin takvim kutusu `www.tuik.gov.tr/Home/GetTakvim/
?value=GG/AA/YYYY&dilId=1` adresinden gün gün JSON alıyor (js/main.min.js). Yalnız onaylı (g_ONAY=1) "Tüketici
Fiyat Endeksi" kayıtları; her ayın ilk 10 günündeki iş günleri taranır; bulunamayan ay ve sonrası "takvimde yok".
Canlı: 3 Kasım ve 3 Aralık 2026 10:00 yerleşik takvimle aynı; Ocak 2027 henüz yok. Artık elle kontrol gereken tek
kaynak Borsa İstanbul tatilleri. Testler gerçek cevaplarla (kişisel iletişim alanları çıkarıldı). **250 test geçti.**

## 2026-11-07 — Arka plan KAP okuyucu: eksik sayfalar kendiliğinden tamamlanır (`kap_worker.py`)

Kullanıcı isteği: "Eksik kalan sayfa olursa otomatik yeniden okusun; kullanıcı dakika sayıp tekrar denemesin; olay
özetini bildirip tamamlanana kadar devam etsin (100'den fazla okunabilecekse)." Gözlem: KAP ~100 istekten sonra
geçici sınır uyguluyor (iki turda 100 ve 99 sayfa; hemen tekrar deneme yine sınır).
- Okuduğu: takvim bildirimlerinin (context) ve günlük güncellemede metni alınamamış haberlerin sayfaları. Yapay zekâ
  ÇAĞIRMAZ; analiz yine "Haberleri güncelle" ile. KAP 1,5 sn beklemesi korunur.
- Sınırda 3 → 5 → 10 dk bekleyip kaldığı yerden sürer; en fazla 4 saat (sonra "devam_gerek" ile bir sonraki
  açılışta sürer). Sınır olmadan ilerleme yoksa durur ("bu sefer okunamadı"). Boş dönen takvim sayfası "" olarak
  işaretlenir (sonsuz deneme yok); ağ hatası yeniden denenir.
- Kendiliğinden başlama: panel açılışında bekleyen > 100 sayfa varsa ya da önceki iş yarım kaldıysa (KAP sınırı,
  süre, panel kapanması); "Haberleri güncelle" KAP sınırına takılırsa. "📥 Takvim için KAP geçmişini al" artık yalnız
  listeyi alır (~35 sn) ve sayfaları okuyucuya bırakır. Aynı anda tek okuyucu.
- Panel: üstte 15 sn'de bir kendiliğinden yenilenen durum kutusu (okunan/toplam, "X dk bekleniyor, HH:MM civarı
  devam"); bitince özet: okunan sayfa, 15 işlem günündeki şirket olayları ve öne çıkanlar (fiyat düzeltmesi, temettü
  hak kullanımı, genel kurul), metni hazır haber sayısı. Durum `data/kap_okuyucu.json`.
- SQLite bağlantı beklemesi 5 → 30 sn (panel ve okuyucu aynı anda yazabilir).
- Testler: `tests/test_kap_worker.py` (sahte KAP her turda 100 sayfadan sonra sınır; bekleme dizisi 3/5/10, tamamlanma,
  özet, ilerlemesiz durma, süre sınırı, kendiliğinden başlama koşulları, panel kutusu). **260 test geçti.**
- Ek (aynı gün): okuyucu durum dosyasına canlılık zamanı yazar; başka bir işlem/pencere çalışan okuyucuyu görürse
  ikincisini başlatmaz (son kayıt < 5 dk ya da planlanan devam + 5 dk geçmediyse). Özetteki "öne çıkanlar" önce fiyatı
  etkileyenler (bedelsiz/bedelli, temettü hak kullanımı), sonra genel kurul. **Canlı deneme:** kalan 14 sayfa 28 sn'de
  okundu → 213 olay sayfasının tamamı okundu; özet: 23 şirkette 48 olay.
- Yakalanan iki test hatası: iki panel testi boş veritabanında şirket listesini KAP'tan indiriyordu (ağa çıkıyordu;
  KAP 429 verince ortaya çıktı) → test verisine şirket eklendi; tüm takım ağ yasaklanarak çalıştırıldı, ağ denemesi yok.
  Gerçek sorun: ilk kurulumda şirket listesi indirilirken KAP sınırı gelirse panel çöküyordu → anlaşılır mesaj.
  **264 test geçti.**

## 2026-11-07 — Parça B4: birleşik takvim ve makro olay riski (`bist_haber/timeline.py`)

- Hisse ayrıntısında "📅 Önümüzdeki 15 işlem günü — bu hisse için" tablosu: piyasa geneli (PPK, TÜFE, Enflasyon
  Raporu, FİR, PPK özeti, Fed, kredi notu, VİOP vade sonu, Borsa tatili/yarım gün) + bilanço yasal son günü
  (açıklanmadıysa/bilinmiyorsa) + şirket olayları; tarih sırası, kaç işlem günü sonra, ayrıntı (GK türü, brüt temettü).
  Yeni tarih üretmez; mevcut doğrulanmış modülleri birleştirir. Takvimi bilinmeyen dönem ve 2027 dini bayram notu
  tablonun altında. CSV'de "15 işlem günü takvimi" sütunu.
- Risk: vade içinde PPK / TÜFE / Fed / Enflasyon Raporu / kredi notu varsa tek madde "Vade içinde piyasa geneli olay:
  …" (1 puan; tüm hisseleri aynı etkilediği için düşük ağırlık). FİR, PPK özeti, VİOP yalnız takvimde.
- Canlı veride (7 Kasım): FROTO → 12.11 Enflasyon Raporu, 23–24.11 olağanüstü GK, 26.11 temettü hak kullanımı (brüt
  3,07 TL), 27.11 FİR. ETILR → 9.11 bilanço son günü, 13.11 temettü hak kullanımı.
- Testler: `tests/test_timeline.py`. **270 test geçti.** B (olay takvimi) bölümü tamamlandı.

## 2026-11-07 — B son kontrol + A+B bütünleşik test

**Bulunan ve düzeltilenler:**
1. **Geç verilen eski dönem raporu yeni dönem sanılıyordu** (gerçek: BRKO, BTCIM, BSOKE 6 aylık raporları 25.09–02.10;
   MERKO 3 aylık raporu 30.10; TRKNT 6 aylık 06.11). KAP listesindeki year/period artık `news.donem` ("2026/3") olarak
   saklanıyor; bilanço durumu dönemle eşleşiyor. Canlı Finansal Raporlar: 417 × 2026/3, 17 eski dönem.
2. **KAP kayıt boşluğu kesinlik uyduruyordu:** uygulama birkaç gün açılmazsa aradaki günler hiç listelenmiyor, bilanço
   "açıklanmadı" diyebiliyordu. `kap_coverage` tablosu her listelenen günü ve alınma anını tutuyor (gün içinde alınıp
   sonra yenilenmeyen gün eksik sayılır). Boşluk varsa "bilinmiyor (X günün listesi alınmamış)"; güncellemede
   `kap_history.fill_gaps` son 45 günün boşluklarını yalnız takvim için doldurur (yapay zekâ yok), sayfaları okuyucu
   okur. Birleşik takvimde boşluk notu. Canlı veriye gerçek kapsam yazıldı: 24.09–07.11, liste anı 14:37:05.
3. SPK "Finansal Rapor Ek Süre" bildirimleri takvime alındı (5 adet; TRKNT 13.10) → "SPK ek süre talebini
   değerlendirdi; son tarih farklı olabilir".
4. Aynı şirketin olağan ve olağanüstü genel kurulu birbirini siliyordu → tür ayrı tutuluyor (aynı türün güncellemesi
   eskiyi geçersiz kılar). Aynı temettü (GK + hak kullanım) risklerde iki kez sayılıyordu → hak günü varsa tek.
5. **A–B uyumu:** temettü düşüşü SL mesafesinin ≥ yarısıysa senaryo notu + referans plan riski (2 puan) — o gün SL
   yapay tetiklenebilir. 6 aylık süredeki sınırlı denetim varsayımı ekranda. "Ücretsiz dene" de okuyucuyu başlatır.
   Likidite oranlarında ölçüm tarihi (7 Kasım 2026) yazıyor.
6. Testlerde ağ: boşluk doldurma iki pipeline testinde KAP'a çıkıyordu → sahte listeye bağlandı; tüm takım ağ
   yasaklanarak çalıştırıldı (deneme 0).

**Bütünleşik test (gerçek veri):** 761 şirketin bilanço durumu ham KAP listesiyle karşılaştırıldı (çelişki 0;
385 açıklandı, 374 açıklanmadı, 2 süresi geçti = MERKO, TRKNT, ikisi de doğru); 220 şirket olayının hepsi kaynaklı ve
işlem gününde; 79 makro olay hafta içi; 44 hisse × 6 kesim = 264 plan: seviye sırası, risk puanı↔seviye, senaryo riski,
tekrar eden risk satırı, takvim sırası/penceresi/kaynağı → sorun 0. A sınır durum testi 5.714 deneme hata 0. Panel canlı
kopyayla hatasız; "None/nan" metni yok. Takvim modülleri dışında kodda elle yazılmış tarih yok. **282 test geçti.**
**Bilinen sınır:** takvim geçmişi 45 gün; daha önce duyurulmuş uzun süreçler (ör. 2. taksit, uzun sermaye artırımı)
kaçabilir — daha uzun pencere KAP isteği gerektirir, onay alınmadı.

## 2026-11-07 — Takvim geçmişi 180 gün (kullanıcı onayı)

`config.KAP_HISTORY_DAYS = 180` (önce 45). Uzun süreçler (2. taksit, aylar süren sermaye artırımı) kaçmasın diye.
Güncellemedeki boşluk doldurma ve Gelişmiş düğmesi ("takvim için KAP geçmişini tamamla") yalnız LİSTESİ ALINMAMIŞ
günleri çeker (`kap_coverage`). Canlı: yedek `data/yedek/bist_haber_2026-11-07_oncesi_180_gun.db`; 12.05–23.09 (135
gün) 90 sn'de listelendi, +4.112 takvim kaydı; kapsam 180 gün (12.05–07.11). Okunacak sayfa 2.506 = 1.655 takvim +
851 günlük haber metni (kullanıcının 15:02 güncellemesinde KAP sınırı nedeniyle yarım kalanlar; analiz yine
"Haberleri güncelle" ve haber sınırıyla). Sayfaları panel içindeki okuyucu KAP sınırına göre bekleyerek okuyor; 4 saati
aşarsa bir sonraki açılışta sürer. Yeni ilk kurulumda ilk güncelleme 180 günü kendiliğinden listeler (~2 dk).
- 180 gün sonrası kontrol: "süresi geçti" 2 → 96 oldu; 95'i yalnız "Konsolide Olmayan" beyanı olan (çoğu borçlanma aracı
  ihraççısı) ve 30 Ekim'e kadar 9 aylık raporu KAP listesinde olmayan şirketler (doğru; metin "KAP'tan kontrol edin,
  gecikme/ek süre olabilir"). 1'i hata: hem konsolide hem bireysel beyan veren QYATB son bildirimine göre bireysel
  sayılıyordu → herhangi bir konsolide beyan varsa konsolide (II-14.1 Md. 10/5, 11/5). Bütünleşik test sorun 0.
- Okuyucu panel yeniden başlatılınca 15 sn'lik durum kutusundan da kendiliğinden sürdürülür. **283 test geçti.**
- **Yakalanan tasarım açığı:** okuyucu yalnız tarayıcıda panel açıkken çalışıyordu; panel yeniden başlatılıp sekme
  bağlanmayınca 2.506 sayfa bekledi. `baslat.bat` artık panelin yanında `python -m bist_haber okuyucu` bekçisini aynı
  pencerede başlatır (pencere kapanınca biter): 2 dk'da bir bakar, bekleyen > 100 sayfa ya da yarım iş varsa okuyucuyu
  çalıştırır; başka işlemde canlı okuyucu varsa karışmaz; tek bekçi (kilit dosyası); hata bekçiyi çökertmez.
  **287 test geçti.**
- Kullanıcı gözlemi: kutu dakikalarca "0/2506" gösterdi (okuma aslında sürüyordu: ~11 sayfa/20 sn). Okuyucu ilerlemeyi
  yalnız tur sonunda yazıyordu → artık tur içinde her 10 sayfada bir yazar. **288 test geçti.**

## 2026-11-07 — Parça C: işlem günlüğü, performans, pozisyon hesabı (`bist_haber/journal.py`)

Kullanıcı onaylı varsayımlar: (1) panelde "uygun" görünen hissenin en uygun giriş senaryosu kendiliğinden SANAL işlem
olarak kaydedilir (hisse başına tek açık kayıt) + "Bu işleme girdim" ile gerçek işlem ayrıca izlenir; (2) maliyet
alış+satış komisyon %0,20 + kayma %0,10 (Ayarlar'dan değişir; Midas oranı doğrulanmadı); (3) pozisyon hesabı: sermaye
ve işlem başına risk % kullanıcı girer (varsayılan yok) → adet, tutar, SL'de azami kayıp (maliyet dahil); (4) stop
kuralı: TP1'de yarısı satılır, stop girişe çekilir, kalan TP2'ye; olaylar kayda yazılır.
- Değerlendirme kuralları 4.400 durumluk geçmiş testle aynı (kırılım: kapanış alarm üstü → ertesi açılış; limit:
  en düşük ≤ limit; aynı gün SL+TP → SL; limit dolduğu gün TP sayılmaz; en fazla 30 işlem günü; signal_day ve öncesi
  yok sayılır). R planlanan risk mesafesine göre (kırılımda açılış SL altına düşebiliyor — gerçek veride yakalandı).
- Metrikler: kazanma oranı, ortalama/medyan net %, ortalama R, kâr faktörü, maksimum düşüş (R, çıkış sırasıyla),
  işlem başına Sharpe, gerçekleşme oranı; 30 kapanan işlemden azsa "karar için kullanmayın" uyarısı.
- **Gerçek veri çapraz kontrolü:** günlük motoru 44 hisse × 4.400 kesimde önceki simülasyonla aynı gerçekleşme
  (%55/63/57) ve önce-TP1 (%37/33/33) oranlarını verdi; yarı satış + başabaş ile net ortalama −%0,01…−%0,32 (haber
  olmadan avantaj yok — önceki sonuçla tutarlı).
- Panel: "📒 İşlem günlüğü" sekmesi (metrikler sanal/gerçek ayrı, son 200 kayıt, "Bu işleme girdim" formu); senaryo
  kartında pozisyon hesabı (sermaye ve risk girilmişse); Ayarlar'da komisyon, kayma, sermaye, risk %.
- Bekçi günde bir kez açık kayıtların hisseleri + XU100 fiyatını indirip günlüğü günceller (tarayıcı açık olmasa da).
  Yakalanan hata: bekçinin yan bilgi yazması okuyucunun canlılık zamanını tazeliyordu (çökmüş okuyucu canlı
  sanılıyordu) → yalnız okuyucu tazeler.
- Canlı kopya: SOKM (destekten tepki) ve FROTO (kırılım) 6 Kasım sinyaliyle "bekliyor" kaydedildi; pozisyon hesabı el
  hesabıyla tutuyor (100.000 TL, %1 → SOKM 496 adet, azami ≈ 999 TL). **311 test geçti** (ağ yasaklı da).
- Henüz yok: birleşik "fırsat puanı" (günlük ≥ 30 kapanan işlem topladıktan sonra test edilecek), portföy riski
  (sektör/korelasyon), geçmiş benzer hareketlere dayalı vade.

## 2026-11-07 — W: Akıllı Piyasa Bekçisi (kullanıcı isteği) — W1: sinyal geçmişi ve karar izi

İstek: sabah (açılış öncesi) ve akşam (kapanış sonrası) analiz — kullanıcı ELLE başlatır (zamanlayıcı yok); kaçırılan
fırsatlar ve nedenleri; 10 bölümlü akşam raporu; geçmişle karşılaştırma; ayarlar kendiliğinden değişmez (öneri →
onay); rutin işte yapay zekâ yok; otomatik emir yok. Plan: W1 karar izi → W2 sabah/akşam düğmeleri → W3 rapor + arşiv
→ W4 kaçırılan fırsatlar → W5 gelişim takibi ve onay bekleyen öneriler → (W6 isteğe bağlı YZ yorumu, maliyet onaylı).

**W1:** `bist_haber/signals.py` — panelin senaryo hesabı ortak modüle taşındı (panel = bekçi; iki yer ayrışmasın).
Eski ve yeni panel canlı kopyada birebir karşılaştırıldı (121 metin, 14 tablo aynı). Karşılaştırma, taşıma sırasında
silinen bir yardımcı işlevi yakaladı (boş veritabanlı panel testleri hisse ayrıntısını çizmediği için görünmüyordu) →
hisseli panel testi eklendi; bu test de URL'si boş haberde panelin çöktüğünü buldu → düzeltildi.
Karar izi: her çalıştırmada evrendeki her hisse için önerildi/önerilmedi + neden kodu + modül (HABER_YOK,
HABER_ANALIZ_BEKLIYOR, HABER_ONEMSIZ, HABER_OLUMSUZ, SKOR_ESIK_ALTI, TEKNIK_VERI_YOK, VERI_KRITIK, LIKIDITE,
SENARYO_UYGUN_DEGIL, ONERILDI) + seviyeler + riskler + "fiyatlanmış" işareti. `watch_runs` ve `signal_log` YALNIZ
EKLENİR (tetikleyiciler UPDATE/DELETE'i reddeder). Canlı kopya: 761 hisse 9,7 sn; önerilen SOKM, FROTO (panelle aynı).
**317 test geçti.**

## 2026-11-07 — W2: sabah / akşam analizi düğmeleri (kullanıcı elle başlatır)
**Panel:** üstte "🛡️ Piyasa bekçisi" kutusu: **🌅 Sabah analizi** ve **🌙 Akşam analizi**. Zamanlama otomatik değil
(kullanıcı isteği); Windows görev zamanlayıcısı vb. kurulmadı.
- **BIST takvim/saat kontrolü** (`watchdog.timing`): hafta sonu/tatil, sabah 09:40 sonrası, akşam kapanış + 10 dk
  öncesi (yarım günde 12:40) → uyarı verir ama ENGELLEMEZ; uyarı rapora da yazılır.
- **Sabah:** haber/KAP toplama (`pipeline.update_all`; yapay zekâ kutusu varsayılan KAPALI = ücretsiz, açılırsa
  Ayarlar'daki adet sınırı ve tahmini maliyet gösterilir) → tüm evrenin fiyatı (`prices.update_universe`, ücretsiz)
  → işlem günlüğü → karar izi (`log_run`) → önerilenler sanal günlüğe → rapor. **Akşam:** haber toplamadan aynı akış.
- **Sabah raporu (7 bölüm):** gece haberleri (önceki kapanış 18:00'den beri; önemsiz/analiz edilen/bekleyen ayrımı),
  günün fırsatları, takip listesi (skor ≥ 1 ama önerilmeyen + neden), açık sanal/gerçek işlemler (stopa / girişe
  uzaklık), riskli (stopa %2'den yakın — görsel uyarı, karar kuralı değil) ve süresi dolan senaryolar, 5 işlem günü
  takvimi, veri durumu. Akşam raporu şimdilik temel; 10 bölümlü hâli W3.
- **Arşiv:** `data/raporlar/YYYY-MM-DD_{sabah|aksam}[_n].md + .json`; aynı gün yeniden çalıştırma yeni dosya açar,
  eski rapor değiştirilmez. GitHub'a yüklenmez (.gitignore).
- **Fiyatı olmayan şirketler:** KAP evrenindeki 761 şirketin 130'unun Yahoo'da fiyatı yok (çoğu borsada işlem görmeyen
  faktoring/varlık kiralama vb.). Her sabah boşuna 1 yıllık indirme denenmesin diye `data/fiyat_yok.json` ile 7 günde
  bir yeniden denenir; raporda ayrıca listelenir.
- **Geri alınan kural:** "giriş gerçekleşmeden kapanış SL altı → geçersiz" kuralı eklenip GERİ ALINDI: limit emirli
  senaryolarda hiç tetiklenemiyor (o fiyata inen limit zaten dolar), kırılımda ise SL kırılım seviyesine göre olduğundan
  kırılım öncesi fiyat SL altında durabilir → geçerli senaryoyu haksız iptal ederdi. Regresyon testi eklendi.
- **Gerçek veri denemesi (canlı veritabanı kopyası, KAP'a istek atılmadan):** 762 hisse fiyatı, ilk çalıştırma ~250 sn
  (753 hisse 1 yıl), sonraki ~100 sn (artımlı). Karar izi: 2 önerilen (SOKM destek, FROTO kırılım — paneldekiyle aynı),
  2 takip (TOASO, ISCTR: senaryo uygun değil), 432 analiz bekliyor, 173 önemsiz, 152 haber yok. Gece haberleri: KAP 393
  + site 121 (Cuma kapanış sonrası bilanço yoğunluğu; ham kayıtla doğrulandı). Aynı gün 3 çalıştırma → 3 ayrı dosya.
- Testler: `tests/test_watchdog_w2.py` (saat/tatil/yarım gün, akışlar, arşiv değişmezliği, artımlı/eksik fiyat, panel
  düğmesi AppTest). Toplam 332 test, ağ bağlantısı engelliyken 0 bağlantı denemesi.
- **Sırada:** W3 akşam raporu 10 bölüm + "📋 Raporlar" sekmesi; W4 kaçırılan fırsatlar; W5 eğilim/öneri listesi.

## 2026-11-07 — W3: 10 bölümlü akşam raporu ve "📋 Raporlar" sekmesi
**Akşam raporu** (kullanıcının istediği 10 bölüm; yalnız kayıtlı veri, yapay zekâ yok):
1. Piyasa özeti: XU100 değişimi, yükselen/düşen/değişmeyen, medyan, toplam hacim, %9,5+ hareketler; ±%10 limiti
   aşmış görünenler ayrıca uyarılır (bedelsiz/temettü düzeltmesi, halka arz ya da veri hatası olabilir). En çok
   yükselen/düşen 5 hisse yalnız likitlerden (20 gün ort. hacim ≥ 2 mn TL).
2. Öneriler: o günün sabah önerileri + akşam (kapanış verisiyle) önerilenler.
3. Gerçekleşen/devam eden işlemler (bugün girilen, kapanan, süresi dolan, devam eden; sanal/gerçek ayrı).
4. TP1/TP2/SL: bugün görülenler + toplam sonuç dağılımı; temkinli kural notu.
5. Net K/Z: bugün kapananlar (brüt/net %, R, plan büyüklüğüyle TL), gerçekleşmiş toplam, gerçekleşmemiş (açık
   işlem; TP1'de satılan yarı ayrı, çıkış maliyeti düşülmüş tahmini). TL yalnız Ayarlar'da sermaye + risk girildiyse.
6. Maliyetler: varsayım (komisyon + kayma) ve kapanan işlemlerde getiriye etkisi.
7–8. Kaçırılan fırsatlar ve nedenleri: **W4'te** (şimdilik "hazırlanıyor" yazar — uydurma yok).
9. Başarılı/başarısız: son 30 günde kapananlar + sanal toplam metrikler; 30 işlemden az örnekte uyarı.
10. Öneriler: karar izinden kodla gözlemler (analiz bekleyen hisse oranı, senaryo/likidite elemesi, veri hatası);
    hiçbir ayar kendiliğinden değişmez.
Hafta sonu/tatilde çalıştırılırsa son işlem günü verisi kullanılır ve bu yazılır.

**Raporlar sekmesi:** arşivdeki tüm sabah/akşam raporları (en yeni üstte, türe göre süzme), .md ve .json indirme.
Yalnız okunur.

**Doğrulama:** elle hesaplanmış örnek (TP1'de yarı satış, TP2 kapanış, sığ hisse, %30 sıçrama) — rapordaki her sayı
testte bağımsız hesaplandı (ör. 172 adet × 100 × %8,7 = 1.496 TL). Canlı kopya (06.11 verisi): XU100 +%1,32 ham
fiyattan ayrıca hesaplandı, aynı; 630 hissede 424 yükselen / 177 düşen; 580 likit hisse. 335 test, ağsız 0 bağlantı.
**Sırada:** W4 kaçırılan fırsatlar (eşik gerçek dağılımdan, o günkü karar izine göre neden), W5 eğilim + onay listesi.

## 2026-11-07 — W4: kaçırılan fırsat analizi (`bist_haber/missed.py`) — akşam raporu bölüm 7–8
**Tanım:** baz günden sonraki en fazla 5 işlem gününde kapanış, XU100 getirisi düşüldükten sonra baz gün ATR'sinin
en az **4 katı** yükseldiyse "ciddi yükseliş". Eşik gerçek dağılımdan (canlı veri, ~1 yıl, likit hisseler, 133.287
hisse-gün): medyan 0,33 · %90 2,12 · %95 3,01 · **%97,5 3,98** · %99 5,48 ATR → 4 ATR ≈ en güçlü %2,5, gün başına
medyan 14 hisse (3 ATR: 29/gün, fazla gürültülü). Pencerede ±%10,5'ten büyük günlük hareket → "veri şüphesi", dışarıda.
**Geriye dönük bilgi yok:** karar = o gün bekçinin kaydettiği karar (signal_log); kaydı olmayan gün yeniden kurulmaz,
raporda "bekçi kaydı olmayan günler" olarak yazılır. Baz gün = çalıştırma anında kapanışı kesinleşmiş son işlem günü
(sabah → önceki gün; kapanış + 10 dk). ATR/likidite baz gün dahil önceki barlarla; yükseliş yalnız sonraki kapanışlarla.
**Nedenler** (kullanıcının soruları): haber yok / analiz bekliyordu / önemsiz bulundu / olumsuz yorumlandı / skor eşik
altı / teknik filtre (senaryo uygun değil) / likidite / veri eksik-kritik / önerildi ama giriş oluşmadı. Ek etiketler:
*haber karardan SONRA geldi* (o an bilinemezdi; botun hatası sayılmaz), *başlıkta kod geçiyor ama eşleşmemiş* (şirket
eşleştirme), *fiyatlanmış/aşırı yükselmiş uyarısı vardı*. Önerildi ve giriş olduysa kaçırılan sayılmaz (bölüm 9).
Her neden için iyileştirme önerisi; hiçbir ayar değişmez. Son 10 işlem gününün kararları taranır; penceresi tamamlanan
kaçırılanlar `missed_log` tablosuna (yalnız eklenir, değiştirilemez/silinemez) W5 eğilimi için yazılır.
**Düzeltilen sızıntı:** `technical.for_ticker(today=geçmiş gün)` o günden sonraki fiyatları da kullanıyordu (geçmiş gün
hesabında geleceği görme). Artık `date<=today` ile kesiliyor; bugünkü kullanımda davranış değişmez. Test eski kodda
başarısız, yenide başarılı.
**Gerçek veri denemesi (yalnız test kopyası):** 27.10 kararı o günün fiyat/haberiyle yeniden kuruldu (kopya A'da 27.10
19:00 sonrası fiyat ve haber silindi), tam fiyatlı kopya B'de tarandı: 584 likit hisse değerlendirildi, 4 kaçırılan
(QNBTR +%43,8 / 11,5 ATR, KONTR +%59,9, KIMMR +%28,4 — haber karardan sonra, DOAS endeks −%3,5 iken +%11,1). İlk 3'ü ham
fiyattan bağımsız hesapla birebir aynı. Hepsi "haber yok": canlı veritabanında 27.10 öncesi analiz edilmiş haber yok
(beklenen). Not: yeniden kurulumda sonradan yapılmış analizler kalabilirdi; canlıda kararlar kayıttan okunduğu için bu
sorun yok. 343 test, ağsız 0 bağlantı.
**Sırada:** W5 — geçmiş raporlarla eğilim (kaynak, strateji, filtre, tekrar eden nedenler) ve onay bekleyen öneri listesi.

## 2026-11-07 — W5: gelişim takibi ve onay bekleyen öneriler (`bist_haber/trends.py`, 🧭 Gelişim sekmesi)
Kullanıcı isteği bölüm 4'ün soruları, yalnız kayıtlı veriden (yapay zekâ yok):
- **Haber kaynağı / strateji / risk seviyesi:** kapanmış sanal işlemler gruplanır (işlem, kazanma %, ort. R, ort. net %);
  kaynak = sinyal günündeki son olumlu haber etkisinin kaynağı (KAP / site adı).
- **Hangi filtre fazla fırsat eliyor:** `missed_day_stats` (yeni, yalnız eklenir): penceresi tamamlanan her karar
  gününde neden başına değerlendirilen / kaçırılan sayısı. Nedenin kaçırma oranı diğerleriyle iki-oran z testiyle
  karşılaştırılır (Wilson güven aralığı gösterilir).
- **Tekrar eden nedenler:** `missed_log` son 28 gün / önceki 28 gün. **Zamanla iyileşme:** haftalık + son 30 / önceki 30.
**Öneri kuralları** (eşik değil, yeterli örnek + anlamlı fark şartı — "küçük pilotla eşik değiştirme"):
filtre (≥ 200 hisse-gün, ≥ 10 kaçırılan, z ≥ 2,58 ve oran ≥ 1,5 × diğerleri); strateji/kaynak (≥ 30 kapanmış işlem
ve ort. R'nin %95 üst sınırı < 0); kapsam (son 10 çalıştırmanın ≥ 5'inde analiz bekleyen pay ≥ %30); eşleştirme (≥ 3
hissede başlıkta kod geçen eşleşmemiş haber); haber sonra geldi (≥ 5). "Haber yok" bir filtre değildir, önerilmez.
**Onay akışı:** `suggestions` tablosu; metin/kanıt değiştirilemez, karar YALNIZ BİR KEZ (onaylandı/reddedildi + not),
silinemez. Aynı öneri beklerken ya da 30 gün içinde karar verildiyse yeniden eklenmez. **Onay hiçbir ayarı
değiştirmez** (testle doğrulandı: ayar dosyası bayt bayt aynı); ayar önerisini kullanıcı Ayarlar'dan değiştirir, kural
önerisi geliştirme listesine girer. Akşam analizi önerileri günceller; bölüm 10'a gelişim özeti eklenir.
**Test yalıtım hatası düzeltildi:** yeni bir test `pipeline.SETTINGS_FILE` modül yüklenirken sabitlendiği için tüm
testler birlikte çalışınca geliştirme klasöründeki ayar dosyasına yazıyordu (içerik değişmedi; panel klasörüne
dokunulmadı). Test artık geçici dosyaya yönlendiriyor; ayar dosyasının değiştirilme zamanı testlerden sonra aynı.
**Gerçek veri:** canlı veride henüz kapanmış sanal işlem ve tamamlanmış karar penceresi yok → öneri üretilmiyor (beklenen).
27.10 yeniden kurulmuş test kopyasında akşam akışı: `missed_day_stats` = HABER_YOK 584/4 (%0,7), öneri yok; akış 12 sn.
357 test, ağsız 0 bağlantı. **W (bekçi) planı tamamlandı.** İsteğe bağlı W6 (yapay zekâ yorumu) yalnız maliyet
tahmini ve onayla.

## 2026-11-07 — W6: yapay zekâ yorumu (`bist_haber/ai_comment.py`) — kullanıcı onayı: aylık 5–10 $ sorun değil
Üç kullanım, panelde iki kutu (varsayılan KAPALI): 🤖 rapor yorumu (sabah/akşam, 1 çağrı) ve 🤖 kaçırılan fırsat
açıklaması (akşam; yalnız haber metni olan kaçırılanlar — "haber yok / veri / likidite" kodla açık, çağrı yapılmaz;
en fazla 5 YENİ çağrı/akşam, daha önce açıklanan önbellekten ücretsiz gösterilir).
- Model gpt-5-mini (değişmedi), mevcut `analyzer.LLM`, düşünme seviyesi "low", yapılandırılmış çıktı.
- **Sayı uydurma denetimi:** yorumdaki her sayı girdide aranır (Türkçe/İngilizce ondalık biçimi, yuvarlama); 0–10 tam
  sayıları hariç. Bulunamayan sayılar "güvenmeyin" uyarısıyla gösterilir. Kodla hesaplanan bölümler değişmez (testle:
  yorumlu raporun ilk kısmı yorumsuz raporla birebir aynı); dipnot "yalnız 🤖 bölümler yapay zekâ" olarak değişir.
- **Geriye dönük bilgi yok:** kaçırılan açıklamasına yalnız karar anına kadar yayımlanmış haber METNİ verilir; sonraki
  haberlerin yalnız başlığı "KARAR ANINDAN SONRA (o an bilinemezdi)" etiketiyle.
- **Bütçe:** Ayarlar → "Bekçi yapay zekâ yorumu aylık bütçesi" (varsayılan 10 $). Çağrının en kötü durum maliyeti
  (13.000 çıktı tokenı varsayımı) bütçeyi aşacaksa çağrı yapılmaz. Harcama `ai_comments` tablosunda (yalnız eklenir).
  Bütçe yalnız bu yorumlar için; haber analizi maliyeti ayrı.
- **Maliyet tahmini (onaydan önce sunulan):** rapor yorumu 0,005–0,03 $/çalıştırma; kaçırılan açıklaması 0,005–0,03 $/
  hisse → üçü birlikte ayda ≈ 0,7–4,1 $. **Gerçek ölçüm (1 ücretli çağrı, test kopyası, 06.11 akşam raporu):** 2.549
  girdi + 695 çıktı token = **0,0020 $**, doğrulanamayan sayı yok → tahminin altında (Türkçe rapor ~2,6 karakter/token;
  düşük düşünme). Kaçırılan açıklaması gerçek veride denenemedi: kopyadaki 4 kaçırılanın hepsi "haber yok" (metin yok,
  kurala göre çağrı yapılmadı); sahte istemcili testlerle doğrulandı.
- Testler `tests/test_ai_comment.py` (sahte istemci, ücretsiz). 368 test, ağsız 0 bağlantı.

## 2026-11-07 — Destek (tepki) senaryosu düzeltmesi: bugünkü dip destek sayılmaz (kullanıcı onayı)
**Bulgu (gerçek veri, bekçi akşam raporu):** SOKM 06.11 — olumlu bilanço haberi, ertesi gün 6 kat hacimle %−9,9.
"20 günlük destek" = o günün kendi dibi (48,38) olduğu için fiyat "desteğe yakın" sayıldı → tepki senaryosu "uygun",
hedef 20 EMA (54,84), risk/getiri "iyi". Yani çöküş gününde tepki alımı öneriliyordu (düşen bıçak).
**Ölçüm (önbellekteki 44 hisse × ~3 yıl, haber yok, journal.evaluate kuralları + maliyet):** destek = bugünkü dip olan
tepki senaryoları ort. −0,02 R, SL %70, kazanma %33 (n=328 kapanan); önceden oluşmuş destek +0,14 R, SL %59, %42
(n=648). Kazanma oranı farkı anlamlı (z ≈ 2,7).
**Değişiklik:** `technical.analyze` yeni alanlar `onceki_destek_20g/60g` = bugün HARİÇ önceki 20/60 günün en düşüğü.
`entries.bounce` yalnız bunları kullanır; fiyat önceki 20 günlük desteğin altındaysa "destek kırıldı, yeni dip
oluşuyor" → senaryo yok (altında yakın 60 günlük eski destek varsa o kullanılır). `destek_20g` (panel tablosu,
tradeplan) değişmedi. SOKM artık: önceki destek 51,50 > fiyat 48,44 → tepki senaryosu yok, öneri yok.
**Yeniden ölçüm:** 4.400 durumluk A2 testi (tam çıkış TP1'de, maliyet yok): destek uygun 1.955 → 1.706; TP1 önce %34 →
%36; SL önce %65 → %63; ort. getiri %0,26 → %0,19 (karışık/küçük); diğer senaryolar aynı, tutarlılık ihlali 0.
Kalan "yeni dip günü" vakaları: (a) yakında 60 günlük eski destek +0,41 R (n=36, az), (b) fiyat gün içinde önceki
desteği kırıp üstüne döndü −0,10 R, SL %68 (n=130) — fark anlamlı değil (z ≈ 1,5): **kural değiştirilmedi** (küçük
örnekle değiştirme yok); W5 strateji takibi izleyecek. 370 test, ağsız 0 bağlantı.

## 2026-11-08 — Son A+B bütünleşik testi (180 günlük takvim verisiyle)
Okuma durumu (01:41): 95 sayfa kaldı — 90 takvim sayfası (hepsi Mayıs 2026) + 5 haber metni. Okunmuş Ağustos–Eylül
sayfalarından ileri tarihli olay çıkmadığı için test bekletilmedi; okuyucu arka planda sürüyor.
**Sonuç (canlı kopya, `integration_ab.py`):** sorun 0. Denetlenen: 761 bilanço durumu (ham KAP listesiyle çelişki 0),
**1.391 şirket olayı** (45 günlük testte 220) — hepsi kaynaklı, işlem gününde; 79 makro olay; 44 hisse × 6 kesim = 264
plan. Bilanço dağılımı: açıklandı 385, açıklanmadı 281, süresi geçti 95.
**"Süresi geçti" 2 → 95 incelendi:** 95'in hepsi konsolide olmayan (180 günlük veride Ağustos 6 aylık raporundan
öğrenildi → son tarih 9 Kasım yerine 30 Ekim; doğru) ve **hiçbirinin borsada fiyatı yok** (faktoring, varlık kiralama:
ADLVY, AKCVR, AKDFA, AKFK, AKSFA, AKTVK…). SPK II-14.1 (RG 29968, 03.02.2017, metinden okundu): ara dönem 3/6/9 aylık
rapor yükümlülüğü "ihraç ettiği sermaye piyasası araçları borsada işlem gören" işletmeler vb. için; pay dışı araç ihraç
eden halka açık olmayan işletmeler "ihraç ettikleri araçların itfa tarihine kadar" tabidir. Aracın dolaşımda olup
olmadığı verimizde yok → "süre geçti" kesin değil. **Değişiklik (yalnız açıklama metni):** `earnings.status` →
`fiyat_var`; fiyatı hiç olmayan şirkette açıklamaya bu mevzuat uyarısı eklenir. Risk hesabı/öneri etkilenmez (bu
şirketler için zaten senaryo yok). 370 test, ağsız 0 bağlantı.
**Bekçi yeniden başlatma hatası (2026-11-08, bulundu ve düzeltildi):** panel yeniden başlatılınca kapatılan eski
bekçinin kilit dosyası (nabız) birkaç dakika taze kalıyordu; yeni bekçi "başka bekçi çalışıyor" deyip HEMEN çıkıyor ve
bir daha denemiyordu → bir sonraki başlatmaya kadar arka plan okuma ve günlük işlem günlüğü güncellemesi yoktu
(01:53 yeniden başlatmasında görüldü; o an okunacak sayfa kalmadığı için kayıp yok). Artık kilitte sahip (süreç no)
var; yeni bekçi taze yabancı kilitte 2 dk'da bir bakarak bekler, kilit bayatlayınca devralır. Test eski kodda
başarısız, yenide başarılı. Okuma sonucu: 95 sayfanın 90'ı okundu; 5 sayfa KAP'tan boş/hatalı geldi, bir sonraki
güncellemede yeniden denenir. 371 test, ağsız 0 bağlantı.

## 2026-11-09 — Plan 1.1: analiz sırası önceliği (`analyzer.pending`)
Ölçüm (08.11): 961 bekleyen haberin 887'si likit hisselere ait (ilk sayımımda canlı veritabanında yalnız 9 hissenin
fiyatı olduğu için yanlış sınıflandırmıştım — tüm BIST fiyatı ancak ilk "Sabah analizi"nde iner; düzeltilmiş ölçüm test
kopyasının fiyatlarıyla yapıldı). Güncelleme başına 10 haber sınırıyla bu kuyruk erimiyor.
**Yeni sıra (maliyet değişmez, aynı adet):** 0 açık/bekleyen işlemi olan hisse → 1 likit (20 gün ort. hacim ≥ 2 mn TL)
ya da eşleşmesiz haber → 2 sığ → 3 fiyatı hiç olmayan; her grupta en yeni önce. "Fiyatı yok" yalnız evrenin fiyatı
indirilmişse (≥ 200 hisse) geri plana atılır; aksi hâlde kimse geri itilmez (eski sıra).
**Gerçek kuyrukta (1.001 bekleyen, tüm BIST fiyatlarıyla):** ilk 10 eski sırada 9 likit + 1 sığ → yeni sırada 10'u da
açık işlem (SOKM, FROTO, TCELL; FROTO ve SOKM bilançoları dahil 13 haber bekliyordu). İlk 50: eski 48 likit; yeni 13
açık işlem + 37 likit. Likidite katmanının şimdiki etkisi küçük (bekleyenin %92'si zaten likit); asıl kazanç açık
işlemler. Kuyruğun kendisi bununla erimez → Plan 2.1 (maliyet tahmini, onay).
Ayrıca: panel takvim tablosunda "Kaç işlem günü sonra" sütunu sayı + "—" karışıktı (bugün olayı olunca tablo dönüştürme
uyarısı) → hep metin. 374 test, ağsız 0 bağlantı.

## 2026-11-09 — Sistem geneli uçtan uca kontrol + veri kaynağı (uydurma veri) denetimi (kullanıcı isteği)
Canlı veritabanı KOPYASI + tüm BIST fiyatları, ağ kapalı; gerçek panel ayarları/verisi değişmedi (dosya zamanlarıyla
doğrulandı). Betikler: scratchpad `e2e_check.py`, `provenance_audit.py`, `concurrency_check.py`.
**Panel akışları (AppTest, gerçek veri):** açılış (6 sekme, 18 tablo), Sabah/Akşam analizi, Raporlar (seçim + süzgeç),
gerçek işlem kaydı, ayar kaydı, ağsız Ücretsiz dene / Takvim kontrolü / KAP geçmişi.
**Bulunan ve düzeltilenler:**
1. Düğme hataları ve saat uyarısı `st.rerun()` yüzünden kullanıcı göremeden siliniyordu (Haberleri güncelle,
   Ücretsiz dene, Sabah/Akşam analizi) → `flash()`: mesaj yenilemeden sonra gösterilir; başarı mesajı da eklendi.
2. Teknik İngilizce hata ("HTTPSConnectionPool… Max retries") → `nice_err()`: "www.kap.org.tr adresine bağlanılamadı…".
3. Takvim kontrolü ağsız başarısız olunca mesaj yoktu → hangi kaynağın okunamadığı yazılır; TÜİK satırı tabloda yoktu.
4. "Kaydet"e ikinci kez basınca veritabanı hatası paneli ÇÖKERTİYORDU → yinelenen kayıt, ileri tarih, sinyal gününden
   önce alış ve SL–TP2 aralığı dışı fiyat (yazım hatası) açık Türkçe uyarı; beklenmeyen hata da yakalanır.
5. Senaryo ve işlem günlüğü tablolarında boş hücreler "None" görünüyordu → "—".
6. "Olumlu haber sinyali yok" metni skor olumlu ama eşik altıyken de yazıyordu (FROTO 1,19) → "olumlu ama zayıf ya da
   eskidi (skor X; en az 1,50)".
7. KAP geçmişi düğmesi "0 eklendi, okunacak sayfa kalmadı" → liste eksiksizse bunu açıkça söyler.
8. Rapor listesi etiketi beklenmeyen değerde çökmeye açıktı → dayanıklı.
**Veri kaynağı denetimi (uydurma veri var mı):** fiyat 154.426 satır — OHLC çelişkisi 0, hafta sonu/tatil fiyatı 0,
negatif/boş 0; ±%10,5 sıçrama 23 (bölünme/bedelsiz/veri hatası adayları; ör. DUNYH 09.11 −%88,8 → sistem "veri kritik"
işaretliyor, senaryo üretmiyor). Yapay zekâ etkileri: aday listesi dışında hisse 0, haberi olmayan etki 0; gerekçedeki
40 sayıdan 39'u haber metninde, 1'i (TOASO "piyasa değeri ~120,6 milyar TL") yapay zekâya bağlam olarak verilen Yahoo
piyasa değeri (120.599.998.474 TL) — uydurma değil. Şirket olayı 1.434 — tarihi kaynak KAP metninde bulunamayan 0.
Bilanço "açıklandı" 398 — KAP kaydı olmayan 0. Makro olay doğrulama etiketi olmayan 0. Haber skoru elle formülle
aynı (8/8). İşlem günlüğü yeniden hesapla aynı (3/3). Panel kararı = bekçi kararı; rapor önerileri = karar kaydı;
aynı hissede çift açık sanal kayıt yok.
**Eşzamanlı yazım:** ayrı süreçte 1.168 okuyucu-benzeri yazım sürerken sabah + akşam analizi: kilit hatası 0.
**Kalıcı testler:** `tests/test_panel_flows.py` (4; eski kodda 3 başarısız + 1 hata), `test_journal` kayıt korumaları.
379 test, ağsız 0 bağlantı. Not: fiyatın tek kaynağı Yahoo (gecikmeli); bağımsız ikinci kaynakla karşılaştırma yok.

## 2026-11-09 — Öncelikli plan: W5 olay türü eksiği + 1.2 Streamlit uyumluluğu
**W5 eksiği tamamlandı:** Gelişim sekmesinde "Haberin olay türüne göre" (bilanço, yeni iş, geri alım…) başarı tablosu
ve öneri kuralı (≥ 30 kapanmış işlem ve ort. R'nin %95 üst sınırı < 0). Olay türü = sinyal günündeki son olumlu haber
etkisinin türü. Etiketler ortak `bist_haber/labels.py` (panel + gelişim). Gelişim tablolarında boş değer "—".
**1.2:** `use_container_width=True` (20 yer; Streamlit'te kaldırılıyor) → `width="stretch"`; kurulumda
`streamlit>=1.50,<2` (eski sınır 1.38 yeni parametreyi desteklemiyordu). Test çıktısında kullanımdan kalkma uyarısı 0;
uçtan uca kontrol temiz. 380 test, ağsız 0 bağlantı.
**1.3 Kullanım kılavuzu:** `KULLANIM.md` (açma, günlük sabah/akşam akışı, maliyetler, sekmeler, senaryo kartı, ayarlar,
bilinmesi gerekenler) + panelde "❓ Nasıl kullanılır" bölümü; README'den bağlantı. Test: kılavuzdaki 14 düğme/sekme adı
panel kodunda birebir var. 381 test.
**Kayma ölçümü (gerçek işlemlerden):** `journal.slippage_stats` — gerçek alış fiyatı ↔ aynı senaryonun sanal giriş
fiyatı (sanal gerçekleştiyse onun dolumu, değilse planlanan giriş); yalnız alış tarafı (satışlar kaydedilmiyor).
İşlem günlüğünde gerçek işlemlerin altında ortalama/medyan/en kötü ve ayar varsayımının alış payıyla karşılaştırma;
10 işlemden az örnekte "varsayımı değiştirmeyin" uyarısı. Ayar kendiliğinden değişmez. 382 test.

## 2026-11-09 — Haber analizi: aylık bütçe, eski haber kuralı, 🔬 Haber analizi bölümü, derin yeniden inceleme
Kullanıcı isteği: ayrı analiz düğmesi (kaç haber, tahmini maliyet), kullanıcının seçtiği haberlerin analizi ve "olumlu/
olumsuz işaretlenmiş" (analiz edilmiş) haberlerin derin yeniden incelenmesi; benim önerim: haber analizine de bütçe.
- **Aylık bütçe** (Ayarlar → "Haber analizi aylık bütçesi", varsayılan 10 $): tüm yollar (Haberleri güncelle, sabah
  analizi, 🔬 bölümü, derin inceleme). Harcama `analyses` token × fiyat (ön eleme + analiz + ikinci görüş birlikte) +
  derin incelemede yerine yazılan önceki analizin maliyeti (`reanalysis_log.eski_*`; aksi hâlde kaybolurdu).
  **Bütçe denetimli sıra:** bir haber ancak gerçek harcama + çalışan haberlerin üst tahmini + kendi üst tahmini bütçeye
  sığarsa başlatılır; her biten haberden sonra gerçek harcama yeniden okunur. Üst tahmin = gözlenen en pahalı haber
  çıktısı × 1,25 ya da 2 × ortalama (geçmiş yoksa 16.000 token) — eski üst tahmin (2 × ortalama) gerçek en pahalı haberin
  (0,0279 $) altında kalabiliyordu → testte bütçe aşımı yakalandı, düzeltildi.
- **Eski haber kuralı:** 5 günden eski haber kendiliğinden analiz edilmez (elle seçilebilir). Ayarlar adet seçenekleri
  1/3/5/10/20/30 (sınır 50; elle bölümde 300).
- **🔬 Haber analizi** (📰 Haberler sekmesi): bekleyen haberler tablosu (öncelik, tarih, yaş, hisse, konu, başlık; hisse /
  öncelik grubu / eski haber süzgeci), "ilk N (öncelik sırasıyla)" ya da "yalnız işaretlediklerim", seçime göre tahmini
  maliyet (alt–üst), bu ay harcanan / bütçe / kalan, bütçeye sığmayan sayısı; sonuçta gerçek maliyet.
- **🔁 Derin yeniden inceleme:** son 14 günün analiz edilmiş haberleri (varsayılan yalnız olumlu/olumsuz; isteğe "⚠️
  kontrol gerektirenler": çelişkili / tek görüş / etki belirsiz), en yüksek doğruluk + ZORUNLU ikinci görüş + iki kat
  metin; önceki sonuç `reanalysis_log`'da (yalnız eklenir), önce → sonra tablosu. Habere sonradan gelen fiyat hareketi
  verilmez (geriye dönük bilgi yok). Tam metni olan haber sitesi haberinde metin yeniden indirilmez/iki kez eklenmez
  (testte yakalandı; ayrıca adres yoksa indirme denenmez).
- **B seçeneği tahmini (canlı kopya, tüm BIST fiyatlarıyla):** 6–9 Kasım, açık işlem + likit: 296 haber (250 KAP, 46 site)
  → 3,71–9,85 $ (temkinli üst tahmin). Çalıştırılmadı: kullanıcıya verdiğim "üst uç 8 $'ı aşmazsa" sınırının üstünde →
  onay bekleniyor. 390 test, ağsız 0 bağlantı; uçtan uca kontrol temiz.

## 2026-11-09 — D aşaması 1: piyasa rejimi (`bist_haber/regime.py`) — yalnız bilgi, kararları değiştirmez
Tanımlar: trend = BIST 100 kapanış > EMA50 > EMA200 "yükseliş", tersi "düşüş", diğer "kararsız"; oynaklık = son 20 gün
ATR% değerinin son ~1 yıldaki yüzdeliği (< %30 düşük, > %70 yüksek); genişlik = likit hisselerin (20 gün ort. hacim ≥ 2 mn
TL) kendi EMA50 üstünde kapanan yüzdesi. Gün = verilen günde ya da öncesinde son fiyat günü (sonraki gün testle dışarıda).
Nerede: sabah raporu başı ("📊 Piyasa durumu"), akşam raporu bölüm 1, panel üst özet (fiyat günü değişince hesaplanır),
bekçi karar kaydı özetine `rejim` (ileride rejime göre başarı). Gerçek veri (06.11): düşüş (11.483; EMA50 12.320, EMA200
12.935), oynaklık yüksek (ATR %2,61, yılın %90'lık dilimi), genişlik %9 (574 likit hisse); 0,5 sn.
**Doğrulama:** EMA50 pandas ile birebir; EMA200'de 12.935 vs 13.011 farkı → modül TA-Lib yöntemiyle (SMA başlangıçlı)
birebir aynı (12.934,5); fark yalnız 251 günlük geçmişte başlangıç değeri duyarlılığı. Düzeltme: BIST 100 geçmişi 600
günden kısaysa sabah analizi bir kez 3 yıl indirir. **Bilinen sınır:** hisselerin EMA200'ü de 1 yıllık geçmişle
(TA-Lib yöntemi) hesaplanıyor; daha uzun geçmiş indirme süresini artırır, şimdilik değiştirilmedi. 394 test.

## 2026-11-09 — B seçeneği (önemli konular) sonucu, canlı ilerleme, panel hızı
**B — yalnız önemli konular (kullanıcı onayı):** 6–9 Kasım, likit hisselerin Finansal Rapor (92) + Özel Durum (46) +
Yeni İş İlişkisi (3) + açık işlem (1) = 142 haber. Tahmin 1,78–4,72 $ → **gerçek 2,20 $**, 142/142 analiz, hata 0,
26,5 dk. Sonra panelde olumlu 50 / olumsuz 43 hisse (önce 3 / 3; kural değişmedi — analiz edilmemiş haber skor üretmez).
**Uydurma denetimi (151 etki):** aday dışı hisse 0. Gerekçelerdeki 1.416 sayının 1.409'u haber metninde ya da yapay
zekâya verilen bağlamda (piyasa değeri, son fiyat); kalan 7'si metindeki sayılardan hesap (ör. REEDR 1.925.450.870 −
673.200.619 = 1,25 mlr TL ✓) ya da tarih/yıl. Sayı denetleyicisi geliştirildi: birim dönüşümü (TL → mn/mlr TL) ve yıl
kısaltması (3Ç'26) tanınır — önceden yanlış "bulunamadı" veriyordu.
**Canlı ilerleme (kullanıcı: "ilerleme barı yok", "kendisi güncellensin, incelenen hisseyi göstersin"):** analiz durumu
`data/analiz_durumu.json` (yalnız gerçek kullanım yolları yazar; testler yazmaz — testte yakalandı, .gitignore).
Panel üstünde 10 sn'de bir yenilenen kutu: ilerleme çubuğu, canlı olumlu/olumsuz sayısı, "⏳ şu an inceleniyor"
(paralel 5 haber), "✅ son biten" (ör. AKGRT olumlu 4/5), gerçek maliyet. Yeni sonuç geldikçe TÜM sayfa (liste ve
sayılar) kendiliğinden yenilenir: en az 30 sn arayla, sayfa çizimi uzunsa çizim süresinin 3 katı (sürekli yenilenme
döngüsü olmasın); bitince bir kez. Not: B analizi panel dışından eski kodla başladığı için kutuda görünmedi.
**Panel hızı:** çok hisse haberli olunca açılış 32 sn oldu (sorguların %94'ü; KAP metinleri büyük, `candidates` sütunu
`body`den sonra → her hisse araması metinleri okuyordu). Dizinler (`subject`, `published_at`, `subject+candidates+source`)
+ "ile başlar" aramaları aralık olarak + `INDEXED BY` + teknik olay uyarısında iki adımlı arama: 126 hissede 33 → 5 sn,
panel açılışı 32 → 7 sn. Çıktılar eski kodla birebir aynı (126 hissenin plan/risk/bilanço/takvimi karşılaştırıldı).
396 test, ağsız 0 bağlantı; uçtan uca kontrol temiz.

## 2026-11-09 — Vade profili testleri (kullanıcı vadesi: en fazla 1–2 hafta) → kurallar DEĞİŞMEDİ
Önbellekteki 44 hisse × ~3 yıl, haber yok, journal.evaluate kuralları + %0,30 maliyet, 5 günde bir kesim (örtüşen
pencereler → belirsizlik gösterilenden büyük). Ort. R (95% aralık):
- 1–2 ay denemesi (kullanıcı önce "uzun vade" dedi, sonra 1–2 hafta olarak netleştirdi): A mevcut +0,02 (±0,08) · B orta
  (stop 1,5×, hedef 14 ATR, 40 gün) +0,06 · **D geniş (stop 2×, hedef 20 ATR, 40 gün) +0,11 (±0,08)** · E = B + TP1
  sonrası iz süren stop (en yüksek kapanış − 2 ATR) +0,05 · C = B + haftalık trend (fiyat > ~30 hafta EMA) −0,05.
  Haftalık trend ve iz süren stop işe yaramadı. D uygulanmadı (vade 1–2 hafta).
- 1–2 hafta: A mevcut (30 gün, hedef 10 ATR) **+0,02, ort. süre 10 gün** · K1 (10 gün, hedef 6 ATR, geçerlilik 5/5/3)
  −0,02 · K2 (K1 + stop 0,8×) −0,03 · K3 (yalnız 10 gün sınırı) −0,03. Kısaltma kazanma oranını %38 → %40–42 artırıyor
  ama kazançları kestiği için ortalama biraz düşüyor; işlemlerin %27–35'i süre dolarak kapanıyor; farklar belirsizlik
  içinde. **Sonuç: mevcut kurallar 1–2 haftalık vadeye zaten uygun (ortalama 10 işlem günü); değiştirilmedi.**
  Uzun fiyat geçmişine (2–3 yıl) gerek yok; 1 yıl yeterli (EMA200 yalnız genel trend bilgisi).

## 2026-11-09 — D aşaması 2: sektör karşılaştırması ve portföy riski (`bist_haber/sectors.py`) — yalnız bilgi
**Kaynak:** KAP Sektörler sayfası (JavaScript ile yükleniyor; uygulamanın tarayıcısında okundu, hiçbir şey
gönderilmedi) → `bist_haber/sektorler.json`: 15 ana sektör, alt sektörler, 631 pay kodu (çok pay gruplu şirkette her
kod ayrı; 3 harfli borçlanma kodları atıldı). Aktarım doğrulaması: tarayıcıda ve Python'da SHA-256 aynı (testte de
kontrol edilir). Kapsam: fiyatı olan 631/631, likit 580/580 hisse. Alındığı tarih dosyada (2026-11-09); KAP sınıflaması
nadiren değişir, gerekirse aynı yolla yenilenir.
- **Hisse ↔ sektör** (hisse ayrıntısında "🏭 Sektör"): 5 ve 20 günlük getiri ↔ karşılaştırma grubunun ortancası ve
  gruptaki SIRA (eşik/etiket uydurulmaz). Grup: alt sektör; kendisi hariç 3'ten az likit hisse varsa ana sektör.
  Gerçek veri (06.11): SOKM 5 gün %−6,6, perakende ortancası %+8,5 (18 hisse içinde 17.) → düşüş hisseye özgü.
- **Akşam raporu bölüm 1:** günün en iyi / en zayıf 3 ana sektörü (likit hisselerin günlük değişim ortancası).
- **Kaçırılan fırsatlar:** "Sektör %" sütunu — aynı pencerede sektörün ortanca getirisi (yükseliş sektör geneli mi?).
- **Portföy riski** (İşlem günlüğü sekmesi + sabah raporu): açık/bekleyen işlemlerin sektörleri; aynı alt sektörde ≥ 2
  işlem, tek ana sektörde ≥ %50 (≥ 3 işlem), 60 günlük günlük getiri korelasyonu ≥ 0,7 olan çiftler için uyarı.
- Hız: fiyatlar bağlantı+gün başına bir kez okunur (126 hisse 0,5 sn; panel açılışı 7,5 sn). 402 test, ağsız 0 bağlantı.
