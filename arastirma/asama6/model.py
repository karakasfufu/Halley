"""Aşama 6 modelleri ve ileriye dönük sınama (yalnız numpy/pandas).
Kullanım: python model.py <etiket.csv> <arastirma.db> <cikti.json>
"""
import json
import sqlite3
import sys

import numpy as np
import pandas as pd

EMBARGO_DAYS = 45          # takvim günü: eğitim etiketleri (≤30 işlem günü) test dönemine taşmasın
PRIOR_M = 50               # benzer durumlar tablosu: küçük grupları üst gruba doğru büzme gücü
NUM = ["rr1", "stop_%", "tp1_%", "skor", "p_trend", "p_rsi", "p_ivme", "p_hacim", "p_goreli_guc", "rsi", "atr_%",
       "sma50_%", "sma200_%", "hacim_orani", "rs20", "rs60", "adx", "di_fark", "macd_hist_%", "bb_gen", "sikisma",
       "zirve_%", "perf5", "perf20", "log_hacim", "x_trend", "x_perf20", "x_atr"]
CAT = {"tur": ["kirilim_teyitli", "geri_cekilme", "destek_teyitli"], "trend": ["Yükseliş", "Düşüş"],
       "risk": ["düşük", "orta"]}


def market(dbp):
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    x = pd.read_sql("SELECT date, high, low, close FROM prices WHERE ticker='XU100' ORDER BY date", c)
    c.close()
    cl = x["close"]
    e50, e200 = cl.ewm(span=50, adjust=False).mean(), cl.ewm(span=200, adjust=False).mean()
    x["x_trend"] = np.where((cl > e50) & (e50 > e200), 1, np.where((cl < e50) & (e50 < e200), -1, 0))
    x["x_perf20"] = (cl / cl.shift(20) - 1) * 100
    tr = np.maximum(x["high"] - x["low"], np.maximum((x["high"] - cl.shift()).abs(), (x["low"] - cl.shift()).abs()))
    x["x_atr"] = tr.rolling(20).mean() / cl * 100
    x.loc[x.index < 200, "x_trend"] = np.nan       # EMA200 oturmadan rejim yok
    return x.rename(columns={"date": "tarih"})[["tarih", "x_trend", "x_perf20", "x_atr"]]


def auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    r = pd.Series(p).rank().values
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def design(df, mu=None, sd=None, med=None):
    X = df[NUM].astype(float).copy()
    if med is None:
        med = X.median()
    X = X.fillna(med)
    lo, hi = X.quantile(0.01), X.quantile(0.99)
    X = X.clip(lo, hi, axis=1) if mu is None else X
    if mu is None:
        mu, sd = X.mean(), X.std().replace(0, 1)
    X = ((X - mu) / sd).clip(-5, 5)
    for k, levels in CAT.items():
        for lv in levels:
            X[f"{k}={lv}"] = (df[k] == lv).astype(float)
    return X, mu, sd, med


def logit_fit(X, y, lam=1.0, iters=50):
    A = np.c_[np.ones(len(X)), X.values]
    w = np.zeros(A.shape[1])
    reg = np.full(A.shape[1], lam)
    reg[0] = 0
    for _ in range(iters):                       # Newton–Raphson, L2 cezalı
        p = 1 / (1 + np.exp(-A @ w))
        g = A.T @ (p - y) + reg * w
        H = (A * (p * (1 - p))[:, None]).T @ A + np.diag(reg)
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def logit_pred(w, X):
    return 1 / (1 + np.exp(-(np.c_[np.ones(len(X)), X.values] @ w)))


def bands(tr):
    return {"atr": list(tr["atr_%"].quantile([1 / 3, 2 / 3]).values)}


def keys(df, b):
    atr = np.digitize(df["atr_%"].fillna(df["atr_%"].median()), b["atr"])
    rsi = np.digitize(df["rsi"].fillna(55), [45, 70])
    return (df["tur"] + "|" + df["trend"].str[:3] + "|a" + pd.Series(atr, index=df.index).astype(str) + "|r"
            + pd.Series(rsi, index=df.index).astype(str))


