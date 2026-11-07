"""Arka plan KAP okuyucu: sahte KAP her turda 100 sayfadan sonra sınır uygular (2026-11-07 gözlemine benzer).
Ağ ve gerçek bekleme yok; saat ve uyku sahte."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, kap_worker as K


class FakeClock:
    def __init__(self):
        self.t = 1_000_000.0
        self.sleeps = []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.db"
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        conn = db.connect(self.path)
        conn.execute("INSERT INTO companies VALUES('AAA','AAA A.Ş.',NULL)")
        for i in range(250):
            conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                         "fetched_at) VALUES(?,?,?,?,?,?,NULL,'AAA','context','n')",
                         (f"kap:{i}", "kap", "2026-10-01T10:00:00+03:00", "2026-10-01", "t",
                          "Genel Kurul İşlemlerine İlişkin Bildirim"))
        conn.commit()
        conn.close()
        self.fc = FakeClock()

    def limited_backfill(self, per_round=100):
        def fn(conn):
            rows = conn.execute("SELECT id FROM news WHERE status='context' AND body IS NULL LIMIT ?", (per_round,)).fetchall()
            for r in rows:
                conn.execute("UPDATE news SET body='Genel Kurul Tarihi\n20.11.2026' WHERE id=?", (r["id"],))
            conn.commit()
            left = conn.execute("SELECT COUNT(*) FROM news WHERE status='context' AND body IS NULL").fetchone()[0]
            return {"kap_siniri": left > 0}
        return fn

    def run_worker(self, backfill_fn, **kw):
        return K.run(self.path, sleep=self.fc.sleep, clock=self.fc.clock, backfill_fn=backfill_fn,
                     fetch_new_fn=lambda c: {"rate_limited": False}, **kw)

    def test_waits_and_continues_until_complete_then_summarises(self):
        st = self.run_worker(self.limited_backfill())
        self.assertEqual((st["durum"], st["okunan"], st["kalan"]), ("tamamlandı", 250, 0))
        self.assertEqual(self.fc.sleeps, [3 * 60, 5 * 60])           # 100 + 100 + 50: iki kez KAP sınırı beklendi
        self.assertEqual(st["kap_siniri_sayisi"], 2)
        self.assertIn("ozet", st)
        self.assertFalse(st["devam_gerek"])
        self.assertEqual(K.load()["durum"], "tamamlandı")              # panel bu dosyadan okur

    def test_wait_grows_to_ten_minutes(self):
        self.run_worker(self.limited_backfill(per_round=50))         # 5 sınır: 3, 5, 10, 10
        self.assertEqual(self.fc.sleeps, [180, 300, 600, 600])

    def test_no_progress_without_limit_stops(self):
        st = self.run_worker(lambda c: {"kap_siniri": False})
        self.assertEqual(st["durum"], "durdu")
        self.assertIn("okunamadı", st["mesaj"])
        self.assertEqual(self.fc.sleeps, [])

    def test_safety_time_limit(self):
        st = self.run_worker(lambda c: {"kap_siniri": True}, max_hours=0.5)
        self.assertEqual(st["durum"], "durdu")
        self.assertTrue(st["devam_gerek"])                            # sonraki açılışta sürer
        self.assertIn("güvenlik süresi", st["mesaj"])

    def test_pending_counts_include_daily_news_bodies(self):
        conn = db.connect(self.path)
        conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                     "fetched_at) VALUES('kap:x','kap','2026-11-07T10:00:00+03:00','2026-11-07','t','Özel Durum',NULL,"
                     "'AAA','new','n')")
        conn.commit()
        self.assertEqual(K.pending_counts(conn), {"takvim": 250, "haber": 1, "toplam": 251})
        conn.close()


class StartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.db"
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.calls = []
        q = patch.object(K, "run", lambda db_path=None: self.calls.append(db_path))
        q.start()
        self.addCleanup(q.stop)

    def add(self, n):
        conn = db.connect(self.path)
        for i in range(n):
            conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                         "fetched_at) VALUES(?,?,?,?,?,?,NULL,'AAA','context','n')",
                         (f"kap:{i}", "kap", "2026-10-01T10:00:00+03:00", "2026-10-01", "t",
                          "Genel Kurul İşlemlerine İlişkin Bildirim"))
        conn.commit()
        conn.close()

    def wait(self):
        for _ in range(50):
            if not K.running():
                return
            time.sleep(0.02)

    def test_small_backlog_without_limit_does_not_autostart(self):
        self.add(14)
        self.assertFalse(K.start(self.path))
        self.assertTrue(K.start(self.path, force=True))               # düğme her zaman başlatır
        self.wait()

    def test_large_backlog_autostarts(self):
        self.add(150)
        self.assertTrue(K.start(self.path))
        self.wait()
        self.assertEqual(self.calls, [self.path])

    def test_previous_rate_limit_autostarts_small_backlog(self):
        self.add(14)
        K.note_rate_limited()
        self.assertTrue(K.start(self.path))
        self.wait()

    def test_nothing_pending(self):
        db.connect(self.path).close()
        self.assertFalse(K.start(self.path, force=True))



class PanelStatusTests(unittest.TestCase):
    def render(self, state):
        import os
        from datetime import datetime
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as t, patch.object(config, "DATA", Path(t)),                 patch.object(config, "DB_PATH", Path(t) / "live.db"),                 patch.dict(os.environ, {"OPENAI_API_KEY": "", "HALLEY_OFFLINE": "1"}):
            db.connect().close()
            if state:
                K._save(state)
            at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            at.run(timeout=30)
            self.assertEqual(len(at.exception), 0, str(at.exception))
            return [e.value for e in list(at.info) + list(at.success) + list(at.warning)]

    def test_running_completed_and_stopped_messages(self):
        from datetime import datetime
        texts = self.render({"durum": "çalışıyor", "okunan": 99, "kalan": 14,
                             "mesaj": "KAP istek sınırı uyguladı; 3 dk bekleniyor, 15:10 civarı kendiliğinden devam edilecek."})
        self.assertTrue(any("arka planda okunuyor: 99/113" in x and "kendiliğinden devam" in x for x in texts), texts)
        today = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
        texts = self.render({"durum": "tamamlandı", "okunan": 113, "kalan": 0, "bitti": today,
                             "mesaj": "Tamamlandı: 113 sayfa okundu, KAP sınırı 1 kez beklendi.", "analiz_bekleyen": 3,
                             "ozet": {"olay": 48, "sirket": 23, "onemli": ["FROTO 26.11 temettü hak kullanımı (brüt 3.07 TL)"]}})
        self.assertTrue(any("113 sayfa okundu" in x and "23 şirkette 48 olay" in x and "FROTO 26.11" in x
                            and "3 haberin metni hazır" in x for x in texts), texts)
        texts = self.render({"durum": "durdu", "mesaj": "2 sayfa bu sefer okunamadı"})
        self.assertTrue(any("KAP okuyucu durdu" in x for x in texts), texts)
        self.assertFalse(any("KAP" in x for x in self.render(None)))


if __name__ == "__main__":
    unittest.main()
