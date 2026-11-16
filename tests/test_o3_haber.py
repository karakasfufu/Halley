"""O3 (16.11.2026): haber güncellik göstergesi, işlem günü kapsamı, tekrar eleme, başarısız analiz, günlük + aylık
bütçe, eşzamanlılık kilidi, sonradan analiz işareti ve bekçinin ücretli analizinin kapalı kalması.
Yapay zekâ TAKLİT edilir (sahte istemci; "ekonomik" profilde haber başına tek çağrı); gerçek ücretli çağrı YOKTUR."""
import shutil
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import analyzer, config, db, haber_kapsam as hk, pipeline

from test_accuracy import analysis

TR = config.TR_TZ
UNI = {"TEST": "Deneme", "ABC": "Abc"}
BIR_CAGRI = 1000 * 0.25e-6 + 7000 * 2e-6       # sahte istemcinin bir çağrısının gerçekleşen maliyeti


class SahteLLM:
    def __init__(self, bekle=0.0, hata=None):
        self.cagri, self.bekle, self.hata = 0, bekle, hata
        self._k = threading.Lock()

    def parse(self, model, system, user, schema, reasoning_effort=None):
        with self._k:
            self.cagri += 1
        if self.bekle:
            time.sleep(self.bekle)
        if self.hata:
            raise self.hata
        return analysis(), 1000, 7000


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=TR)


class Temel(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.conn = db.connect(self.tmp / "h.db")
        self.kilit = patch.object(hk, "KILIT_YOLU", self.tmp / "haber_analiz.kilit")
        self.kilit.start()

    def tearDown(self):
        self.kilit.stop()
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def haber(self, nid, yayin, body="metin " * 50, baslik=None, durum="new", fetched="2026-11-16T10:00:00+03:00"):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,subject,fetched_at,"
                          "status) VALUES(?,'kap',?,?,?,?,'TEST','Yeni İş İlişkisi',?,?)",
                          (nid, yayin, yayin[:10], baslik or f"Sözleşme {nid}", body, fetched, durum))
        self.conn.commit()


class Kapsam(unittest.TestCase):
    def test_monday_covers_friday_and_monday(self):
        k = hk.kapsam_baslangici(t("2026-11-16T10:00"))            # Pazartesi
        self.assertEqual(k["is_gunleri"], ["2026-11-13", "2026-11-16"])
        self.assertEqual(k["baslangic_iso"], "2026-11-13T00:00:00+03:00")   # hafta sonu haberleri de kapsamda

    def test_weekend_covers_last_two_trading_days(self):
        self.assertEqual(hk.kapsam_baslangici(t("2026-11-15T12:00"))["is_gunleri"], ["2026-11-12", "2026-11-13"])

    def test_holiday_and_half_day(self):
        k = hk.kapsam_baslangici(t("2026-10-30T09:00"))             # 29.10 tatil, 28.10 arefe yarım gün
        self.assertEqual(k["is_gunleri"], ["2026-10-28", "2026-10-30"])
        self.assertEqual(k["yarim_gun"], ["2026-10-28"])
        k2 = hk.kapsam_baslangici(t("2026-05-30T09:00"))            # Kurban Bayramı 27–29.05 kapalı (Cumartesi)
        self.assertEqual(k2["is_gunleri"], ["2026-05-25", "2026-05-26"])

    def test_unknown_calendar_warns(self):
        self.assertIsNone(hk.kapsam_baslangici(t("2026-11-16T10:00"))["uyari"])
        self.assertIn("dini bayram", hk.kapsam_baslangici(t("2027-03-10T10:00"))["uyari"])


