"""Aşama 5 (2026-11-15): grafik verisi (EMA teknik analizle aynı), olası fiyat aralığı konisi, seviyeler, açıklama."""
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from bist_haber import chart, db, technical


class ChartData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        d, px = date(2025, 11, 3), 100.0
        n = 0
        while n < 260:
            if d.weekday() < 5:
                px *= 1 + (0.01 if n % 3 else -0.012)
                self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('AAA',?,?,?,?,?,?)",
                                  (d.isoformat(), px * 0.995, px * 1.01, px * 0.985, px, 1e5 + n))
                n += 1
            d += timedelta(days=1)
        self.conn.commit()

    def test_ema_matches_technical_and_history_trims(self):
        df = chart.history(self.conn, "AAA", 120)
        self.assertEqual(len(df), 120)
        closes = [r[0] for r in self.conn.execute("SELECT close FROM prices WHERE ticker='AAA' ORDER BY date")]
        for n in (20, 50, 200):
            self.assertAlmostEqual(df[f"EMA {n}"].iloc[-1], technical.ema(closes, n), places=9)
        self.assertTrue(chart.history(self.conn, "YOK").empty)

    def test_cone_widens_with_sqrt_time_and_skips_holidays(self):
        c = chart.cone(100.0, date(2026, 10, 27), 0.02, 4)          # 28 Ekim yarım gün / 29 Ekim tatil
        self.assertEqual(len(c), 5)
        self.assertNotIn("2026-10-29", [d.date().isoformat() for d in c["date"]])
        last = c.iloc[-1]
        self.assertAlmostEqual(last["p90"], 100 * math.exp(1.2816 * 0.02 * 2), places=6)
        self.assertTrue(last["p10"] < last["p25"] < last["p50"] < last["p75"] < last["p90"])
        self.assertEqual(last["p50"], 100.0)                           # yön varsayılmaz
        self.assertTrue(chart.cone(100.0, date(2026, 11, 13), None).empty)
        df = chart.history(self.conn, "AAA", 70)
        self.assertGreater(chart.daily_vol(df), 0)

    def test_cone_text_and_levels(self):
        cs = chart.cone_summary(chart.cone(100.0, date(2026, 11, 13), 0.02, 10))
        self.assertIsInstance(cs["p90"], float)
        txt = chart.cone_text(cs, {"Giriş": 100.2, "TP1": 105.0, "Zarar durdur (SL)": 85.0})
        self.assertIn("TP1 (105.00) bu aralığın içinde", txt)
        self.assertIn("SL (85.00) aralığın altında", txt)
        far = chart.cone_text(cs, {"Giriş": 140.0, "TP1": 150.0, "Zarar durdur (SL)": 135.0})
        self.assertIn("Giriş (140.00) aralığın dışında", far)
        self.assertIn("giriş gerçekleşince", far)
        self.assertNotIn("TP1 (", far)
        self.assertIn("hesaplanamadı", chart.cone_text({}))
        ready = {"giris": 10, "giris_alt": 9.8, "azami_giris": 10.2, "sl": 9, "tp1": 12, "tp2": 13}
        lv = chart.plan_levels({"destek_20g": 9.5, "direnc_20g": 11}, {"giris": 1, "sl": 1, "tp1": 1, "tp2": 1}, ready)
        self.assertEqual((lv["Giriş"], lv["_band"], lv["Destek (20g)"]), (10, (9.8, 10.2), 9.5))

    def test_figure_builds_and_labels_do_not_overlap(self):
        df = chart.history(self.conn, "AAA", 60)
        c = chart.cone(float(df["close"].iloc[-1]), df["date"].iloc[-1].date(), chart.daily_vol(df), 10)
        lv = {"Giriş": 100.0, "Direnç (20g)": 100.1, "Zarar durdur (SL)": 95, "_band": (99.5, 100.4)}
        fig = chart.figure(df, c, lv)
        spec = fig.to_dict()
        self.assertEqual(len(spec["vconcat"]), 2)
        texts = [ly for ly in spec["vconcat"][0]["layer"] if ly.get("mark", {}).get("type") == "text"]
        vals = sorted(r["ly"] for r in spec["datasets"][texts[0]["data"]["name"]])
        self.assertTrue(all(b - a > 0 for a, b in zip(vals, vals[1:])))
        self.assertIsNone(chart.figure(chart.history(self.conn, "YOK")))
        # karanlık modda beyaz zemin olmamalı; açık modda yazılar koyu
        self.assertEqual(spec["config"]["background"], "transparent")
        self.assertEqual(spec["config"]["axis"]["labelColor"], "#cbd5e1")
        light = chart.figure(df, c, lv, dark=False).to_dict()
        self.assertEqual(light["config"]["axis"]["labelColor"], "#334155")


if __name__ == "__main__":
    unittest.main()
