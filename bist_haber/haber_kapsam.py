"""O3 (16.11.2026): haber analizi KAPSAMI, BÜTÇE, KİLİT ve GÜNCELLİK göstergesi. Yapay zekâ çağırmaz.

KAPSAM: varsayılan analiz kapsamı son İKİ BIST işlem günüdür: bugün işlem günüyse bugün + önceki işlem günü, değilse
  (hafta sonu / tatil) son iki işlem günü; başlangıç o iki günden ilkinin 00:00'ı (TR). Aradaki hafta sonu / tatil
  günlerinde yayımlanan haberler de kapsama girer. Yarım günler (arefe) işlem günüdür.
  Takvim kaynağı: bist_haber.market_calendar (2026: Midas destek sayfası ve hisse.net; 2027: yalnız yasayla sabit milli
  tatiller — dini bayramlar borsa açıklayınca eklenecek). Bilinen takvimin dışındaki günlerde uyarı döner.
  Kapsam dışı (eski) haberler SİLİNMEZ, analiz edilmiş SAYILMAZ; panelde ayrıca sayılır. Geçmişe dönük analiz yalnız
  kullanıcının panelde kendi seçimiyle yapılır ve sonucu 'sonradan_analiz' olarak işaretlenir (geçmiş tahminlere
  eklenmez: tahmin defteri ve hazır fırsat tahmin anındaki haber puanını dondurur).
BÜTÇE: aylık bütçe (Ayarlar 'haber_butce_usd') ve günlük sınır ('haber_gunluk_butce_usd', varsayılan 0,50 $) birlikte;
  DAHA KISITLAYICI olan geçerlidir. Gerçekleşen harcama kayıtlı tokenlardan; tahmin üst sınırdan (ayrı raporlanır).
KİLİT: aynı anda tek haber analizi (süreçler ve iş parçacıkları arası dosya kilidi): tekrar tıklama, Streamlit yeniden
  çalışması ya da ikinci sekme mükerrer çağrı / bütçe aşımı üretemez."""
import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from . import config, market_calendar as mc

GUNLUK_BUTCE_VARSAYILAN = 0.50
KAPSAM_IS_GUNU = 2
KILIT_YOLU = config.DATA / "haber_analiz.kilit"
KILIT_BAYAT_SN = 2 * 3600
_IP_KILIDI = threading.Lock()


class AnalizSuruyor(Exception):
    pass


# ---------------------------------------------------------------- kapsam (BIST işlem günleri)
def kapsam_baslangici(simdi: Optional[datetime] = None, is_gunu: int = KAPSAM_IS_GUNU) -> Dict:
    simdi = simdi or datetime.now(config.TR_TZ)
    d = simdi.date()
    gunler = []
    while len(gunler) < is_gunu:
        if mc.is_trading_day(d):
            gunler.append(d)
        d -= timedelta(days=1)
    bas = datetime.combine(gunler[-1], datetime.min.time(), tzinfo=config.TR_TZ)
    uyari = None
    if simdi.date().isoformat() > mc.RELIGIOUS_KNOWN_UNTIL:
        uyari = (f"BIST takvimi {mc.RELIGIOUS_KNOWN_UNTIL} sonrası için dini bayram kapanışlarını içermiyor; kapsam "
                 "günleri yanlış olabilir (market_calendar güncellenmeli).")
    return {"baslangic": bas, "baslangic_iso": bas.isoformat(timespec="seconds"),
            "is_gunleri": [g.isoformat() for g in reversed(gunler)],
            "yarim_gun": [g.isoformat() for g in gunler if g.isoformat() in mc.HALF_DAYS],
            "kaynak": "bist_haber.market_calendar (Midas + hisse.net 2026; 2027 yalnız sabit milli tatiller)",
            "uyari": uyari}


