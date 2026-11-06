# Halley — BIST Haber Radarı (prototip)

KAP bildirimlerini ve ekonomi haberlerini toplar, OpenAI ile analiz eder, hisse bazında
skorlayıp sade bir web panelinde gösterir. **Emir vermez:** listeyi inceleyip emri Midas'tan
kendiniz girersiniz. Çıktı yatırım tavsiyesi değildir.

## Kullanım (Python bilgisi gerekmez)

1. Bilgisayarda Python 3.9 veya üstü kurulu olmalı.
2. **`baslat.bat`** dosyasına çift tıklayın. İlk açılışta gerekli paketler kurulur (birkaç dakika).
3. Tarayıcıda panel açılır. İlk açılışta üstte çıkan kutuya kendi OpenAI API anahtarınızı bir kez girin.
4. Sağ üstteki **🔄 Haberleri güncelle** düğmesine basın. Panel KAP ve haberleri toplar, yapay zekâya analiz ettirir.
5. **Bugünün listesi** sekmesinde olumlu ve olumsuz haber alan hisseler ayrı listelenir. Bir hisseye tıklayınca
   haberin özeti, nedeni ve kaynağı açılır. ✅ Teyitli: iki ayrı analiz aynı sonuca vardı · ⚠️ Kontrol et: emin değil.
6. Ayarlar (kaç günlük bildirim, güncelleme başına haber sayısı, liste dönemi) **⚙️ Ayarlar** bölümündedir.
   Durum bilgisi ve geçmiş veri pilotu **🔧 Gelişmiş** sekmesindedir.

Canlı akış KAP'ın yanında **BloombergHT ve Uzmanpara** haberlerini de toplar; Dünya, Habertürk,
NTV ve TRT kaynakları korunur. Kaynakların okunma durumu **Gelişmiş** sekmesinde görünür.
RSS haberleri ön elemeden geçer; geçenlerin tam metni alınmaya çalışılır ve aynı modelle analiz edilir.
Maliyet için panelde güncelleme başına **1, 3, 5 veya 10 haber** seçilebilir (varsayılan 10; KAP dahil).
Kalan haberler bekler. Bu adet sınırıdır; **1 USD parasal tavan yalnızca geçmiş veri pilotundadır**.
RSS akışları güncel haberler içindir; doğrulanmış geçmiş arşiv yerine kullanılıp eski backtest'e eklenmez.

> KAP hızlı isteklere sınır koyduğu için bildirim metinleri yaklaşık saniyede bir okunur.
> Günlük ~150-350 bildirimde ilk güncelleme 3-6 dakika sürebilir; sonrakiler sadece yenileri okur.

## Nasıl çalışır?

```
KAP + RSS → toplama (tekrar ayıklama, hisse eşleme, işlem günü)
          → rutin KAP konuları kuralla atlanır; finansal raporlardan tablo özeti, PDF eklerden metin
          → RSS: Aşama 1 "önemli mi?" (gpt-5-mini, az düşünme) → geçenlerin tam metni okunur
          → Aşama 2: hisse bazında analiz (gpt-5-mini, yüksek düşünme, piyasa değeri bağlamıyla)
          → büyük kararlar için ikinci bağımsız analiz (teyit / çelişki işareti)
          → skor = yön × etki × güven × zamanla sönme (aynı olay tek sayılır) → sinyal tablosu
```

- LLM karar vermez; haberi sabit şemalı veriye çevirir. Skoru kurallar hesaplar (`bist_haber/report.py`).
- Etkinin yarılanma süresi: kısa 1 gün, orta 5 gün, uzun 20 gün (swing vadeye göre).
- Eşikler (±1.5, ±4) başlangıç tahminidir; Faz 3-4'te geçmiş veriyle kalibre edilecek.

## Ayarlar

| Ne | Nerede |
|---|---|
| OpenAI anahtarı, model adları | `.env` (örnek: `.env.example`) |
| Takip edilecek hisseler (boşsa tümü) | `data/universe.txt` |
| Haberlerde şirket adı → kod eşlemesi | `data/aliases.csv` |
| RSS kaynakları, atlanacak KAP konuları | `bist_haber/config.py` |

