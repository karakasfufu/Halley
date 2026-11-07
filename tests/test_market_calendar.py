"""Borsa İstanbul tatil/yarım gün takvimi ve etki günü testleri."""
import unittest
from datetime import date, datetime

from bist_haber import config, macro_calendar as M, market_calendar as C
from bist_haber.textutil import effective_date


def tr(y, m, d, h=12, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=config.TR_TZ)


class DataTests(unittest.TestCase):
    def test_closed_days_are_weekdays_and_half_days_are_trading_days(self):
        for d in C.CLOSED:
            self.assertLess(date.fromisoformat(d).weekday(), 5, d)
        for d in C.HALF_DAYS:
            self.assertTrue(C.is_trading_day(date.fromisoformat(d)), d)

    def test_source_weekday_names(self):  # Midas listesindeki gün adları
        expected = {"2026-01-01": 3, "2026-03-20": 4, "2026-04-23": 3, "2026-05-01": 4, "2026-05-19": 1,
                    "2026-05-27": 2, "2026-05-29": 4, "2026-07-15": 2, "2026-10-29": 3,
                    "2026-03-19": 3, "2026-05-26": 1, "2026-10-28": 2}
        for d, wd in expected.items():
            self.assertEqual(date.fromisoformat(d).weekday(), wd, d)

    def test_weekend_holidays_not_listed(self):
        self.assertNotIn("2026-08-30", C.CLOSED)   # Pazar
        self.assertNotIn("2027-05-01", C.CLOSED)   # Cumartesi


class RealDataTests(unittest.TestCase):
    def test_2026_session_count_matches_yahoo_xu100(self):
        # 2026-11-07'de Yahoo'dan indirilen XU100: 1 Ocak – 6 Kasım 2026 arası 212 seans; tarihler birebir aynıydı
        # (kapalı günde işlem yok, açık günde eksik yok). Yarım günlerde hacim medyanın %18–46'sı.
        self.assertEqual(C.trading_days_between(date(2025, 12, 31), date(2026, 11, 6)), 212)


class TradingDayTests(unittest.TestCase):
    def test_bayram_week(self):
        self.assertEqual(C.next_trading_day(date(2026, 5, 26)), date(2026, 6, 1))   # arefe → bayram sonrası
        self.assertEqual(C.trading_days_between(date(2026, 5, 22), date(2026, 6, 1)), 3)  # 25, 26, 1 Haziran
        self.assertEqual(C.add_trading_days(date(2026, 10, 27), 2), date(2026, 10, 30))

    def test_half_day_close(self):
        self.assertEqual(C.session_close(date(2026, 10, 28)), C.HALF_DAY_CLOSE)
        self.assertEqual(C.session_close(date(2026, 10, 27)), C.NORMAL_CLOSE)
        self.assertIsNone(C.session_close(date(2026, 10, 29)))


class EffectiveDateTests(unittest.TestCase):
    def test_normal_day(self):
        self.assertEqual(effective_date(tr(2026, 11, 5, 17, 59)), "2026-11-05")
        self.assertEqual(effective_date(tr(2026, 11, 5, 18, 0)), "2026-11-06")
        self.assertEqual(effective_date(tr(2026, 11, 6, 22, 29)), "2026-11-09")  # cuma akşamı → pazartesi

    def test_half_day_after_1240_moves_past_holiday(self):  # canlı veride gerçek örnek: 28 Ekim 18:49
        self.assertEqual(effective_date(tr(2026, 10, 28, 12, 30)), "2026-10-28")
        self.assertEqual(effective_date(tr(2026, 10, 28, 13, 0)), "2026-10-30")
        self.assertEqual(effective_date(tr(2026, 10, 28, 18, 49)), "2026-10-30")

    def test_holiday_news_moves_to_next_session(self):  # canlı veride gerçek örnek: 23 Nisan 13:09
        self.assertEqual(effective_date(tr(2026, 4, 23, 13, 9)), "2026-04-24")
        self.assertEqual(effective_date(tr(2026, 5, 27, 10, 0)), "2026-06-01")


class CoverageTests(unittest.TestCase):
    def test_religious_holidays_beyond_2026_flagged(self):
        self.assertIsNone(C.coverage_note(date(2026, 11, 7), date(2026, 11, 27)))
        self.assertIn("dini bayram", C.coverage_note(date(2026, 12, 20), date(2027, 1, 12)))

    def test_macro_window_lists_market_closures(self):
        u = M.upcoming(date(2026, 10, 20), 10)
        kinds = [(e["tarih"], e["tur"]) for e in u["olaylar"]]
        self.assertIn(("2026-10-22", "ppk"), kinds)
        self.assertIn(("2026-10-28", "yarim"), kinds)
        self.assertIn(("2026-10-29", "tatil"), kinds)
        self.assertEqual(u["bitis"], "2026-11-04")   # 29 Ekim sayılmadı


if __name__ == "__main__":
    unittest.main()
