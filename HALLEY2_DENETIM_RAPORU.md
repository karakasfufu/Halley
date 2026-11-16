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

---

# EK H (16.11.2026) — FAZ 2 tamamlama raporu: teknik plan evreninin portföy backtesti (araştırma)

> **FAZ 2 kabul notu:** FAZ 2'nin geçerli ana sonucu **Ek H10**'dadır (kabul edilen sürüm `6d7f5d5`, önceden limit emir modeli, kural s3). Bu bölüm ile Ek H2–H4'teki rakamlar ya hatalı gerçekleşme varsayımı (s2: stop altı yapay kâr) ya da teorik seçim (açılışı görüp yerine aday) içerir; **ana sonuç olarak kullanılmaz**, yalnız tarihçe için korunur.

**Kapsam:** Yalnız portföy bazlı backtest simülatörü, araştırma ortamında.

- Canlı koda, kullanıcı verisine, etkin modele ve canlı veritabanına dokunulmadı.
- Model eğitilmedi; müşteri güncellemesi yayımlanmadı; FAZ 3'e geçilmedi.
- Canlıya alma bu fazın konusu değil; simülatör araştırma betiğidir.

> **Adlandırma:** 5 yıllık geçmişte yapay zekâ haber puanı yoktur. Sonuçlar **"teknik plan evreninin portföy
> backtesti"**dir; canlı, haberli hazır fırsat listesinin geçmiş performansı **değildir**.

## H1. Dal, commit, dosyalar

| | |
|---|---|
| Başlangıç | `main` @ `6a95652` (canlıdaki sürüm `cb74a3b` + rapor). Çalışma ağacı temiz. |
| Dal | `faz2-portfoy`. Commit'ler: `f410835` (simülatör + 13 test + etiketlemeye seviyeler), `246aae6` (takvim düzeltmesi + test). Simülasyon `246aae6` ile, temiz ağaçta çalıştı (`kayit.json`: `calisma_agaci_kirli: false`). |

| Dosya | Durum |
|---|---|
| `arastirma/asama6/portfoy.py` | **YENİ:** simülatör (`simule`, `metrikler`, `siralama_anahtari`, `evren_suzgeci`, `takvim_olustur`, CLI) |
| `tests/test_portfoy.py` | **YENİ:** 14 test |
| `arastirma/asama6/etiketle.py` | Plan satırına karar anında bilinen mutlak seviyeler eklendi: kapanış, giriş, SL, TP1, TP2, azami, teknik skor. Etiket tanımı değişmedi. |
| `arastirma/asama6/sonuclar_faz2/<evren>/` | **YENİ:** `kayit.json` ve dönem başına sermaye eğrisi, işlemler, sonda açık pozisyonlar (CSV; 220 KB; gizli bilgi yok) |

Canlı kod dosyalarında **değişiklik yok**: `bist_haber/*`, `app.py`.

## H2. Tek kaynak: yeniden kullanılan parçalar

Simülatör kuralları **ikinci kez kodlamaz**:

| İş | Kullanılan kod |
|---|---|
| Tek işlemin giriş/çıkışı, TP1'de yarı satış, stopun girişe çekilmesi, TP2/SL/30 gün | `journal.evaluate` |
| Riske göre adet | `journal.position_size` |
| Sektör | `sectors.sector_of` |
| Aynı mumda TP/SL belirsizliği | `defter.belirsiz_gunler` |
| Fırsat sıralaması | Canlı `ready.select` anahtarı (`ready.RISK_ORDER`; haber puanı bu evrende 0). Test, `ready.select` ile aynı sırayı verdiğini doğruluyor. |
| Evren eşikleri | `ready.MIN_TECH`, `ready.MIN_TECH_ONLY` |

Kendi bağımsız kopyası olan tek kural, TP1 satış fiyatıdır: açılış ≥ TP1 ise açılış, değilse TP1. Bunun sebebi,
`journal.evaluate`'in açık pozisyonda bacak fiyatı döndürmemesidir. Pozisyon kapanınca journal'ın kendi bacak fiyatıyla
karşılaştırılır; uyuşmazsa simülasyon hata verip durur. Bu sayede ayrışma sessiz kalamaz. Tüm koşularda bu kontrol
hatasız geçti.

## H3. İşlem sırası, maliyet ve risk kuralları

**Gün d için sıra:**

1. **Girişler (d açılışı):** Adaylar, sinyal günü bir önceki işlem günü (d−1) olan planlardır. Karar yalnız d−1
   kapanışında bilinenlerle verilir:
   - sıralama anahtarı,
   - d−1 sonu özsermaye (adet hesabı için),
   - d−1 sonu nakit,
   - d−1 sonu açık pozisyonlar ve açık risk.

   d günü kapanan pozisyonun nakdi ve yeri d girişlerinde **kullanılmaz** (açılıştaki boşluk satışı dahil).
2. **Çıkışlar (d içinde):** Her açık pozisyon `journal.evaluate` ile **yalnız d dahil o güne kadarki mumlarla**
   değerlendirilir. O gün oluşan satış bacakları d gününde nakde yansır. Nihai sonuç önceden hesaplanmaz.
3. **Gün sonu:** özsermaye = nakit + Σ kalan adet × son bilinen kapanış (gerçekleşmemiş kâr/zarar dahil).

**Aday elemesi (sırayla):**

1. aynı hissede açık pozisyon,
2. giriş günü fiyatı yok,
3. açılış > azami giriş (canlı kural),
4. pozisyon sınırı,
5. sektör sınırı,
6. `position_size` ile adet (0 → atla),
7. **nakit sınırı:** son adet = min(adet, ⌊kullanılabilir nakit / (açılış × (1 + (k+s)/200))⌋); 0 → "nakit yetersiz",
8. **toplam risk sınırı:** son adetle.

Eşitlikte bağlayıcı kural: hisse kodu, sonra tür (deterministik).

**Sıralama:** (risk sırası, −(teknik skor + 2·min(haber, 5) + min(r/g, 4)), hisse, tür). Model olasılığıyla sıralama
**yapılmadı**: uygun dönem dışı tahmin kaydı yok ve bu fazda model eğitilmez.

**Maliyet:** Komisyon (%0,20) ve kayma (%0,10) **alış + satış toplamıdır**.

- Alışta: adet × giriş × (k+s)/200.
- Her satış bacağında: satılan adet × **giriş fiyatı** × (k+s)/200.
- Toplam = adet × giriş × (k+s)/100. Bu, `journal.evaluate` ve `position_size` ile aynı. İki kez düşülmez.
- Satış bacağının giriş fiyatı üzerinden hesaplanması, tekil işlem sonuçlarıyla birebir mutabakat içindir.

**Risk:**

- **Aday riski** = adet × ((plan girişi − SL) + plan girişi × (k+s)/100). `position_size` ile aynı.
- **Açık pozisyon riski** = kalan adet × max(0, giriş fiyatı − güncel stop) + kalan adet × giriş fiyatı × (k+s)/200.
  TP1 sonrası stop girişe çekildiği için yalnız kalan satış maliyeti kalır.
- **Toplam risk sınırı:** d−1 sonu özsermayenin %6'sı.

**Kısmi satış:** TP1'de ⌊adet/2⌋ satılır, kalan son çıkışta. Tek adette TP1 satışı olmaz.

**Sektör:** Ana sektör başına en fazla 2 pozisyon. Bilinmeyen sektör tek bir "bilinmiyor" kovasında aynı sınıra
tabidir. Bu evrende sektörü bilinmeyen hisse **0**.

**Simülasyon sonu:** Açık pozisyonlar son bilinen kapanışla değerlenir ve ayrı listelenir. Kâr faktörü ve kazanma oranı
gibi kapanmış işlem metriklerine **girmez**; özsermaye eğrisine gerçekleşmemiş kâr/zarar olarak girer.

**Eksik fiyat:** Pozisyonun o gün mumu yoksa son bilinen kapanış kullanılır ve eksik gün sayılır.

**Ayarlar (önceden tanımlı; Ek A6 önerisi; sonuçlara bakılarak değiştirilmedi):**

| Ayar | Değer |
|---|---|
| Başlangıç sermayesi | 100.000 TL |
| İşlem başına risk | %1 |
| Eşzamanlı pozisyon | en fazla 5 |
| Toplam açık risk | en fazla %6 |
| Ana sektör başına pozisyon | en fazla 2 |
| Maliyet | %0,2 + %0,1 |

## H4. Veri, evren, dönemler

- **Plan evreni:** `etiketle.py` (canlı kod fonksiyonları) ile araştırma veritabanından **salt-okunur** üretildi
  (`planlar_seviyeli.csv`). 45.737 plan, 2022-11 … 2026-11.
  - Önceki `etiket3.csv` 46.053 plandı. Fark 316 plan.
  - Muhtemel neden: arada eklenen sıfır hacim düzeltmesi (`technical.py`, 15.11) bazı işlem görmeyen hisseleri
    eliyor. **Doğrulanmadı.**
- **Evrenler (önceden tanımlı):**

  | Evren | Tanım | Plan | Hisse |
  |---|---|---|---|
  | `canli_ortak` | risk ≠ yüksek, teknik skor ≥ 5 (`ready.MIN_TECH`) | 36.081 | 584 |
  | `yalniz_teknik` | risk ≠ yüksek, teknik skor ≥ 7 (`ready.MIN_TECH_ONLY`) ve yükseliş trendi | 20.457 | 574 |

- **Fiyat:** Araştırma veritabanı (`arastirma_5y.db`, 321 MB, son fiyat 2026-11-13; salt-okunur).
- **Takvim:** Hisse mumlarının birleşimi. XU100 verisinde 2023-12-25, 2024-12-25 ve 2025-12-25 **yok**, ama o günler
  512–593 hisse işlem görmüş (H7).
- **Dönemler:**
  - son 12 ay: 2025-11-14 … 2026-11-13 (251 işlem günü),
  - 2024: 2024-01-02 … 2024-12-31 (250 gün).

  Her dönem 100.000 TL ile ayrı başlar.
- **Yeniden üretim:**
  `python arastirma/asama6/portfoy.py <repo> <arastirma_5y.db> <planlar_seviyeli.csv> <çıktı> --evren <ad>`.
  `kayit.json` şunları içerir:
  - ayarlar ve dönemler,
  - commit (`246aae65…`) ve kirli/temiz bayrağı,
  - Python sürümü,
  - plan dosyasının SHA-256'sı, plan sayısı, tarih aralığı,
  - veritabanı boyutu ve son fiyat günü,
  - XU100'de olmayan günler,
  - sektörü bilinmeyen hisseler.

## H5. Sonuçlar

> **Düzeltme notu (16.11, Ek H4):** Bu bölümün rakamları **hatalı bir gerçekleşme varsayımı içerir**: stopun altında açılan alışlarda alış günü satışı stop fiyatından yazılmış, yapay kâr oluşmuştu. Rakamlar kayıt için olduğu gibi korunmuştur; düzeltilmiş sonuçlar Ek H4'tedir.

Rakamlar geçmiş veri simülasyonudur, gelecek garantisi değildir; **haber şartı yoktur**.

| | canli_ortak · son 12 ay | canli_ortak · 2024 | yalniz_teknik · son 12 ay | yalniz_teknik · 2024 |
|---|---|---|---|---|
| Bitiş özsermayesi (TL) | 77.270 | 135.873 | 75.290 | 125.911 |
| Toplam getiri | **−%22,7** | **+%35,9** | **−%24,7** | **+%25,9** |
| Azami düşüş | −%34,1 (dip 2026-10-27) | −%15,2 | −%39,3 | −%15,2 |
| En uzun düşüş süresi (gün) | 196 | 116 | 184 | 81 |
| Sharpe / Sortino (yıllık) | −1,10 / −1,45 | 1,49 / 2,19 | −1,14 / −1,54 | 1,22 / 1,79 |
| Kapanan işlem | 136 | 105 | 141 | 110 |
| Kazanma oranı | %27,9 | %39,0 | %26,2 | %36,4 |
| Kâr faktörü | 0,72 | 1,34 | 0,76 | 1,24 |
| Ortalama R | −0,19 | +0,26 | −0,19 | +0,18 |
| Beklenen net / işlem (TL) | −185 | +270 | −180 | +189 |
| Ortalama kazanç / kayıp (TL) | 1.692 / −913 | 2.707 / −1.291 | 2.186 / −1.022 | 2.711 / −1.252 |
| En uzun ardışık kayıp | 14 | 7 | 19 | 6 |
| Ortalama işlem günü | 8,8 | 11,3 | 8,4 | 10,9 |
| Ortalama açık pozisyon | 4,4 | 4,6 | 4,2 | 4,6 |
| Sonuç dağılımı (SL / TP2 / başabaş / süre doldu) | 104 / 14 / 9 / 9 | 64 / 23 / 4 / 14 | 108 / 16 / 9 / 8 | 70 / 25 / 6 / 9 |
| Sonda açık pozisyon / gerçekleşmemiş (TL) | 5 / +2.552 | 5 / +7.643 | 2 / +705 | 5 / +5.253 |
| Aynı mumda TP/SL belirsiz işlem | 0 | 0 | 0 | 0 |
| Nakitle küçültülen alış | 16 | 7 | 12 | 6 |

**Muhasebe denkliği** (özsermaye değişimi = kapanan net + açık pozisyon katkısı). Kalan fark işlem başına neti 2
basamağa yuvarlamaktan gelir:

| Simülasyon | Kalan fark (TL) |
|---|---|
| canli_ortak · son 12 ay | −0,04 |
| canli_ortak · 2024 | +0,02 |
| yalniz_teknik · son 12 ay | +0,06 |
| yalniz_teknik · 2024 | −0,01 |

**Sermaye eğrisi (canli_ortak, ay sonu, TL; günlük eğri `*_egri.csv`):**

| Dönem | Ay sonu özsermayeleri |
|---|---|
| son 12 ay | 2025-11 97.772 · 12 101.272 · 2026-01 112.977 · 02 102.418 · 03 98.020 · 04 97.568 · 05 100.799 · 06 100.509 · 07 94.377 · 08 93.020 · 09 84.760 · 10 76.329 · 11 77.270 |
| 2024 | 01 104.300 · 02 117.156 · 03 113.836 · 04 119.118 · 05 122.356 · 06 131.773 · 07 135.845 · 08 124.268 · 09 129.976 · 10 126.920 · 11 124.498 · 12 135.873 |

**Atlanan fırsatlar (nedenlere göre):**

| Neden | ortak · 12 ay | ortak · 2024 | teknik · 12 ay | teknik · 2024 |
|---|---|---|---|---|
| Pozisyon sınırı | 6.454 | 6.956 | 3.529 | 3.810 |
| Açılış azami girişin üstünde | 1.112 | 1.167 | 613 | 695 |
| Zaten açık pozisyon (aynı hisse) | 271 | 225 | 183 | 165 |
| Sektör sınırı | 54 | 41 | 43 | 33 |
| Giriş günü fiyat yok | 0 | 21 | 0 | 14 |
| Nakit yetersiz / toplam risk / 0 adet | 0 | 0 | 0 | 0 |

**Tek işlem ↔ portföy farkı:**

| | Evrendeki TÜM girilen planlar (tekil, eşit ağırlık) | Portföyün seçtikleri |
|---|---|---|
| canli_ortak · son 12 ay | n = 6.831, ort. R **+0,02** | n = 136, ort. R **−0,19** |
| canli_ortak · 2024 | n = 7.346, ort. R +0,14 | n = 105, ort. R +0,26 |
| yalniz_teknik · son 12 ay | n = 3.859, ort. R +0,04 | n = 141, ort. R −0,19 |
| yalniz_teknik · 2024 | n = 4.124, ort. R +0,15 | n = 110, ort. R +0,18 |

**Okuma (ölçüm, öneri değil):**

- **Bağlayıcı sınır:** Her gün beşten çok aday var. Bu yüzden portföyü fiilen **sıralama kuralı** belirliyor
  (pozisyon sınırı en sık neden). Nakit ve toplam risk sınırı neredeyse hiç devreye girmedi.
- **Son 12 ay:** Canlı sıralama kuralının seçtiği işlemler, evrenin ortalamasının belirgin altında kaldı. Düşüş
  özellikle 2026 yazından sonra derinleşti.
- **2024:** Tersi oldu; seçilenler ortalamanın üstünde.
- **Sonuç:** Kuralın değeri döneme göre işaret değiştiriyor. **Kural ya da ayar bu sonuçlara göre değiştirilmedi.**
  Strateji × rejim incelemesi FAZ 4'ün konusu.
- **Tür dağılımı:** Seçilen işlemlerin hepsi "kırılım" ya da "geri çekilme". Sıralama anahtarı "destekten tepki" ve
  "mevcut fiyat" türlerini bu evrende ilk beşe sokmadı.

## H6. Testler

| Komut | Sonuç |
|---|---|
| `python -m unittest tests.test_portfoy` | **14 test OK** |
| `python run_offline.py` (ağ engelli, `246aae6`) | **Ran 573 tests … OK**, ağ denemesi 0 (`tum_testler_faz2_son.log`). Önceki 559 + 14. |

İstenen senaryolar:

1. **Elle hesaplanmış portföy:**
   - 10.000 TL, %1 risk, giriş 100, SL 95 → adet 18.
   - Nakit 8.197,30 → 9.185,95; özsermaye 9.997,30 → 10.175,95 → 10.264,60.
   - Brüt 270, maliyet 5,40, net 264,60. Journal net %'siyle aynı.
2. **Sınırlar ayrı ayrı:**
   - pozisyon sınırı,
   - toplam risk sınırı,
   - sektör sınırı (bilinmeyen kova dahil; farklı sektörde sınır yok),
   - nakit: önce `position_size` nakit sınırı 99 adet, sonra "nakit yetersiz"; %4 riskte ikinci aday 75 yerine 24
     adede küçüldü,
   - işlem riski: adet `position_size` ile.
3. **Kısmi satış:** Açık risk 92,70 → TP1 sonrası 1,35 (yalnız kalan satış maliyeti); nakit doğru.
4. **Gelecek fiyatlar değiştirildi** (D4 ve sonrası ×1,5): D1–D3 gün sonları, o güne kadarki girişler, adetler ve
   atlananlar **aynı**.
5. **Plan ve hisse giriş sırası karıştırıldı:** eğri, işlemler ve atlananlar **aynı**.
6. **Aynı gün:** AAA d açılışında stopta kapanırken BBB'nin d alışı yalnız d−1 sonu nakdiyle yapıldı (90 değil 9 adet).
7. **Kısıtsız ve sabit 100 adette tekil işlemlerle mutabakat:** sonuç, çıkış günü, bacak fiyatları ve adetleri
   journal'la **birebir**; net TL farkı < 0,006 (yuvarlama).
8. **Raporlama:**
   - simülasyon sonunda açık pozisyon (gerçekleşen ve gerçekleşmemiş ayrı),
   - eksik fiyat günü (son kapanışla değerleme, sayılıyor),
   - aynı mumda TP/SL → SL + belirsiz işaretli.
9. **Takvim:** XU100'de olmayan gün takvimden düşmüyor. Yalnız XU100 takvimi kullanılırsa sıra koruması hata veriyor.
10. **Canlı sıralama:** Simülatörün sırası `ready.select` ile aynı.
11. **Metrikler:** Bilinen eğride azami düşüş −%10, kâr faktörü 1,0, ardışık kayıp 2.

**Geliştirme sırasında bulunup düzeltilenler:**

- **Kontrol sırası:** Toplam risk kontrolü nakit küçültmesinden önce yapılıyordu; zaten küçülecek aday büyük riskle
  eleniyordu. Artık son adetle yapılıyor.
- **TP1 fiyatı yuvarlaması:** Journal'la aynı 4 basamak.
- **Takvim:** XU100'deki 25 Aralık eksikleri, gerçek veri koşusunda sıra koruması tarafından yakalandı (H7).

## H7. Bilinen veri eksikleri ve sınırlamalar

1. **Haber şartı yok:** Canlı haberli hazır fırsat listesi bu evrenle eşdeğer değildir.
2. **Hayatta kalma yanlılığı:** Evren bugünkü hisselerden kuruldu (584 / 574 hisse); borsadan çıkanlar yok. Sonuçlar
   büyük olasılıkla iyimser.
3. **Takvim:** Yahoo XU100 verisinde 3 adet 25 Aralık eksik. Takvim hisse mumlarından kuruldu ve sorun giderildi;
   başka kaynak kaynaklı eksik gün olabilir.
4. **Günlük mum:** Gün içi sıra bilinmez. Aynı mumda TP/SL kuralı SL'yi önce sayar; bu koşularda 0 vaka çıktı. TP1–SL
   mesafesi genelde birkaç ATR olduğu için seyrek.
5. **Giriş fiyatı:** Gerçek açılış; açılıştaki likidite ve derinlik modellenmedi. Sabit kayma %0,1 (gidiş-dönüş).
6. **Model sıralaması yok:** Dönem dışı olasılık kaydı olmadığından denenmedi.
7. **Kısmi satış yuvarlaması:** Tek adetlerde TP1 payı ⌊adet/2⌋; journal'ın %50 varsayımından küçük sapma (mutabakat
   testi çift adetle).
8. **Plan sayısı farkı:** Önceki etiket dosyasıyla 316 plan fark var; nedeni doğrulanmadı (H4).
9. **Simülasyon ayarları önceden tanımlı ve tek takım.** Duyarlılık analizi (farklı risk ya da pozisyon sayısı)
   yapılmadı; istenirse ayrı onayla ve optimizasyon olarak değil, sağlamlık kontrolü olarak yapılabilir.

## H8. FAZ 1 canlı doğrulamasının güncel durumu (16.11 11:21)

