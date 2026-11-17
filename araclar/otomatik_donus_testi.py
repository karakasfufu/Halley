"""Başlatıcının OTOMATİK geri dönüşü, gerçek kurulumla (eski kararlı v202611152318 → yeni sürüm, uygulama içi güncelleme):
yeni sürümün paneli bilerek başlatılamaz hâle getirilir (test için hazırlanan 'yeni' klasördeki .streamlit/config.toml
bozulur) → başlatıcı 120 sn sonra önceki sürüme dönmeye çalışır.
 A: veritabanında ÖNCEDEN s3 kaydı var (s3'ü tanımayan eski sürüm önceki) → uyumsuz koda dönüş OLMAMALI; s3 kayıtları
    silinmemeli; kod yeni kalmalı.
 B: s3 kaydı yok → güvenli otomatik dönüş eskisi gibi çalışmalı; veri korunmalı.
Ağ yok (HALLEY_OFFLINE; okuyucu KAP/fiyata çıkmaz değil — HALLEY_OKUYUCU_KAPALI verilmez ki gerçek okuyucu davranışı sınansın)."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

S = Path(sys.argv[1])
YENI = Path(sys.argv[2])
SENARYO = sys.argv[3]                       # A | B
ESKI = S / "eski_surum" / "Halley_Kurulum.exe"
H = S / f"otodonus_{SENARYO}" / "Halley"
PORT = 8513 if SENARYO == "A" else 8514


def py(kod, *arg):
    r = subprocess.run([str(H / "python" / "python.exe"), "-c", kod, *arg], cwd=str(H / "app"), capture_output=True,
                       text=True, env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows", "PYTHONUTF8": "1",
                                       "PATH": os.environ.get("PATH", "")})
    return r.stdout.strip() or r.stderr.strip()[-500:]


def s3_say():
    c = sqlite3.connect(str(H / "app" / "data" / "bist_haber.db"))
    n = sum(1 for (s,) in c.execute("SELECT sonuc_json FROM trade_journal") if s and '"kural": "s3"' in s)
    c.close()
    return n


rapor = {"senaryo": SENARYO}
if H.parent.exists():
    shutil.rmtree(H.parent)
H.parent.mkdir(parents=True)
subprocess.run([str(ESKI), "/sessiz", f"/hedef={H}", "/kisayolsuz", "/baslatma"], timeout=900, check=True)
py("import sys; sys.path.insert(0,'.'); from bist_haber import db; db.connect()")
c = sqlite3.connect(str(H / "app" / "data" / "bist_haber.db"))
for i in range(3):
    c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,durum,"
              "sonuc_json) VALUES('2026-11-10T19:00:00+03:00','2026-11-10',?,'otomatik','destek',100,95,104,110,5,"
              "'bekliyor',?)", (f"T{i}", json.dumps({"durum": "bekliyor", "kural": "s3"}) if SENARYO == "A" else None))
c.commit()
c.close()
(H / "app" / "data" / "ayarlar.json").write_text(json.dumps({"haber_butce_usd": 7.0, "deneme": SENARYO}), encoding="utf-8")
rapor["once_s3"] = s3_say()
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
print(json.dumps(g.hazirla(m, getter=lambda u: R())))
"""
rapor["hazirla"] = py(kod, str(YENI / "surum.json"), str(YENI / "Halley_Guncelleme.zip"))
if "TAM KURULUM" in rapor["hazirla"]:
    # A: uygulama içi güncelleme reddedildi → hiçbir şey değişmemeli; sonra kurulum programıyla güncelleme
    rapor["reddedildi"] = True
    rapor["hazir_json_yok"] = not (H / "guncelleme" / "hazir.json").exists()
    rapor["yeni_klasoru_yok"] = not (H / "guncelleme" / "yeni").exists()
    rapor["kurulu_surum_degismedi"] = (H / "surum.txt").read_text(encoding="utf-8").strip()
    rapor["s3_degismedi"] = s3_say()
    r = subprocess.run([str(YENI / "Halley_Kurulum.exe"), "/sessiz", f"/hedef={H}", "/kisayolsuz", "/baslatma"], timeout=900)
    rapor["kurulum_programi"] = (r.returncode, (H / "surum.txt").read_text(encoding="utf-8").strip())
    rapor["kurulum_sonrasi_s3_destekli"] = b"kural_sec" in (H / "app" / "bist_haber" / "journal.pyc").read_bytes()
    rapor["kurulum_sonrasi_s3"] = s3_say()
    rapor["kurulum_sonrasi_ayarlar"] = json.loads((H / "app" / "data" / "ayarlar.json").read_text(encoding="utf-8-sig")).get("deneme")
    rapor["kurulum_sonrasi_otomatik_donus_yolu"] = (H / "guncelleme" / "onceki").exists()
    (S / "faz6" / f"otodonus_{SENARYO}.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1))
    sys.exit(0)
# yeni sürümün PANELİNİ bilerek başlatılamaz yapan test adımı: 'python -m streamlit' çalışma klasöründeki bu dosyayı
# bulur ve hemen çıkar; okuyucu (python -m bist_haber okuyucu) streamlit'i içe aktarmadığı için etkilenmez.
(H / "guncelleme" / "yeni" / "streamlit.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
t0 = time.time()
p = subprocess.Popen([str(H / "Halley.exe"), "--yeniden-baslat", "--pencere-yok", "--port", str(PORT)], cwd=str(H),
                     env=dict(os.environ, HALLEY_OFFLINE="1"))
time.sleep(150)                                                           # başlatıcı 120 sn sağlık bekler
rapor["gecen_sn"] = round(time.time() - t0)
rapor["kurulu_surum"] = (H / "surum.txt").read_text(encoding="utf-8").strip()
rapor["app_kodu_s3_destekli"] = b"kural_sec" in (H / "app" / "bist_haber" / "journal.pyc").read_bytes()
g = H / "guncelleme"
rapor["guncelleme_klasoru"] = sorted(x.name for x in g.iterdir()) if g.exists() else None
rapor["onceki_kilit"] = json.loads((g / "onceki_kilit.json").read_text(encoding="utf-8")) if (g / "onceki_kilit.json").exists() else None
rapor["son_islem"] = json.loads((g / "son_islem.json").read_text(encoding="utf-8-sig")) if (g / "son_islem.json").exists() else None
rapor["sonra_s3"] = s3_say()
rapor["ayarlar_korundu"] = json.loads((H / "app" / "data" / "ayarlar.json").read_text(encoding="utf-8-sig")).get("deneme") == SENARYO
log = H / "app" / "data" / "gunluk" / "okuyucu.log"
rapor["okuyucu_log_son"] = log.read_text(encoding="utf-8", errors="replace")[-300:] if log.exists() else None
# başlatıcıyı ve (varsa) açık mesaj kutusunu kapat
subprocess.run(["taskkill", "/F", "/T", "/IM", "Halley.exe"], capture_output=True)
for pr in subprocess.run(["wmic", "process", "where", f"CommandLine like '%otodonus_{SENARYO}%'", "get", "ProcessId"],
                         capture_output=True, text=True).stdout.split()[1:]:
    subprocess.run(["taskkill", "/F", "/PID", pr], capture_output=True)
(S / "faz6" / f"otodonus_{SENARYO}.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rapor, ensure_ascii=False, indent=1))
