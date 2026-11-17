"""O4 (17.11.2026): fiyat izlenebilirliği ürüne bağlandı — db.connect yedekli göç, prices.update yazımı fiyat_izi
üzerinden (kaynak, ayarlar, kütüphane/kod sürümü, değişen satırın eskisi), bilinmeyen geçmiş uydurulmaz, göç hatasında
uygulama bugünkü gibi çalışır, eş zamanlı açılışta tek göç. Ağ yok: yfinance taklit edilir."""
import json
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from bist_haber import db, fiyat_izi as fz, prices


def sahte_indirme(degerler):
    """degerler: {ticker: [(tarih, kapanis), ...]} → yf.download biçiminde (MultiIndex) DataFrame."""
    parcalar = {}
    for t, satir in degerler.items():
        idx = pd.to_datetime([d for d, _ in satir])
        parcalar[t + ".IS"] = pd.DataFrame({"Open": [c for _, c in satir], "High": [c + 1 for _, c in satir],
                                            "Low": [c - 1 for _, c in satir], "Close": [c for _, c in satir],
                                            "Volume": [1000.0] * len(satir)}, index=idx)
    return pd.concat(parcalar, axis=1)


def eski_db(p, satirlar=(("AAA", "2026-01-02", 10.5), ("AAA", "2026-01-05", 10.8))):
    c = sqlite3.connect(p)
    c.executescript(db.SCHEMA)
    c.executemany("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,1000)",
                  [(t, d, x, x + 1, x - 1, x) for t, d, x in satirlar])
    c.commit()
    c.close()


