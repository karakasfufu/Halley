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