- Canlıda `cb74a3b` çalışıyor; panel sağlıklı.
- **Defter:** 2 tahmin (BAHKM, ENERY; sözleşmesiz eski grup), 0 sonuç, 0 değerlendirme, 0 olay.
- Geçişten sonra yeni çalıştırma olmadı; son çalıştırma bugünkü sabah kontrolü (09:42). Fiyatlar 13.11'e kadar.
- **Bekleyen kanıtlar:**
  - bu akşamki analiz: 16.11 fiyatları, BAHKM ve ENERY sonuçlandırması, yeni s2 sözleşmeli tahminler,
  - yarın sabahki kontrol.

  Salt-okunur bekçiler kurulu (oturuma bağlı). Halley'in zaman damgalı kayıtları her durumda sonradan okunabilir.
- **FAZ 1 kabul edilmedi;** kanıtlar ayrıca raporlanacak.

**Onay beklenen:** FAZ 2'nin kabulü. FAZ 3'e geçiş ayrı onay ister. Simülatör araştırma betiğidir; canlıya alınacak bir
uygulama değişikliği yoktur.


---

# Ek H2 — FAZ 2 ek kontroller: teknik plan evreninin backtesti (16.11.2026)

**Adı:** "teknik plan evreninin backtesti". `kayit.json` içindeki etiket "teknik plan evreninin portföy backtesti";
aynı şeydir. Haber şartı yoktur; canlı haberli hazır fırsat listesinin geçmiş performansı **değildir**.

**Dürüstlük notu:** Simülasyonlar bu kontrol isteğinden **önce** çalıştırılmıştı (Ek H5). Kontroller sonuçlar
görüldükten sonra yapıldı. Hiçbir ayar, eşik, sıralama ya da evren tanımı değiştirilmedi. Aynı ayarlarla yeniden
çalıştırıldığında dört simülasyonun bütün metrikleri `kayit.json` ile **birebir aynı** çıktı (`portfoy_kontrol.py`).

## H2.1 Seçimde sonuç ve model bilgisi kullanılmıyor

- `plan_oku` plan dosyasından yalnız 12 alanı okur: `ticker, tarih, tur, risk, trend, teknik_skor, rr1, giris, sl, tp1,
  tp2, azami`. Bunların hepsi sinyal günü kapanışına kadarki 250 mumdan hesaplanır (`etiketle.py`).
- Dosyadaki sonuç sütunları (`sonuc, y, r, net, gun`), ertesi gün bilgisi (`acilis_bosluk_%`, `ertesi_kilitli`) ve model
  girdileri **okunmaz**. Dosyada model tahmini (olasılık) sütunu hiç yoktur.
- Sıralama: `ready.RISK_ORDER`, ardından −(teknik skor + 2·haber[=0] + min(rr1, 4)), eşitlikte hisse adı ve tür.
- **Test kanıtı:** `test_outcome_columns_never_read`. Sonuç ve model girdisi sütunları ters değerlerle (TP2 yerine
  SL vb.) değiştirildiğinde okunan planlar birebir aynı kaldı ve yalnız bu 12 alanı içerdi. Simülatör seçimi yalnız
  okunan planlardan yapar.
- **Dönemler (kesin tarihler):**
  - son 12 ay: **2025-11-14 … 2026-11-13**. Son fiyat günü 2026-11-13; başlangıç, 365 gün öncesinden (2025-11-13)
    sonraki ilk işlem günü.
  - 2024: **2024-01-02 … 2024-12-31**.

## H2.2 Journal yalnız o güne kadarki fiyatları görüyor

- Her gün d için çıkış hesabı, `journal.evaluate`'e yalnız sinyal gününden sonraki ve **d dahil** mumları verir
  (`upto = sinyal < tarih ≤ d`).
- Girişler d açılışında, yalnız d−1 sonu bilgisiyle yapılır: nakit, özsermaye ve açık risk.
- d günü çıkışından gelen nakit, d günü girişlerinde kullanılmaz.
- **Testler:**
  - `test_truncated_future_identical_up_to_cut`: kesim gününden sonraki fiyatlar silindiğinde o güne kadarki her şey
    aynı kaldı.
  - `test_slot_cash_risk_released_only_on_exit_day`: pozisyon yeri, nakit ve açık risk ancak çıkış günü gün sonunda
    serbest kalıyor; aynı gün açılışındaki alışa yaramıyor.
  - Ek H6'daki "gelecek fiyatlar ×1,5" ve "aynı gün" senaryoları.
- **Gerçek veri kanıtı:** Kısıtsız ve sabit 100 adet modunda canli_ortak işlemlerinin her biri, dönem sonrası dahil
  **tüm gelecek** mumlarla ayrıca `journal.evaluate`'e verildi. Sonuç, çıkış günü ve R **hiçbir işlemde farklı
  çıkmadı**:

  | Dönem | Karşılaştırılan işlem | Uyuşmayan | En büyük net fark |
  |---|---|---|---|
  | son 12 ay | 2.617 | **0** | 0,005 TL (yuvarlama) |
  | 2024 | 2.627 | **0** | 0,005 TL (yuvarlama) |

  Simülatörün kesik penceresi, gelecekteki mumlar görülseydi farklı olacak hiçbir kararı erken vermedi.

## H2.3 Sektör sınıflaması güncel, tarihsel değil

- Kaynak `bist_haber/sektorler.json` (KAP listesi, alındığı gün **2026-11-09**). Geçmişe aynen uygulandı.
- **Sınırlama:** Geçmişte sektör değiştiren ya da sonradan listelenen şirketler bugünkü sektörüyle sayıldı. Sektörü
  bilinmeyen hisseler tek bir "bilinmiyor" kovasında toplandı ve onlara da en çok 2 sınırı uygulandı (`kayit.json` →
  `sektoru_bilinmeyen_hisse`).

## H2.4 Özsermaye = nakit + piyasa değeri (çift sayım yok)

- Gün sonu: özsermaye = nakit + Σ(kalan adet × o günün kapanışı).
- Satılan pay nakde geçer ve kalan adetten düşer; aynı pay iki yerde sayılmaz.
- Maliyetler nakitten bir kez düşer: alışta (adet × dolum × c2), her satışta (satılan adet × giriş dolumu × c2).
- **Test:** `test_equity_identity_and_no_double_counting`. Her gün özdeşlik sağlanıyor; TP1 yarı satışından sonra
  satılan yarı piyasa değerinde yok.
- **Gerçek veri:** Özsermaye değişimi = kapanan net + açık pozisyon katkısı. Kalan fark ≤ 0,06 TL (Ek H5).

## H2.5 Açık risk formülü ve stop boşluğu

**Formül:** Açık risk = Σ [kalan adet × max(0, dolum − stop) + kalan adet × dolum × c2]. Burada c2 = (komisyon +
kayma) / 200 = %0,15, yani tek bacağın maliyeti.

- **TP1'den sonra:** Yarısı satılır ve stop dolum fiyatına çekilir. Fiyat riski sıfırlanır; geriye yalnız kalan payın
  satış maliyeti kalır. Örnek (Ek H6): 92,70 → 1,35.
