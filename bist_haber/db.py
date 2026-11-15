"""SQLite veritabanı. Prototip için SQLite; ileride PostgreSQL'e geçmek kolay."""
import sqlite3
from pathlib import Path
from typing import Dict, List

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
-- 2026-11-09 hız: panel her hisse için konuya/tarihe göre KAP kaydı arıyor; dizinsiz her sorgu tüm haber metinlerini
-- okuyordu (126 hissede 33 sn). Sonuçları değiştirmez.
CREATE INDEX IF NOT EXISTS ix_news_subject ON news(subject);
CREATE INDEX IF NOT EXISTS ix_news_published ON news(published_at);
-- konu + hisse kodu birlikte: "candidates" sütunu tabloda büyük "body"den sonra geldiği için doğrudan okunması metni de
-- okutuyordu; bu dizinle hisse eşleşmesi metne dokunmadan bulunur (sorgu başına 17,9 → 1,2 ms ölçüldü).
CREATE INDEX IF NOT EXISTS ix_news_subject_cand ON news(subject, candidates, source);
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
-- W1 (2026-11-07): bekçi çalıştırmaları ve her hisse için karar izi. YALNIZ EKLENİR; değiştirilemez, silinemez.
CREATE TABLE IF NOT EXISTS watch_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,            -- sabah | aksam | guncelleme
    day         TEXT NOT NULL,            -- çalıştırma günü (TR)
    started_at  TEXT NOT NULL,
    summary_json TEXT
);
CREATE TABLE IF NOT EXISTS signal_log (
    run_id       INTEGER NOT NULL REFERENCES watch_runs(run_id),
    ticker       TEXT NOT NULL,
    karar        TEXT NOT NULL,           -- onerildi | onerilmedi
    neden_kodu   TEXT NOT NULL,
    modul        TEXT,
    neden        TEXT,
    haber_skoru  REAL,
    haber_sayisi INTEGER,
    son_fiyat    REAL,
    fiyat_gunu   TEXT,
    senaryo      TEXT,
    giris REAL, sl REAL, tp1 REAL, tp2 REAL,
    risk_seviyesi TEXT,
    detay_json   TEXT,
    PRIMARY KEY (run_id, ticker)
);
CREATE TRIGGER IF NOT EXISTS signal_log_no_update BEFORE UPDATE ON signal_log
BEGIN SELECT RAISE(ABORT, 'sinyal geçmişi değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS signal_log_no_delete BEFORE DELETE ON signal_log
BEGIN SELECT RAISE(ABORT, 'sinyal geçmişi silinemez'); END;
CREATE TRIGGER IF NOT EXISTS watch_runs_no_update BEFORE UPDATE ON watch_runs
BEGIN SELECT RAISE(ABORT, 'çalıştırma kaydı değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS watch_runs_no_delete BEFORE DELETE ON watch_runs
BEGIN SELECT RAISE(ABORT, 'çalıştırma kaydı silinemez'); END;
-- W4 (2026-11-07): penceresi tamamlanmış kaçırılan fırsatlar (eğilim takibi için). YALNIZ EKLENİR.
CREATE TABLE IF NOT EXISTS missed_log (
    baz_gun          TEXT NOT NULL,
    ticker           TEXT NOT NULL,
    run_id           INTEGER NOT NULL REFERENCES watch_runs(run_id),
    neden_kodu       TEXT NOT NULL,
    modul            TEXT,
    kazanc_pct       REAL,
    endekse_gore_atr REAL,
    zirve_gunu       TEXT,
    etiketler        TEXT,
    kayit_ani        TEXT NOT NULL,
    UNIQUE (baz_gun, ticker)
);
CREATE TRIGGER IF NOT EXISTS missed_log_no_update BEFORE UPDATE ON missed_log
BEGIN SELECT RAISE(ABORT, 'kaçırılan fırsat kaydı değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS missed_log_no_delete BEFORE DELETE ON missed_log
BEGIN SELECT RAISE(ABORT, 'kaçırılan fırsat kaydı silinemez'); END;
-- W5: penceresi tamamlanmış karar günlerinde neden başına değerlendirilen / kaçırılan sayısı. YALNIZ EKLENİR.
CREATE TABLE IF NOT EXISTS missed_day_stats (
    baz_gun         TEXT NOT NULL,
    neden_kodu      TEXT NOT NULL,
    run_id          INTEGER NOT NULL,
    degerlendirilen INTEGER NOT NULL,
    kacirilan       INTEGER NOT NULL,
    UNIQUE (baz_gun, neden_kodu)
);
CREATE TRIGGER IF NOT EXISTS missed_day_stats_no_update BEFORE UPDATE ON missed_day_stats
BEGIN SELECT RAISE(ABORT, 'kayıt değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS missed_day_stats_no_delete BEFORE DELETE ON missed_day_stats
BEGIN SELECT RAISE(ABORT, 'kayıt silinemez'); END;
-- W5: onay bekleyen iyileştirme önerileri. Öneri metni/kanıtı değişmez; durum YALNIZ BİR KEZ (bekliyor → onaylandı/
-- reddedildi) değiştirilebilir. Onay hiçbir ayarı kendiliğinden değiştirmez.
CREATE TABLE IF NOT EXISTS suggestions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    anahtar     TEXT NOT NULL,
    tur         TEXT NOT NULL,             -- ayar | kod | bilgi
    baslik      TEXT NOT NULL,
    metin       TEXT NOT NULL,
    kanit_json  TEXT NOT NULL,
    nerede      TEXT,
    olusturma   TEXT NOT NULL,
    durum       TEXT NOT NULL DEFAULT 'bekliyor',
    karar_ani   TEXT,
    karar_notu  TEXT
);
CREATE TRIGGER IF NOT EXISTS suggestions_once BEFORE UPDATE ON suggestions
WHEN OLD.durum != 'bekliyor' OR NEW.anahtar != OLD.anahtar OR NEW.metin != OLD.metin OR NEW.kanit_json != OLD.kanit_json
     OR NEW.baslik != OLD.baslik OR NEW.tur != OLD.tur OR NEW.olusturma != OLD.olusturma
BEGIN SELECT RAISE(ABORT, 'öneri kaydı değiştirilemez (karar yalnız bir kez verilir)'); END;
CREATE TRIGGER IF NOT EXISTS suggestions_no_delete BEFORE DELETE ON suggestions
BEGIN SELECT RAISE(ABORT, 'öneri kaydı silinemez'); END;
-- 2026-11-09: analiz edilmiş haberin "derin yeniden inceleme"si; önceki ve yeni sonuç. YALNIZ EKLENİR.
CREATE TABLE IF NOT EXISTS reanalysis_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id       TEXT NOT NULL,
    eski_json     TEXT NOT NULL,
    yeni_json     TEXT,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    durum         TEXT NOT NULL,          -- tamam | hata
    created_at    TEXT NOT NULL,
    eski_input_tokens  INTEGER,           -- yerine yazılan önceki analizin maliyeti (aylık harcamada kaybolmasın)
    eski_output_tokens INTEGER,
    eski_ay            TEXT               -- önceki analizin yapıldığı ay (YYYY-AA)
);
CREATE TRIGGER IF NOT EXISTS reanalysis_log_no_update BEFORE UPDATE ON reanalysis_log
BEGIN SELECT RAISE(ABORT, 'yeniden inceleme kaydı değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS reanalysis_log_no_delete BEFORE DELETE ON reanalysis_log
BEGIN SELECT RAISE(ABORT, 'yeniden inceleme kaydı silinemez'); END;
-- W6: yapay zekâ yorumları ve maliyetleri (aylık bütçe denetimi buradan). YALNIZ EKLENİR.
CREATE TABLE IF NOT EXISTS ai_comments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    kind                TEXT NOT NULL,      -- sabah | aksam | kacirilan
    ref                 TEXT NOT NULL,      -- rapor günü_türü ya da HISSE:baz_gun
    model               TEXT NOT NULL,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    usd                 REAL NOT NULL,
    result_json         TEXT NOT NULL,
    dogrulanamayan_json TEXT,
    created_at          TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ai_comments_no_update BEFORE UPDATE ON ai_comments
BEGIN SELECT RAISE(ABORT, 'yapay zekâ kaydı değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS ai_comments_no_delete BEFORE DELETE ON ai_comments
BEGIN SELECT RAISE(ABORT, 'yapay zekâ kaydı silinemez'); END;
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
-- 2026-11-09 Takip Listem (kullanıcı isteği): seçilen hisseler, senaryoları ve bekçi olayları. Takipten çıkarılan
-- hissenin kaydı SİLİNMEZ (aktif=0); yalnız yeni bildirimler durur.
CREATE TABLE IF NOT EXISTS watchlist (
    ticker      TEXT PRIMARY KEY,
    eklendi     TEXT NOT NULL,
    aktif       INTEGER NOT NULL DEFAULT 1,
    cikarildi   TEXT,
    bildirimler TEXT,                 -- JSON liste: açık bildirim türleri (NULL = hepsi açık)
    son_trend   TEXT                  -- teknik görünüm değişikliğini yakalamak için
);
CREATE TABLE IF NOT EXISTS takip_senaryo (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT NOT NULL,
    senaryo      TEXT NOT NULL,       -- kirilim | geri_cekilme | destek
    signal_day   TEXT NOT NULL,       -- seviyelerin hesaplandığı son fiyat günü (sonraki günler değerlendirilir)
    olusturuldu  TEXT NOT NULL,
    emir         TEXT,
    alarm        REAL,
    giris        REAL NOT NULL,
    sl           REAL NOT NULL,
    tp1          REAL NOT NULL,
    tp2          REAL NOT NULL,
    gecerlilik   INTEGER NOT NULL,
    kalite       TEXT,
    bildirim     INTEGER NOT NULL DEFAULT 1,   -- kullanıcı bu senaryonun bildirimini kapatabilir
    durum        TEXT NOT NULL DEFAULT 'bekliyor',
    sonuc_json   TEXT,
    guncellendi  TEXT,
    UNIQUE (ticker, senaryo, signal_day)
);
CREATE TABLE IF NOT EXISTS takip_olay (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman       TEXT NOT NULL,
    gun         TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    senaryo_id  INTEGER,
    tur         TEXT NOT NULL,        -- giris | sl | tp | gecersiz | hacim | kirilim | teyit | haber | teknik
    mesaj       TEXT NOT NULL,
    anahtar     TEXT NOT NULL UNIQUE, -- aynı olay ikinci kez kaydedilmez / bildirilmez
    kesin       INTEGER NOT NULL DEFAULT 1,  -- 0 = gün içi (kapanışla teyit edilmedi)
    gonderildi  INTEGER NOT NULL DEFAULT 0,  -- 1 gönderildi, -1 bildirim kapalı (yalnız kayıt)
    hata        TEXT
);
CREATE INDEX IF NOT EXISTS ix_takip_olay_ticker ON takip_olay(ticker, zaman);
-- 2026-11-10 Hazır Fırsatlar (kullanıcı isteği): akşam/sabah analizinde seçilen, koşulu zaten sağlanmış işlem planları.
-- Performans bekleyen senaryolardan AYRI ölçülür (giriş = plan günü açılışı, azami girişin üstündeyse giriş yok).
CREATE TABLE IF NOT EXISTS hazir_firsat (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    olusturuldu   TEXT NOT NULL,
    analiz        TEXT NOT NULL,          -- aksam | sabah
    signal_day    TEXT NOT NULL,          -- planın dayandığı son kapanış günü
    giris_gunu    TEXT NOT NULL,          -- planlanan giriş günü (açılış)
    ticker        TEXT NOT NULL,
    tur           TEXT NOT NULL,          -- kirilim_teyitli | geri_cekilme | destek_teyitli | mevcut_fiyat
    kapanis       REAL NOT NULL,
    giris         REAL NOT NULL,
    giris_alt     REAL NOT NULL,
    azami_giris   REAL NOT NULL,
    sl            REAL NOT NULL,
    tp1           REAL NOT NULL,
    tp2           REAL NOT NULL,
    rr1           REAL NOT NULL,
    vade_lo       INTEGER, vade_hi INTEGER,
    haber_skoru   REAL, teknik_skor INTEGER, risk TEXT,
    neden         TEXT,
    durum         TEXT NOT NULL DEFAULT 'aday',   -- aday | onaylandi | iptal | giris | kapandi | girissiz
    iptal_nedeni  TEXT,
    acilis        REAL,
    sonuc_json    TEXT,
    guncellendi   TEXT,
    UNIQUE (signal_day, ticker)
);
"""


def connect(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # Panel ve arka plan KAP okuyucusu aynı anda yazabilir: kilitte 30 sn bekle (varsayılan 5 sn).
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    from .ai_service import SCHEMA as _AI_SCHEMA     # 2026-11-14: YZ çağrı kaydı tablosu
    conn.executescript(_AI_SCHEMA)
    # Eski veritabanlarına sonradan eklenen sütunlar
    cols = {r[1] for r in conn.execute("PRAGMA table_info(impacts)")}
    if "flag" not in cols:
        conn.execute("ALTER TABLE impacts ADD COLUMN flag TEXT")  # ör. "çelişkili", "ikinci görüş"
    news_cols = {r[1] for r in conn.execute("PRAGMA table_info(news)")}
    if "content_hash" not in news_cols:   # 2026-11-14: içerik özeti (aynı içerik yeniden analiz edilmez)
        conn.execute("ALTER TABLE news ADD COLUMN content_hash TEXT")
    if "donem" not in news_cols:  # finansal raporun ait olduğu dönem, KAP listesinden: "2026/3" (3 = 9 aylık)
        conn.execute("ALTER TABLE news ADD COLUMN donem TEXT")
    hz_cols = {r[1] for r in conn.execute("PRAGMA table_info(hazir_firsat)")}
    if "kaynak" not in hz_cols:   # 2026-11-14 Aşama 4: haberli | teknik (yalnız teknik fırsat), ayrı ölçülür
        conn.execute("ALTER TABLE hazir_firsat ADD COLUMN kaynak TEXT NOT NULL DEFAULT 'haber'")
    if "genel_puan" not in hz_cols:
        conn.execute("ALTER TABLE hazir_firsat ADD COLUMN genel_puan REAL")
    if "model_json" not in hz_cols:   # 2026-11-15 Aşama 6 gizli kayıt: öneri anındaki TP1 olasılığı (panelde gösterilmez)
        conn.execute("ALTER TABLE hazir_firsat ADD COLUMN model_json TEXT")
    price_cols = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    for col in ("open", "high", "low"):  # teknik analiz için (2026-11-07)
        if col not in price_cols:
            conn.execute(f"ALTER TABLE prices ADD COLUMN {col} REAL")
    migrate_tahmin(conn, path)
    return conn


# ---------------------------------------------------------------- FAZ 1 (2026-11-16): canlı tahmin defteri
# Tahmin = belirli anda, dondurulmuş plan seviyeleri için modelin söylediği (YALNIZ EKLENİR; değiştirilemez, silinemez).
# Tahmin sonucu = o tahminin kendi seviyeleriyle nihai sonucu (tahmin başına en fazla bir satır; YALNIZ EKLENİR).
# Hazır fırsat (hazir_firsat) ve sanal işlem (trade_journal) ayrı kavramlardır ve bu tablolardan etkilenmez.
TAHMIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS tahmin (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_imzasi      TEXT NOT NULL UNIQUE,
    onceki_tahmin_id INTEGER REFERENCES tahmin(id),
    hazir_firsat_id  INTEGER,
    ticker           TEXT NOT NULL,
    signal_day       TEXT NOT NULL,
    giris_gunu       TEXT NOT NULL,
    analiz           TEXT,
    tahmin_zamani    TEXT NOT NULL,
    model_surum      TEXT NOT NULL,
    model_dosya      TEXT,
    ozellik_surum    TEXT NOT NULL,
    parametre_surum  TEXT NOT NULL,
    kod_surum        TEXT,
    olasilik         REAL NOT NULL,
    bant             TEXT,
    benzer_n         INTEGER,
    benzer_oran      REAL,
    tur              TEXT NOT NULL,
    giris            REAL NOT NULL,
    giris_alt        REAL,
    azami_giris      REAL NOT NULL,
    sl               REAL NOT NULL,
    tp1              REAL NOT NULL,
    tp2              REAL NOT NULL,
    rr1              REAL,
    gecerlilik_gun   INTEGER NOT NULL,
    genel_puan       REAL,
    teknik_skor      INTEGER,
    haber_skoru      REAL,
    kaynak           TEXT,
    risk             TEXT,
    girdi_json       TEXT,
    teknik_json      TEXT,
    rejim_json       TEXT,
    veri_json        TEXT,
    sonradan         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS tahmin_hisse_gun ON tahmin(ticker, giris_gunu);
CREATE TABLE IF NOT EXISTS tahmin_sonuc (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    tahmin_id          INTEGER NOT NULL UNIQUE REFERENCES tahmin(id),
    sonuc_turu         TEXT NOT NULL,     -- tamamlandi | girissiz | iptal | yerini_aldi | gec_kayit
    neden              TEXT,
    giris_gunu_gercek  TEXT,
    giris_fiyati       REAL,
    tp1_goruldu        INTEGER,
    sl_goruldu         INTEGER,
    cikis_nedeni       TEXT,
    cikis_gunu         TEXT,
    islem_gunu         INTEGER,
    net_getiri_pct     REAL,
    r                  REAL,
    mae_r              REAL,
    mfe_r              REAL,
    ayni_gun_belirsiz  INTEGER NOT NULL DEFAULT 0,
    belirsiz_gunler    TEXT,
    ayrinti_json       TEXT,
    degerlendirme_zamani TEXT NOT NULL,
    kural_surum        TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS tahmin_no_update BEFORE UPDATE ON tahmin
BEGIN SELECT RAISE(ABORT, 'tahmin kaydı değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS tahmin_no_delete BEFORE DELETE ON tahmin
BEGIN SELECT RAISE(ABORT, 'tahmin kaydı silinemez'); END;
CREATE TRIGGER IF NOT EXISTS tahmin_sonuc_no_update BEFORE UPDATE ON tahmin_sonuc
BEGIN SELECT RAISE(ABORT, 'tahmin sonucu değiştirilemez'); END;
CREATE TRIGGER IF NOT EXISTS tahmin_sonuc_no_delete BEFORE DELETE ON tahmin_sonuc
BEGIN SELECT RAISE(ABORT, 'tahmin sonucu silinemez'); END;
"""
USER_TABLES = ("news", "hazir_firsat", "trade_journal", "watchlist")
TAHMIN_GOC = {"durum": None, "yedek": None, "hata": None}   # son göç denemesi (panel ve testler okur)


def _has_user_data(conn) -> bool:
    for t in USER_TABLES:
        try:
            if conn.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone():
                return True
        except sqlite3.Error:
            continue
    return False


def migrate_tahmin(conn, path) -> Dict:
    """Tahmin defteri tablolarını ekler (yalnız EKLEME; mevcut tablolara dokunmaz). Tablo zaten varsa hiçbir şey
    yapmaz. Kullanıcı verisi varsa ÖNCE tutarlı yedek alınır ve doğrulanır (PRAGMA integrity_check); yedek
    alınamazsa ya da bozuksa göç YAPILMAZ (Halley bugünkü gibi çalışır, defter kapalı kalır)."""
    from datetime import datetime as _dt
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tahmin'").fetchone():
        TAHMIN_GOC.update(durum="var", yedek=None, hata=None)
        return dict(TAHMIN_GOC)
    yedek = None
    try:
        if path is not None and str(path) != ":memory:" and _has_user_data(conn):
            p = Path(path)
            ydir = p.parent / "yedek"
            ydir.mkdir(parents=True, exist_ok=True)
            yedek = ydir / f"{p.stem}_{_dt.now():%Y%m%d_%H%M%S}_tahmin_defteri_oncesi.db"
            conn.commit()
            dst = sqlite3.connect(yedek)
            try:
                conn.backup(dst)
                chk = dst.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                dst.close()
            if chk != "ok":
                TAHMIN_GOC.update(durum="yedek_bozuk", yedek=str(yedek), hata=chk)
                return dict(TAHMIN_GOC)
    except Exception as e:  # yedek alınamadıysa göç yapılmaz
        TAHMIN_GOC.update(durum="yedek_hatasi", yedek=str(yedek) if yedek else None, hata=str(e)[:200])
        return dict(TAHMIN_GOC)
    try:
        conn.commit()
        conn.execute("BEGIN")
        for stmt in _split_sql(TAHMIN_SCHEMA):
            conn.execute(stmt)
        conn.execute("COMMIT")
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        TAHMIN_GOC.update(durum="goc_hatasi", yedek=str(yedek) if yedek else None, hata=str(e)[:200])
        return dict(TAHMIN_GOC)
    TAHMIN_GOC.update(durum="olusturuldu", yedek=str(yedek) if yedek else None, hata=None)
    return dict(TAHMIN_GOC)


def _split_sql(script: str) -> List[str]:
    """Tetikleyici gövdesindeki ';' bölünmesin diye sqlite3.complete_statement ile ifadelere ayırır."""
    out, buf = [], ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    return out