class Temel(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = self.tmp / "bist_haber.db"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Goc(Temel):
    def test_connect_migrates_with_backup_old_rows_unknown(self):
        eski_db(self.p)
        c = db.connect(self.p)
        self.assertTrue(fz.kurulu(c))
        yedek = list((self.tmp / "yedek").glob("*_fiyat_izi_oncesi.db"))
        self.assertEqual(len(yedek), 1)
        y = sqlite3.connect(yedek[0])
        self.assertEqual(y.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(y.execute("SELECT COUNT(*) FROM prices").fetchone()[0], 2)
        y.close()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM prices WHERE indirme_id IS NULL").fetchone()[0], 2)  # bilinmiyor
        c.close()
        c = db.connect(self.p)                                    # ikinci açılış: yeniden göç / yedek yok
        c.close()
        self.assertEqual(len(list((self.tmp / "yedek").glob("*_fiyat_izi_oncesi.db"))), 1)

    def test_fresh_db_no_pointless_backup(self):
        c = db.connect(self.p)
        self.assertTrue(fz.kurulu(c))
        self.assertFalse((self.tmp / "yedek").exists() and list((self.tmp / "yedek").glob("*fiyat_izi*")))
        c.close()

    def test_concurrent_open_single_migration(self):
        eski_db(self.p)
        hatalar = []

        def ac():
            try:
                db.connect(self.p).close()
            except Exception as e:
                hatalar.append(e)
        th = [threading.Thread(target=ac) for _ in range(4)]
        for t in th:
            t.start()
        for t in th:
            t.join()
        self.assertEqual(hatalar, [])
        c = sqlite3.connect(self.p)
        self.assertEqual([r[1] for r in c.execute("PRAGMA table_info(prices)")].count("indirme_id"), 1)
        c.close()

    def test_migration_failure_keeps_app_working(self):
        eski_db(self.p)
        with patch.object(fz, "migrate", side_effect=RuntimeError("deneme")):
            c = db.connect(self.p)                                # hata yutulur, Halley açılır
        self.assertFalse(fz.kurulu(c))
        with patch.object(prices.yf, "download", return_value=sahte_indirme({"AAA": [("2026-01-06", 11.0)]})):
            self.assertEqual(prices.update(c, ["AAA"]), 1)        # eski yolla yazar
        self.assertIsNone(prices.son_indirme(c))
        c.close()


class Indirme(Temel):
    def setUp(self):
        super().setUp()
        eski_db(self.p)
        self.c = db.connect(self.p)

    def tearDown(self):
        self.c.close()
        super().tearDown()

    def indir(self, degerler, period="1y"):
        with patch.object(prices.yf, "download", return_value=sahte_indirme(degerler)) as d:
            n = prices.update(self.c, list(degerler), period=period)
        return n, d

    def test_download_recorded_changed_rows_preserved(self):
        n, d = self.indir({"AAA": [("2026-01-02", 10.5), ("2026-01-05", 10.6), ("2026-01-06", 11.0)]})
        self.assertEqual(n, 3)
        self.assertEqual(d.call_args.kwargs["auto_adjust"], True)
        r = dict(self.c.execute("SELECT * FROM fiyat_indirme").fetchone())
        self.assertEqual(r["kaynak"], "yfinance")
        self.assertEqual(json.loads(r["ayarlar_json"]), {"period": "1y", "interval": "1d", "auto_adjust": True,
                                                          "group_by": "ticker", "threads": False})
        self.assertIn("auto_adjust=True", r["duzeltme"])
        self.assertEqual((r["hisse_sayisi"], r["satir_sayisi"], r["degisen_satir"]), (1, 3, 1))
        self.assertEqual(r["kaynak_surum"], getattr(prices.yf, "__version__", None))
        self.assertEqual(r["kod_surum"], "gelistirme")
        ids = dict(self.c.execute("SELECT date, indirme_id FROM prices WHERE ticker='AAA'").fetchall())
        self.assertIsNone(ids["2026-01-02"])                      # değişmeyen eski satır yeniden yazılmadı: bilinmiyor
        self.assertEqual((ids["2026-01-05"], ids["2026-01-06"]), (r["id"], r["id"]))
        e = dict(self.c.execute("SELECT * FROM fiyat_eski").fetchone())
        self.assertEqual((e["date"], e["close"], e["onceki_indirme_id"]), ("2026-01-05", 10.8, None))   # önceki hâl
        once = fz.durum_once(self.c, r["id"])                     # indirmeden önceki durum geri kurulur
        self.assertEqual(once[("AAA", "2026-01-05")][3], 10.8)
        self.assertNotIn(("AAA", "2026-01-06"), once)
        s = prices.son_indirme(self.c)
        self.assertEqual((s["degisen"], s["eski_kayit"], s["bilinmeyen_satir"]), (1, 1, 1))

    def test_second_download_chain_and_append_only(self):
        self.indir({"AAA": [("2026-01-05", 10.6)]})
        self.indir({"AAA": [("2026-01-05", 10.7)]}, period="1mo")
        rows = self.c.execute("SELECT indirme_id, close, onceki_indirme_id FROM fiyat_eski ORDER BY indirme_id").fetchall()
        self.assertEqual([tuple(x) for x in rows], [(1, 10.8, None), (2, 10.6, 1)])
        self.assertEqual(json.loads(self.c.execute("SELECT ayarlar_json FROM fiyat_indirme WHERE id=2").fetchone()[0])
                         ["period"], "1mo")
        for q in ("UPDATE fiyat_indirme SET kaynak='x'", "DELETE FROM fiyat_eski"):
            with self.assertRaises(sqlite3.DatabaseError):
                self.c.execute(q)

    def test_old_code_writer_compatible(self):
        """Geri dönüş: eski kod (indirme_id'siz INSERT OR REPLACE) göç edilmiş tabloya yazabilir; satır 'bilinmiyor'."""
        self.indir({"AAA": [("2026-01-06", 11.0)]})
        self.c.execute("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES('AAA','2026-01-06',"
                       "11,12,10,11.1,1000)")
        self.assertIsNone(self.c.execute("SELECT indirme_id FROM prices WHERE date='2026-01-06'").fetchone()[0])


if __name__ == "__main__":
    unittest.main()


from tests import test_panel_flows as _pf  # noqa: E402


class PanelO4(unittest.TestCase):
    setUp = _pf.PanelFlowTests.setUp
    app = _pf.PanelFlowTests.app
    go = _pf.PanelFlowTests.go

    def test_settings_shows_price_trace_and_unknown_history(self):
        at = self.app("⚙️ Ayarlar")
        cap = [c.value for c in at.caption if "Fiyat izlenebilirliği" in c.value]
        self.assertTrue(cap, "fiyat izi satırı yok")
        self.assertIn("bilinmiyor", cap[0])                       # izleme öncesi satırlar uydurulmadı
