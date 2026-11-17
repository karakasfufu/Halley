"""2026-11-15: uygulama içi güncelleme (bist_haber/guncelleme.py) ve paket üretiminin gizli bilgi denetimi."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, guncelleme as g

ROOT = Path(__file__).resolve().parents[1]


class FakeResp:
    def __init__(self, data=None, body=b"", status=200):
        self.data, self.body, self.status = data, body, status

    def raise_for_status(self):
        if self.status != 200:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self.data

    def iter_content(self, n):
        for i in range(0, len(self.body), n):
            yield self.body[i:i + n]


def make_zip(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


GOOD = {"app.py": "x", "bist_haber/__init__.pyc": "x", "bist_haber/guncelleme.pyc": "x", "surum.txt": "2026-11-16 (b)",
        "surum_sira.txt": "202611161200"}


class Guncelleme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        r = self.root = Path(self.tmp.name) / "Halley"
        (r / "app" / "data").mkdir(parents=True)
        (r / "python" / "Lib" / "site-packages" / "pandas-2.1.dist-info").mkdir(parents=True)
        (r / "python" / "Lib" / "site-packages" / "pip-23.dist-info").mkdir()
        for f in ("Halley.exe", "python/python.exe", "python/python39.dll", "python/python3.dll"):
            (r / f).write_text("x")
        (r / "surum.txt").write_text("2026-11-15 (a)", encoding="utf-8")
        (r / "surum_sira.txt").write_text("202611151200", encoding="utf-8")
        (r / "baslatici.txt").write_text("B1", encoding="utf-8")
        for p in (patch.object(config, "ROOT", r / "app"), patch.object(config, "DATA", r / "app" / "data"),
                  patch.dict(os.environ, {"HALLEY_OFFLINE": ""})):
            p.start()
            self.addCleanup(p.stop)
        self.ortam = g.ortam_imzasi(r / "python" / "Lib" / "site-packages", "3.9")

    def manifest(self, **k):
        body = make_zip(k.pop("files", GOOD))
        m = {"surum": "2026-11-16 (b)", "sira": 202611161200, "paket_url": "u", "sha256": hashlib.sha256(body).hexdigest(),
             "boyut": len(body), "ortam": self.ortam, "baslatici": "B1", "notlar": "yeni"}
        m.update(k)
        return m, body

    def test_dev_folder_is_off(self):
        with patch.object(config, "ROOT", ROOT):
            self.assertIsNone(g.kok())
            self.assertEqual(g.kontrol()["durum"], "kapali")

    def test_check_states_and_daily_cache(self):
        self.assertEqual(g.kok(), self.root)
        self.assertEqual(g.yerel_ortam(self.root), self.ortam)        # pip sayılmaz, sürüm python39.dll'den
        m, _ = self.manifest()
        calls = []
        get = lambda u: calls.append(u) or FakeResp(m)
        now = datetime(2026, 11, 16, 9)
        u = g.kontrol(now=now, getter=get)
        self.assertEqual((u["durum"], u["yeni"], u["kurulu"]), ("yeni", "2026-11-16 (b)", "2026-11-15 (a)"))
        self.assertEqual(g.kontrol(now=now + timedelta(hours=2), getter=get)["durum"], "yeni")
        self.assertEqual(len(calls), 1)                                 # günde bir kez ağa çıkar
        g.kontrol(now=now + timedelta(hours=2), getter=get, zorla=True)
        self.assertEqual(len(calls), 2)
        self.assertEqual(g.degerlendir(dict(m, sira=202611151200), self.root)["durum"], "guncel")
        self.assertEqual(g.degerlendir(dict(m, ortam="farkli"), self.root)["durum"], "tam_kurulum")
        self.assertIn("Halley.exe", g.degerlendir(dict(m, baslatici="B2"), self.root)["neden"])

    def test_network_error_never_raises(self):
        def boom(u):
            raise OSError("ağ yok")
        u = g.kontrol(getter=boom)
        self.assertEqual(u["durum"], "hata")
        with patch.dict(os.environ, {"HALLEY_OFFLINE": "1"}):
            self.assertEqual(g.kontrol(zorla=True, getter=boom)["durum"], "kapali")

    def test_prepare_verifies_and_cleans_up(self):
        m, body = self.manifest()
        with patch.object(g, "_ice_aktarma_denemesi") as smoke:
            g.hazirla(m, getter=lambda u: FakeResp(body=body))
        smoke.assert_called_once()
        gd = self.root / "guncelleme"
        self.assertTrue((gd / "yeni" / "app.py").exists())
        self.assertEqual(json.loads((gd / "hazir.json").read_text(encoding="utf-8"))["sira"], 202611161200)
        self.assertFalse((gd / "indirilen.zip").exists())
        self.assertEqual(g.degerlendir(m, self.root)["durum"], "bekliyor")
        g.iptal()
        self.assertFalse((gd / "hazir.json").exists())
        # bozuk indirme: parmak izi tutmuyor → kurulmaz, yarım iş kalmaz
        with self.assertRaises(ValueError):
            g.hazirla(dict(m, sha256="0" * 64), getter=lambda u: FakeResp(body=body))
        self.assertFalse((gd / "yeni").exists())
        self.assertFalse((gd / "hazir.json").exists())

    def test_prepare_rejects_bad_packages(self):
        for files, word in (({**GOOD, "../disari.txt": "x"}, "geçersiz yol"), ({**GOOD, "data/bist_haber.db": "x"}, "korunan"),
                            ({**GOOD, ".env": "x"}, "korunan"), ({"app.py": "x"}, "eksik")):
            m, body = self.manifest(files=files)
            with patch.object(g, "_ice_aktarma_denemesi"):
                with self.assertRaises(ValueError) as e:
                    g.hazirla(m, getter=lambda u: FakeResp(body=body))
            self.assertIn(word, str(e.exception))
            self.assertFalse((self.root / "guncelleme" / "yeni").exists())
        m, body = self.manifest(ortam="farkli")
        with self.assertRaises(RuntimeError):
            g.hazirla(m, getter=lambda u: FakeResp(body=body))

    def test_rollback_request_and_restart_command(self):
        self.assertIsNone(g.onceki())
        with self.assertRaises(RuntimeError):
            g.geri_don_iste()
        o = self.root / "guncelleme" / "onceki"
        o.mkdir(parents=True)
        (o / "app.py").write_text("x")
        (o / "surum.txt").write_text("2026-11-14 (z)", encoding="utf-8")
        self.assertEqual(g.onceki(), "2026-11-14 (z)")
        g.geri_don_iste()
        self.assertTrue((self.root / "guncelleme" / "geri_don.txt").exists())
        with patch.object(g.subprocess, "Popen") as po, patch.dict(os.environ, {"HALLEY_BASLATICI_ARGS": ""}):
            g.yeniden_baslat()
        args = po.call_args[0][0]
        self.assertEqual(args[:3], ["cmd", "/c", "start"])
        self.assertEqual(args[-2:], [str(self.root / "Halley.exe"), "--yeniden-baslat"])
        with patch.object(g.subprocess, "Popen") as po,                 patch.dict(os.environ, {"HALLEY_BASLATICI_ARGS": "--port 8507 --pencere-yok"}):
            g.yeniden_baslat()
        self.assertEqual(po.call_args[0][0][-4:], ["--yeniden-baslat", "--port", "8507", "--pencere-yok"])
        (self.root / "guncelleme" / "son_islem.json").write_text('{"islem": "guncellendi", "surum": "x"}', encoding="utf-8-sig")
        self.assertEqual(g.son_islem()["islem"], "guncellendi")


class PaketDenetimi(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "paket"))
        self.addCleanup(sys.path.remove, str(ROOT / "paket"))
        import build_package
        self.bp = build_package

    def test_compile_strips_sources_and_secret_check(self):
        with tempfile.TemporaryDirectory() as t:
            app = Path(t) / "app"
            (app / "bist_haber").mkdir(parents=True)
            (app / "bist_haber" / "__init__.py").write_text("X = 1\n")
            (app / "bist_haber" / "veri.json").write_text("{}")
            (app / "app.py").write_text("import bist_haber\nY = bist_haber.X + 1\n")
            self.bp.derle(app)
            self.assertFalse((app / "bist_haber" / "__init__.py").exists())
            self.assertTrue((app / "bist_haber" / "__init__.pyc").exists())
            self.assertTrue((app / "bist_haber" / "veri.json").exists())
            self.assertIn("app_kod.pyc", (app / "app.py").read_text(encoding="utf-8"))
            self.assertIn("Önceki sürüme dön", (app / "app.py").read_text(encoding="utf-8"))
            ns = {"__file__": str(app / "app.py")}
            sys.path.insert(0, str(app))
            try:
                code = compile((app / "app.py").read_text(encoding="utf-8"), str(app / "app.py"), "exec")
                saved = sys.modules.pop("bist_haber")
                try:
                    exec(code, ns)                                   # başlangıç dosyası derlenmiş paneli çalıştırır
                finally:
                    sys.modules.pop("bist_haber", None)
                    sys.modules["bist_haber"] = saved
            finally:
                sys.path.remove(str(app))
            self.assertEqual(ns["Y"], 2)
            self.bp.gizli_denetim(app)                               # temiz
            for name, body in ((".env", "OPENAI_API_KEY=abc"), ("bist_haber/k.txt", "anahtar sk-" + "a" * 30),
                               ("bist_haber/x.py", "print(1)"), ("data/bist_haber.db", "x")):
                f = app / name
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(body)
                with self.assertRaises(RuntimeError):
                    self.bp.gizli_denetim(app)
                f.unlink()

    def test_launcher_signature_is_stable(self):
        self.assertEqual(len(self.bp.baslatici_imzasi()), 16)
        self.assertEqual(self.bp.baslatici_imzasi(), self.bp.baslatici_imzasi())


if __name__ == "__main__":
    unittest.main()


class GuvenliGeriDonus(Guncelleme):
    """O2 (17.11.2026): s3 kayıtları varken s3'ü tanımayan önceki sürüme uygulama içinden dönülmez."""

    def onceki_kur(self, s3_destekli):
        o = self.root / "guncelleme" / "onceki"
        (o / "bist_haber").mkdir(parents=True)
        (o / "app.py").write_text("x")
        (o / "surum.txt").write_text("2026-11-15 (eski)", encoding="utf-8")
        (o / "bist_haber" / "journal.pyc").write_bytes(b"..kural_sec.." if s3_destekli else b"..evaluate..")

    def db_kur(self, s3=0, tahmin_s3=0):
        import sqlite3
        c = sqlite3.connect(str(self.root / "app" / "data" / "bist_haber.db"))
        c.execute("CREATE TABLE trade_journal(id INTEGER PRIMARY KEY, sonuc_json TEXT)")
        c.execute("CREATE TABLE tahmin(id INTEGER PRIMARY KEY, kural_surum TEXT)")
        for _ in range(s3):
            c.execute("INSERT INTO trade_journal(sonuc_json) VALUES(?)", (json.dumps({"durum": "bekliyor", "kural": "s3"}),))
        c.execute("INSERT INTO trade_journal(sonuc_json) VALUES(?)", (json.dumps({"durum": "kapandı"}),))
        for _ in range(tahmin_s3):
            c.execute("INSERT INTO tahmin(kural_surum) VALUES('s3')")
        c.commit()
        c.close()

    def test_blocked_when_s3_records_and_old_code_unaware(self):
        self.onceki_kur(False)
        self.db_kur(s3=19, tahmin_s3=1)
        self.assertEqual(g.s3_kayit_sayisi(self.root / "app" / "data" / "bist_haber.db"), 20)
        e = g.geri_donus_engeli(self.root)
        self.assertIn("dönülemez", e)
        with self.assertRaises(RuntimeError):
            g.geri_don_iste()
        self.assertFalse((self.root / "guncelleme" / "geri_don.txt").exists())

    def test_allowed_without_s3_or_with_s3_aware_old_code(self):
        self.onceki_kur(False)
        self.db_kur(s3=0)
        self.assertIsNone(g.geri_donus_engeli(self.root))       # s3 kaydı yok → eski koda dönmek güvenli
        g.geri_don_iste()
        self.assertTrue((self.root / "guncelleme" / "geri_don.txt").exists())

    def test_allowed_when_previous_version_knows_s3(self):
        self.onceki_kur(True)
        self.db_kur(s3=5)
        self.assertIsNone(g.geri_donus_engeli(self.root))       # önceki sürüm de O2: s3 kayıtlarını doğru işler

    def test_unreadable_db_blocks(self):
        self.onceki_kur(False)
        (self.root / "app" / "data" / "bist_haber.db").write_bytes(b"bozuk degil sqlite")
        self.assertIn("doğrulanamadı", g.geri_donus_engeli(self.root))

    def test_starter_fallback_checks_s3(self):
        src = (ROOT / "paket" / "app_baslangic.py").read_text(encoding="utf-8")
        self.assertIn("_geri_donus_guvenli", src)
        self.assertIn("kural_sec", src)
        self.assertIn('\\"kural\\": \\"s3\\"', src)
