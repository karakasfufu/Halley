"""O4 kopya provası (canlı SALT-OKUR kopyalanır; ağ yok; yfinance taklit). A = canlı kod (edcac9d), B = O4 kodu.
1) B ile ilk açılış: yedekli göç; eski tabloların içeriği aynı, prices yalnız yeni sütun (NULL); süre/boyut.
2) B ile taklit fiyat indirmesi: indirme kaydı, değişen satırın eskisi, değişmeyen satırlara dokunulmaması.
3) Geri dönüş: A (eski kod) göç edilmiş kopyada açılır, fiyat yazar, temel işler çalışır; tam dönüş için yedek
   bütünlüğü ve göç öncesiyle eşitliği."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

W, K, P = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
PY = Path.home() / ".venvs" / "bist-haber" / "Scripts" / "python.exe"
O4 = ["bist_haber/fiyat_izi.py", "bist_haber/db.py", "bist_haber/prices.py", "app.py"]


def kopya(ad, kod_kaynak):
    d = P / ad
    if d.exists():
        shutil.rmtree(d)
    (d / "data").mkdir(parents=True)
    for k in ("app.py", "bist_haber"):
        s = kod_kaynak / k
        (shutil.copytree(s, d / k, ignore=shutil.ignore_patterns("__pycache__")) if s.is_dir() else shutil.copy2(s, d / k))
    src = sqlite3.connect(f"file:{(W / 'data' / 'bist_haber.db').as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(d / "data" / "bist_haber.db"))
    src.backup(dst)
    dst.close()
    src.close()
    return d


def ozet(db, haric_sutun=()):
    c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")') if r[1] not in haric_sutun]
        h, n = hashlib.sha256(), 0
        for r in c.execute(f'SELECT {",".join(chr(34) + x + chr(34) for x in cols)} FROM "{t}" ORDER BY rowid'):
            h.update(repr(tuple(r)).encode("utf-8"))
            n += 1
        out[t] = [n, h.hexdigest()[:16]]
    out["_integrity"] = c.execute("PRAGMA integrity_check").fetchone()[0]
    out["_tetikleyici"] = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0]
    c.close()
    return out


def calistir(d, kod):
    r = subprocess.run([str(PY), "-c", kod, str(d)], capture_output=True, text=True, cwd=str(d),
                       env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows", "PYTHONUTF8": "1"})
    if r.returncode:
        raise SystemExit(f"{d.name}: {r.stderr[-1200:]}")
    return r.stdout.strip()


ONEK = ("import sys, json, time; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from bist_haber import config;"
        "config.DATA = Path(sys.argv[1]) / 'data'; config.DB_PATH = config.DATA / 'bist_haber.db';")
TAKLIT = (" import pandas as pd; from unittest.mock import patch; from bist_haber import prices;"
          " c0 = db.connect(); son = c0.execute(\"SELECT ticker, date, open, high, low, close, volume FROM prices WHERE "
          "ticker IN ('BAHKM','ENERY','METRO') AND date>=date((SELECT MAX(date) FROM prices), '-6 day') ORDER BY ticker, "
          "date\").fetchall();"
          " parca = {};"
          "\nfor tk in ('BAHKM','ENERY','METRO'):"
          "\n    s = [r for r in son if r[0]==tk]; kap = [r[5] for r in s]"
          "\n    if tk == 'ENERY': kap[0] = round(kap[0] * 1.01, 4)"
          "\n    parca[tk + '.IS'] = pd.DataFrame({'Open': [r[2] for r in s], 'High': [r[3] for r in s], 'Low': [r[4] for r in s], "
          "'Close': kap, 'Volume': [r[6] for r in s]}, index=pd.to_datetime([r[1] for r in s]))"
          "\ndf = pd.concat(parca, axis=1)"
          "\nwith patch.object(prices.yf, 'download', return_value=df):"
          "\n    n = prices.update(c0, ['BAHKM','ENERY','METRO'], period='1mo')")

P.mkdir(parents=True, exist_ok=True)
rapor = {}
b = kopya("B", W)
for f in O4:
    shutil.copy2(K / f, b / f)
once = ozet(b / "data" / "bist_haber.db")
boyut_once = (b / "data" / "bist_haber.db").stat().st_size
cikti = calistir(b, ONEK + " t0 = time.time(); from bist_haber import db, fiyat_izi; c = db.connect();"
                 " print(json.dumps({'kurulu': fiyat_izi.kurulu(c), 'sure_sn': round(time.time() - t0, 2)}))")
rapor["B_ilk_acilis"] = json.loads(cikti)
sonra = ozet(b / "data" / "bist_haber.db", haric_sutun=("indirme_id",))
rapor["B_yeni_tablolar"] = sorted(set(sonra) - set(once))
rapor["B_degisen_eski_tablo"] = [t for t in once if not t.startswith("_") and once[t] != sonra.get(t)]
rapor["B_tetikleyici"] = (once["_tetikleyici"], sonra["_tetikleyici"])
rapor["B_integrity"] = sonra["_integrity"]
c = sqlite3.connect(str(b / "data" / "bist_haber.db"))
rapor["B_indirme_id_null"] = c.execute("SELECT COUNT(*), SUM(indirme_id IS NULL) FROM prices").fetchone()
c.close()
yedekler = sorted((b / "data" / "yedek").glob("*_fiyat_izi_oncesi.db"))
rapor["B_yedek"] = [y.name for y in yedekler]
yo = ozet(yedekler[0])
rapor["B_yedek_esit_goc_oncesi"] = all(yo.get(t) == once.get(t) for t in once if not t.startswith("_"))
rapor["B_yedek_integrity"] = yo["_integrity"]
rapor["boyut_bayt"] = (boyut_once, (b / "data" / "bist_haber.db").stat().st_size)
# 2) taklit indirme
cikti = calistir(b, ONEK + " from bist_haber import db;" + TAKLIT + "\nprint(json.dumps({'yazilan': n, 'son': prices.son_indirme(c0)}, default=str))")
rapor["B_taklit_indirme"] = json.loads(cikti)
c = sqlite3.connect(str(b / "data" / "bist_haber.db"))
rapor["B_fiyat_eski"] = [tuple(r) for r in c.execute("SELECT indirme_id, ticker, date, close, onceki_indirme_id FROM fiyat_eski")]
rapor["B_indirme_id_dolu"] = c.execute("SELECT COUNT(*) FROM prices WHERE indirme_id IS NOT NULL").fetchone()[0]
c.close()
sonra2 = ozet(b / "data" / "bist_haber.db", haric_sutun=("indirme_id",))
rapor["B_indirme_sonrasi_degisen"] = [t for t in once if not t.startswith("_") and once[t] != sonra2.get(t)]
# 3) geri dönüş: eski kod (A) göç edilmiş kopyada
a = kopya("A", W)
shutil.copy2(b / "data" / "bist_haber.db", a / "data" / "bist_haber.db")
cikti = calistir(a, ONEK + " from bist_haber import db, report, defter; c = db.connect();"
                 + TAKLIT.replace("c0 = db.connect()", "c0 = c") +
                 "\nrows = report.build(c, {r[0]: r[1] for r in c.execute('SELECT * FROM companies')});"
                 "print(json.dumps({'eski_kod_yazdi': n, 'rapor_satir': len(rows), 'sonuclandir': defter.sonuclandir(c)}, default=str))")
rapor["A_eski_kod_gocmus_db"] = json.loads(cikti)
ac = ozet(a / "data" / "bist_haber.db", haric_sutun=("indirme_id",))
rapor["A_integrity"] = ac["_integrity"]
c = sqlite3.connect(str(a / "data" / "bist_haber.db"))
rapor["A_eski_kod_sonrasi_indirme_kaydi"] = c.execute("SELECT COUNT(*) FROM fiyat_indirme").fetchone()[0]
c.close()
(P / "o4_prova.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(rapor, ensure_ascii=False, indent=1, default=str))
