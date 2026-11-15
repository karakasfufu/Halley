"""Halley taşınabilir paketini ve tek dosyalık kurulum programını üretir (2026-11-09).

Neden PyInstaller değil: Streamlit + pandas + pyarrow PyInstaller ile paketlenince kırılgan (gizli importlar, statik
dosyalar, antivirüs yanlış alarmları). Burada bu bilgisayarda çalışan GERÇEK Python 3.9.13 ve aynı kütüphaneler olduğu
gibi kopyalanır; uygulama paket içinde de bugün nasıl çalışıyorsa öyle çalışır.

Kullanım (proje kökünden, sanal ortamın Python'u ile):
    python paket/build_package.py --cikti <klasör> [--veri <canlı data klasörü>] [--veri-yok] [--guncelleme-paketi]
Çıktı: <klasör>/Halley_Kurulum.exe  (+ <klasör>/staging/ açılmış hâli, denemeler için)
       --guncelleme-paketi ile ayrıca <klasör>/Halley_Guncelleme.zip + surum.json (uygulama içi güncelleme, aynı derleme)
API anahtarı (.env) ASLA pakete girmez; kullanıcı ilk açılışta panelden girer.
2026-11-15: uygulama kodu pakete DERLENMİŞ (.pyc) girer; kaynak .py dosyaları pakette yoktur (app.py yalnız derlenmiş
paneli çalıştıran kısa bir başlangıç dosyasıdır). Paket gizli bilgi denetiminden geçmezse üretim durur.
"""
import argparse
import hashlib
import json
import py_compile
import re
import shutil
import sqlite3
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
APP_FILES = ["app.py", "KULLANIM.md", "README.md", "requirements.txt", ".env.example", ".streamlit/config.toml"]
STDLIB_SKIP = {"site-packages", "test", "idlelib", "tkinter", "turtledemo", "ensurepip", "venv", "lib2to3"}
SITE_SKIP = {"pip"}
DLL_SKIP = {"_tkinter.pyd", "tcl86t.dll", "tk86t.dll"}
VC_RUNTIME = ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
              "concrt140.dll"]
DATA_SKIP_DIRS = {"yedek", "gunluk"}
DATA_SKIP_FILES = {"kap_okuyucu_servis.json", "analiz_durumu.json"}
GIZLI = [re.compile(rb"sk-[A-Za-z0-9_\-]{20,}"), re.compile(rb"OPENAI_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{8,}"),
         re.compile(rb"\d{8,10}:[A-Za-z0-9_\-]{30,}")]          # OpenAI anahtarı, .env satırı, Telegram bot anahtarı
GIZLI_DOSYA = (".env", ".db", ".sqlite", "-wal", "-shm")


def log(msg):
    print(msg, flush=True)


