"""Ücretsiz, deterministik regresyon ve pilot entegrasyon kontrolleri."""
import gc
import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bist_haber import analyzer, backtest, config, db, kap


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(db.SCHEMA)
    conn.execute("ALTER TABLE impacts ADD COLUMN flag TEXT")
    return conn


def add_news(conn, nid="kap:1", body=None, published="2026-09-01T12:00:00+03:00", subject="Yeni İş İlişkisi"):
    conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,subject,fetched_at) "
                 "VALUES(?,'kap',?,?,'Sözleşme',?,'TEST',?,'2026-11-06')",
                 (nid, published, published[:10], body, subject))
    conn.commit()


def analysis(impact=3, direction="pozitif"):
    return analyzer.FullAnalysis(olay_tipi="yeni_is_sozlesme_ihale", kalicilik="orta", guven=0.8,
                                 ozet="Sözleşme", etkiler=[analyzer.StockImpact(
                                     hisse="TEST", yon=direction, etki=impact, gerekce="Belgedeki sözleşme")])


def seed_prices(conn):
    for day in ("2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07", "2026-09-08",
                "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-14", "2026-09-15"):
        for ticker in ("TEST", "XU100"):
            conn.execute("INSERT OR REPLACE INTO pilot_bars VALUES(?,?,100,110,90,105)", (ticker, day))
    conn.commit()


