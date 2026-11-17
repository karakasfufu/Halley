"""Pilot paket kurulum testleri (gerçek kurulum programlarıyla, scratch klasörlerinde; canlıya dokunmaz).
T1 temiz kurulum · T2 eski kararlı (v202611152318) → deneme verisi → pilot kurulumu (veri korunur) → pilot açılır →
T3 geri dönüş: eski kararlı kurulum dosyası pilotun üstüne (veri korunur) → eski sürüm açılır.
Gerçek API anahtarı YOK (.env boş anahtarlı); HALLEY_OFFLINE=1 ile açılır (güncelleme denetimi ve ağ işleri kapalı)."""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

S = Path(sys.argv[1])                      # scratchpad
PILOT = S / "pilot" / "Halley_Kurulum.exe"
ESKI = S / "eski_surum" / "Halley_Kurulum.exe"
T = S / "kurulum_test"
PORT = 8511
rapor = {}


def kur(exe, hedef, ek=()):
    t0 = time.time()
    r = subprocess.run([str(exe), "/sessiz", f"/hedef={hedef}", "/kisayolsuz", "/baslatma", *ek], timeout=900)
    log = (Path(os.environ["TEMP"]) / "halley_kurulum.log").read_text(encoding="utf-8", errors="replace")
    return {"kod": r.returncode, "sure_sn": round(time.time() - t0), "log": log[:300]}


def ac(hedef, sure=180):
    env = dict(os.environ, HALLEY_OFFLINE="1")
    subprocess.Popen([str(hedef / "Halley.exe"), "--pencere-yok", "--port", str(PORT)], cwd=str(hedef), env=env)
    t0 = time.time()
    while time.time() - t0 < sure:
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=3).read() == b"ok":
                return round(time.time() - t0)
        except Exception:
            time.sleep(2)
    return None


def kapat(hedef):
    subprocess.run([str(hedef / "Halley.exe"), "--kapat"], timeout=90)
    time.sleep(4)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).exists() else None


def tablo(db, tablolar=None):
    c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        if tablolar and t not in tablolar:
            continue
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
        h = hashlib.sha256()
        n = 0
        for r in c.execute(f'SELECT * FROM "{t}" ORDER BY rowid'):
            h.update(repr(tuple(r)).encode("utf-8"))
            n += 1
        out[t] = [n, h.hexdigest()[:12], len(cols)]
    out["_integrity"] = c.execute("PRAGMA integrity_check").fetchone()[0]
    c.close()
    return out


def surum(h):
    return ((h / "surum.txt").read_text(encoding="utf-8").strip() if (h / "surum.txt").exists() else None,
            (h / "surum_sira.txt").read_text(encoding="utf-8").strip() if (h / "surum_sira.txt").exists() else None)


if T.exists():
    shutil.rmtree(T)
T.mkdir()
# ---------------- T1 temiz kurulum
t1 = T / "temiz"
rapor["T1_kur"] = kur(PILOT, t1)
rapor["T1_surum"] = surum(t1)
rapor["T1_env_yok"] = not (t1 / "app" / ".env").exists()
rapor["T1_data"] = sorted(p.name for p in (t1 / "app" / "data").iterdir()) if (t1 / "app" / "data").exists() else None
rapor["T1_acilis_sn"] = ac(t1)
if rapor["T1_acilis_sn"] is not None:
    html = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=10).read()
    rapor["T1_sayfa_bayt"] = len(html)
    input_hint = S / "faz6" / "T1_ACIK"           # tarayıcı denetimi için işaret (betik dışından bakılır)
    input_hint.write_text(str(PORT), encoding="utf-8")
    bekle = S / "faz6" / "T1_BITTI"
    t0 = time.time()
    while not bekle.exists() and not os.environ.get("TARAYICI_ATLA") and time.time() - t0 < 900:
        time.sleep(3)
kapat(t1)
rapor["T1_data_sonra"] = sorted(p.name for p in (t1 / "app" / "data").iterdir())
rapor["T1_db"] = tablo(t1 / "app" / "data" / "bist_haber.db", {"tahmin", "harcama_rezervasyon", "ai_calls", "trade_journal"}) \
    if (t1 / "app" / "data" / "bist_haber.db").exists() else None
# ---------------- T2 eski kararlı → veri → pilot
t2 = T / "guncelleme"
rapor["T2_eski_kur"] = kur(ESKI, t2)
rapor["T2_eski_surum"] = surum(t2)
rapor["T2_eski_acilis_sn"] = ac(t2)
kapat(t2)
db = t2 / "app" / "data" / "bist_haber.db"
# eski sürüm veritabanını ilk panel oturumunda kurar: kurulu Python ve ESKİ kodla oluştur (gerçek kullanıcıdaki gibi)
r = subprocess.run([str(t2 / "python" / "python.exe"), "-c", "import sys; sys.path.insert(0, '.'); from bist_haber import db; "
                    "c = db.connect(); print(len(c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()))"],
                   cwd=str(t2 / "app"), capture_output=True, text=True, env=dict(os.environ, HALLEY_OFFLINE="1"))
rapor["T2_eski_db_tablo"] = r.stdout.strip() or r.stderr[-300:]
c = sqlite3.connect(str(db))
c.execute("INSERT OR IGNORE INTO companies VALUES('DNM','Deneme A.Ş.',NULL)")
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,durum) "
          "VALUES('2026-11-10T19:00:00+03:00','2026-11-10','DNM','otomatik','destek',100,95,104,110,5,'bekliyor')")
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
          "gercek_giris_gunu,gercek_giris_fiyati,durum,sonuc_json) VALUES('2026-11-10T19:00:00+03:00','2026-11-10','DNM',"
          "'gercek','destek',100,95,104,110,5,'2026-11-11',99.5,'açık','{\"durum\": \"açık\"}')")
