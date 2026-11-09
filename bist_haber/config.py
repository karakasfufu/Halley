"""Uygulama ayarları. Gizli bilgiler (.env) koddan ayrı tutulur (Dipnot 10)."""
import os
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")

# Türkiye 2016'dan beri sabit UTC+3 kullanıyor.
TR_TZ = timezone(timedelta(hours=3))

DB_PATH = Path(os.getenv("DB_PATH", DATA / "bist_haber.db"))
UNIVERSE_FILE = DATA / "universe.txt"  # boşsa/yoksa: KAP'taki tüm şirketler
ALIASES_FILE = DATA / "aliases.csv"

# İki aşamalı LLM: ucuz model ön eleme, güçlü model derin analiz.
MODEL_FILTER = os.getenv("OPENAI_MODEL_FILTER", "gpt-5-mini")
MODEL_ANALYSIS = os.getenv("OPENAI_MODEL_ANALYSIS", "gpt-5-mini")
MAX_BODY_CHARS = int(os.getenv("MAX_BODY_CHARS", "16000"))  # detay kaçmasın; girdi token'ı ucuz
FILTER_BODY_CHARS = 1500
# Ön eleme basit bir evet/hayır sorusu; modelin "düşünme" miktarını azaltmak token tasarrufu sağlar.
# Derin analizde modelin varsayılanı kullanılır (kalite öncelikli).
FILTER_REASONING_EFFORT = os.getenv("FILTER_REASONING_EFFORT", "minimal")
# Derin analizde doğruluk öncelikli: model daha fazla "düşünür" (daha yavaş, biraz daha pahalı).
ANALYSIS_REASONING_EFFORT = os.getenv("ANALYSIS_REASONING_EFFORT", "high")
# İkinci görüş: etkisi büyük (≥3) ya da güveni düşük yönlü kararlar ikinci, bağımsız bir analizle
# kontrol edilir. Yön çelişirse etki nötrlenir ve "çelişkili" olarak işaretlenir.
SECOND_OPINION = os.getenv("SECOND_OPINION", "1") == "1"
SECOND_OPINION_MIN_IMPACT = 3

# Kullanıcının panelden seçebileceği analiz kalitesi (2026-11-07). Varsayılan "yuksek" = yukarıdaki ayarlar.
# Model her profilde gpt-5-mini. Geçmiş veri pilotu bu seçimden etkilenmez (her zaman "yuksek").
# Maliyetin büyük kısmı modelin düşünme dahil çıktısıdır; "maliyet" alanı kabaca göreli tahmindir.
QUALITY_PROFILES = {
    "yuksek": {"etiket": "Yüksek doğruluk (önerilen)", "reasoning": ANALYSIS_REASONING_EFFORT,
               "second_opinion": SECOND_OPINION, "second_min_impact": SECOND_OPINION_MIN_IMPACT,
               "body_factor": 1.0, "maliyet": "tam maliyet"},
    "dengeli": {"etiket": "Dengeli", "reasoning": "medium", "second_opinion": True, "second_min_impact": 4,
                "body_factor": 1.0, "maliyet": "tahminen ~%55–70"},
    "ekonomik": {"etiket": "Ekonomik", "reasoning": "low", "second_opinion": False, "second_min_impact": 5,
                 "body_factor": 0.6, "maliyet": "tahminen ~%30–40"},
}
DEFAULT_QUALITY = "yuksek"
TEST_QUALITY = "ekonomik"  # kaydedilmeyen ucuz test analizi için
ANALYSIS_WORKERS = int(os.getenv("ANALYSIS_WORKERS", "5"))  # aynı anda kaç haber analiz edilsin

# BIST sürekli işlem seansının bitişi (yerel saat). Sonrasında gelen haber
# en erken ertesi işlem günü kullanılabilir (Dipnot 7).
SESSION_CLOSE_HOUR = 18

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (bist-haber prototype)"}
KAP_BASE = "https://www.kap.org.tr"
KAP_HISTORY_DAYS = 180  # takvim için KAP geçmişi (2026-11-07, kullanıcı: 45 → 180 gün; uzun süreçler, 2. taksitler)
KAP_REQUEST_DELAY = 1.5  # saniye; KAP hızlı isteklerde HTTP 429 ile engelliyor
# Ana metni bundan kısa olan bildirimlerde ("açıklama ekte yer almaktadır") PDF ekleri okunur.
KAP_SHORT_BODY_CHARS = 800
KAP_MAX_ATTACHMENTS = 2       # bildirim başına en fazla kaç PDF
KAP_ATTACHMENT_CHARS = 8000   # ek başına en fazla kaç karakter
KAP_ATTACHMENT_PAGES = 10     # PDF başına en fazla kaç sayfa (yatırımcı sunumları uzun)
FINANCIAL_SUMMARY_CHARS = 9000  # finansal rapor özeti üst sınırı

