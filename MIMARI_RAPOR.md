# Halley — Mimari raporu (2026-11-14, Aşama 1)

Felsefe: **Veriyi Python işler. Algoritmalar analiz eder. Yapay zekâ yalnız gerektiğinde yorumlar. Kullanıcı son
kararı verir.** Emir verilmez. Uygulamanın yapay zekâ modeli OpenAI gpt-5-mini'dir (değişmez).

## 1. Çalışma akışı (bugünkü hâl)

```
KAP listesi + RSS haberleri ──► haber tablosu (news)            [kap.py, rss.py — Python]
        │  rutin KAP konuları kuralla atlanır (config.KAP_SKIP_SUBJECTS) — Python
        ▼
   analiz sırası (status='new') ─► YAPAY ZEKÂ haber analizi       [analyzer.py — yalnız elle/düğmeyle]
        │                           (RSS: önce ön eleme çağrısı; KAP: doğrudan tam analiz;
        │                            "yüksek doğruluk"ta büyük etkili haberde ikinci görüş)
        ▼
   etkiler (impacts) ─► haber skoru (yaş ile azalır)              [report.py — Python]
        ▼
   teknik analiz, senaryolar, risk, karar izi                     [technical.py, entries.py, tradeplan.py, signals.py — Python]
        ▼
   ✅ Hazır fırsatlar / ⏳ Bekleyen fırsatlar                      [ready.py, tradeplan.py — Python]
        ▼
   bekçi: kapanış/gün içi olayları, açılış kontrolü, sanal işlem  [tracker.py, ready.py, journal.py — Python]
        ▼
   raporlar, performans, Telegram                                 [watchdog.py, trends.py, missed.py, notify.py — Python]
```

Arka planda (okuyucu süreci, `kap_worker.serve`): KAP sayfa metinleri, işlem günlüğü fiyatları, takip bekçisi,
hazır fırsat otomasyonu (akşam/sabah/açılış). **Yapay zekâ çağırmaz** — tek istisna aşağıdaki tabloda ❗ ile işaretli.

## 2. Bütün yapay zekâ çağrıları

Aşama 2'den beri hepsi **merkezi servis** `bist_haber/ai_service.py` (`LLM.parse`, OpenAI `chat.completions.parse`,
yapılandırılmış JSON) üzerinden geçer ve `ai_calls` tablosuna kaydedilir (modül, işlem, kayıt, token, maliyet, süre,
durum, hata, tekrar). Geçmiş veri pilotu (`backtest.py`) kendi bütçe/önbellek istemcisini korur ama her çağrısını aynı
kayda yazar. Kullanım: ⚙️ Ayarlar → 🤖 Yapay zekâ kullanımı.

| # | Dosya / işlev | Tetikleyen kullanıcı işlemi | Sıklık | Gerçekten YZ gerekir mi? | Python ile değişir mi? | Önbellek |
|---|---|---|---|---|---|---|
| 1 | `analyzer.analyze` → `_analyze_one` **tam analiz** | 🔄 Haberleri güncelle (ayar: en fazla 10 haber), 📰 Haberler → 🔬 analiz et, sabah analizinde işaretli kutu | Kullanıcı bastıkça | **Evet** (haber yorumu) | Hayır; ama gereksiz haberler hiç gönderilmemeli (Aşama 3) | Var: analiz edilen haber tekrar analiz edilmez (status) |
| 2 | Aynı yer **RSS ön eleme** çağrısı | Aynı | RSS haberi başına | Hayır | **Evet** (Aşama 3) | — |
| 3 | Aynı yer **ikinci görüş** | Aynı ("yüksek doğruluk" ayarında, büyük etkili haber) | Nadir | Doğruluk için | Ayara bağlı kalır | — |
| 4 | `tracker.news_check` (takip listesi haberleri) | Bekçi 30 dk'da bir — **yalnız kullanıcı Ayarlar'da açtıysa** (Aşama 1'den beri varsayılan kapalı) | Otomatik (açıksa) | Hayır (kullanıcı istemedikçe) | — | Var |
| 5 | `ready.news_guard(analyze=True)` (hazır fırsat haber kontrolü) | 🤖 düğmesi; sabah otomatiği yalnız düğme açıksa (varsayılan **kapalı**) | Elle | Kullanıcı isterse | — | Var |
| 6 | `analyzer.reanalyze` (derin yeniden inceleme) | 📰 Haberler → 🔁 düğmesi | Elle | Evet | — | Eski sonuç saklanır |
| 7 | `analyzer.test_one` (ucuz test) | Ayarlar → 🧪 düğmesi | Elle | Deneme | — | Kaydedilmez |
| 8 | `ai_comment.comment_report` (rapor yorumu) | Sabah/akşam kutusu (varsayılan kapalı) | Elle | İsteğe bağlı | — | Var |
| 9 | `ai_comment.explain_missed` (kaçırılan fırsat açıklaması) | Akşam kutusu (varsayılan kapalı) | Elle | İsteğe bağlı | — | Açıklanan tekrar ücretlenmez |
| 10 | `backtest.analyze` (geçmiş veri pilotu) | Ayarlar → pilot düğmesi | Elle | Deneme amaçlı | — | Var (pilot DB) |

**Doğrulananlar:** ekran değiştirmek ve hisseye tıklamak yapay zekâ çağırmaz; sabah/akşam raporları, bekçi
olayları, kaçırılan fırsat analizi, hazır fırsat seçimi, performans ve Telegram Python'dur; bütçe tavanları (haber
analizi ve rapor yorumu, aylık) her çağrıdan önce denetlenir; API anahtarı olmadan uygulamanın tamamı çalışır
(bütün testler anahtarsız ve ağsız geçiyor).

