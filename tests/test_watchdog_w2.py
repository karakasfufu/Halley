"""W2: elle başlatılan sabah/akşam analizi, BIST takvim/saat kontrolü, değiştirilemez rapor arşivi."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, journal, market_calendar, prices, watchdog
from tests.test_signals import TODAY, news, seed

TZ = config.TR_TZ


def at(day, hh, mm=0):
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ)


class TimingTests(unittest.TestCase):
    def test_morning_before_open_is_fine(self):
        t = watchdog.timing("sabah", at(TODAY, 8, 30))          # 6 Kasım 2026 Cuma
        self.assertTrue(t["islem_gunu"])
        self.assertIsNone(t["uyari"])

    def test_morning_after_open_warns(self):
        self.assertIn("09:40", watchdog.timing("sabah", at(TODAY, 10, 5))["uyari"])

    def test_weekend_and_holiday_warn(self):
        sat = datetime(2026, 11, 7, 8, 0, tzinfo=TZ)
        self.assertFalse(watchdog.timing("sabah", sat)["islem_gunu"])
        self.assertIn("işlem yok", watchdog.timing("aksam", sat)["uyari"])
        hol = next(d for d in sorted(market_calendar.CLOSED) if d.startswith("2026") and
                   datetime.fromisoformat(d).weekday() < 5)
        self.assertIn("işlem yok", watchdog.timing("sabah", datetime.fromisoformat(hol + "T08:00:00+03:00"))["uyari"])

    def test_evening_before_close_warns_after_close_ok(self):
        self.assertIn("kapanmadı", watchdog.timing("aksam", at(TODAY, 17, 30))["uyari"])
        self.assertIn("kapanmadı", watchdog.timing("aksam", at(TODAY, 18, 5))["uyari"])   # kapanış seansı sürüyor
        self.assertIsNone(watchdog.timing("aksam", at(TODAY, 18, 30))["uyari"])

    def test_half_day_closes_early(self):
        d = datetime.fromisoformat("2026-10-28").date()
        self.assertEqual(watchdog.timing("aksam", at(d, 13, 0))["kapanis"], "12:40")
        self.assertIsNone(watchdog.timing("aksam", at(d, 13, 0))["uyari"])
        self.assertIn("12:40", watchdog.timing("aksam", at(d, 12, 0))["uyari"])


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        self.uni = {t: t for t in ("POS", "NEG", "NONE", "BRK")}
        for t in self.uni:
            self.conn.execute("INSERT INTO companies VALUES(?,?,NULL)", (t, t + " A.Ş."))
        for t in ("POS", "NEG", "BRK"):
            seed(self.conn, t)
        news(self.conn, "n1", "POS", 1, 3, 0.9)
        news(self.conn, "n2", "NEG", -1, 3, 0.9)
        # Kırılım senaryosu: alarm 104, geçerlilik 2 işlem günü; kapanış ~100 → süre doldu, iptal (gerçekleşmedi)
        self.conn.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,emir,alarm,giris,sl,tp1,"
                          "tp2,gecerlilik) VALUES('x','2026-11-03','BRK','otomatik','kirilim','stop',104,105,101,110,"
                          "115,2)")
        self.conn.commit()
        self.calls = []
        self.steps = {"update": lambda: self.calls.append("update") or {"kap": {"yeni": 2}},
                      "prices": lambda: self.calls.append("prices") or {"hisse": 5, "basarisiz": 0,
                                                                         "son_gun": TODAY.isoformat(), "geride": [],
                                                                         "fiyati_yok": ["NONE"]}}

    def run_s(self, kind, hh=8):
        return watchdog.run_session(self.conn, self.uni, kind, {}, ai=False, now=at(TODAY, hh), steps=self.steps)

    def test_morning_runs_all_steps_and_archives(self):
        out = self.run_s("sabah")
        self.assertEqual(self.calls, ["update", "prices"])
        self.assertIsNone(out["zaman"]["uyari"])
        md = (watchdog.report_dir() / f"{out['rapor']}.md").read_text(encoding="utf-8")
        for h in ("## 1. Gece gelen haberler", "## 2. Günün fırsatları", "## 3. Takip listesi",
                  "## 4. Açık sanal ve gerçek işlemler", "## 5. Riskli", "## 6. Önümüzdeki 5 işlem günü",
                  "## 7. Veri durumu", "yatırım tavsiyesi değildir"):
            self.assertIn(h, md)
        self.assertIn("Yapay zekâ analizi bu çalıştırmada yapılmadı", md)
        self.assertIn("1 şirketin Yahoo'da hiç fiyatı yok", md)
        self.assertIn("fiyatı olanların hepsi güncel", md)
        self.assertIn("⌛ #1 BRK: geçerlilik süresi doldu", md)
        data = json.loads((watchdog.report_dir() / f"{out['rapor']}.json").read_text(encoding="utf-8"))
        self.assertEqual([c["hisse"] for c in data["gecersiz"]], ["BRK"])
        brk = self.conn.execute("SELECT durum, sonuc_json FROM trade_journal WHERE ticker='BRK'").fetchone()
        self.assertEqual(brk["durum"], "iptal")
        self.assertEqual(json.loads(brk["sonuc_json"])["sonuc"], "gerçekleşmedi")

    def test_report_matches_decision_log(self):
        out = self.run_s("sabah")
        data = json.loads((watchdog.report_dir() / f"{out['rapor']}.json").read_text(encoding="utf-8"))
        logged = {r[0] for r in self.conn.execute("SELECT ticker FROM signal_log WHERE run_id=? AND karar='onerildi'",
                                                  (out["calistirma"]["run_id"],))}
        self.assertEqual({r["ticker"] for r in data["onerilen"]}, logged)
        # önerilenler sanal günlüğe yazıldı (panelle aynı kural)
        auto = {r[0] for r in self.conn.execute("SELECT ticker FROM trade_journal WHERE kaynak='otomatik' AND "
                                                "signal_day=?", (TODAY.isoformat(),))}
        self.assertEqual(auto, logged)
        self.assertNotIn("NEG", logged)

    def test_evening_skips_news_update(self):
        out = self.run_s("aksam", 19)
        self.assertEqual(self.calls, ["prices"])
        self.assertTrue(out["rapor"].endswith("_aksam"))

    def test_archive_never_overwrites(self):
        a = self.run_s("sabah")["rapor"]
        first = (watchdog.report_dir() / f"{a}.md").read_text(encoding="utf-8")
        b = self.run_s("sabah", 9)["rapor"]
        self.assertEqual((a, b), (f"{TODAY.isoformat()}_sabah", f"{TODAY.isoformat()}_sabah_2"))
        self.assertEqual((watchdog.report_dir() / f"{a}.md").read_text(encoding="utf-8"), first)
        self.assertEqual(watchdog.list_reports()[:2], [b, a])

    def test_late_morning_still_runs_but_warns(self):
        out = self.run_s("sabah", 11)
        md = (watchdog.report_dir() / f"{out['rapor']}.md").read_text(encoding="utf-8")
        self.assertIn("⚠️", md)
        self.assertIn("09:40", md)


class UpdateUniverseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.conn = db.connect(Path(self.tmp.name) / "u.db")
        self.addCleanup(self.conn.close)
        self.today = datetime.now(TZ).date().isoformat()
        self.seen = []

    def fake(self, c, tickers, period="1y"):
        self.seen.append((period, list(tickers)))
        for x in tickers:
            if x == "STALE":
                c.execute("INSERT OR REPLACE INTO prices(ticker,date,close) VALUES(?,?,1)", (x, "2026-10-20"))
            elif x != "MISS":
                c.execute("INSERT OR REPLACE INTO prices(ticker,date,close) VALUES(?,?,1)", (x, self.today))
        return len(tickers)

    def run_u(self, tickers):
        with patch.object(prices, "update", self.fake):
            return prices.update_universe(self.conn, tickers, batch=1)

    def test_incremental_full_behind_and_missing(self):
        self.conn.execute("INSERT INTO prices(ticker,date,close) VALUES('OLD',?,1)", (self.today,))
        r = self.run_u(["OLD", "NEW", "MISS", "OLD", "STALE"])
        self.assertEqual(self.seen, [("1mo", ["OLD"]), ("1y", ["MISS"]), ("1y", ["NEW"]), ("1y", ["STALE"])])
        self.assertEqual((r["hisse"], r["artimli"], r["tam"]), (4, 1, 3))
        self.assertEqual((r["geride"], r["fiyati_yok"]), (["STALE"], ["MISS"]))

    def test_no_data_ticker_skipped_then_retried_after_a_week(self):
        import json as _j
        self.run_u(["MISS"])
        self.seen.clear()
        r = self.run_u(["MISS"])
        self.assertEqual((self.seen, r["atlanan"], r["fiyati_yok"]), ([], 1, ["MISS"]))   # boşuna indirme yok
        f = config.DATA / "fiyat_yok.json"
        f.write_text(_j.dumps({"MISS": "2026-01-01"}), encoding="utf-8")                 # 7 günden eski
        self.run_u(["MISS"])
        self.assertEqual(self.seen, [("1y", ["MISS"])])

    def test_failed_batch_counted_others_continue(self):
        def fake(c, tickers, period="1y"):
            if "BAD" in tickers:
                raise RuntimeError("ağ")
            return 1

        with patch.object(prices, "update", fake):
            r = prices.update_universe(self.conn, ["A", "BAD"], batch=1)
        self.assertEqual(r["basarisiz"], 1)


class PanelButtonTests(unittest.TestCase):
    def test_morning_button_runs_and_shows_report(self):
        import os
        from datetime import timedelta
        from streamlit.testing.v1 import AppTest
        from bist_haber import pipeline
        from tests.test_signals import weekdays_back
        with tempfile.TemporaryDirectory() as t, patch.object(config, "DATA", Path(t)),                 patch.object(config, "DB_PATH", Path(t) / "live.db"),                 patch.dict(os.environ, {"OPENAI_API_KEY": "", "HALLEY_OFFLINE": "1"}),                 patch.object(pipeline, "update_all", lambda *a, **k: {"kap": {}}) as _u,                 patch.object(prices, "update_universe", lambda *a, **k: {"hisse": 2, "geride": []}):
            conn = db.connect()
            conn.execute("INSERT INTO companies VALUES('POS','POS A.Ş.',NULL)")
            today = datetime.now(TZ).date()
            import math
            for i, d in enumerate(weekdays_back(today, 260)):
                p_ = 100 * (1 + 0.01 * math.sin(i / 6.0))
                conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                             ("POS", d.isoformat(), p_ * 0.998, p_ * 1.01, p_ * 0.99, p_, 1_000_000))
            news(conn, "n1", "POS", 1, 3, 0.9, day=(today - timedelta(days=1)).isoformat())
            conn.commit()
            conn.close()
            at_ = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            at_.run(timeout=60)
            self.assertEqual(len(at_.exception), 0, str(at_.exception))
            at_.button(key="watch_sabah").click().run(timeout=60)
            self.assertEqual(len(at_.exception), 0, str(at_.exception))
            self.assertEqual(len(at_.error), 0, [e.value for e in at_.error])
            self.assertTrue(any("Sabah analizi" in m.value for m in at_.markdown))
            self.assertEqual(len(watchdog.list_reports()), 1)


if __name__ == "__main__":
    unittest.main()
