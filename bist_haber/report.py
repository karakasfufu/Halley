"""Günlük sinyal tablosu.

DİKKAT: Buradaki ağırlıklar ve eşikler başlangıç tahminidir, kalibre edilmedi.
Faz 3-4'te backtest ile veriden belirlenecek (Dipnot 5). Çıktı yatırım tavsiyesi değildir.
"""
import csv
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config

# Etkinin yarılanma süresi (gün), kalıcılığa göre.
HALF_LIFE = {"kisa": 1.0, "orta": 5.0, "uzun": 20.0}
THRESHOLDS = [(4.0, "GÜÇLÜ POZİTİF"), (1.5, "POZİTİF"), (-1.5, "İZLE"), (-4.0, "NEGATİF")]


def label(score: float) -> str:
    for th, name in THRESHOLDS:
        if score >= th:
            return name
    return "GÜÇLÜ NEGATİF"


def _price_changes(conn, ticker: str, as_of: date):
    rows = conn.execute("SELECT date, close FROM prices WHERE ticker=? AND date<=? ORDER BY date DESC LIMIT 6",
                        (ticker, as_of.isoformat())).fetchall()
    if len(rows) < 2:
        return None, None
    c0 = rows[0]["close"]
    d1 = (c0 / rows[1]["close"] - 1) * 100
    d5 = (c0 / rows[-1]["close"] - 1) * 100 if len(rows) >= 6 else None
    return d1, d5


def build(conn, universe: Dict[str, str], days: int = 7, as_of: Optional[date] = None) -> List[dict]:
    as_of = as_of or datetime.now(config.TR_TZ).date()
    since = (as_of - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT i.*, n.note AS summary, n.title FROM impacts i JOIN news n ON n.id=i.news_id "
        "WHERE i.effective_date>? AND i.effective_date<=? "
        "AND (n.source!='kap' OR LENGTH(TRIM(COALESCE(n.body,''), char(9)||char(10)||char(13)||' '))>0) "
        "ORDER BY i.published_at",
        (since, as_of.isoformat())).fetchall()
    agg: Dict[str, dict] = {}
    # Aynı olay (aynı hisse + aynı olay türü, 2 gün içinde) birden çok kaynaktan gelebilir
    # (KAP + 2 haber sitesi). Bunlar toplanmaz; kümedeki en güçlü etki sayılır.
    # İstisna: içeriden pay alım-satım bildirimlerinin her biri ayrı bir işlemdir.
    clusters: Dict[tuple, list] = {}
    for r in rows:
        age = (as_of - date.fromisoformat(r["effective_date"])).days
        decay = 0.5 ** (age / HALF_LIFE.get(r["persistence"], 5.0))
        contrib = r["direction"] * r["magnitude"] * r["confidence"] * decay
        eff = date.fromisoformat(r["effective_date"])
        key = (r["ticker"], r["event_type"])
        groups = clusters.setdefault(key, [])
        if (r["event_type"] != "iceriden_pay_alim_satim" and groups
                and (eff - groups[-1]["last_date"]).days <= 2):
            g = groups[-1]
        else:
            g = {"best": 0.0, "last_date": eff}
            groups.append(g)
        g["last_date"] = eff
        if abs(contrib) > abs(g["best"]):
            g["best"] = contrib
        a = agg.setdefault(r["ticker"], {"ticker": r["ticker"], "name": universe.get(r["ticker"], ""),
                                         "score": 0.0, "news_count": 0, "last_news": "", "last_reason": "",
                                         "flags": set()})
        a["news_count"] += 1
        a["last_news"] = r["summary"] or r["title"]
        a["last_reason"] = r["reason"] or ""
        if "flag" in r.keys() and r["flag"]:
            a["flags"].add(r["flag"])
    for (ticker, _), groups in clusters.items():
        agg[ticker]["score"] += sum(g["best"] for g in groups)
    for a in agg.values():
        a["flags"] = ", ".join(sorted(a["flags"]))
    out = []
    for a in agg.values():
        d1, d5 = _price_changes(conn, a["ticker"], as_of)
        a.update(score=round(a["score"], 2), signal=label(a["score"]),
                 chg_1d=None if d1 is None else round(d1, 2), chg_5d=None if d5 is None else round(d5, 2))
        out.append(a)
    out.sort(key=lambda x: -abs(x["score"]))
    return out


def print_table(rows: List[dict], top: int = 30) -> None:
    if not rows:
        print("Raporlanacak etki yok. Önce 'collect' ve 'analyze' çalıştırın.")
        return
    fmt = "{:<7} {:>6}  {:<14} {:>3}  {:>7} {:>7}  {}"
    print(fmt.format("HİSSE", "SKOR", "SİNYAL", "HBR", "1G %", "5G %", "SON HABER"))
    print("-" * 110)
    for r in rows[:top]:
        pct = lambda v: "-" if v is None else f"{v:+.1f}"
        print(fmt.format(r["ticker"], f"{r['score']:+.2f}", r["signal"], r["news_count"],
                         pct(r["chg_1d"]), pct(r["chg_5d"]), (r["last_news"] or "")[:60]))
    print("\nNot: Eşikler henüz kalibre edilmedi (Faz 3-4). Bu tablo yatırım tavsiyesi değildir.")


def save_csv(rows: List[dict], as_of: date) -> str:
    path = config.DATA / f"rapor_{as_of.isoformat()}.csv"
    cols = ["ticker", "name", "score", "signal", "flags", "news_count", "chg_1d", "chg_5d", "last_news", "last_reason"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # Excel uyumlu
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return str(path)