# ---------------------------------------------------------------- bütçe
def gun_harcamasi(conn, simdi: Optional[datetime] = None) -> float:
    """Bugün (TR) haber analizine GERÇEKLEŞEN harcama (kayıtlı token × fiyat). Derin yeniden incelemede yerine yazılan
    eski analizin maliyeti de, o inceleme bugün yapıldıysa, muhafazakâr olarak bugüne sayılır."""
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    g = (simdi or datetime.now(config.TR_TZ)).date().isoformat()
    r = conn.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM analyses "
                     "WHERE substr(created_at,1,10)=?", (g,)).fetchone()
    o = conn.execute("SELECT COALESCE(SUM(eski_input_tokens),0), COALESCE(SUM(eski_output_tokens),0) FROM reanalysis_log "
                     "WHERE durum='tamam' AND substr(created_at,1,10)=?", (g,)).fetchone()
    return (r[0] + o[0]) * INPUT_USD_PER_TOKEN + (r[1] + o[1]) * OUTPUT_USD_PER_TOKEN


def gunluk_butce() -> float:
    from .pipeline import load_settings
    try:
        return max(0.0, float(load_settings().get("haber_gunluk_butce_usd", GUNLUK_BUTCE_VARSAYILAN)))
    except (TypeError, ValueError):
        return GUNLUK_BUTCE_VARSAYILAN


def butce_durumu(conn, aylik_usd: Optional[float], gunluk_usd: Optional[float] = None,
                 simdi: Optional[datetime] = None) -> Dict:
    """Kalan bütçe: aylık ve günlük kalanın KÜÇÜĞÜ. aylik_usd None ise sınırsız (test / pilot yolu)."""
    from . import harcama
    if aylik_usd is None:
        return {"kalan": None, "sinirlayan": None}
    gunluk = gunluk_butce() if gunluk_usd is None else gunluk_usd
    h = harcama.harcanan(conn, "haber", simdi)      # kayıtlı + kayda geçmemiş + açık / belirsiz rezervasyonlar
    ay, gun = h["ay"]["toplam"], h["gun"]["toplam"]
    ak, gk = aylik_usd - ay, gunluk - gun
    return {"aylik_butce": aylik_usd, "gunluk_butce": gunluk, "ay_gerceklesen": round(ay, 4), "gun_gerceklesen": round(gun, 4),
            "aylik_kalan": round(ak, 4), "gunluk_kalan": round(gk, 4), "kalan": min(ak, gk),
            "sinirlayan": "günlük" if gk <= ak else "aylık",
            "rezerve_gun": round(h["gun"]["rezerve"], 4), "belirsiz_adet": h["ay"]["belirsiz_adet"],
            "acik_adet": h["ay"]["acik_adet"]}


# ---------------------------------------------------------------- kilit
@contextmanager
def analiz_kilidi(yol: Optional[Path] = None):
    """Süreçler arası tek analiz. Kilit alınamazsa AnalizSuruyor. KILIT_BAYAT_SN'den eski kilit (çökmüş süreç) temizlenir."""
    yol = Path(yol or KILIT_YOLU)
    if not _IP_KILIDI.acquire(blocking=False):
        raise AnalizSuruyor("bu uygulamada başka bir haber analizi sürüyor")
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(yol), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                yas = time.time() - yol.stat().st_mtime
            except FileNotFoundError:
                yas = 0
            if yas <= KILIT_BAYAT_SN:
                raise AnalizSuruyor("başka bir haber analizi sürüyor (kilit dosyası var)")
            yol.unlink(missing_ok=True)
            fd = os.open(str(yol), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "zaman": datetime.now(config.TR_TZ).isoformat(timespec="seconds")}, f)
        try:
            yield
        finally:
            try:
                yol.unlink()
            except FileNotFoundError:
                pass
    finally:
        _IP_KILIDI.release()


def kilitli_mi(yol: Optional[Path] = None) -> bool:
    yol = Path(yol or KILIT_YOLU)
    return yol.exists() and time.time() - yol.stat().st_mtime <= KILIT_BAYAT_SN


