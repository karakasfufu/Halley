# Halley — Claude / sonraki geliştirici için devir

Tarih: 6 Kasım 2026, Türkiye saati.
Depo: https://github.com/karakasfufu/Halley (gizli), ana dal: `main`.
Bu devirden önceki son kod commit'i: `c7bd4d576b0867a589b9e3de645ab4532e9f0066`.

## Önce oku

Kod değiştirmeden **README.md'nin tamamını**, özellikle en alttaki devam edecek kişi bölümünü,
**NOTLAR.md'nin tamamını** ve bu dosyayı oku. Tarihli eski gözlemlerle güncel durumu ayır.
NOTLAR'daki ilk hazırlığa ait "API anahtarı yok / pilot çalışmadı" gözlemi artık güncel değildir:
kullanıcı anahtarını bağladı ve 10 bildirimlik pilot çıktısı paylaştı.

## Kullanıcı ve değiştirilmeyecek sınırlar

- Kullanıcı Türkçe konuşuyor ve Python bilmiyor. Sade Türkçe anlat; işlemler panelden yapılmalı.
- Birkaç günlük / haftalık swing için BIST haberlerini izliyor. Uygulama emir vermez;
  kullanıcı emirleri Midas'tan elle girer. Broker/otomatik emir entegrasyonu istenmiyor.
- Uygulamanın analiz API modeli **OpenAI `gpt-5-mini`** olacak. Geliştirici asistanın Claude olması,
  uygulamayı Anthropic'e veya başka modele geçirme izni değildir.
- Doğruluk öncelikli, harcama da **olabildiğince düşük** olmalı. Maliyet/süreyi belirgin artıracak
  değişiklikten ve geniş ücretli çalışmadan önce kullanıcıya somut plan + tahmin sun, onayını bekle.
- Kaliteyi sessizce düşürme; gpt-5-mini high düşünme ve gereken ikinci görüş korunuyor.
- Python **3.9** uyumu zorunlu. `X | Y`, `match` veya 3.10+ zorunluluğu getirme.
- `.env`, API anahtarı, `data/*.db`, `data/backtest/` ve gerçek kullanıcı raporlarını GitHub'a yükleme.
  Anahtarı mesaja/loga yazdırma veya sohbetten isteme; paneldeki parola alanı kullanılır.
- KAP beklemesi **1.5 saniye** (`config.KAP_REQUEST_DELAY`). Düşürme; 429'da dur/kayıtları koru.
- Değişiklikleri gerçekten test et; çalışmayan ve sınanamayan kısmı açıkça anlat.
  İş bitince NOTLAR.md'yi güncelle ve commit + push ile GitHub'a kaydet.

## Şu an ne çalışıyor?

### Günlük canlı akış

`app.py` / `baslat.bat` → `pipeline.update_all` → KAP + RSS toplama → analiz → fiyat → sinyaller.

- KAP özel durum açıklamaları, PDF metinleri ve HTML finansal tablo dışa aktarımı okunuyor.
- RSS kaynakları: **BloombergHT, Uzmanpara**, Dünya, Habertürk, NTV, TRT.
- RSS ön elemesi gpt-5-mini minimal; geçen haberin tam metni alınmaya çalışılıyor.
  Derin analiz high; etkisi en az 3 veya güveni düşük yönlü kararlar ayrı ikinci çağrıyla kontrol ediliyor.
- Sonuç şeması: olay türü, yön, etki 1–5, güven 0–1, kalıcılık ve gerekçe.
  Skoru model değil `report.py` hesaplar. İkinci görüş aynı modeldendir; sistematik model hatasını çözmez.
- Panelde günlük güncelleme için **1 / 3 / 5 / 10 haber** seçilebilir; varsayılan 10.
  KAP ve RSS birlikte bu sayıya dahildir. Kalan haberler bekler; tüm arşiv bir kerede analiz edilmez.
- Günlük akışın bu koruması **adet sınırıdır, dolar tavanı değildir**. CLI `analyze` aynı sınıra
  otomatik bağlanmadı. Kullanıcıya günlük sistemin 1 USD ile sınırlı olduğunu söyleme.
- Kaynak bazında okunma durumu ve kayıt/tarih sorunu sayıları Durum sekmesindedir.

### Faz 4: yalnızca ilk olay pilotu var

**Tam backtest, eşik kalibrasyonu ve paper trading bitmedi.**

- `backtest.py`, `backtest_ui.py`; ayrı `data/backtest/pilot.db`.
- En fazla 32 günlük, bitişi en az 21 gün geçmiş tarih aralığı. 100/200 KAP bildirimi,
  `sha256(halley-pilot-v1:bildirim_id)` sırasıyla fiyatlara bakmadan seçilir.
