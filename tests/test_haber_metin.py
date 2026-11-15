"""Aşama 6 / haber 2. aşama (2026-11-15): KAP metnini yapay zekâsız okuma."""
import math
import unittest

from bist_haber import haber_metin as hm

TXT = ("Özel Durum Açıklaması (Genel)\nYapılan Açıklama Güncelleme mi?\nHayır (No)\nAçıklamalar\nExplanations\n"
       "Şirketimiz ile X A.Ş. arasında 12,5 milyon ABD Doları tutarında sözleşme imzalanmıştır. Ayrıca 3.400.000 TL "
       "tutarlı ihaleyi kazandık.\nOur company signed a contract.")


class Rules(unittest.TestCase):
    def test_amounts_with_rates_and_turkish_numbers(self):
        a = hm.amounts_tl(hm.clean(TXT), usd=40.0, eur=45.0)
        self.assertIn(500_000_000.0, a)
        self.assertIn(3_400_000.0, a)
        self.assertEqual(hm.amounts_tl("usd 2 milyon", usd=40.0), [80_000_000.0])
        self.assertEqual(hm.amounts_tl("5 milyon avro"), [])              # kur yoksa çevrilmez

    def test_rule_features(self):
        f = hm.rule_features([TXT], turnover_tl=5e7, usd=40.0, eur=45.0)
        self.assertEqual((f["m_var"], f["m_guncelleme"]), (1.0, 0.0))
        self.assertAlmostEqual(f["m_pos"], math.log1p(2))               # sözleşme imzala + ihaleyi kazan
        self.assertEqual(f["m_neg"], 0.0)
        self.assertAlmostEqual(f["m_tutar"], math.log10(1 + 500e6 / 5e7))
        neg = hm.rule_features(["Güncelleme mi?\nEvet\nAçıklamalar\nŞirket aleyhine dava açılmış, ihale iptal edildi."])
        self.assertEqual(neg["m_guncelleme"], 1.0)
        self.assertLess(neg["m_net"], 0)
        self.assertEqual(hm.rule_features(["Açıklamalar\nYeni ihaleyi kazanarak büyüdük"])["m_neg"], 0.0)  # "kazan" ≠ kaza
        self.assertEqual(hm.rule_features([])["m_var"], 0.0)

    def test_tokens_skip_translation_and_header(self):
        t = hm.tokens([TXT])
        self.assertIn("sözleşme", t)
        self.assertIn("sözleşme_imzalanmıştır", t)
        self.assertNotIn("explanations", t)
        self.assertNotIn("güncelleme", t)                                 # başlık kısmı alınmaz


if __name__ == "__main__":
    unittest.main()
