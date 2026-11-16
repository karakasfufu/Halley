"""FAZ 1 dış inceleme bulguları (A–G) ve ek kabul kriterleri için regresyon testleri (16.11.2026, Ek F).
Her test DOĞRU davranışı tarif eder; düzeltmeden önceki kodda başarısız olması bulgunun kanıtıdır."""
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, defter, journal, pipeline, ready, tp1_model
from tests.test_defter import Base, at, next_wd

ROOT = Path(__file__).resolve().parents[1]


def _rec(e, sl, tp1, tp2, day):
    return {"kaynak": "gercek", "gercek_giris_gunu": day, "gercek_giris_fiyati": e, "signal_day": "2026-01-01",
            "senaryo": "geri_cekilme", "sl": sl, "tp1": tp1, "tp2": tp2, "giris": e, "alarm": None, "gecerlilik": 1}


def _bar(d, o, h, l, c):
    return {"date": d, "open": o, "high": h, "low": l, "close": c}


class A_TP2Acilis(unittest.TestCase):
    """A: ertesi gün doğrudan TP2 üstünde açılışta TP1 hedefine ulaşılmış sayılmalı (TP1, SL'den önce geçildi)."""
    def test_journal_marks_target_reached_on_direct_tp2_gap(self):
        bars = [_bar("2026-01-02", 100, 101, 99, 100), _bar("2026-01-05", 120, 121, 119, 120)]
        res = journal.evaluate(_rec(100, 95, 110, 115, "2026-01-02"), bars)
        self.assertEqual(res["sonuc"], "TP2")
        self.assertFalse(res["tp1_goruldu"])            # anlamı değişmedi: "TP1'de yarısı satıldı" olmadı
        self.assertTrue(res["tp1_hedefi"])              # yeni açık alan: TP1 hedefine SL'den önce ulaşıldı
        tp1_open = journal.evaluate(_rec(100, 95, 110, 130, "2026-01-02"),
                                    [_bar("2026-01-02", 100, 101, 99, 100), _bar("2026-01-05", 111, 112, 109, 111)])
        self.assertTrue(tp1_open["tp1_hedefi"] and tp1_open["tp1_goruldu"])
        sl = journal.evaluate(_rec(100, 95, 110, 115, "2026-01-02"),
                              [_bar("2026-01-02", 100, 101, 94, 95)])
        self.assertFalse(sl["tp1_hedefi"])

    def test_research_labeling_uses_target_field(self):
        src = (ROOT / "arastirma" / "asama6" / "etiketle.py").read_text(encoding="utf-8")
        self.assertIn('res.get("tp1_hedefi"', src)       # eğitim etiketi canlı ölçümle aynı anlam


class A_Defter(Base):
    def test_ledger_counts_direct_tp2_as_tp1_event(self):
        self.store()
        e, a = self.e, self.atr
        self.add_bars([(self.gday, e, e + a, e - a, e), (next_wd(self.gday), e + 7 * a, e + 7.5 * a, e + 6.5 * a, e + 7 * a)])
        defter.sonuclandir(self.conn, at(next_wd(self.gday, 5), "18:30"))
        s = dict(self.conn.execute("SELECT * FROM tahmin_sonuc").fetchone())
        self.assertEqual((s["cikis_nedeni"], s["tp1_olayi"]), ("TP2", 1))
        o = defter.ozet(self.conn, defter.gruplar(self.conn)[0]["grup"])
        self.assertEqual(o["metrik"]["tp1_%"], 100.0)


