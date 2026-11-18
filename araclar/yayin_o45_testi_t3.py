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
T = S / "yayin_o45_test_t3"
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
h = T / "tamkurulum"
db = h / "app" / "data" / "bist_haber.db"
ay = h / "app" / "data" / "ayarlar.json"
# ---------------- T3 tam kurulum (Halley_Kurulum.exe) mevcut verinin üstüne
rapor["T3_eski_kur"] = kur(ESKI_D / "Halley_Kurulum.exe", h)
rapor["T3_eski_surum"] = surum(h)
rapor["T3_eski_db"] = py(h, "import sys; sys.path.insert(0,'.'); from bist_haber import db; c=db.connect(); print(1)")
c = sqlite3.connect(str(db))
c.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('DNM','2026-11-12',1,2,1,2,10)")
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,durum,sonuc_json) VALUES('2026-11-10T19:00:00+03:00','2026-11-10','DNM','gercek','destek',100,95,104,110,5,'açık','{\"kural\": \"s3\"}')")
c.commit(); c.close()
ay.write_text(json.dumps({"deneme_isareti": "kullanici_verisi"}), encoding="utf-8")
(h / "app" / ".env").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
once3, ay3, env3 = tablo(db), sha(ay), sha(h / "app" / ".env")
rapor["T3_kur"] = kur(YENI / "Halley_Kurulum.exe", h)
rapor["T3_surum"] = surum(h)
rapor["T3_acilis_sn"] = ac(h)
kapat(h)
son = tablo(db)
c = sqlite3.connect(str(db)); rapor["T3_fiyat_iz_null"] = c.execute("SELECT COUNT(*), SUM(indirme_id IS NULL) FROM prices").fetchone(); c.close()
rapor["T3_yedekler"] = sorted(p.name for p in (h / "app" / "data" / "yedek").iterdir()) if (h / "app" / "data" / "yedek").exists() else []
rapor["T3_degisen_tablo"] = [t for t in once3 if not t.startswith("_") and once3[t] != son.get(t)]
rapor["T3_integrity"] = son["_integrity"]
rapor["T3_ayar_env_ayni"] = (sha(ay) == ay3, sha(h / "app" / ".env") == env3)
(S / "faz6" / "yayin_o45_testi_t3.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(rapor, ensure_ascii=False, indent=1, default=str))
