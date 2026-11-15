"""Aşama 6 / haber 2. aşama (Python, yapay zekâsız): KAP Özel Durum metinlerinin TP1 olasılığına katkısı.
Karşılaştırılanlar (aynı ileriye dönük sınama: son 12 ay ve 2024):
- E2: yalnız teknik (tp1_v1 ile aynı yöntem)
- R : E2 + kurallı metin okuma (olumlu/olumsuz ifade, tutar/işlem hacmi, güncelleme)
- W : E2 + kelimelerden öğrenen model (E2 skorunun üstüne, yalnız metni olan planlarda; güçlü düzenleme)
- RW: ikisi birlikte
Kullanım: python metin_model.py <repo> <arastirma.db> <etiket3.csv> <sonuc.json>
"""
import bisect
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, str(Path(__file__).parent))
from bist_haber import haber_metin as hm, tp1_model  # noqa: E402
import egit  # noqa: E402
import model as old  # noqa: E402

RULE = ["m_var", "m_pos", "m_neg", "m_net", "m_guncelleme", "m_tutar", "m_uzun"]
MIN_DOC, MIN_TK, MAX_VOCAB = 40, 10, 1500


def plan_texts(conn, df):
    kl = pd.read_sql("SELECT l.idx, l.yayin, l.hisseler, m.metin FROM kap_liste l LEFT JOIN kap_metin m ON m.idx=l.idx "
                     "WHERE l.konu LIKE '%Özel Durum Açıklaması (Genel)%' ORDER BY l.yayin", conn)
    by = {}
    for ts, hs, t in zip(kl.yayin, kl.hisseler, kl.metin):
        for tk in (hs or "").split(","):
            if tk:
                by.setdefault(tk, ([], []))
                by[tk][0].append(ts)
                by[tk][1].append(t)
    out, missing = [], []
    for tk, d in zip(df.ticker, df.tarih):
        ts, tx = by.get(tk, ([], []))
        lo = bisect.bisect_right(ts, (date.fromisoformat(d) - timedelta(days=tp1_model.HABER_GUN)).isoformat() + "T18:00:00")
        hi = bisect.bisect_right(ts, d + "T18:00:00")
        w = tx[lo:hi]
        missing.append(any(t is None for t in w))          # metni henüz indirilmemiş bildirim var
        out.append([t for t in w if t])
    return out, missing


def rates(conn):
    k = pd.read_sql("SELECT para, date, kur FROM kur ORDER BY date", conn)
    return {p: (list(g.date), list(g.kur)) for p, g in k.groupby("para")}


def rate_on(r, p, d):
    ds, ks = r[p]
    i = bisect.bisect_right(ds, d) - 1
    return ks[i] if i >= 0 else None


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_offset(X, y, off, lam):
    w = np.zeros(X.shape[1])
    for _ in range(30):
        p = 1 / (1 + np.exp(-(off + X @ w)))
        g = X.T @ (p - y) + lam * w
        H = (X * (p * (1 - p))[:, None]).T @ X + lam * np.eye(X.shape[1])
        s = np.linalg.solve(H, g)
        w -= s
        if np.abs(s).max() < 1e-7:
            break
    return w


def vocab(tok_lists, tickers):
    df_, tks = {}, {}
    for toks, tk in zip(tok_lists, tickers):
        for t in toks:
            df_[t] = df_.get(t, 0) + 1
            tks.setdefault(t, set()).add(tk)
    keep = [t for t, n in df_.items() if n >= MIN_DOC and len(tks[t]) >= MIN_TK and n <= 0.5 * len(tok_lists)]
    return sorted(keep, key=lambda t: -df_[t])[:MAX_VOCAB]


def bag(tok_lists, voc):
    ix = {t: i for i, t in enumerate(voc)}
    X = np.zeros((len(tok_lists), len(voc)))
    for r, toks in enumerate(tok_lists):
        for t in toks:
            j = ix.get(t)
            if j is not None:
                X[r, j] = 1.0
    n = X.sum(1, keepdims=True)
    return X / np.sqrt(np.maximum(n, 1))


def word_model(tr, te, p_tr, p_te):
    """Metni olan eğitim planlarında, E2 logitinin üstüne kelime ağırlıkları; λ eğitim içi son %20'de seçilir."""
    mtr, mte = tr["m_var"].values == 1, te["m_var"].values == 1
    a = tr[mtr]
    voc = vocab(a["tok"], a["ticker"])
    if len(voc) < 5 or len(a) < 200:
        return p_te.copy(), {"lambda": None, "kelime": len(voc), "olumlu": [], "olumsuz": [], "not": "veri az"}
    Xa = bag(a["tok"], voc)
    ya, offa = a["y"].values, logit(p_tr[mtr])
    order = np.argsort(a["tarih"].values, kind="stable")
    cut = int(len(order) * .8)
    fi, vi = order[:cut], order[cut:]
    best = None
    for lam in (1, 3, 10, 30, 100, 300):
        w = fit_offset(Xa[fi], ya[fi], offa[fi], lam)
        pv = 1 / (1 + np.exp(-(offa[vi] + Xa[vi] @ w)))
        b = old.brier(ya[vi], pv)
        if best is None or b < best[0]:
            best = (b, lam)
    w = fit_offset(Xa, ya, offa, best[1])
    out = p_te.copy()
    if mte.any():
        out[mte] = 1 / (1 + np.exp(-(logit(p_te[mte]) + bag(te[mte]["tok"], voc) @ w)))
    top = sorted(zip(voc, w), key=lambda z: z[1])
    return out, {"lambda": best[1], "kelime": len(voc), "olumsuz": [(k, round(float(v), 3)) for k, v in top[:15]],
                 "olumlu": [(k, round(float(v), 3)) for k, v in top[-15:][::-1]]}


