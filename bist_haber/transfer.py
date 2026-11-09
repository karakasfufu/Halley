"""Veri aktarma (2026-11-09 kullanıcı isteği): verileri tek dosyaya dışa aktar, başka bilgisayardaki Halley'e içe aktar.

Dışa aktarılan: ana veritabanı (haberler, analizler, fiyatlar, işlem günlüğü, bekçi kayıtları), geçmiş veri pilotu,
ayarlar, takvim, rapor arşivi. ASLA dışa aktarılmayan: API anahtarı (.env), günlükler, pencere profili, yedekler.
İçe aktarma: dosya önce denetlenir (Halley dosyası mı, her parçanın SHA-256'sı tutuyor mu, veritabanları sağlam mı);
mevcut veriler data/yedek/ altına yedeklenir; veritabanları SQLite yedekleme API'siyle yazılır (panel ve arka plan
okuyucusu açıkken de güvenli). API anahtarı her bilgisayarda ayrı girilir.
"""
import hashlib
import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Dict, Optional

from . import config, db

FORMAT = 1
MARKER = "Halley"
DB_MAIN = "bist_haber.db"
FILES = ["ayarlar.json", "aliases.csv", "universe.txt", "takvim_guncel.json", "kap_okuyucu.json", "fiyat_yok.json"]
DIRS = ["raporlar"]
ALLOWED_TOP = set(FILES) | set(DIRS) | {DB_MAIN, "backtest", "manifest.json"}
REQUIRED_TABLES = {"news", "impacts", "prices", "trade_journal"}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _db_bytes(path: Path) -> bytes:
    """Açık veritabanının tutarlı kopyası (yedekleme API'si)."""
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "k.db"
        s = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=60)
        d = sqlite3.connect(out)
        try:
            s.backup(d)
        finally:
            d.close()
            s.close()
        return out.read_bytes()


def _summary(db_file: Path) -> Dict:
    c = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    try:
        q = lambda sql: c.execute(sql).fetchone()[0]
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        out = {"haber": q("SELECT COUNT(*) FROM news") if "news" in tables else 0,
               "analiz": q("SELECT COUNT(*) FROM analyses") if "analyses" in tables else 0,
               "etki": q("SELECT COUNT(*) FROM impacts") if "impacts" in tables else 0,
               "islem_gunlugu": q("SELECT COUNT(*) FROM trade_journal") if "trade_journal" in tables else 0,
               "bekci_calismasi": q("SELECT COUNT(*) FROM watch_runs") if "watch_runs" in tables else 0,
               "son_fiyat_gunu": q("SELECT MAX(date) FROM prices") if "prices" in tables else None,
               "son_haber": q("SELECT MAX(published_at) FROM news") if "news" in tables else None}
        return out
    finally:
        c.close()


