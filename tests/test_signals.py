"""W1: ortak karar (panel = bekçi), karar izi nedenleri, değiştirilemez sinyal geçmişi."""
import math
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, signals, watchdog

TODAY = date(2026, 11, 6)


def weekdays_back(end: date, n: int):
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return list(reversed(out))


def seed(conn, ticker, volume=1_000_000, n=260, drift=0.0):
    for i, d in enumerate(weekdays_back(TODAY, n)):
        p = 100 * (1 + 0.01 * math.sin(i / 6.0)) * (1 + drift) ** i
        conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                     (ticker, d.isoformat(), p * 0.998, p * 1.01, p * 0.99, p, volume))


def news(conn, nid, ticker, direction=1, magnitude=3, confidence=0.9, status="analyzed", day="2026-11-05"):
    conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,fetched_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?,'n')", (nid, "rss:x", day + "T10:00:00+03:00", day, "Başlık", None,
                                                   "metin" if status != "new" else None, ticker, status))
    if status == "analyzed":
        conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,reason,"
                     "published_at,effective_date) VALUES(?,?,?,?,?,'orta','diger','gerekçe',?,?)",
                     (nid, ticker, direction, magnitude, confidence, day + "T10:00:00+03:00", day))


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        self.uni = {t: t for t in ("POS", "NEG", "LOW", "THIN", "NOPX", "NONE", "WAIT", "SKIP")}
        for t in self.uni:
            self.conn.execute("INSERT INTO companies VALUES(?,?,NULL)", (t, t + " A.Ş."))
        for t in ("POS", "NEG", "LOW"):
            seed(self.conn, t)
        seed(self.conn, "THIN", volume=1_000)                       # ~0,1 mn TL/gün → likidite
        news(self.conn, "n1", "POS", 1, 3, 0.9)
        news(self.conn, "n2", "NEG", -1, 3, 0.9)
        news(self.conn, "n3", "LOW", 1, 1, 0.5)                     # skor 0,5 → eşik altı
        news(self.conn, "n4", "THIN", 1, 3, 0.9)
        news(self.conn, "n5", "NOPX", 1, 3, 0.9)                    # fiyat yok
        news(self.conn, "n6", "WAIT", status="new")                 # metin/analiz bekliyor
        news(self.conn, "n7", "SKIP", status="skipped")
        self.conn.commit()

    def run_log(self):
        return watchdog.log_run(self.conn, self.uni, "aksam", window=7, today=TODAY)

    def codes(self):
        run = self.run_log()
        return run, dict(self.conn.execute("SELECT ticker, neden_kodu FROM signal_log WHERE run_id=?",
                                           (run["run_id"],)).fetchall())

    def test_every_ticker_gets_a_reason(self):
        run, c = self.codes()
        self.assertEqual(set(c), set(self.uni))
        self.assertEqual(c["NEG"], "HABER_OLUMSUZ")
        self.assertEqual(c["LOW"], "SKOR_ESIK_ALTI")
        self.assertEqual(c["THIN"], "LIKIDITE")
        self.assertEqual(c["NOPX"], "TEKNIK_VERI_YOK")
        self.assertEqual(c["NONE"], "HABER_YOK")
        self.assertEqual(c["WAIT"], "HABER_ANALIZ_BEKLIYOR")
        self.assertEqual(c["SKIP"], "HABER_ONEMSIZ")
        self.assertIn(c["POS"], ("ONERILDI", "SENARYO_UYGUN_DEGIL"))
        self.assertEqual(run["hisse"], 8)

    def test_recommended_rows_carry_levels_and_match_panel_plan(self):
        run, c = self.codes()
        ctx = signals.Context(self.conn, TODAY)
        from bist_haber import report
        row = next(r for r in report.build(self.conn, self.uni, days=7, as_of=TODAY) if r["ticker"] == "POS")
        p = ctx.plan(row)
        g = p["girisler"]
        logged = self.conn.execute("SELECT * FROM signal_log WHERE run_id=? AND ticker='POS'", (run["run_id"],)).fetchone()
        if g.get("en_uygun"):
            best = next(s for s in g["senaryolar"] if s["tur"] == g["en_uygun"])
            self.assertEqual((logged["senaryo"], logged["giris"], logged["sl"]), (best["tur"], best["giris"], best["sl"]))
        else:
            self.assertIsNone(logged["senaryo"])

    def test_log_is_append_only(self):
        run = self.run_log()
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE signal_log SET karar='onerildi' WHERE run_id=?", (run["run_id"],))
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM signal_log")
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM watch_runs")
        self.conn.rollback()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM signal_log").fetchone()[0], 8)

    def test_decision_on_uses_latest_run_up_to_day(self):
        watchdog.log_run(self.conn, self.uni, "sabah", today=TODAY)
        d = watchdog.decision_on(self.conn, "NEG", "2026-11-06")
        self.assertEqual((d["neden_kodu"], d["kind"]), ("HABER_OLUMSUZ", "sabah"))
        self.assertIsNone(watchdog.decision_on(self.conn, "NEG", "2026-11-05"))   # o gün kayıt yoktu

    def test_bad_kind_rejected(self):
        with self.assertRaises(ValueError):
            watchdog.log_run(self.conn, self.uni, "gece")


class PanelWithStockTests(unittest.TestCase):
    """Hisseli panel testi: boş veritabanlı panel testleri hisse ayrıntısını hiç çizmiyordu (W1'de silinen bir
    yardımcı işlev ancak gerçek veriyle karşılaştırmada yakalandı)."""

    def test_stock_details_render(self):
        import os
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as t, patch.object(config, "DATA", Path(t)), \
                patch.object(config, "DB_PATH", Path(t) / "live.db"), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "", "HALLEY_OFFLINE": "1"}):
            conn = db.connect()
            conn.execute("INSERT INTO companies VALUES('POS','POS A.Ş.',NULL)")
            today = date.today()
            for i, d in enumerate(weekdays_back(today, 260)):
                p = 100 * (1 + 0.01 * math.sin(i / 6.0))
                conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                             ("POS", d.isoformat(), p * 0.998, p * 1.01, p * 0.99, p, 1_000_000))
            news(conn, "n1", "POS", 1, 3, 0.9, day=(today - timedelta(days=1)).isoformat())
            conn.commit()
            conn.close()
            at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            at.run(timeout=60)
            self.assertEqual(len(at.exception), 0, str(at.exception))
            self.assertTrue(any("Trend gücü (ADX 14)" in d.value.to_string() for d in at.dataframe))   # teknik tablo çizildi


if __name__ == "__main__":
    unittest.main()
