"""Eksik KAP sayfalarını arka planda, KAP sınırına göre bekleyip TAMAMLANANA KADAR okuyan işçi (2026-11-07).

Kullanıcı isteği: "Eksik kalan sayfa olursa otomatik yeniden okumaya çalışsın; kullanıcı dakika sayıp tekrar
denemesin; olay özetini bildirip tamamlanana kadar devam etsin (100'den fazla okunacaksa)." KAP yaklaşık 100 istekten
sonra geçici sınır uyguluyor (2026-11-07 gözlemi: iki turda 100 ve 99 sayfa).

Ne yapar: takvim bildirimlerinin (status='context') ve günlük güncellemede metni alınamamış haberlerin
(status='new', metin yok) sayfalarını okur. YAPAY ZEKÂ ÇAĞIRMAZ, kredi harcamaz; analiz yine "Haberleri güncelle" ile
yapılır. KAP bekleme süresi (1,5 sn) korunur. Sınır gelirse 3 → 5 → 10 dk bekleyip devam eder; en fazla 4 saat.
İlerleme olmayan (sınır da gelmeyen) turda durur: o sayfalar bu sefer okunamıyor demektir. Durum data/kap_okuyucu.json
dosyasındadır; panel buradan canlı gösterir. Aynı anda tek işçi çalışır.
"""
import json
import threading
import time
from datetime import date, datetime
from typing import Callable, Dict, Optional

from . import config, corp_events, db, kap, kap_history, market_calendar

WAITS_MIN = (3, 5, 10)
MAX_HOURS = 4.0
AUTO_START_MIN_PAGES = 100   # kullanıcı: "100'den fazla okunabilecekse" — ya da önceki tur KAP sınırına takıldıysa
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


def state_file():
    return config.DATA / "kap_okuyucu.json"


def load() -> Dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


STALE_MIN = 5   # canlılık zamanı bundan eskiyse (ve bekleme süresi geçtiyse) çalışan okuyucu yok sayılır


def _save(st: Dict) -> None:
    st["nabiz"] = datetime.now(config.TR_TZ).isoformat(timespec="seconds")  # başka işlemler için canlılık işareti
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def pending_counts(conn) -> Dict[str, int]:
    ctx = conn.execute("SELECT COUNT(*) FROM news WHERE status='context' AND body IS NULL AND subject IN (%s)"
                       % ",".join("?" * len(corp_events.SUBJECTS)), corp_events.SUBJECTS).fetchone()[0]
    new = conn.execute("SELECT COUNT(*) FROM news WHERE source='kap' AND status='new' AND body IS NULL").fetchone()[0]
    return {"takvim": ctx, "haber": new, "toplam": ctx + new}


def event_summary(conn, today: Optional[date] = None, days: int = 15) -> Dict:
    """Tamamlanınca bildirilecek özet: önümüzdeki işlem günlerindeki şirket olayları."""
    today = today or datetime.now(config.TR_TZ).date()
    tickers = [r[0] for r in conn.execute("SELECT DISTINCT ticker FROM companies")]
    evs = [(t, e) for t in tickers for e in corp_events.upcoming(conn, t, today, days)["yaklasan"]]
    # Fiyatı doğrudan etkileyenler (bedelsiz/bedelli düzeltme, temettü hak kullanımı) önce, sonra genel kurul; tarihe göre.
    prio = lambda e: 0 if e["fiyat_duzeltir"] else (1 if e["tur"] == "temettu_hak" else 2)
    evs = sorted(evs, key=lambda te: (prio(te[1]), te[1]["tarih"], te[0]))
    important = [f"{t} {e['tarih'][8:10]}.{e['tarih'][5:7]} " + (
        "bedelsiz/bedelli fiyat düzeltmesi" if e["fiyat_duzeltir"] else
        "temettü hak kullanımı" + (f" (brüt {e['brut_tl']:.2f} TL)" if e.get("brut_tl") else "") if e["tur"] == "temettu_hak"
        else "genel kurul") for t, e in evs if e["fiyat_duzeltir"] or e["tur"] in ("temettu_hak", "genel_kurul")]
    return {"olay": len(evs), "sirket": len({t for t, _ in evs}), "onemli": important[:12],
            "bitis": market_calendar.add_trading_days(today, days).isoformat()}