class Guncellik(Temel):
    def test_collection_is_not_analysis(self):
        an = t("2026-11-16T12:00")
        self.haber("kap:1", "2026-11-16T09:00:00+03:00", fetched="2026-11-16T11:00:00+03:00")
        g = hk.guncellik(self.conn, an)
        self.assertEqual(g["son_toplama"], "2026-11-16T11:00:00+03:00")
        self.assertIsNone(g["son_basarili_analiz"])                   # toplandı ama analiz edilmedi
        self.assertEqual(g["bekleyen_kapsamda"], 1)
        self.assertEqual(g["seviye"], "uyari")
        self.assertIn("İÇERMİYOR", g["durum"])

    def test_old_last_analysis_not_stale_when_nothing_pending(self):
        self.haber("kap:1", "2026-11-05T09:00:00+03:00", durum="analyzed")
        self.conn.execute("INSERT INTO analyses(news_id,stage,model,result_json,input_tokens,output_tokens,created_at) "
                          "VALUES('kap:1','full','m','{}',1,1,'2026-11-05T10:00:00+03:00')")
        self.conn.execute("INSERT INTO kap_coverage(day, listed_at) VALUES('2026-11-16','2026-11-16T11:30:00+03:00')")
        self.conn.commit()
        g = hk.guncellik(self.conn, t("2026-11-16T12:00"))
        self.assertEqual((g["seviye"], g["bekleyen_kapsamda"]), ("tamam", 0))   # son analiz 11 gün önce ama bayat değil

    def test_old_and_textless_counted_separately_not_analyzed(self):
        self.haber("kap:eski", "2026-11-06T09:00:00+03:00")
        self.haber("kap:metinsiz", "2026-11-16T09:00:00+03:00", body=None)
        self.haber("kap:metinsiz_eski", "2026-11-02T09:00:00+03:00", body="")
        g = hk.guncellik(self.conn, t("2026-11-16T12:00"))
        self.assertEqual((g["kapsam_disi_eski"], g["metinsiz_kapsamda"], g["metinsiz_eski"], g["bekleyen_kapsamda"]),
                         (1, 1, 1, 0))
        self.assertEqual(self.conn.execute("SELECT status FROM news WHERE id='kap:eski'").fetchone()[0], "new")  # silinmez
        self.assertIn("metni", g["not"])

    def test_collection_older_than_scope_is_warned(self):
        self.haber("kap:1", "2026-11-06T09:00:00+03:00", durum="analyzed", fetched="2026-11-06T10:00:00+03:00")
        g = hk.guncellik(self.conn, t("2026-11-16T12:00"))
        self.assertIn("toplama eski", g["durum"])


class Butce(Temel):
    def test_daily_cap_more_restrictive_than_monthly(self):
        simdi = datetime.now(TR)
        for i in range(10):
            self.haber(f"kap:{i}", (simdi - timedelta(hours=1)).isoformat(timespec="seconds"))
        d = hk.butce_durumu(self.conn, 10.0, 0.05)
        self.assertEqual((d["sinirlayan"], d["kalan"]), ("günlük", 0.05))
        llm = SahteLLM()
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=llm, budget_usd=10.0,
                             gunluk_butce_usd=0.05, on_eleme=False, quality="ekonomik")
        self.assertLessEqual(hk.gun_harcamasi(self.conn), 0.05 + 1e-9)
        self.assertGreater(s["butce_disi"], 0)
        self.assertEqual(s["butce_sinirlayan"], "günlük")
        self.assertEqual(llm.cagri, s["analyzed"])
        self.assertAlmostEqual(s["gerceklesen_usd"], s["analyzed"] * BIR_CAGRI, places=4)   # gerçekleşen
        self.assertIn("tahmini_ust_usd", s)          # tahmin ayrı raporlanır; ilk haberde gerçekleşenin altında kalabilir

    def test_monthly_cap_more_restrictive_than_daily(self):
        simdi = datetime.now(TR)
        self.conn.execute("INSERT INTO analyses(news_id,stage,model,result_json,input_tokens,output_tokens,created_at) "
                          "VALUES('x','full','m','{}',0,4990000,?)", ((simdi - timedelta(days=1)).isoformat(),)
                          if simdi.day > 1 else (simdi.isoformat(),))
        self.conn.commit()
        d = hk.butce_durumu(self.conn, 10.0, 0.50)
        if simdi.day > 1:
            self.assertEqual(d["sinirlayan"], "aylık")
            self.assertAlmostEqual(d["kalan"], 10.0 - 9.98, places=6)

    def test_zero_budget_no_call(self):
        self.haber("kap:1", datetime.now(TR).isoformat(timespec="seconds"))
        llm = SahteLLM()
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=llm, budget_usd=10.0,
                             gunluk_butce_usd=0.0, on_eleme=False, quality="ekonomik")
        self.assertEqual((llm.cagri, s.get("analyzed", 0)), (0, 0))


class TekrarVeHata(Temel):
    def test_duplicates_removed_before_paid_call(self):
        simdi = datetime.now(TR).isoformat(timespec="seconds")
        self.haber("kap:a", simdi, baslik="Aynı başlık", body="aynı metin " * 40)
        self.haber("kap:b", simdi, baslik="Aynı başlık", body="aynı metin " * 40)
        llm = SahteLLM()
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=llm, budget_usd=10.0, on_eleme=False, quality="ekonomik")
        self.assertEqual((llm.cagri, s["analyzed"], s.get("tekrar")), (1, 1, 1))

    def test_failed_analysis_not_counted_as_success(self):
        self.haber("kap:1", datetime.now(TR).isoformat(timespec="seconds"))
        llm = SahteLLM(hata=RuntimeError("ağ hatası (taklit)"))
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=llm, budget_usd=10.0, on_eleme=False, quality="ekonomik")
        self.assertEqual((s["errors"], s["analyzed"]), (1, 0))
        self.assertEqual(self.conn.execute("SELECT status FROM news WHERE id='kap:1'").fetchone()[0], "error")
        self.assertIsNone(hk.guncellik(self.conn)["son_basarili_analiz"])
        self.assertEqual(s["gerceklesen_usd"], 0.0)


