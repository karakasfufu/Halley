"""O3 düzeltmesi (16.11.2026): ücretli yapay zekâ çağrıları için süreçler arası güvenli MALİYET REZERVASYONU.
Tasarım, geçmiş veri pilotunun (backtest.PilotLLM) zaten kullandığı muhafazakâr yöntemin üretime taşınmasıdır.

Her HTTP denemesinden ÖNCE bir rezervasyon yapılır:
  üst sınır = (UTF-8 bayt(sistem + kullanıcı mesajı + JSON şeması) + 4096) × girdi fiyatı + MAX_CIKTI × çıktı fiyatı
  - bir token en az bir bayttır (bayt tabanlı BPE) → girdi tokenı ≤ bayt sayısı; 4096 mesaj/biçim payı
  - çıktı (düşünme tokenları dahil) API'de max_completion_tokens = MAX_CIKTI ile sınırlıdır
  - istemci iç yeniden denemesi kapalıdır (max_retries=0); kod içindeki her yeni deneme AYRI rezervasyondur
Kalan GÜNLÜK ya da AYLIK bütçe (daha kısıtlayıcı olan) bu rezervasyonu karşılamıyorsa çağrı BAŞLATILMAZ
(ButceYetersiz). Rezervasyon `BEGIN IMMEDIATE` ile yazılır: aynı veritabanını kullanan süreçler ve iş parçacıkları
aynı bütçeyi iki kez harcayamaz.
Sonuç: başarılı çağrıda gerçek maliyet (kullanım tokenları) yazılır. Hata, zaman aşımı, kullanım bilgisi yokluğu ya da
süreç kapanmasında rezervasyon 'belirsiz' / 'acik' kalır ve TAM tutarıyla harcanmış sayılır (sıfır sayılmaz).
KESİNLİK SINIRI: üst sınır, fiyat varsayımı (pipeline.INPUT/OUTPUT_USD_PER_TOKEN; gpt-5-mini 0,25 / 2,00 $ / 1M token)
ve bayt ≥ token ilişkisi doğruysa geçerlidir. OpenAI fiyatı değişirse ya da faturalama farklıysa garanti DEĞİLDİR;
arayüz kesin bütçe garantisi vermez.
İŞ ZARFI: bir haber analizinin (ön eleme + tam analiz + kalite profilindeki ikinci görüş + bilinmeyen parametre
yüzünden olası yeniden denemeler) toplam muhafazakâr üst sınırı, iş BAŞLAMADAN tek seferde ayrılır (zarf_ac). Bütçe
zarfı karşılamıyorsa iş hiç başlatılmaz. İşin çağrıları zarftan düşer; zarfı aşacak bir çağrı yapılmaz. İş bitince
zarfın kullanılmayan kısmı serbest kalır (zarf_kapat); süreç kapanırsa zarf açık kalır ve harcanmış sayılır.
Kategoriler: 'haber' (haber analizi, derin inceleme, ucuz test; bütçe haber_butce_usd + günlük sınır) ve
'yz_yorum' (rapor yorumu, kaçırılan açıklaması; bütçe yz_butce_usd). Geçmiş veri pilotu kendi 1 $ defteriyle ayrıdır."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from . import config

MAX_CIKTI = 16000               # canlıda gözlenen en büyük çıktı haber başına 14.334 (iki çağrı); çağrı başına sınır
GIRDI_PAYI = 4096

SCHEMA = """
CREATE TABLE IF NOT EXISTS harcama_rezervasyon (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman        TEXT NOT NULL,
    gun          TEXT NOT NULL,
    ay           TEXT NOT NULL,
    kategori     TEXT NOT NULL,          -- haber | yz_yorum
    modul        TEXT,
    islem        TEXT,
    ref          TEXT,
    durum        TEXT NOT NULL,          -- acik | tamam | belirsiz | zarf_acik | zarf_kapali
    zarf_id      INTEGER,                -- bu çağrının düştüğü iş zarfı (yoksa doğrudan bütçeden)
    rezerve_usd  REAL NOT NULL,
    gercek_usd   REAL,
    kayda_gecti  INTEGER NOT NULL DEFAULT 0,  -- maliyet analyses / ai_comments kaydına yansıdı mı (çift sayım yok)
    pid          INTEGER,
    hata         TEXT,
    kapanis      TEXT
);
CREATE INDEX IF NOT EXISTS ix_harcama_rez_ay ON harcama_rezervasyon(kategori, ay);
"""


class ButceYetersiz(Exception):
    pass


class ButceKorumasiYok(Exception):
    pass


@dataclass
class Butce:
    kategori: str
    db_path: str
    aylik_usd: Optional[float]
    gunluk_usd: Optional[float] = None


def fiyat():
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    return INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN


def cagri_ust_sinir(system: str, user: str, schema=None, ek_bayt: int = 0) -> float:
    """Tek HTTP denemesinin muhafazakâr üst sınırı. ek_bayt: henüz bilinmeyen metin için ayrılan bayt (karakter × 4)."""
    inp, out = fiyat()
    sema = ""
    if schema is not None:
        try:
            sema = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        except Exception:
            sema = str(schema)
    bayt = len((system or "").encode("utf-8")) + len((user or "").encode("utf-8")) + len(sema.encode("utf-8")) + ek_bayt
    return (bayt + GIRDI_PAYI) * inp + MAX_CIKTI * out


def tablo(conn) -> None:
    conn.executescript(SCHEMA)


def _tablo_var(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='harcama_rezervasyon'").fetchone() \
        is not None


def _kayitli_harcama(conn, kategori: str, ay: str, gun: Optional[str]) -> float:
    """Kalıcı kayıtlarda (analyses / ai_comments) görünen gerçek harcama."""
    inp, out = fiyat()
    if kategori == "haber":
        q = "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM analyses WHERE substr(created_at,1,%d)=?"
        r = conn.execute(q % (10 if gun else 7), (gun or ay,)).fetchone()
        o = conn.execute("SELECT COALESCE(SUM(eski_input_tokens),0), COALESCE(SUM(eski_output_tokens),0) FROM reanalysis_log "
                         + ("WHERE durum='tamam' AND substr(created_at,1,10)=?" if gun else "WHERE durum='tamam' AND eski_ay=?"),
                         (gun or ay,)).fetchone()
        return (r[0] + o[0]) * inp + (r[1] + o[1]) * out
    if kategori == "yz_yorum":
        r = conn.execute("SELECT COALESCE(SUM(usd),0) FROM ai_comments WHERE substr(created_at,1,%d)=?" % (10 if gun else 7),
                         (gun or ay,)).fetchone()
        return float(r[0] or 0)
    raise ValueError(kategori)


def harcanan(conn, kategori: str, simdi: Optional[datetime] = None) -> Dict:
    """Ay ve gün için harcanmış sayılan: kalıcı kayıt + kayda geçmemiş gerçek + AÇIK / BELİRSİZ rezervasyonların tamamı
    + açık iş zarflarının henüz çağrıya dönüşmemiş kısmı. Okuma tabloyu OLUŞTURMAZ (salt-okur panel)."""
    simdi = simdi or datetime.now(config.TR_TZ)
    ay, gun = simdi.strftime("%Y-%m"), simdi.date().isoformat()
    var = _tablo_var(conn)
    out = {}
    for ad, alan, deger in (("ay", "ay", ay), ("gun", "gun", gun)):
        kayitli = _kayitli_harcama(conn, kategori, ay, gun if ad == "gun" else None)
        r = (0.0, 0.0, 0, 0, 0.0)
        if var:
            r = conn.execute(
                f"SELECT COALESCE(SUM(CASE WHEN durum='tamam' AND kayda_gecti=0 THEN gercek_usd ELSE 0 END),0), "
                f"COALESCE(SUM(CASE WHEN durum IN ('acik','belirsiz') THEN rezerve_usd ELSE 0 END),0), "
                f"COALESCE(SUM(durum='belirsiz'),0), COALESCE(SUM(durum IN ('acik','zarf_acik')),0), "
                f"COALESCE((SELECT SUM(MAX(0, z.rezerve_usd - COALESCE((SELECT SUM(c.rezerve_usd) FROM harcama_rezervasyon c "
                f"WHERE c.zarf_id=z.id),0))) FROM harcama_rezervasyon z WHERE z.durum='zarf_acik' AND z.kategori=? "
                f"AND z.{alan}=?),0) "
                f"FROM harcama_rezervasyon WHERE kategori=? AND {alan}=?", (kategori, deger, kategori, deger)).fetchone()
        out[ad] = {"kayitli": kayitli, "kayda_gecmemis": r[0], "rezerve": r[1] + r[4], "belirsiz_adet": r[2],
                   "acik_adet": r[3], "toplam": kayitli + r[0] + r[1] + r[4]}
    return out


def kalan(conn, b: Butce, simdi: Optional[datetime] = None) -> Dict:
    h = harcanan(conn, b.kategori, simdi)
    ak = None if b.aylik_usd is None else b.aylik_usd - h["ay"]["toplam"]
    gk = None if b.gunluk_usd is None else b.gunluk_usd - h["gun"]["toplam"]
    adaylar = [x for x in (ak, gk) if x is not None]
    if not adaylar:
        raise ButceKorumasiYok("bütçe tanımlı değil")
    k = min(adaylar)
    return {"aylik_kalan": ak, "gunluk_kalan": gk, "kalan": k,
            "sinirlayan": "günlük" if gk is not None and (ak is None or gk <= ak) else "aylık", "harcanan": h}


_YEREL = threading.local()


def aktif_zarf() -> Optional[int]:
    return getattr(_YEREL, "zarf", None)


@contextmanager
def zarf_icinde(zarf_id: Optional[int], db_path: Optional[str]):
    """Bu iş parçacığındaki çağrılar verilen zarftan düşsün; çıkışta zarf kapanır (kullanılmayan kısım serbest)."""
    onceki = aktif_zarf()
    _YEREL.zarf = zarf_id
    try:
        yield
    finally:
        _YEREL.zarf = onceki
        if zarf_id is not None and db_path:
            zarf_kapat(db_path, zarf_id)


def zarf_ac(b: Butce, ust_usd: float, modul: str = "", islem: str = "is_zarfi", ref: str = "") -> int:
    """İşin toplam üst sınırını atomik ayırır. Karşılanmıyorsa ButceYetersiz: iş başlatılmaz."""
    return rezerve(b, ust_usd, modul, islem, ref, _zarf=True)


def zarf_kapat(db_path: str, zarf_id: int) -> None:
    c = sqlite3.connect(db_path, timeout=30)
    try:
        c.execute("UPDATE harcama_rezervasyon SET durum='zarf_kapali', kapanis=? WHERE id=? AND durum='zarf_acik'",
                  (datetime.now(config.TR_TZ).isoformat(timespec="seconds"), zarf_id))
        c.commit()
    finally:
        c.close()


def rezerve(b: Butce, ust_usd: float, modul: str = "", islem: str = "", ref: str = "",
            zarf_id: Optional[int] = None, _zarf: bool = False) -> int:
    """Atomik rezervasyon. Karşılanmıyorsa ButceYetersiz (çağrı yapılmaz). zarf_id verilirse çağrı o iş zarfından
    düşer (zarfın kalanı yetmiyorsa ButceYetersiz; bütçeye ikinci kez yazılmaz)."""
    c = sqlite3.connect(b.db_path, timeout=30, isolation_level=None)
    try:
        tablo(c)
        c.execute("BEGIN IMMEDIATE")
        try:
            if zarf_id is not None:
                z = c.execute("SELECT rezerve_usd, durum FROM harcama_rezervasyon WHERE id=?", (zarf_id,)).fetchone()
                if z is None or z[1] != "zarf_acik":
                    raise ButceYetersiz("iş zarfı açık değil")
                kullanilan = c.execute("SELECT COALESCE(SUM(rezerve_usd),0) FROM harcama_rezervasyon WHERE zarf_id=?",
                                       (zarf_id,)).fetchone()[0]
                if ust_usd > z[0] - kullanilan + 1e-12:
                    raise ButceYetersiz(f"çağrı iş zarfını aşıyor ({ust_usd:.4f} $ > kalan {z[0] - kullanilan:.4f} $)")
            else:
                k = kalan(c, b)
                if ust_usd > k["kalan"] + 1e-12:
                    raise ButceYetersiz(f"{k['sinirlayan']} bütçe bu {'işin' if _zarf else 'çağrının'} muhafazakâr üst "
                                        f"sınırını ({ust_usd:.4f} $) karşılamıyor (kalan {max(k['kalan'], 0):.4f} $)")
            simdi = datetime.now(config.TR_TZ)
            cur = c.execute("INSERT INTO harcama_rezervasyon(zaman,gun,ay,kategori,modul,islem,ref,durum,rezerve_usd,pid,"
                            "zarf_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (simdi.isoformat(timespec="seconds"), simdi.date().isoformat(), simdi.strftime("%Y-%m"),
                             b.kategori, modul, islem, ref, "zarf_acik" if _zarf else "acik", ust_usd, os.getpid(),
                             zarf_id))
            c.execute("COMMIT")
            return cur.lastrowid
        except Exception:
            c.execute("ROLLBACK")
            raise
    finally:
        c.close()


def _guncelle(db_path: str, rid: int, **alan) -> None:
    c = sqlite3.connect(db_path, timeout=30)
    try:
        sets = ", ".join(f"{k}=?" for k in alan)
        c.execute(f"UPDATE harcama_rezervasyon SET {sets}, kapanis=? WHERE id=?",
                  (*alan.values(), datetime.now(config.TR_TZ).isoformat(timespec="seconds"), rid))
        c.commit()
    finally:
        c.close()


def tamamla(db_path: str, rid: int, gercek_usd: float) -> None:
    _guncelle(db_path, rid, durum="tamam", gercek_usd=gercek_usd)


def belirsiz(db_path: str, rid: int, hata: str = "") -> None:
    """Maliyet bilinmiyor: rezervasyonun TAMAMI harcanmış sayılır."""
    _guncelle(db_path, rid, durum="belirsiz", hata=(hata or "")[:300])


def son_rezervasyon() -> Optional[int]:
    """Bu iş parçacığında son yapılan çağrı rezervasyonu (tek çağrılı yollar için: yz yorumu)."""
    return getattr(_YEREL, "son_rid", None)


def kayda_gecti(conn, zarf_id: Optional[int] = None, rid: Optional[int] = None) -> None:
    """Maliyeti kalıcı kayda (analyses / ai_comments) yansıyan TAMAM rezervasyonlar çift sayılmasın. Yalnız BU işin
    çağrıları (zarf_id) ya da tek çağrı (rid) işaretlenir; aynı haberin eski, kayda geçmemiş maliyetleri sayılmaya devam
    eder. Belirsiz rezervasyonlar hiçbir zaman düşülmez."""
    if not _tablo_var(conn) or (zarf_id is None and rid is None):
        return
    if zarf_id is not None:
        conn.execute("UPDATE harcama_rezervasyon SET kayda_gecti=1 WHERE zarf_id=? AND durum='tamam'", (zarf_id,))
    if rid is not None:
        conn.execute("UPDATE harcama_rezervasyon SET kayda_gecti=1 WHERE id=? AND durum='tamam'", (rid,))
    conn.commit()


def db_yolu(conn) -> Optional[str]:
    r = conn.execute("PRAGMA database_list").fetchone()
    return r[2] if r and r[2] else None


def uretim_butcesi(conn, kategori: str = "haber", aylik_usd: Optional[float] = None,
                   gunluk_usd: Optional[float] = None) -> Butce:
    """Üretim bütçesi: parametre verilmezse Ayarlar'dan (haber: aylık + günlük; yz_yorum: aylık). Bellek içi
    veritabanında rezervasyon yapılamaz → ButceKorumasiYok (sessizce sınırsız olmaz)."""
    from . import pipeline
    yol = db_yolu(conn)
    if not yol:
        raise ButceKorumasiYok("rezervasyon için dosya veritabanı gerekir")
    if kategori == "haber":
        from . import haber_kapsam
        return Butce("haber", yol, pipeline.news_budget() if aylik_usd is None else aylik_usd,
                     haber_kapsam.gunluk_butce() if gunluk_usd is None else gunluk_usd)
    from . import ai_comment
    return Butce("yz_yorum", yol, ai_comment.budget(pipeline.load_settings()) if aylik_usd is None else aylik_usd,
                 gunluk_usd)
