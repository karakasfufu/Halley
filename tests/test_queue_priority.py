"""Analiz sırası (2026-11-09): açık/bekleyen işlem → likit → sığ → fiyatı olmayan; grup içinde en yeni önce."""
import tempfile
import unittest
from pathlib import Path

from bist_haber import analyzer, db


class QueuePriorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        self.n = 0

    def price(self, t, tl_volume):
        for d in ("2026-11-05", "2026-11-06"):
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,10,10,10,10,?)",
                              (t, d, tl_volume / 10))

    def news(self, cands, hour):
        self.n += 1
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,fetched_at)"
                          " VALUES(?,?,?,?,?,?,?,'new','f')", (f"n{self.n}", "kap", f"2026-11-08T{hour:02d}:00:00+03:00",
                                                               "2026-11-09", "t", "metin", cands))
        return f"n{self.n}"

    def broad_coverage(self):
        for i in range(analyzer.PRICE_COVERAGE_MIN):      # evrenin fiyatı indirilmiş gibi
            self.price(f"Z{i:03d}", 1e3)

    def test_order_and_newest_first_within_group(self):
        self.broad_coverage()
        self.price("LIQ", 5e6)
        self.price("THN", 1e5)
        self.price("HLD", 1e5)                           # sığ ama açık işlem var → en önce
        self.conn.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,"
                          "gecerlilik) VALUES('x','2026-11-06','HLD','otomatik','destek',10,9,11,12,5)")
        ids = {"nopx_new": self.news("NOPX", 23), "thin_new": self.news("THN", 22), "liq_old": self.news("LIQ", 8),
               "liq_new": self.news("LIQ", 20), "held_old": self.news("HLD", 1), "macro": self.news("", 21),
               "multi": self.news("NOPX,LIQ", 9)}
        self.conn.commit()
        order = [r["id"] for r in analyzer.pending(self.conn)]
        inv = {v: k for k, v in ids.items()}
        self.assertEqual([inv[i] for i in order],
                         ["held_old", "macro", "liq_new", "multi", "liq_old", "thin_new", "nopx_new"])
        self.assertEqual([r["id"] for r in analyzer.pending(self.conn, 2)], order[:2])   # sınır sıralamadan sonra

    def test_without_universe_prices_nobody_is_demoted(self):
        # canlı veritabanında sabah analizi çalışmadan önce yalnız birkaç hissenin fiyatı var (ölçüm 08.11: 9)
        self.price("LIQ", 5e6)
        a = self.news("NOPX", 23)
        b = self.news("LIQ", 20)
        self.conn.commit()
        self.assertEqual([r["id"] for r in analyzer.pending(self.conn)], [a, b])         # en yeni önce, eskisi gibi

    def test_empty_body_still_excluded(self):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,fetched_at)"
                          " VALUES('e','kap','2026-11-08T10:00:00+03:00','2026-11-09','t','   ','LIQ','new','f')")
        self.conn.commit()
        self.assertEqual(analyzer.pending(self.conn), [])


if __name__ == "__main__":
    unittest.main()
