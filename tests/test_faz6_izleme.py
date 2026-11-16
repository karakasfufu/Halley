"""FAZ 6: model izleme (bist_haber/izleme.py) ve rejim önbelleği (bist_haber/regime.py).
Kümeli aralıklar, yetersiz veri, dört durumun ayrılığı, teyit (aynı kanıt ikinci doğrulama sayılmaz), tekrar
bastırma, günde bir kontrol, salt-okur panel; önbelleğin veri/parametre değişince geçersizleşmesi ve sonucun aynılığı."""
import json
import random
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import db, defter, izleme, regime

REF = json.loads(izleme.REF_YOLU.read_text(encoding="utf-8"))


def kayitlar(n_gun, gunde, uret, tohum=1):
    rnd = random.Random(tohum)
    out = []
    for d in range(n_gun):
        for _ in range(gunde):
            p, y = uret(rnd)
            out.append({"gun": f"2026-{1 + d // 28:02d}-{1 + d % 28:02d}", "ticker": f"T{rnd.randint(0, 30)}", "y": y, "p": p,
                        "girdi": {}, "rejim": "yükseliş / normal"})
    return out


def iyi(rnd):
    p = rnd.betavariate(2.9, 7.1)
    return p, int(rnd.random() < p)


class Araliklar(unittest.TestCase):
    def test_cluster_auc_matches_plain_auc_and_widens_with_dependence(self):
        g = [f"d{i}" for i in range(200)]
        y = [i % 2 for i in range(200)]
        p = [0.3 + 0.4 * (i % 2) + 0.001 * i for i in range(200)]
        a = izleme.kume_auc(g, y, p)
        self.assertAlmostEqual(a["deger"], 1.0)
        rnd = random.Random(3)
        y2 = [int(rnd.random() < 0.3) for _ in range(400)]
        p2 = [rnd.random() for _ in range(400)]
        bag = izleme.kume_auc([f"d{i // 20}" for i in range(400)], y2, p2)        # 20 gün, günde 20
        bag_yok = izleme.kume_auc([f"d{i}" for i in range(400)], y2, p2)
        self.assertEqual(round(bag["deger"], 9), round(bag_yok["deger"], 9))
        self.assertIsNotNone(bag["aralik"])

    def test_cluster_mean(self):
        r = izleme.kume_ortalama(["a", "a", "b", "b"], [1.0, 1.0, 0.0, 0.0])
        self.assertEqual(r["deger"], 0.5)
        self.assertLess(r["aralik"][0], 0.5)
        self.assertIsNone(izleme.kume_ortalama(["a", "a"], [1.0, 0.0])["aralik"])   # tek gün: aralık yok


