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


ITEMS = [item(1, "Finansal Rapor", "AAA", "28.10.2026 18:30:00"),
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
        return kap_history.backfill(self.conn, self.uni, days=45, today=date(2026, 11, 7),
                                    list_fn=lambda a, b: ITEMS, page_fn=self.page, sleep=lambda s: None)

    def test_only_calendar_subjects_stored_and_never_queued_for_ai(self):
        st = self.run_backfill()
        rows = {r["id"]: dict(r) for r in self.conn.execute("SELECT id, status, body, note FROM news")}
        self.assertEqual(set(rows), {"kap:1", "kap:2", "kap:3", "kap:6"})
        self.assertTrue(all(r["status"] == "context" for r in rows.values()))
        self.assertEqual(analyzer.pending(self.conn), [])            # yapay zekâ kuyruğu boş → kredi yok
        self.assertEqual(sorted(self.pages), [3, 6])                 # yalnız olay bildirimlerinin sayfası okundu
        self.assertEqual((st["eklenen"], st["metin_alinan"], st["metin_bekleyen"]), (4, 1, 1))

    def test_calendar_modules_use_backfilled_records(self):
        self.run_backfill()
        s = earnings.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["durum"], s["aciklama_tarihi"], s["konsolide"]), ("açıklandı", "2026-10-28", True))
        up = corp_events.upcoming(self.conn, "AAA", date(2026, 11, 7), 15)
        self.assertIn("2026-11-12", [e["tarih"] for e in up["yaklasan"] if e["tur"] == "bedelsiz_hak"])

    def test_rerun_is_idempotent_and_retries_missing_pages(self):
        self.run_backfill()
        self.pages.clear()
        st = self.run_backfill()
        self.assertEqual(st["eklenen"], 0)
        self.assertEqual(self.pages, [6])                            # yalnız metni eksik kalan yeniden denenir

    def test_rate_limit_stops_round(self):
        def limited(index):
            raise kap.RateLimited("429")
        st = kap_history.backfill(self.conn, self.uni, today=date(2026, 11, 7), list_fn=lambda a, b: ITEMS,
                                  page_fn=limited, sleep=lambda s: None)
        self.assertTrue(st["kap_siniri"])
        self.assertEqual(st["metin_bekleyen"], 2)


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
