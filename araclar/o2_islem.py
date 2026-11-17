"""Bir kod klasörünün KENDİ koduyla, aynı klasördeki veritabanı kopyasında canlının açılışta/bekçide yaptığı
değerlendirmeleri çalıştırır (ağ yok, yapay zekâ yok): tahmin defteri sonuçlandırma, hazır fırsat değerlendirmesi,
işlem günlüğü güncellemesi. İsteğe bağlı: s3 sözleşmeli deneme tahmini ekler (geri dönüş sınırını göstermek için)."""
import json
import socket
import sys
from datetime import datetime
from pathlib import Path

H = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(H))
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(OSError("ağ engelli (prova)"))
import bist_haber  # noqa: E402
from bist_haber import config, db, defter, journal, ready  # noqa: E402

assert Path(bist_haber.__file__).resolve().parent == H / "bist_haber"
conn = db.connect(H / "data" / "bist_haber.db")
now = datetime(2026, 11, 16, 22, 0, tzinfo=config.TR_TZ)
out = {"kod_kural": getattr(defter, "KURAL_SURUM", None)}
if len(sys.argv) > 2 and sys.argv[2] == "s3_tahmin_ekle":
    conn.execute("INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
                 "parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,komisyon_pct,"
                 "kayma_pct,maliyet_protokol) SELECT 'prova_s3', ticker, signal_day, giris_gunu, tahmin_zamani, model_surum,"
                 " ozellik_surum, parametre_surum, olasilik, bant, tur, giris, acilis, acilis + 0.01, tp1, tp2, gecerlilik_gun,"
                 " 's3', komisyon_pct, kayma_pct, maliyet_protokol FROM tahmin t JOIN (SELECT 163.5 AS acilis) WHERE t.id=1")
    conn.commit()
    out["eklendi"] = "prova_s3 (BAHKM 16.11; SL açılışın 0,01 üstünde → s3'te girişsiz olmalı)"
out["sonuclandir"] = defter.sonuclandir(conn, now)
out["hazir"] = ready.evaluate_all(conn)
out["gunluk"] = {k: v for k, v in journal.update_all(conn, 0.2, 0.1).items() if k != "degisenler"}
out["gruplar"] = [defter.grup_etiketi(g["grup"]) + f" ({g['n']})" for g in defter.gruplar(conn)]
conn.close()
print(json.dumps(out, ensure_ascii=False, default=str))
