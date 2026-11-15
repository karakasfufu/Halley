"""Aşama 6 model geliştirme. Denenenler (aynı ileriye dönük sınama): artırımlı karar ağaçları (gradient boosting,
derinlik 2, yalnız numpy), yakın döneme ağırlık, Platt kalibrasyonu, yeni girdili lojistik ve birleşimler.
Seçilen başlangıç sürümü "E2" = benzer durumlar tablosu + 10 girdili sade lojistik, ortalaması (ağaçlar ve
kalibrasyon sınamada kazandırmadı). --kaydet: E2 TÜM veriyle eğitilip bist_haber/modeller/tp1_v1.json'a yazılır.
Kullanım: python egit.py <repo> <etiket.csv> <sonuc.json> [--kaydet]
"""
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import model as old  # noqa: E402  (tablo/lojistik ve ölçüm fonksiyonları)

FEATS = ["rr1", "stop_%", "tp1_%", "stop_atr", "tp1_atr", "skor", "p_trend", "p_rsi", "p_ivme", "p_hacim",
         "p_goreli_guc", "rsi", "atr_%", "sma50_%", "sma200_%", "hacim_orani", "rs20", "rs60", "adx", "di_fark",
         "macd_hist_%", "bb_gen", "sikisma", "zirve_%", "dip_%", "ema20_atr", "perf1", "perf5", "perf20", "log_hacim",
         "kilitli", "trend_yuk", "trend_dus", "risk_orta", "tur_kirilim_teyitli", "tur_geri_cekilme",
         "tur_destek_teyitli", "x_trend", "x_perf20", "x_atr"]
LR, DEPTH, LAM, MIN_LEAF, MAX_TREES, NBINS = 0.05, 2, 50.0, 300, 600, 32


# ---------------------------------------------------------------- hazırlık
class Prep:
    def __init__(self, df):
        X = df[FEATS].astype(float)
        self.med = X.median().fillna(0)
        Xf = X.fillna(self.med)
        self.lo, self.hi = Xf.quantile(0.01), Xf.quantile(0.99)

    def __call__(self, df):
        X = df[FEATS].astype(float).fillna(self.med)
        return X.clip(self.lo, self.hi, axis=1).values


# ---------------------------------------------------------------- artırımlı ağaçlar
def _edges(X):
    out = []
    for j in range(X.shape[1]):
        e = np.unique(np.quantile(X[:, j], np.linspace(0, 1, NBINS + 1)[1:-1]))
        out.append(e)
    return out


def _grow(B, edges, g, h, idx, depth):
    G, H = g[idx].sum(), h[idx].sum()
    leaf = {"v": float(-G / (H + LAM))}
    if depth == 0 or len(idx) < 2 * MIN_LEAF:
        return leaf
    best = None
    cnt_all = None
    for j, e in enumerate(edges):
        if not len(e):
            continue
        nb = len(e) + 1
        bj = B[idx, j]
        gs = np.bincount(bj, g[idx], nb).cumsum()
        hs = np.bincount(bj, h[idx], nb).cumsum()
        cs = np.bincount(bj, None, nb).cumsum()
        gl, hl, cl = gs[:-1], hs[:-1], cs[:-1]
        ok = (cl >= MIN_LEAF) & (len(idx) - cl >= MIN_LEAF)
        if not ok.any():
            continue
        gain = gl ** 2 / (hl + LAM) + (G - gl) ** 2 / (H - hl + LAM) - G ** 2 / (H + LAM)
        gain[~ok] = -1
        k = int(gain.argmax())
        if gain[k] > 0 and (best is None or gain[k] > best[0]):
            best = (gain[k], j, k)
    if best is None:
        return leaf
    _, j, k = best
    left = idx[B[idx, j] <= k]
    right = idx[B[idx, j] > k]
    return {"f": j, "e": float(edges[j][k]), "l": _grow(B, edges, g, h, left, depth - 1),
            "r": _grow(B, edges, g, h, right, depth - 1)}


