"""2026-11-15 düzeltme: hacmi 21 gündür hep 0 olan (işlem görmeyen) hissede likidite engeli çalışmalı."""
import unittest
from datetime import date

from bist_haber import technical, tracker
from test_tp1_model import bars


class ZeroVolume(unittest.TestCase):
    def test_zero_volume_counts_as_illiquid(self):
        b = bars(260)
        for r in b[-25:]:
            r["volume"] = 0.0
        t = technical.analyze(b[-250:], date.fromisoformat(b[-1]["date"]))
        self.assertEqual(t["islem_hacmi_tl"], 0.0)
        self.assertIn("Likidite çok düşük", tracker.scenario_guard(t))

    def test_unknown_volume_stays_unknown(self):
        b = bars(260)
        for r in b:
            r["volume"] = None
        t = technical.analyze(b[-250:], date.fromisoformat(b[-1]["date"]))
        self.assertIsNone(t["islem_hacmi_tl"])                      # pilot fiyatları: hacim yok → engel uygulanmaz
        self.assertIsNone(tracker.scenario_guard(t))

    def test_normal_volume_unchanged(self):
        b = bars(260)
        t = technical.analyze(b[-250:], date.fromisoformat(b[-1]["date"]))
        want = sum(r["close"] * r["volume"] for r in b[-20:]) / 20
        self.assertAlmostEqual(t["islem_hacmi_tl"], want)


if __name__ == "__main__":
    unittest.main()