class Olcum(unittest.TestCase):
    def test_insufficient_data_is_not_healthy(self):
        o = izleme.olc(kayitlar(10, 2, iyi), REF)
        for k in ("P1", "P2", "K1", "R1", "G1"):
            self.assertEqual(o[k]["durum"], "yetersiz")
            self.assertIn("sağlıklı", o[k]["neden"])                               # "'Model sağlıklı' çıkarılmaz"

    def test_good_model_below_thresholds(self):
        o = izleme.olc(kayitlar(120, 3, iyi), REF)
        self.assertEqual(o["P1"]["durum"], "esik_alti")
        self.assertEqual(o["P2"]["durum"], "esik_alti")
        self.assertIn(o["K1"]["durum"], ("esik_alti", "esik_asildi"))
        self.assertGreater(o["P1"]["deger"], 0.6)

    def test_reversed_model_flags_P1_and_P2(self):
        ters = lambda rnd: (lambda p: (p, int(rnd.random() < 0.9 - p)))(rnd.betavariate(2.9, 7.1))
        o = izleme.olc(kayitlar(120, 3, ters), REF)
        self.assertEqual(o["P1"]["durum"], "esik_asildi")
        self.assertEqual(o["P2"]["durum"], "esik_asildi")

    def test_overprediction_flags_K1_only(self):
        fazla = lambda rnd: (lambda p: (p, int(rnd.random() < 0.5 * p)))(rnd.betavariate(2.9, 7.1))
        o = izleme.olc(kayitlar(120, 3, fazla), REF)
        self.assertEqual(o["K1"]["durum"], "esik_asildi")
        self.assertIn("fazla tahmin", o["K1"]["neden"])
        self.assertEqual(o["P1"]["durum"], "esik_alti")                               # sıralama hâlâ bilgilendirici

    def test_regime_and_input_drift_are_info_not_failure(self):
        k = kayitlar(60, 2, iyi)
        for x in k:
            x["rejim"] = "düşüş / yüksek"
            x["girdi"] = {"rsi": 95.0, "x_trend": -1.0}
        o = izleme.olc(k, REF)
        self.assertEqual(o["R1"]["durum"], "bilgi")
        self.assertIn("nadir", o["R1"]["neden"])
        self.assertIn("başarısızlığı anlamına gelmez", o["R1"]["neden"])
        self.assertEqual(o["G1"]["durum"], "bilgi")
        self.assertEqual(o["G1"]["seviye"], "belirgin kayma")
        self.assertIn("başarısızlığı anlamına gelmez", o["G1"]["neden"])

    def test_psi_zero_on_reference_proportions(self):
        r = REF["girdi"]["rsi"]
        v = []
        for i, oran in enumerate(r["oranlar"]):
            x = r["sinirlar"][i] - 0.01 if i < len(r["sinirlar"]) else r["sinirlar"][-1] + 1
            v += [x] * int(round(oran * 10000))
        self.assertLess(izleme.psi(v, r), 0.01)


class Gecis(unittest.TestCase):
    def test_confirmation_needs_new_evidence(self):
        g = izleme.gecis(None, True, 40)
        self.assertEqual((g["durum"], g["olay"]), ("izleniyor", "ilk_asim"))
        same = izleme.gecis({k: v for k, v in g.items() if k != "olay"}, True, 40)    # aynı kanıt
        self.assertEqual((same["durum"], same["olay"]), ("izleniyor", None))
        az = izleme.gecis({k: v for k, v in g.items() if k != "olay"}, True, 59)      # 19 yeni gün
        self.assertEqual(az["durum"], "izleniyor")
        ok = izleme.gecis({k: v for k, v in g.items() if k != "olay"}, True, 60)      # 20 yeni gün
        self.assertEqual((ok["durum"], ok["olay"]), ("acik", "uyari_acildi"))

    def test_no_repeat_alert_and_close_needs_clean_evidence(self):
        s = {"durum": "acik", "gun0": 60}
        for gun in (61, 70, 90):
            g = izleme.gecis(s, True, gun)
            self.assertEqual((g["durum"], g["olay"]), ("acik", None))                 # devam: yeni uyarı yok
            s = {k: v for k, v in g.items() if k != "olay"}
        g = izleme.gecis(s, False, 95)
        self.assertEqual(g["durum"], "kapanma_izleniyor")
        s = {k: v for k, v in g.items() if k != "olay"}
        self.assertEqual(izleme.gecis(s, False, 100)["durum"], "kapanma_izleniyor")
        self.assertEqual(izleme.gecis(s, False, 115)["olay"], "uyari_kapandi")
        self.assertEqual(izleme.gecis(s, True, 100)["durum"], "acik")

    def test_unconfirmed_first_breach_resets(self):
        g = izleme.gecis({"durum": "izleniyor", "gun0": 40}, False, 45)
        self.assertEqual((g["durum"], g["olay"]), ("normal", "teyit_edilmedi"))


