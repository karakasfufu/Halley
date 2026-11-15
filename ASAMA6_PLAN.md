# Aşama 6 planı — kendi tahmin modelimiz (araştırma yapıldı: sonuç ASAMA6_RAPOR.md)

**Soru:** Halley'in önerdiği bir plan, **zarar durdur (SL) gelmeden TP1'e ulaşır mı?** Model bunun olasılığını
Halley'in kendi kurallarının geçmişte nasıl sonuç verdiğine bakarak hesaplar.

## Bugünkü durum (15.11.2026 ölçümü)
- Fiyat geçmişi: hisse başına yaklaşık **1 yıl** (590 hisse ~255 gün); endeks 3 yıl. Bir model için az.
- Yapay zekâyla analiz edilmiş haber: **151 tane, 4 günlük**. Haber, modelin girdisi olamayacak kadar az.
- Gerçekleşmiş sonuç: 3 kapanan sanal işlem, 0 hazır fırsat sonucu. Bunlarla model kurulamaz.
- Model kütüphanesi (sklearn vb.) yok; yalnız numpy var. Kurulum dosyasını büyütmemek için yeni kütüphane eklenmez.

## Adımlar
1. **Veri (ücretsiz):** BIST hisselerinin **5 yıllık** günlük fiyatı Yahoo'dan, canlı veritabanına dokunmadan **ayrı bir
   araştırma dosyasına** indirilir (bugünkü fiyat güncellemesiyle aynı yöntem; ~630 hisse, ~10–20 dk).
2. **Etiketleme:** geçmişin her günü için Halley'in bugünkü kuralları (kırılım / geri çekilme / destekten tepki, hazır
   plan şartları) **yalnız o güne kadarki veriyle** uygulanır. Sonraki günler işlem günlüğünün aynı çıkış kurallarıyla
   izlenir: önce TP1 mi, önce SL mi, ya da 30 günde ikisi de değil. Komisyon ve kayma dahil.
3. **Girdiler (o gün bilinenler):** teknik skor parçaları, RSI, günlük oynaklık (ATR %), trend, ortalamalara uzaklık,
   hacim oranı, endekse göre güç, piyasa durumu (BIST 100 trendi), senaryo türü, risk/getiri, stop mesafesi.
   **Haber kullanılmaz** (veri yetersiz); haber şartı bugünkü kural olarak kalır.
4. **İki aday model:**
   - (A) **Benzer durumlar tablosu:** senaryo türü × trend × oynaklık × RSI bandı gruplarında geçmiş başarı oranı.
     Anlaşılması en kolay olanı.
   - (B) **Lojistik regresyon:** numpy ile yazılır, yeni kütüphane gerektirmez.
5. **Sınama (en önemli kısım):** eski yıllarla eğitilir, **hiç görmediği son 12 ayda** sınanır. Ölçülenler:
   - isabet (AUC);
   - söylediği olasılıklar doğru mu (kalibrasyon): "%60" dediklerinin gerçekten ~%60'ı tutmuş mu;
   - ekonomik fayda: model "yüksek" dediğinde ortalama kazanç (R) gerçekten daha iyi mi.

   Taban çizgisi: kuralların genel başarı oranı. **Model bunu geçemezse devreye alınmaz**; sonuç olduğu gibi raporlanır.
6. **Rapor → onay → panel:** onaylarsanız kartlarda yalnız bilgi olarak görünür; örneğin "TP1 olasılığı %58 · geçmişte
   benzer 412 durumda %55". Seçimi ve eşikleri değiştirmez ("küçük pilotla eşik değiştirme" kuralı).

## Bilinen sınırlar
- **Borsadan çıkan hisseler** Yahoo'da yok: sonuçlar biraz iyimser çıkabilir.
- 5 yıl içinde farklı piyasa dönemleri var (yüksek enflasyon, sert yükseliş ve düşüşler). Dönemlere göre ayrıca bakılır.
- Tavan/taban kilitli günlerde gerçek işlem yapılamamış olabilir; bu günler işaretlenir.
- Geçmişte iyi çalışan bir model gelecekte de çalışacak demek değildir; yalnız olasılık bilgisidir.

## Maliyet ve süre
- **Yapay zekâ maliyeti: 0 $.** Hiç OpenAI çağrısı yok.
- Araştırma (veri indirme dahil): **yaklaşık 4–6 saat** çalışma. Onaylarsanız panele ekleme ek **~2 saat**.
- Bilgisayar: yalnız işlemci; eğitim birkaç dakika sürer. Ekran kartı gerekmez.

## Onayınız gereken
1. 5 yıllık fiyat verisinin ayrı bir araştırma dosyasına indirilmesi.
2. Araştırma aşamasının başlaması (panelde hiçbir şey değişmez; sonuç rapor olarak gelir).
