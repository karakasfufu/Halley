"""FAZ 2 Ek H3 (araştırma; yalnız okur): risk hesabındaki farkın ayrıştırılması ve iki adet senaryosunun yan yana
raporu. GERİYE DÖNÜK DOĞRULAMADIR: önceki sonuçlar görüldükten sonra yapıldı; dönem dışı başarı kanıtı değildir.
Daha iyi sonuç veren senaryo otomatik SEÇİLMEZ.

Senaryolar (diğer bütün ayarlar aynı, VARSAYILAN):
  mevcut     adet_temeli = planlanan_giris (canlı paneldeki adet hesabı)
  alternatif adet_temeli = azami_giris (adet, nakit ve aday riski açılıştan önce bilinen azami girişle)

%1'i aşan kayıp ayrıştırması (kapanan işlem, kayıp L = −net_tl, bütçe B = önceki gün özsermayesi × %1):
  P = adet × ((plan girişi − SL) + plan girişi × %0,3)      planlanan azami kayıp (position_size; P ≤ B)
  E = adet × (dolum − plan girişi)                           giriş farkı
  G = Σ stop bacakları satılan × max(0, stop − çıkış fiyatı) stop altında çıkış (SL: plan SL; başabaş: dolum)
  C = adet × (dolum − plan girişi) × %0,3                    maliyetin planlanandan farkı
  K = L − (P + E + G + C)                                    kalan (TP1 yarı satışı vb.; tam SL'de ≈ 0)
Neden etiketi: E > 0 ve G > 0 olanlar; C yalnız belirleyiciyse (P+E+G ≤ B < P+E+G+C) eklenir.
Kullanım: python risk_ayristirma.py <repo> <arastirma.db> <planlar.csv> <cikti.json>"""
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

CT = (0.20 + 0.10) / 100      # portfoy.VARSAYILAN komisyon + kayma (gidiş-dönüş)
TOL = 1e-6


def ayristir(t):
    adet, fill, g0, sl = t["adet"], t["giris_fiyati"], t["planlanan_giris"], t["sl"]
    P = adet * ((g0 - sl) + g0 * CT)
    E = adet * (fill - g0)
    C = adet * (fill - g0) * CT
    G = 0.0
    for b in t["bacaklar"]:
        n = b["neden"]
        if n.startswith("SL"):
            G += b["adet"] * max(0.0, sl - b["fiyat"])
        elif n.startswith("başabaş"):
            G += b["adet"] * max(0.0, fill - b["fiyat"])
    L = -t["net_tl"]
    B = t["butce_tl"]
    ad = [x for x, v in (("giriş farkı", E), ("stop altı çıkış", G)) if v > 0.005]
    if P + E + G <= B + TOL < P + E + G + C:
        ad.append("maliyet")
    return {"L": L, "B": B, "P": P, "E": E, "G": G, "C": C, "K": L - (P + E + G + C),
            "etiket": " + ".join(ad) if ad else "diğer"}


