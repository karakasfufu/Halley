"""O4+O5 müşteri paketi testleri (gerçek kurulum programlarıyla, scratch klasörlerinde; canlıya dokunmaz; ağ yok).
T1 temiz kurulum → açılır → O4 tabloları kurulur, izleme dosyası yok.
T2 güncel müşteri sürümü (v202611171741) kurulur → deneme verisi (fiyat, s3 damgalı kayıt, ayarlar, .env) →
   o sürümün KENDİ güncelleyicisiyle uygulama içi güncelleme (yerel zip) → başlatıcı yeniden başlatır → veri/ayar/.env
   korunur, O4 göçü yedekli, eski fiyatların izi "bilinmiyor" (NULL), önceki sürüm s3'ü tanıdığı için geri dönüş serbest.
T3 aynı kurulumun üstüne yeni Halley_Kurulum.exe (tam kurulum yolu) → veri korunur, açılır.
Kullanım: python yayin_o45_testi.py <scratchpad> <yeni_paket_klasoru> <guncel_musteri_paket_klasoru>"""
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

S, YENI, ESKI_D = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
T = S / "yayin_o45_test"
PORT = 8516
rapor = {}


def kur(exe, hedef):
    t0 = time.time()
    r = subprocess.run([str(exe), "/sessiz", f"/hedef={hedef}", "/kisayolsuz", "/baslatma"], timeout=900)
    return {"kod": r.returncode, "sure_sn": round(time.time() - t0)}


def saglik(sure=180):
    t0 = time.time()
    while time.time() - t0 < sure:
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=3).read() == b"ok":
                return round(time.time() - t0)
        except Exception:
            time.sleep(2)
    return None


def ac(h, ek=()):
    subprocess.Popen([str(h / "Halley.exe"), *ek, "--pencere-yok", "--port", str(PORT)], cwd=str(h),
                     env=dict(os.environ, HALLEY_OFFLINE="1"))
    s = saglik(240)
    if s is not None:   # paneli bir kez gerçekten açtır (oturum: veritabanı + göç)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=10).read()
        except Exception:
            pass
        time.sleep(8)
    return s


def kapat(h):
    subprocess.run([str(h / "Halley.exe"), "--kapat"], timeout=90)
    time.sleep(5)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).exists() else None


def surum(h):
    return tuple((h / f).read_text(encoding="utf-8").strip() if (h / f).exists() else None
                 for f in ("surum.txt", "surum_sira.txt"))


def py(h, kod, *arg):
    r = subprocess.run([str(h / "python" / "python.exe"), "-c", kod, *arg], cwd=str(h / "app"), capture_output=True,
                       text=True, env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows", "PYTHONUTF8": "1",
                                       "PATH": os.environ.get("PATH", "")})
    return r.stdout.strip() or r.stderr.strip()[-600:]


def tablo(db):
    c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")') if not (t == "prices" and r[1] == "indirme_id")]
        h, n = hashlib.sha256(), 0
        for r in c.execute(f'SELECT {",".join(chr(34) + x + chr(34) for x in cols)} FROM "{t}" ORDER BY rowid'):
            h.update(repr(tuple(r)).encode("utf-8"))
            n += 1
        out[t] = [n, h.hexdigest()[:12]]
    out["_integrity"] = c.execute("PRAGMA integrity_check").fetchone()[0]
    c.close()
    return out


if T.exists():
    shutil.rmtree(T)
T.mkdir()
# ---------------- T1 temiz kurulum
t1 = T / "temiz"
rapor["T1_kur"] = kur(YENI / "Halley_Kurulum.exe", t1)
rapor["T1_surum"] = surum(t1)
rapor["T1_env_yok"] = not (t1 / "app" / ".env").exists()
rapor["T1_acilis_sn"] = ac(t1)
kapat(t1)
rapor["T1_data"] = sorted(p.name for p in (t1 / "app" / "data").iterdir())
db1 = t1 / "app" / "data" / "bist_haber.db"
if db1.exists():
    c = sqlite3.connect(str(db1))
    rapor["T1_o4_tablolar"] = sorted(r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE name IN ('fiyat_indirme','fiyat_eski','veri_anlik')"))
    c.close()
rapor["T1_izleme_dosyasi_yok"] = not any(p.name.startswith("izleme") for p in (t1 / "app" / "data").iterdir())
# ---------------- T2 güncel müşteri sürümü → veri → uygulama içi güncelleme
h = T / "guncelleme"
rapor["T2_eski_kur"] = kur(ESKI_D / "Halley_Kurulum.exe", h)
rapor["T2_eski_surum"] = surum(h)
rapor["T2_eski_db"] = py(h, "import sys; sys.path.insert(0,'.'); from bist_haber import db; c=db.connect(); "
                            "print(len(c.execute(\"select name from sqlite_master where type='table'\").fetchall()))")
db = h / "app" / "data" / "bist_haber.db"
c = sqlite3.connect(str(db))
c.execute("INSERT OR IGNORE INTO companies VALUES('DNM','Deneme A.Ş.',NULL)")
for i, gun in enumerate(("2026-11-12", "2026-11-13", "2026-11-14")):
    c.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('DNM',?,?,?,?,?,1000)",
              (gun, 100 + i, 102 + i, 99 + i, 101 + i))
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,durum) "
          "VALUES('2026-11-10T19:00:00+03:00','2026-11-10','DNM','otomatik','destek',100,95,104,110,5,'bekliyor')")
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
          "gercek_giris_gunu,gercek_giris_fiyati,durum,sonuc_json) VALUES('2026-11-10T19:00:00+03:00','2026-11-10','DNM',"
          "'gercek','destek',100,95,104,110,5,'2026-11-11',99.5,'açık','{\"durum\": \"açık\", \"kural\": \"s3\"}')")