class B_Maliyet(Base):
    def test_costs_frozen_at_prediction_time(self):
        pipeline.save_settings(komisyon_pct=0.2, kayma_pct=0.1)
        self.store()
        t = dict(self.conn.execute("SELECT * FROM tahmin").fetchone())
        self.assertEqual((t["komisyon_pct"], t["kayma_pct"], t["kural_surum"], t["maliyet_protokol"]),
                         (0.2, 0.1, defter.KURAL_SURUM, defter.MALIYET_PROTOKOL))
        pipeline.save_settings(komisyon_pct=1.0, kayma_pct=1.0)            # sonradan ayar değişti
        e, a = self.e, self.atr
        self.add_bars([(self.gday, e, e + a, e - a, e), (next_wd(self.gday), e, e + a, e - 2.5 * a, e)])
        defter.sonuclandir(self.conn, at(next_wd(self.gday, 5), "18:30"))
        s = dict(self.conn.execute("SELECT * FROM tahmin_sonuc").fetchone())
        self.assertEqual((s["komisyon_pct"], s["kayma_pct"], s["maliyet_kaynagi"]), (0.2, 0.1, "tahmin_sozlesmesi"))
        gross = (t["sl"] / e - 1) * 100
        self.assertAlmostEqual(s["net_getiri_pct"], round(gross - 0.3, 3), places=3)

    def tearDown(self):
        pipeline.save_settings(komisyon_pct=journal.DEFAULT_COMMISSION_PCT, kayma_pct=journal.DEFAULT_SLIPPAGE_PCT)

    def setUp(self):
        super().setUp()
        p = patch.object(pipeline, "SETTINGS_FILE", Path(self.tmp.name) / "ayarlar.json")
        p.start()
        self.addCleanup(p.stop)

    def test_missing_contract_is_shown_not_guessed(self):
        self.store()
        tid = self.conn.execute("SELECT id FROM tahmin").fetchone()[0]
        # eski (sözleşmesiz) kaydı taklit: sözleşme sütunları boş yeni bir satır
        self.conn.execute("INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
                          "parametre_surum,olasilik,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun) SELECT 'eski',ticker,"
                          "signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,parametre_surum,olasilik,tur,giris,"
                          "azami_giris,sl,tp1,tp2,gecerlilik_gun FROM tahmin WHERE id=?", (tid,))
        self.conn.commit()
        g = {x["grup"]["maliyet_protokol"] for x in defter.gruplar(self.conn)}
        self.assertIn("eksik", g)                                       # ayrı grupta, açıkça "eksik"
        self.assertEqual(len(defter.gruplar(self.conn)), 2)


class C_Gruplar(Base):
    def test_versions_never_pooled(self):
        defter.kaydet(self.conn, self.plan, 1, self.gday, "aksam", at(self.day, "18:30"))
        with patch.object(ready, "MIN_TECH", 6):
            defter.kaydet(self.conn, self.plan, 1, self.gday, "aksam", at(self.day, "18:31"))
        gs = defter.gruplar(self.conn)
        self.assertEqual(len(gs), 2)
        for g in gs:
            self.assertEqual(defter.ozet(self.conn, g["grup"])["sayilar"]["tahmin"], 1)
        with self.assertRaises(TypeError):
            defter.ozet(self.conn, "tp1_v1")                            # yalnız model sürümüyle birleşik hesap yok


class D_EksikVeri(Base):
    def test_missing_entry_bar_is_not_final(self):
        self.store()
        self.add_bars([(next_wd(self.gday), self.e, self.e, self.e, self.e)])
        defter.sonuclandir(self.conn, at(next_wd(self.gday, 2), "18:30"))
        self.assertIsNone(self.conn.execute("SELECT 1 FROM tahmin_sonuc").fetchone())     # nihai sonuç yazılmadı
        o = defter.ozet(self.conn, defter.gruplar(self.conn)[0]["grup"])
        self.assertEqual((o["sayilar"]["veri_eksik"], o["sayilar"]["acik"], o["sayilar"]["girissiz"]), (1, 0, 0))
        self.add_bars([(self.gday, self.plan["azami_giris"] * 1.02, self.e * 1.05, self.e, self.e)])  # veri geldi
        defter.sonuclandir(self.conn, at(next_wd(self.gday, 3), "18:30"))
        self.assertEqual(self.conn.execute("SELECT sonuc_turu FROM tahmin_sonuc").fetchone()[0], "girissiz")


class E_MaeMfe(Base):
    def _run(self, bars):
        self.store()
        self.add_bars(bars)
        defter.sonuclandir(self.conn, at(next_wd(self.gday, 40), "18:30"))
        return dict(self.conn.execute("SELECT * FROM tahmin_sonuc").fetchone())

    def test_exit_at_open_ignores_rest_of_exit_bar(self):
        e, a = self.e, self.atr
        s = self._run([(self.gday, e, e + a, e - a, e), (next_wd(self.gday), e - 3 * a, e - 2.8 * a, e - 6 * a, e - 5 * a)])
        self.assertEqual(s["cikis_nedeni"], "SL")
        self.assertAlmostEqual(s["mae_r"], -1.5, places=3)          # açılış (e − 3a), mumun dibi (e − 6a) değil
        self.assertAlmostEqual(s["mfe_r"], 0.5, places=3)
        self.assertEqual(s["mae_mfe_yaklasik"], 0)

    def test_intraday_exit_uses_exit_price_and_is_flagged(self):
        e, a = self.e, self.atr
        s = self._run([(self.gday, e, e + a, e - a, e), (next_wd(self.gday), e, e + 0.5 * a, e - 4 * a, e - 3 * a)])
        self.assertAlmostEqual(s["mae_r"], -1.0, places=3)          # stop (e − 2a) / risk 2a; mumun dibi değil
        self.assertEqual(s["mae_mfe_yaklasik"], 1)
        self.assertIn("gunluk", s["mae_mfe_yontem"])

    def test_entry_day_sl(self):
        e, a = self.e, self.atr
        s = self._run([(self.gday, e, e + 0.5 * a, e - 5 * a, e - 4 * a)])
        self.assertEqual((s["cikis_nedeni"], s["islem_gunu"]), ("SL", 1))
        self.assertAlmostEqual(s["mae_r"], -1.0, places=3)
        self.assertAlmostEqual(s["mfe_r"], 0.0, places=3)           # giriş günü: açılış + çıkış fiyatı