class Eszamanlilik(Temel):
    def test_parallel_requests_single_run_no_double_spend(self):
        simdi = datetime.now(TR).isoformat(timespec="seconds")
        for i in range(3):
            self.haber(f"kap:{i}", simdi)
        llm = SahteLLM(bekle=0.3)
        sonuc = []

        def calis():
            c = db.connect(self.tmp / "h.db")
            sonuc.append(analyzer.analyze(c, UNI, rows=analyzer.pending(c), llm=llm, budget_usd=10.0, on_eleme=False, quality="ekonomik"))
            c.close()

        iplik = [threading.Thread(target=calis) for _ in range(3)]
        for x in iplik:
            x.start()
        for x in iplik:
            x.join()
        kilitli = [s for s in sonuc if s.get("kilitli")]
        self.assertEqual(len(kilitli), 2)                                 # tıklama / rerun / ikinci sekme
        self.assertEqual(llm.cagri, 3)                                    # her haber BİR kez
        self.assertFalse((self.tmp / "haber_analiz.kilit").exists())     # kilit bırakıldı

    def test_cross_process_lock_file_and_stale_lock(self):
        y = self.tmp / "haber_analiz.kilit"
        y.write_text("{}", encoding="utf-8")                              # başka süreç çalışıyor
        self.haber("kap:1", datetime.now(TR).isoformat(timespec="seconds"))
        llm = SahteLLM()
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=llm, budget_usd=10.0, on_eleme=False, quality="ekonomik")
        self.assertIn("kilitli", s)
        self.assertEqual(llm.cagri, 0)
        eski = time.time() - hk.KILIT_BAYAT_SN - 10                       # çökmüş süreçten kalma bayat kilit
        import os
        os.utime(y, (eski, eski))
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=llm, budget_usd=10.0, on_eleme=False, quality="ekonomik")
        self.assertEqual(s["analyzed"], 1)


class SonradanVeBekci(Temel):
    def test_retroactive_analysis_flagged(self):
        self.haber("kap:eski", "2026-01-05T09:00:00+03:00")
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=SahteLLM(), budget_usd=10.0,
                             on_eleme=False, quality="ekonomik")
        self.assertEqual(s.get("sonradan_analiz"), 1)
        self.assertIn("sonradan_analiz", self.conn.execute("SELECT flag FROM impacts WHERE news_id='kap:eski'").fetchone()[0])

    def test_update_all_uses_trading_day_scope(self):
        simdi = datetime.now(TR)
        bas = hk.kapsam_baslangici(simdi)["baslangic"]
        self.haber("kap:guncel", (simdi - timedelta(minutes=5)).isoformat(timespec="seconds"))
        self.haber("kap:eski", (bas - timedelta(days=3)).isoformat(timespec="seconds"))
        yakalanan = {}

        def sahte_analyze(conn, uni, **k):
            yakalanan["rows"] = [r["id"] for r in k["rows"]]
            return {"analyzed": 0}
        with patch.object(pipeline, "universe", return_value=UNI), \
                patch.object(pipeline.kap, "collect", return_value={}), patch.object(pipeline.rss, "collect", return_value={}), \
                patch.object(pipeline.kap, "fetch_missing_bodies", return_value={}), \
                patch("bist_haber.kap_history.fill_gaps", return_value={}), \
                patch.object(pipeline, "has_api_key", return_value=True), \
                patch.object(pipeline.analyzer, "analyze", side_effect=sahte_analyze), \
                patch.object(pipeline.prices, "update", return_value=0):
            out = pipeline.update_all(self.conn, analysis_limit=10)
        self.assertEqual(yakalanan["rows"], ["kap:guncel"])
        self.assertEqual((out["analyze"]["waiting"], out["analyze"]["eski_bekleyen"]), (1, 1))

    def test_watchdog_paid_analysis_stays_off(self):
        from bist_haber import watchdog
        yakalanan = {}
        with patch.object(watchdog, "run_session", side_effect=lambda *a, **k: yakalanan.update(k) or {}), \
                patch.object(watchdog, "saved_settings", return_value={}), \
                patch.object(pipeline, "universe", return_value=UNI):
            watchdog.run_auto(self.conn, "aksam")
        self.assertIs(yakalanan["ai"], False)


if __name__ == "__main__":
    unittest.main()
