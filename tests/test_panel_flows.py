"""2026-11-09 uçtan uca kontrolde bulunan panel hataları için kalıcı testler (kullanıcı akışları)."""
import math
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
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

    def app(self, page=None):
        at = AppTest.from_file(APP, default_timeout=90)
        at.run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        if page:
            self.go(at, page)
        return at

    def go(self, at, page):
        """Aşama 3: üst menüden ekrana geç."""
        at.radio(key="nav").set_value(page).run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        return at

    def test_every_page_renders_and_analysis_link_opens_stock(self):
        at = self.app()
        self.assertEqual(at.radio(key="nav").value, "📊 Dashboard")
        for p in at.radio(key="nav").options:
            self.go(at, p)
        self.go(at, "🎯 Fırsatlar")
        at.button(key="an_POS").click().run()                       # 🔍 Analiz → Hisse Analizi, POS seçili
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertEqual(at.radio(key="nav").value, "🔍 Hisse Analizi")
        self.assertEqual(at.selectbox(key="hisse_pick").value, "POS")
        self.assertTrue(any("Trend gücü (ADX 14)" in d.value.to_string() for d in at.dataframe))

    def test_visual_text_has_no_broken_dollar_or_plus(self):
        """2026-11-09 görünüm kontrolü: iki "$" arası formül gibi bozuluyordu; "+ Takibe Al" düğmesinde + kayboluyordu."""
        import re
        from bist_haber import ai_comment
        watchdog.archive(date.today().isoformat(), "aksam", "# akşam\nYorum maliyeti 0.002 $ · bütçe 10 $\n", {})
        at = self.app()
        for p in at.radio(key="nav").options:
            self.go(at, p)
            texts = [str(e.value) for kind in ("markdown", "caption", "info", "success", "warning", "error")
                     for e in getattr(at, kind)]
            for t in texts:
                self.assertEqual(re.findall(r"(?<!\\)\$", t), [], f"{p}: kaçırılmamış $ → {t[:120]}")
            for b in at.button:
                self.assertFalse(re.match(r"^[+\-*] ", str(b.label)), f"{p}: düğme yazısı liste işaretiyle başlıyor: {b.label}")

    def test_kpi_colors_follow_card_not_position(self):
        src = Path(APP).read_text(encoding="utf-8")
        self.assertNotIn('.st-key-kpi div[data-testid="stColumn"]:nth-of-type', src)    # sıraya bağlı renk yok
        for key, var in (("kpi_pos", "--h-pos"), ("kpi_neg", "--h-neg"), ("kpi_bist_up", "--h-pos"),
                         ("kpi_bist_down", "--h-neg")):
            self.assertRegex(src, rf"\.st-key-{key} div\[data-testid=\"stMetric\"\][^{{]*\{{border-top: 5px solid var\({var}\)")
        for key, label in (("kpi_pos", "Olumlu haber"), ("kpi_neg", "Olumsuz haber")):
            self.assertRegex(src, rf'\(m[12], "{key}", "{label}"')                     # kart doğru anahtarda
        at = self.app()
        self.assertEqual([m.label for m in at.metric][:5],
                         ["BIST 100", "Olumlu haber", "Olumsuz haber", "Hazır fırsat", "Son güncelleme"])

    def test_opportunity_recheck_and_change_log(self):
        from bist_haber import firsat_log
        at = self.app("🎯 Fırsatlar")
        at.button(key="opp_recheck").click().run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(any("yeniden kontrol edildi" in str(s.value) for s in at.success))
        self.assertTrue(firsat_log.path().exists())                         # o anki liste kaydedildi
        cand = next(d.value for d in at.dataframe if "Durum" in d.value.columns)
        self.assertIn("POS", list(cand["Hisse"]))
        # Liste değişince hangi hisse neden çıktı kaydedilir
        firsat_log.record(["POS", "XYZ"], lambda t: "-")
        firsat_log.record(["POS"], lambda t: "haber skoru 1,20'ye indi")
        ch = firsat_log.changes(1)[0]
        self.assertEqual((ch["onceki_sayi"], ch["sayi"], ch["cikan"]), (2, 1, [{"hisse": "XYZ", "neden": "haber skoru 1,20'ye indi"}]))
        self.assertFalse(firsat_log.record(["POS"], lambda t: "-")["degisti"])        # değişiklik yoksa yazmaz
        at.run()
        self.assertTrue(any("2 → 1" in str(m.value) and "çıkan: XYZ" in str(m.value) for m in at.markdown))

    def test_turkish_search_finds_dotted_names(self):
        conn = db.connect()
        conn.execute("INSERT INTO companies VALUES('SISE','TÜRKİYE ŞİŞE VE CAM FABRİKALARI A.Ş.',NULL)")
        conn.commit()
        conn.close()
        at = self.app("🔍 Hisse Analizi")
        at.text_input(key="hisse_q").input("şişe cam").run()
        self.assertEqual(at.selectbox(key="hisse_pick").value, "SISE")
        at.text_input(key="hisse_q").input("turkiye sise").run()             # Türkçe karakter yazmadan da bulur
        self.assertEqual(at.selectbox(key="hisse_pick").value, "SISE")
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.go(at, "⭐ Takip Listem")
        at.text_input(key="tk_add_q").input("şişe").run()
        self.assertEqual(at.selectbox(key="tk_add_pick").options[1:], ["SISE — TÜRKİYE ŞİŞE VE CAM FABRİKALARI A.Ş."])

    def test_theme_change_keeps_page_and_stock_selection_survives_page_switch(self):
        conn = db.connect()
        conn.execute("INSERT INTO companies VALUES('ZZZ','Zeta A.Ş.',NULL)")
        conn.commit()
        conn.close()
        at = self.app("🎯 Fırsatlar")
        at.toggle(key="dark_mode").set_value(False).run()          # tema yenilemesi menü seçimini unutmamalı
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertEqual(at.radio(key="nav").value, "🎯 Fırsatlar")
        self.assertTrue(any(b.key == "opp_recheck" for b in at.button))   # gerçekten Fırsatlar ekranı çizildi
        self.go(at, "🔍 Hisse Analizi")
        at.selectbox(key="hisse_pick").set_value("ZZZ").run()
        self.go(at, "📊 Dashboard")
        self.go(at, "🔍 Hisse Analizi")
        self.assertEqual(at.selectbox(key="hisse_pick").value, "ZZZ")     # seçilen hisse kaybolmadı

    def test_explanations_shown_where_users_got_confused(self):
        """2026-11-09: fırsatlardaki risk (senaryo) ile analizdeki risk (şimdi alım) karışıyordu; İşlem Günlüğü anlaşılmıyordu."""
        at = self.app()
        caps = " ".join(c.value for c in at.caption)
        for t in ("haber skoru +1,50 ve üstü", "koşulu sağlanmış (haberli 0 · 📐 yalnız teknik 0) · bekleyen senaryo", "son haber analizinin saati"):
            self.assertIn(t, caps)
        self.go(at, "🔍 Hisse Analizi")
        labels = [m.label for m in at.metric]
        if any(l.startswith("Referans") for l in labels):          # referans kutuları çizildiyse etiket açık olmalı
            self.assertIn("Risk (şimdi alınırsa)", labels)
            self.assertNotIn("Risk seviyesi", labels)
        caps = " ".join(c.value for c in at.caption)
        self.assertIn("Haber skoru: haberlerin yönü", caps)
        self.go(at, "📒 İşlem Günlüğü")
        self.assertTrue(any(e.label == "❓ İşlem Günlüğü nasıl okunur?" for e in at.expander))
        guide = " ".join(m.value for m in at.markdown)
        for t in ("Sanal işlem:", "Gerçek işlem:", "açık (TP1 görüldü)", "+1R = planlanan zarar kadar kazanç"):
            self.assertIn(t, guide)
        if at.metric:                                  # ölçüler yalnız kapanan işlem varsa çizilir; o zaman açıklaması da olmalı
            self.assertTrue(any("Kâr faktörü: toplam kazanç / toplam zarar" in c.value for c in at.caption))
        self.assertTrue(any("Henüz kapanan işlem yok" in c.value for c in at.caption))

    def test_ready_opportunities_shown_first_and_ai_switch_off_by_default(self):
        """2026-11-10: Hazır Fırsatlar önce, Bekleyen ayrı; sabah haber kontrolünde yapay zekâ kullanıcı açana dek kapalı."""
        c = db.connect()
        today = date.today().isoformat()
        c.execute("INSERT INTO hazir_firsat(olusturuldu,analiz,signal_day,giris_gunu,ticker,tur,kapanis,giris,giris_alt,"
                  "azami_giris,sl,tp1,tp2,rr1,vade_lo,vade_hi,haber_skoru,teknik_skor,risk,neden,durum) VALUES("
                  "'2026-11-09T19:00:00+03:00','aksam','2026-11-09',?,'POS','mevcut_fiyat',100,100,99.4,100.6,96,110,114,2.5,"
                  "10,14,2.5,7,'orta','Haber: deneme gerekçe','aday')", (today,))
        c.commit()
        c.close()
        at = self.app()
        self.assertEqual(at.metric[3].label, "Hazır fırsat")
        self.assertEqual(at.metric[3].value, "1 hisse")
        self.go(at, "🎯 Fırsatlar")
        md_ = " ".join(m.value for m in at.markdown)
        self.assertLess(md_.index("Hazır Fırsatlar"), md_.index("Bekleyen Fırsatlar"))
        self.assertTrue(any(m.label == "Azami giriş" and m.value == "100.60" for m in at.metric))
        self.assertTrue(any("Neden: Haber: deneme gerekçe" in c_.value for c_ in at.caption))
        self.assertFalse(at.toggle(key="hz_ai").value)                    # varsayılan KAPALI
        self.assertFalse(pipeline.load_settings().get("hazir_sabah_yz", False))
        at.toggle(key="hz_ai").set_value(True).run()
        self.assertTrue(pipeline.load_settings()["hazir_sabah_yz"])       # kullanıcı açınca saklanır
        self.assertTrue(at.button(key="hz_ai_now").disabled)              # API anahtarı yok → elle analiz kapalı
        at.button(key="hz_live").click().run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(any("Anlık hesap" in m.value and "kaydedilmedi" in m.value for m in at.markdown))
        self.go(at, "🏁 Performans")
        self.assertTrue(any("Hazır fırsatlar — gerçek sonuçlar" in m.value for m in at.markdown))

    def test_stage4_score_tech_only_section_and_weekly_report(self):
        """2026-11-14 Aşama 4: genel puan kartta, yalnız teknik ayrı bölümde ve haberlilerden sonra, Performans'ta
        kaynak süzgeci, haftalık rapor düğmesi arşive yazar ve 'Haftalık' süzgecinde görünür."""
        c = db.connect()
        today = date.today().isoformat()
        for tk, kaynak, hs in (("POS", "haber", 2.5), ("TEK", "teknik", None)):
            c.execute("INSERT INTO hazir_firsat(olusturuldu,analiz,signal_day,giris_gunu,ticker,tur,kapanis,giris,giris_alt,"
                      "azami_giris,sl,tp1,tp2,rr1,vade_lo,vade_hi,haber_skoru,teknik_skor,risk,neden,durum,kaynak) VALUES("
                      "'2026-11-09T19:00:00+03:00','aksam','2026-11-09',?,?,'kirilim_teyitli',100,100,99.4,100.6,96,110,"
                      "114,2.5,10,14,?,8,'orta','gerekçe','aday',?)", (today, tk, hs, kaynak))
        c.commit()
        c.close()
        at = self.app("🎯 Fırsatlar")
        self.assertEqual(len(at.exception), 0, str(at.exception))
        md_ = " ".join(m.value for m in at.markdown)
        self.assertLess(md_.index("Hazır Fırsatlar"), md_.index("Yalnız teknik fırsatlar"))
        self.assertLess(md_.index("Yalnız teknik fırsatlar"), md_.index("Bekleyen Fırsatlar"))
        caps = [c_.value for c_ in at.caption]
        self.assertTrue(any("Genel fırsat puanı 62/100" in x and "sınanmadı" in x for x in caps), caps)   # 15+24+12,5+10
        self.assertTrue(any("Genel fırsat puanı 46/100" in x and "en fazla 70" in x for x in caps))      # 0+24+12,5+10
        self.assertTrue(any("haber yok (yalnız teknik)" in x for x in caps))
        self.go(at, "🏁 Performans")
        at.radio(key="pf_kay").set_value("📐 Yalnız teknik").run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertEqual(next(m.value for m in at.metric if m.label == "Önerilen"), "1")
        self.go(at, "🛡️ Bekçi")
        at.button(key="rep_weekly").click().run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        at.radio(key="rep_kind").set_value("Haftalık").run()
        opts = at.selectbox(key="rep_pick").options
        self.assertTrue(opts and all("haftalık rapor" in o for o in opts), opts)
        self.assertTrue(any("Haftalık rapor" in m.value for m in at.markdown))

    def test_stage6_model_line_hidden_until_setting_on(self):
        """2026-11-15 Aşama 6: gizli kayıttaki model olasılığı kartta yalnız ayar açıkken görünür (varsayılan kapalı)."""
        c = db.connect()
        mj = json.dumps({"olasilik": 0.3728, "bant": "yüksek", "benzer_n": 1465, "benzer_oran": 0.314, "surum": "tp1_v1"})
        c.execute("INSERT INTO hazir_firsat(olusturuldu,analiz,signal_day,giris_gunu,ticker,tur,kapanis,giris,giris_alt,"
                  "azami_giris,sl,tp1,tp2,rr1,vade_lo,vade_hi,haber_skoru,teknik_skor,risk,neden,durum,kaynak,model_json) "
                  "VALUES('2026-11-09T19:00:00+03:00','aksam','2026-11-09',?,'TEK','kirilim_teyitli',100,100,99.4,100.6,96,"
                  "110,114,2.5,10,14,NULL,8,'orta','gerekçe','aday','teknik',?)", (date.today().isoformat(), mj))
        c.commit()
        c.close()
        at = self.app("🎯 Fırsatlar")
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertFalse(any("ulaşma olasılığı (model)" in c_.value for c_ in at.caption))
        self.go(at, "⚙️ Ayarlar")
        at.toggle(key="model_olasilik_set").set_value(True).run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(pipeline.load_settings().get("model_olasilik_goster"))
        self.go(at, "🎯 Fırsatlar")
        caps = [c_.value for c_ in at.caption]
        self.assertTrue(any("%37 — yüksek" in x and "benzer 1465 durumda %31" in x and "haber hesaba katılmaz" in x
                            for x in caps), caps)

    def test_stage5_chart_and_cone_on_stock_page(self):
        """2026-11-15 Aşama 5: Hisse Analizi'nde grafik çizilir, koni açıklaması ve dönem/koni seçimi çalışır."""
        at = self.app("🔍 Hisse Analizi")
        self.assertEqual(len(at.exception), 0, str(at.exception))
        caps = " ".join(c.value for c in at.caption)
        self.assertIn("yön tahmini değildir", caps)
        self.assertTrue(at.get("arrow_vega_lite_chart"), "grafik çizilmedi")
        k = next(r.key for r in at.radio if (r.key or "").startswith("ch_h_"))
        at.radio(key=k).set_value(20).run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(any("20 işlem günü sonra" in c.value for c in at.caption))

    def test_ai_usage_tab_shows_recorded_calls(self):
        from bist_haber import ai_service
        ai_service.record("haber_analizi", "tam_analiz", "kap:9", "gpt-5-mini", 2000, 800, db_path=config.DB_PATH)
        c = db.connect()          # Aşama 3 ön elemesinin atladığı bir haber: tasarruf satırı görünmeli
        now_ = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
        c.execute("INSERT INTO news(id,source,published_at,effective_date,title,body,candidates,status,note,fetched_at) "
                  "VALUES('kap:77','kap',?,?,'İzahname','metin','POS','skipped','Python ön eleme: rutin KAP konusu',?)",
                  (now_, now_[:10], now_))
        c.commit()
        c.close()
        at = self.app("⚙️ Ayarlar")
        self.assertTrue(any("1 rutin haber (Python ön eleme)" in c_.value for c_ in at.caption))
        self.assertTrue(any(t.label == "🤖 Yapay zekâ kullanımı" for t in at.tabs))
        self.assertTrue(any(m.label == "Bu ay" and m.value == "1 çağrı" for m in at.metric))
        self.assertTrue(any("Haber analizi" in d.value.to_string() and "tam analiz" in d.value.to_string()
                            for d in at.dataframe))

    def test_settings_saved_across_pages(self):
        at = self.app("⚙️ Ayarlar")
        at.slider(key="set_window").set_value(12).run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertEqual(pipeline.load_settings()["liste_pencere"], 12)
        self.go(at, "📊 Dashboard")
        self.go(at, "⚙️ Ayarlar")
        self.assertEqual(at.slider(key="set_window").value, 12)          # ekran değişse de ayar kaybolmaz

    def test_dark_mode_toggle_is_saved_and_applies_theme(self):
        from streamlit import config as st_config
        at = self.app()
        self.assertTrue(at.toggle(key="dark_mode").value)                  # Aşama 3: varsayılan koyu tema
        self.assertTrue(any("--h-bg:#0D1322" in m.value for m in at.markdown))
        at.toggle(key="dark_mode").set_value(False).run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertFalse(pipeline.load_settings()["karanlik_mod"])         # seçim saklandı
        self.assertEqual(st_config.get_option("theme.base"), "light")
        self.assertTrue(any("--h-bg:#F3F5FA" in m.value for m in at.markdown))
        at.toggle(key="dark_mode").set_value(True).run()
        self.assertTrue(pipeline.load_settings()["karanlik_mod"])
        self.assertEqual(st_config.get_option("theme.base"), "dark")
        self.assertTrue(any("--h-bg:#0D1322" in m.value for m in at.markdown))   # koyu renk takımı çizildi

    def test_transfer_section_export_prepares_file(self):
        at = self.app("⚙️ Ayarlar")
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
            at = self.app("⚙️ Ayarlar")
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
        at = self.app("🔍 Hisse Analizi")
        at.button(key="fol_card_POS").click().run()                     # analiz ekranındaki "+ Takibe Al"
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(q(tracker.is_watched, "POS"))
        self.assertTrue(any("POS takibe alındı" in str(m.value) for m in list(at.success) + list(at.warning)))
        self.assertTrue(any(b.key == "unf_card_POS" for b in at.button))   # artık "takipte" düğmesi
        self.go(at, "⭐ Takip Listem")
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
        at = self.app("🛡️ Bekçi")
        self.assertEqual(len(at.selectbox(key="rep_pick").options), 3)
        for kind in ("Akşam", "Sabah", "Hepsi"):
            at.radio(key="rep_kind").set_value(kind).run()
            self.assertEqual(len(at.exception), 0, str(at.exception))
        labels = at.selectbox(key="rep_pick").options
        self.assertTrue(any("(2. çalıştırma)" in x for x in labels), labels)

    def test_tables_show_dash_not_none(self):
        at = self.app()
        for p in at.radio(key="nav").options:
            self.go(at, p)
            for d in at.dataframe:
                s = d.value.astype(str)
                for col in s.columns:
                    self.assertFalse(s[col].isin(["None", "nan"]).any(), f"{p}: {col} sütununda None/nan")

    def test_guide_is_shown_and_names_real_buttons(self):
        at = self.app("⚙️ Ayarlar")
        guide = next((m.value for m in at.markdown if "Kullanım kılavuzu" in m.value), "")
        self.assertTrue(guide, "kılavuz panelde yok")
        src = Path(APP).read_text(encoding="utf-8") + (Path(APP).parent / "bist_haber" / "takip_ui.py").read_text(encoding="utf-8")
        for name in ("🌅 Sabah analizi", "🌙 Akşam analizi", "🔄 Haberleri güncelle", "🧪 Ücretsiz dene",
                     "✍️ Bu işleme girdim", "📊 Dashboard", "🎯 Fırsatlar", "🔍 Hisse Analizi", "⭐ Takip Listem",
                     "🛡️ Bekçi", "📰 Haberler", "📒 İşlem Günlüğü", "🏁 Performans", "⚙️ Ayarlar",
                     "💾 Veri ve gelişmiş", "➕ Takibe Al", "🔍 Analiz", "🤖 Raporu yapay zekâ ile yorumla",
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
            at = self.app("📰 Haberler")
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
        self.assertTrue(any("130 haber analiz edildi" in str(x.value) and r"2.100 \$" in str(x.value) for x in at.success))

    def test_double_save_real_trade_warns(self):
        at = self.app("📒 İşlem Günlüğü")
        at.number_input(key="real_px").set_value(100.5).run()
        at.button(key="real_save").click().run()
        self.assertTrue(any("kaydedildi" in str(s.value) for s in at.success))
        at.button(key="real_save").click().run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(any("zaten kaydedilmiş" in str(e.value) for e in at.error))


if __name__ == "__main__":
    unittest.main()