## 3. Gerçek kullanım (canlı veri, Kasım 2026)

| Aşama | Çağrı | Maliyet |
|---|---|---|
| Tam analiz (KAP + RSS) | 148 | ≈ 2,28 $ (haber başına ≈ 0,015 $) |
| RSS ön eleme | 7 | ≈ 0,00 $ |
| Rapor yorumu / kaçırılan açıklaması | 0 | 0 $ |

Haber durumları: 148 analiz edildi · 982 analiz bekliyor · 1.837 kuralla atlandı · 7 ön elemede önemsiz ·
5.059 yalnız takvim için.

**Sonuç:** harcamanın neredeyse tamamı tam analizden geliyor. En büyük tasarruf, **gereksiz KAP bildirimlerinin
tam analize hiç gönderilmemesi** (Python ön sınıflandırma) ve **aynı içeriğin bir daha analiz edilmemesi** (içerik
özeti). RSS ön elemesini Python'a taşımak ilkeye uygun ama maliyete etkisi küçüktür.

## 4. Korunacaklar

Haber toplama, tüm teknik analiz, senaryolar, hazır/bekleyen fırsatlar, bekçi, takip listesi, işlem günlüğü,
performans, raporlar, Telegram, veri aktarma, kurulum/güncelleme, arayüz (9 ekran) ve kullanıcı verisi aynen kalır.

## 5. Aşama planı

| # | Aşama | Durum |
|---|---|---|
| 1 | Bu rapor + bekçinin kendiliğinden yaptığı YZ haber analizi (tablo #4) varsayılan **kapalı** | ✅ |
| 2 | Merkezi YZ servisi (bütün çağrılar; sayı, token, maliyet, modül, hata/tekrar; günlük/aylık ekran) + içerik özeti + tekrarlanan haber ayıklama | ✅ |
| 3 | Python ön eleme/sınıflandırma (KAP önceliği; RSS ön eleme çağrısının yerini alır) — geçmiş haberlerle kaçırma oranı ölçülerek | ✅ Devrede (kullanıcı onayı 14.11, doğrulama örneği istemeden): 148 etiketli haberde 0 kaçırma; bekleyenlerin ~%37'si YZ'ye gitmez |
| 4 | Genel fırsat puanı, haber özeti/etkisi, "yalnız teknik" fırsatlar, haftalık rapor | ✅ (14.11; puan yalnız bilgi, kurallar sınanmadı) |
| 5 | Profesyonel grafik + olası fiyat aralığı konisi | ✅ (15.11; koni oynaklıktan, yön tahmini değil) |
| 6 | Kendi tahmin modelimiz (TP1'e SL'den önce ulaşma olasılığı) | 🔬 araştırıldı, devreye alınmadı (zayıf ve kararsız fayda; ASAMA6_RAPOR.md) |
| 7 | Hazır zaman serisi modeli (Kronos / Chronos-Bolt / TinyTimeMixer) — BIST ince ayarı, isteğe bağlı paket | |
| 8 | 6 ve 7 işe yararsa birleştirme | |