class FakeClient:
    def __init__(self, results=None, fail_at=None):
        self.results = results or [analysis(), analysis()]
        self.fail_at = fail_at
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self.parse))

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_at == len(self.calls):
            raise TimeoutError("Bağlantı kesildi")
        result = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=7000),
                               choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(
                                   parsed=result, refusal=None))])


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()
        self.addCleanup(self.conn.close)

    def test_old_notification_fetches_full_body(self):
        add_news(self.conn)
        with patch.object(kap, "fetch_body", return_value="Ayrıntılı sözleşme metni") as fetch, patch.object(kap.time, "sleep"):
            result = kap.fetch_missing_bodies(self.conn)
        fetch.assert_called_once_with(1, "Yeni İş İlişkisi")
        self.assertEqual(result["bodies_fetched"], 1)
        self.assertIn("Ayrıntılı", self.conn.execute("SELECT body FROM news").fetchone()[0])

    def test_empty_old_document_waits_instead_of_title_analysis(self):
        add_news(self.conn)
        with patch.object(kap, "fetch_body", return_value=""), patch.object(kap.time, "sleep"):
            result = kap.fetch_missing_bodies(self.conn)
        self.assertEqual(result["bodies_pending"], 1)
        self.assertEqual(analyzer.pending(self.conn), [])
        self.assertIsNone(self.conn.execute("SELECT body FROM news").fetchone()[0])

    def test_legacy_title_fallback_is_recovered(self):
        add_news(self.conn, body="")
        self.conn.execute("UPDATE news SET note='metin alınamadı, başlıkla analiz'")
        self.conn.commit()
        with patch.object(kap, "fetch_body", return_value="Kurtarılan belge"), patch.object(kap.time, "sleep"):
            kap.fetch_missing_bodies(self.conn)
        self.assertEqual(self.conn.execute("SELECT body FROM news").fetchone()[0], "Kurtarılan belge")

    def test_empty_body_is_not_ready_for_llm(self):
        add_news(self.conn, body=" \n ")
        self.assertEqual(analyzer.pending(self.conn), [])

    def test_invalid_model_ranges_are_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            analyzer.StockImpact(hisse="TEST", yon="pozitif", etki=9, gerekce="Hata")
        with self.assertRaises(ValidationError):
            analyzer.FullAnalysis(olay_tipi="diger", kalicilik="kisa", guven=1.2, ozet="Hata", etkiler=[])

    def test_rate_limit_keeps_remaining_documents_pending(self):
        add_news(self.conn)
        with patch.object(kap, "fetch_body", side_effect=kap.RateLimited("429")), patch.object(kap.time, "sleep") as sleep:
            result = kap.fetch_missing_bodies(self.conn)
        self.assertTrue(result["rate_limited"])
        self.assertEqual(result["bodies_pending"], 1)
        sleep.assert_called_with(1.5)

    def test_capped_list_is_split_without_speeding_up_requests(self):
        def response(items):
            return SimpleNamespace(status_code=200, json=lambda: items, raise_for_status=lambda: None)
        large = [{"disclosureIndex": i} for i in range(2000)]
        with patch.object(kap.requests, "post", side_effect=[response(large), response([{"disclosureIndex": 1}]),
                                                            response([{"disclosureIndex": 2}])]) as post, \
                patch.object(kap.time, "sleep") as sleep:
            result = kap.list_disclosures(date(2026, 9, 1), date(2026, 9, 2))
        self.assertEqual(result, [{"disclosureIndex": 1}, {"disclosureIndex": 2}])
        self.assertEqual(post.call_count, 3)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [1.5, 1.5, 1.5])

    def test_capped_single_day_is_not_silently_accepted(self):
        response = SimpleNamespace(status_code=200, json=lambda: [{"disclosureIndex": i} for i in range(2000)],
                                   raise_for_status=lambda: None)
        with patch.object(kap.requests, "post", return_value=response), patch.object(kap.time, "sleep"):
            with self.assertRaises(RuntimeError):
                kap.list_disclosures(date(2026, 9, 1), date(2026, 9, 1))

    def test_daily_collect_dry_run_analyze_report_flow(self):
        import argparse
        import contextlib
        import io
        from bist_haber import report
        from bist_haber.__main__ import cmd_analyze
        item = {"disclosureIndex": 1, "stockCodes": "TEST", "subject": "Yeni İş İlişkisi",
                "publishDate": "01.09.2026 12:00:00", "summary": "Sözleşme"}
        self.conn.execute("INSERT INTO companies VALUES('TEST','Deneme',NULL)")
        self.conn.commit()
        with patch.object(kap, "list_disclosures", return_value=[item]), \
                patch.object(kap, "fetch_body", return_value="Sözleşme ayrıntıları " * 20), patch.object(kap.time, "sleep"):
            kap.collect(self.conn, {"TEST": "Deneme"})
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(config, "UNIVERSE_FILE", Path(temp) / "none.txt"), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            cmd_analyze(self.conn, argparse.Namespace(limit=3, retry_errors=False, dry_run=True))
        self.assertIn("Analiz bekleyen haber: 1", output.getvalue())
        llm = analyzer.LLM.__new__(analyzer.LLM)
        llm.client, llm._unsupported = FakeClient(), set()
        with patch("bist_haber.prices.company_stats", return_value={}):
            stats = analyzer.analyze(self.conn, {"TEST": "Deneme"}, limit=3, llm=llm)
        self.assertEqual(stats["analyzed"], 1)
        rows = report.build(self.conn, {"TEST": "Deneme"}, as_of=date(2026, 9, 2))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "TEST")
        self.assertGreater(rows[0]["score"], 0)
        self.conn.execute("UPDATE news SET body='' WHERE id='kap:1'")
        self.conn.commit()
        self.assertEqual(report.build(self.conn, {"TEST": "Deneme"}, as_of=date(2026, 9, 2)), [])


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = backtest.connect(Path(self.temp.name) / "pilot.db")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.conn.close)
        seed_prices(self.conn)

    def call(self, llm):
        return llm.parse("gpt-5-mini", "Sabit talimat", "Tarihli belge", analyzer.FullAnalysis, "high")

    def test_primary_cache_is_not_independent_second_opinion(self):
        client = FakeClient()
        llm = backtest.PilotLLM(self.conn, "kap:1", client)
        self.call(llm)
        self.call(llm)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual({r[0] for r in self.conn.execute("SELECT purpose FROM pilot_calls")}, {"primary", "second"})
        again = backtest.PilotLLM(self.conn, "kap:1", client)
        self.assertEqual(self.call(again)[1:], (0, 0))
        self.call(again)
        self.assertEqual(len(client.calls), 2)
        self.assertAlmostEqual(backtest.wallet(self.conn)["charged_usd"], 0.0285)
        self.assertEqual(backtest.wallet(self.conn)["reserved_usd"], 0)

    def test_timeout_holds_reservation_and_does_not_auto_retry(self):
        client = FakeClient(fail_at=1)
        with self.assertRaises(TimeoutError):
            self.call(backtest.PilotLLM(self.conn, "kap:1", client))
        self.assertGreater(backtest.wallet(self.conn)["reserved_usd"], 0)
        with self.assertRaises(backtest.BudgetStop):
            self.call(backtest.PilotLLM(self.conn, "kap:1", client))
        self.assertEqual(len(client.calls), 1)

    def test_budget_persists_and_blocks_before_network_call(self):
        self.conn.execute("INSERT INTO pilot_calls VALUES('spent','kap:0','primary','uncertain',?,0,NULL,NULL,NULL,'{}','now')",
                          (backtest.BUDGET_NANO,))
        self.conn.commit()
        client = FakeClient()
        with self.assertRaises(backtest.BudgetStop):
            self.call(backtest.PilotLLM(self.conn, "kap:1", client))
        self.assertEqual(client.calls, [])
        self.assertEqual(backtest.wallet(self.conn)["remaining_usd"], 0)

    def test_distinct_prompt_or_news_invalidates_cache(self):
        client = FakeClient()
        self.call(backtest.PilotLLM(self.conn, "kap:1", client))
        self.call(backtest.PilotLLM(self.conn, "kap:2", client))
        backtest.PilotLLM(self.conn, "kap:1", client).parse(
            "gpt-5-mini", "Değişen talimat", "Tarihli belge", analyzer.FullAnalysis, "high")
        self.assertEqual(len(client.calls), 3)

    def test_other_model_is_rejected_without_charge(self):
        client = FakeClient()
        with self.assertRaises(ValueError):
            backtest.PilotLLM(self.conn, "kap:1", client).parse("other", "p", "u", analyzer.FullAnalysis)
        self.assertFalse(client.calls)

    def test_ten_news_batch_stops_and_resume_keeps_second_opinion(self):
        import hashlib
        body = "Ayrıntılı belge " * 30
        for i in range(11):
            nid = f"kap:{i}"
            add_news(self.conn, nid=nid, body=body)
            self.conn.execute("INSERT INTO pilot_selection VALUES(?)", (nid,))
            self.conn.execute("INSERT INTO pilot_documents VALUES(?,?,'[]',?,'now')",
                              (nid, hashlib.sha256(body.encode()).hexdigest(), len(body)))
        self.conn.commit()
        client = FakeClient()
        first = backtest.analyze(self.conn, client=client)
        self.assertEqual(first["analyzed"], 10)
        self.assertEqual(len(client.calls), 20)
        self.assertTrue(all(c["reasoning_effort"] == "high" for c in client.calls))
        second = backtest.analyze(self.conn, client=client)
        self.assertEqual(second["analyzed"], 1)
        self.assertEqual(len(client.calls), 22)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM impacts WHERE flag='teyitli'").fetchone()[0], 11)

    def test_lowered_budget_preserves_old_usage_and_blocks_new_calls(self):
        self.assertEqual(backtest.BUDGET_NANO, 1_000_000_000)
        self.conn.execute("INSERT INTO pilot_calls VALUES('old','kap:0','primary','done',0,1200000000,0,0,NULL,'{}','now')")
        self.conn.commit()
        self.assertEqual(backtest.wallet(self.conn)["remaining_usd"], 0)
        self.assertEqual(backtest.wallet(self.conn)["charged_usd"], 1.2)
        client = FakeClient()
        with self.assertRaises(backtest.BudgetStop):
            self.call(backtest.PilotLLM(self.conn, "kap:1", client))
        self.assertFalse(client.calls)

    def test_oversized_batch_is_rejected_before_calls(self):
        client = FakeClient()
        with self.assertRaises(ValueError):
            backtest.analyze(self.conn, client=client, max_items=100)
        self.assertFalse(client.calls)

    def test_sampling_does_not_depend_on_list_order_or_future_prices(self):
        items = [{"disclosureIndex": i, "stockCodes": "TEST", "subject": "Yeni İş İlişkisi"} for i in range(250)]
        a, count = backtest.select_items(items, 100)
        b, _ = backtest.select_items(list(reversed(items)), 100)
        self.assertEqual(a, b)
        self.assertEqual(count, 250)
        self.assertEqual(len(a), 100)

    def test_financial_and_long_documents_are_not_silently_accepted(self):
        self.assertTrue(backtest.document_issues("a" * 200, "Finansal Rapor"))
        self.assertTrue(backtest.document_issues("a" * (config.MAX_BODY_CHARS + 1), "Sözleşme"))
        self.assertFalse(backtest.document_issues("a" * 200, "Sözleşme"))

    def test_excel_attachment_is_flagged_before_analysis(self):
        with patch.object(kap, "_get", return_value=SimpleNamespace(text="page")), \
                patch.object(kap, "_parse_page", return_value=("Belge " * 50,
                             [{"fileExtension": "xlsx", "objId": "x"}])):
            body, issues = backtest.fetch_document(1, "Sözleşme")
        self.assertIn("PDF dışındaki ekler okunmadı.", issues)
        self.assertTrue(body)

    def test_scanned_pdf_page_is_flagged_before_analysis(self):
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "")])
        with patch.object(kap, "_get", return_value=SimpleNamespace(text="page", content=b"%PDF")), \
                patch.object(kap, "_parse_page", return_value=("Belge " * 50,
                             [{"fileExtension": "pdf", "objId": "x"}])), \
                patch("pypdf.PdfReader", return_value=reader), patch("time.sleep"):
            _, issues = backtest.fetch_document(1, "Sözleşme")
        self.assertIn("PDF içinde metni okunamayan sayfa var.", issues)

    def test_pdf_page_and_text_limits_are_flagged(self):
        page = SimpleNamespace(extract_text=lambda: "x" * 1000)
        reader = SimpleNamespace(pages=[page] * 11)
        with patch.object(kap, "_get", return_value=SimpleNamespace(text="page", content=b"%PDF")), \
                patch.object(kap, "_parse_page", return_value=("Belge " * 50,
                             [{"fileExtension": "pdf", "objId": "x"}])), \
                patch("pypdf.PdfReader", return_value=reader), patch("time.sleep"):
            _, issues = backtest.fetch_document(1, "Sözleşme")
        self.assertIn("PDF sayfa sınırını aşıyor.", issues)
        self.assertIn("PDF metni uzunluk sınırını aşıyor.", issues)

    def test_changed_document_cannot_use_old_validation(self):
        add_news(self.conn, body="Sonradan değişen belge " * 20)
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        self.conn.execute("INSERT INTO pilot_documents VALUES('kap:1','oldhash','[]',300,'now')")
        self.conn.commit()
        client = FakeClient()
        result = backtest.analyze(self.conn, client=client)
        self.assertIn("değişti", result["stopped"])
        self.assertFalse(client.calls)

    def test_prepare_reuses_documents_and_avoids_current_universe(self):
        items = [{"disclosureIndex": 1, "stockCodes": "OLDCO", "subject": "Yeni İş İlişkisi",
                  "publishDate": "01.09.2026 12:00:00", "summary": "Eski şirket"}]
        with patch.object(kap, "list_disclosures", return_value=items), \
                patch.object(backtest, "fetch_document", return_value=("Belge " * 40, [])) as fetch, \
                patch("time.sleep"):
            backtest.prepare(self.conn, date(2026, 9, 1), date(2026, 9, 2))
            backtest.prepare(self.conn, date(2026, 9, 1), date(2026, 9, 2))
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(self.conn.execute("SELECT candidates FROM news").fetchone()[0], "OLDCO")
        self.assertEqual(backtest.overview(self.conn)["ready"], 1)

    def test_incomplete_document_never_calls_model(self):
        add_news(self.conn, body="Eksik")
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        self.conn.execute("INSERT INTO pilot_documents VALUES('kap:1','hash','[\"Eksik\"]',5,'now')")
        self.conn.commit()
        client = FakeClient()
        result = backtest.analyze(self.conn, client=client)
        self.assertEqual(result["analyzed"], 0)
        self.assertFalse(client.calls)

    def test_missing_prices_never_spend_analysis_budget(self):
        add_news(self.conn, body="Ayrıntılı belge " * 30)
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        self.conn.execute("INSERT INTO pilot_documents VALUES('kap:1','hash','[]',400,'now')")
        self.conn.execute("DELETE FROM pilot_bars WHERE ticker='TEST'")
        self.conn.commit()
        client = FakeClient()
        result = backtest.analyze(self.conn, client=client)
        self.assertEqual(result["skipped_prices"], 1)
        self.assertFalse(client.calls)
        self.assertEqual(backtest.wallet(self.conn)["charged_usd"], 0)

    def test_end_to_end_analysis_uses_no_current_price_context_and_keeps_second(self):
        body = "2026 tarihli somut sözleşme metni. " * 10
        add_news(self.conn, body=body)
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        import hashlib
        self.conn.execute("INSERT INTO pilot_documents VALUES('kap:1',?,'[]',?,'now')",
                          (hashlib.sha256(body.encode()).hexdigest(), len(body)))
        self.conn.commit()
        client = FakeClient()
        with patch("bist_haber.prices.company_stats", side_effect=AssertionError("Bugünkü veri çağrılmamalı")):
            result = backtest.analyze(self.conn, client=client)
        self.assertEqual(result["analyzed"], 1)
        self.assertEqual(len(client.calls), 2)
        self.assertNotIn("piyasa değeri ≈", client.calls[0]["messages"][1]["content"])
        self.assertEqual(self.conn.execute("SELECT flag FROM impacts").fetchone()[0], "teyitli")
        self.assertEqual(backtest.analyze(self.conn, client=client)["analyzed"], 0)
        self.assertEqual(len(client.calls), 2)

    def test_second_failure_does_not_publish_first_as_confirmed(self):
        body = "Ayrıntılı belge " * 30
        add_news(self.conn, body=body)
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        import hashlib
        self.conn.execute("INSERT INTO pilot_documents VALUES('kap:1',?,'[]',?,'now')",
                          (hashlib.sha256(body.encode()).hexdigest(), len(body)))
        self.conn.commit()
        client = FakeClient(fail_at=2)
        result = backtest.analyze(self.conn, client=client)
        self.assertIn("stopped", result)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM impacts").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT status FROM news").fetchone()[0], "new")


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = backtest.connect(Path(self.temp.name) / "pilot.db")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.conn.close)
        add_news(self.conn, published="2026-09-04T23:00:00+03:00")  # cuma gece
        self.conn.execute("INSERT INTO pilot_selection VALUES('kap:1')")
        self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,"
                          "published_at,effective_date) VALUES('kap:1','TEST',1,3,.8,'orta','diger',"
                          "'2026-09-04T23:00:00+03:00','2026-09-07')")
        self.days = ["2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11",
                     "2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"]
        for i, day in enumerate(self.days):
            for ticker in ("TEST", "XU100"):
                self.conn.execute("INSERT INTO pilot_bars VALUES(?,?,?,?,?,?)",
                                  (ticker, day, 100, 110 + i, 90, 100 + i))
        self.conn.commit()

    def test_next_session_open_horizons_and_benchmark(self):
        rows = backtest.evaluate(self.conn, 20)
        self.assertEqual([r["vade"] for r in rows], [1, 3, 5, 10])
        self.assertEqual(rows[0]["giriş"], "2026-09-07")
        self.assertEqual(rows[0]["çıkış"], "2026-09-07")
        self.assertEqual(rows[2]["çıkış"], "2026-09-11")
        self.assertAlmostEqual(rows[0]["net_getiri_%"], 0.8)
        self.assertAlmostEqual(rows[0]["endekse_göre_%"], -0.2)
        self.assertAlmostEqual(rows[0]["en_düşük_%"], -10)

    def test_missing_entry_never_shifts_to_later_stock_price(self):
        self.conn.execute("DELETE FROM pilot_bars WHERE ticker='TEST' AND date='2026-09-07'")
        rows = backtest.evaluate(self.conn)
        self.assertTrue(all(r["eksik"] for r in rows))
        self.assertTrue(all(r["getiri_%"] is None for r in rows))
        self.assertEqual(rows[0]["giriş"], "2026-09-07")

    def test_missing_interior_day_is_not_a_complete_observation(self):
        self.conn.execute("DELETE FROM pilot_bars WHERE ticker='TEST' AND date='2026-09-08'")
        rows = backtest.evaluate(self.conn)
        self.assertFalse(rows[0]["eksik"])
        self.assertTrue(rows[1]["eksik"])

    def test_incomplete_forward_period_is_kept_as_missing(self):
        self.conn.execute("DELETE FROM pilot_bars WHERE date>'2026-09-11'")
        rows = backtest.evaluate(self.conn)
        self.assertEqual(len(rows), 4)
        self.assertTrue(rows[-1]["eksik"])

    def test_future_events_cannot_use_earlier_prices(self):
        self.conn.execute("UPDATE impacts SET published_at='2026-09-30T23:00:00+03:00'")
        self.assertTrue(all(r["eksik"] for r in backtest.evaluate(self.conn)))


