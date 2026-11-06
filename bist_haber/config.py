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
ANALYSIS_WORKERS = int(os.getenv("ANALYSIS_WORKERS", "5"))  # aynı anda kaç haber analiz edilsin

# BIST sürekli işlem seansının bitişi (yerel saat). Sonrasında gelen haber
# en erken ertesi işlem günü kullanılabilir (Dipnot 7).
SESSION_CLOSE_HOUR = 18

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (bist-haber prototype)"}
KAP_BASE = "https://www.kap.org.tr"
KAP_REQUEST_DELAY = 1.5  # saniye; KAP hızlı isteklerde HTTP 429 ile engelliyor
# Ana metni bundan kısa olan bildirimlerde ("açıklama ekte yer almaktadır") PDF ekleri okunur.
KAP_SHORT_BODY_CHARS = 800
KAP_MAX_ATTACHMENTS = 2       # bildirim başına en fazla kaç PDF
KAP_ATTACHMENT_CHARS = 8000   # ek başına en fazla kaç karakter
KAP_ATTACHMENT_PAGES = 10     # PDF başına en fazla kaç sayfa (yatırımcı sunumları uzun)
FINANCIAL_SUMMARY_CHARS = 9000  # finansal rapor özeti üst sınırı

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
# Hisse eşleşmesi olmayan RSS haberleri ancak bu kelimelerden birini içerirse LLM'e gider.
RSS_MARKET_KEYWORDS = ["borsa", "bist", "hisse", "kap'a", "kap’a", "temettü", "halka arz", "bedelsiz", "bedelli"]
