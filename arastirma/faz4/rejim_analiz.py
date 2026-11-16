"""FAZ 4 (araştırma; yalnız okur): strateji türü × piyasa rejimi, TEKİL işlem sonuçları. Tanımlar ön kayıtta
(rejim_tanimi.json, commit c1a4192 — sonuçlardan önce). Rejim: canlı bist_haber.regime (değiştirilmedi), karar anına
kadarki BIST 100 verisiyle. Portföy metriği HESAPLANMAZ. Eşik optimize edilmez; strateji seçilmez.
Kullanım: python rejim_analiz.py <repo> <arastirma.db> <planlar_seviyeli.csv> <cikti_klasoru>"""
import csv
import json
import random
import sqlite3
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date
from pathlib import Path

KAPANAN = {"SL", "TP2", "başabaş (TP1 sonrası)", "süre doldu"}
DONEMLER = {"2022_son": ("2022-11-01", "2022-12-31"), "2023": ("2023-01-01", "2023-12-31"),
            "2024": ("2024-01-01", "2024-12-31"), "2025_ilk": ("2025-01-01", "2025-11-13"),
            "son_12_ay": ("2025-11-14", "2026-11-13"), "tumu": ("2022-11-01", "2026-11-13")}
TEKRAR = 10
TEKRAR_BOOT, TOHUM = 2000, 20261116


def f_(v):
    try:
        return float(v) if v not in (None, "", "nan") else None
    except ValueError:
        return None