def analiz(r):
    m = r["metrik"]
    hepsi = r["islemler"] + r["acik_son"]
    asan_bas = [x for x in hepsi if x["risk_bas_gercek_tl"] > x["butce_tl"] + 0.01]
    oran_bas = max(x["risk_bas_gercek_tl"] / x["butce_tl"] for x in hepsi) if hepsi else None
    egri = r["egri"]
    port = [(e["giris_ani_risk_gercek"] / e["ozsermaye_onceki"], e["gun"]) for e in egri]
    port_max = max(port)
    plan_oran = max((e["acik_risk"] / e["ozsermaye_onceki"]) for e in egri)
    kayip = []
    for t in r["islemler"]:
        if -t["net_tl"] > t["butce_tl"] + 0.01:
            a = ayristir(t)
            a.update(ticker=t["ticker"], giris_gunu=t["giris_gunu"], r=t["r"], sonuc=t["sonuc"])
            kayip.append(a)
    et = Counter(k["etiket"] for k in kayip)
    top = {k: round(sum(x[k] for x in kayip), 2) for k in ("L", "B", "P", "E", "G", "C", "K")}
    sl_alti = [x for x in hepsi if x["acilis_sl_alti"]]
    sl_alti_k = [t for t in r["islemler"] if t["acilis_sl_alti"]]
    hayali = sum(sum(b["adet"] * (b["fiyat"] - t["giris_fiyati"]) for b in t["bacaklar"] if b["neden"] == "SL (alış günü)")
                 for t in sl_alti_k)
    return {
        "metrik": {k: m[k] for k in ("bitis_ozsermaye", "toplam_getiri_%", "azami_dusus_%", "sortino_yillik", "kar_faktoru",
                                     "ort_R", "kapanan_islem", "kazanma_orani_%", "nakitle_kucultulen", "sonda_acik_pozisyon",
                                     "sonda_gerceklesmemis_tl", "atlanan")},
        "acilan": len(hepsi),
        "baslangic_riski_butceyi_asan": len(asan_bas),
        "baslangic_riski_en_yuksek_butce_kati": round(oran_bas, 4) if oran_bas else None,
        "baslangic_riski_ornek": sorted(((round(x["risk_bas_gercek_tl"] / x["butce_tl"], 3), x["ticker"], x["giris_gunu"])
                                         for x in asan_bas), reverse=True)[:3],
        "giris_ani_portfoy_riski_gercek_en_yuksek_%": round(100 * port_max[0], 3), "gunu": port_max[1],
        "giris_ani_portfoy_riski_%6_asan_gun": sum(1 for v, _ in port if v > 0.06 + 1e-9),
        "gun_sonu_acik_risk_en_yuksek_%": round(100 * plan_oran, 3),
        "kaybi_butceyi_asan_kapanan": len(kayip), "kapanan": len(r["islemler"]),
        "kaybi_asan_nedenleri": dict(et), "kaybi_asan_bilesen_toplam_tl": top,
        "kaybi_asan_en_buyuk": sorted(((round(k["L"] / k["B"], 3), k["ticker"], k["giris_gunu"], k["etiket"]) for k in kayip),
                                      reverse=True)[:5],
        "acilis_sl_alti_giris": len(sl_alti), "acilis_sl_alti_kapanan_sonuc": dict(Counter(t["sonuc"] for t in sl_alti_k)),
        "acilis_sl_alti_alis_gunu_stoptan_satis_kari_tl": round(hayali, 2),
        "acilis_sl_alti_ornek": [(t["ticker"], t["giris_gunu"], t["giris_fiyati"], t["sl"],
                                  [(b["neden"], b["fiyat"]) for b in t["bacaklar"]], t["net_tl"]) for t in sl_alti_k[:5]],
    }


def main():
    repo, dbp, plan_csv, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    sys.path.insert(0, str(Path(__file__).parent))
    import portfoy as pf
    out = {"not": "Geriye dönük doğrulama; önceki sonuçlar görüldükten sonra yapıldı. Dönem dışı başarı kanıtı değildir. "
                  "Senaryo otomatik seçilmez."}
    for evren in ("canli_ortak", "yalniz_teknik"):
        planlar = pf.plan_oku(plan_csv, evren)
        bars = pf.bar_oku(dbp, [p["ticker"] for p in planlar] + ["XU100"])
        takvim = pf.takvim_olustur(bars)
        son = takvim[-1]
        bas12 = (date.fromisoformat(son) - timedelta(days=365)).isoformat()
        donemler = {"son_12_ay": (min(d for d in takvim if d > bas12), son), "2024": ("2024-01-01", "2024-12-31")}
        # Evren genelinde (kısıtsız, sabit 100 adet) stop altında açılış sıklığı
        for ad, (b, s) in donemler.items():
            for sen, temel in (("mevcut", "planlanan_giris"), ("alternatif", "azami_giris")):
                r = pf.simule(planlar, bars, takvim, b, s, {"adet_temeli": temel})
                a = analiz(r)
                a["donem"] = [b, s]
                out[f"{evren}/{ad}/{sen}"] = a
                print(evren, ad, sen, json.dumps({k: a[k] for k in ("baslangic_riski_butceyi_asan", "kaybi_butceyi_asan_kapanan",
                                                                     "kaybi_asan_nedenleri", "giris_ani_portfoy_riski_gercek_en_yuksek_%",
                                                                     "acilis_sl_alti_giris")}, ensure_ascii=False),
                      json.dumps(a["metrik"], ensure_ascii=False), flush=True)
            u = pf.simule(planlar, bars, takvim, b, s, {"baslangic_sermaye": 1e12, "sinirsiz": True, "sabit_adet": 100})
            alt = [t for t in u["islemler"] if t["acilis_sl_alti"]]
            out[f"{evren}/{ad}/kisitsiz_sl_alti"] = {
                "girilen": len(u["islemler"]) + len(u["acik_son"]), "acilis_sl_alti": len(alt),
                "sonuclar": dict(Counter(t["sonuc"] for t in alt)),
                "alis_gunu_stoptan_satis": sum(1 for t in alt if any(x["neden"] == "SL (alış günü)" for x in t["bacaklar"])),
                "bu_islemlerin_net_toplami_tl": round(sum(t["net_tl"] for t in alt), 2)}
            print(evren, ad, "kisitsiz", json.dumps(out[f"{evren}/{ad}/kisitsiz_sl_alti"], ensure_ascii=False), flush=True)
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
