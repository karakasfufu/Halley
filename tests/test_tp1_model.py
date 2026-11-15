"""Aşama 6 (2026-11-15): TP1 olasılık modeli — girdiler, kayıtlı model dosyası, eğitim = canlı tahmin eşliği."""
import importlib.util
import json
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from bist_haber import db, ready, technical, tp1_model

ROOT = Path(__file__).resolve().parents[1]


def bars(n=300, seed=1.0):
    out, d, px = [], date(2025, 1, 2), 100.0 * seed
    i = 0
    while len(out) < n:
        if d.weekday() < 5:
            px *= 1 + (0.012 if i % 3 else -0.015) + 0.0004
            out.append({"date": d.isoformat(), "open": px * 0.996, "high": px * 1.012, "low": px * 0.986, "close": px,
                        "volume": 2e5 + 10 * i})
            i += 1
        d += timedelta(days=1)
    return out


class Features(unittest.TestCase):
    def setUp(self):
        self.b, self.x = bars(), bars(seed=100)
        self.t = technical.analyze(self.b[-250:], date.fromisoformat(self.b[-1]["date"]), self.x[-250:])
        self.ts = ready.tech_score(self.t)
        e = self.t["son_fiyat"]
        self.plan = {"tur": "kirilim_teyitli", "giris": e, "sl": e - 2 * self.t["atr"], "tp1": e + 5 * self.t["atr"],
                     "rr1": 2.5}

    def test_features_complete_and_known_values(self):
        mk = tp1_model.market_features(self.x)
        self.assertEqual(mk["x_trend"], 1.0)
        f = tp1_model.features(self.t, self.plan, self.ts, "orta", mk)
        self.assertAlmostEqual(f["stop_atr"], 2.0)
        self.assertAlmostEqual(f["tp1_atr"], 5.0)
        self.assertEqual((f["tur_kirilim_teyitli"], f["tur_geri_cekilme"], f["risk_orta"]), (1.0, 0.0, 1.0))
        m = tp1_model.load()
        self.assertIsNotNone(m, "bist_haber/modeller/tp1_v1.json paketle gelmeli")
        self.assertEqual(set(m["lojistik"]["girdiler"]) - set(f), set())   # model her girdiyi features()'ta bulur
        self.assertIsNone(tp1_model.market_features(self.x[:100])["x_trend"])

    def test_shipped_model_predicts_probability(self):
        m = tp1_model.load()
        f = tp1_model.features(self.t, self.plan, self.ts, "düşük", tp1_model.market_features(self.x))
        p = tp1_model.predict(f, m)
        self.assertTrue(0.01 < p < 0.99)
        self.assertIn(tp1_model.band(p, m), ("düşük", "orta", "yüksek"))
        f2 = dict(f, rsi=None, adx=None)                                 # eksik girdi ortanca ile doldurulur
        self.assertTrue(0 < tp1_model.predict(f2, m) < 1)
        self.assertGreater(m["egitim"]["hisse"], 100)
        self.assertIsNone(tp1_model.load("yok.json"))


class PlanProbability(unittest.TestCase):
    def test_live_db_plan_uses_same_window_and_news(self):
        b, x = bars(320), bars(320, seed=100)
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "t.db")
            for tk, rows in (("AAA", b), ("XU100", x)):
                conn.executemany("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                                 [(tk, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"]) for r in rows])
            day = b[-1]["date"]
            conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,candidates,status,fetched_at) "
                         "VALUES('kap:1','kap',?,?,'t','Yeni İş İlişkisi','AAA','new',?)", (day + "T10:00:00+03:00", day, day))
            conn.commit()
            t = technical.analyze(b[-250:], date.fromisoformat(day), x[-250:])
            e = t["son_fiyat"]
            plan = {"ticker": "AAA", "signal_day": day, "tur": "geri_cekilme", "giris": e, "sl": e - 2 * t["atr"],
                    "tp1": e + 4 * t["atr"], "rr1": 2.0, "risk": "düşük"}
            want = tp1_model.predict(tp1_model.features(t, plan, ready.tech_score(t), "düşük",
                                                        tp1_model.market_features(x[-250:])))
            res = tp1_model.plan_probability(conn, plan)
            self.assertAlmostEqual(res["olasilik"], want, places=12)      # canlı = eğitimdeki hesap
            f = tp1_model.plan_features(conn, plan)
            self.assertEqual((f["h_is"], f["h_var"]), (1.0, 1.0))
            self.assertIsNone(tp1_model.plan_probability(conn, dict(plan, signal_day="2020-01-02")))
            # gizli kayıt: hazır fırsat kaydına öneri anındaki olasılık yazılır; model hatası kaydı engellemez
            from datetime import datetime
            from unittest.mock import patch
            now = datetime(2026, 11, 16, 18, 25)
            full = dict(plan, kapanis=e, giris_alt=e * 0.99, azami_giris=e * 1.01, tp2=e + 6 * t["atr"], vade_lo=3,
                        vade_hi=8, haber_skoru=None, teknik_skor=7, neden="deneme", kaynak="teknik", genel_puan=50)
            ready._store(conn, full, "aksam", "2026-11-17", "aday", now)
            mj = json.loads(conn.execute("SELECT model_json FROM hazir_firsat WHERE ticker='AAA'").fetchone()[0])
            self.assertAlmostEqual(mj["olasilik"], round(want, 4))
            self.assertEqual((mj["surum"], mj["bant"] in ("düşük", "orta", "yüksek")), ("tp1_v1", True))
            with patch.object(tp1_model, "plan_probability", side_effect=RuntimeError("bozuk")):
                ready._store(conn, dict(full, ticker="BBB"), "aksam", "2026-11-17", "aday", now)
            mj = json.loads(conn.execute("SELECT model_json FROM hazir_firsat WHERE ticker='BBB'").fetchone()[0])
            self.assertIn("bozuk", mj["hata"])
            # canlı doğrulama: kapanan önerilerde tahmin ↔ gerçek
            chk = tp1_model.live_check(conn)
            self.assertEqual(chk["kapanan"], 0)
            conn.execute("UPDATE hazir_firsat SET durum='kapandi', sonuc_json=? WHERE ticker='AAA'",
                         (json.dumps({"tp1_goruldu": True, "sonuc": "TP2"}),))
            conn.execute("UPDATE hazir_firsat SET durum='kapandi', sonuc_json='{}' WHERE ticker='BBB'")   # hatalı kayıt
            chk = tp1_model.live_check(conn, min_n=1)
            self.assertEqual((chk["kapanan"], chk["gercek_pct"], chk["auc"]), (1, 100.0, None))   # tek sınıf → AUC yok
            self.assertEqual(tp1_model._auc([1, 0, 1, 0], [0.9, 0.1, 0.6, 0.6]), 0.875)
            conn.close()