## Komut satırı (isteğe bağlı)

```
python -m bist_haber init | collect | analyze --dry-run | analyze | prices | report | status | run
```

## Bilinen sınırlar

- KAP'ın belgelenmiş resmi API'si yok; sitenin kendi uç noktaları kullanılıyor, site değişirse bozulabilir.
- Taranmış (resim) PDF'ler ve Excel ekleri okunmuyor.
- Fiyatlar ve piyasa değeri yfinance'tan, gecikmeli. Resmi tatiller işlem günü hesabında yok.
- Ayrıntılı kararlar, riskler ve sonraki fazlar için: `NOTLAR.md`.

## Geçmiş veri pilotu (Faz 4 başlangıcı)

Panelde **🔧 Gelişmiş** sekmesindeki **Geçmiş veri pilotu** bölümünü açın:
1. En az 21 gün önce biten, en fazla 32 günlük bir tarih aralığı seçip **Belgeleri hazırla** düğmesine basın.
2. **Fiyatları al** düğmesine basın. Bu iki adım OpenAI harcaması yapmaz.
3. **En fazla 10 bildirimi analiz et** düğmesi yalnızca belgesi ve 10 işlem günlük fiyatı hazır olayları işler.
   Model gpt-5-mini; yüksek düşünme ve gerektiğinde ayrı ikinci görüş korunur.
   Bir basışta en fazla 10 bildirim işlenir; sonraki grup otomatik başlamaz. İlk küçük tur
   yöntem/analiz kontrolü içindir; bu kadar az olayla başarı oranı veya eşik seçilmez.

- 100 veya 200 bildirim, fiyat sonuçlarına bakılmadan tekrar üretilebilir biçimde örneklenir.
- Toplam pilot API bütçesi **1 USD**; kullanım ve belirsiz çağrı rezervleri diskte tutulur.
  Eski 5 USD sınırı düşürülmüştür; önceki harcama/rezervler silinmez. Önceden 1 USD veya üstü
  kullanılmışsa yeni ücretli çağrı açılmaz.
  Yeniden açmak veya tarih değiştirmek bütçeyi sıfırlamaz. Bu sınır günlük güncelleme akışına uygulanmaz.
- İstek içeriği/talimat/model/görüş aynıysa saklanan sonuç kullanılır. İlk ve ikinci görüşün önbelleği ayrıdır.
  Bağlantı kopması/yarım yanıt otomatik ücretli tekrar başlatmaz; gerekiyorsa kayıt geliştirici tarafından incelenir.
- Metin/ek kesilmesi, okunamayan PDF ve PDF dışındaki ekler pilotta işaretlenir; eksik belge analiz edilmez.
- Giriş, yayın gününden **sonraki** endeks işlem gününün açılışıdır; 1/3/5/10 gün sonraki kapanışlar ölçülür.
  Giriş günü birinci işlem günüdür. Eksik fiyat başka tarihe kaydırılmaz.
- Bugünkü piyasa değeri veya şirket listesi geçmişe taşınmaz; kodlar eski bildirimin ihraççı kodlarından alınır.
  Dolaylı hisse etkileri bu ilk pilotun kapsamı dışındadır.
- Bu bir **olay pilotudur**; tam günlük birleşik skor/portföy backtest'i değildir. Eşikleri değiştirmez.
  Tarihsel kotasyon evreni, resmi tatil takvimi ve fiyat düzeltmeleri henüz bağımsız doğrulanmadı.
  Fiyatı/ekleri eksik olayların dışarıda kalması ve örtüşen haberler sonuçları etkileyebilir.
