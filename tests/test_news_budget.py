"""2026-11-09: haber analizi aylık bütçesi, eski haber kuralı, seçili haber analizi, derin yeniden inceleme."""
import json
import sqlite3
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from bist_haber import analyzer, config

from test_accuracy import add_news, analysis, memory_db

UNI = {"TEST": "Deneme", "ABC": "Abc"}
COST_ONE = 1000 * 0.25e-6 + 7000 * 2e-6         # FakeClient bir çağrı: 1.000 girdi + 7.000 çıktı token = 0,01425 $


class FakeLLM:
    def __init__(self, results=None):
        self.results = results or [analysis()]
        self.calls = []

    def parse(self, model, system, user, schema, reasoning_effort=None):
        self.calls.append({"user": user, "effort": reasoning_effort})
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)], 1000, 7000


def now(days_ago=0):
    return (datetime.now(config.TR_TZ) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def past_analysis(conn, nid, tin, tout, when):
    conn.execute("INSERT INTO analyses(news_id,stage,model,result_json,input_tokens,output_tokens,created_at) "
                 "VALUES(?, 'full', 'gpt-5-mini', '{}', ?, ?, ?)", (nid, tin, tout, when))


class BudgetAndAgeTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()

    def test_month_spend_counts_only_this_month(self):
        past_analysis(self.conn, "a", 1000, 7000, now())
        past_analysis(self.conn, "b", 1000, 7000, "2025-01-15T10:00:00+03:00")
        self.assertAlmostEqual(analyzer.month_spend(self.conn), COST_ONE)

    def test_old_news_not_auto_analyzed_but_selectable(self):
        add_news(self.conn, nid="kap:new", body="metin " * 50, published=now(1))
        add_news(self.conn, nid="kap:old", body="metin " * 50, published=now(9))
        ids = lambda rows: [r["id"] for r in rows]
        self.assertEqual(ids(analyzer.pending(self.conn, max_age_days=5)), ["kap:new"])
        self.assertEqual(sorted(ids(analyzer.pending(self.conn))), ["kap:new", "kap:old"])
        llm = FakeLLM()
        s = analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn)[1:], llm=llm)   # elle: eski haber
        self.assertEqual(s["analyzed"], 1)
        self.assertEqual(self.conn.execute("SELECT status FROM news WHERE id='kap:old'").fetchone()[0], "analyzed")

    def test_budget_stops_before_exceeding(self):
        for i in range(5):
            add_news(self.conn, nid=f"kap:{i}", body="metin " * 50, published=now())
        rows = analyzer.pending(self.conn)
        one_high = analyzer.row_cost(rows[0], analyzer._avg_out(self.conn), None, analyzer._high_out(self.conn))[1]
        keep, over = analyzer.within_budget(self.conn, rows, one_high * 2.5)
        self.assertEqual((len(keep), over), (2, 3))                     # 2 haberin üst tahmini sığar
        llm = FakeLLM()
        s = analyzer.analyze(self.conn, UNI, rows=rows, llm=llm, budget_usd=one_high * 2.5)
        self.assertEqual((s["analyzed"], s["butce_disi"]), (2, 3))
        self.assertLessEqual(analyzer.month_spend(self.conn), one_high * 2.5)
        s2 = analyzer.analyze(self.conn, UNI, llm=llm, budget_usd=0.0)          # bütçe 0 → hiç çağrı yok
        self.assertEqual(s2.get("analyzed", 0), 0)

    def test_pipeline_uses_settings_budget_and_age(self):
        from bist_haber import pipeline
        add_news(self.conn, nid="kap:1", body="metin " * 50, published=now())
        with patch.object(pipeline, "load_settings", return_value={"haber_butce_usd": 0.0}):
            self.assertEqual(pipeline.news_budget(), 0.0)
            est = pipeline.estimate_next_run(self.conn, 10)
        self.assertEqual((est["next_count"], est["butce_disi"]), (0, 1))
        with patch.object(pipeline, "load_settings", return_value={}):
            self.assertEqual(pipeline.news_budget(), config.NEWS_BUDGET_USD)
        with self.assertRaises(ValueError):
            pipeline.update_all(self.conn, analysis_limit=config.MAX_ANALYSIS_PER_RUN + 1)


class ReanalysisTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()
        add_news(self.conn, nid="kap:1", body="Sözleşme bedeli 10 milyon TL. " * 20, published=now(2))
        analyzer.analyze(self.conn, UNI, rows=analyzer.pending(self.conn), llm=FakeLLM([analysis(impact=2)]))

    def test_old_result_logged_new_used_and_spend_kept(self):
        before = analyzer.month_spend(self.conn)
        self.assertAlmostEqual(before, COST_ONE)
        llm = FakeLLM([analysis(impact=4), analysis(impact=4)])
        res = analyzer.reanalyze(self.conn, UNI, ["kap:1"], llm=llm)
        self.assertEqual((res["incelenen"], res["degisen"], res["hata"]), (1, 1, 0))
        self.assertEqual(len(llm.calls), 2)                               # ikinci görüş ZORUNLU
        self.assertTrue(all(c["effort"] == config.ANALYSIS_REASONING_EFFORT for c in llm.calls))
        imp = self.conn.execute("SELECT magnitude, flag FROM impacts WHERE news_id='kap:1'").fetchone()
        self.assertEqual((imp["magnitude"], imp["flag"]), (4, "teyitli"))
        log = self.conn.execute("SELECT * FROM reanalysis_log").fetchone()
        self.assertEqual(json.loads(log["eski_json"])[0]["magnitude"], 2)
        self.assertEqual(json.loads(log["yeni_json"])[0]["magnitude"], 4)
        # aylık harcama: önceki analiz (1 çağrı) + derin inceleme (2 çağrı) — önceki maliyet kaybolmaz
        self.assertAlmostEqual(analyzer.month_spend(self.conn), 3 * COST_ONE)
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE reanalysis_log SET durum='x'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM reanalysis_log")

    def test_budget_and_only_analyzed_news(self):
        res = analyzer.reanalyze(self.conn, UNI, ["kap:1"], llm=FakeLLM(), budget_usd=analyzer.month_spend(self.conn))
        self.assertEqual((res["incelenen"], res["butce_disi"]), (0, 1))
        add_news(self.conn, nid="kap:2", body="metin " * 30, published=now())     # analiz edilmemiş → incelenmez
        self.assertEqual(analyzer.reanalyze(self.conn, UNI, ["kap:2"], llm=FakeLLM())["incelenen"], 0)

    def test_full_text_not_fetched_twice(self):
        self.conn.execute("UPDATE news SET source='rss:x', url='https://ornek', body=body || '\n\n[TAM METİN]\nTam' "
                          "WHERE id='kap:1'")
        self.conn.commit()
        filt = analyzer.FilterResult(onemli=True, neden="önemli")
        with patch.object(analyzer, "fetch_article", side_effect=AssertionError("yeniden indirildi")) as fa:
            res = analyzer.reanalyze(self.conn, UNI, ["kap:1"], llm=FakeLLM([filt, analysis(), analysis()]))
        self.assertEqual(res["hata"], 0, res)
        body = self.conn.execute("SELECT body FROM news WHERE id='kap:1'").fetchone()[0]
        self.assertEqual(body.count("[TAM METİN]"), 1)
        self.assertFalse(fa.called and fa.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