def table_fit(tr):
    b = bands(tr)
    base = tr["y"].mean()
    k1 = tr["tur"]
    lvl1 = tr.groupby(k1)["y"].agg(["sum", "count"])
    p1 = (lvl1["sum"] + PRIOR_M * base) / (lvl1["count"] + PRIOR_M)
    k = keys(tr, b)
    g = tr.groupby(k)["y"].agg(["sum", "count"])
    parent = pd.Series([p1.get(s.split("|")[0], base) for s in g.index], index=g.index)
    p = (g["sum"] + PRIOR_M * parent) / (g["count"] + PRIOR_M)
    return {"b": b, "p": p, "n": g["count"], "p1": p1, "base": base}


def table_pred(m, df):
    k = keys(df, m["b"])
    fallback = df["tur"].map(m["p1"]).fillna(m["base"])
    return k.map(m["p"]).fillna(fallback).values.astype(float), k.map(m["n"]).fillna(0).values


def calib(y, p, n=5):
    q = pd.qcut(pd.Series(p).rank(method="first"), n, labels=False)
    out = []
    for i in range(n):
        s = q == i
        out.append({"dilim": i + 1, "n": int(s.sum()), "tahmin_%": round(100 * float(np.mean(p[s])), 1),
                    "gercek_%": round(100 * float(np.mean(y[s])), 1)})
    return out


def econ(te, p, frac=0.2):
    cut = np.quantile(p, 1 - frac)
    top, rest = te[p >= cut], te[p < cut]
    return {"ust_%20_n": int(len(top)), "ust_%20_tp1_%": round(100 * top["y"].mean(), 1),
            "ust_%20_ort_R": round(top["r"].mean(), 3), "ust_%20_ort_net_%": round(top["net"].mean(), 2),
            "diger_tp1_%": round(100 * rest["y"].mean(), 1), "diger_ort_R": round(rest["r"].mean(), 3),
            "tum_ort_R": round(te["r"].mean(), 3)}


def block_ci(te, p, f, reps=300, seed=1):
    """Ay blokları ile bootstrap (aynı günlerdeki ilişkili örnekler birlikte çekilir)."""
    rng = np.random.default_rng(seed)
    months = te["tarih"].str[:7].values
    ums = np.unique(months)
    idx = {m: np.where(months == m)[0] for m in ums}
    vals = []
    for _ in range(reps):
        sel = np.concatenate([idx[m] for m in rng.choice(ums, len(ums))])
        vals.append(f(te.iloc[sel], p[sel]))
    return [round(float(np.nanpercentile(vals, 5)), 3), round(float(np.nanpercentile(vals, 95)), 3)]


