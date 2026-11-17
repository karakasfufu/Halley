"""FAZ 3 (16.11.2026) — fiyat izlenebilirliği, sürüm "fiyat_izi_v1". O4 (17.11.2026): ürüne bağlandı —
db.connect() göçü yedekli ve tek süreçte yapar (hata olursa Halley bugünkü gibi çalışır); prices.update yazımı
yaz() üzerinden yapar. Canlıya alma ayrı onay ister.

SORUN: prices.update yfinance'tan auto_adjust=True ile indirir ve INSERT OR REPLACE ile yazar. Her indirme geçmiş
satırları o günün düzeltme tabanıyla üzerine yazar; kaynak, ayar, zaman ve eski değer saklanmaz. Bir backtestin
kullandığı veri kümesi sonradan yeniden üretilemez.

TASARIM (yalnız EKLEME; mevcut tablo ve satırlar değişmez):
  fiyat_indirme  her indirmenin kaydı: zaman, kaynak, kaynak sürümü, indirme ayarları (period/interval/auto_adjust),
                 düzeltme türü, kod sürümü, hisse/satır sayısı, yazılan satırların SHA-256 özeti, değişen satır sayısı.
                 Ekle-yalnız (UPDATE/DELETE tetikleyiciyle engelli).
  fiyat_eski     bir indirme mevcut satırı FARKLI değerle değiştirdiğinde ESKİ satır buraya yazılır (hangi indirmenin
                 değiştirdiği ile). Böylece belli bir indirmeden önceki durum geri kurulabilir (yalnız bu tablo
                 kurulduktan SONRAKİ değişiklikler için). Ekle-yalnız.
  prices.indirme_id  satırın BUGÜNKÜ değerini koyan indirme (değişmeyen satır yeniden yazılmaz). Eski satırlarda
                 NULL = "bilinmiyor" (UYDURULMAZ).
  veri_anlik     backtest veri kümesi anlık görüntüsü: ad, zaman, dosya yolu, satır/hisse/tarih aralığı, SHA-256
                 parmak izi, en büyük indirme_id, kod sürümü, not. Görüntü ayrı bir SQLite dosyasıdır (prices kopyası).
GEÇMİŞ: Bu tablolar kurulmadan önceki fiyat sürümleri KORUNMAMIŞTIR ve geri oluşturulamaz. Bugünkü araştırma
veritabanı için ancak bugünkü durumun parmak izi alınabilir.
GERİ DÖNÜŞ: Göç yalnız ekleme yaptığından eski kod yeni sütun ve tabloları yok sayar (prices.update adlı sütunlarla
yazar; indirme_id NULL kalır). Tam geri dönüş: göç öncesi yedek, YALNIZ göçten sonra yeni kullanıcı verisi oluşmadıysa
geri yüklenir; aksi halde ek tablolar yerinde bırakılır (veri kaybı yok)."""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

SURUM = "fiyat_izi_v1"
ALANLAR = ("open", "high", "low", "close", "volume")

SCHEMA = """
CREATE TABLE IF NOT EXISTS fiyat_indirme (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman         TEXT NOT NULL,
    kaynak        TEXT NOT NULL,
    kaynak_surum  TEXT,
    ayarlar_json  TEXT NOT NULL,
    duzeltme      TEXT NOT NULL,
    kod_surum     TEXT,
    hisse_sayisi  INTEGER NOT NULL,
    satir_sayisi  INTEGER NOT NULL,
    degisen_satir INTEGER NOT NULL,
    ozet_sha256   TEXT NOT NULL,
    sema_surum    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fiyat_eski (
    indirme_id INTEGER NOT NULL REFERENCES fiyat_indirme(id),
    ticker TEXT NOT NULL, date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    onceki_indirme_id INTEGER,
    PRIMARY KEY (indirme_id, ticker, date)
);
CREATE TABLE IF NOT EXISTS veri_anlik (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ad           TEXT NOT NULL UNIQUE,
    zaman        TEXT NOT NULL,
    dosya        TEXT NOT NULL,
    satir        INTEGER NOT NULL,
    hisse        INTEGER NOT NULL,
    ilk_tarih    TEXT, son_tarih TEXT,
    ozet_sha256  TEXT NOT NULL,
    indirme_id_azami INTEGER,
    kod_surum    TEXT,
    notlar       TEXT
);
CREATE TRIGGER IF NOT EXISTS fiyat_indirme_guncellenmez BEFORE UPDATE ON fiyat_indirme
BEGIN SELECT RAISE(ABORT, 'fiyat_indirme ekle-yalniz'); END;
CREATE TRIGGER IF NOT EXISTS fiyat_indirme_silinmez BEFORE DELETE ON fiyat_indirme
BEGIN SELECT RAISE(ABORT, 'fiyat_indirme ekle-yalniz'); END;
CREATE TRIGGER IF NOT EXISTS fiyat_eski_guncellenmez BEFORE UPDATE ON fiyat_eski
BEGIN SELECT RAISE(ABORT, 'fiyat_eski ekle-yalniz'); END;
CREATE TRIGGER IF NOT EXISTS fiyat_eski_silinmez BEFORE DELETE ON fiyat_eski
BEGIN SELECT RAISE(ABORT, 'fiyat_eski ekle-yalniz'); END;
CREATE TRIGGER IF NOT EXISTS veri_anlik_guncellenmez BEFORE UPDATE ON veri_anlik
BEGIN SELECT RAISE(ABORT, 'veri_anlik ekle-yalniz'); END;
CREATE TRIGGER IF NOT EXISTS veri_anlik_silinmez BEFORE DELETE ON veri_anlik
BEGIN SELECT RAISE(ABORT, 'veri_anlik ekle-yalniz'); END;
"""


