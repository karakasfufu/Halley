"""FAZ 4: rejimin karar anına kadarki veriyle hesaplanması (gelecek veri geçmişi değiştirmez), küme bootstrap,
yeterlilik işareti, örnek süzgeci (canli_ortak, kapanmış, s3 stop altı girişsiz) ve tekrar bayrağı."""
import csv
import importlib.util
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from bist_haber import defter, regime

ROOT = Path(__file__).resolve().parents[1]
_s = importlib.util.spec_from_file_location("rejim_analiz", ROOT / "arastirma" / "faz4" / "rejim_analiz.py")
ra = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ra)


def xu_seri(n=420, bas=date(2023, 1, 2)):
    rows, d, px = [], bas, 1000.0
    for i in range(n):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        px *= 1 + 0.01 * math.sin(i / 17) + 0.002
        rows.append((d.isoformat(), px, px * 1.01, px * 0.99, px * (1 + 0.003 * math.cos(i / 5)), 1e6))
        d += timedelta(days=1)
    return rows


class GelecekBagimsizligi(unittest.TestCase):
    def test_future_bars_do_not_change_past_regimes(self):
        rows = xu_seri()
        gunler = [r[0] for r in rows[250:380]]
        a = ra.rejimler(ra.xu100_baglanti(rows), gunler, regime)
        bozuk = rows[:380] + [(d, o * 3, h * 4, l * 0.5, c * 2.5, v) for d, o, h, l, c, v in rows[380:]]
        b = ra.rejimler(ra.xu100_baglanti(bozuk), gunler, regime)
        self.assertEqual(a, b)
        kesik = ra.rejimler(ra.xu100_baglanti(rows[:380]), gunler, regime)   # gelecek hiç yok
        self.assertEqual(a, kesik)
        self.assertTrue(all(v is not None for v in a.values()))

    def test_each_day_uses_only_data_up_to_that_day(self):
        rows = xu_seri()
        for i in (260, 300, 350):
            g = rows[i][0]
            tam = ra.rejimler(ra.xu100_baglanti(rows), [g], regime)[g]
            sadece_gecmis = ra.rejimler(ra.xu100_baglanti(rows[:i + 1]), [g], regime)[g]
            self.assertEqual(tam, sadece_gecmis)

    def test_short_history_has_no_regime(self):
        rows = xu_seri(150)
        g = rows[-1][0]
        self.assertIsNone(ra.rejimler(ra.xu100_baglanti(rows), [g], regime)[g])

    def test_missing_day_uses_last_available(self):
        rows = xu_seri()
        eksik = rows[300][0]
        r = ra.rejimler(ra.xu100_baglanti(rows[:300] + rows[301:]), [eksik], regime)[eksik]
        self.assertEqual(r["rejim_gunu"], rows[299][0])


class Istatistik(unittest.TestCase):
    def test_cluster_bootstrap_reproducible_and_degenerate(self):
        g = [(f"d{i % 25}", float(i % 3 == 0)) for i in range(200)]
        a = ra.kume_bootstrap(g, ra.ortalama)
        self.assertEqual(a, ra.kume_bootstrap(g, ra.ortalama))              # sabit tohum
        self.assertLessEqual(a[0], ra.ortalama([v for _, v in g]))
        self.assertGreaterEqual(a[1], ra.ortalama([v for _, v in g]))
        self.assertEqual(ra.kume_bootstrap([("d1", 1.0)] * 50, ra.ortalama), None)   # tek gün: aralık yok
        self.assertEqual(ra.kume_bootstrap([("d1", 2.0), ("d2", 2.0)], ra.ortalama), [2.0, 2.0])

    def test_cluster_wider_than_iid_when_days_correlated(self):
        """Aynı günün gözlemleri aynı sonuçsa (tam bağımlı), küme aralığı gün sayısına göre geniş olmalı."""
        g = [(f"d{i}", float(i % 2)) for i in range(20) for _ in range(30)]       # 600 gözlem, 20 bağımsız gün
        a = ra.kume_bootstrap(g, ra.ortalama)
        iid = 1.96 * math.sqrt(0.25 / 600)
        self.assertGreater(a[1] - a[0], 4 * iid)

    def test_group_summary_and_insufficient_flag(self):
        rows = [{"ticker": f"T{i % 7}", "tarih": f"2024-01-{1 + i % 25:02d}", "y": float(i % 4 == 0),
                 "net": (5.0 if i % 4 == 0 else -2.0), "r": (1.5 if i % 4 == 0 else -1.0), "tekrar": False,
                 "sic_pencere": i % 10 == 0, "sic_tutma": False} for i in range(40)]
        o = ra.grup_ozeti(rows, defter.guven)
        self.assertEqual((o["n"], o["gun"], o["hisse"]), (40, 25, 7))
        self.assertEqual(o["tp1_%"], 25.0)
        self.assertEqual(o["kazanma_%"], 25.0)
        self.assertAlmostEqual(o["ort_net_%"], (10 * 5 - 30 * 2) / 40, places=3)
        self.assertEqual(o["veri_gosterge_sicrama_%"], 10.0)
        self.assertFalse(o["yetersiz"])
        self.assertTrue(ra.grup_ozeti(rows[:29], defter.guven)["yetersiz"])         # n < 30
        az_gun = [dict(r, tarih="2024-02-0" + str(1 + i % 5)) for i, r in enumerate(rows)]
        self.assertTrue(ra.grup_ozeti(az_gun, defter.guven)["yetersiz"])            # gün < 20


class OrnekSuzgeci(unittest.TestCase):
    def test_universe_closed_s3_exclusion_and_repeat_flag(self):
        alan = ["ticker", "tarih", "tur", "risk", "teknik_skor", "sonuc", "kapanis", "acilis_bosluk_%", "sl", "y", "net",
                "r", "gun"]
        satir = [
            ("AAA", "2024-01-02", "kirilim_teyitli", "orta", 6, "SL", 100, 0.5, 95, 0, -5.3, -1.06, 2),
            ("AAA", "2024-01-04", "kirilim_teyitli", "orta", 6, "TP2", 100, 0.0, 95, 1, 9.7, 2.0, 5),   # tekrar
            ("BBB", "2024-01-02", "geri_cekilme", "orta", 6, "SL", 100, -6.0, 95, 0, 0.5, 0.1, 1),      # açılış 94 ≤ SL
            ("CCC", "2024-01-02", "geri_cekilme", "yüksek", 9, "SL", 100, 0.0, 95, 0, -5, -1, 1),       # risk yüksek
            ("DDD", "2024-01-02", "geri_cekilme", "orta", 4, "SL", 100, 0.0, 95, 0, -5, -1, 1),          # skor < 5
            ("EEE", "2024-01-02", "geri_cekilme", "orta", 6, "girissiz", 100, 3.0, 95, "", "", "", "")]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(alan)
            w.writerows(satir)
        gunler = {"AAA": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"], "BBB": ["2024-01-02"]}
        rows, haric = ra.ornekler(f.name, {"AAA": ["2024-01-03"]}, gunler)
        self.assertEqual([(r["ticker"], r["tarih"]) for r in rows], [("AAA", "2024-01-02"), ("AAA", "2024-01-04")])
        self.assertEqual(haric, {"s3_acilis_stop_alti_girissiz": 1, "girissiz": 1})
        self.assertEqual([r["tekrar"] for r in rows], [False, True])
        self.assertTrue(rows[0]["sic_tutma"])                                       # 01-03 sıçraması tutma süresinde
        self.assertTrue(rows[1]["sic_pencere"])                                     # 01-03 gösterge penceresinde


if __name__ == "__main__":
    unittest.main()
