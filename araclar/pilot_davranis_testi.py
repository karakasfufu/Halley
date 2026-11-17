"""KURULU pilot (kurulum_test/temiz, edcac9d) üzerinde davranış geri dönüşü — müşterinin yapacağı gibi:
ayar dosyasına Not Defteri tarzında satır eklenir (UTF-8 BOM'lu), kurulu Python + kurulu derlenmiş kodla, VARSAYILAN
yollarla (app\\data) çalıştırılır. Ayrıca bozuk JSON durumu sınanır. Ağ yok, yapay zekâ yok, canlıya dokunulmaz."""
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

S = Path(sys.argv[1])
K = S / "kurulum_test" / "temiz"
D = K / "app" / "data"
shutil.copy2(S / "faz6" / "prova_o2" / "B" / "data" / "bist_haber.db", D / "bist_haber.db")   # canlı kopyası: 19 s3 damgalı
c = sqlite3.connect(str(D / "bist_haber.db"))
c.execute("INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,parametre_surum,"
          "olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,komisyon_pct,kayma_pct,maliyet_protokol) "
          "SELECT 'pilot_s3',ticker,signal_day,'2026-11-16','2026-11-15T19:00:00+03:00',model_surum,ozellik_surum,parametre_surum,"
          "olasilik,bant,tur,giris,163.5,163.51,tp1,tp2,gecerlilik_gun,'s3',0.2,0.1,'ayar_tahmin_ani_v1' FROM tahmin WHERE id=1")
c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik) "
          "VALUES('2026-11-17T12:00:00+03:00','2026-11-17','YENI','otomatik','destek',10,9,12,13,5)")   # geri dönüşten sonra yeni kayıt
c.commit()
c.close()
ay = D / "ayarlar.json"
eski = json.loads(ay.read_text(encoding="utf-8-sig")) if ay.exists() else {}
eski.update(haber_butce_usd=7.0, sermaye=50000.0)        # müşterinin kendi ayarları (korunmalı)
metin = json.dumps(eski, ensure_ascii=False, indent=2)
# Not Defteri düzenlemesi: son "}" öncesine virgül + yeni satır; Not Defteri UTF-8 BOM ekleyebilir
duz = metin.rstrip()[:-1].rstrip() + ',\n  "gerceklesme_kurali": "s2"\n}'
ay.write_bytes(b"\xef\xbb\xbf" + duz.encode("utf-8"))
kod = r"""
import sys, json; sys.path.insert(0, '.')
from datetime import datetime
from bist_haber import config, pipeline, journal, ready, defter, db
c = db.connect()
print(json.dumps({"ayar_dosyasi": str(pipeline.SETTINGS_FILE.relative_to(config.ROOT)), "yeni_kural": journal.yeni_kural(),
  "butce": pipeline.load_settings().get("haber_butce_usd"), "gunluk": journal.update_all(c, 0.2, 0.1)["degerlendirilen"],
  "hazir": ready.evaluate_all(c), "defter": defter.sonuclandir(c, datetime(2026, 11, 17, 18, 30, tzinfo=config.TR_TZ))}))
"""
r = subprocess.run([str(K / "python" / "python.exe"), "-c", kod], cwd=str(K / "app"), capture_output=True, text=True,
                   env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows", "PYTHONUTF8": "1"})
out = {"kurulu_surum": (K / "surum.txt").read_text(encoding="utf-8").strip(), "cikti": r.stdout.strip() or r.stderr[-500:]}
c = sqlite3.connect(str(D / "bist_haber.db"))
k = [(json.loads(s or "{}") or {}).get("kural") for (s,) in c.execute("SELECT sonuc_json FROM trade_journal WHERE durum='bekliyor' AND ticker<>'YENI'")]
out["eski_s3_damgali_korunan"] = f"{k.count('s3')}/{len(k)}"
out["yeni_kayit_kurali"] = [(json.loads(s or "{}") or {}).get("kural") for (s,) in
                            c.execute("SELECT sonuc_json FROM trade_journal WHERE ticker='YENI'")]
out["s3_tahmin_sonucu"] = c.execute("SELECT s.kural_surum, s.sonuc_turu FROM tahmin t JOIN tahmin_sonuc s ON s.tahmin_id=t.id "
                                    "WHERE t.plan_imzasi='pilot_s3'").fetchall()
c.close()
out["ayarlar_korundu"] = json.loads(ay.read_text(encoding="utf-8-sig")).get("haber_butce_usd") == 7.0
# bozuk JSON: virgül unutulursa
ay.write_bytes(metin.rstrip()[:-1].rstrip().encode("utf-8") + b'\n  "gerceklesme_kurali": "s2"\n}')
r2 = subprocess.run([str(K / "python" / "python.exe"), "-c", "import sys; sys.path.insert(0,'.'); from bist_haber import journal, pipeline;"
                     "print(journal.yeni_kural(), pipeline.load_settings())"], cwd=str(K / "app"), capture_output=True,
                    text=True, env={"HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows", "PYTHONUTF8": "1"})
out["bozuk_json"] = r2.stdout.strip() or r2.stderr[-300:]
ay.write_bytes(b"\xef\xbb\xbf" + duz.encode("utf-8"))          # panel denemesi için düzgün hâle getir
print(json.dumps(out, ensure_ascii=False, indent=1))
