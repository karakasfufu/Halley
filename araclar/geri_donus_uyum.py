"""Geri dönüş uyumluluğu: s3 damgalı sanal işlemler (ve s3 sözleşmeli tahmin) varken
 (1) ESKİ KARARLI kod (v202611152318, kurulu python + derlenmiş kod) aynı veritabanı kopyasında ne yapıyor?
 (2) PİLOT / O2 kodu + gerceklesme_kurali="s2" (davranış geri dönüşü) ne yapıyor?
Kopyalar üzerinde; canlıya ve kullanıcı verisine dokunulmaz. Ağ yok, yapay zekâ yok."""
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

S = Path(sys.argv[1])
KARARLI = S / "kurulum_test" / "guncelleme"            # T3 sonrası: kararlı v202611152318 kurulu
O2 = Path(sys.argv[2])                                   # o2 kodu (edcac9d worktree)
KAYNAK_DB = S / "faz6" / "prova_o2" / "B" / "data" / "bist_haber.db"   # canlı kopyası, O2 ile bir tur çalışmış
T = S / "faz6" / "uyum"
if T.exists():
    shutil.rmtree(T)
T.mkdir()
SORGU = "SELECT id, kaynak, durum, sonuc_json FROM trade_journal WHERE durum IN ('bekliyor','açık','açık (TP1 görüldü)')"


def damgalar(db):
    c = sqlite3.connect(str(db))
    out = {}
    for i, k, d, s in c.execute(SORGU):
        out[i] = (d, (json.loads(s or "{}") or {}).get("kural"))
    c.close()
    return out


def s3_tahmin_ekle(db):
    c = sqlite3.connect(str(db))
    c.execute("INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
              "parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,komisyon_pct,"
              "kayma_pct,maliyet_protokol) SELECT 'uyum_s3',ticker,signal_day,'2026-11-16','2026-11-15T19:00:00+03:00',"
              "model_surum,ozellik_surum,parametre_surum,olasilik,bant,tur,giris,163.5,163.51,tp1,tp2,gecerlilik_gun,'s3',"
              "0.2,0.1,'ayar_tahmin_ani_v1' FROM tahmin WHERE id=1")
    c.commit()
    c.close()


rapor = {}
# (1) eski kararlı kod
d1 = T / "kararli" / "data"
d1.mkdir(parents=True)
shutil.copy2(KAYNAK_DB, d1 / "bist_haber.db")
s3_tahmin_ekle(d1 / "bist_haber.db")
once = damgalar(d1 / "bist_haber.db")
kod = ("import sys, json; sys.path.insert(0, sys.argv[1]); from pathlib import Path; import sqlite3;"
       "from bist_haber import config; config.DATA = Path(sys.argv[2]); config.DB_PATH = config.DATA / 'bist_haber.db';"
       "from bist_haber import db, journal, ready; c = db.connect(config.DB_PATH);"
       "print(json.dumps({'gunluk': journal.update_all(c, 0.2, 0.1)['degerlendirilen'], 'hazir': ready.evaluate_all(c)}));"
       "print('defter_modulu_var', __import__('importlib').util.find_spec('bist_haber.defter') is not None)")
r = subprocess.run([str(KARARLI / "python" / "python.exe"), "-c", kod, str(KARARLI / "app"), str(d1)],
                   capture_output=True, text=True, cwd=str(KARARLI / "app"), env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows",
                                                                                     "PYTHONUTF8": "1"})
rapor["kararli_cikti"] = (r.stdout.strip() or r.stderr[-400:])
sonra = damgalar(d1 / "bist_haber.db")
rapor["kararli_s3_damga_once"] = sum(1 for v in once.values() if v[1] == "s3")
rapor["kararli_s3_damga_sonra"] = sum(1 for v in sonra.values() if v[1] == "s3")
c = sqlite3.connect(str(d1 / "bist_haber.db"))
rapor["kararli_s3_tahmin_sonucu"] = c.execute("SELECT s.kural_surum, s.sonuc_turu FROM tahmin t LEFT JOIN tahmin_sonuc s "
                                              "ON s.tahmin_id=t.id WHERE t.plan_imzasi='uyum_s3'").fetchall()
c.close()
# (2) O2 kodu + davranış geri dönüşü
d2 = T / "davranis" / "data"
d2.mkdir(parents=True)
shutil.copy2(KAYNAK_DB, d2 / "bist_haber.db")
s3_tahmin_ekle(d2 / "bist_haber.db")
(d2 / "ayarlar.json").write_text(json.dumps({"gerceklesme_kurali": "s2"}), encoding="utf-8")
once2 = damgalar(d2 / "bist_haber.db")
kod2 = ("import sys, json; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from datetime import datetime;"
        "from bist_haber import config; config.DATA = Path(sys.argv[2]); config.DB_PATH = config.DATA / 'bist_haber.db';"
        "from bist_haber import pipeline; pipeline.SETTINGS_FILE = config.DATA / 'ayarlar.json';"
        "from bist_haber import db, journal, ready, defter; c = db.connect(config.DB_PATH);"
        "print(json.dumps({'yeni_kural': journal.yeni_kural(), 'gunluk': journal.update_all(c, 0.2, 0.1)['degerlendirilen'],"
        "'hazir': ready.evaluate_all(c), 'defter': defter.sonuclandir(c, datetime(2026, 11, 17, 18, 30, tzinfo=config.TR_TZ))}))")
r2 = subprocess.run([str(Path.home() / ".venvs/bist-haber/Scripts/python.exe"), "-c", kod2, str(O2), str(d2)],
                    capture_output=True, text=True, cwd=str(O2), env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows",
                                                                         "PYTHONUTF8": "1"})
rapor["davranis_cikti"] = (r2.stdout.strip() or r2.stderr[-400:])
sonra2 = damgalar(d2 / "bist_haber.db")
rapor["davranis_s3_damga_once"] = sum(1 for v in once2.values() if v[1] == "s3")
rapor["davranis_s3_damga_sonra"] = sum(1 for v in sonra2.values() if v[1] == "s3")
c = sqlite3.connect(str(d2 / "bist_haber.db"))
rapor["davranis_s3_tahmin_sonucu"] = c.execute("SELECT s.kural_surum, s.sonuc_turu, s.neden FROM tahmin t LEFT JOIN "
                                               "tahmin_sonuc s ON s.tahmin_id=t.id WHERE t.plan_imzasi='uyum_s3'").fetchall()
c.close()
print(json.dumps(rapor, ensure_ascii=False, indent=1))
