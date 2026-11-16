"""FAZ 3 (araştırma; veritabanlarını YALNIZ OKUR): veri bulgularının ayrıştırılması. KESİN NEDEN İDDİA ETMEZ.
  1) Eksik günler: (a) piyasa geneli düşük kapsamalı gün (o gün hisselerin < %50'si işlem görmüş → takvim şüpheli,
     işlem beklenmeyen gün olabilir); (b) ≥ 5 ardışık eksik (olası işlem durdurma; KAP'ta Borsa/BISTECH duyurusu
     varsa işaretlenir); (c) tekil/kısa eksik (olası veri eksikliği). İlk mumdan önceki günler sayılmaz; ilk mumu
     veritabanı başlangıcından sonra olan hisseler "halka arz ya da veri başlangıcı" (ayrılamadı) olarak sayılır.
  2) İki veritabanı farkı: her hisse için fark oranının örüntüsü (belli bir günden önceki bütün günlerde sabit oran =
     geriye dönük düzeltme ile UYUMLU; dağınık = başka neden). Yakın KAP kâr payı/sermaye bildirimi listelenir.
  3) Geçmiş tarihte erişilebilir veri: FAZ 2 kabul işlemlerinden tutma süresi ya da 250 günlük gösterge penceresi
     içinde KAP kâr payı / sermaye artırımı bildirimi olanlar (düzeltilmiş seriyle düzeltilmemiş gerçek fiyat
     ayrışabilir). Düzeltilmemiş fiyat elimizde olmadığından ETKİ ÖLÇÜLEMEDİ; yalnız maruz kalan işlem sayılır.
Kullanım: python veri_ayrintilari.py <arastirma.db> <canli.db> <kabul_klasoru> <cikti.json>"""
import csv
import json
import sqlite3
import sys
from bisect import bisect_left
from collections import Counter, defaultdict
from pathlib import Path

KAR_SERMAYE = ("Kar Payı", "Sermaye Artırımı", "Hak Kullanımı", "Bölünme", "Bedelsiz")
BORSA = ("BISTECH", "Borsa İstanbul", "Devre Kesici", "İşlem Sırası")


def kap_olaylari(c, anahtarlar):
    out = defaultdict(list)
    for yayin, konu, baslik, hisseler in c.execute("SELECT yayin, konu, baslik, hisseler FROM kap_liste "
                                                   "WHERE hisseler IS NOT NULL"):
        metin = f"{konu or ''} {baslik or ''}"
        if any(k.lower() in metin.lower() for k in anahtarlar):
            for tk in hisseler.split(","):
                out[tk.strip()].append(yayin[:10])
    for v in out.values():
        v.sort()
    return out


def aralikta(liste, bas, son):
    return liste[bisect_left(liste, bas):bisect_left(liste, son + "z")]