- Belge eksik/kesilmişse veya 10 işlem günlük fiyatı yoksa ücretli analiz yapılmaz.
- İhraççı kodları geçmiş KAP bildiriminden alınır. Bugünkü evren/piyasa değeri geçmişe taşınmaz;
  bu, tarihsel kotasyon evreninin doğrulandığı anlamına gelmez. Tarihli şirket büyüklüğü eksiktir.
- Her analiz turu **en fazla 10 bildirim**; sonraki grup otomatik başlamaz.
- **Toplam pilot tavanı 1 USD**, tüm pilot veritabanı içindir; önceki 5 USD tavanı indirildi.
  Tarih/panel değişimiyle sıfırlanmaz. Eski harcama/rezervleri silerek limit açma.
- `pilot_calls`: çağrıdan önce ihtiyatlı rezervasyon, sonra gerçek token kullanımıyla hesap.
  Fiyat sabitleri 2026-11-06'da girdi 0.25 USD / 1M, çıktı 2 USD / 1M olarak doğrulanmıştı;
  gelecekte ücretli çalışmadan önce güncelliğini resmi kaynaktan doğrula.
- `PilotLLM`: SDK retry kapalı; 16000 maksimum çıktı tokenı. Yarım/ret/bağlantısı kesilmiş yanıt
  başarı veya nötr sonuç sayılmaz. Belirsiz çağrı rezervi tutulur, otomatik tekrar gönderilmez.
  Böyle bir durumda kullanım kaydını incele; körlemesine "retry / cache temizle" yapma.
- İstek önbelleği belge/mesaj, prompt, model, şema, düşünme, çıktı sınırı ve görüşü kapsar.
  İlk/ikinci görüşün anahtarları ayrıdır. İlk önbelleği ikinci teyit olarak kullanma.
- Giriş: yayın gününden sonraki ilk endeks işlem gününün **açılışı**.
  Çıkış: giriş dahil 1, 3, 5, 10. işlem gününün kapanışı. Eksik hisse fiyatı sonraki güne kaydırılmaz.
  Negatif sinyalde açığa satış kazancı hesaplanmaz. Maliyet senaryosu, endekse göre fark ve düşük fiyat gösterilir.
- Endeks (`XU100.IS`) fiyat tarihleri geçici işlem takvimidir. Resmi tatil/yarım gün takvimi ve
  yfinance fiyat düzeltmeleri bağımsız doğrulanmış değildir.
- Güncel RSS listesi geçmiş haber arşivi değildir; BloombergHT/Uzmanpara haberlerini arşiv
  ve yayın anındaki metin doğrulanmadan geçmiş KAP pilotuna ekleme.

## Son kullanıcı durumu ve raporlar

- Kullanıcı API anahtarını bağladığını bildirdi ve `halley_pilot.csv` paylaştı.
- Paylaşılan dosya: **10 farklı bildirim × 4 vade = 40 satır**, fiyat sonucu eksiği 0.
  Bu, 40 bağımsız işlem veya tüm belgelerin eksiksiz okunması anlamına gelmez.
- Paylaşılan sonuçlarda 3 pozitif, 2 negatif, 5 nötr bildirim vardı; bu küçük örnekle başarı
  kanıtlanmadı, eşikler değiştirilmedi. Getiri değerlendirmesi tamamlanmış sayılmaz.
- Kullanıcı ayrıca **22 belge eksiği** paylaştı: uzun/çok sayfalı PDF, ek sayısı sınırı,
  okunmayan/resim sayfa, PDF dışı ek ve kısa metin sorunları. Bu kayıtlar pilot analizine alınmaz.
  Eksik belgelerin dışlanması seçilim yanlılığı yaratır; sonuçları tüm haberlere genelleme.
- Eski indirme düğmesi yalnızca ana CSV'yi indiriyordu. Şimdi ayrı indirmeler ve tek ZIP var:
  `halley_pilot.csv`, `halley_pozitif_ozet.csv`, `halley_belge_eksikleri.csv`, `halley_yontem.txt`.
  `pilot_export.py` ekran ve dosya özetini aynı veriden üretir; UTF-8 BOM ve vade sütunu korunur.
  İndirme yeni model çağrısı yapmaz. CSV'deki `eksik` yalnızca fiyat sonucudur; belge eksikleri ayrı dosyadır.
- Gerçek kullanıcı veritabanı, token/harcama defteri ve raporlar **depoda yok**; klonlayınca otomatik gelmez.
  Güncel ücret/ilerleme için kullanıcının yerel defterini oku; eski sayıları güncel sanma.
