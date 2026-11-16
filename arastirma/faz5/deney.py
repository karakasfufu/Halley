"""FAZ 5 deneyi (ön kayıt: deney_tanimi.json, commit 6430231): R0 / R1 / M1, zaman sıralı bölümler ve ambargo,
ön işleme ve λ yalnız eğitimden. Yerel CPU, numpy. Hiçbir model dosyaya yazılmaz ya da etkinleştirilmez.
Kullanım: python deney.py <repo> <hedefler.csv> <cikti.json>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HEDEFLER = ["H5_tp1", "H10_tp1", "H5_pozitif", "H10_pozitif"]
AMBARGO_GUN, IC_AMBARGO_GUN = 45, 20
LAMBDALAR = (1, 10, 100, 1000)
BOLUMLER = {"ana_sinama": ("2025-11-14", None), "ek_sinama": ("2024-01-01", "2025-01-01")}


def _mod(repo):
    sys.path.insert(0, str(Path(repo) / "arastirma" / "asama6"))
    import model as m
    return m


def bolum(df, bas, son):
    """Eğitim: test başlangıcından AMBARGO_GUN takvim günü öncesine kadar; test: [bas, son)."""
    emb = (pd.Timestamp(bas) - pd.Timedelta(days=AMBARGO_GUN)).date().isoformat()
    tr = df[df["tarih"] < emb]
    te = df[(df["tarih"] >= bas) & ((df["tarih"] < son) if son else True)]
    return tr, te, emb


def logloss(y, p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def m1_uydur(m, tr, hedef):
    """λ yalnız eğitim içinde: son %20 doğrulama, aralarında IC_AMBARGO_GUN ambargo; ön işleme yalnız eğitimden."""
    tarihler = sorted(tr["tarih"])
    kes = tarihler[int(len(tarihler) * 0.8)]
    fit_son = (pd.Timestamp(kes) - pd.Timedelta(days=IC_AMBARGO_GUN)).date().isoformat()
    fit, val = tr[tr["tarih"] < fit_son], tr[tr["tarih"] >= kes]
    en_iyi = None
    for lam in LAMBDALAR:
        Xa, mu, sd, med = m.design(fit)
        Xv, *_ = m.design(val, mu, sd, med)
        w = m.logit_fit(Xa, fit[hedef].values.astype(float), lam)
        b = m.brier(val[hedef].values.astype(float), m.logit_pred(w, Xv))
        if en_iyi is None or b < en_iyi[1]:
            en_iyi = (lam, b)
    X, mu, sd, med = m.design(tr)
    w = m.logit_fit(X, tr[hedef].values.astype(float), en_iyi[0])
    return {"w": w, "mu": mu, "sd": sd, "med": med, "lam": en_iyi[0], "ic_bolum": [fit_son, kes]}


def m1_tahmin(m, model, te):
    X, *_ = m.design(te, model["mu"], model["sd"], model["med"])
    return m.logit_pred(model["w"], X)


def olc(m, te, hedef, p, p_ref, n_ufuk):
    y = te[hedef].values.astype(float)
    tey = te.assign(y=y, r=te[f"H{n_ufuk}_R"].values, net=te[f"H{n_ufuk}_net_%"].values)
    skill = lambda t, q: 1 - m.brier(t["y"].values, q) / m.brier(t["y"].values, p_ref[np.asarray(t.index.map(pos), dtype=int)])
    pos = {ix: i for i, ix in enumerate(te.index)}
    out = {"Brier": round(m.brier(y, p), 5), "LogLoss": round(logloss(y, p), 5), "AUC": round(m.auc(y, p), 4),
           "kalibrasyon": m.calib(y, np.asarray(p)), "AUC_%90": m.block_ci(tey, np.asarray(p), lambda t, q: m.auc(t["y"].values, q))}
    if p_ref is not None:
        out["Brier_beceri_R1e_gore"] = round(1 - m.brier(y, p) / m.brier(y, p_ref), 4)
        out["Brier_beceri_%90"] = m.block_ci(tey, np.asarray(p), skill)
    cut = np.quantile(p, 0.8)
    ust, kalan = tey[p >= cut], tey[p < cut]
    out["ekonomik_tekil"] = {"ufuk": n_ufuk, "ust_%20_n": int(len(ust)), "ust_%20_ort_net_%": round(ust["net"].mean(), 3),
                             "kalan_ort_net_%": round(kalan["net"].mean(), 3), "ust_%20_ort_R": round(ust["r"].mean(), 3),
                             "kalan_ort_R": round(kalan["r"].mean(), 3)}
    return out


def betimle(repo, df):
    """Hedef × strateji türü betimlemesi (tüm ortak örneklem): n, farklı gün, aynı hisse tekrar %, oran/ortalama ve %95
    gün kümesi bootstrap (FAZ 4 rejim_analiz.kume_bootstrap)."""
    sys.path.insert(0, str(Path(repo) / "arastirma" / "faz4"))
    import rejim_analiz as ra
    out = {}
    for tur, g in df.groupby("tur"):
        d = {"n": int(len(g)), "gun": int(g["tarih"].nunique()), "ayni_hisse_tekrar_%": round(100 * g["tekrar_10"].mean(), 1)}
        for k in ("H5_tp1", "H10_tp1", "H5_pozitif", "H10_pozitif", "H5_net_%", "H10_net_%", "H5_R", "H10_R"):
            v = g[k].astype(float)
            d[k] = round(float(v.mean()) * (100 if not k.endswith(("_%", "_R")) else 1), 3)
            ci = ra.kume_bootstrap(list(zip(g["tarih"], v)), ra.ortalama, tekrar=1000)
            d[k + "_%95"] = [round(x * (100 if not k.endswith(("_%", "_R")) else 1), 3) for x in ci] if ci else None
        d["takvim_boslugu_%"] = round(100 * g["H10_takvim_boslugu"].mean(), 2)
        out[tur] = d
    return out


def calistir(repo, csv_yolu):
    m = _mod(repo)
    df = pd.read_csv(csv_yolu, dtype={"tarih": str})
    df = df[df["x_trend"].notna()].sort_values(["tarih", "ticker"]).reset_index(drop=True)
    sonuc = {"ornek": int(len(df)), "ornek_gun": int(df["tarih"].nunique()), "bolumler": {},
             "betimleme_tum_ornek": betimle(repo, df)}
    for ad, (bas, son) in BOLUMLER.items():
        tr, te, emb = bolum(df, bas, son)
        b_out = {"egitim_n": int(len(tr)), "egitim_ilk": tr["tarih"].min(), "egitim_son": tr["tarih"].max(), "ambargo_sinir": emb,
                 "test_n": int(len(te)), "test_gun": int(te["tarih"].nunique()), "test_ilk": te["tarih"].min(),
                 "test_son": te["tarih"].max(), "test_ayni_hisse_tekrar_%": round(100 * te["tekrar_10"].mean(), 1),
                 "hedefler": {}}
        for h in HEDEFLER:
            n_ufuk = int(h[1:].split("_")[0])
            y_tr = tr[h].values.astype(float)
            p0 = np.full(len(te), y_tr.mean())
            p1 = te["tur"].map(tr.groupby("tur")[h].mean()).fillna(y_tr.mean()).values
            mdl = m1_uydur(m, tr, h)
            p2 = m1_tahmin(m, mdl, te)
            r = {"egitim_orani_%": round(100 * y_tr.mean(), 2), "test_orani_%": round(100 * te[h].mean(), 2),
                 "R0_sabit": olc(m, te, h, p0, None, n_ufuk), "R1_tur": olc(m, te, h, p1, None, n_ufuk),
                 "M1_lojistik": olc(m, te, h, p2, p1, n_ufuk), "M1_lambda": mdl["lam"], "M1_ic_bolum": mdl["ic_bolum"]}
            r["R1_tur"]["Brier_beceri_R0a_gore"] = round(1 - m.brier(te[h].values, p1) / m.brier(te[h].values, p0), 4)
            b_out["hedefler"][h] = r
            print(ad, h, "AUC", r["M1_lojistik"]["AUC"], r["M1_lojistik"]["AUC_%90"], "beceri",
                  r["M1_lojistik"]["Brier_beceri_R1e_gore"], r["M1_lojistik"]["Brier_beceri_%90"], flush=True)
        sonuc["bolumler"][ad] = b_out
    karar = {}
    for h in HEDEFLER:
        kos = []
        for ad in BOLUMLER:
            x = sonuc["bolumler"][ad]["hedefler"][h]["M1_lojistik"]
            kos.append(x["AUC_%90"][0] > 0.5 and x["Brier_beceri_R1e_gore"] > 0 and x["Brier_beceri_%90"][0] > 0)
        karar[h] = "katkı" if all(kos) else "katkı yok"
    sonuc["on_kayitli_karar"] = karar
    return sonuc


def main():
    repo, csv_yolu, cikti = sys.argv[1:4]
    s = calistir(repo, csv_yolu)
    Path(cikti).write_text(json.dumps(s, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("karar:", s["on_kayitli_karar"])


if __name__ == "__main__":
    main()
