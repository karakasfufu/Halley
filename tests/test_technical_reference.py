"""Teknik analiz doğruluk testleri: referans değerler, bağımsız pandas hesabı, veri kontrolleri, senaryo kuralları."""
import random
import unittest
from datetime import date, timedelta

import pandas as pd

from bist_haber import technical, tradeplan
from test_accuracy import memory_db

# StockCharts "RSI" eğitim örneği (Wilder RSI, 14 gün) — yaygın kullanılan referans tablo.
SC_CLOSES = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28,
             46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
SC_RSI = {15: 70.53, 16: 66.32, 17: 66.55, 18: 69.41, 19: 66.36, 20: 57.97}  # ilk k kapanışla RSI


def walk(n=300, seed=7, start=100.0):
    rnd = random.Random(seed)
    out, p = [], start
    d0 = date(2025, 11, 1)
    for i in range(n):
        p *= 1 + rnd.uniform(-0.03, 0.03)
        h, l = p * (1 + rnd.uniform(0, 0.02)), p * (1 - rnd.uniform(0, 0.02))
        out.append({"date": (d0 + timedelta(days=i)).isoformat(), "open": p, "high": h, "low": l,
                    "close": p, "volume": rnd.randint(500, 1500)})
    return out


class ReferenceValueTests(unittest.TestCase):
    def test_rsi_matches_stockcharts_reference_table(self):
        # Yayımlanan tablo ara değerleri yuvarlıyor; tam hesap her satırda ~0,06 daha düşük (ilk satır tam: 70,46).
        # Fark sabit ve aynı yönde olduğundan algoritma (Wilder) doğru; tolerans 0,1.
        diffs = []
        for k, expected in SC_RSI.items():
            value = technical.rsi(SC_CLOSES[:k])
            self.assertAlmostEqual(value, expected, delta=0.1, msg=f"{k} kapanış")
            diffs.append(value - expected)
        self.assertLess(max(diffs) - min(diffs), 0.02)  # sapma sistematik (yuvarlama), rastgele değil


class PandasCrossCheckTests(unittest.TestCase):
    """Göstergeler pandas ile ayrıca yazılmış hesapla aynı sonucu vermeli."""

    def setUp(self):
        self.bars = walk()
        self.df = pd.DataFrame(self.bars)
        self.t = technical.analyze(self.bars, today=date.fromisoformat(self.bars[-1]["date"]))

    def test_moving_averages(self):
        for n, key in ((20, "sma20"), (50, "sma50"), (200, "sma200")):
            self.assertAlmostEqual(self.t[key], self.df["close"].rolling(n).mean().iloc[-1], places=9)

    def test_macd_and_signal(self):
        c = self.df["close"]
        line = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
        signal = line.ewm(span=9, adjust=False).mean()
        self.assertAlmostEqual(self.t["macd"], line.iloc[-1], places=9)
        self.assertAlmostEqual(self.t["macd_sinyal"], signal.iloc[-1], places=9)

    def test_wilder_atr(self):
        d = self.df
        prev = d["close"].shift(1)
        tr = pd.concat([d["high"] - d["low"], (d["high"] - prev).abs(), (d["low"] - prev).abs()], axis=1).max(axis=1)
        tr = tr.iloc[1:].reset_index(drop=True)
        atr = tr.iloc[:14].mean()
        for v in tr.iloc[14:]:
            atr = (atr * 13 + v) / 14
        self.assertAlmostEqual(self.t["atr_%"], atr / d["close"].iloc[-1] * 100, places=9)

    def test_rsi_against_pandas_wilder(self):
        diff = self.df["close"].diff().iloc[1:]
        g, l = diff.clip(lower=0).tolist(), (-diff.clip(upper=0)).tolist()
        ag, al = sum(g[:14]) / 14, sum(l[:14]) / 14
        for a, b in zip(g[14:], l[14:]):
            ag, al = (ag * 13 + a) / 14, (al * 13 + b) / 14
        self.assertAlmostEqual(self.t["rsi14"], 100 - 100 / (1 + ag / al), places=9)

    def test_levels_and_performance(self):
        d = self.df
        self.assertAlmostEqual(self.t["destek_20g"], d["low"].iloc[-20:].min(), places=9)
        self.assertAlmostEqual(self.t["onceki_destek_20g"], d["low"].iloc[-21:-1].min(), places=9)  # bugün hariç
        self.assertAlmostEqual(self.t["onceki_destek_60g"], d["low"].iloc[-61:-1].min(), places=9)
        self.assertAlmostEqual(self.t["direnc_20g"], d["high"].iloc[-20:].max(), places=9)
        self.assertAlmostEqual(self.t["zirve_52h"], d["high"].iloc[-252:].max(), places=9)
        self.assertAlmostEqual(self.t["perf_20g_%"], (d["close"].iloc[-1] / d["close"].iloc[-21] - 1) * 100, places=9)