def copy_python(dst: Path) -> None:
    base = Path(sys.base_prefix)
    site = Path(sysconfig.get_paths()["purelib"])
    log(f"Python: {base}  (sürüm {sys.version.split()[0]})\nKütüphaneler: {site}")
    dst.mkdir(parents=True)
    for f in ["python.exe", "pythonw.exe", "python39.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll",
              "LICENSE.txt"]:
        shutil.copy2(base / f, dst / f)
    sys32 = Path(r"C:\Windows\System32")
    for f in VC_RUNTIME:                      # VC++ çalışma zamanı uygulama yanında (hedefte kurulu olmayabilir)
        if not (dst / f).exists() and (sys32 / f).exists():
            shutil.copy2(sys32 / f, dst / f)
    (dst / "DLLs").mkdir()
    for f in (base / "DLLs").iterdir():
        if f.is_file() and f.name not in DLL_SKIP:
            shutil.copy2(f, dst / "DLLs" / f.name)
    lib = dst / "Lib"
    lib.mkdir()
    for item in (base / "Lib").iterdir():
        if item.name in STDLIB_SKIP:
            continue
        if item.is_dir():
            shutil.copytree(item, lib / item.name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(item, lib / item.name)
    # lib2to3 bazı paketlerce içe aktarılabilir: testleri hariç kopyala
    shutil.copytree(base / "Lib" / "lib2to3", lib / "lib2to3", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    sp = lib / "site-packages"
    sp.mkdir()
    for item in site.iterdir():
        if item.name in SITE_SKIP or item.name.startswith("pip-") or item.name == "__pycache__":
            continue
        if item.is_dir():
            shutil.copytree(item, sp / item.name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(item, sp / item.name)


def copy_app(dst: Path) -> None:
    dst.mkdir(parents=True)
    for f in APP_FILES:
        (dst / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dst / f)
    shutil.copytree(ROOT / "bist_haber", dst / "bist_haber", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # panel paket içinde tarayıcıyı başlatıcı açar
    cfg = dst / ".streamlit" / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("headless = false", "headless = true"), encoding="utf-8")
    derle(dst)


def derle(app: Path) -> None:
    """Kaynak .py → derlenmiş .pyc (aynı klasörde; Python kaynaksız .pyc'yi doğrudan yükler), kaynak silinir.
    app.py → app_kod.pyc + kısa başlangıç dosyası (Streamlit .py dosyası çalıştırır)."""
    n = 0
    for f in sorted((app / "bist_haber").rglob("*.py")):
        py_compile.compile(str(f), cfile=str(f.with_suffix(".pyc")), dfile=f.relative_to(app).as_posix(), doraise=True)
        f.unlink()
        n += 1
    py_compile.compile(str(app / "app.py"), cfile=str(app / "app_kod.pyc"), dfile="app.py", doraise=True)
    shutil.copy2(ROOT / "paket" / "app_baslangic.py", app / "app.py")    # derlenmiş paneli çalıştırır; hata olursa geri dönüş
    log(f"Uygulama kodu derlendi: {n + 1} dosya (kaynak .py pakette yok)")


def gizli_denetim(app: Path, veri_dahil: bool = False) -> None:
    """Pakete gizli bilgi girmesin: .env/veritabanı dosyası ya da anahtar biçiminde metin varsa üretimi durdur."""
    bad = []
    for f in app.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(app).as_posix()
        if veri_dahil and rel.startswith("data/"):
            continue
        if f.name.endswith(GIZLI_DOSYA) or rel.startswith("data/"):
            bad.append(rel)
            continue
        if f.name.endswith(".py") and rel != "app.py":
            bad.append(rel + " (kaynak kod)")
            continue
        b = f.read_bytes()
        if any(r.search(b) for r in GIZLI):
            bad.append(rel + " (anahtar biçiminde metin)")
    if bad:
        raise RuntimeError("Gizli bilgi denetimi BAŞARISIZ, paket üretilmedi: " + ", ".join(sorted(bad)[:20]))
    log("Gizli bilgi denetimi: temiz")


def baslatici_imzasi() -> str:
    t = (ROOT / "paket" / "Halley.cs").read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def guncelleme_paketi(stage: Path, out: Path, surum: str, sira: str, rev: str) -> None:
    """Uygulama içi güncelleme paketi: app klasörü (data ve .env hariç) + sürüm dosyaları; surum.json bilgisi."""
    sys.path.insert(0, str(ROOT))
    from bist_haber import guncelleme
    app = stage / "app"
    gizli_denetim(app)
    zp = out / "Halley_Guncelleme.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(app.rglob("*")):
            rel = f.relative_to(app).as_posix()
            if f.is_file() and not rel.startswith("data/") and rel != ".env":
                z.write(f, rel)
        z.writestr("surum.txt", surum)
        z.writestr("surum_sira.txt", sira)
    h = hashlib.sha256(zp.read_bytes()).hexdigest()
    tag = f"v{sira}"
    m = {"surum": surum, "sira": int(sira), "commit": rev, "etiket": tag,
         "paket_url": f"https://github.com/{guncelleme.DEPO}/releases/download/{tag}/Halley_Guncelleme.zip",
         "sha256": h, "boyut": zp.stat().st_size,
         "ortam": guncelleme.ortam_imzasi(Path(sysconfig.get_paths()["purelib"]), "%d.%d" % sys.version_info[:2]),
         "baslatici": baslatici_imzasi(), "notlar": ""}
    (out / "surum.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Güncelleme paketi: {zp} ({zp.stat().st_size / 1e6:.1f} MB) · etiket {tag} · sha256 {h[:12]}…")


def copy_data(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if rel.parts[0] in DATA_SKIP_DIRS or item.name in DATA_SKIP_FILES or item.suffix in (".db-wal", ".db-shm") \
                or item.name.endswith(("-wal", "-shm")):
            continue
        out = dst / rel
        if item.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif item.suffix == ".db":            # açık veritabanı: tutarlı kopya (SQLite yedekleme)
            out.parent.mkdir(parents=True, exist_ok=True)
            s = sqlite3.connect(f"file:{item}?mode=ro", uri=True, timeout=60)
            d = sqlite3.connect(out)
            s.backup(d)
            d.close()
            s.close()
            chk = sqlite3.connect(out).execute("PRAGMA integrity_check").fetchone()[0]
            if chk != "ok":
                raise RuntimeError(f"Veri kopyası bozuk: {rel}: {chk}")
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, out)
    log(f"Veri kopyalandı: {sum(1 for _ in dst.rglob('*') if _.is_file())} dosya")


def make_icon(path: Path) -> None:
    from PIL import Image, ImageDraw
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, 248, 248], radius=56, fill=(30, 27, 75, 255))
    for i in range(40):                      # kuyruk
        t = i / 40
        x0, y0 = 40 + t * 120, 200 - t * 110
        r = 6 + t * 18
        d.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=(251, 191, 36, int(30 + 140 * t)))
    d.ellipse([150, 52, 214, 116], fill=(253, 230, 138, 255))
    d.ellipse([162, 64, 202, 104], fill=(255, 251, 235, 255))
    img.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def assembly_info(out: Path, title: str, desc: str, rev: str) -> Path:
    """Dosya özellikleri (Ayrıntılar sekmesi): ad, açıklama, yayıncı, sürüm. 2026-11-09: imzasız ve bilgisiz exe'ler
    virüs taramalarında daha sık yanlış alarm veriyordu (kullanıcının bilgisayarında "tehdit bulundu")."""
    from datetime import date as _d
    t = _d.today()
    ver = f"{t.year}.{t.month}.{t.day}.0"
    f = out / f"_info_{title.replace(' ', '_')}.cs"
    lines = ["using System.Reflection;",
             f'[assembly: AssemblyTitle("{title}")]',
             f'[assembly: AssemblyDescription("{desc}")]',
             '[assembly: AssemblyCompany("Halley")]',
             '[assembly: AssemblyProduct("Halley")]',
             f'[assembly: AssemblyCopyright("Copyright (c) {t.year} Halley")]',
             f'[assembly: AssemblyVersion("{ver}")]',
             f'[assembly: AssemblyFileVersion("{ver}")]',
             f'[assembly: AssemblyInformationalVersion("{t.isoformat()} ({rev})")]']
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


