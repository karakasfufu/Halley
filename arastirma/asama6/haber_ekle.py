"""Aşama 6 / haber 1. aşama: etiket CSV'sine KAP konu girdilerini ekler (bist_haber.tp1_model.news_features; canlıyla
aynı fonksiyon). Yapay zekâ yok. Kullanım: python haber_ekle.py <repo> <arastirma.db> <etiket.csv> <cikti.csv>
"""
import bisect
import sqlite3
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, sys.argv[1])
from bist_haber import tp1_model  # noqa: E402

conn = sqlite3.connect(f"file:{sys.argv[2]}?mode=ro", uri=True)
by = {}
for ts, konu, hs in conn.execute("SELECT yayin, konu, hisseler FROM kap_liste ORDER BY yayin"):
    for tk in (hs or "").split(","):
        if tk:
            by.setdefault(tk, ([], []))
            by[tk][0].append(ts)
            by[tk][1].append(konu)
cover = conn.execute("SELECT MIN(bas), MAX(son) FROM kap_liste_aralik").fetchone()
df = pd.read_csv(sys.argv[3], dtype={"tarih": str})
rows = []
for tk, d in zip(df["ticker"], df["tarih"]):
    ts, ks = by.get(tk, ([], []))
    lo = bisect.bisect_left(ts, (date.fromisoformat(d) - timedelta(days=31)).isoformat())
    hi = bisect.bisect_right(ts, d + "T23:59:59")
    rows.append(tp1_model.news_features(zip(ts[lo:hi], ks[lo:hi]), d))
out = pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
out["kap_kapsam"] = ((out["tarih"] >= cover[0]) & (out["tarih"] <= cover[1])).astype(int)
out.to_csv(sys.argv[4], index=False)
print("satır", len(out), "KAP kapsamı", cover, "haberli plan %", round(100 * out["h_var"].mean(), 1))
print(out.groupby("h_var")["y"].agg(["size", "mean"]).round(3))
