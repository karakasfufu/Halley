"""FAZ 3 (araştırma; yalnız okur): FAZ 2 kabul dosyalarından bağımsız metrik doğrulaması, ek metrikler,
dağılımlar ve MAE/MFE. Simülasyon yeniden çalıştırılmaz.
Kullanım: python faz3_hesap.py <repo> <arastirma.db> <kabul_klasoru> <cikti.json>"""
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ESLES = {"toplam_getiri_%": None, "azami_dusus_%": "mdd_%", "sortino_yillik": "sortino", "sharpe_yillik": "sharpe",
         "kar_faktoru": "pf", "en_uzun_ardisik_kayip": "en_uzun_ardisik_kayip", "en_uzun_dusus_suresi_gun":
         "en_uzun_dusus_gun", "kapanan_islem": "kapanan", "ort_R": "ort_R", "kazanma_orani_%": "kazanma_%"}
YUV = {"azami_dusus_%": 2, "sortino_yillik": 3, "sharpe_yillik": 3, "kar_faktoru": 3, "ort_R": 3, "kazanma_orani_%": 1}


def main():
    repo, dbp, kabul, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    sys.path.insert(0, str(Path(__file__).parent))
    import mae_mfe as mm
    import metrikler as mt
    from bist_haber import defter
    kayit = json.loads((Path(kabul) / "kayit.json").read_text(encoding="utf-8"))
    ters = {v: k for k, v in kayit["dosya_adlari"].items()}
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    bars = defaultdict(list)
    for tk, d, o, h, l, cl in c.execute("SELECT ticker, date, open, high, low, close FROM prices WHERE close IS NOT NULL "
                                        "ORDER BY ticker, date"):
        bars[tk].append({"date": d, "open": o, "high": h, "low": l, "close": cl})
    out = {"not": "Bağımsız yeniden hesap; FAZ 2 kabul dosyaları (commit 6d7f5d5) üzerinde. Gün sonu verisi.", "kosular": {}}
    for egri_p in sorted(Path(kabul).glob("*_egri.csv")):
        e, p, k, _ = egri_p.name.split("_")
        anahtar = f"{ters[e]}/{ters[p]}/{ters[k]}"
        egri = mt.egri_oku(egri_p)
        isl = mt.islem_oku(Path(kabul) / egri_p.name.replace("_egri", "_islemler"))
        m = mt.hesapla(egri, isl, kayit["ayar_varsayilan"]["baslangic_sermaye"])
        m["toplam_getiri_%_bagimsiz"] = 100 * (egri[-1]["ozsermaye"] / kayit["ayar_varsayilan"]["baslangic_sermaye"] - 1)
        ref = kayit["sonuc"][anahtar]
        dogrulama = {}
        for rk, bk in ESLES.items():
            v = m["toplam_getiri_%_bagimsiz"] if bk is None else m[bk]
            yv = round(v, YUV.get(rk, 2)) if isinstance(v, float) else v
            dogrulama[rk] = {"simulator": ref[rk], "bagimsiz": yv,
                             "ayni": (abs(yv - ref[rk]) <= 10 ** -YUV.get(rk, 2) * 1.01) if isinstance(yv, float)
                             and ref[rk] is not None else yv == ref[rk]}
        mae = [x for x in (mm.hesapla(t, bars[t["ticker"]], defter) for t in isl) if x]
        ozet_mae = {}
        for key in ("mae_R_plan", "mfe_R_plan", "mae_R_dolum", "mfe_R_dolum", "mae_%", "mfe_%",
                    "cikis_sonrasi_en_yuksek_%", "cikis_sonrasi_en_dusuk_%"):
            vals = [x[key] for x in mae if x.get(key) is not None]
            ozet_mae[key] = {f"p{int(pp * 100)}": round(mt.yuzdelik(vals, pp), 3) for pp in (0.05, 0.25, 0.5, 0.75, 0.95)} \
                if vals else None
            ozet_mae[key + "_n"] = len(vals)
        ozet_mae["yaklasik_islem"] = sum(x["yaklasik"] for x in mae)
        ozet_mae["R_dolum_tanimsiz"] = sum(1 for x in mae if x["mae_R_dolum"] is None)
        ozet_mae["varsayimsal_cikis"] = sum(1 for x in mae if x["varsayimsal_cikis"])
        out["kosular"][anahtar] = {"dogrulama": dogrulama, "dogrulama_tamam": all(v["ayni"] for v in dogrulama.values()),
                                   "ek_metrikler": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()
                                                    if k not in ESLES.values()},
                                   "mae_mfe": ozet_mae}
        print(anahtar, "doğrulama:", out["kosular"][anahtar]["dogrulama_tamam"],
              {k: v for k, v in dogrulama.items() if not v["ayni"]}, flush=True)
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
