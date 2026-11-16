"""FAZ 5: hedef tanımları (getiri zaman çıkışı ↔ TP1 olayı ayrı), giriş dışlamaları, eksik veri, geleceğe bakmama,
zaman sıralı bölüm + ambargo ve ön işlemenin yalnız eğitimden öğrenilmesi."""
import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from bist_haber import journal

ROOT = Path(__file__).resolve().parents[1]


def _y(ad, yol):
    s = importlib.util.spec_from_file_location(ad, ROOT / yol)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


hd = _y("faz5_hedefler", "arastirma/faz5/hedefler.py")
dn = _y("faz5_deney", "arastirma/faz5/deney.py")

G = [f"2026-01-{d:02d}" for d in range(2, 30)]


def plan(**k):
    p = {"ticker": "AAA", "tarih": G[0], "tur": "kirilim_teyitli", "giris": 100.0, "sl": 95.0, "tp1": 110.0, "tp2": 120.0,
         "azami": 101.0}
    p.update(k)
    return p


def mumlar(seri):
    """seri: [(o, h, l, c)] G[1]'den başlar; G[0] sinyal günü."""
    out = [{"date": G[0], "open": 100, "high": 100, "low": 100, "close": 100}]
    for i, (o, h, l, c) in enumerate(seri):
        out.append({"date": G[i + 1], "open": o, "high": h, "low": l, "close": c})
    return out


DUZ = (100, 101, 99, 100)


class Hedefler(unittest.TestCase):
    def test_time_exit_return_and_R_by_hand(self):
        b = mumlar([DUZ] * 4 + [(100, 104, 99, 103)] + [DUZ] * 5)
        j, neden = hd.giris(plan(), b)
        self.assertEqual((j, neden), (1, "giris"))
        h = hd.hedef(plan(), b, j, 5, journal)
        self.assertAlmostEqual(h["H5_net_%"], 3.0 - 0.30, places=4)          # 5. gün kapanışı 103
        self.assertAlmostEqual(h["H5_R"], 3 / 5 - 0.003 * 100 / 5, places=4)  # R_plan
        self.assertEqual(h["H5_pozitif"], 1)

    def test_tp1_event_separate_from_return(self):
        """TP1 3. gün görülür ama 5. gün kapanışı zararda: H5_tp1 = 1, H5_pozitif = 0 — iki hedef ayrı."""
        b = mumlar([DUZ, DUZ, (101, 111, 100, 105), (104, 105, 96, 97), (97, 98, 96, 97)] + [DUZ] * 6)
        h = hd.hedef(plan(), b, 1, 5, journal)
        self.assertEqual((h["H5_tp1"], h["H5_pozitif"]), (1, 0))

    def test_tp1_after_window_counts_only_in_longer_horizon(self):
        b = mumlar([DUZ] * 6 + [(101, 112, 100, 110)] + [DUZ] * 4)          # TP1 7. gün
        self.assertEqual(hd.hedef(plan(), b, 1, 5, journal)["H5_tp1"], 0)
        self.assertEqual(hd.hedef(plan(), b, 1, 10, journal)["H10_tp1"], 1)

    def test_stop_before_tp1_and_same_candle_rule(self):
        b = mumlar([DUZ, (99, 100, 94, 95), (96, 112, 95.5, 110)] + [DUZ] * 8)   # 2. gün SL, sonra TP1
        self.assertEqual(hd.hedef(plan(), b, 1, 5, journal)["H5_tp1"], 0)
        b2 = mumlar([DUZ, (100, 112, 94, 100)] + [DUZ] * 9)                       # aynı mumda TP1 ve SL → SL önce
        self.assertEqual(hd.hedef(plan(), b2, 1, 5, journal)["H5_tp1"], 0)

    def test_entry_exclusions_and_missing_data(self):
        self.assertEqual(hd.giris(plan(), mumlar([(102, 103, 101, 102)]))[1], "girissiz_azami_ustu")
        self.assertEqual(hd.giris(plan(), mumlar([(95, 96, 94, 95)]))[1], "girissiz_stop_alti")
        self.assertEqual(hd.giris(plan(), mumlar([]))[1], "giris_mumu_yok")
        self.assertIsNone(hd.hedef(plan(), mumlar([DUZ] * 4), 1, 5, journal))       # 5 mum yok → sonuc_yok

    def test_future_after_window_does_not_change_target(self):
        a = mumlar([DUZ] * 5 + [DUZ] * 6)
        b = mumlar([DUZ] * 5 + [(50, 300, 10, 200)] * 6)
        self.assertEqual(hd.hedef(plan(), a, 1, 5, journal), hd.hedef(plan(), b, 1, 5, journal))

    def test_calendar_gap_flagged_not_dropped(self):
        b = mumlar([DUZ] * 10)
        tix = {d: i for i, d in enumerate(G)}
        b2 = [x for x in b if x["date"] != G[3]]                                  # hissede bir gün eksik
        h = hd.hedef(plan(), b2, 1, 5, journal, tix)
        self.assertEqual(h["H5_takvim_boslugu"], 1)


class Bolumler(unittest.TestCase):
    def df(self):
        t = pd.date_range("2023-01-02", "2026-06-30", freq="B").strftime("%Y-%m-%d")
        rng = np.random.default_rng(0)
        return pd.DataFrame({"tarih": t, "x": rng.normal(size=len(t))})

    def test_embargo_and_order(self):
        tr, te, emb = dn.bolum(self.df(), "2025-11-14", None)
        self.assertLess(tr["tarih"].max(), "2025-09-30")                        # 45 takvim günü
        self.assertEqual(emb, "2025-09-30")
        self.assertGreaterEqual(te["tarih"].min(), "2025-11-14")
        tr2, te2, _ = dn.bolum(self.df(), "2024-01-01", "2025-01-01")
        self.assertLess(tr2["tarih"].max(), "2023-11-17")
        self.assertLess(te2["tarih"].max(), "2025-01-01")

    def test_preprocessing_learned_from_train_only(self):
        m = dn._mod(str(ROOT))
        rng = np.random.default_rng(1)
        n = 400
        cols = {k: rng.normal(size=n) for k in m.NUM}
        cols.update(tur="kirilim_teyitli", trend="Yükseliş", risk="orta", tarih=[f"2024-{1 + i % 12:02d}-01" for i in range(n)])
        tr = pd.DataFrame(cols)
        te = tr.copy()
        te[m.NUM] = te[m.NUM] * 100 + 1000                                     # test dağılımı çok farklı
        Xtr, mu, sd, med = m.design(tr)
        Xte, *_ = m.design(te, mu, sd, med)
        Xte2, mu2, *_ = m.design(te)
        self.assertTrue(np.allclose(mu.values, tr[m.NUM].clip(tr[m.NUM].quantile(.01), tr[m.NUM].quantile(.99), axis=1)
                                    .mean().values))
        self.assertFalse(np.allclose(Xte.values, Xte2.values))                  # test istatistiğiyle değil

    def test_logloss(self):
        self.assertAlmostEqual(dn.logloss([1, 0], [0.5, 0.5]), np.log(2), places=9)


if __name__ == "__main__":
    unittest.main()
