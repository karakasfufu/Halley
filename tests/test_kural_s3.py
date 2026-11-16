"""Ek H4 (16.11.2026, araştırma): stop altında açılışta yapay kârın giderilmesi — journal.evaluate kural "s3" ve
journal.giris_kosulu. Varsayılan "s2" (canlıdaki mevcut davranış) DEĞİŞMEDİ. Üç işlem türü ayrı:
  A) yeni öneri, henüz alınmamış → giris_kosulu: açılış ≤ SL ise girişsiz;
  B) önceden açık pozisyon, stopun altında açılış → açılıştan çıkış (+ genel kayma), stop fiyatından değil;
  C) kullanıcının kaydettiği gerçek alış SL'nin altında/eşit → kayıt korunur, s3'te satış alış fiyatından."""
import importlib.util
import random
import unittest
from pathlib import Path

from bist_haber import journal

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("portfoy", ROOT / "arastirma" / "asama6" / "portfoy.py")
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)

D = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]


def bar(d, o, h, l, c):
    return {"date": d, "open": o, "high": h, "low": l, "close": c}


def rec(fill, kaynak="gercek", senaryo="kirilim_teyitli", sl=95.0):
    return {"kaynak": kaynak, "gercek_giris_gunu": D[1], "gercek_giris_fiyati": fill, "signal_day": D[0],
            "senaryo": senaryo, "sl": sl, "tp1": 110.0, "tp2": 120.0, "giris": 100.0, "alarm": None, "gecerlilik": 1}


MALIYET = 0.20 + 0.10


class GirisKosulu(unittest.TestCase):
    def test_entry_condition_for_new_suggestion(self):
        self.assertIsNone(journal.giris_kosulu(100.0, 101.0, 95.0))              # stop üstü, azami altı
        self.assertEqual(journal.giris_kosulu(101.5, 101.0, 95.0), "açılış azami girişin üstünde")
        self.assertEqual(journal.giris_kosulu(95.0, 101.0, 95.0), "açılış stopun altında veya eşit")   # eşit
        self.assertEqual(journal.giris_kosulu(94.0, 101.0, 95.0), "açılış stopun altında veya eşit")   # altı
        self.assertEqual(journal.giris_kosulu(None, 101.0, 95.0), "açılış fiyatı yok")
        self.assertIsNone(journal.giris_kosulu(95.01, 101.0, 95.0))               # hemen üstü geçerli


