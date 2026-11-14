"""Aşama 3 (2026-11-14): Python ön eleme kuralları ve analiz akışına bağlanması (kullanıcı onayıyla)."""
import tempfile
import unittest
from pathlib import Path

from bist_haber import db, prefilter


def row(subject="", title="", body="x", source="kap", candidates="AAA"):
    return {"source": source, "subject": subject, "title": title, "body": body, "candidates": candidates}


GA_GUNLUK = "Özet Bilgi 05.11.2026 Tarihli Hisse Geri Alım İşlemleri Yapılan Açıklama Güncelleme mi ? Evet " \
            "Yönetim Kurulu Karar Tarihi 30.09.2026 Geri Alıma Konu Azami Pay Miktarı"
GA_BASLAT = "Özet Bilgi Pay Geri Alım Programı Başlatılması Yapılan Açıklama Güncelleme mi ? Hayır"


class Classify(unittest.TestCase):
    def k(self, **kw):
        return prefilter.classify(row(**kw))[0]

    def test_important_kap_subjects_always_go_to_ai(self):
        for s in ("Finansal Rapor", "Özel Durum Açıklaması (Genel)", "Yeni İş İlişkisi", "Kar Payı Dağıtım İşlemlerine",
                  "Pay Alım Satım Bildirimi", "Temerrüt İşlemi", "Hiç görülmemiş bir konu", ""):
            self.assertEqual(self.k(subject=s), "ai", s)

    def test_procedural_subjects_are_routine(self):
        for s in ("Portföy Sınırlamalarına Uyumun Kontrolü", "İzahname", "Bağımsız Denetim Kuruluşunun Belirlenmesi",
                  "Fon Kurucusu Tarafından Yapılan Pay Alım Satım Bildirimi"):
            self.assertEqual(self.k(subject=s), "rutin", s)

    def test_buyback_daily_report_routine_but_new_program_ai(self):
        s = "Payların Geri Alınmasına İlişkin Bildirim"
        self.assertEqual(self.k(subject=s, title="X: 05.11.2026 Tarihli Geri Alım İşlemleri", body=GA_GUNLUK), "rutin")
        self.assertEqual(self.k(subject=s, title="X: Pay Geri Alım Programı Başlatılması", body=GA_BASLAT), "ai")
        self.assertEqual(self.k(subject=s, title="X: Geri alım programının sona ermesi", body=GA_GUNLUK), "ai")
        self.assertEqual(self.k(subject=s, title="X: Geri alım", body="alan bilgisi olmayan metin"), "ai")  # emin değil

    def test_general_assembly_with_capital_or_dividend_goes_to_ai(self):
        s = "Genel Kurul İşlemlerine İlişkin Bildirim"
        self.assertEqual(self.k(subject=s, title="X: Genel Kurulun Tescili", body="Tescil edildi."), "rutin")
        self.assertEqual(self.k(subject=s, title="X: Olağanüstü Genel Kurul", body="Gündem: bedelsiz sermaye artırımı"), "ai")
        self.assertEqual(self.k(subject=s, title="X: Olağan Genel Kurul", body="Kâr payı dağıtımı önerisi"), "ai")

    def test_rss(self):
        self.assertEqual(self.k(source="rss:x", title="Tofaş'ın kârı beklentileri aştı", candidates="TOASO"), "ai")
        self.assertEqual(self.k(source="rss:x", title="Merkez Bankası faiz kararını açıkladı", candidates=""), "ai")
        self.assertEqual(self.k(source="rss:x", title="Riyad'daki Aramco binasına saldırı", candidates=""), "ai")
        self.assertEqual(self.k(source="rss:x", title="BIST 100 endeksi güne yükselişle başladı", candidates=""), "rutin")
        self.assertEqual(self.k(source="rss:x", title="Borsa İstanbul haftaya yükselişle başladı", candidates=""), "rutin")
        self.assertEqual(self.k(source="rss:x", title="Ünlü şarkıcının yeni albümü", candidates=""), "rutin")


class Apply(unittest.TestCase):
    def test_apply_moves_only_routine_and_keeps_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "t.db")
            for nid, subj in (("kap:1", "İzahname"), ("kap:2", "Finansal Rapor")):
                conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                             "fetched_at) VALUES(?,'kap','2026-11-10T10:00:00+03:00','2026-11-10','t',?,'metin','AAA','new','f')",
                             (nid, subj))
            conn.commit()
            self.assertEqual(prefilter.apply(conn), {"incelenen": 2, "rutin": 1, "ai": 1})
            st = dict(conn.execute("SELECT id, status FROM news").fetchall())
            self.assertEqual(st, {"kap:1": "skipped", "kap:2": "new"})
            self.assertIn("Python ön eleme", conn.execute("SELECT note FROM news WHERE id='kap:1'").fetchone()[0])
            conn.close()

    def test_wired_into_analysis_manual_choice_respected(self):
        from unittest.mock import patch
        from bist_haber import analyzer, config
        from tests.test_accuracy import FakeClient
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.db"
            conn = db.connect(path)
            conn.execute("INSERT INTO companies VALUES('TEST','Deneme',NULL)")
            for nid, subj in (("kap:1", "İzahname"), ("kap:2", "Yeni İş İlişkisi"), ("kap:3", "İzahname")):
                conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                             "fetched_at) VALUES(?,'kap','2026-11-10T10:00:00+03:00','2026-11-10',?,?,?,'TEST','new','f')",
                             (nid, "Başlık " + nid, subj, "Ayrıntı " * 20 + nid))
            conn.commit()
            with patch.object(config, "DB_PATH", path), patch("bist_haber.prices.company_stats", return_value={}):
                st = analyzer.analyze(conn, {"TEST": "Deneme"}, limit=1, llm=analyzer.LLM("haber_analizi", client=FakeClient()))
                self.assertEqual((st["analyzed"], st.get("rutin")), (1, 2))      # sınır rutin habere harcanmadı
                st_ = dict(conn.execute("SELECT id, status FROM news").fetchall())
                self.assertEqual(st_, {"kap:1": "skipped", "kap:2": "analyzed", "kap:3": "skipped"})
                # kullanıcı elle seçerse ön eleme uygulanmaz
                row = conn.execute("SELECT * FROM news WHERE id='kap:1'").fetchone()
                st2 = analyzer.analyze(conn, {"TEST": "Deneme"}, rows=[row], on_eleme=False,
                                       llm=analyzer.LLM("haber_analizi", client=FakeClient()))
                self.assertEqual(st2["analyzed"], 1)
                # otomatik akışta verilen satırlar (takip/hazır fırsat) da elenir
                r3 = conn.execute("SELECT * FROM news WHERE id='kap:3'").fetchone()
                conn.execute("UPDATE news SET status='new' WHERE id='kap:3'")
                st3 = analyzer.analyze(conn, {"TEST": "Deneme"}, rows=[r3],
                                       llm=analyzer.LLM("haber_analizi", client=FakeClient()))
                self.assertEqual((st3["analyzed"], st3.get("rutin")), (0, 1))
            conn.close()

if __name__ == "__main__":
    unittest.main()
