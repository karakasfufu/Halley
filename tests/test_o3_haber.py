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
    def kap_tam(self, bugun_saat="2026-11-16T11:30:00+03:00"):
        """13–15.11 listeleri gün bittikten sonra alınmış (eksiksiz), bugünün listesi bugün alınmış."""
        for g in ("2026-11-13", "2026-11-14", "2026-11-15"):
            self.conn.execute("INSERT INTO kap_coverage(day, listed_at) VALUES(?, '2026-11-16T09:00:00+03:00')", (g,))
        self.conn.execute("INSERT INTO kap_coverage(day, listed_at) VALUES('2026-11-16', ?)", (bugun_saat,))
        self.conn.commit()

    def test_collection_is_not_analysis(self):
        an = t("2026-11-16T12:00")
        self.kap_tam("2026-11-16T10:30:00+03:00")
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
        self.conn.commit()
        self.kap_tam()
        g = hk.guncellik(self.conn, t("2026-11-16T12:00"))
        self.assertEqual((g["seviye"], g["bekleyen_kapsamda"]), ("tamam", 0))   # son analiz 11 gün önce ama bayat değil
        self.assertTrue(g["tam_guncel"])
        self.assertTrue(g["durum"].startswith("güncel"))

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
        self.assertTrue(g["durum"].startswith("toplama eksik"))
        self.assertFalse(g["tam_guncel"])

    def test_current_textless_news_is_coverage_gap_not_fresh(self):
        """O3 düzeltmesi: analiz bekleyen yok ama güncel bir haberin metni alınamamış → 'kapsam eksik', güncel DEĞİL."""
        self.kap_tam()
        self.haber("kap:metinsiz", "2026-11-16T09:00:00+03:00", body=None)
        g = hk.guncellik(self.conn, t("2026-11-16T12:00"))
        self.assertEqual(g["bekleyen_kapsamda"], 0)
        self.assertTrue(g["durum"].startswith("kapsam eksik"))
        self.assertIn("İÇERMİYOR", g["durum"])
        self.assertEqual((g["seviye"], g["tam_guncel"]), ("uyari", False))

    def test_missing_or_partial_kap_day_blocks_fresh_claim(self):
        self.kap_tam()
        self.conn.execute("DELETE FROM kap_coverage WHERE day='2026-11-14'")                   # gün hiç alınmamış
        self.conn.execute("UPDATE kap_coverage SET listed_at='2026-11-13T15:00:00+03:00' WHERE day='2026-11-13'")
        self.conn.commit()                                                                       # 13.11 gün bitmeden
        g = hk.guncellik(self.conn, t("2026-11-16T12:00"))
        self.assertEqual(g["toplama_bosluk_gunleri"], ["2026-11-13", "2026-11-14"])
        self.assertTrue(g["durum"].startswith("toplama eksik"))
        self.assertFalse(g["tam_guncel"])

    def test_unverified_calendar_blocks_fresh_claim(self):
        an = t("2027-03-10T12:00")
        k = hk.kapsam_baslangici(an)
        d = k["baslangic"].date()
        while d <= an.date():
            self.conn.execute("INSERT INTO kap_coverage(day, listed_at) VALUES(?, '2027-03-10T11:00:00+03:00')",
                              (d.isoformat(),))
            d += timedelta(days=1)
        self.conn.commit()
        g = hk.guncellik(self.conn, an)
        self.assertEqual(g["eksikler"], ["takvim doğrulanmadı"])
        self.assertFalse(g["tam_guncel"])


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


# ============================================================================ O3 düzeltmesi: muhafazakâr rezervasyon
import subprocess  # noqa: E402
import sys  # noqa: E402
import textwrap  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import httpx  # noqa: E402
import openai  # noqa: E402

from bist_haber import ai_comment, ai_service, harcama  # noqa: E402


def _istek():
    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def kotu_istek(mesaj):
    return openai.BadRequestError(mesaj, response=httpx.Response(400, request=_istek()), body=None)


class SahteIstemci:
    """OpenAI istemcisini taklit eder (ağ YOK). Her çağrının kwargs'ı kaydedilir; verilen hatalar sırayla atılır."""

    def __init__(self, girdi=1000, cikti=7000, hatalar=(), kullanim=True, bekle=0.0):
        self.girdi, self.cikti, self.hatalar, self.kullanim, self.bekle = girdi, cikti, list(hatalar), kullanim, bekle
        self.kwargs, self._k = [], threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    @property
    def cagri(self):
        return len(self.kwargs)

    def _parse(self, **kw):
        with self._k:
            self.kwargs.append(kw)
            hata = self.hatalar.pop(0) if self.hatalar else None
        if self.bekle:
            time.sleep(self.bekle)
        if hata is not None:
            raise hata
        sema = kw["response_format"]
        if sema is analyzer.FullAnalysis:
            parsed = analysis()
        elif sema is analyzer.FilterResult:
            parsed = analyzer.FilterResult(onemli=True, neden="önemli")
        else:
            parsed = sema(ozet="Özet", dikkat=[], riskler=[])
        u = SimpleNamespace(prompt_tokens=self.girdi, completion_tokens=self.cikti) if self.kullanim else None
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed, refusal=None))], usage=u)


