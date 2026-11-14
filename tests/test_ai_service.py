"""Aşama 2 (2026-11-14): merkezi YZ servisi kaydı, kullanım özeti, sahte istemcinin kayıt yazmaması, içerik özeti
ile tekrarlanan haber ayıklama. Gerçek OpenAI'ye bağlanılmaz."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bist_haber import ai_service, config, db, dedupe


class FakeCompletions:
    def __init__(self, fail=None):
        self.fail, self.calls = fail, 0

    def parse(self, **kw):
        self.calls += 1
        if self.fail:
            raise self.fail
        msg = SimpleNamespace(parsed={"ok": True}, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                               usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500))


def fake_client(fail=None):
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(fail)))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.db"
        p = patch.object(config, "DB_PATH", self.path)
        p.start()
        self.addCleanup(p.stop)
        self.conn = db.connect(self.path)
        self.addCleanup(self.conn.close)


class ServiceTests(Base):
    def test_calls_recorded_with_module_operation_cost(self):
        llm = ai_service.LLM("haber_analizi", client=fake_client(), db_path=self.path)
        out, tin, tout = llm.parse("gpt-5-mini", "s", "u", dict, islem="tam_analiz", ref="kap:1")
        self.assertEqual((out, tin, tout), ({"ok": True}, 1000, 500))
        r = self.conn.execute("SELECT modul, islem, ref, model, input_tokens, output_tokens, usd, durum FROM ai_calls").fetchone()
        self.assertEqual(tuple(r)[:6], ("haber_analizi", "tam_analiz", "kap:1", "gpt-5-mini", 1000, 500))
        self.assertGreater(r["usd"], 0)
        self.assertEqual(r["durum"], "ok")

    def test_errors_recorded_and_raised(self):
        llm = ai_service.LLM("rapor_yorumu", client=fake_client(RuntimeError("ağ yok")), db_path=self.path)
        with self.assertRaises(RuntimeError):
            llm.parse("gpt-5-mini", "s", "u", dict, islem="yorum")
        r = self.conn.execute("SELECT durum, hata FROM ai_calls").fetchone()
        self.assertEqual((r["durum"], r["hata"]), ("hata", "ağ yok"))

    def test_fake_client_without_db_path_writes_nothing(self):
        llm = ai_service.LLM("haber_analizi", client=fake_client())       # testlerdeki sahte istemci
        llm.parse("gpt-5-mini", "s", "u", dict)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] if
                         self.conn.execute("SELECT name FROM sqlite_master WHERE name='ai_calls'").fetchone() else 0, 0)

    def test_usage_summary(self):
        now = datetime.now(config.TR_TZ)
        ai_service.record("haber_analizi", "tam_analiz", "kap:1", "gpt-5-mini", 1000, 500, db_path=self.path)
        ai_service.record("haber_analizi", "ikinci_gorus", "kap:1", "gpt-5-mini", 1000, 500, db_path=self.path)
        ai_service.record("rapor_yorumu", "yorum", None, "gpt-5-mini", 0, 0, "hata", "zaman aşımı", db_path=self.path)
        u = ai_service.usage(self.conn, now)
        self.assertEqual((u["bugun"]["cagri"], u["ay"]["cagri"], u["ay"]["hata"]), (3, 3, 1))
        self.assertEqual({(m["Modül"], m["İşlem"]) for m in u["modul"]},
                         {("Haber analizi", "tam analiz"), ("Haber analizi", "ikinci görüş"), ("Rapor yorumu", "yorum")})
        self.assertEqual(u["hatalar"][0]["hata"], "zaman aşımı")
        self.assertAlmostEqual(ai_service.month_usd(self.conn, now), u["ay"]["usd"])

    def test_every_ai_entry_point_uses_the_service(self):
        """Kodda OpenAI istemcisini doğrudan kuran yalnız servis (ve kendi kaydını servise yazan pilot) olmalı."""
        import re
        root = Path(config.ROOT) / "bist_haber"
        direct = [p.name for p in root.glob("*.py") if re.search(r"\bOpenAI\(", p.read_text(encoding="utf-8"))]
        self.assertEqual(sorted(direct), ["ai_service.py", "backtest.py"])
        self.assertIn("ai_service.record", (root / "backtest.py").read_text(encoding="utf-8"))
        from bist_haber import analyzer
        self.assertIs(analyzer.LLM, ai_service.LLM)


class DedupeTests(Base):
    def add(self, nid, title, body, cands="AAA", source="kap", status="new", pub="2026-11-10T10:00:00+03:00"):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,fetched_at) "
                          "VALUES(?,?,?,?,?,?,?,?,'f')", (nid, source, pub, pub[:10], title, body, cands, status))
        self.conn.commit()
        return self.conn.execute("SELECT * FROM news WHERE id=?", (nid,)).fetchone()

    def test_same_content_not_sent_again(self):
        self.add("kap:1", "AAA: Yeni iş ilişkisi", "Şirket 1 milyar TL sözleşme imzaladı.", status="analyzed")
        r2 = self.add("kap:2", "AAA:  yeni İŞ ilişkisi", "Şirket 1 milyar TL  sözleşme imzaladı.")   # yalnız boşluk/harf farkı
        r3 = self.add("kap:3", "AAA: Yeni iş ilişkisi", "Şirket 2 milyar TL sözleşme imzaladı.")       # içerik farklı
        kept, dup = dedupe.filter_duplicates(self.conn, [r2, r3])
        self.assertEqual(([r["id"] for r in kept], dup), (["kap:3"], 1))
        st = self.conn.execute("SELECT status, note FROM news WHERE id='kap:2'").fetchone()
        self.assertEqual(st["status"], "duplicate")
        self.assertIn("kap:1", st["note"])
        self.assertIsNotNone(self.conn.execute("SELECT content_hash FROM news WHERE id='kap:3'").fetchone()[0])

    def test_other_company_same_text_is_still_analyzed(self):
        self.add("kap:1", "Ortak açıklama", "Aynı metin.", cands="AAA", status="analyzed")
        r2 = self.add("kap:2", "Ortak açıklama", "Aynı metin.", cands="BBB")                          # başka şirket
        kept, dup = dedupe.filter_duplicates(self.conn, [r2])
        self.assertEqual((len(kept), dup), (1, 0))

    def test_duplicates_inside_one_batch_and_rss_same_title(self):
        a = self.add("kap:1", "Başlık", "Metin.")
        b = self.add("kap:2", "Başlık", "Metin.")
        kept, dup = dedupe.filter_duplicates(self.conn, [a, b])
        self.assertEqual(([r["id"] for r in kept], dup), (["kap:1"], 1))
        # aynı partideki tekrar kalıcı işaretlenmez (ilk kayıt hata alırsa kaybolmasın); ilki analiz edilince işaretlenir
        self.assertEqual(self.conn.execute("SELECT status FROM news WHERE id='kap:2'").fetchone()[0], "new")
        self.conn.execute("UPDATE news SET status='analyzed' WHERE id='kap:1'")
        self.conn.commit()
        b = self.conn.execute("SELECT * FROM news WHERE id='kap:2'").fetchone()
        dedupe.filter_duplicates(self.conn, [b])
        self.assertEqual(self.conn.execute("SELECT status FROM news WHERE id='kap:2'").fetchone()[0], "duplicate")
        self.add("rss:x:1", "Faiz kararı açıklandı!", "kaynak X metni", cands="", source="rss:x", status="analyzed")
        r = self.add("rss:y:1", "Faiz Kararı Açıklandı", "kaynak Y farklı metin", cands="", source="rss:y",
                     pub="2026-11-11T09:00:00+03:00")
        kept, dup = dedupe.filter_duplicates(self.conn, [r])
        self.assertEqual(dup, 1)                                                                   # aynı başlık, başka site


class AnalyzeIntegration(Base):
    def test_analyze_skips_duplicate_and_reports_it(self):
        from bist_haber import analyzer
        from tests.test_accuracy import FakeClient
        self.conn.execute("INSERT INTO companies VALUES('TEST','Deneme',NULL)")
        for nid in ("kap:1", "kap:2"):
            self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                              "fetched_at) VALUES(?,'kap','2026-11-10T10:00:00+03:00','2026-11-10','Sözleşme','Yeni İş İlişkisi',"
                              "?, 'TEST','new','f')", (nid, "Sözleşme ayrıntıları " * 20))
        self.conn.commit()
        llm = ai_service.LLM("haber_analizi", client=FakeClient())
        with patch("bist_haber.prices.company_stats", return_value={}):
            st = analyzer.analyze(self.conn, {"TEST": "Deneme"}, limit=5, llm=llm)
        self.assertEqual((st["analyzed"], st["tekrar"]), (1, 1))                    # ikincisi YZ'ye gönderilmedi
        # ilk kayıt hata alsaydı: ikincisi kaybolmaz, sonraki turda analiz edilir
        self.assertEqual(self.conn.execute("SELECT status FROM news WHERE id='kap:2'").fetchone()[0], "new")
        with patch("bist_haber.prices.company_stats", return_value={}):
            st2 = analyzer.analyze(self.conn, {"TEST": "Deneme"}, limit=5, llm=llm)
        self.assertEqual((st2.get("analyzed"), st2.get("tekrar")), (0, 1))          # artık analiz edilmişin tekrarı
        self.assertEqual(self.conn.execute("SELECT status FROM news WHERE id='kap:2'").fetchone()[0], "duplicate")


if __name__ == "__main__":
    unittest.main()