def run(db_path=None, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.time,
        backfill_fn=None, fetch_new_fn=None, max_hours: float = MAX_HOURS) -> Dict:
    """Tamamlanana (ya da durma koşulu oluşana) kadar okur. Test için sleep/clock/işlevler değiştirilebilir."""
    from .universe import load_universe
    conn = db.connect(db_path)
    uni = load_universe(conn)
    backfill_fn = backfill_fn or (lambda c: kap_history.backfill(c, uni, list_fn=lambda a, b: [], sleep=sleep))
    fetch_new_fn = fetch_new_fn or (lambda c: kap.fetch_missing_bodies(c))
    t0 = clock()
    start = pending_counts(conn)
    st = {"durum": "çalışıyor", "basladi": datetime.now(config.TR_TZ).isoformat(timespec="seconds"),
          "baslangic_bekleyen": start["toplam"], "okunan": 0, "kalan": start["toplam"], "tur": 0,
          "kap_siniri_sayisi": 0, "mesaj": "Okunuyor...", "ozet": None}
    _save(st)
    waits = 0
    try:
        while True:
            before = pending_counts(conn)
            if before["toplam"] == 0:
                break
            st["tur"] += 1
            limited = False
            try:
                r1 = backfill_fn(conn)
                limited = bool(r1.get("kap_siniri"))
                if not limited:  # takvim bitti ya da sınır yok → günlük haber metinleri
                    r2 = fetch_new_fn(conn)
                    limited = bool(r2.get("rate_limited"))
            except kap.RateLimited:
                limited = True
            except Exception as e:  # ağ hatası vb.: sınır gibi bekleyip dene
                limited, st["son_hata"] = True, str(e)[:200]
            after = pending_counts(conn)
            st["okunan"] += max(0, before["toplam"] - after["toplam"])
            st["kalan"] = after["toplam"]
            if after["toplam"] == 0:
                break
            if not limited and after["toplam"] >= before["toplam"]:
                st.update(durum="durdu", devam_gerek=False, mesaj=f"{after['toplam']} sayfa bu sefer okunamadı (KAP sayfası boş ya da "
                          "hatalı); bir sonraki güncellemede yeniden denenir.")
                _save(st)
                return st
            if clock() - t0 > max_hours * 3600:
                st.update(durum="durdu", devam_gerek=True, mesaj=f"{max_hours:g} saatlik güvenlik süresi doldu; {after['toplam']} sayfa "
                          "kaldı. Panel bir sonraki açılışta kaldığı yerden devam eder.")
                _save(st)
                return st
            if limited:
                st["devam_gerek"] = True   # panel kapanırsa bir sonraki açılışta kaldığı yerden sürsün
                wait = WAITS_MIN[min(waits, len(WAITS_MIN) - 1)]
                waits += 1
                st["kap_siniri_sayisi"] += 1
                resume = datetime.fromtimestamp(clock() + wait * 60, config.TR_TZ)
                st.update(mesaj=f"KAP istek sınırı uyguladı; {wait} dk bekleniyor, {resume:%H:%M} civarı kendiliğinden "
                          f"devam edilecek. {after['toplam']} sayfa kaldı.", sonraki=resume.isoformat(timespec="seconds"))
                _save(st)
                sleep(wait * 60)
            else:
                waits = 0
                st["mesaj"] = f"Okunuyor... {after['toplam']} sayfa kaldı."
                _save(st)
        st.update(durum="tamamlandı", kalan=0, devam_gerek=False, mesaj=f"Tamamlandı: {st['okunan']} sayfa okundu"
                  + (f", KAP sınırı {st['kap_siniri_sayisi']} kez beklendi" if st["kap_siniri_sayisi"] else "") + ".",
                  bitti=datetime.now(config.TR_TZ).isoformat(timespec="seconds"), ozet=event_summary(conn),
                  analiz_bekleyen=conn.execute("SELECT COUNT(*) FROM news WHERE status='new' AND body IS NOT NULL "
                                               "AND LENGTH(TRIM(body))>0").fetchone()[0])
        _save(st)
        return st
    finally:
        conn.close()