def _apply(tree, X):
    out = np.empty(len(X))
    stack = [(tree, np.arange(len(X)))]
    while stack:
        node, ix = stack.pop()
        if "v" in node:
            out[ix] = node["v"]
            continue
        m = X[ix, node["f"]] <= node["e"]
        stack.append((node["l"], ix[m]))
        stack.append((node["r"], ix[~m]))
    return out


def gbm_fit(X, y, w, n_trees, Xv=None, yv=None):
    """Döndürür: (başlangıç, ağaçlar, doğrulama kaybı listesi)."""
    edges = _edges(X)
    B = np.column_stack([np.searchsorted(e, X[:, j], side="left") for j, e in enumerate(edges)])
    p0 = np.clip(np.average(y, weights=w), 1e-4, 1 - 1e-4)
    base = float(np.log(p0 / (1 - p0)))
    F = np.full(len(X), base)
    Fv = np.full(len(Xv), base) if Xv is not None else None
    trees, losses = [], []
    idx = np.arange(len(X))
    for _ in range(n_trees):
        p = 1 / (1 + np.exp(-F))
        tr = _grow(B, edges, w * (p - y), w * p * (1 - p), idx, DEPTH)
        trees.append(tr)
        F += LR * _apply(tr, X)
        if Xv is not None:
            Fv += LR * _apply(tr, Xv)
            pv = np.clip(1 / (1 + np.exp(-Fv)), 1e-6, 1 - 1e-6)
            losses.append(float(-np.mean(yv * np.log(pv) + (1 - yv) * np.log(1 - pv))))
    return base, trees, losses


def gbm_raw(base, trees, X):
    return base + LR * sum(_apply(t, X) for t in trees)


def platt(z, y):
    a, b = 1.0, 0.0
    for _ in range(50):
        p = 1 / (1 + np.exp(-(a * z + b)))
        g = np.array([((p - y) * z).sum(), (p - y).sum()])
        hw = p * (1 - p)
        H = np.array([[(hw * z * z).sum(), (hw * z).sum()], [(hw * z).sum(), hw.sum()]]) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, g)
        a, b = a - step[0], b - step[1]
        if np.abs(step).max() < 1e-9:
            break
    return float(a), float(b)


def weights(dates, end, halflife):
    if not halflife:
        return np.ones(len(dates))
    age = (pd.Timestamp(end) - pd.to_datetime(dates)).dt.days.values
    return 0.5 ** (age / halflife)


def train(tr, halflife, calibrate=True):
    """tr içinde zaman sıralı %80/%20: ağaç sayısı ve Platt doğrulamada seçilir; sonra tr'nin tümüyle yeniden eğitilir."""
    tr = tr.sort_values("tarih")
    cut = tr["tarih"].iloc[int(len(tr) * 0.8)]
    emb = (pd.Timestamp(cut) - pd.Timedelta(days=old.EMBARGO_DAYS)).date().isoformat()
    a_, v_ = tr[tr["tarih"] < emb], tr[tr["tarih"] >= cut]
    prep = Prep(a_)
    Xa, Xv = prep(a_), prep(v_)
    ya, yv = a_["y"].values, v_["y"].values
    base, trees, losses = gbm_fit(Xa, ya, weights(a_["tarih"], a_["tarih"].max(), halflife), MAX_TREES, Xv, yv)
    n = int(np.argmin(losses)) + 1
    ab = platt(gbm_raw(base, trees[:n], Xv), yv) if calibrate else (1.0, 0.0)
    prep = Prep(tr)
    X = prep(tr)
    base, trees, _ = gbm_fit(X, tr["y"].values, weights(tr["tarih"], tr["tarih"].max(), halflife), n)
    return {"prep": prep, "base": base, "trees": trees, "n": n, "ab": ab}


