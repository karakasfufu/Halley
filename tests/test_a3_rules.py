"""Parça A3: haber fiyatlanmış mı, likidite filtresi ve "bugün fırsat yok" özeti."""
import unittest

from bist_haber import tradeplan

from test_entries import base

NEWS = {"score": 3, "direction": 1, "confidence": 0.8, "flags": "", "persistence": "orta"}


class PricedInTests(unittest.TestCase):
    def risks(self, move, **kw):
        return tradeplan.risk_factors(base(**kw), dict(NEWS, hareket=move))

    def test_big_move_after_news_is_flagged(self):
        r = self.risks({"sonra_%": 5.0, "sonra_atr": 2.5, "once_5g_%": 0.0})
        self.assertTrue(any(x.startswith("Haberden bu yana fiyat %5.0") for x in r))

    def test_small_move_after_news_is_not_flagged(self):
        r = self.risks({"sonra_%": 3.0, "sonra_atr": 1.5, "once_5g_%": 0.0})
        self.assertFalse(any("Haberden bu yana" in x for x in r))

    def test_drop_against_positive_news_is_flagged(self):  # gerçek örnek: SOKM bilanço sonrası −%9,8
        r = self.risks({"sonra_%": -9.8, "sonra_atr": -2.4, "once_5g_%": -2.6})
        self.assertTrue(any(x.startswith("Haber olumlu ama fiyat haberden bu yana %9.8 düştü") for x in r))
        self.assertFalse(any(x.startswith("Haber olumlu ama fiyat") for x in self.risks({"sonra_%": -2.0, "sonra_atr": -1.0})))

    def test_run_up_before_news_is_flagged_in_atr_units(self):
        self.assertTrue(any("önceki 5 işlem" in x for x in self.risks({"once_5g_%": 6.0})))      # 6 / 2 = 3 ATR
        self.assertFalse(any("önceki 5 işlem" in x for x in self.risks({"once_5g_%": 5.9})))

    def test_missing_measurements_are_not_guessed(self):
        r = self.risks({"once_5g_%": None, "sonra_%": None, "sonra_atr": None})
        self.assertFalse(any("Haberden" in x for x in r))
        self.assertEqual(r, tradeplan.risk_factors(base(), NEWS))

    def test_priced_in_raises_risk_weight(self):
        calm = tradeplan.plan(base(), NEWS)
        hot = tradeplan.plan(base(), dict(NEWS, hareket={"sonra_%": 6.0, "sonra_atr": 3.0}))
        self.assertEqual(len(hot["riskler"]), len(calm["riskler"]) + 1)
        self.assertEqual(hot["risk_seviyesi"], "yüksek")  # fiyatlanma 2 puan sayılır

    def test_priced_in_adds_two_risk_points(self):
        quiet = base(atr=4.0, **{"atr_%": 4.0})  # sakin ve r/g iyi olmayabilir; yalnız puan farkına bakılır
        calm = tradeplan.plan(quiet, NEWS)
        hot = tradeplan.plan(quiet, dict(NEWS, hareket={"sonra_%": 9.0, "sonra_atr": 2.2}))
        pts = lambda p: sum(4 if r.startswith("Risk/getiri elverişsiz") else 2 if r.startswith((
            "Haber olumlu ama teknik trend", "Risk/getiri zayıf", "Düşük likidite", "Haberden bu yana")) else 1
            for r in p["riskler"])
        self.assertEqual(pts(hot) - pts(calm), 2)


