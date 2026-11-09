"""2026-11-09 uçtan uca kontrolde bulunan panel hataları için kalıcı testler (kullanıcı akışları)."""
import math
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from bist_haber import config, db, pipeline, watchdog
from tests.test_signals import news, weekdays_back

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class PanelFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        for p in (patch.object(config, "DATA", t), patch.object(config, "DB_PATH", t / "live.db"),
                  patch.object(pipeline, "SETTINGS_FILE", t / "ayarlar.json"),
                  patch.dict(os.environ, {"OPENAI_API_KEY": "", "HALLEY_OFFLINE": "1"})):
            p.start()
            self.addCleanup(p.stop)
        conn = db.connect()
        conn.execute("INSERT INTO companies VALUES('POS','POS A.Ş.',NULL)")
        today = date.today()
        for i, d in enumerate(weekdays_back(today - timedelta(days=1), 260)):
            px = 100 * (1 + 0.01 * math.sin(i / 6.0))
            conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                         ("POS", d.isoformat(), px * 0.998, px * 1.01, px * 0.99, px, 1_000_000))
        news(conn, "n1", "POS", 1, 3, 0.9, day=(today - timedelta(days=1)).isoformat())
        sd = weekdays_back(today - timedelta(days=1), 2)[0].isoformat()
        conn.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik)"
                     " VALUES('x',?,'POS','otomatik','destek',100,95,104,110,5)", (sd,))
        conn.commit()
        conn.close()
        watchdog.archive(today.isoformat(), "sabah", "# sabah\n", {})
        watchdog.archive(today.isoformat(), "aksam", "# akşam\n", {})
        watchdog.archive(today.isoformat(), "sabah", "# sabah 2\n", {})

    def app(self):
        at = AppTest.from_file(APP, default_timeout=90)
        at.run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        return at

    def test_dark_mode_toggle_is_saved_and_applies_theme(self):
        from streamlit import config as st_config
        at = self.app()
        self.assertFalse(at.toggle(key="dark_mode").value)
        at.toggle(key="dark_mode").set_value(True).run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(pipeline.load_settings()["karanlik_mod"])          # seçim saklandı
        self.assertEqual(st_config.get_option("theme.base"), "dark")
        self.assertTrue(any("--h-bg:#0D1322" in m.value for m in at.markdown))   # koyu renk takımı çizildi
        at.toggle(key="dark_mode").set_value(False).run()
        self.assertFalse(pipeline.load_settings()["karanlik_mod"])
        self.assertEqual(st_config.get_option("theme.base"), "light")
        self.assertTrue(any("--h-bg:#F3F5FA" in m.value for m in at.markdown))

    def test_transfer_section_export_prepares_file(self):
        at = self.app()
        self.assertTrue(any("💾 Veri aktarma" in m.value for m in at.markdown))
        self.assertFalse(any("Halley yeni kurulmuş" in str(i.value) for i in at.info))     # verisi olan kurulum
        at.button(key="export_prepare").click().run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(any("Hazır:" in c.value and "1 haber" in c.value for c in at.caption))

    def test_telegram_setup_and_test_message(self):
        from bist_haber import notify
        sent = []
        root = Path(self.tmp.name)
        with patch.object(config, "ROOT", root), \
                patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}), \
                patch.object(notify, "find_chats", lambda: [{"id": "11", "ad": "Ali", "tur": "private"}]), \
                patch.object(notify, "send", lambda t: sent.append(t) or {"ok": True, "gonderilen": 1, "hatalar": []}):
            at = self.app()
            self.assertTrue(at.toggle(key="tg_on").disabled)                   # ayarlanmadan açılamaz
            at.text_input(key="tg_token").input("123:ABC").run()
            at.button(key="tg_save_token").click().run()
            self.assertIn("TELEGRAM_BOT_TOKEN=123:ABC", (root / ".env").read_text(encoding="utf-8"))
            at.button(key="tg_find").click().run()
            self.assertEqual(at.multiselect(key="tg_pick").value, ["11"])
            at.button(key="tg_save_chats").click().run()
            self.assertEqual(len(at.exception), 0, str(at.exception))
            self.assertTrue(notify.configured())
            self.assertTrue(pipeline.load_settings()["telegram_acik"])         # alıcı kaydedilince açılır
            self.assertTrue(at.toggle(key="tg_on").value)
            at.button(key="tg_test").click().run()
            self.assertEqual(len(sent), 1)
            self.assertTrue(any("1 alıcıya gönderildi" in str(s.value) for s in at.success))

    def test_follow_from_card_and_watchlist_tab(self):
        from bist_haber import tracker

        def q(fn, *a, **k):
            c = db.connect()
            try:
                return fn(c, *a, **k)
            finally:
                c.close()
        at = self.app()
        at.button(key="fol_card_POS").click().run()                     # hisse kartındaki "+ Takibe Al"
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(q(tracker.is_watched, "POS"))
        self.assertTrue(any("POS takibe alındı" in str(m.value) for m in list(at.success) + list(at.warning)))
        self.assertTrue(any(b.key == "unf_card_POS" for b in at.button))   # artık "takipte" düğmesi
        at.multiselect(key="tk_types_POS").set_value(["sl", "tp"]).run()   # yalnız SL ve TP bildirimi
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertEqual(q(tracker.watched)[0]["bildirimler"], ["sl", "tp"])
        sc = q(tracker.scenarios, "POS", active_only=True)
        if sc:                                                            # senaryo bildirimini kapat
            at.toggle(key=f"tk_sw_{sc[0]['id']}").set_value(False).run()
            self.assertEqual(next(s for s in q(tracker.scenarios, "POS") if s["id"] == sc[0]["id"])["bildirim"], 0)
        at.button(key="tk_rm_POS").click().run()
        self.assertFalse(q(tracker.is_watched, "POS"))
        self.assertEqual(len(q(tracker.scenarios, "POS")), len(sc))      # geçmiş duruyor
        self.assertTrue(any("Takipten çıkarılanlar" in c.value for c in at.caption))

    def test_settings_file_with_bom_is_not_lost(self):
        # Not Defteri dosyayı BOM ile kaydederse ayarlar okunamayıp sıfırlanıyordu (2026-11-09 önizlemede görüldü)
        pipeline.SETTINGS_FILE.write_bytes(b'\xef\xbb\xbf{"karanlik_mod": true, "komisyon_pct": 0.3}')
        self.assertEqual(pipeline.load_settings(), {"karanlik_mod": True, "komisyon_pct": 0.3})
        pipeline.save_settings(kayma_pct=0.1)
        self.assertEqual(pipeline.load_settings(), {"karanlik_mod": True, "komisyon_pct": 0.3, "kayma_pct": 0.1})

    def test_button_error_survives_rerun_in_plain_turkish(self):
        def boom(*a, **k):
            raise OSError("HTTPSConnectionPool(host='www.kap.org.tr', port=443): Max retries exceeded")
        with patch.object(pipeline, "free_check", boom):
            at = self.app()
            at.button(key="free_check").click().run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        errs = [str(e.value) for e in at.error]
        self.assertTrue(any("www.kap.org.tr adresine bağlanılamadı" in e for e in errs), errs)
        self.assertFalse(any("Max retries" in e for e in errs))          # teknik İngilizce gösterilmez

    def test_report_filter_change_does_not_crash(self):
        at = self.app()
        self.assertEqual(len(at.selectbox(key="rep_pick").options), 3)
        for kind in ("Akşam", "Sabah", "Hepsi"):
            at.radio(key="rep_kind").set_value(kind).run()
            self.assertEqual(len(at.exception), 0, str(at.exception))
        labels = at.selectbox(key="rep_pick").options
        self.assertTrue(any("(2. çalıştırma)" in x for x in labels), labels)

    def test_tables_show_dash_not_none(self):
        at = self.app()
        for d in at.dataframe:
            s = d.value.astype(str)
            for col in s.columns:
                self.assertFalse(s[col].isin(["None", "nan"]).any(), f"{col} sütununda None/nan")

    def test_guide_is_shown_and_names_real_buttons(self):
        at = self.app()
        guide = next((m.value for m in at.markdown if "Kullanım kılavuzu" in m.value), "")
        self.assertTrue(guide, "kılavuz panelde yok")
        src = Path(APP).read_text(encoding="utf-8")
        for name in ("🌅 Sabah analizi", "🌙 Akşam analizi", "🔄 Haberleri güncelle", "🧪 Ücretsiz dene",
                     "✍️ Bu işleme girdim", "⚙️ Ayarlar", "📈 Bugünün listesi", "📒 İşlem günlüğü", "📋 Raporlar",
                     "🧭 Gelişim", "📰 Haberler", "🔧 Gelişmiş", "🤖 Raporu yapay zekâ ile yorumla",
                     "🤖 Kaçırılan fırsatları yapay zekâ ile açıkla"):
            self.assertIn(name, guide)
            self.assertIn(name, src)        # kılavuzdaki ad panelde gerçekten var

    def test_news_analysis_section_runs_with_estimate_and_budget(self):
        from bist_haber import analyzer
        conn = db.connect()
        from datetime import datetime
        now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
        for i in range(3):
            conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,fetched_at)"
                         " VALUES(?,'kap',?,?,'Başlık','metin metin','POS','new','f')", (f"k{i}", now, now[:10]))
        conn.commit()
        conn.close()
        calls = []

        def fake_analyze(conn, uni, rows=None, **k):
            calls.append((len(rows), k.get("budget_usd")))
            return {"analyzed": len(rows), "filtered_out": 0, "errors": 0}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), patch.object(analyzer, "analyze", fake_analyze):
            at = self.app()
            self.assertTrue(any("🔬 Haber analizi" in m.value for m in at.markdown))
            self.assertTrue(any("tahmini maliyet" in str(i.value) for i in at.info))
            at.number_input(key="na_n").set_value(2).run()
            at.button(key="na_run").click().run()
            self.assertEqual(len(at.exception), 0, str(at.exception))
            self.assertEqual(calls, [(2, config.NEWS_BUDGET_USD)])           # seçilen adet + bütçe iletildi
            self.assertTrue(any("2 haber analiz edildi" in str(s.value) for s in at.success))
            at.radio(key="na_mode").set_value("🔁 Analiz edilmiş haberi derin yeniden incele").run()
            self.assertEqual(len(at.exception), 0, str(at.exception))

    def test_analysis_progress_box_visible(self):
        import json as _j
        from datetime import datetime
        from bist_haber import analyzer
        now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
        analyzer.status_file().write_text(_j.dumps({"tur": "haber analizi", "durum": "çalışıyor", "toplam": 142,
                                                    "biten": 45, "harcanan_usd": 0.6, "nabiz": now}), encoding="utf-8")
        at = self.app()
        self.assertTrue(any("Haber analizi sürüyor: 45/142" in str(i.value) for i in at.info), [i.value for i in at.info])
        analyzer.status_file().write_text(_j.dumps({"tur": "haber analizi", "durum": "tamamlandı", "toplam": 142,
                                                    "biten": 142, "harcanan_usd": 2.1, "nabiz": now, "bitti": now,
                                                    "sonuc": {"analyzed": 130, "filtered_out": 12}}), encoding="utf-8")
        at = self.app()
        self.assertTrue(any("130 haber analiz edildi" in str(x.value) and "2.100 $" in str(x.value) for x in at.success))

    def test_double_save_real_trade_warns(self):
        at = self.app()
        at.number_input(key="real_px").set_value(100.5).run()
        at.button(key="real_save").click().run()
        self.assertTrue(any("kaydedildi" in str(s.value) for s in at.success))
        at.button(key="real_save").click().run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(any("zaten kaydedilmiş" in str(e.value) for e in at.error))


if __name__ == "__main__":
    unittest.main()
