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
