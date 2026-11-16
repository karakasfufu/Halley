"""FAZ 2 (16.11.2026): portföy backtest simülatörü (arastirma/asama6/portfoy.py) — elle hesaplanmış portföy,
sınırlar, kısmi satış, geleceğe bakmama, giriş sırası bağımsızlığı, aynı gün nakit, tekil işlemlerle mutabakat,
açık pozisyon/eksik fiyat/belirsizlik raporu, canlı sıralama kuralıyla eşlik."""
import copy
import importlib.util
import random
import unittest
from pathlib import Path
from unittest.mock import patch

from bist_haber import journal, ready

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("portfoy", ROOT / "arastirma" / "asama6" / "portfoy.py")
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)

D = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12"]


def bar(d, o, h, l, c):
    return {"date": d, "open": o, "high": h, "low": l, "close": c}


def plan(tk, gun, giris=100.0, sl=95.0, tp1=110.0, tp2=120.0, azami=101.0, skor=7, rr1=2.0, risk="orta", tur="kirilim_teyitli"):
    return {"ticker": tk, "tarih": gun, "tur": tur, "risk": risk, "teknik_skor": skor, "rr1": rr1, "giris": giris,
            "sl": sl, "tp1": tp1, "tp2": tp2, "azami": azami, "trend": "Yükseliş"}


def duz(tk, gunler, px=100.0):
    return [bar(d, px, px * 1.005, px * 0.995, px) for d in gunler]


SEK = lambda tk: "Sanayi"


class ElleHesap(unittest.TestCase):
    def setUp(self):
        self.bars = {"AAA": [bar(D[0], 100, 100, 100, 100), bar(D[1], 100, 101, 99, 100), bar(D[2], 100, 111, 100, 110),
                             bar(D[3], 110, 121, 109, 120)]}
        self.r = pf.simule([plan("AAA", D[0])], self.bars, D[:4], D[1], D[3],
                           {"baslangic_sermaye": 10000, "risk_pct": 1.0}, SEK)

    def test_cash_shares_costs_equity(self):
        r = self.r
        t = r["islemler"][0]
        self.assertEqual(t["adet"], 18)                        # position_size: floor(100 / (5 + 0,3)) = 18
        e = {x["gun"]: x for x in r["egri"]}
        self.assertAlmostEqual(e[D[1]]["nakit"], 8197.30, places=2)       # 10000 − 1800 − 2,70
        self.assertAlmostEqual(e[D[1]]["ozsermaye"], 9997.30, places=2)
        self.assertAlmostEqual(e[D[2]]["nakit"], 9185.95, places=2)       # + 9×110 − 9×100×0,0015
        self.assertAlmostEqual(e[D[2]]["ozsermaye"], 10175.95, places=2)  # + 9 × 110 piyasa değeri
        self.assertAlmostEqual(e[D[3]]["ozsermaye"], 10264.60, places=2)
        self.assertEqual((t["brut_tl"], t["maliyet_tl"], t["net_tl"]), (270.0, 5.4, 264.6))
        self.assertEqual([(b["adet"], b["fiyat"]) for b in t["bacaklar"]], [(9, 110.0), (9, 120.0)])
        self.assertAlmostEqual(t["net_tl"], 18 * 100 * t["journal_net_%"] / 100, places=6)   # tekil sonuçla aynı

    def test_partial_sale_updates_open_risk(self):
        e = {x["gun"]: x for x in self.r["egri"]}
        self.assertAlmostEqual(e[D[1]]["acik_risk"], 18 * 5 + 18 * 100 * 0.0015, places=6)   # 92,70
        self.assertAlmostEqual(e[D[2]]["acik_risk"], 9 * 100 * 0.0015, places=6)            # stop girişte: 1,35
        self.assertEqual(e[D[3]]["acik_pozisyon"], 0)


