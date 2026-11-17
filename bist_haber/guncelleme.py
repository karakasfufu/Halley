"""Uygulama içinden güncelleme (2026-11-15, kullanıcı: "uygulamanın güncel sürümünü takip edecek bir versiyon").

Akış (yalnız kurulum dosyasıyla kurulmuş Halley'de; geliştirme klasöründe kapalı):
  1. kontrol(): herkese açık güncelleme deposundaki surum.json okunur (panel her açıldığında; kullanıcı isteği 15.11).
     İnternet yoksa son okunan bilgiyle devam edilir; panel açılışı en fazla ~4 sn bekler.
  2. hazirla(): güncelleme paketi (yalnız uygulama kodu, derlenmiş) indirilir, SHA-256 doğrulanır, <kök>\\guncelleme\\yeni
     klasörüne açılır, gömülü Python ile içe aktarma denemesi yapılır; <kök>\\guncelleme\\hazir.json yazılır.
  3. yeniden_baslat(): Halley.exe --yeniden-baslat. Dosya değişimini Halley.exe yapar (hiçbir şey çalışmazken): eski kod
     <kök>\\guncelleme\\onceki'ye taşınır, yenisi app\\'e. Yeni sürüm 2 dakikada açılmazsa Halley.exe önceki sürüme
     kendiliğinden döner. Veriler (app\\data) ve API anahtarı (app\\.env) hiç taşınmaz.
  Paket uyumsuzsa (gömülü Python/kütüphaneler ya da Halley.exe değişmişse) güncelleme yapılmaz; tam kurulum istenir.
Yapay zekâ yok; ağ: yalnız güncelleme deposu (GitHub).
"""
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, Optional

from . import config

DEPO = "karakasfufu/Halley-guncelleme"
SURUM_URL = f"https://github.com/{DEPO}/releases/latest/download/surum.json"
SAYFA_URL = f"https://github.com/{DEPO}/releases/latest"
KONTROL_ARALIK = timedelta(hours=20)
KORUNAN = {"data", ".env"}                      # app\ içinde güncellemenin asla dokunmadığı yerler
_ZORUNLU = ("app.py", "bist_haber/__init__.pyc", "bist_haber/guncelleme.pyc")


def kok() -> Optional[Path]:
    """Kurulum klasörü (Halley.exe + python\\ + app\\). Geliştirme klasöründe None → özellik kapalı."""
    r = config.ROOT.parent
    if (r / "Halley.exe").exists() and (r / "python" / "python.exe").exists() and config.ROOT.name == "app":
        return r
    return None


def _oku(p: Path, varsayilan: str = "") -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return varsayilan


def kurulu(root: Optional[Path] = None) -> Dict:
    root = root or kok()
    if not root:
        return {"surum": "", "sira": 0}
    s = _oku(root / "surum_sira.txt", "0")
    return {"surum": _oku(root / "surum.txt", "bilinmiyor"), "sira": int(s) if s.isdigit() else 0}


def ortam_imzasi(site_packages: Path, py_surum: str) -> str:
    """Gömülü Python sürümü + kurulu kütüphaneler (dist-info adları). Paket kurulumla aynı ortamda üretilmiş mi?"""
    names = sorted(p.name.lower() for p in site_packages.glob("*.dist-info") if not p.name.lower().startswith("pip-"))
    return hashlib.sha256((py_surum + "|" + "|".join(names)).encode()).hexdigest()[:16]


def _py_surum(root: Path) -> str:
    for f in (root / "python").glob("python3*.dll"):
        if f.name != "python3.dll":
            n = f.stem[len("python"):]
            return f"{n[0]}.{n[1:]}"
    return "?"


def yerel_ortam(root: Path) -> str:
    return ortam_imzasi(root / "python" / "Lib" / "site-packages", _py_surum(root))


def uyum(m: Dict, root: Path) -> Optional[str]:
    """Uygulama içinden güncellenebilir mi? Değilse nedeni (tam kurulum gerekir)."""
    if m.get("ortam") != yerel_ortam(root):
        return "bu sürüm yeni bir Python kütüphanesi içeriyor"
    if m.get("baslatici") != _oku(root / "baslatici.txt"):
        return "bu sürümde Halley.exe de değişti"
    return None


