"""Takvimi resmi sayfalardan kontrol etme testleri. Ağ KULLANILMAZ: 2026-11-07'de kaydedilmiş gerçek TCMB ve Fed
sayfaları (tests/fixtures) sahte bir indirici ile verilir."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bist_haber import calendar_sync as S, config, macro_calendar as M

FIX = Path(__file__).parent / "fixtures"
TCMB_HTML = (FIX / "tcmb_takvim_2026-11-07.html").read_text(encoding="utf-8")
FED_HTML = (FIX / "fed_fomc_2026-11-07.html").read_text(encoding="utf-8")
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=config.TR_TZ)


class FakeResp:
    def __init__(self, text, status=200):
        self.text, self.status = text, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


def fake_get(pages):
    def get(url, headers=None, timeout=None):
        v = pages.get(url)
        if isinstance(v, Exception):
            raise v
        return FakeResp(v) if v is not None else FakeResp("", 404)
    return get


class Isolated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(config, "DATA", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)


class ParseTests(unittest.TestCase):
    def test_real_tcmb_page_matches_builtin_calendar(self):
        d = S.parse_tcmb(TCMB_HTML)
        self.assertEqual(d["ppk"], [x for x, _ in M.PPK])
        self.assertEqual(d["ozet"], M.PPK_OZET)
        self.assertEqual(d["er"], M.ENFLASYON_RAPORU)
        self.assertEqual(d["fir"], M.FINANSAL_ISTIKRAR)
        self.assertEqual(M.diff_with_builtin("tcmb", d), [])

    def test_real_fed_page_matches_builtin_calendar(self):
        d = [x for x in S.parse_fed(FED_HTML) if x[0] >= "2026"]
        self.assertEqual(d, M.FOMC)
        self.assertEqual(M.diff_with_builtin("fed", d), [])

    def test_changed_structure_is_rejected(self):
        with self.assertRaises(S.ParseError):
            S.parse_tcmb(TCMB_HTML.replace("Enflasyon Raporu</h3>", "Başka Rapor</h3>"))
        with self.assertRaises(S.ParseError):
            S.parse_tcmb(TCMB_HTML.replace("12 Kasım 2026", "12 Kasimm 2026"))
        with self.assertRaises(S.ParseError):
            S.parse_tcmb(TCMB_HTML.replace("17 Aralık 2026", "19 Aralık 2026"))  # cumartesi
        with self.assertRaises(S.ParseError):
            S.parse_tcmb("<html>bakım çalışması</html>")
        with self.assertRaises(S.ParseError):
            S.parse_fed("<html></html>")

    def test_diff_reports_new_and_missing_dates(self):
        d = S.parse_tcmb(TCMB_HTML.replace("10 Aralık 2026", "9 Aralık 2026"))
        diff = M.diff_with_builtin("tcmb", d)
        self.assertTrue(any("yeni/değişen tarih: 2026-12-09" in x for x in diff))
        self.assertTrue(any("resmi takvimde olmayan: 2026-12-10" in x for x in diff))


class CheckTests(Isolated):
    def test_check_saves_official_data_and_tags_events(self):
        r = S.check(get=fake_get({S.TCMB_URL: TCMB_HTML, S.FED_URL: FED_HTML}), now=NOW)
        self.assertEqual(r["tcmb"], {"durum": "güncel", "farklar": []})
        self.assertEqual(r["fed"], {"durum": "güncel", "farklar": []})
        self.assertEqual(len(r["elle"]), 2)
        saved = json.loads(S.state_file().read_text(encoding="utf-8"))
        self.assertEqual(saved["sources"]["tcmb"]["url"], S.TCMB_URL)
        e = next(e for e in M.events() if e["tarih"] == "2026-12-10" and e["tur"] == "ppk")
        self.assertEqual(e["dogrulama"], "resmi sayfadan kontrol edildi")
        self.assertFalse(S.due(NOW))

    def test_new_official_dates_extend_calendar(self):
        extra = TCMB_HTML.replace("<tr> </tr> </tbody>", "").replace(
            "</tbody>", '<tr><td>22 Temmuz 2027</td><td>29 Temmuz 2027</td><td>12 Ağustos 2027</td><td>&nbsp;</td></tr></tbody>', 1)
        r = S.check(get=fake_get({S.TCMB_URL: extra, S.FED_URL: FED_HTML}), now=NOW)
        self.assertTrue(any("2027-07-22" in x for x in r["tcmb"]["farklar"]))
        self.assertIn("2027-07-22", M.lists()["ppk"])
        self.assertEqual(M.lists()["known"]["ppk"], "2027-07-31")

    def test_failure_keeps_previous_data(self):
        S.check(get=fake_get({S.TCMB_URL: TCMB_HTML, S.FED_URL: FED_HTML}), now=NOW)
        r = S.check(get=fake_get({S.TCMB_URL: ConnectionError("reset"), S.FED_URL: "<html>yapı değişti</html>"}), now=NOW)
        self.assertEqual(r["tcmb"]["durum"], "kontrol edilemedi")
        self.assertEqual(r["fed"]["durum"], "kontrol edilemedi")
        self.assertTrue(S.load()["sources"]["tcmb"]["data"]["ppk"])     # önceki geçerli veri duruyor
        self.assertIn("2026-12-10", M.lists()["ppk"])

    def test_no_saved_state_uses_builtin(self):
        self.assertEqual(M.lists()["official"], {"tcmb": False, "fed": False})
        self.assertTrue(S.due(NOW))

    def test_due_after_24_hours(self):
        S.check(get=fake_get({}), now=NOW)
        self.assertFalse(S.due(datetime(2026, 11, 8, 11, 59, tzinfo=config.TR_TZ)))
        self.assertTrue(S.due(datetime(2026, 11, 8, 12, 0, tzinfo=config.TR_TZ)))


class ViopAndRatingTests(unittest.TestCase):
    def test_viop_expiries_follow_rule(self):
        v = M.viop_expiries((2026,))
        self.assertEqual(v, ["2026-02-27", "2026-04-30", "2026-06-30", "2026-08-31", "2026-10-30", "2026-12-31"])
        # Ekim 2026: 30 Ekim cuma (29 tatil, 28 yarım gün değil son gün) → 30 Ekim

    def test_ratings_effect_next_trading_day(self):
        e = next(e for e in M.events() if e["tur"] == "kredi" and e["tarih"] == "2026-10-16")
        self.assertEqual(e["etki_gunu"], "2026-10-19")
        self.assertIn("S&P", e["ad"])



class PanelTests(Isolated):
    def test_auto_check_on_open_and_button(self):
        import os
        from streamlit.testing.v1 import AppTest
        from bist_haber import db
        real_check = S.check
        calls = []

        def fake_check(get=None, now=None):
            calls.append(1)
            return real_check(get=fake_get({S.TCMB_URL: TCMB_HTML, S.FED_URL: FED_HTML}), now=now)

        root = Path(self.tmp.name)
        env = {k: v for k, v in os.environ.items() if k != "HALLEY_OFFLINE"}
        env["OPENAI_API_KEY"] = ""
        with patch.object(config, "DB_PATH", root / "live.db"), patch.object(config, "UNIVERSE_FILE", root / "u.txt"),                 patch.dict(os.environ, env, clear=True), patch.object(S, "check", fake_check):
            db.connect().close()
            at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            at.run(timeout=30)
            self.assertEqual(len(at.exception), 0, str(at.exception))
            self.assertEqual(len(calls), 1)                    # açılışta otomatik kontrol (günde bir)
            at.run(timeout=30)
            self.assertEqual(len(calls), 1)                    # 24 saat dolmadan tekrar yok
            at.button(key="calendar_check").click().run(timeout=30)
            self.assertEqual(len(calls), 2)                    # düğme her zaman kontrol eder
            self.assertTrue(any("TCMB: güncel" in c.value for c in at.caption))
            self.assertTrue(any("elle kontrol gerekir" in d.value.to_string() for d in at.dataframe))


if __name__ == "__main__":
    unittest.main()
