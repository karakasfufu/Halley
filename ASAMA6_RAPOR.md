# Aşama 6 araştırma raporu: "TP1, SL'den önce gelir mi?" (15.11.2026)

**Kısa sonuç:** Modeller zayıf ama gerçek bir ayırt etme gücü gösterdi. Söyledikleri **yüzdeler güvenilir değil** ve
faydaları dönemden döneme değişti. Plandaki kurala göre (**taban çizgisini açıkça geçemeyen model devreye alınmaz**)
modeli panele **olasılık yüzdesi olarak eklemiyorum.** Panelde hiçbir şey değişmedi. Seçim ve eşikler aynı.

## Ne yapıldı
- **Veri:**
  - 632 hissenin 5 yıllık günlük fiyatı (15.11.2021–13.11.2026) ayrı bir dosyaya indirildi
    (`data/backtest/arastirma_5y.db`, GitHub'a yüklenmez).
  - Canlı veritabanı yalnızca okundu. Yapay zekâ maliyeti 0 $.
- **Etiketleme** (`arastirma/asama6/etiketle.py`):
  - Halley'in bugünkü "koşulu bugün sağlanmış plan" kuralları kullanıldı (kırılım gerçekleşmiş, geri çekilme bölgede,
    destekten tepki). Aynı kod (`ready.candidates`, `entries`, `technical`) geçmişin her günü için **o güne kadarki
    250 günle** çalıştırıldı. Bu, canlıdaki 1 yıllık pencereyle aynıdır.
  - Giriş ertesi günün açılışı. Açılış azami girişin üstündeyse giriş yok sayıldı.
  - Çıkış, işlem günlüğünün aynı kurallarıyla yapıldı: TP1'de yarısı satılır, stop girişe çekilir; TP2; SL; 30 gün.
    Komisyon %0,2, kayma %0,1.
  - Haber kullanılmadı.
- **Kapsam:**
  - 46.053 sinyal üretildi: 6.627'sinde giriş olmadı, 129'u hâlâ açık.
  - Risk seviyesi "yüksek" olan 4.481 plan çıkarıldı (canlıda önerilmez).
  - Zarar mesafesi %1'den küçük 151 plan veri hatası sayılıp çıkarıldı (bkz. bulgu 4).
  - Kalan **34.579 kapanmış plan** kullanıldı (Kasım 2022–Ekim 2026).
- **Sınama:**
  - Ana sınama: eğitim Kasım 2022–Eylül 2025 (25.305 plan). Arada 45 günlük boşluk bırakıldı. Model hiç görmediği
    **son 12 ayda** (12.11.2025–12.11.2026; 7.988 plan, 572 hisse) sınandı.
  - Ek sınama: 2023 ile eğitilip 2024 yılında sınandı.

## Sonuçlar

### 1. Halley'in kuralları tek başına (model olmadan)

| | Plan sayısı | TP1 SL'den önce | Ortalama sonuç (R) |
|---|---|---|---|
| Tüm dönem | 34.665 | %30 | +0,15 R |
| Son 12 ay | 8.024 | %26 | −0,03 R (maliyet sonrası başabaşa yakın) |

Son 12 ayın senaryo türüne göre dökümü:

| Senaryo türü | Plan sayısı | TP1 SL'den önce | Ortalama sonuç (R) |
|---|---|---|---|
| **Kırılım (gerçekleşmiş)** | 2.638 | **%32** | **+0,09 R** |
| Geri çekilme (bölgede) | 4.594 | %24 | −0,03 R |
| Destekten tepki | 792 | %18 | −0,40 R |

Tüm dönemde de sıra aynı: kırılım %36 / +0,32 R, geri çekilme %26 / +0,05 R, destek %26 / −0,03 R. Kırılım her iki
dönemde de açıkça en iyisi.

Canlıdaki "yalnız teknik" süzgecinden (yükseliş trendi, teknik skor ≥ 7) geçenler son 12 ayda %28,5 TP1 ve +0,04 R
verdi. Yani süzgecin kendisi belirgin bir üstünlük sağlamadı.

### 2. Modeller (son 12 ay, hiç görülmemiş veri)

