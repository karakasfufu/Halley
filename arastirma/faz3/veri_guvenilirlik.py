"""FAZ 3 (araştırma; veritabanını YALNIZ OKUR): fiyat verisi güvenilirlik taraması ve FAZ 2 kabul işlemlerine etkisi.

Bayraklar (mum düzeyi; eşikler önceden tanımlı, sonuçlara göre ayarlanmadı):
  eksik_gun       hissenin ilk-son günü arasında, takvimde (bütün hisselerin birleşimi) olup hissede olmayan gün
  uzun_bosluk     ardışık ≥ 5 takvim işlem günü eksik (işlem durdurma / veri eksikliği)
  sifir_hacim     volume = 0 ya da boş
  bayat           önceki mumla OHLC aynı ve hacim 0 (fiyat ilerlememiş; eski fiyat taşınmış olabilir)
  ohlc_tutarsiz   high < max(open, close) ya da low > min(open, close) ya da fiyat ≤ 0 ya da OHLC eksik
  sicrama_10      |kapanış / önceki kapanış − 1| > %10,5 (BIST pay piyasası günlük fiyat sınırı ±%10; tek gün aşımı
                  kurumsal işlem, işlem durdurma sonrası açılış ya da veri hatası belirtisidir)
  sicrama_25      |…| > %25
  kurumsal_yakin  sıçrama gününün ±5 takvim günü içinde KAP'ta sermaye artırımı/azaltımı, hak kullanımı, kâr payı ya da
                  bölünme bildirimi var (kap_liste; eşleşme hisse koduyla, yalnız varlık — tutar doğrulanmadı)
Kullanım: python veri_guvenilirlik.py <arastirma.db> <kabul_klasoru> <cikti.json>"""
import csv
import json
import sqlite3
import sys
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ESIK_10, ESIK_25, UZUN_BOSLUK = 0.105, 0.25, 5
KURUMSAL_KONU = ("Sermaye Artırımı", "Hak Kullanımı", "Kar Payı", "Bölünme", "Birleşme", "Bedelsiz")


def bayrakla(bars, takvim_idx, takvim):
    """bars: bir hissenin tarih sıralı mumları. Dönüş: {tarih: set(bayrak)} ve eksik günler listesi."""
    out = defaultdict(set)
    eksik = []
    if not bars:
        return out, eksik
    i0, i1 = takvim_idx[bars[0]["date"]], takvim_idx[bars[-1]["date"]]
    var = {b["date"] for b in bars}
    seri = 0
    for d in takvim[i0:i1 + 1]:
        if d not in var:
            eksik.append(d)
            seri += 1
        else:
            if seri >= UZUN_BOSLUK:
                out[d].add("uzun_bosluk_sonrasi")
            seri = 0
    onceki = None
    for b in bars:
        d, o, h, l, c, v = b["date"], b["open"], b["high"], b["low"], b["close"], b["volume"]
        if not v:
            out[d].add("sifir_hacim")
        if None in (o, h, l, c) or min(x for x in (o, h, l, c) if x is not None) <= 0 or \
                h < max(o, c) - 1e-9 or l > min(o, c) + 1e-9:
            out[d].add("ohlc_tutarsiz")
        if onceki is not None:
            if (o, h, l, c) == (onceki["open"], onceki["high"], onceki["low"], onceki["close"]) and not v:
                out[d].add("bayat")
            if onceki["close"] and c:
                g = c / onceki["close"] - 1
                if abs(g) > ESIK_10:
                    out[d].add("sicrama_10")
                if abs(g) > ESIK_25:
                    out[d].add("sicrama_25")
        onceki = b
    return out, eksik


