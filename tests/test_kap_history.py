"""Takvim için KAP geçmişi: ağ yok (sahte liste ve sayfa). En önemli kural: kayıtlar yapay zekâ kuyruğuna girmez."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from bist_haber import analyzer, corp_events, db, earnings, kap, kap_history

from test_corp_events import BEDELSIZ


def item(idx, subject, code, when="05.11.2026 18:30:00"):
    return {"disclosureIndex": idx, "subject": subject, "stockCodes": code, "publishDate": when, "kapTitle": code,
            "summary": subject}


ITEMS = [dict(item(1, "Finansal Rapor", "AAA", "28.10.2026 18:30:00"), year=2026, period=3),  # KAP: 9 aylık
         item(2, "Sorumluluk Beyanı (Konsolide)", "AAA", "28.10.2026 18:31:00"),
         item(3, "Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim", "AAA", "01.11.2026 10:00:00"),
         item(4, "Özel Durum Açıklaması (Genel)", "AAA"),          # takvim konusu değil → alınmaz
         item(5, "Finansal Rapor", "ZZZ"),                          # evren dışı → alınmaz
         item(6, "Genel Kurul İşlemlerine İlişkin Bildirim", "AAA", "02.11.2026 10:00:00")]


class BackfillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        self.uni = {"AAA": "AAA A.Ş."}
        self.pages = []

    def page(self, index):
        self.pages.append(index)
        return BEDELSIZ.replace("14.09.2026", "12.11.2026") if index == 3 else ""

    def run_backfill(self):
        def listing(a, b):
            return ITEMS
        listing.records_coverage = True   # gerçek KAP listesi gibi: alınan günler "tarandı" sayılır
        return kap_history.backfill(self.conn, self.uni, days=45, today=date(2026, 11, 7),
                                    list_fn=listing, page_fn=self.page, sleep=lambda s: None)

    def test_only_calendar_subjects_stored_and_never_queued_for_ai(self):
        st = self.run_backfill()
        rows = {r["id"]: dict(r) for r in self.conn.execute("SELECT id, status, body, note FROM news")}
        self.assertEqual(set(rows), {"kap:1", "kap:2", "kap:3", "kap:6"})
        self.assertTrue(all(r["status"] == "context" for r in rows.values()))
        self.assertEqual(analyzer.pending(self.conn), [])            # yapay zekâ kuyruğu boş → kredi yok
        self.assertEqual(sorted(self.pages), [3, 6])                 # yalnız olay bildirimlerinin sayfası okundu
        self.assertEqual((st["eklenen"], st["metin_alinan"], st["metin_bekleyen"], st["bos_sayfa"]), (4, 1, 0, 1))

    def test_calendar_modules_use_backfilled_records(self):
        self.run_backfill()
        s = earnings.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["durum"], s["aciklama_tarihi"], s["konsolide"]), ("açıklandı", "2026-10-28", True))
        up = corp_events.upcoming(self.conn, "AAA", date(2026, 11, 7), 15)
        self.assertIn("2026-11-12", [e["tarih"] for e in up["yaklasan"] if e["tur"] == "bedelsiz_hak"])

    def test_rerun_is_idempotent_empty_pages_not_retried_network_errors_retried(self):
        self.run_backfill()
        self.pages.clear()
        st = self.run_backfill()
        self.assertEqual(st["eklenen"], 0)
        self.assertEqual(self.pages, [])                              # boş sayfa sonsuz denenmez
        import requests
        self.conn.execute("UPDATE news SET body=NULL WHERE id='kap:3'")
        calls = []
        def flaky(index):
            calls.append(index)
            raise requests.ConnectionError("koptu")
        st = kap_history.backfill(self.conn, self.uni, today=date(2026, 11, 7), list_fn=lambda a, b: ITEMS,
                                  page_fn=flaky, sleep=lambda s: None)
        self.assertEqual((calls, st["metin_bekleyen"]), ([3], 1))     # ağ hatası → yeniden denenecek
        self.assertIsNone(self.conn.execute("SELECT body FROM news WHERE id='kap:3'").fetchone()[0])

    def test_rate_limit_stops_round(self):
        def limited(index):
            raise kap.RateLimited("429")
        st = kap_history.backfill(self.conn, self.uni, today=date(2026, 11, 7), list_fn=lambda a, b: ITEMS,
                                  page_fn=limited, sleep=lambda s: None)
        self.assertTrue(st["kap_siniri"])
        self.assertEqual(st["metin_bekleyen"], 2)


    def test_period_and_coverage_recorded(self):
        self.run_backfill()
        self.assertEqual(self.conn.execute("SELECT donem FROM news WHERE id='kap:1'").fetchone()[0], "2026/3")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM kap_coverage").fetchone()[0], 45)

    def test_fill_gaps_lists_only_missing_days(self):
        from bist_haber import kap
        kap.record_coverage(self.conn, date(2026, 9, 24), date(2026, 10, 31), "2026-11-01T09:00:00+03:00")
        asked = []
        def listing(a, b):
            asked.append((a.isoformat(), b.isoformat()))
            return []
        listing.records_coverage = True
        res = kap_history.fill_gaps(self.conn, self.uni, lookback_days=45, today=date(2026, 11, 7), list_fn=listing)
        self.assertEqual(asked, [("2026-11-01", "2026-11-07")])
        self.assertEqual(res["bosluk_gun"], 7)
        self.assertEqual(kap.coverage_gaps(self.conn, date(2026, 9, 24), date(2026, 11, 7), date(2026, 11, 7)), [])
        self.assertEqual(kap_history.fill_gaps(self.conn, self.uni, today=date(2026, 11, 7), list_fn=listing)["bosluk_gun"], 0)


class DailyCollectPromotionTests(unittest.TestCase):
    """Takvim için saklanan bildirim günlük güncellemenin penceresine girerse normal analize alınmalı."""

    def test_context_row_promoted_to_new(self):
        with tempfile.TemporaryDirectory() as t:
            conn = db.connect(Path(t) / "t.db")
            kap_history.backfill(conn, {"AAA": "A"}, today=date(2026, 11, 7), list_fn=lambda a, b: ITEMS,
                                 page_fn=lambda i: "", sleep=lambda s: None)
            with patch.object(kap, "list_disclosures", return_value=[ITEMS[0], ITEMS[1]]):
                kap.collect(conn, {"AAA": "A"}, days=1, fetch_bodies=False)
            st = dict(conn.execute("SELECT id, status FROM news").fetchall())
            self.assertEqual(st["kap:1"], "new")                     # Finansal Rapor → analiz sırasına
            self.assertEqual(st["kap:2"], "skipped")                 # Sorumluluk Beyanı → atlanacaklar listesi
            self.assertEqual(st["kap:3"], "context")                 # pencere dışı → takvim kaydı kalır
            conn.close()


if __name__ == "__main__":
    unittest.main()
