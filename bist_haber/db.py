"""SQLite veritabanı. Prototip için SQLite; ileride PostgreSQL'e geçmek kolay."""
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    city   TEXT
);
CREATE TABLE IF NOT EXISTS news (
    id             TEXT PRIMARY KEY,      -- kap:<index> | rss:<sha1(url)>
    source         TEXT NOT NULL,
    published_at   TEXT NOT NULL,         -- ISO, UTC+3
    effective_date TEXT NOT NULL,         -- haberin en erken kullanılabileceği işlem günü
    title          TEXT NOT NULL,
    title_key      TEXT,                  -- tekrar eden haberleri ayıklamak için
    subject        TEXT,
    body           TEXT,
    url            TEXT,
    candidates     TEXT,                  -- virgülle ayrılmış aday hisse kodları
    status         TEXT NOT NULL DEFAULT 'new', -- new|skipped|filtered_out|analyzed|error
    note           TEXT,
    fetched_at     TEXT NOT NULL,
    donem          TEXT                   -- finansal rapor dönemi (KAP listesi year/period): "2026/3"
);
CREATE INDEX IF NOT EXISTS ix_news_status ON news(status);
-- 2026-11-07: hangi günlerin KAP listesi eksiksiz alındı (boşluk varsa bilanço durumu "bilinmiyor" denir)
CREATE TABLE IF NOT EXISTS kap_coverage (
    day       TEXT PRIMARY KEY,           -- YYYY-AA-GG
    listed_at TEXT NOT NULL               -- o günün listesinin en son alındığı an (ISO, TR)
);
CREATE INDEX IF NOT EXISTS ix_news_title_key ON news(title_key);
CREATE TABLE IF NOT EXISTS analyses (
    news_id       TEXT PRIMARY KEY REFERENCES news(id),
    stage         TEXT NOT NULL,          -- filter | full
    model         TEXT NOT NULL,
    result_json   TEXT NOT NULL,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS impacts (
    news_id        TEXT NOT NULL REFERENCES news(id),
    ticker         TEXT NOT NULL,
    direction      INTEGER NOT NULL,      -- +1 / 0 / -1
    magnitude      INTEGER NOT NULL,      -- 1..5
    confidence     REAL NOT NULL,         -- 0..1
    persistence    TEXT NOT NULL,         -- kisa|orta|uzun
    event_type     TEXT NOT NULL,
    reason         TEXT,
    published_at   TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    PRIMARY KEY (news_id, ticker)
);
CREATE TABLE IF NOT EXISTS company_stats (
    ticker     TEXT PRIMARY KEY,
    date       TEXT NOT NULL,      -- verinin alındığı gün
    market_cap REAL,               -- TL
    last_price REAL
);
-- Parça C1 (2026-11-07): işlem günlüğü. otomatik = panelin "uygun" senaryosu (sanal), gercek = kullanıcının girdiği.
CREATE TABLE IF NOT EXISTS trade_journal (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    signal_day   TEXT NOT NULL,            -- senaryonun hesaplandığı son fiyat günü (sonraki günler değerlendirilir)
    ticker       TEXT NOT NULL,
    kaynak       TEXT NOT NULL,            -- otomatik | gercek
    haber_skoru  REAL,
    risk_seviyesi TEXT,
    senaryo      TEXT NOT NULL,            -- kirilim | geri_cekilme | destek
    emir         TEXT,
    alarm        REAL,
    giris        REAL NOT NULL,
    sl           REAL NOT NULL,
    tp1          REAL NOT NULL,
    tp2          REAL NOT NULL,
    gecerlilik   INTEGER NOT NULL,
    gercek_giris_gunu TEXT,                -- gercek kayıtta kullanıcının alış günü/fiyatı
    gercek_giris_fiyati REAL,
    ana_id       INTEGER,                  -- gercek kaydın türetildiği otomatik kayıt
    durum        TEXT NOT NULL DEFAULT 'bekliyor',
    sonuc_json   TEXT,
    guncellendi  TEXT,
    UNIQUE (ticker, signal_day, senaryo, kaynak)
);
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL,
    volume REAL,
    open   REAL,
    high   REAL,
    low    REAL,
    PRIMARY KEY (ticker, date)
);
"""


def connect(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # Panel ve arka plan KAP okuyucusu aynı anda yazabilir: kilitte 30 sn bekle (varsayılan 5 sn).
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Eski veritabanlarına sonradan eklenen sütunlar
    cols = {r[1] for r in conn.execute("PRAGMA table_info(impacts)")}
    if "flag" not in cols:
        conn.execute("ALTER TABLE impacts ADD COLUMN flag TEXT")  # ör. "çelişkili", "ikinci görüş"
    news_cols = {r[1] for r in conn.execute("PRAGMA table_info(news)")}
    if "donem" not in news_cols:  # finansal raporun ait olduğu dönem, KAP listesinden: "2026/3" (3 = 9 aylık)
        conn.execute("ALTER TABLE news ADD COLUMN donem TEXT")
    price_cols = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    for col in ("open", "high", "low"):  # teknik analiz için (2026-11-07)
        if col not in price_cols:
            conn.execute(f"ALTER TABLE prices ADD COLUMN {col} REAL")
    return conn