class Sinirlar(unittest.TestCase):
    def _iki(self, ayar, sek=SEK, p2=None):
        bars = {"AAA": duz("AAA", D[:4]), "BBB": duz("BBB", D[:4])}
        ps = [plan("AAA", D[0], skor=9), p2 or plan("BBB", D[0], skor=7)]
        return pf.simule(ps, bars, D[:4], D[1], D[3], dict({"baslangic_sermaye": 10000, "risk_pct": 1.0}, **ayar), sek)

    def neden(self, r):
        return [x["neden"] for x in r["atlanan"]]

    def test_position_limit(self):
        r = self._iki({"azami_pozisyon": 1})
        self.assertEqual(self.neden(r), ["pozisyon sınırı"])
        self.assertEqual([t["ticker"] for t in r["acik_son"]], ["AAA"])       # sıralama: yüksek skor önce

    def test_total_risk_limit(self):
        r = self._iki({"azami_toplam_risk_pct": 1.5})
        self.assertEqual(self.neden(r), ["toplam risk sınırı"])

    def test_sector_limit_and_unknown_bucket(self):
        self.assertEqual(self.neden(self._iki({"azami_sektor": 1})), ["sektör sınırı"])
        r = self._iki({"azami_sektor": 1}, sek=lambda tk: "bilinmiyor")
        self.assertEqual(self.neden(r), ["sektör sınırı (sektör bilinmiyor)"])
        self.assertEqual(self.neden(self._iki({"azami_sektor": 1}, sek=lambda tk: tk)), [])   # farklı sektör: ikisi de

    def test_cash_limit_reduces_then_skips(self):
        r = self._iki({"risk_pct": 60.0})                       # risk büyük → nakit sınırlar
        a = {t["ticker"]: t for t in r["acik_son"]}
        self.assertEqual(a["AAA"]["adet_bas"], 99)               # position_size nakit sınırı: floor(10000/100,15)
        self.assertNotIn("BBB", a)
        self.assertEqual(self.neden(r), ["nakit yetersiz"])
        r2 = self._iki({"risk_pct": 4.0})                       # AAA 75 adet (7511,25 TL) → BBB kalan nakde göre
        b = {t["ticker"]: t for t in r2["acik_son"]}
        self.assertEqual((b["AAA"]["adet_bas"], b["BBB"]["adet_bas"], r2["kucultulen"]), (75, 24, 1))


class ZamanSirasi(unittest.TestCase):
    def _veri(self):
        rng = random.Random(3)
        bars, ps = {}, []
        for k, tk in enumerate(["AAA", "BBB", "CCC", "DDD"]):
            px, rows = 100.0, []
            for i, d in enumerate(D):
                o = px * (1 + rng.uniform(-0.01, 0.01))
                c = o * (1 + rng.uniform(-0.06, 0.08))
                rows.append(bar(d, round(o, 4), round(max(o, c) * 1.01, 4), round(min(o, c) * 0.99, 4), round(c, 4)))
                px = c
            bars[tk] = rows
            for gi in (0, 2):
                e = rows[gi]["close"]
                ps.append(plan(tk, D[gi], giris=e, sl=e * 0.95, tp1=e * 1.06, tp2=e * 1.1, azami=e * 1.02, skor=6 + k % 3))
        return bars, ps

    def test_future_prices_do_not_change_past_decisions(self):
        bars, ps = self._veri()
        a = pf.simule(ps, bars, D, D[1], D[-1], {"baslangic_sermaye": 10000}, SEK)
        b2 = copy.deepcopy(bars)
        for tk in b2:                                           # D[4] ve sonrası tamamen değişti
            for x in b2[tk][4:]:
                for k in ("open", "high", "low", "close"):
                    x[k] = x[k] * 1.5
        b = pf.simule(ps, b2, D, D[1], D[-1], {"baslangic_sermaye": 10000}, SEK)
        self.assertEqual(a["egri"][:3], b["egri"][:3])           # D1–D3 gün sonları aynı
        ent = lambda r: [(t["ticker"], t["giris_gunu"], t["adet_bas"] if "adet_bas" in t else t["adet"])
                         for t in r["islemler"] + r["acik_son"] if t["giris_gunu"] <= D[3]]
        self.assertEqual(sorted(ent(a)), sorted(ent(b)))
        self.assertEqual([x for x in a["atlanan"] if x["gun"] <= D[3]], [x for x in b["atlanan"] if x["gun"] <= D[3]])

    def test_input_order_independent(self):
        bars, ps = self._veri()
        a = pf.simule(ps, bars, D, D[1], D[-1], {"baslangic_sermaye": 10000, "azami_pozisyon": 2}, SEK)
        ps2 = list(reversed(ps))
        random.Random(9).shuffle(ps2)
        bars2 = dict(reversed(list(bars.items())))
        b = pf.simule(ps2, bars2, D, D[1], D[-1], {"baslangic_sermaye": 10000, "azami_pozisyon": 2}, SEK)
        self.assertEqual(a["egri"], b["egri"])
        self.assertEqual(a["islemler"], b["islemler"])
        self.assertEqual(a["atlanan"], b["atlanan"])

    def test_same_day_exit_cash_not_used_for_entry(self):
        bars = {"AAA": [bar(D[0], 100, 100, 100, 100), bar(D[1], 100, 101, 99, 100), bar(D[2], 80, 82, 78, 80),
                        bar(D[3], 80, 81, 79, 80)],
                "BBB": duz("BBB", D[:4])}
        ps = [plan("AAA", D[0]), plan("BBB", D[1])]               # BBB girişi D2 açılışı; AAA aynı açılışta stopta
        r = pf.simule(ps, bars, D[:4], D[1], D[3], {"baslangic_sermaye": 10000, "sabit_adet": 90,
                                                     "azami_toplam_risk_pct": 100.0}, SEK)
        t = {x["ticker"]: x for x in r["islemler"]}
        self.assertEqual((t["AAA"]["cikis_gunu"], t["AAA"]["sonuc"]), (D[2], "SL"))
        b = {x["ticker"]: x for x in r["acik_son"]}["BBB"]
        # D1 sonu nakit = 10000 − 9000 − 13,5 = 986,5 → BBB en fazla floor(986,5 / 100,15) = 9 adet (AAA'nın nakdi yok)
        self.assertEqual(b["adet_bas"], 9)
        self.assertEqual(r["kucultulen"], 1)