class F_Karsilastirma(Base):
    def test_no_backtest_equivalence_claimed(self):
        self.store()
        e, a = self.e, self.atr
        self.add_bars([(self.gday, e, e + a, e - a, e), (next_wd(self.gday), e, e + a, e - 2.5 * a, e)])
        defter.sonuclandir(self.conn, at(next_wd(self.gday, 5), "18:30"))
        b = defter.ozet(self.conn, defter.gruplar(self.conn)[0]["grup"])["beklenti"]
        self.assertNotIn("gecmis_benzer_oran_%", b)
        self.assertIsNone(b["donem_disi_referans"])
        self.assertIn("haber şartı", b["donem_disi_gerekce"])


class G_Gorunurluk(Base):
    def test_failure_logged_once_and_coverage_visible(self):
        with patch.object(tp1_model, "plan_context", side_effect=RuntimeError("bozuk")):
            self.store()
            self.store()                                                # tekrar deneme
        ev = [dict(r) for r in self.conn.execute("SELECT * FROM defter_olay WHERE olay='kayit_hatasi'")]
        self.assertEqual(len(ev), 1)
        self.assertIn("bozuk", ev[0]["mesaj"])
        k = defter.kapsam(self.conn)
        self.assertEqual((k["hazir_firsat"], k["tahminli"], k["eksik"]), (1, 0, 1))
        self.store()                                                    # hata giderildi → tek tahmin
        self.store()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM tahmin").fetchone()[0], 1)
        self.assertEqual(defter.kapsam(self.conn)["eksik"], 0)
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM defter_olay")


