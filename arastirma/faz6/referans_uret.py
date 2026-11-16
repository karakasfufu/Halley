"""FAZ 6: izleme referansları (ön kayıt izleme_tanimi.json). Yalnız okur.
  girdi: tp1_v1 eğitim örnekleri (etiket2.csv, egit.load_df süzgeci) → her girdi için 10 eşit yüzdelikli dilim sınırı
         ve eğitim oranları (PSI için). Örnek kimliği ya da fiyat içermez; yalnız özet.
  rejim: FAZ 4 rejim_sonuclari.json → eğitim dönemi sinyal günü rejim dağılımı.
Kullanım: python referans_uret.py <repo> <etiket2.csv> <faz4_rejim_sonuclari.json> <cikti.json>"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

GIRDILER = ["x_trend", "x_perf20", "rsi", "skor", "tp1_atr", "stop_atr", "rs20", "perf20", "atr_%", "rr1"]


def main():
    repo, etiket, rejim_json, cikti = sys.argv[1:5]
    sys.path.insert(0, str(Path(repo) / "arastirma" / "asama6"))
    import egit
    df = egit.load_df(etiket)
    ref = {"kaynak": "tp1_v1 eğitim örnekleri: etiket2.csv (FAZ 3 arşivi), egit.load_df süzgeci",
           "etiket2_sha256": hashlib.sha256(Path(etiket).read_bytes()).hexdigest(), "n": int(len(df)),
           "egitim_ilk": df["tarih"].min(), "egitim_son": df["tarih"].max(),
           "egitim_tp1_orani": float(df["y"].mean()), "girdi": {}, "tur_orani": {}}
    for k in GIRDILER:
        v = df[k].astype(float).dropna().values
        sinir = sorted(set(np.quantile(v, [i / 10 for i in range(1, 10)]).round(6).tolist()))
        dilim = np.digitize(v, sinir)
        oran = [float(np.mean(dilim == i)) for i in range(len(sinir) + 1)]
        ref["girdi"][k] = {"sinirlar": sinir, "oranlar": oran, "n": int(len(v))}
    ref["tur_orani"] = {k: float(x) for k, x in df["tur"].value_counts(normalize=True).items()}
    rj = json.loads(Path(rejim_json).read_text(encoding="utf-8"))["rejim_gun_dagilimi"]
    top = sum(rj.values())
    ref["rejim_gun_payi"] = {k: v / top for k, v in rj.items()}
    ref["rejim_kaynak"] = "FAZ 4 rejim_sonuclari.json (canli_ortak sinyal günleri 2022-11 … 2026-11, regime.py)"
    Path(cikti).write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
    print(ref["n"], ref["egitim_tp1_orani"], list(ref["girdi"]))


if __name__ == "__main__":
    main()