- Bu oturumun yerel çalışma kopyası:
  `C:\Users\fkara\Documents\ChatGPT\Bulutların Üstü\work\Halley`.
  GitHub'a bağlı kaynak kopyası kullanıldı; yerelde `.git` bulunduğunu varsayma.
- Kullanıcının paylaştığı CSV: `D:\Downloads\halley_pilot.csv`.
  Hazırlanan dört dosya + ZIP:
  `C:\Users\fkara\Documents\ChatGPT\Bulutların Üstü\outputs\halley_pilot_raporu`.
  Bu yollar yalnızca aynı bilgisayarda geçerli; başka ortamda kullanıcı panelden raporu dışa aktarabilir.

## Son düzeltmelerin teknik tuzakları

1. **Eski KAP metni kaybı:** Önceki kod 6 saatten eski haberi metni çekmeden başlıkla analize
   bırakıyordu. Kaldırıldı. Eski ama henüz analiz edilmemiş boş kayıtlar yeniden metin çekimine alınır.
   Daha önce metinsiz analiz edilmiş kayıtlar silinmez/otomatik ücretlendirilmez; skordan çıkarılır ve panel uyarır.
2. **KAP liste sınırı:** Aylık sorgu 2000 kayıtla kesilebiliyor. Sınıra ulaşan aralık ikiye bölünür;
   tek gün hâlâ sınıra ulaşırsa eksiksizlik varsayılmadan durur. Eylül 2026 sorgusu bu sayede
   2000 yerine **7606** kayıt verdi. İlk 100 örnek için hazırlık 429 nedeniyle kısmen kesilmişti;
   kullanıcı daha sonra devam etti. O ilk hazırlık sayaçları güncel ilerleme değildir.
3. **Uzmanpara saat hatası:** RSS yerel saati GMT diye etiketleyebiliyor. Yeni haberlerin yayın
   saati sayfanın açık saat dilimli `datePublished` meta alanından doğrulanır (`rss.article_published`).
   Sabit 3 saat çıkarma, dateModified kullanma, tarihsiz habere bugün deme. Çelişen/naif tarih reddedilir.
4. **PDF sınırları:** Günlük akış ile pilotun belge kontrolü aynı katılıkta değildir.
   Pilot `fetch_document` ek/sayfa/metin kesilmesini işaretler ve harcamayı durdurur.
   Sınırı körlemesine yükseltmek token/süreyi artırır; taranmış PDF veya Excel'i çözmez.
5. **Skorlama varsayımları:** Eşikler ±1.5 / ±4, yarılanma 1 / 5 / 20 gün hâlâ tahmindir.
   Varsayılan 7 günlük haber penceresi ile 20 günlük uzun etkiyi beraber incele.
   Aynı hisse+olay türü+2 gün kümelemesi gerçek anlamda olay kimliği değildir; ayrı olayları birleştirebilir.
6. **Tam metin:** Haber tam metni alınmaya çalışılır; site erişimi/ayrıştırma başarısı garanti değildir.
   Sadece RSS özetiyle kalınan durumların görünürlüğü ve analiz güveni ayrıca denetlenmeli.
7. **Kuyruk:** Günlük düşük adet sınırı eski haber birikimine yol açabilir. Kaynaklar için ayrı
   adil sıra/priorite uygulanmadı. "Tüm haberler anında analiz ediliyor" deme.

## Dosya haritası

| Dosya | İlgili görev |
|---|---|
| `app.py`, `baslat.bat` | Panel ve başlatma |
| `bist_haber/config.py`, `pipeline.py` | Ayarlar, günlük güncelleme/adet sınırı |
| `bist_haber/kap.py`, `financials.py` | KAP liste/metin/ekler ve finansal tablo özeti |
| `bist_haber/rss.py`, `universe.py` | Haber kaynakları, tarih doğrulama, hisse eşleme |
| `bist_haber/analyzer.py`, `report.py` | Model analizi, ikinci görüş, sabit kurallı skor |
| `bist_haber/prices.py`, `db.py` | Fiyat/şirket büyüklüğü ve şema |
| `bist_haber/backtest.py`, `backtest_ui.py` | Bütçe/önbellek, olay ölçümü, pilot paneli |
| `bist_haber/pilot_export.py` | Pozitif özet, belge eksikleri, CSV/TXT/ZIP |
| `tests/test_accuracy.py` | Günlük/pilot akış, maliyet, tarihler, panel regresyonları |
| `tests/test_pilot_export.py`, `tests/test_news_sources.py` | İndirmeler, RSS, tarih ve adet kontrolü |

## Gerçekte ne test edildi?

