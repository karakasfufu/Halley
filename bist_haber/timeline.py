"""Birleşik takvim: bir hisse için önümüzdeki işlem günlerinde neler var? (Parça B4, 2026-11-07)

Tek listede, tarih sırasıyla: piyasa geneli (PPK, TÜFE, Enflasyon Raporu, Fed, kredi notu, VİOP vade sonu, Borsa
tatili/yarım gün), hissenin bilanço yasal son günü (açıklanmadıysa/bilinmiyorsa) ve şirket olayları (genel kurul,
kâr payı, sermaye artırımı). Yalnız mevcut modüllerin doğrulanmış verisini birleştirir; yeni tarih üretmez.
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config, corp_events, earnings, macro_calendar, market_calendar

MACRO_RISK_TYPES = ("ppk", "tufe", "fomc", "er", "kredi")   # fiyatı piyasa genelinde oynatabilecekler
SHORT = {"ppk": "TCMB faiz kararı", "tufe": "TÜFE", "fomc": "Fed kararı", "er": "Enflasyon Raporu",
         "kredi": "kredi notu"}


def _d(iso: str) -> str:
    return f"{int(iso[8:10])}.{iso[5:7]}"


def for_ticker(conn, ticker: str, today: Optional[date] = None, days: int = 15) -> Dict:
    today = today or datetime.now(config.TR_TZ).date()
    end = market_calendar.add_trading_days(today, days).isoformat()
    items: List[Dict] = []
    up = macro_calendar.upcoming(today, days)
    for e in up["olaylar"]:
        items.append({"tarih": e["tarih"], "kapsam": "Piyasa", "olay": e["ad"],
                      "ayrinti": e.get("saat") or "", "dogrulama": e.get("dogrulama", ""), "tur": e["tur"]})
    s = earnings.status(conn, ticker, today)
    if s["durum"] in ("açıklanmadı", "bilinmiyor") and today.isoformat() <= s["son_tarih"] <= end:
        items.append({"tarih": s["son_tarih"], "kapsam": "Hisse", "olay": f"{s['donem']['donem']} bilanço yasal son günü",
                      "ayrinti": "henüz açıklanmadı" if s["durum"] == "açıklanmadı" else "açıklanıp açıklanmadığı bilinmiyor",
                      "dogrulama": "SPK II-14.1 süresi", "tur": "bilanco"})
    for e in corp_events.upcoming(conn, ticker, today, days)["yaklasan"]:
        extra = e.get("tip") or ""
        if e.get("brut_tl"):
            extra = (extra + " · " if extra else "") + f"brüt {e['brut_tl']:.4f} TL/pay"
        items.append({"tarih": e["tarih"], "kapsam": "Hisse", "olay": e["ad"], "ayrinti": extra,
                      "dogrulama": "KAP bildirimi", "tur": e["tur"]})
    items.sort(key=lambda x: (x["tarih"], x["kapsam"] != "Hisse"))
    for x in items:
        x["is_gunu_sonra"] = market_calendar.trading_days_between(today, date.fromisoformat(x["tarih"]))
    from .kap import coverage_gaps
    gaps = coverage_gaps(conn, today - timedelta(days=config.KAP_HISTORY_DAYS - 1), today, today)
    gap_note = (f"KAP listesi {len(gaps)} gün için alınmamış: bu günlerde açıklanan şirket olayları eksik olabilir "
                "(bir sonraki güncellemede kendiliğinden tamamlanır)." if gaps else None)
    unread = conn.execute("SELECT COUNT(*) FROM news WHERE status='context' AND body IS NULL AND (','||candidates||',') "
                          "LIKE ? AND subject IN (%s)" % ",".join("?" * len(corp_events.SUBJECTS)),
                          (f"%,{ticker},%", *corp_events.SUBJECTS)).fetchone()[0]
    unread_note = (f"Bu hisse için {unread} takvim bildiriminin (genel kurul / kâr payı / sermaye artırımı) sayfası henüz "
                   "okunmadı: şirket olayları eksik olabilir; arka planda okunuyor, tamamlanınca kendiliğinden görünür."
                   if unread else None)
    return {"olaylar": items, "bitis": end, "bilinmeyen": up["bilinmeyen"], "tatil_notu": up.get("tatil_notu"),
            "kap_boslugu": gap_note, "okunmamis": unread, "okunmamis_notu": unread_note}


def macro_risk(today: Optional[date] = None, days: int = 15) -> Optional[str]:
    """Vade içinde piyasa geneli önemli olaylar → tek risk maddesi (tüm hisseleri etkiler, 1 puan)."""
    today = today or datetime.now(config.TR_TZ).date()
    evs = [e for e in macro_calendar.upcoming(today, days)["olaylar"] if e["tur"] in MACRO_RISK_TYPES]
    if not evs:
        return None
    parts = [f"{_d(e['tarih'])} {SHORT[e['tur']]}" for e in evs]
    return ("Vade içinde piyasa geneli olay: " + ", ".join(parts) +
            " — bu açıklamalar tüm piyasayı oynatabilir (açıklama öncesi/sonrası oynaklık artar)")


def compact(tl: Dict, limit: int = 8) -> str:
    """CSV için kısa metin."""
    xs = tl["olaylar"][:limit]
    if not xs:
        return "Önümüzdeki işlem günlerinde kayıtlı olay yok."
    return "; ".join(f"{_d(x['tarih'])} {x['olay'].split(':')[0]}" for x in xs) + (" …" if len(tl["olaylar"]) > limit else "")
