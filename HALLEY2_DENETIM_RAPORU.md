# Halley 2.0 — Denetim, Eksik Analizi ve Yol Haritası (FAZ 0)

Tarih: 16.11.2026 · Kod sürümü: 4689b6e (gizli depo) · Hazırlayan: Claude (Opus 5.5)

Bu rapor "HALLEY 2.0 – Master Technical Audit" isteğinin 20. maddesine uygun hazırlandı:

- Kod değiştirilmedi, dosya silinmedi, bağımlılık eklenmedi, model eğitilmedi.
- API çağrısı yapılmadı, veritabanına yazılmadı.
- Yalnız kod, raporlar ve veritabanı **okundu**. Canlı veritabanı salt-okunur açıldı.

Uygulama aşaması onay bekliyor.

İşaretler:

- ✅ var ve çalışıyor
- 🟡 kısmen var
- 🔲 yok, yapılabilir
- ⛔ denendi, işe yaramadı / önerilmez
- 📏 ölçülmüş sonuç
- 💭 teorik beklenti (ölçülmedi)

---

## 0. Yönetici özeti

1. **Halley'in iskeleti istenen platformun büyük kısmını zaten içeriyor.** Merkezi karar akışı, zorunlu risk
   filtreleri, değiştirilemez karar geçmişi, açıklama metinleri, sanal portföy, strateji türüne göre sonuç tablosu,
   piyasa rejimi kaydı, ileriye dönük sınama ve uygulama içi güncelleme mevcut. **Yeni bir karar motoru yazmak
   gereksiz**; mevcut akışın birkaç eksiği tamamlanmalı.
2. **En büyük eksik kod değil, kanıt.** Canlı veride neredeyse hiç sonuçlanmış öneri yok:
   - Hazır fırsat: 0 kapanmış.
   - Sanal işlem: 30 kayıttan yalnız 3'ü girişle sonuçlandı, üçü de SL.
   - Takip senaryosu: 0 sonuçlanmış.

   Bütün performans rakamları **5 yıllık geçmiş veri sınamasından** geliyor; canlı doğrulama henüz yok.
3. **Ölçülmüş sonuçlar tutarlı:**
   - TP1 modeli işe yarıyor ama sınırlı: isabet 0,605 / 0,612. Son 12 ayda en yüksek %20'lik dilim +0,17 R,
     diğerleri −0,08 R.
   - Haber, Kronos, Chronos ve ağaç modelleri katkı vermedi.
   - Genel puan TP1'i öngörmüyor (isabet 0,49).

   Bu yüzden **puan ağırlıklarını "iyileştirmek" aşırı uyuma yol açar**. Asıl değer, sınamayı ve kayıtları
   güvenilir kılmakta.
4. **Kritik bilinen sınır:** Araştırma verisi bugünkü 632 hisseyle kuruldu, borsadan çıkan hisseler yok. Geçmiş
   sınama sonuçları büyük olasılıkla **biraz iyimser**.
5. **Önerilen sıra:**
   - FAZ 1: backtest metrikleri, hayatta kalma yanlılığı, veri kaydı.
   - FAZ 3: strateji ve rejim, yalnız araştırmada.
   - FAZ 4: 5/10 günlük hedefler, yalnız araştırmada.
   - FAZ 2: karar kaydı ve sürümleme.
   - FAZ 5 ve FAZ 6: ölçüm ve tasarım notu.

   Hepsi işlemciyle çalışır ve **0 $** API maliyetiyle yapılır.

---

## 1. İstekteki "değiştirilemez kurallar" ve "deney sonuçları": doğrulama

| İddia | Doğrulama | Kanıt |
|---|---|---|
| Windows 10, Python 3.9, CPU, GPU yok | ✅ Doğru | Uygulama ortamı Python 3.9.13. Araştırma ortamında torch 2.8.0+cpu. Kurulum paketi gömülü Python 3.9 içeriyor. |
| API modeli gpt-5-mini; Ollama yok | ✅ Doğru | `analyzer.py`, `backtest.py` (MODEL = "gpt-5-mini"). Kodda Ollama yok. |
| Haber eleme ve bütçe kontrolü var | ✅ Doğru | `prefilter.apply` (rutin haberler), `dedupe.filter_duplicates` (tekrar), `analyzer.within_budget` / `news_budget()` (aylık bütçe), basış başına en fazla 10 haber (`pipeline.update_all`). |
| Kronos üretimde yok; Kronos ve Chronos katkı vermedi | ✅ Doğru, 📏 | `ASAMA7_PLAN.md` "Sonuç". Kronos-mini tek başına isabet 0,52. Birleşikte 0,595–0,598 (yalnız teknik model 0,601); en yüksek %20'nin R'si düştü. Chronos: 0,599 → 0,600 (anlamsız). |
| 34.579 planla eğitilmiş TP1 modeli | ✅ Doğru | `bist_haber/modeller/tp1_v1.json` (egitim.n). |
| Son 12 ay en yüksek %20: +0,17 R; diğer: −0,08 R | ✅ Doğru, 📏 | `metin_model.py` çıktısı: ust_%20 +0,166 R, diger −0,077 R, tümü −0,028 R. **Not:** tümü negatif; yani bugünkü kurallarla bütün planlara girmek son 12 ayda zarar ettirirdi. |
| Haberin TP1'e ölçülebilir katkısı yok | ✅ Doğru, 📏 | ASAMA6_RAPOR Ek 2 (KAP konuları 0,603 / 0,605) ve Ek 4 (metin okuma: hiçbir sürüm 0,605'i geçmedi). **Sınır:** yapay zekâ haber puanı geçmişte olmadığı için o sınanamadı. |
| Gradient boosting basit modeli geçemedi | ✅ Doğru, 📏 | ASAMA6_RAPOR (GBM, Platt ve yakın döneme ağırlık iyileşme getirmedi). |
| Ensemble katkı vermedi | ✅ Doğru, 📏 | ASAMA7 birleşik denemeleri (Chronos, Kronos + E2). |
| **Eklenmesi gereken:** canlı doğrulama | ⚠️ Eksik | Canlı veritabanı (16.11): hazır fırsat 2 açık / 0 kapanmış; sanal işlem 30 kayıt, 3 girişli (3 SL, ort. −%4,8), 26 henüz sonuçlanmamış; takip senaryosu 3 bekliyor; bekçi çalıştırması 2. **Canlı sonuçla doğrulanmış tek bir oran yok.** |

---

## 2. Bölüm bölüm eksik analizi

Her başlıkta beş alan var: **mevcut durum**, **dosya / fonksiyon**, **kanıt**, **eksik** ve **artı / eksi**.

### 2.1 Merkezi karar motoru (istek md. 4)

**Mevcut durum: 🟡 Var, ama tek bir kayıtta toplanmıyor.** Karar zinciri birkaç modüle dağılmış durumda ve
zorunlu filtreler **puandan bağımsız** çalışıyor. İstenen davranış zaten bu.

| İstenen çıktı | Halley'deki karşılığı | Dosya / fonksiyon |
|---|---|---|
| Hazır fırsat | Koşulu sağlanmış, ertesi açılışta uygulanabilir plan (en fazla 5) | `ready.build` / `ready.select`, `ready.build_tech` / `select_tech` |
| Bekleyen fırsat | Koşul bekleyen giriş senaryoları | `entries.scenarios`, `tradeplan.plan` |
| Takip edilmeli | Takip listesi ve bekçi | `tracker`, `takip_ui` |
| Uygun değil | Elenen ve nedeni ("haber skoru 1,20", "teknik 4/10", "risk yüksek" …) | `ready.select` → `elenen`, `signals.decide` → `neden_kodu` |
| Geçersiz fırsat | Sabah iptali, açılış azami girişin üstünde → "giriş olmadı" | `ready.morning`, `ready.opening_check` |

**Zorunlu filtreler (puan ne olursa olsun hazır fırsatı engeller):**

- Veri kritik hata (eski fiyat, sıçrama, uzun boşluk) → senaryo üretilmez:
  `tradeplan.plan` içinde `t["veri_kritik"]`.
- Likidite: günlük işlem hacmi 2 mn TL'nin altındaysa senaryo yok (`tradeplan.LIQ_MIN_TL`). Hacmi 21 gündür sıfır
  olan hisseler de bu filtreye takılıyor; 15.11 düzeltmesi.
- Risk/getiri en az 1:2 (`MIN_RR`). Azami girişten alınsa bile en az 1:1,5 (`MIN_RR_AT_MAX`).
- Zarar mesafesi en fazla %15 (`MAX_STOP_PCT`).
- Risk seviyesi "yüksek" ise elenir.
- Teknik skor en az 5 (yalnız teknik fırsatta en az 7).
- Açılış azami girişin üstündeyse alım yok.

**Değerlendirilen girdiler:**

| Girdi | Durum |
|---|---|
| Teknik, hacim, likidite, risk/getiri | ✅ |
| Haber etkisi, haber/fiyat ilişkisi (fiyatlanmış mı, sızıntı) | ✅ `tradeplan.risk_factors` |
| Ekonomik takvim | ✅ `macro_risk` → risk notu |
| Sektör | 🟡 Yalnız bilgi (`sectors.compare`) |
| Portföy riski | 🟡 Yalnız sektör yoğunlaşma uyarısı (`sectors.CONC_WARN`) |
| Piyasa rejimi | 🟡 Yalnız bilgi |

**Kanıt:**

- Testler: `tests/test_stage4.py`, `tests/test_ready.py`, `tests/test_panel_flows.py` (toplam 522 test geçiyor).
- Bekçi kararları **değiştirilemez** tabloda: `signal_log`. Veritabanı tetikleyicileri güncellemeyi ve silmeyi
  engelliyor. Canlıda 1.522 karar satırı var, 27'si "önerildi".

**Eksik:**

- (a) Hazır fırsat kararının **bütün girdileri tek bir kayıtta** saklanmıyor. Neden metni ve risk listesi var;
  ama rejim, sektör, veri kalitesi ve parametre sürümü aynı kayıtta değil.
- (b) "Uygun değil" nedenleri hazır fırsat için yalnız o anki ekranda; kalıcı olarak saklanmıyor. Bekçinin
  `signal_log` kaydı ise kalıcı.
- (c) Portföy riski (toplam açık risk) zorunlu filtre değil.

**Artı / eksi:**

- **Artı:** Yeni motor yazmamak; mevcut, testli akışı korumak.
- **Eksi (yeni motor yazılırsa):** Aynı kuralları ikinci kez kodlamak, iki sistemin ayrışma riski, testlerin
  yeniden yazılması.
- **Öneri:** Yalnız eksik (a), (b) ve isteğe bağlı (c) tamamlanmalı (FAZ 2).

### 2.2 Açıklanabilir analiz ve puanlama (md. 5)

**Mevcut durum: ✅ Büyük ölçüde var.**

- **Teknik skor (0–10)** beş bileşenden oluşuyor: trend, RSI, ivme (MACD/ADX), hacim/OBV, endekse göre güç.
  Bileşenler kartta "güçlü: …" olarak yazılıyor (`ready.tech_score`).
- **Genel puan (0–100)** dört parçadan oluşuyor: haber 30, teknik 30, risk/getiri 20, risk 20. Parçalar kartta
  gösteriliyor (`ready.overall_score`, `score_text`).
- **Gerekçe metni** koddan üretiliyor: haber cümlesi + teknik + "neden şimdi" + risk/getiri (`ready.build` →
  `neden`). Yapay zekâ hesap yapmıyor; haber özeti yapay zekâdan geliyor.
- **Risk faktörleri listesi** ve **elenme nedenleri** ekranda.
- **Model olasılığı + benzer geçmiş durumların gerçek oranı:** kartta isteğe bağlı.

**Ölçülmüş sonuçlar:**

- 📏 Genel puan TP1'i öngörmüyor (isabet 0,49).
- 📏 Teknik skor zayıf öngörüyor (0,53).

Bu yüzden puan ekranda yalnız bilgi olarak duruyor ve yanında bu not yazıyor.

**Eksik:**

- "Puanı düşüren faktörler" ve "eksik veriler" ayrı başlık olarak gösterilmiyor; bilgi risk listesine dağılmış.
- Hacim katkısı ve göreli güç katkısı teknik skorun içinde ayrı görünüyor; genel puanda ayrı parça değil.

**Artı / eksi:**

- **Artı (sunum eklemek):** Kullanıcı neyin eksik olduğunu daha net görür.
- **Eksi (yeni ağırlıklı puan sistemi):** Öngörü gücü olmayan bir puanı daha ayrıntılı göstermek yanıltıcı olur.
  Ağırlıkları geçmiş veriye göre ayarlamak aşırı uyumdur.
- **Öneri:** Yeni puan sistemi kurmak yerine kartta üç başlık:
  - "Engelleyen / uyaran riskler",
  - "Eksik veri",
  - "Ölçülmüş öngörü": model olasılığı, kalibrasyon notuyla.

  Sunum işi (FAZ 2).

### 2.3 Veri kalitesi ve güvenilirlik (md. 6)

**Mevcut durum: 🟡**

- **Fiyat kalite kontrolü:** eski veri (son işlem günüyle karşılaştırma), günlük sınırı aşan sıçrama, uzun
  boşluk, kurumsal olay uyarısı (`technical.analyze` → `veri_uyarilari`, `veri_kritik`). Kritik olan senaryoyu
  engelliyor.
- **Zaman:**
  - Türkiye saati (`config.TR_TZ`) her yerde kullanılıyor.
  - Haber–fiyat eşleştirmesinde geleceği görme yok. Model penceresi sinyal günü 18:00'e kadar
    (`tp1_model.news_features`).
- **Günlük / haftalık karışması:** Yalnız günlük veri kullanılıyor; haftalık veri yok, karışma riski yok.
- **Akşam analizi kaçırıldıysa** hafta sonu da yapılıyor. Fiyatlar eskiyse panel uyarıyor.

**Kanıt:**

- `tests/test_zero_volume.py`, teknik testleri.
- Canlı: 632 hisse, son fiyat günü 13.11 (Cuma). Doğru, çünkü hafta sonu.

**Eksik:**

- (a) `prices` tablosunda **kaynak, indirme zamanı, sürüm** sütunu yok. Satırın ne zaman, hangi kaynaktan
  geldiği bilinmiyor.
- (b) **Tek kaynak** var: Yahoo, ücretsiz. İkinci bir kaynakla karşılaştırma yok. Yahoo'nun kullanım şartları
  kişisel kullanıma yönelik; ticari dağıtımda ayrıca incelenmeli.
- (c) Haber tarafında yayın zamanı var, ama "doğrulama durumu" alanı yok.

**Artı / eksi:**

- **Artı (a):** Ucuz bir veritabanı göçüyle (yedekle) her satıra kaynak ve indirme zamanı eklenir; eski veri
  tespiti kesinleşir.
- **Eksi (b):** İkinci kaynak lisans ve süreklilik riski taşıyor; Borsa İstanbul'un resmî verisi ücretli.
- **Öneri:** (a) yapılmalı (FAZ 1). (b) için önce ücretsiz ve izinli bir kaynak araştırılmalı; bulunamazsa
  eksiklik açıkça yazılmalı.

### 2.4 Fırsat sürümleme ve geçmiş kararlar (md. 7)

**Mevcut durum: 🟡**

- ✅ **Bekçi karar geçmişi** (`watch_runs` + `signal_log`) her çalıştırmada yeni kayıt olarak ekleniyor.
  **Güncelleme ve silme veritabanı düzeyinde yasak.** İçeriği:
  - karar ve neden kodu,
  - haber skoru,
  - fiyat ve fiyat günü,
  - senaryo,
  - giriş, SL, TP1, TP2,
  - risk ve ayrıntı JSON'u.

  Rejim de çalıştırma özetine yazılıyor (`summary_json.rejim`).
- ✅ **Fırsat listesi değişiklik geçmişi:** eklenen/çıkan hisseler ve nedeni (`firsat_log`).
- ✅ **Model sürümü:** hazır fırsat kaydında (`hazir_firsat.model_json.surum`).
- 🟡 **Hazır fırsat kaydı** `UNIQUE(signal_day, ticker)` ve `ON CONFLICT DO UPDATE` kullanıyor (`ready._store`).
  Aynı gün yeniden analiz edilirse **eski satırın üzerine yazılıyor**.

**Eksik:**

- (a) Kayıtlarda **algoritma sürümü** (kod sürümü) ve **parametre sürümü** yok.
- (b) Hazır fırsatın gün içi yeniden analizlerinde önceki hâli kayboluyor.
- (c) Kullanıcı arayüzünde "bu fırsatın geçmiş sürümleri" görünümü yok.

**Artı / eksi:**

- **Artı:** (a) çok ucuz. Kod sürümü zaten paketin `surum.txt` dosyasında var; parametre sürümü, sabitlerin
  parmak izinden çıkar. Geçmiş kararlar sonradan "hangi kuralla verildi" diye incelenebilir.
- **Eksi:** (b) için ek tablo ve göç gerekir. Her küçük yenilemede sürüm üretmemek için "anlamlı değişiklik"
  tanımı lazım: tür, giriş, SL, TP ya da durum değiştiyse.
- **Öneri:** FAZ 2.

### 2.5 Strateji ve parametre yönetimi (md. 8)

**Mevcut durum: 🟡**

- Eşikler modüllerin başında sabit olarak duruyor:
  - `tradeplan`: MIN_RR, MAX_STOP_PCT, LIQ_MIN_TL, ATR_STOP_MULT
  - `ready`: READY_GAP_ATR, MAX_ENTRY_ATR, MIN_RR_AT_MAX, MIN_TECH, MIN_TECH_ONLY
  - `signals` / `config`: haber eşiği 1,50
- Kullanıcı ayarları (komisyon, kayma, sermaye, risk %) `data/ayarlar.json` içinde.
- ✅ **Araştırma ve canlı aynı kodu kullanıyor:** etiketleme canlı fonksiyonları çağırıyor (`ready.candidates`,
  `entries`, `technical.analyze`, `journal.evaluate`). Yani backtest ve canlı aynı parametrelerle çalışıyor. Bu,
  istenen ilkenin en önemli kısmı.

**Eksik:**

- Parametreler tek yerde değil.
- Değişiklik kaydı ve sürüm numarası yok; değişiklikler yalnız git geçmişinde ve NOTLAR'da.

**Artı / eksi:**

- **Artı:** Merkezi bir "parametre parmak izi" sürüm takibini kolaylaştırır.
- **Eksi:** Sabitleri tek dosyaya taşımak çok dosyaya dokunur ve testlerin `patch` yollarını değiştirir. Risk
  orta, değer düşük.
- **Öneri:** Taşıma yapılmasın. Yalnız sabitleri okuyup parmak izi üreten bir fonksiyon eklensin
  (`params_version()`). Değeri kayıtlara yazılsın (FAZ 2).