class NewsFeatures(unittest.TestCase):
    def test_kap_subject_features_without_look_ahead(self):
        items = [("2026-11-10T09:00:00", "Yeni İş İlişkisi"), ("2026-11-12T19:00:00", "Finansal Rapor"),
                 ("2026-11-11T10:00:00", "Pay Bazında Devre Kesici Bildirimi"),
                 ("2026-11-12T10:00:00+03:00", "Pay Dışında Sermaye Piyasası Aracı İşlemlerine İlişkin Bildirim"),
                 ("2026-10-25T10:00:00", "Özel Durum Açıklaması (Genel)"), ("2026-11-13T09:00:00", "Kar Payı")]
        f = tp1_model.news_features(items, "2026-11-12")
        self.assertEqual((f["h_is"], f["h_finansal"], f["h_kar_payi"], f["h_ozel"]), (1.0, 0.0, 0.0, 0.0))  # 18:00 sonrası yok
        self.assertEqual((f["h_devre"], f["h_var"], f["h_gun"]), (1.0, 1.0, 2.0))
        self.assertAlmostEqual(f["h_say30"], math.log1p(2))                  # tahvil bildirimi sayılmaz
        self.assertEqual(tp1_model.news_features([], "2026-11-12")["h_var"], 0.0)


class TrainingMatchesLive(unittest.TestCase):
    def test_exported_model_equals_training_prediction(self):
        try:
            import numpy as np
            import pandas as pd
        except ImportError:
            self.skipTest("numpy/pandas yok")
        spec = importlib.util.spec_from_file_location("egit", ROOT / "arastirma" / "asama6" / "egit.py")
        egit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(egit)
        rng = np.random.default_rng(3)
        n = 4000
        df = pd.DataFrame({k: rng.normal(size=n) for k in egit.FEATS})
        df["tur"] = rng.choice(list(tp1_model.TURLER), n)
        df["trend"] = rng.choice(["Yükseliş", "Düşüş", "Yatay / kararsız"], n)
        for k in tp1_model.TURLER:
            df["tur_" + k] = (df["tur"] == k).astype(float)
        df["trend_yuk"] = (df["trend"] == "Yükseliş").astype(float)
        df["trend_dus"] = (df["trend"] == "Düşüş").astype(float)
        df["atr_%"] = rng.uniform(1, 6, n)
        df["rsi"] = rng.uniform(25, 85, n)
        df.loc[rng.random(n) < 0.05, "rsi"] = np.nan
        df["tarih"] = [(date(2023, 1, 2) + timedelta(days=int(i // 4))).isoformat() for i in range(n)]
        z = 0.8 * df["skor"] - 0.5 * df["tp1_atr"] + 0.6 * df["tur_kirilim_teyitli"] - 0.8
        df["y"] = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(float)
        df["ticker"], df["r"] = "AAA", 0.0
        m = egit.fit_e2(df)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            egit.export(m, df, path, {})
            live = json.loads(path.read_text(encoding="utf-8"))
        want = egit.predict_e2(m, df.iloc[:300])
        cols = egit.FEATS
        for i in range(300):
            row = {k: (None if pd.isna(v) else float(v)) for k, v in df.iloc[i][cols].items()}
            self.assertAlmostEqual(tp1_model.predict(row, live), want[i], places=9)
        self.assertGreater(egit.old.auc(df["y"].values, egit.predict_e2(m, df)), 0.6)   # öğrenebildiğini göster
        info = tp1_model.similar(row, live)
        self.assertEqual(info["n"], live["tablo"]["sayi"].get(info["grup"], 0))


if __name__ == "__main__":
    unittest.main()
