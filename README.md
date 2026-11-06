# Halley — BIST Haber Radarı (prototip)

KAP bildirimlerini ve ekonomi haberlerini toplar, OpenAI ile analiz eder, hisse bazında
skorlayıp sade bir web panelinde gösterir. **Emir vermez:** listeyi inceleyip emri Midas'tan
kendiniz girersiniz. Çıktı yatırım tavsiyesi değildir.

## Kullanım (Python bilgisi gerekmez)

1. Bilgisayarda Python 3.9 veya üstü kurulu olmalı.
2. **`baslat.bat`** dosyasına çift tıklayın. İlk açılışta gerekli paketler kurulur (birkaç dakika).
3. Tarayıcıda panel açılır. Sol menüden OpenAI API anahtarınızı bir kez girin.
4. **Verileri güncelle** düğmesine basın. Panel KAP ve haberleri toplar, yapay zekâya analiz ettirir.
5. **Sinyaller** sekmesinde bir satır seçerek o hisseyi etkileyen haberleri ve gerekçeleri görün.

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

## Geliştirmeye devam edecek kişi / yapay zekâ için

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

**Bilinmesi gerekenler**
- Python 3.9 uyumlu kalmalı (kullanıcının makinesi): `X | Y` tip sözdizimi, `match` vb. kullanmayın.
- Windows'ta proje yolu uzunsa venv kurulumu "long path" hatası verir; `baslat.bat` venv'i `%USERPROFILE%\.venvs\bist-haber` altına kurar.
- KAP ~1 sn/istek üzerinde HTTP 429 veriyor; `KAP_REQUEST_DELAY` düşürülmemeli.
- Streamlit sunucusu `bist_haber` modüllerindeki değişiklikleri her zaman yeniden yüklemiyor; kod değişince paneli yeniden başlatın.
- Otomatik test yok. Değişiklikten sonra: `python -m bist_haber collect` → `analyze --dry-run` → `analyze --limit 3` → `report`.
- `.env` (API anahtarı) ve `data/*.db` git'e eklenmez.