c.commit()
c.close()
ay = h / "app" / "data" / "ayarlar.json"
d = json.loads(ay.read_text(encoding="utf-8-sig")) if ay.exists() else {}
d.update(sermaye=100000.0, haber_butce_usd=7.0, deneme_isareti="kullanici_verisi")
ay.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
(h / "app" / ".env").write_text("# deneme: gerçek anahtar yok\nOPENAI_API_KEY=\n", encoding="utf-8")
once_db = tablo(db)
once = {"ayarlar": sha(ay), ".env": sha(h / "app" / ".env")}
kod = r"""
import sys, json; sys.path.insert(0, '.')
from bist_haber import guncelleme as g
m = json.load(open(sys.argv[1], encoding='utf-8')); zp = sys.argv[2]
class R:
    def raise_for_status(self): pass
    def iter_content(self, n):
        with open(zp, 'rb') as f:
            while True:
                b = f.read(n)
                if not b: break
                yield b
print(json.dumps({'degerlendir': g.degerlendir(m, g.kok())['durum']}))
print(json.dumps(g.hazirla(m, getter=lambda u: R())))
"""
rapor["T2_eski_guncelleyici"] = py(h, kod, str(YENI / "surum.json"), str(YENI / "Halley_Guncelleme.zip"))
rapor["T2_yeni_acilis_sn"] = ac(h, ("--yeniden-baslat",))
kapat(h)
rapor["T2_yeni_surum"] = surum(h)
rapor["T2_son_islem"] = json.loads((h / "guncelleme" / "son_islem.json").read_text(encoding="utf-8-sig")) \
    if (h / "guncelleme" / "son_islem.json").exists() else None
rapor["T2_kod_paketle_ayni"] = sha(h / "app" / "app_kod.pyc") == hashlib.sha256(
    __import__("zipfile").ZipFile(YENI / "Halley_Guncelleme.zip").read("app_kod.pyc")).hexdigest()[:16]
rapor["T2_onceki_var"] = (h / "guncelleme" / "onceki" / "app.py").exists() or \
    any((h / "guncelleme" / "onceki").glob("*")) if (h / "guncelleme" / "onceki").exists() else False
sonra = tablo(db)
rapor["T2_degisen_eski_tablo"] = [t for t in once_db if not t.startswith("_") and once_db[t] != sonra.get(t)]
rapor["T2_yeni_tablo"] = sorted(set(sonra) - set(once_db))
rapor["T2_integrity"] = sonra["_integrity"]
c = sqlite3.connect(str(db))
rapor["T2_fiyat_iz_null"] = c.execute("SELECT COUNT(*), SUM(indirme_id IS NULL) FROM prices").fetchone()
c.close()
rapor["T2_goc_yedegi"] = sorted(p.name for p in (h / "app" / "data" / "yedek").glob("*fiyat_izi_oncesi*")) \
    if (h / "app" / "data" / "yedek").exists() else []
rapor["T2_ayar_env_korundu"] = {"ayarlar": json.loads(ay.read_text(encoding="utf-8-sig")).get("deneme_isareti") == "kullanici_verisi",
                                ".env": sha(h / "app" / ".env") == once[".env"]}
rapor["T2_geri_don"] = py(h, "import sys; sys.path.insert(0,'.'); from bist_haber import guncelleme as g\n"
                             "print('ENGEL: ' + str(g.geri_donus_engeli(g.kok())) if g.geri_donus_engeli(g.kok()) else 'serbest (önceki s3 tanır)')")
rapor["T2_izleme"] = py(h, "import sys, json; sys.path.insert(0,'.'); from bist_haber import db, izleme; c = db.connect(); "
                           "print(json.dumps({'k1': izleme.UYARI_OLCUTLERI, 'grup': [(x['grup'].get('kural_surum'), "
                           "x.get('neden')) for x in izleme.degerlendir(c)]}, ensure_ascii=False))")
# ---------------- T3 tam kurulum (Halley_Kurulum.exe) mevcut verinin üstüne
once3, ay3, env3 = tablo(db), sha(ay), sha(h / "app" / ".env")
rapor["T3_kur"] = kur(YENI / "Halley_Kurulum.exe", h)
rapor["T3_surum"] = surum(h)
rapor["T3_acilis_sn"] = ac(h)
kapat(h)
son = tablo(db)
rapor["T3_degisen_tablo"] = [t for t in once3 if not t.startswith("_") and once3[t] != son.get(t)]
rapor["T3_integrity"] = son["_integrity"]
rapor["T3_ayar_env_ayni"] = (sha(ay) == ay3, sha(h / "app" / ".env") == env3)
(S / "faz6" / "yayin_o45_testi.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(rapor, ensure_ascii=False, indent=1, default=str))