class GerceklesmisAlis(unittest.TestCase):
    """Tür C: kaydedilmiş gerçek alış — silinmez, girişsiz sayılmaz; alış bilgisi korunur."""

    def test_s2_default_unchanged_shows_artificial_profit(self):
        """Mevcut davranışın belgesi: açılış 94 < SL 95 → satış 95'ten, net KÂR (yapay)."""
        bars = [bar(D[1], 94, 96, 93, 95)]
        r = journal.evaluate(rec(94.0), bars)                                    # varsayılan = s2
        self.assertEqual(r, journal.evaluate(rec(94.0), bars, kural="s2"))
        self.assertEqual(r["bacaklar"], [{"pay": 1.0, "fiyat": 95.0, "neden": "SL (alış günü)"}])
        self.assertGreater(r["net_getiri_pct"], 0)

    def test_s3_below_stop_no_artificial_profit(self):
        bars = [bar(D[1], 94, 96, 93, 95)]
        r = journal.evaluate(rec(94.0), bars, kural="s3")
        self.assertEqual(r["durum"], "kapandı")
        self.assertEqual((r["giris_gunu"], r["giris_fiyati"]), (D[1], 94.0))     # gerçek alış korunur
        self.assertEqual(r["bacaklar"], [{"pay": 1.0, "fiyat": 94.0, "neden": "SL (alış stopun altında)"}])
        self.assertEqual(r["sonuc"], "SL")
        self.assertTrue(r["acilis_sl_alti"])
        self.assertAlmostEqual(r["net_getiri_pct"], -MALIYET, places=6)          # yalnız maliyet
        self.assertLessEqual(r["net_getiri_pct"], 0)

    def test_s3_fill_equal_to_stop(self):
        r = journal.evaluate(rec(95.0), [bar(D[1], 95, 97, 94, 96)], kural="s3")
        self.assertEqual(r["bacaklar"][0]["fiyat"], 95.0)
        self.assertAlmostEqual(r["net_getiri_pct"], -MALIYET, places=6)

    def test_s3_fill_above_stop_identical_to_s2(self):
        """Stop üstü alış: alış günü stopa değerse SL fiyatından (gün içi sıra bilinmez, mevcut kural) — s2 ile aynı."""
        for bars in ([bar(D[1], 96, 97, 94, 95)],                               # alış günü stop görüldü
                     [bar(D[1], 100, 101, 99, 100), bar(D[2], 100, 111, 99, 110), bar(D[3], 110, 121, 109, 120)]):
            self.assertEqual(journal.evaluate(rec(bars[0]["open"]), bars, kural="s3"),
                             journal.evaluate(rec(bars[0]["open"]), bars, kural="s2"))

    def test_random_fills_above_stop_never_differ(self):
        rnd = random.Random(7)
        for _ in range(300):
            px, bars = 100.0, []
            for d in D[1:]:
                o = px * (1 + rnd.uniform(-0.06, 0.06))
                h, l = o * (1 + rnd.uniform(0, 0.05)), o * (1 - rnd.uniform(0, 0.05))
                c = rnd.uniform(l, h)
                bars.append(bar(d, round(o, 2), round(h, 2), round(l, 2), round(c, 2)))
                px = c
            fill = bars[0]["open"]
            a, b = journal.evaluate(rec(fill), bars, kural="s2"), journal.evaluate(rec(fill), bars, kural="s3")
            if fill > 95.0:
                self.assertEqual(a, b)
            elif a.get("durum") == "kapandı":                                     # stop altı/eşit: s3'te kâr yok
                self.assertLessEqual(b["net_getiri_pct"], 0)

    def test_unknown_rule_rejected(self):
        with self.assertRaises(ValueError):
            journal.evaluate(rec(100.0), [bar(D[1], 100, 101, 99, 100)], kural="s4")


class AcikPozisyonBoslugu(unittest.TestCase):
    """Tür B: önceden açık pozisyon stopun altında açılırsa açılıştan çıkar (s2 = s3); stop fiyatı gösterilmez."""

    def test_gap_below_stop_exits_at_open(self):
        bars = [bar(D[1], 100, 101, 99, 100), bar(D[2], 85, 86, 84, 85)]
        for k in ("s2", "s3"):
            r = journal.evaluate(rec(100.0), bars, kural=k)
            self.assertEqual(r["bacaklar"], [{"pay": 1.0, "fiyat": 85.0, "neden": "SL (açılışta boşluk)"}])
            self.assertAlmostEqual(r["net_getiri_pct"], -15.0 - MALIYET, places=6)
            self.assertLess(r["r"], -1.0)                                         # kayıp planlanan riskten büyük

    def test_open_equal_to_stop_exits_at_stop(self):
        r = journal.evaluate(rec(100.0), [bar(D[1], 100, 101, 99, 100), bar(D[2], 95, 96, 94, 95)], kural="s3")
        self.assertEqual(r["bacaklar"][0]["fiyat"], 95.0)

    def test_gap_below_breakeven_after_tp1(self):
        bars = [bar(D[1], 100, 101, 99, 100), bar(D[2], 100, 111, 99, 110), bar(D[3], 97, 98, 96, 97)]
        for k in ("s2", "s3"):
            r = journal.evaluate(rec(100.0), bars, kural=k)
            self.assertEqual([b["neden"] for b in r["bacaklar"]], ["TP1 (yarısı)", "başabaş stop (açılış)"])
            self.assertEqual(r["bacaklar"][1]["fiyat"], 97.0)                     # girişten (100) değil açılıştan