def xu100_baglanti(rows):
    """Yalnız XU100 satırları olan bellek içi veritabanı: regime() genişlik döngüsü boş kalır, trend/oynaklık aynı."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE prices (ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, "
              "PRIMARY KEY (ticker, date))")
    c.executemany("INSERT INTO prices VALUES ('XU100',?,?,?,?,?,?)", rows)
    return c


def rejimler(conn, gunler, regime_mod):
    out = {}
    for g in sorted(set(gunler)):
        r = regime_mod.regime(conn, date.fromisoformat(g))
        out[g] = None if r.get("yok") else {"trend": r["trend"], "oynaklik": r["oynaklik"], "rejim_gunu": r["gun"]}
    return out


def kume_bootstrap(gozlem, fn, tekrar=TEKRAR_BOOT, tohum=TOHUM):
    """gozlem: [(gun, deger)]. Gün kümeleri yerine koyarak örneklenir; %95 yüzdelik aralığı."""
    kume = defaultdict(list)
    for g, v in gozlem:
        kume[g].append(v)
    anah = list(kume)
    if len(anah) < 2:
        return None
    rnd = random.Random(tohum)
    sonuc = []
    for _ in range(tekrar):
        vals = []
        for _ in anah:
            vals.extend(kume[anah[rnd.randrange(len(anah))]])
        sonuc.append(fn(vals))
    sonuc.sort()
    return [round(sonuc[int(0.025 * (tekrar - 1))], 4), round(sonuc[int(0.975 * (tekrar - 1))], 4)]


def ortalama(x):
    return sum(x) / len(x) if x else None


def grup_ozeti(rows, guven_fn):
    n = len(rows)
    gun = len({r["tarih"] for r in rows})
    out = {"n": n, "gun": gun, "hisse": len({r["ticker"] for r in rows}), "guven": guven_fn(n, gun),
           "yetersiz": n < 30 or gun < 20}
    if not n:
        return out
    out.update({"tp1_%": round(100 * ortalama([r["y"] for r in rows]), 2),
                "kazanma_%": round(100 * ortalama([r["net"] > 0 for r in rows]), 2),
                "ort_net_%": round(ortalama([r["net"] for r in rows]), 3), "ort_R": round(ortalama([r["r"] for r in rows]), 3),
                "ayni_hisse_tekrar_%": round(100 * ortalama([r["tekrar"] for r in rows]), 1),
                "veri_gosterge_sicrama_%": round(100 * ortalama([r["sic_pencere"] for r in rows]), 1),
                "veri_tutma_sicrama_%": round(100 * ortalama([r["sic_tutma"] for r in rows]), 1)})
    if gun >= 2:
        out["ga95_tp1_%"] = [round(100 * x, 2) for x in kume_bootstrap([(r["tarih"], r["y"]) for r in rows], ortalama)]
        out["ga95_kazanma_%"] = [round(100 * x, 2) for x in kume_bootstrap([(r["tarih"], float(r["net"] > 0)) for r in rows],
                                                                          ortalama)]
        out["ga95_ort_net_%"] = kume_bootstrap([(r["tarih"], r["net"]) for r in rows], ortalama)
        out["ga95_ort_R"] = kume_bootstrap([(r["tarih"], r["r"]) for r in rows], ortalama)
    return out


def ornekler(plan_csv, sicrama, gunler_tk):
    """canli_ortak, kapanmış, s3 tür A (açılış ≤ SL) hariç; veri kalitesi ve tekrar bayrakları."""
    tut, haric = [], defaultdict(int)
    son_sinyal = {}
    with open(plan_csv, encoding="utf-8") as fh:
        satirlar = list(csv.DictReader(fh))
    for r in satirlar:
        if r["risk"] == "yüksek" or (f_(r["teknik_skor"]) or 0) < 5:
            continue
        if r["sonuc"] not in KAPANAN:
            haric[r["sonuc"] or "bos"] += 1
            continue
        acil = f_(r["kapanis"]) * (1 + f_(r["acilis_bosluk_%"]) / 100) if f_(r["acilis_bosluk_%"]) is not None else None
        if acil is not None and acil <= f_(r["sl"]) * (1 + 1e-4):
            haric["s3_acilis_stop_alti_girissiz"] += 1
            continue
        tk, d = r["ticker"], r["tarih"]
        g = gunler_tk.get(tk, [])
        j = bisect_right(g, d) - 1
        s = sicrama.get(tk, [])
        pen = j >= 0 and bisect_right(s, d) - bisect_left(s, g[max(0, j - 249)]) > 0
        n = int(f_(r["gun"]) or 1)
        tutma = j + 1 < len(g) and bisect_right(s, g[min(len(g) - 1, j + n)]) - bisect_left(s, g[j + 1]) > 0
        onceki = son_sinyal.get(tk)
        tekrar = onceki is not None and j - onceki <= TEKRAR
        son_sinyal[tk] = j
        tut.append({"ticker": tk, "tarih": d, "tur": r["tur"], "y": float(r["y"]), "net": float(r["net"]),
                    "r": float(r["r"]), "sic_pencere": pen, "sic_tutma": tutma, "tekrar": tekrar})
    return tut, dict(haric)


def main():
    repo, dbp, plan_csv, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    from bist_haber import defter, regime
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    xu = c.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker='XU100' ORDER BY date").fetchall()
    seri = defaultdict(list)
    for tk, d, cl in c.execute("SELECT ticker, date, close FROM prices WHERE close IS NOT NULL AND ticker!='XU100' "
                               "ORDER BY ticker, date"):
        seri[tk].append((d, cl))
    gunler_tk = {tk: [d for d, _ in s] for tk, s in seri.items()}
    sicrama = {tk: [s[i][0] for i in range(1, len(s)) if s[i - 1][1] and abs(s[i][1] / s[i - 1][1] - 1) > 0.105]
               for tk, s in seri.items()}
    rows, haric = ornekler(plan_csv, sicrama, gunler_tk)
    # sıralama: tarih sırası (tekrar bayrağı için ornekler zaten dosya sırasıyla — dosya tarih, hisse sıralı)
    rg = rejimler(xu100_baglanti(xu), [r["tarih"] for r in rows], regime)
    rejimsiz = 0
    for r in rows:
        x = rg.get(r["tarih"])
        if x is None or x["oynaklik"] is None:
            r["trend"], r["oynaklik"] = (x or {}).get("trend") or "rejim_yok", "rejim_yok"
            rejimsiz += 1
        else:
            r["trend"], r["oynaklik"] = x["trend"], x["oynaklik"]
    out = {"on_kayit": "rejim_tanimi.json (commit c1a4192)", "ornek": len(rows), "haric": haric,
           "rejimsiz_ornek": rejimsiz, "rejim_gun_dagilimi": {}, "donemler": {}}
    gunluk = defaultdict(int)
    for g, x in rg.items():
        gunluk[f"{x['trend']} / {x['oynaklik']}" if x else "rejim_yok"] += 1
    out["rejim_gun_dagilimi"] = dict(sorted(gunluk.items()))
    anahtarlar = {"ana": lambda r: (r["tur"], r["trend"], r["oynaklik"]), "tur_trend": lambda r: (r["tur"], r["trend"]),
                  "tur_oynaklik": lambda r: (r["tur"], r["oynaklik"]), "rejim": lambda r: (r["trend"], r["oynaklik"]),
                  "tur": lambda r: (r["tur"],)}
    for ad, (b, s) in DONEMLER.items():
        dr = [r for r in rows if b <= r["tarih"] <= s]
        d_out = {}
        for k, fn in anahtarlar.items():
            gr = defaultdict(list)
            for r in dr:
                gr[" | ".join(fn(r))].append(r)
            d_out[k] = {g: grup_ozeti(v, defter.guven) for g, v in sorted(gr.items())}
        out["donemler"][ad] = d_out
        print(ad, len(dr), flush=True)
    # çoklu karşılaştırma özeti (ana gruplar, tüm dönem)
    ana = out["donemler"]["tumu"]["ana"]
    yeterli = {g: v for g, v in ana.items() if not v["yetersiz"]}
    disla = [g for g, v in yeterli.items() if v.get("ga95_ort_R") and (v["ga95_ort_R"][0] > 0 or v["ga95_ort_R"][1] < 0)]
    out["coklu_karsilastirma"] = {"ana_grup": len(ana), "yeterli_grup": len(yeterli),
                                  "ga95_ort_R_sifiri_dislayan": len(disla), "dislayanlar": disla,
                                  "rastlantiyla_beklenen_yaklasik": round(0.05 * len(yeterli), 1),
                                  "not": "Gruplar bağımsız değildir (aynı günler, aynı hisseler); beklenen sayı kaba bir "
                                         "ölçektir. Düzeltilmiş anlamlılık iddia edilmez."}
    Path(cikti).mkdir(parents=True, exist_ok=True)
    (Path(cikti) / "rejim_sonuclari.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("ornek", "haric", "rejimsiz_ornek", "rejim_gun_dagilimi", "coklu_karsilastirma")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
