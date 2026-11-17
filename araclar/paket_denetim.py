"""Pilot paket içerik denetimi (salt-okur). staging/app + Halley_Guncelleme.zip.
Gizli bilgi / kişisel veri / veri dosyası / kaynak kod / yedek yok mu; O2 + O3 bileşenleri var mı; K1 (izleme) ve
yayımlanmamış özellikler (fiyat_izi, izleme) yok mu; etkin model ve seçim eşikleri canlıyla aynı mı."""
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

PILOT, W, KAYNAK = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
app = PILOT / "staging" / "app"
out = {}
dosyalar = [p for p in app.rglob("*") if p.is_file()]
rel = sorted(p.relative_to(app).as_posix() for p in dosyalar)
out["app_dosya_sayisi"] = len(rel)
out["data_icerigi"] = [r for r in rel if r.startswith("data/")]
out["yasak_dosya"] = [r for r in rel if r.endswith((".env", ".db", ".sqlite", "-wal", "-shm", ".jsonl"))
                      or "/yedek" in r or r.startswith(("data/", "arastirma/", "tests/", "raporlar/"))]
out["kaynak_py"] = [r for r in rel if r.endswith(".py") and r != "app.py"]
desen = {"openai_anahtar": rb"sk-[A-Za-z0-9_\-]{20,}", "env_satiri": rb"OPENAI_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{8,}",
         "telegram": rb"\d{8,10}:[A-Za-z0-9_\-]{30,}", "eposta": rb"[A-Za-z0-9._%+-]+@gmail\.com",
         "kullanici_yolu": rb"C:.Users."}
# Kişiye özel desenler (kullanıcı adı, e-posta) depoya YAZILMAZ: çalıştırırken HALLEY_KISISEL_DESEN ortam değişkeniyle
# verilir (| ile ayrılmış düzenli ifade).
import os as _os
if _os.environ.get("HALLEY_KISISEL_DESEN"):
    desen["kisisel"] = _os.environ["HALLEY_KISISEL_DESEN"].encode("utf-8")
bulgu = {k: [] for k in desen}
for p in dosyalar:
    b = p.read_bytes()
    for k, d in desen.items():
        if re.search(d, b, re.I):
            bulgu[k].append(p.relative_to(app).as_posix())
out["desen_bulgulari"] = {k: v for k, v in bulgu.items() if v}
z = zipfile.ZipFile(PILOT / "Halley_Guncelleme.zip")
zn = z.namelist()
out["zip_dosya"] = len(zn)
out["zip_korunan_alan"] = [n for n in zn if n.split("/")[0] in ("data", ".env")]
out["zip_kaynak_py"] = [n for n in zn if n.endswith(".py") and n != "app.py"]
out["zip_sha256"] = hashlib.sha256((PILOT / "Halley_Guncelleme.zip").read_bytes()).hexdigest()
out["kurulum_sha256"] = hashlib.sha256((PILOT / "Halley_Kurulum.exe").read_bytes()).hexdigest()
gerekli = ["bist_haber/harcama.pyc", "bist_haber/haber_kapsam.pyc", "bist_haber/journal.pyc", "bist_haber/defter.pyc",
           "bist_haber/ready.pyc", "bist_haber/modeller/tp1_v1.json"]
out["gerekli_var"] = {g: g in rel for g in gerekli}
out["yayimlanmamis_yok"] = {g: g not in rel for g in ("bist_haber/izleme.pyc", "bist_haber/fiyat_izi.pyc",
                                                      "bist_haber/izleme_ref.json")}
out["model_ayni"] = (hashlib.sha256((app / "bist_haber/modeller/tp1_v1.json").read_bytes()).hexdigest() ==
                     hashlib.sha256((W / "bist_haber/modeller/tp1_v1.json").read_bytes()).hexdigest())
out["modeller_klasoru"] = sorted(p.name for p in (app / "bist_haber/modeller").iterdir())
# derlenmiş kodu paketin KENDİ Python'uyla içe aktar: sürüm sabitleri ve eşikler
kod = r"""
import sys, json, hashlib; sys.path.insert(0, sys.argv[1])
from bist_haber import defter, journal, harcama, haber_kapsam, ready, tradeplan, ai_service, config, guncelleme
print(json.dumps({"KURAL_SURUM": defter.KURAL_SURUM, "KURAL_YENI": journal.KURAL_YENI,
  "stop_notu": "üst sınır değildir" in journal.STOP_KAYIP_NOTU, "MAX_CIKTI": harcama.MAX_CIKTI,
  "gunluk_varsayilan": haber_kapsam.GUNLUK_BUTCE_VARSAYILAN, "model": config.MODEL_ANALYSIS,
  "parametreler": defter.parametreler(), "parametre_sha": defter._sha(defter.parametreler()),
  "depo": guncelleme.DEPO, "surum_url": guncelleme.SURUM_URL}, ensure_ascii=False))
"""
r = subprocess.run([str(PILOT / "staging/python/python.exe"), "-c", kod, str(app)], capture_output=True, text=True,
                   encoding="utf-8", env={"PYTHONUTF8": "1", "HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows"})
out["paket_ici"] = json.loads(r.stdout) if r.returncode == 0 else r.stderr[-800:]
r2 = subprocess.run([str(Path.home() / ".venvs/bist-haber/Scripts/python.exe"), "-c", kod, str(W)], capture_output=True,
                    text=True, encoding="utf-8", env={"PYTHONUTF8": "1", "HALLEY_OFFLINE": "1", "SYSTEMROOT": "C:\\Windows"})
canli = json.loads(r2.stdout) if r2.returncode == 0 else {"hata": r2.stderr[-400:]}
out["canli_parametre_sha"] = canli.get("parametre_sha")
out["esikler_ayni"] = isinstance(out["paket_ici"], dict) and out["paket_ici"]["parametreler"] == canli.get("parametreler")
# paketteki derlenmiş kod = kaynak commit (her .pyc, kaynağın aynı Python ile derlenmesine eşit mi: marshal gövdesi)
import importlib.util, marshal, py_compile, tempfile  # noqa: E402
fark = []
for p in sorted((app / "bist_haber").rglob("*.pyc")):
    src = KAYNAK / p.relative_to(app).with_suffix(".py")
    if not src.exists():
        fark.append(p.relative_to(app).as_posix() + " (kaynak yok)")
        continue
    with tempfile.TemporaryDirectory() as t:
        c = Path(t) / "x.pyc"
        py_compile.compile(str(src), cfile=str(c), dfile=p.relative_to(app).as_posix(), doraise=True)
        if c.read_bytes()[16:] != p.read_bytes()[16:]:
            fark.append(p.relative_to(app).as_posix())
out["pyc_kaynakla_farkli"] = fark
print(json.dumps(out, ensure_ascii=False, indent=1))