class LiquidityTests(unittest.TestCase):
    def test_very_low_liquidity_blocks_scenario(self):
        p = tradeplan.plan(base(islem_hacmi_tl=1.5e6), NEWS)
        self.assertEqual(p["durum"], "yok")
        self.assertIn("Likidite çok düşük", p["neden_yok"])

    def test_low_liquidity_warns(self):
        p = tradeplan.plan(base(islem_hacmi_tl=5e6), NEWS)
        self.assertEqual(p["durum"], "senaryo")
        self.assertTrue(any(x.startswith("Düşük likidite: günlük ortalama işlem hacmi 5.0") for x in p["riskler"]))

    def test_normal_or_unknown_liquidity_no_warning(self):
        for v in (50e6, None):  # bilinmiyorsa (ör. pilot barlarında hacim yok) uyarı uydurulmaz
            p = tradeplan.plan(base(islem_hacmi_tl=v), NEWS)
            self.assertFalse(any("likidite" in x.lower() for x in p["riskler"]), v)


class OpportunitySummaryTests(unittest.TestCase):
    def test_lists_usable_and_counts_reasons(self):
        plans = {"AAA": tradeplan.plan(base(), NEWS),
                 "BBB": tradeplan.plan(base(islem_hacmi_tl=1e6), NEWS),
                 "CCC": tradeplan.plan(base(), dict(NEWS, score=1.0)),
                 "DDD": tradeplan.plan(base(direnc_20g=130.0, direnc_60g=140.0, zirve_52h=150.0, ema20=95.0,
                                            destek_20g=80.0, destek_60g=75.0), NEWS)}
        s = tradeplan.opportunity_summary(plans)
        self.assertEqual([x[0] for x in s["uygun"]], ["AAA"])
        self.assertEqual(s["nedenler"], {"likidite çok düşük": 1, "haber sinyali yeterince güçlü değil": 1,
                                         "giriş senaryoları uygun değil (risk/getiri elverişsiz ya da koşul yok)": 1})

    def test_empty(self):
        self.assertEqual(tradeplan.opportunity_summary({}), {"uygun": [], "nedenler": {}})


if __name__ == "__main__":
    unittest.main()


class ReviewFixTests(unittest.TestCase):
    """Son kontrol (2026-11-07) düzeltmeleri."""

    def test_scenario_risk_does_not_use_reference_plans_reward_risk(self):
        p = tradeplan.plan(base(), NEWS)
        self.assertTrue(p["elverissiz"])                       # mevcut fiyattan: TP 103, SL ~96 → 1:0,75
        self.assertEqual(p["risk_seviyesi"], "yüksek")
        brk = next(s for s in p["girisler"]["senaryolar"] if s["tur"] == "kirilim")
        self.assertEqual(brk["kalite"], "zayıf")
        self.assertEqual(brk["risk_seviyesi"], "orta")          # ortak risk 0 + zayıf r/g 2
        self.assertEqual(tradeplan.opportunity_summary({"AAA": p})["uygun"][0][2], "orta")

    def test_common_risks_raise_every_scenario(self):
        p = tradeplan.plan(base(islem_hacmi_tl=5e6), NEWS)     # düşük likidite: 2 puan
        brk = next(s for s in p["girisler"]["senaryolar"] if s["tur"] == "kirilim")
        self.assertEqual(brk["risk_seviyesi"], "yüksek")        # 2 + 2

    def test_partial_last_bar_is_warned(self):
        from bist_haber import technical as T
        from test_indicators_v2 import series
        bars = series(60)
        bars[-1] = dict(bars[-1], open=None, high=None, low=None)
        from datetime import date
        today = date.fromisoformat(bars[-1]["date"])           # deneme serisi eski tarihli: "bugün" = son gün
        t = T.analyze(bars, today=today)
        self.assertTrue(any("yarım veri" in w for w in t["veri_uyarilari"]))
        self.assertFalse(t["veri_kritik"])                      # uyarı; senaryoyu engellemez
        self.assertFalse(any("yarım veri" in w for w in T.analyze(series(60), today=today)["veri_uyarilari"]))

    def test_partial_bar_warning_does_not_add_risk_points(self):
        w = "Son günün (2026-11-06) açılış/en yüksek/en düşük fiyatı eksik (gün içi yarım veri): ..."
        self.assertEqual(tradeplan._points([w]), 0)
        self.assertEqual(tradeplan._points([w, "MACD ivmesi zayıf"]), 1)
