"""Aşama 7: sınama dönemlerindeki (son 12 ay + 2024) kapanmış planlar, hisse başına 14 günde bir (tekil).
Mutlak seviyeler etiketlerden geri hesaplanır: giriş = sinyal günü kapanışı (ready.candidates'ta hep böyle),
SL/TP1 = stop_% / tp1_%, azami giriş = ready kuralı (ATR = atr_% × giriş). TP2 etikette yok → yedek kural
(max(giriş + 3 risk, TP1 + risk)); yalnız R'yi etkiler, TP1 olasılığını etkilemez.
Kullanım: python planlar.py <etiket3.csv> <cikti.csv>
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asama6"))
import egit  # noqa: E402

df = egit.load_df(sys.argv[1])
last = df.tarih.max()
t12 = (pd.Timestamp(last) - pd.DateOffset(months=12)).date().isoformat()
df = df[(df.tarih >= t12) | ((df.tarih >= "2024-01-01") & (df.tarih < "2025-01-01"))].copy()
df["donem"] = (df.tarih >= t12).map({True: "son12", False: "2024"})
keep, lastd = [], {}
for i, (tk, d) in enumerate(zip(df.ticker, df.tarih)):
    if tk not in lastd or (pd.Timestamp(d) - pd.Timestamp(lastd[tk])).days > 14:
        keep.append(i)
        lastd[tk] = d
df = df.iloc[keep].copy()
import sqlite3  # noqa: E402
conn = sqlite3.connect(f"file:{sys.argv[3]}?mode=ro", uri=True) if len(sys.argv) > 3 else None
close = {}
for (tk, d) in zip(df.ticker, df.tarih):
    close[(tk, d)] = conn.execute("SELECT close FROM prices WHERE ticker=? AND date=?", (tk, d)).fetchone()[0]
df["kapanis"] = [close[(a, b)] for a, b in zip(df.ticker, df.tarih)]
df["giris"] = df.kapanis
df["sl"] = df.giris * (1 - df["stop_%"] / 100)
df["tp1"] = df.giris * (1 + df["tp1_%"] / 100)
risk = df.giris - df.sl
df["tp2"] = pd.concat([df.giris + 3 * risk, df.tp1 + risk], axis=1).max(axis=1)
atr = df["atr_%"] * df.giris / 100
cap = (df.tp1 + 1.5 * df.sl) / 2.5
df["azami"] = pd.concat([df.giris, pd.concat([df.giris + 0.3 * atr, cap], axis=1).min(axis=1)], axis=1).max(axis=1)
df = df.sample(frac=1, random_state=7)              # karışık sıra: yarıda kesilse de iki dönemden örnek olsun
df[["ticker", "tarih", "donem", "tur", "kapanis", "giris", "sl", "tp1", "tp2", "azami", "y", "r"]].to_csv(sys.argv[2], index=False)
print(len(df), df.donem.value_counts().to_dict())
