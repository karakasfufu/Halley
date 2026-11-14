"""Aşama 3 (2026-11-14): Python ön eleme kuralları. Henüz analiz akışına bağlı DEĞİL (kullanıcı onayı bekleniyor)."""
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

    def test_not_wired_into_analysis_yet(self):
        from bist_haber import config
        src = (Path(config.ROOT) / "bist_haber" / "analyzer.py").read_text(encoding="utf-8")
        self.assertNotIn("prefilter", src)          # kullanıcı onayından sonra bağlanacak


if __name__ == "__main__":
    unittest.main()