def running() -> bool:
    return _thread is not None and _thread.is_alive()


def alive_elsewhere(st: Optional[Dict] = None, now: Optional[datetime] = None) -> bool:
    """Başka bir işlemde (ör. ikinci panel penceresi) okuyucu çalışıyor mu? Durum dosyasındaki canlılık zamanına bakar:
    son kayıt 5 dk içindeyse ya da planlanan devam zamanı + 5 dk henüz geçmediyse çalışıyor sayılır."""
    st = load() if st is None else st
    if st.get("durum") != "çalışıyor":
        return False
    now = now or datetime.now(config.TR_TZ)
    try:
        beat = datetime.fromisoformat(st.get("nabiz", ""))
        if (now - beat).total_seconds() < STALE_MIN * 60:
            return True
        nxt = st.get("sonraki")
        return bool(nxt) and (now - datetime.fromisoformat(nxt)).total_seconds() < STALE_MIN * 60
    except ValueError:
        return False


def start(db_path=None, force: bool = False) -> bool:
    """Arka planda başlatır (zaten çalışıyorsa False). force=False iken yalnız gerekiyorsa başlar."""
    global _thread
    with _lock:
        if running():
            return False
        conn = db.connect(db_path)
        try:
            pend = pending_counts(conn)["toplam"]
        finally:
            conn.close()
        if pend == 0:
            return False
        prev = load()
        if alive_elsewhere(prev):
            return False   # başka bir pencerede/işlemde zaten okuyor: KAP'a ikinci kez gitme
        # Kendiliğinden başlama: çok sayfa var, ya da önceki iş yarım kaldı (KAP sınırı / süre / panel kapandı).
        if not force and not (pend > AUTO_START_MIN_PAGES or prev.get("devam_gerek") or prev.get("durum") == "çalışıyor"):
            return False
        _thread = threading.Thread(target=run, kwargs={"db_path": db_path}, daemon=True, name="halley-kap-okuyucu")
        _thread.start()
        return True


SERVE_CHECK_SEC = 120


def _serve_lock():
    return config.DATA / "kap_okuyucu_servis.json"


def serve(db_path=None, sleep: Callable[[float], None] = time.sleep, once: bool = False,
          run_fn: Optional[Callable] = None) -> None:
    """baslat.bat ile panelin yanında çalışan bekçi (2026-11-07): tarayıcıda panel açık olmasa da bekleyen sayfaları
    kendiliğinden tamamlar. 2 dk'da bir bakar; başka bir işlemde okuyucu çalışıyorsa (canlılık zamanı) karışmaz.
    Aynı anda tek bekçi: başka bekçinin kilidi tazeyse çıkar. Pencere kapanınca biter."""
    lock = _serve_lock()
    try:
        other = json.loads(lock.read_text(encoding="utf-8"))
        beat = datetime.fromisoformat(other["nabiz"])
        if (datetime.now(config.TR_TZ) - beat).total_seconds() < SERVE_CHECK_SEC * 3 and not once:
            return  # başka bir bekçi çalışıyor
    except (OSError, ValueError, KeyError):
        pass
    run_fn = run_fn or run
    while True:
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"nabiz": datetime.now(config.TR_TZ).isoformat(timespec="seconds")}), encoding="utf-8")
        try:
            conn = db.connect(db_path)
            try:
                pend = pending_counts(conn)["toplam"]
            finally:
                conn.close()
            prev = load()
            need = pend > 0 and (pend > AUTO_START_MIN_PAGES or prev.get("devam_gerek") or prev.get("durum") == "çalışıyor")
            if need and not alive_elsewhere(prev) and not running():
                run_fn(db_path=db_path)
        except Exception as e:  # bekçi asla çökmemeli; bir sonraki turda yeniden dener
            st = load()
            st["bekci_hata"] = str(e)[:200]
            _save(st)
        if once:
            return
        sleep(SERVE_CHECK_SEC)


def note_rate_limited() -> None:
    """Günlük güncelleme KAP sınırına takıldıysa işaretle: panel okuyucuyu kendiliğinden başlatsın."""
    st = load()
    st["devam_gerek"] = True
    _save(st)
