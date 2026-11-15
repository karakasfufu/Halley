"""Aşama 6 / haber 1. aşama: KAP bildirim LİSTELERİNİ (metin değil) araştırma veritabanına indirir. Yapay zekâ yok.
KAP bekleme süresi (config.KAP_REQUEST_DELAY) kap.list_disclosures içinde korunur. Kaldığı yerden devam eder.
Kullanım: python kap_liste.py <repo> <arastirma.db> <ilk-gün> <son-gün>
"""
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, sys.argv[1])
from bist_haber import kap  # noqa: E402

conn = sqlite3.connect(sys.argv[2])
conn.execute("""CREATE TABLE IF NOT EXISTS kap_liste (idx TEXT PRIMARY KEY, yayin TEXT NOT NULL, konu TEXT,
    ozet TEXT, baslik TEXT, hisseler TEXT, ham TEXT)""")
conn.execute("CREATE TABLE IF NOT EXISTS kap_liste_aralik (bas TEXT PRIMARY KEY, son TEXT NOT NULL, adet INTEGER)")
d0, d1 = date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])
done = {r[0] for r in conn.execute("SELECT bas FROM kap_liste_aralik")}
d = d0
while d <= d1:
    e = min(d + timedelta(days=6), d1, date(d.year, 12, 31))
    if d.isoformat() not in done:
        for k in range(6):
            try:
                items = kap.list_disclosures(d, e)
                break
            except Exception as ex:          # 429 ya da bağlantı: bekle, tekrar dene
                print("hata", d, ex, flush=True)
                __import__("time").sleep(300)   # KAP sınırı: 5 dk bekle
        else:
            print("bırakıldı", d, flush=True)
            break
        for it in items:
            pub = datetime.strptime(it["publishDate"], "%d.%m.%Y %H:%M:%S").isoformat()
            conn.execute("INSERT OR REPLACE INTO kap_liste VALUES(?,?,?,?,?,?,?)",
                         (str(it["disclosureIndex"]), pub, it.get("subject"), it.get("summary"), it.get("kapTitle"),
                          ",".join(kap._tickers(it)), json.dumps(it, ensure_ascii=False)))
        conn.execute("INSERT OR REPLACE INTO kap_liste_aralik VALUES(?,?,?)", (d.isoformat(), e.isoformat(), len(items)))
        conn.commit()
        print(d, e, len(items), flush=True)
    d = e + timedelta(days=1)
print("bitti", conn.execute("SELECT COUNT(*), MIN(yayin), MAX(yayin) FROM kap_liste").fetchone(), flush=True)
