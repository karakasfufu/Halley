"""FAZ 3: metriklerin elle hesapla ve çapraz doğrulaması (arastirma/faz3/metrikler.py ↔ asama6/portfoy.metrikler ↔
journal.metrics), MAE/MFE penceresi ve R paydaları."""
import importlib.util
import json
import math
import random
import sqlite3
import unittest
from pathlib import Path

from bist_haber import defter, journal

ROOT = Path(__file__).resolve().parents[1]


def _yukle(ad, yol):
    s = importlib.util.spec_from_file_location(ad, ROOT / yol)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


mt = _yukle("faz3_metrikler", "arastirma/faz3/metrikler.py")
mm = _yukle("faz3_mae_mfe", "arastirma/faz3/mae_mfe.py")
pf = _yukle("portfoy", "arastirma/asama6/portfoy.py")


def islem(net, r=None, gun=3, cikis="2026-01-05", tk="AAA", adet=10, fiyat=100.0, sonuc="SL"):
    return {"net_tl": net, "r": r, "islem_gunu": gun, "cikis_gunu": cikis, "ticker": tk, "adet": adet,
            "giris_fiyati": fiyat, "sonuc": sonuc}


class ElleMetrik(unittest.TestCase):
    def test_drawdown_known_series(self):
        m = mt.seri_metrikleri([100.0, 110.0, 99.0, 120.0])
        self.assertAlmostEqual(m["mdd_%"], -10.0, places=9)                # 99 / 110 − 1
        self.assertAlmostEqual(m["mdd_tl"], 11.0, places=9)
        self.assertEqual(m["en_uzun_dusus_gun"], 1)
        r = [0.1, 99 / 110 - 1, 120 / 99 - 1]
        ort = sum(r) / 3
        asagi = math.sqrt((99 / 110 - 1) ** 2 / 3)                          # bütün günlere bölünür
        self.assertAlmostEqual(m["sortino"], ort / asagi * math.sqrt(252), places=9)
        sd = math.sqrt(sum((x - ort) ** 2 for x in r) / 2)
        self.assertAlmostEqual(m["sharpe"], ort / sd * math.sqrt(252), places=9)
        self.assertAlmostEqual(m["cagr_%"], 100 * (1.2 ** (252 / 3) - 1), places=6)
        self.assertAlmostEqual(m["ulcer"], math.sqrt((0 + 0 + 100 + 0) / 4), places=9)

    def test_no_drawdown_and_flat(self):
        m = mt.seri_metrikleri([100.0, 101.0, 102.0])
        self.assertEqual(m["mdd_%"], 0.0)
        self.assertIsNone(m["sortino"])                                    # aşağı yönlü gün yok → tanımsız
        self.assertIsNone(m["calmar"])

    def test_profit_factor_zero_counts_as_loss_and_streaks(self):
        t = [islem(100, 1.0, cikis="2026-01-02"), islem(0, 0.0, cikis="2026-01-03"), islem(-50, -1.0, cikis="2026-01-04"),
             islem(-25, -0.5, cikis="2026-01-05"), islem(60, 0.6, cikis="2026-01-06"), islem(-10, -0.1, cikis="2026-01-07")]
        m = mt.islem_metrikleri(t)
        self.assertAlmostEqual(m["pf"], 160 / 85, places=9)
        self.assertAlmostEqual(m["kazanma_%"], 100 * 2 / 6, places=9)
        self.assertEqual(m["en_uzun_ardisik_kayip"], 3)                    # 0, −50, −25
        self.assertEqual(m["ardisik_kayip_dagilimi"], {1: 1, 3: 1})
        self.assertAlmostEqual(m["odeme_orani"], 80 / (85 / 4), places=9)

    def test_all_wins_pf_undefined(self):
        self.assertIsNone(mt.islem_metrikleri([islem(10, 1.0)])["pf"])


