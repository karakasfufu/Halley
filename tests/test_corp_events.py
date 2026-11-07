"""Şirket olayları (genel kurul, kâr payı, sermaye artırımı) — gerçek KAP bildirimlerinin form alanlarından
kısaltılmış örneklerle. Bedelsiz hak kullanım günleri (KORDS 14.09, AKFYE 21.09, MEGMT 21.09.2026) Yahoo'nun bölünme
kayıtlarıyla birebir aynı çıktı (2026-11-07)."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from bist_haber import corp_events as C, db

GK_NEW = """Özet Bilgi
2026 Yılı Olağanüstü Genel Kurul Tescili hk.
Genel Kurul Çağrısı
Genel Kurul Tipi
Olağanüstü Genel Kurul
Karar Tarihi
04.08.2026
Genel Kurul Tarihi
02.09.2026
Genel Kurul Saati
10:30
GK'na Katılım İçin Pay Sahibi Olunması Gereken Son Tarih
01.09.2026
Gündemde Yer Alan Hak Kullanım Süreçleri
Yoktur
Genel Kurul Sonuçları
Genel Kurul Yapıldı mı?
Evet
Genel Kurul Sonuçları
Şirketimizin ... 02Eylül 2026 ... yapılmıştır"""

GK_OLD = """Genel Kurul İşlemlerine İlişkin Bildirim
Bildirim İçeriği
Karar Tarihi
05/11/2026
Genel Kurul Toplantı Türü
Olağanüstü (Extraordinary)
Tarih
Date
05/11/2026
Saati
Time
14:00"""

KAR = """Karar Tarihi
24.08.2026
Konunun Gündemde Yer Aldığı Genel Kurul Tarihi
29.09.2026
Nakit Kar Payı Ödeme Şekli
Peşin
A Grubu, İşlem Görmüyor, TREEIBG00025
Peşin
0,0179792
1,79792
B Grubu, ETILR, TREEIBG00017
Peşin
0,0179792
1,79792
Pay Olarak Kar Payı Ödeme Tutar ve Oranları
B Grubu, ETILR, TREEIBG00017
0"""

KAR_TAKSIT = """Konunun Gündemde Yer Aldığı Genel Kurul Tarihi
15.04.2026
Nakit Kar Payı Ödeme Şekli
2 Taksit
B Grubu, SDTTR, TRESDTT00013
1. Taksit
0,0082909
B Grubu, SDTTR, TRESDTT00013
2. Taksit
0,0082909
B Grubu, SDTTR, TRESDTT00013
TOPLAM
0,0165818
Kar Payı Ödeme Tarihleri
Genel kurulca, nakit kar payı dağıtım tarihinin/tarihlerinin belirlenmesi konusunda şirket yönetimi yetkilendirilmiştir.
Pay Olarak Kar Payı Ödeme Tutar ve Oranları"""

BEDELSIZ = """Özet Bilgi
Bedelsiz Sermaye Artırımı Hk.
Bedelsiz Sermaye Artırımı
SPK Onay Tarihi
09.09.2026
Bedelsiz Pay Alma Hakkı Kullanım Başlangıç Tarihi
14.09.2026
Kayıt Tarihi
15.09.2026 * Borsada işlem gören tipteki payların hak sahiplerinin belirlendiği tarih.
Ödeme Tarihi
16.09.2026 * Sermaye artırımı varsa yeni payların ..."""

RUCHAN = """Özet Bilgi
Bedelli Sermaye Artırımında Kullanılmayan Rüçhan Hakkı Tutarı Hk.
Bedelli Sermaye Artırımı (Rüçhan hakkı kullandırılarak)
Rüçhan Hakkı Kullanımı Başlangıç Tarihi
22.10.2026
Rüçhan Hakkı Kullanımı Bitiş Tarihi
05.11.2026
SPK Onay Tarihi
16.10.2026"""


def by_type(evs):
    return {e["tur"]: e for e in evs}


class ParseTests(unittest.TestCase):
    def test_general_assembly_new_form(self):
        e = by_type(C.parse_notice("Genel Kurul İşlemlerine İlişkin Bildirim", GK_NEW, ["IDGYO"], "t", "n1"))
        self.assertEqual((e["genel_kurul"]["tarih"], e["gk_son_pay"]["tarih"]), ("2026-09-02", "2026-09-01"))
        self.assertEqual((e["genel_kurul"]["tip"], e["genel_kurul"]["saat"]), ("Olağanüstü Genel Kurul", "10:30"))
        self.assertEqual(e["genel_kurul"]["yapildi"], "Evet")          # ASCII değer atlanmamalı (yakalanan hata)
        self.assertEqual(e["genel_kurul"]["hak_surecleri"], "Yoktur")
        self.assertNotIn("2026-08-04", [x["tarih"] for x in e.values()])  # karar tarihi olay değil

    def test_general_assembly_old_bilingual_form(self):
        e = by_type(C.parse_notice("Genel Kurul Bildirimi", GK_OLD, ["MRBKF"], "t", "n2"))
        self.assertEqual((e["genel_kurul"]["tarih"], e["genel_kurul"]["saat"]), ("2026-11-05", "14:00"))
        self.assertEqual(e["genel_kurul"]["tip"], "Olağanüstü (Extraordinary)")

    def test_dividend_single_payment(self):
        e = by_type(C.parse_notice("Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", KAR, ["ETILR"], "t", "n3"))
        self.assertEqual(e["temettu_gk"]["tarih"], "2026-09-29")
        self.assertEqual((e["temettu_gk"]["odeme_sekli"], e["temettu_gk"]["brut_tl"]), ("Peşin", 0.0179792))

    def test_dividend_instalments_use_total_and_no_invented_dates(self):
        evs = C.parse_notice("Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", KAR_TAKSIT, ["SDTTR"], "t", "n4")
        e = by_type(evs)
        self.assertEqual(e["temettu_gk"]["brut_tl"], 0.0165818)
        self.assertNotIn("temettu_tarih", e)                       # tablo boş: tarih uydurulmaz

    def test_bonus_issue_adjustment_day(self):  # KORDS gerçek örnek; Yahoo bölünme günü 14.09.2026
        e = by_type(C.parse_notice("Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim", BEDELSIZ, ["KORDS"], "t", "n5"))
        self.assertEqual(e["bedelsiz_hak"]["tarih"], "2026-09-14")
        self.assertTrue(e["bedelsiz_hak"]["fiyat_duzeltir"])
        self.assertEqual((e["kayit"]["tarih"], e["odeme"]["tarih"]), ("2026-09-15", "2026-09-16"))
        self.assertEqual(e["bedelsiz_hak"]["tip"], "Bedelsiz Sermaye Artırımı")

    def test_rights_issue_type_not_confused_with_summary_line(self):  # SKBNK gerçek örnek
        e = by_type(C.parse_notice("Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim", RUCHAN, ["SKBNK"], "t", "n6"))
        self.assertEqual(e["ruchan_bas"]["tip"], "Bedelli Sermaye Artırımı (Rüçhan hakkı kullandırılarak)")
        self.assertEqual((e["ruchan_bas"]["tarih"], e["ruchan_bit"]["tarih"]), ("2026-10-22", "2026-11-05"))

    def test_other_subjects_ignored(self):
        self.assertEqual(C.parse_notice("Özel Durum Açıklaması (Genel)", BEDELSIZ, ["X"], "t", "n7"), [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)

    def add(self, nid, when, subject, body, ticker="KORDS"):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,fetched_at) "
                          "VALUES(?,?,?,?,?,?,?,?,'n')", (nid, "kap", when, when[:10], subject, subject, body, ticker))
        self.conn.commit()

    def test_latest_notice_wins_and_window(self):
        self.add("a", "2026-09-01T10:00:00+03:00", "Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim",
                 BEDELSIZ.replace("14.09.2026", "10.09.2026"))
        self.add("b", "2026-09-10T10:00:00+03:00", "Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim", BEDELSIZ)
        up = C.upcoming(self.conn, "KORDS", date(2026, 9, 11), 15)
        self.assertEqual([e["tarih"] for e in up["yaklasan"] if e["tur"] == "bedelsiz_hak"], ["2026-09-14"])
        risks = C.risk_lines(up)
        self.assertTrue(any(r.startswith("Vade içinde fiyat düzeltmesi: 14.09") for r in risks))
        self.assertIn("Yaklaşan", C.describe(up))

    def test_dividend_risk_with_yield(self):
        self.add("c", "2026-09-10T10:00:00+03:00", "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", KAR, "ETILR")
        up = C.upcoming(self.conn, "ETILR", date(2026, 9, 20), 15)
        r = C.risk_lines(up, price=1.8)
        self.assertTrue(any("kâr payı" in x and "%1.0" in x for x in r), r)

    def test_nothing_recorded(self):
        up = C.upcoming(self.conn, "XXX", date(2026, 11, 7), 15)
        self.assertEqual(C.risk_lines(up), [])
        self.assertIn("yok", C.describe(up))



FROTO_KAR = """Konunun Gündemde Yer Aldığı Genel Kurul Tarihi
24.11.2026
Nakit Kar Payı Ödeme Şekli
Peşin
Nakit Kar Payı Ödeme Tutar ve Oranları
FROTO, TRAOTOSN91H6
Peşin
3,0700000
307
15
2,6095000
260,95
Kar Payı Ödeme Tarihleri
Ödeme
Teklif Edilen
Nakit Kar Payı Hak Kullanım Tarihi (1)
Kesinleşen
Nakit Kar Payı Hak Kullanım Tarihi (2)
Ödeme Tarihi (3)
Kayıt Tarihi (4)
Peşin
26.11.2026
30.11.2026
27.11.2026
(1) Kar payının şirket tarafından ödeneceği ve payın kar payı hakkı bulunmadan işlem görmeye başlayacağı tarih (teklif edilen).
Pay Olarak Kar Payı Ödeme Tutar ve Oranları"""

SDTTR_TABLE = """B Grubu, SDTTR, TRESDTT00013
1. Taksit
0,0082909
B Grubu, SDTTR, TRESDTT00013
2. Taksit
0,0082909
B Grubu, SDTTR, TRESDTT00013
TOPLAM
0,0165818
Kar Payı Ödeme Tarihleri
Ödeme
Teklif Edilen
Nakit Kar Payı Hak Kullanım Tarihi (1)
Kesinleşen
Nakit Kar Payı Hak Kullanım Tarihi (2)
Ödeme Tarihi (3)
Kayıt Tarihi (4)
1. Taksit
25.11.2026
27.11.2026
26.11.2026
2. Taksit
23.12.2026
25.12.2026
24.12.2026
(1) ...
Pay Olarak Kar Payı Ödeme Tutar ve Oranları"""


class PaymentTableTests(unittest.TestCase):
    """Gerçek dolu tablolar (2026-11-07). MCARD 23.10.2026 hak kullanımı ve 2,5711 TL brüt tutarı Yahoo temettü
    kaydıyla birebir aynı çıktı."""

    def test_single_group_company_and_ex_date(self):  # FROTO: tek gruplu satır "FROTO, TRA..."
        e = [x for x in C.parse_notice("Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", FROTO_KAR, ["FROTO"], "t", "n")]
        hak = next(x for x in e if x["tur"] == "temettu_hak")
        self.assertEqual((hak["tarih"], hak["brut_tl"]), ("2026-11-26", 3.07))
        self.assertEqual(next(x for x in e if x["tur"] == "temettu_odeme")["tarih"], "2026-11-30")

    def test_instalments_each_row(self):
        e = C.parse_notice("Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", SDTTR_TABLE, ["SDTTR"], "t", "n")
        hak = [(x["tarih"], x["brut_tl"]) for x in e if x["tur"] == "temettu_hak"]
        self.assertEqual(hak, [("2026-11-25", 0.0082909), ("2026-12-23", 0.0082909)])

    def test_inconsistent_order_is_not_labelled(self):
        bad = FROTO_KAR.replace("26.11.2026\n30.11.2026\n27.11.2026", "30.11.2026\n26.11.2026\n27.11.2026")
        e = C.parse_notice("Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", bad, ["FROTO"], "t", "n")
        self.assertFalse(any(x["tur"] == "temettu_hak" for x in e))
        self.assertTrue(any(x["tur"] == "temettu_tarih" for x in e))   # tarihler "bildirimi açın" notuyla kalır

    def test_dividend_risk_line_with_yield(self):
        e = C.parse_notice("Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", FROTO_KAR, ["FROTO"], "t", "n")
        up = {"yaklasan": [x for x in e if x["tur"] == "temettu_hak"], "yakin_gecmis": []}
        r = C.risk_lines(up, price=73.15)
        self.assertTrue(any("26.11" in x and "%4.2" in x for x in r), r)


class PlanIntegrationTests(unittest.TestCase):
    def test_price_adjustment_weighs_two_points(self):
        from bist_haber import tradeplan
        from test_entries import base
        news = {"score": 3, "direction": 1, "confidence": 0.8, "flags": "", "persistence": "orta"}
        line = "Vade içinde fiyat düzeltmesi: 14.09 Bedelsiz pay hak kullanımı başlangıcı ..."
        calm = tradeplan.plan(base(), news)
        hot = tradeplan.plan(base(), dict(news, olay_riskleri=[line, "Vade içinde genel kurul: 20.10 (Olağan)"]))
        self.assertIn(line, hot["riskler"])
        self.assertEqual(tradeplan._points(hot["riskler"]) - tradeplan._points(calm["riskler"]), 3)


if __name__ == "__main__":
    unittest.main()


class ReviewBTests(unittest.TestCase):
    """B son kontrolü (2026-11-07) düzeltmeleri."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)

    def add(self, nid, when, subject, body, ticker="FROTO"):
        self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,body,candidates,fetched_at) "
                          "VALUES(?,?,?,?,?,?,?,?,'n')", (nid, "kap", when, when[:10], subject, subject, body, ticker))
        self.conn.commit()

    def test_two_different_general_assemblies_both_kept(self):
        olagan = GK_NEW.replace("Olağanüstü Genel Kurul", "Olağan Genel Kurul").replace("02.09.2026", "20.11.2026")
        olaganustu = GK_NEW.replace("02.09.2026", "24.11.2026")
        self.add("a", "2026-10-20T10:00:00+03:00", "Genel Kurul İşlemlerine İlişkin Bildirim", olagan)
        self.add("b", "2026-10-27T10:00:00+03:00", "Genel Kurul İşlemlerine İlişkin Bildirim", olaganustu)
        gk = [e["tarih"] for e in C.events_for(self.conn, "FROTO") if e["tur"] == "genel_kurul"]
        self.assertEqual(gk, ["2026-11-20", "2026-11-24"])

    def test_same_assembly_update_replaces_old_date(self):  # erteleme/düzeltme: eski tarih kalmaz
        self.add("a", "2026-10-20T10:00:00+03:00", "Genel Kurul İşlemlerine İlişkin Bildirim", GK_NEW.replace("02.09.2026", "20.11.2026"))
        self.add("b", "2026-10-27T10:00:00+03:00", "Genel Kurul İşlemlerine İlişkin Bildirim", GK_NEW.replace("02.09.2026", "27.11.2026"))
        gk = [e["tarih"] for e in C.events_for(self.conn, "FROTO") if e["tur"] == "genel_kurul"]
        self.assertEqual(gk, ["2026-11-27"])

    def test_same_dividend_counted_once_in_risks(self):
        self.add("k", "2026-10-27T18:20:00+03:00", "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", FROTO_KAR)
        up = C.upcoming(self.conn, "FROTO", date(2026, 11, 7), 15)
        r = [x for x in C.risk_lines(up, price=73.15) if "kâr payı" in x]
        self.assertEqual(len(r), 1, r)
        self.assertIn("26.11", r[0])