| | İsabet (AUC; 0,50 = yazı-tura) | Olasılık doğruluğu (tabana göre) | En yüksek %20'nin sonucu |
|---|---|---|---|
| Taban: herkese aynı oran (%30,6) | 0,500 | — | −0,03 R (tümü) |
| Taban: senaryo türüne göre oran | 0,546 (0,52–0,57) | %0,5 daha iyi | +0,09 R |
| **A: benzer durumlar tablosu** | **0,583 (0,56–0,61)** | %1,3 daha iyi | **+0,10 R** (diğerleri −0,06 R) |
| B: lojistik regresyon | 0,576 (0,54–0,62) | %1,3 daha iyi | −0,01 R |

Parantez içi değerler %90 güven aralığıdır (aylık bloklarla yeniden örnekleme).

- **Ayırt etme:** İki model de yazı-turadan ve senaryo türü tabanından biraz iyi; aralıklar 0,50'nin üstünde.
  Ancak 0,58, "zayıf" sayılan bir ayırt etmedir.
- **Yüzdeler güvenilmez:** Olasılık doğruluğundaki kazanç yalnız %1 civarında.
  - Benzer durumlar tablosu son 12 ayda olasılıkları **5–9 puan yüksek** söyledi. Örneğin "%41" dediği grupta gerçek
    oran %35 oldu.
  - Sebebi piyasanın değişmesi: TP1 oranı 2022'de %38 iken 2026'da %24.
  - Son 6 aya göre ölçekleme denendi; daha da kötüleştirdi (son 6 ayın oranı %33, sonraki 12 ay %26 çıktı).
