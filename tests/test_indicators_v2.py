"""EMA, ADX, Bollinger, OBV, endekse göre güç, salınım dibi ve haber öncesi/sonrası hareket testleri (2026-11-07).

Referans değerler TA-Lib 0.8.1 (sektör standardı kütüphane) ile aynı seri üzerinde hesaplanıp donduruldu.
Ayrıca 44 gerçek BIST hissesinin 1 yıllık verisinde TA-Lib ile fark 0 çıktı (NOTLAR.md).
"""
import math
import unittest
from datetime import date, timedelta

from bist_haber import technical as T

TALIB = {"ema20": 108.04851881937492, "ema50": 108.91287874783512, "ema200": 108.72111003327579,
         "adx": 40.923082913960435, "pdi": 11.097264744309468, "mdi": 41.58241463218904,
         "bb_lo": 99.91729911341415, "bb_up": 121.29918081116861, "obv20": -47000.0}


def series(n=260):
    out, p, d = [], 100.0, date(2025, 1, 1)
    for i in range(n):
        p *= 1 + 0.012 * math.sin(i / 7.0) + 0.004 * math.cos(i / 3.1)
        o = p * (1 - 0.003 * math.sin(i))
        h = max(o, p) * (1 + 0.006 + 0.002 * math.cos(i / 2))
        l = min(o, p) * (1 - 0.006 - 0.002 * math.sin(i / 5))
        out.append({"date": (d + timedelta(days=i)).isoformat(), "open": o, "high": h, "low": l, "close": p,
                    "volume": 1000 + 500 * (i % 7)})
    return out


class TalibReferenceTests(unittest.TestCase):
    def setUp(self):
        self.bars = series()
        self.closes = [b["close"] for b in self.bars]

    def test_ema_matches_talib(self):
        for n in (20, 50, 200):
            self.assertAlmostEqual(T.ema(self.closes, n), TALIB[f"ema{n}"], places=9)

    def test_adx_and_di_match_talib(self):
        a, pdi, mdi = T.adx(self.bars)
        # TA-Lib ADX ile ~7e-7 puan fark (DI'lar 9 basamak aynı); ekranda ADX tam sayı gösterilir, etkisiz.
        self.assertAlmostEqual(a, TALIB["adx"], places=5)
        self.assertAlmostEqual(pdi, TALIB["pdi"], places=6)
        self.assertAlmostEqual(mdi, TALIB["mdi"], places=6)

    def test_bollinger_matches_talib(self):
        lo, mid, up, width = T.bollinger(self.closes)
        self.assertAlmostEqual(lo, TALIB["bb_lo"], places=9)
        self.assertAlmostEqual(up, TALIB["bb_up"], places=9)
        self.assertAlmostEqual(width, (up - lo) / mid * 100, places=9)

    def test_obv_20_day_change_matches_talib(self):
        obv = T.obv_series(self.bars)
        self.assertEqual(obv[-1] - obv[-21], TALIB["obv20"])
        self.assertEqual(T.analyze(self.bars)["obv_egilim"], "azalıyor")


class EdgeCaseTests(unittest.TestCase):
    def test_not_enough_data_returns_none(self):
        self.assertIsNone(T.ema([1.0] * 19, 20))
        self.assertIsNone(T.adx(series(28)))
        self.assertIsNone(T.bollinger([1.0] * 19))

    def test_flat_series(self):
        flat = [dict(b, open=10, high=10, low=10, close=10) for b in series(60)]
        self.assertEqual(T.bollinger([10.0] * 20)[3], 0.0)
        self.assertEqual(T.adx(flat)[0], 0.0)  # hareket yok → trend gücü yok

    def test_no_volume_means_no_obv_or_turnover(self):
        bars = [dict(b, volume=None) for b in series()]
        t = T.analyze(bars)
        self.assertIsNone(t["obv_egilim"])
        self.assertIsNone(t["islem_hacmi_tl"])

    def test_turnover_is_20_day_average_of_price_times_volume(self):
        bars = series()
        t = T.analyze(bars)
        self.assertAlmostEqual(t["islem_hacmi_tl"], sum(b["close"] * b["volume"] for b in bars[-20:]) / 20)

    def test_strong_uptrend_has_high_adx_and_plus_di(self):
        bars = [{"date": f"2025-01-{i:02d}" if i < 32 else f"2025-02-{i - 31:02d}", "open": 100 + i, "high": 101 + i,
                 "low": 99.5 + i, "close": 100.8 + i, "volume": 1} for i in range(1, 50)]
        a, pdi, mdi = T.adx(bars)
        self.assertGreater(a, 25)
        self.assertGreater(pdi, mdi)