class DataCheckTests(unittest.TestCase):
    def test_clean_recent_series_has_no_warnings(self):
        b = walk()
        _, critical = technical.data_checks(b, today=date.fromisoformat(b[-1]["date"]))
        w, _ = technical.data_checks(b, today=date.fromisoformat(b[-1]["date"]))
        self.assertEqual(w, [])
        self.assertFalse(critical)

    def test_stale_prices_warn_and_very_stale_is_critical(self):
        b = walk()
        last = date.fromisoformat(b[-1]["date"])
        w, c = technical.data_checks(b, today=last + timedelta(days=7))
        self.assertTrue(any("güncel değil" in x for x in w))
        _, c2 = technical.data_checks(b, today=last + timedelta(days=20))
        self.assertTrue(c2)

    def test_jump_beyond_daily_limit_recent_is_critical_old_is_warning(self):
        b = walk()
        for x in b[-10:]:
            for k in ("open", "high", "low", "close"):
                x[k] *= 0.5  # yarıya inme: düzeltilmemiş bölünme gibi
        w, c = technical.data_checks(b, today=date.fromisoformat(b[-1]["date"]))
        self.assertTrue(c)
        self.assertTrue(any("sıçrama" in x for x in w))
        b2 = walk()
        for x in b2[-200:]:
            for k in ("open", "high", "low", "close"):
                x[k] *= 0.5
        w2, c2 = technical.data_checks(b2, today=date.fromisoformat(b2[-1]["date"]))
        self.assertFalse(c2)
        self.assertTrue(any("sıçrama" in x for x in w2))

    def test_gap_zero_volume_and_flat_days(self):
        b = walk()
        for x in b[-30:]:
            x["date"] = (date.fromisoformat(x["date"]) + timedelta(days=15)).isoformat()
        for x in b[-5:]:
            x["volume"] = 0
            x["high"] = x["low"] = x["close"]
        w, _ = technical.data_checks(b, today=date.fromisoformat(b[-1]["date"]))
        text = " ".join(w)
        self.assertIn("boşluk", text)
        self.assertIn("hacim yok", text)
        self.assertIn("tek seviyede", text)

    def test_corporate_event_warning_from_news(self):
        conn = memory_db()
        b = walk(n=60)
        for x in b:
            conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('TEST',?,?,?,?,?,?)",
                         (x["date"], x["open"], x["high"], x["low"], x["close"], x["volume"]))
        conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,candidates,fetched_at) "
                     "VALUES('kap:9','kap',?,?,'Bedelsiz','Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim','TEST','n')",
                     (b[-10]["date"] + "T12:00:00+03:00", b[-10]["date"]))
        t = technical.for_ticker(conn, "TEST", today=date.fromisoformat(b[-1]["date"]))
        self.assertTrue(any("kurumsal olay" in x for x in t["veri_uyarilari"]))


class ScenarioRuleTests(unittest.TestCase):
    def tech(self, **kw):
        base = {"son_fiyat": 100.0, "atr_%": 3.0, "destek_20g": 95.0, "direnc_20g": 115.0, "zirve_52h": 130.0,
                "trend": "Yükseliş", "rsi14": 55.0, "macd_hist": 0.5, "fiyat_sma50_%": 5.0, "hacim_orani": 1.0,
                "gun_sayisi": 250, "veri_uyarilari": [], "veri_kritik": False}
        base.update(kw)
        return base

    news = {"score": 2.5, "direction": 1, "confidence": 0.9, "flags": "teyitli", "persistence": "orta", "reason": "kâr"}

    def test_support_based_stop_and_resistance_target(self):
        p = tradeplan.plan(self.tech(), self.news)
        self.assertAlmostEqual(p["sl"], 95.0 * 0.99)
        self.assertEqual(p["tp"], 115.0)
        self.assertGreaterEqual(p["rr"], 2)
        self.assertEqual(p["risk_seviyesi"], "düşük")
        lo, hi = p["vade"]
        self.assertTrue(5 <= lo <= hi)

    def test_stop_never_below_15_percent_and_always_below_entry(self):
        p = tradeplan.plan(self.tech(**{"atr_%": 12.0, "destek_20g": 50.0}), self.news)
        self.assertGreaterEqual(p["sl"], 85.0)
        self.assertLess(p["sl"], 100.0)

    def test_close_resistance_makes_scenario_unfavorable_and_risky(self):
        p = tradeplan.plan(self.tech(**{"atr_%": 4.0, "destek_20g": 80.0, "direnc_20g": 101.0,
                                        "direnc_60g": 101.5, "zirve_52h": 102.0}), self.news)
        self.assertTrue(p["elverissiz"])
        self.assertEqual(p["risk_seviyesi"], "yüksek")

    def test_noise_level_resistance_skipped_but_never_jumps_past_real_one(self):
        # 101 fiyata 1 ATR'den (3 TL) yakın → gürültü; ilk gerçek direnç 108 (60 gün); 130'a atlanmaz.
        p = tradeplan.plan(self.tech(**{"direnc_20g": 101.0, "direnc_60g": 108.0, "zirve_52h": 130.0}), self.news)
        self.assertEqual(p["tp"], 108.0)
        self.assertEqual(p["tp_dayanak"], "60 günlük direnç")
        self.assertTrue(any("hemen üstünde" in n for n in p["notlar"]))
        self.assertLess(p["rr"], 2)  # gerçek direnç yakın → risk/getiri zayıf, iyimser gösterilmez

    def test_downtrend_against_positive_news_weighs_more(self):
        p = tradeplan.plan(self.tech(trend="Düşüş", macd_hist=-0.1), self.news)
        self.assertEqual(p["risk_seviyesi"], "orta")

    def test_critical_data_blocks_scenario(self):
        p = tradeplan.plan(self.tech(veri_kritik=True, veri_uyarilari=["sıçrama"]), self.news)
        self.assertEqual(p["durum"], "yok")
        self.assertIn("kritik", p["neden_yok"])

    def test_no_buy_scenario_for_negative_news(self):
        p = tradeplan.plan(self.tech(), dict(self.news, score=-2.0, direction=-1))
        self.assertEqual(p["durum"], "yok")

    def test_explanation_is_scenario_language_not_advice(self):
        text = tradeplan.plan(self.tech(), self.news)["aciklama"]
        self.assertIn("Neden olumlu görünüyor", text)
        self.assertIn("yatırım tavsiyesi değildir", text)
        self.assertNotIn("almalısınız", text)


if __name__ == "__main__":
    unittest.main()
