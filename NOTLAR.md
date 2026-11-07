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
