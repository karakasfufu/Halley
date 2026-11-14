"""Hazır Fırsatlar (2026-11-10): kural, eleme nedenleri, sınır (≤5, 0 olabilir), akşam kaydı, sabah iptali, açılış
kontrolü (azami giriş), gerçek sonuç ölçümü, otomatik zamanlama, yapay zekâ düğmesi varsayılan kapalı. Ağa çıkılmaz."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, pipeline, ready

TZ = config.TR_TZ
D0, D1, D2 = "2026-11-06", "2026-11-09", "2026-11-10"      # cuma, pazartesi, salı


def at(day, hh, mm=0):
    y, m, d = map(int, day.split("-"))
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def tech(**k):
    t = {"son_fiyat": 100.0, "atr": 2.0, "tarih": D0, "trend": "Yükseliş", "rsi14": 58, "macd_hist": 0.3, "adx": 25,
         "arti_di": 25, "eksi_di": 15, "hacim_orani": 1.3, "obv_egilim": "artıyor", "rs_20g_%": 3, "rs_60g_%": 4,
         "direnc_20g": 110.0, "direnc_60g": None, "zirve_52h": None}
    t.update(k)
    return t


def plan(**k):
    p = {"durum": "senaryo", "sl": 96.0, "sl_dayanak": "20 günlük desteğin hemen altı", "riskler": [],
         "girisler": {"senaryolar": [], "en_uygun": None}}
    p.update(k)
    return p


class Ctx:
    def __init__(self, techs, plans, news=None):
        self.techs, self.plans, self.news = techs, plans, news or {}

    def tech(self, tk):
        return self.techs.get(tk)

    def plan(self, r):
        return self.plans[r["ticker"]]

    def news_info(self, r):
        return self.news.get(r["ticker"], {"reason": "Büyük sözleşme imzaladı. İkinci cümle."})


def row(tk, score=2.5):
    return {"ticker": tk, "score": score, "name": tk + " A.Ş."}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        for p in (patch.object(config, "DATA", t), patch.object(pipeline, "SETTINGS_FILE", t / "ayarlar.json"),
                  patch.dict(os.environ, {"HALLEY_OFFLINE": "1", "TELEGRAM_BOT_TOKEN": "1:x", "TELEGRAM_CHAT_ID": "7"})):
            p.start()
            self.addCleanup(p.stop)
        self.conn = db.connect(t / "t.db")
        self.addCleanup(self.conn.close)

    def bar(self, tk, day, o, h, l, c, v=1e6):
        self.conn.execute("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                          (tk, day, o, h, l, c, v))

    def flat(self, tk, n=25, end=D0):
        from tests.test_signals import weekdays_back
        y, m, d = map(int, end.split("-"))
        from datetime import date
        for x in weekdays_back(date(y, m, d), n):
            self.bar(tk, x.isoformat(), 100, 101, 99, 100)


class RuleTests(Base):
    def test_tech_score_parts(self):
        self.assertEqual(ready.tech_score(tech())["skor"], 10)
        weak = ready.tech_score(tech(trend="Düşüş", rsi14=25, macd_hist=-1, adx=10, hacim_orani=0.5, obv_egilim="azalıyor",
                                     **{"rs_20g_%": -2, "rs_60g_%": -1}))
        self.assertEqual(weak["skor"], 0)

    def test_current_price_plan_selected_with_max_entry(self):
        b = ready.build(self.conn, Ctx({"AAA": tech()}, {"AAA": plan()}), row("AAA"))
        p = b["plan"]
        self.assertEqual((p["tur"], p["giris"], p["sl"], p["tp1"]), ("mevcut_fiyat", 100.0, 96.0, 110.0))
        self.assertAlmostEqual(p["rr1"], 2.5)
        self.assertAlmostEqual(p["azami_giris"], 100.6)              # giriş + 0,3 ATR
        self.assertLessEqual(p["azami_giris"], (p["tp1"] + 1.5 * p["sl"]) / 2.5 + 1e-9)   # azamide r/g ≥ 1:1,5
        self.assertTrue(p["neden"].startswith("Haber: Büyük sözleşme imzaladı"))
        self.assertNotIn("İkinci cümle", p["neden"])

    def test_rejections_have_reasons(self):
        c = Ctx({"A": tech(), "B": tech(trend="Düşüş", rsi14=25, macd_hist=-1, hacim_orani=0.5, obv_egilim="azalıyor",
                                      **{"rs_20g_%": -1, "rs_60g_%": -1}), "C": tech(), "D": tech()},
                {"A": plan(sl=99.0), "B": plan(), "C": plan(riskler=["Haberden bu yana fiyat 2 ATR yükseldi"] * 4),
                 "D": plan(durum="yok", neden_yok="Likidite çok düşük")})
        a = ready.build(self.conn, Ctx({"A": tech(direnc_20g=101.2)}, {"A": plan()}), row("A"))   # r/g düşük
        self.assertIn("1:2", a["neden"])
        self.assertIn("teknik skor", ready.build(self.conn, c, row("B"))["neden"])
        self.assertIn("risk seviyesi yüksek", ready.build(self.conn, c, row("C"))["neden"])
        self.assertIn("Likidite", ready.build(self.conn, c, row("D"))["neden"])
        self.assertIn("1,50", ready.build(self.conn, c, row("A", 1.2))["neden"])

    def test_pending_support_far_away_is_not_ready(self):
        s = {"tur": "destek", "giris": 95.0, "sl": 93.0, "tp1": 100.0, "tp2": 104.0, "kalite": "iyi"}
        b = ready.build(self.conn, Ctx({"A": tech()}, {"A": plan(sl=None, girisler={"senaryolar": [s]})}), row("A"))
        self.assertIn("plan yok", b["neden"])                       # 2,5 ATR aşağıdaki destek hazır sayılmaz

    def test_confirmed_breakout_detected(self):
        self.flat("BRK", end="2026-11-05")
        self.bar("BRK", D0, 100.5, 104, 100.4, 103.5)                # 20 günlük zirve 101 üstünde yükselen kapanış
        t = tech(son_fiyat=103.5, direnc_20g=104, direnc_60g=115.0)
        cands = ready.candidates(self.conn, t, plan(sl=None, _ticker="BRK"))
        k = next(c for c in cands if c["tur"] == "kirilim_teyitli")
        self.assertAlmostEqual(k["sl"], 101 - 2.0)

    def test_select_caps_at_five_and_can_be_zero(self):
        techs = {f"T{i}": tech() for i in range(8)}
        plans = {f"T{i}": plan() for i in range(8)}
        sel = ready.select(self.conn, Ctx(techs, plans), [row(f"T{i}", 2 + i / 10) for i in range(8)])
        self.assertEqual(len(sel["secilen"]), 5)
        self.assertEqual(sel["secilen"][0]["ticker"], "T7")             # en yüksek haber skoru önce
        self.assertTrue(any("ilk 5" in v for v in sel["elenen"].values()))
        self.assertEqual(ready.select(self.conn, Ctx({}, {}), [row("X", 1.0)])["secilen"], [])


class LifecycleTests(Base):
    def setUp(self):
        super().setUp()
        self.ctx = Ctx({"AAA": tech(), "BBB": tech()}, {"AAA": plan(), "BBB": plan()})

    def test_evening_morning_opening_and_results(self):
        res = ready.evening(self.conn, self.ctx, [row("AAA"), row("BBB")], at(D0, 19))
        self.assertEqual(res["giris_gunu"], D1)                        # cuma akşamı → pazartesi açılış
        self.assertEqual([r["durum"] for r in ready.rows_for(self.conn, D1)], ["aday", "aday"])
        # gece BBB'ye olumsuz haber
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,fetched_at) "
                          "VALUES('k1','kap','2026-11-08T10:00:00+03:00','2026-11-09','BBB: dava','x','BBB','analyzed','f')")
        self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,reason,"
                          "published_at,effective_date) VALUES('k1','BBB',-1,4,0.9,'orta','dava','r','2026-11-08T10:00:00+03:00','2026-11-09')")
        self.conn.commit()
        calls = []
        m = ready.morning(self.conn, self.ctx, [row("AAA"), row("BBB")], at(D1, 8, 45), ai=False,
                          news_fn=lambda *a: calls.append(a))
        self.assertEqual(calls, [])                                    # yapay zekâ düğmesi kapalı → çağrı yok
        st = {r["ticker"]: r for r in ready.rows_for(self.conn, D1)}
        self.assertEqual(st["AAA"]["durum"], "onaylandi")
        self.assertEqual(st["BBB"]["durum"], "iptal")
        self.assertIn("olumsuz haber", st["BBB"]["iptal_nedeni"])
        self.assertIn("⛔ BBB iptal", ready.report_md(m))
        # açılış: AAA azami 100,6; açılış 101 → iptal
        q = {"AAA": {"zaman": at(D1, 10, 0), "acilis": 101.0}}
        o = ready.opening_check(self.conn, q, at(D1, 10, 15))
        self.assertEqual([x[0] for x in o["iptal"]], ["AAA"])
        aaa = next(r for r in ready.rows_for(self.conn, D1) if r["ticker"] == "AAA")
        self.assertIn("eski fiyattan alım önerilmez", aaa["iptal_nedeni"])
        self.assertEqual(aaa["durum"], "girissiz")                       # 2026-11-15: sabah iptali sayılmaz
        pf = ready.performance(self.conn)
        self.assertEqual((pf["girissiz"], pf["sabah_iptal"]), (1, 1))     # BBB olumsuz haberle sabah iptali

    def test_results_measured_from_open(self):
        ready.evening(self.conn, self.ctx, [row("AAA"), row("BBB")], at(D0, 19))
        self.flat("AAA")
        self.flat("BBB")
        self.bar("AAA", D1, 100.2, 104, 100, 103)       # açılış 100,2 ≤ azami → giriş
        self.bar("AAA", D2, 103, 115, 102.5, 114)       # TP1 110 görülür (yarısı), aynı gün TP2 sayılmaz
        self.bar("AAA", "2026-11-11", 114, 116, 113, 115)   # TP2 114
        self.bar("BBB", D1, 101.5, 102, 100, 101)       # açılış 101,5 > azami 100,6 → giriş yok
        ready.evaluate_all(self.conn)
        st = {r["ticker"]: r for r in ready.rows_for(self.conn, D1)}
        self.assertEqual(st["BBB"]["durum"], "girissiz")
        self.assertEqual(st["AAA"]["durum"], "kapandi")
        self.assertEqual(st["AAA"]["sonuc"]["sonuc"], "TP2")
        self.assertEqual(st["AAA"]["acilis"], 100.2)
        pf = ready.performance(self.conn)
        self.assertEqual((pf["onerilen"], pf["kapanan"], pf["girissiz"], pf["TP2 %"]), (2, 1, 1, 100.0))

    def test_stale_quote_no_decision(self):
        ready.evening(self.conn, self.ctx, [row("AAA")], at(D0, 19))
        o = ready.opening_check(self.conn, {"AAA": {"zaman": at(D0, 17), "acilis": 150}}, at(D1, 10, 15))
        self.assertEqual(o["veri_yok"], ["AAA"])
        self.assertEqual(ready.rows_for(self.conn, D1)[0]["durum"], "aday")

    def test_morning_ai_only_when_user_turned_it_on(self):
        ready.evening(self.conn, self.ctx, [row("AAA")], at(D0, 19))
        calls = []
        ready.morning(self.conn, self.ctx, [row("AAA")], at(D1, 8, 45), ai=True,
                      news_fn=lambda conn, tickers, since: calls.append(tickers) or {"analiz": {"analyzed": 0}})
        self.assertEqual(calls, [["AAA"]])                             # yalnız hazır listedeki hisseler


class TickTests(Base):
    def test_auto_runs_once_and_opening_alert(self):
        runs, sent = [], []
        run = lambda kind: runs.append(kind) or {}
        send = lambda t: sent.append(t) or {"ok": True}
        with patch("bist_haber.watchdog.list_reports", return_value=[]):
            ready.tick(self.conn, at(D1, 18, 45), run, None, send)            # kapanış sonrası → akşam
            ready.tick(self.conn, at(D1, 19, 30), run, None, send)            # aynı akşam tekrar yok
            ready.tick(self.conn, at(D2, 8, 40), run, None, send)             # sabah
            ready.tick(self.conn, at(D2, 9, 0), run, None, send)              # sabah tekrar yok
        self.assertEqual(runs, ["aksam", "sabah"])
        with patch("bist_haber.watchdog.list_reports", return_value=[f"{D2}_aksam"]):
            ready.tick(self.conn, at(D2, 18, 45), run, None, send)            # elle yapılmış → yinelenmez
        self.assertEqual(runs, ["aksam", "sabah"])
        # açılış kontrolü + Telegram
        ctx = Ctx({"AAA": tech(tarih=D2)}, {"AAA": plan()})
        ready.evening(self.conn, ctx, [row("AAA")], at(D2, 19))
        q = lambda tickers: {"AAA": {"zaman": at("2026-11-11", 10, 0), "acilis": 105.0}}
        with patch("bist_haber.watchdog.list_reports", return_value=["2026-11-11_sabah", "2026-11-10_aksam"]):
            out = ready.tick(self.conn, at("2026-11-11", 10, 10), run, q, send)
        self.assertEqual([x[0] for x in out["acilis"]["iptal"]], ["AAA"])
        self.assertIn("eski fiyattan ALMAYIN", sent[-1])

    def test_missed_evening_not_run_with_intraday_prices_and_late_morning_adds_nothing(self):
        runs = []
        with patch("bist_haber.watchdog.list_reports", return_value=[]):
            out = ready.tick(self.conn, at(D2, 11, 0), lambda k: runs.append(k), lambda t: {}, lambda t: {})
        self.assertNotIn("aksam", runs)                                # pazartesi akşamı kaçtı, salı 11:00 → yapılmaz
        self.assertIn("aksam_atlandi", out)
        ctx = Ctx({"AAA": tech(tarih=D1)}, {"AAA": plan()})
        m = ready.morning(self.conn, ctx, [row("AAA")], at(D2, 10, 30))   # açılıştan sonra sabah kontrolü
        self.assertTrue(m["gec"])
        self.assertEqual(ready.rows_for(self.conn, D2), [])               # geçmiş açılışa yeni öneri eklenmedi
        self.assertIn("açılıştan sonra yapıldı", ready.report_md(m))

    def test_offline_mode_starts_no_network_analysis(self):
        out = ready.tick(self.conn, at(D1, 18, 45))                       # HALLEY_OFFLINE=1, işlev verilmedi
        self.assertEqual(out, {})

    def test_weekend_no_runs(self):
        runs = []
        with patch("bist_haber.watchdog.list_reports", return_value=[]):
            ready.tick(self.conn, at(D0, 19), lambda k: runs.append(k), None, lambda t: {})
            runs.clear()
            ready.tick(self.conn, at("2026-11-08", 10, 30), lambda k: runs.append(k), None, lambda t: {})
        self.assertEqual(runs, [])


class SessionIntegration(unittest.TestCase):
    """Elle/otomatik sabah-akşam analizinin raporunda Hazır Fırsatlar bölümü var."""

    def setUp(self):
        from tests import test_watchdog_w2 as w2
        w2.SessionTests.setUp(self)

    def test_report_has_ready_section(self):
        from bist_haber import watchdog
        from tests.test_watchdog_w2 import at as wat, TODAY
        out = watchdog.run_session(self.conn, self.uni, "aksam", {}, now=wat(TODAY, 19), steps=self.steps)
        md = (watchdog.report_dir() / f"{out['rapor']}.md").read_text(encoding="utf-8")
        self.assertIn("## ✅ Hazır Fırsatlar", md)
        self.assertLess(md.index("✅ Hazır Fırsatlar"), md.index("## 1."))      # önce hazır fırsatlar
        self.assertIn("hazir", out)


if __name__ == "__main__":
    unittest.main()
