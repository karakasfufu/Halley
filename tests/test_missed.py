"""W4: kaçırılan fırsat analizi — karar kaydına göre, geriye dönük bilgi olmadan."""
import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, market_calendar, missed

BASE = "2026-11-02"            # Pazartesi; karar akşam 19:00'da verildi
RUN_AT = "2026-11-02T19:00:00+03:00"


def tdays(start: date, end: date):
    d = start
    while d <= end:
        if market_calendar.is_trading_day(d):
            yield d.isoformat()
        d += timedelta(days=1)


class BaseDayTests(unittest.TestCase):
    def test_base_day_rules(self):
        self.assertEqual(missed.base_day("2026-11-09T08:30:00+03:00"), date(2026, 11, 6))   # sabah → Cuma
        self.assertEqual(missed.base_day("2026-11-06T18:05:00+03:00"), date(2026, 11, 5))   # kapanış oturmadı
        self.assertEqual(missed.base_day("2026-11-06T18:30:00+03:00"), date(2026, 11, 6))
        self.assertEqual(missed.base_day("2026-11-07T19:00:00+03:00"), date(2026, 11, 6))   # Cumartesi
        self.assertEqual(missed.base_day("2026-10-28T13:00:00+03:00"), date(2026, 10, 28))  # yarım gün 12:40
        self.assertEqual(missed.base_day("2026-10-29T19:00:00+03:00"), date(2026, 10, 28))  # 29 Ekim tatil


class MissedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        c = self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(c.close)
        pre = list(tdays(date(2026, 9, 15), date(2026, 11, 2)))
        self.post = ["2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
        # ileri kapanışlar (baz kapanış 100, ATR = 2 → 4 ATR = +%8 endekse göre)
        fwd = {"X": [103, 106, 109, 108], "Y": [103, 106, 109, 108], "Z": [101, 102, 104, 103],
               "R": [103, 106, 109, 108], "Q": [103, 106, 109, 108], "J": [120, 121, 122, 121],
               "T": [103, 106, 109, 108], "N": [103, 106, 109, 108]}
        for t in list(fwd) + ["XU100"]:
            base = 1000 if t == "XU100" else 100
            for d in pre:
                c.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)", (t, d, base, base * 1.01, base * 0.99, base, 1e6))
            for d, v in zip(self.post, fwd.get(t, [1000, 1000, 1000, 1000])):
                c.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)", (t, d, v, v * 1.01, v * 0.99, v, 1e6))
        cur = c.execute("INSERT INTO watch_runs(kind, day, started_at, summary_json) VALUES('aksam',?,?,'{}')",
                        (BASE, RUN_AT))
        self.run_id = cur.lastrowid
        codes = {"X": ("onerilmedi", "HABER_YOK", "{}"), "Y": ("onerilmedi", "HABER_YOK", "{}"),
                 "Z": ("onerilmedi", "HABER_YOK", "{}"), "R": ("onerildi", "ONERILDI", "{}"),
                 "Q": ("onerildi", "ONERILDI", "{}"), "J": ("onerilmedi", "HABER_YOK", "{}"),
                 "T": ("onerilmedi", "HABER_YOK", "{}"),
                 "N": ("onerilmedi", "SENARYO_UYGUN_DEGIL", json.dumps({"fiyatlanmis": True}))}
        for t, (k, code, det) in codes.items():
            c.execute("INSERT INTO signal_log(run_id,ticker,karar,neden_kodu,modul,neden,detay_json) VALUES(?,?,?,?,?,?,?)",
                      (self.run_id, t, k, code, "m", "n", det))
        for t, durum in (("R", "açık"), ("Q", "bekliyor")):
            c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
                      "durum) VALUES('x',?,?,'otomatik','destek',99,95,104,110,5,?)", (BASE, t, durum))
        # Y: haber karar anından SONRA geldi; T: başlıkta kodu geçen ama eşleşmemiş haber (karardan önce)
        c.execute("INSERT INTO news(id,source,published_at,effective_date,title,candidates,status,fetched_at) "
                  "VALUES('y1','kap','2026-11-03T10:00:00+03:00','2026-11-03','Y şirketi ihale kazandı','Y','analyzed','f')")
        c.execute("INSERT INTO news(id,source,published_at,effective_date,title,candidates,status,fetched_at) "
                  "VALUES('t1','rss:x','2026-11-01T10:00:00+03:00','2026-11-01','Analist: T hissesinde hedef yükseldi',"
                  "'BAŞKA','skipped','f')")
        c.commit()

    def scan(self, today=date(2026, 11, 7)):
        return missed.scan(self.conn, today)

    def test_detects_and_classifies(self):
        r = self.scan()
        got = {x["hisse"]: x for x in r["liste"]}
        self.assertEqual(set(got), {"X", "Y", "Q", "T", "N"})          # Z küçük, R girildi, J veri şüphesi
        self.assertAlmostEqual(got["X"]["endekse_gore_atr"], 4.5, places=6)  # (109−100)/2
        self.assertEqual(got["X"]["zirve_gunu"], "2026-11-05")
        self.assertEqual(got["Q"]["neden_kodu"], "ONERILDI")
        self.assertIn("HABER_SONRA", got["Y"]["etiketler"])
        self.assertNotIn("HABER_SONRA", got["X"]["etiketler"])
        self.assertIn("ESLESME", got["T"]["etiketler"])
        self.assertIn("FIYATLANMIS", got["N"]["etiketler"])
        self.assertEqual(r["gunler"][0]["veri_suphesi"], 1)
        self.assertFalse(r["gunler"][0]["tamamlandi"])                   # 4/5 gün → henüz kaydedilmez
        self.assertEqual(r["kaydedilen"], 0)

    def test_uses_logged_decision_not_hindsight(self):
        # karardan sonra eklenen analiz (ör. geç okunmuş haber) karar kodunu değiştirmemeli
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,candidates,status,fetched_at) "
                          "VALUES('x1','kap','2026-11-01T10:00:00+03:00','2026-11-01','X','X','analyzed','f')")
        self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,"
                          "reason,published_at,effective_date) VALUES('x1','X',1,3,0.9,'orta','diger','r',"
                          "'2026-11-01T10:00:00+03:00','2026-11-01')")
        got = {x["hisse"]: x for x in self.scan()["liste"]}
        self.assertEqual(got["X"]["neden_kodu"], "HABER_YOK")

    def test_prices_after_window_ignored(self):
        # pencere 5 gün: 6. günün (13.11) dev yükselişi Z'yi kaçırılan yapmamalı
        for d, v in (("2026-11-09", 103), ("2026-11-10", 130)):
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('Z',?,?,?,?,?,1e6)", (d, v, v, v, v))
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('XU100',?,1000,1000,1000,1000,0)", (d,))
        got = {x["hisse"] for x in self.scan(date(2026, 11, 11))["liste"]}
        self.assertNotIn("Z", got)

    def test_completed_window_is_stored_once_and_immutable(self):
        for t in ("X", "Y", "Z", "R", "Q", "J", "T", "N"):
            v = 103 if t == "Z" else 108        # Z eşik altında kalır (108 olsaydı tam 4 ATR → kaçırılan sayılırdı)
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,'2026-11-09',?,?,?,?,1e6)",
                              (t, v, v, v, v))
        self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('XU100','2026-11-09',1000,1000,1000,1000,0)")
        r = self.scan(date(2026, 11, 10))
        self.assertTrue(r["gunler"][0]["tamamlandi"])
        self.assertEqual(r["kaydedilen"], 5)
        self.assertEqual(self.scan(date(2026, 11, 10))["kaydedilen"], 0)     # ikinci kez eklenmez
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE missed_log SET neden_kodu='x'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM missed_log")

    def test_report_text(self):
        md = missed.report_md(self.scan())
        self.assertIn("**5 kaçırılan fırsat**", md["md_liste"])
        self.assertIn("1 veri şüphesi nedeniyle dışarıda", md["md_liste"])
        self.assertIn("| X | 2026-11-02 | 2026-11-05 | +9.0 | +0.0 | — | 4.5 | sürüyor | HABER_YOK |", md["md_liste"])
        self.assertIn("karar anından SONRA gelen haberle", md["md_neden"])
        self.assertIn("onayınız olmadan hiçbir ayar değişmez", md["md_neden"])
        self.assertIn("2026-11-03", md["md_liste"])          # 3–6 Kasım bekçi kaydı yok → yazılır

    def test_no_runs(self):
        self.conn.execute("DROP TRIGGER watch_runs_no_delete")   # yalnız bu test için boş geçmiş
        self.conn.execute("DROP TRIGGER signal_log_no_delete")
        self.conn.execute("DELETE FROM signal_log")
        self.conn.execute("DELETE FROM watch_runs")
        md = missed.report_md(self.scan())
        self.assertIn("Değerlendirilecek karar günü yok", md["md_liste"])


class AsOfTests(unittest.TestCase):
    def test_technical_for_ticker_ignores_future_prices(self):
        from bist_haber import technical
        with tempfile.TemporaryDirectory() as d:
            c = db.connect(Path(d) / "a.db")
            days = list(tdays(date(2026, 8, 1), date(2026, 11, 6)))
            for i, x in enumerate(days):
                v = 100 + (50 if x > "2026-10-20" else 0)          # 20 Ekim sonrası sıçrama
                c.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES('A',?,?,?,?,?,1e6)",
                          (x, v, v, v, v))
            t = technical.for_ticker(c, "A", date(2026, 10, 20))
            self.assertEqual((t["tarih"], t["son_fiyat"]), ("2026-10-20", 100))
            c.close()


if __name__ == "__main__":
    unittest.main()