def evaluate(df, test_start, test_end=None, label=""):
    te_mask = (df["tarih"] >= test_start) & ((df["tarih"] < test_end) if test_end else True)
    emb = (pd.Timestamp(test_start) - pd.Timedelta(days=EMBARGO_DAYS)).date().isoformat()
    tr, te = df[df["tarih"] < emb].copy(), df[te_mask].copy()
    y_tr, y_te = tr["y"].values.astype(float), te["y"].values.astype(float)
    base = y_tr.mean()
    res = {"donem": label, "egitim_n": int(len(tr)), "egitim_ilk": tr["tarih"].min(), "egitim_son": tr["tarih"].max(),
           "test_n": int(len(te)), "test_ilk": te["tarih"].min(), "test_son": te["tarih"].max(),
           "test_hisse": int(te["ticker"].nunique()), "egitim_tp1_%": round(100 * base, 1),
           "test_tp1_%": round(100 * y_te.mean(), 1), "test_ort_R": round(te["r"].mean(), 3)}
    preds = {"taban (sabit oran)": np.full(len(te), base)}
    p_tur = tr.groupby("tur")["y"].mean()
    preds["taban (senaryo türüne göre)"] = te["tur"].map(p_tur).fillna(base).values
    tm = table_fit(tr)
    preds["A: benzer durumlar tablosu"], _ = table_pred(tm, te)
    recent = tr[tr["tarih"] >= (pd.Timestamp(emb) - pd.DateOffset(months=6)).date().isoformat()]["y"].mean()
    preds["A2: tablo, son 6 ayın oranına ölçekli"] = np.clip(preds["A: benzer durumlar tablosu"] * recent / base, 0.01, 0.99)
    res["son_6_ay_egitim_tp1_%"] = round(100 * recent, 1)
    Xtr, mu, sd, med = design(tr)
    Xte, *_ = design(te, mu, sd, med)
    lam_best, best = None, None
    # λ yalnız EĞİTİM içinde (son %20'lik zaman dilimi doğrulama) seçilir; test verisine bakılmaz
    cut = tr["tarih"].quantile(0.8) if False else sorted(tr["tarih"])[int(len(tr) * 0.8)]
    fit_m, val_m = tr["tarih"] < cut, tr["tarih"] >= cut
    for lam in (1, 10, 100, 1000):
        Xa, mua, sda, meda = design(tr[fit_m])
        Xv, *_ = design(tr[val_m], mua, sda, meda)
        w = logit_fit(Xa, y_tr[fit_m.values], lam)
        b = brier(y_tr[val_m.values], logit_pred(w, Xv))
        if best is None or b < best:
            lam_best, best = lam, b
    w = logit_fit(Xtr, y_tr, lam_best)
    preds["B: lojistik regresyon"] = logit_pred(w, Xte)
    res["lojistik_lambda"] = lam_best
    res["modeller"] = {}
    for name, p in preds.items():
        m = {"AUC": round(auc(y_te, p), 3), "Brier": round(brier(y_te, p), 4),
             "Brier_beceri_%": round(100 * (1 - brier(y_te, p) / brier(y_te, preds["taban (sabit oran)"])), 2),
             "kalibrasyon": calib(y_te, p), "ekonomik": econ(te, p)}
        if not name.startswith("taban (sabit"):
            m["AUC_%90_aralik"] = block_ci(te, p, lambda t, q: auc(t["y"].values, q))
            m["ust_%20_R_farki_%90_aralik"] = block_ci(
                te, p, lambda t, q: t["r"].values[q >= np.quantile(q, .8)].mean() - t["r"].values.mean())
        res["modeller"][name] = m
    # aynı hissenin ardışık günlerdeki neredeyse aynı sinyalleri: hisse başına 14 günde bir sinyal
    keep, lastd = [], {}
    for i, (tk, d) in enumerate(zip(te["ticker"], te["tarih"])):
        if tk not in lastd or (pd.Timestamp(d) - pd.Timestamp(lastd[tk])).days > 14:
            keep.append(i)
            lastd[tk] = d
    keep = np.array(keep)
    t1 = te.iloc[keep]
    res["tekil"] = {"n": int(len(keep)), "tp1_%": round(100 * t1["y"].mean(), 1), "ort_R": round(t1["r"].mean(), 3)}
    for name, p in preds.items():
        if not name.startswith("taban (sabit"):
            res["tekil"][name] = {"AUC": round(auc(t1["y"].values, p[keep]), 3), "ekonomik": econ(t1, p[keep])}
    coefs = sorted(zip(["sabit"] + list(Xtr.columns), w), key=lambda z: -abs(z[1]))
    res["lojistik_en_etkili"] = [(k, round(float(v), 3)) for k, v in coefs[:12]]
    # canlı "yalnız teknik" süzgecinden geçenler (trend yükseliş, skor ≥ 7, risk yüksek değil)
    live = (te["trend"] == "Yükseliş") & (te["skor"] >= 7)
    if live.sum() > 30:
        pl = preds["B: lojistik regresyon"][live.values]
        pa = preds["A: benzer durumlar tablosu"][live.values]
        t2 = te[live]
        res["canli_suzgec"] = {"n": int(live.sum()), "tp1_%": round(100 * t2["y"].mean(), 1),
                               "ort_R": round(t2["r"].mean(), 3),
                               "AUC_lojistik": round(auc(t2["y"].values, pl), 3),
                               "AUC_tablo": round(auc(t2["y"].values, pa), 3),
                               "ekonomik_lojistik": econ(t2, pl), "ekonomik_tablo": econ(t2, pa)}
    return res