class LimitEmirDolumu(unittest.TestCase):
    """Limit emirli plan (otomatik/takip): açılış SL'nin altındaysa limit emir DOLAR (üst fiyat limiti SL altı alışı
    engellemez); s3'te hemen stop, satış dolum fiyatından."""

    def test_limit_fill_below_stop(self):
        r2 = journal.evaluate(rec(None, kaynak="takip", senaryo="geri_cekilme"), [bar(D[1], 94, 96, 93, 95)], kural="s2")
        r3 = journal.evaluate(rec(None, kaynak="takip", senaryo="geri_cekilme"), [bar(D[1], 94, 96, 93, 95)], kural="s3")
        self.assertEqual(r2["giris_fiyati"], 94.0)
        self.assertGreater(r2["net_getiri_pct"], 0)                               # s2: yapay kâr
        self.assertAlmostEqual(r3["net_getiri_pct"], -MALIYET, places=6)          # s3: yalnız maliyet


SEK = lambda tk: "Sanayi"


def plan(tk, gun, azami=102.0):
    return {"ticker": tk, "tarih": gun, "tur": "kirilim_teyitli", "risk": "orta", "teknik_skor": 7, "rr1": 2.0,
            "giris": 100.0, "sl": 95.0, "tp1": 110.0, "tp2": 120.0, "azami": azami, "trend": "Yükseliş"}


class PortfoyS3(unittest.TestCase):
    AYAR = {"baslangic_sermaye": 10000, "risk_pct": 1.0}

    def _bars(self, acilis):
        return {"AAA": [bar(D[0], 100, 100, 100, 100), bar(D[1], acilis, acilis + 2, acilis - 1, acilis + 1),
                        bar(D[2], 96, 97, 95.5, 96)]}

    def test_seen_open_below_stop_is_no_entry(self):
        """Açılışı görüp elle alım (planlanan giriş senaryosu): açılış ≤ SL → girişsiz; nakit ve eğri hiç değişmez."""
        for acilis in (94.0, 95.0):
            r = pf.simule([plan("AAA", D[0])], self._bars(acilis), D[:3], D[1], D[2],
                          dict(self.AYAR, kural="s3", stop_alti_girissiz=True), SEK)
            self.assertEqual(r["islemler"], [])
            self.assertEqual(r["acik_son"], [])
            self.assertEqual([x["neden"] for x in r["atlanan"]], ["açılış stopun altında veya eşit (girişsiz)"])
            self.assertTrue(all(e["ozsermaye"] == 10000 for e in r["egri"]))

    def test_preplaced_limit_below_stop_fills_and_stops_at_cost(self):
        """Açılış seansına azami limitli emir (alternatif): emir SL altında da dolar; s3 → zarar = maliyet, kâr yok."""
        r = pf.simule([plan("AAA", D[0])], self._bars(94.0), D[:3], D[1], D[2],
                      dict(self.AYAR, kural="s3", adet_temeli="azami_giris"), SEK)
        t = r["islemler"][0]
        self.assertTrue(t["acilis_sl_alti"])
        self.assertEqual(t["cikis_gunu"], D[1])
        self.assertAlmostEqual(t["net_tl"], -t["adet"] * 94.0 * MALIYET / 100, places=2)
        r2 = pf.simule([plan("AAA", D[0])], self._bars(94.0), D[:3], D[1], D[2],
                       dict(self.AYAR, kural="s2", adet_temeli="azami_giris"), SEK)
        self.assertGreater(r2["islemler"][0]["net_tl"], 0)                        # eski: yapay kâr

    def test_above_stop_open_unaffected(self):
        a = pf.simule([plan("AAA", D[0])], self._bars(100.0), D[:3], D[1], D[2], self.AYAR, SEK)
        b = pf.simule([plan("AAA", D[0])], self._bars(100.0), D[:3], D[1], D[2],
                      dict(self.AYAR, kural="s3", stop_alti_girissiz=True), SEK)
        self.assertEqual(a["islemler"], b["islemler"])
        self.assertEqual(a["egri"], b["egri"])


if __name__ == "__main__":
    unittest.main()
