"""Aşama 6 etiketleme: geçmişin her günü için Halley'in bugünkü "koşulu sağlanmış plan" kuralları (ready.candidates,
yalnız teknik) o güne kadarki 250 günlük veriyle (canlıdaki 1 yıllık indirmeyle aynı pencere) uygulanır.
Giriş: ertesi işlem gününün AÇILIŞI (azami girişin üstündeyse giriş yok). Çıkış: journal.evaluate (TP1'de yarısı,
stop girişe; TP2; SL; 30 gün), komisyon %0,2 + kayma %0,1. Etiket: TP1 SL'den önce görüldü mü.
Geleceği görme yok: girdiler yalnız sinyal gününe kadarki barlardan; sonuç yalnız sonraki barlardan.
Kullanım: python etiketle.py <repo> <arastirma.db> <cikti.csv>
"""
import csv
import sqlite3
import sys
from datetime import date
from multiprocessing import Pool

WIN = 250
REPO = DBP = None


def init(repo, dbp):
    global REPO, DBP
    REPO, DBP = repo, dbp
    sys.path.insert(0, repo)


def load(conn, tk):
    return [dict(zip(("date", "open", "high", "low", "close", "volume"), r)) for r in conn.execute(
        "SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? ORDER BY date", (tk,))]


NEWS0 = {"direction": 0, "score": 0, "confidence": None, "flags": "", "bilanco_riski": None, "olay_riskleri": [],
         "makro_riski": None}


def work(tk):
    from bist_haber import entries, journal, ready, technical, tracker, tradeplan
    conn = sqlite3.connect(f"file:{DBP}?mode=ro", uri=True)
    bars = load(conn, tk)
    bench = load(conn, "XU100")
    conn.close()
    bidx = {b["date"]: i for i, b in enumerate(bench)}
    cur = {"w": []}
    ready._bars = lambda c, t, upto, n=22: cur["w"][-n:]       # candidates() SQL yerine bellekteki pencere
    out = []
    bars = [b for b in bars if b.get("close")]
    for i in range(WIN - 1, len(bars) - 1):
        w = bars[i - WIN + 1:i + 1]
        d = w[-1]["date"]
        bi = bidx.get(d)
        bw = bench[max(0, bi - WIN + 1):bi + 1] if bi is not None else []
        t = technical.analyze(w, date.fromisoformat(d), bench=bw or None)   # bayat-veri kontrolü o güne göre
        if not t or tracker.scenario_guard(t):
            continue
        cur["w"] = w
        g = entries.scenarios(t)
        cands = [c for c in ready.candidates(None, t, {"girisler": g, "_ticker": tk}) if c["rr1"] >= tradeplan.MIN_RR]
        if not cands:
            continue
        order = list(ready.TYPE_NAMES)
        best = max(cands, key=lambda c: (round(c["rr1"], 2), -order.index(c["tur"])))
        ts = ready.tech_score(t)
        riskler = tradeplan.risk_factors(t, NEWS0) + list(t.get("veri_uyarilari") or [])
        risk = tradeplan._level(tradeplan._points(riskler))
        atr, e, sl, tp1 = t["atr"], best["giris"], best["sl"], best["tp1"]
        cap = (tp1 + ready.MIN_RR_AT_MAX * sl) / (1 + ready.MIN_RR_AT_MAX)
        azami = max(e, min(e + ready.MAX_ENTRY_ATR * atr, cap))
        nxt = bars[i + 1]
        row = {"ticker": tk, "tarih": d, "tur": best["tur"], "rr1": round(best["rr1"], 3),
               "stop_%": round((e - sl) / e * 100, 3), "tp1_%": round((tp1 / e - 1) * 100, 3),
               "skor": ts["skor"], **{"p_" + k: v for k, v in ts["parca"].items()}, "risk": risk,
               "trend": t["trend"], "rsi": t["rsi14"], "atr_%": t["atr_%"], "sma50_%": t["fiyat_sma50_%"],
               "sma200_%": t["fiyat_sma200_%"], "hacim_orani": t["hacim_orani"], "rs20": t["rs_20g_%"],
               "rs60": t["rs_60g_%"], "adx": t["adx"], "di_fark": (t["arti_di"] or 0) - (t["eksi_di"] or 0),
               "macd_hist_%": (t["macd_hist"] / t["son_fiyat"] * 100) if t["macd_hist"] is not None else None,
               "bb_gen": t["bb_genislik_%"], "sikisma": int(bool(t["bb_sikisma"])), "zirve_%": t["zirveye_uzaklik_%"],
               "perf5": t["perf_5g_%"], "perf20": t["perf_20g_%"], "hacim_tl": t["islem_hacmi_tl"],
               "kilitli": int(bool(t["son_gun_kilitli"])), "ertesi_kilitli": int(nxt["high"] == nxt["low"]),
               "acilis_bosluk_%": round((nxt["open"] / t["son_fiyat"] - 1) * 100, 3) if nxt.get("open") else None}
        if not nxt.get("open") or nxt["open"] > azami + 1e-9:
            row.update(sonuc="girissiz", y="", r="", net="", gun="")
            out.append(row)
            continue
        rec = {"kaynak": "gercek", "gercek_giris_gunu": nxt["date"], "gercek_giris_fiyati": nxt["open"],
               "signal_day": d, "senaryo": best["tur"], "sl": sl, "tp1": tp1, "tp2": best["tp2"], "giris": e,
               "alarm": None, "gecerlilik": 1}
        res = journal.evaluate(rec, bars[i + 1:i + 1 + journal.MAX_HOLD + 2], 0.20, 0.10)
        if res.get("durum") != "kapandı":
            row.update(sonuc="acik", y="", r="", net="", gun="")
        else:
            row.update(sonuc=res["sonuc"], y=int(bool(res["tp1_goruldu"])), r=res["r"], net=res["net_getiri_pct"],
                       gun=res["islem_gunu"])
        out.append(row)
    return out


def main():
    repo, dbp, outp = sys.argv[1:4]
    conn = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    tks = [r[0] for r in conn.execute("SELECT ticker FROM prices WHERE ticker!='XU100' GROUP BY ticker "
                                      "HAVING COUNT(*)>=?", (WIN + 30,))]
    conn.close()
    if len(sys.argv) > 4:
        tks = tks[:int(sys.argv[4])]
    print("hisse:", len(tks), flush=True)
    rows, n = [], 0
    with Pool(4, initializer=init, initargs=(repo, dbp)) as p:
        for res in p.imap_unordered(work, tks, chunksize=2):
            rows.extend(res)
            n += 1
            if n % 50 == 0:
                print(n, len(rows), flush=True)
    rows.sort(key=lambda r: (r["tarih"], r["ticker"]))
    keys = list(rows[0].keys()) if rows else []
    with open(outp, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, keys)
        wr.writeheader()
        wr.writerows(rows)
    print("satır:", len(rows), flush=True)


if __name__ == "__main__":
    main()