class KontrolVePanel(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def degerler(self, esik):
        o = izleme.olc(kayitlar(120, 3, iyi), REF)
        if esik:
            o["P2"]["durum"] = "esik_asildi"
        return [{"grup": {}, "etiket": "G", "pencereler": {"birikimli": o, "son_60_gun": o}}]

    def test_daily_check_logs_only_transitions_and_once_per_day(self):
        with patch.object(izleme, "degerlendir", lambda conn: self.degerler(True)):
            r1 = izleme.kontrol_et(None, self.tmp, datetime(2026, 12, 1, 19))
            r2 = izleme.kontrol_et(None, self.tmp, datetime(2026, 12, 1, 21))          # aynı gün
        self.assertEqual([x["olay"] for x in r1["olaylar"]], ["ilk_asim", "ilk_asim"])
        self.assertIn("atlandi", r2)
        satir = (self.tmp / "izleme_kayit.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(satir), 2)
        kayit = json.loads(satir[0])
        for k in ("olay", "grup", "pencere", "olcut", "olcum"):
            self.assertIn(k, kayit)
        for k in ("orneklem", "referans", "neden", "aralik_%90"):
            self.assertIn(k, kayit["olcum"])
        with patch.object(izleme, "degerlendir", lambda conn: self.degerler(True)):  # ertesi gün, aynı kanıt
            r3 = izleme.kontrol_et(None, self.tmp, datetime(2026, 12, 2, 19))
        self.assertEqual(r3["olay"], 0)                                                 # teyit için yeni gün yok

    def test_panel_summary_is_read_only(self):
        p = self.tmp / "bist_haber.db"
        c = db.connect(p)
        db.migrate_tahmin(c, p)
        once = sorted(x.name for x in self.tmp.iterdir())
        oz = izleme.panel_ozeti(c, self.tmp)
        self.assertEqual(oz["degerlendirme"], [])
        self.assertEqual(sorted(x.name for x in self.tmp.iterdir()), once)              # dosya yazılmadı
        c.close()

    def test_contract_missing_group_not_measured(self):
        gr = {"model_surum": "tp1_v1", "ozellik_surum": "x", "parametre_surum": "y", "kural_surum": "eksik",
              "maliyet_protokol": "eksik", "komisyon_pct": None, "kayma_pct": None}
        with patch.object(defter, "gruplar", lambda conn: [{"grup": gr, "n": 2, "son": ""}]):
            e = izleme.degerlendir(None, REF)
        self.assertEqual(e[0]["durum"], "sozlesme_eksik")


class RejimOnbellegi(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        self.c.execute("CREATE TABLE prices (ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL,"
                       " PRIMARY KEY (ticker, date))")
        d, px = date(2025, 1, 1), 1000.0
        for i in range(300):
            px *= 1.001 + 0.01 * ((i % 7) - 3) / 3
            self.c.execute("INSERT INTO prices VALUES ('XU100',?,?,?,?,?,1)", (d.isoformat(), px, px * 1.01, px * 0.99, px))
            d += timedelta(days=1)
        self.gun = d - timedelta(days=1)
        regime._ONBELLEK.clear()

    def test_cached_equals_uncached_and_returns_copy(self):
        a = regime.regime(self.c, self.gun)
        b = regime.regime(self.c, self.gun)
        self.assertEqual(a, regime.regime(self.c, self.gun, onbellek=False))
        self.assertEqual(a, b)
        b["trend"] = "BOZUK"
        self.assertNotEqual(regime.regime(self.c, self.gun)["trend"], "BOZUK")      # önbellek değiştirilemez

    def test_invalidated_when_data_changes(self):
        a = regime.regime(self.c, self.gun)
        self.c.execute("UPDATE prices SET close=close*0.5 WHERE date=?", (self.gun.isoformat(),))
        b = regime.regime(self.c, self.gun)
        self.assertEqual(b, regime.regime(self.c, self.gun, onbellek=False))
        self.assertNotEqual(a["xu100"], b["xu100"])

    def test_invalidated_when_parameters_change(self):
        regime.regime(self.c, self.gun)
        with patch.object(regime, "LOW_PCT", 99), patch.object(regime, "HIGH_PCT", 100):
            self.assertEqual(regime.regime(self.c, self.gun)["oynaklik"], "düşük")
        self.assertEqual(regime.regime(self.c, self.gun), regime.regime(self.c, self.gun, onbellek=False))


if __name__ == "__main__":
    unittest.main()