def export_bytes(data_dir: Optional[Path] = None, db_path: Optional[Path] = None) -> Dict:
    """Zip dosyasının baytları + özet. API anahtarı (.env) dosyaya girmez."""
    data_dir = Path(data_dir or config.DATA)
    db_path = Path(db_path or config.DB_PATH)
    items = {}
    if db_path.exists():
        items[DB_MAIN] = _db_bytes(db_path)
    for f in sorted((data_dir / "backtest").glob("*.db")):
        items[f"backtest/{f.name}"] = _db_bytes(f)
    for name in FILES:
        if (data_dir / name).is_file():
            items[name] = (data_dir / name).read_bytes()
    for d in DIRS:
        for f in sorted((data_dir / d).rglob("*")) if (data_dir / d).is_dir() else []:
            if f.is_file():
                items[f.relative_to(data_dir).as_posix()] = f.read_bytes()
    ozet = {}
    if DB_MAIN in items:
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "s.db").write_bytes(items[DB_MAIN])
            ozet = _summary(Path(t) / "s.db")
    ozet["rapor"] = sum(1 for k in items if k.startswith("raporlar/") and k.endswith(".md"))
    manifest = {"uygulama": MARKER, "bicim": FORMAT,
                "olusturma": datetime.now(config.TR_TZ).isoformat(timespec="seconds"),
                "ozet": ozet,
                "dosyalar": {k: {"sha256": _sha(v), "boyut": len(v)} for k, v in items.items()}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for k, v in items.items():
            z.writestr(k, v)
    return {"bytes": buf.getvalue(), "manifest": manifest}


def _safe(name: str) -> bool:
    p = PurePosixPath(name)
    return (not p.is_absolute() and ".." not in p.parts and "\\" not in name and ":" not in name
            and bool(p.parts) and p.parts[0] in ALLOWED_TOP)


def inspect(data: bytes) -> Dict:
    """İçe aktarmadan önce denetim. Sonuç: ok, hatalar, manifest, ozet."""
    errs = []
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return {"ok": False, "hatalar": ["Bu bir Halley veri dosyası değil (zip okunamadı)."]}
    with z:
        try:
            man = json.loads(z.read("manifest.json").decode("utf-8"))
        except (KeyError, ValueError):
            return {"ok": False, "hatalar": ["Bu bir Halley veri dosyası değil (içerik listesi yok)."]}
        if man.get("uygulama") != MARKER:
            return {"ok": False, "hatalar": ["Bu bir Halley veri dosyası değil."]}
        if man.get("bicim", 0) > FORMAT:
            errs.append("Dosya Halley'in daha yeni bir sürümüyle hazırlanmış; önce Halley'i güncelleyin.")
        files = man.get("dosyalar") or {}
        names = [n for n in z.namelist() if n != "manifest.json" and not n.endswith("/")]
        for n in names:
            if not _safe(n):
                errs.append(f"Güvenli olmayan dosya adı: {n}")
            elif n not in files:
                errs.append(f"Listede olmayan dosya: {n}")
        for n, meta in files.items():
            if not _safe(n):
                errs.append(f"Güvenli olmayan dosya adı: {n}")
                continue
            try:
                b = z.read(n)
            except KeyError:
                errs.append(f"Eksik dosya: {n}")
                continue
            if _sha(b) != meta.get("sha256"):
                errs.append(f"Dosya bozuk ya da değiştirilmiş: {n}")
        if DB_MAIN not in files:
            errs.append("Ana veritabanı dosyada yok.")
        if not errs:
            with tempfile.TemporaryDirectory() as t:
                for n in files:
                    if n.endswith(".db"):
                        out = Path(t) / n.replace("/", "_")
                        out.write_bytes(z.read(n))
                        try:
                            c = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
                            chk = c.execute("PRAGMA integrity_check").fetchone()[0]
                            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                            c.close()
                        except sqlite3.DatabaseError as e:
                            errs.append(f"Veritabanı okunamadı: {n} ({e})")
                            continue
                        if chk != "ok":
                            errs.append(f"Veritabanı sağlam değil: {n}")
                        if n == DB_MAIN and not REQUIRED_TABLES <= tables:
                            errs.append("Ana veritabanında beklenen tablolar yok.")
    return {"ok": not errs, "hatalar": errs, "manifest": man, "ozet": man.get("ozet", {})}


def _backup_current(data_dir: Path, db_path: Path) -> Path:
    stamp = datetime.now(config.TR_TZ).strftime("%Y-%m-%d_%H%M%S")
    dst = data_dir / "yedek" / f"ice_aktarma_oncesi_{stamp}"
    dst.mkdir(parents=True, exist_ok=False)
    if db_path.exists():
        (dst / DB_MAIN).write_bytes(_db_bytes(db_path))
    if (data_dir / "backtest").is_dir():
        for f in (data_dir / "backtest").glob("*.db"):
            (dst / "backtest").mkdir(exist_ok=True)
            (dst / "backtest" / f.name).write_bytes(_db_bytes(f))
    for name in FILES:
        if (data_dir / name).is_file():
            shutil.copy2(data_dir / name, dst / name)
    for d in DIRS:
        if (data_dir / d).is_dir():
            shutil.copytree(data_dir / d, dst / d)
    return dst


def _restore_db(src_bytes: bytes, target: Path) -> None:
    """Veritabanını yedekleme API'siyle yaz: hedef açık olsa da (panel/okuyucu) güvenli, yarım kalmaz."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        src_path = Path(t) / "src.db"
        src_path.write_bytes(src_bytes)
        s = sqlite3.connect(src_path)
        d = sqlite3.connect(target, timeout=60)
        try:
            s.backup(d)
            if d.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError(f"İçe aktarılan veritabanı doğrulanamadı: {target.name}")
        finally:
            d.close()
            s.close()


def import_bytes(data: bytes, data_dir: Optional[Path] = None, db_path: Optional[Path] = None) -> Dict:
    """Denetle → mevcut veriyi yedekle → içe aktar. .env'e (API anahtarı) dokunmaz."""
    data_dir = Path(data_dir or config.DATA)
    db_path = Path(db_path or config.DB_PATH)
    chk = inspect(data)
    if not chk["ok"]:
        raise ValueError("Veri dosyası içe aktarılamaz: " + "; ".join(chk["hatalar"]))
    backup = _backup_current(data_dir, db_path)
    files = chk["manifest"]["dosyalar"]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        _restore_db(z.read(DB_MAIN), db_path)
        db.connect(db_path).close()          # eski sürüm dosyası ise yeni sütun/tablolar eklenir
        for n in files:
            if n == DB_MAIN:
                continue
            b = z.read(n)
            out = data_dir / Path(*PurePosixPath(n).parts)
            if n.endswith(".db"):
                _restore_db(b, out)
                db.connect(out).close()
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b)
    return {"yedek": str(backup), "ozet": chk["ozet"], "dosya": len(files)}