class Mutabakat(unittest.TestCase):
    def test_unconstrained_matches_single_trade_results(self):
        rng = random.Random(5)
        bars, ps = {}, []
        for tk in ["AAA", "BBB", "CCC", "DDD", "EEE"]:
            px, rows = 50.0, []
            for d in D:
                o = px * (1 + rng.uniform(-0.03, 0.03))
                c = o * (1 + rng.uniform(-0.07, 0.07))
                rows.append(bar(d, o, max(o, c) * 1.02, min(o, c) * 0.98, c))
                px = c
            bars[tk] = rows
            e = rows[0]["close"]
            ps.append(plan(tk, D[0], giris=e, sl=e * 0.94, tp1=e * 1.05, tp2=e * 1.09, azami=e * 1.05))
        r = pf.simule(ps, bars, D, D[1], D[-1], {"baslangic_sermaye": 1e9, "sinirsiz": True, "sabit_adet": 100}, SEK)
        for t in r["islemler"]:
            p = next(x for x in ps if x["ticker"] == t["ticker"])
            rec = {"kaynak": "gercek", "gercek_giris_gunu": D[1], "gercek_giris_fiyati": bars[t["ticker"]][1]["open"],
                   "signal_day": D[0], "senaryo": p["tur"], "sl": p["sl"], "tp1": p["tp1"], "tp2": p["tp2"],
                   "giris": p["giris"], "alarm": None, "gecerlilik": 1}
            j = journal.evaluate(rec, bars[t["ticker"]], 0.2, 0.1)
            self.assertEqual((t["sonuc"], t["cikis_gunu"]), (j["sonuc"], j["cikis_gunu"]))
            # journal'ın kendi bacak fiyatları ve payları ile birebir: Σ pay·100·(fiyat − giriş) − 100·giriş·%0,3
            beklenen = sum(b["pay"] * 100 * (b["fiyat"] - t["giris_fiyati"]) for b in j["bacaklar"]) \
                - 100 * t["giris_fiyati"] * 0.3 / 100
            self.assertAlmostEqual(t["net_tl"], round(beklenen, 2), delta=0.006)
            self.assertAlmostEqual(t["net_tl"] / (100 * t["giris_fiyati"]) * 100, j["net_getiri_pct"], delta=0.001)
            self.assertEqual([(b["fiyat"], b["adet"]) for b in t["bacaklar"]],
                             [(b["fiyat"], int(round(b["pay"] * 100))) for b in j["bacaklar"]])
        self.assertEqual(len(r["islemler"]) + len(r["acik_son"]) + len(r["atlanan"]), len(ps))
        self.assertTrue(all(x["neden"] == "açılış azami girişin üstünde" for x in r["atlanan"]))


