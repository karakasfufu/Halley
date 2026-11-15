"""FAZ 1 (2026-11-16): canlı tahmin defteri — değiştirilemezlik, tekrar/yeni ayrımı, sonuçlandırma kuralları (s1),
ölçüm, sürüm ayrımı ve veritabanı göçü (HALLEY2_DENETIM_RAPORU.md Ek B4 + Ek C)."""
import json
import math
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, defter, ready, technical, tp1_model
from tests.test_tp1_model import bars

TR = config.TR_TZ


def at(day: str, hm: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{hm}:00").replace(tzinfo=TR)


def next_wd(d: str, k: int = 1) -> str:
    x = date.fromisoformat(d)
    while k:
        x += timedelta(days=1)
        if x.weekday() < 5:
            k -= 1
    return x.isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.db"
        self.conn = db.connect(self.path)
        self.addCleanup(self.conn.close)
        self.hist, x = bars(320), bars(320, seed=100)
        for tk, rows in (("AAA", self.hist), ("XU100", x)):
            self.conn.executemany("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                                  [(tk, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"]) for r in rows])
        self.conn.commit()
        self.day = self.hist[-1]["date"]
        self.gday = next_wd(self.day)
        t = technical.analyze(self.hist[-250:], date.fromisoformat(self.day), x[-250:])
        e, a = t["son_fiyat"], t["atr"]
        self.e, self.atr = e, a
        self.plan = {"ticker": "AAA", "signal_day": self.day, "tur": "geri_cekilme", "kapanis": e, "giris": e,
                     "giris_alt": e - 0.3 * a, "azami_giris": e + 0.3 * a, "sl": e - 2 * a, "tp1": e + 4 * a,
                     "tp2": e + 6 * a, "rr1": 2.0, "vade_lo": 3, "vade_hi": 8, "haber_skoru": None, "teknik_skor": 7,
                     "risk": "orta", "neden": "deneme", "kaynak": "teknik", "genel_puan": 50}

    def store(self, p=None, analiz="aksam", durum="aday", now=None):
        ready._store(self.conn, p or self.plan, analiz, self.gday, durum, now or at(self.day, "18:30"))
        self.conn.commit()

    def add_bars(self, rows):
        self.conn.executemany("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES('AAA',?,?,?,?,?,1e6)",
                              [(d, o, h, l, c) for d, o, h, l, c in rows])
        self.conn.commit()

    def tahminler(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM tahmin ORDER BY id")]

    def sonuc(self, tid):
        r = self.conn.execute("SELECT * FROM tahmin_sonuc WHERE tahmin_id=?", (tid,)).fetchone()
        return dict(r) if r else None


class Kayit(Base):
    def test_frozen_fields_and_immutability(self):
        self.store()
        t = self.tahminler()
        self.assertEqual(len(t), 1)
        t = t[0]
        hf = self.conn.execute("SELECT model_json FROM hazir_firsat").fetchone()[0]
        self.assertAlmostEqual(t["olasilik"], json.loads(hf)["olasilik"], places=4)        # aynı hesap
        self.assertEqual((t["model_surum"], t["gecerlilik_gun"], t["kaynak"], t["giris_gunu"]), ("tp1_v1", 1, "teknik", self.gday))
        for k in ("girdi_json", "teknik_json", "rejim_json", "veri_json"):
            self.assertIsNotNone(json.loads(t[k]), k)
        tk = json.loads(t["teknik_json"])
        self.assertEqual(tk["tarih"], self.day)
        self.assertIn("rsi14", tk)
        self.assertIn("teknik_skor", tk)
        self.assertIn("veri_kritik", json.loads(t["veri_json"]))
        self.assertEqual(json.loads(t["rejim_json"])["gun"], self.day)
        for sql in ("UPDATE tahmin SET olasilik=0.9", "DELETE FROM tahmin"):
            with self.assertRaises(sqlite3.DatabaseError):
                self.conn.execute(sql)
        self.conn.rollback()
        self.assertEqual(self.tahminler()[0]["olasilik"], t["olasilik"])

    def test_repeat_vs_new_prediction(self):
        r = [defter.kaydet(self.conn, self.plan, 1, self.gday, "aksam", at(self.day, "18:30")) for _ in range(5)]
        self.assertEqual([x["durum"] for x in r], ["yeni"] + ["tekrar"] * 4)
        self.assertEqual(len(self.tahminler()), 1)
        first = self.tahminler()[0]
        # yalnız olasılık değişse (ör. geç gelen bilgi) → yeni tahmin DEĞİL, ilk kayıt dondurulmuş kalır
        with patch.object(tp1_model, "predict", return_value=0.99):
            self.assertEqual(defter.kaydet(self.conn, self.plan, 1, self.gday, "sabah", at(self.gday, "08:30"))["durum"], "tekrar")
        self.assertEqual(self.tahminler()[0]["olasilik"], first["olasilik"])
        # seviye değişti → yeni tahmin, önceki bağlantılı
        p2 = dict(self.plan, sl=self.plan["sl"] * 1.01)
        r2 = defter.kaydet(self.conn, p2, 1, self.gday, "sabah", at(self.gday, "08:30"))
        self.assertEqual(r2["durum"], "yeni")
        t = self.tahminler()
        self.assertEqual((len(t), t[1]["onceki_tahmin_id"]), (2, t[0]["id"]))
        # parametre sürümü değişti → yeni tahmin (sonuçlar karışmasın)
        with patch.object(ready, "MIN_TECH", 6):
            self.assertEqual(defter.kaydet(self.conn, p2, 1, self.gday, "sabah", at(self.gday, "08:31"))["durum"], "yeni")
        self.assertEqual(len({x["parametre_surum"] for x in self.tahminler()}), 2)

    def test_store_path_writes_once_and_never_blocks(self):
        for _ in range(3):
            self.store()
        self.assertEqual(len(self.tahminler()), 1)
        with patch.object(tp1_model, "plan_context", side_effect=RuntimeError("bozuk")):
            r = defter.kaydet(self.conn, dict(self.plan, ticker="BBB"), None, self.gday, "aksam")
            self.assertEqual(r["durum"], "hata")
            self.store(dict(self.plan, ticker="BBB"))                    # hazır fırsat yine kaydedilir
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM hazir_firsat WHERE ticker='BBB'").fetchone())

    def test_no_store_when_upsert_skipped(self):
        self.store()
        self.conn.execute("UPDATE hazir_firsat SET durum='giris'")
        self.conn.commit()
        self.store(dict(self.plan, sl=self.plan["sl"] * 1.02), analiz="sabah", durum="onaylandi")
        self.assertEqual(len(self.tahminler()), 1)                       # plan yazılmadı → tahmin de yok


class Sonuc(Base):
    def run_(self, now=None):
        return defter.sonuclandir(self.conn, now or at(next_wd(self.gday, 40), "18:30"), 0.2, 0.1)

    def test_tp_path_and_mae_mfe(self):
        self.store()
        e, a = self.e, self.atr
        g2, g3 = next_wd(self.gday), next_wd(self.gday, 2)
        self.add_bars([(self.gday, e, e + a, e - a, e + 0.5 * a),
                       (g2, e + a, e + 4.5 * a, e + 0.8 * a, e + 4 * a),   # TP1 (yarısı), stop girişe
                       (g3, e + 4 * a, e + 6.5 * a, e + 3.5 * a, e + 6 * a)])  # TP2
        self.assertEqual(self.run_()["yazilan"], 1)
        s = self.sonuc(self.tahminler()[0]["id"])
        self.assertEqual((s["sonuc_turu"], s["tp1_goruldu"], s["sl_goruldu"], s["cikis_nedeni"], s["islem_gunu"]),
                         ("tamamlandi", 1, 0, "TP2", 3))
        self.assertGreater(s["r"], 0)
        self.assertAlmostEqual(s["mae_r"], -0.5, places=3)               # en düşük e − a; risk 2a
        self.assertAlmostEqual(s["mfe_r"], 3.25, places=3)               # en yüksek e + 6,5a
        self.assertEqual(s["ayni_gun_belirsiz"], 0)
        self.assertEqual(self.run_()["yazilan"], 0)                      # tek sonuç; tekrar yazılmaz
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE tahmin_sonuc SET r=9")
        self.conn.rollback()

    def test_same_candle_tp_and_sl_counts_sl_and_flags(self):
        self.store()
        e, a = self.e, self.atr
        g2 = next_wd(self.gday)
        self.add_bars([(self.gday, e, e + a, e - a, e),
                       (g2, e, e + 4.5 * a, e - 2.5 * a, e)])            # aynı mumda TP1 ve SL
        self.run_()
        s = self.sonuc(self.tahminler()[0]["id"])
        self.assertEqual((s["cikis_nedeni"], s["tp1_goruldu"], s["sl_goruldu"], s["ayni_gun_belirsiz"]), ("SL", 0, 1, 1))
        self.assertEqual(json.loads(s["belirsiz_gunler"]), [g2])
        o = defter.ozet(self.conn, "tp1_v1")
        self.assertEqual((o["sayilar"]["belirsiz"], o["olculen"]), (1, 1))
        self.assertEqual(defter.ozet(self.conn, "tp1_v1", belirsiz_dahil=False)["olculen"], 0)

    def test_entry_day_both_touched_is_sl_and_flagged(self):
        self.store()
        e, a = self.e, self.atr
        self.add_bars([(self.gday, e, e + 4.5 * a, e - 2.5 * a, e)])
        self.run_()
        s = self.sonuc(self.tahminler()[0]["id"])
        self.assertEqual((s["cikis_nedeni"], s["ayni_gun_belirsiz"], s["islem_gunu"]), ("SL", 1, 1))

    def test_open_above_max_and_missing_entry_day(self):
        self.store()
        self.add_bars([(self.gday, self.plan["azami_giris"] * 1.01, self.e * 1.05, self.e, self.e)])
        self.run_()
        s = self.sonuc(self.tahminler()[0]["id"])
        self.assertEqual((s["sonuc_turu"], s["neden"]), ("girissiz", "açılış azami girişin üstünde"))

    def test_no_entry_day_bar_but_later_bars(self):
        self.store()
        self.add_bars([(next_wd(self.gday), self.e, self.e, self.e, self.e)])
        self.run_()
        self.assertEqual(self.sonuc(self.tahminler()[0]["id"])["neden"], "giriş günü işlem verisi yok")

    def test_open_prediction_not_in_metrics(self):
        self.store()
        self.add_bars([(self.gday, self.e, self.e * 1.005, self.e * 0.995, self.e)])   # pozisyon sürüyor
        self.run_()
        self.assertIsNone(self.sonuc(self.tahminler()[0]["id"]))
        o = defter.ozet(self.conn, "tp1_v1")
        self.assertEqual((o["sayilar"]["acik"], o["olculen"], o["metrik"]), (1, 0, None))
        self.assertEqual(o["guven"], "çok az örnek, karar verilmez")

    def test_own_frozen_levels_superseded_and_cancel(self):
        self.store()                                                    # akşam tahmini A
        p2 = dict(self.plan, sl=self.e - 1.5 * self.atr)
        self.store(p2, analiz="sabah", durum="onaylandi", now=at(self.gday, "08:30"))   # sabah seviyeler yenilendi → B
        a_, b_ = self.tahminler()
        self.assertEqual(b_["onceki_tahmin_id"], a_["id"])
        self.conn.execute("UPDATE hazir_firsat SET sl=?", (self.e - 3 * self.atr,))     # hazır fırsat sonradan değişse de
        self.conn.commit()
        e, a = self.e, self.atr
        self.add_bars([(self.gday, e, e + a, e - a, e), (next_wd(self.gday), e, e + a, e - 1.6 * a, e)])
        self.run_()
        self.assertEqual(self.sonuc(a_["id"])["sonuc_turu"], "yerini_aldi")
        sb = self.sonuc(b_["id"])
        self.assertEqual((sb["sonuc_turu"], sb["cikis_nedeni"]), ("tamamlandi", "SL"))  # B'nin kendi SL'si (e − 1,5a)
        # iptal edilen hazır fırsat
        self.store(dict(self.plan, ticker="XU100", signal_day=self.day))
        tid = self.tahminler()[-1]["id"]
        self.conn.execute("UPDATE hazir_firsat SET durum='iptal', iptal_nedeni='olumsuz haber' WHERE ticker='XU100'")
        self.conn.commit()
        self.run_()
        s = self.sonuc(tid)
        self.assertEqual((s["sonuc_turu"], s["neden"]), ("iptal", "olumsuz haber"))
        o = defter.ozet(self.conn, "tp1_v1")
        self.assertEqual((o["sayilar"]["yerini_aldi"], o["sayilar"]["iptal"], o["olculen"]), (1, 1, 1))

    def test_late_and_backfilled_are_excluded(self):
        defter.kaydet(self.conn, self.plan, None, self.gday, "sabah", at(self.gday, "10:30"))
        defter.kaydet(self.conn, dict(self.plan, ticker="XU100"), None, self.gday, "aksam", at(self.day, "19:00"),
                      sonradan=True)
        self.run_()
        t = self.tahminler()
        self.assertEqual(self.sonuc(t[0]["id"])["sonuc_turu"], "gec_kayit")
        o = defter.ozet(self.conn, "tp1_v1")
        self.assertEqual((o["sayilar"]["gec_kayit"], o["sayilar"]["sonradan"], o["olculen"]), (1, 1, 0))


class Olcum(Base):
    def _ins(self, i, p, y, surum="tp1_v1", bant="orta", sonuc="tamamlandi", rejim=None, r=1.0):
        cur = self.conn.execute(
            "INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
            "parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kaynak,rejim_json) "
            "VALUES(?,?,?,?,?,?,'f','p',?,?,'geri_cekilme',10,10.3,9,12,13,1,'haber',?)",
            (f"x{i}{surum}", f"T{i}", "2026-01-01", "2026-01-02", "2026-01-01T18:30:00+03:00", surum, p, bant,
             json.dumps(rejim or {"trend": "yükseliş", "oynaklik": "normal"})))
        self.conn.execute("INSERT INTO tahmin_sonuc(tahmin_id,sonuc_turu,tp1_goruldu,net_getiri_pct,r,mae_r,mfe_r,islem_gunu,"
                          "degerlendirme_zamani,kural_surum) VALUES(?,?,?,?,?,-0.5,1.0,5,'z','s1')",
                          (cur.lastrowid, sonuc, y, 2.0 if y else -2.0, r if y else -1.0))

    def test_known_metrics_and_versions_not_mixed(self):
        ps = [0.1, 0.2, 0.3, 0.3, 0.4, 0.5, 0.25, 0.35, 0.45, 0.15]
        ys = [0, 0, 1, 0, 1, 1, 0, 0, 1, 0]
        for i, (p, y) in enumerate(zip(ps, ys)):
            self._ins(i, p, y, bant="yüksek" if p >= 0.34 else "orta" if p >= 0.229 else "düşük")
        self._ins(100, 0.9, 1, surum="tp1_v2")                          # başka sürüm: karışmamalı
        self._ins(101, 0.3, 0, sonuc="girissiz")
        self.conn.commit()
        o = defter.ozet(self.conn, "tp1_v1")
        self.assertEqual((o["sayilar"]["tahmin"], o["olculen"], o["sayilar"]["girissiz"]), (11, 10, 1))
        brier = sum((p - y) ** 2 for p, y in zip(ps, ys)) / 10
        ll = -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in zip(ps, ys)) / 10
        self.assertAlmostEqual(o["metrik"]["brier"], round(brier, 4))
        self.assertAlmostEqual(o["metrik"]["log_loss"], round(ll, 4))
        self.assertEqual((o["metrik"]["tp1_%"], o["metrik"]["kazanma_%"]), (40.0, 40.0))
        self.assertEqual(o["metrik"]["tp1_%90"], defter.wilson(4, 10))
        lo, hi = defter.wilson(4, 10)
        self.assertLess(lo, 40)
        self.assertGreater(hi, 40)
        cal = {c["bant"]: c for c in o["kalibrasyon"]}
        self.assertEqual((cal["yüksek"]["n"], cal["yüksek"]["gercek_%"]), (4, 75.0))   # 0.4,0.5,0.35,0.45 → 1,1,0,1
        self.assertEqual(defter.ozet(self.conn, "tp1_v2")["olculen"], 1)
        self.assertEqual([v["model_surum"] for v in defter.model_surumleri(self.conn)][0] in ("tp1_v1", "tp1_v2"), True)
        self.assertEqual(defter.guven(29), "çok az örnek, karar verilmez")
        self.assertEqual(defter.guven(100), "orta güven")