def predict(m, df):
    z = gbm_raw(m["base"], m["trees"], m["prep"](df))
    a, b = m["ab"]
    return 1 / (1 + np.exp(-(a * z + b)))


# ---------------------------------------------------------------- E2: tablo + sade lojistik
SADE = ["tur_kirilim_teyitli", "tur_destek_teyitli", "x_trend", "x_perf20", "rsi", "skor", "tp1_atr", "stop_atr",
        "rs20", "perf20"]


def _std(tr):
    a = tr[SADE].astype(float)
    med = a.median().fillna(0)
    a = a.fillna(med)
    lo, hi = a.quantile(.01), a.quantile(.99)
    a = a.clip(lo, hi, axis=1)
    return med, lo, hi, a.mean(), a.std().replace(0, 1)


def _zs(df, st):
    med, lo, hi, mu, sd = st
    return (df[SADE].astype(float).fillna(med).clip(lo, hi, axis=1) - mu) / sd


def fit_e2(tr):
    """Döndürür: model dosyasındaki biçimde {"tablo", "lojistik"} (λ yalnız eğitim içi son %20 doğrulamada seçilir)."""
    tr = tr.sort_values("tarih")
    cut = tr["tarih"].iloc[int(len(tr) * .8)]
    a_, v_ = tr[tr["tarih"] < cut], tr[tr["tarih"] >= cut]
    best = None
    for lam in (1, 10, 100, 1000, 10000):
        st = _std(a_)
        w = old.logit_fit(_zs(a_, st), a_["y"].values, lam)
        b = old.brier(v_["y"].values, old.logit_pred(w, _zs(v_, st)))
        if best is None or b < best[0]:
            best = (b, lam)
    st = _std(tr)
    w = old.logit_fit(_zs(tr, st), tr["y"].values, best[1])
    med, lo, hi, mu, sd = st
    tm = old.table_fit(tr)
    g = tr.groupby(old.keys(tr, tm["b"]))["y"].mean()
    tablo = {"atr_sinir": [float(x) for x in tm["b"]["atr"]], "atr_ortanca": float(tr["atr_%"].median()),
             "oran": {k: float(v) for k, v in tm["p"].items()}, "sayi": {k: int(v) for k, v in tm["n"].items()},
             "ham": {k: round(float(v), 4) for k, v in g.items()},
             "tur_orani": {k: float(v) for k, v in tm["p1"].items()}, "genel": float(tm["base"])}
    lojistik = {"girdiler": SADE, "lambda": best[1], "sabit": float(w[0]), "agirlik": [float(x) for x in w[1:]],
                "ortanca": [float(x) for x in med], "alt": [float(x) for x in lo], "ust": [float(x) for x in hi],
                "ort": [float(x) for x in mu], "sd": [float(x) for x in sd]}
    return {"tablo": tablo, "lojistik": lojistik}


def predict_e2(m, df):
    tb, lg = m["tablo"], m["lojistik"]
    atr = df["atr_%"].fillna(tb["atr_ortanca"]).values
    rsi = df["rsi"].fillna(55).values
    key = (df["tur"] + "|" + df["trend"].str[:3] + "|a" + pd.Series(np.digitize(atr, tb["atr_sinir"]), index=df.index)
           .astype(str) + "|r" + pd.Series(np.digitize(rsi, [45, 70]), index=df.index).astype(str))
    pt = key.map(tb["oran"]).fillna(df["tur"].map(tb["tur_orani"])).fillna(tb["genel"]).values
    X = df[SADE].astype(float)
    X = X.fillna(pd.Series(lg["ortanca"], index=SADE)).clip(pd.Series(lg["alt"], index=SADE),
                                                            pd.Series(lg["ust"], index=SADE), axis=1)
    z = lg["sabit"] + ((X - np.array(lg["ort"])) / np.array(lg["sd"])).values @ np.array(lg["agirlik"])
    return (pt + 1 / (1 + np.exp(-z))) / 2