c.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,subject,fetched_at,status) VALUES("
          "'kap:deneme','kap','2026-11-12T10:00:00+03:00','2026-11-12','Deneme haberi','metin','DNM','Yeni İş İlişkisi',"
          "'2026-11-12T10:05:00+03:00','new')")
c.commit()
c.close()
ay = t2 / "app" / "data" / "ayarlar.json"
d = json.loads(ay.read_text(encoding="utf-8-sig")) if ay.exists() else {}
d.update(sermaye=100000.0, risk_pct=1.0, deneme_isareti="kullanici_verisi")
ay.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
(t2 / "app" / ".env").write_text("# deneme: gerçek anahtar yok\nOPENAI_API_KEY=\n", encoding="utf-8")
once_db = tablo(db)
once = {"ayarlar": sha(ay), ".env": sha(t2 / "app" / ".env"), "db_dosya": sha(db)}
rapor["T2_veri_once"] = {"dosya": once, "tablo_sayisi": len(once_db) - 1, "integrity": once_db["_integrity"]}
rapor["T2_pilot_kur"] = kur(PILOT, t2)
rapor["T2_pilot_surum"] = surum(t2)
rapor["T2_kurulum_sonrasi_dosyalar_ayni"] = {"ayarlar": sha(ay) == once["ayarlar"], ".env": sha(t2 / "app" / ".env") == once[".env"],
                                             "db_dosya": sha(db) == once["db_dosya"]}
rapor["T2_yedek_klasoru"] = sorted(p.name for p in (t2 / "app" / "data" / "yedek").iterdir()) \
    if (t2 / "app" / "data" / "yedek").exists() else None
rapor["T2_pilot_kod_ayni"] = sha(t2 / "app" / "app_kod.pyc") == sha(S / "pilot" / "staging" / "app" / "app_kod.pyc")
rapor["T2_pilot_acilis_sn"] = ac(t2)
if rapor["T2_pilot_acilis_sn"] is not None:
    (S / "faz6" / "T2_ACIK").write_text(str(PORT), encoding="utf-8")
    t0 = time.time()
    while not (S / "faz6" / "T2_BITTI").exists() and time.time() - t0 < 900:
        time.sleep(3)
kapat(t2)
sonra_db = tablo(db)
rapor["T2_eski_tablolar_korundu"] = {t: once_db[t] == sonra_db.get(t) for t in once_db if not t.startswith("_")}
rapor["T2_degisen_eski_tablolar"] = {t: (once_db[t], sonra_db.get(t)) for t in once_db
                                     if not t.startswith("_") and once_db[t] != sonra_db.get(t)}
rapor["T2_yeni_tablolar"] = sorted(set(sonra_db) - set(once_db))
rapor["T2_integrity"] = sonra_db["_integrity"]
rapor["T2_ayarlar_isaret"] = json.loads(ay.read_text(encoding="utf-8-sig")).get("deneme_isareti")
rapor["T2_env_ayni"] = sha(t2 / "app" / ".env") == once[".env"]
# güncelleyicinin sürüm seçimi: pilot kurulu iken kararlı Latest manifesti → "guncel" (geri inmez)
kod = ("import sys, json; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from bist_haber import guncelleme as g;"
       "m = json.load(open(sys.argv[2], encoding='utf-8-sig')); print(json.dumps(g.degerlendir(m, Path(sys.argv[3]))))")
r = subprocess.run([str(t2 / "python" / "python.exe"), "-c", kod, str(t2 / "app"), str(S / "eski_surum" / "surum.json"), str(t2)],
                   capture_output=True, text=True, cwd=str(t2 / "app"), env=dict(os.environ, HALLEY_OFFLINE="1"))
rapor["T2_pilotta_kararli_manifest"] = r.stdout.strip() or r.stderr[-300:]
# ---------------- T3 geri dönüş: eski kararlı kurulum pilotun üstüne
pilot_sonrasi = tablo(db)
ay_once, env_once = sha(ay), sha(t2 / "app" / ".env")
rapor["T3_eski_kur"] = kur(ESKI, t2)
rapor["T3_surum"] = surum(t2)
rapor["T3_dosyalar_ayni"] = {"ayarlar": sha(ay) == ay_once, ".env": sha(t2 / "app" / ".env") == env_once}
rapor["T3_eski_kod_ayni"] = sha(t2 / "app" / "app_kod.pyc") != sha(S / "pilot" / "staging" / "app" / "app_kod.pyc")
rapor["T3_acilis_sn"] = ac(t2)
kapat(t2)
son = tablo(db)
rapor["T3_tablolar_korundu"] = {t: pilot_sonrasi[t][:2] == son.get(t, [None, None])[:2] for t in pilot_sonrasi
                                if not t.startswith("_")}
rapor["T3_degisen"] = {t: (pilot_sonrasi[t], son.get(t)) for t in pilot_sonrasi
                       if not t.startswith("_") and pilot_sonrasi[t][:2] != son.get(t, [None, None])[:2]}
rapor["T3_integrity"] = son["_integrity"]
(S / "faz6" / "kurulum_testi.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rapor, ensure_ascii=False, indent=1))
