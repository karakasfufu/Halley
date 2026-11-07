"""SL/TP senaryo testinin ücretsiz testleri (yapay pilot verisiyle)."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from bist_haber import backtest, scenario_test


def weekdays(start, n):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


class ScenarioTestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = backtest.connect(Path(self.temp.name) / "pilot.db")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.conn.close)
        self.days = weekdays(date(2025, 6, 2), 300)
        self.event_idx = 260  # yayın günü; giriş bir sonraki işlem günü
        for i, d in enumerate(self.days):
            self.conn.execute("INSERT INTO pilot_bars VALUES('XU100',?,100,101,99,100)", (d,))
        # Geçmiş: 100 civarında salınan fiyat → destek ~95, direnç ~110, ATR ~%3
        for i, d in enumerate(self.days[:self.event_idx + 1]):
            base = 100 + (10 if i % 20 == 10 else 0) - (5 if i % 20 == 0 else 0)
            self.bar(d, base, base + 1.5, base - 1.5, base)
        pub = self.days[self.event_idx] + "T19:00:00+03:00"
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,fetched_at) "
                          "VALUES('kap:1','kap',?,?,'Olumlu','n')", (pub, self.days[self.event_idx + 1]))
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,"
                          "reason,published_at,effective_date,flag) VALUES('kap:1','TEST',1,3,0.9,'orta','diger',"
                          "'olumlu haber',?,?,'teyitli')", (pub, self.days[self.event_idx + 1]))
        self.conn.commit()

    def bar(self, d, o, h, l, c):
        self.conn.execute("INSERT OR REPLACE INTO pilot_bars VALUES('TEST',?,?,?,?,?)", (d, o, h, l, c))

    def forward(self, path):
        """path: [(open, high, low, close), ...] giriş gününden itibaren."""
        for d, (o, h, l, c) in zip(self.days[self.event_idx + 1:], path):
            self.bar(d, o, h, l, c)
        self.conn.commit()

    def run_one(self):
        res = scenario_test.run(self.conn)
        self.assertEqual(len(res), 1)
        return res[0]

    def test_target_first(self):
        self.forward([(100, 102, 99, 101)] * 3 + [(105, 130, 104, 120)] + [(120, 121, 119, 120)] * 30)
        r = self.run_one()
        self.assertEqual(r["sonuç"], "TP")
        self.assertEqual(r["gün"], 4)
        self.assertGreater(r["getiri_%"], 0)

    def test_stop_first(self):
        self.forward([(100, 101, 99, 100), (98, 99, 80, 82)] + [(82, 83, 81, 82)] * 30)
        r = self.run_one()
        self.assertEqual(r["sonuç"], "SL")
        self.assertLess(r["getiri_%"], 0)

    def test_same_day_both_counts_as_stop(self):
        self.forward([(100, 140, 70, 100)] + [(100, 101, 99, 100)] * 30)
        r = self.run_one()
        self.assertEqual(r["sonuç"], "SL")
        self.assertIn("temkinli", r["not"])

    def test_gap_open_below_stop_fills_at_open(self):
        self.forward([(70, 72, 69, 71)] + [(71, 72, 70, 71)] * 30)
        r = self.run_one()
        self.assertEqual(r["sonuç"], "SL")
        self.assertEqual(r["gün"], 1)
        self.assertAlmostEqual(r["getiri_%"], 0.0)  # açılıştan girildi, açılıştan çıktı

    def test_unfinished_when_forward_data_short(self):
        self.forward([(100, 101, 99, 100)] * 5)
        self.assertEqual(self.run_one()["sonuç"], "devam ediyor")

    def test_levels_do_not_use_future_prices(self):
        self.forward([(100, 101, 99, 100)] * 31)
        a = self.run_one()
        self.forward([(100, 101, 99, 100)] * 10 + [(100, 500, 99, 400)] * 21)  # gelecekte dev sıçrama
        b = self.run_one()
        self.assertEqual((a["sl"], a["tp"]), (b["sl"], b["tp"]))

    def test_negative_news_is_not_tested(self):
        self.conn.execute("UPDATE impacts SET direction=-1")
        self.forward([(100, 101, 99, 100)] * 31)
        self.assertEqual(self.run_one()["sonuç"], "senaryo yok")

    def test_summary_text(self):
        self.forward([(100, 102, 99, 101)] * 3 + [(105, 130, 104, 120)] + [(120, 121, 119, 120)] * 30)
        s = scenario_test.summary(scenario_test.run(self.conn))
        self.assertEqual((s["tp"], s["sl"], s["test_edilen"]), (1, 0, 1))
        self.assertIn("geleceği görmeden", scenario_test.as_text(scenario_test.run(self.conn)))

    def test_missing_entry_open_is_not_measured(self):
        self.forward([(100, 101, 99, 100)] * 31)
        self.conn.execute("UPDATE pilot_bars SET open=NULL WHERE ticker='TEST' AND date=?", (self.days[self.event_idx + 1],))
        self.conn.commit()
        self.assertEqual(self.run_one()["sonuç"], "ölçülemedi")


if __name__ == "__main__":
    unittest.main()