# ---------------------------------------------------------------- sınama
VARIANTS = {"C: artırımlı ağaç": (None, False), "C+k: ağaç + kalibrasyon": (None, True),
            "D: ağaç + yakın dönem ağırlığı (1 yıl) + kalibrasyon": (365, True)}


def metrics(te, p, base_p):
    y = te["y"].values
    return {"AUC": round(old.auc(y, p), 3), "AUC_%90_aralik": old.block_ci(te, p, lambda t, q: old.auc(t["y"].values, q)),
            "Brier_beceri_%": round(100 * (1 - old.brier(y, p) / old.brier(y, base_p)), 2),
            "kalibrasyon": old.calib(y, p), "ekonomik": old.econ(te, p),
            "ust_%20_R_farki_%90_aralik": old.block_ci(
                te, p, lambda t, q: t["r"].values[q >= np.quantile(q, .8)].mean() - t["r"].values.mean())}


def dedup_idx(te):
    keep, lastd = [], {}
    for i, (tk, d) in enumerate(zip(te["ticker"], te["tarih"])):
        if tk not in lastd or (pd.Timestamp(d) - pd.Timestamp(lastd[tk])).days > 14:
            keep.append(i)
            lastd[tk] = d
    return np.array(keep)


def fold(df, start, end, label):
    emb = (pd.Timestamp(start) - pd.Timedelta(days=old.EMBARGO_DAYS)).date().isoformat()
    tr = df[df["tarih"] < emb].copy()
    te = df[(df["tarih"] >= start) & ((df["tarih"] < end) if end else True)].copy()
    base = tr["y"].mean()
    preds = {"taban (sabit oran)": np.full(len(te), base),
             "taban (senaryo türüne göre)": te["tur"].map(tr.groupby("tur")["y"].mean()).fillna(base).values}
    preds["A: benzer durumlar tablosu"], _ = old.table_pred(old.table_fit(tr), te)
    Xtr, mu, sd, med = old.design(tr)
    Xte, *_ = old.design(te, mu, sd, med)
    preds["B: lojistik regresyon"] = old.logit_pred(old.logit_fit(Xtr, tr["y"].values.astype(float), 1.0), Xte)
    preds["E2: tablo + sade lojistik (seçilen)"] = predict_e2(fit_e2(tr), te)
    trees = {}
    for name, (hl, cal) in VARIANTS.items():
        m = train(tr, hl, cal)
        trees[name] = m["n"]
        preds[name] = predict(m, te)
    res = {"donem": label, "egitim_n": int(len(tr)), "test_n": int(len(te)), "test_tp1_%": round(100 * te["y"].mean(), 1),
           "egitim_tp1_%": round(100 * base, 1), "agac_sayisi": trees, "modeller": {}}
    k = dedup_idx(te)
    t1 = te.iloc[k]
    for name, p in preds.items():
        m = metrics(te, p, preds["taban (sabit oran)"])
        m["tekil"] = {"n": int(len(k)), "AUC": round(old.auc(t1["y"].values, p[k]), 3), "ekonomik": old.econ(t1, p[k])}
        res["modeller"][name] = m
    return res


def load_df(csvp):
    raw = pd.read_csv(csvp, dtype={"tarih": str})
    df = raw[raw["sonuc"].isin(["SL", "TP2", "başabaş (TP1 sonrası)", "süre doldu"]) & (raw["risk"] != "yüksek")].copy()
    for c in ("y", "r", "net"):
        df[c] = df[c].astype(float)
    df = df[df["stop_%"] >= 1].copy()
    df["r"] = df["r"].clip(-3, 6)
    df["net"] = df["net"].clip(-50, 50)
    df = df[df["x_trend"].notna()].copy()
    return df.sort_values(["tarih", "ticker"]).reset_index(drop=True)