- **Giriş kontrolü:** Toplam risk sınırı (önceki gün özsermayesinin %6'sı), adayın **planlanan** girişiyle hesaplanan
  riskiyle (adet × [(giriş − SL) + giriş × %0,3]) yapılır.
- **Gerçek veride gün sonu açık riskin önceki gün özsermayesine oranı en çok:**

  | ortak · 12 ay | ortak · 2024 | teknik · 12 ay | teknik · 2024 |
  |---|---|---|---|
  | %5,52 | %5,55 | %5,28 | %5,37 |

  Dördü de %6 sınırının altında.

**Teorik risk aşılabilir.** İki ayrı neden var:

1. **Açılışta boşluk:** Fiyat stopun altında açılırsa satış açılıştan olur ve kayıp hesaplanan riskten büyük çıkar.
   - Bu işlemlerin net toplamı: ortak · 12 ay **5 işlem, −6.174 TL**; ortak · 2024 **6 işlem, −12.426 TL**; teknik ·
     12 ay 9 işlem, −13.051 TL; teknik · 2024 5 işlem, −7.502 TL.
   - En kötü örnekler: GOLTS (2026-02-20) **−3,15 R**; TEZOL (2024-05-09) −2,59 R.
   - Test: `test_gap_stop_loss_exceeds_theoretical_risk`.
2. **Planlanan girişin üstünde dolum (yeni tespit, değiştirilmedi):**
   - Adet, canlı paneldeki gibi **planlanan giriş** fiyatıyla `journal.position_size` üzerinden hesaplanıyor. Ama alış
     gerçek açılıştan yapılıyor ve açılış azami girişe kadar yukarıda olabiliyor. Bu durumda stopta kayıp %1'i aşıyor.
   - Planlanan girişin üstünde dolan işlem: ortak · 12 ay **60 / 136**; ortak · 2024 58 / 105.
   - SL işlemlerinde kaybı önceki gün özsermayesinin %1'ini aşan:

     | | SL'de %1'i aşan | En büyük kayıp |
     |---|---|---|
     | ortak · 12 ay | **43 / 104** | %2,31 |
     | ortak · 2024 | 31 / 64 | %2,44 |
     | teknik · 12 ay | 49 / 108 | %2,49 |
     | teknik · 2024 | 33 / 70 | %1,78 |

   - Journal'ın R'si de planlanan risk mesafesine (giriş − SL) göredir. Bu yüzden stopta R genelde −1'in altına iner
     (R < −1,1 olan işlem: ortak 37 / 27).
   - **Not:** Bu, canlı uygulamadaki adet hesabıyla aynı davranıştır. Düzeltme bir **kural değişikliği** olurdu (adedi
     gerçek açılışla yeniden hesaplamak); bu fazda yapılmadı, ayrı karar ister.

## H2.6 Sortino ve kâr faktörü varsayımları

- **Getiri serisi:** Günlük özsermaye eğrisinin basit getirileri. Başlangıç sermayesi ilk nokta; açık pozisyonlar o günün
  kapanışıyla değerlenir.
- **Sortino:** ortalama günlük getiri / aşağı yönlü sapma × √252.
  - Hedef getiri 0, risksiz faiz 0.
  - Aşağı yönlü sapma = √(ortalama(min(r, 0)²)); bütün günlere bölünür, yalnız kayıplı günlere değil.
- **Sharpe:** Örneklem standart sapması (n−1) × √252, risksiz faiz 0. TL bazında, enflasyon ya da mevduat faizi
  düşülmedi.
- **Kâr faktörü:** Yalnız **kapanmış** işlemler üzerinden, maliyet dahil net TL ile: Σ pozitif net / |Σ sıfır ve negatif
  net|. Sıfır net işlem kayıp tarafında sayılır.
- Azami düşüş ve düşüş süresi gün sonu özsermaye eğrisinden ölçülür; gün içi dip dikkate alınmaz.

## H2.7 Dönem sonunda açık pozisyonlar (zorla kapatma yok)

Dönem sonunda pozisyonlar **zorla kapatılmadı**. Son kapanışla değerlenip özsermayeye katıldılar; kapanan işlem
metriklerine (kazanma oranı, kâr faktörü, R) **girmediler**.

**canli_ortak · son 12 ay** (5 pozisyon, gerçekleşmemiş toplam +2.552 TL; hiçbirinde TP1 görülmedi):

| Hisse | Giriş günü | Kalan adet | Gerçekleşmemiş (TL) |
|---|---|---|---|
| DURDO | 2026-10-19 | 1.214 | +509,88 |
| AHGAZ | 2026-10-23 | 293 | +1.007,92 |
| GARAN | 2026-11-05 | 100 | +1.170,00 |
| ACSEL | 2026-11-06 | 90 | −535,50 |
| THYAO | 2026-11-11 | 50 | +400,00 |

**canli_ortak · 2024** (5 pozisyon, gerçekleşmemiş toplam +7.643 TL; hiçbirinde TP1 görülmedi):

| Hisse | Giriş günü | Kalan adet | Gerçekleşmemiş (TL) |
|---|---|---|---|
| AKGRT | 2024-12-02 | 3.726 | +3.651,48 |
| MAVI | 2024-12-03 | 400 | +603,50 |
| DMSAS | 2024-12-23 | 2.828 | +2.658,32 |
| BEYAZ | 2024-12-25 | 993 | +586,95 |
| TRGYO | 2024-12-27 | 456 | +143,16 |

yalniz_teknik için aynı liste `sonuclar_faz2/yalniz_teknik/*_acik_son.csv` içinde: 12 ay 2 pozisyon, 2024 5 pozisyon.

## H2.8 İki dönemin özeti (istenen bütün kalemler)

> **Düzeltme notu (16.11, Ek H4):** Bu bölümün rakamları **hatalı bir gerçekleşme varsayımı içerir**: stopun altında açılan alışlarda alış günü satışı stop fiyatından yazılmış, yapay kâr oluşmuştu. Rakamlar kayıt için olduğu gibi korunmuştur; düzeltilmiş sonuçlar Ek H4'tedir.

| | canli_ortak · son 12 ay | canli_ortak · 2024 | yalniz_teknik · son 12 ay | yalniz_teknik · 2024 |
|---|---|---|---|---|
| Dönem | 2025-11-14 … 2026-11-13 | 2024-01-02 … 2024-12-31 | aynı | aynı |
| Başlangıç → bitiş özsermayesi (TL) | 100.000 → 77.270 | 100.000 → 135.873 | 100.000 → 75.290 | 100.000 → 125.911 |
| Net getiri (maliyet dahil) | **−%22,7** | **+%35,9** | −%24,7 | +%25,9 |
| Azami düşüş | −%34,1 | −%15,2 | −%39,3 | −%15,2 |
| Sortino / kâr faktörü | −1,45 / 0,72 | 2,19 / 1,34 | −1,54 / 0,76 | 1,79 / 1,24 |
| Açılan / kapanan / sonda açık | 141 / 136 / 5 | 110 / 105 / 5 | 143 / 141 / 2 | 115 / 110 / 5 |
| Toplam maliyet (komisyon + kayma, TL) | 7.092 | 6.697 | 7.957 | 7.361 |
| En çok eşzamanlı pozisyon (sınır 5) | 5 | 5 | 5 | 5 |
| En çok aynı sektörde eşzamanlı (sınır 2) | 2 | 2 | 2 | 2 |
| En yüksek açık risk / özsermaye (sınır %6) | %5,52 | %5,55 | %5,28 | %5,37 |

- **Atlanan fırsatlar ve nedenleri:** Ek H5 tablosu (en sık neden pozisyon sınırı).
- **Sermaye eğrisi:** Ay sonu değerleri Ek H5'te; günlük eğri `sonuclar_faz2/<evren>/<dönem>_egri.csv`.
- **Eşzamanlılık ölçümü:** Giriş anında tutulan pozisyonlar (giriş günü ≤ d ≤ çıkış günü) sayıldı. Bu, gün sonu
  sayısından daha sıkı bir ölçüdür.
- **Toplam maliyet:** Kapanan işlemlerin bütün bacakları + açık pozisyonların ödenmiş alış ve TP1 satış maliyeti.

**Tekil işlem mutabakatı (aynı varsayımlar: açılıştan giriş, journal çıkışları, %0,2 + %0,1):**

- **Kısıtsız ve sabit 100 adet modu:** H2.2'deki tablo; 5.244 işlemde uyuşmazlık 0.
- **Evrendeki tüm planlar ile portföyün seçtikleri:** Ek H5. Örnek: son 12 ay ort R +0,02 ile −0,19; 2024 +0,14 ile
  +0,26.
- Kısıtsız modda da "aynı hisse zaten açık" ve "açılış azami girişin üstünde" elemeleri geçerlidir (sırasıyla 4.723
  ve 670 plan, son 12 ay).

**Veri kapsamı, eksikler ve hayatta kalma yanlılığı:** Ek H4 ve H7 geçerli. Özetle:

- Bugün işlem gören 584 / 574 hisse kullanıldı; borsadan çıkanlar yok. Sonuçlar büyük olasılıkla **iyimser**.
- XU100'de 3 adet 25 Aralık eksik; takvim hisse mumlarından kuruldu.
- 2024'te 21 / 14 plan giriş günü fiyatı olmadığı için atlandı.
- Sektör sınıflaması güncel (H2.3).
- Plan sayısında önceki dosyayla 316 fark var; nedeni doğrulanmadı.
- Gün içi sıra bilinmiyor (aynı mumda TP/SL vakası 0).

## H2.9 Değişen dosyalar (dal `faz2-portfoy`)

- `tests/test_portfoy.py`: yeni `GelecegeBakmama` sınıfı, 5 test. Portföy testleri 19 / 19 OK; tam takım (ağ engelli) **578 test OK**, ağ denemesi 0.
- `arastirma/asama6/portfoy_kontrol.py`: yeni, salt-okur gerçek veri kontrolleri. Çıktısı yerel `kontrol.json`;
  repoya konmadı.
- `HALLEY2_DENETIM_RAPORU.md` (bu ek) ve `NOTLAR.md`.
- Simülatör (`portfoy.py`) ve sonuç dosyaları **değişmedi**.

## H2.10 FAZ 1 canlı doğrulaması (ayrı tutuluyor)

- FAZ 1 kanıtları bu raporla karıştırılmadı.
- Bu akşamki analiz ve yarın sabahki kontrol henüz **gözlenmedi**. Gözlenmeyen durum doğrulanmış sayılmadı.
- FAZ 1 kabul edilmedi.

**Onay beklenen:** FAZ 2'nin kabulü. Canlıya alma yok; FAZ 3'e geçilmedi.


---

# Ek H3 — Risk hesabındaki farkın kesinleştirilmesi (16.11.2026, dal `faz2-portfoy`, yalnız araştırma)

**Konumu:** Bu ek **geriye dönük doğrulamadır**. Önceki sonuçlar (Ek H5, H2) görüldükten sonra yapıldı ve **dönem
dışı başarı kanıtı sayılmaz**.

- Orijinal sonuçlar değiştirilmedi: `sonuclar_faz2/*` dosyalarına dokunulmadı. Varsayılan davranışla yeniden
  çalıştırınca dört simülasyonun metrikleri `kayit.json` ile birebir aynı çıktı.
- Canlı kural değişmedi. Parametre optimizasyonu yapılmadı. Senaryolar arasında otomatik seçim yok.

## H3.1 Önceki "sınırlar aşılmadı" ifadesi hangi tanıma dayanıyordu?

1. **İşlem başı %1:** Simülatörde ayrıca denetlenen bir sınır değildi. Adet `journal.position_size` ile **planlanan
   girişe** göre hesaplanır: adet × ((plan girişi − SL) + plan girişi × %0,3) ≤ %1. Gerçek dolumla başlangıç riski
   hiç ölçülmemişti. Ek H2.5'te bunun aşıldığı zaten belirtildi.
2. **Toplam %6 sınırı:** Girişte, adayın **planlanan girişle** hesaplanan riskiyle denetleniyordu. Ek H2'deki
   %5,52 / %5,55 değerleri ise **gün sonu** açık riskiydi: gerçek dolumla, ama o günün çıkışlarından ve TP1 stop
   çekilmesinden **sonra**. Giriş anının ölçüsü değildi.
3. **Yeni ölçü (bu ek):** Giriş anındaki portföy riski, o günün çıkışlarından önce ve gerçek dolumla hesaplandı:
   - yeni pozisyonlar: adet × ((dolum − SL) + dolum × %0,3),
   - eski pozisyonlar: kalan × max(0, dolum − güncel stop) + kalan satış maliyeti.

## H3.2 Gerçek dolumla başlangıç riski ve portföy riski

| | ortak · 12 ay | ortak · 2024 | teknik · 12 ay | teknik · 2024 |
|---|---|---|---|---|
| **Mevcut:** başlangıç riski bütçeyi aşan işlem | **57 / 141** | **48 / 110** | **57 / 143** | **50 / 115** |
| Mevcut: en yüksek başlangıç riski (bütçenin katı) | 1,33 (GSDDE) | 1,37 (DESPC) | 1,33 | 1,37 |
| **Alternatif:** başlangıç riski bütçeyi aşan | **0** | **0** | **0** | **0** |
| Alternatif: en yüksek kat | 0,997 | 0,994 | 0,997 | 0,992 |
| Giriş anı portföy riski en yüksek (mevcut / alternatif) | %5,56 / %4,40 | %5,60 / %4,50 | %5,41 / %4,53 | %5,39 / %4,34 |
| Giriş anında %6'yı aşan gün (iki senaryo) | 0 | 0 | 0 | 0 |

- **Portföy düzeyi:** Gerçek dolum temelinde de %6 sınırı hiç aşılmadı. Gerekçe: adayların çoğu pozisyon sınırına
  takılıyor, risk sınırına değil.
- **İşlem düzeyi:** Mevcut davranışta işlemlerin yaklaşık %40'ında başlangıç riski %1'i aştı (en çok %1,37).

## H3.3 %1'i aşan gerçekleşen kayıpların nedenleri (kapanan işlemler)

**Tanımlar.** L = kayıp, B = bütçe (önceki gün özsermayesinin %1'i).

| Bileşen | Hesap | Anlamı |
|---|---|---|
| P | adet × ((plan girişi − SL) + plan girişi × %0,3) | planlanan kayıp; her zaman P ≤ B |
| E | adet × (dolum − plan girişi) | giriş farkı |
| G | stop bacaklarında satılan × (stop − çıkış fiyatı) | stop altında çıkış |
| C | adet × (dolum − plan girişi) × %0,3 | maliyetin planlanandan farkı |
| K | L − (P + E + G + C) | kalan; tam SL'de ≈ 0 |

**Neden etiketi:** E > 0 ve G > 0 olanlar listelenir. Maliyet yalnız tek başına belirleyiciyse eklenir
(P + E + G ≤ B < P + E + G + C).

| Mevcut davranış | ortak · 12 ay | ortak · 2024 | teknik · 12 ay | teknik · 2024 |
|---|---|---|---|---|
| Kaybı %1'i aşan / kapanan | **43 / 136** | **31 / 105** | **49 / 141** | **33 / 110** |
| Yalnız giriş farkı | 27 | 16 | 27 | 22 |
| Yalnız stop altı çıkış | 4 | 5 | 7 | 2 |
| Giriş farkı + stop altı çıkış | 12 | 10 | 15 | 9 |
| Maliyet belirleyici | 0 | 0 | 0 | 0 |
| Bütçe üstü toplam aşım (L − B, TL) | 5.300 | 8.055 | 7.784 | 5.009 |
| Bileşen toplamı: E / G / C (TL) | 3.864 / 1.973 / 11,6 | 3.552 / 4.516 / 10,7 | 4.615 / 3.524 / 13,9 | 3.991 / 1.091 / 12,0 |

| Alternatif | ortak · 12 ay | ortak · 2024 | teknik · 12 ay | teknik · 2024 |
|---|---|---|---|---|
| Kaybı %1'i aşan / kapanan | **1 / 136** | **4 / 105** | **3 / 141** | **1 / 110** |
| Neden | stop altı çıkış (GOLTS, 2,30 kat) | stop altı 2, giriş farkı + stop altı 2 (TEZOL 1,94 kat) | stop altı 3 | giriş farkı + stop altı 1 |

- Alternatifte P + E + C her zaman ≤ B olur, çünkü dolum azami girişi geçemez. Bu yüzden kalan aşımın **tamamı**
  stop boşluğundan gelir.
- **Maliyetler** hiçbir işlemde aşımın belirleyicisi olmadı. Planlanan maliyet adet hesabında zaten var; fark yalnız
  dolum farkının %0,3'ü kadar.

## H3.4 İki senaryo (aynı dönem, aynı diğer ayarlar)

> **Düzeltme notu (16.11, Ek H4):** Bu bölümün rakamları **hatalı bir gerçekleşme varsayımı içerir**: stopun altında açılan alışlarda alış günü satışı stop fiyatından yazılmış, yapay kâr oluşmuştu. Rakamlar kayıt için olduğu gibi korunmuştur; düzeltilmiş sonuçlar Ek H4'tedir.

**Mevcut:** Adet, planlanan girişe göre hesaplanır. Nakit kontrolü açılış fiyatıyla yapılır. Canlı paneldeki adet
hesabı budur.

**Alternatif — "azami girişle önceden adet":**

- Adet, nakit ayırma ve aday riski **açılıştan önce bilinen azami girişle** hesaplanır.
- **Emir zamanlaması:** Sabah planı açılıştan önce hazır olur. Emir BIST açılış seansına (emir toplama yaklaşık
  09:40–09:55) **azami giriş fiyatından limitli** verilir.
- Açılış fiyatı ≤ azami ise emir açılış fiyatından dolar; > azami ise dolmaz. Bu, canlıdaki "açılış azami girişin
  üstündeyse alma" kuralıyla aynıdır.
- **Fiyat varsayımı:** Dolum = günlük mumun açılış fiyatı (iki senaryoda aynı). Açılış fiyatı adet kararında
  **kullanılmaz**.
- **Doğrulanmayanlar:** Açılış seansında kısmi dolum, derinlik ve Yahoo açılışı ile seans fiyatı farkı modellenmedi.
  Midas'ta açılış seansına limit emir girilebildiği bu çalışmada **doğrulanmadı**; kullanıcının kontrol etmesi
  gerekir.

**Değerlendirilip seçilmeyen yöntem — "fiyatı gördükten sonra işlem":**

- Canlıda açılış 15 dk gecikmeli görülür. Alış o andaki fiyattan olurdu; bu fiyat günlük veride yok.
- Açılıştan alış yaptırmak, açılışı önceden biliyormuş gibi davranmak olur (yasaklanan varsayım).
- Kapanıştan alış ise giriş modelini değiştirir.
- Gün içi veri olmadan dürüstçe test edilemediği için seçilmedi.

| | Mevcut · ortak 12 ay | Alternatif · ortak 12 ay | Mevcut · ortak 2024 | Alternatif · ortak 2024 |
|---|---|---|---|---|
| Bitiş özsermayesi (TL) | 77.270 | 80.252 | 135.873 | 128.914 |
| Net getiri | −%22,7 | −%19,8 | +%35,9 | +%28,9 |
| Azami düşüş | −%34,1 | −%30,3 | −%15,2 | −%12,3 |
| Sortino | −1,45 | −1,51 | 2,19 | 2,18 |
| Kâr faktörü | 0,718 | 0,714 | 1,344 | 1,350 |
| Ortalama R / kazanma oranı | −0,19 / %27,9 | aynı | +0,26 / %39,0 | aynı |
| Kapanan / sonda açık | 136 / 5 | 136 / 5 | 105 / 5 | 105 / 5 |
| Nakitle küçültülen alış | 16 | 0 | 7 | 0 |
| Atlananlar | — | birebir aynı | — | birebir aynı |

| | Mevcut · teknik 12 ay | Alternatif · teknik 12 ay | Mevcut · teknik 2024 | Alternatif · teknik 2024 |
|---|---|---|---|---|
| Bitiş özsermayesi (TL) | 75.290 | 80.408 | 125.911 | 120.187 |
| Net getiri | −%24,7 | −%19,6 | +%25,9 | +%20,2 |
| Azami düşüş | −%39,3 | −%33,3 | −%15,2 | −%12,8 |
| Sortino / kâr faktörü | −1,54 / 0,761 | −1,46 / 0,767 | 1,79 / 1,237 | 1,71 / 1,234 |

**Okuma:**

- Aynı işlemler seçildi; alternatif yalnız pozisyonları küçülttü.
- Risk ayarlı ölçüler (Sortino, kâr faktörü, R) neredeyse aynı kaldı.
- Kötü yılda kayıp ve düşüş azaldı, iyi yılda getiri de azaldı.
- Bu bir performans iyileştirmesi değil, **risk tanımının tutarlılığı** sorunudur.

## H3.5 Stopun altında açılan girişler: mevcut sistem nasıl ele alıyor?

**Kod davranışı (değiştirilmedi):**

- `ready.opening_check` ve `evaluate_all` yalnız "açılış > azami" durumunda girişi iptal eder. **Alt sınır yok:**
  açılış SL'nin altında olsa da alış yapılmış sayılır.
- `journal.evaluate`, gerçek giriş kaydında alış gününü "gün içi sıra bilinmez" kabul eder. O gün en düşük fiyat ≤ SL
  ise satışı **SL fiyatından** yazar ("SL (alış günü)").
- Dolum SL'nin altındaysa bu satış, alış fiyatının **üstünde** bir fiyattan yazılmış olur. Sonuç "SL" görünür ama net
  **kâr** kaydedilir. Gerçekte stop emri açılışta tetiklenir ve satış açılış civarından olurdu. Bu yüzden kayıt
  **iyimserdir**.
- Test: `test_open_below_stop_current_handling` (açılış 94, SL 95 → satış 95'ten, net kâr).

**Gerçek veride sıklık:**

| | ortak · 12 ay | ortak · 2024 | teknik · 12 ay | teknik · 2024 |
|---|---|---|---|---|
| Portföyde stop altı açılış (iki senaryoda) | 6 | 1 | 5 | 0 |
| Bu işlemlere yazılan "stoptan satış" kârı, mevcut (TL) | +3.739 | +249 | +5.566 | 0 |
| Aynı kâr, alternatif (TL) | +2.966 | +197 | +4.490 | 0 |
| Kısıtsız evrende stop altı açılış / girilen | 32 / 2.639 | 22 / 2.752 | 24 / 1.691 | 20 / 1.781 |

- Kısıtsız evrende bu işlemlerin 30 / 32 ve 21 / 22'si kârlı yazıldı. Örnekler:
  - TERA 2026-04-21: tavan/taban kilitli mum, açılış = en düşük = 321, SL 336;
  - BAKAB 2024-02-01: açılış 48,08, SL 89,28 → büyük olasılıkla bölünme ya da veri hatası.
- Yaklaşık etki: portföy sonuçları bu işlemlerde **en çok** yukarıdaki tutarlar kadar iyimser. Bu, yeniden simülasyon
  değil üst sınır tahminidir. Ortak 12 ay için yaklaşık 3,7 puan getiri.

## H3.6 Testler (ayrı ayrı)

| Test | Kanıtladığı |
|---|---|
| `test_default_is_current_behavior` | Varsayılan = mevcut davranış; bilinmeyen seçenek hata verir. |
| `test_initial_risk_exceeds_budget_only_in_current` | Başlangıç riski aşımı: mevcutta 18 adet → 131,5 TL > 100; alternatifte 13 adet → 94,98 ≤ 100. Boşluksuz stopta kayıp = başlangıç riski; ayrıştırma "giriş farkı", K ≈ 0. |
| `test_gap_loss_exceeds_budget_even_in_alternative` | Stop boşluğu aşımı: alternatifte başlangıç riski bütçe içinde, ama açılış 85'te kayıp bütçeyi aşar; aşımın tamamı G. |
| `test_open_below_stop_current_handling` | Stop altı açılışın iki senaryodaki mevcut ele alınışı (yukarıda). |

**Sonuç:** Portföy testleri **23 / 23 OK**; tam takım (ağ engelli) **582 test OK**, ağ denemesi 0.

## H3.7 Öneri (teknik gerekçeyle; karar kullanıcının)

1. **Adet hesabı: risk hesabının değiştirilmesini öneriyorum** (alternatif yöntem: azami girişle önceden adet).
   Bu bir **canlı kural değişikliğidir** ve ayrı onay ister. Gerekçeler:
   - "İşlem başı %1 risk" kuralı mevcut hesapla işlemlerin yaklaşık %40'ında ihlal ediliyor (en çok %1,37), üstelik
     kullanıcı paneldeki "SL'de en fazla kayıp" rakamına güveniyor.
   - Alternatif başlangıç riski aşımını **tamamen** kaldırıyor. Kalan aşım yalnız stop boşluğundan geliyor; bu, adet
     hesabıyla önlenemez.
   - Risk ayarlı sonuçlar değişmiyor. Bu nedenle seçim performansa göre değil tanım tutarlılığına göre yapılmış olur.
   - Bedeli: daha küçük pozisyon, iyi dönemde daha düşük getiri (2024: +%35,9 → +%28,9).
   - Daha sade bir eşdeğer seçenek de var: paneldeki adedi "azami girişe göre" göstermek ve "SL'de en fazla kayıp"
     rakamını azami girişle hesaplamak.
2. **Stop altı açılış: ayrı bir düzeltme gerekiyor.** İki parça var:
   - açılış ≤ SL ise alım önerilmemesi (sabah açılış kontrolüne alt sınır),
   - journal'ın alış günü kuralında, dolum SL'nin altındaysa satışın açılıştan sayılması.

   Bunlar canlı kural ve kayıt değişikliğidir, ayrı onay ister. FAZ 1 defterinin s2 sözleşmesini etkileyebileceği
   için önce etki analizi gerekir.
3. **Mevcut davranış korunursa** en azından raporlarda ve panelde "%1 risk" ifadesinin **planlanan giriş** için
   geçerli olduğu açıkça yazılmalıdır.

Hiçbiri uygulanmadı. FAZ 2 kabulü ve olası canlı değişiklik için kullanıcı kararı bekleniyor.

## H3.8 Değişen dosyalar

- `arastirma/asama6/portfoy.py`:
  - yeni `adet_temeli` seçeneği (varsayılan `planlanan_giris` = mevcut);
  - tanılama alanları: `butce_tl`, `risk_bas_gercek_tl`, `risk_bas_plan_tl`, `acilis_sl_alti`, `planlanan_giris`,
    `sl`, `azami` (işlemler ve sonda açıklar), `giris_ani_risk_gercek` ve `ozsermaye_onceki` (eğri).
  - Karar mantığı varsayılanda değişmedi.
- `arastirma/asama6/risk_ayristirma.py` (yeni): ayrıştırma ve iki senaryo. Çıktısı `sonuclar_faz2/risk_h3.json`.
- `tests/test_portfoy.py`: `RiskTemeli` (4 test).
- Bu ek ve `NOTLAR.md`.


---

# Ek H4 — Stop altı açılışta yapay kârın giderilmesi: gerçekleşme kuralı s3 (16.11.2026, dal `faz2-portfoy`, yalnız araştırma)

**Konumu:** Bu ek **geriye dönük doğrulamadır**. Dönem dışı başarı kanıtı değildir. Parametre optimizasyonu yapılmadı
ve senaryo otomatik seçilmedi.

- **Canlı kural değişmedi:** `journal.evaluate` varsayılanı hâlâ `s2`. Yeni `giris_kosulu` hiçbir canlı yoldan
  çağrılmıyor. Canlı veritabanı yalnız okundu.
- **Önceki raporlar korundu:** Ek H5, H2.8 ve H3.4'e "hatalı gerçekleşme varsayımı içerir" notu eklendi; rakamları
  değişmedi.
- **Değiştirilemez kayıtlar** güncellenmedi ve silinmedi. Model eğitilmedi; etkin model değişmedi.

## H4.1 Üç işlem türü ve kural s3

| Tür | Durum | s2 (mevcut) | s3 (araştırma) |
|---|---|---|---|
| **A. Yeni öneri, henüz alınmamış** | Açılış ≤ SL | Alış yapılmış sayılır. Alış günü satış SL fiyatından yazılır, sonuç "SL" ama net **kâr** (yapay). | `journal.giris_kosulu` → **girişsiz** ("açılış stopun altında veya eşit"). Alış ya da satış getirisi yazılmaz. |
| **B. Önceden açık pozisyon** | Ertesi gün açılış ≤ stop | Açılıştan çıkar ("SL (açılışta boşluk)" ya da TP1 sonrası "başabaş stop (açılış)"). Toplam %0,2 + %0,1 maliyet ve kayma. | **Aynı** (zaten gerçekçiydi). Boşluk + genel kayma varsayımı belgelendi; stop fiyatı gösterilmez. |
| **C. Kullanıcının kaydettiği gerçek alış** | Alış fiyatı ≤ SL | Tür A ile aynı yapay kâr. | Kayıt **korunur**: silinmez, girişsiz sayılmaz; gerçek alış günü ve fiyatı aynen kalır. Stop alışla birlikte tetiklenmiş sayılır ve satış **alış fiyatından** yazılır ("SL (alış stopun altında)"). Zarar = maliyet. |
| Limit emirli plan (otomatik/takip) | Açılış SL'nin altında, limit dolar | Yapay kâr. | Tür C gibi: satış dolum fiyatından. |

- **Stopa eşit açılış:** A'da girişsiz. B'de açılıştan, yani stop fiyatından çıkış. C'de satış alış fiyatından (stopa
  eşit), zarar = maliyet.
- **Stop üstü açılış:** s2 ile s3 **birebir aynı**. 300 rastgele senaryoda doğrulandı.

**Günlük veriyle modellenen giriş koşulunun sınırları:**

- **"Açılış ≤ SL ise girişsiz" kuralı açılış fiyatını görmeyi gerektirir.** Bu ancak kullanıcı açılıştan sonra fiyata
  bakıp elle aldığında uygulanabilir. Halley'in açılış kontrolü 15 dk gecikmeli fiyatla çalışır.
  - Simülasyon böyle bir alışı **açılış fiyatından** yapar. Gerçekte alış birkaç dakika sonra ve farklı bir fiyattan
    olur. Bu iyimser bir yaklaşımdır; mevcut Halley sonuç kuralıyla (`ready.evaluate_all`) aynı varsayımdır.
- **Açılış seansına önceden verilen azami limitli emir yalnız üst sınırı uygular.** Açılış SL'nin altındaysa emir yine
  dolar. Bu yüzden alternatif senaryoda stop altı açılışlar **alınmış** sayıldı: s3 ile hemen stop olur, zarar =
  maliyet. Üst limitin SL altı alışı engellediği **varsayılmadı**.
- Midas'ta alt sınırı da uygulayan koşullu ya da şartlı bir emir türü olup olmadığı **doğrulanmadı**.

## H4.2 Etki analizi: hangi yollar etkileniyor?

| Yol | Tür | s3 etkisi | Şu anki canlı veri (salt-okunur, 16.11 12:13) |
|---|---|---|---|
| `journal.evaluate` (gerçek kayıt alış günü, limit dolumu) | C, limit | Yalnız alış ≤ SL durumunda satış fiyatı | — |
| `journal.update_all` → `trade_journal` | C ve otomatik | Yalnız **açık/bekleyen** kayıtları yeniden yazar; kapanmışlara dokunmaz | 30 kayıt (3 kapanmış). Alış ≤ SL **0**. Tek "SL (alış günü)" kaydında alış (48,44) stopun (46,57) üstünde, etkilenmez. |
| `ready.opening_check` / `evaluate_all` → `hazir_firsat` | A | Alt sınır eklenmeli (girişsiz) | 2 kayıt (onaylandı), açılış ≤ SL **0** |
| `tracker` (takip senaryoları) | limit | `journal.evaluate` üzerinden aynı | Ölçülmedi (olay günlüğü değişir, sonuç alanı yok) |
| `defter._degerlendir` → tahmin defteri | A | s2 sözleşmesi donmuş. s3 ayrı kural sürümü gerekir (H4.6). | 2 tahmin, 0 sonuç, 0 değerlendirme |
| `arastirma/asama6/etiketle.py` (eğitim etiketleri) | A | Bu planlar girişsize dönerdi | 39.112 girilen planın **293**'ünde (%0,75) açılış ≤ SL (yaklaşık, plan dosyasındaki açılış boşluğundan). Hepsi zaten y = 0 (SL); **TP1 etiketi değişmez**, yalnız örnek eğitimden çıkardı. Yeniden etiketleme ve eğitim yapılmadı. |
| `arastirma/asama6/portfoy.py` | A ve C | `kural` + `stop_alti_girissiz` seçenekleri (varsayılan = eski) | Bu ek |

## H4.3 Regresyon testleri (`tests/test_kural_s3.py`, 14 test)

| Test | Kanıtladığı |
|---|---|
| `test_entry_condition_for_new_suggestion` | Tür A koşulu: azami üstü, stopa eşit, stop altı, fiyat yok, hemen stop üstü. |
| `test_s2_default_unchanged_shows_artificial_profit` | Varsayılan s2 değişmedi; eski yapay kâr belgelendi (94'ten alış, 95'ten satış). |
| `test_s3_below_stop_no_artificial_profit` | Tür C: kayıt korunur (gün, fiyat), satış 94'ten, net = −%0,3. |
| `test_s3_fill_equal_to_stop` | Stopa eşit alış: zarar = maliyet. |
| `test_s3_fill_above_stop_identical_to_s2` + `test_random_fills_above_stop_never_differ` | Stop üstünde s2 = s3 (300 rastgele yol); stop altında s3'te hiç kâr yok. |
| `test_gap_below_stop_exits_at_open` | Tür B: açılış 85 → satış 85'ten, R < −1. |
| `test_open_equal_to_stop_exits_at_stop` | Açık pozisyonda açılış = stop. |
| `test_gap_below_breakeven_after_tp1` | TP1 sonrası boşluk: satış açılıştan (97), girişten değil. |
| `test_limit_fill_below_stop` | Limit emir SL altında dolar; s2 kâr, s3 yalnız maliyet. |
| `test_unknown_rule_rejected` | Bilinmeyen kural hata verir. |
| `PortfoyS3` (3 test) | Açılışı görerek alımda stop altı → girişsiz, nakit değişmez. Önceden verilen emirde dolar ve zarar = maliyet. Stop üstünde sonuç değişmez. |

**Gerçek veride yapay kâr kontrolü:** Bütün s3 koşularında stop altı açılan ve kârlı yazılan işlem sayısı **0**. s2'de
bu sayı 6 / 1 / 5 / 0'dı.

## H4.4 Düzeltilmiş karşılaştırma

**Koşular.** Her koşu kendi nakit ve risk durumuyla **bağımsız** yürür; aynı işlemleri seçmeye zorlanmaz. Diğer bütün
ayarlar aynı.

- **mevcut_s3:** planlanan girişe göre adet; açılışı görüp elle alım (açılış ≤ SL girişsiz).
- **alternatif_s3:** azami girişe göre önceden adet; açılış seansına azami limitli emir; stop altında da dolar.
- `_s2` sütunları eski, hatalı varsayımlı koşulardır (karşılaştırma için).

**canli_ortak · son 12 ay (2025-11-14 … 2026-11-13)**

| | mevcut_s2 | **mevcut_s3** | alternatif_s2 | **alternatif_s3** |
|---|---|---|---|---|
| Bitiş özsermayesi (TL) | 77.270 | **85.564** | 80.252 | **77.877** |
| Net getiri | −%22,7 | **−%14,4** | −%19,8 | **−%22,1** |
| Azami düşüş | −%34,1 | −%30,7 | −%30,3 | −%32,2 |
| Sortino / kâr faktörü | −1,45 / 0,72 | −0,81 / 0,82 | −1,51 / 0,71 | −1,68 / 0,68 |
| Ortalama R | −0,19 | −0,08 | −0,19 | −0,22 |
| Açılan / kapanan | 141 / 136 | 134 / 129 | 141 / 136 | 141 / 136 |
| Toplam maliyet (TL) | 7.092 | 6.951 | 6.059 | 5.963 |
| Başlangıç riski %1'i aşan | 57 | 56 | 0 | **0** |
| Kaybı %1'i aşan | 43 | 43 | 1 | **1** (stop boşluğu) |
| Giriş anı portföy riski en yüksek | %5,56 | %5,54 | %4,40 | %4,40 |
| Stop altı açılış: alınan / kârlı yazılan / net (TL) | 6 / 6 / +3.396 | 0 / 0 / 0 (70 aday girişsiz) | 6 / 6 / +2.695 | 6 / **0** / −266 |
| s2 koşusuyla ortak işlem | — | 114 (27 çıktı, 20 girdi) | — | 141 (aynı) |

**canli_ortak · 2024**

| | mevcut_s2 | **mevcut_s3** | alternatif_s2 | **alternatif_s3** |
|---|---|---|---|---|
| Bitiş / net getiri | 135.873 / +%35,9 | **135.071 / +%35,1** | 128.914 / +%28,9 | **128.719 / +%28,7** |
| Azami düşüş | −%15,2 | −%15,7 | −%12,3 | −%12,4 |
| Sortino / kâr faktörü | 2,19 / 1,34 | 2,12 / 1,33 | 2,18 / 1,35 | 2,16 / 1,35 |
| Açılan / kapanan | 110 / 105 | 110 / 105 | 110 / 105 | 110 / 105 |
| Toplam maliyet (TL) | 6.697 | 6.696 | 5.260 | 5.257 |
| Başlangıç riski aşan / kaybı aşan | 48 / 31 | 48 / 31 | 0 / 4 | 0 / 4 |
| Stop altı: alınan / kârlı / net (TL) | 1 / 1 / +176 | 0 (49 aday girişsiz) | 1 / 1 / +139 | 1 / 0 / −58 |

**yalniz_teknik**

| | mevcut_s2 | mevcut_s3 | alternatif_s2 | alternatif_s3 |
|---|---|---|---|---|
| 12 ay getiri / düşüş | −%24,7 / −%39,3 | −%24,6 / −%41,0 | −%19,6 / −%33,3 | −%22,8 / −%35,7 |
| 12 ay kâr faktörü | 0,76 | 0,75 | 0,77 | 0,72 |
| 12 ay başlangıç aşan / kayıp aşan | 57 / 49 | 54 / 46 | 0 / 3 | 0 / 3 |
| 2024 getiri / düşüş | +%25,9 / −%15,2 | aynı | +%20,2 / −%12,8 | aynı |

2024'te seçilen yolda stop altı açılış yok; s2 = s3.

**Düzeltmenin saf etkisi** (aynı işlemler, yalnız yapay kâr kalktı: alternatif_s2 → s3):

| | Getiri etkisi | TL |
|---|---|---|
| ortak · 12 ay | **−2,4 puan** | −2.375 |
| ortak · 2024 | −0,2 puan | — |
| teknik · 12 ay | −3,2 puan | — |

**Mevcut senaryoda tablo yanıltıcı olabilir.** mevcut_s2 → s3'te getirinin artması (ortak 12 ay +8,3 puan) düzeltmenin
kendisinden **değil**, **yol bağımlılığından** geliyor. Girişsiz sayılan aday, o gün yerini sıradaki adaya bıraktı ve
27 işlem değişti. Yapay kârın kalkması tek başına sonucu düşürür.

**Ayrıştırma koşuları** (öneri değil; adet etkisini "açılışı görerek SL süzgeci" etkisinden ayırmak için çapraz
koşular, s3):

| ortak · 12 ay | Açılışı görüp alım (SL süzgeci var) | Önceden emir (SL süzgeci yok) |
|---|---|---|
| Planlanan girişe göre adet | −%14,4 (düşüş −%30,7) = mevcut_s3 | −%25,5 (−%36,2) |
| Azami girişe göre adet | −%9,9 (−%26,1) | −%22,1 (−%32,2) = alternatif_s3 |

| ortak · 2024 | Açılışı görüp | Önceden emir |
|---|---|---|
| Planlanan girişe göre adet | +%35,1 | +%35,6 |
| Azami girişe göre adet | +%28,3 | +%28,7 |

teknik · 12 ay: planlanan + önceden emir −%28,7; azami + açılışı görüp −%19,5.

**Okuma:**

- **Adet etkisi** (aynı giriş türünde azami ile planlanan): 12 ayda +3 – +5 puan, 2024'te −7 puan. İşareti döneme
  göre değişiyor; bu orantılı küçülmedir.
- **SL süzgecinin görünen etkisi** (12 ayda +11 – +12 puan) neredeyse tümüyle yol bağımlılığı. Stop altı alınan
  işlemlerin doğrudan zararı yalnız maliyet kadar: alternatif_s3'te 6 işlemde −266 TL. 2024'te etki yok denecek
  kadar küçük.
- Bu büyüklükte bir fark sağlam bir avantaj olarak **okunmamalıdır**. Üstelik süzgeç açılışı görmeye dayanır
  (H4.1 sınırı).

## H4.5 Azami girişe göre adet önerisinin yeniden değerlendirilmesi

1. **Risk tanımı açısından öneri geçerli.** Bütün s3 koşularında azami girişe göre adetle başlangıç riski aşımı
   **0**; %1'i aşan kayıp yalnız stop boşluğundan geliyor (1–4 işlem). Planlanan girişe göre adette 48–57 aşım sürüyor.
2. **Performans gerekçesi yok.** Getiri farkı dönem ve giriş türüyle işaret değiştiriyor. Seçim performansa göre
   yapılmamalı.
3. **Uygulanabilirlik koşullu.** Midas'ta açılış seansına limit emir verilebildiği doğrulanmadı.
   - Doğrulanırsa: emir azami limitle önceden verilir. Stop altı açılışta emir dolar ve hemen stop olur (maliyet
     kadar zarar); bunu ancak koşullu bir emir önler, o da doğrulanmadı.
   - Doğrulanmazsa ya da kullanıcı açılışı görüp elle almaya devam ederse, **daha uygun canlı seçenek** şudur: panel
     adedi alış anında kullanıcının gireceği **gerçek fiyatla** yeniden hesaplar ve plan açılışı görüldüğünde stop
     altıysa girişsiz sayılır. Bu, günlük veriyle test edilemez; azami girişe göre adet, onun en kötü durum
     (muhafazakâr) üst sınırıdır.
4. **Öneri:**
   - **(a) s3 gerçekleşme düzeltmesi + A türü alt sınır:** doğruluk düzeltmesi olarak önerilir.
   - **(b) Adet hesabı:** "azami girişe göre" (en kötü durum) ya da "alış anında gerçek fiyatla yeniden hesap". Hangisi
     olacağı Midas doğrulamasına bağlı.

   İkisi de ayrı canlı onay ister.

## H4.6 Canlı değişiklik kapsamı (uygulanmadı; onay sonrası plan)

**Dosyalar:**

- `bist_haber/journal.py`: s3'ü varsayılan yapmak ve sonuç kaydına `kural` alanı eklemek.
- `bist_haber/ready.py`: `opening_check` ve `evaluate_all` alt sınırı (A türü girişsiz, açıklamalı neden).
- `bist_haber/defter.py`: `KURAL_SURUM = "s3"`, girişsiz nedeni, s2 sonuçlarına ayrı s3 değerlendirmesi.
- `app.py`: adet ve "SL'de en fazla kayıp" metni, girişsiz nedeni gösterimi.
- `bist_haber/tracker.py`: yalnız çağrı yolu.
- Testler.

**Şema:**

- Yeni tablo ya da sütun **gerekmiyor**.
- `tahmin_degerlendirme` zaten `kural_surum` taşıyor; s3 satırları eklenir, s2 satırları değişmez.
- `hazir_firsat` için mevcut `durum='girissiz'` + `iptal_nedeni` yeterli.
- `trade_journal.sonuc_json` serbest JSON'dur; `kural` alanı eklenir.

**Sürümleme:**

- Tahmin defteri: s2 değişmez, s3 ayrı değerlendirme satırı olur (s1 → s2 mekanizmasıyla aynı). Panel sürüm grupları
  kural sürümünü zaten ayırıyor.
- `trade_journal`: `update_all` yalnız açık ve bekleyen kayıtları yeniden yazar. Kapanmış kayıtlar eski kuralla kalır;
  `kural` alanı olmayan kayıt s2 kabul edilir.
- Etiketler ve model: değişmez. Yeniden eğitim ayrı karar.

**Yedekleme ve geri dönüş:** FAZ 1 v2 geçişiyle aynı yol.

1. Halley durdurulur (aktif iş yokken).
2. Kod yedeği ve DB yedeği alınır (`integrity_check`).
3. Kod değiştirilir (şema göçü yok).
4. Başlatılır ve sağlık kontrolü yapılır.

- **Geri dönüş:** Önceki commit'in koduna dönülür. s3 değerlendirme satırları eklemedir ve s2'yi bozmaz; eski kod
  onları yok sayar.
- **Yeni veri kaybı yok:** Yedek doğrudan geri yüklenmez.

## H4.7 FAZ 1 canlı kabul durumu (ayrı)

- **16.11 12:13 itibarıyla:** 2 tahmin, 0 sonuç, 0 değerlendirme, 0 olay. Geçişten sonra yeni akşam ya da sabah
  çalıştırması gözlenmedi.
- Bu akşamki analiz ve yarın sabahki kontrol için bekçiler çalışıyor (oturuma bağlı).
- **FAZ 1 kabul edilmedi; gözlenmeyen durum doğrulanmış sayılmadı.**

## H4.8 Değişen dosyalar (dal `faz2-portfoy`)

- `bist_haber/journal.py`: `giris_kosulu()` yeni; `evaluate(..., kural="s2")` seçeneği. Varsayılan davranış birebir
  aynı. Canlı çağrılar parametre geçmiyor.
- `arastirma/asama6/portfoy.py`: `kural` ve `stop_alti_girissiz` seçenekleri (varsayılan eski).
- `arastirma/asama6/kural_s3_karsilastirma.py` (yeni). Çıktısı `sonuclar_faz2/kural_s3.json`.
- `tests/test_kural_s3.py` (yeni, 14 test).
- Bu ek; Ek H5, H2.8, H3.4 düzeltme notları; `NOTLAR.md`.

**Testler:** `tests.test_kural_s3` 14 / 14 OK; tam takım (ağ engelli) **596 test OK**, ağ denemesi 0. Varsayılan kuralla orijinal (Ek H5) ve Ek H3 metrikleri birebir yeniden üretildi.

**Onay beklenen:** canlı değişiklik (H4.6) ve FAZ 2 nihai kabulü. FAZ 3 yok.


---

# Ek H9 — FAZ 2 son kapsam: gerçek / varsayım ayrımı, emir modeli, senaryo sınıflaması (16.11.2026, dal `faz2-portfoy`)

**Konumu:** Geriye dönük doğrulamadır. Dönem dışı başarı kanıtı değildir ve canlı kullanım için başarı kanıtı da
sayılmaz.

- Canlı değişiklik yok; s3 canlıya alınmadı. Parametre değişmedi; senaryo otomatik seçilmedi.
- **FAZ 2 kabul ölçütü** (kullanıcı tanımı): Simülatörün belgelenmiş varsayımlarla doğru çalışması. Stratejinin kârlı
  olması değil.

## H9.1 Gerçek alış ile varsayımsal çıkış ayrıldı (`journal.evaluate`, yalnız s3)

- **Varsayılan s2 çıktısı birebir aynı.** Test `test_s2_output_has_no_s3_fields` s3'ün eklediği alanların s2'de
  bulunmadığını doğrular.
- **Kullanıcı satış fiyatı girmez.** `trade_journal` tablosunda satış fiyatı alanı yoktur. Bu yüzden bütün çıkışlar,
  gerçek alış kayıtlarında da, günlük mumlarla **kurala göre hesaplanır**.
- s3 her kapanmış sonuca şu ayrımı yazar:
  - `gerceklesme.alis` = `kullanici_kaydi` (gerçek bilgi) ya da `kural_simulasyonu`;
  - `gerceklesme.cikis` = `varsayimsal_kural_simulasyonu`;
  - `gerceklesme.not` = kullanılan maliyet ve kayma (örnek: "komisyon %0.2 + kayma %0.1, gidiş-dönüş").
- **Alış ≤ SL durumu:** Bacak adı "SL **varsayımı** (alış stopun altında)". Ek olarak `cikis_varsayimi` metni yazılır:
  "stopun alışla birlikte tetiklendiği VARSAYILDI; satış fiyatı = alış fiyatı … Gerçekleşmiş satış değildir."
- **Canlı için not (uygulanmadı):** Bugünkü panel, gerçek alış kayıtlarının kurala göre hesaplanan sonucunu ayrıca
  etiketlemiyor. Canlı değişiklik sırasında panelde "kurala göre hesaplanan sonuç (satış girilmedi)" ayrımı gerekir.
  Gerçek satış fiyatı alanı eklemek bir şema değişikliği olur ve ayrı karar ister.

## H9.2 Girişsiz adayın yerine alınan adayın seçim zamanı

**Bulgu (doğrulandı):** Önceki bütün koşularda simülatör adayları sırayla dolaşıyordu. Açılış fiyatına bakarak eleme
yapıyordu (azami üstü, s3'te SL altı) ve elenen adayın yerine sıradaki adayı **aynı açılış fiyatından** alıyordu. Bu,
açılışı görüp başka hisse seçmek ve onu da aynı açılıştan almak demektir; gerçekte mümkün değildir.

- Test `test_theoretical_model_substitutes_after_seeing_open`: AAA açılışı azami üstünde → BBB aynı açılıştan alınmış
  sayıldı.
- Ayrıca planlanan girişe göre adette nakit sınırı **açılış fiyatıyla** hesaplanıyordu.

**Düzeltme:** Yeni `emir_modeli="onceden_limit"`.

- Emir listesi açılıştan **önce**, yalnız d−1 bilgisiyle kurulur: yer, sektör, adet, nakit (azami fiyatla ayrılır),
  toplam risk.
- Her emir azami giriş limitlidir. Açılış ≤ azami ise açılış fiyatından dolar.
- Değilse **dolmaz** ve yerine başka aday alınmaz. Dolmayan emrin yeri ve ayrılan nakdi o gün başka emre verilmez.
- Açılış SL'nin altındaysa emir yine dolar (s3: zarar = maliyet). Açılışı gören süzgeç bu modelle kullanılamaz;
  kullanılırsa hata verir.
- **Testler:**
  - `test_preplaced_order_no_substitution`;
  - `test_preplaced_orders_independent_of_open_prices`: 5 farklı açılış fiyatı kümesinde verilen emirler aynı;
  - `test_preplaced_below_stop_fills_no_profit`;
  - `test_preplaced_cannot_use_open_filter`.
- **Eski model korundu:** `emir_modeli="acilisi_gorup"` varsayılan. Artık açıkça **teorik** olarak etiketli.

## H9.3 Senaryo sınıflaması

| Sınıf | Senaryo | Neden |
|---|---|---|
| **Uygulanabilirliği doğrulanmış** | **Yok** | Hiçbir emir yolu gerçek aracı kurumda doğrulanmadı. Günlük veri, açılıştan sonraki gerçek alış fiyatını bilemez. |
| **Emir altyapısına bağlı** | **E**: önceden limit emir, yerine aday yok (`onceden_limit`). Her iki adet yöntemiyle. | Şu koşullara bağlı: Midas'ta BIST açılış seansına limit emir verilebilmesi; nakdin limit fiyatıyla bloke edilmesi; dolumun açılış seansı fiyatından olması (Yahoo açılışıyla aynı varsayıldı); kısmi dolum olmaması. **Hiçbiri doğrulanmadı.** |
| **Teorik günlük veri senaryosu** | **T1**: açılışı görüp, azami ve SL süzgeci, yerine aday aynı açılıştan (Ek H4 `mevcut_s3`). | Açılışı görmek ve aynı açılıştan almak birlikte mümkün değil. |
| | **T2**: açılışı görüp, yalnız azami süzgeci, yerine aday aynı açılıştan. Ek H4'teki `alternatif_s3` ve `ayr_planlanan_onceden_emir_s3` koşuları. | Ek H4'te "önceden emir" diye adlandırılmıştı. Yerine aday seçimi açılışa baktığı için **teoriktir** (H9.2). Ad düzeltildi. |
| | Bütün s2 koşuları: Ek H bölüm H5 ana sonuçları, Ek H2, Ek H3. | Hem stop altı yapay kâr hem T2 seçim varsayımı içerir. |

## H9.4 Sonuçlar: adet yöntemi × giriş/gerçekleşme yöntemi (kural s3)

Yalnız E satırları yeni koşudur (`emir_modeli_karsilastirma.py`). T1 ve T2 Ek H4 koşularıdır. Kod değişikliğinden
sonra Ek H4'ün 24 koşusunun hepsi aynı metrikleri verdi (regresyon: **True**).

**canli_ortak · son 12 ay (2025-11-14 … 2026-11-13)**

| Giriş/gerçekleşme modeli (sınıf) | Planlanan girişe göre adet | Azami girişe göre adet |
|---|---|---|
| **E** önceden limit emir (emir altyapısına bağlı) | **−%25,2**, düşüş −%35,6, PF 0,67, başlangıç aşımı 52, kayıp aşımı 42 | **−%21,7**, düşüş −%31,6, PF 0,67, başlangıç aşımı **0**, kayıp aşımı 2 |
| T1 açılışı görüp + SL süzgeci (teorik) | −%14,4, düşüş −%30,7 | −%9,9, düşüş −%26,1 |
| T2 açılışı görüp, yalnız azami (teorik) | −%25,5, düşüş −%36,2 | −%22,1, düşüş −%32,2 |

**canli_ortak · 2024**

| Model | Planlanan | Azami |
|---|---|---|
| **E** (altyapıya bağlı) | **+%22,9**, düşüş −%19,8, PF 1,20, başlangıç aşımı 54, kayıp aşımı 33 | **+%19,5**, düşüş −%16,4, PF 1,21, başlangıç aşımı **0**, kayıp aşımı 4 |
| T1 (teorik) | +%35,1, düşüş −%15,7 | +%28,3, düşüş −%12,7 |
| T2 (teorik) | +%35,6, düşüş −%15,3 | +%28,7, düşüş −%12,4 |

**yalniz_teknik**

| Model | 12 ay planlanan | 12 ay azami | 2024 planlanan | 2024 azami |
|---|---|---|---|---|
| **E** (altyapıya bağlı) | −%31,9 | −%27,3 | +%10,4 | +%8,9 |
| T1 (teorik) | −%24,6 | −%19,5 | +%25,9 | +%20,2 |
| T2 (teorik) | −%28,7 | −%22,8 | +%25,9 | +%20,2 |

**E modelinin ayrıntıları (canli_ortak):**

| | 12 ay planlanan | 12 ay azami | 2024 planlanan | 2024 azami |
|---|---|---|---|---|
| Açılan / kapanan | 135 / 130 | 135 / 130 | 128 / 123 | 128 / 123 |
| Dolmayan emir (açılış azami üstünde) | 23 | 23 | 12 | 12 |
| Toplam maliyet (TL) | 6.633 | 5.771 | 8.018 | 6.418 |
| Giriş anı portföy riski en yüksek | %5,55 | %4,39 | %5,48 | %4,44 |
| Stop altı dolan / kârlı yazılan / net (TL) | 4 / 0 / −184 | 4 / 0 / −157 | 4 / 0 / −248 | 4 / 0 / −204 |
| Ortalama R | −0,23 | −0,23 | +0,18 | +0,18 |

**Okuma (ölçüm, öneri değil):**

- **Adet yönteminin karşılaştırması yalnız aynı satırda geçerlidir.** E modelinde azami girişe göre adet 12 ayda
  +3,5 puan, 2024'te −3,4 puan. Bu orantılı küçülmedir; R ve kâr faktörü neredeyse aynı. Başlangıç riski aşımı 52–54'ten
  **0**'a iniyor.
- **Ek H4'teki "−%14,4 ile −%22,1" karşılaştırması bir adet karşılaştırması değildi:** T1 ile T2 farklı giriş
  kurallarıdır. Burada ayrıldı.
- **Teorik T modelleri, uygulanabilir olabilecek E modelinden belirgin iyi** (2024'te +%35,1 ile +%22,9). Fark,
  açılışı görüp yerine aday seçmekten geliyor. Bu iyimserlik önceki bütün rapor sonuçlarında vardı.

## H9.5 FAZ 2 kabul önerisi

**Öneri: FAZ 2, simülatör olarak kabul edilebilir.** Ölçüt "belgelenmiş varsayımlarla doğru çalışma"dır:

- Tek kaynak kuralları kullanılıyor: `journal`, `position_size`, sektör, sıralama.
- Zaman sırası testli: d−1 bilgisiyle karar, d içinde çıkış, aynı gün nakit kullanılmıyor.
- Geleceğe bakmama testli ve gerçek veride 5.244 işlemle tekil mutabakat yapıldı.
- Muhasebe özdeşliği tutuyor; risk tanımları ayrıştırıldı.
- Yapay kâr giderildi (s3).
- Açılışa bakan seçim, ayrı ve teorik olarak etiketlenmiş bir model hâline geldi; önceden emir modeli eklendi.
- Bütün varsayılan koşular birebir yeniden üretiliyor. Tam takım OK (H9.7).

**Kabul, strateji başarısı anlamına gelmez.** Altyapıya bağlı E modelinde son 12 ay iki adet yönteminde de zararlı
(−%22 – −%25, kâr faktörü 0,67). 2024 kârlı. Haber şartı yok.

## H9.6 Kalan sınırlamalar

1. **Uygulanabilirliği doğrulanmış senaryo yok.** E modeli Midas'ın açılış seansı limit emri, nakit blokesi, dolum
   fiyatı ve kısmi dolum davranışına bağlı; hiçbiri doğrulanmadı.
2. **Günlük veri:** Gün içi sıra bilinmiyor. Açılış seansı fiyatı Yahoo açılışıyla aynı varsayıldı. Likidite ve derinlik
   modellenmedi.
3. **Hayatta kalma yanlılığı:** Yalnız bugün işlem gören hisseler var; sonuçlar iyimser olabilir. **Sektör listesi
   güncel**, tarihsel değil.
4. **Haber puanı yok:** Canlıdaki haberli hazır fırsat listesi bu evrenle eşdeğer değil.
5. **Model sıralaması denenmedi:** Dönem dışı tahmin kaydı yok.
6. **Çıkışlar kurala göre:** Gerçek alış kayıtlarında da çıkış varsayımsal. Canlıda satış fiyatı alanı yok (H9.1).
7. **Stop boşluğu adet hesabıyla önlenemez:** Kalan %1 üstü kayıplar bundan geliyor.
8. **Diğer:** Plan sayısında önceki etiket dosyasıyla 316 fark var ve doğrulanmadı. XU100'de 3 adet 25 Aralık eksik.
   Tek adette TP1 yuvarlaması var.
9. **Geriye dönüklük:** Bütün düzeltmeler sonuçlar görüldükten sonra yapıldı. Dönem dışı doğrulama sayılmaz.
10. **Canlıya alınmadı:** s3 ve adet değişikliği canlıda değil. Canlıdaki "%1 risk" ve gerçek kayıt sonuçları s2
    davranışındadır (Ek H3, H4).

## H9.7 Değişen dosyalar ve testler

- `bist_haber/journal.py`: s3'e `gerceklesme` ve `cikis_varsayimi` alanları, bacak adı "SL varsayımı …". s2 değişmedi.
- `arastirma/asama6/portfoy.py`: `emir_modeli` (`acilisi_gorup` varsayılan, teorik | `onceden_limit`); `emirler`
  listesi. Varsayılan sonuç birebir.
- `arastirma/asama6/emir_modeli_karsilastirma.py` (yeni). Çıktısı `sonuclar_faz2/emir_modeli.json`.
- `tests/test_kural_s3.py`: +7 test (gerçek / varsayım alanları 2, önceden limit 5), 21 test.
- Bu ek ve `NOTLAR.md`.

**Testler:** `tests.test_kural_s3` 21 / 21, `tests.test_portfoy` 23 / 23; tam takım (ağ engelli) **603 test OK**, ağ denemesi 0.

## H9.8 FAZ 1 canlı kabul durumu (ayrı)

- 16.11 12:30 (salt-okunur): 2 tahmin, 0 sonuç, 0 değerlendirme, 0 olay. Geçişten sonra akşam/sabah çalıştırması henüz yok.
- Bekçiler bu akşamki analizi (16.11) ve yarın sabahki kontrolü (17.11) bekliyor (oturuma bağlı).
- **FAZ 1 kabul edilmedi.**

**Onay beklenen:** FAZ 2 kabulü (H9.5). s3 ve adet değişikliği canlıya alınmadı. Sonraki faz için kullanıcı kararı bekleniyor.


---

# Ek H10 — FAZ 2 KABUL KAYDI (16.11.2026)

**Kabul:** Kullanıcı, FAZ 2'yi commit **`6d7f5d5`** kapsamındaki **araştırma amaçlı portföy simülatörü** olarak kabul etti.

- **Gerekçe:**
  - 603 başarılı test;
  - muhasebe ve zaman sırası kontrolleri;
  - teorik modellerin ayrılması;
  - sınırlamaların belgelenmesi.
- **Kabul şunları kapsamaz:**
  - stratejinin kârlı olduğu;
  - emir uygulamasının doğrulandığı;
  - canlıya geçişin onaylandığı.
- **Canlı kural değişmedi:** s3 ve adet değişikliği canlıda değil.

## H10.1 Sabitlenen sürüm ve ayarlar

| Öğe | Değer |
|---|---|
| Kod | commit `6d7f5d50d4ba95f64c8d096df5862073028684d3`, dal `faz2-portfoy`, etiket `faz2-kabul`. İzlenen dosyalarda değişiklik yok. `portfoy.py` ve `journal.py` SHA-256 değerleri `kayit.json` içinde. |
| Plan evreni | `planlar_seviyeli.csv` (45.737 plan). SHA-256 `kayit.json` içinde. |
| Fiyat verisi | `arastirma_5y.db` (son fiyat 2026-11-13) |
| Dönemler | son 12 ay 2025-11-14 … 2026-11-13; 2024: 2024-01-02 … 2024-12-31 |
| Evrenler | `canli_ortak`, `yalniz_teknik` (Ek H4) |
| Ayarlar | 100.000 TL; %1 risk; 5 pozisyon; toplam risk %6; sektör başına 2; komisyon %0,2 + kayma %0,1 (gidiş-dönüş) |
| Emir modeli | `onceden_limit`: emir listesi açılıştan önce, azami limitli; dolmayanın yerine aday yok. **Emir altyapısına bağlı**, doğrulanmadı. |
| Gerçekleşme kuralı | s3. Stop altı dolan alışta çıkış **varsayımsal** (alış fiyatı); ek kayma belirsiz. İşlem dosyalarında `cikis_varsayimsal_stop_alti` sütunu ile işaretli. |
| Adet yöntemi | iki ayrı koşu: planlanan girişe göre (canlıdaki davranış) / azami girişe göre |
| Sonuç dosyaları | `arastirma/asama6/sonuclar_faz2/kabul/`: `kayit.json` + `<evren>_<dönem>_<adet>_{egri,islemler,atlanan,acik_son}.csv`. Üretim: `faz2_kabul_kaydi.py`. |

## H10.2 Ana sonuçlar (yalnız bunlar FAZ 2 ana sonucudur)

| Evren · dönem | Planlanan girişe göre adet | Azami girişe göre adet | Stop altı varsayımsal çıkış |
|---|---|---|---|
| canli_ortak · son 12 ay | −%25,2 (düşüş −%35,6, PF 0,67) | −%21,7 (düşüş −%31,6, PF 0,67) | 4 / 4 işlem |
| canli_ortak · 2024 | +%22,9 (düşüş −%19,8, PF 1,20) | +%19,5 (düşüş −%16,4, PF 1,21) | 4 / 4 |
| yalniz_teknik · son 12 ay | −%31,9 (düşüş −%39,7, PF 0,67) | −%27,3 (düşüş −%34,8, PF 0,66) | 6 / 6 |
| yalniz_teknik · 2024 | +%10,4 (düşüş −%19,3, PF 1,07) | +%8,9 (düşüş −%16,1, PF 1,07) | 1 / 1 |

- Ayrıntılı metrikler `kayit.json → sonuc` içinde.
- Bütün değerler Ek H9 ile birebir aynı; kabul kaydı aynı kodla yeniden üretildi.
- **Ana sonuç değildir:** Teorik modeller (açılışı görüp) ve bütün s2 rakamları.

**Uyarı:** Haber şartı yoktur. Hayatta kalma yanlılığı vardır ve sektör listesi güncel listedir. Sonuçlar geriye dönük
düzeltmelerden sonra üretildi; dönem dışı kanıt değildir.


---

# EK I (16.11.2026) — FAZ 3: backtest metrikleri, MAE/MFE ve veri güvenilirliği (dal `faz3-metrik`, araştırma)

**Konumu:**

- Canlı kod ve canlı veritabanı **değişmedi**; veritabanları yalnız okundu. Göç yalnız kopyada denendi.
- Model eğitilmedi; etkin model, seçim eşikleri ve FAZ 2 ayarları değişmedi.
- Bayraklı veri silinmedi, düzeltilmedi, analizden çıkarılmadı.
- FAZ 2 kabul sonuçları yeniden üretilmedi; kabul dosyaları (`sonuclar_faz2/kabul/`) okundu.
- Bu çalışma geriye dönük incelemedir, dönem dışı kanıt değildir.

## I.1 Metrik doğrulaması (MDD, Sortino, kâr faktörü)

Bağımsız kod (`arastirma/faz3/metrikler.py`) aynı tanımlarla, ayrı yazılmış olarak çalıştırıldı.

- **Kabul dosyaları:** 8 kabul koşusunun **8'inde de** 10 metrik simülatörle aynı (`sonuclar/metrik_mae.json → dogrulama`):
  toplam getiri, MDD, Sortino, Sharpe, kâr faktörü, ardışık kayıp, düşüş süresi, kapanan sayısı, ortalama R, kazanma.
- **Rastgele sınama:** 50 rastgele eğri ve işlem kümesinde iki kod aynı sonucu verdi.
- **Hata:** Metrik hesabında hata bulunmadı; önce/sonra farkı yok.
- **Tanımlar** (`metrikler.py` başı):
  - MDD ve düşüş süresi gün sonu özsermayesinden ölçülür; gün içi dip görülmez.
  - Sortino'da hedef 0 ve risksiz faiz 0; aşağı yönlü sapma bütün günlere bölünür.
  - Kâr faktörü yalnız kapanmış işlemlerden, maliyet dahil hesaplanır; sıfır net işlem kayıp tarafında sayılır.
- **Canlı panel metriği (`journal.metrics`) farklı şeyi ölçer:** işlem başınadır, portföy metriği değildir.
  - kâr faktörü net yüzdelerle (eşit ağırlık);
  - azami düşüş kümülatif R ile;
  - "Sharpe" işlem başına (anakütle sapması).

  Elle hesapla doğrulandı (`test_panel_metrics_by_hand`).

## I.2 Ek metrikler ve dağılımlar (FAZ 2 kabul ana sonucu, canli_ortak)

| | 12 ay · planlanan | 12 ay · azami | 2024 · planlanan | 2024 · azami |
|---|---|---|---|---|
| CAGR | −%25,3 | −%21,8 | +%23,1 | +%19,7 |
| Yıllık oynaklık | %21,8 | %18,0 | %22,8 | %18,9 |
| Calmar / kurtarma çarpanı | −0,71 / −0,63 | −0,69 / −0,61 | 1,17 / 0,81 | 1,20 / 0,88 |
| Ulcer endeksi | 17,3 | 15,3 | 8,2 | 6,9 |
| Piyasada kalma (≥ 1 pozisyon) | %99,6 | %99,6 | %100 | %100 |
| Ödeme oranı (ort. kazanç / ort. kayıp) | 2,05 | 2,05 | 2,68 | 2,71 |
| Beklenen net / işlem (TL) | −212 | −183 | +159 | +137 |
| En kötü gün | −%4,5 | −%4,0 | −%5,0 | −%4,0 |

**Dağılımlar** (iki adet yönteminde aynı işlemler; yüzdelikler):

| | 12 ay | 2024 |
|---|---|---|
| Net getiri % (p5 / p25 / medyan / p75 / p95) | −10,5 / −6,6 / −4,4 / −0,3 / +16,0 | −10,5 / −5,9 / −4,4 / +10,4 / +20,8 |
| R (p5 / medyan / p95) | −1,32 / −1,03 / +3,25 | −1,27 / −1,02 / +3,81 |
| İşlem günü (p5 / p25 / medyan / p75 / p95) | 1 / 2 / 6 / 12 / 30 | 1 / 3 / 7 / 14 / 30 |
| R kovaları (<−1,5 / −1,5…−0,5 / −0,5…0,5 / 0,5…1,5 / ≥1,5) | 3 / 86 / 14 / 10 / 17 | 3 / 78 / 5 / 3 / 34 |
| Ardışık kayıp serileri (uzunluk: adet) | 1:5, 2:5, 3:4, 4:1, 5:3, 6:1, 7:1, 8:2, 9:1, **14:1** | 1:8, 2:3, 3:4, 4:5, 5:1, 6:1, 7:2, **14:1** |

- Aylık getiriler ve `yalniz_teknik` değerleri `sonuclar/metrik_mae.json` içinde.
- 12 aylık CAGR dönem bir yıl olduğu için toplam getiriye yakındır.

## I.3 MAE/MFE, R paydası ve günlük veri belirsizliği (`arastirma/faz3/mae_mfe.py`)

**İşlem içi pencere** (`defter.mae_mfe` ile aynı, `gunluk_s2`):

- Giriş mumu tamdır (giriş açılışta). Ara mumlar tamdır.
- Çıkış mumu: açılışta çıkışsa yalnız açılış; gün içi çıkışsa yalnız çıkış fiyatı; süre dolduysa tam mum.
- **Gün içi çıkışta değer bir alt sınırdır:** o gün çıkıştan önce daha kötü ya da iyi bir fiyat görülmüş olabilir.
  - "Yaklaşık" işaretli işlem: 12 ay 109 / 130, 2024 97 / 123.
- Ölçülen şey fiyat hareketidir, pozisyon kâr/zararı değildir (TP1'den sonra yarı pozisyon kalır).

**İki R paydası:**

- `R_plan` = (fiyat − dolum) / (plan girişi − SL). journal ve defterle aynıdır.
- `R_dolum` = (fiyat − dolum) / (dolum − SL). Dolum ≤ SL ise **tanımsızdır**: 4 işlemde böyle (stop altı varsayımsal
  çıkışlar).
- Dolum plan girişinin üstündeyse `R_plan` riski küçük gösterir.
  - Örnek, MAE medyanı (12 ay, azami adet): `R_plan` −0,97, `R_dolum` −1,00.
  - Dağılımın kuyruğu: p5 değeri `R_plan`'de −1,23, `R_dolum`'da −1,05.

| canli_ortak · azami | MAE R_plan (p5 / medyan / p95) | MFE R_plan (p5 / medyan / p95) |
|---|---|---|
| 12 ay | −1,23 / −0,97 / −0,03 | 0,00 / 0,83 / 3,84 |
| 2024 | −1,20 / −0,98 / −0,10 | 0,00 / 0,85 / 5,17 |

**Çıkış sonrası hareket (işlem içi DEĞİL; ayrı alan):** Çıkıştan sonraki 10 mumun en yükseği ve en düşüğü, çıkış
fiyatına göre.

- 12 ay: medyan +%6,7 / −%6,7. 2024: +%7,9 / −%5,5.
- Yalnız bağlam içindir. Kaçırılan kazanç ya da kaçınılan zarar olarak **kesin ölçüm gibi okunmamalı**; aynı
  pencerede iki yön birden vardır.

## I.4 Veri güvenilirliği: bulgular ve ayrımlar

Tarama `veri_guvenilirlik.py`, ayrıştırma `veri_ayrintilari.py` ve `aday_maruziyeti.py` ile yapıldı.
Kapsam: `arastirma_5y.db`, 631 hisse, 674.958 mum.

| Bulgu | Sayı | Ayrım / yorum |
|---|---|---|
| Eksik gün (hissenin ilk-son mumu arasında) | 348 | **329**'u tek bir gün: **2024-04-09**, o gün 631 hissenin yalnız 218'i var. Piyasa geneli düşük kapsama; bayram arifesi yarım günü ile uyumlu, ama doğrulanmadı. **Hata sayılmadı.** Kalan **19** tekil/kısa eksik "olası veri eksikliği". ≥ 5 ardışık eksik (olası işlem durdurma) 0. |
| Geç başlayan hisse | 191 | Veritabanı başlangıcından (2021-11-15) sonra başlıyor. Halka arz mı veri başlangıcı mı **ayrılamadı**; ilk mumdan önceki günler eksik sayılmadı. |
| Sıfır hacim / bayat (OHLC aynı + hacim 0) | 4.296 / 3.762 | İşlem görmeyen gün ya da taşınmış eski fiyat; ayrılamadı. |
| OHLC tutarsız | 25 | Veri hatası belirtisi. |
| > %10,5 tek gün sıçrama | 605 (> %25: 83) | Günlük fiyat sınırı ±%10. Bunların 106'sı KAP'taki bir sermaye, hak kullanımı ya da kâr payı bildirimine ±5 gün yakın. **Yakınlık kurumsal işlemi kanıtlamaz.** Açık veri hatası örneği: TRHOL +%10.124 ve ertesi gün −%99. KAP listesi 2022-10-17'den önceyi kapsamıyor (33 sıçrama kapsam dışı). |
| Son güne gelmeyen hisse | 1 | ISKUR (son mum 2026-08-12). Borsadan çıkış mı veri kesintisi mi doğrulanmadı. |

**İki veritabanı farkı: geçmiş veri değişmiş.**

- Ortak 156.441 günde, %0,1'i aşan fark 4 hissede ve 927 günde var: MGROS −%1,32, FLAP −%1,07, ETILR −%0,29, KBORU
  −%0,19.
- Örüntü dört hissede de aynı: **2025-11-10 … 2026-10-12** arasında sabit oran, sonrasında fark yok.
- MGROS örneği: canlı veritabanında 13.10.2026 öncesi değerler 501,0 ve 503,0 gibi yuvarlak; araştırma
  veritabanında ×0,987.
- Yorum: Araştırma veritabanının son bir yıllık bloğu, 13.10 civarındaki bir olaydan sonra yeniden indirilmiş ve
  geriye dönük düzeltilmiş olabilir. Bloğun öncesi eski indirmeden kalma; bu yüzden **araştırma veritabanında
  2025-11-07 → 2025-11-10 sınırında %0,2–1,3 taban kayması olası**.
  - Bu örüntü geriye dönük temettü ya da bölünme düzeltmesiyle **uyumlu**. Ancak yakın KAP kâr payı bildirimi
    bulunamadı, **neden kesinleştirilmedi**. Fark temettü düzeltmesine bağlanmadı.

**Geçmişte erişilebilir veri ile bugünkü düzeltilmiş veri:**

- Fiyatlar `auto_adjust=True` ile, yani sonraki kurumsal işlemler için geriye dönük düzeltilmiş olarak indiriliyor.
  Bu yüzden geçmiş bir günde gerçekte görülen fiyat ile veritabanındaki fiyat farklı olabilir.
- Getiri oranları büyük ölçüde korunur. Mutlak fiyat ve TL hacim etkilenebilir. Hak kullanım günündeki gerçek
  düşüş, düzeltilmiş seride görünmeyebilir; bu da stop tetiklenmesini değiştirebilir.
- **Düzeltilmemiş fiyat elimizde olmadığından etki ÖLÇÜLEMEDİ.** Geleceğe bakma var ya da yok diye kesin bir iddia
  yapılmadı.
- Maruziyet (FAZ 2 kabul, canli_ortak): tutma süresinde KAP kâr payı ya da sermaye bildirimi olan işlem 12 ayda
  14 / 130, 2024'te 14 / 123. Gösterge penceresinde neredeyse hepsi.

**Seçim ve sıralama belirsizliği** ("pozisyon açıkken bayraklı gün yok" bulgusunun sınırı):

- FAZ 2 kabul işlemlerinde tutma süresinde bayraklı mum 0. 250 günlük gösterge penceresinde sıçrama ya da tutarsızlık
  2–15 işlemde var.
- **Bütün aday planların** %27,1'inde (12.412 / 45.737; canli_ortak %26,9) gösterge penceresinde > %10,5 sıçrama var.
- Bu planlar seçilen, elenen ve sıralamada geride kalan adaylardır. Sıçramalı veri göstergeleri, dolayısıyla teknik
  skoru ve sıralamayı etkilemiş olabilir; hangi adayın seçileceği değişebilirdi.
- Etki ölçülmedi. Ölçmek için düzeltilmemiş ya da temizlenmiş seriyle **ayrı bir duyarlılık koşusu** gerekir. Bu
  yapılmadı; orijinal sonuçlar korunurken ayrı onayla yapılabilir.

## I.5 Fiyat izlenebilirliği: `bist_haber/fiyat_izi.py` (sürüm `fiyat_izi_v1`, HAZIRLIK)

Canlı kod bu modülü **çağırmıyor**; `db.connect` göçü otomatik yapmıyor.

**Tablolar** (yalnız ekleme; ekle-yalnız tetikleyicilerle korunuyor):

- `fiyat_indirme`: her indirmenin zamanı, kaynağı ve kaynak sürümü, indirme ayarları (period, interval,
  auto_adjust), düzeltme türü, kod sürümü, hisse ve satır sayısı, değişen satır sayısı, yazılan satırların SHA-256
  özeti.
- `fiyat_eski`: bir indirme mevcut satırı farklı değerle değiştirirse **eski satır** saklanır. Böylece belli bir
  indirmeden önceki durum birebir geri kurulabilir (`durum_once`).
- `prices.indirme_id`: satırın bugünkü değerini koyan indirme. Değişmeyen satır yeniden yazılmaz. Eski satırlarda
  NULL, yani "bilinmiyor"; **uydurulmaz**.
- `veri_anlik`: backtest veri kümesinin ayrı SQLite dosyası olarak anlık görüntüsü ve parmak izi (`anlik_goruntu`).

**Geçmiş için sınır:**

- Bu tablolar kurulmadan önceki fiyat sürümleri **korunmamıştır ve geri oluşturulamaz**.
- Araştırma veritabanının bugünkü parmak izi alındı (`sonuclar/arastirma_db_parmak_izi.json`, SHA-256 `d563b954…`).
  FAZ 2 kabul koşusuyla aynı veri olduğu **doğrulanamaz**; yalnız boyut ve son fiyat günü aynı.

**Kopyada prova** (`kopyada_goc.py`, `sonuclar/kopyada_goc.json`; canlı dosyanın değiştirilme zamanı aynı kaldı):

1. Canlı veritabanının sqlite yedek kopyası alındı: bütünlük ok.
2. Göç yapıldı (otomatik yedekli): bütünlük ok.
3. 24 eski tablonun satır özetleri aynı; fiyat parmak izi aynı.
4. Bugünkü `db.connect` açtı. `prices.update`'in bugünkü yazma ifadesi çalıştı (`indirme_id` NULL kaldı).
5. Sahte indirme denendi: 3 değişen satır `fiyat_eski`'ye yazıldı; önceki durum **birebir** geri kuruldu.
6. Geri dönüş (yedek geri yükleme) denendi: bütünlük ok, tablolar göç öncesiyle aynı, yeni tablo yok.

**Testte bulunup düzeltilen tasarım hatası:** Değişmeyen satırlar da yeni indirme numarasıyla yeniden yazılıyordu;
önceki durum yanlış kuruluyordu. Artık yalnız yeni ya da değişen satır yazılıyor.

**Canlıya alma (onaylanmadı):**

- `prices.update` yazımı `fiyat_izi.yaz` üzerinden yapılır; göç bir kez çalıştırılır.
- Yedek, bütünlük kontrolü ve geri dönüş adımları FAZ 1 v2 geçişindeki gibidir.
- Göç yalnız ekleme yaptığı için eski kod yeni tablo ve sütunları yok sayar.
- Yedek yalnız göçten sonra yeni kullanıcı verisi yoksa geri yüklenir.

**Depolama:** Her indirme yalnız değişen satırları saklar. Düzeltme olayı başına yaklaşık bir yıllık satır (~250 /
hisse) birikir. Anlık görüntü dosyası ~10–40 MB'tır.

## I.6 Borsadan çıkan hisseler ve tarihsel sektör: kaynaklar

| Kaynak | Ne sağlar | Durum |
|---|---|---|
| [Borsa İstanbul pay piyasası verileri](https://borsaistanbul.com/en/data/equity-market-data) | "Borsa İstanbul pazarlarından kalıcı olarak çıkarılan şirketler" dosyası (şirket listesi) | Erişilebilir, indirilmedi. Fiyat geçmişi içermiyor. |
| Borsa İstanbul DataStore ([veri sayfası](https://www.borsaistanbul.com/en/data/equity-market-data/market-data)) | Gün sonu fiyat ve hacim (akademik dışı kullanımda pazar başına aylık 50 TL bildirildi) | Ücretli. Borsadan çıkan hisseleri kapsayıp kapsamadığı **doğrulanamadı**. |
| [BIST sektör endeksleri](https://borsaistanbul.com/en/index/1/8/sector) + sektör değişikliği duyuruları ([örnek](https://borsaistanbul.com/en/announcement/15358/changes-be-made-within-scope-bist-stock-indices-due-sector-change-arsan-tekstil)) | Güncel bileşenler ve tek tek değişiklik duyuruları | Tarihsel sektör arşivi **bulunamadı**. Duyurulardan yeniden kurmak mümkün ama emek ister ve eksik kalabilir. |
| KAP / araştırma veritabanındaki `kap_liste` (2022-10-17'den beri) | İşlem sırası kapatma ve kottan çıkarma duyuruları | 7 bildirim (ör. OLMK, TIRE). Finansal rapor veren ama fiyat verisi olmayan 167 kod var; bunların çoğu borçlanma aracı ihraççısı ya da fon. Borsadan çıkan pay **ayrılamadı**. |

**Sınırlama (sürüyor):**

- Hayatta kalma yanlılığı giderilemedi.
- Sektör listesi güncel KAP listesi (09.11.2026).
- Borsadan çıkan hisselerin fiyat geçmişi ve tarihsel sektör ücretli ya da elle kurulacak kaynaklara bağlı; bu
  fazda alınmadı. Veri satın alma ya da indirme ayrı karar ister.

## I.7 Model metriklerinin kökeni (`sonuclar/model_metrik_kokeni.json`)

| | `tp1_v1` |
|---|---|
| Model dosyası | `bist_haber/modeller/tp1_v1.json`, SHA-256 `09f8e5e0…` |
| Kod | commit `e90d0ab` (2026-11-15 12:03; model dosyasının tek commit'i) |
| Eğitim | 34.579 plan, 587 hisse, 2022-11-09 … 2026-11-12, TP1 %29,3 |
| Sınama (dosyadan) | Son 12 ay: AUC 0,605 (%90 aralık 0,567–0,646), Brier becerisi %2,81 |
| Etiket sürümü | **`etiket2.csv` en olası, kesin değil** |
| Etiket tanımı | y = `tp1_goruldu`, journal s2 |
| Veri sürümü | Etiketleme anındaki parmak izi kayıtlı değil |

- **Etiket sürümü gerekçesi:** Model `etiket3.csv`'den (12:45) önce kaydedilmiş, yani etiket3 olamaz. etiket ve
  etiket2 aynı kapanmış sayıyı (34.665) ve aynı TP1 oranını veriyor; model girdileri etiket2 sütunlarıyla
  eşleşiyor. Dosyaların SHA-256 değerleri kayıtta.
- **Dikkat:** Etiket dosyaları eski oturumun geçici klasöründe, repoda değil.
- **Doğrulanmayan:** Modelin 34.579 planı ile filtrelenmiş 34.665 arasındaki 86 fark.

**Sonradan bulunan etiket sorunları (eski metrikler korunur):**

| Sorun | Etki |
|---|---|
| `tp1_hedefi` (Ek F-A) | 91 plan |
| s3 stop altı girişsiz (Ek H4) | ~293 plan; y = 0, örnek çıkar |
| Fiyat taban kayması (I.4) | Ölçülmedi |

Düzeltilmiş etiketlerle yeniden sınama **yapılmadı**, çünkü sınama model uydurmayı gerektirir ve model eğitimi yasak.
Etki yalnız sayı olarak raporlandı.

## I.8 Testler

| Komut | Sonuç |
|---|---|
| `tests.test_faz3_metrik` | 8 test: elle hesap (MDD, Sortino, Sharpe, CAGR, Ulcer), sıfır net kayıp sayılır, ardışık seriler, tanımsız durumlar, 50 rastgele çapraz doğrulama, canlı panel metriği, MAE/MFE alt sınır, iki R paydası, çıkış sonrası ayrımı |
| `tests.test_fiyat_izi` | 7 test: yedekli göç, satırlar aynı, tekrar göç yok, eski yazıcı çalışır, başarısız göç geri alınır, değişen satır korunur ve önceki durum birebir kurulur (iki indirmeli), ekle-yalnız, parmak izi sıra bağımsız, anlık görüntü |
| Tam takım (ağ engelli, `run_offline.py`) | **Ran 618 tests … OK**, ağ denemesi 0 (603 + 15 yeni) |

## I.9 Değişen dosyalar (dal `faz3-metrik`)

- **Yeni:**
  - `bist_haber/fiyat_izi.py` (canlıya bağlı değil)
  - `arastirma/faz3/{veri_guvenilirlik, veri_ayrintilari, yeniden_duzeltme, aday_maruziyeti, metrikler, mae_mfe,
    faz3_hesap, kopyada_goc}.py`
  - `arastirma/faz3/sonuclar/*.json`
  - `tests/test_faz3_metrik.py`, `tests/test_fiyat_izi.py`
- **Değişmeyen:** Canlı modüller (journal, ready, defter, prices, db), simülatör ve FAZ 2 kabul dosyaları.

## I.10 Kalan sınırlamalar

1. Düzeltilmemiş fiyat yok. Geçmişte erişilebilir fiyatla fark ve etkisi ölçülemedi.
2. Sıçramalı ya da şüpheli veriyle duyarlılık koşusu yapılmadı (ayrı onayla yapılabilir).
3. Hayatta kalma yanlılığı ve güncel sektör listesi sürüyor (I.6).
4. Eksik gün, halka arz ve işlem durdurma ayrımı kısmen yapılabildi (I.4).
5. MAE/MFE gün içi çıkışlarda alt sınırdır.
6. Model etiket sürümü olasılıkla bağlandı; etiket dosyaları repoda değil.
7. Fiyat izlenebilirliği yalnız hazırlık; canlıya alınana kadar yeni indirmeler de izlenmiyor.

## I.11 FAZ 1 canlı doğrulaması (ayrı)

16.11 14:32'de canlı veritabanı salt-okunur okundu:

- 2 tahmin (BAHKM, ENERY; giriş günü 16.11), 0 sonuç, 0 değerlendirme, 0 olay.
- Son çalıştırma 16.11 09:42 sabah kontrolü. Fiyatlar 13.11'e kadar.
- Geçişten sonra akşam analizi henüz yok. **FAZ 1 kabul edilmedi.**

**Onay beklenen:** FAZ 3 kabulü, canlıya alma (`fiyat_izi`) ve FAZ 4. Hiçbiri yapılmadı.


---

# Ek I2 (16.11.2026) — FAZ 3 son düzeltmeler ve kabul önerisi

Canlı kod ve veritabanı değişmedi. Model eğitilmedi. Yeni kapsam açılmadı.

## I2.1 MAE/MFE: işaret, sınır yönü, kesin ve olası hareket

**İşaret** (R_plan birimi; 1 R = plan girişi − SL):

- **MAE = (pozisyon açıkken en düşük fiyat − dolum) / R.** Negatif ya da 0 olarak tutulur; aleyhte hareketin işaretli
  değeridir, pozitif kayıp büyüklüğü değildir.
- **MFE = (pozisyon açıkken en yüksek fiyat − dolum) / R.** Pozitif ya da 0'dır.

**Kesin bilinen hareket:**

- Giriş mumu (giriş açılışta olduğundan mumun tamamı girişten sonradır).
- Ara mumlar.
- Çıkış fiyatı.

**Olabilecek hareket:** Gün içi çıkış mumunda çıkıştan önceki kısım. O mumun en yüksek ya da en düşük değeri
çıkıştan önce de sonra da olmuş olabilir.

**Kural kısıtıyla sınırlar** (`arastirma/faz3/mae_mfe.py → sinirlar`):

| Çıkış türü | MAE | MFE |
|---|---|---|
| Stopta gün içi (SL, başabaş) | **Kesin.** Stop ilk dokunuşta satar; çıkıştan önce fiyat stopun üstündeydi. | Aralık: [kesin, mumun en yükseği]. Hesaplanan değer **alt sınır**. |
| Hedefte gün içi (TP2) | Aralık: [mumun en düşüğü, kesin]. Hesaplanan değer işaretli olarak **üst sınır**, büyüklük olarak alt sınır. | **Kesin.** Çıkıştan önce fiyat hedefin altındaydı. |
| Açılışta çıkış ya da süre doldu (kapanış) | Kesin | Kesin |
| Alış stopun altında (s3) | **Varsayımsal**: çıkış bir varsayım | Varsayımsal |

- **Varsayım:** Stop ve hedef emri tam seviyesinden dolar. Boşluk varsa çıkış açılıştandır (ayrı satır).
- **Ek I.3'ün düzeltilmesi:** I.3'teki "gün içi çıkışta değer bir alt sınırdır" ifadesi **eksikti**. Doğrusu:
  - stopta çıkışta MAE kesin, MFE alt sınır;
  - hedefte çıkışta MFE kesin, MAE işaretli üst sınır.
- **Canlı kod:** `defter.mae_mfe` ve `yaklasik` bayrağı aynı değeri hesaplar, ama bütün gün içi çıkışları "yaklaşık"
  sayar. Bu daha kaba bir etikettir; canlı kod değiştirilmedi.

**Elle doğrulanabilir örnekler** (dolum 100, SL 95, 1 R = 5 TL; `tests.test_faz3_metrik.MaeMfeSinirlari`, 3 test):

1. **Stopta çıkış.** 1. gün mum en yüksek 104, en düşük 98. 2. gün en yüksek 106, en düşük 94; 95'ten SL.
   - MAE = (95 − 100) / 5 = **−1,0, kesin**. 94 stoptan sonradır; o anda pozisyon yoktu.
   - MFE kesin = (104 − 100) / 5 = **0,8**. Olası en iyi = (106 − 100) / 5 = **1,2**, çünkü 106 çıkıştan önce olmuş
     olabilir.
2. **Hedefte çıkış.** 2. gün en yüksek 121, en düşük 96; 120'den TP2.
   - MFE = (120 − 100) / 5 = **4,0, kesin**. 121 hedeften sonradır.
   - MAE kesin = (98 − 100) / 5 = **−0,4**. Olası en kötü = (96 − 100) / 5 = **−0,8**.
3. **Süre doldu** (2. gün açılış 90, en yüksek 99, en düşük 89, kapanış 97): MAE −2,2 ve MFE 0,8, ikisi de kesin.
   **Açılışta boşlukla SL (90):** MAE −2,0, kesin. **Stop altı alış:** "varsayımsal".

**FAZ 2 kabul işlemlerinde** (canli_ortak; `sonuclar/mae_mfe_sinirlari.json`):

| Dönem | MAE kesin, MFE aralık | MAE aralık, MFE kesin | Kesin | Varsayımsal |
|---|---|---|---|---|
| 12 ay (130 işlem) | 91 | 14 | 21 | 4 |
| 2024 (123 işlem) | 72 | 21 | 26 | 4 |

- MAE belirsizlik genişliği bütün işlemlerde **0**. Hedef gününden önceki en kötü fiyat daha önceki bir günde
  görülmüş.
- MFE belirsizlik genişliği: medyan 0, p95 0,39 R (12 ay) ve 0,22 R (2024), en çok 1,54 R.
- MFE medyanı 12 ayda 0,83 (kesin) ile 0,92 (olası) arasında.

## I2.2 Yeniden değerlendirme ile yeniden eğitimin ayrımı

**Önceki ifadenin düzeltilmesi:** "Düzeltilmiş etiketlerle yeniden sınama model eğitmeyi gerektirir" ifadesi **yalnız
dönem dışı sınama için** doğrudur. Etkin model sabit tutularak aynı örnekler ve girdiler üzerinde metrik **yeniden
hesaplanabilir** ve hesaplandı (`yeniden_degerlendirme.py`; model eğitilmedi).

- **Bu hesap EĞİTİM İÇİDİR.** `tp1_v1`, kapanmış bütün verilerle (2022-11-09 … 2026-11-12) uydurulmuştur; bu
  örneklerin hepsini görmüştür. Sonuç **dönem dışı doğrulama değildir**.
- **Dönem dışı karşılaştırma neden yapılamıyor:** `tp1_v1.json`'daki dönem dışı sonuçlar (son 12 ay AUC 0,605),
  test döneminden önceki verilerle ayrı uydurulan kat modellerinden geliyor. O kat modelleri ve dönem dışı tahminleri
  **saklanmamış**. Yeniden hesaplamak kat modellerini yeniden uydurmayı, yani eğitimi gerektirir; yapılmadı.

**Eşleşme:** etiket2'nin 34.579 eğitim örneğinin 34.579'u FAZ 2 plan dosyasıyla `(hisse, tarih)` anahtarıyla
eşleşti. Girdileri farklı olan 0.

| `tp1_v1` sabit, eğitim içi | n | AUC | Brier | TP1 % |
|---|---|---|---|---|
| A: eski etiket (`tp1_goruldu`) | 34.579 | 0,6361 | 0,19807 | %29,27 |
| B: düzeltilmiş etiket (`tp1_hedefi`; 91 örnekte 0 → 1) | 34.579 | 0,6347 | 0,19922 | %29,54 |
| C: B + s3 stop altı girişsiz çıkarılmış (250 örnek) | 34.329 | 0,6350 | 0,20002 | %29,75 |

- **Önce ve sonra etkisi:** AUC −0,001, Brier +0,002. Eski rakamlar ilgili etiket sürümüne ait olarak korunur.
- Bu fark dönem dışı performans için bir tahmin **değildir**.

## I2.3 Geçici kanıtlar arşive alındı

**Arşiv:** `data/backtest/arsiv/faz3_koken_20261116/` (435 MB; Git dışı, `.gitignore: data/backtest/`).

- **İçerik:** 21 dosya.
  - Eski çalışma klasöründen: etiket, etiket2 ve etiket3 dosyaları ile logları, eski `etiketle.py`, `model.py`,
    `sonuc.json`, `egit_sonuc.json`, indirme betiği ve logu, deneme dosyaları, KAP logları, 15.11'e ait iki
    araştırma veritabanı yedeği.
  - FAZ 2'den: `planlar_seviyeli.csv` ve `etiketle.log`.
- Her dosyanın SHA-256 değeri, boyutu, satır sayısı ve değiştirilme zamanı kaydedildi. Kopyalar kaynakla doğrulandı
  (21 / 21 aynı). Manifest: `arastirma/faz3/sonuclar/arsiv_manifest.json` (Git'te) ve arşivde.
- `gunluk_model_kaydi.txt`: eski oturum günlüğünden model kaydı komutunun ve çıktısının değiştirilmemiş alıntısı.
- Kaynak dosyalar silinmedi.

**Model–etiket bağlantısı:** `tp1_v1` ← **etiket2.csv**, kanıtla bağlandı (kriptografik değil).

- **Kanıtlar:**
  - Oturum günlüğü, 15.11 08:55:19Z komutu: `egit.py … a6/etiket2.csv … --kaydet`.
  - Komutun 08:59:20Z çıktısı: "kaydedildi: …tp1_v1.json λ 1000 bantlar [0.229, 0.34] grup 45 boyut 8692". Repodaki
    dosya 8.692 bayt, bantlar 0,2289 / 0,3402, 45 grup; hepsi tutuyor.
  - Bu çıktıyla commit `e90d0ab` (09:03:32Z) arasında modele yazan başka komut görülmedi.
  - Eğitim süzgeciyle etiket2'nin 45 grup sayısı birebir aynı.
- **Kalan belirsizlik:**
  - O anda dosya parmak izi alınmadı.
  - etiket3.csv de aynı grup sayılarını veriyor; yani **sayım tek başına ayırt etmez**. Ayırt eden kanıt günlük
    komutudur.
  - Dosya zamanları yalnız destekleyici bilgidir.
- **Çözülen:** 34.579 ile 34.665 arasındaki 86 plan farkı, eğitimdeki "x_trend dolu" süzgecinden geliyor.
- **Veri sürümü:** Eğitim anındaki fiyat verisinin parmak izi yok. Arşivdeki 12:18 ve 12:59 yedekleri eğitimden
  sonra alınmış; aynı veri olduğu **doğrulanamaz**.

## I2.4 FAZ 3 özeti

**A. Metrik ve izlenebilirlik altyapısında tamamlananlar:**

- Bağımsız metrik doğrulaması: 8 kabul koşusunda 10 metrik birebir; 50 rastgele çapraz sınama; metrik hatası yok.
- Ek metrikler: CAGR, oynaklık, Calmar, Ulcer, ödeme oranı, piyasada kalma, aylık getiri. Getiri, R ve süre
  dağılımları; ardışık kayıp serileri.
- MAE/MFE: iki R paydası, kesin ve olası sınırlar, çıkış sonrası hareketin ayrı tutulması.
- `fiyat_izi_v1` şeması (hazırlık): indirme kaydı, eski satır günlüğü, `indirme_id`, anlık görüntü ve parmak izi.
  Kopyada göç, geri kurma ve geri dönüş provası tamam.
- Araştırma veritabanının bugünkü parmak izi; model kökeni kaydı; köken arşivi.

**B. Doğrulanmış veri sorunları** (gözlem olarak kesin; nedenleri ayrı):

- 2024-04-09'da piyasa geneli düşük kapsama (329 eksik).
- 19 tekil eksik gün.
- 25 OHLC tutarsızlığı.
- 605 tek gün > %10,5 sıçrama; aralarında açık veri hataları var (TRHOL +%10.124 / −%99).
- 4.296 sıfır hacim; 3.762 bayat mum.
- İki veritabanında aynı gün için farklı fiyat: 4 hisse, 927 gün. Geçmiş veri değişmiş.
- Fiyatlar kaynak, zaman ve ayar kaydı olmadan yeniden yazılıyor (`INSERT OR REPLACE` + `auto_adjust`).

**C. Nedeni ya da etkisi ölçülmemiş sorunlar:**

- Sıçramaların nedeni. KAP'a yakınlık (106) kanıt değildir.
- İki veritabanı farkının nedeni. Geriye dönük düzeltmeyle uyumlu, ama kesinleşmedi.
- Araştırma veritabanında blok sınırı taban kaymasının etkisi.
- Düzeltilmiş ile o gün erişilebilir fiyat farkının sonuçlara etkisi (düzeltilmemiş fiyat yok).
- 191 geç başlayan hissede halka arz ile veri başlangıcı ayrımı.
- Bayat ya da sıfır hacimli mumların işlem görmeme mi veri taşıma mı olduğu.
- **Adayların %27,1'inin** gösterge penceresinde sıçrama var.
  - Bu, **%27'sinin hatalı olduğu anlamına gelmez**; sonuçların etkilenmediğini de göstermez.
  - Bu konuda **duyarlılık analizi yapılmadı**.

**D. Tarihsel performans iddialarına sınırlamalar:**

- FAZ 2 rakamları, kaynağı ve zamanı kayıtlı olmayan, sonradan yeniden düzeltilebilen bir veri sürümüne dayanır. Aynı
  veri kümesiyle yeniden üretilebilirlik ancak bugünkü parmak iziyle mümkündür.
- Seçim ve sıralama, şüpheli mum içeren pencerelerden etkilenmiş olabilir; ölçülmedi.
- Hayatta kalma yanlılığı ve güncel sektör listesi sürüyor. Borsadan çıkan hisseler ve tarihsel sektör verisi
  ücretli ya da elle kurulacak kaynaklara bağlı.
- MAE/MFE gün sonu verisiyle hesaplanıyor. Stop çıkışlarında MFE, hedef çıkışlarında MAE yalnız sınır olarak
  verilir.
- Model metrikleri belirli bir etiket ve veri sürümüne aittir; dönem dışı yeniden doğrulama eğitim gerektirdiği için
  yapılmadı.
- Bütün bunlar sonuçlar görüldükten sonra yapılan incelemedir; dönem dışı kanıt değildir.

## I2.5 FAZ 3 kabul önerisi

**Öneri:** FAZ 3, **metrik ve izlenebilirlik altyapısı ile veri güvenilirliği envanteri** olarak kabul edilebilir.

- **Gerekçe:**
  - metrikler bağımsız kodla doğrulandı;
  - MAE/MFE tanımları ve sınırları elle doğrulanabilir testlerle belirlendi;
  - veri sorunları gözlem ve neden olarak ayrıldı;
  - izlenebilirlik şeması kopyada göç ve geri dönüşle sınandı;
  - geçici kanıtlar arşivlendi ve model kökeni kanıtla bağlandı.
- **Kabul şunları kapsamaz:** tarihsel performansın güvenilir olduğu; veri sorunlarının etkisiz olduğu;
  `fiyat_izi`'nin canlıya alınması.
- **Açık kalanlar** (her biri ayrı onay ister):
  - duyarlılık analizi;
  - düzeltilmemiş fiyat edinimi;
  - borsadan çıkan hisse ve tarihsel sektör verisi;
  - `fiyat_izi` canlı geçişi;
  - FAZ 4.

**Testler:**

- `tests.test_faz3_metrik`: 11 / 11 (3 yeni sınır testi).
- `tests.test_fiyat_izi`: 7 / 7.
- Tam takım (ağ engelli): **Ran 621 tests … OK**, ağ denemesi 0 (618 + 3).

## I2.6 FAZ 1 (ayrı)

- 16.11 14:32'de canlı veritabanı salt-okunur okundu: 2 tahmin, 0 sonuç, 0 değerlendirme, 0 olay. Son çalıştırma
  09:42 sabah kontrolü. Fiyatlar 13.11'e kadar.
- Bu ekten önce yeni bir okuma: **16.11 17:23**, durum aynı (2 tahmin, 0 sonuç, 0 değerlendirme, 0 olay, son çalıştırma 09:42 sabah kontrolü). Bu akşamki analiz henüz çalışmadı.
- **FAZ 1 kabul edilmedi.**

---

# EK I3 (16.11.2026) — FAZ 3 KABUL KAYDI

Kullanıcı FAZ 3'ü onayladı ve FAZ 4'e başlamayı onayladı (16.11.2026). Kabul edilen sürüm: commit `94d2fc8` (dal `faz3-metrik`), etiket `faz3-kabul`.

- Kapsam: metrik ve izlenebilirlik altyapısı, veri güvenilirliği envanteri (Ek I, I2).
- Kapsam dışı: tarihsel performansın güvenilirliği, veri sorunlarının etkisizliği, `fiyat_izi` canlı geçişi, duyarlılık analizi (yapılmadı).
- Canlı kod ve veritabanı değişmedi.


---

# EK J (16.11.2026) — FAZ 4: strateji türü × piyasa rejimi (tekil işlem araştırması; dal `faz4-rejim`)

**Konumu:**

- Canlı kod, veritabanı, etkin model ve seçim kuralları **değişmedi**.
- Model eğitilmedi; ücretli yapay zekâ çağrısı yok; güncelleme yayımlanmadı.
- **Haber şartı yok:** Bu evren canlı haberli hazır fırsat listesi değildir.
- **Bağımsız doğrulama değildir:** Kullanılan planlar ve dönemler daha önce incelendi (FAZ 2, `tp1_v1` eğitimi,
  Aşama 6).
- **Yalnız tekil işlem sonuçlarıdır:** Rejimlere ayrılmış tekil işlemlerden portföy getirisi ya da portföy düşüşü
  **çıkarılmadı**. Aynı hissenin üst üste sinyalleri ayrı işlem sayılır; bu bir portföyün izleyebileceği yol değildir.

## J.1 Ön kayıt, sürümler, yöntem

**Ön kayıt:** `arastirma/faz4/rejim_tanimi.json`, commit **`c1a4192`** (17:31). Analiz kodu ve testleri commit
`603ab1d`. Sonuçlar bu iki commit'ten **sonra** üretildi.

**Rejim:** Canlı `bist_haber/regime.py` kullanıldı (değiştirilmedi; son değişiklik commit `d673cc0`, SHA-256
`861fd47f…`).

- **Trend:** BIST 100 kapanış, EMA50 ve EMA200 sıralaması. Sınıflar: yükseliş, düşüş, kararsız.
- **Oynaklık:** 20 günlük ATR%'nin **o güne kadarki** son 252 gözlemdeki yüzdeliği. %30'un altı düşük, %70'in üstü
  yüksek. Eşikler canlı kodda sabit; tüm dönemden hesaplanmaz.
- **Genişlik kullanılmadı:** Canlı kodda sınıf eşiği yok; eşik koymak yeni bir kural olurdu.
- **Karar anı:** Sinyal günü kapanışı. Yalnız o güne kadarki BIST 100 mumları kullanıldı. 25 Aralık gibi eksik
  günlerde son mevcut gün alındı (canlıyla aynı).

**Veri:**

- `planlar_seviyeli.csv` (SHA-256 `2413d1df…`; FAZ 3 arşivinde).
- `arastirma_5y.db` (bugünkü parmak izi `d563b954…`). FAZ 3'teki veri sorunları geçerli.

**Örnek:**

- Evren `canli_ortak`; yalnız sonucu kapanmış planlar.
- Çıkarılanlar:
  - 5.352 girişsiz (açılış azami girişin üstünde);
  - 42 açık;
  - **217** s3 tür A (açılış ≤ SL). Bunlar s2'deki yapay kârı taşıyordu; çıkarıldı.
- Kalan **30.470** tekil işlem. Bütün sinyal günlerinin rejimi hesaplanabildi.
- `mevcut_fiyat` türü bu evrende yok. "Destekten tepki" türünde toplam 74 örnek var.

**Ölçütler:**

- TP1 % = y (`tp1_hedefi`).
- Kazanma % = maliyet sonrası net > 0.
- Ortalama net % ve ortalama R (journal; komisyon %0,2 + kayma %0,1).
- **%95 güven aralığı:** sinyal gününe göre **küme bootstrap** (2.000 tekrar, sabit tohum). Aynı günün gözlemleri
  birlikte örneklenir.
- **Yeterlilik:** `defter.guven`. n < 30 ya da bağımsız gün < 20 ise **YETERSİZ**.
- **Aynı hisse uyarısı:** Önceki sinyalden 10 işlem günü içinde gelen sinyal payı.
  - Bu pay **%54–83** ve çok yüksek. Aynı hisseden ilişkili gözlemler var.
  - Gün kümesi aralıkları bunu **düzeltmez**. Gerçek belirsizlik tablolardakinden geniştir; örnek sayısı tek başına
    güvenilirlik kanıtı değildir.
- **Veri kalitesi:** Gösterge penceresinde (250 mum) ve tutma süresinde > %10,5 sıçrama olan plan payı (FAZ 3 tanımı).

**Rejim gün dağılımı** (sinyal günleri):

| Rejim | Gün |
|---|---|
| yükseliş / düşük | 286 |
| yükseliş / normal | 226 |
| yükseliş / yüksek | 112 |
| kararsız / yüksek | 148 |
| kararsız / normal | 135 |
| kararsız / düşük | 38 |
| düşüş / normal | 35 |
| düşüş / yüksek | 14 |
| düşüş / düşük | 0 |

Düşüş rejimi az ve kümelenmiş (35 + 14 gün).

## J.2 Sonuç tabloları

Tablolar `arastirma/faz4/sonuclar/rejim_tablolari.md` dosyasından aynen alındı; tam veri `rejim_sonuclari.json`
içinde.

**Ana gruplar — tüm dönem (2022-11 … 2026-11-13): strateji × trend × oynaklık**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| destekten tepki · düşüş · normal | 1 | 1 | 0.0 (—) | 0.0 (—) | -5.23 | -1.166 (—) | 0.0 | 0.0 / 0.0 | **YETERSİZ** |
| destekten tepki · kararsız · düşük | 2 | 2 | 100.0 (100.0…100.0) | 100.0 (100.0…100.0) | 24.535 | 3.72 (+3.54…+3.90) | 100.0 | 0.0 / 0.0 | **YETERSİZ** |
| destekten tepki · kararsız · normal | 11 | 11 | 27.27 (0.0…54.5) | 27.27 (0.0…54.5) | -1.859 | -0.298 (-0.99…+0.58) | 54.5 | 36.4 / 0.0 | **YETERSİZ** |
| destekten tepki · kararsız · yüksek | 3 | 3 | 33.33 (0.0…100.0) | 66.67 (0.0…100.0) | 7.222 | 0.794 (-0.80…+2.59) | 33.3 | 0.0 / 0.0 | **YETERSİZ** |
| destekten tepki · yükseliş · düşük | 37 | 31 | 24.32 (11.6…37.8) | 24.32 (11.6…37.8) | -0.093 | -0.101 (-0.65…+0.55) | 64.9 | 13.5 / 2.7 | düşük güven |
| destekten tepki · yükseliş · normal | 17 | 13 | 23.53 (5.6…46.7) | 23.53 (5.6…46.7) | -0.309 | 0.069 (-0.81…+1.16) | 70.6 | 58.8 / 5.9 | **YETERSİZ** |
| destekten tepki · yükseliş · yüksek | 3 | 3 | 0.0 (0.0…0.0) | 0.0 (0.0…0.0) | -7.83 | -1.03 (-1.04…-1.01) | 100.0 | 0.0 / 0.0 | **YETERSİZ** |
| geri çekilme · düşüş · normal | 446 | 35 | 38.12 (30.5…46.1) | 50.22 (43.8…56.9) | 4.762 | 0.695 (+0.41…+1.00) | 79.4 | 9.2 / 0.0 | düşük güven |
| geri çekilme · düşüş · yüksek | 19 | 7 | 47.37 (18.2…66.7) | 47.37 (18.2…66.7) | 3.458 | 0.721 (-0.26…+1.67) | 73.7 | 5.3 / 0.0 | **YETERSİZ** |
| geri çekilme · kararsız · düşük | 592 | 38 | 20.95 (15.4…26.7) | 26.86 (20.9…32.9) | -1.463 | -0.147 (-0.35…+0.07) | 77.5 | 38.0 / 0.3 | düşük güven |
| geri çekilme · kararsız · normal | 1888 | 135 | 27.22 (24.2…30.6) | 32.94 (29.5…36.7) | 0.592 | 0.103 (-0.03…+0.24) | 79.2 | 32.9 / 0.2 | orta güven |
| geri çekilme · kararsız · yüksek | 1955 | 148 | 29.31 (26.4…32.1) | 36.06 (32.7…39.4) | 1.634 | 0.264 (+0.14…+0.39) | 82.5 | 20.1 / 0.9 | orta güven |
| geri çekilme · yükseliş · düşük | 5920 | 286 | 24.41 (22.4…26.6) | 29.19 (27.1…31.5) | -0.536 | -0.033 (-0.12…+0.06) | 81.2 | 17.5 / 0.4 | orta güven |
| geri çekilme · yükseliş · normal | 4990 | 226 | 31.5 (27.5…35.6) | 36.41 (32.4…40.6) | 1.797 | 0.272 (+0.11…+0.44) | 79.3 | 37.8 / 0.2 | orta güven |
| geri çekilme · yükseliş · yüksek | 2523 | 111 | 16.88 (13.7…20.6) | 20.89 (17.4…25.1) | -2.832 | -0.354 (-0.49…-0.19) | 80.7 | 16.4 / 0.8 | orta güven |
| kırılım · düşüş · normal | 320 | 35 | 31.87 (25.9…37.7) | 36.88 (30.7…42.5) | 0.835 | 0.171 (-0.08…+0.43) | 53.8 | 9.4 / 0.3 | düşük güven |
| kırılım · düşüş · yüksek | 40 | 13 | 30.0 (0.0…47.1) | 37.5 (0.0…62.5) | 0.1 | 0.162 (-0.95…+0.93) | 37.5 | 15.0 / 0.0 | **YETERSİZ** |
| kırılım · kararsız · düşük | 222 | 37 | 29.73 (23.0…37.3) | 31.98 (24.7…39.9) | 0.678 | 0.098 (-0.20…+0.45) | 55.9 | 29.7 / 0.0 | düşük güven |
| kırılım · kararsız · normal | 1050 | 129 | 31.71 (28.6…34.8) | 37.71 (33.8…41.2) | 0.526 | 0.126 (-0.02…+0.26) | 55.8 | 16.3 / 0.2 | orta güven |
| kırılım · kararsız · yüksek | 769 | 135 | 38.75 (35.1…42.2) | 43.43 (39.2…47.5) | 2.459 | 0.375 (+0.23…+0.52) | 54.7 | 16.4 / 0.4 | orta güven |
| kırılım · yükseliş · düşük | 4346 | 286 | 34.93 (32.6…37.2) | 38.68 (36.1…41.2) | 1.205 | 0.235 (+0.13…+0.35) | 55.9 | 27.6 / 0.1 | orta güven |
| kırılım · yükseliş · normal | 4039 | 224 | 41.45 (37.5…45.8) | 45.46 (41.1…50.3) | 3.258 | 0.484 (+0.30…+0.68) | 55.7 | 29.6 / 0.4 | orta güven |
| kırılım · yükseliş · yüksek | 1277 | 110 | 33.2 (28.5…37.6) | 38.84 (33.6…43.8) | 2.39 | 0.339 (+0.08…+0.58) | 54.3 | 45.3 / 0.8 | orta güven |

**Strateji türü — tüm dönem**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| destekten tepki | 74 | 64 | 25.68 (16.2…35.7) | 27.03 (17.1…37.3) | 0.174 | -0.004 (-0.42…+0.43) | 64.9 | 25.7 / 2.7 | düşük güven |
| geri çekilme | 18333 | 986 | 26.36 (24.8…27.9) | 31.59 (29.9…33.2) | 0.233 | 0.066 (+0.00…+0.13) | 80.4 | 25.2 / 0.4 | orta güven |
| kırılım | 12063 | 969 | 36.7 (35.0…38.5) | 41.01 (39.2…43.0) | 2.016 | 0.325 (+0.24…+0.41) | 55.5 | 27.9 / 0.3 | orta güven |

**Rejim (türler birleşik) — tüm dönem**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| düşüş · normal | 767 | 35 | 35.46 (29.6…41.1) | 44.59 (39.3…49.9) | 3.111 | 0.474 (+0.25…+0.70) | 68.6 | 9.3 / 0.1 | düşük güven |
| düşüş · yüksek | 59 | 14 | 35.59 (7.7…48.6) | 40.68 (7.7…58.9) | 1.181 | 0.342 (-0.59…+0.85) | 49.2 | 11.9 / 0.0 | **YETERSİZ** |
| kararsız · düşük | 816 | 38 | 23.53 (19.1…28.5) | 28.43 (23.6…33.4) | -0.817 | -0.071 (-0.25…+0.12) | 71.7 | 35.7 / 0.2 | düşük güven |
| kararsız · normal | 2949 | 135 | 28.82 (26.4…31.4) | 34.62 (31.7…37.7) | 0.559 | 0.109 (+0.00…+0.22) | 70.8 | 27.0 / 0.2 | orta güven |
| kararsız · yüksek | 2727 | 148 | 31.98 (29.5…34.4) | 38.17 (35.3…41.0) | 1.873 | 0.296 (+0.19…+0.40) | 74.6 | 19.0 / 0.7 | orta güven |
| yükseliş · düşük | 10303 | 286 | 28.85 (27.1…30.8) | 33.17 (31.2…35.2) | 0.2 | 0.08 (+0.00…+0.16) | 70.5 | 21.7 / 0.3 | orta güven |
| yükseliş · normal | 9046 | 226 | 35.93 (32.9…39.1) | 40.43 (37.0…43.9) | 2.445 | 0.366 (+0.23…+0.51) | 68.8 | 34.1 / 0.3 | orta güven |
| yükseliş · yüksek | 3803 | 112 | 22.35 (19.0…25.9) | 26.9 (23.0…30.9) | -1.083 | -0.122 (-0.29…+0.05) | 71.9 | 26.1 / 0.8 | orta güven |

**2022 son (11–12. ay): strateji × trend**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| destekten tepki · yükseliş | 3 | 3 | 0.0 (0.0…0.0) | 0.0 (0.0…0.0) | -7.549 | -0.972 (-1.04…-0.87) | 100.0 | 0.0 / 0.0 | **YETERSİZ** |
| geri çekilme · yükseliş | 990 | 38 | 32.63 (21.2…45.3) | 35.25 (23.2…48.5) | 1.183 | 0.293 (-0.24…+0.87) | 71.8 | 9.7 / 1.8 | düşük güven |
| kırılım · yükseliş | 907 | 38 | 48.07 (38.6…57.1) | 49.39 (39.9…58.6) | 3.372 | 0.497 (+0.17…+0.82) | 63.9 | 10.6 / 2.4 | düşük güven |

**2023: strateji × trend**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| destekten tepki · kararsız | 6 | 6 | 50.0 (16.7…83.3) | 50.0 (16.7…83.3) | 9.22 | 1.031 (-0.42…+2.67) | 66.7 | 66.7 / 0.0 | **YETERSİZ** |
| destekten tepki · yükseliş | 13 | 10 | 15.38 (0.0…36.4) | 15.38 (0.0…36.4) | -2.392 | -0.2 (-1.09…+0.89) | 92.3 | 84.6 / 0.0 | **YETERSİZ** |
| geri çekilme · kararsız | 1239 | 81 | 23.65 (19.9…27.9) | 29.46 (25.3…34.3) | 0.506 | 0.018 (-0.15…+0.20) | 81.2 | 83.9 / 0.9 | orta güven |
| geri çekilme · yükseliş | 3698 | 167 | 28.91 (24.1…33.8) | 32.42 (27.4…37.7) | 0.41 | 0.135 (-0.06…+0.33) | 79.4 | 74.0 / 0.3 | orta güven |
| kırılım · kararsız | 248 | 70 | 29.03 (22.7…35.7) | 31.85 (25.0…39.0) | 0.29 | 0.088 (-0.17…+0.35) | 56.0 | 80.6 / 0.4 | orta güven |
| kırılım · yükseliş | 2480 | 165 | 40.2 (35.6…45.5) | 45.97 (40.6…51.9) | 4.176 | 0.618 (+0.39…+0.87) | 54.8 | 83.2 / 0.1 | orta güven |

**2024 (FAZ 2'de incelendi): strateji × trend**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| destekten tepki · kararsız | 3 | 3 | 0.0 (0.0…0.0) | 33.33 (0.0…100.0) | -2.919 | -0.503 (-1.09…+0.59) | 0.0 | 0.0 / 0.0 | **YETERSİZ** |
| destekten tepki · yükseliş | 12 | 11 | 41.67 (16.7…66.7) | 41.67 (16.7…66.7) | 6.912 | 0.834 (-0.49…+2.24) | 83.3 | 16.7 / 16.7 | **YETERSİZ** |
| geri çekilme · düşüş | 44 | 9 | 56.82 (50.9…64.3) | 56.82 (50.9…64.3) | 5.885 | 0.994 (+0.74…+1.33) | 77.3 | 13.6 / 0.0 | **YETERSİZ** |
| geri çekilme · kararsız | 619 | 79 | 27.79 (23.8…31.6) | 34.41 (29.3…39.0) | 0.022 | 0.074 (-0.10…+0.24) | 76.9 | 11.0 / 0.8 | orta güven |
| geri çekilme · yükseliş | 3610 | 161 | 22.66 (20.0…25.5) | 29.31 (26.5…32.5) | -0.583 | -0.062 (-0.17…+0.06) | 82.1 | 7.3 / 0.7 | orta güven |
| kırılım · düşüş | 114 | 9 | 37.72 (25.6…51.0) | 45.61 (32.1…59.1) | 2.815 | 0.558 (+0.05…+1.15) | 45.6 | 14.0 / 0.9 | **YETERSİZ** |
| kırılım · kararsız | 623 | 78 | 32.58 (28.7…36.5) | 39.33 (34.6…43.5) | 0.989 | 0.167 (-0.01…+0.35) | 54.3 | 8.3 / 0.3 | orta güven |
| kırılım · yükseliş | 2270 | 160 | 38.02 (34.6…41.4) | 43.3 (39.5…47.2) | 2.349 | 0.413 (+0.24…+0.60) | 53.5 | 24.2 / 0.2 | orta güven |

**2025-01-01 … 2025-11-13: strateji × trend**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| destekten tepki · düşüş | 1 | 1 | 0.0 (—) | 0.0 (—) | -5.23 | -1.166 (—) | 0.0 | 0.0 / 0.0 | **YETERSİZ** |
| destekten tepki · kararsız | 1 | 1 | 100.0 (—) | 100.0 (—) | 13.26 | 3.542 (—) | 100.0 | 0.0 / 0.0 | **YETERSİZ** |
| destekten tepki · yükseliş | 18 | 14 | 11.11 (0.0…27.3) | 11.11 (0.0…27.3) | -4.16 | -0.788 (-1.13…-0.27) | 44.4 | 5.6 / 0.0 | **YETERSİZ** |
| geri çekilme · düşüş | 413 | 28 | 37.05 (29.1…46.0) | 50.12 (43.1…57.3) | 4.718 | 0.679 (+0.38…+1.00) | 80.1 | 8.7 / 0.0 | düşük güven |
| geri çekilme · kararsız | 1490 | 87 | 29.33 (26.1…33.1) | 35.17 (31.6…39.6) | 1.315 | 0.229 (+0.09…+0.38) | 80.9 | 7.0 / 0.5 | orta güven |
| geri çekilme · yükseliş | 2095 | 102 | 26.25 (23.0…29.7) | 29.69 (26.3…33.3) | 0.118 | 0.022 (-0.10…+0.15) | 82.9 | 5.9 / 0.0 | orta güven |
| kırılım · düşüş | 227 | 28 | 31.28 (25.3…37.5) | 35.68 (29.6…41.9) | 0.416 | 0.072 (-0.16…+0.32) | 57.7 | 7.5 / 0.0 | düşük güven |
| kırılım · kararsız | 782 | 87 | 37.98 (34.2…41.8) | 43.61 (38.8…48.1) | 2.394 | 0.376 (+0.21…+0.54) | 55.2 | 9.8 / 0.3 | orta güven |
| kırılım · yükseliş | 1805 | 102 | 33.19 (29.1…37.3) | 36.73 (31.8…41.7) | 1.005 | 0.141 (-0.08…+0.37) | 55.0 | 7.5 / 0.1 | orta güven |

**son 12 ay 2025-11-14 … 2026-11-13 (FAZ 2'de incelendi): strateji × trend**

| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | sıçrama gösterge/tutma % | durum |
|---|---|---|---|---|---|---|---|---|---|
| destekten tepki · kararsız | 6 | 6 | 33.33 (0.0…66.7) | 33.33 (0.0…66.7) | -1.589 | -0.279 (-1.02…+0.49) | 66.7 | 0.0 / 0.0 | **YETERSİZ** |
| destekten tepki · yükseliş | 11 | 9 | 36.36 (9.1…66.7) | 36.36 (9.1…66.7) | 1.227 | 0.369 (-0.68…+1.60) | 54.5 | 9.1 / 0.0 | **YETERSİZ** |
| geri çekilme · düşüş | 8 | 5 | 12.5 (0.0…50.0) | 12.5 (0.0…50.0) | -2.205 | -0.072 (-0.92…+2.10) | 37.5 | 0.0 / 0.0 | **YETERSİZ** |
| geri çekilme · kararsız | 1087 | 74 | 28.43 (24.5…32.5) | 35.33 (30.9…39.9) | 0.78 | 0.196 (+0.02…+0.37) | 81.0 | 2.6 / 0.0 | orta güven |
| geri çekilme · yükseliş | 3040 | 155 | 22.47 (19.8…25.3) | 27.76 (25.1…30.6) | -0.719 | -0.114 (-0.23…+0.02) | 80.8 | 3.8 / 0.0 | orta güven |
| kırılım · düşüş | 19 | 11 | 0.0 (0.0…0.0) | 0.0 (0.0…0.0) | -7.572 | -0.984 (-1.10…-0.87) | 21.1 | 15.8 / 0.0 | **YETERSİZ** |
| kırılım · kararsız | 388 | 66 | 32.22 (26.7…38.1) | 35.05 (29.3…41.2) | 0.086 | 0.06 (-0.13…+0.26) | 57.2 | 8.8 / 0.0 | orta güven |
| kırılım · yükseliş | 2200 | 155 | 32.77 (29.9…35.9) | 35.41 (32.3…38.8) | 0.405 | 0.107 (+0.00…+0.22) | 55.8 | 5.8 / 0.0 | orta güven |

## J.3 Okuma (betimleyici; strateji seçimi ya da eşik önerisi değildir)

**Çoklu karşılaştırma:**

- Tüm dönemde 23 ana grup var; 15'i yeterli.
- Yeterli grupların **8'inde** ortalama R'nin %95 aralığı sıfırı dışlıyor. Bağımsız gruplar için rastlantıyla
  beklenen sayı yaklaşık 0,8.
- Ama gruplar bağımsız değil: aynı günler, aynı hisseler, 10 gün içinde tekrar eden sinyaller (%54–83). Bu yüzden bu
  karşılaştırma **anlamlılık kanıtı sayılmaz**. Düzeltilmiş anlamlılık iddia edilmez.

**Görülenler** (yalnız betimleme):

- **Kırılım ve geri çekilme:** Tüm dönemde kırılımın tekil ortalama R'si (+0,33; %95 +0,24…+0,41) geri çekilmeden
  (+0,07; +0,00…+0,13) yüksek. Kırılım, yeterli rejimlerin çoğunda geri çekilmenin üstünde; istisna düşüş / normal (geri çekilme +0,70, kırılım +0,17).
- **Yükseliş + yüksek oynaklıkta geri çekilme:** Ortalama R −0,35 (−0,49…−0,19; 2.523 işlem, 111 gün).
- **Döneme göre değişim:** Kırılım × yükseliş 2022 son, 2023 ve 2024'te pozitif. 2025 ilk dönemde aralık sıfırı
  içeriyor; son 12 ayda +0,11 (+0,00…+0,22) ile sınırda.
- **Son 12 ayda geri çekilme × yükseliş:** −0,11 (−0,23…+0,02).
- **Düşüş rejimi:** Gün sayısı az (35 + 14) ve tek tek dönemlerde çoğu grup YETERSİZ. Tüm dönemdeki pozitif düşüş
  grupları birkaç kümelenmiş döneme dayanıyor.
- **Tekil ile portföy farkı:** Tekil ortalamalar pozitif olabilir, ama aynı dönemdeki FAZ 2 portföyü zararlı (Ek H10).
  Tekil sonuç, sınırlı pozisyonla ve sıralamayla seçilen işlemlerin sonucu değildir. Buradan portföy getirisi
  çıkarılmamalı.
- **Veri kalitesi:** 2023 gruplarında gösterge penceresinde sıçrama payı **%74–85**; bu pencereler 2022–2023
  sıçramalarını kapsıyor. Bu, yüzde bu kadarının hatalı olduğu anlamına gelmez; sonuçların etkilenmediğini de
  göstermez. **Duyarlılık analizi yapılmadı.** Tutma süresinde sıçrama payı çoğu grupta %1'in altında.

**Katkı değerlendirmesi:**

- Ön kayıtlı rejim sınıfları, strateji türleri arasında tutarlı ve sağlam bir ayrım kanıtı **vermiyor**. Sebepler:
  - etki dönemler arasında işaret ve büyüklük değiştiriyor;
  - düşüş rejimi örneği az;
  - gözlemler yüksek oranda ilişkili;
  - veri kalitesi uyarıları var;
  - bu dönemler daha önce incelendi.
- Bu nedenle **uygulanabilir bir katkı bulunmadı.** Bulgular yalnız ileride dönem dışı (yeni) veriyle sınanacak
  hipotez olarak kaydedildi:
  - "kırılım, geri çekilmeden iyi";
  - "geri çekilme, yükseliş + yüksek oynaklıkta zayıf".

**Canlı için öneri (yalnız öneri, uygulanmadı):**

1. Canlı tahmin defterinin rejim tablosu (`defter.ozet → rejim`) bugünkü gibi `guven(n, gun)` ile sınırlansın. Bu
   çalışma, aynı hisseden ilişkili gözlemler yüzünden ek bir "aynı hisse tekrar payı" uyarısının yararlı olacağını
   gösteriyor.
2. Hiçbir strateji ya da rejim kuralı değiştirilmesin. Bu hipotezler, FAZ 1 defterinde biriken dönem dışı kayıtlarla
   ayrıca sınanabilir.

## J.4 Testler

| Komut | Sonuç |
|---|---|
| `tests.test_faz4_rejim` | 8 test. **Gelecek bağımsızlığı:** gelecek mumlar bozulduğunda ya da hiç olmadığında geçmiş günlerin rejimi aynı; her gün yalnız o güne kadarki veriyle aynı; kısa geçmişte rejim yok; eksik günde son mevcut gün. **İstatistik:** küme bootstrap tekrarlanabilir; tek günde aralık yok; bağımlı günlerde aralık bağımsız varsayıma göre geniş. Grup özeti elle hesapla doğrulandı; n < 30 ve gün < 20 YETERSİZ. **Süzgeç:** canli_ortak evreni, kapanmış sonuç, s3 stop altı girişsiz, tekrar bayrağı, sıçrama bayrakları. |
| Tam takım (ağ engelli) | **Ran 629 tests … OK**, ağ denemesi 0 (621 + 8) |

## J.5 Değişen dosyalar (dal `faz4-rejim`)

- **Yeni:**
  - `arastirma/faz4/rejim_tanimi.json` (ön kayıt)
  - `arastirma/faz4/rejim_analiz.py`, `arastirma/faz4/tablo_yaz.py`
  - `arastirma/faz4/sonuclar/rejim_sonuclari.json`, `arastirma/faz4/sonuclar/rejim_tablolari.md`
  - `tests/test_faz4_rejim.py`
- **Değişmeyen:** Canlı modüller (`regime`, `defter`, `journal`, `ready`), model ve veritabanları.
- **Ayrıca:** FAZ 3 kabul kaydı (Ek I3, etiket `faz3-kabul`) `faz3-metrik` dalında.

## J.6 Sınırlamalar

1. Bağımsız doğrulama değildir; dönemler ve planlar önceden incelendi.
2. Tekil işlem sonucudur; portföy değildir. Aynı hisse ve aynı gün bağımlılığı yüksektir; aralıklar yalnız gün
   kümesini hesaba katar.
3. FAZ 3 veri sorunları geçerli:
   - düzeltilmiş fiyatlar;
   - iki indirme bloğu arasındaki taban kayması;
   - sıçramalar (gösterge penceresinde yaygın);
   - duyarlılık analizi yok.
4. Hayatta kalma yanlılığı ve güncel sektör listesi sorunu sürüyor. Haber şartı yok.
5. Düşüş rejimi örneği az. Rejim sınıfları yalnız BIST 100'e dayanır; hisse ya da sektör rejimi yok.
6. Çok sayıda karşılaştırma yapıldı; iyi görünen gruplar rastlantı olabilir.

## J.7 FAZ 1 (ayrı)

- 16.11 17:40'te canlı veritabanı salt-okunur okundu: 2 tahmin, 0 sonuç, 0 değerlendirme, 0 olay.
- Son çalıştırma 16.11 09:42 sabah kontrolü; fiyatlar 13.11'e kadar. Bu akşamki analiz henüz çalışmadı.
- **FAZ 1 kabul edilmedi.**

**Onay beklenen:** FAZ 4 kabul kararı. FAZ 5'e geçilmedi; canlıya alma yok.

---

# EK J2 (16.11.2026) — FAZ 4 KABUL KAYDI ve rapor dosyası olayı

- **Kabul:** Kullanıcı FAZ 4'ü commit `2538d28` kapsamındaki **betimleyici araştırma** olarak kabul etti (etiket `faz4-kabul`). Strateji veya rejim filtresinin canlıya alınması **onaylanmadı**. Sonradan eklenen rapor dosyası (31dbcf7) kabulün parçası değildir.
- **Olay:** Canlı bekçi raporu `faz4-rejim` dalına gönderildi (31dbcf7) ve kaldırıldı (63f88a5). Depo herkese açık. İçerik işlem raporudur; kimlik bilgisi, API anahtarı veya kişisel veri içermez. Geçmiş temizliği kullanıcı adımıdır; temiz dal `faz4-rejim-temiz` hazırlandı.
- **Önleme:** `.gitignore` kuralları eklendi; geçmişteki dosyayı temizlemez.


---

# EK K (16.11.2026) — FAZ 5: 5 ve 10 işlem günlük hedefler (araştırma; dal `faz5-hedef`)

**Konumu:**

- Canlı kod, veritabanı, seçim eşikleri ve etkin model **değişmedi**. Etkin model `tp1_v1` (SHA-256 `09f8e5e0…`);
  `modeller/` klasöründe başka dosya yok.
- Aday modeller yalnız bellekte, yerel CPU ile uydurulup değerlendirildi. **Dosyaya yazılmadı, etkinleştirilmedi.**
- Ücretli yapay zekâ çağrısı yok. Canlı müşteri verisi kullanılmadı.
- **Haber şartı yok:** Bu evren canlı haberli fırsat listesi değildir.
- **Bağımsız başarı kanıtı değildir:** Dönemler (2024, son 12 ay) ve planlar daha önce incelendi.

## K.1 Ön kayıt ve sürümler

**Ön kayıt:** `arastirma/faz5/deney_tanimi.json`, commit **`6430231`** (18:54). Kod ve testler commit `5dd858f`.
Sonuçlar bu iki commit'ten **sonra** üretildi. Deneme listesi genişletilmedi.

**Kabul kayıtları doğrulandı:**

| Etiket | Commit |
|---|---|
| `faz2-kabul` | `6d7f5d5` |
| `faz3-kabul` | `94d2fc8` |
| `faz4-kabul` | `2538d28` |

FAZ 5 dalı `faz4-rejim-temiz` (`2a04d04`) üstüne açıldı. Eski `faz4-rejim` dalı GitHub'da hâlâ duruyor; silinmesi
kullanıcı adımıdır.

**Veri:**

- `planlar_seviyeli.csv` (SHA-256 `2413d1df…`) ve `arastirma_5y.db` (parmak izi `d563b954…`; FAZ 3 sorunları geçerli).
- Üretilen hedef dosyası `hedefler.csv` (SHA-256 `233a6a83…`; yerel, Git dışı).

## K.2 Hedef tanımları (iki ayrı hedef türü)

**Giriş:**

- Sinyal gününden sonraki işlem gününün açılışında alış.
- Açılış azami girişin üstündeyse girişsiz (5.352 plan).
- Açılış SL'nin altında ya da SL'ye eşitse girişsiz (214 plan).

**Hedefler:**

- **Getiri hedefi (zaman çıkışı) `H5_getiri` / `H10_getiri`:**
  - Giriş günü 1. gün sayılır; çıkış 5. ya da 10. işlem gününün kapanışında. **Stop ve hedef uygulanmaz.**
  - net % = (çıkış / dolum − 1) × 100 − 0,30.
  - **R paydası = plan girişi − SL** (journal ile aynı), maliyet dahil.
  - İkili hedef: `H*_pozitif` = net > 0.
- **TP1 olay hedefi `H5_tp1` / `H10_tp1`:** İlk 5 ya da 10 gün içinde TP1'e SL'den önce ulaşılması.
  - `journal.evaluate` mumlar ilk N günle sınırlanarak çalıştırıldı.
  - Aynı mumda TP1 ve SL varsa SL önce sayılır.
- Bu iki tür **karıştırılmadı.** `tp1_v1` bu hedeflerin tahmincisi olarak kullanılmadı.

**Eksik veri:**

- Girişten sonra N mum yoksa örnek dışı (5 günde 29, 10 günde 14).
- Hissede eksik takvim günü olan pencereler tutuldu ve işaretlendi. Oranı: kırılımda %0,2, geri çekilmede %1,1.

**Ortak örneklem:** 30.404 plan, 989 sinyal günü. `x_trend` dolu olanlar; dört hedefin hepsi aynı örneklerde.

**Girdiler:** `model.py` içindeki NUM ve CAT sütunları; sinyal günü kapanışına kadarki veriden. Ertesi gün bilgisi ve
sonuç sütunları kullanılmadı.

**Bölümler:**

| Sınama | Test dönemi | Test örneği | Gün | Eğitim |
|---|---|---|---|---|
| Ana | 2025-11-14 … 2026-10-30 | 6.729 | 238 | 22.517 örnek, 2025-09-29'a kadar (45 gün ambargo) |
| Ek | 2024 | 7.264 | 248 | 8.780 örnek, 2023-11-16'ya kadar |

- **λ seçimi** yalnız eğitim içinde: son %20'lik dilim doğrulama, aralarında 20 gün ambargo.
- **Ön işleme** (doldurma, kırpma, standartlaştırma) yalnız eğitimden öğrenildi.
- **Aynı hisse tekrarı:** Test örneklerinde aynı hissenin 10 gün içinde tekrar gelen sinyali %70–71. Gözlemler yüksek
  oranda bağımlı.

## K.3 Betimleme (tüm ortak örneklem; %95 aralık gün kümesi bootstrap)

| Tür | n | gün | aynı hisse tekrar | 5 gün TP1 | 10 gün TP1 | 5 gün net % (R) | 10 gün net % (R) |
|---|---|---|---|---|---|---|---|
| kırılım | 12.032 | 962 | %55,5 | %13,1 (12,3…14,0) | %23,5 (22,4…24,8) | +0,44 (+0,10…+0,78); R +0,08 | +1,23 (+0,69…+1,82); R +0,20 |
| geri çekilme | 18.298 | 985 | %80,4 | %6,9 (6,2…7,6) | %14,8 (13,7…15,9) | −0,14 (−0,56…+0,28); R −0,02 | +0,24 (−0,36…+0,81); R +0,06 |
| destekten tepki | 74 | 64 | %64,9 | %8,1 | %16,2 | +0,47 (−1,40…+2,21) | +0,66 (−2,08…+3,49) — **örnek az** |

Bunlar tekil işlem ortalamalarıdır. Portföy getirisi çıkarılmadı.

## K.4 Sonuçlar (R0 sabit oran, R1 türe göre oran, M1 lojistik)

Aralıklar %90, aylık blok bootstrap ile.

| Hedef · sınama | Test oranı | R1 Brier / LogLoss / AUC | M1 Brier / LogLoss | M1 AUC (%90) | M1 Brier becerisi (R1'e göre, %90) | Ön kayıtlı ölçüt |
|---|---|---|---|---|---|---|
| H5_tp1 · ana | %8,1 | 0,0737 / 0,276 / 0,615 | 0,0710 / 0,258 | **0,730** (0,690…0,763) | +%3,7 (+2,3…+4,9) | geçti |
| H5_tp1 · ek (2024) | %7,7 | 0,0726 / 0,277 / 0,570 | 0,0687 / 0,252 | **0,714** (0,689…0,738) | +%5,4 (+4,4…+6,7) | geçti |
| H10_tp1 · ana | %16,2 | 0,1342 / 0,437 / 0,591 | 0,1300 / 0,422 | **0,667** (0,633…0,705) | +%3,1 (+1,1…+5,2) | geçti |
| H10_tp1 · ek | %15,7 | 0,1352 / 0,443 / 0,569 | 0,1263 / 0,408 | **0,682** (0,659…0,702) | +%6,6 (+5,0…+8,3) | geçti |
| H5_pozitif · ana | %44,7 | 0,2476 / 0,688 / 0,522 | 0,2471 / 0,687 | 0,530 (0,505…0,557) | +%0,2 (−0,6…+1,2) | geçmedi |
| H5_pozitif · ek | %44,7 | 0,2488 / 0,691 / 0,555 | 0,2504 / 0,695 | 0,539 (0,518…0,555) | −%0,7 (−4,4…+2,7) | geçmedi |
| H10_pozitif · ana | %44,3 | 0,2485 / 0,690 / 0,522 | 0,2485 / 0,690 | 0,518 (0,467…0,569) | −%0,0 (−1,6…+2,0) | geçmedi |
| H10_pozitif · ek | %45,9 | 0,2501 / 0,693 / 0,571 | 0,2582 / 0,711 | 0,516 (0,481…0,560) | −%3,2 (−8,7…+1,0) | geçmedi |

**Kalibrasyon (M1; 5 dilim, tahmin → gerçek):**

- H5_tp1 · ana: 1,2→1,9 · 3,5→3,1 · 6,3→6,3 · 10,5→11,0 · 19,1→18,4. İyi.
- H10_pozitif · ek: 31,5→44,9 … 63,8→49,1. **Kötü:** tahminler gerçekten fazla yayılıyor.

**Ekonomik (tekil; M1'in üst %20'si ile kalanın karşılaştırması; aynı ufukta zaman çıkışı net %):**

| | Üst %20 | Kalan |
|---|---|---|
| H5_tp1 · ana | −0,30 | −0,64 |
| H5_tp1 · ek | +0,27 | −0,49 |
| H10_tp1 · ana | −0,51 | −0,44 (ters) |
| H10_tp1 · ek | +0,30 | −0,65 |

Bu tekil işlem farkıdır; portföy getirisi değildir ve tek başına katkı sayılmaz.

## K.5 Değerlendirme

**Ön kayıtlı karar:**

- `H5_tp1` ve `H10_tp1`: ölçüt **geçti** ("katkı").
- `H5_pozitif` ve `H10_pozitif`: **katkı yok**. 5 ve 10 günlük maliyet sonrası getirinin yönü bu girdilerle türe göre
  orandan daha iyi tahmin edilemedi.

**"Katkı"nın anlamı sınırlıdır.** Sonradan yapılan tanı (`sonuclar/sonradan_tani.json`; karar ölçütü değildir, yeni
model değildir):

- Yalnız TP1'e uzaklık (`tp1_%`, tersten sıralı) tek başına 5 günlük TP1'de AUC 0,692 (ana) ve 0,693 (ek) veriyor.
- Yani M1'in 0,71–0,73'lük ayırt etme gücünün **büyük kısmı mekanik**: hedef yakınsa kısa sürede ulaşılması daha
  olası.
- Bu, kârlı seçim kanıtı değildir:
  - aynı modelin üst %20'sinde 5 günlük zaman çıkışı getirisi son 12 ayda yine **eksi** (−%0,30);
  - 10 günlük TP1'de üst %20 kalandan daha kötü.
- Ön kayıtlı referans listesinde "uzaklık" referansı yoktu; bu eksiklik ön kaydın bir zayıflığıdır.

**Uygulanabilir katkı yok.** Kısa vadeli TP1 olayının olasılığı bir ölçüde tahmin edilebiliyor, ama bunun canlı
seçim ya da kâr açısından değeri gösterilemedi. Dönemler önceden incelendi; aynı hisse bağımlılığı yüksek.

**Öneri (yalnız öneri):**

- Canlıda hiçbir şey değiştirilmesin; aday model etkinleştirilmesin.
- İleride bir deney yapılırsa, ön kayda "hedef uzaklığı" gibi mekanik bir referans **baştan** konmalı. Yeni (dönem
  dışı) veriyle sınanmalı.

## K.6 Testler

| Komut | Sonuç |
|---|---|
| `tests.test_faz5_hedef` | 10 test: zaman çıkışı getirisi ve R elle; TP1 olayı ile getirinin ayrı olduğu (TP1 görülse de 5. gün zarar); 7. günde TP1 → 5 günde 0, 10 günde 1; SL önce ve aynı mum kuralı; giriş dışlamaları ve eksik veri; pencere sonrası verinin hedefi değiştirmemesi; takvim boşluğu işaretlenir, silinmez; 45 gün ambargo ve bölüm sırası; ön işlemenin yalnız eğitimden öğrenilmesi; Log Loss elle |
| Tam takım (ağ engelli) | **Ran 639 tests … OK**, ağ denemesi 0 (629 + 10) |

## K.7 Değişen dosyalar (dal `faz5-hedef`)

- **Yeni:**
  - `arastirma/faz5/deney_tanimi.json` (ön kayıt)
  - `arastirma/faz5/hedefler.py`, `arastirma/faz5/deney.py`
  - `arastirma/faz5/sonuclar/deney_sonuclari.json`, `arastirma/faz5/sonuclar/sonradan_tani.json`
  - `tests/test_faz5_hedef.py`
- **Değişmeyen:** Canlı modüller, `modeller/` ve veritabanları.

## K.8 Sınırlamalar

1. Bağımsız doğrulama değildir; dönemler önceden incelendi.
2. Tekil işlem sonucudur; portföy değildir. Aynı hisse tekrarı %70 civarında; aralıklar yalnız ay bloklarını hesaba
   katar.
3. FAZ 3 veri sorunları sürüyor: düzeltilmiş fiyatlar, taban kayması, sıçramalar, duyarlılık analizi yok.
4. Hayatta kalma yanlılığı, güncel sektör listesi, haber şartı yok.
5. Zaman çıkışı getirisi gerçek strateji kurallarından (stop, kısmi satış) farklıdır.
6. Ön kayıtta mekanik bir referans yoktu (K.5).

## K.9 FAZ 1 (ayrı)

- 16.11 19:03 salt-okunur okuma: 5 tahmin, 0 sonuç, 0 değerlendirme, 0 olay. Son çalıştırma 18:23 akşam analizi; fiyatlar 16.11.
- Akşam kaydı doğrulandı (Ek J2). **Gözlenmeyen:** 17.11 sabah kontrolü ve gerçek sonuçlandırma. FAZ 1 kabul edilmedi.

**Onay beklenen:** FAZ 5 kabul kararı. FAZ 6'ya geçilmedi.