def main():
    csvp, dbp, outp = sys.argv[1:4]
    raw = pd.read_csv(csvp, dtype={"tarih": str})
    summary = {"tum_tetik": int(len(raw)), "sonuc_dagilimi": raw["sonuc"].value_counts().to_dict()}
    df = raw[raw["sonuc"].isin(["SL", "TP2", "başabaş (TP1 sonrası)", "süre doldu"])].copy()
    df = df[df["risk"] != "yüksek"]               # canlıda risk "yüksek" plan önerilmez
    summary["risk_yuksek_cikarilan"] = int(((raw["risk"] == "yüksek") & raw["y"].notna()).sum())
    for c in ("y", "r", "net"):
        df[c] = df[c].astype(float)
    # fiyatı kıpırdamayan/işlem görmeyen hisselerde zarar mesafesi ~0 → R sonsuza gider (DUNYH, KSTUR): çıkarılır
    summary["stop_%1_alti_cikarilan"] = int((df["stop_%"] < 1).sum())
    df = df[df["stop_%"] >= 1].copy()
    df["r"] = df["r"].clip(-3, 6)                 # uç değerler ortalamayı bozmasın (veri hatası şüphesi)
    df["net"] = df["net"].clip(-50, 50)
    df["log_hacim"] = np.log10(df["hacim_tl"].clip(lower=1))
    df = df.merge(market(dbp), on="tarih", how="left")
    df = df[df["x_trend"].notna()]
    summary["kullanilan"] = int(len(df))
    summary["yil_dagilimi"] = df.groupby(df["tarih"].str[:4]).agg(n=("y", "size"), tp1=("y", "mean"),
                                                                 R=("r", "mean")).round(3).reset_index().to_dict("records")
    summary["tur_dagilimi"] = df.groupby("tur").agg(n=("y", "size"), tp1=("y", "mean"), R=("r", "mean")).round(3) \
        .reset_index().to_dict("records")
    summary["kilitli_ertesi_gun"] = int(df["ertesi_kilitli"].sum())
    last = df["tarih"].max()
    t12 = (pd.Timestamp(last) - pd.DateOffset(months=12)).date().isoformat()
    folds = [evaluate(df, t12, None, "son 12 ay (ana sınama)")]
    for y in ("2023", "2024"):
        if df["tarih"].min() < f"{int(y) - 1}-06-01":
            folds.append(evaluate(df, f"{y}-01-01", f"{int(y) + 1}-01-01", f"{y} yılı (ek sınama)"))
    summary["sinamalar"] = folds
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    for fo in folds:
        print("==", fo["donem"], "eğitim", fo["egitim_n"], "test", fo["test_n"], "test TP1%", fo["test_tp1_%"],
              "R", fo["test_ort_R"], "λ", fo["lojistik_lambda"])
        for k, m in fo["modeller"].items():
            print(f"  {k:32s} AUC {m['AUC']:.3f} {m.get('AUC_%90_aralik', '')}  Brier {m['Brier']:.4f} "
                  f"beceri {m['Brier_beceri_%']:+.2f}%  üst%20 TP1 {m['ekonomik']['ust_%20_tp1_%']}% "
                  f"R {m['ekonomik']['ust_%20_ort_R']} (tümü {m['ekonomik']['tum_ort_R']}) "
                  f"{m.get('ust_%20_R_farki_%90_aralik', '')}")
        if "canli_suzgec" in fo:
            print("  canlı süzgeç:", json.dumps(fo["canli_suzgec"], ensure_ascii=False))


if __name__ == "__main__":
    main()
