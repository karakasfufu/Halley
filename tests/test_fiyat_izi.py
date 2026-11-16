"""FAZ 3: fiyat izlenebilirliği (bist_haber/fiyat_izi.py) — yedekli göç, ekle-yalnız kayıtlar, değişen satırların
korunması, önceki durumun geri kurulması, anlık görüntü parmak izi. Canlı kod bu modülü çağırmaz."""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from bist_haber import db, fiyat_izi as fz


def _db(tmp):
    p = Path(tmp) / "bist_haber.db"
    c = db.connect(p)
    c.executemany("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                  [("AAA", "2026-01-02", 10, 11, 9, 10.5, 1000), ("AAA", "2026-01-05", 10.5, 11, 10, 10.8, 900),
                   ("BBB", "2026-01-02", 50, 51, 49, 50.5, 10)])
    c.execute("INSERT INTO watchlist(ticker, eklendi) VALUES('AAA','2026-01-01')")    # kullanıcı verisi
    c.commit()
    return p, c


class Goc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p, self.c = _db(self.tmp)

    def tearDown(self):
        self.c.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migrate_backup_integrity_and_rows_unchanged(self):
        once = fz.veri_ozeti(self.c)
        r = fz.migrate(self.c, self.p)
        self.assertEqual(r["durum"], "kuruldu")
        y = sqlite3.connect(r["yedek"])
        self.assertEqual(y.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertNotIn("indirme_id", {x[1] for x in y.execute("PRAGMA table_info(prices)")})   # yedek göç öncesi
        y.close()
        self.assertEqual(fz.veri_ozeti(self.c), once)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM prices WHERE indirme_id IS NOT NULL").fetchone()[0], 0)
        self.assertEqual(fz.migrate(self.c, self.p)["durum"], "var")

    def test_old_writer_still_works_after_migration(self):
        fz.migrate(self.c, self.p)
        self.c.execute("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                       ("AAA", "2026-01-06", 10.8, 11, 10.5, 10.9, 800))     # prices.update ile aynı ifade
        self.assertIsNone(self.c.execute("SELECT indirme_id FROM prices WHERE date='2026-01-06'").fetchone()[0])
        db.connect(self.p).close()                                          # bugünkü connect yeni şemayı açar

    def test_failed_migration_rolls_back(self):
        c = sqlite3.connect(":memory:")                                    # prices tablosu yok → ALTER hata verir
        r = fz.migrate(c, None)
        self.assertEqual(r["durum"], "goc_hatasi")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='fiyat_indirme'").fetchone()[0], 0)


class Kayit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p, self.c = _db(self.tmp)
        fz.migrate(self.c, self.p)
        self.ayar = {"period": "1y", "interval": "1d", "auto_adjust": True}

    def tearDown(self):
        self.c.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _yaz(self, satir):
        return fz.yaz(self.c, satir, "yfinance", self.ayar, "auto_adjust=True (bölünme+temettü, geriye dönük)",
                      "0.2.x", "deneme")

    def test_changed_rows_preserved_and_state_reconstructed(self):
        once = {(r[0], r[1]): tuple(r[2:7]) for r in self.c.execute(
            "SELECT ticker, date, open, high, low, close, volume FROM prices")}
        i1 = self._yaz([("AAA", "2026-01-02", 9.9, 10.9, 8.9, 10.4, 1000),      # geriye dönük düzeltme: değişti
                        ("AAA", "2026-01-05", 10.5, 11, 10, 10.8, 900),         # aynı
                        ("AAA", "2026-01-06", 10.8, 11, 10.5, 10.9, 800)])      # yeni satır
        k = self.c.execute("SELECT * FROM fiyat_indirme WHERE id=?", (i1,)).fetchone()
        self.assertEqual((k["satir_sayisi"], k["degisen_satir"], k["hisse_sayisi"]), (3, 1, 1))
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM fiyat_eski").fetchone()[0], 1)
        self.assertEqual(self.c.execute("SELECT close FROM fiyat_eski").fetchone()[0], 10.5)
        geri = {k: v[:5] for k, v in fz.durum_once(self.c, i1).items()}
        self.assertEqual(geri, once)                                        # indirme öncesi durum birebir
        i2 = self._yaz([("AAA", "2026-01-02", 9.8, 10.8, 8.8, 10.3, 1000)])
        self.assertEqual({k: v[:5] for k, v in fz.durum_once(self.c, i2).items()}[("AAA", "2026-01-02")],
                         (9.9, 10.9, 8.9, 10.4, 1000))
        self.assertEqual({k: v[:5] for k, v in fz.durum_once(self.c, i1).items()}, once)

    def test_append_only(self):
        self._yaz([("AAA", "2026-01-02", 9.9, 10.9, 8.9, 10.4, 1000)])
        for q in ("UPDATE fiyat_indirme SET kaynak='x'", "DELETE FROM fiyat_indirme", "UPDATE fiyat_eski SET close=1",
                  "DELETE FROM fiyat_eski"):
            with self.assertRaises(sqlite3.DatabaseError):
                self.c.execute(q)

    def test_fingerprint_order_independent_and_snapshot(self):
        a = fz.ozet([("B", "d1", 1, 2, 0.5, 1.5, 10), ("A", "d1", 1, 2, 0.5, 1.5, 10)])
        b = fz.ozet([("A", "d1", 1, 2, 0.5, 1.5, 10), ("B", "d1", 1, 2, 0.5, 1.5, 10)])
        self.assertEqual(a, b)
        self.assertNotEqual(a, fz.ozet([("A", "d1", 1, 2, 0.5, 1.5001, 10), ("B", "d1", 1, 2, 0.5, 1.5, 10)]))
        o = fz.anlik_goruntu(self.c, Path(self.tmp) / "anlik" / "g1.db", "g1", "deneme")
        self.assertEqual(o["ozet_sha256"], fz.veri_ozeti(self.c)["ozet_sha256"])
        self.assertEqual(self.c.execute("SELECT ozet_sha256 FROM veri_anlik WHERE ad='g1'").fetchone()[0], o["ozet_sha256"])
        with self.assertRaises(sqlite3.DatabaseError):
            self.c.execute("DELETE FROM veri_anlik")

    def test_write_requires_migration(self):
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE prices (ticker TEXT, date TEXT, close REAL, volume REAL, open REAL, high REAL, low REAL)")
        with self.assertRaises(RuntimeError):
            fz.yaz(c, [], "yfinance", {}, "x")


if __name__ == "__main__":
    unittest.main()
