"""Aşama 4 (2026-11-14): genel fırsat puanı (yalnız bilgi), yalnız teknik fırsatlar (ayrı kayıt ve ölçüm),
haftalık rapor (YZ'siz, arşiv + otomatik üretim). Ağa çıkılmaz."""
import json
import unittest
from datetime import date
from unittest.mock import patch

from bist_haber import ready, watchdog, weekly
from tests.test_ready import D0, D1, Base, Ctx, at, plan, row, tech


class TCtx(Ctx):
    today = date(2026, 11, 6)

    def corp(self, tk):
        return {"yaklasan": []}

    def earning(self, tk):
        return {}

    def macro_risk(self):
        return None


def tctx(techs, plans=None):
    return TCtx(techs, plans or {})


class Score(unittest.TestCase):
    def test_overall_score_parts_and_tech_only_has_no_news_points(self):
        g = ready.overall_score(2.5, 10, 2.5, "düşük")
        self.assertEqual(g["parca"], {"haber": 15.0, "teknik": 30.0, "risk_getiri": 12.5, "risk": 20.0})
        self.assertEqual(g["puan"], 78)
        t = ready.overall_score(None, 10, 9, "düşük", "teknik")
        self.assertEqual((t["parca"]["haber"], t["puan"]), (0.0, 70))          # haber yok → en fazla 70
        self.assertEqual(ready.overall_score(9, 12, 9, "yüksek")["puan"], 80)  # sınırlar kırpılır
        self.assertIn("sınanmadı", ready.score_text(g))


class TechOnly(Base):
    def breakout(self, tk="BRK"):
        self.flat(tk, end="2026-11-05")
        self.bar(tk, D0, 100.5, 104, 100.4, 103.5)
        self.conn.commit()
        return tech(son_fiyat=103.5, direnc_20g=104, direnc_60g=115.0)

    def patches(self):
        for p in (patch("bist_haber.earnings.window_risk", return_value=None),
                  patch("bist_haber.corp_events.risk_lines", return_value=[])):
            p.start()
            self.addCleanup(p.stop)

    def test_build_tech_rules(self):
        self.patches()
        t = self.breakout()
        b = ready.build_tech(self.conn, tctx({"BRK": t}), "BRK", "Brk A.Ş.")
        p = b["plan"]
        self.assertEqual((p["kaynak"], p["tur"], p["haber_skoru"]), ("teknik", "kirilim_teyitli", None))
        self.assertLessEqual(p["genel_puan"], 70)
        self.assertIn("Haber yok", p["neden"])
        self.assertIn("trend", ready.build_tech(self.conn, tctx({"BRK": dict(t, trend="Yatay")}), "BRK")["neden"])
        weak = dict(t, macd_hist=-1, obv_egilim="azalıyor", hacim_orani=0.9, **{"rs_20g_%": -1})   # 10 → 6
        self.assertIn("en az 7", ready.build_tech(self.conn, tctx({"BRK": weak}), "BRK")["neden"])
        self.assertIn("Likidite", ready.build_tech(self.conn, tctx({"BRK": dict(t, islem_hacmi_tl=5e5)}), "BRK")["neden"])

    def test_select_tech_skips_news_tickers_and_evening_morning_store_separately(self):
        self.patches()
        t = self.breakout("BRK")
        self.breakout("POS")
        self.breakout("NEG")
        ctx = tctx({"BRK": t, "POS": t, "NEG": t, "AAA": tech()},
                   {"AAA": plan(), "POS": plan(durum="yok", neden_yok="başka neden")})
        uni = {"BRK": "Brk", "POS": "Pos", "NEG": "Neg", "AAA": "Aaa"}
        rows = [row("AAA"), row("POS", 2.0), row("NEG", -1.0)]
        sel = ready.select_tech(self.conn, ctx, rows, uni)
        self.assertEqual([p["ticker"] for p in sel["secilen"]], ["BRK"])       # haberliler ve olumsuzlar hariç
        res = ready.evening(self.conn, ctx, rows, at(D0, 19), universe=uni)
        kay = {r["ticker"]: (r["kaynak"], r["genel_puan"]) for r in ready.rows_for(self.conn)}
        self.assertEqual(kay["BRK"][0], "teknik")
        self.assertEqual(kay["AAA"][0], "haber")
        self.assertIsNotNone(kay["AAA"][1])
        md = ready.report_md(res)
        self.assertIn("📐 Yalnız teknik", md)
        self.assertIn("BRK", md.split("📐")[1])
        self.assertIn("Yalnız teknik", ready.telegram_text(res, "aksam"))
        m = ready.morning(self.conn, ctx, rows, at(D1, 8, 45), universe=uni)
        st = {r["ticker"]: r["durum"] for r in ready.rows_for(self.conn)}
        self.assertEqual((st["BRK"], st["AAA"]), ("onaylandi", "onaylandi"))
        self.assertEqual([p["ticker"] for p in m["teknik"]["secilen"]], ["BRK"])
        self.assertEqual(ready.performance(self.conn, "teknik")["onerilen"], 1)
        self.assertEqual(ready.performance(self.conn, "haber")["onerilen"], 1)
        self.assertEqual(ready.performance(self.conn)["onerilen"], 2)

    def test_morning_cancels_tech_pick_after_negative_news(self):
        self.patches()
        t = self.breakout("BRK")
        ctx = tctx({"BRK": t})
        ready.evening(self.conn, ctx, [], at(D0, 19), universe={"BRK": "Brk"})
        ready.morning(self.conn, ctx, [row("BRK", -2.0)], at(D1, 8, 45), universe={"BRK": "Brk"})
        r = ready.rows_for(self.conn)[0]
        self.assertEqual(r["durum"], "iptal")


