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

## 2026-11-09 — Görünüm düzenlemesi (kullanıcı: "dağınık, önemli bilgiler beyaz üstüne açık gri gibi silik")
- Yalnız sunum değişti; hesap, karar, metin içerikleri ve düğme adları aynı (kılavuz testi düğme adlarını doğruluyor).
- Silikliğin asıl nedeni: Streamlit açıklama yazılarını (`st.caption`) %60 saydam çiziyor → `opacity: 1`, koyu
  renk (#334155), biraz daha büyük yazı. `.news-meta` da koyulaştırıldı.
- Tema (`.streamlit/config.toml`): indigo ana renk, kenar/yuvarlaklık, tablo başlığı rengi.
- Üst bant: koyu lacivert, kuyruklu yıldız (Halley) süsü, tarih / son güncelleme / "emir vermez" etiketleri.
- Piyasa bekçisi tek kartta: iki düğme yan yana, yapay zekâ seçenekleri tek satırda üç kutu.
- Piyasa durumu gri yazı yerine renkli şerit (trend düşüş → kırmızı kenar, yükseliş → yeşil).
- Özet kutuları: olumlu yeşil, olumsuz kırmızı üst çizgi ve sayı rengi.
- Fırsat özeti uzun paragraf yerine hisse etiketleri; kenar rengi = risk (yeşil düşük, turuncu orta, kırmızı yüksek).
- Olumlu/olumsuz/izlenecek listeleri: renkli kenarlı kartlar, başlıkta hisse sayısı.
- Sekmeler hap düğme görünümünde; seçili sekme renkli.
- Hisse ayrıntısındaki kutularda sayılar artık "4.48…" diye kesilmiyor.
- Akşam analizi uyarısı "(kapanış 18" diye yarım kalıyordu (saatteki iki nokta yüzünden) → düzeltildi.
- İşlem günlüğünde her portföy uyarısı ayrı sarı kutuydu (7 kutu) → tek kutuda madde listesi.
- Kullanıcı geri bildirimi: üst bant ile Ayarlar bitişikti → bant altına 18 px boşluk (ölçüldü: 0 → 18 px).
- Doğrulama: panelin kopyası API anahtarsız ve çevrimdışı kipte (HALLEY_OFFLINE=1, yalnız 127.0.0.1) ayrı portta
  açılıp ekran görüntüleriyle kontrol edildi; 402 test geçti.

## 2026-11-09 — Karanlık mod (kullanıcı: "karanlık mod çalışmıyor, beyaz ekran göz yoruyor")
- Neden çalışmıyordu: `.streamlit/config.toml`'daki özel tema, Streamlit'in Ayarlar menüsünde temayı "Custom Theme"e
  kilitliyor (koyu seçilemiyor); ayrıca eklediğimiz CSS renkleri açık temaya sabitti.
- Çözüm: üst bantta "🌙 Karanlık mod" düğmesi. Seçim `data/ayarlar.json` → `karanlik_mod`. Tema her çalıştırmada
  `streamlit.config.set_option("theme.*")` ile uygulanır (Streamlit 1.50'de oturum başına tema API'si yok; tek kullanıcılı
  yerel uygulama olduğu için genel ayar sorun değil). Tema değişince sayfa bir kez yenilenir (oturum başına tek sefer
  korumalı, sonsuz döngü yok). Tüm özel renkler CSS değişkenine çevrildi; iki renk takımı var (açık / koyu).
- Not: `streamlit.config.set_option` resmi ama "scriptable" olmayan seçenekler için belgelenmemiş kullanım; Streamlit
  sürümü yükseltilirse karanlık mod düğmesi yeniden denenmeli (test: `test_dark_mode_toggle_is_saved_and_applies_theme`).
- Ayrıca bulunan gerçek risk: `ayarlar.json` başına BOM eklenirse (Not Defteri ile kaydetme) dosya okunamıyor ve bir
  sonraki kayıtta TÜM ayarlar (bütçeler, kalite, komisyon) sıfırlanıyordu → `load_settings` artık `utf-8-sig` ile
  okuyor (test: `test_settings_file_with_bom_is_not_lost`).
- Doğrulama: önizleme kopyasında (çevrimdışı, yalnız 127.0.0.1) açık→koyu→açık geçişi, koyu kayıtlıyken yeniden
  başlatmada ilk açılışın koyu gelmesi, hisse ayrıntısı ve tablolar ekran görüntüsüyle kontrol edildi; 404 test geçti.

## 2026-11-09 — 2.2 adım 1: pilotun kalan bildirimleri analiz edildi (haber sinyalinin katkısı, küçük örnek)
- Önce yedek: `data/yedek/pilot_oncesi_2026-11-09.db`. Analiz: 68 bildirim (8'i önceden yapılmıştı) → toplam 76 analizli;
  19 belge eksik/taranmış PDF (analiz edilmedi), 13 bildirimin fiyatı yok (ölçüme katılmadı, uydurma fiyat yok).
- Maliyet: bu çalıştırma 0,726 $; pilot toplamı 0,807 $ (onaylanan üst sınır 1,5 $).
- Ölçüm (`backtest.evaluate`, giriş = bildirimden sonraki ilk seans açılışı, çıkış = n. seans kapanışı, XU100'e göre,
  0,20 % maliyet düşülmüş; eksik gün kaydırılmadı):
  - Olumsuz (9 etki): 3 gün ort. −5,95 %, 5 gün −6,32 % (ortanca −4,33 %), doğru yön 7/9.
  - Olumlu (38): 5 gün ort. −1,66 % / ortanca +1,09 %, 10 gün ort. −0,50 % / ortanca +1,75 %; doğru yön 20–21/38 (~%55,
    yazı-tura düzeyine yakın).
  - Güçlü olumlu (etki ≥3 ve güven ≥0,7; 9 etki): 10 gün ort. +10,35 %, ortanca +4,90 %, 7/9 pozitif.
  - Nötr (29): 10 gün ort. −5,88 % — dönemin bu küçük/orta hisseler için genel olarak zayıf olduğunu gösteriyor (örnek seçimi
    etkisi olabilir).
  - 40 ölçümde giriş/çıkış günü tek fiyat (tavan/taban kilidi olabilir) notu var: bu işlemlerin bir kısmı gerçekte
    yapılamayabilirdi.
- Uydurma sayı denetimi: gerekçelerdeki 258 sayının 245'i modele verilen belge metninde birebir var; kalan 13'ün tamamı
  elle kontrol edildi: tarih yazım farkı veya belgedeki sayılardan yapılmış doğru hesap (ör. 750.000 × 6,58 = 4.935.000;
  92,6 mn × 158,90 ≈ 14,7 mlr). Uydurma sayı bulunmadı.
- Yorum: örnek çok küçük (olumsuz 9, güçlü olumlu 9) → hiçbir eşik DEĞİŞTİRİLMEDİ (kullanıcı kuralı). Sinyal en çok
  "güçlü olumlu" ve "olumsuz" gruplarında umut verici; genel "olumlu" grubu tek başına ayırt edici görünmüyor.
  Doğrulamak için 2. adım (≈600 bildirim, 6–10 $) gerekir — kullanıcı kararı bekliyor.
- Betikler: scratchpad `run_pilot_step1.py`, `pilot_eval.py` (repo dışında; salt okuma kopya üzerinde).

## 2026-11-09 — Karanlık mod iyileştirmesi + Windows kurulum paketi (Halley_Kurulum.exe)
- Karanlık mod: düğme, giriş kutusu ve uyarı renkleri artık temaya bırakılmıyor, iki tema için CSS değişkenleriyle açıkça
  veriliyor (tema sonradan değişince tarayıcı eski beyaz düğme rengini tutabiliyordu). Koyu zemin biraz yumuşatıldı
  (#0D1322), üst bant koyu temada mor-indigo, uyarılar: sarı/mavi/yeşil/kırmızı kenarlı, okunur yazı. Açık tema da aynı
  kurallarla (ölçüldü: koyu düğme #1A2338, üstüne gelince #262F55 + indigo kenar; açık #FFFFFF → #EEF2FF).
- Kurulum paketi (`paket/`): PyInstaller KULLANILMADI (Streamlit+pandas+pyarrow ile kırılgan). Bu bilgisayardaki
  gerçek Python 3.9.13 + sanal ortamdaki kütüphaneler olduğu gibi kopyalanır, VC++ çalışma zamanı DLL'leri yanına konur.
  - `paket/Halley.cs` → Halley.exe (C# 5, Windows'taki .NET 4 derleyicisi): siyah pencere yok, panel + okuyucu başlatır,
    saat yanında simge (Paneli aç / Günlük klasörü / Kapat), tek kopya (ikinci açılış paneli öne getirir), `--kapat`,
    `--kaldir` (verileri Belgeler'e taşıma seçeneği), port doluysa sonraki boş port. Günlükler: app\data\gunluk\.
  - `paket/Kurulum.cs` → Halley_Kurulum.exe: tek dosya (155 MB), %LOCALAPPDATA%\Programs\Halley'e kurar, yönetici izni
    gerekmez, masaüstü + Başlat menüsü kısayolu. Yeniden kurulum = güncelleme: app\data\ altındaki MEVCUT dosyalara ve
    app\.env'e dokunmaz; program dosyalarını yeniler. `/sessiz /hedef= /kisayolsuz /baslatma` deneme seçenekleri.
  - `paket/build_package.py --cikti <klasör> --veri <data>`: veritabanları SQLite yedekleme API'siyle tutarlı kopyalanır
    (integrity_check), .env ASLA pakete girmez. `--hazir-klasor`: Python'u yeniden kopyalamadan yeniden derler.
  - Okuyucuya `HALLEY_OKUYUCU_KAPALI` ortam değişkeni eklendi (paket denemesinde KAP/fiyat isteği yapmasın; test eklendi).
- Doğrulama (2026-11-09):
  - Sessiz kurulum 39 sn, 448 MB, 18.290 dosya; .env yok.
  - PATH yalnız Windows klasörleriyken paketteki Python tüm kütüphaneleri yükledi; sanal ortama / Store Python'a yol yok.
  - 405 test PAKETİN Python'u ve paketteki uygulama koduyla: hepsi geçti.
  - Halley.exe: 2 sn'de sağlıklı; 2 süreç (panel, okuyucu); ikinci açılış yeni kopya başlatmadı; `--kapat` tüm
    süreçleri bitirdi; tüm sekmeler + hisse ayrıntısı + açık/koyu geçişi hatasız; günlüklerde hata yok.
  - Denemede bulunan hata: canlı panel 8501'i 0.0.0.0/:: üzerinde dinlerken başlatıcı 127.0.0.1:8501'i boş sandı (iki
    sunucu aynı portta) → port kontrolü "önce bağlan, sonra tüm arayüzlerde özel kullanımla aç" yapıldı; yeniden
    denemede 8502'ye geçti, canlı panel etkilenmedi.
  - Güncelleme kurulumu: .env, kullanıcı dosyası, değiştirilmiş ayar ve veritabanı korundu; program dosyası yenilendi;
    sonra panel API anahtarını tanıdı.
  - Denenemeyen: başka (temiz) bir bilgisayar — bu makinede Python ve VC++ kurulu olduğundan "hiçbir şey kurulu değil"
    durumu tam benzetilemedi (VC++ DLL'leri bu yüzden pakete kondu). Kurulum penceresinin görünümü ve `--kaldir`
    (onay pencereleri) elle denenmeli. Program imzasız: Windows SmartScreen "Ek bilgi → Yine de çalıştır" isteyebilir.

## 2026-11-09 — Halley kendi penceresinde (kullanıcı: "tarayıcı tabanlı değil, Halley adında uygulama istiyorum") — A yolu
- Kullanıcı A'yı seçti (B = ekranı baştan masaüstü kütüphanesiyle yazmak; A beğenilmezse sonra yapılabilir, hesap/veri
  katmanı ekrandan ayrı olduğu için etkilenmez).
- Halley.exe artık kendi "Halley" penceresini açar (WinForms + Microsoft WebView2; `paket/webview2/` Microsoft imzalı
  1.0.4314.35 DLL'leri, nuget.org'dan kullanıcı onayıyla indirildi, imzalar doğrulandı). Tarayıcı / adres çubuğu / sekme
  yok; tepsi simgesi kaldırıldı. Pencere kapanınca panel + okuyucu kapanır. İkinci açılış açık pencereyi öne getirir.
  Panel çizilene kadar koyu "Halley açılıyor…" ekranı (üst bant `.hero` görünene kadar). Başlık çubuğu Karanlık mod
  ayarına uyar (1,5 sn'de bir ayarlar.json'a bakar). Dış bağlantılar (haber kaynağı) varsayılan tarayıcıda açılır.
  WebView2 bileşeni yoksa (çok eski Windows 10) panel varsayılan tarayıcıda açılır ve pencere kurulum bağlantısını verir.
  Profil: app\data\pencere. `--pencere-yok` (eski `--tarayici-yok`) yalnız deneme için.
- Panelin sağ üstündeki Streamlit menüsü (Stop / ⋮ / durum) gizlendi (CSS); yenileme F5.
- İlk denenen Edge "--app" kipi kullanıcı istemediği için geri alındı (derlenmedi, kaydedilmedi).
- Derleme betiği: `--hazir-klasor --veri <data>` veriyi tazeleyerek hızlı yeniden derler.
- Doğrulama: temiz kurulum (449 MB) + yalıtılmış Python; pencere başlığı "Halley", içerik WebView2'de 127.0.0.1 paneli
  (ayrı msedge.exe yok); ekran görüntüleriyle açılış ekranı ve hazır panel kontrol edildi; pencere kapatılınca Halley,
  python ve WebView2 süreçlerinin hepsi bitti; tek kopya, --kapat, port çakışması (8502'ye geçti, canlı panel sağlam),
  güncellemede .env/ayar/veri korunması yeniden geçti; 405 test geçti.
- Denenemeyen: başka bilgisayar (temiz Windows), kurulum penceresinin görünümü, "Halley'i kaldır" onay pencereleri.

## 2026-11-09 — Verisiz kurulum dosyası GitHub'a sürüm olarak (kullanıcı onayı)
- `build_package.py --hazir-klasor --veri-yok` → boş veri klasörüyle Halley_Kurulum.exe (147 MB). Paket içinde .db / .env /
  ayarlar.json yok (tarandı; "sk-" yalnız örnek yazılar). Kurulup açıldı (sağlık ok), sonra kapatıldı.
- Gizli depoya sürüm: `v2026.11.09` (yalnız bu dosya; veriler USB ile taşınır). Veri dahil kurulum dosyası GitHub'a
  YÜKLENMEDİ (kullanıcı kuralı: veritabanı GitHub'a yüklenmez).

## 2026-11-09 — Veri aktarma (dışa / içe aktar) — kullanıcı: "sıfırdan kurdurup verileri içe aktarma olarak vermek"
- `bist_haber/transfer.py`: tek zip dosyası (manifest + SHA-256). İçerik: ana veritabanı ve pilot (SQLite yedekleme
  API'siyle tutarlı kopya), ayarlar.json, aliases, universe, takvim, kap_okuyucu.json, fiyat_yok.json, raporlar/.
  ASLA girmeyen: .env (API anahtarı), günlükler, pencere profili, yedekler (izinli ad listesi).
- İçe aktarma: denetim (Halley dosyası mı, sürüm, her parçanın SHA-256'sı, güvenli dosya adı — "../" engelli,
  integrity_check, gerekli tablolar) → mevcut veri data/yedek/ice_aktarma_oncesi_<zaman>/ altına → veritabanları
  yedekleme API'siyle yazılır (panel/okuyucu açıkken güvenli; açık bağlantı yeni veriyi görür) → db.connect ile
  şema güncellenir. Reddedilen dosyada hiçbir şey değişmez. .env'e dokunulmaz.
- Panel: 🔧 Gelişmiş → 💾 Veri aktarma (Hazırla/İndir; dosya seç → özet → "Anladım" → İçe aktar). Haber yoksa üstte
  "Halley yeni kurulmuş görünüyor…" yönlendirmesi. KULLANIM.md'ye adımlar eklendi.
- Testler: tests/test_transfer.py (gidiş-dönüş, anahtar taşınmaz, yedek, değiştirilmiş/yabancı dosya reddi, güvenli
  olmayan yol) + panel testi (bölüm görünür, dosya hazırlanır). 410 test geçti.
- Gerçek veriyle: canlı veri (salt okuma) 8,6 MB dosyaya aktarıldı (7.717 haber, 151 analiz sonucu, 23 işlem günlüğü,
  pilot); anahtar dosyada yok. Boş kopyada (yalnız şirket listesi, KAP'a gidilmedi) panelden dosya yüklenip içe
  aktarıldı: olumlu/olumsuz 50/43 (canlıyla aynı), ana veritabanındaki 15 ve pilottaki 20 tablonun satır sayıları
  canlıyla birebir; yeni bilgisayarın .env'i değişmedi; önceki veri yedeklendi.
- Bilinen sınır: yeni bilgisayarda Halley ilk açılışta KAP şirket listesini indirir (internet gerekir); KAP o an
  sınır uygularsa panel açılmaz ve içe aktarma bölümüne ulaşılamaz (birkaç dakika sonra yeniden açmak yeterli).
- Dağıtım (2026-11-09 17:45): masaüstü + dagitim/ → verisiz Halley_Kurulum.exe (147 MB) + halley_veri_2026-11-09.zip
  (8,6 MB, güncel). Önceki veri dahil kurulum dosyası bunlarla değiştirildi. GitHub sürümü v2026.11.09'daki dosya
  yeni (veri aktarmalı) verisiz paketle değiştirildi; sürüm notu güncellendi. Paket içinde içe aktarma denendi:
  verisiz kurulum → paketin Python'uyla içe aktarma → panel 50/43, anahtar isteği görünüyor, hata yok.

## 2026-11-09 — baslat.bat: Halley zaten açıksa ikinci kopya başlatılmaz
- Kullanıcı "Port 8501 is already in use" gördü: asıl Halley açıkken (ve bir kez de geliştirme klasöründeki eski veriyle
  çalışan kopyadan) ikinci başlatma denendi. Artık baslat.bat önce 8501 sağlık adresine bakar; açıksa paneli tarayıcıda
  açar ve çıkar. (Kontrol denendi: açık panelde 0, kapalı portta 1.) Asıl veriler etkilenmedi (7.717 haber, 151 analiz
  sonucu, 23 işlem günlüğü doğrulandı).

## 2026-11-09 — Telegram bildirimi (kullanıcı: "telegram üzerinden bildirim göndersin bize")
- `bist_haber/notify.py`: Telegram Bot API (ücretsiz, yapay zekâ yok, emir yok). Bot anahtarı ve alıcılar .env'de
  (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID virgülle birden çok alıcı/grup); kodda, GitHub'da ve veri aktarma dosyasında
  YOK. HALLEY_OFFLINE'da ağa çıkılmaz. Her alıcıya ayrı gönderim; biri başarısız olsa diğerleri gider; hata metninde
  anahtar *** ile gizlenir; 4096 karakter sınırında kesilir.
- `watchdog.run_session`: rapor arşive yazıldıktan SONRA, ayarlar["telegram"] açıksa özet gönderilir
  (out["bildirim"]). Gönderim hatası analizi/raporu bozmaz; panelde sarı uyarı.
- Mesaj (yalnız kayıtlı veri): önerilen senaryolar (giriş/SL/TP1/TP2/risk, en çok 10), sabahta takip listesi ve
  stopa yaklaşanlar, işlem günlüğü durum değişiklikleri (giriş, TP1, kapanış sonucu ve net %, süresi dolan), akşamda
  BIST 100, sanal toplam (örnek az uyarısıyla), kaçırılan fırsat sayısı, rapor adı, "yatırım tavsiyesi değildir".
- Panel: ⚙️ Ayarlar → 📨 Telegram bildirimi: aç/kapa düğmesi (ayarlanmadan kapalı), kurulum adımları, anahtar kaydet,
  🔍 Alıcıları bul (getUpdates: bota /start yazanlar ve botun eklendiği gruplar), alıcı seç/kaydet (ilk kayıtta
  bildirim açılır), 📨 Deneme mesajı. Ayar ayarlar.json'da `telegram_acik`.
- Bulunan ve düzeltilen hata (panel testiyle): alıcı kaydedilince ayar açılıyor ama düğmenin eski konumu ayarı hemen
  geri kapatıyordu → düğme durumu da güncelleniyor.
- Testler: tests/test_notify.py (8: çoklu alıcı ve hata sürekliliği, anahtar sızmaz, geçersiz anahtar, ayarsız,
  çevrimdışı, uzun mesaj, alıcı bulma, .env'de OpenAI anahtarı korunur, mesaj metni, analize bağlantı, ağ hatasında
  rapor yine kaydedilir) + panel akışı (anahtar → alıcı bul → kaydet → açık → deneme). 419 test geçti.
- Gerçek Telegram sunucusuna sahte anahtarla deneme: "bot anahtarı geçersiz" Türkçe mesajı geldi (bağlantı çalışıyor).
  Gerçek bir bota gönderim DENENMEDİ: bot anahtarı kullanıcıda (BotFather'da bot açmak kullanıcının işi).
- Sınır: bildirim yalnız sabah/akşam analizi düğmeye basılınca gider; Halley kendiliğinden zamanlı analiz yapmaz.

## 2026-11-09 — Swing terminali planı (kullanıcı talebi, onaylandı) — Aşama 1–2: Takip Listem + bekçi
Onaylanan varsayılanlar: bekçi yalnız Halley açıkken; sabah/akşam Telegram özeti takip listesine daraltılır; önce
motor (Aşama 1–2), sonra arayüz (Aşama 3); haber bildirimi bütçe tavanı içinde otomatik (Aşama 4).
- Veritabanı (db.py): watchlist (aktif/çıkarıldı, bildirim türleri, son trend), takip_senaryo (seviyeler, durum,
  sonuç, senaryo bazında bildirim aç/kapa), takip_olay (anahtar UNIQUE → aynı olay bir kez; kesin=0 gün içi;
  gonderildi 1/0/-1). Takipten çıkarılınca hiçbir kayıt silinmez.
- `bist_haber/tracker.py`: add (fiyatı tazeler: geçmiş <200 gün → 1 yıl, son fiyat son kapanmış günden eski → 1 ay;
  sonra entries.scenarios — mevcut kurallar AYNEN; takip listesinde haber şartı yok, veri kritik/likidite <2 mn TL ise
  senaryo yok), remove, set_types, set_scenario_alert, refresh_scenarios (aynı türde etkin takip varsa yenisi yok).
  close_check(gün): journal.evaluate ile (işlem günlüğüyle aynı kurallar) giriş, kırılım teyidi, TP1, TP2/SL/başabaş/
  süre doldu, iptal; limit senaryoda giriş olmadan kapanış SL altı → geçersiz (kırılımda DEĞİL: SL kırılan seviyenin
  altı, kırılımdan önce fiyatın SL altında olması olağan — gerçek veride ASELS'te yanlış "geçersiz" görüldü,
  düzeltildi); bugün hariç 20 günlük zirve/dip kapanış kırılımı; hacim ≥ 2× 20 gün ort.; destek/geri çekilme giriş
  bölgesinde alt fitil (≥ mum boyunun yarısı) + yükselen kapanış; trend değişimi; yeni senaryo. O güne ait fiyatı
  olmayan hisse için olay yok (veri_yok). intraday_check: Yahoo 5 dk mumları (~15 dk gecikmeli, prices tablosuna
  YAZILMAZ); son mum 45 dk'dan eski ya da başka günse olay yok; giriş seviyesine değme, kırılım denemesi, stop/TP1/TP2
  değme, gün içi hacim ≥ 1,5× günlük ort. dispatch: gönderilmemiş olaylar (24 saat) hisse türü + senaryo anahtarına
  göre tek mesaj; başarısızsa yeniden dener; Telegram kapalıysa yalnız kayıt. tick: kapanış+20 dk sonrası (yalnız
  ileri gün; kaçırılırsa ilk fırsatta) kapanış kontrolü, seans içinde 5 dk'da bir gün içi kontrol. performance:
  strateji türüne göre TP1/TP2/SL/başabaş/süre doldu oranları.
- kap_worker.serve döngüsü (baslat.bat ve Halley.exe'deki okuyucu) her turda tracker.safe_tick (hata okuyucuyu
  durdurmaz; durum data/takip_durum.json).
- Panel: hisse kartında "+ Takibe Al"/"takipten çıkar"; yeni ⭐ Takip Listem sekmesi (bekçi durumu, hisse ekle,
  senaryo kartları + senaryo bildirim düğmesi, bildirim türleri, son olaylar, bekçi olay tablosu, sonuç tablosu,
  takipten çıkarılanlar). Ayarlar → Telegram: "takip listesi olaylarını gönder" (varsayılan açık). Sabah/akşam
  özeti takip listesine daraltıldı (gerçek işlemler her zaman yazılır). `bist_haber/takip_ui.py` (Aşama 3'te sayfa).
- Bulunan ve düzeltilen hatalar: kapanıştan hemen önce önceki günün yeniden işlenmesi (yalnız ileri); takip
  düğmelerinin sayfa yenilerken veritabanı bağlantısını açık bırakması; eski fiyatla senaryo; kırılımda yanlış
  geçersizlik.
- Testler: tests/test_tracker.py (16) + panel akışı (karttan takibe al → türleri seç → senaryo bildirimini kapat →
  takipten çıkar, geçmiş durur) + özet daraltma. Tam takım geçti.
- Gerçek veriyle (canlı verinin KOPYASI, Telegram'a gönderim yok): THYAO/ASELS/AKGRT takibe alındı → 4 senaryo;
  Yahoo gün içi verisi 17:55'e kadar geldi; 9 Kasım kapanış kontrolü: THYAO 310,00 kapanışla 20 günlük zirveyi
  (304,75) aştı → tek olay. Gerçek Telegram gönderimi DENENMEDİ (bot anahtarı kullanıcıda).
- Sınırlar: Yahoo ~15 dk gecikmeli; bekçi yalnız Halley açıkken; gün içi olaylar kapanışla teyit edilmez (öyle yazılır).

## 2026-11-09 — Aşama 3: terminal arayüzü (üstte sabit menü, 9 ekran)
- app.py yeniden düzenlendi (hesap kodu AYNEN taşındı; yalnız yerleşim): üst bant (Halley, tarih, son güncelleme,
  🔄 Haberleri güncelle, 🧪 Ücretsiz dene, 🌙 Koyu tema) + yapışkan menü (st.radio key="nav", CSS ile sekme görünümü):
  📊 Dashboard · 🎯 Fırsatlar · 🔍 Hisse Analizi · ⭐ Takip Listem · 🛡️ Bekçi · 📰 Haberler · 📒 İşlem Günlüğü ·
  🏁 Performans · ⚙️ Ayarlar. Yalnız seçili ekran çizilir (önceden tüm sekmeler her seferinde hesaplanıyordu).
- Dashboard kartları: BIST 100 (son iki kapanış), olumlu/olumsuz/uygun fırsat sayıları, piyasa rejimi şeridi, günün
  fırsatları (🔍 Analiz düğmeli), bekçi durumu + son 6 olay, takip listesindeki aktif senaryolar, açık işlemler,
  15 günlük piyasa takvimi. Fırsatlar: kısa satırlar (skor, haber, teyit, teknik etiket, 🔍 Analiz, + Takibe Al);
  ayrıntı ayrı ekranda (Hisse Analizi; "_goto" ile ekran + hisse seçilir). Hisse Analizi: tüm hisseler seçilebilir;
  haberi olmayan hissede senaryolar yalnız fiyattan (tracker.scenario_guard + entries.scenarios — bekçiyle aynı kural).
  Bekçi: sabah/akşam analizi + takip bekçisi olayları + rapor arşivi. Performans: takip senaryolarının strateji
  oranları + Gelişim. Ayarlar: ayarlar/Telegram, 💾 Veri ve gelişmiş, ❓ Kılavuz.
- Ayarlar artık ayrı ekranda olduğu için KAP gün sayısı, analiz sınırı ve liste penceresi de ayarlar.json'da
  saklanıyor (kap_gun, panel_analiz_siniri, liste_pencere); diğer ekranlar kayıtlı değeri kullanır.
- Panelin "uygun" senaryolarını sanal işleme yazma (Parça C1) her ekranda çalışmaya devam ediyor (eskiden Bugünün
  listesi sekmesi her seferinde çizildiği için).
- Varsayılan tema koyu (kullanıcı isteği); seçim saklanıyor. Streamlit üst çubuğu gizlendi, genişlik 1440 px.
- Bulunan ve düzeltilen: Telegram ayar düğmeleri sayfayı yenilerken veritabanı bağlantısını kapatmıyordu.
- Testler yeni ekranlara göre güncellendi (+ her ekran açılıyor ve 🔍 Analiz yönlendirmesi, ayarlar ekran değişince
  kaybolmuyor testleri). 438 test geçti, ağ denemesi 0. Görsel kontrol: geliştirme kopyası ağsız kipte (8504) —
  Dashboard, Fırsatlar, Hisse Analizi.
- Not: Streamlit'in yerleşik çok sayfalı yapısı (st.navigation) yerine tek dosyada radyo menü seçildi: test
  edilebilir (AppTest), widget anahtarları korunur, ekranlar arası yönlendirme basit.

## 2026-11-09 — Aşama 4: önemli yeni haber bildirimi + strateji başarı raporu
- tracker.news_check (bekçi turunda, işlem günlerinde 08:00–19:30, 30 dk'da bir): kap.collect(days=1, metin yok — tüm
  evren, normal güncellemeyle aynı; KAP bekleme süreleri DEĞİŞMEDİ) → YALNIZ takip edilen hisselerin son 3 gündeki
  metni olmayan bildirimleri okunur (KAP_REQUEST_DELAY; sınır/hata olursa tur bırakılır) → takip edilen hisselerin
  metni hazır bildirimleri analyzer.analyze ile, ayarlar.json'daki analiz kalitesi ve AYLIK HABER BÜTÇESİ tavanıyla
  analiz edilir (kullanıcı onayı: bütçe içinde otomatik) → hisse takibe alındıktan SONRA yayımlanmış, yönü olumlu/
  olumsuz ve etkisi ≥3/5 olan her etki "haber" olayı (anahtar h:haber:hisse, bir kez). Panelden yapılan analizler
  de değerlendirilir. Ayar: takip_haber_analizi (varsayılan açık; Ayarlar'da düğme). API anahtarı yoksa analiz yok.
- Not: bekçinin günlük KAP listesini alması, panelde "Haberleri güncelle"nin ilk adımıyla aynıdır; yeni bildirimler
  analiz sırasına girer ve mevcut arka plan okuyucusu metinleri (ücretsiz, yapay zekâsız) her zamanki gibi tamamlar.
- Strateji başarısı: 🏁 Performans ekranında takip senaryolarının strateji türüne göre TP1/TP2/SL/başabaş/süre doldu
  oranları ve ortalama net % (tracker.performance; 30'dan az örnekte "güvenilir değil" uyarısı) + mevcut Gelişim.
- Testler: tests/test_tracker.py NewsTests (yalnız takip edilen hissenin metni okunur, bütçe iletilir, bir kez
  bildirilir, ikinci turda yeniden analiz yok; takipten önceki/zayıf haber bildirilmez; ayar kapalıyken yapay zekâ
  çağrılmaz; KAP hatası turu durdurmaz; API anahtarı yoksa analiz yok; 30 dk aralık, hafta sonu yok). 442 test geçti.
- Gerçek KAP'la deneme (canlı verinin KOPYASI, sahte analiz, maliyet 0): liste alındı (662 bildirim), takip
  edilenlerde metni bekleyen yoktu; kopyada takip tarihi 3 gün geriye alınınca AKGRT'nin analiz edilmiş etki 3/5
  haberi doğru şekilde olay oldu. Gerçek yapay zekâ çağrısıyla haber bildirimi DENENMEDİ (maliyet; canlıda bütçe
  içinde kendiliğinden olacak). Gerçek Telegram gönderimi DENENMEDİ (bot anahtarı kullanıcıda).

## 2026-11-09 — Görünüm kontrolü ve düzeltmeler (kullanıcı: "olumlu haber kırmızı, olumsuz beyaz; uyumsuzluklar var")
Tüm ekranlar canlı panelde (1440 px, koyu) ve geliştirme kopyasında (koyu + açık tema) tek tek gözle tarandı.
- Kart renkleri sıraya bağlıydı (nth-of-type); başa BIST 100 eklenince kaydı → renkler kartın anahtarına bağlandı
  (kpi_pos yeşil, kpi_neg kırmızı, kpi_opp turuncu, kpi_upd mor; BIST 100 günün yönüne göre yeşil/kırmızı/mor).
- Üst menü kaydırınca kayboluyordu (menü kendi kabında sabitleniyordu) → sabitleme menünün kabına taşındı.
- "+ Takibe Al" düğmesinde + kayboluyordu (Markdown liste işareti) → "➕ Takibe Al".
- İki "$" arası formül sayılıyordu ("2.285 $ · bütçe 10 $" eğik/bozuk) → paneldeki tüm $ kaçırıldı; rapor ve kılavuz
  metinleri dollar() ile gösteriliyor (yapay zekâ maliyet satırları rapor dosyalarında $ içeriyor).
- Tema değişince menü "Fırsatlar" gösterirken Dashboard açılıyordu (Streamlit yenilemede menü seçimini unutuyordu) →
  seçili ekran ayrıca saklanıyor; Hisse Analizi'nde seçilen hisse ekran değişince kaybolmuyor.
- Takip Listem: tekrarlanan giriş cümlesi kaldırıldı; bildirim türü adları kısaldı (açıklamalar ? işaretinde);
  başlıklar diğer ekranlarla aynı stil. İşlem Günlüğü başlığı diğer ekranlarla aynı. Fırsatlar'daki tekrar eden piyasa
  takvimi kaldırıldı (Dashboard'da). "Koyu tema" yazısı taşmasın diye "🌙 Koyu".
- Hisse Analizi: takipteki hissede "⭐ Takipteki senaryolar" kutusu ve açıklama (takip senaryosu hesap günündeki
  fiyatla izlenir; aşağıdaki analiz bugünkü fiyatla — AKGRT'de "destekten tepki" takipte beklerken bugünkü analizde
  uygulanamaz görünmesinin nedeni).

## 2026-11-09 — Fırsat sayısı değişim kaydı ve elle kontrol (kullanıcı: "20'den 19'a düştü, neye göre?")
- `bist_haber/firsat_log.py`: uygun liste her değiştiğinde data/firsat_gecmisi.json'a zaman, eklenen, çıkan ve NEDEN
  (signals.decide — panel/bekçiyle aynı karar kodu; skor eşiği altına inen için skor ve "haber eskidikçe azalır")
  yazılır (son 60 kayıt). Yalnız kayıt; hiçbir eşik/karar değişmez. Kayıt 9 Kasım akşamından itibaren tutuluyor
  (20 → 19 değişikliğinin nedeni geriye dönük bilinemez; büyük olasılıkla bir hissenin haber skoru eşiğin altına indi
  ya da fiyat güncellemesiyle senaryosu uygun olmaktan çıktı).
- Fırsatlar ekranı üst kutu: şu anki sayı + son değişiklik, "🔄 Fırsatları şimdi yeniden kontrol et" (isteğe bağlı
  ücretsiz fiyat güncellemesiyle), "📋 Tüm adaylar — elle kontrol" (her olumlu haberli hisse: ✅/❌ neden, en uygun
  senaryo ve seviyeler; eşiğe yakınlar; değişiklik tablosu).
- Türkçe arama: textutil.tr_fold (Türkçe küçük harf + ş/ğ/ü/ö/ç/ı katlama, kelime kelime eşleşme); Hisse Analizi ve
  Takip Listem'de "Ara" kutusu (Streamlit'in kendi araması "aksigorta" ile "AKSİGORTA"yı eşleştirmiyordu).
- Testler: kaçırılmamış $ ve liste işaretiyle başlayan düğme yazısı hiçbir ekranda yok; kart renkleri anahtara bağlı;
  fırsat yeniden kontrol + değişim kaydı; Türkçe arama; tema değişince ekran korunur, hisse seçimi korunur. 447 test geçti.

## 2026-11-09 — Kurulum: kuruluysa güncelle, veriler korunur (kullanıcı: "üstüne yazsın, tekrar tekrar kurulmasın; eski veriler kaybolmasın")
- paket/Kurulum.cs: kurulu Halley algılanır (Halley.exe) → pencere "GÜNCELLENECEK (yeniden kurulmaz)", kurulu/yeni
  sürüm ve "Güncelle" düğmesi; aynı sürüm kuruluysa "zaten kurulu ve güncel" + "Halley'i aç" / "Yeniden kur";
  sessiz kipte aynı sürüm atlanır (ZATEN GUNCEL), /zorla ile yeniden kurulur. Hep aynı klasör; kısayollar aynı adla
  üstüne yazılır.
- Açık Halley "--kapat" ile, bu klasörden çalışan arta kalan python/Halley işlemleri ayrıca kapatılır (başka
  programlara dokunulmaz).
- Güncellemeden ÖNCE: app\data kökündeki .db/.json/.csv/.txt + app\.env + raporlar → app\data\yedek\
  guncelleme_oncesi_<zaman>\ (son 3 yedek). Kurulum app\data\ altındaki mevcut dosyalara ve app\.env'e dokunmaz
  (verisiz pakette veri dosyası zaten yok). Güncellemeden SONRA: önceki her veri dosyası yerinde ve aynı boyutta mı
  denetlenir; değilse yedekten geri konur. Hata olursa "Verileriniz silinmedi" uyarısı.
- build_package.py pakete surum.txt yazar ("tarih (git kısa kimlik)"), kurulum bunu karşılaştırır.
- Deneme (geçici klasör, gerçek kuruluma dokunulmadı): masaüstündeki ESKİ verisiz paket kuruldu → sahte veri
  (5.000 satırlı veritabanı, pilot.db, ayarlar.json, OpenAI+Telegram anahtarlı .env, rapor) → Halley AÇIKKEN (3 işlem)
  yeni paketle güncelleme: işlemler kapandı (0 kaldı), 5 veri dosyasının SHA-256'sı birebir aynı, 5.000 satır
  duruyor, yedek alındı, yeni kod ve sürüm kuruldu; ikinci çalıştırma "ZATEN GUNCEL"; 5 kurulumdan sonra 3 yedek;
  güncellenen Halley açıldı (sağlık ok) ve "--kapat" ile kapandı. Kurulum penceresi (görsel) bu bilgisayarda
  açılıp gözle denenmedi; mantığı sessiz kiple aynı işlevden geçiyor.
- Dağıtım: yeni verisiz Halley_Kurulum.exe (2026-11-09, e579cc6) masaüstüne, dagitim/ klasörüne ve GitHub sürümüne.
- Dağıtım güncellendi: bb9c11d (açıklama yazıları dahil), dosya özellikleri + bildirim; masaüstü, dagitim/, GitHub sürümü.

## 2026-11-09 — Yanlış alarm (kullanıcının bilgisayarında Windows "tehdit bulundu")
- Bu bilgisayarda Defender kayıtlarında Halley tespiti yok; kurulum dosyası ve Halley.exe MpCmdRun ile tarandı: temiz.
  Uyarı yalnız diğer kullanıcının bilgisayarında (imzasız, az indirilen, içinde büyük paket taşıyan ve süreç kapatan
  exe → sezgisel/bulut yanlış alarmı olası). Windows güvenlik ayarlarına DOKUNULMADI (istisna/kapatma önerilmedi).
- Yapılan: iki exe'ye dosya özellikleri (ad, açıklama, yayıncı "Halley", ürün, telif, sürüm 2026.11.9.0, bilgi sürümü
  "tarih (git)") ve uygulama bildirimi (paket/halley.manifest: asInvoker — yönetici izni istemez, Windows 10/11,
  ekran ölçekleme). Kesin çözüm DEĞİL; olasılığı azaltır.
- Doğrulandı: dosya özellikleri okunuyor; Defender taraması temiz; önceki sürüm (fda858b) üstüne güncelleme veriyi
  korudu; yeni Halley.exe açıldı ve kapandı. Diğer bilgisayarda yeniden denenmedi (erişim yok).
- Kalıcı çözümler (kullanıcının kararı/işi): Microsoft'a yanlış pozitif bildirimi (microsoft.com/wdsi/filesubmission,
  kullanıcının hesabıyla); kod imzalama sertifikası (ücretli).

## 2026-11-09 — Açıklama yazıları (kullanıcı: AKSGY/DEVA'da fırsatlarda risk düşük/orta, analizde yüksek — çelişki mi?)
- Çelişki değildi: Fırsatlar/Dashboard EN UYGUN GİRİŞ SENARYOSUNUN riskini (ortak riskler + o senaryonun r/g),
  analizdeki "Risk seviyesi" kutusu ŞİMDİ SON FİYATTAN ALIMIN riskini gösteriyordu (o planın elverişsiz r/g'si 4 puan).
  Canlı veri: AKSGY şimdi 9,12'den r/g 1:0,74 → yüksek; kırılım 9,58 üstü r/g 1:2,51 → düşük. DEVA şimdi 1:0,99 →
  yüksek; kırılım 87,99 (+%10,8) r/g 1:4,52, ortak 2 madde (Enflasyon Raporu, haberden önce %16,2 yükseliş) → orta.
  Hesap DEĞİŞMEDİ; yalnız etiketler ve açıklamalar.
- Eklenen açıklamalar: analizde "Senaryo riski — Fırsatlar'da görünen risk budur", kutu yüzdeleri ve r/g'nin anlamı,
  senaryo türleri/durum sütunu; referans bölümü "bugün son fiyattan alsaydınız" + etiketler "Referans (son fiyat)",
  "Risk (şimdi alınırsa)"; haber skorunun anlamı; Dashboard kartlarının altında ne saydıkları; fırsat çiplerinde
  "senaryo riski"; aktif senaryolar ve açık işlemler (sanal/gerçek, stopa uzaklık); Fırsatlar listesi (skor, teyit,
  etiket, düğmeler); Takip Listem durumları, hesap günü, Bildirim düğmesi; bekçi olay tablosu (teyit, Telegram);
  takip senaryosu sonuç tablosu sütunları.
- İşlem Günlüğü: üstte açık "❓ İşlem Günlüğü nasıl okunur?" (amaç, sanal/gerçek, durumlar, sütunlar, ölçüler,
  portföy riski), ölçülerin altında tanımlar, tablo başlıklarında açıklama (column_config help). KULLANIM.md'ye
  iki bölüm. Test: açıklamaların göründüğü panel testi. 448 test geçti.

## 2026-11-10 — Hazır İşlem Fırsatları katmanı (kullanıcı isteği, onaylandı; sabah YZ kararı kullanıcıda: düğme, varsayılan kapalı)
- `bist_haber/ready.py` (mevcut motorun ÜSTÜNDE seçme/sıralama): olumlu haberli (skor ≥1,50) her hisse için koşulu
  bugün sağlanmış planlar: kirilim_teyitli (son kapanış önceki 20 gün zirvesi üstünde + yükselen mum; SL = seviye −
  1 ATR, hedefler entries._targets), geri_cekilme (giriş fiyata ≤0,5 ATR — zaten bölgede), destek_teyitli (giriş
  fiyata ≤0,5 ATR + bugün yükselen kapanış), mevcut_fiyat (tradeplan referans SL'si). Giriş = son kapanış. Şart:
  TP1 r/g ≥ 1:2 (tradeplan.MIN_RR), zarar ≤ %15, ortak risk puanı "yüksek" değil, teknik skor ≥5/10. Azami giriş =
  min(giriş + 0,3 ATR, TP1 r/g'nin 1:1,5'e düştüğü fiyat). En iyi plan TP1 r/g'ye göre; sıralama: risk, teknik +
  2×haber + r/g; en fazla 5, 0 olabilir. Teknik skor 0–10 (trend, RSI 45–70, MACD/ADX, hacim/OBV, endekse göre güç;
  eşit ağırlık). YENİ sabitler sınanmadı (READY_GAP_ATR 0,5, MAX_ENTRY_ATR 0,3, MIN_RR_AT_MAX 1,5, MIN_TECH 5);
  mevcut eşikler değişmedi.
- Veritabanı hazir_firsat (aday → onaylandi | iptal → giris | girissiz → kapandi). evening(): eski önerileri
  değerlendir, seç, ertesi işlem günü için 'aday' kaydet (yeniden hesaplamada düşeni iptal). morning(): akşamdan
  sonra olumsuz etki (direction<0) gelen → iptal; yeniden hesapla, bozulan → iptal, uygun → 'onaylandi' (seviyeler
  güncellenir); yeni uygun varsa ekle (toplam ≤5) — 09:55'ten sonra yeni ekleme yok. news_guard(analyze=True) yalnız
  kullanıcı açtıysa/düğmeye bastıysa: hazır hisselerin yeni KAP bildirimleri (liste, metin, bütçe içinde analiz).
  opening_check(): Yahoo gün içi verisinin ilk mumu (acilis) azami girişin üstündeyse → iptal. evaluate_all():
  giriş = giriş günü açılışı (azami üstündeyse girissiz), sonra journal.evaluate (gercek kipte) → TP/SL/başabaş/süre;
  performance() ayrı ölçüm.
- Bağlantılar: watchdog.run_session (elle ve otomatik) hazır bölümünü raporun EN ÜSTÜNE ve Telegram özetinin başına
  ekler; watchdog.run_auto/saved_settings (otomatik çalışma, ai=False). ready.tick (okuyucu döngüsünde): akşam
  (kapanış+20 dk; kaçırılırsa ertesi sabah 09:30'a kadar), sabah (08:30–09:55), açılış kontrolü (10:05–17:30) —
  günde birer; elle yapılmış rapor varsa yinelemez; HALLEY_OFFLINE'da başlatmaz. tracker.fetch_intraday 'acilis'.
- Panel: Dashboard'da önce "✅ Hazır Fırsatlar" kartı, sonra "⏳ Bekleyen fırsatlar"; özet kartı "Hazır fırsat".
  Fırsatlar: Hazır Fırsatlar bölümü (plan kartları; iptaller; "Şimdi yeniden hesapla (kaydetmeden)" + elenme
  nedenleri; 🤖 sabah haber kontrolü düğmesi hazir_sabah_yz varsayılan KAPALI; "Yeni haberlerini şimdi analiz et"),
  sonra "Bekleyen Fırsatlar". Performans: hazır fırsat gerçek sonuçları. Bekçi: otomatik çalışma durumu. Ayarlar:
  hazır açılış bildirimi (hazir_bildirim) ve YZ düğmesi.
- Bulunup düzeltilenler: okuyucu testlerinde otomatik analiz ağa çıkıyordu (HALLEY_OFFLINE koruması); kaçırılan akşam
  analizi seans içinde yarım fiyatla çalışabilirdi (09:30 sınırı); otomatik sabah analizi açılıştan sonra da
  çalışıyordu (08:30–09:55 sınırı); açılıştan sonraki sabah kontrolü geçmiş açılışa öneri ekleyebilirdi; gerekçe
  metni cümle ortasında kesiliyordu.
- Testler: tests/test_ready.py (15) + panel testi (önce hazır, kart, YZ varsayılan kapalı ve saklanıyor, anlık hesap,
  performans). Tam takım geçti, ağ denemesi 0.
- Gerçek veri (salt okunur + kopya): 44 olumlu haberliden 1 hazır (METEN, mevcut fiyattan, giriş 21,44, azami 21,67,
  SL 19,22, TP1 25,89, TP2 28,11, r/g 1:2,0, teknik 7/10, risk orta); 27'si "koşulu sağlanmış r/g ≥1:2 plan yok",
  14'ü teknik veri yok, 2'si risk yüksek. Kopyada akşam → sabah onay → rapor/Telegram metni doğrulandı.

## 2026-11-10 — Diğer kullanıcı GitHub'dan kuramadı ("Defender kapalıyken bile"): inceleme ve düzeltmeler
- Depo ÖZEL (private): girişsiz sürüm sayfası ve dosya bağlantısı 404 (doğrulandı). İkinci yetkili hesap:
  ihtiyarkilicoglu. İndirmek için o hesapla GitHub'a giriş gerekir.
- GitHub'daki dosya sağlam: indirildi, SHA-256 yereldekiyle aynı (d9813de3…). "İnternetten indirildi" işareti
  (Zone.Identifier, ZoneId=3) eklenince Windows çalıştırmayı durdurdu ("İşlem kullanıcı tarafından iptal edildi" —
  SmartScreen onayı); Unblock-File sonrası aynı dosya sorunsuz kuruldu. Defender'ı kapatmak SmartScreen'i kapatmaz;
  Windows 11 Akıllı Uygulama Denetimi açıksa imzasız program hiç çalışmaz ("Yine de çalıştır" yok). Paketteki
  python/pythonw (Python Software Foundation) ve WebView2 dosyaları (Microsoft) imzalı; imzasız: Halley_Kurulum.exe,
  Halley.exe. Kalıcı çözüm kod imzalama (kullanıcı kararı/ücretli).
- Yapılanlar: KURULUM_YARDIM.md (doğru dosya, giriş, Engellemeyi kaldır, Yine de çalıştır, Akıllı Uygulama Denetimi,
  günlük dosyası, SHA-256) ve sürüm notuna aynı adımlar; kurulum penceresi kipinde de hata/başarı
  %TEMP%\halley_kurulum.log'a yazılır (Windows sürümüyle) ve hata penceresi dosya yolunu gösterir.
- Ayrıca bulunan hata: prices.update_universe son 40 günde fiyatı olan her hissede yalnız 1 ay indiriyordu; bir kez
  1 aylık inen hisse (TUPRS dahil 14 olumlu haberli hisse) 22 günde kalıp teknik analize (≥30 gün) hiç giremiyordu →
  artımlı indirme yalnız geçmişi yeterli (≥200 gün ya da ilk fiyatı ~11 ay önce) hisseye; diğerleri 1 yıl. Test eklendi.
- Hazır fırsat özellik doğrulaması (kullanıcı listesine göre) sohbet yanıtında madde madde; eksik/kısmi: "mevcut seans"
  girişli kayıtlı öneri yok (yalnız ertesi gün açılışı; gün içi anlık hesap kaydedilmez), açılış fiyatı açılıştan önce
  bilinemez (kontrol 10:05'ten sonra), sabah kötü haber kontrolü YZ düğmesi kapalıyken yalnız önceden analiz edilmiş
  haberleri görür (kullanıcı kararı).

## 2026-11-14 — Aşama 1/8 (YZ maliyet optimizasyonu ve sadeleştirme planı, kullanıcı onayı)
- MIMARI_RAPOR.md: çalışma akışı, bütün YZ çağrıları (10 yer; dosya, tetikleyen işlem, sıklık, gerekli mi, Python'a
  taşınır mı, önbellek), Kasım gerçek kullanımı (148 tam analiz ≈ 2,28 $, RSS ön eleme 7 çağrı ≈ 0 $, rapor yorumu 0),
  korunacaklar, 8 aşamalı plan. Bulgu: harcamanın neredeyse tamamı tam analiz → en büyük tasarruf gereksiz KAP
  bildirimlerinin tam analize gönderilmemesi (Aşama 3 odağı) ve içerik özeti (Aşama 2).
- Bekçinin kendiliğinden YZ haber analizi (tracker.news_check, takip_haber_analizi) varsayılan KAPALI (önceden açık).
  KAP listesi/metin okuma (ücretsiz) ve analiz edilmiş haberden önemli haber bildirimi sürer. Ayarlar düğmesi
  "bekçi otomatik analiz etsin (varsayılan kapalı)". Test: varsayılan kapalıyken YZ çağrılmaz, metin okunur.
- 466 test geçti, ağ denemesi 0.

## 2026-11-14 — Aşama 2/8: merkezi YZ servisi, kullanım ekranı, içerik özeti, tekrar ayıklama
- `bist_haber/ai_service.py`: LLM sınıfı buraya taşındı (analyzer.LLM aynı sınıf, eski ad korunur). Her çağrı
  ai_calls tablosuna (zaman, modül, işlem, ref, model, girdi/çıktı token, tahmini $, süre ms, durum ok/hata, hata,
  parametre-tekrar sayısı); kayıt kendi kısa bağlantısıyla (paralel iş parçacıkları), kayıt hatası çağrıyı bozmaz.
  Modüller: haber_analizi, takip_haber, hazir_haber, derin_inceleme, ucuz_test, rapor_yorumu, kacirilan_aciklama,
  pilot. İşlemler: on_eleme, tam_analiz, ikinci_gorus. Pilot (backtest.PilotLLM) kendi bütçe/önbelleğini korur, kaydı
  servise yazar. Sahte (test) istemcilerin çağrıları kaydedilmez (is_real) — testler 130 sahte kaydı geliştirme
  veritabanına yazmıştı, silindi ve önlendi. Test: OpenAI() yalnız ai_service ve backtest'te.
- usage(): bugün/ay/toplam, modül×işlem kırılımı (ay), son 30 gün günlük, son hatalar, son 30 çağrı, kayıt öncesi
  haber analizi harcaması (analyses). Panel: ⚙️ Ayarlar → 🤖 Yapay zekâ kullanımı. Bütçe denetimi değişmedi.
- `bist_haber/dedupe.py`: news.content_hash (Türkçe katlanmış başlık + sadeleştirilmiş metin, SHA-256); analyze()
  YZ'den ÖNCE filter_duplicates: analiz edilmiş aynı içerik → 'duplicate' (not: ilk kayıt), aynı partide tekrar →
  ilk tutulur, RSS'te aynı başlık ±3 gün → tekrar; aday hisseleri ilk kayıttakilerin içinde değilse tekrar SAYILMAZ.
  stats['tekrar']. Gelişmiş durum tablosunda "Tekrarlanan haber". Test örneklerinde aynı başlık+metin kullanan
  add_news başlığa kayıt no eklendi.
- Gerçek veri (kopya): metni hazır 963 bekleyen haberden 2'si tekrar (TTKOM finansal rapor, LKMNH) — tasarruf bugün
  küçük; asıl tasarruf Aşama 3'te. Testler: tests/test_ai_service.py (9) + panel. 476 test geçti, ağ denemesi 0.

## 2026-11-14 — Aşama 1–2 denetimi (kullanıcı: "1-2'yi kontrol et")
- Değişikliklerin tamamı satır satır okundu; paralel çalışma denendi: 5 kanal + ana iş parçacığı yazarken çağrı kaydı
  kilitlenmedi, kayıp yok (9 haber × 2 çağrı = 18 ok + 1 hata kaydı), kayıt başına ~7 ms; hata alan haber yeniden
  denenince içerik özeti engellemedi; bütçe yetmeyince çağrı ve kayıt yok.
- HATA (düzeltildi): aynı partideki tekrar kalıcı 'duplicate' işaretleniyordu; ilk kayıt hata alır/bütçeye takılırsa
  ikincisi hiç analiz edilmeyebilirdi → parti içi tekrar yalnız o tur atlanır (status 'new' kalır), ilk kayıt analiz
  edilince sonraki turda kalıcı işaretlenir. Testler eklendi.
- Küçük: elle analizde tekrar sessiz atlanıyordu → mesajda "X haber tekrar olduğu için atlandı (ücretlendirilmedi)";
  güncelleme sonucunda da yazılır. ai_calls tablosu db.connect'te oluşur (kullanım sekmesi her çizimde DDL denemesin).
  MIMARI_RAPOR'da bekçi satırı "varsayılan kapalı" olarak güncellendi. 476 test geçti, ağ denemesi 0.

## 2026-11-14 — Aşama 3/8: Python ön eleme kuralları (ölçüldü, HENÜZ DEVREDE DEĞİL)
- Yeni `bist_haber/prefilter.py`: `classify(row) -> ("ai"|"rutin", neden)`, `apply(conn)` (rutinleri `skipped` + not
  "Python ön eleme: ..." yapar). Yapay zekâ kullanmaz. **analyzer'a bağlanmadı** (test bunu kontrol ediyor); kullanıcı onayı bekleniyor.
- Kurallar (doğruluk önce, emin olunmayan her şey "ai"):
  - KAP rutin konular: portföy uyumu, MKK, tipe dönüşüm, ihraç tavanı/belgesi, borçlanma aracı itfa, YK komiteleri,
    denetçi seçimi, merkez değişikliği, finansal takvim, izahname, fon kullanım raporu, halka arz varsayım raporu,
    fon kurucusu alım satımı, esas sözleşme, tescil vb.
  - Geri alım bildirimi: süren programın günlük uygulama raporu ("Güncelleme mi? Evet") rutin; programın başlatılması/
    kararı/sonu ya da alan bulunamazsa → ai.
  - Genel kurul: bedelsiz/sermaye/kâr payı/birleşme/bölünme geçiyorsa → ai, yoksa rutin.
  - **Pay Alım Satım Bildirimi hep ai**: ilk taslakta "rutin" sanılan örneklerin bildirimi yapanı YK üyesi/ortak çıktı
    (SPK II-15.1 md.12 içeriden işlem) → kural kaldırıldı.
  - RSS: şirket eşleşmesi varsa ai; yoksa piyasa geneli anahtar kelimesi (faiz, enflasyon, vergi, petrol, savaş/saldırı,
    SPK/BDDK…) varsa ai; açılış/kapanış/altın/kripto bülteni ve geri kalanı rutin.
- Ölçüm (canlı veritabanının bellekteki kopyası, salt okunur): 148 YZ etiketli haberin (141 KAP + 7 RSS) **hiçbiri** rutin
  denmedi → kaçırma 0. YZ'nin RSS ön elemesinde önemsiz dediği 7 haberin 6'sı Python'da da rutin, 1'i ai (güvenli taraf).
  Bekleyen 963 haberin 352'si (%37; KAP 335, RSS 17) yapay zekâya gitmezdi (≈ 352 × 0,0154 $ ≈ 5,4 $ birikmiş sırada).
- Dürüst sınır: rutin sayılan konuların (en çok 211 günlük geri alım raporu) geçmişte YZ etiketi yok; kaçırma oranı bu
  gruplar için ÖLÇÜLEMEDİ. Öneri: ~30 rutin haberlik ücretli doğrulama örneği (≈ 0,4–0,6 $), kullanıcı onayıyla.
- Testler: tests/test_prefilter.py (7). Tüm paket 483 test OK, ağ denemesi 0.

## 2026-11-14 — Aşama 3 devreye alındı (kullanıcı: "Doğrudan devreye al"; ücretli doğrulama örneği istenmedi)
- `analyzer.analyze(on_eleme=True)`: sıra kendiliğinden seçiliyorsa önce `prefilter.apply` (bütün sıra; 10 haberlik sınır
  rutin haberlere harcanmasın), satırlar verildiyse (takip/hazır fırsat) `prefilter.split`. `stats["rutin"]`.
- Panelde kullanıcının KENDİ seçtiği haberlerde `on_eleme=False` (seçimine saygı). 🔬 analiz bölümüne "ön elemenin atladığı
  haberleri de göster" kutusu eklendi (🧹 işaretli); atlanan haber elle analiz ettirilebilir → geri dönüş yolu.
- `pipeline.refresh`: metinler okunduktan sonra API anahtarı olmasa da `prefilter.apply` (bekleyen sayıları doğru görünsün);
  Haberler sayfasındaki son güncelleme notunda "N rutin haber ... gönderilmedi" yazar.
- RSS'te YZ ön eleme çağrısı (FILTER_PROMPT) KALDIRILMADI: Python'un geçirdiği RSS haberleri için çok ucuz (≈0,0003 $) ve
  yarısını eleyip 0,015 $'lık tam analizden kurtarıyor → kaldırmak maliyeti artırırdı. Python artık önünde ilk süzgeç.
- Canlı DB yedeği: `data/yedek/bist_haber_asama3_oncesi_20261114.db`.
- Test altyapısı: `prices._fetch_stats` HALLEY_OFFLINE'da ağa çıkmaz. Bulgu: yfinance curl_cffi kullandığı için Python soket
  engelini aşabiliyordu (tam pakette 4 testte gerçek Yahoo isteği görüldü); run_offline artık curl_cffi isteklerini de sayıyor.
- Dürüst sınır (değişmedi): rutin sayılan gruplarda (özellikle günlük geri alım raporları) kaçırma oranı ölçülmedi.
- 483 test OK, ağ denemesi 0 (soket + curl).

## 2026-11-14 — Aşama 4/8: fırsat katmanı ve haftalık rapor (YZ'siz)
- **Genel fırsat puanı** `ready.overall_score` (0–100 = haber 30 + teknik 30 + r/g 20 + risk 20). YALNIZ BİLGİ: seçim ve
  sıralama değişmedi (mevcut eşikler aynı; "küçük pilotla eşik değiştirme" kuralı). Kartta parçalarıyla, olumlu haber
  listesinde "puan" (en uygun giriş senaryosuna göre `pending_score`), Dashboard tablosunda, rapor tablolarında.
- **Yalnız teknik fırsatlar** `ready.build_tech/select_tech`: skor ≥1,50 ya da <0 haberi olanlar hariç evren; tracker
  koruması (veri/likidite), yükseliş trendi, teknik ≥ 7/10 (`MIN_TECH_ONLY`, sınanmadı), koşulu sağlanmış plan (kırılım/
  geri çekilme/destek; "mevcut fiyattan" yok), r/g ≥ 1:2, risk yüksek değil; risk maddeleri haber yönü 0 ile
  (bilanço/şirket olayı/makro dahil). `hazir_firsat.kaynak` ('haber'|'teknik') + `genel_puan` sütunları (ALTER);
  akşam/sabah/açılış/sonuç ölçümü aynı yaşam döngüsü, her kaynak için ayrı en fazla 5. Sabahta teknik planın hissesine
  olumsuz haber geldiyse iptal. Performans ekranında kaynak süzgeci; rapor ve Telegram'da ayrı bölüm.
  Canlı veride (14.11 kopya) 761 hisse ~10 sn: 1 yalnız teknik (ENERY, kırılım, r/g 1:2, puan 44), 0 haberli.
- **Haber özeti/etkisi** haberli hazır fırsat kartında (`news_line`, kayıtlı analizden).
- **Haftalık rapor** `bist_haber/weekly.py`: piyasa, hazır fırsatlar (kaynak ayrı), kapanan günlük işlemleri, takip olayları,
  haber/ön eleme/tekrar sayıları, YZ çağrı ve maliyeti (ai_calls; 14.11 öncesi analyses tokenlarından). Arşiv
  `YYYY-AA-GG_haftalik`. `ready.tick`: haftanın son işlem gününün akşam raporu varsa bir kez üretir (Telegram kısa özet,
  ayar açıksa). Panel: Bekçi → Rapor arşivi "📅 Bu haftanın raporunu şimdi oluştur", "Haftalık" süzgeci.
- Testler: tests/test_stage4.py (7) + panel akışı (1). Tüm paket 491 OK, ağ 0.
- Sürüm: kurulum paketi 5952225 ile yeniden derlendi (147 MB, SHA-256 1e49d13a…). Güncelleme testi: eski (646432d)
  kurulumun üstüne sessiz güncelleme → 3 veri dosyası birebir korundu, yedek klasörü oluştu, sürüm 5952225, sağlık
  testi 8507 tamam, --kapat sonrası süreç kalmadı. Defender taraması temiz. GitHub sürümü v2026.11.09 güncellendi
  ("Halley 2026-11-14 (güncel: 5952225)"); Masaüstü ve dagitim/ kopyaları yenilendi.

## 2026-11-14 — Aşama 3–4 denetimi ve 1–2 ile uyum (kullanıcı: "3 ile 4'ü kontrol et, sonra 1 ve 2 ile düzgün çalışıyorlar mı")
- Kod incelemesi + canlı DB kopyasında uçtan uca deneme (`scratchpad/e2e_asama1_4.py`, ağ yok, sahte istemci):
  analyze → ön eleme (20 rutin) → tekrar ayıklama → bütçe → merkezi kayıt (ai_calls) doğru; bekçi akşam analizi
  (run_session ai=False, 35 sn, YZ çağrısı engellenmişken) **0 YZ çağrısı**, hazır + yalnız teknik (ENERY) kaydı, rapor
  bölümleri; sabah kontrolü onayladı; haftalık rapor + tick.
- Bulunan ve düzeltilen:
  1. Haftalık rapor yalnız arşivde "o günün akşam raporu" varsa üretiliyordu → Cuma akşamı Halley kapalıysa (akşam
     analizi ertesi gün yapılmaz/başka tarih alır) haftalık hiç oluşmuyordu. Artık `aksam_gunu` (akşam turu işlendi)
     bilgisine bakılıyor. Test eklendi.
  2. Bir yama betiği (heredoc) koşul satırını tek satıra birleştirmişti (çalışıyordu, okunaksızdı) → düzeltildi.
  3. Panelden elle haftalık rapor Telegram'a da gönderiyordu (her tıkta mesaj) → elle üretimde gönderilmez.
  4. Dashboard "Hazır fırsat" kutusu haberli/teknik ayrımını göstermiyordu → "koşulu sağlanmış (haberli N · 📐 yalnız
     teknik M)".
  5. Aşama 2 ekranı Aşama 3 tasarrufunu göstermiyordu → 🤖 Yapay zekâ kullanımı'nda "bu ay YZ'ye gönderilmeyen rutin +
     tekrar haber ≈ X $" satırı (tahmini, ortalama tam analiz maliyetiyle).
- Uyum kontrolü: ön eleme/yalnız teknik/haftalık rapor YZ çağırmaz (Aşama 1 ilkesi); YZ çağıran tek yol hâlâ merkezi
  servis (test_every_ai_entry_point_uses_the_service); ön eleme tekrar ayıklamadan önce çalışır; elle seçimde ön eleme
  yok. 492 test OK, ağ 0.

## 2026-11-15 — Aşama 5/8: profesyonel grafik + olası fiyat aralığı konisi (YZ'siz)
- Yeni `bist_haber/chart.py`: `history` (OHLCV + EMA 20/50/200; technical.ema ile aynı yöntem — testte birebir),
  `daily_vol` (60 günlük log-getiri std), `cone` (drift 0, √t, %50/%80; tatiller market_calendar ile atlanır),
  `cone_summary/cone_text` (TP1/SL koni içinde mi; giriş fiyattan >%1,5 uzaksa yalnız girişin aralıkta olup olmadığı —
  SL/TP yorumu girişten sonra anlamlı), `plan_levels` (hazır plan > en uygun senaryo; destek/direnç), `figure`
  (Altair: mum + EMA + seviye çizgileri ve çakışmayan etiketler + azami giriş bandı + koni; altında hacim).
- Panel: `chart_block` Hisse Analizi'nde (haberli ve haber kaydı olmayan hisseler) ve hazır fırsat kartında
  ("📈 Grafik ve olası fiyat aralığı" açılır bölümü). Dönem 3/6/12 ay, koni 5/10/20 işlem günü.
- Koni bir tahmin modeli DEĞİL (yön yok); Aşama 6–7 modelleri onaylanırsa yanına eklenecek.
- Testler: tests/test_chart.py (4) + panel (1). 497 test OK, ağ 0. Canlıda görsel kontrol yapıldı.
- Sürüm: kurulum paketi 6b4d2d4 (147 MB, SHA-256 b5e54db7…). Güncelleme testi 5952225 → 6b4d2d4: veri birebir korundu,
  yedek oluştu, chart.py pakette, sağlık 8507 tamam, kapatma temiz; Defender temiz. GitHub v2026.11.09 güncellendi
  ("Halley 2026-11-15 (güncel: 6b4d2d4)"); Masaüstü ve dagitim/ kopyaları yenilendi.

## 2026-11-15 — 6. aşama öncesi genel doğrulama (kullanıcı: "fiyat modelimizden önce her şeyin doğru çalıştığından emin ol")
- Canlı kurulum = GitHub HEAD (113 dosya, satır sonu hariç birebir; yalnız NOTLAR farklıydı). Panel sağlıklı, 2 okuyucu.
- Canlı DB denetimi (salt okunur kopya, `scratchpad/db_denetim.py`): integrity ok; yetim/geçersiz etki 0; hatalı haber 0;
  tutarsız/çift fiyat 0; işlem günlüğü ve hazır fırsat seviye sırası tutarlı; gönderilemeyen takip bildirimi 0.
- Teknik göstergeler 40 likit hissede bağımsız pandas hesabıyla karşılaştırıldı (`scratchpad/teknik_bagimsiz.py`):
  RSI, ATR, MACD hist, ADX/±DI, SMA50/200, Bollinger, destek/direnç → en büyük fark 0,0000.
- Uçtan uca kopyada akşam → sabah → açılış → sonuç ölçümü → Telegram metni (`scratchpad/e2e_sabah.py`): YZ çağrısı 0.
- **Bulunan hatalar ve düzeltmeler:**
  1. **Hafta sonu kaçırılan akşam analizi atlanıyordu** (en önemlisi): kural "ertesi gün 09:30'dan sonra seans
     başlamıştır" diyordu; Cumartesi/Pazar/tatilde seans yok. Sonuç: 11–13 Kasım akşamları Halley kapalıyken evren
     fiyatları 10.11'de kaldı (761 hissenin yalnız 28'i güncel — onlar da işlem günlüğü güncellemesinden) ve Pazartesi
     hazır listesi oluşmadı. Artık seans başlamadıysa (aynı akşam, ertesi işlem günü 09:30 öncesi, hafta sonu/tatil)
     yapılır. Testler eklendi.
  2. 4. aşamada haftalık rapor bloğu akşam/sabah `if–elif` zincirinin ortasına girmişti → ayrı bloğa alındı.
  3. Açılış azami girişin üstündeyse kayıt "iptal" (sabah iptali) sayılıyordu → "girissiz" (giriş olmadı); Performans
     sayıları doğru kutuya düşer.
  4. Fiyatlar eskiyken panel uyarmıyordu → Dashboard, Fırsatlar ve Bekçi'de "Hisse fiyatları güncel değil" uyarısı
     (son kapanmış günün fiyatı olmayan hisse oranı > %30 ise).
- 498 test OK, ağ 0.
- Kullanıcı: "grafik karanlık modda beyaz görünüyor" → grafik renkleri Streamlit temasına bırakılmıştı (Halley
  penceresinde açık temaya düşüyordu). `chart.figure(dark=...)`: saydam zemin, eksen/yazı/ızgara renkleri karanlık mod
  ayarından; `st.altair_chart(theme=None)`. X ekseninde tarih yazıları seyreltildi. Test eklendi; canlıda görüldü.
- Canlıda doğrulama: durum kaydı sıfırlanınca (yedek: data/yedek/hazir_durum_20261115.json) bekçi kaçırılan Cuma akşam
  analizini 01:02'de kendisi yaptı → 631 hissenin tamamı 13.11 fiyatlı (önce 28), Pazartesi (16.11) için 2 yalnız
  teknik hazır fırsat (BAHKM kırılım r/g 1:3,1, ENERY kırılım r/g 1:2), haberli 0; YZ çağrısı 0; rapor 2026-11-15_aksam.
- Sürüm: kurulum paketi 42ecf7f (147 MB, SHA-256 b1651209…): güncelleme testi 6b4d2d4 → 42ecf7f veri korundu, sağlık
  tamam, Defender temiz; GitHub v2026.11.09 "Halley 2026-11-15 (güncel: 42ecf7f)".
- Aşama 6 planı yazıldı: ASAMA6_PLAN.md (onay bekliyor; YZ maliyeti 0 $, araştırma ~4–6 saat).

## 2026-11-15 — Aşama 6 araştırması (kullanıcı onayı: "Evet, başla")
- 632 hissenin 5 yıllık fiyatı ayrı dosyaya: `data/backtest/arastirma_5y.db` (gitignore; canlı DB yalnız okundu). YZ 0 $.
- `arastirma/asama6/etiketle.py`: canlı kod (ready.candidates/entries/technical, 250 günlük pencere, bayat-veri kontrolü
  o güne göre) geçmişin her gününde; giriş ertesi açılış (azami üstü → girişsiz), çıkış journal.evaluate. 46.053 sinyal,
  34.579 kapanmış plan (risk yüksek ve stop < %1 çıkarıldı).
- `model.py`: (A) benzer durumlar tablosu, (B) numpy lojistik; son 12 ay ve 2024 ileriye dönük sınama, 45 gün ambargo,
  aylık blok bootstrap, tekilleştirilmiş kontrol.
- Sonuç: AUC tablo 0,583 / lojistik 0,576 (taban senaryo türü 0,546); Brier kazancı ~%1; tablo olasılıkları son 12 ayda
  5–9 puan yüksek; ekonomik fayda 2024'te senaryo türü tabanını geçemedi → **plan kuralı gereği devreye alınmadı**,
  panel değişmedi. Kırılım her dönemde en iyi tür (son 12 ay %32 TP1 / +0,09 R; destek %18 / −0,40 R).
  Genel puan AUC 0,49 (TP1'i ayırt etmiyor), teknik skor 0,53.
- Yan bulgu: hacmi tamamen 0 olan hisselerde (DUNYH, ISATR) işlem hacmi "ölçülemedi" (None) sayılıp likidite engeli
  çalışmıyor; düzeltme kullanıcı onayına bırakıldı.
- Rapor: ASAMA6_RAPOR.md. Kod değişikliği yok (yalnız araştırma betikleri ve belgeler).

## 2026-11-15 — Aşama 6 ikinci tur: geliştirilmiş model, başlangıç sürümü tp1_v1 (kullanıcı: "Modeli geliştir…")
- Yeni `bist_haber/tp1_model.py`: `features()` + `market_features()` (eğitim ve canlı ORTAK), `predict()`, `band()`,
  `similar()`; model dosyası `bist_haber/modeller/tp1_v1.json` (8,7 KB, paketle gelir). Panele BAĞLI DEĞİL.
- `arastirma/asama6/etiketle.py` artık tp1_model.features kullanıyor; yeniden etiketlendi (46.053 sinyal).
- `arastirma/asama6/egit.py`: artırımlı ağaç (numpy), yakın dönem ağırlığı, Platt, yeni girdili lojistik denendi →
  kazandırmadı (taban oranı kayıyor). Seçilen E2 = tablo + 10 girdili sade lojistik ortalaması: AUC 0,605 / 0,612,
  Brier +%2,8 / +%3,8 (son 12 ay / 2024); en yüksek %20 son 12 ayda +0,17 R (diğer −0,08). ~6 varyant aynı sınamaya
  bakılarak seçildi → hafif iyimserlik; canlı planlarla izlenmeli.
- Test: tests/test_tp1_model.py (girdiler, kayıtlı model, eğitimdeki tahmin = canlı tahmin 9 basamak).
- Canlı deneme: BAHKM kırılım %33 (orta), ENERY kırılım %37 (yüksek).

## 2026-11-15 — Aşama 6 haber 1. aşama: KAP konu başlıkları (kullanıcı: "Yalnız 1'e devam")
- `arastirma/asama6/kap_liste.py`: 4 yıllık KAP LİSTELERİ araştırma DB'sine (kap_liste; 299.996 bildirim, boşluksuz;
  KAP_REQUEST_DELAY korundu; 429'da 5 dk bekleyip kaldığı yerden devam). Metin yok, YZ yok.
- `tp1_model.news_features()` / `news_items()` (canlıyla ortak; sinyal günü 18:00'e kadar, 5 gün pencere) + test.
- `haber_ekle.py`: etiketlere haber girdileri. Sonuç: haberli %29,2 / haberli olmayan %29,3 TP1; teknik+haber türü
  AUC 0,603 / 0,609 (teknik 0,605 / 0,612) → katkı yok; tp1_v1 değişmedi. Konudan içerik anlaşılmıyor (Özel Durum).
- 2. aşama için gereken metin sayısı (plan öncesi 5 gün, gürültü hariç): 19.752 (Özel Durum 5.649).

## 2026-11-15 — Aşama 6 haber 2. aşama, Python ile (kullanıcı: "Evet pythonla dene"; API yok, 0 $) — SÜRÜYOR
- `bist_haber/haber_metin.py` (canlıyla ortak): kurallı okuma (olumlu/olumsuz ifade, güncelleme mi, en büyük tutar /
  günlük işlem hacmi; USD/EUR o günün kuruyla) + `tokens()` (öğrenen kelime modeli girdisi). Test: test_haber_metin.
- `arastirma/asama6/metin_indir.py`: plan öncesi 5 gündeki 5.649 Özel Durum metni araştırma DB'sine (kap_metin), karışık
  sırayla. KAP her ~80 istekte 5 dk sınır uyguluyor (bekleme süresi düşürülmedi) → ~8–9 saat.
- Kurlar (USDTRY/EURTRY 5 yıl, Yahoo) araştırma DB'sinde `kur`.
- `metin_model.py`: E2 / +kurallı / +öğrenen kelime / ikisi; metni eksik planlar çıkarılır. Sonuç indirme bitince.
- Canlı tek çağrı: `tp1_model.plan_probability(conn, plan)` / `plan_features()` — eğitimle aynı 250 günlük pencere
  (hisse + endeks) ve haber girdileri; canlı hazır fırsat kayıtlarında salt okunur denendi: BAHKM %32,6 (orta),
  ENERY %37,3 (yüksek) = elle hesapla birebir. Test: PlanProbability. Panele bağlı DEĞİL.
- Ara bakış (metinlerin %11'i, 732 plan; kesin değil): kurallı okuma "olumlu" → TP1 %38,7 / +0,40 R (n=124);
  nötr %26,7 / +0,06 R; "olumsuz" %25,9 / −0,11 R. Metinsiz planlar %29,3. Tam veriyle sınanacak.

## 2026-11-15 — Aşama 6 gizli kayıt (kullanıcı: "Gizli kayıt başlasın")
- `hazir_firsat.model_json` (yeni sütun, db göçü): her hazır fırsat kaydında/güncellemesinde (akşam aday, sabah
  onay) `ready.model_info()` → tp1_model.plan_probability: olasılık, bant, benzer sayısı/oranı, sürüm, zaman.
  Seçim/sıralama/eşik/panel/Telegram DEĞİŞMEDİ. Model hatası öneriyi engellemez ({"hata": ...}).
- Test: PlanProbability (kayıt + hata durumu). Kopyada akşam→sabah: BAHKM 0,3265 orta, ENERY 0,3728 yüksek yazıldı.
- Canlı DB yedeği: data/yedek/bist_haber_20261115_gizli_kayit_oncesi.db. Mevcut 2 kayıt Pazartesi sabah analizinde
  dolacak. Ölçüm: birkaç hafta sonra kapanan önerilerde olasılık ↔ gerçek sonuç.

## 2026-11-15 — Hata düzeltmesi: hacmi 0 olan hisse likidite engeline takılmıyordu
- `technical.analyze`: hacim bilgisi var ama 21 gündür hep 0 ise `islem_hacmi_tl = 0` (önce None = "ölçülemedi" →
  `scenario_guard` likidite engeli çalışmıyordu; Aşama 6 araştırmasında stop ~%0 planlar böyle çıktı). Hacim bilgisi hiç
  olmayan seriler (pilot) None kalır. Eşik değişmedi (2 mn TL).
- Canlıda etkilenen: DUNYH, ISATR, UMPAS → "Likidite çok düşük; senaryo üretilmedi". Test: tests/test_zero_volume.py.
- Sürüm: kurulum paketi 1e5dab8 (147 MB, SHA-256 8ae0a7c9…): güncelleme testi 42ecf7f → 1e5dab8 veri korundu, sağlık
  tamam, tp1_model + modeller/tp1_v1.json pakette, Defender temiz; GitHub v2026.11.09 "Halley 2026-11-15 (güncel:
  1e5dab8)"; Masaüstü ve dagitim/ kopyaları yenilendi.
- metin_indir.py: istek arası 6 sn (KAP sınırına takılmasın, canlı okuyucuya yer kalsın) + hafta içi 08:00–19:00 durur.

## 2026-11-15 — Aşama 7 planı (onay bekliyor): ASAMA7_PLAN.md
- Adaylar: Kronos-small (finans mumları, olası fiyat yolları; 24,7 M), Chronos-Bolt-small (Apache-2.0, 48 M),
  TTM-r2 (Apache-2.0, ~0,8 M). Python 3.9 kısıtı: PyTorch 2.9+ ve chronos-forecasting 2.x Python ≥3.10 ister →
  ayrı araştırma ortamı (Python 3.9, PyTorch 2.8 CPU, chronos-forecasting 1.5.3; requires_python >=3.9 doğrulandı).
  Halley'e/pakete eklenmez. İndirme ~0,7 GB, disk ~2 GB, YZ 0 $. Taban çizgisi tp1_v1.

## 2026-11-15 — Aşama 7 "olduğu gibi" deneme (kullanıcı: "o zaman devam edelim"; sonra "ilerleyebildiğin kadar ilerle")
- Ayrı araştırma ortamı: `%USERPROFILE%\.venvs\halley-arastirma` (Python 3.9.13, torch 2.8.0+cpu, transformers 4.53.3,
  chronos-forecasting 1.5.3, python-dotenv). Halley ortamı/paketi DEĞİŞMEDİ. Kronos kodu (MIT, shiyu-coder/Kronos @67b630e)
  `%USERPROFILE%\.venvs\kronos_kod`; çalıştırmadan önce okundu (ağ/dosya erişimi yok).
- `arastirma/asama7/planlar.py`: sınama planları (son 12 ay 3.264 + 2024 3.212; hisse başına 14 günde bir). Mutlak
  seviyeler etiketlerden geri hesaplandı → gerçek barlarla 300/300 etiket birebir.
- Bulgu: **Kronos-small** fiyatı yılda ~3 kat artmış hisselerde ertesi gün −%30…−%40 öngörüyor (MOBTL, ASELS; resmî
  `KronosPredictor.predict` ile de) → BIST ±%10 sınırına aykırı. **Kronos-mini** makul ve ~5 kat hızlı → deneme
  mini ile (10 yol × 20 gün, dönem başına 1.000 plan, ilk günü ±%11'i aşan yol geçersiz). Sürüyor.
- **Chronos-Bolt-small** (6.476 plan, 3 dk): tek başına AUC 0,56 (son 12 ay) / 0,58 (2024) — E2'nin (0,60 / 0,58)
  gerisinde. 2024'te birleşik eğitilip son 12 ayda: AUC 0,599 → 0,600 (fark −0,01…+0,03, anlamsız); Brier +%1,1–1,2
  (yalnız E2 yeniden ölçeği +%0,6 → Chronos'un payı ~%0,6); en yüksek %20 R'si +0,17 → +0,09–0,11 (kötüleşti).
  Sonuç: katkı yok.

## 2026-11-15 — Denetim (kullanıcı: "tekrar kontrol et bir eksiklik var mı")
- Canlı panel sağlıklı; model_json panele/tabloya sızmıyor (app Performans tablosu sütunları açık seçilmiş); veri aktarma
  tüm DB'yi kopyaladığı için sütun korunuyor.
- Eksik bulundu ve eklendi: gizli kaydı gerçek sonuçla karşılaştıran ölçüm yoktu → `tp1_model.live_check()` (+ test).
- ASAMA6_RAPOR Ek 3 ve MIMARI_RAPOR aşama 7 satırı güncellendi.

## 2026-11-15 — Aylık yeniden eğitim + kart gösterimi (kapalı anahtar) (kullanıcı: "Önerdiğin gibi yap")
- `tp1_model.active_name()` / `load()`: etkin model `modeller/aktif.txt`'den (yoksa tp1_v1.json); eski dosyalar
  silinmez, geri dönmek için aktif.txt'yi değiştirmek yeterli.
- `arastirma/asama6/yeniden_egit.py`: --fiyat (araştırma DB'sine son 3 ay, Yahoo) → --etiket (etiketle.py) → ileriye
  dönük sınama (son 12 ay) + eski modelin görmediği planlarda karşılaştırma → KAPI (AUC ≥ 0,55, Brier sabit orandan iyi,
  eskiden en fazla 0,02 AUC düşük) → tp1_vYYYYMMDD.json; --etkinlestir ile aktif.txt. Canlı DB'ye yazmaz.
  Deneme (geçici kopya repo): sınama AUC 0,605 / Brier +%2,81; yapay eski model (Eylül 2025'e kadar) ile 9.170 yeni
  planda eski 0,6025 ↔ aday 0,6038 → kapı geçti; --etkinlestir yokken aktif.txt değişmedi.
- Panel: ⚙️ Ayarlar → "🎯 … olasılığını göster" anahtarı (`model_olasilik_goster`, varsayılan KAPALI); açıkken hazır
  fırsat kartında `model_line()`: "%37 — yüksek · geçmişte benzer 1465 durumda %31" + "haber hesaba katılmaz" uyarısı.
  KULLANIM.md bölümü eklendi. Test: test_stage6_model_line_hidden_until_setting_on. 510 test OK.

## 2026-11-15 — Genel puan notu (kullanıcı: "senin önerilerine göre devam edelim")
- Genel puan ekranda kalır, seçimi/sırayı yine değiştirmez; "ağırlıklar sınanmadı" yazan yerler (Fırsatlar kartı,
  Pano altyazısı, olumlu haber listesi açıklaması, rapor dipnotu, score_text) "5 yıllık geçmiş sınamada TP1'i öngörmedi
  (yazı-tura düzeyi)" olarak değişti (Aşama 6: AUC 0,49). Kart model olasılığı anahtarı KAPALI kalır; metin sınaması
  sonucu görülünce karar verilecek. 510 test OK.

## 2026-11-15 — Model olasılığı açık hazır fırsatlara sonradan eklendi (kullanıcı: "kullanıcı denemek istiyor")
- Canlı DB yedeği: data/yedek/bist_haber_20261115_model_sonradan_oncesi.db.
- Açık (aday) 2 kayda `ready.model_info` ile model_json yazıldı, `"sonradan": true` işaretli: BAHKM %32,7 orta,
  ENERY %37,3 yüksek (sinyal günü 13.11; hesap yalnız o güne kadarki veriyle → geleceği görme yok).
- Panel kontrolü (tarayıcı): Ayarlar'da anahtar görünüyor (kapalı), genel puanın yeni notu Pano'da görünüyor.
  Anahtarı açmak kullanıcıya bırakıldı. Kod değişmedi.

## 2026-11-15 — Müşteri denemesi: açık fırsatlara olasılık kendiliğinden + kurulum dosyası yenilendi
- Sorun: müşterideki sürümde (1e5dab8) kart anahtarı yok; güncellemeden önce oluşmuş açık fırsatlarda model kaydı da
  olmayabilir → anahtarı açsa bile satır görmezdi.
- `ready.fill_missing_model(conn)`: model_json'u boş AÇIK (aday/onaylandi/giris) kayıtlara olasılık ekler,
  "sonradan": true; kapanmış kayıtlara dokunmaz. Panel her oturumda bir kez çağırır (hata paneli engellemez).
  Test: test_tp1_model (açık kayda eklenir, kapanmışa eklenmez, ikinci çağrı 0). 510 test OK.

## 2026-11-15 — Kurulum dosyası e07601b + Kronos sonucu
- Kurulum dosyası yeniden oluşturuldu (e07601b): güncelleme testi (eski 1e5dab8 → yeni) veri korundu, açıldı
  (sağlık OK), kapandı; Defender temiz; SHA-256 852f687c…45b4, 147.180.544 bayt. Sürüm v2026.11.09'a yüklendi,
  başlık "Halley 2026-11-15 (güncel: e07601b)", notlara model anahtarı ve genel puan notu eklendi.
- Kronos-mini (2.000 plan, 10 yol, ~4 saat): tek başına AUC 0,52 / 0,52; birleşik son 12 ay 0,595–0,598 (E2 0,601),
  en yüksek %20 R'si kötüleşti; geçersiz yol %2. Katkı yok → canlıya alınmadı, ince ayar önerilmez
  (ASAMA7_PLAN.md "Sonuç", MIMARI satırı ⛔).

## 2026-11-15 — Hisse Analizi: .html olarak indirme (kullanıcı isteği)
- `bist_haber/html_export.py`: Kaydedici (Recorder) — ekranı çizen fonksiyonlar (tracked_box, stock_details /
  generic_details) aynen çalışır, `st` geçici olarak kaydediciyle değişir (DARK=False: açık zemin); sayılar/metinler
  ekranla aynı hesaptan. Grafik Vega-Lite olarak gömülür (CDN; internet yoksa not görünür, geri kalanı çevrimdışı).
  Hata olsa da `st` geri konur. YZ çağrısı yok.
- Panel: Hisse Analizi'nde "📄 HTML olarak indir" → "💾 Dosyayı kaydet (TK_analiz_YYYYMMDD_HHMM.html)" (iki adım:
  her açılışta boşuna üretilmesin). KULLANIM.md tablosu güncellendi.
- Testler: tests/test_html_export.py (3), test_hisse_page_html_download (panel). 514 test OK. Canlı veri kopyasıyla
  ENERY dosyası üretildi ve tarayıcıda açıldı: grafik, senaryolar, teknik tablo, takvim, haberler, dipnot görünüyor.

## 2026-11-15 — Uygulama içi güncelleme (kullanıcı: "güncel sürümü takip edecek bir versiyon")
- Kod: `bist_haber/guncelleme.py` (kontrol günde 1 kez · indir · SHA-256 · güvenli açma (data/.env/yol kaçışı reddi) ·
  gömülü Python'la içe aktarma denemesi · hazir.json · yeniden_baslat), `paket/Halley.cs` (--yeniden-baslat; dosya
  değişimini hiçbir şey çalışmazken yapar; eski kod guncelleme\onceki; yeni sürüm 2 dk'da açılmazsa otomatik geri dönüş;
  --port/--pencere-yok yeniden başlatmada korunur), `paket/app_baslangic.py` (panel kodu hata verirse bist_haber'siz
  "önceki sürüme dön" düğmesi), panelde üst bant + Ayarlar → Veri ve gelişmiş → 🔄 Güncelleme (kontrol, geri dön).
- Paket: uygulama kodu DERLENMİŞ (.pyc), kaynak .py yok; gizli bilgi denetimi (.env/.db/anahtar biçimi/kaynak) üretimi
  durdurur. `build_package.py --guncelleme-paketi` → Halley_Guncelleme.zip (~0,4 MB) + surum.json (sıra, sha256,
  ortam imzası = Python+kütüphaneler, başlatıcı imzası; uyumsuzsa "tam kurulum gerekir"). Kurulum programı eski
  guncelleme klasörünü siler. Lisans notu eklenmedi (kullanıcı istemedi).
- Dağıtım: herkese açık ayrı depo (ad onay bekliyor); asıl depo gizli kalır. Geliştirme klasöründe özellik kapalı.
- Uçtan uca (gerçek kurulum, 8507, penceresiz): A kur → B paketini hazırla → --yeniden-baslat: sıra 2134→2139, veri ve
  .env korundu, onceki yedeği var, son_islem "guncellendi"; geri dön: sıra 2134, "geri_donuldu"; --kapat temiz.
  Panel içinden tetikleme ve otomatik geri dönüş gerçek kurulumda ayrıca denenmedi (birim testleri var). 522 test OK.

## 2026-11-15 — Açık güncelleme deposu ve ilk yayın (kullanıcı: "Evet, oluştur")
- Herkese açık depo: karakasfufu/Halley-guncelleme (yalnız README + sürüm dosyaları; kaynak kod yok).
- İlk sürüm v202611152200 = 2026-11-15 (0dae4a7): Halley_Guncelleme.zip (0,44 MB; 64 dosya, tek .py başlangıç
  dosyası, data/.env/anahtar yok), surum.json, Halley_Kurulum.exe (SHA-256 bb087c77…9019). Defender: ikisi de temiz.
- Gerçek adresten doğrulama: eski test kurulumu (sıra 2134) kontrol → "yeni", indirdi, SHA-256 tuttu. Ardından PANELİN
  İÇİNDEKİ "🔄 Güncelle" düğmesiyle: Halley kapanıp yeni sürümle açıldı (sıra 2200), son_islem "guncellendi", panelde
  "✅ Halley güncellendi… Verileriniz korundu", veri ve .env korundu. Otomatik geri dönüş (yeni sürüm açılmazsa) gerçek
  kurulumda denenmedi; birim testleri ve elle geri dönüş denemesi var.
- Özel depodaki v2026.11.09 sürümüne de aynı kurulum dosyası konuldu (başlık "güncel: 0dae4a7").
- Yeni sürüm yayımlama adımı (bundan sonra): build_package.py --guncelleme-paketi → surum.json'a not → gh release
  create v<sıra> -R karakasfufu/Halley-guncelleme (zip + surum.json + kurulum dosyası).

## 2026-11-15 — Güncelleme kontrolü her açılışta (kullanıcı: "her açılışta güncelleme var mı diye kontrol etsin")
- update_banner artık `guncelleme.kontrol(zorla=True)` (her panel oturumu başında); ağ zaman aşımı 6 → 4 sn; ağ
  hatasında son bilinen bilgiyle devam. Ayarlar metni ve KULLANIM.md "🔄 Güncelleme" bölümü eklendi. 522 test OK.
- Yayın v202611152318 = 2026-11-15 (9ad93a9) açık depoya (zip ae039bd8…, kurulum 62108e46…a060;
  Defender temiz; ortam/başlatıcı imzası öncekiyle aynı → uygulama içinden güncellenir).
- Doğrulama (test kurulumu, sıra 2200): eski sürüm "20 saatte bir" kuralıyla bandı göstermedi (beklenen); Ayarlar →
  "Güncellemeyi şimdi kontrol et" → 🔄 Güncelle → sıra 2318, "guncellendi", veri korundu. Yeni sürümde her oturum
  açılışında son_kontrol yenileniyor (23:32:03 → 23:32:14). Not: 2200 sürümündeki bir kurulum yeni sürümü en geç
  ~20 saatte kendiliğinden görür (o sürümün kuralı); müşteride henüz 2200 kurulu değil.

## 2026-11-15 — Haber metni sınaması (Python, yapay zekâsız): katkı yok
- İndirme bitti: 5.649 metnin 5.647'si. metin_model.py: son 12 ay E2 0,605 · R 0,602 · W 0,604 · RW 0,601; 2024 E2 0,612
  · R 0,610 · W 0,606 · RW 0,607. Fark aralıkları sıfır/altı; Brier iyileşmedi; en yüksek %20 R'si düşmedi-yükselmedi
  (0,166 → 0,159–0,161). Kelime modeli gürültü öğrendi. Kural tablosu: olumsuz %26,6 / nötr %28,2 / olumlu %31,2 (ara
  bakıştaki %39 tekrar etmedi). Karar: E3 yok, tp1_v1 kalır. ASAMA6_RAPOR Ek 4, MIMARI aşama 6 satırı güncellendi.
- Sınır: yapay zekâ haber puanıyla karşılaştırma yapılamadı (geçmişte puan yok); canlı kayıtlarla ölçülecek.

## 2026-11-16 — Halley 2.0 denetim raporu (FAZ 0; kullanıcının ilettiği "Master Technical Audit" isteği)
- HALLEY2_DENETIM_RAPORU.md: istekteki kurallar/sonuçlar kodla ve raporlarla doğrulandı; md. 4–17 için mevcut durum,
  dosya/fonksiyon, kanıt, eksik, artı/eksi; "kodda var / gerçek veride" tablosu; FAZ 1–6 planı (süre, risk, test,
  kabul); önerilmeyenler. Kod, veritabanı ve API'ye dokunulmadı (canlı DB salt-okunur sayıldı: hazır fırsat 2 açık /
  0 kapanmış; sanal işlem 30 kayıt, 3 girişli → 3 SL; takip 3 bekliyor).
- Başlıca bulgular: merkezi karar akışı ve zorunlu filtreler var (yeni motor gereksiz); signal_log değiştirilemez
  karar geçmişi; hazir_firsat aynı gün yeniden analizde üzerine yazılıyor; algoritma/parametre sürümü kaydı yok; prices
  tablosunda kaynak/indirme zamanı yok; MDD/Sortino/log loss/MAE/MFE/portföy simülasyonu yok; hayatta kalma yanlılığı
  var (araştırma evreni bugünkü 632 hisse); rejimin etkisi ölçülmedi; YZ çağrıları yalnız düğme/zamanlı (rerun'da yok).

## 2026-11-16 — Denetim raporuna Ek A: portföy backtest, canlı model izleme, bozulma tespiti (kod değişmedi)
- Bulgular: journal sermaye/nakit/eşzamanlı pozisyon tutmuyor (yalnız tek işlem + position_size); MAE/MFE yok;
  hazir_firsat.model_json aynı gün yeniden analizde güncellenebiliyor ve sonuç aynı satırda tutuluyor (değiştirilemez
  tahmin kaydı yok); live_check yalnız kapananları sayıyor (doğru) ama log loss/rejim/backtest farkı yok; araştırma
  evreni haber şartı içermiyor (geçmiş YZ puanı yok) → portföy simülasyonu teknik evreni ölçer.
- Plan: FAZ 1'e portföy simülatörü + MAE/MFE; FAZ 2 = canlı tahmin defteri (tahmin + tahmin_sonuc, yalnız eklenir,
  tetikleyiciyle korunur) öne alındı; FAZ 5'e bozulma uyarıları (≥50 sonuç, %90 GA, PSI>0,25; otomatik işlem yok).
  Toplam ~10,5–11,5 gün, 0 $.

## 2026-11-16 — Denetim raporu Ek B: nihai plan (kullanıcının sırası), FAZ 1 tasarımı, yedek/geri dönüş (kod değişmedi)
- Sıra: 1 tahmin defteri · 2 portföy simülatörü · 3 metrikler/MAE-MFE/veri · 4 strateji×rejim · 5 hedefler · 6 bozulma uyarıları/hız · 7 vadeler (~11–11,5 gün, 0 $).
- FAZ 1: tahmin + tahmin_sonuc (yalnız eklenir, tetikleyicili), plan imzası UNIQUE + INSERT OR IGNORE (rerun/tekrar tek satır), sonuç tahminin dondurulmuş seviyelerinden journal.evaluate ile, aynı mumda TP1+SL → SL + ayni_gun_belirsiz, ölçüme yalnız açılıştan önce kaydedilmiş ve sonradan=0 son tahmin girer. Göç yalnız ekleme; öncesinde otomatik yedek + integrity_check; geri dönüş 3 seviye, kopyada denenecek. Yalnız FAZ 1 için onay istendi.

## 2026-11-16 — FAZ 1 canlı tahmin defteri (dal: faz1-tahmin-defteri; CANLIYA ALINMADI)
- defter.py (yeni), db.py göçü (yedek→integrity_check→tek işlem), ready.py iki bağlantı, tp1_model.plan_context, app.py Performans bölümü; 17+1 test. 540 test OK.
- Gerçek kopya sınaması: 20/20 tablo göç sonrası aynı; BAHKM/ENERY yeni→tekrar; UPDATE/DELETE reddedildi; eski kod (3310a61) hatasız açtı; tablo silme ve yedek geri koyma birebir. Canlı DB: tahmin tablosu yok, yedek yok. Ayrıntı: HALLEY2_DENETIM_RAPORU Ek D.

## 2026-11-16 00:43 — FAZ 1 CANLIYA ALINDI (kullanıcı: "Evet, canlıya al")
- Sıra: faz1 dalı main'e ileri birleştirildi (ac24f8f), 540 test OK → Halley kapatıldı → elle yedek
  data/yedek/bist_haber_20261116_004323_faz1_oncesi.db (integrity ok, canlıyla birebir: 20 tablo, 167.412 satır) →
  kod canlı klasöre → göç TEK süreçte kontrollü çalıştırıldı (otomatik yedek
  bist_haber_20261116_004339_tahmin_defteri_oncesi.db, integrity ok) → 20 mevcut tablo birebir aynı, canlı integrity
  ok, 4 tetikleyici yerinde → Halley başlatıldı (sağlık OK, 2 okuyucu, ikinci göç/yedek yok) → Performans'ta defter
  bölümü hatasız ("henüz tahmin yok").
- Bekleyen gerçek veri kabulü: 16.11 08:30 sabah kontrolü (BAHKM/ENERY tahminleri), ilk akşam analizi ve açılış
  sonrası sonuçlandırma. Müşteri güncellemesi YAYIMLANMADI (ayrı onay). FAZ 2 başlamadı.
- Geri dönüş: önceki commit 3310a61 kodu + gerekirse DROP TABLE tahmin_sonuc, tahmin; ya da elle yedeği geri koymak
  (Halley kapalıyken).

## 2026-11-16 — FAZ 1 panel düzeltmesi: "Planı üreten analiz" + "Kayıt zamanı" (dal: faz1-panel-etiket; CANLIYA ALINMADI)
- Neden (Ek E2): sabah onaylanan akşam planı `ready.py` satır 500 gereği analiz="aksam" etiketiyle kaydediliyor; panelde
  "Akşam / Sabah" yanıltıcıydı. Kayıt, imza, model, sonuçlandırma, seçim kuralları DEĞİŞMEDİ.
- `defter.kayit_zamani(tahmin_zamani, giris_gunu)`: giriş günü yazıldıysa "sabah", önceki tarihte (gece yarısını geçen
  akşam analizi dahil) "aksam"; `defter.ozet(..., kayit=)`. Panel: "Analiz" → "Planı üreten analiz" (açıklamalı),
  yeni "Kayıt zamanı" (Tümü / Sabah / Akşam).
- Testler: test_defter.KayitZamani (kural + filtre; kayıtlar birebir aynı), panel testine etiket/filtre kontrolü.
  542 test OK. Prova kopyasında (08:30, etiket 'aksam', 2 tahmin): Planı üreten Akşam = 2, Kayıt Sabah = 2, Kayıt
  Akşam = 0; tahmin kayıtları değişmedi; panel hatasız.

## 2026-11-16 — FAZ 1 dış inceleme bulguları A–G (dal: faz1-dogrulama; CANLIYA ALINMADI)
- Başlangıç main 60ff0b2: 540 test OK. Bulgu testleri düzeltme öncesi 15/16 başarısız (eşzamanlılık zaten sağlanıyordu).
- Düzeltmeler: journal.tp1_hedefi (+etiketle; yeniden çalıştırılmadı; 34.665 eğitim planının 91i etkilenir), değerlendirme sözleşmesi (kural s2, komisyon, kayma, protokol), sürüm grupları (ozet tek grup), veri_eksik (nihai yazılmaz), MAE/MFE gunluk_s2 penceresi, dönem dışı karşılaştırma yok notu, defter_olay + kapsam, güven = örnek + bağımsız gün, s1 sonuçları için ayrı tahmin_degerlendirme (s1 değişmez). Hata yolundaki rollback kaldırıldı (hazır fırsatı geri alırdı).
- Şema v2 (yalnız ekleme, yedekli, tek işlem). Canlı kopyada: 22/22 tablo aynı, eski alanlar boş kaldı, eski kod (60ff0b2) hatasız açtı, geri dönüş 2-3 birebir. Canlı DB v1, dokunulmadı. 559 test OK. Ayrıntı: HALLEY2_DENETIM_RAPORU Ek F.

## 2026-11-16 10:45–10:51 — FAZ 1 v2 CANLIYA ALINDI (cb74a3b)
- Durdurma 10:45:11 (aktif iş/yazma günlüğü yoktu) → kod yedeği kod_60ff0b2_20261116_104552 + DB yedeği bist_haber_20261116_104552_faz1_v2_oncesi.db (integrity ok) → kod → göç 10:46:13-17 guncellendi_v2 (otomatik yedek ok) → 22/22 tablo aynı, BAHKM/ENERY v1 özeti d5d7973ca0bbe41e aynı, yeni alanlar boş → 8 tetikleyici (deneme kopyada) → başlatma 10:47:03 sağlık OK. Model parmak izi 09f8e5e0… aynı. Panel hatasız, sayılar DB ile eşleşiyor. Yeni s2 tahmin ve gerçek sonuçlandırma henüz gözlenmedi (akşam/sabah). Uyku 01:15: kullanıcı bilgisayarı kapattı. Ayrıntı: Ek G.

## 2026-11-16 — FAZ 2 portföy backtest simülatörü (dal faz2-portfoy; araştırma, canlıya dokunulmadı)
- arastirma/asama6/portfoy.py: journal.evaluate/position_size, sectors, defter.belirsiz_gunler, ready sıralaması tek kaynak; gün sırası d−1 bilgisiyle giriş, d içinde çıkış, aynı gün satış nakdi kullanılmaz; maliyet alış+satış toplamı, satış bacağı giriş fiyatı üzerinden (journal ile birebir). 14 test, 573 test OK.
- Takvim hisse mumlarının birleşimi (XU100 verisinde 25 Aralık 2023/24/25 yok; gerçek koşuda sıra koruması yakaladı).
- Sonuç (teknik plan evreni, haber yok): canli_ortak son 12 ay −%22,7 (MDD −%34,1, PF 0,72, ort R −0,19) · 2024 +%35,9 (MDD −%15,2, PF 1,34, ort R +0,26). Evrendeki tüm planlar son 12 ay ort R +0,02 → sıralama kuralı bu dönemde ortalamanın altında seçti. Ayar değiştirilmedi. Ayrıntı: Ek H.


## 2026-11-16 — FAZ 2 ek kontroller (dal faz2-portfoy; araştırma, canlıya dokunulmadı; ayar değiştirilmedi)
- Simülasyonlar bu kontrollerden önce çalıştırılmıştı; aynı ayarla yeniden üretim 4/4 birebir aynı.
- Seçim yalnız 12 karar anı alanını okur (sonuç/model sütunu yok); son 12 ay = 2025-11-14 … 2026-11-13.
- Geleceğe bakmama: yeni GelecegeBakmama testleri (5) + gerçek veride kısıtsız 5.244 işlem tüm gelecekle journal'a
  ayrıca verildi: 0 uyuşmazlık.
- Sınırlar gerçek veride: en çok 5 pozisyon, sektörde 2, açık risk ≤ %5,55 (< %6). Sektör listesi güncel KAP
  (2026-11-09), tarihsel değil.
- Yeni tespit (değiştirilmedi): adet planlanan girişle hesaplanıyor, alış açılıştan → SL'de kayıp %1'i aşabiliyor
  (ortak 12 ay 43/104, en çok %2,31). Ayrıca açılışta boşluk (GOLTS −3,15 R).
- Dönem sonu pozisyonlar zorla kapatılmadı. Ayrıntı: HALLEY2_DENETIM_RAPORU Ek H2.

## 2026-11-16 — FAZ 2 Ek H3: risk hesabı farkı (dal faz2-portfoy; araştırma, canlı kural değişmedi, geriye dönük doğrulama)
- portfoy.py: adet_temeli seçeneği (varsayılan planlanan_giris = mevcut; orijinal metrikler 4/4 birebir) + gerçek dolumla başlangıç/giriş anı risk tanılaması.
- Mevcut: başlangıç riski bütçeyi aşan ~%40 (ör. ortak 12 ay 57/141, en çok 1,37 kat); %1 üstü kayıp 43/136 (27 giriş farkı, 4 stop altı, 12 birleşim, maliyet 0). Portföy %6 gerçek dolumla da aşılmadı (en çok %5,60).
- Alternatif (azami girişle önceden adet, açılış seansına azami limitli emir): başlangıç aşımı 0; kalan aşım yalnız stop boşluğu (1–4 işlem). Aynı işlemler, küçük pozisyon: ortak 12 ay −%22,7 → −%19,8; 2024 +%35,9 → +%28,9; Sortino/PF ~aynı. Otomatik seçilmedi.
- Stop altı açılış: alt sınır yok; journal alış günü satışı SL fiyatından yazıyor → 'SL' ama kâr (iyimser; ortak 12 ay +3.739 TL). Ayrı düzeltme önerildi, uygulanmadı.
- RiskTemeli 4 test; portföy 23/23. Ayrıntı: HALLEY2_DENETIM_RAPORU Ek H3.

## 2026-11-16 — FAZ 2 Ek H4: stop altı açılışta yapay kâr giderildi (kural s3; dal faz2-portfoy; araştırma, canlı kural değişmedi)
- journal.giris_kosulu (yeni öneri: açılış ≤ SL girişsiz) + evaluate(kural='s3'): alış ≤ SL ise alış günü satışı alış fiyatından (gerçek alış korunur). Varsayılan s2 birebir; canlı çağrılar değişmedi.
- Etki: canlıda etkilenen kayıt 0 (salt-okunur); eğitim planlarının 293/39.112'si (hepsi y=0, etiket değişmez). Defter için s3 ayrı kural sürümü tasarlandı, uygulanmadı.
- Düzeltilmiş bağımsız koşular (ortak 12 ay): mevcut_s3 −%14,4 (yol bağımlılığı: 27 işlem değişti), alternatif_s3 −%22,1 (saf düzeltme etkisi −2,4 puan); başlangıç riski aşımı 56 vs 0. Önceki raporlara 'hatalı gerçekleşme varsayımı' notu.
- test_kural_s3 (14); 596 test OK. Ayrıntı: HALLEY2_DENETIM_RAPORU Ek H4.

## 2026-11-16 — FAZ 2 Ek H9: son kapsam (dal faz2-portfoy; araştırma, canlı değişiklik yok)
- journal s3: gerçek alış (kullanici_kaydi) ile varsayımsal çıkış (kural simülasyonu) ayrı alanlarda; alış ≤ SL bacağı 'SL varsayımı'. s2 çıktısı birebir.
- Bulgu: simülatör açılışa bakıp elenen adayın yerine sıradakini aynı açılıştan alıyordu (teorik). Yeni emir_modeli=onceden_limit: emir listesi açılıştan önce, dolmayan emrin yerine aday yok. Eski model varsayılan, teorik etiketli.
- Sınıflama: doğrulanmış yok; emir altyapısına bağlı = önceden limit (Midas doğrulanmadı); teorik = açılışı görüp (T1/T2) ve bütün s2 koşuları.
- E modeli (ortak): 12 ay −%25,2 / −%21,7 (planlanan / azami), 2024 +%22,9 / +%19,5; teorik T1 2024 +%35,1. Ek H4 24 koşu regresyonu aynı. 603 test OK. FAZ 2 simülatör olarak kabul önerildi; strateji başarısı değil.

## 2026-11-16 — FAZ 2 KABUL EDİLDİ (simülatör olarak; commit 6d7f5d5, etiket faz2-kabul)
- Kullanıcı kabulü: araştırma simülatörü; kârlılık, emir uygulaması ya da canlıya geçiş onayı değil. Canlı kural değişmedi.
- Ana sonuç = önceden limit emir + s3 (sonuclar_faz2/kabul/, faz2_kabul_kaydi.py). Önceki s2/teorik rakamlar ana sonuç değil (rapora not). Ayrıntı: Ek H10.

## 2026-11-16 — FAZ 3 başladı (dal faz3-metrik; ARA KAYIT, tamamlanmadı; canlı kod/DB değişmedi)
- Veri taraması (arastirma_5y.db, salt-okunur; arastirma/faz3/veri_guvenilirlik.py): 674.958 mum, 631 hisse; eksik gün 348, sıfır hacim 4.296, bayat (OHLC aynı + hacim 0) 3.762, OHLC tutarsız 25, >%10,5 sıçrama 605 (106'sı KAP kurumsal işlem bildirimine ±5 gün yakın; >%25: 83; ör. TRHOL +%10.124 / −%99 veri hatası). Son güne gelmeyen 1 hisse (ISKUR 2026-08-12).
- FAZ 2 kabul işlemlerine etkisi: tutma süresinde bayraklı mum 0; 22 günlük sinyal penceresinde 0–1; 250 günlük gösterge penceresinde sıçrama/tutarsızlık ortak 12 ay 2, 2024 15, teknik 12 ay 5, 2024 14 işlem. Sonuçlar değiştirilmedi.
- Yeniden düzeltme (yeniden_duzeltme.py): prices.update auto_adjust=True + INSERT OR REPLACE, kaynak/zaman kaydı yok. Araştırma ve canlı DB ortak 156.441 günde %0,1 üstü fark 927 gün / 4 hisse (MGROS −%1,32, FLAP −%1,07).
- KALAN: metrik doğrulama ve ek metrikler, dağılımlar, MAE/MFE tanımı, fiyat kaynağı şeması ve kopyada göç testi, delist/tarihsel sektör kaynak araştırması, model metrik kaynağı, testler ve FAZ 3 raporu.

## 2026-11-16 — FAZ 3 tamamlandı (dal faz3-metrik; araştırma; canlı kod/DB değişmedi; KABUL BEKLİYOR)
- Metrikler: bağımsız kodla 8 kabul koşusunda 10 metrik birebir; hata yok. Ek metrikler (CAGR, oynaklık, Calmar, Ulcer, ödeme oranı, dağılımlar, ardışık kayıp serileri) eklendi.
- MAE/MFE: iki R paydası (plan/dolum), gün içi çıkış alt sınırı (12 ay 109/130), çıkış sonrası hareket ayrı alan.
- Veri: 348 eksik günün 329'u tek piyasa geneli gün (2024-04-09), 19 olası veri eksikliği; 605 sıçramanın 106'sı KAP bildirimine yakın (kanıt değil); iki DB farkı 4 hissede 2025-11-10…2026-10-12 sabit oran (neden kesinleşmedi; araştırma DB'sinde blok sınırı taban kayması olası); adayların %27'sinin gösterge penceresinde sıçrama; düzeltilmemiş fiyat yok → etki ölçülmedi.
- fiyat_izi_v1 (hazırlık): fiyat_indirme/fiyat_eski/veri_anlik + prices.indirme_id; kopyada göç/geri kurma/geri dönüş provası tamam; testte bulunan 'değişmeyen satırı yeniden yazma' hatası düzeltildi.
- Delist/sektör: BIST kalıcı çıkarılanlar listesi ve DataStore (ücretli) var; tarihsel sektör arşivi bulunamadı. Model kökeni: tp1_v1 ← etiket2.csv (en olası), e90d0ab. 618 test OK. Ayrıntı: HALLEY2_DENETIM_RAPORU Ek I.

## 2026-11-16 — FAZ 3 son düzeltmeler (Ek I2; dal faz3-metrik; canlı değişmedi; KABUL BEKLİYOR)
- MAE/MFE: işaret (MAE ≤ 0, MFE ≥ 0) ve sınır yönü: stopta çıkışta MAE kesin/MFE alt sınır, hedefte MFE kesin/MAE işaretli üst sınır; sinirlar() + 3 elle doğrulanabilir test. Ek I.3 ifadesi düzeltildi.
- Yeniden değerlendirme (eğitim yok, EĞİTİM İÇİ): tp1_v1 sabit, 34.579 örnek; AUC 0,6361 → 0,6347 (tp1_hedefi, 91 değişen) → 0,6350 (+s3, 250 çıkan). Dönem dışı: kat modelleri saklanmadığı için yapılamadı.
- Köken: tp1_v1 ← etiket2.csv, oturum günlüğü komut+çıktısıyla bağlandı (kriptografik değil); 86 fark = x_trend süzgeci. Kanıtlar data/backtest/arsiv/faz3_koken_20261116/ (435 MB, Git dışı, manifest Git'te).
- 621 test OK. FAZ 3 kabul önerisi: metrik/izlenebilirlik altyapısı + veri envanteri olarak; duyarlılık analizi yapılmadı.

## 2026-11-16 — FAZ 3 KABUL EDİLDİ (commit 94d2fc8, etiket faz3-kabul); FAZ 4 onaylandı
- Kapsam: metrik/izlenebilirlik altyapısı + veri envanteri. fiyat_izi canlıda değil; duyarlılık analizi yapılmadı.

## 2026-11-16 — FAZ 4: strateji × rejim (dal faz4-rejim; araştırma; canlı değişmedi; KABUL BEKLİYOR)
- Ön kayıt c1a4192 (sonuçlardan önce); rejim = canlı regime.py trend × oynaklık (karar anına kadarki veri; genişlik kullanılmadı); 30.470 tekil işlem (canli_ortak, s3 stop altı 217 çıkarıldı); gün kümesi bootstrap %95; n<30 / gün<20 YETERSİZ.
- 23 ana grup, 15 yeterli; 8'inde R aralığı sıfırı dışlıyor ama aynı hisse 10 gün içinde tekrar %54–83 → bağımlı; anlamlılık iddiası yok. Kırılım tekil R +0,33 > geri çekilme +0,07; geri çekilme × yükseliş × yüksek oynaklık −0,35; dönemler arasında değişken; düşüş rejimi az.
- Sonuç: uygulanabilir katkı yok; hipotez olarak kaydedildi. Portföy metriği çıkarılmadı. 629 test OK. Ayrıntı: Ek J.

## 2026-11-16 — FAZ 4 KABUL EDİLDİ (betimleyici araştırma; commit 2538d28, etiket faz4-kabul)
- Kapsam: strateji türü × rejim tekil işlem betimlemesi (Ek J). Strateji/rejim filtresinin canlıya alınması ONAYLANMADI. Sonradan eklenen rapor dosyası kabulün parçası değil.

## 2026-11-16 18:25 — FAZ 1 canlı kanıtı: v2 sonrası ilk akşam analizi (yalnız özet; gerçek rapor repoya konmaz)
- Akşam çalıştırması 18:21–18:23 gözlendi; fiyatlar 16.11'e güncellendi; bütünlük ok.
- 3 yeni s2 sözleşmeli tahmin kaydedildi; kural, komisyon, kayma, maliyet protokolü alanları dolu (gözlendi).
- 16.11 girişli 2 eski tahmin açık; nihai sonuç yok. Eski (v1) sütun özeti değişmedi. Sonuç/değerlendirme/olay 0.
- GÖZLENMEDİ: sabah kontrolü (17.11), gerçek sonuçlandırma (TP/SL/30 gün), s1→s2 yeniden değerlendirme. FAZ 1 kabul edilmedi.

## 2026-11-16 — Olay: gerçek bekçi raporu GitHub'a gönderildi (faz4-rejim, 31dbcf7; 63f88a5'te kaldırıldı)
- Depo HERKESE AÇIK (06.11.2026'dan beri; önceki notlardaki 'özel/gizli' ifadesi yanlıştı).
- İçerik sınıfı: işlem raporu (hisse kodları, tarih, fiyat, model olasılığı, çalıştırma zamanı). Kimlik bilgisi/API anahtarı/kişisel veri YOK (desen taraması 0).
- Geçmiş temizliği zorla gönderme gerektiriyor; izin denetimi engelledi, aşılmadı. Temiz dal: faz4-rejim-temiz (2538d28 üstüne, dosyasız). Eski dalın silinmesi kullanıcı adımı.
- .gitignore: dongu_*.txt, faz1_aksam/sabah_*.txt, *canli_rapor*, *bekci_rapor* — yalnız GELECEKTEKİ eklemeleri önler, geçmişi temizlemez.

## 2026-11-16 — FAZ 5: 5/10 günlük hedefler (dal faz5-hedef; araştırma; canlı/model değişmedi; KABUL BEKLİYOR)
- Ön kayıt 6430231 (sonuçlardan önce), kod 5dd858f. Hedefler ayrı: zaman çıkışı getirisi (H5/H10_pozitif, net %, R_plan) ve TP1 olayı (H5/H10_tp1, journal.evaluate ilk N mum). Ortak örneklem 30.404, ambargo 45 gün, ön işleme/λ yalnız eğitimden.
- Ön kayıtlı karar: TP1 olay hedeflerinde ölçüt geçti (AUC 0,67–0,73), getiri hedeflerinde katkı yok. Sonradan tanı: yalnız TP1 uzaklığı AUC 0,69 → büyük kısmı mekanik; üst %20 son 12 ayda yine eksi. Uygulanabilir katkı yok; aday model etkinleştirilmedi, dosyaya yazılmadı.
- 639 test OK. Ayrıntı: Ek K.

## 2026-11-16 — FAZ 5 KABUL EDİLDİ (araştırma teslimi; commit 6c7e7a2, etiket faz5-kabul)
- Ayrımlar: TP1 olay hedefleri ön kayıtlı ölçütü geçti; mekanik uzaklık referansı sonradan incelendi, ek katkı/ekonomik fayda kanıtlanmadı; getiri hedeflerinde katkı yok; dönemler bağımsız değil.
- '+%3,7' = Brier becerisi (R1'e göre GÖRELİ azalma), yüzde puan değil. Kabul kaydı arastirma/faz5/kabul_kaydi.json; yeniden üretim SHA-256 birebir aynı. Etkin model/kurallar değişmedi.

## 2026-11-16 — FAZ 6: model izleme + hız (dal faz6-izleme; canlı değişmedi; ÖNERİ: KISMİ KABUL)
- Ön kayıt 1a492a3, değişiklik 1 c141c71 (sonuçlardan önce: kümeli analitik aralıklar). izleme.py: P1/P2/K1 uyarı, R1/G1 bilgi; yetersiz veri; teyit (≥20 yeni gün), bastırma; salt-okur panel; yerel kayıt (gitignore). defter.olculen_kayitlar ortak seçim.
- Yapay seri (500 tekrar, 250 gün, tohum 20261116, ~29 dk): K1 BAŞARISIZ — normal seride 250 günlük izlemde %14,4/%21,2 en az bir yanlış alarm (günlük oran değil); P2 son 60 gün ayırt kaybını %69 yakalıyor (yanlış alarm %0,4); P1 düşük güç. Eşikler değiştirilmedi; K1 canlıya alınmaz; yeniden tasarım ayrı ön kayıt + ayrı doğrulama serisi.
- Hız: regime önbelleği — 5 çağrılık aynı-gün iş yükü 2,51 → 1,06 sn, sonuç aynı; bütün uygulama ölçülmedi. API: 09.11'den beri ücretli çağrı yok — tasarım (bekçi ai=False, sabah haber kontrolü kapalı); 733 analize uygun haber bekliyor; bu ay 2,29 $.
- Ek M: yedi faz değerlendirmesi (zorunlu Z1–Z5, entegrasyon Ü1–Ü5, isteğe bağlı İ1–İ5; tavan olasılığı ayrı İ4). 656 test OK.

## 2026-11-16 20:00 — FAZ 6 KISMEN KABUL EDİLDİ (commit 3e5c325, etiket faz6-kismi-kabul)
- Kabul: ölçüm/test altyapısı, yapay seri belgelemesi, rejim önbelleği (5 çağrılık aynı-gün iş yükü), haber/API teşhisi. Hiçbir bileşen canlıya alınmadı.
- Açık: K1 başarısız (uyarı üretmez); P1 düşük güç; P2 %0,4 yalnız yapay senaryo (canlı kanıtı değil); canlı eşik doğrulaması yok.
- Öneriler (uygulanmadı, Ek L2): yanlış alarm hedefi ≤ %5 / 250 gün, %95 üst sınır < %5, ≥ 2.000 tekrar; K1 v2 planı (örtüşmeyen bloklar, Bonferroni, bağımsız blok teyidi, yeni tohum doğrulama serileri); haber politikası (son 2 iş günü, tekrar eleme, eski haber geçmişe taşınmaz, günlük ~0,50 $ sınırı).
- Müşteri sürümü gereksinimi eklendi: son haber analizi zamanı, bekleyen sayısı, güncellik uyarısı. Depo bilerek açık (kullanıcı); zorunlu düzeltme değil.

## 2026-11-16 — FAZ 7: vade tasarımı (yalnız belge; dal faz7-vade; KABUL BEKLİYOR)
- Ek N: V0 gün içi (önerilmez), V1 1–5 gün (araştırma gerekli; FAZ 5'te katkı yok), V2 bugünkü kısa vade (mevcut altyapı), V3 1–3 ay (ek veri + araştırma), V4 uzun (ek veri + araştırma; bağımsız yıl az).
- Çelişki sunumu (birleşik puan yok), ortak portföy (tek hisse tek pozisyon, vade başına risk bütçesi), vade alanı ve ayrı sözleşme, vade_firsat tablosu, ambargo ≥ pencere, mekanik ve endeks referansı, durdurma ölçütleri, şema/dosya taslağı, emek tahmini.
- Müşteri pilotu: yalnız V2 + Ek M zorunluları; diğer vadeler isteğe bağlı. Kod, test, simülasyon yok.

## 2026-11-16 — FAZ 7 KABUL EDİLDİ (tasarım belgesi; commit b061eff, etiket faz7-kabul) + tek entegrasyon planı (Ek O)
- Ek N2: risk payları, tek pozisyon ve araştırma eşikleri yalnız tasarım önerisi (canlı kural değil); örtüşmeyen pencere sayısı yardımcı bağımlılık ölçüsü, kesin etkin örneklem değil (N.7/N.8 düzeltildi).
- Ek O: Ek M'nin uygulama sırası — O1 FAZ 1 kanıtları, O2 s3 + risk gösterimi, O3 haber göstergesi + bütçeli politika, O4 fiyat_izi, O5 izleme (K1 kapalı), O6 birleştirme/paket/kurulum/yayın; ~6–7 iş günü. Yalnız plan; kod/çağrı/eğitim/canlı geçiş yok.

## 2026-11-16 — O3 geliştirme/test: haber güncellik göstergesi + bütçeli politika (dal o3-haber; canlı değişmedi; ücretli çağrı yok)
- haber_kapsam.py: son iki BIST işlem günü kapsamı (market_calendar; yarım gün dahil, 2027 dini bayram uyarısı), günlük 0,50 $ + aylık bütçe (kısıtlayıcı olan), süreçler arası analiz kilidi, güncellik göstergesi (toplama ≠ analiz; bekleyen yoksa bayat değil).
- analyzer: kilit, günlük sınır, ilk gerçek maliyet görülene kadar tek iş (testte bulunan aşım: 0,071 > 0,05 → 0,0428), sonradan_analiz işareti, tahmini/gerçekleşen ayrı. pipeline: işlem günü kapsamı. Panel: güncellik bölümü + günlük sınır ayarı.
- Canlı kopya: 114 güncel bekleyen, 619 eski, 9/6 metinsiz; geçerli sınır günlük. Testler: test_o3_haber 18, tam takım 674 OK, ağ 0. Not: geliştirmede iki test KAP'ın ücretsiz şirket listesine istek attı (429); düzeltildi.
- Ek O: O2 geliştirme/test Midas doğrulamasından ayrıldı; 'stop seviyesinde tahmini kayıp' (boşluk/kayma açıklamalı).

## 2026-11-16 21:30 — O3 son düzeltmeleri: kesin bütçe rezervasyonu + güncellik/kapsam ayrımı (dal o3-haber; canlı değişmedi; ücretli çağrı yok)
- harcama.py: süreçler arası (BEGIN IMMEDIATE) maliyet rezervasyonu. Çağrı üst sınırı = (UTF-8 bayt + 4096) × girdi fiyatı + 16.000 × çıktı fiyatı; max_completion_tokens=16000 zorunlu, OpenAI(max_retries=0). Haber işi başlamadan iş zarfı (ön eleme + tam analiz + ikinci görüş + olası ek denemeler); yetmezse iş başlatılmaz. Hata/zaman aşımı/kullanım yok → 'belirsiz', tamamı sayılır; çöken süreçten kalan açık kayıtlar da sayılır.
- Bütün üretim yolları korumalı: haber analizi (bütçe verilmezse Ayarlar), derin inceleme, ucuz test, rapor yorumu, kaçırılan açıklaması, komut satırı. Gerçek istemci bütçesiz çağrı yapmaz (ButceKorumasiYok). Açık istisna: butcesiz_izin (yalnız sahte istemci), pilot (ayrı defter). gpt-5 için temperature baştan gönderilmiyor (zaten çıkarılıyordu; model aynı).
- Güncellik: tam 'güncel' yalnız KAP listeleri eksiksiz + bekleyen yok + metinsiz güncel yok + takvim doğrulanmışsa; 'toplama eksik' / 'analiz bekliyor' / 'kapsam eksik' / 'takvim doğrulanmadı' ayrı. Panel: 'harcanmış sayılan', kesin garanti değildir.
- Kanıt: test_o3_haber 31 OK; tam takım 687 OK, ağ 0. Kopya prova: yalnız yeni tablo; canlı dosya değişmedi. Zarf medyanı 0,071 $ (gerçek 0,015 $); günlük 0,50 $ ile ~28 haber (~32 yerine). Ek O-3b. Kontrollü canlı geçiş onayı bekleniyor.

## 2026-11-16 21:25 — O3 CANLIYA ALINDI (kontrollü; yalnız O3; ücretli çağrı yok)
- Canlı: dal o3-canli 0e8bbaf = main 6a95652 + yalnız iki O3 commit'i (FAZ 2–7 değişiklikleri canlıya alınmadı). 590 test OK, ağ 0.
- Varsayımlar doğrulandı: gpt-5-mini 0,25 / 2,00 $ / 1M token; max_completion_tokens düşünme dahil toplamı sınırlar. OpenAI modeli "deprecated" işaretlemiş (model değiştirilmedi).
- Defter geçiş öncesini sayıyor: ay 2,285221 $ = eski hesap; gün 0; çift sayım yok. Eski "ucuz test" maliyetleri hiç kaydedilmemişti (OpenAI paneli).
- Durdurma 21:23:50; yedek data/yedek/kod_main_6a95652_20261116_212401 + bist_haber_20261116_212401_o3_oncesi.db (integrity ok, yedek = canlı); kopyada yedek→uygula→geri dönüş sınandı; göç yalnız harcama_rezervasyon; 24/24 tablo (170.636 satır) ve 22 tetikleyici aynı; yeniden başlatma 21:25:01 (~1 dk).
- Panel: "analiz bekliyor" (114) + "kapsam eksik" (9), bütçe 0,00/0,50 · 2,29/10,00 $, garanti değildir notu. Bekçi ai=False. Geri dönüş aracı araclar/o3_gecis.py.
- Bekleyen: tek haberlik ücretli deneme (öneri kap:1698251 ARDYZ; azami ayrılacak 0,1058 $; "Yalnız işaretlediklerim" + tek haber) — kullanıcının düğmesi. Ek O-3c.

## 2026-11-16 21:47 — O3 tek haberlik ücretli doğrulama (kullanıcı düğmesi) → KABUL ÖNERİSİ
- Yalnız kap:1698251 (ARDYZ) işlendi: 1 zarf (0,1058 $ → zarf_kapali) + 1 çağrı (tamam, kayda_gecti=1); ai_calls 1 satır ok, deneme 0; ikinci görüş eşik altında (etki 1 < 3).
- Maliyet 0,006398 $ (2.737 / 2.857 token): defter = ai_calls = analyses. Ay 2,285221 → 2,291619 (çift sayım yok); belirsiz/açık 0. Panel 0,01/0,50 · 2,29/10 $, bekleyen 114 → 113.
- Geçmiş tahminler/hazır fırsatlar yedekle satır satır aynı; diğer yazımlar mevcut davranış (148 haberde content_hash, ARDYZ company_stats, journal guncellendi).
- Açık: OpenAI kullanım ekranı karşılaştırması (gecikmeli), kayıtsız eski ucuz test harcaması bilinmiyor (sıfır sayılmadı), gpt-5-mini deprecated, 9 metinsiz haber, 113 bekleyen (topluca işlenmedi). Ek O-3d.

## 2026-11-16 — O3 KABUL EDİLDİ (canlı o3-canli 0e8bbaf, etiket o3-kabul)
- Kapsam: Ek O-3c canlı geçiş + Ek O-3d tek haber doğrulaması. Kabul kaydı Ek O-3e.
- Açık: OpenAI kullanım ekranı karşılaştırması (aynı proje/model/zaman/kapsam; fark nedeni doğrulanmadan eski testlere bağlanmaz); kayıtsız geçmiş maliyet bilinmiyor (sıfır değil); "günde ~28 haber" kapasite garantisi değil; kuyruk topluca işlenmez.
- Sonraki: O2 geliştirme/test onaylandı (canlı ve müşteri yayını hariç).

## 2026-11-16 — O2 geliştirme/test: stop altı gerçekleşme s3 + risk gösterimi (dal o2-s3 819d8c3; canlı değişmedi)
- s3 araştırmadan birebir; yollar: yeni öneri s3 (açılış ≤ SL girişsiz), önceden açık pozisyon s2 sabit, gerçek alış korunur + çıkış varsayımsal; sürüm damgası (açık s3 kaydın s2ye dönmesi hatası bulundu, düzeltildi).
- Tahmin defteri: yeni sözleşme s3; her tahmin kendi kuralıyla; s2→s3 ayrı değerlendirme ve ayrı ölçüm grubu (birleştirilmez). FAZ 1: mevcut 5 tahmin s2 ile sonuçlanır (kopyada A=B).
- Panel: "stop seviyesinde tahmini kayıp", giriş kaynağı (azami giriş ön hesap / gerçek alış / plan), üst sınır değil + Midas doğrulanmadı uyarısı.
- Geri dönüş: kod geri dönüşü s3 tahmini varken hatalı sonuç yazar (kopya E) → ayar gerceklesme_kurali=s2 (kopya F doğru). 622 test OK, ağ 0. Ek O-2. Canlıya geçiş onay bekliyor (O1 + 17.11 açılış kontrolünden sonra önerilir).

## 2026-11-17 — FAZ 1 sabah kanıtı + O2 CANLIYA ALINDI (edcac9d) + pilot/beta pre-release v202611170052
- FAZ 1: sabah 08:37, 17.11 adayları onaylandı, BAHKM/ENERY açık, v1 özeti aynı, 5/5 kapsam, sonuç 0 (gerçek sonuçlandırma açık madde; Ek O-1a).
- O2: bütçe defterindeki 2 satır 16.11 tek haber denemesi (zarf + çağrı); 2404943→edcac9d tek değişiklik (önceden açık gerçek alış s2 kalır; paket testinde bulundu); 624 test OK. Açılış ~10:16 (adaylar SL üstünde), durdurma 10:19:07, yedek bist_haber_20261117_101917_o2_oncesi.db (integrity ok), göç yok, başlatma 10:20:05; değiştirilemez tablolar aynı, 19 bekleyen sanal kayıt s3 damgası, gerçekleşmişler eski kural. Geri dönüş yalnız davranış (gerceklesme_kurali=s2). Ek O-2b.
- Pilot: pre-release, Latest v202611152318 korundu; indirme doğrulandı (SHA-256 c83bb4bf…389a, Defender temiz); uygulama içinden önerilmez. Ek P1.

## 2026-11-17 — O2 canlı geçişi BAŞARILI (kayıt; edcac9d, etiket o2-canli-gecis) + geri dönüş uyumluluğu + pilot notu düzeltmesi
- Açık: gerçek s3 sonuçlandırması, FAZ 1 kabulü. Ücretli çağrı / ek geliştirme yok.
- Uyumluluk (s3 damgalı 19 sanal işlem + s3 tahmini, kopyada): eski kararlı kod damgaları siler (19→0), s3 tahminini sonuçlandırmaz → güvenli değil; O2/pilot + gerceklesme_kurali=s2 → damgalar korunur, s3 tahmini girişsiz (s3). Pilot sürüm notu düzeltildi (dosya aynı). Ek O-2c.

## 2026-11-17 — Git geçmişi temizliği (yanlışlıkla eklenen kişisel bilgi; Ek G-T)
- d5ef349→ce68145, ab463ee→e7ad2e6, 77d193c→eaa14f9, 3e702d8→4ea7412 (o3-haber); ref güncellemesini kullanıcı yaptı. Uzak ve yerel referanslardan erişim 0. Eski commit GitHub önbelleğinde (Destek talebi kullanıcıda); önceki kopyalar geri çekilemez. Etiketler, kabul kayıtları ve pilot değişmedi.

## 2026-11-17 — Pilot geri dönüş talimatı kurulu pilotta doğrulandı, not yeniden düzeltildi (Ek O-2d)
- Kurulu pilotta elle ayar düzenlemesi: yeni kural s2, 19/19 s3 damgası korundu, s3 tahmini girişsiz (s3), ayarlar korundu, panel açıldı. Bozuk JSON ayarları okunamaz kılar → not: önce kopya al, sonra kontrol et. Yol hatası düzeltildi; eski kararlı kurulum önerilmiyor.
- Açık: d5ef349 SHA ile erişilebilir (tam silinme tamamlanmadı; Destek talebi kullanıcıda, garanti yok); gerçek s3 sonuçlandırma; FAZ 1 kabulü.

## 2026-11-17 — Normal kanalda yayın v202611171741 (1dae1e7, beta) + güvenli geri dönüş düzeltmeleri (Ek P2)
- Latest = v202611171741; uygulama içinden görülür. Dosyalar indirilip doğrulandı, Defender temiz. Pilot pre-release duruyor.
- Geri dönüş: s3 varken uyumsuz önceki sürüme elle dönüş engeli; ilk açılış penceresinde okuyucu yazmaz; kurulu kod s3'ü tanımıyor ve s3 var ise uygulama içi güncelleme reddedilir (tam kurulum). Başlatıcı değişmedi. Ayarlar'da gerçekleşme kuralı seçimi.
- Gerçek kurulum testleri: kararlı → uygulama içi OK; A (s3 var) reddedildi + kurulum programı OK; B güvenli otomatik dönüş; gerçek adres OK (ilk denemede hazırlık sessiz kaldı, ikinci başarılı; neden açık). 637 test OK.

## 2026-11-17 — O4 ve O5 geliştirme/test (canlı değil) + paralel takip (Ek O-4, O-5, O-1b)
- O4 o4-fiyat-izi 23e9539: db.connect yedekli tek göç (fiyat_izi_v1), prices.update kaynak/ayar/sürüm kaydı + değişen satırın eskisi; bilinmeyen geçmiş NULL. Kopya: eski tablolar aynı, 157.069 satır bilinmiyor, taklit indirmede 1 eski değer saklandı, eski kod uyumlu. 652 test OK.
- O5 o5-izleme 084a5d9: izleme bekçiye (akşam, günde bir, hata yalıtımlı) ve panele (salt-okur); K1 kapalı (0 olay); P1/P2 notları; olculen_kayitlar ortak seçim; O2 grupları ayrı. Kopya: hepsi yetersiz veri, 0 olay. 672 test OK.
- Takip: FAZ 1 sonuç yok, s3 tahmini 0 (akşam analizi bekleniyor) — açık. 77 metinsiz: 76'sı bugünkü bildirimler (okuyucu eşiği 100), 1'i okunamayan sayfa. OpenAI karşılaştırması için Usage ekranı kapsamı yazıldı.
- Canlıya geçiş onayı beklenen: O4, O5. Canlı edcac9d; müşteri Latest v202611171741 (1dae1e7).
