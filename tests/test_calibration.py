"""Faz 3 ön kayıtlı eşik testinin ücretsiz testleri (yapay veriyle)."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from bist_haber import backtest, calibration, report


def _day(i):
    return (date(2026, 1, 1) + timedelta(days=i)).isoformat()


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = backtest.connect(Path(self.temp.name) / "pilot.db")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.conn.close)

    def make(self, n, score_of, excess_of, locked=lambda i: False):
        """n olay: her biri 1 gün arayla; skor ve 5 günlük endekse göre getiri fonksiyonla verilir."""
        results = []
        for i in range(n):
            nid = f"kap:{i}"
            mag, conf = score_of(i)
            pub = _day(i) + "T12:00:00+03:00"
            self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,fetched_at) "
                              "VALUES(?,'kap',?,?,'x','now')", (nid, pub, _day(i)))
            self.conn.execute("INSERT INTO pilot_selection VALUES(?)", (nid,))
            self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,"
                              "event_type,published_at,effective_date) VALUES(?,?,1,?,?,'orta','diger',?,?)",
                              (nid, "T%d" % i, mag, conf, pub, _day(i)))
            for h in calibration.REPORT_HORIZONS:
                results.append({"bildirim": nid, "hisse": "T%d" % i, "vade": h, "giriş": _day(i + 1),
                                "çıkış": _day(i + h), "endekse_göre_%": excess_of(i), "eksik": "",
                                "uygulanabilirlik": "kilit" if locked(i) else ""})
        self.conn.commit()
        return results

    def test_small_sample_selects_nothing_and_never_validates(self):
        rows = self.make(10, lambda i: (3, 1.0), lambda i: 1.0)
        rep = calibration.calibrate(self.conn, rows)
        self.assertIsNone(rep["seçilen_eşik"])
        self.assertIsNone(rep["doğrulama"])
        self.assertIn("yetersiz veri", rep["durum"])

    def test_threshold_chosen_on_development_only_with_conservative_tie_break(self):
        high = lambda i: i % 2 == 0
        rows = self.make(120, lambda i: (3, 1.0) if high(i) else (1, 0.8), lambda i: 2.0 if high(i) else -1.0)
        rep = calibration.calibrate(self.conn, rows)
        # 1.0–3.0 arası eşiklerin hepsi yalnız yüksek skorlu olayları alır (ortalama eşit) → en temkinlisi seçilir.
        self.assertEqual(rep["seçilen_eşik"], 3.0)
        self.assertEqual(rep["geliştirme_olay"], 72)
        self.assertGreater(rep["doğrulama"]["pozitif_5g"]["olay"], 0)

    def test_validation_results_cannot_change_the_choice(self):
        high = lambda i: i % 2 == 0
        a = calibration.calibrate(self.conn, self.make(120, lambda i: (3, 1.0) if high(i) else (1, 0.8),
                                                       lambda i: 2.0 if high(i) else -1.0))
        self.conn.execute("DELETE FROM impacts"); self.conn.execute("DELETE FROM pilot_selection")
        self.conn.execute("DELETE FROM news"); self.conn.commit()
        b = calibration.calibrate(self.conn, self.make(
            120, lambda i: (3, 1.0) if high(i) else (1, 0.8),
            lambda i: (2.0 if high(i) else -1.0) if i < 72 else (-5.0 if high(i) else 5.0)))
        self.assertEqual(a["seçilen_eşik"], b["seçilen_eşik"])
        self.assertLess(b["doğrulama"]["pozitif_5g"]["ortalama"], 0)  # doğrulama kötü olsa da seçim değişmedi

    def test_embargo_drops_development_outcomes_overlapping_validation(self):
        rows = self.make(100, lambda i: (3, 1.0), lambda i: 1.0)
        rep = calibration.calibrate(self.conn, rows)
        first_val = rep["doğrulama_başlangıcı"]
        dev_10d = rep["taban"][10]["olay"]
        allowed = sum(1 for r in rows if r["vade"] == 10 and int(r["bildirim"].split(":")[1]) < 60
                      and r["çıkış"] < first_val)
        self.assertEqual(dev_10d, allowed)
        self.assertLess(dev_10d, 60)

    def test_locked_rows_are_excluded_from_selection(self):
        rows = self.make(100, lambda i: (3, 1.0), lambda i: 1.0, locked=lambda i: i < 50)
        rep = calibration.calibrate(self.conn, rows)
        self.assertLessEqual(rep["taban"][5]["olay"], 10)

    def test_live_thresholds_untouched_and_text_report_readable(self):
        before = list(report.THRESHOLDS)
        rep = calibration.calibrate(self.conn, self.make(10, lambda i: (2, 0.5), lambda i: 0.5))
        text = calibration.as_text(rep)
        self.assertEqual(report.THRESHOLDS, before)
        self.assertIn("ÖN KAYITLI TEST", text)
        self.assertIn("Canlı eşikleri DEĞİŞTİRMEZ", text)


if __name__ == "__main__":
    unittest.main()
