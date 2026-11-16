"""O3 canlı geçiş aracı. Kullanım:
  python o3_gecis.py durum   <hedef>                         -> tablo sayıları + özetler (salt-okur)
  python o3_gecis.py yedek   <hedef> <etiket>                -> kod + veritabanı yedeği, bütünlük, yedek = canlı
  python o3_gecis.py uygula  <hedef> <kaynak_worktree>       -> yalnız O3 dosyalarını kopyalar + yeni tabloyu ekler
  python o3_gecis.py geri    <hedef> <kod_yedegi_klasoru>    -> yalnız O3 dosyalarını eski hâline döndürür (veri DOKUNULMAZ)
Süreçleri DURDURMAZ / BAŞLATMAZ (bunu çağıran yapar). .env ve data/ dışındaki kod dosyalarına dokunur."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEGISEN = ["app.py", "bist_haber/__main__.py", "bist_haber/ai_comment.py", "bist_haber/ai_service.py",
           "bist_haber/analyzer.py", "bist_haber/pipeline.py", ".gitignore"]
YENI = ["bist_haber/haber_kapsam.py", "bist_haber/harcama.py", "tests/test_o3_haber.py"]
KOD_KOK = ["app.py", "baslat.bat", "requirements.txt", ".gitignore", ".env.example", ".streamlit", "bist_haber", "tests",
           "arastirma", "paket", "dagitim"]
VENV_PY = Path.home() / ".venvs" / "bist-haber" / "Scripts" / "python.exe"


def db_yolu(h):
    return Path(h) / "data" / "bist_haber.db"


def ozet(db):
    c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        out = {}
        for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            h = hashlib.sha256()
            n = 0
            for r in c.execute(f'SELECT * FROM "{t}" ORDER BY rowid'):
                h.update(repr(r).encode("utf-8"))
                n += 1
            out[t] = (n, h.hexdigest()[:16])
        trig = sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))
        return {"tablolar": out, "tetikleyiciler": trig,
                "integrity": c.execute("PRAGMA integrity_check").fetchone()[0]}
    finally:
        c.close()


def dosya_ozeti(h):
    h = Path(h)
    out = {}
    for f in DEGISEN + YENI + ["bist_haber/watchdog.py", "bist_haber/ready.py", "bist_haber/modeller/tp1_v1.json",
                              "bist_haber/db.py", "bist_haber/defter.py", "data/ayarlar.json"]:
        p = h / f
        out[f] = hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None
    return out


def yedek(h, etiket, db_ek="o3_oncesi"):
    h = Path(h)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    kod = h / "data" / "yedek" / f"kod_{etiket}_{ts}"
    for k in KOD_KOK:
        s = h / k
        if s.is_dir():
            shutil.copytree(s, kod / k, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif s.exists():
            kod.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, kod / k)
    hedef_db = h / "data" / "yedek" / f"bist_haber_{ts}_{db_ek}.db"
    src = sqlite3.connect(f"file:{db_yolu(h).as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(hedef_db))
    src.backup(dst)
    dst.close()
    src.close()
    a, b = ozet(db_yolu(h)), ozet(hedef_db)
    sonuc = {"kod_yedegi": str(kod), "kod_dosya_sayisi": sum(1 for p in kod.rglob("*") if p.is_file()),
             "db_yedegi": str(hedef_db), "db_yedegi_bayt": hedef_db.stat().st_size,
             "yedek_integrity": b["integrity"], "canli_integrity": a["integrity"],
             "yedek_esit_canli": a["tablolar"] == b["tablolar"] and a["tetikleyiciler"] == b["tetikleyiciler"],
             "env_yedekte_mi": (kod / ".env").exists()}
    return sonuc


def uygula(h, kaynak):
    h, kaynak = Path(h).resolve(), Path(kaynak).resolve()
    for f in DEGISEN + YENI:
        (h / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kaynak / f, h / f)
    # Kopyada sınanan migrasyon: yalnız yeni tablo (CREATE TABLE IF NOT EXISTS). Yeni kodla, tek süreç.
    kod = ("import sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from bist_haber import db, ai_service;"
           "c = db.connect(Path(sys.argv[2])); ai_service._ensure(c); c.close(); print('tablo ok')")
    r = subprocess.run([str(VENV_PY), "-c", kod, str(h), str(db_yolu(h))], capture_output=True, text=True,
                       cwd=str(h), encoding="utf-8", errors="replace")
    return {"kopyalanan": DEGISEN + YENI, "migrasyon_cikti": (r.stdout + r.stderr).strip()[-400:], "kod": r.returncode}


def geri(h, kod_yedegi):
    h, kod_yedegi = Path(h), Path(kod_yedegi)
    for f in DEGISEN:
        shutil.copy2(kod_yedegi / f, h / f)
    for f in YENI:
        if not (kod_yedegi / f).exists() and (h / f).exists():
            (h / f).unlink()
    return {"geri_alinan": DEGISEN, "silinen_yeni": [f for f in YENI if not (kod_yedegi / f).exists()],
            "not": "veritabanı DOKUNULMADI (harcama_rezervasyon tablosu zararsız kalır; yeni veri korunur)"}


if __name__ == "__main__":
    komut, hedef = sys.argv[1], str(Path(sys.argv[2]).resolve())
    sys.argv[3:] = [str(Path(a).resolve()) if komut in ("uygula", "geri") else a for a in sys.argv[3:]]
    if komut == "durum":
        print(json.dumps({"db": ozet(db_yolu(hedef)), "dosya": dosya_ozeti(hedef)}, ensure_ascii=False, indent=1))
    elif komut == "yedek":
        print(json.dumps(yedek(hedef, sys.argv[3]), ensure_ascii=False, indent=1))
    elif komut == "uygula":
        print(json.dumps(uygula(hedef, sys.argv[3]), ensure_ascii=False, indent=1))
    elif komut == "geri":
        print(json.dumps(geri(hedef, sys.argv[3]), ensure_ascii=False, indent=1))