- **Parametre optimizasyonu önerilmez:** "Küçük pilotla eşikleri değiştirme" kuralı geçerli; ayrıca aşırı uyum
  riski var.

### 2.6 Strateji bazlı performans (md. 9)

**Mevcut durum: 🟡 Strateji etiketleri var ama istekteki örneklerin çoğu ayrı strateji değil.**

| İstekteki strateji | Halley'de karşılığı |
|---|---|
| Hacim kırılımı | ✅ Kırılım (gerçekleşmiş) |
| Trend devamı | ✅ Geri çekilme |
| Destekten dönüş | ✅ Destekten tepki |
| (istekte yok) | ✅ Mevcut fiyattan |
| Haber destekli momentum | ✅ kaynak: Haberli |
| Teknik momentum | ✅ kaynak: Yalnız teknik |
| Göreli güç liderliği | 🔲 Yok; yalnız teknik skorun bir parçası |
| Sektör liderliği | 🔲 Yok |

**Kanıt:**

- 📏 Geçmiş sınamada türe göre (son 12 ay):
  - Kırılım: TP1 %32, +0,09 R.
  - Destek: TP1 %18, −0,40 R.
- Ölçüm tabloları:
  - `ready.performance(kaynak)`: haberli / yalnız teknik ayrı.
  - `tracker.performance`: takipte türe göre.
  - `journal.metrics`: kazanma, kâr faktörü, işlem başına Sharpe.
- Panelde 30'dan az örnekte uyarı var.

**Eksik:**

- Beklenen kazanç, azami düşüş ve rejime göre kırılım hesaplanmıyor.
- Canlıda örnek yok (bkz. özet).
- "Göreli güç liderliği" ve "sektör liderliği" diye ayrı stratejiler yok.

**Artı / eksi:**

- **Artı:** Mevcut türleri 5 yıllık veride ayrı raporlamak hemen mümkün; veri ve etiketler hazır.
- **Eksi:** Yeni stratejiler (sektör liderliği vb.) eklemek yeni kural demek, sınanmamış eşik demek.
- **Öneri:** Önce mevcut türler raporlansın (FAZ 3). Destek türünün zayıflığı (−0,40 R) bir karar konusu olarak
  kullanıcıya sunulsun. **Bu bir kural değişikliğidir, onaysız yapılmaz.**

### 2.7 Piyasa rejimi (md. 10)

**Mevcut durum: 🟡 Yalnız bilgi** (`regime.py`):

- Trend: BIST100 kapanış / EMA50 / EMA200 → yükseliş, düşüş, kararsız.
- Oynaklık yüzdeliği: düşük, normal, yüksek.
- Genişlik: likit hisselerin EMA50 üstü oranı.
- Her bekçi çalıştırmasında kaydediliyor.

**Kanıt:** Rejimin performansla ilişkisi **ölçülmedi** 💭.

**Eksik:**

- 5 seviyeli sınıflama yok.
- Rejimin strateji sonuçlarına etkisi sınanmadı.

**Artı / eksi:**

- **Artı:** 5 yıllık XU100 ve etiketli 34.579 plan elde. Rejim × strateji tablosu birkaç saatlik araştırma işi.
- **Eksi:** Hücre başına örnek azalır (5 rejim × 4 tür = 20 hücre); bazı hücreler 30'un altında kalabilir.
  Böyle hücreler "yetersiz" yazılmalı.
- **Öneri:** FAZ 3, yalnız araştırma. Katkı ölçülürse ancak o zaman karar motoruna, onayla.

### 2.8 Fırsat geçerliliği (md. 11)

**Mevcut durum: ✅ Büyük ölçüde var.**

- Hazır fırsat yalnız giriş günü açılışı için geçerli.
- Sabah kontrolü olumsuz haberde iptal ediyor.
- Açılış kontrolü 10:05'ten sonra yapılıyor: açılış azami girişin üstündeyse "giriş olmadı" (`opening_check`).
  Telegram uyarısı isteğe bağlı.
- Takip senaryolarının geçerlilik günü var (`takip_senaryo.gecerlilik`), süre dolunca sonuçlanıyor.
- Panel, kaçırılmış akşam analizini ve eski fiyatı uyarıyor.

**Eksik:**

- Azami giriş aşıldıktan sonra kart "giriş olmadı" olarak işaretleniyor; ama gün içinde (açılış kontrolünden
  önce) panelde eski fiyattan gösterilebilir. Açılış kontrolü saatini netleştiren bir uyarı eklenebilir. Küçük iş.
- "Yeni analiz anlamlı değişiklik içeriyorsa yeni sürüm" kuralı 2.4'teki eksikle aynı.

### 2.9 Backtest ve istatistiksel güvenilirlik (md. 12)

**Mevcut durum: 🟡 Yöntem sağlam, metrikler eksik.**

İki ayrı sistem var:

**1. Araştırma sınaması (asıl):** `arastirma/asama6/`

- `etiketle.py`: canlı kodla etiketleme.
- `egit.py`, `model.py`: ileriye dönük sınama.
  - Ana sınama: son 12 ay. Ek sınama: 2024.
  - **45 gün ambargo.**
  - Aylık blok bootstrap güven aralığı.
  - Hisse başına 14 günde bir tekilleştirme kontrolü.
- Gerçekçi işlem kuralları:
  - Giriş ertesi açılışta.
  - Azami giriş aşılırsa işlem yok.
  - Komisyon %0,2, kayma %0,1 (`journal.evaluate`).
- Metrikler:
  - Var: isabet (AUC), Brier, kalibrasyon tablosu, en yüksek %20'nin R'si ve net %'si, TP1 oranı.
  - Canlı ölçüm (`journal.metrics`): kazanma, kâr faktörü, işlem başına Sharpe.

**2. KAP haber pilotu:** `bist_haber/backtest.py` + `backtest_ui.py`. Ayrı veritabanı, 1 $ bütçeli,
yapay zekâlı ve eski bir pilot. Eşik ayarı yapmaz, yalnız ölçer.

**Eksik metrikler 🔲:**

- azami düşüş (MDD), Sortino, log loss,
- MAE / MFE (işlem içi en kötü/en iyi hareket),
- ardışık kayıp, kazanç/kayıp dağılımı, işlem süresi dağılımı,
- rejime göre sonuç.

**Portföy ve tek işlem ayrımı 🔲:** Bugün sonuçlar tek işlem bazında. Portföy simülasyonu yok: eşzamanlı işlem
sınırı ve sermaye paylaşımı yok.

**Hayatta kalma yanlılığı ⚠️:**

- Araştırma veritabanı bugünkü 632 hisseyle indirildi; 2021–2026 arasında borsadan çıkan hisseler yok.
  Sonuçlar **büyük olasılıkla iyimser**. Çıkan hisseler genelde kötü performanslı oluyor.
- Yahoo, borsadan çıkan hisselerin geçmişini çoğunlukla tutmuyor.
- Seçenek: KAP'taki işlem sırası kapatılan şirketler listesi + başka bir kaynaktan geçmiş fiyat. Kaynak ve
  lisans araştırılmalı.
- **Veri bulunamazsa** etkinin büyüklüğü tahmin edilip raporlara açık uyarı olarak yazılmalı.

**Bölünme ve temettü:** ✅ Fiyatlar düzeltilmiş olarak çekiliyor (`prices.update`, `auto_adjust=True`). Kurumsal
olay günleri ayrıca uyarılıyor.

**Artı / eksi:**

- **Artı:** Metrikler mevcut etiket verisinden ek indirmesiz hesaplanır; 1 gün iş. Raporların güvenilirliği
  belirgin artar.
- **Eksi:** Portföy simülasyonu yeni varsayımlar ister (eşzamanlı en fazla 5 işlem, eşit risk); varsayımlar açık
  yazılmalı.
- **Öneri:** FAZ 1. En yüksek öncelik.

### 2.10 Yeni tahmin hedefleri (md. 13)

**Mevcut durum: 🔲**

- Tek hedef var: "TP1, SL'den önce görülür mü".
- 5 ve 10 günlük getiri, MAE/MFE ve alternatif TP/SL hedefleri yok.

**Kanıt:** Etiketleme altyapısı (`etiketle.py`) her plan için gelecek fiyat yolunu zaten okuyor; bu hedefler
aynı geçişte üretilebilir.

**Artı / eksi:**

- **Artı:** Ek veri indirmesi yok. Aynı ileriye dönük sınama ve aynı kapıyla (`yeniden_egit.py`
  mantığıyla) karşılaştırılır.
- **Eksi:**
  - 💭 Getiri tahmini genelde TP1 olasılığından daha gürültülü. Fiyattan tahminde hazır büyük modeller bile
    katkı vermedi.
  - Başarısız çıkma olasılığı yüksek.
  - Çok hedef denemek "şans eseri iyi görünen hedef" riskini artırır. Hedef listesi **önceden** sabitlenmeli.
- **Öneri:** FAZ 4, yalnız araştırma. Kabul ölçütü: işlem maliyeti sonrası, en yüksek %20'de mevcut modelden
  anlamlı daha iyi R.

### 2.11 Modüller arası veri sözleşmeleri (md. 14)

**Mevcut durum: 🟡**

- Modüller düz `dict` alışverişi yapıyor. Alan adları tutarlı: `technical.analyze`, `tradeplan.plan`,
  `ready.build` planı, `tracker`.
- Testler bu yapıları dolaylı olarak koruyor.

**Eksik:** Tür tanımı yok. Örneğin bir alan adı değişirse ancak testler yakalar.

**Artı / eksi:**

- **Artı:** Kritik 3–4 sınırda Python 3.9 uyumlu `TypedDict` tanımı belgelendirme sağlar; davranış değişmez.
  Örnekler: teknik sonuç, plan, hazır fırsat, karar kaydı.
- **Eksi:** İstekteki 11 sınıfın tamamını kurmak büyük bir yeniden yazım olur ve kullanıcıya görünür fayda
  sağlamaz. İstek de "gereksiz soyutlama oluşturma" diyor.
- **Öneri:** FAZ 5, yalnız sınır tipleri.

### 2.12 Performans optimizasyonu (md. 15)

**Mevcut durum: 🟡**

- Fiyatlar artımlı güncelleniyor (`prices.update`).
- Teknik hesap her çalıştırmada hisse başına bir kez yapılıyor (`CTX.tech` önbelleği, `_TL_CACHE`).
- KAP istekleri sınırlı ve yavaşlatılmış.
- Okuyucu arka planda ayrı süreç olarak çalışıyor.

**API çağrıları ve Streamlit yeniden çalıştırma: ✅ doğrulandı.** Yapay zekâ çağrıları yalnız şu yollarla
tetikleniyor; sayfa yeniden çalışınca kendiliğinden çağrı **yok**:

- düğmeler: "Haberleri güncelle", "N haberi analiz et", "derin incele",
- zamanlanmış bekçi çalıştırması, ayarla açık/kapalı,
- isteğe bağlı sabah haber kontrolü, varsayılan kapalı.

Ek korumalar:

- Aynı içerik ikinci kez gönderilmiyor (`dedupe`).
- Aylık bütçe aşılınca duruyor.
- Bütün çağrılar tek kayıtta: ⚙️ Ayarlar → 🤖 Yapay zekâ kullanımı.

**Eksik:** Panel açılış süresi ve sayfa başına hesap süresi **ölçülmedi** 💭.

**Öneri:** FAZ 5. Önce ölç, sonra yalnız ölçülen darboğazı düzelt. Önbellek güncellik kontrolünü atlamamalı.

### 2.13 Dinamik vade (md. 16)

**Mevcut durum: 🔲 Tek vade (2–10 gün).**

- `tradeplan.HORIZON` yalnız vade tahmini için var.
- Etiketler, geçerlilik süresi ve TP/SL tanımları 2–10 güne göre.

**Teknik maliyet (vade başına):**

- yeni etiket (aynı fiyat verisinden),
- vadeye uygun TP/SL ve geçerlilik kuralları,
- ayrı model ve ayrı sınama,
- panelde vade seçimi.

**Veri yeterliliği:**

| Vade | Yeterlilik |
|---|---|
| 1–3 gün | Yeterli. Ama işlem maliyeti (%0,3) getiriye göre büyük. |
| 10–30 gün | 5 yılda yeterli. |
| 30–90 gün | 5 yılda bağımsız dönem sayısı az (~20–40). İstatistik zayıf. |

**Öneri:** FAZ 6, yalnız tasarım notu. İstek de ilk aşamada etkinleştirmeyi yasaklıyor.

### 2.14 Donanım ve ortamlar (md. 17)

**Mevcut durum: ✅**

- Python 3.9, CPU.
- Ayrı araştırma ortamı (`.venvs/halley-arastirma`).
- Kurulum paketi gömülü Python ile geliyor.
- Uygulama içi güncelleme var: açık depo, derlenmiş kod, geri dönüş.
- Geliştirme klasöründe güncelleme özelliği kapalı.

**Eksik:** Yok. Python yükseltmesi gerekmiyor; önerilen işlerin hiçbiri 3.10+ istemiyor.

---

## 3. "Kodda var" ile "gerçek veride çalışıyor" farkı

| Özellik | Kodda | Testte | Gerçek veride |
|---|---|---|---|
| Hazır fırsat seçimi | ✅ | ✅ | ✅ Çalışıyor (13.11 akşamı 2 öneri). **Sonuç henüz yok.** |
| Açılış / sabah kontrolü | ✅ | ✅ | ⏳ İlk gerçek açılış 16.11 Pazartesi. |
| Gizli model kaydı | ✅ | ✅ | ✅ 2 kayıt (sonradan eklendi). Ölçüm için en az 30 kapanmış öneri gerekiyor. |
| Sanal işlem günlüğü | ✅ | ✅ | 🟡 30 kayıt, 3 sonuç (3 SL). Örnek çok az. |
| Takip / bekçi | ✅ | ✅ | 🟡 3 senaryo bekliyor, sonuç yok. |
| Strateji türüne göre tablo | ✅ | ✅ | 🔲 Canlıda boş. 5 yıllık sınamada türe göre sonuç var. |
| Rejim kaydı | ✅ | ✅ | ✅ 2 çalıştırmada kayıtlı. Etkisi ölçülmedi. |
| Uygulama içi güncelleme | ✅ | ✅ | ✅ Gerçek kurulumda panelden güncelleme ve geri dönüş denendi. Otomatik geri dönüş gerçek kurulumda denenmedi. |
| HTML indirme | ✅ | ✅ | ✅ Canlı veriyle üretildi ve tarayıcıda açıldı. |

---

## 4. Yol haritası (fazlar)

Ortak kurallar:

- Her faz ayrı onayla başlar.
- Her fazın sonunda md. 19'daki tamamlama raporu yazılır.
- Yapay zekâ maliyeti bütün fazlarda **0 $**. Hepsi işlemciyle çalışır.
- Veritabanı değişikliğinden önce yedek alınır.
- Süreler benim çalışma süremdir; arka planda çalışan hesaplar dahil.

### FAZ 1 — Backtest doğruluğu, eksik metrikler, veri güvenilirliği (öncelik: 1)

- **Amaç:** Geçmiş sınama raporlarını eksiksiz ve dürüst yapmak.
- **Mevcut dosyalar:** `arastirma/asama6/model.py`, `egit.py`, `etiketle.py`, `bist_haber/journal.py`,
  `bist_haber/prices.py`, `bist_haber/db.py`.
- **Değiştirilecek:**
  - `model.py`: MDD, Sortino, log loss, ardışık kayıp, dağılımlar.
  - `etiketle.py`: MAE/MFE, işlem süresi sütunları.
  - `journal.metrics`: aynı metrikler canlı için.
  - `db.py`: göç, `prices` için kaynak ve indirme zamanı.
  - `prices.py`: bu alanların yazılması.
- **Yeni dosyalar:**
  - `arastirma/asama6/portfoy.py`: basit portföy simülasyonu (eşzamanlı en fazla 5, eşit risk).
  - `arastirma/hayatta_kalma.md`: borsadan çıkan hisse araştırması.
- **Tahmini süre:** 1,5–2 gün. Yeniden etiketleme ~25 dk.
- **Risk:**
  - Düşük. Canlı karar kuralları değişmez.
  - Veritabanı göçü yalnız sütun ekler.
- **Test:**
  - Metrikler için elle hesaplanmış küçük örnekler (birim testi).
  - Eski metriklerin değişmediği kontrolü (0,605 / 0,612 aynı kalmalı).
- **Kabul:**
  - Son 12 ay ve 2024 için tam metrik tablosu.
  - Portföy simülasyonu sonucu.
  - Hayatta kalma yanlılığı raporu: veri bulunduysa etkisi ölçülmüş, bulunamadıysa açıkça eksik.

### FAZ 2 — Karar kaydı, sürümleme, açıklanabilirlik (öncelik: 4)

- **Amaç:** Her hazır fırsat kararının hangi veri ve hangi kural sürümüyle verildiği sonradan incelenebilsin.
- **Mevcut dosyalar:** `ready.py` (`_store`, `build`), `db.py`, `app.py` (`ready_card`), `watchdog.py`.
- **Değişiklikler:**
  - `params_version()`: sabitlerin parmak izi.
  - Kod sürümü.
  - `hazir_firsat_gecmis` tablosu: yalnız anlamlı değişiklikte yeni satır; tür, giriş, SL, TP, durum.
  - Karar kaydına rejim, veri uyarıları ve eksik veri listesi.
  - Kartta "engelleyen / uyaran riskler" ve "eksik veri" başlıkları.
  - İsteğe bağlı: toplam açık risk uyarısı. **Zorunlu filtre yapılması ayrıca onay ister.**
- **Tahmini süre:** 1,5–2 gün.
- **Risk:**
  - Orta. Hazır fırsat kayıt yolu değişir.
  - Kural değişmez; testler korunur.
- **Test:**
  - Aynı gün iki analiz → iki sürüm, değişiklik yoksa tek sürüm.
  - Panel testi.
  - Mevcut 522 test.
- **Kabul:** Gerçek veriyle bir akşam ve sabah döngüsünde sürüm kayıtları doğru oluşmuş olmalı.

### FAZ 3 — Strateji bazlı performans ve piyasa rejimi (öncelik: 2, yalnız araştırma)

- **Amaç:** Hangi senaryo türünün, hangi rejimde işe yaradığını 5 yıllık veride ölçmek.
- **Dosyalar:**
  - Yeni: `arastirma/asama8/strateji_rejim.py`.
  - Değiştirilmeyecek: `regime.py`. 5 seviye araştırma tarafında hesaplanır.