class Weekly(Base):
    def test_week_helpers(self):
        self.assertEqual(weekly.week_bounds(date(2026, 11, 12)), (date(2026, 11, 9), date(2026, 11, 13)))
        self.assertEqual(weekly.last_trading_day_of_week(date(2026, 11, 10)), date(2026, 11, 13))

    def test_build_and_archive(self):
        for d, c in (("2026-11-06", 100.0), ("2026-11-13", 103.0)):
            self.bar("XU100", d, c, c, c, c)
        self.conn.execute("INSERT INTO hazir_firsat(olusturuldu,analiz,signal_day,giris_gunu,ticker,tur,kapanis,giris,"
                          "giris_alt,azami_giris,sl,tp1,tp2,rr1,durum,kaynak,sonuc_json) VALUES('x','aksam','2026-11-06',"
                          "'2026-11-09','BRK','kirilim_teyitli',10,10,9.8,10.1,9,12,13,2,'kapandi','teknik',?)",
                          (json.dumps({"sonuc": "TP2", "net_getiri_pct": 12.0, "cikis_gunu": "2026-11-12"}),))
        self.conn.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,"
                          "gecerlilik,durum,sonuc_json) VALUES('x','2026-11-06','AAA','otomatik','kirilim',10,9,11,12,3,"
                          "'kapandı',?)", (json.dumps({"durum": "kapandı", "sonuc": "SL", "net_getiri_pct": -5.0,
                                                       "cikis_gunu": "2026-11-11", "r": -1.0, "islem_gunu": 2}),))
        self.conn.commit()
        md, data = weekly.build(self.conn, date(2026, 11, 13))
        self.assertIn("%+3.00", md)
        self.assertIn("| 2026-11-09 | BRK |", md)
        self.assertIn("BRK TP2", md)
        self.assertIn("| AAA | sanal | kirilim | SL |", md)
        self.assertEqual(data["hazir"]["teknik"]["onerilen"], 1)
        self.assertIn("yapay zekâ kullanılmadı", md)
        sent = []
        name = weekly.run(self.conn, date(2026, 11, 13), send=sent.append)
        self.assertEqual(name, "2026-11-13_haftalik")
        self.assertTrue((watchdog.report_dir() / f"{name}.md").exists())

    def test_tick_makes_weekly_once_after_friday_evening(self):
        calls = []
        runs = lambda kind: watchdog.archive("2026-11-13", kind, "x", {})
        wk = lambda d: calls.append(d) or "ok"
        ready.tick(self.conn, at("2026-11-13", 18, 30), run_fn=runs, weekly_fn=wk)
        ready.tick(self.conn, at("2026-11-13", 19, 0), run_fn=runs, weekly_fn=wk)
        self.assertEqual(calls, [date(2026, 11, 13)])
        calls.clear()
        ready.tick(self.conn, at("2026-11-12", 18, 30), run_fn=runs, weekly_fn=wk)   # perşembe: haftalık yok
        self.assertEqual(calls, [])

    def test_weekly_not_lost_when_friday_evening_missed(self):
        """Denetim: Cuma akşamı Halley kapalıydı; Cumartesi açılınca akşam analizi yapılmaz ama haftalık üretilir."""
        calls = []
        ready.tick(self.conn, at("2026-11-14", 12, 0), run_fn=lambda k: "x", weekly_fn=lambda d: calls.append(d))
        self.assertEqual(calls, [date(2026, 11, 13)])


if __name__ == "__main__":
    unittest.main()
