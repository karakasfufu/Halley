"""2026-11-06 pilot incelemesinden çıkan düzeltmelerin ücretsiz testleri."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bist_haber import analyzer, backtest, config, kap
from bist_haber.textutil import strip_translation
from test_accuracy import FakeClient, add_news, memory_db, seed_prices


BILINGUAL = """Özel Durum Açıklaması (Genel)
Material Event Disclosure General
Yapılan Açıklama Güncelleme mi?
Update Notification Flag
Evet (Yes)
Şirketimizin portföyünde yer alan Marmaris'teki Sinpaş Kızılbük projesi kapsamında 284 adet satış yapılmıştır.
Within the scope of the Marmaris Sinpaş Kızılbük Project included in our Company's portfolio, 284 units were sold.
This statement has been translated into English for informational purposes.
Kızılbük GYO A.Ş."""


class TranslationTests(unittest.TestCase):
    def test_english_lines_dropped_turkish_and_names_kept(self):
        out = strip_translation(BILINGUAL)
        self.assertIn("284 adet satış", out)
        self.assertIn("Kızılbük GYO A.Ş.", out)
        self.assertIn("Evet (Yes)", out)  # değer satırı korunur
        self.assertNotIn("Within the scope", out)
        self.assertNotIn("Update Notification Flag", out)
        self.assertNotIn("translated into English", out)

    def test_fully_english_document_is_not_emptied(self):
        text = ("The Company has signed a supply agreement with a total value of USD 10 million. "
                "The agreement is expected to contribute to the revenues of the Company.\n") * 3
        self.assertEqual(strip_translation(text), text)

    def test_clean_uses_translation_strip(self):
        self.assertNotIn("Within the scope", kap._clean(BILINGUAL))


class AttachmentSelectionTests(unittest.TestCase):
    def test_routine_and_english_copies_are_skipped(self):
        atts = [{"fileExtension": "pdf", "fileName": "ENERJİ YATIRIMLARI.pdf"},
                {"fileExtension": "pdf", "fileName": "ENERJİ YATIRIMLARI (ENG).pdf"},
                {"fileExtension": "pdf", "fileName": "İDEALİST GYO HAZİRUN CETVELİ.pdf"},
                {"fileExtension": "pdf", "fileName": "Özgeçmişler.pdf"}]
        keep, skipped = kap.select_attachments(atts)
        self.assertEqual([a["fileName"] for a in keep], ["ENERJİ YATIRIMLARI.pdf"])
        self.assertEqual(len(skipped), 3)

    def test_single_english_pdf_is_read(self):
        keep, skipped = kap.select_attachments([{"fileExtension": "pdf", "fileName": "Invitation to General Assembly.pdf"}])
        self.assertEqual(len(keep), 1)
        self.assertFalse(skipped)

    def test_all_routine_still_reads_first_instead_of_nothing(self):
        keep, _ = kap.select_attachments([{"fileExtension": "pdf", "fileName": "Hazirun.pdf"},
                                          {"fileExtension": "pdf", "fileName": "Vekaletname.pdf"}])
        self.assertEqual(len(keep), 1)


def _fetch(pages, attachments):
    reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=(lambda t=t: t)) for t in pages])
    with patch.object(kap, "_get", return_value=SimpleNamespace(text="page", content=b"%PDF")), \
            patch.object(kap, "_parse_page", return_value=("Belge metni " * 30, attachments)), \
            patch("pypdf.PdfReader", return_value=reader), patch("time.sleep"):
        return backtest.fetch_document(1, "Yeni İş İlişkisi")


class PilotDocumentTests(unittest.TestCase):
    def test_blank_last_page_is_a_note_not_a_blocker(self):
        body, issues = _fetch(["Sözleşme bedeli 10 milyon TL olarak belirlenmiştir."] * 2 + [""],
                              [{"fileExtension": "pdf", "objId": "x", "fileName": "Sözleşme.pdf"}])
        self.assertNotIn("PDF içinde metni okunamayan sayfa var.", issues)
        self.assertIn("imza/kaşe", body)

    def test_blank_middle_page_still_blocks(self):
        _, issues = _fetch(["Metin var.", "", "Metin var."],
                           [{"fileExtension": "pdf", "objId": "x", "fileName": "Sözleşme.pdf"}])
        self.assertIn("PDF içinde metni okunamayan sayfa var.", issues)

    def test_routine_attachments_do_not_trigger_count_limit(self):
        atts = [{"fileExtension": "pdf", "objId": "a", "fileName": "Birleşme Sözleşmesi.pdf"},
                {"fileExtension": "pdf", "objId": "b", "fileName": "Duyuru Metni.pdf"},
                {"fileExtension": "pdf", "objId": "c", "fileName": "Hazirun Cetveli.pdf"},
                {"fileExtension": "pdf", "objId": "d", "fileName": "Birleşme (ENG).pdf"}]
        body, issues = _fetch(["Birleşme oranı 1,25 olarak belirlenmiştir."], atts)
        self.assertNotIn("PDF ek sayısı okuma sınırını aşıyor.", issues)
        self.assertIn("ATLANAN RUTİN/ÇEVİRİ EKLER", body)


class RoutineSubjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = backtest.connect(Path(self.temp.name) / "pilot.db")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.conn.close)
        seed_prices(self.conn)

    def test_pilot_skips_routine_subject_without_spending(self):
        body = "Borsa yatırım fonu işlemi olmamıştır. " * 10
        add_news(self.conn, body=body, subject="Piyasa Yapıcılığı Kapsamında Gerçekleştirilen İşlemler Bildirimi")
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        self.conn.execute("INSERT INTO pilot_documents VALUES('kap:1',?,'[]',?,'now')",
                          (hashlib.sha256(body.encode()).hexdigest(), len(body)))
        self.conn.commit()
        client = FakeClient()
        result = backtest.analyze(self.conn, client=client)
        self.assertEqual(result["skipped_routine"], 1)
        self.assertFalse(client.calls)
        self.assertEqual(self.conn.execute("SELECT status FROM news").fetchone()[0], "new")  # silinmedi

    def test_daily_flow_skips_routine_subject(self):
        conn = memory_db()
        add_news(conn, body=None, subject="Piyasa Yapıcılığı Kapsamında Gerçekleştirilen İşlemler Bildirimi")
        self.assertEqual(kap.apply_skip_rules(conn), 1)
        self.assertEqual(conn.execute("SELECT status FROM news").fetchone()[0], "skipped")


class LockedDayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = backtest.connect(Path(self.temp.name) / "pilot.db")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.conn.close)
        seed_prices(self.conn)
        add_news(self.conn, published="2026-09-01T12:00:00+03:00")
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,"
                          "published_at,effective_date) VALUES('kap:1','TEST',1,3,.8,'orta','diger',"
                          "'2026-09-01T12:00:00+03:00','2026-09-01')")
        self.conn.commit()

    def test_single_price_exit_day_is_flagged_but_still_measured(self):
        # 3 günlük vadenin çıkışı 2026-09-04: gün boyu tek fiyat (taban kilidi gibi)
        self.conn.execute("UPDATE pilot_bars SET open=95,high=95,low=95,close=95 WHERE ticker='TEST' AND date='2026-09-04'")
        rows = {r["vade"]: r for r in backtest.evaluate(self.conn)}
        self.assertIn("çıkış günü tek fiyat", rows[3]["uygulanabilirlik"])
        self.assertIsNotNone(rows[3]["getiri_%"])
        self.assertEqual(rows[1]["uygulanabilirlik"], "")

    def test_normal_days_are_not_flagged(self):
        self.assertTrue(all(r["uygulanabilirlik"] == "" for r in backtest.evaluate(self.conn)))


STAMP = "Doğrulama Kodu: 8199240d-da90-49cc-baed-8c372a205c53https://spk.gov.tr/dokuman-dogrulama\n01  07"


def _reader(pages):
    return SimpleNamespace(pages=[SimpleNamespace(extract_text=(lambda t=t: t)) for t in pages])


class SubjectLimitTests(unittest.TestCase):
    def test_important_subjects_get_wider_limits_others_unchanged(self):
        big = config.reading_limits("Pay Alım Teklifi Yoluyla Pay Toplanmasına İlişkin Bildirim")
        self.assertEqual((big["attachment_chars"], big["pages"], big["attachments"], big["body_chars"]),
                         (30000, 25, 4, 60000))
        self.assertEqual(config.reading_limits("Birleşme İşlemlerine İlişkin Bildirim")["pages"], 25)
        gk = config.reading_limits("Genel Kurul İşlemlerine İlişkin Bildirim")
        self.assertEqual((gk["attachment_chars"], gk["attachments"], gk["body_chars"]), (8000, 4, 25000))
        default = config.reading_limits("Özel Durum Açıklaması (Genel)")
        self.assertEqual((default["attachment_chars"], default["pages"], default["attachments"],
                          default["body_chars"]),
                         (config.KAP_ATTACHMENT_CHARS, config.KAP_ATTACHMENT_PAGES,
                          config.KAP_MAX_ATTACHMENTS, config.MAX_BODY_CHARS))

    def test_long_tender_offer_passes_but_same_length_ordinary_is_flagged(self):
        pages = ["Pay alım teklifi fiyatı ve koşulları bu bölümde ayrıntılı olarak açıklanmıştır. " * 18] * 15
        atts = [{"fileExtension": "pdf", "objId": "x", "fileName": "Bilgilendirme Notu.pdf"}]
        with patch.object(kap, "_get", return_value=SimpleNamespace(text="page", content=b"%PDF")), \
                patch.object(kap, "_parse_page", return_value=("Belge metni " * 30, atts)), \
                patch("pypdf.PdfReader", return_value=_reader(pages)), patch("time.sleep"):
            _, important = backtest.fetch_document(1, "Pay Alım Teklifi Yoluyla Pay Toplanmasına İlişkin Bildirim")
            _, ordinary = backtest.fetch_document(1, "Özel Durum Açıklaması (Genel)")
        self.assertEqual(important, [])
        self.assertIn("PDF sayfa sınırını aşıyor.", ordinary)
        self.assertIn("PDF metni uzunluk sınırını aşıyor.", ordinary)


class ScannedPageTests(unittest.TestCase):
    def test_stamp_only_page_is_blank_but_number_table_is_not(self):
        from bist_haber.textutil import page_is_blank
        self.assertTrue(page_is_blank(STAMP))
        self.assertTrue(page_is_blank(""))
        self.assertFalse(page_is_blank("05/11/2026 472.450 0 472.450 11.526.639 11.999.089 6,00 6,00 6,25 6,25"))

    def _fetch(self, readers, names):
        atts = [{"fileExtension": "pdf", "objId": str(i), "fileName": n} for i, n in enumerate(names)]
        with patch.object(kap, "_get", return_value=SimpleNamespace(text="page", content=b"%PDF")), \
                patch.object(kap, "_parse_page", return_value=("Belge metni " * 30, atts)), \
                patch("pypdf.PdfReader", side_effect=readers), patch("time.sleep"):
            return backtest.fetch_document(1, "Pay Alım Teklifi Yoluyla Pay Toplanmasına İlişkin Bildirim")

    def test_scanned_form_next_to_readable_note_is_a_warning(self):
        readable = _reader(["Pay Alım Teklifi Fiyatı : 104,00 TL. Teklif süresi on iş günüdür. " * 20])
        scanned = _reader([STAMP] * 5)
        body, issues = self._fetch([readable, scanned], ["Bilgilendirme Notu.pdf", "Onaylı Bilgi Formu.pdf"])
        self.assertEqual(issues, [])
        self.assertIn("taranmış görüntü", body)
        self.assertIn("Onaylı Bilgi Formu.pdf", body)

    def test_only_scanned_attachments_still_block(self):
        _, issues = self._fetch([_reader([STAMP] * 5)], ["Onaylı Duyuru Metni.pdf"])
        self.assertIn("PDF içinde metni okunamayan sayfa var.", issues)

    def test_daily_reader_marks_scanned_attachment(self):
        atts = [{"fileExtension": "pdf", "objId": "x", "fileName": "SPK Onaylı İhraç Belgesi.pdf"}]
        with patch.object(kap, "_get", return_value=SimpleNamespace(content=b"%PDF")), \
                patch("pypdf.PdfReader", return_value=_reader([STAMP] * 3)), patch("time.sleep"):
            text = kap._attachment_texts(atts)
        self.assertIn("taranmış görüntü", text)
        self.assertNotIn("Doğrulama Kodu", text)


class DocumentCheckMigrationTests(unittest.TestCase):
    def test_old_clean_unanalyzed_documents_need_recheck_analyzed_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pilot.db"
            conn = backtest.connect(path)
            add_news(conn, nid="kap:1", body="Eski kurallarla temiz " * 10)
            add_news(conn, nid="kap:2", body="Analiz edilmiş " * 10)
            conn.execute("UPDATE news SET status='analyzed' WHERE id='kap:2'")
            for nid in ("kap:1", "kap:2"):
                conn.execute("INSERT INTO pilot_documents VALUES(?,'h','[]',200,'now')", (nid,))
            backtest._meta(conn, "document_check_version", 1)  # eski kurallarla hazırlanmış veritabanı
            conn.commit()
            conn.close()
            conn = backtest.connect(path)
            issues = dict(conn.execute("SELECT news_id, issues FROM pilot_documents").fetchall())
            self.assertIn("yeniden denetlenmeli", issues["kap:1"])
            self.assertEqual(issues["kap:2"], "[]")
            client = FakeClient()
            self.assertEqual(backtest.analyze(conn, client=client)["analyzed"], 0)
            self.assertFalse(client.calls)
            conn.close()
            conn = backtest.connect(path)  # ikinci açılış tekrar işaretlemez
            self.assertEqual(backtest.metadata(conn)["document_check_version"], backtest.DOCUMENT_CHECK_VERSION)
            conn.close()


class ReportTextTests(unittest.TestCase):
    def test_gap_messages_with_semicolon_stay_whole_and_row_count_is_dynamic(self):
        from bist_haber import pilot_export
        with tempfile.TemporaryDirectory() as temp:
            conn = backtest.connect(Path(temp) / "pilot.db")
            add_news(conn, nid="kap:1")
            conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
            conn.execute("INSERT INTO pilot_documents VALUES('kap:1','h',?,1,'now')",
                         ('["PDF okunamadı; resim/bozuk/şifreli olabilir.", "PDF sayfa sınırını aşıyor."]',))
            conn.commit()
            row = {"bildirim": "kap:1", "hisse": "TEST", "yön": 1, "vade": 1, "giriş": "2026-09-02",
                   "çıkış": "2026-09-02", "getiri_%": 1.0, "net_getiri_%": 0.8, "endekse_göre_%": 0.1,
                   "en_düşük_%": -1.0, "eksik": "", "uygulanabilirlik": ""}
            report = pilot_export.build_report(conn, [dict(row, vade=v) for v in (1, 3, 5)])
            conn.close()
        self.assertEqual(report["gaps"].iloc[0]["eksikler"],
                         "PDF okunamadı; resim/bozuk/şifreli olabilir. | PDF sayfa sınırını aşıyor.")
        methods = report["files"]["halley_yontem.txt"].decode("utf-8-sig")
        self.assertIn("3 satır 3 bağımsız olay", methods)
        self.assertNotIn("40 satır", methods)


class PromptRuleTests(unittest.TestCase):
    def test_prompt_contains_review_rules(self):
        p = analyzer.ANALYSIS_PROMPT
        for phrase in ("Güncelleme mi? Evet", "KÜMÜLATİF", "FİNANSAL SIKINTI", "Finansal yükümlülüklerin yerine getirilmesi"):
            self.assertIn(phrase, p)

    def test_model_and_quality_settings_unchanged(self):
        self.assertEqual(backtest.MODEL, "gpt-5-mini")
        self.assertEqual(config.MODEL_ANALYSIS, "gpt-5-mini")
        self.assertEqual(config.ANALYSIS_REASONING_EFFORT, "high")
        self.assertTrue(config.SECOND_OPINION)
        self.assertEqual(config.KAP_REQUEST_DELAY, 1.5)


if __name__ == "__main__":
    unittest.main()


class FreeCheckTests(unittest.TestCase):
    def test_free_check_never_calls_ai_and_estimates_cost(self):
        from bist_haber import pipeline
        from datetime import datetime
        conn = memory_db()
        now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")   # güncel haber (5 günden eski otomatik atlanır)
        add_news(conn, nid="kap:1", body="Sözleşme bedeli 10 milyon TL. " * 20, published=now)
        add_news(conn, nid="kap:2", body="Yeni yatırım kararı alındı. " * 20, published=now)
        with patch.object(pipeline, "universe", return_value={"TEST": "Deneme"}), \
                patch.object(kap, "collect", return_value={"new": 2}), \
                patch.object(kap, "list_disclosures", return_value=[]), \
                patch.object(kap, "fetch_missing_bodies", return_value={}), \
                patch("bist_haber.rss.collect", return_value={"new": 0}), \
                patch("bist_haber.prices.update", return_value=0), \
                patch.object(analyzer, "analyze", side_effect=AssertionError("Ücretsiz denemede yapay zekâ çağrılmamalı")), \
                patch.object(analyzer, "LLM", side_effect=AssertionError("Ücretsiz denemede istemci kurulmamalı")), \
                patch.object(pipeline, "has_api_key", return_value=True):
            out = pipeline.free_check(conn, analysis_limit=10)
        self.assertTrue(out["free"])
        self.assertNotIn("analyze", out)
        est = out["estimate"]
        self.assertEqual(est["next_count"], 2)
        self.assertGreater(est["high_usd"], est["low_usd"])
        self.assertGreater(est["low_usd"], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0], 0)


class QueueOrderTests(unittest.TestCase):
    def test_newest_news_is_analyzed_first(self):
        conn = memory_db()
        add_news(conn, nid="kap:eski", body="Eski haber metni " * 10, published="2026-11-05T09:00:00+03:00")
        add_news(conn, nid="kap:yeni", body="Yeni haber metni " * 10, published="2026-11-06T15:00:00+03:00")
        add_news(conn, nid="kap:orta", body="Orta haber metni " * 10, published="2026-11-06T09:00:00+03:00")
        self.assertEqual([r["id"] for r in analyzer.pending(conn)], ["kap:yeni", "kap:orta", "kap:eski"])
        self.assertEqual([r["id"] for r in analyzer.pending(conn, 1)], ["kap:yeni"])