- **Tahmini süre:** 1 gün.
- **Risk:** Düşük; canlıya dokunmaz.
- **Test / kabul:**
  - Tür × rejim tablosu: işlem sayısı, kazanma, beklenen R, kâr faktörü, MDD, ortalama süre, güven aralığı.
  - 30'dan az örnekli hücreler "yetersiz" yazılır.
  - Sonuç rapor olur; **kural değişikliği önerisi varsa ayrıca onaya sunulur.** Örneğin destek türünün zayıflığı.

### FAZ 4 — 5 ve 10 günlük yeni hedefler (öncelik: 3, yalnız araştırma)

- **Amaç:** 5/10 günlük getiri, MAE/MFE ve 1–2 alternatif TP/SL hedefinin öğrenilebilirliğini ölçmek.
- **Dosyalar:** `etiketle.py` (FAZ 1'de eklenen sütunlar), yeni `arastirma/asama8/hedefler.py`.
- **Tahmini süre:** 1,5 gün.
- **Risk:**
  - Düşük. Canlıya dokunmaz.
  - Çoklu deneme riskine karşı hedef listesi işe başlamadan sabitlenir.
- **Kabul:**
  - Aynı sınama protokolünde, maliyet sonrası R olarak mevcut modelle karşılaştırma.
  - Kapıyı geçmeyen hedef canlıya alınmaz.

### FAZ 5 — Performans ölçümü ve veri sözleşmeleri (öncelik: 5)

- **Amaç:** Panel ve analiz sürelerini ölçmek; kritik sınırlara tip tanımı eklemek.
- **Dosyalar:** yeni `bist_haber/sozlesmeler.py` (`TypedDict`'ler); ölçülen darboğaz dosyası.
- **Tahmini süre:** 1 gün.
- **Risk:** Düşük.
- **Test / kabul:**
  - Ölçüm tablosu: önce / sonra.
  - Davranış değişmez; 522 test geçer.
  - Yapay zekâ çağrı sayısı değişmez.

### FAZ 6 — Farklı vadeler (öncelik: 6, yalnız tasarım)

- **Amaç:** Vade başına gereken etiket, kural, model ve sınamayı ve veri yeterliliğini yazılı bir tasarımla
  belgelemek.
- **Etkinleştirme yok.**
- **Tahmini süre:** 0,5 gün.

**Toplam:** yaklaşık 7–8 iş günü. Fazlar ayrı ayrı onaylanır; her biri kendi başına değer üretir.

---

## 5. Yapılmamasını önerdiklerim (gerekçeli)

| Öneri dışı | Neden |
|---|---|
| Yeni merkezi karar motoru | Mevcut zincir aynı işi yapıyor ve testli. İkinci sistem ayrışma riski demek. |
| Puan ağırlıklarını geçmiş veriye göre ayarlamak | Genel puanın öngörü gücü yok (0,49). Ağırlık aramak aşırı uyum. |
| İstekteki 11 sonuç sınıfının hepsi | Kullanıcıya görünür fayda yok, büyük yeniden yazım. 3–4 sınır tipi yeterli. |
| Sabitleri tek dosyaya taşımak | Çok dosyaya dokunur. Parmak izi aynı faydayı daha az riskle verir. |
| Yeni strateji türleri (sektör liderliği vb.) | Sınanmamış yeni kural. Önce mevcut türler ölçülmeli. |
| Kronos, LSTM, yerel LLM | Ölçüldü / kural gereği. |
| Python yükseltmesi | Önerilen işlerin hiçbiri gerektirmiyor. |

## 6. Onayınızı bekleyenler

1. Faz sırası: 1 → 3 → 4 → 2 → 5 → 6, ya da sizin tercih ettiğiniz sıra.
2. FAZ 1'deki veritabanı göçü: `prices` tablosuna sütun eklenmesi, yedekle.
3. Hayatta kalma yanlılığı için borsadan çıkan hisse verisi aranması. Yalnız ücretsiz ve kullanım şartları uygun
   kaynaklar; bulunamazsa açık uyarı.
4. Kural değişikliği gerektirebilecek bulgular ayrıca onaya sunulacak. Örnekler: destek türü, portföy riski
   filtresi.

> Bu rapordaki performans rakamları geçmiş veri sınamasıdır; gelecek getiri garantisi değildir. Halley emir
> vermez, yatırım tavsiyesi değildir.

---

# EK A (16.11.2026) — Portföy backtest, canlı model izleme ve bozulma tespiti

Bu ek, "HALLEY 2.0 – Ek Geliştirme Kararı" isteğine göre yazıldı. Yöntem aynı:

- **Kod değiştirilmedi.**
- Yalnız kod ve canlı veritabanı (salt-okunur) incelendi.
- Uygulama onay bekliyor.

## A1. Portföy bazlı backtest

### Mevcut durum (kodda doğrulandı)

| Bileşen | Ne yapıyor | Ne yapmıyor |
|---|---|---|
| `journal.evaluate` (sanal ve gerçek işlem) | Tek işlemin girişini, çıkışını, maliyet sonrası getirisini, R'sini ve süresini hesaplıyor. Kurallar: giriş ertesi açılışta ya da limitte; TP1'de yarı satış ve stop girişe; en fazla 30 gün; komisyon ve kayma düşülür. | Sermaye, nakit, adet ya da aynı anda açık pozisyon sınırı yok. MAE/MFE hesaplanmıyor. |
| `journal.record_auto` | "Uygun" görünen her hissenin en uygun senaryosunu sanal işlem olarak kaydediyor. Aynı hissede açık kayıt varken yenisini açmıyor. | Kaç işlemin aynı anda açık olabileceğine ve hangisinin seçileceğine karar vermiyor; her uygun hisse kaydediliyor. |
| `journal.metrics` | Kazanma oranı, kâr faktörü, işlem başına Sharpe. 30'dan az işlemde "yetersiz örnek" işaretleniyor. | Sermaye eğrisi, azami düşüş ve Sortino yok. |
| `journal.position_size` | Tek işlem için adet ve tutar hesaplıyor: sermaye, risk %, giriş, SL ve maliyetten. Kartta 🧮 olarak gösteriliyor. | Diğer açık pozisyonları ve kalan nakdi hesaba katmıyor. |
| `sectors.CONC_WARN` | Açık işlemlerin yarısı ya da fazlası tek ana sektördeyse uyarıyor. | Sınır koymuyor. |
| Araştırma sınaması (`arastirma/asama6`) | 5 yıllık plan evreninde tek işlem bazında isabet, Brier ve en yüksek %20'nin R'si. | Portföy simülasyonu yok. |

### Sonuç

**Evet, ayrı bir portföy simülatörüne gerçekten ihtiyaç var.** Gerekçeler:

- Bugünkü bütün rakamlar "her plana eşit, sınırsız sermayeyle girilseydi" varsayımına dayanıyor.
- Gerçekte aynı gün birden fazla fırsat geliyor, sermaye sınırlı ve pozisyonlar üst üste biniyor.
- Bu yüzden portföy getirisi ve düşüşü, tek işlem ortalamasından **farklı** olur 💭.

Mevcut kod tekrar yazılmamalı. Simülatör, tek işlem sonuçlarını üreten `journal.evaluate`'i **aynen kullanmalı**.
Yeni olan yalnız sermaye ve sıra yönetimi.

### Önemli uyarı: geçmiş evren canlı listeyle aynı değil

- Canlı hazır fırsat **olumlu haber** (skor ≥ 1,50) şartı istiyor.
- 5 yıllık geçmişte yapay zekâ haber puanı yok. Bu yüzden araştırma evreni, haber şartı olmayan **teknik plan
  evreni** (34.579 plan).
- Yani portföy simülasyonu "yalnız teknik" kuralların portföy sonucunu verir; **haberli canlı listeninkini değil.**
- Haberli listenin portföy sonucu ancak canlı kayıtlar biriktikçe ölçülebilir (A2).

### Tasarım: `arastirma/asama6/portfoy.py` (yalnız araştırma)

1. **Olay sırası**
   - Simülasyon gün gün ilerler.
   - Her gün önce açık pozisyonların o günkü fiyatıyla çıkışlar işlenir, sonra yeni girişler yapılır.
   - Giriş ertesi açılışta yapılır; açılış azami girişin üstündeyse girilmez.
   - Gün içinde stop ve hedef aynı anda görülürse stop önce sayılır. Bu, `journal.evaluate`'teki temkinli kuralla
     aynı.
2. **Aynı gün birden fazla fırsat:** Sıralama yalnız o gün bilinen bilgiyle yapılır. İki yöntem ayrı ayrı
   raporlanır:
   - (a) Canlıdaki seçim kuralı: risk seviyesi, teknik skor, risk/getiri.
   - (b) TP1 modelinin **o dönem için dışarıda tutulmuş** olasılığı. Model ileriye dönük eğitilir; aynı yılın
     verisiyle eğitilmiş model kullanılmaz.
3. **Sermaye kuralları:** Hepsi ayarlanabilir; varsayılanlar Halley'in bugünkü ayarlarından gelir.
   - başlangıç sermayesi,
   - işlem başına risk % (adet `journal.position_size` ile hesaplanır),
   - en fazla 5 eşzamanlı pozisyon (canlıdaki "en fazla 5" ile aynı),
   - azami toplam açık risk (ör. %6),
   - tek ana sektörde en fazla N pozisyon.

   Nakit yetmezse işlem atlanır ve atlanan işlem sayılır.
4. **Maliyet:** Komisyon %0,2 ve kayma %0,1, mevcut kurallarla aynı. Düşük likiditede ek kayma isteğe bağlı.
5. **Çıktılar**
   - günlük sermaye eğrisi (gerçekleşmemiş kâr/zarar dahil; açık pozisyonlar o günün kapanışıyla değerlenir),
   - azami düşüş ve süresi,
   - Sortino ve Sharpe (günlük),
   - kâr faktörü, beklenen kazanç, kazanma oranı,
   - ardışık kayıp, ortalama süre,
   - atlanan fırsat sayısı ve nedeni (nakit, risk sınırı, sektör, pozisyon sınırı),
   - tek işlem bazındaki sonuçla yan yana karşılaştırma.

   Son 12 ay ve 2024 ayrı raporlanır.
6. **Geleceği görme engeli**
   - Pozisyon seçiminde yalnız sinyal gününe kadarki veri kullanılır.
   - Sermaye, o güne kadar **gerçekleşmiş** sonuçlardan hesaplanır.
   - Test: geleceğe ait bir fiyat bozulduğunda geçmiş günlerin kararları değişmemeli.

### Canlı portföy görünümü (isteğe bağlı, sonraya)

Aynı simülatör canlıdaki hazır fırsat kayıtlarına uygulanabilir: "Önerilerin hepsine bu kurallarla girilseydi
sermaye eğrisi". Bu yalnız gösterimdir; yeterli kapanmış öneri birikince anlamlı olur.

### Süre ve test

**Tahmini süre:** Araştırma simülatörü ve rapor 1,5 gün. Canlı görünüm 0,5 gün, sonraya bırakılabilir.

**Testler:**

1. Elle hesaplanmış 3–4 işlemlik küçük senaryoda nakit, adet, düşüş ve gerçekleşmemiş kâr/zarar birebir tutmalı.
2. Sermaye ve pozisyon sınırsızken işlem başına sonuç, `journal.evaluate` toplamıyla aynı çıkmalı.
3. Geleceğe ait veri bozulduğunda geçmiş kararlar değişmemeli.
4. Aynı girdiyle iki çalıştırma aynı sonucu vermeli.

**Kabul:** Son 12 ay ve 2024 için portföy raporu; tek işlem / portföy farkı ve varsayımlar açıkça yazılmış.

## A2. Canlı tahmin ve model performans izleme

### Mevcut durum (kodda doğrulandı)

- **Gizli kayıt:** `hazir_firsat.model_json` alanında olasılık, bant, benzer durum sayısı ve oranı, model sürümü ve
  hesaplanma zamanı tutuluyor. Yazan: `ready._store` → `ready.model_info`.
- **Sonuç** aynı satırda tutuluyor: `ready.evaluate_all` → `durum`, `sonuc_json`. İçeriği:
  - giriş olup olmadığı,
  - TP1 görüldü mü, TP2, SL, başabaş ya da süre doldu,
  - net getiri ve R,
  - işlem günü.
- **Ölçüm:** `tp1_model.live_check(conn)` kapanan öneri sayısını, bantlara göre gerçek oranı, ortalama tahmini,
  gerçek oranı ve Brier'i veriyor. 30'dan az örnekte isabeti hesaplamıyor. Panelde gösterilmiyor.
- **Canlı veri (16.11):** 2 açık kayıt, 0 kapanmış. İkisi de "sonradan" işaretli.

### Eksikler (isteğe göre)

| İstenen | Durum | Not |
|---|---|---|
| Tahmin kimliği, hisse, zaman, model sürümü, olasılık | ✅ var | `hazir_firsat.id`, `model_json` |
| Tahmin edilen sonuç (bant) | ✅ var | düşük / orta / yüksek |
| Giriş, stop ve TP1 seviyeleri | ✅ var | aynı satırda |
| Fırsat puanı | ✅ var | `genel_puan` |
| **Özellik sürümü** | 🔲 yok | Modelin girdi listesi ve kod sürümü kayda yazılmıyor. |
| **Piyasa rejimi** | 🔲 yok | Rejim yalnız bekçi çalıştırma özetinde. |
| **Veri kalitesi** | 🔲 yok | Veri uyarıları kayda yazılmıyor. |
| **Girdi değerleri** | 🔲 yok | Dağılım değişikliğini ölçmek için gerekli (A3). |
| **Değiştirilemezlik** | ❌ yok | Aynı gün yeniden analizde `ON CONFLICT DO UPDATE` model_json'u **değiştirebiliyor**; sonradan ekleme de güncelleme ile yapılıyor. |
| **Sonucun ayrı kayıt olması** | ❌ yok | Sonuç tahminle aynı satırda, güncellenerek tutuluyor. |
| MAE / MFE | 🔲 yok | `journal.evaluate` hesaplamıyor (FAZ 1'de eklenecek). |
| Win rate, beklenen kazanç | 🟡 kısmen | `ready.performance` var; modelle ilişkilendirilmemiş. |
| Log loss, kalibrasyon, rejime göre başarı, backtest–canlı farkı | 🔲 yok | |
| Açık tahminin hesaba katılmaması | ✅ var | `live_check` yalnız `durum='kapandi'` olanları sayıyor. |
| Düşük örneklem uyarısı | 🟡 kısmen | `live_check` 30'un altında isabet vermiyor; panelde gösterilmiyor. |

### Tasarım

Yöntem, mevcut **bekçi karar defteri** (`signal_log`) ile aynı: kayıt yalnız eklenir, veritabanı tetikleyicisi
güncellemeyi ve silmeyi engeller.

1. **`tahmin` tablosu** (yeni; yalnız eklenir, değiştirilemez, silinemez). Her hazır fırsat ilk kaydedildiğinde
   bir satır yazılır. Alanlar:
   - kimlik, `hazir_firsat_id`, hisse, sinyal günü, tahmin zamanı (Türkiye saati),
   - model sürümü, özellik sürümü (girdi listesinin parmak izi), kod sürümü, parametre sürümü (FAZ 2'deki
     `params_version()`),
   - olasılık, bant, benzer durum sayısı ve oranı,
   - tür, giriş, azami giriş, SL, TP1, TP2, geçerlilik,
   - genel puan, teknik skor, haber skoru,
   - rejim (trend, oynaklık, genişlik),
   - veri uyarıları,
   - girdi değerleri (JSON),
   - `sonradan` bayrağı: güncellemeden önceki kayıtlara eklenenler ayrı tutulur ve istenirse ölçümden çıkarılır.

   Aynı gün yeniden analizde plan anlamlı değiştiyse (tür, giriş, SL ya da TP) **yeni** satır eklenir, eskisi
   kalır. Değişmediyse satır eklenmez.
2. **`tahmin_sonuc` tablosu** (yeni; yalnız eklenir). Değerlendirmenin her adımında değil, yalnız **nihai sonuç**
   kesinleştiğinde bir satır yazılır. Alanlar:
   - giriş oldu mu, giriş günü ve fiyatı,
   - TP1 görüldü mü, SL görüldü mü, TP2,
   - çıkış nedeni, işlem günü,
   - net getiri, R, MAE, MFE,
   - değerlendirme zamanı, değerlendirme kuralı sürümü.

   "Giriş olmadı" ve "sabah iptal" de birer sonuçtur. Bunlar isabet hesabında **ayrı** sayılır; model yalnız
   girilen planlarda ölçülür.
3. **Yazan yerler**
   - Tahmin satırını `ready._store` yazar.
   - Nihai sonuç satırını `ready.evaluate_all`, `ready.morning` ve `opening_check` yazar.
   - Mevcut `hazir_firsat` akışı ve ekranı değişmez; yeni tablolar onun yanına eklenir.
4. **Ölçüm** (yeni modül yok; `tp1_model.live_check` genişletilir)
   - tahmin sayısı; sonuçlanan, açık, girişsiz ve iptal sayıları,
   - win rate, beklenen kazanç (R ve net %),
   - Brier, log loss,
   - kalibrasyon: bantlara göre tahmin ve gerçek oran, güven aralığıyla,
   - rejime göre sonuç,
   - aynı model için geçmiş sınamanın beklediği oranla canlı oranın farkı, güven aralığıyla.
5. **Güvenilirlik etiketi:** Bütün oranlar Wilson ya da bootstrap güven aralığıyla gösterilir.
   - Sonuçlanan < 30: "çok az örnek, karar verilmez".
   - 30–99: "düşük güven".
   - ≥ 100: "orta güven".
6. **Panel:** 🏁 Performans'ta "Model canlı performansı" bölümü. Yalnız okuma; kararları etkilemez.

### Gerçekçi beklenti (örneklem)

- Hazır fırsat günde 0–5 tane çıkıyor ve sonuçlanması 30 işlem gününe kadar sürebiliyor.
- 💭 30 sonuçlanmış tahmin için 1–2 ay, 100 için 3–6 ay gerekebilir.
- Bu yüzden **kayda erken başlamak**, ölçümün kendisinden daha önemli.

### Veritabanı değişiklikleri

- Yeni tablolar: `tahmin` ve `tahmin_sonuc`, değiştirilemezlik tetikleyicileriyle.
- Yeni sütun yok; mevcut tablolara dokunulmaz.
- Göçten önce yedek alınır.
- Mevcut `model_json` alanı geriye uyumluluk için kalır.

### Süre ve test

**Tahmini süre:** 2 gün (kayıt ve sonuç 1 gün; ölçüm ve panel 1 gün).

**Testler:**

1. Tahmin satırı güncellenmeye ya da silinmeye çalışılınca veritabanı reddetmeli.
2. Aynı gün değişmeyen yeniden analiz yeni satır üretmemeli; değişen analiz üretmeli.
3. Açık tahmin ölçüme girmemeli.
4. Bilinen 10 tahmin ve sonuçla Brier, log loss ve kalibrasyon elle hesaplananla aynı çıkmalı.
5. Girişsiz ve iptal ayrı sayılmalı.
6. Mevcut 522 test geçmeli.
7. Gerçek bir akşam, sabah ve açılış döngüsünde kayıtlar doğru oluşmalı.

**Kabul:** Gerçek veride en az bir döngü doğrulanmış olmalı; panel yalnız gerçekten sonuçlanmış tahminleri saymalı.

## A3. Model performansında bozulma tespiti

### Mevcut durum

Yok 🔲. Bugün yalnız `live_check` var. Aylık yeniden eğitim betiğinin "kapısı" (`yeniden_egit.py`) **yeni**
modeli eski modelle karşılaştırıyor; canlı bozulmayı izlemiyor.

### Tasarım

Sistem yalnız **uyarı** üretir; modeli otomatik olarak yeniden eğitmez ya da devre dışı bırakmaz. Dört uyarı türü:

| Uyarı | Ölçü | Yanlış alarm koruması |
|---|---|---|
| **Performans düşüşü** | Girilen planlarda gerçek TP1 oranı ve R, geçmiş sınamanın beklediğinden düşük mü? | En az 50 sonuçlanmış tahmin. Fark %90 güven aralığının dışında olmalı ve ardışık iki değerlendirmede tekrar etmeli. |
| **Kalibrasyon bozulması** | Bant başına tahmin ile gerçek arasındaki fark; toplam Brier'in geçmiş sınamaya göre değişimi | Bant başına en az 20 sonuç; bootstrap güven aralığı. |
| **Piyasa rejimi değişikliği** | `regime.py`'nin trendi ya da oynaklık yüzdeliği, modelin eğitildiği dönemde nadir görülen bir bölgeye geçti mi? | Yalnız bilgi notu: "Model bu koşulda az sınandı". Fiyattan hemen hesaplanır, örnek beklemez. |
| **Girdi dağılımı değişikliği** | Modelin 10 girdisinin son 60 işlem günündeki dağılımı ile eğitim dağılımı arasındaki fark (PSI). Girdi değerleri A2'deki tahmin satırında saklanır. | Girdi başına PSI > 0,25 ve en az 100 tahmin. |

- **Gösterim:** Uyarılar 🏁 Performans'ta ve haftalık raporda sarı ya da kırmızı not olarak çıkar. Telegram
  isteğe bağlıdır, varsayılan kapalı. Açıklama sade olur: "Son 60 sonuçta model %37 dedi, gerçek %22 çıktı; fark
  anlamlı. Modeli yeniden eğitmeyi ya da kartta göstermeyi kapatmayı düşünün."
- **Eylem kullanıcıda:** Yeniden eğitim mevcut `yeniden_egit.py` ile yapılır; kapıdan geçerse ve onayla.

### Bağımlılık ve süre

- Uyarıların A2'nin kayıtlarına ihtiyacı var.
- Girdi dağılımı ve rejim uyarısı, tahmin kaydı başlar başlamaz çalışabilir.
- Performans ve kalibrasyon uyarıları ancak 50'den fazla sonuçla anlamlı olur. O zamana kadar panelde "henüz
  yeterli sonuç yok" yazar.

**Tahmini süre:** 1 gün.

**Testler:**

1. Yapay verilerle:
   - kalibrasyonu doğru 200 tahminde **uyarı çıkmamalı**,
   - tahmin %35, gerçek %15 olan 200 tahminde uyarı çıkmalı,
   - 20 tahminde hiçbir koşulda uyarı çıkmamalı.
2. PSI elle hesaplananla aynı olmalı.
3. Hiçbir uyarı modeli ya da ayarı değiştirmemeli.

## A4. Güncellenmiş yol haritası (Ek A dahil)

Bu ekle plan iki noktada değişti:

- **Canlı tahmin defteri öne alındı.** Canlı kanıt yalnız zamanla birikiyor; kayıt ne kadar erken başlarsa
  doğrulama o kadar erken mümkün olur.
- **Portföy simülatörü FAZ 1'e girdi.** Zaten planlanmıştı; bu ekle kapsamı netleşti.

| Faz | İçerik | Süre | Ön koşul |
|---|---|---|---|
| **FAZ 1** | Backtest metrikleri (MDD, Sortino, log loss, ardışık kayıp, dağılımlar) · `journal.evaluate`'e **MAE/MFE** · **portföy simülatörü (A1)** · hayatta kalma yanlılığı araştırması · `prices` tablosuna kaynak ve indirme zamanı | 3–3,5 gün | — |
| **FAZ 2** | **Canlı tahmin defteri (A2)**: değiştirilemez `tahmin` ve `tahmin_sonuc` tabloları · özellik, kod ve parametre sürümü (`params_version()`) · anlamlı değişiklikte yeni sürüm · Performans'ta "Model canlı performansı" · kartta "engelleyen riskler / eksik veri" | 2,5–3 gün | MAE/MFE (FAZ 1) |
| **FAZ 3** | Strateji türü × rejim (5 seviye) tablosu, yalnız araştırma · portföy simülatörüyle türe göre portföy sonucu | 1 gün | FAZ 1 |
| **FAZ 4** | 5 ve 10 günlük getiri, MAE/MFE ve alternatif TP/SL hedefleri, yalnız araştırma | 1,5 gün | FAZ 1 |
| **FAZ 5** | **Bozulma tespiti (A3)** · hız ölçümü · kritik sınırlarda `TypedDict` | 2 gün | FAZ 2 ve zamanla birikmiş sonuç |
| **FAZ 6** | Farklı vadeler, yalnız tasarım notu | 0,5 gün | — |

- **Toplam:** yaklaşık 10,5–11,5 iş günü. Önceki plan 7–8 gündü; ek iş yaklaşık 3,5 gün.
- **Maliyet:** Yapay zekâ maliyeti **0 $**; her şey işlemciyle çalışır.

**Dosya özeti**

- **Değişecek dosyalar:**
  - `bist_haber/journal.py`: MAE/MFE, metrikler
  - `bist_haber/ready.py`: tahmin ve sonuç kayıtları
  - `bist_haber/tp1_model.py`: `live_check` genişletmesi
  - `bist_haber/db.py`: yeni tablolar, `prices` sütunları
  - `bist_haber/prices.py`
  - `app.py`: Performans bölümü, kart başlıkları
  - `arastirma/asama6/model.py`, `etiketle.py`
- **Yeni dosyalar:**
  - `arastirma/asama6/portfoy.py`
  - `arastirma/asama8/strateji_rejim.py`
  - `arastirma/asama8/hedefler.py`
  - `bist_haber/izleme.py` (bozulma uyarıları)
  - `bist_haber/sozlesmeler.py`
  - testler

## A5. Artılar ve eksiler

| Konu | Artı | Eksi / risk |
|---|---|---|
| Portföy simülatörü | Gerçek düşüşü ve sermaye kısıtını gösterir; tek işlem ortalamasının yanıltıcılığını giderir. | Yeni varsayımlar gerekir (pozisyon sınırı, risk %) ve sonuç bunlara duyarlıdır; birkaç ayar birlikte raporlanmalı. Haberli canlı listeyi değil, teknik evreni ölçer. |
| Canlı tahmin defteri | Gerçek kanıt üretir. Geçmiş sınama ile canlı sonuç arasındaki fark ilk kez ölçülür. Değiştirilemez kayıt güven verir. | Örnek birikmesi aylar sürer; ilk aylarda "yetersiz örnek" görülür. Kayıt hacmi küçük, diske etkisi önemsiz. |
| Bozulma uyarıları | Modelin sessizce kötüleşmesini yakalar. | Az örnekte yanlış alarm riski var; eşikler bu yüzden sıkı. İlk aylarda performans uyarısı çıkmaz. |
| Planın genel etkisi | Canlı karar kuralları değişmez; yalnız ekran ve kayıt eklenir. | Veritabanına iki yeni tablo eklenir; göç ve yedek gerekir. |

## A6. Onayınızı bekleyenler (Ek A)

1. Güncellenmiş faz sırası: FAZ 1 → FAZ 2 → FAZ 3 → FAZ 4 → FAZ 5 → FAZ 6.
2. Portföy simülatörünün varsayılanları (yalnız simülasyonda kullanılır, canlı kuralları değiştirmez):
   - başlangıç sermayesi: Halley ayarındaki değer,
   - işlem başına risk: %1,
   - en fazla 5 eşzamanlı pozisyon,
   - toplam açık risk: %6,
   - tek ana sektörde en fazla 2 pozisyon.
3. Değiştirilemez yeni `tahmin` ve `tahmin_sonuc` tabloları; göç öncesi yedek alınır.
4. Bozulma uyarı eşikleri: en az 50 sonuç, %90 güven aralığı, PSI > 0,25. Yalnız uyarı üretilir, otomatik işlem
   yapılmaz.

---

# EK B (16.11.2026) — Nihai geliştirme planı (kullanıcının onayladığı sıra)

Kullanıcı genel yaklaşımı onayladı, faz sırasını değiştirdi ve ek kabul kriterleri verdi. Bu bölüm o karara göre
yazıldı.

- **Kod hâlâ değiştirilmedi.**
- Yalnız **FAZ 1** için onay isteniyor.
- Sonraki her faz ayrı onayla başlar.

## B0. Onaylanan sıra

| Faz | İçerik | Süre | Canlıya etkisi |
|---|---|---|---|
| **1** | Canlı tahmin defteri ve değiştirilemez tahmin kayıtları | 2,5 gün | Yeni kayıt ve yeni panel bölümü. Karar kuralları değişmez. |
| **2** | Portföy bazlı backtest simülatörü | 1,5–2 gün | Yok (araştırma) |
| **3** | Backtest metrikleri, MAE/MFE, veri güvenilirliği, hayatta kalma yanlılığı araştırması | 2 gün | `prices` tablosuna sütun; yeni metrikler |
| **4** | Strateji türü × piyasa rejimi araştırması | 1 gün | Yok (araştırma) |
| **5** | 5/10 günlük hedef araştırması | 1,5 gün | Yok (araştırma) |
| **6** | Model bozulma uyarıları ve performans optimizasyonu | 2 gün | Yalnız uyarı; otomatik işlem yok |
| **7** | Farklı vadelerin tasarımı | 0,5 gün | Yok (yalnız tasarım notu) |

**Toplam:** yaklaşık 11–11,5 iş günü. Yapay zekâ (OpenAI) maliyeti bütün fazlarda **0 $**; her şey işlemciyle
çalışır.

## B1. Üç kavramın ayrımı (kabul kriteri 1)

| Kavram | Ne | Kayıt | Değişir mi? |
|---|---|---|---|
| **Tahmin** | Belirli bir anda, belirli plan seviyeleri için modelin söylediği olasılık ve o anki bağlam | **yeni:** `tahmin` | **Hayır.** Yalnız eklenir; veritabanı güncellemeyi ve silmeyi reddeder. |
| **Tahmin sonucu** | O tahminin, kendi seviyeleriyle gerçek fiyatlarda nasıl sonuçlandığı | **yeni:** `tahmin_sonuc` (tahmin başına en fazla bir satır) | **Hayır.** Yalnız nihai sonuç yazılır. |
| **Hazır fırsat** | Panelde ve raporda görünen öneri; durum makinesi (aday → onaylandı / iptal → giriş / girişsiz → kapandı) | mevcut: `hazir_firsat` | Evet (bugünkü gibi). Dokunulmaz. |
| **Sanal işlem** | "Uygun" senaryoların otomatik sanal kaydı | mevcut: `trade_journal` | Evet (bugünkü gibi). Dokunulmaz. |

- Tahmin, hazır fırsata yalnız kimlik (`hazir_firsat_id`) ile bağlanır.
- Sonuç, hazır fırsatın değişebilen alanlarından değil, **tahminin kendi dondurulmuş seviyelerinden** hesaplanır.
- Bu sayede hazır fırsat sabah güncellense bile akşamki tahminin sonucu bozulmaz.

## B2. FAZ 1 — Canlı tahmin defteri (ayrıntı)

### Ne zaman tahmin yazılır?

Hazır fırsatı yazan iki yol var; ikisi de bekçinin arka plan görevinde çalışıyor (`kap_worker` → `ready.safe_tick`
→ `watchdog.run_auto`):

- **akşam analizi:** `ready.evening` → `_store(..., "aday")`
- **sabah kontrolü:** `ready.morning` → `_store(..., "onaylandi")`. Sabah kontrolü seviyeleri güncel veriyle
  yenileyebilir.

Tahmin `_store`'un hemen ardından, aynı işlemde yazılır. **Hata olursa hazır fırsat yine kaydedilir.** Bu, bugünkü
model kaydıyla aynı kural.

### Tekrar kaydı önleme (kabul kriteri 2)

- Her tahminin bir **plan imzası** var: hisse, sinyal günü, giriş günü, tür, giriş, azami giriş, SL, TP1, TP2
  (4 basamağa yuvarlanmış), model sürümü ve özellik sürümü.
- `UNIQUE(plan_imzasi)` + `INSERT OR IGNORE` kullanılır. Aynı plan kaç kez hesaplanırsa hesaplansın **tek satır**
  olur:
  - Streamlit yeniden çalışması,
  - bekçinin ikinci çalışması,
  - elle yeniden kontrol.
- Plan **anlamlı değişirse** (ör. sabah seviyeler yenilendi) imza değişir ve yeni satır eklenir. Eski satır kalır;
  yenisi `onceki_tahmin_id` ile eskisine bağlanır.
- Panelin "eksik model olasılığını doldur" adımı (`fill_missing_model`) deftere **tahmin yazmaz**. O yalnız
  hazır fırsatın gösterim alanını doldurur.

### `tahmin` tablosu (yeni)

| Alan | Açıklama |
|---|---|
| `id`, `plan_imzasi` (benzersiz), `onceki_tahmin_id` | kimlik, tekrar engeli, sürüm zinciri |
| `hazir_firsat_id`, `ticker`, `signal_day`, `giris_gunu`, `analiz` | bağlam (akşam / sabah) |
| `tahmin_zamani` | Türkiye saati, ISO |
| `model_surum`, `ozellik_surum`, `kod_surum`, `parametre_surum` | Model dosyası adı; girdi listesinin parmak izi; kurulu sürüm (`surum.txt`) ya da geliştirme işareti; karar sabitlerinin parmak izi (`ready`, `tradeplan`) |
| `olasilik`, `bant`, `benzer_n`, `benzer_oran` | modelin söylediği |
| `tur`, `giris`, `azami_giris`, `sl`, `tp1`, `tp2`, `gecerlilik_gun` | dondurulmuş plan seviyeleri |
| `genel_puan`, `teknik_skor`, `haber_skoru`, `kaynak`, `risk` | puanlar |
| `rejim_json` | `regime.regime(conn, signal_day)`: trend, oynaklık, genişlik |
| `veri_json` | veri uyarıları, son fiyat günü, veri kritik mi |
| `girdi_json` | modelin girdi değerleri (FAZ 6'daki dağılım uyarısı için) |
| `sonradan` | 0/1. Tahmin zamanından önce oluşmuş bir plana sonradan eklenen kayıt |

### `tahmin_sonuc` tablosu (yeni)

| Alan | Açıklama |
|---|---|
| `tahmin_id` (benzersiz) | tahmin başına en fazla bir nihai sonuç |
| `sonuc_turu` | `tamamlandi` / `girissiz` (açılış azami girişin üstünde) / `iptal` (hazır fırsat sabah iptal edildi ya da yeniden hesaplamada düştü) / `yerini_aldi` (aynı fırsatın açılıştan önce daha yeni tahmini geldi) / `gec_kayit` (giriş günü açılışından sonra kaydedilmiş; ölçülmez) |
| `giris_gunu_gercek`, `giris_fiyati` | gerçekleşen giriş (açılış) |
| `tp1_goruldu`, `sl_goruldu`, `cikis_nedeni`, `islem_gunu` | sonuç |
| `net_getiri_pct`, `r` | maliyet sonrası |
| `mae_r`, `mfe_r` | girişten çıkışa kadar en kötü ve en iyi hareket (R cinsinden) |
| `ayni_gun_belirsiz` | 0/1. TP1 ile SL aynı mumda görüldü mü (kabul kriteri 6) |
| `degerlendirme_zamani`, `kural_surum` | ne zaman, hangi kuralla |

### Sonuçlandırma kuralları

Yeni `defter.sonuclandir()`, akşam ve sabah analizinin başında çalışır; yani `ready.evaluate_all` ile aynı yerde.

1. **Giriş:** Giriş günü açılışında yapılır. Açılış azami girişin üstündeyse sonuç `girissiz` olur; bu, bugünkü
   kuralla aynı.
2. **Çıkış:** Mevcut `journal.evaluate` aynen kullanılır; tek işlem hesabı yeniden yazılmaz.
   - TP1'de yarı satış, stop girişe çekilir.
   - TP2, SL, başabaş, en fazla 30 işlem günü.
   - Komisyon ve kayma ayardan alınır.
3. **Aynı mumda TP1 ve SL (kabul kriteri 6):**
   - Günlük mumda gerçekleşme sırası bilinemez. Bu durumda **SL önce sayılır** (muhafazakâr kural). Bu,
     `journal.evaluate`'in bugünkü kuralıyla aynı.
   - Ek olarak sonuç satırına `ayni_gun_belirsiz = 1` yazılır.
   - Raporda bu tahminlerin sayısı ayrıca gösterilir; isteğe bağlı olarak hariç tutulmuş bir ikinci hesap da
     verilir.
4. **Sonuçlanmamış tahmin (kabul kriteri 5):**
   - Sonuç satırı olmayan tahmin "açık" sayılır. Kazanma oranına, beklenen kazanca, Brier'e ya da log loss'a
     **girmez**; yalnız "açık tahmin sayısı" olarak görünür.
5. **Tahminden sonraki veri (kabul kriteri 7):**
   - Tahminin girdileri yalnız sinyal gününe kadarki veridir; model bugün de böyle hesaplıyor.
   - Ölçüme yalnız **giriş günü açılışından önce kaydedilmiş** tahminler girer: `tahmin_zamani < giris_gunu
     09:55 TR` ve `sonradan = 0`.
   - Aynı fırsatın birden fazla tahmini varsa ölçülen, **açılıştan önceki son tahmin**dir. Eskilerinin sonucu
     `yerini_aldi` olur.
   - Sonradan eklenen ya da geç kaydedilen tahminler ayrı bir satırda gösterilir, ana hesaba katılmaz.
   - Bu kural sayesinde bugünkü 2 "sonradan" kaydı (BAHKM, ENERY) ana ölçümü kirletmez.

### Ölçüm ve panel

`defter.ozet(conn)` hesaplar; 🏁 Performans ekranında "🎯 Model canlı performansı (tahmin defteri)" bölümünde
gösterilir:

- **Sayılar:** tahmin, sonuçlanan, açık, girişsiz, iptal, aynı mumda belirsiz.
- **Oranlar:** girilen ve tamamlanan tahminlerde kazanma oranı, TP1 oranı, beklenen kazanç (ortalama R ve net %).
- **Olasılık doğruluğu:** Brier ve log loss. TP1 olayı: yarı satış gerçekleşti mi.
- **Kalibrasyon tablosu:** her bant (düşük / orta / yüksek) için ortalama tahmin, gerçek oran ve Wilson güven
  aralığı.
- **Rejime göre:** trend ve oynaklık.
- **Geçmiş sınama farkı:** modelin 5 yıllık sınamada aynı bant için gördüğü oran ile canlı oran.
- **Güven etiketi:** sonuçlanan < 30 "çok az örnek, karar verilmez"; 30–99 "düşük güven"; ≥ 100 "orta güven".

Mevcut `tp1_model.live_check` korunur. Yeni özet onun yerine geçmez; yanında durur.

### Dosyalar

| Dosya | Değişiklik |
|---|---|
| `bist_haber/defter.py` | **YENİ.** `kaydet()`, `plan_imzasi()`, `surumler()`, `sonuclandir()`, `ozet()` |
| `bist_haber/db.py` | Şemaya iki tablo, benzersiz indeksler ve dört tetikleyici: `tahmin` için güncelleme/silme yasağı; `tahmin_sonuc` için güncelleme/silme yasağı. Göçten önce otomatik yedek (B3). |
| `bist_haber/ready.py` | `_store` sonunda `defter.kaydet(...)` (try/except). `evening` ve `morning` başında `defter.sonuclandir(...)`. Seçim kuralları **değişmez**. |
| `app.py` | 🏁 Performans'a yeni bölüm (yalnız okuma) |
| `tests/test_defter.py` | **YENİ** (B4) |
| `KULLANIM.md`, `NOTLAR.md` | açıklama |

Dokunulmayanlar: `journal.py` (yalnız çağrılır), `tradeplan.py`, `entries.py`, `signals.py`, `trade_journal`,
`hazir_firsat` şeması.

## B3. Veritabanı göçü: yedekleme ve geri dönüş planı

**Göçün niteliği:**

- Yalnız **ekleme**: iki yeni tablo, indeksler ve tetikleyiciler.
- Mevcut tablolara ve satırlara dokunulmaz; sütun eklenmez ya da silinmez.
- Eski Halley sürümleri yeni tabloları görmez ve çalışmaya devam eder.

**Yedekleme:**

1. Göç, `db.connect` içinde `tahmin` tablosu **yoksa** çalışır.
2. Önce SQLite yedekleme yöntemiyle tutarlı bir kopya alınır:
   `data/yedek/bist_haber_<zaman>_tahmin_defteri_oncesi.db`
3. Kopyada `PRAGMA integrity_check` sonucu `ok` değilse göç yapılmaz; panel uyarır ve eski hâliyle devam eder.
4. Yedek başarılı olursa tablolar tek işlemde (transaction) oluşturulur. Hata olursa işlem geri alınır.

Bu otomatik adım müşteri bilgisayarlarında da çalışır. Ayrıca canlıya almadan önce senin veritabanının elle bir
yedeği alınır.

**Geri dönüş (üç seviye):**

| Durum | Ne yapılır | Veri kaybı |
|---|---|---|
| Yeni kod sorun çıkardı | Uygulama içi "↩️ Önceki sürüme dön" ya da geliştirmede önceki commit. Eski kod yeni tabloları yok sayar. | Yok |
| Yeni tablolar tamamen kaldırılmak istenirse | `DROP TABLE tahmin_sonuc; DROP TABLE tahmin;` Satır tetikleyicileri tablo silmeyi engellemez. | Yalnız defter kayıtları |
| Veritabanı bozuldu (beklenmez) | Göç öncesi yedek dosyası geri konur | Göçten sonra eklenen veriler |

Geri dönüş adımı, canlıya almadan önce bir **veritabanı kopyasında** denenecek: göç → kayıt → eski kodla açma →
tablo silme.

## B4. FAZ 1 testleri ve kabul ölçütleri

**Birim ve bütünleşme testleri** (`tests/test_defter.py`):

1. Tahmin satırı `UPDATE` ve `DELETE` ile değiştirilemiyor; sonuç satırı da öyle. Veritabanı reddediyor (kriter 3).
2. Aynı plan beş kez kaydedilince tek satır oluşuyor. Seviye değişince yeni satır ve `onceki_tahmin_id`
   bağlantısı oluşuyor (kriter 2).
3. Panel yüzlerce kez yeniden çalıştırıldığında (AppTest) tahmin sayısı değişmiyor (kriter 2).
4. Sabah hazır fırsat seviyeleri değişince akşamki tahminin sonucu kendi seviyeleriyle hesaplanıyor; hazır fırsat
   güncellemesi onu etkilemiyor (kriter 1, 4).
5. Açık tahmin metriklere girmiyor; yalnız "açık" sayısında görünüyor (kriter 5).
6. Aynı mumda TP1 ve SL'ye dokunan yapay seri: SL sayılıyor, `ayni_gun_belirsiz = 1` (kriter 6).
7. Açılıştan sonra kaydedilen ya da `sonradan` tahmin ana ölçüme girmiyor (kriter 7).
8. Bilinen 10 tahmin ve sonuçla Brier, log loss, kalibrasyon ve Wilson aralığı elle hesaplananla aynı.
9. Girişsiz, iptal ve yerini aldı ayrı sayılıyor; isabet hesabına girmiyor.
10. Göç: yedek dosyası oluşuyor ve `integrity_check` geçiyor. İkinci açılışta göç tekrar çalışmıyor. Eski şemalı
    bir veritabanı kopyasında göç, ardından tablo silme ile geri dönüş çalışıyor.
11. Tahmin yazımı hata verirse (zorla bozulmuş model) hazır fırsat yine kaydediliyor.
12. Mevcut 522 testin hepsi geçiyor.

**Gerçek veride kabul:**

- Canlıya alındıktan sonraki ilk **akşam analizi → sabah kontrolü → açılış** döngüsünde:
  - tahmin satırları doğru sayıda oluşmuş,
  - sabah seviye değişikliği varsa yeni sürüm satırı eklenmiş,
  - panelde "açık tahmin" sayısı doğru.
- Kanıt olarak satır sayıları ve örnek kayıtlar faz raporunda verilir.

**Not:** İlk sonuçlanmış tahminler ancak giriş gününden sonraki günlerde oluşur. FAZ 1'in kabulü kayıt ve
sonuçlandırma mekanizmasının doğruluğuna dayanır; anlamlı performans rakamları aylar içinde birikir.

## B5. Sonraki fazların kabul kriterleri (özet)

| Faz | Kabul |
|---|---|
| **2. Portföy simülatörü** | Aynı anda açık pozisyonlar, kullanılabilir nakit ve toplam portföy riski hesaba katılıyor. Aynı gün fırsatlar yalnız o gün bilinen bilgiyle sıralanıyor (canlı kural ya da dönem dışı model olasılığı). Elle hesaplanmış küçük senaryo birebir tutuyor. Sınırsız sermayede tek işlem toplamına eşit çıkıyor. Geleceğe ait veri bozulunca geçmiş kararlar değişmiyor. Son 12 ay ve 2024 raporu; varsayımlar açık. Not: geçmiş evren haber şartı içermiyor. |
| **3. Metrikler / MAE-MFE / veri** | MDD, Sortino, log loss, ardışık kayıp, dağılımlar ve MAE/MFE; eski metrikler (0,605 / 0,612) değişmeden kalıyor. `prices` tablosuna kaynak ve indirme zamanı, yedekli göçle. Borsadan çıkan hisseler için kaynak araştırması: bulunduysa etkisi ölçülmüş, bulunamadıysa açıkça eksik yazılmış. |
| **4. Strateji × rejim** | Tür × 5 seviyeli rejim tablosu; güven aralıkları; 30'dan az örnekli hücreler "yetersiz". Kural değişikliği önerisi varsa ayrıca onaya sunulur. |
| **5. 5/10 günlük hedefler** | Hedef listesi işe başlamadan sabitleniyor. Aynı protokol; maliyet sonrası R olarak mevcut modelle karşılaştırma. Kapıyı geçmeyen canlıya alınmaz. |
| **6. Bozulma uyarıları / hız** | Yapay veride doğru kalibrasyonda uyarı yok, bozulmada var, 20 örnekte hiçbir koşulda yok. Uyarılar hiçbir ayarı ya da modeli değiştirmiyor. Hız ölçümü önce/sonra; yapay zekâ çağrı sayısı değişmiyor. |
| **7. Vadeler** | Vade başına etiket, kural, model, sınama ve veri yeterliliğini yazan tasarım notu; etkinleştirme yok. |

## B6. Faz sonu rapor biçimi (her fazda)

Her faz sonunda şunlar raporlanır:

- tamamlanan işler,
- değiştirilen ve yeni dosyalar,
- veritabanı değişiklikleri ve alınan yedek,
- yapay zekâ çağrılarındaki değişim (beklenen: yok),
- test sonuçları: sayı ve çıktı,
- gerçek veri kanıtı,
- performans farkı (varsa),
- bilinen sorunlar, eksik işler.

Kurallar:

- Arayüzde görünmesi tamamlanmış sayılmak için yeterli değildir.
- Canlıya alma, kurulum paketi ya da uygulama içi güncelleme yayımı faz raporundan **sonra** ve ayrı onayla
  yapılır.

## B7. Onay istenen

**Yalnız FAZ 1: Canlı tahmin defteri.** Kapsamı B2–B4'te yazılı:

- iki yeni değiştirilemez tablo (otomatik yedekli, yalnız ekleme yapan göç),
- `bist_haber/defter.py`,
- `ready.py`'ye iki çağrı,
- Performans'ta okuma bölümü,
- testler.

Seçim kuralları, eşikler ve yapay zekâ kullanımı değişmez. Tahmini süre 2,5 gün.

---

# EK C (16.11.2026) — FAZ 1 teknik kesinleştirmeler (kabul kriterlerine eklendi)

Kullanıcının istediği beş ayrıntı aşağıda kesinleştirildi. Bunlar B4'teki kabul ölçütlerine **eklenmiştir**.

## C1. Dondurma: tahmin anında neler saklanır

Tahmin satırı yazıldığı anda aşağıdakilerin hepsi o satıra kopyalanır. Satır bir daha değişmez; veritabanı
tetikleyicileri güncellemeyi ve silmeyi reddeder. Sonraki analizler yalnız **yeni** satır ekleyebilir.

| Grup | Alanlar | Kaynak (tahmin anında) |
|---|---|---|
| Model | `olasilik`, `bant`, `benzer_n`, `benzer_oran`, `model_surum`, `model_dosya` | `tp1_model.predict` / `band` / `similar`; etkin model dosyası |
| Model girdileri | `girdi_json` (modelin 10 + haber girdisi) | `tp1_model.plan_features` ile aynı hesap |
| Teknik göstergeler | `teknik_json`: son fiyat ve günü, trend, RSI, MACD histogramı, ADX ve ±DI, ATR ve ATR %, SMA50/200, EMA20/50/200, hacim oranı, OBV eğilimi, 20/60 gün göreli güç, 20 gün destek/direnç, işlem hacmi, teknik skor ve parçaları | `technical.analyze` (sinyal gününe kadarki 250 gün), `ready.tech_score` |
| Piyasa rejimi | `rejim_json`: trend, oynaklık, genişlik, gün | `regime.regime(conn, signal_day)` |
| Veri kalitesi | `veri_json`: veri uyarıları, veri kritik mi, gün sayısı, son fiyat günü | `technical.analyze` |
| İşlem seviyeleri | `tur`, `giris`, `giris_alt`, `azami_giris`, `sl`, `tp1`, `tp2`, `rr1`, `gecerlilik_gun` (=1: yalnız giriş günü açılışı) | hazır fırsat planı |
| Puanlar | `genel_puan`, `teknik_skor`, `haber_skoru`, `kaynak` (haber / teknik), `risk` | hazır fırsat planı |
| Sürümler | `ozellik_surum`, `parametre_surum`, `kod_surum`, `kural_surum` | C2 |

Teknik göstergeler ve model girdileri, olasılığın hesaplandığı **aynı** pencereden tek seferde alınır. Böylece
saklanan olasılık ile saklanan girdiler birbiriyle tutarlıdır.

## C2. Plan imzası: hangi alanlar, ne yeni tahmin sayılır

**Plan imzası** (`plan_imzasi`) şu alanların SHA-256'sıdır. Sayılar 4 basamağa yuvarlanır.

```
ticker | signal_day | giris_gunu | tur | giris | azami_giris | sl | tp1 | tp2 | gecerlilik_gun
| model_surum | ozellik_surum | parametre_surum
```

| Değişen şey | Sonuç | Gerekçe |
|---|---|---|
| Aynı plan yeniden hesaplandı: sayfa yenilendi, bekçi ikinci kez çalıştı, elle kontrol yapıldı | **Tekrar** → satır eklenmez (`INSERT OR IGNORE`) | Aynı karar, aynı model |
| Tür, giriş, azami giriş, SL, TP1, TP2, giriş günü ya da sinyal günü değişti (ör. sabah kontrolü seviyeleri yeniledi) | **Yeni tahmin** → yeni satır; `onceki_tahmin_id` eskisini gösterir | Farklı işlem planı |
| Model sürümü, özellik listesi ya da karar parametreleri değişti | **Yeni tahmin** | Farklı karar mekanizması; sonuçlar karışmasın (C4) |
| Plan ve sürümler aynı, yalnız **olasılık** değişti (ör. sinyal gününe ait geç gelen bir haber girdiyi değiştirdi) | **Yeni tahmin değil.** İlk kayıt dondurulmuş hâliyle kalır; tekrar sayılır. | Tahmin, ilk yapıldığı andaki bilgidir. Sonradan gelen bilgi geçmiş tahmini değiştirmemeli. |
| Plan aynı, yalnız **rejim** ya da **veri kalitesi** değişti | **Yeni tahmin değil**; ilk kayıt kalır | Bunlar sinyal gününe bağlı bağlamdır; plan aynıyken karar aynıdır |

Her `kaydet` çağrısı sonucunu döndürür: `yeni`, `tekrar` ya da `hata`. Testler ve panel bu ayrımı kullanır.

Sürüm parmak izleri:

- **ozellik_surum:** etkin modelin girdi adları listesinin (lojistik girdileri + tablo anahtarları) SHA-256'sının
  ilk 12 karakteri.
- **parametre_surum:** karar sabitlerinin (`ready`: READY_GAP_ATR, MAX_ENTRY_ATR, MIN_RR_AT_MAX, MIN_TECH,
  MIN_TECH_ONLY, MAX_PICKS; `tradeplan`: MIN_RR, MAX_STOP_PCT, ATR_STOP_MULT, LIQ_MIN_TL; haber eşiği 1,50) adı
  ve değerinin parmak izi.
- **kod_surum:** kurulu paketin `surum.txt` dosyası. Geliştirme klasöründe "gelistirme".
- **kural_surum:** sonuçlandırma kuralının sürümü ("s1"; C3).

## C3. Sonuçlandırma kuralları (kural sürümü "s1")

Sonuç yalnız **tahmin satırındaki dondurulmuş seviyelerle**, sinyal gününden **sonraki** günlük mumlarla
hesaplanır.

1. **Geçerlilik.** Tahmin yalnız giriş günü açılışı için geçerlidir (`gecerlilik_gun = 1`).
   - Giriş günü mumu yoksa ama sonraki günlerin mumu varsa (hisse o gün işlem görmedi) → `girissiz` ("giriş günü
     işlem verisi yok").
   - Henüz hiç mum yoksa tahmin açık kalır.
2. **Giriş.**
   - Giriş günü açılışı azami girişin üstündeyse → `girissiz`.
   - Değilse giriş, giriş günü **açılış** fiyatından yapılır.
3. **Çıkış.** Mevcut `journal.evaluate` aynen kullanılır; kod kopyalanmaz.
   - **Giriş günü:** Gün içi sıra bilinmediği için yalnız SL kontrol edilir (düşük ≤ SL → SL). TP o gün sayılmaz.
   - **Sonraki günler, sırayla:**
     - (a) Açılış stopun altındaysa → açılış fiyatından çıkış.
     - (b) Açılış TP1'in üstündeyse → yarısı açılıştan satılır; açılış TP2'nin de üstündeyse tamamı satılır.
     - (c) Gün içi düşük ≤ stop → stop fiyatından çıkış.
     - (d) Gün içi yüksek ≥ TP1 → yarısı TP1'den satılır, stop giriş fiyatına çekilir. TP2 aynı gün sayılmaz.
     - (e) TP1'den sonra yüksek ≥ TP2 → kalan yarı TP2'den satılır.
   - **Süre:** En fazla 30 işlem günü; sonra son kapanıştan "süre doldu".
   - **Maliyet:** Komisyon ve kayma Ayarlar'dan alınır (varsayılan %0,20 + %0,10).
4. **Aynı mumda TP ve SL.** (c) adımı (d)'den önce geldiği için **SL önceliklidir** (muhafazakâr). Ek olarak bir
   mumda aynı aşamanın stopu ve hedefi birlikte görüldüyse sonuç satırına `ayni_gun_belirsiz = 1` ve
   `belirsiz_gunler` (tarihler) yazılır. Aynı aşama demek:
   - TP1'den önce: SL ve TP1,
   - TP1'den sonra: giriş fiyatı (stop) ve TP2,
   - giriş günü: SL ve TP1.
5. **Sonuç alanları.**
   - `tp1_goruldu`: yarı satış gerçekleşti mi.
   - `sl_goruldu`: TP1'den önce tam SL.
   - `cikis_nedeni`: TP2 / başabaş (TP1 sonrası) / SL / süre doldu.
   - `islem_gunu`, `net_getiri_pct`, `r`.
   - `mae_r` ve `mfe_r`: giriş mumundan çıkış mumuna kadar en düşük ve en yüksek fiyatın girişe uzaklığı, planlanan
     risk (giriş − SL) cinsinden.
6. **Diğer sonuç türleri.**
   - `iptal`: hazır fırsat giriş gününden önce iptal edildi (sabah haber kontrolü ya da yeniden hesaplamada
     düştü).
   - `yerini_aldi`: aynı hisse ve giriş günü için açılıştan önce daha yeni bir tahmin var.
   - `gec_kayit`: tahmin, giriş günü 09:55'ten sonra kaydedildi.

   Bu üç tür hiçbir isabet ya da getiri hesabına girmez.
7. **Açık tahmin.** Sonuç satırı olmayan tahmin açıktır ve yalnız "açık" sayısında görünür.

## C4. Filtreleme: model sürümleri karıştırılmaz

- Canlı performans özeti **her zaman tek bir model sürümü** için hesaplanır. Panelde model sürümü seçilir;
  varsayılan en son sürümdür. "Tümü" seçeneği yoktur; farklı sürümler yan yana ayrı satırlarda gösterilir.
- Ek filtreler:
  - kaynak (haberli / yalnız teknik),
  - senaryo türü,
  - analiz (akşam / sabah),
  - bant,
  - belirsiz mumları dahil et / hariç tut.
- Aynı model sürümünde özellik ya da parametre sürümü farklı olan tahminler varsa bu panelde açıkça uyarılır ve
  ayrı satırda gösterilir.

## C5. Veritabanı: yedek, göç ve geri dönüşün gerçek kopyada sınanması

- Göç `db.connect` içinde yalnız `tahmin` tablosu yoksa çalışır.
- Kullanıcı verisi varsa önce tutarlı bir yedek alınır: `<veri klasörü>/yedek/<dosya>_<zaman>_tahmin_defteri_oncesi.db`.
  Kullanıcı verisi demek: `news`, `hazir_firsat`, `trade_journal` ya da `watchlist` tablolarından birinde satır
  olması.
- Yedekte `PRAGMA integrity_check` sonucu `ok` değilse göç **yapılmaz**. Halley bugünkü gibi çalışmaya devam eder,
  defter kapalı kalır.
- Tablolar tek işlemde (transaction) oluşturulur.
- **Gerçek kopya sınaması (FAZ 1 kabulü):** Canlı veritabanının tutarlı bir kopyası test klasörüne alınır. Sırayla
  şunlar denenir:
  1. Göç öncesi bütün tabloların satır sayısı ve içerik özeti alınır.
  2. Yeni kodla açılır: yedek dosyası, integrity_check ve iki tablo oluşmalı.
  3. Mevcut tabloların sayıları ve özetleri **birebir aynı** kalmalı.
  4. Tahmin yazılır; güncelleme ve silme reddedilmeli.
  5. Eski kodla (FAZ 1 öncesi commit) açılır, sorunsuz çalışmalı.
  6. Tablolar silinir (geri dönüş 2. seviye); mevcut veriler aynı kalmalı.
  7. Yedek geri konur (3. seviye); göç öncesi özetlerle birebir aynı olmalı.

  **Canlı veritabanına göç yapılmaz.** FAZ 1 kodu canlı klasöre ancak ayrı onayla konur.

---

# EK D (16.11.2026) — FAZ 1 tamamlama raporu: canlı tahmin defteri (test ortamı)

**Durum:**

- Kod yazıldı ve test ortamında sınandı.
- Canlı veritabanına göç **yapılmadı**.
- Canlı klasöre **konmadı**.
- Müşteriye güncelleme **yayımlanmadı**.
- FAZ 2'ye **geçilmedi**.

Kod ayrı bir dalda: `faz1-tahmin-defteri` (gizli depo). Ana dal (`main`) FAZ 1 içermez; ileride başka bir düzeltme
canlıya alınırsa FAZ 1 istemeden gitmez.

## D1. Tamamlanan işler

- **İki yeni tablo:** `tahmin` ve `tahmin_sonuc`. Yalnız eklenir; dört tetikleyici güncellemeyi ve silmeyi
  reddeder.
- **Plan imzası:** Ek C2'deki alanlar, `UNIQUE` + `INSERT OR IGNORE`.
  - Tekrar kayıt "tekrar" sayılır.
  - Seviye ya da sürüm değişince "yeni" kayıt açılır ve öncekine bağlanır (`onceki_tahmin_id`).
  - Yalnız olasılık, rejim ya da veri kalitesi değişirse ilk kayıt dondurulmuş kalır.
- **Dondurma:** Tahmin anında kopyalananlar:
  - olasılık, bant, benzer durumlar,
  - model, özellik, parametre ve kod sürümü,
  - model girdileri, teknik göstergeler ve teknik skor,
  - rejim, veri kalitesi,
  - işlem seviyeleri ve puanlar.

  Göstergeler ile olasılık aynı pencereden tek seferde alınır (`tp1_model.plan_context`).
- **Sonuçlandırma (kural sürümü s1, Ek C3):**
  - `journal.evaluate` aynen kullanılır.
  - Giriş günü açılışında giriş yapılır; açılış azami girişin üstündeyse sonuç `girissiz` olur.
  - Giriş günü mumu yoksa sonuç `girissiz` olur.
  - Aynı mumda TP ve SL görülürse SL önce sayılır; ayrıca `ayni_gun_belirsiz` işareti ve günleri yazılır.
  - MAE/MFE (R) hesaplanır.
  - Diğer sonuç türleri: `iptal`, `yerini_aldi`, `gec_kayit`.
  - Açık tahmin metriklere girmez.
- **Ölçüm** (`defter.ozet`): tek model sürümü üzerinden çalışır; sürümler karışmaz. Hesaplananlar:
  - sayılar, kazanma oranı, TP1 oranı (%90 Wilson aralığıyla),
  - beklenen R, ortalama net %,
  - Brier, log loss,
  - MAE/MFE ortalamaları,
  - kalibrasyon (bantlara göre), rejime göre sonuç,
  - geçmiş beklenti ile canlı sonucun farkı,
  - güven etiketi,
  - aynı model sürümünde birden fazla özellik ya da parametre sürümü varsa uyarı.
- **Panel:** 🏁 Performans → "🎯 Model canlı performansı (tahmin defteri)". Yalnız okuma. Filtreler:
  - model sürümü (tek seçim, "tümü" yok),
  - kaynak,
  - senaryo türü,
  - analiz (akşam / sabah),
  - aynı mumda TP/SL olanları dahil et / hariç tut.
- **Bağlantılar:**
  - `ready._store`: plan gerçekten yazıldıysa (`rowcount`) tahmin kaydedilir.
  - `ready.evening` ve `ready.morning`: başlarında sonuçlandırma yapılır.
  - Her iki çağrı da hata fırlatmaz; hazır fırsat akışını engellemez.

## D2. Değiştirilen ve yeni dosyalar

| Dosya | Değişiklik |
|---|---|
| `bist_haber/defter.py` | **YENİ** (378 satır): kayıt, imza, sürümler, sonuçlandırma, ölçüm |
| `bist_haber/db.py` | +150: `TAHMIN_SCHEMA`, `migrate_tahmin` (yedek → integrity_check → tek işlemde oluşturma), `_split_sql` |
| `bist_haber/ready.py` | +19 / −2: `_store` sonunda tahmin kaydı; `evening`/`morning` başında `_defter_sonuclandir`. **Seçim kuralları ve eşikler değişmedi.** |
| `bist_haber/tp1_model.py` | +20 / −6: `plan_context()` eklendi; `plan_features()` onu çağırıyor. **Hesap aynı.** Eğitim = canlı eşlik testi (TrainingMatchesLive) geçiyor. |
| `app.py` | +68: `model_live_panel()` ve Performans'ta çağrısı |
| `tests/test_defter.py` | **YENİ** (17 test) |
| `tests/test_panel_flows.py` | +1 test (panel + yeniden çalıştırma) |

Değişmeyenler: `journal.py`, `tradeplan.py`, `entries.py`, `signals.py`, model dosyası (`tp1_v1.json`),
`analyzer.py` (gpt-5-mini kullanımı), `hazir_firsat` ve `trade_journal` şemaları.

## D3. Veritabanı değişiklikleri

- **Yeni:** `tahmin`, `tahmin_sonuc`, `tahmin_hisse_gun` indeksi ve 4 tetikleyici.
- **Değişen:** mevcut tablo ya da sütun yok.
- **Göç ne zaman çalışır:** `db.connect` içinde, yalnız `tahmin` tablosu yoksa.
- **Yedek ne zaman alınır:** Kullanıcı verisi varsa (news, hazir_firsat, trade_journal ya da watchlist tablosunda
  satır) önce yedek alınır: `<veri>/yedek/<ad>_<zaman>_tahmin_defteri_oncesi.db`.
- **Yedek bozuksa ya da alınamazsa:** Göç yapılmaz, defter kapalı kalır, Halley bugünkü gibi çalışır.

## D4. Yapay zekâ çağrılarındaki değişim

**Yok.** Defter yalnız kayıtlı fiyatları ve yerel model dosyasını kullanır.

## D5. Test sonuçları

- **Tam takım:** `Ran 540 tests … OK`. Önceki 522 + 17 defter testi + 1 panel testi. Ağ denemesi 0.
- **Defter testleri** (`tests/test_defter.py`, 17 test, hepsi geçti):
  - **Değiştirilemezlik:** `UPDATE` ve `DELETE` reddediliyor (tahmin ve sonuç).
  - **Dondurma:** Saklanan olasılık hazır fırsattaki olasılıkla aynı. Girdi, teknik, rejim ve veri alanları dolu;
    teknik gösterge günü sinyal günü.
  - **Tekrar / yeni:**
    - 5 kayıt → 1 satır.
    - Yalnız olasılık değişince "tekrar" ve ilk değer korunuyor.
    - SL değişince "yeni" + `onceki_tahmin_id`.
    - Parametre sürümü değişince "yeni".
  - **Akış:**
    - `_store` 3 kez → 1 tahmin.
    - Defter hatası hazır fırsatı engellemiyor.
    - `_store` yazmadıysa (durum "giris") tahmin yok.
  - **Sonuç:**
    - TP1 → TP2 yolu, R > 0, MAE −0,5 R ve MFE 3,25 R, elle hesaplananla aynı.
    - Aynı mumda TP1 + SL → SL + belirsiz işaretli ve günü yazılı.
    - Giriş gününde ikisi birden görülürse → SL + belirsiz.
    - Açılış azami girişin üstündeyse → girişsiz.
    - Giriş günü mumu yoksa → girişsiz.
    - Pozisyon sürüyorsa → açık ve metrik yok.
  - **Kendi seviyeleri:** Sabah yeni tahmin oluşunca akşamki "yerini aldı" oluyor. Hazır fırsatın SL'si sonradan
    değişse bile sonuç tahminin kendi SL'siyle hesaplanıyor. İptal edilen fırsat → "iptal".
  - **Zaman:** Açılıştan sonra kaydedilen → "geç kayıt". Sonradan eklenen → ana hesap dışında.
  - **Metrik:** Bilinen 10 tahminde Brier, log loss, TP1 %, Wilson aralığı ve bant kalibrasyonu elle hesaplananla
    aynı. Başka model sürümü karışmıyor. Girişsiz ayrı sayılıyor.
  - **Göç:**
    - Yeni veritabanında yedek alınmıyor, ikinci açılışta tekrar çalışmıyor.
    - Kullanıcı verili eski şemada önce yedek alınıyor; yedek sağlam ve göç öncesi hâlinde.
    - Yedek alınamazsa göç yok, defter kapalı, veri yerinde.
    - Tablo silme (2. seviye) çalışıyor.
- **Panel testi:** Performans ↔ Fırsatlar arasında 3 kez gidip gelme ve yeniden çalışmalardan sonra tahmin sayısı
  1 olarak kaldı; "eksik olasılık" yalnız hazır fırsatın gösterim alanını doldurdu; bölüm ve model seçici görünüyor.

## D6. Gerçek veritabanı kopyasında göç ve geri dönüş (Ek C5)

Canlı veritabanı salt-okunur açılıp tutarlı kopyası test klasörüne alındı: 35,8 MB, 20 tablo, 167.412 satır.

| Adım | Sonuç |
|---|---|
| 1. Göç öncesi tablo sayıları ve içerik özetleri | alındı |
| 2. Yeni kodla açma | göç: `olusturuldu`; yedek `bist_haber_20261116_003415_tahmin_defteri_oncesi.db`; yedek integrity_check **ok**; yedekte tahmin tablosu yok |
| 3. Mevcut tablolar göçten sonra | **20/20 tablo birebir aynı** (satır sayısı ve içerik özeti); yedek = göç öncesi kopya |
| 4. Gerçek hazır fırsatlarla kayıt | BAHKM ilk "yeni", ikinci "tekrar" (olasılık 0,3265, orta). ENERY ilk "yeni", ikinci "tekrar" (0,3728, yüksek). Ortak: tp1_v1, özellik 97b3f45b5a82, parametre 22b983b5a3ec, rejim düşüş / yüksek oynaklık. `UPDATE` ve `DELETE` reddedildi. |
| 5. Sonuçlandırma | 2 incelendi, 0 yazıldı. Giriş günü (16.11) mumu henüz yok → doğru olarak açık. Özet: 2 tahmin, 2 açık, "çok az örnek". |
| 6. Kayıttan sonra mevcut tablolar | birebir aynı |
| 7. FAZ 1 öncesi kodla (3310a61) açma (geri dönüş 1. seviye) | Eski `db.connect`, hazır fırsat listesi ve `live_check` çalıştı. Eski panelde Performans, Fırsatlar ve Dashboard **hatasız**. Tahmin tabloları dokunulmadan duruyor. Mevcut tablolar değişmedi. |
| 8. Tabloları silme (2. seviye) | 2 satırlı tablolar silindi; diğer bütün tablolar silmeden önceki hâliyle aynı |
| 9. Yedeği geri koyma (3. seviye) | integrity **ok**; göç öncesiyle **birebir aynı**; tahmin tablosu yok |

**Canlı veritabanı kontrolü (sınamadan sonra):**

- tahmin tablosu yok,
- `data/yedek` içinde defter yedeği yok,
- `defter.py` canlı klasörde yok.

## D7. Performans farkı

Canlı karar kuralları değişmediği için öneri performansında fark beklenmez. Ek iş, her hazır fırsat kaydında bir
model hesabı ve bir satırdır; günde en fazla 5–10 kayıt. Panel açılışında defter yalnız okunur.

## D8. Bilinen sınırlar ve eksik işler

1. **İlk sonuçlar zaman ister.** İlk sonuçlanmış tahmin, giriş gününden sonraki ilk değerlendirmede oluşur.
   Anlamlı ölçüm (30+ sonuç) haftalar ya da aylar sürer.
2. **Açılıştan sonraki sabah kontrolü:** `ready.morning` açılıştan sonra çalışırsa ve seviyeleri yenilerse tahmin
   `gec_kayit` olur, ölçülmez; açılıştan önceki tahmin ölçülür. Bu bilinçli bir seçim (Ek C3).
3. **Kod sürümü:** Geliştirme klasöründe "gelistirme" yazar; gerçek sürüm yalnız kurulu pakette görünür.
4. **Mevcut `hazir_firsat.model_json` alanı:** Gösterim için kalıyor; ölçümün kaynağı artık defter.
5. **Kalan aşamalar:** Canlıya alma (canlı veritabanına göç, elle yedekle) ve müşteriye uygulama içi güncelleme
   ayrı onay bekliyor. FAZ 2 (portföy simülatörü) onay bekliyor.

## D9. Canlıya alma önerisi (onaylanırsa)

1. Canlı veritabanının elle yedeği alınır: `data/yedek/bist_haber_<zaman>_faz1_oncesi.db`.
2. `faz1-tahmin-defteri` dalı `main`'e birleştirilir; canlı klasöre konur; Halley yeniden başlatılır.
3. Göç otomatik yedekle çalışır.
4. Sonraki akşam analizi, sabah kontrolü ve açılış döngüsünde kayıtlar gerçek veride kontrol edilir: satır
   sayıları, sürüm zinciri, açık / girişsiz.
5. Müşteri güncellemesi ayrı onayla yayımlanır.

---

# EK E (16.11.2026 01:00) — FAZ 1 gerçek veri kabul testi: ara rapor

**Durum: FAZ 1 henüz KABUL EDİLMEDİ.**

- Canlı sabah kontrolü saat 08:30'da yapılacak.
- Rapor yazılırken saat 00:56'ydı ve canlı defterde henüz tahmin yoktu.
- Bu durum beklenen bir durumdu: 15.11 akşam analizi FAZ 1 canlıya alınmadan önce çalışmıştı, bu yüzden o
  analizde tahmin yazılmadı.
- Gerçek veri kanıtları iki zamanda toplanacak:
  - 09:15: sabah kontrolünden sonra,
  - akşam analizinden sonra.

  İki bekçi (salt-okunur) kurulu.

Beklerken sabah akışı **canlı veritabanının kopyasında**, **canlı klasördeki kodla**, saat 08:30'a ayarlanarak
prova edildi. Provada:

- haber ve fiyat güncelleme adımları boş geçildi,
- yapay zekâ çağrısı yasaklandı,
- Telegram kapatıldı,
- rapor arşivi kopyanın klasörüne yazıldı.

Prova canlı veritabanını değiştirmedi: canlıda 0 tahmin kaldı ve hazır fırsatlar "aday" durumunda kaldı.

## E1. Prova sonuçları (kanıt: `sabah_prova.py`, `panel_prova.py` çıktıları)

| Kontrol | Sonuç | Kanıt |
|---|---|---|
| BAHKM ve ENERY tahminleri oluştu mu? | ✅ 08:30'da 2 tahmin (#1 BAHKM, #2 ENERY); hazır fırsatlar "onaylandı" | prova öncesi 0 → sonrası 2 |
| Olasılıklar doğru dondurulmuş mu? | ✅ BAHKM 0,3265 (orta), ENERY 0,3728 (yüksek). Hazır fırsattaki gösterim olasılığıyla birebir aynı. | defter ↔ `hazir_firsat.model_json` |
| Teknik göstergeler doğru mu? | ✅ Gösterge günü 13.11 (sinyal günü). BAHKM: RSI 59,96, ATR 11,82, teknik skor 7. ENERY: RSI 62,18, ATR 0,541, skor 8. | `teknik_json` |
| Model sürümleri | ✅ tp1_v1 / özellik 97b3f45b5a82 / parametre 22b983b5a3ec (ikisinde aynı) | `tahmin` satırları |
| İşlem seviyeleri | ✅ BAHKM: kırılım, giriş 163,50, azami 167,05, SL 150,88, TP1 202,00. ENERY: kırılım, giriş 14,60, azami 14,72, SL 13,99, TP1 15,82. Hazır fırsatla aynı. | `tahmin` ↔ `hazir_firsat` |
| Rejim ve veri kalitesi | ✅ Rejim: düşüş, yüksek oynaklık, genişlik %12,1. Veri: uyarı yok, kritik değil, 250 gün, son fiyat 13.11. | `rejim_json`, `veri_json` |
| Aynı analiz tekrarlanınca mükerrer kayıt | ✅ **Yok.** 08:45'te ikinci sabah analizi: yeni satır 0; eski satırlar birebir aynı | 2 → 2 |
| Sayfa yenileme ve Streamlit rerun | ✅ **Değişmiyor.** Performans ↔ Fırsatlar 3 kez + rerun: kayıt sayısı (2, 0, 2) → (2, 0, 2) | `panel_prova.py` |
| Giriş günü ve zaman damgası | ✅ Giriş günü 16.11, sinyal günü 13.11, tahmin zamanı 2026-11-16T08:30:00+03:00. Açılıştan (09:55) önce olduğu için ölçüme girecek. | `tahmin` |
| Açık / girişsiz / sonuçlanmış ayrımı | ✅ 16.11 fiyatı henüz yok → ikisi de **açık**, sonuç satırı yok. Girişsiz ve sonuçlanmış ayrımı birim testlerinde doğrulandı; gerçek veride akşam analizinde görülecek. | özet: açık 2, sonuçlanan 0 |
| Panel sayıları = veritabanı | ✅ Panel: Tahmin 2, Sonuçlanan 0, Açık 2, diğerleri 0. Veritabanı: 2 / 0 / 2. Model seçicide tek seçenek "tp1_v1 (2 tahmin)". Panel hatasız. | `panel_prova.py` |
| Eski tahminler yeni analizden etkileniyor mu? | ✅ Etkilenmiyor. İkinci analizden sonra satırlar birebir aynı; tetikleyiciler değişikliği zaten reddediyor (Ek D6). | karşılaştırma `True` |

## E2. Bulgu: "analiz" etiketi (hata değil, açıklama gerekiyor)

- **Ne görüldü:** Sabah 08:30'da yazılan iki tahminin `analiz` alanı **"aksam"**.
- **Neden:** `ready.morning`, akşam listesindeki fırsatları onaylarken `_store`'u **fırsatın kendi analiz etiketiyle**
  çağırıyor: `ready.py` satır 500, `_store(conn, p, o["analiz"], gday, "onaylandi", now)`. Bu, hazır fırsat
  tablosunun bugünkü davranışı. Defter bu etiketi aynen aldı. Yani alanın anlamı "planı üreten analiz", "kaydın
  yazıldığı analiz" değil.
- **Etkisi:**
  - Veride hata yok. Kaydın gerçek zamanı `tahmin_zamani` alanında doğru (08:30).
  - Ölçüm kuralı (açılıştan önceki son tahmin) etkilenmiyor.
  - Yalnız paneldeki "Analiz: Akşam / Sabah" filtresi, sabah onaylanan akşam planlarını "Akşam" altında gösterir.
    Bu yanıltıcı olabilir.
- **Önerilen düzeltme (onayınla):** Kayıt değiştirilmez; tetikleyiciler buna zaten izin vermez. Panel etiketi
  "Planı üreten analiz" olarak değiştirilir. Ayrıca filtreye "kaydın yazıldığı saat" bilgisi eklenir: açılıştan
  önce akşam ya da sabah, `tahmin_zamani`'ndan hesaplanır.
  - Seçim kurallarına, olasılıklara ve kayıtlara dokunmaz.
  - Yalnız `app.py` metni ve `defter.ozet`'e bir filtre eklenir.

## E3. Kalan kabul adımları (gerçek veri)

1. **09:15 raporu:**
   - Canlı defterde BAHKM ve ENERY tahminleri yazılmış mı?
   - Alanlar provayla aynı mı?
   - Mükerrer var mı?
   - Panel ile veritabanı eşleşiyor mu?
2. **Akşam raporu:**
   - 16.11 fiyatları indikten sonra sonuçlandırma: açılış azami girişin üstündeyse "girişsiz", değilse açık
     pozisyon.
   - Yeni akşam tahminleri eklendi mi?
   - Önceki tahminler değişmedi mi?
3. İki rapor da beklenen sonucu verirse FAZ 1 kabulü önerilecek. Karar kullanıcıda.

## E4. Canlı sabah kontrolü (16.11, gerçek veri) — sonuçlar

**Olay:** Bilgisayar 01:15'te uykuya geçti ve 09:10'da uyandı. Kanıt: Windows Power-Troubleshooter olayı,
"Uykuya Geçiş 2026-11-15T22:15:34Z, Uyanma 2026-11-16T06:10:57Z". Uyanınca Halley süreçleri çalışmıyordu; iki
salt-okunur bekçi de çıktı vermeden sonlanmıştı (çıkış kodu 4). Bu yüzden 08:30 sabah kontrolü yapılmadı. **Bu bir
kod hatası değil, ortam olayı.** Halley 09:37'de yeniden başlatıldı; kod ve kurallar değişmedi.

**Sabah kontrolü:** 09:38'de çalıştı. Bekçi kaydı: `watch_runs` run_id 3, sabah, 2026-11-16, başlangıç kaydı 09:42:26.

| Kontrol | Canlı sonuç | Kanıt |
|---|---|---|
| BAHKM ve ENERY tahminleri | ✅ #1 BAHKM, #2 ENERY; hazır fırsatlar "onaylandı" | `tahmin`, `hazir_firsat` |
| Zaman damgası ve giriş günü | ✅ tahmin_zamani 2026-11-16T09:38:05+03:00, giriş günü 16.11, sinyal günü 13.11. Açılış sınırından (09:55) önce, yani **ölçüme girecek**. | `tahmin` |
| Olasılık | ✅ BAHKM 0,32647 (orta), ENERY 0,37279 (yüksek). Hazır fırsat gösterimiyle ve sabah provasıyla birebir aynı. | `tahmin` ↔ `hazir_firsat.model_json` |
| Teknik göstergeler | ✅ Gün 13.11. BAHKM: RSI 59,96, ATR 11,82, skor 7. ENERY: RSI 62,18, ATR 0,541, skor 8. Provayla aynı. | `teknik_json` |
| Sürümler | ✅ tp1_v1 / 97b3f45b5a82 / 22b983b5a3ec; kod sürümü "gelistirme" (geliştirme klasörü, beklenen) | `tahmin` |
| İşlem seviyeleri | ✅ BAHKM: giriş 163,50, azami 167,05, SL 150,88, TP1 202,00, TP2 214,62. ENERY: giriş 14,60, azami 14,72, SL 13,99, TP1 15,82, TP2 16,43. Hazır fırsatla aynı. | `tahmin` ↔ `hazir_firsat` |
| Rejim ve veri | ✅ Rejim: düşüş, yüksek oynaklık, genişlik %12,1. Veri: uyarı yok, kritik değil, 250 gün. | `rejim_json`, `veri_json` |
| Mükerrer kayıt | ✅ Canlıda tek sabah çalıştırması oldu; 2 tahmin. Aynı analizin tekrarı canlı kopyada sınandı (Ek E1: tekrar → 0 yeni satır). | `watch_runs`, `tahmin` |
| Sayfa yenileme / rerun | ✅ Panel ziyaretleri ve 3 tam sayfa yenilemeden sonra: 2 tahmin, 0 sonuç, satır özeti `aeed9616f1d40205` (değişmedi) | salt-okunur sorgu |
| Açık / girişsiz / sonuçlanmış | ✅ 16.11 fiyatı henüz yok, ikisi de **açık**. Girişsiz ya da sonuçlanmış ayrımı akşam analizinde görülecek. | `tahmin_sonuc` boş |
| Panel = veritabanı | ✅ Panel: Tahmin 2, Sonuçlanan 0, Açık 2, Giriş olmadı 0, İptal/yerini aldı 0, Aynı mumda 0. Model seçici "tp1_v1 (2 tahmin)". Veritabanı: 2 / 0. | canlı panel metni |
| Veritabanı sağlamlığı | ✅ integrity_check ok | salt-okunur sorgu |

**Kalan:** Akşam analizi sonrası kontrol. Bekleneceklerler:

- 16.11 açılışına göre sonuç: açılış azami girişin üstündeyse "girişsiz", değilse açık pozisyon.
- Yeni akşam tahminleri.
- Sabahki iki satırın özetinin değişmemesi.

Akşam bekçisi sonucu `aksam_raporu_20261116.txt` dosyasına da yazacak.

**FAZ 1 hâlâ kabul edilmedi;** akşam adımı bekleniyor.

---

# EK F (16.11.2026) — FAZ 1 dış inceleme bulguları: doğrulama, düzeltme ve test (test ortamı)

**Kapsam:** Yalnız FAZ 1 doğrulama, düzeltme ve test.

- Canlıya alınmadı.
- Canlı veritabanında göç yapılmadı.
- Müşteri güncellemesi yayımlanmadı.
- FAZ 2'ye geçilmedi.
- Model, seçim kuralları ve eşikler değişmedi; yeniden eğitim yapılmadı.

## F0. İncelenen dal ve commit

| | |
|---|---|
| Canlıdaki kod (başlangıç) | `main` @ `60ff0b2` (FAZ 1 v1, kural s1). Çalışma ağacı temizdi. |
| Bekleyen panel düzeltmesi | `faz1-panel-etiket` @ `c7ee840` (onaylı, canlıya alınmamış) |
| Bu çalışmanın dalı | `faz1-dogrulama`: `main`'den açıldı, `faz1-panel-etiket` birleştirildi (`71acd60`), düzeltmeler üstüne eklendi |
| Başlangıç test sonucu | `python run_offline.py` (ağ engelli) → **Ran 540 tests … OK**, ağ denemesi 0. Log: `baslangic_testleri_main_60ff0b2.log` |

## F1. Bulguların doğrulanması

Kanıt yöntemi: bulgu başına önce **doğru davranışı tarif eden** test yazıldı (`tests/test_faz1_dogrulama.py`) ve
düzeltmeden önceki kodda çalıştırıldı. Sonuç: **16 testin 15'i başarısız, 1'i geçti.** Log:
`bulgu_kaniti_once.log`.

| Bulgu | Sonuç | Kanıt (düzeltme öncesi) |
|---|---|---|
| **A. Doğrudan TP2 açılışında TP1 etiketi** | ✅ **Doğrulandı, beklenenden geniş.** `journal.evaluate` açılış ≥ TP2 olduğunda tamamını TP2'de kapatıyor ama `tp1_goruldu=False` bırakıyor. Etiket tanımları farklıydı: `ready.performance`, `tracker.performance` ve `tp1_model.live_check` "tp1_goruldu **veya** sonuç TP2" kullanıyor (doğru); `defter.ozet` ve **araştırma etiketleme** (`etiketle.py` satır 83, eğitim etiketi y) yalnız `tp1_goruldu` kullanıyordu (yanlış). | Test: sonuç "TP2" iken `tp1_goruldu` False. Eğitim verisinde etkilenen plan sayıları F4'te. |
| **B. Maliyetin sonuçlandırma günündeki ayardan okunması** | ✅ **Doğrulandı.** `defter.sonuclandir` komisyon ve kaymayı her çalıştırmada `pipeline.load_settings()`'ten okuyordu. Tahmin satırında sözleşme yoktu. | Kod incelemesi; `test_costs_frozen_at_prediction_time`: alan yok (KeyError) |
| **C. Sürüm gruplarının birleşmesi** | ✅ **Doğrulandı.** `defter.ozet(model_surum)`, aynı modelde farklı özellik veya parametre sürümünü yalnız uyarıyla aynı hesapta topluyordu. | Kod (`surum_uyarisi` sonrası tüm satırlar hesaplanıyordu); test |
| **D. Eksik giriş günü verisi** | ✅ **Doğrulandı.** Giriş günü mumu yok, sonraki günler varken değiştirilemez "girissiz" sonucu yazılıyordu. | Test: sonuç satırı oluştu (`is not None` başarısız) |
| **E. MAE/MFE penceresi** | ✅ **Doğrulandı.** Çıkış mumunun tamamı kullanılıyordu; çıkıştan sonraki hareketler de hesaba giriyordu. | Açılışta stop: beklenen −1,5 R, kod −3,0 R. Gün içi stop: beklenen −1,0, kod −2,0. Giriş günü SL: beklenen −1,0, kod −2,5. |
| **F. Backtest ile canlı karşılaştırma** | ✅ **Doğrulandı.** Panel, modeldeki eğitim tablosu "benzer durum oranını" "Geçmiş ↔ canlı" başlığıyla gösteriyordu. Bu dönem dışı değil; haber şartı da yok. | Kod (`beklenti.gecmis_benzer_oran_%`); test |
| **G. Kayıt hatalarının görünürlüğü** | ✅ **Doğrulandı.** `ready._store` `defter.kaydet` sonucunu yok sayıyordu; "hata", "veri_yok" ve "model_yok" hiçbir yerde görünmüyordu. | Kod; test (`defter_olay` ve `kapsam` yok) |
| Kabul 3: eşzamanlı yazma | ✅ **Zaten sağlanıyordu.** 4 eşzamanlı yazıcı → tek satır (`UNIQUE` + `INSERT OR IGNORE`). | `test_concurrent_writers_single_row` düzeltmeden önce de **geçti** |
| Kabul 9: bağımlı örnekler | ✅ **Eksikti.** Güven etiketi yalnız örnek sayısına bakıyordu. | Test |

## F2. Yapılan düzeltmeler

**A — TP1 olayı:**

- `journal.evaluate` çıktısına `tp1_hedefi` alanı eklendi. Anlamı: TP1 hedefine SL'den önce ulaşıldı, doğrudan TP2
  açılışı dahil.
- `tp1_goruldu`'nun anlamı **değişmedi** ("TP1'de yarısı satıldı"); onu kullanan sanal işlem, takip ve rapor
  davranışları aynı kaldı.
- Defter TP1 olayını `tp1_olayi` olarak kaydeder ve ölçer.
- `etiketle.py` artık `tp1_hedefi` kullanıyor; **yeniden çalıştırılmadı**. Mevcut `etiket3.csv` ve `tp1_v1`
  değişmedi.

**B — Değerlendirme sözleşmesi:**

- Yeni tahminlere tahmin anında `kural_surum` (s2), `komisyon_pct`, `kayma_pct` ve `maliyet_protokol`
  ("ayar_tahmin_ani_v1") yazılır.
- Sonuçlandırma bunları kullanır. Sonradan ayar değişse de geçmiş tahminin sonucu değişmez.
- Eski kayıtlarda bu alanlar **boş kalır** (doldurulmaz). Sonuç satırında kullanılan maliyetin kaynağı açıkça
  yazılır:
  - `tahmin_sozlesmesi`,
  - `s1_sonuclandirma_ayari`,
  - `sozlesme_eksik_sonuclandirma_ani_ayari`.

**C — Sürüm grupları:**

- `defter.gruplar()` gruplama anahtarı: model × özellik × parametre × kural × maliyet protokolü (ve değerleri).
- `defter.ozet()` artık yalnız **tek grup** kabul eder; model sürümüyle çağrılırsa `TypeError` verir.
- Panel grupları yan yana tablo hâlinde gösterir; birleşik bir rakam yoktur.
- Sözleşmesi eksik eski kayıtlar "kural eksik · maliyet eksik" grubundadır.

**D — Eksik veri:**

- Giriş günü mumu yok ama sonraki günler varsa nihai sonuç **yazılmaz**.
- Bu durum `veri_eksik` olarak sayılır; panelde ayrı kutuda görünür ve metriklere girmez.
- Bir defter olayı yazılır (tahmin başına bir kez).
- Veri gelince normal sonuçlandırılır.

**E — MAE/MFE (yöntem "gunluk_s2"):**

- **Pencere:**
  - Giriş mumu (girişten sonra) ve aradaki mumlar **tam** alınır.
  - Çıkış mumunda:
    - açılışta çıkışsa yalnız açılış fiyatı,
    - gün içi çıkışsa yalnız çıkış fiyatı,
    - süre dolduysa (kapanışta çıkış) tam mum.
- **R paydası:** planlanan risk (giriş − SL), `journal.evaluate`'teki R ile aynı.
- **Yaklaşık işareti:** Gün içi çıkışlarda gerçek sıra günlük mumdan çıkarılamaz. Bu yüzden değer bir sınır ölçümüdür
  ve `mae_mfe_yaklasik = 1` işaretlenir; panelde sayısı gösterilir.

**F — Karşılaştırma:**

- "Geçmişte benzer durumlar" karşılaştırması kaldırıldı.
- Panelde yalnız model ↔ canlı **kalibrasyon** var.
- "Dönem dışı geçmiş sınama ile karşılaştırma: **mevcut değil**" yazar. Gerekçe: araştırma evreni haber şartı
  içermiyor; hazır fırsat seçim koşulları farklı; benzer oran eğitim tablosundan geliyor.

**G — Görünürlük:**

- Yeni `defter_olay` tablosu: yalnız eklenir, değiştirilemez, silinemez.
- `kaydet` başarısızlıklarını yazar: kayıt hatası, veri yok, model yok. Anahtar (hazır fırsat, giriş günü) olduğu
  için tekrar denemede olay çoğalmaz.
- `defter.kapsam()` sonucu panelde "🧾 Kayıt kapsamı: x/y … eksik" bölümünde, eksik fırsatlar ve son olaylarla
  gösterilir.
- **Ek güvenlik düzeltmesi:** Hata yolundaki `rollback` kaldırıldı. Çağıran `_store`'un henüz kaydedilmemiş hazır
  fırsat yazımını geri alırdı; bu, "akışı durdurma" kuralını bozardı.

**Kabul 9:** Güven etiketi artık farklı giriş günü sayısına da bakar:

| Koşul | Etiket |
|---|---|
| 30'dan az sonuç | "çok az örnek, karar verilmez" |
| 20'den az farklı gün | "az bağımsız gün, karar verilmez" |
| 100'den az sonuç ya da 60'tan az gün | "düşük güven" |
| Diğer | "orta güven" |

Panel, %90 aralıkların bağımsızlık varsaydığını yazar.

**Eski s1 sonuçları:**

- s1 ile yazılmış fiyat sonuçları değiştirilmez.
- Bunlar için ayrı ve sürümlü `tahmin_degerlendirme` kaydı (s2) eklenir: `UNIQUE(tahmin_id, kural_surum)`, yalnız
  eklenir.
- Ölçüm s2 değerlendirmesini kullanır. s2 değerlendirmesi yoksa s1 sonucu metriğe girmez ("s1_bekliyor").
- s1'in eksik veride yazdığı "girişsiz" sonucu "veri eksik" sayılır.

## F3. Değiştirilen dosyalar

| Dosya | Değişiklik |
|---|---|
| `bist_haber/journal.py` | +`tp1_hedefi` alanı (`tp2_gap`); başka davranış değişmedi |
| `bist_haber/defter.py` | Kural s2; sözleşme; `olay()`; `mae_mfe()`; `_degerlendir()`; s1 → s2 ayrı değerlendirme; `gruplar()`, `grup_etiketi()`, `kapsam()`, `guven(n, gun)`; `ozet(grup)`. **Plan imzası değişmedi.** |
| `bist_haber/db.py` | Sürüm 2 göçü (yalnız ekleme, yedekli, tek işlem): `V2_TAHMIN_COLS`, `V2_SONUC_COLS`, `V2_SCHEMA`, `_missing_v2()`, `migrate_tahmin()` |
| `app.py` | Panel: sürüm grubu seçimi, grup tablosu, kayıt kapsamı ve olaylar, "Veri eksik" kutusu, s1 notu, güven (bağımsız gün), MAE/MFE notu, "dönem dışı karşılaştırma mevcut değil". `faz1-panel-etiket` değişiklikleri de dahil. |
| `arastirma/asama6/etiketle.py` | Etiket `tp1_hedefi`; **çalıştırılmadı** |
| `tests/test_faz1_dogrulama.py` | **YENİ**: 16 regresyon testi (A–G, kabul 3 ve 9, s1 → s2, v1 → v2 göçü) |
| `tests/veri/tahmin_v1_semasi.sql` | **YENİ**: canlıdaki v1 şeması (göç testi fikstürü) |
| `tests/test_defter.py` | `ozet` grup ile; D ve E'nin yeni beklentileri; fikstür s2 |
| `tests/test_panel_flows.py` | Grup seçimi, "mevcut değil" notu; yeni test: kayıt hatası panelde görünür |

## F4. Etkiler: metrikler ve araştırma etiketleri

**Araştırma etiketleri** (`etiket3.csv`; yeniden etiketlenmedi, yalnız sayıldı):

| Küme | Etkilenen plan | Olumlu oran |
|---|---|---|
| Kapanmış planlar (39.297) | **130 (%0,33)**: TP2 ile kapanıp y=0 | %28,82 → %29,15 |
| Eğitim süzgeci (risk ≠ yüksek, stop ≥ %1; 34.665 plan) | **91 (%0,26)** | %29,31 → %29,57 |
| Son 12 aylık sınama dönemi | 14 plan | — |

- **tp1_v1 yeniden eğitilmedi**, raporlardaki ölçüler (AUC 0,605 / 0,612 vb.) eski etiketlerle hesaplanmış olarak
  kalır.
- Etkinin küçük olması beklenir, ama ölçülmedi.
- Bir sonraki aylık yeniden eğitim (`yeniden_egit.py --etiket`) düzeltilmiş etiketle çalışır. O aday model de kapıdan
  geçmek ve onay almak zorundadır.
- Aşama 7 Kronos betiği (`kronos_yol.py`, biten araştırma) yalnız `tp1_goruldu` sayıyordu; sonuç (katkı yok)
  değişmez, yeniden çalıştırılmadı.

**Canlı metrikler:** Canlıda henüz sonuçlanmış tahmin **yok** (2 açık). Bu yüzden canlı metriklerde değişen bir
değer yok.

## F5. Şema değişikliği, yedek ve geri dönüş kanıtı

**Canlı veritabanının kopyasında** sınandı. Canlı salt-okunur açıldı; kopya 36,7 MB, 22 tablo, 169.089 satır.

| Adım | Sonuç |
|---|---|
| Göç | `guncellendi_v2`. Yedek `bist_haber_20261116_102656_tahmin_defteri_v2_oncesi.db`: integrity **ok**; yedek v1 hâlinde; yedek = göç öncesi |
| Kayıtların korunması | **22/22 tablo birebir aynı.** tahmin ve tahmin_sonuc için eski sütunlar karşılaştırıldı; BAHKM ve ENERY tahminleri dahil. |
| Eski kayıtların yeni alanları | (1, BAHKM, None, None, None, None), (2, ENERY, None, None, None, None). **Doldurulmadı.** |
| Değiştirilemezlik | `UPDATE tahmin …`, `DELETE FROM tahmin`, `UPDATE tahmin SET kural_surum` reddedildi. `defter_olay` için ekleme kabul, güncelleme ve silme reddedildi. |
| Gruplar ve kapsam | "tp1_v1 · özellik 97b3f4 · parametre 22b983 · kural eksik · maliyet eksik" (2). Kapsam 2/2. |
| Sonuçlandırma | 2 incelendi, 0 yazıldı. 16.11 mumu kopyada henüz yok → açık. Eski alanlar yine aynı. |
| Eski kodla açılış (main 60ff0b2) | `db.connect` "var"; hazır fırsat listesi, eski özet ve eski sonuçlandırma v2 şemasında çalıştı. Eski panelde Performans, Fırsatlar ve Dashboard **hatasız**. |
| Geri dönüş 2. seviye | v2 tabloları (`defter_olay`, `tahmin_degerlendirme`) silindi; diğer tablolar aynı. Eklenen boş sütunlar zararsız kalır. |
| Geri dönüş 3. seviye | Yedek geri kondu: integrity **ok**, göç öncesiyle **birebir aynı**, yapı v1 |
| Canlı kontrol (sınama sonrası) | Canlı DB'de v2 sütunu ya da tablosu yok; tahmin 2, sonuç 0; v2 yedeği yok; canlı klasördeki kod s1 |

Birim testinde de sınandı (`GocV2`): v1 şemalı, kullanıcı verili DB → yedek, v2 sütunları, eski satır aynı,
tetikleyici korunuyor, ikinci açılışta tekrar yok.

## F6. Testler

| Komut | Sonuç |
|---|---|
| `python run_offline.py` (başlangıç, main 60ff0b2) | **540 test OK**, ağ 0 |
| `python -m unittest tests.test_faz1_dogrulama` (düzeltme öncesi) | 16 test: **15 başarısız/hata, 1 geçti** (eşzamanlılık) |
| `python -m unittest tests.test_faz1_dogrulama tests.test_defter` (düzeltme sonrası) | **35 test OK** |
| `python -m unittest tests.test_panel_flows…test_faz1_ledger_panel_and_reruns_do_not_duplicate` | OK |
| `python -m unittest tests.test_panel_flows…test_faz1_ledger_failure_visible_in_panel` | OK |
| `python run_offline.py` (son, `faz1-dogrulama`) | **559 test OK**, ağ 0. Log: `tum_testler_faz1_dogrulama.log` |

Yeni ve korunan kabul kriterleri testlerle:

1. **Ayrı kavramlar:** `test_own_frozen_levels…`, hazır fırsat ve sanal işlem tablolarına dokunulmuyor.
2. **Değiştirilemezlik:** tahmin, sonuç, değerlendirme ve olay tabloları.
3. **Tekrar ve eşzamanlılık:** rerun, yeniden analiz ve eşzamanlı yazma → tek satır.
4. **Yeni plan → yeni sürüm.**
5. **Dondurulmuş seviyeler.**
6. **Açık tahmin metrik dışı;** veri eksik metrik dışı.
7. **Yalnız tahmin anındaki bilgi:** geç kayıt ve sonradan eklenen hariç.
8. **Aynı mumda belirsizlik:** SL önce sayılır ve işaretlenir.
9. **Bağımsız gün:** 40 sonuç / 1 gün → "karar verilmez".
10. **Model, kural ve eşikler:** dokunulmadı. Diff'te `ready.py` seçim kodu, `tradeplan.py`, `tp1_v1.json` ve
    `analyzer.py` yok.

## F7. Canlıda henüz doğrulanmayanlar

- **Bu düzeltmeler (s2, v2 şeması) canlıda değil.** Canlı hâlâ s1 kuralıyla çalışıyor. Bu akşamki analiz BAHKM ve
  ENERY için s1 sonuç yazabilir; örneğin giriş günü SL gerçekleşirse MAE s1 yöntemiyle yazılır. s2 canlıya
  alınınca bu satırlar **değiştirilmez**; ayrı s2 değerlendirmesi eklenir ve ölçüm onu kullanır.
- **Gerçek sonuçlanma döngüsü canlıda henüz görülmedi:** girişsiz ya da açık pozisyon, TP, SL, süre dolması.
- **Canlı veritabanında v2 göçü yapılmadı.** Onayla ve elle yedekle yapılacak.

## F8. FAZ 1 kabulü için kalan işler

1. **Kullanıcı onayı:** `faz1-dogrulama` dalının canlıya alınması. Adımlar:
   - Halley'i kapat,
   - elle yedek al,
   - göçü tek süreçte kontrollü çalıştır,
   - önce/sonra özetleri karşılaştır,
   - Halley'i başlat.
2. **Canlıda gerçek döngü:**
   - akşam analizi → sonuçlandırma: girişsiz ya da açık,
   - eski (s1) sonuç varsa s2 değerlendirmesinin eklenmesi,
   - yeni tahminlerin sözleşmeli (s2) yazılması,
   - panel ile veritabanının eşleşmesi.
3. Bu kanıtlarla FAZ 1 kabul raporu. **Karar kullanıcıda.**
4. **Ortam notu:** Gece uyku modu Halley'i ve bekçileri durdurdu (Ek E4). Kabul döngüsü için bilgisayarın açık kalması
   gerekiyor.

Faz sırası korunuyor:

1. Defter ve kabul (sürüyor)
2. Portföy simülatörü
3. Metrikler, MAE/MFE ve veri
4. Strateji × rejim
5. 5/10 günlük hedefler
6. Bozulma uyarıları ve hız
7. Vadeler

---

# EK G (16.11.2026) — FAZ 1 canlıya geçiş: ön kontrol notu (hedef tanımı uyumsuzluğu)

**Hedef tanımı uyumsuzluğu (panel ve rapor):**

- **Eski tanım:** Etkin model `tp1_v1`, eski etiketle eğitildi. Bu etikette doğrudan TP2 açılışı y=0 sayılıyordu.
  Eğitim planlarının %0,26'sı (34.665 planda 91) bu durumda.
- **Yeni tanım:** Canlı ölçüm (kural s2) doğrudan TP2 açılışını TP1'e ulaşmış sayar.
- **Sonuç:** Canlı sonuçlar, modelin tarihsel ölçüleriyle (isabet 0,605 / 0,612; en yüksek %20 için +0,17 R) doğrudan
  eşdeğer değildir.
- **Nerede açıklanıyor:** Panelde her zaman görünen not: `defter.ETIKET_UYUMSUZLUGU`, Performans → Model canlı
  performansı. Test: `test_faz1_ledger_panel_and_reruns_do_not_duplicate`.
- **Model:** Yeniden eğitilmedi; etkin model değişmedi.

**Eksik sözleşmeli sonuçlar:** Maliyet ya da kural sözleşmesi olmayan eski tahminler, "kural eksik · maliyet eksik"
grubunda kalır. Tam bilgili yeni tahminlerle aynı performans grubunda birleşmez (Ek F-C; test
`test_missing_contract_is_shown_not_guessed`; canlı kopyada BAHKM ve ENERY bu grupta). Yeni değerlendirme bu bilgiyi
uydurmaz; kullanılan maliyetin kaynağı sonuç satırına yazılır.

Geçiş ayrıntıları ve kanıtları aşağıdaki bölümlerde.

## G1. Canlıya geçiş (16.11.2026)

| | |
|---|---|
| Canlıya alınan commit | `cb74a3b` (dal `faz1-dogrulama`; `a19593a` + hedef tanımı uyumsuzluğu notu) |
| Önceki canlı sürüm | `main` `60ff0b2` (kod dosyaları canlıyla birebir; yalnız iki belge dosyası farklıydı) |
| Fark kapsamı | `app.py`, `bist_haber/db.py`, `bist_haber/defter.py`, `bist_haber/journal.py` (yalnız `tp1_hedefi` alanı), `arastirma/asama6/etiketle.py`, testler, belgeler. **Değişmeyenler:** `ready.py`, `tradeplan.py`, `entries.py`, `signals.py`, `tp1_model.py`, `modeller/`, `analyzer.py`, `ai_service.py`, `watchdog.py`, `pipeline.py`. |
| Testler (canlıya alınan kod) | `run_offline.py` → **559 test OK**, ağ 0 (`tum_testler_etiket_notu.log`). İlgili 37 test OK. Commit'e testten sonra eklenen yalnız rapor metnidir. |
| Etkin model parmak izi | `tp1_v1.json` SHA-256 `09f8e5e0b279372663f43d293f6aedbce5a266b7578b6f01dd9954834806feb6`. Geçiş öncesi ve sonrası aynı. `aktif.txt` yok. |
| Durdurma öncesi | Bugünün sabah kontrolü ve açılış kontrolü tamamdı (`hazir_durum.json`: sabah_gunu ve acilis_gunu 16.11). Analiz yoktu (`analiz_durumu.json` yok). `bist_haber.db-*` yazma günlüğü yoktu. |
| Durdurma | 10:45:11 (Halley ve okuyucu). Durdurma sonrası da yazma günlüğü yok. |
| Kod yedeği | `data/yedek/kod_60ff0b2_20261116_104552` (143 dosya; `.env` ve veri hariç). Ayrıca git `60ff0b2`. |
| Veritabanı yedeği (elle) | `data/yedek/bist_haber_20261116_104552_faz1_v2_oncesi.db`: integrity **ok**, yedek = canlı |
| Göç | 10:46:13–10:46:17, tek süreç, canlı klasördeki yeni kodla. Sonuç `guncellendi_v2`. Otomatik yedek `bist_haber_20261116_104613_tahmin_defteri_v2_oncesi.db` (integrity **ok**). |
| Önce/sonra koruma | **22/22 tablo birebir aynı** (169.093 satır; tahmin ve tahmin_sonuc için v1 sütunları). BAHKM ve ENERY v1 sütun özeti `d5d7973ca0bbe41e`, önce = sonra. Eski tahminlerin yeni alanları boş: (1, BAHKM, None×4), (2, ENERY, None×4). |
| Koruma tetikleyicileri | Canlıdan salt-okunur okundu: 8 tetikleyici (tahmin, tahmin_sonuc, tahmin_degerlendirme, defter_olay; güncelleme ve silme), hepsi `RAISE(ABORT`. Deneme canlının o anki **kopyasında** yapıldı: satır olan tablolarda 8/8 işlem reddedildi; kopya silindi. Canlıya yazılmadı. |
| Yeniden başlatma | 10:47:03; sağlık OK; 2 okuyucu süreci. Göç tekrarlanmadı (v2 yedeği tek). Kesinti ~2 dk. |

## G2. Geçiş sonrası kontroller (16.11 10:47–10:51)

| Kontrol | Sonuç |
|---|---|
| Panel | Performans hatasız. "Hedef tanımı uyumsuzluğu" notu görünüyor. Sürüm grubu "tp1_v1 · özellik 97b3f4 · parametre 22b983 · kural eksik · maliyet eksik (2 tahmin)". Sayılar: Tahmin 2, Sonuçlanan 0, Açık 2, Veri eksik 0, Giriş olmadı 0, İptal/yerini aldı 0, Aynı mum 0. Güven "çok az örnek, karar verilmez". "Dönem dışı karşılaştırma: mevcut değil" notu görünüyor. |
| Panel = veritabanı | Veritabanında tahmin 2, sonuç 0, değerlendirme 0, olay 0, açık 2. Panelle **eşleşiyor**. |
| Eski tahminler | Değişmedi: v1 sütun özeti aynı. Sözleşmesiz oldukları için "kural eksik · maliyet eksik" grubunda; yeni tahminlerle birleşmez. |
| Sayfa yenileme | 3 tam yenilemeden sonra sayılar ve özet aynı (2 / 0 / 0 / 0). |
| Model, kurallar, eşikler | Model parmak izi aynı; kural ve seçim dosyaları farkta yok. |
| Yeni tahminlerde sözleşme alanları | **Henüz canlıda gözlenmedi:** geçişten sonra yeni hazır fırsat yazılmadı. İlk yeni tahminler bu akşamki analizde oluşacak; kural s2, komisyon, kayma, protokol alanları dolu olmalı. Testte doğrulandı (`test_costs_frozen_at_prediction_time`). |
| Kayıt hatası ve kapsam uyarısı | Canlıda hata yok; kapsam 2/2. Uyarının çalışması panel testinde doğrulandı (`test_faz1_ledger_failure_visible_in_panel`). Canlıda hata zorla üretilmedi. |
| Açık / veri eksik / girişsiz / tamamlanmış | Şu an 2 açık. 16.11 fiyatı akşam analizinde inecek; ayrım o zaman gerçek veride görülecek. |
| Eski sonuçların korunması, ayrı değerlendirme | Canlıda s1 sonucu yok, bu yüzden ayrı değerlendirme oluşmadı. Test: `test_s1_row_kept_and_s2_evaluation_added`. |

## G3. Uyku olayı ve izleme

- **Olay:** 16.11 01:15 uykusu boşta kalma süresinden değil, kullanıcının bilgisayarı kapatmasından oldu (kullanıcının
  bildirimi).
- **Windows kaydı:** Kernel-Power 187: "kullanıcı modu işlemi SetSuspendState çağırdı". Güç planı (salt-okunur): uykudan
  önce bekleme prizde ve pilde 0 (hiçbir zaman). Güç ayarlarına dokunulmadı.
- **İzleme:** Salt-okunur iki bekçi kuruldu:
  - bu akşam (`dongu_aksam_20261116.txt`, en geç 23:30),
  - yarın sabah (`dongu_sabah_20261117.txt`, en geç 10:30).

  Bekçiler bu oturuma bağlıdır; bilgisayar kapanır ya da oturum biterse onlar da durur. Asıl kanıt Halley'in kendi
  zaman damgalı kayıtlarıdır (`watch_runs`, `tahmin`, `tahmin_sonuc`, `tahmin_degerlendirme`, `defter_olay`); bekçi
  durursa sonradan okunabilir. Bekçi betiği bugünkü sabah çalıştırmasıyla denendi ve hatasız rapor üretti.
- **Döngünün gerçekleşme koşulu:** Bilgisayar açık ve Halley çalışıyor olmalı:
  - akşam analizi kapanıştan sonra (~18:25),
  - sabah kontrolü 08:30.

## G4. Geri dönüş durumu

| Seviye | Yöntem |
|---|---|
| 1 | Önceki kod (`kod_60ff0b2_…` ya da git `60ff0b2`) canlı klasöre konur. Eski kod v2 şemasıyla çalışır (kopyada sınandı). |
| 2 | `DROP TABLE defter_olay; DROP TABLE tahmin_degerlendirme;` Eklenen boş sütunlar zararsız kalır (kopyada sınandı). |
| 3 | Elle yedek geri konur. **Uyarı:** Geçişten sonra yeni kayıtlar oluştuysa (yeni haberler, tahminler, sonuçlar) doğrudan geri yükleme onları kaybettirir. Bu durumda önce 1. ve 2. seviye tercih edilir. |

## G5. Kabul durumu

**FAZ 1 henüz kabule hazır değil.** Gerekçe: geçiş ve geçiş sonrası kontroller başarılı, ama aşağıdakiler **canlıda
henüz gözlenmedi**:

- yeni (s2, sözleşmeli) tahmin kaydı,
- gerçek sonuçlandırma (girişsiz, açık ya da tamamlandı),
- akşam → sabah döngüsü.

Bu kanıtlar akşam analizi ve yarın sabahki kontrolden sonra eklenecek.
