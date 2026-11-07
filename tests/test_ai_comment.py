"""W6: yapay zekâ yorumu — sahte istemciyle (ücretsiz); bütçe, sayı denetimi, önbellek, geriye dönük bilgi yok."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bist_haber import ai_comment, config, db, watchdog
from tests.test_watchdog_w2 import TODAY, at, news, seed


class FakeLLM:
    def __init__(self, text="Piyasa %1,32 yükseldi; QNBTR %43,8 arttı.", tin=5000, tout=3000, fail=False):
        self.calls, self.text, self.tin, self.tout, self.fail = [], text, tin, tout, fail

    def parse(self, model, system, user, schema, reasoning_effort=None):
        self.calls.append({"model": model, "system": system, "user": user, "effort": reasoning_effort})
        if self.fail:
            raise RuntimeError("bağlantı yok")
        if schema is ai_comment.ReportComment:
            return schema(ozet=self.text, dikkat=["SOKM riskli"], riskler=["Örnek az"]), self.tin, self.tout
        return schema(aciklama=self.text, o_an_bilinebilir_miydi="kismen", sorumlu_modul="ön eleme",
                      oneri="Ön eleme konu listesi izlensin."), self.tin, self.tout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)


class NumberCheckTests(unittest.TestCase):
    def test_numbers(self):
        src = "BIST 100: 11482.60 (+1.32%) · QNBTR +43.8 · 1,496 TL · 584 hisse-gün"
        self.assertEqual(ai_comment.unverified_numbers("Endeks %1,32 arttı, QNBTR %43,8; 584 hisse; 3 madde", src), [])
        self.assertEqual(ai_comment.unverified_numbers("Hedef 55,5 TL ve 12000 adet", src), ["55,5", "12000"])
        self.assertEqual(ai_comment.unverified_numbers("11.482,60 puan", src), [])          # Türkçe biçim


class ReportCommentTests(Base):
    def test_cost_recorded_with_model_and_low_effort(self):
        llm = FakeLLM()
        r = ai_comment.comment_report(self.conn, "aksam", "2026-11-06_aksam", "XU100 +1.32 QNBTR 43.8", {}, llm=llm)
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["usd"], 5000 * 0.25e-6 + 3000 * 2e-6)                   # 0,00725 $
        self.assertAlmostEqual(ai_comment.month_spend(self.conn), r["usd"])
        self.assertEqual((llm.calls[0]["model"], llm.calls[0]["effort"]), ("gpt-5-mini", "low"))
        self.assertEqual(r["dogrulanamayan"], [])
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM ai_comments")
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE ai_comments SET usd=0")

    def test_fabricated_number_flagged_in_md(self):
        r = ai_comment.comment_report(self.conn, "aksam", "x", "XU100 +1.32", {}, llm=FakeLLM("Hedef fiyat 77,7 TL"))
        self.assertEqual(r["dogrulanamayan"], ["77,7"])
        self.assertIn("raporda bulunamadı, güvenmeyin: 77,7", ai_comment.report_md(r))

    def test_budget_blocks_call(self):
        llm = FakeLLM()
        ai_comment.comment_report(self.conn, "aksam", "a", "x", {}, llm=llm)          # 0,00725 $ harcandı
        r = ai_comment.comment_report(self.conn, "aksam", "b", "x" * 6000, {"yz_butce_usd": 0.02}, llm=llm)
        self.assertFalse(r["ok"])
        self.assertIn("bütçesi yetmiyor", r["hata"])
        self.assertEqual(len(llm.calls), 1)                                            # ikinci çağrı yapılmadı

    def test_failure_does_not_raise(self):
        r = ai_comment.comment_report(self.conn, "sabah", "a", "x", {}, llm=FakeLLM(fail=True))
        self.assertFalse(r["ok"])
        self.assertIn("alınamadı", ai_comment.report_md(r))
        self.assertEqual(ai_comment.month_spend(self.conn), 0)

    def test_estimate_matches_measurement_assumptions(self):
        e = ai_comment.estimate(6300)
        tin = (6300 + len(ai_comment.REPORT_PROMPT)) / 1.7
        self.assertAlmostEqual(e["low"], tin * 0.25e-6 + 2000 * 2e-6)
        self.assertAlmostEqual(e["high"], tin * 0.25e-6 + 13000 * 2e-6)
        self.assertLess(e["high"], 0.03)


class MissedExplainTests(Base):
    def setUp(self):
        super().setUp()
        c = self.conn
        self.run_id = c.execute("INSERT INTO watch_runs(kind,day,started_at,summary_json) VALUES('aksam','2026-11-02',"
                                "'2026-11-02T19:00:00+03:00','{}')").lastrowid
        c.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,fetched_at) VALUES"
                  "('b1','kap','2026-11-01T10:00:00+03:00','2026-11-01','ONC yeni iş ilişkisi','Önce gelen metin','ONC',"
                  "'skipped','f')")
        c.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,fetched_at) VALUES"
                  "('a1','kap','2026-11-03T10:00:00+03:00','2026-11-03','ONC sonraki haber','SONRAKI GİZLİ METİN','ONC',"
                  "'analyzed','f')")
        c.commit()

    def item(self, t, code, tags=()):
        return {"hisse": t, "baz_gun": "2026-11-02", "run_id": self.run_id, "baz_kapanis": 100.0,
                "zirve_gunu": "2026-11-05", "zirve_kapanis": 109.0, "kazanc_%": 9.0, "endeks_%": 0.0,
                "endekse_gore_atr": 4.5, "neden_kodu": code, "aciklama": "a", "etiketler": list(tags),
                "haber_skoru": None, "senaryolar": None, "neden_yok": None}

    def test_eligibility_limit_cache_and_no_hindsight(self):
        items = [self.item("ONC", "HABER_ONEMSIZ"), self.item("NOP", "HABER_YOK"),
                 self.item("MAT", "HABER_YOK", ["ESLESME"]), self.item("LIQ", "LIKIDITE")]
        items += [self.item(f"S{i}", "SENARYO_UYGUN_DEGIL") for i in range(5)]
        self.assertEqual([x["hisse"] for x in ai_comment.eligible(items)][:2], ["ONC", "MAT"])
        llm = FakeLLM("Haber önemsiz sayıldı; %9 yükseldi.")
        rs = ai_comment.explain_missed(self.conn, items, {}, llm=llm)
        self.assertEqual(len(rs), 5)
        self.assertEqual(len(llm.calls), 5)
        onc = llm.calls[0]["user"]
        known, _, later = onc.partition("KARAR ANINDAN SONRA")
        self.assertIn("Önce gelen metin", known)
        self.assertNotIn("SONRAKI GİZLİ METİN", onc)          # sonraki haberin metni verilmez
        self.assertIn("ONC sonraki haber", later)              # yalnız başlığı, "sonra" etiketiyle
        self.assertEqual(rs[0]["dogrulanamayan"], [])           # %9 girdide var
        rs2 = ai_comment.explain_missed(self.conn, items, {}, llm=llm)
        self.assertEqual(len(llm.calls), 7)                     # ilk 5 önbellekten, kalan 2 yeni
        self.assertTrue(all(r.get("onceden") for r in rs2[:5]))
        md = ai_comment.missed_md(rs, len(ai_comment.eligible(items)))
        self.assertIn("**ONC**", md)
        self.assertIn("2 hisse sınır nedeniyle açıklanmadı", md)

    def test_nothing_to_explain(self):
        md = ai_comment.missed_md([], 0)
        self.assertIn("kodla yeterince açık", md)


class SessionIntegrationTests(Base):
    def setUp(self):
        super().setUp()
        self.uni = {"POS": "POS", "NEG": "NEG"}
        for t in self.uni:
            self.conn.execute("INSERT INTO companies VALUES(?,?,NULL)", (t, t))
            seed(self.conn, t)
        seed(self.conn, "XU100")
        news(self.conn, "n1", "POS", 1, 3, 0.9)
        self.conn.commit()

    def run_s(self, settings, llm=None, kind="aksam", hh=19):
        out = watchdog.run_session(self.conn, self.uni, kind, settings, now=at(TODAY, hh),
                                   steps={"prices": lambda: {}, "update": lambda: {}, "llm": llm})
        return out, (watchdog.report_dir() / f"{out['rapor']}.md").read_text(encoding="utf-8")

    def test_ai_section_appended_code_sections_unchanged(self):
        _, plain = self.run_s({})
        llm = FakeLLM()
        out, md = self.run_s({"yz_rapor": True, "yz_kacirilan": True}, llm=llm)
        self.assertEqual(len(llm.calls), 1)                     # kaçırılan yok → yalnız rapor yorumu
        head = md.split("\n## 🤖 Yapay zekâ yorumu")[0]
        self.assertEqual(head, plain.split("\n---\n_Bu rapor")[0])  # kodla hesaplanan bölümler birebir aynı
        self.assertLess(md.index("## 🤖 Yapay zekâ yorumu"), md.index("yatırım tavsiyesi değildir. Emirleri"))
        self.assertIn("## 🤖 Kaçırılan fırsat açıklamaları", md)
        self.assertTrue(out["yz_yorum"]["ok"])
        self.assertIn("yalnız 🤖 işaretli bölümler yapay zekâ yorumudur", md)
        self.assertNotIn("(yapay zekâ yorumu yok)", md)

    def test_off_by_default_no_call(self):
        llm = FakeLLM()
        _, md = self.run_s({}, llm=llm)
        self.assertEqual(llm.calls, [])
        self.assertNotIn("🤖", md)

    def test_morning_comment_and_failure_still_archives(self):
        out, md = self.run_s({"yz_rapor": True}, llm=FakeLLM(fail=True), kind="sabah", hh=8)
        self.assertIn("Yapay zekâ yorumu alınamadı", md)
        self.assertIn("## 7. Veri durumu", md)


if __name__ == "__main__":
    unittest.main()