- Veriler `data/backtest/` altında, günlük veritabanından ayrı tutulur ve GitHub'a gönderilmez.
- **Bütün pilot tablolarını ve yöntemi indir (ZIP)** düğmesi olay sonuçları, pozitif olay özeti,
  belge eksikleri CSV'leri ve yöntem TXT'sini birlikte indirir. Aynı dosyalar ayrı düğmelerle de indirilebilir.
  İndirme mevcut sonuçları kullanır; yeniden analiz veya API harcaması başlatmaz.
  Sonuç tablosundaki `eksik: 0` yalnızca fiyat sonuçlarını anlatır; eksik belgeler ayrı listededir.

Tam kalibrasyon için sonraki adım: doğrulanmış tarihsel evren/takvim, eksiksiz haber penceresi,
tarihli şirket büyüklüğü bağlamı, zaman sıralı ayrı doğrulama dönemi ve ileriye dönük izleme.

## Geliştirmeye devam edecek kişi / yapay zekâ için

**Güncel devir:** [DEVIR.md](DEVIR.md). README, NOTLAR ve devir dosyasını kod değiştirmeden birlikte okuyun.

**Kullanıcı:** Türkçe konuşuyor, Python bilmiyor; arayüzü çıktıya bakarak yönlendiriyor. Vade: birkaç günlük/haftalık
swing. Emirleri Midas'tan elle giriyor (otomatik emir yok, Faz 6 iptal). Model **gpt-5-mini** olmalı (kullanıcının açık isteği).

**Dosya haritası**

| Dosya | Görev |
|---|---|
| `app.py` | Streamlit paneli (`baslat.bat` bunu açar) |
| `bist_haber/pipeline.py` | Paneldeki "Verileri güncelle" akışı: topla → analiz → fiyat |
| `bist_haber/kap.py` | KAP liste API'si (`/tr/api/disclosure/members/byCriteria`), bildirim sayfası (Next.js akışı ayrıştırma), PDF ekler, 429 yönetimi |
| `bist_haber/financials.py` | Finansal rapor özeti: `/tr/api/notification/export/excel/<id>` (HTML tablo); değerler hücrelerin `title` özniteliğinden |
| `bist_haber/rss.py` | RSS toplama, eski haber/tekrar eleme |
| `bist_haber/universe.py` | KAP şirket listesi (3 harfli borçlanma kodları atılır), takma ad eşleme |
| `bist_haber/analyzer.py` | Ön eleme, tam metin, piyasa değeri bağlamı, analiz, ikinci görüş, doğrulama; paralel çalışır |
| `bist_haber/report.py` | Skorlama (sönme, çift sayım önleme), eşikler |
| `bist_haber/prices.py` | yfinance fiyat + piyasa değeri (günlük önbellek) |
| `bist_haber/config.py` | Tüm ayarlar ve KAP atlama listesi |
| `bist_haber/backtest.py` | Belge denetimi, 1 USD bütçe/istek önbelleği, 10 bildirimlik turlar ve olay ölçümü |
| `bist_haber/backtest_ui.py` | Panelin geçmiş veri pilotu sekmesi |

**Bilinmesi gerekenler**
- Python 3.9 uyumlu kalmalı (kullanıcının makinesi): `X | Y` tip sözdizimi, `match` vb. kullanmayın.
- Windows'ta proje yolu uzunsa venv kurulumu "long path" hatası verir; `baslat.bat` venv'i `%USERPROFILE%\.venvs\bist-haber` altına kurar.
- KAP ~1 sn/istek üzerinde HTTP 429 veriyor; `KAP_REQUEST_DELAY` düşürülmemeli.
- Streamlit sunucusu `bist_haber` modüllerindeki değişiklikleri her zaman yeniden yüklemiyor; kod değişince paneli yeniden başlatın.
- Ücretsiz regresyon testleri: `python -m unittest discover -s tests -v` (Python 3.9).
  Anahtar/ağ uygunsa ek canlı kontrol: `collect` → `analyze --dry-run` → `analyze --limit 3` → `report`.
  Gerçek API kontrolünün ücretli olduğu unutulmamalı; test sonucu ile gerçek piyasa başarısı ayrı şeylerdir.
- `.env` (API anahtarı) ve `data/*.db` git'e eklenmez.