class Kabul(Base):
    def test_concurrent_writers_single_row(self):
        paths = []

        def worker():
            c = db.connect(self.path)
            paths.append(defter.kaydet(c, self.plan, 1, self.gday, "aksam", at(self.day, "18:30"))["durum"])
            c.close()
        ts = [threading.Thread(target=worker) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM tahmin").fetchone()[0], 1)
        self.assertEqual(sorted(paths).count("yeni"), 1)

    def test_reliability_needs_independent_days(self):
        g = None
        for i in range(40):                                             # 40 tahmin, hepsi AYNI giriş günü
            cur = self.conn.execute(
                "INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
                "parametre_surum,olasilik,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,komisyon_pct,"
                "kayma_pct,maliyet_protokol) VALUES(?,?,?,?,?,'m','f','p',0.3,'t',10,10.3,9,12,13,1,?,0.2,0.1,?)",
                (f"k{i}", f"T{i}", "2026-01-01", "2026-01-02", "2026-01-01T18:30:00+03:00", defter.KURAL_SURUM,
                 defter.MALIYET_PROTOKOL))
            self.conn.execute("INSERT INTO tahmin_sonuc(tahmin_id,sonuc_turu,tp1_goruldu,tp1_olayi,r,net_getiri_pct,"
                              "degerlendirme_zamani,kural_surum) VALUES(?,'tamamlandi',0,0,-1,-2,'z',?)",
                              (cur.lastrowid, defter.KURAL_SURUM))
        self.conn.commit()
        g = next(x["grup"] for x in defter.gruplar(self.conn) if x["grup"]["model_surum"] == "m")
        o = defter.ozet(self.conn, g)
        self.assertEqual((o["olculen"], o["bagimsiz_gun"]), (40, 1))
        self.assertIn("karar verilmez", o["guven"])


class S1Yeniden(Base):
    """s1 kuralıyla yazılmış nihai sonuç DEĞİŞTİRİLMEZ; s2 değerlendirmesi ayrı, sürümlü kayıt olarak eklenir."""
    def test_s1_row_kept_and_s2_evaluation_added(self):
        self.store()
        src = self.conn.execute("SELECT id FROM tahmin").fetchone()[0]
        # canlıdaki v1 kaydı gibi: sözleşmesiz tahmin + s1 sonucu (yalnız tp1_goruldu; doğrudan TP2'de 0)
        cur = self.conn.execute("INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,"
                                "ozellik_surum,parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun) "
                                "SELECT 'v1kaydi',ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
                                "parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun FROM tahmin "
                                "WHERE id=?", (src,))
        tid = cur.lastrowid
        e, a = self.e, self.atr
        self.add_bars([(self.gday, e, e + a, e - a, e), (next_wd(self.gday), e + 7 * a, e + 7.5 * a, e + 6.5 * a, e + 7 * a)])
        self.conn.execute("INSERT INTO tahmin_sonuc(tahmin_id,sonuc_turu,tp1_goruldu,sl_goruldu,cikis_nedeni,islem_gunu,"
                          "net_getiri_pct,r,degerlendirme_zamani,kural_surum,ayrinti_json) VALUES(?,'tamamlandi',0,0,'TP2',2,"
                          "5,2.5,'z','s1',?)", (tid, json.dumps({"komisyon_pct": 0.2, "kayma_pct": 0.1})))
        self.conn.commit()
        once = self.conn.execute("SELECT * FROM tahmin_sonuc WHERE tahmin_id=?", (tid,)).fetchall()
        defter.sonuclandir(self.conn, at(next_wd(self.gday, 5), "18:30"))
        self.assertEqual(self.conn.execute("SELECT * FROM tahmin_sonuc WHERE tahmin_id=?", (tid,)).fetchall(), once)
        d = dict(self.conn.execute("SELECT * FROM tahmin_degerlendirme WHERE tahmin_id=?", (tid,)).fetchone())
        self.assertEqual((d["kural_surum"], d["tp1_olayi"], d["maliyet_kaynagi"], d["komisyon_pct"]),
                         (defter.KURAL_SURUM, 1, "s1_sonuclandirma_ayari", 0.2))
        g = next(x["grup"] for x in defter.gruplar(self.conn) if x["grup"]["maliyet_protokol"] == "eksik")
        o = defter.ozet(self.conn, g)
        self.assertEqual((o["olculen"], o["metrik"]["tp1_%"]), (1, 100.0))   # ölçüm s2 değerlendirmesini kullanır


V1_SCHEMA = (ROOT / "tests" / "veri" / "tahmin_v1_semasi.sql")


class GocV2(unittest.TestCase):
    def test_v1_to_v2_migration_with_backup(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "data" / "bist_haber.db"
            c = db.connect(p)
            for tb in ("defter_olay", "tahmin_degerlendirme", "tahmin_sonuc", "tahmin"):
                c.execute(f"DROP TABLE IF EXISTS {tb}")
            c.executescript(V1_SCHEMA.read_text(encoding="utf-8"))     # FAZ 1 v1 şeması (canlıdaki)
            c.execute("INSERT INTO news(id,source,published_at,effective_date,title,status,fetched_at) "
                      "VALUES('kap:1','kap','2026-01-01','2026-01-01','t','new','x')")
            c.execute("INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
                      "parametre_surum,olasilik,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun) "
                      "VALUES('v1','A','2026-01-01','2026-01-02','z','m','f','p',0.3,'t',1,1,1,1,1,1)")
            c.commit()
            once = hashlib.sha256(repr([tuple(r) for r in c.execute("SELECT * FROM tahmin")]).encode()).hexdigest()
            c.close()
            c = db.connect(p)
            g = dict(db.TAHMIN_GOC)
            self.assertEqual(g["durum"], "guncellendi_v2")
            self.assertTrue(Path(g["yedek"]).exists())
            yc = sqlite3.connect(g["yedek"])
            self.assertEqual(yc.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertNotIn("kural_surum", {r[1] for r in yc.execute("PRAGMA table_info(tahmin)")})   # yedek v1 hâli
            yc.close()
            cols = {r[1] for r in c.execute("PRAGMA table_info(tahmin)")}
            self.assertTrue({"kural_surum", "komisyon_pct", "kayma_pct", "maliyet_protokol"} <= cols)
            row = c.execute("SELECT * FROM tahmin").fetchone()
            self.assertEqual(row["kural_surum"], None)                  # eski kayıt doldurulmadı
            n = len(c.execute("PRAGMA table_info(tahmin)").fetchall())
            self.assertEqual(hashlib.sha256(repr([tuple(row)[:n - 4]]).encode()).hexdigest(), once)  # eski alanlar aynı
            with self.assertRaises(sqlite3.DatabaseError):
                c.execute("UPDATE tahmin SET olasilik=0.9")
            c.rollback()
            c.close()
            c = db.connect(p)
            self.assertEqual(db.TAHMIN_GOC["durum"], "var")             # ikinci açılışta tekrar yok
            c.close()


if __name__ == "__main__":
    unittest.main()
