"""O4 + O5 canlı geçiş aracı (o3_gecis / o2_gecis düzeni). Kullanım:
  python o45_gecis.py durum   <hedef>
  python o45_gecis.py yedek   <hedef> <etiket>
  python o45_gecis.py uygula  <hedef> <kaynak_worktree>     -> dosyaları kopyalar + O4 göçünü (yedekli) TEK süreçte uygular
  python o45_gecis.py dogrula <hedef> <once.json>           -> eski tablolar aynı mı, yeni tablolar, NULL izler, K1 kapalı
  python o45_gecis.py geri    <hedef> <kod_yedegi>          -> yalnız kod (veri dokunulmaz); hedef kod s3'ü tanımalı
Süreçleri DURDURMAZ / BAŞLATMAZ."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import o2_gecis as o2  # noqa: E402
import o3_gecis as g  # noqa: E402

DEGISEN = [".gitignore", "app.py", "bist_haber/db.py", "bist_haber/defter.py", "bist_haber/kap_worker.py",
           "bist_haber/prices.py", "bist_haber/watchdog.py", "paket/app_baslangic.py", "tests/test_guncelleme.py"]
YENI = ["bist_haber/fiyat_izi.py", "bist_haber/guncelleme.py", "bist_haber/izleme.py", "bist_haber/izleme_ref/tp1_v1.json",
        "tests/test_faz6_izleme.py", "tests/test_fiyat_izi.py", "tests/test_o4_fiyat_izi.py", "tests/test_o5_izleme.py"]
YENI_TABLO = {"fiyat_indirme", "fiyat_eski", "veri_anlik"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).exists() else None


def ozet_haric(db):
    """Tablo özetleri; prices için yeni indirme_id sütunu hariç (eski veri aynı mı?)."""
    c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        out = {}
        for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")') if not (t == "prices" and r[1] == "indirme_id")]
            h, n = hashlib.sha256(), 0
            for r in c.execute(f'SELECT {",".join(chr(34) + x + chr(34) for x in cols)} FROM "{t}" ORDER BY rowid'):
                h.update(repr(tuple(r)).encode("utf-8"))
                n += 1
            out[t] = [n, h.hexdigest()[:16]]
        return {"tablolar": out, "integrity": c.execute("PRAGMA integrity_check").fetchone()[0],
                "tetikleyici": sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))}
    finally:
        c.close()


def durum(h):
    return {"db": ozet_haric(g.db_yolu(h)), "s3": o2.s3_kayitlari(h),
            "dosya": {f: sha(Path(h) / f) for f in DEGISEN + YENI}}


def uygula(h, kaynak):
    h, kaynak = Path(h).resolve(), Path(kaynak).resolve()
    for f in DEGISEN + YENI:
        (h / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kaynak / f, h / f)
    kod = ("import sys, json, time; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from bist_haber import db, "
           "fiyat_izi; t = time.time(); c = db.connect(Path(sys.argv[2])); print(json.dumps({'kurulu': fiyat_izi.kurulu(c), "
           "'sure_sn': round(time.time() - t, 2)})); c.close()")
    r = subprocess.run([str(g.VENV_PY), "-c", kod, str(h), str(g.db_yolu(h))], capture_output=True, text=True,
                       cwd=str(h), encoding="utf-8", errors="replace")
    esit = {f: sha(h / f) == sha(kaynak / f) for f in DEGISEN + YENI}
    return {"kopyalanan": len(DEGISEN + YENI), "kaynakla_ayni": all(esit.values()),
            "goc_cikti": (r.stdout + r.stderr).strip()[-600:], "kod": r.returncode}


def dogrula(h, once_json):
    once = json.loads(Path(once_json).read_text(encoding="utf-8"))["db"]
    sonra = ozet_haric(g.db_yolu(h))
    c = sqlite3.connect(f"file:{g.db_yolu(h).as_posix()}?mode=ro", uri=True)
    try:
        null = c.execute("SELECT COUNT(*), SUM(indirme_id IS NULL) FROM prices").fetchone()
        indirme = c.execute("SELECT COUNT(*) FROM fiyat_indirme").fetchone()[0]
    finally:
        c.close()
    yed = sorted((Path(h) / "data" / "yedek").glob("*_fiyat_izi_oncesi.db"))
    yo = ozet_haric(yed[-1]) if yed else None
    return {"integrity": sonra["integrity"],
            "degisen_eski_tablo": [t for t in once["tablolar"] if once["tablolar"][t] != sonra["tablolar"].get(t)],
            "yeni_tablo": sorted(set(sonra["tablolar"]) - set(once["tablolar"])),
            "tetikleyici": (len(once["tetikleyici"]), len(sonra["tetikleyici"])),
            "eski_tetikleyiciler_duruyor": set(once["tetikleyici"]) <= set(sonra["tetikleyici"]),
            "prices_satir_null": null, "fiyat_indirme_kaydi": indirme,
            "goc_yedegi": yed[-1].name if yed else None,
            "goc_yedegi_integrity": yo and yo["integrity"],
            "goc_yedegi_esit_once": bool(yo) and yo["tablolar"] == once["tablolar"]}


def geri(h, yedek):
    h, yedek = Path(h), Path(yedek)
    jr = (yedek / "bist_haber" / "journal.py").read_bytes()
    if b"kural_sec" not in jr:
        return {"reddedildi": True, "neden": "yedek kod s3 kayıtlarını tanımıyor; canlıda s3 kaydı var: " + json.dumps(o2.s3_kayitlari(h))}
    for f in DEGISEN:
        shutil.copy2(yedek / f, h / f)
    for f in YENI:
        if not (yedek / f).exists() and (h / f).exists():
            (h / f).unlink()
    return {"geri_alinan": DEGISEN, "silinen": [f for f in YENI if not (yedek / f).exists()],
            "not": "veritabanı DOKUNULMADI. O4 tabloları zararsız kalır; eski kodun yazdığı fiyat satırlarında iz "
                   "(indirme_id) boş olur → fiyat iz geçmişinde boşluk. O5 yerel dosyaları (data/izleme_*) kalır."}


if __name__ == "__main__":
    komut, hedef = sys.argv[1], str(Path(sys.argv[2]).resolve())
    if komut == "durum":
        print(json.dumps(durum(hedef), ensure_ascii=False, indent=1))
    elif komut == "yedek":
        print(json.dumps(g.yedek(hedef, sys.argv[3], "o45_oncesi"), ensure_ascii=False, indent=1))
    elif komut == "uygula":
        print(json.dumps(uygula(hedef, str(Path(sys.argv[3]).resolve())), ensure_ascii=False, indent=1))
    elif komut == "dogrula":
        print(json.dumps(dogrula(hedef, sys.argv[3]), ensure_ascii=False, indent=1))
    elif komut == "geri":
        print(json.dumps(geri(hedef, str(Path(sys.argv[3]).resolve())), ensure_ascii=False, indent=1))
