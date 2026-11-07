"""Birleşik takvim (Parça B4): piyasa + bilanço + şirket olayları tek listede; makro olay riski."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, timeline as T, tradeplan

from test_corp_events import KAR
from test_entries import base

NEWS = {"score": 3, "direction": 1, "confidence": 0.8, "flags": "", "persistence": "orta"}


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))   # kayıtlı resmi takvim (json) karışmasın
        p.start()
        self.addCleanup(p.stop)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO companies VALUES('ETILR','ETİLER GIDA A.Ş.',NULL)")
        # Kapsam dönem başından (bilanço durumu kesin): 9 aylık rapor yok, konsolide bilinmiyor → son gün 9 Kasım
        from bist_haber import kap
        kap.record_coverage(self.conn, date(2026, 10, 1), date(2026, 11, 7), "2026-11-07T12:00:00+03:00")
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                          "fetched_at) VALUES('k1','kap','2026-11-01T10:00:00+03:00','2026-11-02','t',"
                          "'Kar Payı Dağıtım İşlemlerine İlişkin Bildirim',?,'ETILR','context','n')",
                          (KAR.replace("29.09.2026", "20.11.2026"),))
        self.conn.commit()

    def test_merged_and_sorted(self):
        tl = T.for_ticker(self.conn, "ETILR", date(2026, 11, 7), 15)
        rows = [(x["tarih"], x["kapsam"], x["tur"]) for x in tl["olaylar"]]
        self.assertEqual(rows, [("2026-11-09", "Hisse", "bilanco"), ("2026-11-12", "Piyasa", "er"),
                                ("2026-11-20", "Hisse", "temettu_gk"), ("2026-11-27", "Piyasa", "fir")])
        self.assertEqual(tl["olaylar"][0]["is_gunu_sonra"], 1)
        self.assertEqual(tl["bitis"], "2026-11-27")
        self.assertIn("brüt 0.0180 TL/pay", tl["olaylar"][2]["ayrinti"])

    def test_compact_text(self):
        txt = T.compact(T.for_ticker(self.conn, "ETILR", date(2026, 11, 7), 15))
        self.assertTrue(txt.startswith("9.11 2026 9 aylık bilanço yasal son günü; 12.11 TCMB Enflasyon Raporu"), txt)

    def test_unread_calendar_pages_are_warned(self):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                          "fetched_at) VALUES('k9','kap','2026-10-15T10:00:00+03:00','2026-10-15','t',"
                          "'Genel Kurul İşlemlerine İlişkin Bildirim',NULL,'ETILR','context','n')")
        self.conn.commit()
        tl = T.for_ticker(self.conn, "ETILR", date(2026, 11, 7), 15)
        self.assertEqual(tl["okunmamis"], 1)
        self.assertIn("1 takvim bildiriminin", tl["okunmamis_notu"])
        self.conn.execute("UPDATE news SET body='x' WHERE id='k9'")
        self.assertIsNone(T.for_ticker(self.conn, "ETILR", date(2026, 11, 7), 15)["okunmamis_notu"])

    def test_published_report_not_listed(self):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,candidates,fetched_at,"
                          "donem) VALUES('k2','kap','2026-11-05T18:00:00+03:00','2026-11-06','x','Finansal Rapor','ETILR',"
                          "'n','2026/3')")
        self.conn.commit()
        tl = T.for_ticker(self.conn, "ETILR", date(2026, 11, 7), 15)
        self.assertNotIn("bilanco", [x["tur"] for x in tl["olaylar"]])


class MacroRiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)

    def test_lists_key_macro_events_only(self):
        r = T.macro_risk(date(2026, 11, 26), 15)
        self.assertEqual(r.split(" — ")[0], "Vade içinde piyasa geneli olay: 3.12 TÜFE, 9.12 Fed kararı, 10.12 TCMB faiz kararı")
        self.assertNotIn("Finansal İstikrar", r)                  # FİR, özet, VİOP risk sayılmaz (yalnız takvimde)

    def test_none_when_quiet(self):
        self.assertIsNone(T.macro_risk(date(2026, 8, 17), 5))     # 17–21 Ağustos 2026: önemli makro olay yok

    def test_macro_risk_is_one_point(self):
        msg = T.macro_risk(date(2026, 11, 26), 15)
        calm = tradeplan.plan(base(), NEWS)
        hot = tradeplan.plan(base(), dict(NEWS, makro_riski=msg))
        self.assertIn(msg, hot["riskler"])
        self.assertEqual(tradeplan._points(hot["riskler"]) - tradeplan._points(calm["riskler"]), 1)


if __name__ == "__main__":
    unittest.main()
