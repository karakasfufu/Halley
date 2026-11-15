"""Aşama 7: Chronos-Bolt (Amazon, Apache-2.0) ile her plan için kapanışın 1–20 gün sonraki yüzdelik tahminleri →
TP1'in üstünde / SL'nin altında kapanma olasılığı (yüzdeliklerden doğrusal ara değer). Yol sırası bilinmez; bu yüzden
"önce hangisi" yerine "5/10/20. gün kapanışı TP1 üstü mü, SL altı mı" girdileri üretilir.
Ayrı araştırma ortamında çalışır; Halley'e eklenmez. Yapay zekâ (OpenAI) yok.
Kullanım: python chronos_yol.py <arastirma.db> <planlar.csv> <cikti.csv> [model]
"""
import sqlite3
import sys
import time

import numpy as np
import pandas as pd
import torch
from chronos import BaseChronosPipeline

dbp, plans_p, out_p = sys.argv[1:4]
MODEL = sys.argv[4] if len(sys.argv) > 4 else "amazon/chronos-bolt-small"
CTX, H = 250, 20
pipe = BaseChronosPipeline.from_pretrained(MODEL, device_map="cpu", torch_dtype=torch.float32)
Q = np.array(pipe.quantiles if hasattr(pipe, "quantiles") else [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])


def p_above(qv, level):
    """qv: yüzdelik değerleri (artan). P(X > level) doğrusal ara değerle; uçlarda 0,05 / 0,95'e kırpılır."""
    if level <= qv[0]:
        return 1 - Q[0] / 2
    if level >= qv[-1]:
        return (1 - Q[-1]) / 2
    return float(1 - np.interp(level, qv, Q))


conn = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
plans = pd.read_csv(plans_p, dtype={"tarih": str})
ctx, keep = [], []
for p in plans.itertuples(index=False):
    c = [r[0] for r in conn.execute("SELECT close FROM prices WHERE ticker=? AND date<=? ORDER BY date DESC LIMIT ?",
                                    (p.ticker, p.tarih, CTX))][::-1]
    if len(c) >= 60:
        ctx.append(torch.tensor(c, dtype=torch.float32))
        keep.append(p)
print("plan", len(keep), "model", MODEL, flush=True)
rows, t0 = [], time.time()
for i in range(0, len(ctx), 256):
    with torch.no_grad():
        q = pipe.predict(ctx[i:i + 256], prediction_length=H)        # (B, len(Q), H)
    q = q.numpy()
    for j, p in enumerate(keep[i:i + 256]):
        qq = np.sort(q[j], axis=0)
        r = {"ticker": p.ticker, "tarih": p.tarih}
        for h in (5, 10, 20):
            r[f"c_tp1_{h}"] = round(p_above(qq[:, h - 1], p.tp1), 4)
            r[f"c_sl_{h}"] = round(1 - p_above(qq[:, h - 1], p.sl), 4)
        med = qq[len(Q) // 2]
        r["c_getiri10"] = round(float(med[9] / p.kapanis - 1) * 100, 3)
        r["c_genislik10"] = round(float((qq[-1, 9] - qq[0, 9]) / p.kapanis) * 100, 3)
        r["c_gun1"] = round(float(med[0] / p.kapanis - 1) * 100, 3)
        rows.append(r)
    print(len(rows), round(time.time() - t0), "sn", flush=True)
pd.DataFrame(rows).to_csv(out_p, index=False)
print("bitti", len(rows), flush=True)