- **Ekonomik fayda dönemden döneme değişti:**
  - Son 12 ayda tablonun en yüksek %20'si diğerlerinden anlamlı olarak iyiydi (+0,10 R'ye karşı −0,06 R; fark aralığı
    0,03–0,23).
  - **2024 sınamasında ise basit "senaryo türü" tabanı iki modelden de iyi sonuç verdi** (+0,36 R'ye karşı +0,19 R).
    Tablonun 2024'teki farkı anlamlı değil.
  - Aynı hissenin ardışık günlerdeki tekrar sinyalleri ayıklanınca (hisse başına 14 günde bir) fark küçüldü. 2024'te
    tamamen kayboldu.
- **Lojistik regresyon** son 12 ayda ekonomik fayda göstermedi (en yüksek %20'si −0,01 R); 2024'te tablodan biraz iyiydi.
  Yani hangisinin iyi olduğu da dönemden döneme değişiyor.

### 3. Panelde gösterilen puanlar

| Puan | İsabet (AUC) | Yorum |
|---|---|---|
| Genel puan (ağırlıklar sınanmamıştı) | 0,49 | TP1 olasılığını **hiç ayırt etmiyor** |
| Teknik skor | 0,53 | Çok zayıf |

- Teknik skor 7 ve üstündeki planlar, 6–7 olanlardan daha iyi değil.
- Risk/getiri oranı yükseldikçe TP1'e ulaşma olasılığı düşüyor (AUC 0,40). Bu beklenen bir sonuç: hedef uzaklaşıyor.
  Genel puan risk/getiriyi ödüllendirdiği için TP1 olasılığıyla ilişkisiz çıkıyor.
- Panelde zaten "ağırlıklar sınanmadı, yalnız bilgi" yazıyor. Bu ölçüm o uyarıyı doğruluyor.

### 4. Yan bulgu: işlem görmeyen hisse
- DUNYH ve ISATR'de fiyat günlerdir kıpırdamıyor ve hacim 0. Bu hisselerde zarar mesafesi sıfıra yakın planlar oluştu.
- Sebebi: hacim tamamen 0 olunca likidite "ölçülemedi" sayılıyor. Bu yüzden "likidite çok düşük" engeli devreye
  girmiyor.
- Bu planlar yükseliş trendinde olmadığı için yalnız teknik listeye girmedi. Haberli listede ise teorik olarak
  çıkabilir.
- Küçük bir düzeltme önerisi: hacmi tamamen 0 olan hisse "likidite çok düşük" sayılsın. Onayınla yapılır; bir eşik
  değişikliği değil, hata düzeltmesidir.

## Bilinen sınırlar
- **Borsadan çıkmış hisseler** Yahoo'da yok. Sonuçlar biraz iyimser olabilir.
- Yahoo'da günlerin %14–22'sinde açılış önceki kapanışa tam eşit. Canlı Halley aynı veriyi kullandığı için ölçüm
  tutarlı, ama gerçek açılış biraz farklı olabilir.
- 2 milyon TL likidite sınırı bugünkü TL ile. Yüksek enflasyon nedeniyle eski yıllarda daha az hisse bu sınırı geçiyor.
- Yükseliş ve düşüş dönemleri karışık; 4 yıl tek bir piyasa döngüsü sayılmaz.
- Haber yok: haberli planların sonucu bu ölçümde yok (haber verisi 4 günlük).

## Öneri
1. **Modeli panele olasılık yüzdesi olarak eklemeyelim.** Yüzdeler 5–9 puan şaşıyor, faydası da kalıcı değil.
2. İstersen kartlarda **yalnız sağlam olan bilgiyi** gösterebilirim, eşik ve seçim değişmeden. Örnek: "Bu tür planlar
   (kırılım) son 4 yılda %36 oranında TP1'e SL'den önce ulaştı (12.174 plan); son 12 ayda %32." Ek iş yaklaşık 1 saat.
3. Senaryo türü farkı (kırılım iyi, destekten tepki zayıf) seçim kuralını değiştirmek için bir ipucu. Ancak "küçük
   pilotla eşik değiştirme" kuralı gereği kararı sana bırakıyorum. Değiştirmeden önce haberli planlarla ayrıca
   bakılmalı.
4. Aşama 7 (hazır zaman serisi modeli): bu sonuç, yalnız fiyattan tahminin BIST'te zor olduğunu gösteriyor. Aşama 7'ye
   büyük beklentiyle girmemeyi öneririm; yine de istersen aynı sınama düzeneğiyle ölçebilirim.

## Tekrar üretmek için
Betikler `arastirma/asama6/` klasöründe. Sırasıyla:
- `indir.py <repo> <canlı.db> <arastirma.db>` (~4 dk)
- `etiketle.py <repo> <arastirma.db> <etiket.csv>` (~25 dk, 4 çekirdek)
- `model.py <etiket.csv> <arastirma.db> <sonuc.json>` (~1 dk)

Hiçbir betik canlı veritabanına yazmaz.

---

# Ek (15.11.2026, ikinci tur): geliştirilmiş model ve başlangıç sürümü (tp1_v1)

Kullanıcı isteği: "Modeli geliştir, başlangıç sürümü eğitilmiş bir model olsun."

## Ne değişti
- **Ortak girdi fonksiyonu:** `bist_haber/tp1_model.py → features()`. Eğitim (etiketleme) ve canlı kullanım aynı
  fonksiyonu çağırır; eğitimdeki girdiler canlıdakiyle birebir aynıdır. Piyasa girdileri de canlı gibi son 250 günden
  hesaplanır. Etiketleme bununla baştan yapıldı; yine 46.053 sinyal çıktı.
- **Yeni girdiler:** hedef ve stop uzaklığı (ATR cinsinden), 20 günlük ortalamaya uzaklık, 52 haftalık dibe uzaklık,
  1 günlük getiri.
- **Denenen modeller:** artırımlı karar ağaçları (yalnız numpy), yakın döneme ağırlık, olasılık kalibrasyonu, yeni
  girdili lojistik regresyon ve birleşimler. Hepsi aynı iki ileriye dönük sınamada karşılaştırıldı.

## Sonuç

| Model | Son 12 ay isabet (AUC) | 2024 isabet (AUC) | Olasılık doğruluğu (12 ay / 2024) | En yüksek %20'nin sonucu (12 ay / 2024) |
|---|---|---|---|---|
| Taban: senaryo türü | 0,546 | 0,577 | +%0,5 / +%1,6 | +0,09 R / +0,36 R |
| A: benzer durumlar tablosu | 0,583 | 0,593 | +%1,3 / +%0,1 | +0,10 R / +0,19 R |
| B: lojistik regresyon | 0,583 | 0,590 | +%2,0 / −%0,7 | +0,04 R / +0,25 R |
| Artırımlı ağaçlar (3 türü) | 0,57–0,59 | 0,56–0,57 | −%3,7 … +%1,4 | ≤ +0,09 R |
| **Seçilen: tablo + sade lojistik (10 girdi), ortalaması** | **0,605** | **0,612** | **+%2,8 / +%3,8** | **+0,17 R / +0,29 R** |

- **Neden bu model:** Sade birleşim, olasılık doğruluğunu **iki dönemde de** artıran tek model oldu.
- **Ağaçlar ve kalibrasyon kazandırmadı.** Sebep piyasanın genel başarı oranının dönemden döneme kayması: 2022'de %38,
  2026'da %24.
- **Yüzdelerin gerçeğe yakınlığı:** Seçilen model son 12 ayda olasılıkları 2–6 puan yüksek söyledi (tablo 5–9 puan
  yüksek söylüyordu).

  | Model "yaklaşık şu kadar" dedi | 21 | 26 | 29 | 33 | 41 |
  |---|---|---|---|---|---|
  | Gerçekte olan (%) | 18,5 | 19,7 | 23,6 | 28,6 | 38,0 |

- **Ekonomik fark:**
  - Son 12 ayda modelin en yüksek %20'si +0,17 R kazandırdı, diğerleri −0,08 R'de kaldı. Fark anlamlı (%90 aralık
    0,02–0,32).
  - 2024'te fark sınırda (−0,02–0,29). O yıl basit "senaryo türü" tabanının en yüksek %20'si hâlâ daha yüksek R
    verdi (+0,36).
- **Dürüst uyarı:** Altı kadar modeli aynı iki sınama dönemine bakarak karşılaştırdım ve en iyisini seçtim. Bu seçim
  kendisi biraz iyimserlik katar. Gerçek değeri ancak **bundan sonraki canlı planlar** gösterir.

## Başlangıç sürümü: `bist_haber/modeller/tp1_v1.json`
- 34.579 kapanmış planın tamamıyla eğitildi (Kasım 2022–Ekim 2026, 588 hisse). Dosya 8,7 KB. Yeni kütüphane
  gerektirmez; kurulum paketine girer.
- **İçerik:** 45 gruplu benzer durumlar tablosu ve 10 girdili lojistik regresyon. Girdiler: senaryo türü, BIST 100
  trendi ve 20 günlük getirisi, RSI, teknik skor, TP1 ve SL uzaklığı (ATR), endekse göre güç, 20 günlük getiri.
- **Kullanım:**
  - `tp1_model.predict(features)` → olasılık.
  - `band()` → düşük / orta / yüksek. Sınırlar son 12 ayın alt ve üst %20'si: %22,9 ve %34,0.
  - `similar()` → "geçmişte benzer N durumda %X".
- **Canlı deneme (16.11 planları):**

  | Hisse | Plan | TP1 olasılığı | Bant | Benzer geçmiş durum | Gerçekleşen |
  |---|---|---|---|---|---|
  | BAHKM | kırılım | %33 | orta | 341 | %27 |
  | ENERY | kırılım | %37 | yüksek | 1.465 | %31 |

- **Panele bağlı değil.** Seçimi ve eşikleri değiştirmez. Kartlarda bilgi olarak gösterilmesi ayrı onaya bağlı.
- **Yeniden eğitmek için:** `python arastirma/asama6/egit.py <repo> <etiket.csv> <sonuc.json> --kaydet`

---

# Ek 2 (15.11.2026): haber 1. aşama — KAP konu başlıkları (yapay zekâsız)

Kullanıcı kararı: "Yalnız 1. aşama" (yapay zekâ skoru yok).

## Ne yapıldı
- **Veri:** 4 yılın KAP bildirim listeleri indirildi (17.10.2022–13.11.2026; 299.996 bildirim, 216 haftalık aralık,
  boşluk yok).
  - Yalnız liste bilgisi alındı; metin okunmadı. Araştırma dosyasında `kap_liste` tablosunda duruyor.
  - KAP bekleme süresi korundu. KAP iki kez istek sınırı uyguladı; beklenip kaldığı yerden devam edildi.
- **Haber girdileri:** `tp1_model.news_features()`. Canlı ile ortak; canlıda `news_items()` haber tablosundan okur.
  - Sinyal gününden önceki 5 gün içinde, o gün saat 18:00'e kadar yayımlanmış bildirimler sayılır. 18:00'den sonra
    yayımlananlar hesaba katılmaz, böylece geleceği görme olmaz.
  - Girdiler:
    - haber var mı, kaç tane, son haberden bu yana geçen gün sayısı;
    - konu türleri: yeni iş ilişkisi / sözleşme, geri alım, pay alım satım, sermaye artırımı, finansal rapor, kâr
      payı, özel durum, olağan dışı hareket, genel kurul;
    - devre kesici.
  - Tahvil, bono ve bilgi formu gibi gürültü niteliğindeki bildirimler sayılmaz.
- Planların %42'sinde son 5 günde en az bir haber vardı.

## Sonuç: haber türü modele katkı yapmadı

| Durum | TP1 SL'den önce |
|---|---|
| Son 5 günde haberi olan planlar | %29,2 |
| Haberi olmayan planlar | %29,3 |

- Konu türleri arasında da belirgin fark yok; çoğu %27–33 arasında.
- Tek fark devre kesici: devre kesicisi olan planlarda TP1 oranı %24,8, olmayanlarda %31,2. Bu bilgiyi model
  oynaklık girdisinden zaten alıyor.

| Model | Son 12 ay isabet (AUC) | 2024 isabet (AUC) |
|---|---|---|
| Yalnız teknik (tp1_v1) | 0,605 | 0,612 |
| Teknik + haber türü | 0,603 | 0,609 |

- Fark aralığı son 12 ayda −0,006…+0,002, 2024'te −0,005…−0,001. Haber türü eklemek modeli iyileştirmiyor, hatta çok
  az kötüleştiriyor.
- **Karar:** Model dosyası tp1_v1 (yalnız teknik) olarak kalıyor.
- Haber girdileri kodda hazır duruyor. 2. aşamada (haber metninden skor) aynı yapıya eklenecek.

## Neden beklenen bir sonuç
- Asıl haberlerin çoğu "Özel Durum Açıklaması (Genel)" konusunda: 5.649 bildirim.
- İçeriğin iyi mi kötü mü olduğu konu başlığından anlaşılmıyor. Bunu yalnız metin söyler.

---

# Ek 3 (15.11.2026): canlıya alınanlar ve süren iş

- **Gizli kayıt (canlıda):**
  - Her hazır fırsatın öneri anındaki TP1 olasılığı `hazir_firsat.model_json` sütununa yazılır: olasılık, bant,
    benzer durum sayısı ve oranı, sürüm, zaman.
  - Panel, Telegram, seçim ve eşikler değişmedi. Model hatası öneriyi engellemez.
  - Ölçüm aracı: `tp1_model.live_check(conn)`. Kapanan önerilerde ortalama tahmin, gerçek oran, Brier ve bantlara göre
    gerçek oranı verir. İsabet (AUC) en az 30 kapanmış öneri birikince hesaplanır.
- **Hata düzeltmesi:** Hacmi 21 gündür 0 olan hisseler (DUNYH, ISATR, UMPAS) artık likidite engeline takılıyor.
- **Haber 2. aşama, Python ile (sürüyor):**
  - 5.649 Özel Durum metni indiriliyor; KAP sınırını paylaşmamak için istekler arasında 6 sn bekleniyor ve hafta içi
    seans saatlerinde indirme duruyor.
  - Kurallı okuma ve kelimelerden öğrenen model hazır.
  - Ara bakış (metinlerin %11'i): "olumlu" okunan metinlerde TP1 oranı %39, diğerlerinde %26–27. Kesin değil; sonuç
    tam veriyle eklenecek.
