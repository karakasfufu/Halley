"""Takip Listem + bekçi (2026-11-09): senaryo kaydı, kapanış ve gün içi olayları, tekrar engeli, eski veri,
bildirim türü filtreleri, zamanlama, takipten çıkarma, performans. Ağa çıkılmaz (sahte fiyat/teklif/gönderim)."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, pipeline, tracker
from tests.test_signals import TODAY, seed, weekdays_back

TZ = config.TR_TZ
D0 = TODAY.isoformat()                              # 2026-11-06 Cuma
D1, D2, D3 = "2026-11-09", "2026-11-10", "2026-11-11"


def at(day, hh, mm=0):
    y, m, d = map(int, day.split("-"))
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        for p in (patch.object(config, "DATA", t), patch.object(pipeline, "SETTINGS_FILE", t / "ayarlar.json"),
                  patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "1:x", "TELEGRAM_CHAT_ID": "7", "HALLEY_OFFLINE": "1"})):
            p.start()
            self.addCleanup(p.stop)
        self.conn = db.connect(t / "t.db")
        self.addCleanup(self.conn.close)
        for tk in ("POS", "TST"):
            self.conn.execute("INSERT INTO companies VALUES(?,?,NULL)", (tk, tk + " A.Ş."))
        seed(self.conn, "POS")
        for d in weekdays_back(TODAY, 60):          # düz fiyat: 100 (99–101), hacim 1 milyon
            self.bar("TST", d.isoformat(), 100, 101, 99, 100)
        self.conn.execute("INSERT INTO watchlist(ticker, eklendi) VALUES('TST','x')")
        self.conn.commit()
        self.sent = []

    def bar(self, tk, day, o, h, l, c, v=1_000_000):
        self.conn.execute("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                          (tk, day, o, h, l, c, v))

    def scen(self, kind="destek", giris=98, sl=95, tp1=104, tp2=110, alarm=None, valid=5):
        cur = self.conn.execute("INSERT INTO takip_senaryo(ticker,senaryo,signal_day,olusturuldu,emir,alarm,giris,sl,tp1,"
                                "tp2,gecerlilik,kalite) VALUES('TST',?,?,'x','limit',?,?,?,?,?,?,'iyi')",
                                (kind, D0, alarm, giris, sl, tp1, tp2, valid))
        self.conn.commit()
        return cur.lastrowid

    def keys(self):
        return {r["anahtar"] for r in self.conn.execute("SELECT anahtar FROM takip_olay")}

    def send(self, text):
        self.sent.append(text)
        return {"ok": True, "gonderilen": 1, "hatalar": []}


class WatchlistTests(Base):
    def test_add_remove_keeps_history_and_no_duplicate_scenarios(self):
        res = tracker.add(self.conn, "pos")
        self.assertTrue(tracker.is_watched(self.conn, "POS"))
        self.assertTrue(res["yeni"] or res.get("neden"))
        n = len(tracker.scenarios(self.conn, "POS"))
        tracker.remove(self.conn, "POS")
        self.assertFalse(tracker.is_watched(self.conn, "POS"))
        self.assertEqual(len(tracker.scenarios(self.conn, "POS")), n)          # geçmiş silinmez
        tracker.add(self.conn, "POS")                                          # yeniden takip: aynı türler eklenmez
        self.assertEqual(len(tracker.scenarios(self.conn, "POS")), n)
        with self.assertRaises(ValueError):
            tracker.add(self.conn, "YOKBOYLE")

    def test_prices_refreshed_before_scenarios(self):
        calls = []
        fn = lambda conn, tickers, period: calls.append((tuple(tickers), period))
        tracker.ensure_prices(self.conn, "TST", fn, at(D1, 19))           # 60 gün geçmiş → 1 yıl
        tracker.ensure_prices(self.conn, "POS", fn, at(D1, 19))           # 260 gün ama son fiyat cuma → 1 ay
        tracker.ensure_prices(self.conn, "POS", fn, at(D1, 17))           # pazartesi kapanış olmadı → güncel
        self.assertEqual(calls, [(("TST",), "1y"), (("POS",), "1mo")])
        boom = lambda *a, **k: (_ for _ in ()).throw(OSError("ağ yok"))
        self.assertIn("güncellenemedi", tracker.ensure_prices(self.conn, "TST", boom, at(D1, 19)))
        self.assertIn("güncellenemedi", tracker.add(self.conn, "TST", price_fn=boom)["uyari"])

    def test_short_history_gives_reason_not_fake_scenario(self):
        self.conn.execute("INSERT INTO companies VALUES('NEW','Yeni A.Ş.',NULL)")
        for d in weekdays_back(TODAY, 10):
            self.bar("NEW", d.isoformat(), 10, 10.2, 9.8, 10)
        res = tracker.add(self.conn, "NEW")
        self.assertEqual(res["yeni"], [])
        self.assertIn("yetersiz", res["neden"])


class CloseCheckTests(Base):
    def test_entry_tp1_tp2_events_once_each(self):
        sid = self.scen()
        self.bar("TST", D1, 99, 100, 97, 99.5, v=5_000_000)        # limit 98 doldu + hacim 5 kat
        tracker.close_check(self.conn, D1, at(D1, 19))
        self.bar("TST", D2, 100, 105, 99.5, 104.5)                 # TP1 104 + 20 günlük zirve (101) üstünde kapanış
        tracker.close_check(self.conn, D2, at(D2, 19))
        self.bar("TST", D3, 105, 111, 104.8, 110.5)                # TP2 110
        tracker.close_check(self.conn, D3, at(D3, 19))
        k = self.keys()
        for key in (f"s{sid}:giris", f"s{sid}:tp1", f"s{sid}:son", f"TST:{D1}:hacim", f"TST:{D2}:direnc"):
            self.assertIn(key, k)
        rec = tracker.scenarios(self.conn, "TST")
        rec = next(r for r in rec if r["id"] == sid)
        self.assertEqual((rec["durum"], rec["sonuc"]["sonuc"]), ("kapandı", "TP2"))
        before = self.conn.execute("SELECT COUNT(*) FROM takip_olay").fetchone()[0]
        tracker.close_check(self.conn, D3, at(D3, 20))                       # aynı gün yeniden: tekrar olay yok
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM takip_olay").fetchone()[0], before)

    def test_breakout_below_its_sl_before_breakout_stays_waiting(self):
        # Gerçek veri denemesinde (ASELS) yanlışlıkla "geçersiz" sayılıyordu: kırılımda SL kırılan seviyenin altıdır,
        # kırılımdan önce fiyatın SL altında olması olağandır; senaryo süresi dolana dek bekler.
        sid = self.scen(kind="kirilim", giris=105.5, sl=99.5, tp1=110, tp2=115, alarm=105)
        self.bar("TST", D1, 99.6, 99.8, 98.5, 99.0)
        tracker.close_check(self.conn, D1, at(D1, 19))
        rec = next(r for r in tracker.scenarios(self.conn, "TST") if r["id"] == sid)
        self.assertEqual(rec["durum"], "bekliyor")
        self.assertNotIn(f"s{sid}:son", self.keys())

    def test_limit_close_below_sl_without_fill_invalidates(self):
        # Limit dolmadan kapanışın SL altında olması gerçekte olamaz (dip girişe değer); kayıt elle bozulursa kural çalışır
        sid = self.scen(giris=98, sl=95)
        self.conn.execute("UPDATE takip_senaryo SET giris=90 WHERE id=?", (sid,))   # giriş 90 < SL 95 (bozuk kayıt)
        self.bar("TST", D1, 96, 96.5, 93.5, 94)
        tracker.close_check(self.conn, D1, at(D1, 19))
        rec = next(r for r in tracker.scenarios(self.conn, "TST") if r["id"] == sid)
        self.assertEqual(rec["durum"], "geçersiz")
        self.assertIn(f"s{sid}:son", self.keys())

    def test_lower_wick_rising_close_confirmation(self):
        sid = self.scen(giris=97.5, sl=94, tp1=104, tp2=110)
        self.bar("TST", D1, 99.0, 100.6, 97.0, 100.5)              # uzun alt fitil, yükselen kapanış
        tracker.close_check(self.conn, D1, at(D1, 19))
        self.assertIn(f"s{sid}:{D1}:fitil", self.keys())

    def test_missing_day_produces_no_events(self):
        self.scen()
        res = tracker.close_check(self.conn, D1, at(D1, 19))       # D1 fiyatı yok (veri kesildi)
        self.assertEqual(res["veri_yok"], ["TST"])
        self.assertEqual(self.keys(), set())


class IntradayTests(Base):
    def q(self, now, low, high, last, vol=100_000, age_min=20):
        return {"TST": {"zaman": now - timedelta(minutes=age_min), "son": last, "yuksek": high, "dusuk": low,
                        "hacim": vol}}

    def test_entry_touch_is_provisional_and_once(self):
        sid = self.scen()
        now = at(D1, 11)
        tracker.intraday_check(self.conn, self.q(now, 97.9, 100, 98.5), now)
        tracker.intraday_check(self.conn, self.q(now + timedelta(minutes=5), 97.5, 100, 98), now + timedelta(minutes=5))
        rows = [dict(r) for r in self.conn.execute("SELECT * FROM takip_olay")]
        self.assertEqual([(r["anahtar"], r["kesin"]) for r in rows], [(f"s{sid}:giris_gi", 0)])

    def test_stale_or_missing_quote_gives_no_signal(self):
        self.scen()
        now = at(D1, 11)
        res = tracker.intraday_check(self.conn, self.q(now, 90, 120, 95, vol=9e9, age_min=120), now)
        self.assertEqual(res["veri_yok"], ["TST"])
        tracker.intraday_check(self.conn, {}, now)
        self.assertEqual(self.keys(), set())

    def test_open_trade_sl_tp_and_volume(self):
        sid = self.scen()
        self.conn.execute("UPDATE takip_senaryo SET durum='açık', sonuc_json=? WHERE id=?", (json.dumps({"stop": 95}), sid))
        now = at(D1, 15)
        tracker.intraday_check(self.conn, self.q(now, 94.9, 104.2, 100, vol=2_000_000), now)
        k = self.keys()
        self.assertTrue({f"s{sid}:sl_gi:95.0000", f"s{sid}:tp1_gi", f"TST:{D1}:hacim_gi"} <= k, k)


class DispatchTests(Base):
    def test_type_filter_scenario_switch_and_retry(self):
        sid, sid2 = self.scen(), self.scen(kind="geri_cekilme")
        now = at(D1, 19)
        tracker._event(self.conn, now, "TST", "giris", "giriş", "a", sid)
        tracker._event(self.conn, now, "TST", "tp", "tp1", "b", sid)
        tracker._event(self.conn, now, "TST", "tp", "tp diğer", "c", sid2)
        tracker.set_types(self.conn, "TST", ["sl", "tp"])
        tracker.set_scenario_alert(self.conn, sid2, False)
        fail = lambda text: {"ok": False, "gonderilen": 0, "hatalar": ["7: ağ yok"]}
        tracker.dispatch(self.conn, fail, now)
        st = {r["anahtar"]: (r["gonderildi"], r["hata"]) for r in self.conn.execute("SELECT * FROM takip_olay")}
        self.assertEqual(st["a"][0], -1)                 # giriş türü kapalı
        self.assertEqual(st["c"][0], -1)                 # senaryo bildirimi kapalı
        self.assertEqual(st["b"], (0, "7: ağ yok"))      # gönderilemedi → yeniden denenecek
        tracker.dispatch(self.conn, self.send, now + timedelta(minutes=2))
        self.assertEqual(len(self.sent), 1)
        self.assertIn("tp1", self.sent[0])
        self.assertNotIn("giriş", self.sent[0].split("TST")[1])
        tracker.dispatch(self.conn, self.send, now + timedelta(minutes=4))
        self.assertEqual(len(self.sent), 1)              # aynı olay ikinci kez gitmez

    def test_not_configured_or_removed_ticker_not_sent(self):
        now = at(D1, 19)
        tracker._event(self.conn, now, "TST", "tp", "x", "a")
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}):
            tracker.dispatch(self.conn, self.send, now)
        self.assertEqual(self.sent, [])
        tracker.remove(self.conn, "TST")
        tracker._event(self.conn, now, "TST", "tp", "y", "b")
        tracker.dispatch(self.conn, self.send, now)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM takip_olay").fetchone()[0], 2)   # kayıt durur


class TickTests(Base):
    def test_schedule_close_once_then_intraday_next_day(self):
        self.scen()
        self.bar("TST", D1, 99, 100, 97, 99.5)
        calls, quotes = [], []
        price = lambda conn, tickers, period: calls.append((tuple(tickers), period))
        quote = lambda tickers: quotes.append(tickers) or {}
        out = tracker.tick(self.conn, at(D1, 18, 45), price, quote, self.send)       # kapanış + 20 dk geçti
        self.assertEqual(out["kapanis"]["gun"], D1)
        self.assertEqual(len(calls), 1)
        self.assertIn(f"s{tracker.scenarios(self.conn, 'TST')[-1]['id']}:giris", self.keys())
        self.assertEqual(len(self.sent), 1)                                          # olaylar bildirildi
        tracker.tick(self.conn, at(D1, 19, 30), price, quote, self.send)
        self.assertEqual(len(calls), 1)                                              # aynı akşam tekrar yok
        tracker.tick(self.conn, at(D1, 18, 5), price, quote, self.send)
        out = tracker.tick(self.conn, at(D2, 11, 0), price, quote, self.send)       # seans içi
        self.assertIn("gunici", out)
        tracker.tick(self.conn, at(D2, 11, 2), price, quote, self.send)             # 5 dk dolmadı
        self.assertEqual(len(quotes), 1)
        self.assertEqual(tracker.last_closed_day(at("2026-11-08", 12)).isoformat(), D0)   # pazar → cuma
        self.assertFalse(tracker.in_session(at("2026-11-08", 12)))

    def test_nothing_watched_no_network(self):
        tracker.remove(self.conn, "TST")
        boom = lambda *a, **k: self.fail("ağa çıkılmamalı")
        tracker.tick(self.conn, at(D1, 19), boom, boom, self.send)


class PerformanceTests(Base):
    def test_strategy_rates(self):
        a, b, c = self.scen(), self.scen(kind="geri_cekilme"), self.scen(kind="kirilim", alarm=105)
        for sid, durum, res in ((a, "kapandı", {"sonuc": "TP2", "tp1_goruldu": True, "net_getiri_pct": 8}),
                                (b, "kapandı", {"sonuc": "SL", "net_getiri_pct": -3}),
                                (c, "iptal", {"sonuc": "gerçekleşmedi"})):
            self.conn.execute("UPDATE takip_senaryo SET durum=?, sonuc_json=? WHERE id=?", (durum, json.dumps(res), sid))
        perf = {r["Strateji"]: r for r in tracker.performance(self.conn)}
        self.assertEqual(perf["Destekten tepki"]["TP2 %"], 100.0)
        self.assertEqual(perf["Geri çekilme"]["SL %"], 100.0)
        self.assertEqual(perf["Kırılım"]["Girişsiz biten"], 1)


class NewsTests(Base):
    """Aşama 4: takip edilen hissenin yeni KAP haberi → metin → bütçe içinde analiz → önemliyse olay (bir kez)."""

    def setUp(self):
        super().setUp()
        pipeline.save_settings(takip_haber_analizi=True)    # bu testler kullanıcı düğmeyi AÇMIŞ gibi çalışır
        self.now = at(D1, 11)
        self.conn.execute("UPDATE watchlist SET eklendi=? WHERE ticker='TST'", (tracker._iso(self.now - timedelta(days=1)),))
        self.news("kap:1", "TST", self.now - timedelta(hours=1))             # takip sonrası, metni yok
        self.news("kap:2", "POS", self.now - timedelta(hours=1))             # takip edilmeyen hisse
        self.conn.commit()
        self.bodies, self.analyzed = [], []
        p = patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
        p.start()
        self.addCleanup(p.stop)

    def news(self, nid, tk, when, body=None, status="new"):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,status,"
                          "fetched_at) VALUES(?,'kap',?,?,'TST A.Ş.: Yeni iş ilişkisi','Özel Durum',?,?,?,'f')",
                          (nid, tracker._iso(when), when.date().isoformat(), body, tk, status))

    def body_fn(self, index, subject):
        self.bodies.append(index)
        return "Şirket 1 milyar TL'lik sözleşme imzaladı."

    def analyze_fn(self, conn, uni, rows=None, quality=None, budget_usd=None):
        self.analyzed.append(([r["id"] for r in rows], budget_usd))
        for r in rows:
            conn.execute("UPDATE news SET status='analyzed' WHERE id=?", (r["id"],))
            conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,reason,"
                         "published_at,effective_date) VALUES(?,?,1,4,0.8,'orta','is_iliskisi','büyük sözleşme',?,?)",
                         (r["id"], "TST", r["published_at"], r["effective_date"]))
        conn.commit()
        return {"analyzed": len(rows), "filtered_out": 0, "errors": 0}

    def run_check(self, **k):
        return tracker.news_check(self.conn, self.now, collect_fn=k.get("collect", lambda c: {"new": 0}),
                                  body_fn=self.body_fn, analyze_fn=self.analyze_fn, sleep=lambda s: None)

    def test_only_watched_news_read_analyzed_and_alerted_once(self):
        pipeline.save_settings(haber_butce_usd=7.5)
        res = self.run_check()
        self.assertEqual(self.bodies, [1])                                   # yalnız takip edilen hissenin metni
        self.assertEqual(self.analyzed, [(["kap:1"], 7.5)])                 # bütçe tavanı iletildi
        self.assertEqual(res["olay"], 1)
        self.assertIn("h:kap:1:TST", self.keys())
        msg = self.conn.execute("SELECT mesaj, tur FROM takip_olay").fetchone()
        self.assertEqual(msg["tur"], "haber")
        self.assertIn("Olumlu önemli haber (etki 4/5", msg["mesaj"])
        self.assertEqual(self.run_check()["olay"], 0)                       # ikinci tur: tekrar yok, yeniden analiz yok
        self.assertEqual(len(self.analyzed), 1)

    def test_watcher_does_not_call_ai_by_default(self):
        # 2026-11-14 (kullanıcı isteği): bekçi kullanıcı açmadıkça yapay zekâ çağırmaz; metin yine okunur (ücretsiz)
        import json as _j
        pipeline.SETTINGS_FILE.write_text(_j.dumps({}), encoding="utf-8")
        res = self.run_check()
        self.assertEqual(self.analyzed, [])
        self.assertEqual(self.bodies, [1])
        self.assertIsNone(res["analiz"])

    def test_old_or_weak_news_not_alerted_and_switch_off(self):
        for nid, when, mag in (("kap:9", self.now - timedelta(days=2), 5), ("kap:8", self.now - timedelta(hours=2), 2)):
            self.news(nid, "TST", when, body="x", status="analyzed")         # takipten önce / etkisi zayıf
            self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,"
                              "reason,published_at,effective_date) VALUES(?,'TST',1,?,0.9,'orta','diger','r',?,?)",
                              (nid, mag, tracker._iso(when), when.date().isoformat()))
        self.conn.commit()
        pipeline.save_settings(takip_haber_analizi=False)
        res = self.run_check()
        self.assertEqual(self.analyzed, [])                                  # kapalı: yapay zekâ çağrılmaz
        self.assertEqual(res["olay"], 0)

    def test_kap_error_does_not_stop_and_no_key_no_ai(self):
        boom = lambda c: (_ for _ in ()).throw(OSError("429 Request Limit"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            res = self.run_check(collect=boom)
        self.assertIn("429", res["hata"])
        self.assertEqual(res["analiz"], "API anahtarı yok")
        self.assertEqual(self.analyzed, [])

    def test_tick_runs_news_every_30_min_on_trading_days(self):
        calls = []
        fn = lambda conn, now: calls.append(now) or {"olay": 0}
        noop = lambda *a, **k: {}
        tracker.tick(self.conn, at(D1, 11, 0), noop, noop, self.send, fn)
        tracker.tick(self.conn, at(D1, 11, 10), noop, noop, self.send, fn)    # 30 dk dolmadı
        tracker.tick(self.conn, at(D1, 11, 31), noop, noop, self.send, fn)
        tracker.tick(self.conn, at("2026-11-08", 12, 0), noop, noop, self.send, fn)   # pazar: yok
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