class DividendVsStopTests(unittest.TestCase):
    """A–B uyumu: temettü düşüşü zarar durdur mesafesinin yarısı ya da fazlasıysa uyarı."""

    def test_warning_when_dividend_eats_stop_distance(self):
        from bist_haber import tradeplan
        from test_entries import base
        news = {"score": 3, "direction": 1, "confidence": 0.8, "flags": "", "persistence": "orta",
                "temettu": [("2026-11-26", 4.2)]}
        p = tradeplan.plan(base(), news)
        brk = next(s for s in p["girisler"]["senaryolar"] if s["tur"] == "kirilim")   # SL ~%2,3
        self.assertTrue(any(n.startswith("Temettü düşüşü SL'yi tetikleyebilir: 26.11") for n in brk["notlar"]))
        self.assertTrue(any(r.startswith("Temettü düşüşü SL'yi tetikleyebilir") for r in p["riskler"]))  # referans

    def test_small_dividend_no_warning(self):
        from bist_haber import tradeplan
        from test_entries import base
        news = {"score": 3, "direction": 1, "confidence": 0.8, "flags": "", "persistence": "orta",
                "temettu": [("2026-11-13", 0.2)]}
        p = tradeplan.plan(base(), news)
        self.assertFalse(any("Temettü düşüşü" in n for s in p["girisler"]["senaryolar"] for n in s.get("notlar", [])))
        self.assertFalse(any("Temettü düşüşü" in r for r in p["riskler"]))
