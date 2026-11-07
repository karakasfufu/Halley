"""Makro takvim (PPK, TÜFE) testleri: veri tutarlılığı ve pencere hesabı."""
import unittest
from datetime import date

from bist_haber import macro_calendar as M


import tempfile as _tempfile
from pathlib import Path as _Path
from unittest.mock import patch as _patch
from bist_haber import config as _config

_TMP, _P = None, None


def setUpModule():  # kayıtlı resmi takvim (data/takvim_guncel.json) testleri etkilemesin
    global _TMP, _P
    _TMP = _tempfile.TemporaryDirectory()
    _P = _patch.object(_config, "DATA", _Path(_TMP.name))
    _P.start()


def tearDownModule():
    _P.stop()
    _TMP.cleanup()


class DataConsistencyTests(unittest.TestCase):
    def test_all_events_on_weekdays_and_sorted(self):
        ev = M.events()
        self.assertEqual([e["tarih"] for e in ev], sorted(e["tarih"] for e in ev))
        for e in ev:
            self.assertLess(date.fromisoformat(e["tarih"]).weekday(), 5, e)

    def test_ppk_on_wednesday_or_thursday(self):
        for d, _ in M.PPK:  # PPK perşembe; 22 Nisan 2026 çarşamba (23 Nisan tatili)
            self.assertIn(date.fromisoformat(d).weekday(), (2, 3), d)

    def test_tufe_is_monthly_early_in_month_for_previous_month(self):
        months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
                  "Kasım", "Aralık"]
        for d, period in M.TUFE:
            x = date.fromisoformat(d)
            self.assertLessEqual(x.day, 5)
            name, year = period.split()
            prev = (x.month - 2) % 12
            self.assertEqual(name, months[prev])
            self.assertEqual(int(year), x.year if x.month > 1 else x.year - 1)

    def test_known_weekday_names_from_source(self):  # kaynaktaki gün adları
        self.assertEqual(date(2026, 12, 3).weekday(), 3)   # 3 Aralık 2026 Perşembe
        self.assertEqual(date(2026, 11, 3).weekday(), 1)   # 3 Kasım 2026 Salı


class WindowTests(unittest.TestCase):
    def test_business_day_arithmetic(self):
        self.assertEqual(M.add_business_days(date(2026, 11, 7), 15), date(2026, 11, 27))  # cumartesiden
        self.assertEqual(M.business_days_between(date(2026, 11, 7), date(2026, 12, 3)), 19)

    def test_today_window_and_next_events(self):
        u = M.upcoming(date(2026, 11, 7), 15)
        self.assertEqual([(e["tarih"], e["tur"]) for e in u["olaylar"]], [("2026-11-12", "er"), ("2026-11-27", "fir")])
        self.assertEqual(u["bilinmeyen"], [])
        nxt = {e["tur"]: e["tarih"] for e in M.next_of_each(date(2026, 11, 7))}
        self.assertEqual(nxt, {"tufe": "2026-12-03", "ppk": "2026-12-10", "er": "2026-11-12", "fomc": "2026-12-09"})

    def test_event_inside_window_with_distance(self):
        u = M.upcoming(date(2026, 11, 26), 15)
        self.assertEqual([(e["tur"], e["is_gunu_sonra"]) for e in u["olaylar"]],
                         [("fir", 1), ("tufe", 5), ("fomc", 9), ("ppk", 10), ("ozet", 15)])

    def test_event_today_is_flagged(self):
        u = M.upcoming(date(2026, 12, 10), 5)
        self.assertTrue(u["olaylar"][0]["bugun"])

    def test_beyond_known_calendar_is_unknown_not_guessed(self):
        u = M.upcoming(date(2026, 12, 20), 15)
        self.assertIn("TÜİK enflasyon (TÜFE)", u["bilinmeyen"])
        self.assertFalse(any(e["tur"] == "tufe" for e in u["olaylar"]))
        self.assertEqual(next(e for e in M.next_of_each(date(2026, 12, 20)) if e["tur"] == "tufe")["dogrulama"],
                         "takvimde yok")

    def test_2027_dates_verified_from_official_tcmb_table(self):
        e = next(e for e in M.events() if e["tarih"] == "2027-03-18" and e["tur"] == "ppk")
        self.assertEqual(e["dogrulama"], "doğrulandı")

    def test_stale_warning(self):
        self.assertIsNone(M.stale(date(2026, 11, 7)))       # TÜFE 2026 takvimi yıl sonuna kadar
        self.assertIsNotNone(M.stale(date(2026, 12, 5)))    # yıl sonuna 30 günden az: 2027 takvimi eklenmeli

    def test_window_inside_known_year_is_not_unknown(self):
        u = M.upcoming(date(2026, 11, 26), 15)               # 17 Aralık'a kadar: 2026 takvimi kapsıyor
        self.assertEqual(u["bilinmeyen"], [])



class FedAndReportTests(unittest.TestCase):
    def test_fomc_tr_time_follows_us_daylight_saving(self):
        self.assertEqual(M.fomc_tr_time("2026-10-28"), "21:00")   # ABD yaz saati 1 Kasım'a kadar
        self.assertEqual(M.fomc_tr_time("2026-12-09"), "22:00")
        self.assertEqual(M.fomc_tr_time("2027-03-17"), "21:00")   # yaz saati 14 Mart'ta başlar

    def test_fomc_effect_is_next_trading_day(self):
        e = next(e for e in M.events() if e["tur"] == "fomc" and e["tarih"] == "2026-10-28")
        self.assertEqual(e["etki_gunu"], "2026-10-30")             # 29 Ekim BIST kapalı
        self.assertIn("projeksiyonlu", next(e for e in M.events() if e["tarih"] == "2026-12-09" and e["tur"] == "fomc")["ad"])

    def test_fomc_decision_days_are_wednesdays(self):  # FOMC 2 günlük toplantı Salı–Çarşamba
        for d, _ in M.FOMC:
            self.assertEqual(date.fromisoformat(d).weekday(), 2, d)

    def test_report_dates_are_trading_days(self):
        from bist_haber import market_calendar as C
        for d in M.ENFLASYON_RAPORU + M.FINANSAL_ISTIKRAR + M.PPK_OZET:
            self.assertTrue(C.is_trading_day(date.fromisoformat(d)), d)

    def test_ppk_summary_about_one_week_after_decision(self):
        for (d, _), o in zip(M.PPK[:8], M.PPK_OZET):
            self.assertTrue(5 <= (date.fromisoformat(o) - date.fromisoformat(d)).days <= 8, (d, o))


if __name__ == "__main__":
    unittest.main()