class CaprazDogrulama(unittest.TestCase):
    def test_independent_matches_simulator_metrics_random(self):
        rnd = random.Random(3)
        for _ in range(50):
            oz, egri = 100000.0, []
            for i in range(60):
                oz *= 1 + rnd.gauss(0, 0.015)
                egri.append({"gun": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "ozsermaye": round(oz, 2),
                             "acik_pozisyon": rnd.randint(0, 5)})
            isl = [islem(round(rnd.gauss(0, 500), 2), rnd.gauss(0, 1), rnd.randint(1, 30), f"2026-01-{1 + j % 28:02d}",
                         f"T{j}") for j in range(rnd.randint(1, 40))]
            for t in isl:
                t.update(ayni_mum_belirsiz=False)
            ref = pf.metrikler(egri, isl, [], 100000.0, [], 0)
            b = mt.hesapla(egri, isl, 100000.0)
            self.assertAlmostEqual(ref["azami_dusus_%"], round(b["mdd_%"], 2), places=6)
            if ref["sortino_yillik"] is not None:
                self.assertAlmostEqual(ref["sortino_yillik"], round(b["sortino"], 3), places=6)
            self.assertEqual(ref["kar_faktoru"], round(b["pf"], 3) if b["pf"] is not None else None)
            self.assertEqual(ref["en_uzun_ardisik_kayip"], b["en_uzun_ardisik_kayip"])
            self.assertEqual(ref["en_uzun_dusus_suresi_gun"], b["en_uzun_dusus_gun"])


class CanliPanelMetrigi(unittest.TestCase):
    """journal.metrics (canlı panel): işlem başına tanımlar — kâr faktörü NET %'lerle (eşit ağırlık), azami düşüş
    kümülatif R ile (çıkış gününe göre), 'Sharpe' işlem başına (anakütle std). Portföy metriği değildir."""

    def test_panel_metrics_by_hand(self):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE trade_journal (kaynak TEXT, durum TEXT, sonuc_json TEXT)")
        kay = [("2026-01-02", 4.0, 1.0), ("2026-01-03", -2.0, -1.0), ("2026-01-04", -3.0, -1.2), ("2026-01-05", 1.0, 0.5)]
        for g, net, r in kay:
            c.execute("INSERT INTO trade_journal VALUES ('otomatik','kapandı',?)",
                      (json.dumps({"durum": "kapandı", "cikis_gunu": g, "net_getiri_pct": net, "r": r, "sonuc": "SL"}),))
        m = journal.metrics(c)
        self.assertEqual(m["kar_faktoru"], round(5 / 5, 2))
        self.assertEqual(m["maks_dusus_R"], -2.2)                          # 1 → 0 → −1,2: tepe 1, dip −1,2
        self.assertEqual(m["kazanma_orani_%"], 50.0)


class MaeMfe(unittest.TestCase):
    def bars(self):
        return [{"date": "D1", "open": 100, "high": 104, "low": 98, "close": 101},
                {"date": "D2", "open": 101, "high": 103, "low": 94, "close": 95},
                {"date": "D3", "open": 96, "high": 130, "low": 90, "close": 120}]

    def test_intraday_exit_is_lower_bound_and_post_exit_separate(self):
        t = {"giris_gunu": "D1", "islem_gunu": 2, "bacaklar": [{"neden": "SL", "fiyat": 95.0}], "giris_fiyati": 100.0,
             "sl": 95.0, "planlanan_giris": 100.0}
        x = mm.hesapla(t, self.bars(), defter)
        self.assertEqual(x["yaklasik"], 1)                                 # gün içi çıkış → alt sınır
        self.assertAlmostEqual(x["mae_R_plan"], -1.0)                      # D2 düşüğü 94 değil, çıkış 95 kullanılır
        self.assertAlmostEqual(x["mfe_R_plan"], 0.8)                       # D1 tepe 104
        self.assertAlmostEqual(x["cikis_sonrasi_en_yuksek_%"], round(100 * (130 / 95 - 1), 3))   # işlem içine girmez
        self.assertNotEqual(x["mfe_R_plan"], (130 - 100) / 5)

    def test_fill_based_R_and_undefined_below_stop(self):
        t = {"giris_gunu": "D1", "islem_gunu": 2, "bacaklar": [{"neden": "SL", "fiyat": 95.0}], "giris_fiyati": 102.0,
             "sl": 95.0, "planlanan_giris": 100.0}
        x = mm.hesapla(t, self.bars(), defter)
        self.assertAlmostEqual(x["mae_R_plan"], round((95 - 102) / 5, 3))  # plan paydası: −1,4
        self.assertAlmostEqual(x["mae_R_dolum"], -1.0, places=3)           # dolum paydası: −1
        t2 = dict(t, giris_fiyati=94.0, bacaklar=[{"neden": "SL varsayımı (alış stopun altında)", "fiyat": 94.0}],
                  islem_gunu=1)
        y = mm.hesapla(t2, self.bars(), defter)
        self.assertIsNone(y["mae_R_dolum"])


if __name__ == "__main__":
    unittest.main()