class Rapor(unittest.TestCase):
    def test_open_positions_missing_prices_and_ambiguity(self):
        bars = {"AAA": [bar(D[0], 100, 100, 100, 100), bar(D[1], 100, 101, 99, 100), bar(D[3], 101, 103, 100, 102)],
                "BBB": [bar(D[0], 100, 100, 100, 100), bar(D[1], 100, 101, 99, 100), bar(D[2], 100, 111, 94, 100)]}
        ps = [plan("AAA", D[0]), plan("BBB", D[0])]
        r = pf.simule(ps, bars, D[:4], D[1], D[3], {"baslangic_sermaye": 100000, "sabit_adet": 10}, SEK)
        b = {t["ticker"]: t for t in r["islemler"]}["BBB"]
        self.assertEqual((b["sonuc"], b["ayni_mum_belirsiz"], b["belirsiz_gunler"]), ("SL", True, [D[2]]))
        a = r["acik_son"][0]
        self.assertEqual((a["ticker"], a["kalan"], a["eksik_fiyat_gunu"], a["son_kapanis"]), ("AAA", 10, 1, 102))
        self.assertEqual(r["eksik_fiyat"], {"AAA": 1})
        e = {x["gun"]: x for x in r["egri"]}
        self.assertAlmostEqual(e[D[2]]["piyasa_degeri"], 10 * 100, places=6)    # eksik gün: son bilinen kapanış
        m = r["metrik"]
        self.assertEqual((m["sonda_acik_pozisyon"], m["sonda_gerceklesmemis_tl"], m["kapanan_islem"]), (1, 20.0, 1))
        self.assertEqual(m["ayni_mum_belirsiz_islem"], 1)

    def test_metrics_known_curve(self):
        egri = [{"gun": d, "ozsermaye": v, "acik_pozisyon": 0} for d, v in zip(D, [100, 110, 99, 120, 108])]
        islem = [{"net_tl": 10, "r": 1.0, "cikis_gunu": D[0], "ticker": "A", "islem_gunu": 2, "ayni_mum_belirsiz": False},
                 {"net_tl": -5, "r": -0.5, "cikis_gunu": D[1], "ticker": "B", "islem_gunu": 3, "ayni_mum_belirsiz": False},
                 {"net_tl": -5, "r": -0.5, "cikis_gunu": D[2], "ticker": "C", "islem_gunu": 1, "ayni_mum_belirsiz": False}]
        m = pf.metrikler(egri, islem, [], 100, [], 0)
        self.assertEqual(m["azami_dusus_%"], -10.0)                # 110 → 99
        self.assertEqual((m["kar_faktoru"], m["kazanma_orani_%"], m["en_uzun_ardisik_kayip"]), (1.0, 33.3, 2))
        self.assertEqual(m["toplam_getiri_%"], 8.0)


class Takvim(unittest.TestCase):
    def test_calendar_is_union_and_guard_catches_skipped_day(self):
        """XU100'de olmayan bir işlem günü (25 Aralık örneği) takvimden düşmemeli; düşerse sıra koruması hata verir."""
        bars = {"XU100": [bar(d, 1, 1, 1, 1) for d in D[:5] if d != D[2]],
                "AAA": [bar(D[0], 100, 100, 100, 100), bar(D[1], 100, 101, 99, 100), bar(D[2], 100, 111, 100, 110),
                        bar(D[3], 110, 112, 108, 111), bar(D[4], 111, 113, 109, 112)]}
        tk = pf.takvim_olustur(bars)
        self.assertEqual(tk, D[:5])                               # D2 (XU100'de yok) takvimde
        r = pf.simule([plan("AAA", D[0], tp2=130)], bars, tk, D[1], D[4], {"baslangic_sermaye": 10000}, SEK)
        self.assertEqual(r["acik_son"][0]["tp1_satildi"], True)  # TP1 D2'de işlendi
        xu_takvim = [b["date"] for b in bars["XU100"]]
        with self.assertRaises(AssertionError):                   # yalnız XU100 takvimi: TP1 günü atlanır → koruma
            pf.simule([plan("AAA", D[0], tp2=130)], bars, xu_takvim, D[1], D[4], {"baslangic_sermaye": 10000}, SEK)


class CanliSiralama(unittest.TestCase):
    def test_same_order_as_ready_select(self):
        ps = [plan("AAA", D[0], skor=6, rr1=3.0, risk="orta"), plan("BBB", D[0], skor=9, rr1=2.0, risk="orta"),
              plan("CCC", D[0], skor=5, rr1=2.5, risk="düşük"), plan("DDD", D[0], skor=8, rr1=4.5, risk="orta")]
        canli = [dict(p, haber_skoru=0.0) for p in ps]
        with patch.object(ready, "build", side_effect=lambda conn, ctx, r: {"plan": canli[r["i"]]}):
            sec = ready.select(None, None, [{"i": i, "score": 2.0, "ticker": p["ticker"]} for i, p in enumerate(ps)])
        self.assertEqual([p["ticker"] for p in sec["secilen"]], [p["ticker"] for p in sorted(ps, key=pf.siralama_anahtari)])


if __name__ == "__main__":
    unittest.main()
