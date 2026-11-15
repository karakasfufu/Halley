"""Aşama 6: 5 yıllık günlük fiyatları AYRI araştırma veritabanına indirir (canlı veritabanı yalnız okunur)."""
import sqlite3, sys, time
sys.path.insert(0, sys.argv[1])
from bist_haber import db, prices
live, out = sys.argv[2], sys.argv[3]
s = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
tickers = sorted(r[0] for r in s.execute("SELECT DISTINCT ticker FROM prices"))
s.close()
from pathlib import Path
conn = db.connect(Path(out))
done = {r[0] for r in conn.execute("SELECT ticker FROM prices GROUP BY ticker HAVING COUNT(*)>300")}
todo = [t for t in tickers if t not in done]
print("hisse:", len(tickers), "indirilecek:", len(todo), flush=True)
t0 = time.time()
for i in range(0, len(todo), 50):
    part = todo[i:i + 50]
    for k in range(2):
        try:
            print(i, prices.update(conn, part, period="5y"), "satır", round(time.time() - t0), "sn", flush=True)
            break
        except Exception as e:
            print("hata", e, flush=True); time.sleep(10)
print("bitti", conn.execute("SELECT COUNT(DISTINCT ticker), COUNT(*), MIN(date), MAX(date) FROM prices").fetchone())
