"""Aşama 7 değerlendirme: hazır modellerin (Chronos-Bolt, Kronos) çıktıları tp1_v1'e (E2) göre ne katıyor?
Tasarım (geleceği görme yok):
- E2 her sınama dönemi için o dönemden önceki verilerle eğitilir (Aşama 6 ile aynı; 45 gün ambargo).
- (a) Tek başına: hazır model çıktısının AUC'si (eğitim gerekmez), iki dönemde.
- (b) Birleşik (aşama 8 ilk denemesi): 2024 planlarında [E2 logiti + hazır model girdileri] lojistik regresyonu
  eğitilir (oradaki E2 tahmini de dönem dışıdır) → son 12 ayda sınanır; taban E2.
Planlar hisse başına 14 günde bir (tekil). Kullanım: python degerlendir.py <etiket3.csv> <planlar.csv> <model.csv> <ad>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asama6"))
import egit  # noqa: E402
import model as old  # noqa: E402

etiket, planlar, mcsv, ad = sys.argv[1:5]
df = egit.load_df(etiket)
pl = pd.read_csv(planlar, dtype={"tarih": str})
mo = pd.read_csv(mcsv, dtype={"tarih": str})
feats = [c for c in mo.columns if c not in ("ticker", "tarih", "k_n", "k_gecersiz")]
last = df.tarih.max()
t12 = (pd.Timestamp(last) - pd.DateOffset(months=12)).date().isoformat()


def e2_for(start, end):
    emb = (pd.Timestamp(start) - pd.Timedelta(days=old.EMBARGO_DAYS)).date().isoformat()
    m = egit.fit_e2(df[df.tarih < emb])
    te = df[(df.tarih >= start) & ((df.tarih < end) if end else True)]
    return te.assign(e2=egit.predict_e2(m, te))


te12, te24 = e2_for(t12, None), e2_for("2024-01-01", "2025-01-01")
out = {"model": ad, "girdiler": feats}
sets = {}
for lab, te in (("son12", te12), ("2024", te24)):
    s = te.merge(pl[["ticker", "tarih"]], on=["ticker", "tarih"]).merge(mo, on=["ticker", "tarih"])
    s = s.dropna(subset=[feats[0]])
    sets[lab] = s
    y = s.y.values
    r = {"n": int(len(s)), "tp1_%": round(100 * y.mean(), 1), "E2_AUC": round(old.auc(y, s.e2.values), 4)}
    for f in feats:
        v = s[f].astype(float).fillna(s[f].astype(float).median()).values
        r[f + "_AUC"] = round(old.auc(y, v), 4)
    if "k_gecersiz" in s:
        r["gecersiz_yol_%"] = round(100 * s.k_gecersiz.sum() / s.k_n.sum(), 2)
    out[lab] = r
# birleşik: 2024'te eğit → son 12 ayda sına
tr, te = sets["2024"], sets["son12"]


def X(d, mu=None, sd=None, med=None):
    a = d[feats].astype(float)
    med = a.median() if med is None else med
    a = a.fillna(med)
    mu = a.mean() if mu is None else mu
    sd = a.std().replace(0, 1) if sd is None else sd
    return ((a - mu) / sd).clip(-5, 5), mu, sd, med


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


Xtr, mu, sd, med = X(tr)
Xte, *_ = X(te, mu, sd, med)
res = {}
for lam in (1, 10, 100):
    A = np.c_[logit(tr.e2.values), Xtr.values]
    w = np.zeros(A.shape[1] + 1)
    Ab = np.c_[np.ones(len(A)), A]
    for _ in range(40):
        p = 1 / (1 + np.exp(-Ab @ w))
        reg = np.full(len(w), lam)
        reg[:2] = 0
        g = Ab.T @ (p - tr.y.values) + reg * w
        Hm = (Ab * (p * (1 - p))[:, None]).T @ Ab + np.diag(reg) + 1e-9 * np.eye(len(w))
        st = np.linalg.solve(Hm, g)
        w -= st
        if np.abs(st).max() < 1e-8:
            break
    pt = 1 / (1 + np.exp(-(np.c_[np.ones(len(te)), logit(te.e2.values), Xte.values] @ w)))
    y = te.y.values
    res[lam] = {"AUC": round(old.auc(y, pt), 4), "Brier_E2ye_gore_%": round(100 * (1 - old.brier(y, pt) / old.brier(y, te.e2.values)), 2),
                "AUC_farki_%90": old.block_ci(te, np.arange(len(te)), lambda t, ix: old.auc(t.y.values, pt[ix]) - old.auc(t.y.values, te.e2.values[ix])),
                "ekonomik": old.econ(te, pt), "agirlik": dict(zip(["sabit", "E2"] + feats, [round(float(x), 3) for x in w]))}
out["birlesik_2024_egit_son12_sina"] = res
# kontrol: yalnız E2'nin 2024'te yeniden ölçeklenmesi (hazır model girdisi YOK) — Brier kazancı nereden geliyor?
a_, b_ = 1.0, 0.0
zt, yt = logit(tr.e2.values), tr.y.values
for _ in range(50):
    p = 1 / (1 + np.exp(-(a_ * zt + b_)))
    g = np.array([((p - yt) * zt).sum(), (p - yt).sum()])
    hw = p * (1 - p)
    Hm = np.array([[(hw * zt * zt).sum(), (hw * zt).sum()], [(hw * zt).sum(), hw.sum()]])
    st = np.linalg.solve(Hm, g)
    a_, b_ = a_ - st[0], b_ - st[1]
pc = 1 / (1 + np.exp(-(a_ * logit(te.e2.values) + b_)))
out["kontrol_yalniz_E2_olcek"] = {"AUC": round(old.auc(te.y.values, pc), 4),
                                  "Brier_E2ye_gore_%": round(100 * (1 - old.brier(te.y.values, pc) / old.brier(te.y.values, te.e2.values)), 2)}
out["E2_son12_ekonomik"] = old.econ(te, te.e2.values)
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