def fold(df, start, end, label):
    emb = (pd.Timestamp(start) - pd.Timedelta(days=old.EMBARGO_DAYS)).date().isoformat()
    tr = df[df.tarih < emb].copy()
    te = df[(df.tarih >= start) & ((df.tarih < end) if end else True)].copy()
    base_cols = list(egit.SADE)
    m = egit.fit_e2(tr)
    p = {"E2 (yalnız teknik)": egit.predict_e2(m, te)}
    p_tr = egit.predict_e2(m, tr)
    egit.SADE = base_cols + RULE
    p["R: + kurallı metin"] = egit.predict_e2(egit.fit_e2(tr), te)
    pr_tr = egit.predict_e2(egit.fit_e2(tr), tr)
    egit.SADE = base_cols
    p["W: + öğrenen kelime"], info = word_model(tr, te, p_tr, p["E2 (yalnız teknik)"])
    p["RW: ikisi"], _ = word_model(tr, te, pr_tr, p["R: + kurallı metin"])
    y = te.y.values
    base = np.full(len(te), tr.y.mean())
    mt = te.m_var.values == 1
    res = {"donem": label, "test_n": int(len(te)), "metinli_n": int(mt.sum()),
           "metinli_tp1_%": round(100 * te.y[mt].mean(), 1), "metinsiz_tp1_%": round(100 * te.y[~mt].mean(), 1),
           "kelime_modeli": info, "modeller": {}}
    e2 = p["E2 (yalnız teknik)"]
    for k, q in p.items():
        r = {"AUC": round(old.auc(y, q), 4), "Brier_beceri_%": round(100 * (1 - old.brier(y, q) / old.brier(y, base)), 2),
             "metinli_AUC": round(old.auc(y[mt], q[mt]), 4) if mt.sum() >= 30 else float("nan"),
             "metinli_Brier_E2ye_gore_%": round(100 * (1 - old.brier(y[mt], q[mt]) / old.brier(y[mt], e2[mt])), 2)
             if mt.sum() >= 30 else float("nan"),
             "ekonomik": old.econ(te, q)}
        if k != "E2 (yalnız teknik)":
            r["AUC_farki_%90"] = old.block_ci(te, np.arange(len(te)),
                                              lambda t, ix: old.auc(t.y.values, q[ix]) - old.auc(t.y.values, e2[ix]))
        if k != "E2 (yalnız teknik)" and mt.sum() >= 30:
            r["metinli_AUC_farki_%90"] = old.block_ci(
                te[mt], np.arange(mt.sum()),
                lambda t, ix: old.auc(t.y.values, q[mt][ix]) - old.auc(t.y.values, e2[mt][ix]))
        res["modeller"][k] = r
    return res


def main():
    repo, dbp, csvp, outp = sys.argv[1:5]
    conn = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True, timeout=60)
    df = egit.load_df(csvp)
    texts, missing = plan_texts(conn, df)
    r = rates(conn)
    feats, toks = [], []
    for (tk, d, vol), tx in zip(df[["ticker", "tarih", "hacim_tl"]].itertuples(index=False), texts):
        feats.append(hm.rule_features(tx, vol, rate_on(r, "USD", d), rate_on(r, "EUR", d)))
        toks.append(hm.tokens(tx))
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(feats)], axis=1)
    df["tok"] = toks
    # metin indirmesi bitmediyse: penceresinde metni inmemiş bildirim olan planlar çıkarılır (yanlış "metinsiz" olmasın)
    df["eksik"] = missing
    print("plan", len(df), "metni eksik (çıkarıldı)", int(df.eksik.sum()), flush=True)
    df = df[~df.eksik].copy()
    print("kalan", len(df), "metinli", int(df.m_var.sum()), flush=True)
    last = df.tarih.max()
    t12 = (pd.Timestamp(last) - pd.DateOffset(months=12)).date().isoformat()
    folds = [fold(df, t12, None, "son 12 ay (ana sınama)")]
    if df.tarih.min() < "2023-06-01" and last >= "2024-12-31":
        folds.append(fold(df, "2024-01-01", "2025-01-01", "2024 (ek sınama)"))
    for fo in folds:
        print("==", fo["donem"], "test", fo["test_n"], "metinli", fo["metinli_n"], "TP1 metinli/metinsiz",
              fo["metinli_tp1_%"], fo["metinsiz_tp1_%"])
        for k, m in fo["modeller"].items():
            print(f"  {k:22s} AUC {m['AUC']:.4f} {m.get('AUC_farki_%90', '')} Brier+ {m['Brier_beceri_%']:+.2f}% | metinli "
                  f"AUC {m['metinli_AUC']:.4f} {m.get('metinli_AUC_farki_%90', '')} Brier(E2ye) "
                  f"{m['metinli_Brier_E2ye_gore_%']:+.2f}% | üst%20 R {m['ekonomik']['ust_%20_ort_R']}")
        print("  kelime:", fo["kelime_modeli"]["lambda"], fo["kelime_modeli"]["kelime"],
              "olumlu", fo["kelime_modeli"]["olumlu"][:8], "olumsuz", fo["kelime_modeli"]["olumsuz"][:8])
    sub = df[df.m_var == 1]
    print("kural ile basit bakış (metinli):", sub.groupby(np.sign(sub.m_net))["y"].agg(["size", "mean"]).round(3).to_dict())
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(folds, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
