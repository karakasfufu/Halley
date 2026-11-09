"""Teknik analiz, analiz kalitesi profilleri, ucuz test ve ayarların ücretsiz testleri."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import analyzer, config, pipeline, technical
from test_accuracy import add_news, analysis, memory_db


def bars(closes, volume=1000):
    start = date(2025, 1, 1)
    return [{"date": (start + timedelta(days=i)).isoformat(), "open": c, "high": c * 1.01, "low": c * 0.99,
             "close": c, "volume": volume} for i, c in enumerate(closes)]


class TechnicalTests(unittest.TestCase):
    def test_rising_series_is_uptrend_with_high_rsi(self):
        t = technical.analyze(bars([100 + i for i in range(260)]))
        self.assertEqual(t["trend"], "Yükseliş")
        self.assertGreater(t["rsi14"], 90)
        self.assertGreater(t["macd"], 0)
        self.assertAlmostEqual(t["zirveye_uzaklik_%"], (359 / (359 * 1.01) - 1) * 100, places=4)
        self.assertIn("RSI aşırı alım bölgesinde", t["notlar"])

    def test_falling_series_is_downtrend_with_low_rsi(self):
        t = technical.analyze(bars([400 - i for i in range(260)]))
        self.assertEqual(t["trend"], "Düşüş")
        self.assertLess(t["rsi14"], 10)
        self.assertIn("RSI aşırı satım bölgesinde", t["notlar"])

    def test_flat_series_rsi_neutral_and_short_history_none(self):
        t = technical.analyze(bars([50.0] * 60))
        self.assertEqual(t["rsi14"], 50.0)
        self.assertIsNone(t["sma200"])
        self.assertIsNone(technical.analyze(bars([50.0] * 20)))
        self.assertEqual(technical.short_label(None), "teknik veri yok")

    def test_volume_spike_is_noted(self):
        b = bars([100.0] * 60)
        for x in b[-5:]:
            x["volume"] = 5000
        self.assertIn("hacim son 5 günde ortalamanın 5.0 katı", technical.analyze(b)["notlar"])

    def test_reads_from_prices_table(self):
        conn = memory_db()
        for i, c in enumerate([10 + i * 0.1 for i in range(40)]):
            conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('TEST',?,?,?,?,?,100)",
                         ((date(2026, 1, 1) + timedelta(days=i)).isoformat(), c, c, c, c))
        self.assertEqual(technical.for_ticker(conn, "TEST")["gun_sayisi"], 40)


class RecordingLLM:
    def __init__(self, result):
        self.result, self.calls = result, []

    def parse(self, model, system, user, schema, reasoning_effort=None):
        self.calls.append({"effort": reasoning_effort, "len": len(user), "schema": schema.__name__})
        if schema is analyzer.FilterResult:
            return analyzer.FilterResult(onemli=True, neden="test"), 10, 5
        return self.result, 1000, 2000


class QualityProfileTests(unittest.TestCase):
    def row(self):
        conn = memory_db()
        add_news(conn, body="Sözleşme bedeli 10 milyon TL. " * 3000)  # sınırdan uzun (önemli konu: 60 bin)
        return conn, conn.execute("SELECT * FROM news").fetchone()

    def test_default_and_pilot_path_keep_high_accuracy(self):
        conn, row = self.row()
        llm = RecordingLLM(analysis(impact=3))
        analyzer._work(llm, row, {"TEST": "Deneme"}, {})  # pilot bu yolu kullanır
        self.assertEqual([c["effort"] for c in llm.calls], ["high", "high"])  # etki 3 → ikinci görüş

    def test_economic_profile_low_effort_no_second_opinion_shorter_text(self):
        conn, row = self.row()
        high, eco = RecordingLLM(analysis(impact=5)), RecordingLLM(analysis(impact=5))
        analyzer._work(high, row, {"TEST": "Deneme"}, {}, analyzer.quality_profile("yuksek"))
        analyzer._work(eco, row, {"TEST": "Deneme"}, {}, analyzer.quality_profile("ekonomik"))
        self.assertEqual([c["effort"] for c in eco.calls], ["low"])
        self.assertLess(eco.calls[0]["len"], high.calls[0]["len"])

    def test_balanced_profile_second_opinion_only_for_big_calls(self):
        conn, row = self.row()
        mid, big = RecordingLLM(analysis(impact=3)), RecordingLLM(analysis(impact=4))
        analyzer._work(mid, row, {"TEST": "Deneme"}, {}, analyzer.quality_profile("dengeli"))
        analyzer._work(big, row, {"TEST": "Deneme"}, {}, analyzer.quality_profile("dengeli"))
        self.assertEqual(len(mid.calls), 1)
        self.assertEqual([c["effort"] for c in big.calls], ["medium", "medium"])

    def test_unknown_profile_falls_back_to_high_and_model_stays(self):
        self.assertEqual(analyzer.quality_profile("yok")["reasoning"], config.ANALYSIS_REASONING_EFFORT)
        self.assertEqual(config.MODEL_ANALYSIS, "gpt-5-mini")

    def test_cheap_test_saves_nothing(self):
        conn = memory_db()
        add_news(conn, body="Yeni iş sözleşmesi imzalandı. " * 20)
        llm = RecordingLLM(analysis(impact=4))
        out = analyzer.test_one(conn, {"TEST": "Deneme"}, llm=llm)
        self.assertEqual([c["effort"] for c in llm.calls], ["low"])
        self.assertGreater(out["usd"], 0)
        self.assertEqual(conn.execute("SELECT status FROM news").fetchone()[0], "new")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM impacts").fetchone()[0], 0)

    def test_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(pipeline, "SETTINGS_FILE", Path(temp) / "ayarlar.json"):
            self.assertEqual(pipeline.load_settings(), {})
            pipeline.save_settings(analiz_kalitesi="dengeli")
            self.assertEqual(pipeline.load_settings()["analiz_kalitesi"], "dengeli")

    def test_estimate_without_second_opinion_has_equal_bounds(self):
        from datetime import datetime
        from bist_haber import config
        conn = memory_db()
        add_news(conn, body="Metin " * 50, published=datetime.now(config.TR_TZ).isoformat(timespec="seconds"))
        est = pipeline.estimate_next_run(conn, 10, "ekonomik")
        self.assertEqual(est["low_usd"], est["high_usd"])
        self.assertGreater(pipeline.estimate_next_run(conn, 10, "yuksek")["high_usd"], est["high_usd"])


if __name__ == "__main__":
    unittest.main()
