"""Üç giriş senaryosu (kırılım / geri çekilme / destekten tepki) kural testleri — elle hesaplanmış beklenen değerler."""
import unittest

from bist_haber import entries, tradeplan


def base(**kw):
    t = {"son_fiyat": 100.0, "atr": 2.0, "atr_%": 2.0, "direnc_20g": 103.0, "direnc_60g": 108.0, "zirve_52h": 115.0,
         "destek_20g": 97.0, "destek_60g": 90.0, "ema20": 99.0, "ema50": 96.0, "ema200": 90.0, "salinim_dibi": 96.5,
         "adx": 30.0, "trend": "Yükseliş", "rsi14": 55.0, "bb_sikisma": False, "obv_egilim": "artıyor",
         "veri_uyarilari": [], "veri_kritik": False, "gun_sayisi": 252, "macd_hist": 0.1, "fiyat_sma50_%": 4.0,
         "hacim_orani": 1.0, "son_gun_kilitli": False, "dip_52h": 80.0, "destek_60g_": None}
    t.update(kw)
    return t


class BreakoutTests(unittest.TestCase):
    def test_levels_from_nearest_resistance(self):
        s = entries.breakout(base())
        self.assertAlmostEqual(s["giris"], 103.4)          # direnç 103 + 0,2 ATR
        self.assertAlmostEqual(s["sl"], 101.0)             # direnç − 1 ATR
        self.assertEqual((s["tp1"], s["tp2"]), (108.0, 115.0))
        self.assertAlmostEqual(s["rr1"], (108 - 103.4) / 2.4)
        self.assertEqual(s["kalite"], "zayıf")
        self.assertIn("Fiyat alarmı: 103.00 TL üstü", s["emir"])
        self.assertIn("Günlük kapanış 103.00 TL", s["teyit"])

    def test_far_resistance_is_not_applicable(self):
        s = entries.breakout(base(direnc_20g=110.0, direnc_60g=112.0))
        self.assertIn("uzak", s["uygulanamaz"])

    def test_price_above_all_levels(self):
        s = entries.breakout(base(direnc_20g=99.0, direnc_60g=95.0, zirve_52h=100.2))
        self.assertIn("zaten", s["uygulanamaz"])

    def test_weak_adx_and_falling_obv_are_noted(self):
        s = entries.breakout(base(adx=15.0, obv_egilim="azalıyor"))
        self.assertTrue(any("ADX 15" in n for n in s["notlar"]))
        self.assertTrue(any("OBV" in n for n in s["notlar"]))

    def test_no_resistance_above_target_uses_risk_multiples(self):
        s = entries.breakout(base(direnc_60g=103.0, zirve_52h=103.0))
        self.assertAlmostEqual(s["tp1"], 103.4 + 2 * 2.4)
        self.assertAlmostEqual(s["tp2"], 103.4 + 3 * 2.4)


    def test_level_beyond_10_atr_is_not_a_target(self):
        s = entries.breakout(base(zirve_52h=150.0))      # 150 > 103,4 + 10×2 = 123,4
        self.assertEqual(s["tp1"], 108.0)
        self.assertAlmostEqual(s["tp2"], 103.4 + 3 * 2.4)  # risk katına döner
        self.assertTrue(any("52 haftalık zirve (150.00 TL" in n and "uzak" in n for n in s["notlar"]))

class PullbackTests(unittest.TestCase):
    def test_limit_at_ema20_with_swing_low_stop(self):
        s = entries.pullback(base())
        self.assertAlmostEqual(s["giris"], 99.0)
        self.assertAlmostEqual(s["sl"], 96.5 - 0.4)        # salınım dibi − 0,2 ATR
        self.assertEqual((s["tp1"], s["tp2"]), (103.0, 108.0))
        self.assertIn("Limit emir: 99.00 TL", s["emir"])
        self.assertIn("50 EMA (96.00 TL)", s["gecersiz"])

    def test_requires_uptrend(self):
        self.assertIn("Yükseliş trendi yok", entries.pullback(base(ema20=95.0))["uygulanamaz"])
        self.assertIn("Yükseliş trendi yok", entries.pullback(base(son_fiyat=95.0))["uygulanamaz"])

    def test_price_already_in_zone_uses_current_price(self):
        s = entries.pullback(base(son_fiyat=99.4))
        self.assertAlmostEqual(s["giris"], 99.4)

    def test_swing_low_too_far_uses_atr_stop(self):
        s = entries.pullback(base(salinim_dibi=80.0))
        self.assertAlmostEqual(s["sl"], 99.0 - 3.0)


class BounceTests(unittest.TestCase):
    def test_limit_above_support_and_poor_rr_is_unfavourable(self):
        s = entries.bounce(base())
        self.assertAlmostEqual(s["giris"], 97.5)           # destek 97 + 0,25 ATR
        self.assertAlmostEqual(s["sl"], 95.5)              # destek − 0,75 ATR
        self.assertEqual(s["tp1"], 99.0)                   # 20 EMA ilk hedef
        self.assertEqual(s["kalite"], "elverişsiz")        # 1,5 / 2 = 0,75 < 1

    def test_far_support_not_applicable(self):
        self.assertIn("uzak", entries.bounce(base(destek_20g=90.0, destek_60g=85.0))["uygulanamaz"])

    def test_downtrend_note(self):
        s = entries.bounce(base(trend="Düşüş"))
        self.assertTrue(any("düşen bıçağı" in n for n in s["notlar"]))

    def test_limit_never_above_current_price(self):
        s = entries.bounce(base(son_fiyat=97.2))
        self.assertAlmostEqual(s["giris"], 97.2)


class SelectionTests(unittest.TestCase):
    def test_best_is_highest_tp1_reward_risk(self):
        res = entries.scenarios(base())
        self.assertEqual(res["en_uygun"], "kirilim")        # 1,92 > geri çekilme 1,38; destek elverişsiz
        self.assertEqual([s["tur"] for s in res["senaryolar"]], ["kirilim", "geri_cekilme", "destek"])

    def test_wide_stop_is_unfavourable(self):
        s = entries.pullback(base(atr=12.0, salinim_dibi=None))   # SL 18 TL aşağıda → %18 > %15
        self.assertEqual(s["kalite"], "elverişsiz")

    def test_no_atr_no_scenarios(self):
        res = entries.scenarios(base(atr=None))
        self.assertEqual(res["senaryolar"], [])
        self.assertIsNone(res["en_uygun"])

    def test_none_usable_explains_why(self):
        res = entries.scenarios(base(direnc_20g=130.0, direnc_60g=140.0, zirve_52h=150.0, ema20=95.0,
                                     destek_20g=80.0, destek_60g=75.0))
        self.assertIsNone(res["en_uygun"])
        self.assertIn("hiçbiri uygun değil", res["neden_yok"])

    def test_texts_have_positive_negative_and_expiry(self):
        s = entries.breakout(base())
        self.assertIn("TP1", s["olumlu"])
        self.assertIn("SL", s["olumsuz"])
        self.assertIn("10 işlem günü", s["iptal"])

    def test_plan_includes_entry_scenarios(self):
        p = tradeplan.plan(base(), {"score": 3, "direction": 1, "confidence": 0.8, "flags": "", "persistence": "orta"})
        self.assertEqual(p["girisler"]["en_uygun"], "kirilim")


if __name__ == "__main__":
    unittest.main()
