-- FAZ 1 v1 tahmin defteri şeması (main 60ff0b2, canlıdaki); test fikstürü — değiştirmeyin.

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
BEGIN SELECT RAISE(ABORT, 'tahmin kaydÄ± deÄŸiÅŸtirilemez'); END;
CREATE TRIGGER IF NOT EXISTS tahmin_no_delete BEFORE DELETE ON tahmin
BEGIN SELECT RAISE(ABORT, 'tahmin kaydÄ± silinemez'); END;
CREATE TRIGGER IF NOT EXISTS tahmin_sonuc_no_update BEFORE UPDATE ON tahmin_sonuc
BEGIN SELECT RAISE(ABORT, 'tahmin sonucu deÄŸiÅŸtirilemez'); END;
CREATE TRIGGER IF NOT EXISTS tahmin_sonuc_no_delete BEFORE DELETE ON tahmin_sonuc
BEGIN SELECT RAISE(ABORT, 'tahmin sonucu silinemez'); END;
