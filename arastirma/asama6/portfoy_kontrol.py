"""FAZ 2 gerçek veri kontrolleri (araştırma; yalnız okur). Aynı ayarlarla simülasyonu yeniden çalıştırıp:
yeniden üretilebilirlik (kayit.json ile aynı mı), sınırların uygulandığı (azami pozisyon, açık risk oranı, sektör başına
eşzamanlı pozisyon), toplam maliyet, açılan/kapanan/açık sayıları, stop boşluğu kayıpları ve KISITSIZ + sabit 100 adet
modunda her işlemin journal.evaluate ile tekil mutabakatını raporlar.
Kullanım: python portfoy_kontrol.py <repo> <arastirma.db> <planlar.csv> <sonuc_klasoru_kökü> <cikti.json>"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

repo, dbp, plan_csv, kok, cikti = sys.argv[1:6]
sys.path.insert(0, repo)
sys.path.insert(0, str(Path(__file__).parent))
import portfoy as pf  # noqa: E402
from bist_haber import journal  # noqa: E402

C2 = (pf.VARSAYILAN["komisyon_pct"] + pf.VARSAYILAN["kayma_pct"]) / 200
out = {}
for evren in ("canli_ortak", "yalniz_teknik"):
    kayit = json.loads((Path(kok) / evren / "kayit.json").read_text(encoding="utf-8"))
    planlar = pf.plan_oku(plan_csv, evren)
    bars = pf.bar_oku(dbp, [p["ticker"] for p in planlar] + ["XU100"])
    takvim = pf.takvim_olustur(bars)
    for ad, (b, s) in kayit["donemler"].items():
        r = pf.simule(planlar, bars, takvim, b, s)
        m = r["metrik"]
        ayni = {k: m[k] == kayit["sonuc"][ad][k] for k in m}
        # eşzamanlı sektör sayısı: işlem aralıklarından
        aralik = [(t["giris_gunu"], t["cikis_gunu"], t["sektor"]) for t in r["islemler"]] + \
                 [(a["giris_gunu"], s, pf._sektor(a["ticker"])) for a in r["acik_son"]]
        # giriş anında (çıkışlar işlenmeden önce) aynı anda tutulan: giris_gunu <= d <= cikis_gunu
        sek_max, poz_max = 0, 0
        for d in [e["gun"] for e in r["egri"]]:
            tut = [sk for g, c_, sk in aralik if g <= d <= c_]
            c = Counter(tut)
            sek_max = max(sek_max, max(c.values()) if c else 0)
            poz_max = max(poz_max, len(tut))
        oz_once = [pf.VARSAYILAN["baslangic_sermaye"]] + [e["ozsermaye"] for e in r["egri"][:-1]]
        risk_oran = max(e["acik_risk"] / o for e, o in zip(r["egri"], oz_once))
        maliyet = sum(t["maliyet_tl"] for t in r["islemler"]) + sum(
            a["adet_bas"] * a["giris_fiyati"] * C2 + (a["adet_bas"] - a["kalan"]) * a["giris_fiyati"] * C2 for a in r["acik_son"])
        rs = sorted((t["r"], t["ticker"], t["giris_gunu"], t["sonuc"]) for t in r["islemler"] if t["r"] is not None)
        bosluk = [x for x in r["islemler"] if x["r"] is not None and x["r"] < -1.0]
        ent = {"yeniden_uretim_metrikler_ayni": all(ayni.values()), "farkli_metrik": [k for k, v in ayni.items() if not v],
               "acilan": len(r["islemler"]) + len(r["acik_son"]), "kapanan": len(r["islemler"]), "sonda_acik": len(r["acik_son"]),
               "azami_gun_sonu_acik_pozisyon": max(e["acik_pozisyon"] for e in r["egri"]),
               "azami_giris_aninda_tutulan_pozisyon": poz_max,
               "azami_acik_risk_orani_%": round(100 * risk_oran, 3),
               "azami_eszamanli_ayni_sektor": sek_max, "toplam_maliyet_tl": round(maliyet, 2),
               "stop_boslugu_r_lt_-1": len(bosluk), "en_kotu_R": rs[0] if rs else None,
               "bosluk_ornekleri": [(x["ticker"], x["giris_gunu"], x["cikis_gunu"], x["r"], x["bacaklar"][-1]["neden"])
                                    for x in sorted(bosluk, key=lambda x: x["r"])[:5]],
               "sonda_acik_liste": [(a["ticker"], a["giris_gunu"], a["kalan"], a["tp1_satildi"], a["gerceklesmemis_tl"])
                                    for a in r["acik_son"]]}
        if evren == "canli_ortak":                                # tekil mutabakat (kısıtsız, sabit 100 adet)
            u = pf.simule(planlar, bars, takvim, b, s, {"baslangic_sermaye": 1e12, "sinirsiz": True, "sabit_adet": 100})
            pidx = defaultdict(list)
            for p in planlar:
                pidx[(p["ticker"], p["tarih"])].append(p)
            bozuk, enb = [], 0.0
            for t in u["islemler"]:
                p = pidx[(t["ticker"], t["sinyal_gunu"])][0]
                rec = {"kaynak": "gercek", "gercek_giris_gunu": t["giris_gunu"], "gercek_giris_fiyati": t["giris_fiyati"],
                       "signal_day": p["tarih"], "senaryo": p["tur"], "sl": p["sl"], "tp1": p["tp1"], "tp2": p["tp2"],
                       "giris": p["giris"], "alarm": None, "gecerlilik": 1}
                gelecek = [x for x in bars[t["ticker"]] if x["date"] > p["tarih"]]   # dönem sonrası dahil TÜM gelecek
                j = journal.evaluate(rec, gelecek, pf.VARSAYILAN["komisyon_pct"], pf.VARSAYILAN["kayma_pct"])
                bek = sum(x["pay"] * 100 * (x["fiyat"] - t["giris_fiyati"]) for x in j["bacaklar"]) - 100 * t["giris_fiyati"] * 0.003
                fark = abs(t["net_tl"] - bek)
                enb = max(enb, fark)
                if j.get("sonuc") != t["sonuc"] or j.get("cikis_gunu") != t["cikis_gunu"] or j.get("r") != t["r"] or fark > 0.006:
                    bozuk.append((t["ticker"], t["giris_gunu"], t["sonuc"], j.get("sonuc"), round(fark, 4)))
            ent["tekil_mutabakat"] = {"kisitsiz_kapanan_islem": len(u["islemler"]), "kisitsiz_sonda_acik": len(u["acik_son"]),
                                      "uyusmayan": len(bozuk), "ornek": bozuk[:5], "en_buyuk_net_fark_tl": round(enb, 4),
                                      "atlanan_nedenleri": dict(Counter(x["neden"] for x in u["atlanan"]))}
        out[f"{evren}/{ad}"] = ent
        print(evren, ad, json.dumps(ent, ensure_ascii=False, default=str), flush=True)
Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
