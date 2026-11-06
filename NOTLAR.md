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
| 4 Backtest ve paper trading | ⏳ |
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
- KAP "Finansal Rapor" metni rakam içermiyor. Bilanço rakamlarını tablo/ek dosyalardan okumak ileride ayrı bir iş.
