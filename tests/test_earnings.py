"""Bilanço takvimi (SPK II-14.1 Md. 10–11) testleri."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from bist_haber import db, earnings as E


class DeadlineTests(unittest.TestCase):
    def test_q3_2026(self):  # 30 Eylül + 30 / 40 gün
        last, nxt = E.periods_around(date(2026, 11, 7))
        self.assertEqual((last["donem"], last["son_bireysel"], last["son_konsolide"]),
                         ("2026 9 aylık", "2026-10-30", "2026-11-09"))
        self.assertEqual((nxt["donem"], nxt["son_bireysel"], nxt["son_konsolide"]),
                         ("2026 yıllık", "2027-03-01", "2027-03-11"))   # 31 Aralık + 60 / 70

    def test_weekend_and_holiday_shift_to_next_business_day(self):
        last, _ = E.periods_around(date(2026, 2, 1))
        self.assertEqual(last["son_bireysel"], "2026-03-02")   # 1 Mart 2026 pazar
        q1 = E.periods_around(date(2026, 4, 5))[0]
        self.assertEqual(q1["son_konsolide"], "2026-05-11")    # 10 Mayıs pazar

    def test_half_year_includes_limited_review_10_days(self):
        h1 = E.periods_around(date(2026, 7, 15))[0]
        self.assertEqual((h1["son_bireysel"], h1["son_konsolide"]), ("2026-08-10", "2026-08-19"))  # 40 / 50 gün


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO companies VALUES('AAA','AAA SANAYİ A.Ş.',NULL)")
        self.conn.execute("INSERT INTO companies VALUES('BNK','ÖRNEK BANKASI A.Ş.',NULL)")
        self.n = 0

    def news(self, ticker, subject, when, source="kap", donem=None):
        self.n += 1
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,candidates,fetched_at,"
                          "donem) VALUES(?,?,?,?,?,?,?,'n',?)",
                          (f"x{self.n}", source, when, when[:10], subject, subject, ticker, donem))
        self.conn.commit()

    def cover(self, start="2026-10-01", end="2026-11-07", listed_at="2026-11-07T12:00:00+03:00"):
        """KAP listesinin bu günler için eksiksiz alındığını işaretle (kap.record_coverage)."""
        from bist_haber import kap
        kap.record_coverage(self.conn, date.fromisoformat(start), date.fromisoformat(end), listed_at)

    def test_published_from_kap(self):
        self.cover()
        self.news("AAA", "Finansal Rapor", "2026-10-28T18:30:00+03:00", donem="2026/3")
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["durum"], s["aciklama_tarihi"], s["kaynak"]), ("açıklandı", "2026-10-28", "KAP finansal rapor bildirimi"))
        self.assertIsNone(E.window_risk(s, date(2026, 11, 7), 15))

    def test_late_previous_period_report_is_not_current(self):  # gerçek örnek: BRKO 6 aylık rapor 25.09, BTCIM 02.10
        self.cover()
        self.news("AAA", "Finansal Rapor", "2026-10-02T19:56:00+03:00", donem="2026/2")
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual(s["durum"], "açıklanmadı")
        self.assertIsNone(s["aciklama_tarihi"])

    def test_not_published_with_full_coverage_and_consolidated(self):
        self.cover()
        self.news("AAA", "Sorumluluk Beyanı (Konsolide)", "2026-08-15T10:00:00+03:00")
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["durum"], s["konsolide"], s["son_tarih"]), ("açıklanmadı", True, "2026-11-09"))
        self.assertTrue(E.window_risk(s, date(2026, 11, 7), 15).startswith("Vade içinde bilanço açıklanacak"))
        self.assertIn("9 Kasım 2026", E.describe(s, date(2026, 11, 7)))

    def test_non_consolidated_deadline_passed(self):
        self.cover()
        self.news("AAA", "Faaliyet Raporu (Konsolide Olmayan)", "2026-08-15T10:00:00+03:00")
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["durum"], s["konsolide"]), ("süresi geçti, kayıtlarda yok", False))
        self.assertIsNone(E.window_risk(s, date(2026, 11, 7), 15))
        # fiyatı hiç yok (gerçek: 95 faktoring/varlık kiralama şirketi) → yükümlülük kesin değil uyarısı
        self.assertFalse(s["fiyat_var"])
        self.assertIn("aracın vadesi dolana kadar tabidir", E.describe(s, date(2026, 11, 7)))
        self.conn.execute("INSERT INTO prices(ticker,date,close) VALUES('AAA','2026-11-06',10)")
        s2 = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertTrue(s2["fiyat_var"])
        self.assertNotIn("aracın vadesi", E.describe(s2, date(2026, 11, 7)))   # borsada işlem gören: uyarı yok

    def test_gap_in_listing_makes_status_unknown(self):  # uygulama birkaç gün açılmadı → kesinlik uydurulmaz
        self.cover("2026-10-01", "2026-10-20", "2026-10-21T09:00:00+03:00")
        self.cover("2026-10-24", "2026-11-07")
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["durum"], s["bosluk_sayisi"]), ("bilinmiyor", 3))
        self.assertIn("3 günün KAP listesi alınmamış", E.describe(s, date(2026, 11, 7)))

    def test_day_listed_only_during_that_day_counts_as_gap(self):
        self.cover("2026-10-01", "2026-11-07", "2026-11-07T08:00:00+03:00")
        self.cover("2026-10-15", "2026-10-15", "2026-10-15T09:00:00+03:00")  # MAX: sonraki alım geçerli kalır
        self.assertEqual(E.status(self.conn, "AAA", date(2026, 11, 7))["bosluk_sayisi"], 0)
        from bist_haber import kap
        self.conn.execute("UPDATE kap_coverage SET listed_at='2026-10-15T09:00:00+03:00' WHERE day='2026-10-15'")
        self.assertEqual(kap.coverage_gaps(self.conn, date(2026, 10, 14), date(2026, 10, 16), date(2026, 11, 7)),
                         [date(2026, 10, 15)])                         # o gün 09:00'da alınmış: akşam bildirimleri eksik

    def test_unknown_when_records_start_after_period_end(self):
        self.cover("2026-11-06", "2026-11-07")
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual(s["durum"], "bilinmiyor")
        self.assertIn("bilmiyoruz", E.describe(s, date(2026, 11, 7)))
        self.assertIn("konsolide değilse 30 Ekim 2026, konsolide ise 9 Kasım 2026", E.describe(s, date(2026, 11, 7)))
        self.assertTrue(E.window_risk(s, date(2026, 11, 7), 15).startswith("Bilanço henüz açıklanmadıysa"))

    def test_spk_extension_notice_is_reported(self):  # gerçek örnek: TRKNT 13.10.2026
        self.cover()
        self.news("AAA", "Finansal Rapor Ek Süre Taleplerine İlişkin SPK Değerlendirmesi", "2026-10-13T14:58:00+03:00")
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual(s["ek_sure"], "2026-10-13")
        self.assertIn("SPK ek süre talebini değerlendirdi (13 Ekim 2026", E.describe(s, date(2026, 11, 7)))

    def test_company_with_both_consolidated_and_solo_is_consolidated(self):  # gerçek örnek: QYATB
        self.cover()
        self.news("AAA", "Sorumluluk Beyanı (Konsolide)", "2026-08-14T10:00:00+03:00")
        self.news("AAA", "Sorumluluk Beyanı (Konsolide Olmayan)", "2026-08-14T10:05:00+03:00")   # en son bu
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["konsolide"], s["son_tarih"], s["durum"]), (True, "2026-11-09", "açıklanmadı"))

    def test_half_year_assumption_is_stated(self):
        s = E.status(self.conn, "AAA", date(2026, 7, 15))
        self.assertIn("sınırlı bağımsız denetim için +10 gün", E.describe(s, date(2026, 7, 15)))

    def test_financial_result_news_counts_as_published(self):  # gerçek örnek: SOKM, Bloomberg HT 5 Kasım
        self.news("XYZ", "Özel Durum Açıklaması (Genel)", "2026-11-06T10:00:00+03:00")
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,fetched_at) "
                          "VALUES('r1','rss:bloomberght','2026-11-05T22:29:00+03:00','2026-11-06','Kâra döndü','n')")
        self.conn.execute("INSERT INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,event_type,"
                          "reason,published_at,effective_date) VALUES('r1','AAA',1,3,0.9,'orta','finansal_sonuc','x',"
                          "'2026-11-05T22:29:00+03:00','2026-11-06')")
        self.conn.commit()
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual((s["durum"], s["kaynak"]), ("açıklandı", "haber analizi (finansal sonuç)"))

    def test_old_period_report_does_not_count(self):
        self.cover("2026-07-01", "2026-11-07")
        self.news("AAA", "Finansal Rapor", "2026-08-10T10:00:00+03:00", donem="2026/2")   # 6 aylık rapor
        s = E.status(self.conn, "AAA", date(2026, 11, 7))
        self.assertEqual(s["durum"], "açıklanmadı")      # konsolide bilinmiyor → temkinli geç tarih (9 Kasım)
        self.assertIsNone(s["aciklama_tarihi"])

    def test_bank_special_regulation_note(self):
        s = E.status(self.conn, "BNK", date(2026, 11, 7))
        self.assertTrue(s["ozel_mevzuat"])
        self.assertIn("daha kısa olabilir", E.describe(s, date(2026, 11, 7)))



class PlanIntegrationTests(unittest.TestCase):
    def test_earnings_risk_enters_plan_with_weight_two(self):
        from bist_haber import tradeplan
        from test_entries import base
        news = {"score": 3, "direction": 1, "confidence": 0.8, "flags": "", "persistence": "orta"}
        msg = "Vade içinde bilanço açıklanacak (yasal son gün 9 Kasım 2026): ..."
        calm = tradeplan.plan(base(), news)
        hot = tradeplan.plan(base(), dict(news, bilanco_riski=msg))
        self.assertIn(msg, hot["riskler"])
        self.assertEqual(tradeplan._points(hot["riskler"]) - tradeplan._points(calm["riskler"]), 2)
        self.assertEqual(tradeplan._points(["Bilanço henüz açıklanmadıysa vade içinde ..."]), 1)


if __name__ == "__main__":
    unittest.main()
