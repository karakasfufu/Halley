"""FAZ 3 (araştırma; iki veritabanını YALNIZ OKUR): aynı hisse ve gün için iki ayrı indirmedeki fiyat farkı.
prices.update yfinance'tan auto_adjust=True ile indirir ve INSERT OR REPLACE ile yazar: her indirme geçmişi O GÜNÜN
düzeltme tabanıyla (temettü/bölünme) yeniden yazar; kaynak ve indirme zamanı saklanmaz. Bu betik, araştırma
veritabanı ile canlı veritabanının ortak günlerinde kapanış farkını ölçer.
Kullanım: python yeniden_duzeltme.py <arastirma.db> <canli.db> <cikti.json>"""
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


def main():
    a_db, c_db, cikti = sys.argv[1:4]
    a = sqlite3.connect(f"file:{a_db}?mode=ro", uri=True)
    c = sqlite3.connect(f"file:{c_db}?mode=ro", uri=True)
    canli = {(t, d): cl for t, d, cl in c.execute("SELECT ticker, date, close FROM prices WHERE close IS NOT NULL")}
    fark = defaultdict(list)
    n = 0
    for t, d, cl in a.execute("SELECT ticker, date, close FROM prices WHERE close IS NOT NULL"):
        k = canli.get((t, d))
        if k:
            n += 1
            fark[t].append((d, cl / k - 1))
    esik = [0.001, 0.01, 0.05]
    say = {e: sum(1 for v in fark.values() for _, x in v if abs(x) > e) for e in esik}
    hisse = {e: sum(1 for v in fark.values() if any(abs(x) > e for _, x in v)) for e in esik}
    en = sorted(((t, max(v, key=lambda z: abs(z[1]))) for t, v in fark.items()), key=lambda z: -abs(z[1][1]))[:12]
    out = {"ortak_gun_sayisi": n, "ortak_hisse": len(fark),
           "fark_esigi_ustu_gun": {f"%{e*100:g}": say[e] for e in esik},
           "fark_esigi_ustu_hisse": {f"%{e*100:g}": hisse[e] for e in esik},
           "en_buyuk_farklar": [(t, d, round(100 * x, 3)) for t, (d, x) in en],
           "canli_tarih_araligi": c.execute("SELECT MIN(date), MAX(date) FROM prices").fetchone()}
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