def _iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def kurulu(conn) -> bool:
    t = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    return {"fiyat_indirme", "fiyat_eski", "veri_anlik"} <= t and "indirme_id" in cols


def _parca(v):
    return "" if v is None else repr(round(float(v), 6))


def ozet(satirlar: Iterable) -> str:
    """Kanonik SHA-256: (ticker, date, open, high, low, close, volume) sıralı; sayılar 6 basamağa yuvarlanır."""
    h = hashlib.sha256()
    for r in sorted(satirlar, key=lambda r: (r[0], r[1])):
        h.update(("|".join([r[0], r[1]] + [_parca(x) for x in r[2:7]]) + "\n").encode())
    return h.hexdigest()


def veri_ozeti(conn, bas: Optional[str] = None, son: Optional[str] = None) -> Dict:
    q = "SELECT ticker, date, open, high, low, close, volume FROM prices WHERE close IS NOT NULL"
    a = []
    if bas:
        q += " AND date>=?"
        a.append(bas)
    if son:
        q += " AND date<=?"
        a.append(son)
    rows = conn.execute(q, a).fetchall()
    return {"satir": len(rows), "hisse": len({r[0] for r in rows}), "ilk_tarih": min((r[1] for r in rows), default=None),
            "son_tarih": max((r[1] for r in rows), default=None), "ozet_sha256": ozet(tuple(r) for r in rows)}


def migrate(conn, path) -> Dict:
    """Yedek (sqlite backup) → integrity_check → tek işlemde ekleme. Yedek alınamaz/bozuksa göç YAPILMAZ."""
    if kurulu(conn):
        return {"durum": "var", "yedek": None}
    yedek = None
    try:                                   # O4: fiyat verisi yoksa (yeni kurulum) korunacak bir şey yok, yedek gereksiz
        dolu = conn.execute("SELECT 1 FROM prices LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        dolu = True
    if dolu and path is not None and str(path) != ":memory:":
        p = Path(path)
        ydir = p.parent / "yedek"
        ydir.mkdir(parents=True, exist_ok=True)
        yedek = ydir / f"{p.stem}_{datetime.now():%Y%m%d_%H%M%S}_fiyat_izi_oncesi.db"
        conn.commit()
        dst = sqlite3.connect(yedek)
        try:
            conn.backup(dst)
            chk = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
        if chk != "ok":
            return {"durum": "yedek_bozuk", "yedek": str(yedek), "hata": chk}
    try:
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")        # O4: panel ve okuyucu aynı anda açılırsa göç tek kez yapılır
        if kurulu(conn):
            conn.execute("COMMIT")
            return {"durum": "var", "yedek": str(yedek) if yedek else None}
        for stmt in _ifadeler(SCHEMA):
            conn.execute(stmt)
        if "indirme_id" not in {r[1] for r in conn.execute("PRAGMA table_info(prices)")}:
            conn.execute("ALTER TABLE prices ADD COLUMN indirme_id INTEGER")
        conn.execute("COMMIT")
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return {"durum": "goc_hatasi", "yedek": str(yedek) if yedek else None, "hata": str(e)[:200]}
    return {"durum": "kuruldu", "yedek": str(yedek) if yedek else None, "sema": SURUM}


def _ifadeler(script: str) -> List[str]:
    out, buf = [], ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    return out


def yaz(conn, satirlar: List[tuple], kaynak: str, ayarlar: Dict, duzeltme: str, kaynak_surum: Optional[str] = None,
        kod_surum: Optional[str] = None) -> int:
    """satirlar: (ticker, date, open, high, low, close, volume). Önce indirme kaydı, sonra her satır: mevcut satır
    farklıysa eskisi fiyat_eski'ye yazılır; satır indirme_id ile yazılır. Tek işlem. Dönüş: indirme id."""
    if not kurulu(conn):
        raise RuntimeError("fiyat_izi kurulmamış (migrate gerekli)")
    conn.commit()
    conn.execute("BEGIN")
    try:
        mevcut = {}
        for tk in {r[0] for r in satirlar}:
            for r in conn.execute("SELECT ticker, date, open, high, low, close, volume, indirme_id FROM prices "
                                  "WHERE ticker=?", (tk,)):
                mevcut[(r[0], r[1])] = tuple(r)
        degisen = [(k, v) for k, v in ((r[:2], r) for r in satirlar) if k in mevcut and
                   [_parca(x) for x in mevcut[k][2:7]] != [_parca(x) for x in v[2:7]]]
        cur = conn.execute(
            "INSERT INTO fiyat_indirme(zaman,kaynak,kaynak_surum,ayarlar_json,duzeltme,kod_surum,hisse_sayisi,"
            "satir_sayisi,degisen_satir,ozet_sha256,sema_surum) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (_iso(), kaynak, kaynak_surum, json.dumps(ayarlar, ensure_ascii=False, sort_keys=True), duzeltme, kod_surum,
             len({r[0] for r in satirlar}), len(satirlar), len(degisen), ozet(satirlar), SURUM))
        iid = cur.lastrowid
        for k, _ in degisen:
            e = mevcut[k]
            conn.execute("INSERT INTO fiyat_eski(indirme_id,ticker,date,open,high,low,close,volume,onceki_indirme_id) "
                         "VALUES(?,?,?,?,?,?,?,?,?)", (iid, *e[:7], e[7]))
        degisen_k = {k for k, _ in degisen}
        for r in satirlar:                     # yalnız YENİ ya da DEĞİŞEN satır yazılır: indirme_id = değeri koyan indirme
            if r[:2] in mevcut and r[:2] not in degisen_k:
                continue
            conn.execute("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume,indirme_id) "
                         "VALUES(?,?,?,?,?,?,?,?)", (*r, iid))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return iid


