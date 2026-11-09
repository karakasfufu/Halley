"""İşlem günlüğü (C1): el hesabıyla doğrulanabilir örnekler."""
import json
import tempfile
import unittest
from pathlib import Path

from bist_haber import db, journal as J

REC = {"senaryo": "destek", "giris": 100.0, "sl": 95.0, "tp1": 105.0, "tp2": 110.0, "gecerlilik": 5,
       "signal_day": "2026-01-01", "kaynak": "otomatik", "alarm": None}


def bars(*rows):
    """(open, high, low, close) → 2026-01-02'den itibaren günlük barlar."""
    return [{"date": f"2026-01-{i + 2:02d}", "open": o, "high": h, "low": l, "close": c} for i, (o, h, l, c) in enumerate(rows)]


class EvaluateTests(unittest.TestCase):
    def test_half_at_tp1_then_tp2(self):
        r = J.evaluate(REC, bars((101, 101.5, 99.5, 100.5), (101, 106, 100.5, 105.5), (106, 111, 105, 110)))
        self.assertEqual((r["durum"], r["sonuc"]), ("kapandı", "TP2"))
        self.assertAlmostEqual(r["brut_getiri_pct"], 7.5)                     # 0,5×%5 + 0,5×%10
        self.assertAlmostEqual(r["net_getiri_pct"], 7.2)                      # − %0,30 maliyet
        self.assertAlmostEqual(r["r"], 1.44)                                  # 1,5R − 0,06R maliyet
        self.assertEqual(r["cikis_gunu"], "2026-01-04")
        self.assertTrue(any("stop girişe" in x for x in r["olaylar"]))

    def test_breakeven_after_tp1(self):
        r = J.evaluate(REC, bars((101, 101.5, 99.5, 100.5), (101, 106, 100.5, 105.5), (104, 104.5, 99, 99.5)))
        self.assertEqual(r["sonuc"], "başabaş (TP1 sonrası)")
        self.assertAlmostEqual(r["brut_getiri_pct"], 2.5)

    def test_stop_loss(self):
        r = J.evaluate(REC, bars((101, 101.5, 99.5, 100.5), (99, 99.5, 94, 94.5)))
        self.assertEqual(r["sonuc"], "SL")
        self.assertAlmostEqual(r["brut_getiri_pct"], -5.0)
        self.assertAlmostEqual(r["r"], -1.06)

    def test_same_day_stop_and_target_counts_stop(self):
        r = J.evaluate(REC, bars((101, 101.5, 99.5, 100.5), (100, 106, 94, 100)))
        self.assertEqual(r["sonuc"], "SL")

    def test_fill_day_stop_counts_but_target_does_not(self):
        self.assertEqual(J.evaluate(REC, bars((100.5, 101, 94, 95)))["sonuc"], "SL")
        r = J.evaluate(REC, bars((100.5, 106, 99, 104)))                     # dolduğu gün TP1 görülse de sayılmaz
        self.assertEqual(r["durum"], "açık")

    def test_gap_below_stop_exits_at_open(self):
        r = J.evaluate(REC, bars((101, 101.5, 99.5, 100.5), (90, 91, 89, 90)))
        self.assertAlmostEqual(r["brut_getiri_pct"], -10.0)

    def test_slippage_stats(self):
        import tempfile
        from pathlib import Path
        from bist_haber import db
        with tempfile.TemporaryDirectory() as d:
            c = db.connect(Path(d) / "t.db")
            c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
                      "sonuc_json) VALUES('x','2026-11-02','AAA','otomatik','destek',100,95,104,110,5,?)",
                      ('{"giris_fiyati": 99.5}',))                                 # sanal limit 99,5'ten doldu
            c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik)"
                      " VALUES('x','2026-11-02','BBB','otomatik','kirilim',50,48,53,56,10)")   # sanal gerçekleşmedi
            c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
                      "gercek_giris_gunu,gercek_giris_fiyati,ana_id) VALUES('x','2026-11-02','AAA','gercek','destek',100,"
                      "95,104,110,5,'2026-11-03',100.0,1)")
            c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
                      "gercek_giris_gunu,gercek_giris_fiyati,ana_id) VALUES('x','2026-11-02','BBB','gercek','kirilim',50,"
                      "48,53,56,10,'2026-11-03',49.5,2)")
            s = J.slippage_stats(c)
            self.assertEqual(s["n"], 2)
            got = {x["hisse"]: round(x["kayma_%"], 4) for x in s["islemler"]}
            self.assertEqual(got, {"AAA": round((100 / 99.5 - 1) * 100, 4), "BBB": -1.0})   # referans: sanal dolum / plan
            self.assertAlmostEqual(s["ortalama_pct"], ((100 / 99.5 - 1) * 100 - 1.0) / 2)
            c.close()

    def test_record_real_guards(self):
        import tempfile
        from datetime import datetime
        from pathlib import Path
        from bist_haber import config, db
        with tempfile.TemporaryDirectory() as d:
            c = db.connect(Path(d) / "t.db")
            c.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik)"
                      " VALUES('x','2026-11-06','AAA','otomatik','destek',100,95,104,110,5)")
            c.commit()
            today = datetime.now(config.TR_TZ).date().isoformat()
            for day, px, msg in (("2099-01-01", 100.0, "ileri"), ("2026-11-06", 100.0, "sonra olmalı"),
                                 ("2026-11-09", 10000.0, "aralığı"), ("2026-11-09", 94.0, "aralığı"),
                                 ("2026-11-09", 0.0, "geçersiz")):
                with self.assertRaises(ValueError) as cm:
                    J.record_real(c, 1, day if day != "2026-11-09" else min(today, day), px)
                self.assertIn(msg, str(cm.exception))
            day = min(today, "2026-11-09")
            if day > "2026-11-06":
                J.record_real(c, 1, day, 100.5)
                with self.assertRaises(ValueError) as cm:                      # ikinci "Kaydet": çökme değil, uyarı
                    J.record_real(c, 1, day, 100.5)
                self.assertIn("zaten kaydedilmiş", str(cm.exception))
            c.close()

    def test_breakout_waiting_below_stop_is_not_cancelled(self):
        # Kırılımda SL giriş seviyesine göredir; kırılım olmadan fiyatın SL altında durması senaryoyu bozmaz
        # (kartta "kapanış SL altına inerse kırılım başarısız" kırılımdan SONRASI içindir). Erken iptal hatası önlenir.
        rec = dict(REC, senaryo="kirilim", alarm=103.0, giris=103.4, sl=101.0, tp1=108.0, tp2=115.0)
        r = J.evaluate(rec, bars((102, 102.5, 100, 100.5)))
        self.assertEqual(r["durum"], "bekliyor")
        r2 = J.evaluate(REC, bars((101, 101.5, 94.0, 94.5)))         # limit doldu ve aynı gün SL → SL
        self.assertEqual(r2["sonuc"], "SL")

    def test_not_filled(self):
        self.assertEqual(J.evaluate(REC, bars(*[(103, 104, 101, 103)] * 5))["durum"], "iptal")
        self.assertEqual(J.evaluate(REC, bars(*[(103, 104, 101, 103)] * 2))["durum"], "bekliyor")

    def test_breakout_fills_next_open_after_close_above_alarm(self):
        rec = dict(REC, senaryo="kirilim", alarm=103.0, giris=103.4, sl=101.0, tp1=108.0, tp2=115.0)
        r = J.evaluate(rec, bars((102, 103.5, 101.5, 102.5), (102.5, 104.5, 102, 104), (104.5, 105, 104, 104.8)))
        self.assertEqual((r["giris_gunu"], r["giris_fiyati"]), ("2026-01-04", 104.5))   # kapanış 104 > 103 → ertesi açılış
        self.assertEqual(r["durum"], "açık")

    def test_breakout_gap_open_below_stop(self):  # gerçek veride görülen durum: R yine hesaplanır
        rec = dict(REC, senaryo="kirilim", alarm=103.0, giris=103.4, sl=101.0, tp1=108.0, tp2=115.0)
        r = J.evaluate(rec, bars((102, 104, 101.5, 103.5), (100, 100.5, 99, 99.5)))
        self.assertEqual((r["sonuc"], r["giris_fiyati"]), ("SL", 100))
        self.assertTrue(r["acilis_sl_alti"])
        self.assertIsNotNone(r["r"])

    def test_max_hold_closes_at_close(self):
        r = J.evaluate(REC, bars((101, 101.5, 99.5, 100.5), *[(101, 102, 100, 101)] * 30))
        self.assertEqual((r["sonuc"], r["islem_gunu"]), ("süre doldu", 30))
        self.assertAlmostEqual(r["brut_getiri_pct"], 1.0)

    def test_signal_day_and_earlier_bars_ignored(self):  # geleceği görmeme: signal_day dahil önceki barlar yok sayılır
        early = [{"date": "2026-01-01", "open": 90, "high": 120, "low": 80, "close": 100}]
        r = J.evaluate(REC, early + bars((101, 101.5, 99.5, 100.5)))
        self.assertEqual(r["giris_gunu"], "2026-01-02")

    def test_real_trade_uses_user_fill(self):
        rec = dict(REC, kaynak="gercek", gercek_giris_gunu="2026-01-02", gercek_giris_fiyati=99.0)
        r = J.evaluate(rec, bars((99, 100, 98.5, 99.5), (100, 106, 99.5, 105)))
        self.assertEqual(r["giris_fiyati"], 99.0)
        self.assertTrue(r["tp1_goruldu"])

    def test_costs_configurable(self):
        r = J.evaluate(REC, bars((101, 101.5, 99.5, 100.5), (99, 99.5, 94, 94.5)), commission_pct=0.0, slippage_pct=0.0)
        self.assertAlmostEqual(r["net_getiri_pct"], -5.0)


class StoreAndMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)

    def plan(self):
        s = {"tur": "destek", "emir": "Limit emir: 100", "giris": 100.0, "sl": 95.0, "tp1": 105.0, "tp2": 110.0,
             "gecerlilik_gun": 5, "risk_seviyesi": "orta", "kalite": "iyi"}
        return {"durum": "senaryo", "girisler": {"senaryolar": [s], "en_uygun": "destek"}}

    def add_prices(self, ticker, rows):
        for b in rows:
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close) VALUES(?,?,?,?,?,?)",
                              (ticker, b["date"], b["open"], b["high"], b["low"], b["close"]))
        self.conn.commit()

    def test_one_open_auto_record_per_ticker(self):
        self.assertIsNotNone(J.record_auto(self.conn, "AAA", self.plan(), "2026-01-01", 3.0))
        self.assertIsNone(J.record_auto(self.conn, "AAA", self.plan(), "2026-01-02", 3.0))   # açık kayıt var
        self.assertIsNone(J.record_auto(self.conn, "BBB", {"durum": "yok"}, "2026-01-01", 1.0))

    def test_update_and_metrics(self):
        a = J.record_auto(self.conn, "AAA", self.plan(), "2026-01-01", 3.0)
        J.record_auto(self.conn, "BBB", self.plan(), "2026-01-01", 2.0)
        self.add_prices("AAA", bars((101, 101.5, 99.5, 100.5), (101, 106, 100.5, 105.5), (106, 111, 105, 110)))
        self.add_prices("BBB", bars((101, 101.5, 99.5, 100.5), (99, 99.5, 94, 94.5)))
        self.assertEqual(J.update_all(self.conn)["degerlendirilen"], 2)
        m = J.metrics(self.conn)
        self.assertEqual((m["kapanan"], m["kazanma_orani_%"]), (2, 50.0))
        self.assertAlmostEqual(m["kar_faktoru"], round(7.2 / 5.3, 2))
        self.assertAlmostEqual(m["maks_dusus_R"], -1.06)                      # TP2 (+1,44R) önce değil: aynı gün kapanış
        self.assertFalse(m["yeterli_ornek"])
        rid = J.record_real(self.conn, a, "2026-01-02", 100.2)
        self.assertEqual(self.conn.execute("SELECT kaynak, ana_id FROM trade_journal WHERE id=?", (rid,)).fetchone()[:],
                         ("gercek", a))
        J.update_all(self.conn)
        self.assertEqual(J.metrics(self.conn, "gercek")["kapanan"], 1)

    def test_bad_real_price_rejected(self):
        a = J.record_auto(self.conn, "AAA", self.plan(), "2026-01-01", 3.0)
        with self.assertRaises(ValueError):
            J.record_real(self.conn, a, "2026-01-02", 0)


    def test_daily_refresh_downloads_open_tickers_only(self):
        J.record_auto(self.conn, "AAA", self.plan(), "2026-01-01", 3.0)
        asked = []
        def fake_prices(conn, tickers):
            asked.append(sorted(tickers))
            self.add_prices("AAA", bars((101, 101.5, 99.5, 100.5), (99, 99.5, 94, 94.5)))
            return 2
        res = J.daily_refresh(self.conn, "2026-01-05", price_fn=fake_prices)
        self.assertEqual(asked, [["AAA", "XU100"]])
        self.assertEqual((res["hisse"], res["durumu_degisen"]), (1, 1))
        self.assertEqual(self.conn.execute("SELECT durum FROM trade_journal").fetchone()[0], "kapandı")
        self.assertEqual(J.daily_refresh(self.conn, "2026-01-06", price_fn=fake_prices)["hisse"], 0)   # açık kalmadı


class PositionSizeTests(unittest.TestCase):
    def test_risk_limited(self):
        p = J.position_size(100_000, 1.0, 100.0, 95.0)          # pay başı risk 5 + %0,30 maliyet = 5,30 TL
        self.assertEqual((p["adet"], p["sinirlayan"]), (188, "risk"))
        self.assertAlmostEqual(p["azami_kayip"], 996.4)
        self.assertLessEqual(p["azami_kayip_%"], 1.0)

    def test_cash_limited(self):
        p = J.position_size(10_000, 50.0, 100.0, 99.0)
        self.assertEqual(p["sinirlayan"], "nakit")
        self.assertLessEqual(p["tutar"], 10_000)

    def test_invalid_inputs(self):
        for args in ((0, 1, 100, 95), (1000, 0, 100, 95), (1000, 1, 100, 101)):
            with self.assertRaises(ValueError):
                J.position_size(*args)


if __name__ == "__main__":
    unittest.main()