class Rezervasyon(Temel):
    def butce(self, aylik=10.0, gunluk=None):
        return harcama.Butce("haber", str(self.tmp / "h.db"), aylik, gunluk)

    def defter(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM harcama_rezervasyon ORDER BY id")]

    def haberler(self, n):
        simdi = datetime.now(TR)
        for i in range(n):
            self.haber(f"kap:{i}", (simdi - timedelta(minutes=30 + i)).isoformat(timespec="seconds"))
        return analyzer.pending(self.conn)

    def test_expensive_first_call_cannot_exceed_daily_cap(self):
        """İlk çağrı pahalı (15.000 çıktı tokenı ≈ 0,030 $): eski 'gözlenen maliyet' yöntemi burada aşabiliyordu."""
        ist = SahteIstemci(cikti=15000)
        llm = ai_service.LLM("haber_analizi", client=ist, butce=self.butce(10.0, 0.20))
        s = analyzer.analyze(self.conn, UNI, rows=self.haberler(12), llm=llm, budget_usd=10.0, gunluk_butce_usd=0.20,
                             on_eleme=False, quality="ekonomik")
        gercek = s["analyzed"] * (1000 * 0.25e-6 + 15000 * 2e-6)
        self.assertGreaterEqual(s["analyzed"], 1)
        self.assertGreater(s["butce_disi"], 0)
        self.assertLessEqual(gercek, 0.20)                                     # gerçek harcama sınırın içinde
        self.assertLessEqual(harcama.harcanan(self.conn, "haber")["gun"]["toplam"], 0.20 + 1e-9)
        self.assertEqual(ist.cagri, s["analyzed"])
        for kw in ist.kwargs:                                                  # çıktı API'de sınırlı
            self.assertEqual(kw["max_completion_tokens"], harcama.MAX_CIKTI)
        d = self.defter()
        self.assertTrue(all(r["durum"] in ("tamam", "zarf_kapali") for r in d))
        self.assertTrue(all(r["kayda_gecti"] == 1 for r in d if r["durum"] == "tamam"))     # çift sayım yok
        self.assertAlmostEqual(harcama.harcanan(self.conn, "haber")["gun"]["toplam"], gercek, places=6)

    def test_two_call_profile_reserved_before_job_starts(self):
        """'yuksek' profil (ikinci görüş) iki çağrı gerektirebilir: bütçe bir çağrıya yetip ikincisine yetmiyorsa iş
        HİÇ başlatılmaz (yarım iş için para harcanmaz)."""
        rows = self.haberler(1)
        ist = SahteIstemci()
        llm = ai_service.LLM("haber_analizi", client=ist, butce=self.butce(10.0, None))
        q2 = analyzer.quality_profile("yuksek")
        self.assertTrue(q2["second_opinion"])
        for k in ("temperature", "reasoning_effort"):
            llm._supported.add((config.MODEL_ANALYSIS, k))
        tek = analyzer.is_ust_siniri(llm, rows[0], UNI, {}, dict(q2, second_opinion=False))
        iki = analyzer.is_ust_siniri(llm, rows[0], UNI, {}, q2)
        self.assertAlmostEqual(iki, 2 * tek)
        gunluk = (tek + iki) / 2                                               # bir çağrıya yeter, ikisine yetmez
        llm.butce = self.butce(10.0, gunluk)
        s = analyzer.analyze(self.conn, UNI, rows=rows, llm=llm, budget_usd=10.0, gunluk_butce_usd=gunluk,
                             on_eleme=False, quality="yuksek")
        self.assertEqual((ist.cagri, s["analyzed"], s["butce_disi"]), (0, 0, 1))
        self.assertEqual(self.conn.execute("SELECT status FROM news").fetchone()[0], "new")   # hata sayılmadı
        self.assertIn("işin", s["butce_durdu"])

    def test_retry_gets_own_reservation_and_uncertain_cost_is_not_zero(self):
        rows = self.haberler(1)
        ist = SahteIstemci(hatalar=[kotu_istek("Unsupported parameter: 'temperature'")])
        llm = ai_service.LLM("haber_analizi", client=ist, butce=self.butce(10.0, 1.0))
        s = analyzer.analyze(self.conn, UNI, rows=rows, llm=llm, budget_usd=10.0, gunluk_butce_usd=1.0, on_eleme=False,
                             quality="ekonomik")
        self.assertEqual((s["analyzed"], ist.cagri), (1, 2))
        self.assertIn("temperature", ist.kwargs[0])
        self.assertNotIn("temperature", ist.kwargs[1])                         # parametre çıkarılıp yeniden denendi
        cagrilar = [r for r in self.defter() if r["zarf_id"]]
        self.assertEqual([r["durum"] for r in cagrilar], ["belirsiz", "tamam"])  # her deneme ayrı rezervasyon
        h = harcama.harcanan(self.conn, "haber")["gun"]
        self.assertAlmostEqual(h["toplam"], BIR_CAGRI + cagrilar[0]["rezerve_usd"], places=9)   # belirsiz TAM sayılır
        self.assertEqual(h["belirsiz_adet"], 1)
        zarf = [r for r in self.defter() if r["durum"] == "zarf_kapali"][0]     # zarf ek denemeyi de kapsıyordu
        self.assertLessEqual(sum(r["rezerve_usd"] for r in cagrilar), zarf["rezerve_usd"] + 1e-12)

    def test_timeout_and_missing_usage_counted_in_full(self):
        rows = self.haberler(2)
        ist = SahteIstemci(hatalar=[openai.APITimeoutError(request=_istek())])
        llm = ai_service.LLM("haber_analizi", client=ist, butce=self.butce(10.0, 1.0))
        with patch.object(config, "ANALYSIS_WORKERS", 1):
            s = analyzer.analyze(self.conn, UNI, rows=rows, llm=llm, budget_usd=10.0, gunluk_butce_usd=1.0,
                                 on_eleme=False, quality="ekonomik")
        self.assertEqual((s["errors"], s["analyzed"]), (1, 1))
        d = [r for r in self.defter() if r["zarf_id"]]
        self.assertEqual([r["durum"] for r in d], ["belirsiz", "tamam"])
        h = harcama.harcanan(self.conn, "haber")["gun"]
        self.assertAlmostEqual(h["toplam"], BIR_CAGRI + d[0]["rezerve_usd"], places=9)
        ist2 = SahteIstemci(kullanim=False)                                    # kullanım bilgisi dönmezse de belirsiz
        llm2 = ai_service.LLM("x", client=ist2, butce=self.butce(10.0, 1.0))
        llm2.parse(config.MODEL_ANALYSIS, "s", "u", analyzer.FullAnalysis)
        self.assertEqual(self.defter()[-1]["durum"], "belirsiz")

    def test_crashed_process_leftovers_are_counted(self):
        """Süreç kapanırsa açık çağrı rezervasyonu ve açık iş zarfı TAMAMIYLA harcanmış sayılır."""
        b = self.butce(1.0, 0.50)
        z = harcama.zarf_ac(b, 0.10, "x")
        harcama.rezerve(b, 0.04, "x", zarf_id=z)                 # zarfın içinden; kapanmadan süreç "öldü"
        harcama.rezerve(b, 0.03, "y")                            # zarfsız açık çağrı
        h = harcama.harcanan(self.conn, "haber")["gun"]
        self.assertAlmostEqual(h["toplam"], 0.10 + 0.03)         # zarf (0,04 içinde) + 0,03; çift sayım yok
        self.assertAlmostEqual(harcama.kalan(self.conn, b)["kalan"], 0.50 - 0.13)
        with self.assertRaises(harcama.ButceYetersiz):
            harcama.rezerve(b, 0.07, "x", zarf_id=z)             # zarfın kalanı 0,06: aşan çağrı yapılmaz
        harcama.zarf_kapat(b.db_path, z)                          # kapanınca yalnız çağrı rezervasyonları kalır
        self.assertAlmostEqual(harcama.harcanan(self.conn, "haber")["gun"]["toplam"], 0.04 + 0.03)

    def test_concurrent_threads_cannot_double_spend(self):
        b = self.butce(10.0, 0.10)
        ok, k = [], threading.Lock()

        def dene():
            try:
                harcama.rezerve(b, 0.03, "t")
                with k:
                    ok.append(1)
            except harcama.ButceYetersiz:
                pass
        th = [threading.Thread(target=dene) for _ in range(10)]
        for x in th:
            x.start()
        for x in th:
            x.join()
        self.assertEqual(len(ok), 3)                              # 3 × 0,03 = 0,09 ≤ 0,10; dördüncü sığmaz
        self.assertLessEqual(harcama.harcanan(self.conn, "haber")["gun"]["toplam"], 0.10)

    def test_concurrent_processes_cannot_double_spend(self):
        kok = Path(__file__).resolve().parents[1]
        baslangic = time.time() + 4.0
        kod = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(kok)!r})
            from bist_haber import harcama
            b = harcama.Butce("haber", {str(self.tmp / 'h.db')!r}, 0.20, None)
            while time.time() < {baslangic!r}:
                time.sleep(0.005)
            ok = 0
            for _ in range(4):
                try:
                    harcama.rezerve(b, 0.03, "surec")
                    ok += 1
                except harcama.ButceYetersiz:
                    pass
            print(ok)
        """)
        ps = [subprocess.Popen([sys.executable, "-c", kod], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
              for _ in range(4)]
        sonuc = [p.communicate(timeout=120) for p in ps]
        self.assertTrue(all(p.returncode == 0 for p in ps), [e for _, e in sonuc])
        self.assertEqual(sum(int(o.strip()) for o, _ in sonuc), 6)   # 16 denemeden 6'sı: 0,18 ≤ 0,20
        self.assertLessEqual(harcama.harcanan(self.conn, "haber")["ay"]["toplam"], 0.20 + 1e-9)
        self.assertEqual(len({r["pid"] for r in self.defter()}) > 1, True)   # gerçekten farklı süreçler yazdı

    def test_missing_monthly_param_uses_production_budget(self):
        """Aylık bütçe parametresi verilmese de üretim bütçesi uygulanır; sessizce sınırsız olmaz."""
        rows = self.haberler(10)
        ist = SahteIstemci(cikti=15000)
        with patch.object(pipeline, "news_budget", return_value=0.15), patch.object(hk, "gunluk_butce", return_value=5.0), \
                patch("openai.OpenAI", return_value=ist) as yapici:
            s = analyzer.analyze(self.conn, UNI, rows=rows, on_eleme=False, quality="ekonomik")   # bütçe YOK, llm YOK
        yapici.assert_called_once_with(max_retries=0)              # istemcinin iç yeniden denemesi kapalı
        self.assertGreater(s["butce_disi"], 0)
        self.assertLessEqual(harcama.harcanan(self.conn, "haber")["ay"]["toplam"], 0.15 + 1e-9)
        self.assertLessEqual(ist.cagri * (1000 * 0.25e-6 + 15000 * 2e-6), 0.15)
        with patch.object(pipeline, "news_budget", return_value=0.0):   # sahte LLM + parametre yok → yine üretim bütçesi
            s0 = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=SahteLLM(), on_eleme=False,
                                  quality="ekonomik")
        self.assertEqual(s0["analyzed"], 0)
        with patch.object(pipeline, "news_budget", return_value=0.0):   # açık test istisnası
            s1 = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn)[:1], llm=SahteLLM(), on_eleme=False,
                                  quality="ekonomik", butcesiz_izin=True)
        self.assertEqual(s1["analyzed"], 1)

    def test_real_client_without_budget_refuses(self):
        GercekGibi = type("OpenAI", (), {"__module__": "openai._client"})
        istemci = GercekGibi()
        istemci.chat = SimpleNamespace(completions=SimpleNamespace(parse=lambda **k: self.fail("çağrı yapılmamalıydı")))
        llm = ai_service.LLM("x", client=istemci)
        with self.assertRaises(harcama.ButceKorumasiYok):
            llm.parse(config.MODEL_ANALYSIS, "s", "u", analyzer.FullAnalysis)
        import sqlite3
        mem = sqlite3.connect(":memory:")
        with self.assertRaises(harcama.ButceKorumasiYok):              # bellek içi veritabanında rezervasyon yok
            harcama.uretim_butcesi(mem, "haber")

    def test_cheap_test_and_comment_go_through_reservation(self):
        self.haberler(1)
        ist = SahteIstemci()
        with patch.object(pipeline, "news_budget", return_value=1.0), patch.object(hk, "gunluk_butce", return_value=1.0), \
                patch("openai.OpenAI", return_value=ist):
            r = analyzer.test_one(self.conn, UNI)
        self.assertIsNotNone(r)
        d = [x for x in self.defter() if x["zarf_id"]]
        self.assertEqual([(x["durum"], x["kayda_gecti"]) for x in d], [("tamam", 0)])   # kaydedilmez → defterde sayılır
        self.assertAlmostEqual(harcama.harcanan(self.conn, "haber")["gun"]["toplam"], BIR_CAGRI)
        ist2 = SahteIstemci(girdi=5000, cikti=3000)
        with patch.object(config, "DATA", self.tmp), patch("openai.OpenAI", return_value=ist2):
            c = ai_comment.comment_report(self.conn, "aksam", "2026-11-16_aksam", "XU100 +1.32", {"yz_butce_usd": 1.0})
        self.assertTrue(c["ok"], c)
        y = self.conn.execute("SELECT durum, kayda_gecti FROM harcama_rezervasyon WHERE kategori='yz_yorum'").fetchall()
        self.assertEqual([tuple(x) for x in y], [("tamam", 1)])
        self.assertAlmostEqual(harcama.harcanan(self.conn, "yz_yorum")["ay"]["toplam"], c["usd"])