def export(m, df, out_path, summary):
    recent = df[df["tarih"] >= (pd.Timestamp(df["tarih"].max()) - pd.DateOffset(months=12)).date().isoformat()]
    pr = predict_e2(m, recent)
    doc = {"surum": "tp1_v1", "egitildi": date.today().isoformat(), "model": "E2: benzer durumlar tablosu + sade lojistik",
           "aciklama": "TP1'in SL'den önce görülme olasılığı; yalnız teknik veri; bilgi amaçlı, seçim/eşik değiştirmez.",
           "egitim": {"plan": int(len(df)), "hisse": int(df["ticker"].nunique()), "ilk": df["tarih"].min(),
                      "son": df["tarih"].max(), "tp1_%": round(100 * df["y"].mean(), 1),
                      "son_12_ay_tp1_%": round(100 * recent["y"].mean(), 1)},
           **m, "bantlar": [float(np.quantile(pr, 0.2)), float(np.quantile(pr, 0.8))], "sinama": summary}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    return doc, pr


def main():
    repo, csvp, outp = sys.argv[1:4]
    df = load_df(csvp)
    last = df["tarih"].max()
    t12 = (pd.Timestamp(last) - pd.DateOffset(months=12)).date().isoformat()
    folds = [fold(df, t12, None, "son 12 ay (ana sınama)"), fold(df, "2024-01-01", "2025-01-01", "2024 (ek sınama)")]
    for fo in folds:
        print("==", fo["donem"], "eğitim", fo["egitim_n"], "test", fo["test_n"], "TP1%", fo["test_tp1_%"], fo["agac_sayisi"])
        for k, m in fo["modeller"].items():
            e = m["ekonomik"]
            print(f"  {k:52s} AUC {m['AUC']:.3f} {m['AUC_%90_aralik']} Brier+ {m['Brier_beceri_%']:+.2f}% "
                  f"üst%20 TP1 {e['ust_%20_tp1_%']}% R {e['ust_%20_ort_R']} (diğer {e['diger_ort_R']}) "
                  f"fark {m['ust_%20_R_farki_%90_aralik']} | tekil AUC {m['tekil']['AUC']} "
                  f"R {m['tekil']['ekonomik']['ust_%20_ort_R']}/{m['tekil']['ekonomik']['diger_ort_R']}")
            print("     kalibrasyon:", [(c["tahmin_%"], c["gercek_%"]) for c in m["kalibrasyon"]])
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(folds, f, ensure_ascii=False, indent=1, default=str)
    if "--kaydet" in sys.argv:
        name = "E2: tablo + sade lojistik (seçilen)"
        keep = ("AUC", "AUC_%90_aralik", "Brier_beceri_%")
        summ = [{"donem": fo["donem"], "test_n": fo["test_n"], "test_tp1_%": fo["test_tp1_%"],
                 **{k: dict({kk: v[kk] for kk in keep}, ust_20_ort_R=v["ekonomik"]["ust_%20_ort_R"],
                            diger_ort_R=v["ekonomik"]["diger_ort_R"], ust_20_tp1=v["ekonomik"]["ust_%20_tp1_%"],
                            kalibrasyon=v["kalibrasyon"])
                    for k, v in fo["modeller"].items() if k in (name, "taban (senaryo türüne göre)")}} for fo in folds]
        path = __import__("pathlib").Path(repo) / "bist_haber" / "modeller" / "tp1_v1.json"
        path.parent.mkdir(exist_ok=True)
        doc, pr = export(fit_e2(df), df, path, summ)
        print("kaydedildi:", path, "λ", doc["lojistik"]["lambda"], "bantlar", [round(x, 3) for x in doc["bantlar"]],
              "grup", len(doc["tablo"]["oran"]), "boyut", path.stat().st_size)
        print("ağırlıklar:", dict(zip(SADE, [round(x, 3) for x in doc["lojistik"]["agirlik"]])))


if __name__ == "__main__":
    main()
