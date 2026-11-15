# Aşama 7 planı — hazır zaman serisi modelleri (onay bekliyor)

**Soru:** Büyük şirketlerin milyonlarca fiyat serisiyle önceden eğittiği hazır modeller, Halley'in planlarında
"TP1, SL'den önce gelir mi?" sorusuna bizim modelimizden (tp1_v1) daha iyi ya da ona ek bilgi veriyor mu?

## Adaylar (15.11.2026 kontrolü)

| Model | Kim | Boyut | Lisans | Ne verir |
|---|---|---|---|---|
| **Kronos-small** | NeoQuasar | 24,7 M parametre | MIT (mirror'da; resmî sayfada doğrulanacak) | **Finans mumlarıyla** (açılış/yüksek/düşük/kapanış/hacim) eğitilmiş; olası **fiyat yolları** üretir → TP1/SL sırası doğrudan sayılabilir |
| **Chronos-Bolt-small** | Amazon | 48 M | Apache-2.0 | Genel zaman serisi; kapanış için **yüzdelik tahminler** (p10…p90) |
| **TTM-r2 (TinyTimeMixer)** | IBM | ~0,8 M | Apache-2.0 | Çok küçük ve hızlı; nokta tahmini |

En uygun aday **Kronos**. Hem finans verisiyle eğitilmiş hem de fiyat yolu üretiyor. Bizim sorumuz da yol sırasıyla
ilgili: önce TP1 mi, önce SL mi?

## Önemli kısıt: Python 3.9
- Güncel PyTorch (2.9+) ve güncel Chronos paketi (2.x) Python 3.10 ister.
- Python 3.9 ile çalışan son sürümler: **PyTorch 2.8 (CPU)** ve **chronos-forecasting 1.5.3** (`requires_python >=3.9`
  doğrulandı). Kronos ve TTM de PyTorch üzerinde çalışır.
- **Halley'e ve kurulum dosyasına hiçbir şey eklenmez.** Araştırma ayrı bir sanal ortamda yapılır
  (`%USERPROFILE%\.venvs\halley-arastirma`, Python 3.9). Halley'in kendi ortamı değişmez.

## Adımlar
1. **Kurulum (onay gerekli, indirme):**
   - PyTorch 2.8 CPU ~200 MB, transformers ve yardımcı paketler ~150 MB (PyPI'dan).
   - Model dosyaları (Hugging Face): Kronos-small + tokenizer ~110 MB, Chronos-Bolt-small ~190 MB, TTM ~5 MB.
   - Toplam indirme ~**0,7 GB**, disk ~**2 GB**.
2. **Sıfırdan eğitim yok, önce "olduğu gibi" deneme:** Aşama 6'daki etiketli planların sınama dönemlerinde (son 12 ay
   ve 2024; hisse başına 14 günde bir, ~6.500 plan) her plan için yalnız o güne kadarki 250–512 günlük fiyat verilir.
   - Kronos: 30 günlük olası fiyat yolları üretilir (plan başına 20 yol). "TP1'e SL'den önce ulaşan yol oranı" bir
     olasılık olur.
   - Chronos-Bolt: yüzdeliklerden TP1 ve SL'ye ulaşma olasılığı yaklaşık hesaplanır.
   - TTM: tahmin edilen yön ve büyüklük girdi olarak kullanılır.
3. **Aynı sınama:**
   - (a) Hazır modelin olasılığı tek başına.
   - (b) tp1_v1 ile birleşik (aşama 8'in ilk denemesi).
   - Ölçüler: isabet (AUC), olasılık doğruluğu (Brier), en yüksek %20'nin ortalama R'si ve güven aralıkları.
   - **Taban çizgisi tp1_v1.** Geçemeyen model devreye alınmaz.
4. **BIST'e ince ayar** (yalnız 3. adım umut verirse, ayrıca onay ile): Kronos'un BIST'in 4 yıllık verisiyle ince
   ayarı. İşlemciyle birkaç saat sürer.
5. **Rapor → senin kararın.** İşe yararsa canlıya nasıl taşınacağı ayrıca planlanır. Kurulum dosyasına PyTorch eklemek
   paketi ~300 MB büyütür; alternatif olarak skorlar araştırma ortamında gece hesaplanıp Halley'e dosya olarak
   verilebilir.

## Bilinen sınırlar ve riskler
- Bu modeller çoğunlukla **2024 öncesi** verilerle eğitildi. Sınama dönemimizin bir kısmını "görmüş" olabilirler.
  Kronos'un eğitim verisinde BIST olup olmadığı belli değil. Bu yüzden asıl ağırlık **son 12 ay** sonucuna verilir.
- Yalnız fiyattan tahmin BIST'te zor: Aşama 6'da isabet 0,61'de kaldı. Büyük sıçrama beklemiyorum.
- Kronos'un lisansı ve kod deposu kurulumdan önce resmî kaynaktan doğrulanacak.

## Maliyet ve süre
- **Yapay zekâ (OpenAI) maliyeti: 0 $.** Hepsi bilgisayarında, işlemciyle çalışır; ekran kartı gerekmez.
- Kurulum ~30 dk.
- "Olduğu gibi" deneme: Kronos yaklaşık 1–3 saat (arka planda); Chronos/TTM dakikalar içinde.
- Çalışma ve rapor ~4–5 saat.
- İnce ayar ayrıca onaylanırsa: ek ~4–6 saat.

## Onayın gerekenler
1. Ayrı araştırma ortamının kurulması ve yukarıdaki ~0,7 GB'lık indirmeler (PyPI ve Hugging Face'in resmî sayfaları).
2. "Olduğu gibi" denemenin yapılması (3. adım). İnce ayar ayrıca sorulur.
