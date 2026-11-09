"""2026-11-09 Telegram bildirimi: gönderim, alıcı bulma, .env kaydı, mesaj metni, sabah/akşam analizine bağlantı.
Gerçek Telegram'a hiç bağlanılmaz (sahte post işlevi)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from bist_haber import config, notify, watchdog
from tests import test_watchdog_w2 as w2
from tests.test_watchdog_w2 import at, TODAY

TOK = "123456:SECRET-abc"


class FakeResp:
    def __init__(self, body, code=200):
        self.body, self.status_code = body, code

    def json(self):
        return self.body


class FakePost:
    def __init__(self, replies=None):
        self.calls, self.replies = [], replies or {}

    def __call__(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        r = self.replies.get(str((json or {}).get("chat_id")))
        if isinstance(r, Exception):
            raise r
        return r or FakeResp({"ok": True, "result": []})


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (patch.object(config, "ROOT", Path(self.tmp.name)),
                  patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""})):
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("HALLEY_OFFLINE", None)

    def test_send_to_each_chat_and_keep_going_on_error(self):
        post = FakePost({"2": FakeResp({"ok": False, "description": "Bad Request: chat not found"}, 400),
                         "3": requests.ConnectionError(f"HTTPSConnectionPool(host='api.telegram.org') bot{TOK}")})
        r = notify.send("merhaba", tok=TOK, chats=["1", "2", "3"], post=post)
        self.assertEqual(r["gonderilen"], 1)
        self.assertFalse(r["ok"])
        self.assertEqual(len(post.calls), 3)
        self.assertIn("/start", r["hatalar"][0])
        self.assertIn("bağlanılamadı", r["hatalar"][1])
        self.assertNotIn(TOK, " ".join(r["hatalar"]))                # anahtar ekrana/rapora sızmaz
        self.assertTrue(post.calls[0][0].endswith("/sendMessage"))

    def test_bad_token_and_not_configured_and_offline(self):
        post = FakePost({"1": FakeResp({"ok": False, "description": "Unauthorized"}, 401)})
        self.assertIn("geçersiz", notify.send("x", tok=TOK, chats=["1"], post=post)["hatalar"][0])
        self.assertIn("ayarlanmamış", notify.send("x", post=post)["hatalar"][0])
        with patch.dict(os.environ, {"HALLEY_OFFLINE": "1"}):
            post2 = FakePost()
            self.assertFalse(notify.send("x", tok=TOK, chats=["1"], post=post2)["ok"])
            self.assertEqual(post2.calls, [])                         # deneme kipinde ağa çıkılmaz

    def test_long_message_is_cut(self):
        post = FakePost()
        notify.send("a" * 9000, tok=TOK, chats=["1"], post=post)
        self.assertLessEqual(len(post.calls[0][1]["text"]), 4096)

    def test_find_chats_lists_people_and_groups(self):
        body = {"ok": True, "result": [
            {"message": {"chat": {"id": 11, "first_name": "Ali", "last_name": "Veli", "type": "private"}}},
            {"message": {"chat": {"id": 11, "first_name": "Ali", "last_name": "Veli", "type": "private"}}},
            {"my_chat_member": {"chat": {"id": -500, "title": "Halley grubu", "type": "group"}}}]}
        got = notify.find_chats(TOK, post=lambda *a, **k: FakeResp(body))
        self.assertEqual(sorted((c["id"], c["ad"]) for c in got), [("-500", "Halley grubu"), ("11", "Ali Veli")])

    def test_save_keeps_openai_key(self):
        env = Path(self.tmp.name) / ".env"
        env.write_text("OPENAI_API_KEY=sk-x\n", encoding="utf-8")
        notify.save(tok=TOK)
        notify.save(chats=["11", "-500"])
        notify.save(tok=TOK + "2")
        text = env.read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=sk-x", text)
        self.assertEqual(text.count("TELEGRAM_BOT_TOKEN="), 1)
        self.assertIn(f"TELEGRAM_BOT_TOKEN={TOK}2", text)
        self.assertEqual(notify.chat_ids(), ["11", "-500"])
        self.assertTrue(notify.configured())

    def test_message_text(self):
        out = {"zaman": {"zaman": "2026-11-09T09:15:00+03:00", "uyari": None}, "rapor": "2026-11-09_sabah",
               "gunluk": {"degisenler": [
                   {"id": 7, "hisse": "ASELS", "kaynak": "gercek", "yeni": "kapandı", "sonuc": "TP2", "net_%": 8.4},
                   {"id": 8, "hisse": "BRK", "kaynak": "otomatik", "yeni": "iptal", "sonuc": "gerçekleşmedi"}]}}
        data = {"onerilen": [{"ticker": "THYAO", "senaryo": "kirilim", "giris": 300, "sl": 290, "tp1": 310,
                              "tp2": 320, "risk_seviyesi": "orta"}],
                "takip": [{"ticker": "SISE"}], "riskli": [{"no": 3, "hisse": "EREGL", "stop_uzaklik_%": 1.2}]}
        t = notify.session_message("sabah", out, data)
        for s in ("🌅 Halley sabah analizi — 09.11 09:15", "THYAO — kirilim · giriş 300.00 · SL 290.00",
                  "henüz önerilmeyen: SISE", "#3 EREGL: stopa yalnız %1.2", "#7 ASELS (gerçek): kapandı — TP2 · net %+8.40",
                  "#8 BRK (sanal): süresi doldu", "yatırım tavsiyesi değildir"):
            self.assertIn(s, t)
        self.assertIn("uygun giriş senaryosu yok", notify.session_message("aksam", out, {}))
        # takip listesine daraltma: THYAO takipte değil → yazılmaz, sayısı belirtilir; GERÇEK işlem her zaman yazılır
        n = notify.session_message("sabah", out, data, watch={"SISE"})
        self.assertNotIn("THYAO —", n)
        self.assertIn("Takip listeniz dışında 1 hissede", n)
        self.assertIn("#7 ASELS (gerçek)", n)
        self.assertNotIn("#8 BRK", n)
        self.assertNotIn("EREGL", n)
        self.assertIn("SISE", n)


class SessionHookTests(unittest.TestCase):
    """Analiz bitince gönderilir; kapalıyken gönderilmez; gönderim hatası analizi ve raporu bozmaz."""
    setUp = w2.SessionTests.setUp

    def test_sent_after_report_when_enabled(self):
        sent = []
        with patch.object(notify, "send", lambda text: sent.append(text) or {"ok": True, "gonderilen": 1, "hatalar": []}):
            out = watchdog.run_session(self.conn, self.uni, "aksam", {"telegram": True}, now=at(TODAY, 19),
                                       steps=self.steps)
            off = watchdog.run_session(self.conn, self.uni, "sabah", {}, now=at(TODAY, 8), steps=self.steps)
        self.assertEqual(len(sent), 1)
        self.assertIn("🌙 Halley akşam analizi", sent[0])
        self.assertTrue(out["bildirim"]["ok"])
        self.assertNotIn("bildirim", off)

    def test_send_failure_does_not_break_session(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": TOK, "TELEGRAM_CHAT_ID": "1"}), \
                patch.object(requests, "post", side_effect=requests.ConnectionError("ağ yok")):
            os.environ.pop("HALLEY_OFFLINE", None)
            out = watchdog.run_session(self.conn, self.uni, "sabah", {"telegram": True}, now=at(TODAY, 8),
                                       steps=self.steps)
        self.assertFalse(out["bildirim"]["ok"])
        self.assertTrue((watchdog.report_dir() / f"{out['rapor']}.md").exists())


if __name__ == "__main__":
    unittest.main()