def main():
    dbp, kabul, cikti = sys.argv[1:4]
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    rows = c.execute("SELECT ticker, date, open, high, low, close, volume FROM prices WHERE close IS NOT NULL "
                     "ORDER BY ticker, date").fetchall()
    bars = defaultdict(list)
    for tk, d, o, h, l, cl, v in rows:
        bars[tk].append({"date": d, "open": o, "high": h, "low": l, "close": cl, "volume": v})
    takvim = sorted({b["date"] for tk, bs in bars.items() if tk != "XU100" for b in bs})
    tix = {d: i for i, d in enumerate(takvim)}
    kap = defaultdict(list)
    for yayin, konu, hisseler in c.execute("SELECT yayin, konu, hisseler FROM kap_liste WHERE hisseler IS NOT NULL"):
        if konu and any(k.lower() in konu.lower() for k in KURUMSAL_KONU):
            for tk in hisseler.split(","):
                kap[tk.strip()].append(yayin[:10])
    for v in kap.values():
        v.sort()
    kap_ilk = c.execute("SELECT MIN(yayin) FROM kap_liste").fetchone()[0][:10]
    bayrak, ozet, sicramalar = {}, Counter(), []
    eksik_say, uzun = Counter(), []
    son_gun = {}
    for tk, bs in bars.items():
        if tk == "XU100":
            continue
        f, eksik = bayrakla(bs, tix, takvim)
        bayrak[tk] = f
        son_gun[tk] = bs[-1]["date"]
        eksik_say[tk] = len(eksik)
        ozet["mum"] += len(bs)
        ozet["eksik_gun"] += len(eksik)
        for d, s in f.items():
            for x in s:
                ozet[x] += 1
            if "sicrama_10" in s:
                gun = date.fromisoformat(d)
                lo, hi = (gun - timedelta(days=5)).isoformat(), (gun + timedelta(days=5)).isoformat()
                k = kap.get(tk, [])
                yakin = k[bisect_left(k, lo):bisect_left(k, hi + "z")]
                if yakin:
                    s.add("kurumsal_yakin")
                    ozet["sicrama_10_kurumsal_yakin"] += 1
                elif d < kap_ilk:
                    ozet["sicrama_10_kap_kapsami_disinda"] += 1
                i = next(j for j, b in enumerate(bs) if b["date"] == d)
                sicramalar.append({"ticker": tk, "gun": d, "getiri_%": round(100 * (bs[i]["close"] / bs[i - 1]["close"] - 1), 2),
                                   "kurumsal_yakin": bool(yakin), "uzun_bosluk_sonrasi": "uzun_bosluk_sonrasi" in s})
    # en son fiyat günü: bütün hisseler aynı güne kadar mı (eski fiyat / borsadan çıkış belirtisi)
    son = max(son_gun.values())
    geride = sorted(((tk, d) for tk, d in son_gun.items() if d < son), key=lambda x: x[1])
    # FAZ 2 kabul işlemlerine etkisi: işlemin sinyal penceresi (son 22 mum) ya da tutma süresi bayraklı mum içeriyor mu
    etki = {}
    for dosya in sorted(Path(kabul).glob("*_islemler.csv")):
        n, f_tut, f_sinyal, net_bayrakli, net_tum, tur = 0, 0, 0, 0.0, 0.0, Counter()
        f_250, net_250 = 0, 0.0
        for t in csv.DictReader(open(dosya, encoding="utf-8")):
            n += 1
            tk, g, cgun, sg = t["ticker"], t["giris_gunu"], t["cikis_gunu"], t["sinyal_gunu"]
            f = bayrak.get(tk, {})
            tut = {x for d, s in f.items() if g <= d <= cgun for x in s if x != "sifir_hacim"}
            bs = bars[tk]
            j = next(i for i, b in enumerate(bs) if b["date"] == sg)
            pencere = {b["date"] for b in bs[max(0, j - 21):j + 1]}
            sin = {x for d, s in f.items() if d in pencere for x in s if x != "sifir_hacim"}
            pen250 = {b["date"] for b in bs[max(0, j - 249):j + 1]}          # gösterge penceresi (etiketle.WIN)
            g250 = {x for d, s in f.items() if d in pen250 for x in s if x in ("sicrama_10", "sicrama_25", "ohlc_tutarsiz")}
            f_250 += bool(g250)
            if g250:
                net_250 += float(t["net_tl"])
            net_tum += float(t["net_tl"])
            if tut or sin:
                net_bayrakli += float(t["net_tl"])
                tur.update(tut | sin)
            f_tut += bool(tut)
            f_sinyal += bool(sin)
        etki[dosya.name] = {"islem": n, "tutma_suresinde_bayrak": f_tut, "sinyal_penceresinde_bayrak": f_sinyal,
                            "bayrakli_islem_net_tl": round(net_bayrakli, 2), "tum_net_tl": round(net_tum, 2),
                            "gosterge_penceresi_250_sicrama_veya_tutarsiz": f_250, "bu_islemlerin_net_tl": round(net_250, 2),
                            "bayrak_turleri": dict(tur)}
    sonuc = {"veritabani": dbp, "hisse": len(bayrak), "takvim_gunu": len(takvim), "fiyat_son_gun": son,
             "kap_liste_ilk_gun": kap_ilk, "ozet": dict(ozet),
             "sicrama_10_sayisi": len(sicramalar), "sicrama_ornekleri_en_buyuk": sorted(
                 sicramalar, key=lambda x: -abs(x["getiri_%"]))[:15],
             "sicrama_kurumsal_yakin_olmayan_ornek": [x for x in sorted(sicramalar, key=lambda x: -abs(x["getiri_%"]))
                                                      if not x["kurumsal_yakin"]][:10],
             "son_gune_kadar_gelmeyen_hisse": len(geride), "son_gune_kadar_gelmeyen_ornek": geride[:15],
             "eksik_gunu_en_cok": eksik_say.most_common(10),
             "faz2_kabul_islemlerine_etki": etki}
    Path(cikti).write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in sonuc.items() if k not in ("faz2_kabul_islemlerine_etki",)}, ensure_ascii=False)[:4000])
    for k, v in etki.items():
        print(k, v)


if __name__ == "__main__":
    main()
