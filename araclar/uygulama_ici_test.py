"""Eski KARARLI müşteri sürümünden (v202611152318) yeni sürüme UYGULAMA İÇİ güncelleme — müşterinin yaşayacağı yol:
eski sürümün KENDİ guncelleme.hazirla'sı (indirme yerel dosyadan; SHA-256, güvenli açma, içe aktarma denemesi) →
Halley.exe --yeniden-baslat (başlatıcı kodu değiştirir, önceki sürümü saklar). Ardından veri/ayar/.env korunması, s3
damgaları ve "önceki sürüme dön" engeli. Gerçek API anahtarı yok; ağ yok (HALLEY_OFFLINE)."""
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

S = Path(sys.argv[1])
YENI = Path(sys.argv[2])                       # paket klasörü (Halley_Guncelleme.zip + surum.json)
ESKI = S / "eski_surum" / "Halley_Kurulum.exe"
T = S / "uygulama_ici_test"
H = T / "Halley"
PORT = 8512
rapor = {}


def ac(sure=180):
    subprocess.Popen([str(H / "Halley.exe"), "--pencere-yok", "--port", str(PORT)], cwd=str(H),
                     env=dict(os.environ, HALLEY_OFFLINE="1"))
    return saglik(sure)


def saglik(sure=180):
    t0 = time.time()
    while time.time() - t0 < sure:
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=3).read() == b"ok":
                return round(time.time() - t0)
        except Exception:
            time.sleep(2)
    return None


def kapat():
    subprocess.run([str(H / "Halley.exe"), "--kapat"], timeout=90)
    time.sleep(4)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).exists() else None


def py(kod, *arg):
    r = subprocess.run([str(H / "python" / "python.exe"), "-c", kod, *arg], cwd=str(H / "app"), capture_output=True,
                       text=True, env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows", "PYTHONUTF8": "1",
                                       "PATH": os.environ.get("PATH", "")})
    return (r.stdout.strip() or r.stderr.strip()[-600:])


if T.exists():
    shutil.rmtree(T)
T.mkdir()
r = subprocess.run([str(ESKI), "/sessiz", f"/hedef={H}", "/kisayolsuz", "/baslatma"], timeout=900)
rapor["eski_kurulum"] = (r.returncode, (H / "surum.txt").read_text(encoding="utf-8").strip())
rapor["eski_db_tablo"] = py("import sys; sys.path.insert(0,'.'); from bist_haber import db; c=db.connect(); "
                            "print(len(c.execute(\"select name from sqlite_master where type='table'\").fetchall()))")
db = H / "app" / "data" / "bist_haber.db"
c = sqlite3.connect(str(db))
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,durum) "
          "VALUES('2026-11-10T19:00:00+03:00','2026-11-10','DNM','otomatik','destek',100,95,104,110,5,'bekliyor')")
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
          "gercek_giris_gunu,gercek_giris_fiyati,durum,sonuc_json) VALUES('2026-11-10T19:00:00+03:00','2026-11-10','DNM',"
          "'gercek','destek',100,95,104,110,5,'2026-11-11',99.5,'açık','{\"durum\": \"açık\"}')")
c.commit()
c.close()
ay = H / "app" / "data" / "ayarlar.json"
ay.write_text(json.dumps({"sermaye": 100000.0, "risk_pct": 1.0, "haber_butce_usd": 7.0, "deneme": "kullanici"},
                         ensure_ascii=False), encoding="utf-8")
