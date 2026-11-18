"""O5 kontrolü (hedef klasörde, yeni kodla): sürüm grupları, yetersiz veri, iki kez çalıştırmada mükerrer olay yok, K1 kapalı.
Kullanım: python o5_canli_kontrol.py <hedef> [--yaz]  (--yaz yoksa izleme dosyaları geçici klasöre yazılır)"""
import json, sys, tempfile
from datetime import datetime
from pathlib import Path
h = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(h))
from bist_haber import config, db, izleme, defter, harcama
conn = db.connect(h / "data" / "bist_haber.db")
hedef = h / "data" if "--yaz" in sys.argv else Path(tempfile.mkdtemp())
out = {"izleme_dosya_yeri": "canlı data" if "--yaz" in sys.argv else "geçici"}
e = izleme.degerlendir(conn)
out["gruplar"] = []
for x in e:
    g = x.get("grup", {})
    b = (x.get("pencereler") or {}).get("birikimli") or {}
    out["gruplar"].append({"etiket": x.get("etiket"), "kural": g.get("kural_surum"), "olcum": g.get("olcum_kurali"),
                           "durum": {k: b[k]["durum"] for k in ("P1", "P2", "K1", "R1", "G1") if k in b},
                           "n_P2": (b.get("P2", {}).get("orneklem") or {}).get("n"), "neden": x.get("neden")})
now = datetime.now(config.TR_TZ).replace(tzinfo=None)
r1 = izleme.kontrol_et(conn, hedef, now)
r2 = izleme.kontrol_et(conn, hedef, now)
out["kontrol1"] = {k: v for k, v in r1.items() if k != "olaylar"}
out["kontrol2"] = {k: v for k, v in r2.items() if k != "olaylar"}
kay = hedef / "izleme_kayit.jsonl"
satir = [json.loads(s) for s in kay.read_text(encoding="utf-8").splitlines()] if kay.exists() else []
out["kayit_satiri"] = len(satir)
out["K1_olay"] = sum(1 for s in satir if s.get("olcut") == "K1")
d = json.loads((hedef / "izleme_durumu.json").read_text(encoding="utf-8")) if (hedef / "izleme_durumu.json").exists() else {}
out["durum_anahtar_K1"] = [k for k in d if "|K1" in k]
out["UYARI_OLCUTLERI"] = izleme.UYARI_OLCUTLERI
out["harcama_ay"] = round(harcama.harcanan(conn, "haber")["ay"]["toplam"], 6)
out["varsayilan_kural"] = __import__("bist_haber.journal", fromlist=["x"]).kural_sec({}) if hasattr(__import__("bist_haber.journal", fromlist=["x"]), "kural_sec") else None
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