def main():
    adb, cdb, kabul, cikti = sys.argv[1:5]
    a = sqlite3.connect(f"file:{adb}?mode=ro", uri=True)
    bars = defaultdict(list)
    for tk, d, cl in a.execute("SELECT ticker, date, close FROM prices WHERE close IS NOT NULL ORDER BY ticker, date"):
        bars[tk].append((d, cl))
    bars.pop("XU100", None)
    kapsama = Counter(d for bs in bars.values() for d, _ in bs)
    takvim = sorted(kapsama)
    tix = {d: i for i, d in enumerate(takvim)}
    db_ilk = takvim[0]
    borsa = kap_olaylari(a, BORSA)
    kar = kap_olaylari(a, KAR_SERMAYE)
    kap_ilk = a.execute("SELECT MIN(yayin) FROM kap_liste").fetchone()[0][:10]
    # 1) eksik günler
    tur = Counter()
    ornek = defaultdict(list)
    gec_baslayan = 0
    for tk, bs in bars.items():
        if bs[0][0] > takvim[min(5, len(takvim) - 1)]:
            gec_baslayan += 1
        var = {d for d, _ in bs}
        aralik = takvim[tix[bs[0][0]]:tix[bs[-1][0]] + 1]
        seri = []
        for d in aralik + [None]:
            if d is not None and d not in var:
                seri.append(d)
                continue
            if seri:
                for g in seri:
                    if kapsama[g] < 0.5 * len(bars):
                        k = "piyasa_geneli_dusuk_kapsama"
                    elif len(seri) >= 5:
                        k = "olasi_islem_durdurma" + ("_kap_duyurusu_var" if aralikta(borsa.get(tk, []), seri[0],
                                                                                       seri[-1]) else "")
                    else:
                        k = "olasi_veri_eksikligi"
                    tur[k] += 1
                    if len(ornek[k]) < 6:
                        ornek[k].append((tk, g, len(seri)))
                seri = []
    dusuk_gunler = [(d, kapsama[d]) for d in takvim if kapsama[d] < 0.5 * len(bars)]
    # 2) iki veritabanı farkı örüntüsü
    c = sqlite3.connect(f"file:{cdb}?mode=ro", uri=True)
    canli = {(t, d): cl for t, d, cl in c.execute("SELECT ticker, date, close FROM prices WHERE close IS NOT NULL")}
    farklar = {}
    for tk, bs in bars.items():
        seri = [(d, cl / canli[(tk, d)] - 1) for d, cl in bs if canli.get((tk, d))]
        buyuk = [(d, x) for d, x in seri if abs(x) > 0.001]
        if not buyuk:
            continue
        son_fark = max(d for d, _ in buyuk)
        once = [x for d, x in seri if d <= son_fark]
        sonra = [x for d, x in seri if d > son_fark]
        sabit = max(once) - min(once) < 0.002 and all(abs(x) <= 0.001 for x in sonra)
        farklar[tk] = {"farkli_gun": len(buyuk), "ilk": min(d for d, _ in buyuk), "son": son_fark,
                       "oran_min_%": round(100 * min(once), 3), "oran_max_%": round(100 * max(once), 3),
                       "ornek": "belli günden önce sabit oran (geriye dönük düzeltmeyle UYUMLU)" if sabit else "dağınık",
                       "son_farktan_sonraki_10_gunde_kap_kar_sermaye": aralikta(kar.get(tk, []), son_fark,
                                                                                takvim[min(len(takvim) - 1, tix[son_fark] + 10)])}
    # 3) FAZ 2 kabul işlemlerinin kurumsal olaya maruziyeti
    maruz = {}
    for dosya in sorted(Path(kabul).glob("*_islemler.csv")):
        n = tut = pen = 0
        for t in csv.DictReader(open(dosya, encoding="utf-8")):
            n += 1
            tk = t["ticker"]
            k = kar.get(tk, [])
            if aralikta(k, t["giris_gunu"], t["cikis_gunu"]):
                tut += 1
            i = tix.get(t["sinyal_gunu"])
            if i is not None and aralikta(k, takvim[max(0, i - 249)], t["sinyal_gunu"]):
                pen += 1
        maruz[dosya.name] = {"islem": n, "tutma_suresinde_kap_kar_sermaye": tut, "gosterge_penceresinde": pen}
    out = {"not": "Neden kesinleştirilmedi; örüntü ve yakınlık yalnız UYUM gösterir. KAP listesi "
                  f"{kap_ilk} öncesini kapsamaz.",
           "eksik_gun_turleri": dict(tur), "eksik_gun_ornekleri": ornek,
           "piyasa_geneli_dusuk_kapsamali_gunler": dusuk_gunler,
           "veritabani_baslangicindan_sonra_baslayan_hisse": gec_baslayan, "veritabani_ilk_gun": db_ilk,
           "iki_veritabani_farki": farklar, "faz2_kabul_kurumsal_olay_maruziyeti": maruz}
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, default=str)[:3500])


if __name__ == "__main__":
    main()