Son kod commit'inde Python **3.9.13** ile **50 ücretsiz test** ve `compileall` geçti.
Test komutu: `python -m unittest discover -s tests -v`.

- Bütçe/rezerv, 10'da durma/devam etme, cache ve ayrı ikinci görüş, eksik belge/fiyat,
  giriş/çıkış tarihleri, KAP 2000/429, günlük akış, RSS tarihi/tekrarları, ZIP/CSV ve Streamlit AppTest.
- Gerçek KAP ve yfinance veri alımı denendi; KAP'ın geçici engeli görüldü ve veri korunarak duruldu.
- Son gerçek RSS kontrolünde BloombergHT 50, Uzmanpara 20 haber; 1 tekrar elendi,
  Uzmanpara'da 19 haberin saati sayfadan doğrulandı. Birer tam metin 2756 ve 792 karakterdi.
  Bu anlık erişim kontrolüdür; gelecekte tüm haberlerde başarı garantisi değildir.
- Kullanıcının CSV'sinden gerçek dört dosyalı ZIP hazırlandı ve arşiv bütünlüğü kontrol edildi.
- Bu asistan yeni ücretli model çağrısı yapmadı. Model testleri sahte istemci kullanır;
  kullanıcının panelden aldığı gerçek çıktıyı, model doğruluğunun bağımsız testi gibi sunma.
- Yeni indirme düğmelerinin tarayıcıdan dosyaya kaydetme davranışı ayrıca elle gözlemlenmedi;
  AppTest'te düğmeler ve gerçek ZIP/CSV üretimi doğrulandı.

Windows'ta `py -3.9` sandbox içinde açılamayabilir. Bu bilgisayarda test edilen ortam:
`%USERPROFILE%\.venvs\bist-haber\Scripts\python.exe`.
`baslat.bat` de aynı venv'i kullanır. Panel modülleri her değişiklikte yeniden yüklenmeyebilir;
kod değişince sunucunun açık olduğu pencereyi kapatıp `baslat.bat` ile yeniden başlat.

## Önerilen devam sırası

1. Önce mevcut kodu/devir belgelerini incele ve kısa durum özeti ver; ücretli çağrı başlatma.
2. Kullanıcının yeni indirmeleri ve BloombergHT/Uzmanpara kaynak durumunu panelde görmesini doğrula.
   Gerekirse mevcut CSV/ZIP ve yerel defteri **yeniden analiz etmeden** incele.
3. 22 eksik belgenin nedenlerini sınıflandır. Gereksiz/rutin ek ile maddi bilgi eksikliğini ayırmak
   için bir tasarım öner; kaliteyi düşüren kör kesme veya herkese OCR/LLM çalıştırma yapma.
4. Geniş ücretli çalışmadan önce tarihsel evren, resmi takvim, fiyat düzeltmeleri, tarihli şirket
   büyüklüğü ve tam haber penceresi sorunlarını çözmek için düşük maliyetli plan çıkar.
5. Gerçek kalibrasyon: küçük ve önceden belirlenmiş eşik ailesi; zaman sıralı geliştirme/doğrulama/final
   dönemleri; vade sonuçlarının bölüm sınırına taşmasını engelleme; örtüşen olay ve seçilim yanlılığı kontrolü.
   Son değerlendirme dönemine bakıp tekrar tekrar ayar yapma. İleriye dönük takip ile doğrula.
6. OpenAI Batch henüz uygulanmadı. Geniş işte aynı model/kaliteyle masrafı azaltma seçeneği olarak
   önce güncel resmi doküman ve maliyeti incele; kullanıcının onayı olmadan toplu ücretli iş başlatma.

Bu liste öneridir; kullanıcının yeni isteği önceliklidir. Küçük pilotu "başarılı strateji" diye sunma,
eşikleri henüz kalibre edilmiş sayma ve eksik belgeleri nötr/başarısız sinyal gibi sayma.

## Yakın commit'ler

- `6589f1f142a3c2252e5a2db28518e5be7725e6e4`: KAP veri kaybı/liste sınırı, bütçeli olay pilotu.
- `9d2aa53aae9daac4063c720e2298edea069f4c32`: 1 USD tavan, 10 bildirimlik pilot turları.
- `c7bd4d576b0867a589b9e3de645ab4532e9f0066`: tüm rapor indirmeleri, Uzmanpara, tarih doğrulama,
  günlük adet sınırı, kaynak durumu; 50 test.

Devir belgesinin eklenmesi yalnızca dokümantasyon değişikliğidir; bu işlem için ücretli çalışma
başlatılmadı ve uygulama kodu değiştirilmedi. En güncel kaynak her zaman depodaki kod ve yeni commit'lerdir.
