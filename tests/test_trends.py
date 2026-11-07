"""W5: gelişim takibi ve onay bekleyen öneriler (yeterli örnek + anlamlı fark; ayar kendiliğinden değişmez)."""
import json
import math
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, trends

TODAY = date(2026, 11, 20)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)

    def stats(self, code, n, k, days=10):
        for i in range(days):
            d = (date(2026, 10, 1) + timedelta(days=i)).isoformat()
            self.conn.execute("INSERT INTO missed_day_stats VALUES(?,?,1,?,?)",
                              (d, code, n // days + (1 if i < n % days else 0), k // days + (1 if i < k % days else 0)))
        self.conn.commit()

    def trade(self, i, senaryo, r, net, source=None, ticker=None):
        t = ticker or f"T{i}"
        res = {"durum": "kapandı", "sonuc": "SL" if net < 0 else "TP2", "net_getiri_pct": net, "r": r,
               "cikis_gunu": (date(2026, 9, 1) + timedelta(days=i)).isoformat()}
        self.conn.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,"
                          "gecerlilik,durum,sonuc_json,risk_seviyesi) VALUES('x','2026-08-30',?,'otomatik',?,100,95,"
                          "104,110,5,'kapandı',?,'orta')", (t, senaryo, json.dumps(res)))
        if source:
            nid = f"n{i}"
            self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,candidates,status,fetched_at)"
                              " VALUES(?,?,'2026-08-29T10:00:00+03:00','2026-08-29','b',?,'analyzed','f')",
                              (nid, source, t))
            self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,"
                              "reason,published_at,effective_date) VALUES(?,?,1,3,0.9,'orta','diger','r',"
                              "'2026-08-29T10:00:00+03:00','2026-08-29')", (nid, t))


class FilterRuleTests(Base):
    def test_significant_filter_is_suggested(self):
        self.stats("SENARYO_UYGUN_DEGIL", 300, 30)     # %10
        self.stats("HABER_YOK", 3000, 60)              # %2
        fr = trends.filter_rates(self.conn)
        top = fr["satirlar"][0]
        self.assertEqual((top["neden"], top["degerlendirilen"], top["kacirilan"]), ("SENARYO_UYGUN_DEGIL", 300, 30))
        self.assertAlmostEqual(top["oran_%"], 10.0)
        self.assertAlmostEqual(top["digerleri_%"], 2.0)
        # elle: p=90/3300; se=sqrt(p(1-p)(1/300+1/3000)); z=(0,10−0,02)/se
        p = 90 / 3300
        z = 0.08 / math.sqrt(p * (1 - p) * (1 / 300 + 1 / 3000))
        self.assertAlmostEqual(top["z"], z, places=6)
        keys = [s["anahtar"] for s in trends.generate(self.conn, TODAY)]
        self.assertIn("filtre:SENARYO_UYGUN_DEGIL", keys)
        self.assertNotIn("filtre:HABER_YOK", keys)                          # haber yok bir filtre değil

    def test_small_or_insignificant_not_suggested(self):
        self.stats("SENARYO_UYGUN_DEGIL", 150, 15)     # n < 200
        self.stats("SKOR_ESIK_ALTI", 400, 9)           # k < 10
        self.stats("HABER_ONEMSIZ", 1000, 30)          # %3 — diğerlerinden anlamlı yüksek değil
        self.stats("HABER_YOK", 3000, 60)
        self.assertEqual(trends.generate(self.conn, TODAY), [])

    def test_missed_scan_writes_day_stats(self):
        # test_missed senaryosu: tamamlanan pencerede neden başına değerlendirilen/kaçırılan sayıları kaydedilir
        from tests.test_missed import MissedTests
        t = MissedTests("test_completed_window_is_stored_once_and_immutable")
        t.setUp()
        try:
            t.test_completed_window_is_stored_once_and_immutable()
            rows = {r["neden_kodu"]: (r["degerlendirilen"], r["kacirilan"])
                    for r in t.conn.execute("SELECT * FROM missed_day_stats")}
            self.assertEqual(rows, {"HABER_YOK": (4, 3), "ONERILDI": (2, 1), "SENARYO_UYGUN_DEGIL": (1, 1)})
            with self.assertRaises(sqlite3.DatabaseError):
                t.conn.execute("UPDATE missed_day_stats SET kacirilan=0")
        finally:
            t.doCleanups()


class StrategyRuleTests(Base):
    def test_losing_strategy_with_enough_trades(self):
        for i in range(30):
            self.trade(i, "kirilim", -0.5 + (0.1 if i % 2 else -0.1), -1.0)
        for i in range(30, 40):
            self.trade(i, "destek", 1.0, 2.0)
        st = {r["grup"]: r for r in trends.strategy_stats(self.conn)["senaryo"]}
        self.assertEqual(st["kirilim"]["n"], 30)
        self.assertAlmostEqual(st["kirilim"]["ort_R"], -0.5)
        self.assertFalse(st["destek"]["yeterli"])
        keys = [s["anahtar"] for s in trends.generate(self.conn, TODAY)]
        self.assertEqual(keys, ["senaryo:kirilim:zayif"])                  # destek: 10 işlem → öneri yok

    def test_29_trades_not_enough(self):
        for i in range(29):
            self.trade(i, "kirilim", -0.5 + (0.1 if i % 2 else -0.1), -1.0)
        self.assertEqual(trends.generate(self.conn, TODAY), [])

    def test_source_grouping(self):
        self.trade(1, "destek", 1.0, 2.0, source="kap")
        self.trade(2, "destek", -1.0, -1.0, source="rss:bloomberght")
        self.trade(3, "destek", -1.0, -1.0)
        g = {r["grup"]: r["n"] for r in trends.strategy_stats(self.conn)["kaynak_haber"]}
        self.assertEqual(g, {"KAP": 1, "BloombergHT": 1, "bilinmiyor": 1})

    def test_performance_comparison(self):
        for i in range(60):
            self.trade(i, "destek", -1.0 if i < 30 else 1.0, -1.0 if i < 30 else 1.0)
        p = trends.performance(self.conn)
        self.assertEqual((p["karsilastirma"]["onceki"]["ort_R"], p["karsilastirma"]["son"]["ort_R"]), (-1.0, 1.0))
        self.assertTrue(p["haftalik"])