(H / "app" / ".env").write_text("# deneme: gerçek anahtar yok\nOPENAI_API_KEY=\n", encoding="utf-8")
once = {"ayarlar": sha(ay), ".env": sha(H / "app" / ".env")}
c = sqlite3.connect(str(db))
once_jr = [tuple(x) for x in c.execute("SELECT id,ticker,kaynak,giris,sl,gercek_giris_gunu,gercek_giris_fiyati FROM trade_journal")]
c.close()
# ---- eski sürümün KENDİ güncelleyicisiyle hazırla (yerel dosya = yayımlanacak paket)
m = json.loads((YENI / "surum.json").read_text(encoding="utf-8"))
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
print(json.dumps({'degerlendir': g.degerlendir(m, g.kok())['durum'], 'kurulu': g.kurulu(g.kok())}))
print(json.dumps(g.hazirla(m, getter=lambda u: R())))
"""
rapor["eski_guncelleyici"] = py(kod, str(YENI / "surum.json"), str(YENI / "Halley_Guncelleme.zip"))
rapor["hazir_json"] = (H / "guncelleme" / "hazir.json").exists()
# ---- başlatıcı: yeniden başlatırken güncellemeyi uygular
subprocess.Popen([str(H / "Halley.exe"), "--yeniden-baslat", "--pencere-yok", "--port", str(PORT)], cwd=str(H),
                 env=dict(os.environ, HALLEY_OFFLINE="1"))
rapor["yeni_acilis_sn"] = saglik(240)
time.sleep(5)
rapor["yeni_surum"] = ((H / "surum.txt").read_text(encoding="utf-8").strip(), (H / "surum_sira.txt").read_text(encoding="utf-8").strip())
rapor["son_islem"] = json.loads((H / "guncelleme" / "son_islem.json").read_text(encoding="utf-8-sig")) \
    if (H / "guncelleme" / "son_islem.json").exists() else None
rapor["onceki_var"] = (H / "guncelleme" / "onceki" / "app.py").exists()
rapor["kod_yeni_paketle_ayni"] = sha(H / "app" / "app_kod.pyc") == hashlib.sha256(
    __import__("zipfile").ZipFile(YENI / "Halley_Guncelleme.zip").read("app_kod.pyc")).hexdigest()[:16]
(S / "faz6" / "UI_ACIK").write_text(str(PORT), encoding="utf-8")     # tarayıcıyla panel denetimi
t0 = time.time()
while not (S / "faz6" / "UI_BITTI").exists() and time.time() - t0 < 900:
    time.sleep(3)
kapat()
# ---- yeni kodla (kurulu) günlük güncellemesi: s3 damgaları, eski kayıtların kuralı
rapor["yeni_kod_gunluk"] = py("import sys; sys.path.insert(0,'.'); from bist_haber import db, journal; c=db.connect(); "
                              "print(journal.update_all(c, 0.2, 0.1)['degerlendirilen'])")
c = sqlite3.connect(str(db))
rapor["kayit_kurallari"] = [(i, k, d, (json.loads(s or "{}") or {}).get("kural")) for i, k, d, s in
                            c.execute("SELECT id,kaynak,durum,sonuc_json FROM trade_journal")]
rapor["kullanici_alanlari_ayni"] = [tuple(x) for x in c.execute(
    "SELECT id,ticker,kaynak,giris,sl,gercek_giris_gunu,gercek_giris_fiyati FROM trade_journal")] == once_jr
rapor["tablolar"] = len(c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
rapor["integrity"] = c.execute("PRAGMA integrity_check").fetchone()[0]
c.close()
rapor["ayarlar_env_korundu"] = {"ayarlar_deger": json.loads(ay.read_text(encoding="utf-8-sig")).get("deneme") == "kullanici"
                                and json.loads(ay.read_text(encoding="utf-8-sig")).get("haber_butce_usd") == 7.0,
                                ".env": sha(H / "app" / ".env") == once[".env"]}
# ---- "önceki sürüme dön" (eski kararlı s3'ü tanımaz, s3 damgası var) → engellenmeli
rapor["geri_don_engeli"] = py("import sys; sys.path.insert(0,'.'); from bist_haber import guncelleme as g\n"
                              "try:\n    g.geri_don_iste(); print('GERI_DON_KABUL')\nexcept RuntimeError as e:\n    print('ENGEL:', str(e)[:120])")
rapor["geri_don_dosyasi_yok"] = not (H / "guncelleme" / "geri_don.txt").exists()
(S / "faz6" / "uygulama_ici_test.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rapor, ensure_ascii=False, indent=1))
