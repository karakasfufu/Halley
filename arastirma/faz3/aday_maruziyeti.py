"""FAZ 3 (araştırma; yalnız okur): evrendeki BÜTÜN planların (seçilen, elenen, sıralamada kalan) gösterge penceresinde
(sinyal gününe kadarki 250 mum) > %10,5 tek gün sıçrama olan pay. Seçim/sıralama belirsizliğinin büyüklüğü içindir;
planlar ve sonuçlar DEĞİŞTİRİLMEZ. Kullanım: python aday_maruziyeti.py <arastirma.db> <planlar.csv> <cikti.json>"""
import csv
import json
import sqlite3
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

db, pc, cikti = sys.argv[1:4]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
seri = defaultdict(list)
for tk, d, cl in c.execute("SELECT ticker, date, close FROM prices WHERE close IS NOT NULL ORDER BY ticker, date"):
    seri[tk].append((d, cl))
sic, gun = {}, {}
for tk, s in seri.items():
    gun[tk] = [d for d, _ in s]
    sic[tk] = [s[i][0] for i in range(1, len(s)) if s[i - 1][1] and abs(s[i][1] / s[i - 1][1] - 1) > 0.105]
out = {}
for evren, kosul in (("tum_planlar", lambda r: True),
                     ("canli_ortak", lambda r: r["risk"] != "yüksek" and float(r["teknik_skor"]) >= 5)):
    n = m = 0
    for r in csv.DictReader(open(pc, encoding="utf-8")):
        if not kosul(r):
            continue
        tk, d = r["ticker"], r["tarih"]
        g = gun.get(tk, [])
        j = bisect_right(g, d) - 1
        if j < 0:
            continue
        bas = g[max(0, j - 249)]
        n += 1
        s = sic.get(tk, [])
        m += bisect_right(s, d) - bisect_left(s, bas) > 0
    out[evren] = {"plan": n, "gosterge_penceresinde_sicrama": m, "oran_%": round(100 * m / n, 2) if n else None}
Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(out)
