"""D: piyasa rejimi (bilgi amaçlı) — trend, oynaklık yüzdeliği, genişlik; geriye dönük bilgi yok."""
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from bist_haber import db, regime, technical

END = date(2026, 11, 6)


def days(n):
    out, d = [], END
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return out[::-1]


class RegimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)

    def put(self, t, closes, vol=1e6, rng=0.01):
        for d, c in zip(days(len(closes)), closes):
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                              (t, d, c, c * (1 + rng), c * (1 - rng), c, vol))

    def test_uptrend_breadth_and_definitions(self):
        up = [100 * 1.002 ** i for i in range(300)]
        # son 20 günde gün içi aralık genişliyor → oynaklık yüksek
        for i, (d, c) in enumerate(zip(days(300), up)):
            rng = 0.03 if i >= 280 else 0.005
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('XU100',?,?,?,?,?,0)",
                              (d, c, c * (1 + rng), c * (1 - rng), c))
        self.put("AAA", up[-100:])                               # likit, yükselişte → EMA50 üstünde
        self.put("BBB", [100 * 0.997 ** i for i in range(100)])  # likit, düşüşte → altında
        self.put("CCC", up[-100:], vol=10)                       # sığ → genişliğe girmez
        self.conn.commit()
        r = regime.regime(self.conn, END)
        self.assertEqual(r["trend"], "yükseliş")
        self.assertEqual(r["oynaklik"], "yüksek")
        self.assertEqual((r["genislik_hisse"], round(r["genislik_%"])), (2, 50))
        self.assertIn("**yükseliş**", r["ozet"])
        closes = [x * 1 for x in up]
        self.assertAlmostEqual(r["ema50"], technical.ema(closes, 50), places=6)

    def test_downtrend_and_no_lookahead(self):
        down = [100 * 0.998 ** i for i in range(300)]
        self.put("XU100", down)
        self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('XU100','2026-11-09',"
                          "200,200,200,200,0)")                  # sonraki gün sıçraması 6 Kasım hesabına girmemeli
        self.conn.commit()
        r = regime.regime(self.conn, END)
        self.assertEqual((r["gun"], r["trend"]), ("2026-11-06", "düşüş"))
        self.assertIsNone(r["genislik_%"])
        self.assertIn("genişlik hesaplanamadı", r["ozet"])

    def test_not_enough_history(self):
        self.put("XU100", [100] * 50)
        self.conn.commit()
        self.assertIn("yeterli fiyat geçmişi yok", regime.regime(self.conn, END)["yok"])


if __name__ == "__main__":
    unittest.main()
