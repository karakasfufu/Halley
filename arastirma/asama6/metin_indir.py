"""Aşama 6 / haber 2. aşama (Python, yapay zekâsız): plan sinyalinden önceki 5 günde yayımlanmış KAP bildirimlerinin
ANA METNİNİ (ek PDF'ler değil) araştırma veritabanına indirir. KAP bekleme süresi korunur; sınırda 5 dk beklenir;
kaldığı yerden devam eder. Kullanım: python metin_indir.py <repo> <arastirma.db> <etiket.csv> [konu-süzgeci]
"""
import sqlite3
import sys
import time
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, sys.argv[1])
from bist_haber import config, kap, tp1_model  # noqa: E402

conn = sqlite3.connect(sys.argv[2])
conn.execute("CREATE TABLE IF NOT EXISTS kap_metin (idx TEXT PRIMARY KEY, metin TEXT, alindi TEXT)")
konu = sys.argv[4] if len(sys.argv) > 4 else "Özel Durum Açıklaması (Genel)"
kl = pd.read_sql("SELECT idx, yayin, konu, hisseler FROM kap_liste WHERE konu LIKE ?", conn, params=(f"%{konu}%",))
ex = kl.assign(tk=kl.hisseler.str.split(",")).explode("tk")
d = pd.read_csv(sys.argv[3], dtype={"tarih": str}, usecols=["ticker", "tarih", "sonuc"])
d = d[d.sonuc.isin(["SL", "TP2", "başabaş (TP1 sonrası)", "süre doldu"])]
need = set()
g = dict(tuple(ex.groupby("tk")))
for tk, sub in d.groupby("ticker"):
    e = g.get(tk)
    if e is None:
        continue
    for day in sub.tarih.unique():
        lo = (date.fromisoformat(day) - timedelta(days=tp1_model.HABER_GUN)).isoformat() + "T18:00:00"
        need.update(e[(e.yayin > lo) & (e.yayin <= day + "T18:00:00")].idx)
have = {r[0] for r in conn.execute("SELECT idx FROM kap_metin")}
todo = sorted(need - have, key=int)
__import__("random").Random(7).shuffle(todo)   # karışık sıra: yarıda kalsa da her dönemden örnek olsun
print("gereken", len(need), "kalan", len(todo), flush=True)
t0 = time.time()
for i, idx in enumerate(todo):
    for k in range(6):
        try:
            body = kap._parse_page(kap._get(kap.DETAIL_URL.format(index=idx)).text)[0]
            break
        except kap.RateLimited:
            print("KAP sınırı, 5 dk bekleniyor", flush=True)
            time.sleep(300)
        except Exception as ex_:
            print("hata", idx, ex_, flush=True)
            time.sleep(30)
    else:
        print("bırakıldı", idx, flush=True)
        break
    conn.execute("INSERT OR REPLACE INTO kap_metin VALUES(?,?,?)", (idx, body, time.strftime("%Y-%m-%dT%H:%M:%S")))
    if i % 25 == 0:
        conn.commit()
        print(i, len(todo), round(time.time() - t0), "sn", flush=True)
    time.sleep(config.KAP_REQUEST_DELAY)
conn.commit()
print("bitti", conn.execute("SELECT COUNT(*), SUM(LENGTH(metin)>0) FROM kap_metin").fetchone(), flush=True)
