"""Veri aktarma (2026-11-09): dışa aktar → başka (boş) kuruluma içe aktar; anahtar asla taşınmaz; bozuk dosya reddedilir."""
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from bist_haber import db, transfer


def make_install(root: Path, with_data=True, key="sk-gizli-anahtar"):
    data = root / "data"
    data.mkdir(parents=True)
    (root / ".env").write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
    c = db.connect(data / "bist_haber.db")
    if with_data:
        c.execute("INSERT INTO news(id,source,published_at,effective_date,title,status,fetched_at) "
                  "VALUES('kap:1','kap','2026-11-06T10:00:00+03:00','2026-11-06','Haber','analyzed','x')")
        c.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,reason,"
                  "published_at,effective_date) VALUES('kap:1','AKBNK',1,3,0.8,'orta','diger','neden',"
                  "'2026-11-06T10:00:00+03:00','2026-11-06')")
        c.execute("INSERT INTO prices(ticker,date,close,volume) VALUES('AKBNK','2026-11-06',50,1e6)")
        c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik) "
                  "VALUES('x','2026-11-05','AKBNK','gercek','destek',10,9,11,12,5)")
        c.commit()
        (data / "ayarlar.json").write_text('{"haber_butce_usd": 7.5, "karanlik_mod": true}', encoding="utf-8")
        (data / "raporlar").mkdir()
        (data / "raporlar" / "2026-11-06_aksam.md").write_text("# akşam raporu", encoding="utf-8")
        (data / "backtest").mkdir()
        b = db.connect(data / "backtest" / "pilot.db")
        b.execute("CREATE TABLE IF NOT EXISTS pilot_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        b.execute("INSERT INTO pilot_meta VALUES('not','pilot verisi')")
        b.commit()
        b.close()
        (data / "gunluk").mkdir()
        (data / "gunluk" / "panel.log").write_text("günlük", encoding="utf-8")
    c.close()
    return data


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.src = make_install(t / "eski")
        self.dst = make_install(t / "yeni", with_data=False, key="sk-yeni-bilgisayar")

    def export(self):
        return transfer.export_bytes(self.src, self.src / "bist_haber.db")

    def test_roundtrip_into_fresh_install(self):
        ex = self.export()
        names = zipfile.ZipFile(io.BytesIO(ex["bytes"])).namelist()
        self.assertIn("bist_haber.db", names)
        self.assertIn("backtest/pilot.db", names)
        self.assertIn("raporlar/2026-11-06_aksam.md", names)
        self.assertFalse(any(".env" in n or "gunluk" in n for n in names))          # anahtar ve günlük taşınmaz
        self.assertNotIn(b"sk-gizli-anahtar", ex["bytes"])
        self.assertEqual(ex["manifest"]["ozet"]["haber"], 1)
        self.assertEqual(ex["manifest"]["ozet"]["islem_gunlugu"], 1)
        self.assertEqual(ex["manifest"]["ozet"]["rapor"], 1)

        live = db.connect(self.dst / "bist_haber.db")                      # panel açıkken içe aktarma
        res = transfer.import_bytes(ex["bytes"], self.dst, self.dst / "bist_haber.db")
        self.assertEqual(live.execute("SELECT COUNT(*) FROM impacts").fetchone()[0], 1)   # açık bağlantı yeni veriyi görür
        live.close()
        c = sqlite3.connect(self.dst / "bist_haber.db")
        self.assertEqual(c.execute("SELECT ticker, reason FROM impacts").fetchone(), ("AKBNK", "neden"))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM trade_journal").fetchone()[0], 1)
        c.close()
        self.assertEqual(json.loads((self.dst / "ayarlar.json").read_text(encoding="utf-8"))["haber_butce_usd"], 7.5)
        self.assertEqual((self.dst / "raporlar" / "2026-11-06_aksam.md").read_text(encoding="utf-8"), "# akşam raporu")
        p = sqlite3.connect(self.dst / "backtest" / "pilot.db")
        self.assertEqual(p.execute("SELECT value FROM pilot_meta").fetchone()[0], "pilot verisi")
        p.close()
        # yeni bilgisayarın kendi anahtarı yerinde, yedek alındı
        self.assertEqual((self.dst.parent / ".env").read_text(encoding="utf-8"), "OPENAI_API_KEY=sk-yeni-bilgisayar\n")
        self.assertTrue((Path(res["yedek"]) / "bist_haber.db").exists())

    def test_backup_keeps_previous_data(self):
        ex = self.export()
        c = db.connect(self.dst / "bist_haber.db")
        c.execute("INSERT INTO prices(ticker,date,close,volume) VALUES('ESKI','2026-01-01',1,1)")
        c.commit()
        c.close()
        res = transfer.import_bytes(ex["bytes"], self.dst, self.dst / "bist_haber.db")
        b = sqlite3.connect(Path(res["yedek"]) / "bist_haber.db")
        self.assertEqual(b.execute("SELECT ticker FROM prices").fetchone()[0], "ESKI")          # önceki hâl yedekte
        b.close()
        c = sqlite3.connect(self.dst / "bist_haber.db")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM prices WHERE ticker='ESKI'").fetchone()[0], 0)
        c.close()

    def test_tampered_or_foreign_files_are_rejected(self):
        ex = self.export()
        self.assertTrue(transfer.inspect(ex["bytes"])["ok"])
        # bir parçası değiştirilmiş dosya
        src = zipfile.ZipFile(io.BytesIO(ex["bytes"]))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n in src.namelist():
                b = src.read(n)
                z.writestr(n, b + b"x" if n == "ayarlar.json" else b)
        r = transfer.inspect(buf.getvalue())
        self.assertFalse(r["ok"])
        self.assertTrue(any("bozuk ya da değiştirilmiş: ayarlar.json" in e for e in r["hatalar"]))
        with self.assertRaises(ValueError):
            transfer.import_bytes(buf.getvalue(), self.dst, self.dst / "bist_haber.db")
        self.assertFalse((self.dst / "yedek").exists())                    # reddedilen dosyada hiçbir şey değişmez
        # zip olmayan / Halley'e ait olmayan
        self.assertFalse(transfer.inspect(b"merhaba")["ok"])
        buf2 = io.BytesIO()
        with zipfile.ZipFile(buf2, "w") as z:
            z.writestr("manifest.json", json.dumps({"uygulama": "Baska"}))
        self.assertFalse(transfer.inspect(buf2.getvalue())["ok"])

    def test_unsafe_paths_are_rejected(self):
        ex = self.export()
        src = zipfile.ZipFile(io.BytesIO(ex["bytes"]))
        man = json.loads(src.read("manifest.json"))
        evil = b"zarar"
        man["dosyalar"]["../../Windows/zarar.txt"] = {"sha256": transfer._sha(evil), "boyut": 5}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n in src.namelist():
                z.writestr(n, json.dumps(man) if n == "manifest.json" else src.read(n))
            z.writestr("../../Windows/zarar.txt", evil)
        r = transfer.inspect(buf.getvalue())
        self.assertFalse(r["ok"])
        self.assertTrue(any("Güvenli olmayan" in e for e in r["hatalar"]))
        # .env de içe aktarılamaz (izinli adlar dışında)
        self.assertFalse(transfer._safe(".env"))
        self.assertFalse(transfer._safe("C:/x.db"))


if __name__ == "__main__":
    unittest.main()