class RelativeStrengthTests(unittest.TestCase):
    def test_stock_up_10_index_up_5(self):
        bars = [{"date": f"d{i:02d}", "close": 100.0} for i in range(21)]
        bars[-1]["close"] = 110.0
        bench = [{"date": f"d{i:02d}", "close": 1000.0} for i in range(21)]
        bench[-1]["close"] = 1050.0
        self.assertAlmostEqual(T.relative_strength(bars, bench, 20), (1.10 / 1.05 - 1) * 100)

    def test_missing_index_date_is_not_guessed(self):
        bars = [{"date": f"d{i:02d}", "close": 100.0} for i in range(21)]
        bench = [{"date": f"d{i:02d}", "close": 1000.0} for i in range(1, 21)]  # başlangıç günü yok
        self.assertIsNone(T.relative_strength(bars, bench, 20))
        self.assertIsNone(T.relative_strength(bars, None, 20))


class SwingLowTests(unittest.TestCase):
    def test_finds_most_recent_pivot_low(self):
        lows = [10, 9, 8, 9, 10, 11, 10, 9.5, 10, 11, 12]
        bars = [{"date": str(i), "close": l + 0.5, "high": l + 1, "low": l} for i, l in enumerate(lows)]
        self.assertEqual(T.swing_low(bars), 9.5)  # en yakın dip (8 daha eski)

    def test_monotonic_series_has_no_pivot(self):
        bars = [{"date": str(i), "close": 10 + i, "high": 11 + i, "low": 9 + i} for i in range(20)]
        self.assertIsNone(T.swing_low(bars))


class NewsMoveTests(unittest.TestCase):
    def setUp(self):
        self.bars = [{"date": f"2025-03-{d:02d}", "close": c} for d, c in
                     zip(range(3, 15), [100, 100, 101, 102, 104, 108, 110, 112, 111, 115, 116, 118])]

    def test_base_is_last_close_before_effective_day(self):
        m = T.news_moves(self.bars, "2025-03-09", atr_value=2.0)  # taban: 03-08 kapanışı 108
        self.assertAlmostEqual(m["once_5g_%"], (108 / 100 - 1) * 100)  # 03-03 → 03-08
        self.assertAlmostEqual(m["sonra_%"], (118 / 108 - 1) * 100)
        self.assertAlmostEqual(m["sonra_atr"], 5.0)

    def test_same_day_reaction_is_after_not_before(self):
        m = T.news_moves(self.bars, "2025-03-08")  # gün içi yayın: o günün kapanışı "sonra"ya girer
        self.assertAlmostEqual(m["sonra_%"], (118 / 104 - 1) * 100)  # taban 03-07 kapanışı 104
        self.assertIsNone(m["once_5g_%"])  # tabandan önce 5 işlem günü yok → hesaplanmaz, uydurulmaz

    def test_after_close_news_counts_that_days_close_as_before(self):
        # Gerçek örnek (SOKM): 2026-11-05 22:29 yayın → etki günü 11-06; 11-05 kapanışı haber ÖNCESİ.
        from datetime import datetime
        from bist_haber.textutil import effective_date
        from bist_haber import config
        eff = effective_date(datetime(2025, 3, 12, 22, 29, tzinfo=config.TR_TZ))
        self.assertEqual(eff, "2025-03-13")
        m = T.news_moves(self.bars, eff)
        self.assertAlmostEqual(m["sonra_%"], (118 / 115 - 1) * 100)  # taban 03-12 kapanışı 115

    def test_no_history_before_publication(self):
        self.assertEqual(T.news_moves(self.bars, "2025-03-01"), {})

    def test_latest_bar_is_base_means_no_after_move(self):
        m = T.news_moves(self.bars, "2025-03-20")
        self.assertIsNone(m["sonra_%"])


if __name__ == "__main__":
    unittest.main()