def _durum_yolu() -> Path:
    return config.DATA / "guncelleme_durum.json"


def _durum() -> Dict:
    try:
        return json.loads(_durum_yolu().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _durum_yaz(d: Dict) -> None:
    try:
        _durum_yolu().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def manifest() -> Dict:
    """Son kontrolde okunan sürüm bilgisi (yoksa boş)."""
    return _durum().get("manifest") or {}


def kontrol(zorla: bool = False, now: Optional[datetime] = None, getter: Callable = None) -> Dict:
    """{"durum": "kapali"|"guncel"|"yeni"|"tam_kurulum"|"hata"|"bekliyor", ...}. Günde en fazla bir kez ağa çıkar
    (zorla=True hariç); ağ hatası paneli asla engellemez."""
    root = kok()
    if not root or os.environ.get("HALLEY_OFFLINE"):
        return {"durum": "kapali"}
    now = now or datetime.now()
    d = _durum()
    son = d.get("son_kontrol")
    m = d.get("manifest")
    if zorla or not son or now - datetime.fromisoformat(son) > KONTROL_ARALIK or not m:
        try:
            if getter is None:
                import requests
                getter = lambda u: requests.get(u, timeout=4, headers={"User-Agent": "Halley-guncelleme"})
            r = getter(SURUM_URL)
            r.raise_for_status()
            m = r.json()
            d.update(son_kontrol=now.isoformat(timespec="seconds"), manifest=m, hata=None)
        except Exception as e:  # ağ yok / depo yok: sessizce eski bilgiyle devam
            d.update(son_kontrol=now.isoformat(timespec="seconds"), hata=str(e)[:200])
            _durum_yaz(d)
            if not m:
                return {"durum": "hata", "hata": str(e)[:200]}
        _durum_yaz(d)
    return degerlendir(m, root)


def degerlendir(m: Dict, root: Path) -> Dict:
    k = kurulu(root)
    out = {"kurulu": k["surum"], "yeni": m.get("surum"), "notlar": m.get("notlar", ""), "sayfa": SAYFA_URL,
           "boyut_mb": round((m.get("boyut") or 0) / 1e6, 1)}
    if (root / "guncelleme" / "hazir.json").exists():
        return dict(out, durum="bekliyor")
    if int(m.get("sira") or 0) <= k["sira"]:
        return dict(out, durum="guncel")
    neden = uyum(m, root)
    if neden:
        return dict(out, durum="tam_kurulum", neden=neden)
    return dict(out, durum="yeni")


def _guvenli_ac(z: zipfile.ZipFile, hedef: Path) -> None:
    h = hedef.resolve()
    for info in z.infolist():
        p = (hedef / info.filename).resolve()
        if h not in p.parents and p != h:
            raise ValueError(f"Güncelleme paketinde geçersiz yol: {info.filename}")
        top = info.filename.replace("\\", "/").split("/")[0]
        if top in KORUNAN:
            raise ValueError(f"Güncelleme paketi korunan alana yazmaya çalışıyor: {info.filename}")
    z.extractall(hedef)


def hazirla(m: Dict, ilerleme: Callable[[float, str], None] = lambda p, t: None, getter: Callable = None) -> Dict:
    """Paketi indir → doğrula → aç → içe aktarma denemesi → hazir.json. Hata olursa yarım iş silinir."""
    root = kok()
    if not root:
        raise RuntimeError("Güncelleme yalnız kurulum dosyasıyla kurulmuş Halley'de yapılabilir.")
    neden = uyum(m, root)
    if neden:
        raise RuntimeError(f"Tam kurulum gerekiyor: {neden}.")
    g = root / "guncelleme"
    g.mkdir(exist_ok=True)
    zp, yeni = g / "indirilen.zip", g / "yeni"
    try:
        ilerleme(0.05, "Güncelleme indiriliyor…")
        if getter is None:
            import requests
            getter = lambda u: requests.get(u, timeout=60, stream=True, headers={"User-Agent": "Halley-guncelleme"})
        r = getter(m["paket_url"])
        r.raise_for_status()
        h = hashlib.sha256()
        toplam, boyut = 0, int(m.get("boyut") or 0)
        with open(zp, "wb") as f:
            for parca in r.iter_content(1 << 16):
                f.write(parca)
                h.update(parca)
                toplam += len(parca)
                if boyut:
                    ilerleme(0.05 + 0.6 * min(toplam / boyut, 1), f"İndiriliyor… {toplam / 1e6:.1f} / {boyut / 1e6:.1f} MB")
        if h.hexdigest() != m["sha256"]:
            raise ValueError("İndirilen dosya doğrulanamadı (parmak izi tutmuyor); güncelleme yapılmadı.")
        ilerleme(0.7, "Dosyalar açılıyor…")
        if yeni.exists():
            shutil.rmtree(yeni)
        with zipfile.ZipFile(zp) as z:
            _guvenli_ac(z, yeni)
        eksik = [x for x in _ZORUNLU if not (yeni / x).exists()]
        if eksik:
            raise ValueError("Güncelleme paketi eksik: " + ", ".join(eksik))
        ilerleme(0.85, "Yeni sürüm deneniyor…")
        _ice_aktarma_denemesi(root, yeni)
        (g / "hazir.json").write_text(json.dumps({"surum": m.get("surum"), "sira": m.get("sira"),
                                                  "hazirlandi": datetime.now().isoformat(timespec="seconds")},
                                                 ensure_ascii=False), encoding="utf-8")
        ilerleme(1.0, "Güncelleme hazır.")
        return {"surum": m.get("surum")}
    except Exception:
        shutil.rmtree(yeni, ignore_errors=True)
        raise
    finally:
        try:
            zp.unlink()
        except OSError:
            pass


def _ice_aktarma_denemesi(root: Path, yeni: Path) -> None:
    """Yeni kodu gömülü Python'la ayrı süreçte içe aktar (panel ve okuyucu modülleri). Açılmayan paket kurulmaz."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH")}
    env.update(PYTHONNOUSERSITE="1", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", HALLEY_OFFLINE="1")
    kod = ("import sys; sys.path.insert(0, sys.argv[1]); import bist_haber.config as c; "
           "assert c.ROOT.resolve() == __import__('pathlib').Path(sys.argv[1]).resolve(), c.ROOT; "
           "import bist_haber.pipeline, bist_haber.ready, bist_haber.watchdog, bist_haber.guncelleme, "
           "bist_haber.html_export, bist_haber.tp1_model; print('ok')")
    r = subprocess.run([str(root / "python" / "python.exe"), "-c", kod, str(yeni)], cwd=str(yeni), env=env,
                       capture_output=True, text=True, timeout=180,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or "ok" not in r.stdout:
        raise RuntimeError("Yeni sürüm denemede açılmadı; güncelleme yapılmadı. " + (r.stderr or r.stdout)[-300:])


def onceki(root: Optional[Path] = None) -> Optional[str]:
    """Geri dönülebilecek önceki sürüm (varsa)."""
    root = root or kok()
    o = root / "guncelleme" / "onceki" if root else None
    if o and (o / "app.py").exists():
        return _oku(o / "surum.txt", "önceki sürüm")
    return None


def temiz_kurulum(root: Path) -> bool:
    """Veri klasöründe kullanıcı verisi hiç yok (yalnız günlük klasörü): doğrulanmış temiz kurulum."""
    d = Path(root) / "app" / "data"
    try:
        return not d.exists() or all(p.name == "gunluk" for p in d.iterdir())
    except OSError:
        return False


def uygulama_db_yolu(root: Path) -> Optional[Path]:
    """Uygulamanın GERÇEKTEN açtığı veritabanı (config.DB_PATH) kurulumun veri klasöründeyse o yol; değilse None
    (yol doğrulanamadı)."""
    try:
        p, beklenen = Path(config.DB_PATH).resolve(), (Path(root) / "app" / "data" / "bist_haber.db").resolve()
    except OSError:
        return None
    return p if p == beklenen else None


def s3_kayit_sayisi(db_path: Path, temiz: bool = False) -> int:
    """O2 (s3) kuralıyla başlamış kayıt sayısı: s3 sözleşmeli tahmin, s3 sonucu, s3 değerlendirmesi, sonucunda
    "kural": "s3" damgası olan sanal / gerçek işlem, hazır fırsat, takip senaryosu. Dosya yoksa yalnız doğrulanmış
    temiz kurulumda 0; aksi halde ve okuma hatasında -1 (uyumluluk doğrulanamadı)."""
    import sqlite3
    if not Path(db_path).exists():
        return 0 if temiz else -1
    try:
        c = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True, timeout=10)
    except Exception:
        return -1
    try:
        tablolar = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        n = 0
        if "tahmin" in tablolar:
            n += c.execute("SELECT COUNT(*) FROM tahmin WHERE kural_surum='s3'").fetchone()[0]
        for t in ("tahmin_sonuc", "tahmin_degerlendirme"):
            if t in tablolar:
                n += c.execute(f"SELECT COUNT(*) FROM {t} WHERE kural_surum='s3'").fetchone()[0]
        for t in ("trade_journal", "hazir_firsat", "takip_senaryo"):
            if t in tablolar:
                n += c.execute(f"SELECT COUNT(*) FROM {t} WHERE sonuc_json LIKE '%\"kural\": \"s3\"%'").fetchone()[0]
        return n
    except Exception:
        return -1
    finally:
        c.close()


def s3_destekli(app_dir: Path) -> bool:
    """Klasördeki uygulama kodu s3 kayıtlarını tanıyor mu (O2 ve sonrası: journal.kural_sec)?"""
    for ad in ("journal.pyc", "journal.py"):
        p = Path(app_dir) / "bist_haber" / ad
        try:
            if p.exists():
                return b"kural_sec" in p.read_bytes()
        except OSError:
            return False
    return False


def geri_donus_engeli(root: Optional[Path] = None) -> Optional[str]:
    """O2 (17.11.2026): önceki sürüm s3 kayıtlarını tanımıyorsa ve veritabanında s3 kaydı varsa (ya da bu
    doğrulanamıyorsa) geri dönüş güvenli DEĞİLDİR: eski kod s3 damgalarını siler, kayıtları eski kuralla yeniden
    hesaplar, s3 tahminlerini sonuçlandırmaz. Engel yoksa None."""
    root = root or kok()
    o = root / "guncelleme" / "onceki" if root else None
    if not o or not (o / "app.py").exists() or s3_destekli(o):
        return None
    yol = uygulama_db_yolu(root)
    n = s3_kayit_sayisi(yol, temiz_kurulum(root)) if yol is not None else -1
    if n == 0:
        return None
    neden = (f"bu sürümün s3 kuralıyla başlattığı {n} kayıt var" if n > 0
             else "uyumluluk doğrulanamadı (veritabanı yolu ya da okunması)")
    return (f"Önceki sürüme dönülemez: {neden} ve önceki sürüm bu kayıtları doğru işleyemez (s3 işaretlerini siler, "
            "kayıtları eski kuralla yeniden hesaplar). Güvenli yol: bu sürümde kalıp gerçekleşme kuralını \"s2 (geri "
            "dönüş)\" yapmak; yeni kayıtlar eski kuralla başlar, s3 kayıtları kendi kuralıyla sonuçlanır.")


def denetim_suruyor(root: Optional[Path] = None) -> bool:
    """Başlatıcı güncellemeden sonraki ilk açılışı denetliyor mu (guncelleme/denetim.txt; sağlık kontrolü geçince
    başlatıcı siler)? Bu sırada sağlık kontrolü başarısız olursa başlatıcı önceki sürüme KENDİLİĞİNDEN döner."""
    root = root or kok()
    return bool(root) and (root / "guncelleme" / "denetim.txt").exists()


def uyumsuz_onceki_kilitle(root: Optional[Path] = None) -> Optional[Dict]:
    """O2 (17.11.2026): başlatıcının otomatik geri dönüşü s3'ü tanımayan koda yapılmasın. Önceki sürüm s3'ü
    tanımıyorsa ve veritabanında s3 kaydı varsa ya da bu doğrulanamıyorsa, önceki sürüm klasörü SİLİNMEDEN
    'onceki_uyumsuz_<zaman>' adıyla kenara alınır (otomatik / elle geri dönüş artık o koda yapılamaz). Kayıt:
    guncelleme/onceki_kilit.json. Yapılacak bir şey yoksa None."""
    root = root or kok()
    if not root:
        return None
    o = root / "guncelleme" / "onceki"
    if not (o / "app.py").exists() or s3_destekli(o):
        return None
    yol = uygulama_db_yolu(root)
    n = s3_kayit_sayisi(yol, temiz_kurulum(root)) if yol is not None else -1
    if n == 0:
        return None
    hedef = root / "guncelleme" / f"onceki_uyumsuz_{datetime.now():%Y%m%d_%H%M%S}"
    o.rename(hedef)
    k = {"zaman": datetime.now().isoformat(timespec="seconds"), "s3_kayit": n, "kenara_alinan": hedef.name,
         "neden": "önceki sürüm s3 kayıtlarını tanımıyor" if n > 0 else "uyumluluk doğrulanamadı"}
    (root / "guncelleme" / "onceki_kilit.json").write_text(json.dumps(k, ensure_ascii=False), encoding="utf-8")
    return k


def geri_don_iste() -> None:
    root = kok()
    if not root or not onceki(root):
        raise RuntimeError("Geri dönülecek önceki sürüm yok.")
    engel = geri_donus_engeli(root)
    if engel:
        raise RuntimeError(engel)
    (root / "guncelleme" / "geri_don.txt").write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")


def iptal() -> None:
    """Hazırlanmış ama uygulanmamış güncellemeyi sil."""
    root = kok()
    if root:
        for p in ("hazir.json",):
            try:
                (root / "guncelleme" / p).unlink()
            except OSError:
                pass
        shutil.rmtree(root / "guncelleme" / "yeni", ignore_errors=True)


def yeniden_baslat() -> None:
    """Halley.exe --yeniden-baslat: açık Halley'i kapatır, (varsa) güncellemeyi/geri dönüşü uygular, yeniden açar.
    "cmd /c start" ara süreci hemen kapanır; böylece yeni Halley.exe panelin süreç ağacında değildir (kapatılırken
    birlikte öldürülmez)."""
    root = kok()
    if not root:
        raise RuntimeError("Yeniden başlatma yalnız kurulu Halley'de yapılabilir.")
    ek = os.environ.get("HALLEY_BASLATICI_ARGS", "").split()          # başlatıcının seçenekleri (ör. --port) korunur
    subprocess.Popen(["cmd", "/c", "start", "", str(root / "Halley.exe"), "--yeniden-baslat"] + ek, cwd=str(root),
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True)


def son_islem(root: Optional[Path] = None) -> Optional[Dict]:
    """Halley.exe'nin son güncelleme/geri dönüş kaydı (panelde bir kez gösterilir)."""
    root = root or kok()
    p = root / "guncelleme" / "son_islem.json" if root else None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig")) if p and p.exists() else None
    except (OSError, ValueError):
        return None


class TamKurulumGerekli(ImportError):
    pass


def guncelleme_on_kontrolu(cwd: Optional[Path] = None) -> None:
    """O2 (17.11.2026): ESKİ sürümün uygulama içi güncelleme hazırlığı yeni kodu ayrı süreçte içe aktararak dener
    (çalışma klasörü <kök>/guncelleme/yeni). Bu modül o sırada yüklenince: şu an kurulu kod s3'ü tanımıyorsa ve
    veritabanında s3 kaydı varsa (ya da bu doğrulanamıyorsa) deneme BİLEREK başarısız olur → uygulama içi güncelleme
    yapılmaz, tam kurulum istenir. Neden: başlatıcının otomatik geri dönüşü (yeni sürüm açılamazsa, saniyeler içinde
    olabilir) s3'ü tanımayan bu koda dönerdi. Kurulum programında otomatik geri dönüş yoktur. Başka her durumda
    hiçbir şey yapmaz."""
    yeni = Path(cwd or os.getcwd())
    if yeni.name != "yeni" or yeni.parent.name != "guncelleme":
        return
    root = yeni.parent.parent
    mevcut = root / "app"
    if not (root / "Halley.exe").exists() or not (mevcut / "app.py").exists() or s3_destekli(mevcut):
        return
    n = s3_kayit_sayisi(mevcut / "data" / "bist_haber.db", temiz_kurulum(root))
    if n != 0:
        raise TamKurulumGerekli(
            "TAM KURULUM GEREKİYOR: s3 kayıtları var " + (f"({n})" if n > 0 else "(doğrulanamadı)")
            + ", kurulu sürüm bunları tanımıyor. Halley_Kurulum.exe ile güncelleyin (veriler korunur).")


guncelleme_on_kontrolu()
