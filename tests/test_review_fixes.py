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
