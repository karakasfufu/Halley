"""O2 canlı geçiş aracı (o3_gecis.py ile aynı düzen; göç YOK — şema değişmez). Kullanım:
  python o2_gecis.py durum  <hedef>
  python o2_gecis.py yedek  <hedef> <etiket>
  python o2_gecis.py uygula <hedef> <kaynak_worktree>
  python o2_gecis.py davranis_geri <hedef>           -> ayar gerceklesme_kurali = "s2" (YALNIZ davranış geri dönüşü)
  python o2_gecis.py kod_geri <hedef> <kod_yedegi>   -> yalnız s3 kaydı YOKSA eski kod (varsa reddeder)
Süreçleri durdurmaz/başlatmaz."""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import o3_gecis as g  # noqa: E402

DEGISEN = ["app.py", "bist_haber/defter.py", "bist_haber/journal.py", "bist_haber/ready.py", "bist_haber/tracker.py",
           "tests/test_defter.py", "tests/test_faz1_dogrulama.py"]
YENI = ["arastirma/asama6/portfoy.py", "tests/test_kural_s3.py", "tests/test_o2_s3.py"]


def s3_kayitlari(h):
    c = sqlite3.connect(f"file:{g.db_yolu(h).as_posix()}?mode=ro", uri=True)
    try:
        out = {"tahmin_s3": c.execute("SELECT COUNT(*) FROM tahmin WHERE kural_surum='s3'").fetchone()[0],
               "degerlendirme_s3": c.execute("SELECT COUNT(*) FROM tahmin_degerlendirme WHERE kural_surum='s3'").fetchone()[0]}
        n = 0
        for t in ("trade_journal", "hazir_firsat", "takip_senaryo"):
            try:
                n += sum(1 for (s,) in c.execute(f"SELECT sonuc_json FROM {t}") if s and '"kural": "s3"' in s)
            except sqlite3.OperationalError:
                pass
        out["sonuc_json_s3"] = n
        return out
    finally:
        c.close()


def uygula(h, kaynak):
    h, kaynak = Path(h).resolve(), Path(kaynak).resolve()
    for f in DEGISEN + YENI:
        (h / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kaynak / f, h / f)
    return {"kopyalanan": DEGISEN + YENI, "goc": "yok (şema değişmez)"}


def davranis_geri(h):
    p = Path(h) / "data" / "ayarlar.json"
    d = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    d["gerceklesme_kurali"] = "s2"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ayar": "gerceklesme_kurali = s2", "not": "YALNIZ davranış geri dönüşü: kod O2 olarak kalır; yeni kayıtlar s2 ile "
            "başlar, s3 ile başlamış kayıtlar s3 ile sonuçlanır. Eski koda tam dönüş DEĞİLDİR."}


def kod_geri(h, yedek):
    k = s3_kayitlari(h)
    if any(k.values()):
        return {"reddedildi": True, "s3": k, "neden": "s3 kayıtları var: eski kod bunları s2 ile sonuçlandırır (kalıcı hata). "
                "Yalnız davranis_geri kullanılabilir."}
    h, yedek = Path(h), Path(yedek)
    for f in DEGISEN:
        shutil.copy2(yedek / f, h / f)
    for f in YENI:
        if not (yedek / f).exists() and (h / f).exists():
            (h / f).unlink()
    return {"geri_alinan": DEGISEN, "s3": k}


if __name__ == "__main__":
    komut, hedef = sys.argv[1], str(Path(sys.argv[2]).resolve())
    if komut == "durum":
        print(json.dumps({"db": g.ozet(g.db_yolu(hedef)), "s3": s3_kayitlari(hedef),
                          "dosya": {f: (hashlib.sha256((Path(hedef) / f).read_bytes()).hexdigest()[:16]
                                        if (Path(hedef) / f).exists() else None) for f in DEGISEN + YENI}},
                         ensure_ascii=False, indent=1))
    elif komut == "yedek":
        print(json.dumps(g.yedek(hedef, sys.argv[3], "o2_oncesi"), ensure_ascii=False, indent=1))
    elif komut == "uygula":
        print(json.dumps(uygula(hedef, sys.argv[3]), ensure_ascii=False, indent=1))
    elif komut == "davranis_geri":
        print(json.dumps(davranis_geri(hedef), ensure_ascii=False, indent=1))
    elif komut == "kod_geri":
        print(json.dumps(kod_geri(hedef, str(Path(sys.argv[3]).resolve())), ensure_ascii=False, indent=1))