class Goc(unittest.TestCase):
    def test_fresh_db_no_backup_and_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            c = db.connect(Path(t) / "a.db")
            self.assertEqual((db.TAHMIN_GOC["durum"], db.TAHMIN_GOC["yedek"]), ("olusturuldu", None))
            c.close()
            c = db.connect(Path(t) / "a.db")
            self.assertEqual(db.TAHMIN_GOC["durum"], "var")
            c.close()

    def _old_db_with_user_data(self, t):
        p = Path(t) / "data" / "bist_haber.db"
        c = db.connect(p)
        c.execute("DROP TABLE tahmin_sonuc")
        c.execute("DROP TABLE tahmin")                                  # FAZ 1 öncesi şema (geri dönüş 2. seviye da budur)
        c.execute("INSERT INTO news(id,source,published_at,effective_date,title,status,fetched_at) "
                  "VALUES('kap:1','kap','2026-01-01','2026-01-01','t','new','x')")
        c.commit()
        c.close()
        return p

    def test_backup_before_migration_and_user_data_kept(self):
        with tempfile.TemporaryDirectory() as t:
            p = self._old_db_with_user_data(t)
            c = db.connect(p)
            g = dict(db.TAHMIN_GOC)
            self.assertEqual(g["durum"], "olusturuldu")
            y = Path(g["yedek"])
            self.assertTrue(y.exists() and y.parent.name == "yedek" and "tahmin_defteri_oncesi" in y.name)
            yc = sqlite3.connect(y)
            self.assertEqual(yc.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(yc.execute("SELECT COUNT(*) FROM news").fetchone()[0], 1)
            self.assertIsNone(yc.execute("SELECT 1 FROM sqlite_master WHERE name='tahmin'").fetchone())   # göç öncesi hâl
            yc.close()
            self.assertEqual(c.execute("SELECT COUNT(*) FROM news").fetchone()[0], 1)
            c.close()
            c = db.connect(p)                                             # ikinci açılışta göç/yedek tekrar yok
            self.assertEqual(db.TAHMIN_GOC["durum"], "var")
            self.assertEqual(len(list((p.parent / "yedek").glob("*tahmin_defteri_oncesi*"))), 1)
            c.close()

    def test_backup_failure_skips_migration_app_continues(self):
        with tempfile.TemporaryDirectory() as t:
            p = self._old_db_with_user_data(t)
            real = sqlite3.connect

            def fake(target, *a, **k):
                if "tahmin_defteri_oncesi" in str(target):
                    raise sqlite3.OperationalError("disk dolu")
                return real(target, *a, **k)
            with patch.object(db.sqlite3, "connect", side_effect=fake):
                c = db.connect(p)
            self.assertEqual(db.TAHMIN_GOC["durum"], "yedek_hatasi")
            self.assertFalse(defter.tablo_var(c))
            self.assertEqual(defter.kaydet(c, {}, None, "2026-01-02", "aksam")["durum"], "tablo_yok")
            self.assertEqual(defter.sonuclandir(c)["hata"], "tablo_yok")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM news").fetchone()[0], 1)
            c.close()

    def test_drop_tables_rollback_level2(self):
        with tempfile.TemporaryDirectory() as t:
            c = db.connect(Path(t) / "b.db")
            c.execute("INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
                      "parametre_surum,olasilik,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun) "
                      "VALUES('i','A','d','g','z','m','f','p',0.3,'t',1,1,1,1,1,1)")
            c.commit()
            c.execute("DROP TABLE tahmin_sonuc")
            c.execute("DROP TABLE tahmin")                              # satır tetikleyicileri tablo silmeyi engellemez
            c.commit()
            self.assertFalse(defter.tablo_var(c))
            c.close()


if __name__ == "__main__":
    unittest.main()