def csc(args) -> None:
    cmd = [str(CSC), "/nologo", "/optimize+", "/codepage:65001"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("Derleme hatası:\n" + r.stdout + r.stderr)
    if r.stdout.strip():
        log(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cikti", required=True)
    ap.add_argument("--veri", help="pakete konacak data klasörü (ör. panel klasörünün data'sı)")
    ap.add_argument("--veri-yok", action="store_true")
    ap.add_argument("--guncelleme-paketi", action="store_true",
                    help="ayrıca Halley_Guncelleme.zip + surum.json üret (uygulama içi güncelleme)")
    ap.add_argument("--hazir-klasor", action="store_true",
                    help="önceki staging'deki Python ve veriyi yeniden kullan; yalnız uygulama kodu ve exe'ler yenilenir")
    a = ap.parse_args()
    out = Path(a.cikti).resolve()
    stage = out / "staging"
    out.mkdir(parents=True, exist_ok=True)
    if a.hazir_klasor and (stage / "python" / "python.exe").exists():
        app = stage / "app"
        for item in app.iterdir():                     # veri hariç uygulama dosyalarını yenile
            if item.name != "data":
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        data_tmp = app / "data"
        tmp = stage / "_data"
        data_tmp.rename(tmp)
        shutil.rmtree(app)
        copy_app(app)
        if a.veri and not a.veri_yok:                  # veri verildiyse tazele (en güncel hâli pakete girsin)
            shutil.rmtree(tmp)
            copy_data(Path(a.veri), app / "data")
        elif a.veri_yok:                               # verisiz paket (ör. GitHub sürümü): boş veri klasörü
            shutil.rmtree(tmp)
            (app / "data").mkdir()
        else:
            tmp.rename(app / "data")
    else:
        if stage.exists():
            shutil.rmtree(stage)
        copy_python(stage / "python")
        copy_app(stage / "app")
        if a.veri and not a.veri_yok:
            copy_data(Path(a.veri), stage / "app" / "data")
        else:
            (stage / "app" / "data").mkdir(parents=True, exist_ok=True)
    log("Python dosyaları önceden derleniyor (ilk açılış hızlı olsun)…")
    subprocess.run([str(stage / "python" / "python.exe"), "-m", "compileall", "-q", "-j", "0",
                    str(stage / "python" / "Lib")], check=False, capture_output=True)
    gizli_denetim(stage / "app", veri_dahil=bool(a.veri and not a.veri_yok))
    ico = out / "halley.ico"
    make_icon(ico)
    shutil.copy2(ico, stage / "halley.ico")
    wv = ROOT / "paket" / "webview2"                 # Microsoft WebView2 (Halley penceresi); exe'nin yanında durmalı
    for f in ("Microsoft.Web.WebView2.Core.dll", "Microsoft.Web.WebView2.WinForms.dll", "WebView2Loader.dll"):
        shutil.copy2(wv / f, stage / f)
    shutil.copy2(wv / "LICENSE.txt", stage / "WebView2_LICENSE.txt")
    try:
        rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, check=True).stdout.strip()
    except Exception:
        rev = "?"
    manifest = ROOT / "paket" / "halley.manifest"
    info_app = assembly_info(out, "Halley", "Halley - BIST haber ve senaryo paneli (emir vermez)", rev)
    csc(["/target:winexe", f"/win32icon:{ico}", f"/win32manifest:{manifest}", f"/out:{stage / 'Halley.exe'}",
         "/r:System.Windows.Forms.dll",
         "/r:System.Drawing.dll", f"/r:{wv / 'Microsoft.Web.WebView2.Core.dll'}",
         f"/r:{wv / 'Microsoft.Web.WebView2.WinForms.dll'}", str(ROOT / "paket" / "Halley.cs"), str(info_app)])
    # Sürüm bilgisi (kurulum programı kurulu sürümle karşılaştırır: aynıysa yeniden kurmaz, farklıysa günceller)
    from datetime import datetime as _dt
    now = _dt.now()
    surum, sira = f"{now:%Y-%m-%d} ({rev})", f"{now:%Y%m%d%H%M}"
    (stage / "surum.txt").write_text(surum, encoding="utf-8")
    (stage / "surum_sira.txt").write_text(sira, encoding="utf-8")          # uygulama içi güncelleme karşılaştırması
    (stage / "baslatici.txt").write_text(baslatici_imzasi(), encoding="utf-8")
    log("Sürüm: " + surum + " · sıra " + sira)
    if a.guncelleme_paketi:
        guncelleme_paketi(stage, out, surum, sira, rev)
    log("Paket sıkıştırılıyor…")
    payload = out / "payload.zip"
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(stage).as_posix())
    info_setup = assembly_info(out, "Halley Kurulum", "Halley kurulum ve guncelleme programi (verileri korur)", rev)
    csc(["/target:winexe", f"/win32icon:{ico}", f"/win32manifest:{manifest}", f"/out:{out / 'Halley_Kurulum.exe'}",
         f"/resource:{payload},payload.zip", "/r:System.IO.Compression.dll", "/r:System.IO.Compression.FileSystem.dll",
         "/r:System.Windows.Forms.dll", "/r:System.Drawing.dll", str(ROOT / "paket" / "Kurulum.cs"), str(info_setup)])
    payload.unlink()
    info_app.unlink()
    info_setup.unlink()
    mb = (out / "Halley_Kurulum.exe").stat().st_size / 1e6
    log(f"HAZIR: {out / 'Halley_Kurulum.exe'} ({mb:.0f} MB)")


if __name__ == "__main__":
    main()