class PanelTests(unittest.TestCase):
    def test_main_panel_and_pilot_render_without_network_or_key(self):
        from streamlit.testing.v1 import AppTest
        import os
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(config, "DB_PATH", root / "live.db"), patch.object(config, "DATA", root / "data"), \
                    patch.object(config, "UNIVERSE_FILE", root / "universe.txt"), \
                    patch.dict(os.environ, {"OPENAI_API_KEY": "", "HALLEY_OFFLINE": "1"}):
                conn = db.connect()
                conn.execute("INSERT INTO companies VALUES('TEST','Deneme',NULL)")
                conn.commit()
                conn.close()
                at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
                at.run(timeout=30)
                self.assertEqual(len(at.exception), 0, str(at.exception))
                # Sade düzen: 3 sekme; durum ve geçmiş veri pilotu "Gelişmiş" sekmesinde.
                self.assertEqual(len(at.tabs), 3)
                self.assertTrue(any("Gelişmiş" in tab.label for tab in at.tabs))
                self.assertTrue(any("Geçmiş veri pilotu" in m.value for m in at.markdown))
                self.assertTrue(any(b.label == "🔄 Haberleri güncelle" for b in at.button))
                self.assertTrue(any(b.key == "cheap_test" for b in at.button))
                self.assertEqual(at.radio(key="analysis_quality").value, "yuksek")  # varsayılan yüksek doğruluk
                # Ücretsiz deneme: toplama ağ gerektirdiği için sahte; yapay zekâ çağrılırsa test düşer.
                from bist_haber import analyzer, pipeline
                fake = {"free": True, "kap": {"new": 3}, "rss": {"new": 1},
                        "estimate": {"waiting": 4, "next_count": 4, "low_usd": 0.01, "high_usd": 0.03}}
                with patch.object(pipeline, "free_check", return_value=fake) as free, \
                        patch.object(analyzer, "analyze", side_effect=AssertionError("kredi harcanmamalı")):
                    at.button(key="free_check").click().run(timeout=30)
                free.assert_called_once()
                self.assertEqual(len(at.exception), 0, str(at.exception))
                self.assertTrue(any("kredi harcanmadı" in i.value for i in at.info))
                self.assertEqual([m.label for m in at.metric][:3], ["Olumlu haber", "Olumsuz haber", "Son güncelleme"])
                at.run(timeout=30)
                self.assertEqual(len(at.exception), 0)
                del at
                gc.collect()

    def test_populated_pilot_and_prepare_button_without_paid_calls(self):
        from streamlit.testing.v1 import AppTest
        import os
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(config, "DB_PATH", root / "live.db"), patch.object(config, "DATA", root / "data"), \
                    patch.object(config, "UNIVERSE_FILE", root / "universe.txt"), \
                    patch.dict(os.environ, {"OPENAI_API_KEY": "", "HALLEY_OFFLINE": "1"}):
                live = db.connect()
                live.execute("INSERT INTO companies VALUES('TEST','Deneme',NULL)")
                live.commit()
                live.close()
                pilot = backtest.connect()
                backtest._meta(pilot, "selection", {"start": "2026-09-01", "end": "2026-09-30",
                                                   "eligible": 1000, "selected": 1})
                body = "Belge " * 50
                add_news(pilot, body=body)
                pilot.execute("INSERT INTO pilot_selection VALUES('kap:1')")
                import hashlib
                pilot.execute("INSERT INTO pilot_documents VALUES('kap:1',?,'[]',?,'now')",
                              (hashlib.sha256(body.encode()).hexdigest(), len(body)))
                pilot.commit()
                seed_prices(pilot)
                backtest.analyze(pilot, client=FakeClient())
                pilot.close()
                at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
                at.run(timeout=30)
                self.assertEqual(len(at.exception), 0, str(at.exception))
                self.assertTrue(at.button(key="bt_analyze").disabled)
                # Sayfa açılınca hiçbir indirme dosyası hazırlanmaz; kullanıcı isteyince 5 düğme çıkar.
                self.assertEqual(len(at.get("download_button")), 0)
                at.button(key="bt_export_prepare").click().run(timeout=30)
                self.assertEqual(len(at.exception), 0, str(at.exception))
                self.assertEqual(len(at.get("download_button")), 5)
                at.button(key="bt_export_hide").click().run(timeout=30)
                self.assertEqual(len(at.get("download_button")), 0)
                with patch.object(backtest, "prepare", return_value={}) as prepare:
                    at.button(key="bt_prepare").click().run(timeout=30)
                prepare.assert_called_once()
                self.assertEqual(len(at.exception), 0, str(at.exception))
                del at
                gc.collect()


if __name__ == "__main__":
    unittest.main()