class CoverageAndSyncTests(Base):
    def runs(self, shares):
        for i, sh in enumerate(shares):
            n = {"HABER_ANALIZ_BEKLIYOR": int(sh * 100), "HABER_YOK": 100 - int(sh * 100)}
            self.conn.execute("INSERT INTO watch_runs(kind,day,started_at,summary_json) VALUES('aksam',?,?,?)",
                              (f"2026-11-{i + 1:02d}", f"2026-11-{i + 1:02d}T19:00:00+03:00",
                               json.dumps({"nedenler": n})))
        self.conn.commit()

    def test_coverage_rule(self):
        self.runs([0.4] * 6 + [0.1] * 4)
        self.assertEqual([s["anahtar"] for s in trends.generate(self.conn, TODAY)], ["kapsam:analiz_bekleyen"])

    def test_coverage_rule_needs_5_of_10(self):
        self.runs([0.4] * 4 + [0.1] * 6)
        self.assertEqual(trends.generate(self.conn, TODAY), [])

    def test_sync_dedupe_decide_once_and_resuggest_after_30_days(self):
        self.runs([0.4] * 10)
        r1 = trends.sync(self.conn, TODAY)
        self.assertEqual(len(r1["eklenen"]), 1)
        self.assertEqual(trends.sync(self.conn, TODAY)["eklenen"], [])     # bekliyor → tekrar eklenmez
        sid = r1["eklenen"][0]
        self.assertTrue(trends.decide(self.conn, sid, "reddedildi", "şimdilik maliyet istemiyorum"))
        self.assertFalse(trends.decide(self.conn, sid, "onaylandı"))       # karar bir kez
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE suggestions SET metin='x' WHERE id=?", (sid,))
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM suggestions")
        self.conn.rollback()
        self.assertEqual(trends.sync(self.conn, TODAY)["eklenen"], [])     # 30 gün dolmadı
        with patch.object(trends, "datetime") as dt:                       # karar 31 gün önce verilmiş gibi
            dt.now.return_value.isoformat.return_value = "2026-12-25T10:00:00+03:00"
            r = trends.sync(self.conn, date(2026, 12, 25))
        self.assertEqual(len(r["eklenen"]), 1)
        d = trends.decided(self.conn)[0]
        self.assertEqual((d["durum"], d["karar_notu"]), ("reddedildi", "şimdilik maliyet istemiyorum"))

    def test_decisions_never_touch_settings(self):
        from bist_haber import pipeline
        f = config.DATA / "ayarlar.json"
        p_ = patch.object(pipeline, "SETTINGS_FILE", f)   # yol modül yüklenirken sabitlenir: gerçek dosyaya yazılmasın
        p_.start()
        self.addCleanup(p_.stop)
        pipeline.save_settings(analiz_kalitesi="yuksek")
        before = f.read_text(encoding="utf-8")
        self.runs([0.4] * 10)
        sid = trends.sync(self.conn, TODAY)["eklenen"][0]
        trends.decide(self.conn, sid, "onaylandı")
        self.assertEqual((config.DATA / "ayarlar.json").read_text(encoding="utf-8"), before)

    def test_bad_decision_rejected(self):
        with self.assertRaises(ValueError):
            trends.decide(self.conn, 1, "uygula")

    def test_summary_md(self):
        self.runs([0.4] * 10)
        trends.sync(self.conn, TODAY)
        s = trends.summary_md(self.conn, TODAY)
        self.assertIn("Henüz kapanmış sanal işlem yok", s)
        self.assertIn("Onayınızı bekleyen öneri: **1**", s)


class PanelTrendTabTests(unittest.TestCase):
    def test_approve_from_panel(self):
        import os
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as t, patch.object(config, "DATA", Path(t)), \
                patch.object(config, "DB_PATH", Path(t) / "live.db"), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "", "HALLEY_OFFLINE": "1"}):
            conn = db.connect()
            conn.execute("INSERT INTO companies VALUES('POS','POS A.Ş.',NULL)")
            conn.execute("INSERT INTO suggestions(anahtar,tur,baslik,metin,kanit_json,nerede,olusturma) VALUES("
                         "'k','ayar','Deneme önerisi','Metin','{}','Ayarlar','2026-11-07T19:00:00+03:00')")
            conn.commit()
            conn.close()
            at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            at.run(timeout=60)
            self.assertEqual(len(at.exception), 0, str(at.exception))
            self.assertTrue(any("Deneme önerisi" in m.value for m in at.markdown))
            at.button(key="sug_ok_1").click().run(timeout=60)
            self.assertEqual(len(at.exception), 0, str(at.exception))
            c = db.connect()
            self.assertEqual(c.execute("SELECT durum FROM suggestions").fetchone()[0], "onaylandı")
            c.close()


if __name__ == "__main__":
    unittest.main()