# ---------------------------------------------------------------- güncellik göstergesi
def guncellik(conn, simdi: Optional[datetime] = None) -> Dict:
    """Panel göstergesi. Toplama ile analiz AYRI: yeni toplanan haber analiz edilmiş sayılmaz. Kapsamda analiz bekleyen
    haber yoksa son analiz zamanı eski diye 'bayat' denmez."""
    simdi = simdi or datetime.now(config.TR_TZ)
    k = kapsam_baslangici(simdi)
    bas = k["baslangic_iso"]
    hazir = "body IS NOT NULL AND TRIM(body)!=''"
    one = lambda q, a=(): conn.execute(q, a).fetchone()[0]
    son_toplama = max([x for x in (one("SELECT MAX(fetched_at) FROM news"),
                                   one("SELECT MAX(listed_at) FROM kap_coverage")) if x] or [None])
    out = {"kapsam": k,
           "son_toplama": son_toplama,
           "son_basarili_analiz": one("SELECT MAX(created_at) FROM analyses"),
           "bekleyen_kapsamda": one(f"SELECT COUNT(*) FROM news WHERE status='new' AND {hazir} AND published_at>=?", (bas,)),
           "kapsam_disi_eski": one(f"SELECT COUNT(*) FROM news WHERE status='new' AND {hazir} AND published_at<?", (bas,)),
           "metinsiz_kapsamda": one("SELECT COUNT(*) FROM news WHERE status='new' AND (body IS NULL OR TRIM(body)='') "
                                    "AND published_at>=?", (bas,)),
           "metinsiz_eski": one("SELECT COUNT(*) FROM news WHERE status='new' AND (body IS NULL OR TRIM(body)='') "
                                "AND published_at<?", (bas,)),
           "son_haberli_liste": one("SELECT MAX(olusturuldu) FROM hazir_firsat WHERE kaynak='haber'"),
           "analiz_suruyor": kilitli_mi()}
    # O3 düzeltmesi (16.11.2026): güncellik ile kapsam eksikliği AYRI. Tam "güncel" ancak (1) kapsamdaki her günün KAP
    # listesi eksiksiz alınmış, (2) analiz bekleyen güncel haber yok, (3) metni alınamamış güncel haber yok ve
    # (4) takvim bu günler için doğrulanmışsa denir. Aksi halde her eksik ayrı yazılır.
    from .kap import coverage_gaps
    bugun = simdi.date()
    try:
        bosluk = [g.isoformat() for g in coverage_gaps(conn, k["baslangic"].date(), bugun, bugun)]
    except Exception:
        bosluk = ["(okunamadı)"]
    out["toplama_bosluk_gunleri"] = bosluk
    eksikler = []
    if bosluk or not son_toplama:
        eksikler.append(("toplama eksik", "KAP listesi şu günler için hiç alınmamış ya da gün bitmeden alınıp "
                         f"yenilenmemiş: {', '.join(bosluk) or 'tüm kapsam'} — bu günlerin haberleri eksik olabilir "
                         "(\"Haberleri güncelle\" ile toplanır; toplama ücretsizdir)"))
    if out["bekleyen_kapsamda"]:
        eksikler.append(("analiz bekliyor", f"{out['bekleyen_kapsamda']} güncel haber henüz analiz edilmedi: haberli fırsat "
                         "listesi ve haber puanı bu haberleri İÇERMİYOR"))
    if out["metinsiz_kapsamda"]:
        eksikler.append(("kapsam eksik", f"{out['metinsiz_kapsamda']} güncel haberin metni alınamadı: analiz edilemedi, "
                         "haberli fırsat listesi ve haber puanı bu haberleri İÇERMİYOR (arka plan okuyucu yeniden dener)"))
    if k.get("uyari"):
        eksikler.append(("takvim doğrulanmadı", k["uyari"]))
    out["eksikler"] = [ad for ad, _ in eksikler]
    out["tam_guncel"] = not eksikler
    if eksikler:
        out["durum"] = eksikler[0][0] + ": " + eksikler[0][1]
        out["seviye"] = "uyari"
        if len(eksikler) > 1:
            out["not"] = " · ".join(f"{ad}: {ac}" for ad, ac in eksikler[1:])
    else:
        out["durum"], out["seviye"] = (f"güncel: kapsamdaki (son iki işlem günü) KAP listeleri eksiksiz (son alım "
                                       f"{(son_toplama or '')[11:16]}), analiz bekleyen ya da metni eksik güncel haber "
                                       "yok"), "tamam"
    return out
