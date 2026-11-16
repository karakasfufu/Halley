"""FAZ 5: 5/10 işlem günlük hedeflerin üretimi (ön kayıt: deney_tanimi.json, commit 6430231). Yalnız okur.
Getiri hedefi (zaman çıkışı) ile TP1 olay hedefi AYRIDIR. TP1 olayı journal.evaluate ile (mumlar ilk N ile sınırlı).
Kullanım: python hedefler.py <repo> <arastirma.db> <planlar_seviyeli.csv> <cikti.csv>"""
import csv
import sqlite3
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

MALIYET_PCT = 0.30          # komisyon %0,2 + kayma %0,1 (gidiş-dönüş)
UFUKLAR = (5, 10)


def f_(v):
    try:
        return float(v) if v not in (None, "", "nan") else None
    except ValueError:
        return None


def giris(plan: Dict, bars: List[Dict]) -> Tuple[Optional[int], str]:
    """Sinyal gününden sonraki ilk mum; açılış > azami ya da ≤ SL → girişsiz. Dönüş: (mum indeksi | None, neden)."""
    j = next((i for i, b in enumerate(bars) if b["date"] > plan["tarih"]), None)
    if j is None:
        return None, "giris_mumu_yok"
    o = bars[j].get("open") or bars[j]["close"]
    if o > plan["azami"] + 1e-9:
        return None, "girissiz_azami_ustu"
    if o <= plan["sl"] + 1e-9:
        return None, "girissiz_stop_alti"
    return j, "giris"


def hedef(plan: Dict, bars: List[Dict], j: int, n: int, journal_mod, takvim_idx=None) -> Optional[Dict]:
    """j: giriş mumu indeksi. İlk n mum (giriş günü 1. gün). n mum yoksa None (sonuc_yok)."""
    pencere = bars[j:j + n]
    if len(pencere) < n:
        return None
    fill = pencere[0].get("open") or pencere[0]["close"]
    cikis = pencere[-1]["close"]
    risk = plan["giris"] - plan["sl"]
    net = (cikis / fill - 1) * 100 - MALIYET_PCT
    r_plan = (cikis - fill) / risk - MALIYET_PCT / 100 * fill / risk if risk > 0 else None
    rec = {"kaynak": "gercek", "gercek_giris_gunu": pencere[0]["date"], "gercek_giris_fiyati": fill,
           "signal_day": plan["tarih"], "senaryo": plan["tur"], "sl": plan["sl"], "tp1": plan["tp1"], "tp2": plan["tp2"],
           "giris": plan["giris"], "alarm": None, "gecerlilik": 1}
    res = journal_mod.evaluate(rec, pencere)
    bosluk = 0
    if takvim_idx is not None:
        a, b = takvim_idx[pencere[0]["date"]], takvim_idx[pencere[-1]["date"]]
        bosluk = (b - a + 1) - n
    return {f"H{n}_net_%": round(net, 4), f"H{n}_R": round(r_plan, 4) if r_plan is not None else None,
            f"H{n}_pozitif": int(net > 0), f"H{n}_tp1": int(bool(res.get("tp1_hedefi"))),
            f"H{n}_takvim_boslugu": int(bosluk > 0)}


def plan_oku(path: str) -> List[Dict]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["risk"] == "yüksek" or (f_(r["teknik_skor"]) or 0) < 5:
                continue
            p = dict(r)
            for k in ("giris", "sl", "tp1", "tp2", "azami"):
                p[k] = float(r[k])
            out.append(p)
    return out


def main():
    repo, dbp, plan_csv, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    from bist_haber import journal
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    bars = defaultdict(list)
    for tk, d, o, h, l, cl in c.execute("SELECT ticker, date, open, high, low, close FROM prices WHERE close IS NOT NULL "
                                        "AND ticker!='XU100' ORDER BY ticker, date"):
        bars[tk].append({"date": d, "open": o, "high": h, "low": l, "close": cl})
    takvim = sorted({b["date"] for bs in bars.values() for b in bs})
    tix = {d: i for i, d in enumerate(takvim)}
    planlar = plan_oku(plan_csv)
    yaz, say = [], defaultdict(int)
    son_sinyal = {}
    for p in planlar:
        bs = bars.get(p["ticker"], [])
        j, neden = giris(p, bs)
        say[neden] += 1
        if j is None:
            continue
        satir = {k: p[k] for k in p}
        ok = True
        for n in UFUKLAR:
            h = hedef(p, bs, j, n, journal, tix)
            if h is None:
                say[f"sonuc_yok_H{n}"] += 1
                ok = False
                break
            satir.update(h)
        if not ok:
            continue
        onceki = son_sinyal.get(p["ticker"])
        satir["tekrar_10"] = int(onceki is not None and j - onceki <= 10)
        son_sinyal[p["ticker"]] = j
        yaz.append(satir)
    alan = list(yaz[0].keys())
    with open(cikti, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, alan)
        w.writeheader()
        w.writerows(yaz)
    print(dict(say), "ortak örneklem:", len(yaz))


if __name__ == "__main__":
    main()
