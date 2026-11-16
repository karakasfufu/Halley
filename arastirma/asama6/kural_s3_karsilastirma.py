"""FAZ 2 Ek H4 (araştırma; yalnız okur): gerçekleşme düzeltmesi (kural s3) ile iki adet senaryosunun yeniden üretimi.
GERİYE DÖNÜK DOĞRULAMADIR; dönem dışı başarı kanıtı değildir; senaryo otomatik seçilmez; parametre değişmez.

Koşular (her biri kendi nakit/risk durumuyla BAĞIMSIZ; aynı işlemleri seçmeye zorlanmaz):
  mevcut_s2     planlanan girişe göre adet, eski gerçekleşme (Ek H5 orijinali — hatalı varsayım içerir)
  mevcut_s3     planlanan girişe göre adet, açılışı görüp elle alım → açılış ≤ SL girişsiz; journal s3
  alternatif_s2 azami girişe göre adet, eski gerçekleşme (Ek H3 — hatalı varsayım içerir)
  alternatif_s3 azami girişe göre adet, açılış seansına azami limitli emir → SL altında da dolar; journal s3
Kullanım: python kural_s3_karsilastirma.py <repo> <arastirma.db> <planlar.csv> <cikti.json>"""
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

KOSULAR = {"mevcut_s2": {"adet_temeli": "planlanan_giris"},
           "mevcut_s3": {"adet_temeli": "planlanan_giris", "kural": "s3", "stop_alti_girissiz": True},
           "alternatif_s2": {"adet_temeli": "azami_giris"},
           "alternatif_s3": {"adet_temeli": "azami_giris", "kural": "s3"},
           # AYRIŞTIRMA (öneri değil): adet etkisi ile "açılışı görerek SL süzgeci" etkisini ayırmak için çapraz koşular
           "ayr_planlanan_onceden_emir_s3": {"adet_temeli": "planlanan_giris", "kural": "s3"},
           "ayr_azami_acilisi_gorup_s3": {"adet_temeli": "azami_giris", "kural": "s3", "stop_alti_girissiz": True}}


def main():
    repo, dbp, plan_csv, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    sys.path.insert(0, str(Path(__file__).parent))
    import portfoy as pf
    import risk_ayristirma as ra
    c2 = (pf.VARSAYILAN["komisyon_pct"] + pf.VARSAYILAN["kayma_pct"]) / 200
    out = {"not": "Geriye dönük doğrulama; dönem dışı başarı kanıtı değildir; senaryo otomatik seçilmez."}
    for evren in ("canli_ortak", "yalniz_teknik"):
        planlar = pf.plan_oku(plan_csv, evren)
        bars = pf.bar_oku(dbp, [p["ticker"] for p in planlar] + ["XU100"])
        takvim = pf.takvim_olustur(bars)
        son = takvim[-1]
        bas12 = (date.fromisoformat(son) - timedelta(days=365)).isoformat()
        donemler = {"son_12_ay": (min(d for d in takvim if d > bas12), son), "2024": ("2024-01-01", "2024-12-31")}
        for ad, (b, s) in donemler.items():
            secim = {}
            for kosu, ayar in KOSULAR.items():
                r = pf.simule(planlar, bars, takvim, b, s, ayar)
                a = ra.analiz(r)
                hepsi = r["islemler"] + r["acik_son"]
                a["toplam_maliyet_tl"] = round(sum(t["maliyet_tl"] for t in r["islemler"]) + sum(
                    x["adet_bas"] * x["giris_fiyati"] * c2 * 2 - x["kalan"] * x["giris_fiyati"] * c2 for x in r["acik_son"]), 2)
                a["sl_alti_kapanan_net_pozitif"] = sum(1 for t in r["islemler"] if t["acilis_sl_alti"] and t["net_tl"] > 0)
                a["sl_alti_kapanan_net_toplam_tl"] = round(sum(t["net_tl"] for t in r["islemler"] if t["acilis_sl_alti"]), 2)
                a["donem"] = [b, s]
                secim[kosu] = {(x["ticker"], x["giris_gunu"]) for x in hepsi}
                out[f"{evren}/{ad}/{kosu}"] = a
                m = a["metrik"]
                print(evren, ad, kosu, m["bitis_ozsermaye"], m["toplam_getiri_%"], m["azami_dusus_%"], m["sortino_yillik"],
                      m["kar_faktoru"], m["ort_R"], "kapanan", m["kapanan_islem"], "acilan", a["acilan"], "maliyet",
                      a["toplam_maliyet_tl"], "bas_asim", a["baslangic_riski_butceyi_asan"], "kayip_asim",
                      a["kaybi_butceyi_asan_kapanan"], a["kaybi_asan_nedenleri"], "port%", a["giris_ani_portfoy_riski_gercek_en_yuksek_%"],
                      "slalti", a["acilis_sl_alti_giris"], "slalti_net+", a["sl_alti_kapanan_net_pozitif"],
                      a["sl_alti_kapanan_net_toplam_tl"], "atlanan", m["atlanan"], flush=True)
            for x, y in (("mevcut_s2", "mevcut_s3"), ("alternatif_s2", "alternatif_s3"), ("mevcut_s3", "alternatif_s3")):
                out[f"{evren}/{ad}/ortak_islem/{x}~{y}"] = {"ortak": len(secim[x] & secim[y]), "yalniz_" + x: len(secim[x] - secim[y]),
                                                           "yalniz_" + y: len(secim[y] - secim[x])}
                print(evren, ad, x, "~", y, out[f"{evren}/{ad}/ortak_islem/{x}~{y}"], flush=True)
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