def durum_once(conn, indirme_id: int) -> Dict[tuple, tuple]:
    """indirme_id ÇALIŞMADAN ÖNCEKİ fiyat durumu (yalnız izleme kurulduktan sonraki değişiklikler geri alınabilir):
    bugünkü satırlar; indirme_id ≥ verilen olanlar fiyat_eski'deki en erken eski değere döndürülür; o indirmelerle
    İLK kez eklenmiş (eskisi olmayan) satırlar çıkarılır."""
    simdi = {(r[0], r[1]): tuple(r[2:8]) for r in conn.execute(
        "SELECT ticker, date, open, high, low, close, volume, indirme_id FROM prices")}
    eski = {}
    for r in conn.execute("SELECT ticker, date, open, high, low, close, volume, onceki_indirme_id, indirme_id "
                          "FROM fiyat_eski WHERE indirme_id>=? ORDER BY indirme_id DESC", (indirme_id,)):
        eski[(r[0], r[1])] = tuple(r[2:8])                 # azalan sıra: en erken değişikliğin eskisi kalır
    out = {}
    for k, v in simdi.items():
        if v[5] is not None and v[5] >= indirme_id:
            if k in eski:
                out[k] = eski[k]
            continue
        out[k] = v
    return out


def anlik_goruntu(conn, hedef: Path, ad: str, kod_surum: Optional[str] = None, notlar: str = "") -> Dict:
    """prices tablosunun ayrı SQLite dosyasına kopyası + parmak izi; kayıt veri_anlik'e eklenir."""
    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    o = veri_ozeti(conn)
    d = sqlite3.connect(hedef)
    try:
        d.execute("CREATE TABLE prices (ticker TEXT NOT NULL, date TEXT NOT NULL, close REAL, volume REAL, open REAL, "
                  "high REAL, low REAL, indirme_id INTEGER, PRIMARY KEY (ticker, date))")
        d.executemany("INSERT INTO prices(ticker,date,open,high,low,close,volume,indirme_id) VALUES(?,?,?,?,?,?,?,?)",
                      conn.execute("SELECT ticker, date, open, high, low, close, volume, indirme_id FROM prices"))
        d.commit()
        o2 = veri_ozeti(d)
    finally:
        d.close()
    if o2["ozet_sha256"] != o["ozet_sha256"]:
        raise RuntimeError("anlık görüntü parmak izi kaynakla uyuşmuyor")
    azami = conn.execute("SELECT MAX(indirme_id) FROM prices").fetchone()[0]
    conn.execute("INSERT INTO veri_anlik(ad,zaman,dosya,satir,hisse,ilk_tarih,son_tarih,ozet_sha256,indirme_id_azami,"
                 "kod_surum,notlar) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 (ad, _iso(), str(hedef), o["satir"], o["hisse"], o["ilk_tarih"], o["son_tarih"], o["ozet_sha256"],
                  azami, kod_surum, notlar))
    conn.commit()
    return dict(o, dosya=str(hedef), indirme_id_azami=azami)
