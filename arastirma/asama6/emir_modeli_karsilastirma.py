"""FAZ 2 Ek H5 (araştırma; yalnız okur): emir modeli düzeltmesi. Yalnız EKSİK koşular çalıştırılır:
  onceden_limit × {planlanan_giris, azami_giris} (kural s3) — açılıştan önce kurulan emir listesi, yerine aday yok.
Ayrıca Ek H4 koşuları (sonuclar_faz2/kural_s3.json) kod değişikliğinden sonra aynı metrikleri veriyor mu (regresyon).
GERİYE DÖNÜK DOĞRULAMA; dönem dışı başarı kanıtı değildir; senaryo otomatik seçilmez; parametre değişmez.
Kullanım: python emir_modeli_karsilastirma.py <repo> <arastirma.db> <planlar.csv> <kural_s3.json> <cikti.json>"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

YENI = {"onceden_limit_planlanan_s3": {"adet_temeli": "planlanan_giris", "kural": "s3", "emir_modeli": "onceden_limit"},
        "onceden_limit_azami_s3": {"adet_temeli": "azami_giris", "kural": "s3", "emir_modeli": "onceden_limit"}}


def main():
    repo, dbp, plan_csv, eski_json, cikti = sys.argv[1:6]
    sys.path.insert(0, repo)
    sys.path.insert(0, str(Path(__file__).parent))
    import portfoy as pf
    import risk_ayristirma as ra
    from kural_s3_karsilastirma import KOSULAR
    eski = json.loads(Path(eski_json).read_text(encoding="utf-8"))
    c2 = (pf.VARSAYILAN["komisyon_pct"] + pf.VARSAYILAN["kayma_pct"]) / 200
    out = {"not": "Geriye dönük doğrulama; dönem dışı başarı kanıtı değildir; senaryo otomatik seçilmez.",
           "regresyon_ek_h4_metrikleri_ayni": {}}
    for evren in ("canli_ortak", "yalniz_teknik"):
        planlar = pf.plan_oku(plan_csv, evren)
        bars = pf.bar_oku(dbp, [p["ticker"] for p in planlar] + ["XU100"])
        takvim = pf.takvim_olustur(bars)
        son = takvim[-1]
        bas12 = (date.fromisoformat(son) - timedelta(days=365)).isoformat()
        donemler = {"son_12_ay": (min(d for d in takvim if d > bas12), son), "2024": ("2024-01-01", "2024-12-31")}
        for ad, (b, s) in donemler.items():
            for kosu, ayar in KOSULAR.items():                    # regresyon: Ek H4 koşuları değişmedi mi
                m = pf.simule(planlar, bars, takvim, b, s, ayar)["metrik"]
                out["regresyon_ek_h4_metrikleri_ayni"][f"{evren}/{ad}/{kosu}"] = all(
                    m.get(k) == v for k, v in eski[f"{evren}/{ad}/{kosu}"]["metrik"].items())
            for kosu, ayar in YENI.items():
                r = pf.simule(planlar, bars, takvim, b, s, ayar)
                a = ra.analiz(r)
                a["toplam_maliyet_tl"] = round(sum(t["maliyet_tl"] for t in r["islemler"]) + sum(
                    x["adet_bas"] * x["giris_fiyati"] * c2 * 2 - x["kalan"] * x["giris_fiyati"] * c2 for x in r["acik_son"]), 2)
                a["sl_alti_kapanan_net_pozitif"] = sum(1 for t in r["islemler"] if t["acilis_sl_alti"] and t["net_tl"] > 0)
                a["sl_alti_kapanan_net_toplam_tl"] = round(sum(t["net_tl"] for t in r["islemler"] if t["acilis_sl_alti"]), 2)
                a["dolmayan_emir"] = sum(1 for x in r["atlanan"] if x["neden"].startswith("emir dolmadı"))
                a["donem"] = [b, s]
                out[f"{evren}/{ad}/{kosu}"] = a
                m = a["metrik"]
                print(evren, ad, kosu, m["bitis_ozsermaye"], m["toplam_getiri_%"], m["azami_dusus_%"], m["sortino_yillik"],
                      m["kar_faktoru"], m["ort_R"], "kapanan", m["kapanan_islem"], "acilan", a["acilan"], "maliyet",
                      a["toplam_maliyet_tl"], "bas_asim", a["baslangic_riski_butceyi_asan"], "kayip_asim",
                      a["kaybi_butceyi_asan_kapanan"], a["kaybi_asan_nedenleri"], "port%",
                      a["giris_ani_portfoy_riski_gercek_en_yuksek_%"], "slalti", a["acilis_sl_alti_giris"],
                      a["sl_alti_kapanan_net_pozitif"], a["sl_alti_kapanan_net_toplam_tl"], "dolmayan", a["dolmayan_emir"],
                      "atlanan", m["atlanan"], flush=True)
    print("regresyon:", all(out["regresyon_ek_h4_metrikleri_ayni"].values()),
          [k for k, v in out["regresyon_ek_h4_metrikleri_ayni"].items() if not v])
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