# Konuya göre okuma sınırları (2026-11-06). Önemli olayların belgeleri uzun olduğu için varsayılan
# sınırlarda dışarıda kalıyordu (seçilim yanlılığı). Sınır yalnızca bu konularda büyür; diğerleri değişmez.
# Konu adında geçen metinle eşleşir; ilk eşleşen grup kullanılır.
READING_PROFILES = [
    (("Pay Alım Teklifi", "Birleşme", "Payların Geri Alınmasına", "Yeni İş İlişkisi"),
     {"attachment_chars": 30000, "pages": 25, "attachments": 4, "body_chars": 60000}),
    (("Genel Kurul",),
     {"attachment_chars": KAP_ATTACHMENT_CHARS, "pages": KAP_ATTACHMENT_PAGES, "attachments": 4,
      "body_chars": 25000}),
]


def reading_limits(subject):
    """{"attachment_chars", "pages", "attachments", "body_chars"} — konuya göre okuma sınırları."""
    for keys, limits in READING_PROFILES:
        if any(k in (subject or "") for k in keys):
            return dict(limits)
    return {"attachment_chars": KAP_ATTACHMENT_CHARS, "pages": KAP_ATTACHMENT_PAGES,
            "attachments": KAP_MAX_ATTACHMENTS, "body_chars": MAX_BODY_CHARS}

# Bu konulardaki KAP bildirimleri yapay zekâya hiç gönderilmez ve metinleri de çekilmez
# (maliyet + KAP istek sınırı). Konu adında geçen metinle eşleşir. 2026-11-06 verisinde
# bu türlerin hepsi ya elendi ya da "yönsüz" çıktı; token'ların ~%70'ini bunlar harcıyordu.
KAP_SKIP_SUBJECTS = [
    "Pay Dışında Sermaye Piyasası Aracı",   # bono/tahvil ihraç bildirimleri
    "Devre Kesici",                         # borsanın otomatik fiyat duyurusu, haber değil
    "Faaliyet Raporu",
    "Sorumluluk Beyanı",
    "Şirket Genel Bilgi Formu",
    "Kurumsal Yönetim İlkelerine Uyum",
    "Varant - Sertifika",
    "Kamuyu Aydınlatma Platformu Duyurusu",
    "BISTECH",
    # 2026-11-06 pilot incelemesi: içerik olarak fiyat bilgisi taşımayan rutin bildirimler.
    "Piyasa Yapıcılığı Kapsamında",           # aracı kurumun fon piyasa yapıcılığı işlem raporu
    "Likidite Sağlayıcılık Kapsamında",
    "Bilgilendirme Politikası",
    "Haftalık Rapor",
    "Sürdürülebilirlik Raporu",
    "Kurumsal Yönetim Bilgi Formu",
]

RSS_FEEDS = {
    "bloomberght": "https://www.bloomberght.com/rss/tum-haberler.xml",
    "uzmanpara": "https://uzmanpara.milliyet.com.tr/haber_rss/",
    "dunya": "https://www.dunya.com/rss?dunya",
    "haberturk": "https://www.haberturk.com/rss/ekonomi.xml",
    "ntv": "https://www.ntv.com.tr/ekonomi.rss",
    "trt": "https://www.trthaber.com/ekonomi_articles.rss",
}
RSS_SOURCE_LABELS = {"bloomberght": "BloombergHT", "uzmanpara": "Uzmanpara", "dunya": "Dünya",
                     "haberturk": "Habertürk", "ntv": "NTV", "trt": "TRT Haber"}
RSS_MAX_AGE_DAYS = 3  # bazı akışlar aylar önceki haberleri de içeriyor
# 2026-11-09 (kullanıcı onayı): kendiliğinden (güncelleme / sabah analizi) analiz edilecek haberin en fazla yaşı.
# Haber skoru orta kalıcılıkta 5 günde yarıya iner; daha eski haber elle seçilirse yine analiz edilir.
AUTO_ANALYSIS_MAX_AGE_DAYS = 5
NEWS_BUDGET_USD = 10.0     # haber analizi aylık bütçe varsayılanı (Ayarlar'dan değişir)
MAX_ANALYSIS_PER_RUN = 50  # güncelleme / sabah analizi başına en fazla haber (Ayarlar seçenekleri 1–30)
MAX_ANALYSIS_MANUAL = 300  # "🔬 Haber analizi" bölümünde tek seferde en fazla
# Hisse eşleşmesi olmayan RSS haberleri ancak bu kelimelerden birini içerirse LLM'e gider.
RSS_MARKET_KEYWORDS = ["borsa", "bist", "hisse", "kap'a", "kap’a", "temettü", "halka arz", "bedelsiz", "bedelli"]
