"""O2 (16.11.2026): stop altı gerçekleşme (kural s3) ve risk gösterimi — ürün yollarına bağlanması.
s3 kuralının kendisi araştırma dalındaki `journal.giris_kosulu` / `journal.evaluate(kural="s3")` (tests/test_kural_s3.py);
burada yalnız YOLLAR sınanır: yeni öneri, önceden açık pozisyon, kullanıcının gerçek alışı, tahmin defteri sürümleri,
pozisyon hesabı. Ağ ve yapay zekâ yok."""
import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bist_haber import config, db, defter, journal, ready

SIG, GUN, GUN2, GUN3 = "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"
SL, AZAMI, GIRIS, TP1, TP2 = 9.0, 10.3, 10.0, 12.0, 13.0


def bar(conn, tk, d, o, h, lo, c):
    conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,1000000)",
                 (tk, d, o, h, lo, c))


def ozet_tablolar(conn, tablolar):
    out = {}
    for t in tablolar:
        h = hashlib.sha256()
        for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid"):
            h.update(repr(tuple(r)).encode("utf-8"))
        out[t] = h.hexdigest()
    return out


class Temel(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.conn = db.connect(self.tmp / "o2.db")

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hazir(self, tk, durum="aday", sonuc_json=None, acilis=None):
        cur = self.conn.execute(
            "INSERT INTO hazir_firsat(olusturuldu,analiz,signal_day,giris_gunu,ticker,tur,kapanis,giris,giris_alt,"
            "azami_giris,sl,tp1,tp2,rr1,vade_lo,vade_hi,haber_skoru,teknik_skor,risk,neden,durum,acilis,sonuc_json) "
            "VALUES('2026-01-05T19:00:00+03:00','aksam',?,?,?,'mevcut_fiyat',10,?,9.7,?,?,?,?,2.0,5,10,2.0,7,'orta',"
            "'deneme',?,?,?)", (SIG, GUN, tk, GIRIS, AZAMI, SL, TP1, TP2, durum, acilis, sonuc_json))
        self.conn.commit()
        return cur.lastrowid

    def hz(self, i):
        r = dict(self.conn.execute("SELECT * FROM hazir_firsat WHERE id=?", (i,)).fetchone())
        r["sonuc"] = json.loads(r["sonuc_json"]) if r["sonuc_json"] else {}
        return r


class YeniOneri(Temel):
    """Yeni öneri (henüz alınmamış): açılış ≤ SL → GİRİŞSİZ (yapay kâr yok)."""

    def test_open_below_equal_above_stop(self):
        for tk, o in (("ALT", 8.5), ("ESIT", SL), ("UST", 9.2), ("AZAMI", 10.5)):
            bar(self.conn, tk, GUN, o, max(o, 9.6), min(o, 8.4), 9.5)
            self.hazir(tk)
        self.conn.commit()
        ready.evaluate_all(self.conn)
        d = {r["ticker"]: r for r in (self.hz(i) for i in range(1, 5))}
        self.assertEqual((d["ALT"]["durum"], d["ALT"]["sonuc"]["sonuc"]), ("girissiz", "açılış stopun altında veya eşit"))
        self.assertEqual((d["ESIT"]["durum"], d["ESIT"]["sonuc"]["sonuc"]), ("girissiz", "açılış stopun altında veya eşit"))
        self.assertEqual(d["ALT"]["sonuc"]["kural"], "s3")
        self.assertEqual(d["AZAMI"]["sonuc"]["sonuc"], "açılış azami girişin üstünde")
        u = d["UST"]                                              # açılış SL'nin üstünde: girildi, s3 ile izleniyor
        self.assertIn(u["durum"], ("giris", "kapandi"))
        self.assertEqual(u["sonuc"]["kural"], "s3")
        self.assertEqual(u["sonuc"]["gerceklesme"]["alis"], "kural_simulasyonu_acilis")
        self.assertEqual(u["sonuc"]["gerceklesme"]["cikis"], "varsayimsal_kural_simulasyonu")
        self.assertEqual(ready.performance(self.conn)["girissiz"], 3)

    def test_opening_check_marks_below_stop(self):
        i = self.hazir("ACK")
        now = datetime(2026, 1, 6, 10, 10, tzinfo=config.TR_TZ)
        self.conn.execute("UPDATE hazir_firsat SET giris_gunu=? WHERE id=?", (now.date().isoformat(), i))
        out = ready.opening_check(self.conn, {"ACK": {"acilis": 8.9, "zaman": now}}, now)
        r = self.hz(i)
        self.assertEqual((r["durum"], r["sonuc"]["sonuc"], r["sonuc"]["kural"]), ("girissiz", "açılış stopun altında veya eşit", "s3"))
        self.assertIn("zarar durdurun", r["iptal_nedeni"])
        self.assertEqual(len(out["iptal"]), 1)


class OncedenAcikPozisyon(Temel):
    """s3'ten ÖNCE girilmiş öneri kendi (s2) kuralıyla sürer: geçmişe dönük değişmez."""

    def test_entered_before_s3_keeps_s2(self):
        bar(self.conn, "ESK", GUN, 8.5, 9.6, 8.4, 9.5)            # s2'de yapay kâr üreten durum
        bar(self.conn, "ESK", GUN2, 9.5, 9.7, 9.3, 9.6)
        s2 = journal.evaluate({"kaynak": "gercek", "gercek_giris_gunu": GUN, "gercek_giris_fiyati": 8.5, "signal_day": SIG,
                               "senaryo": "mevcut_fiyat", "sl": SL, "tp1": TP1, "tp2": TP2, "giris": GIRIS, "alarm": None,
                               "gecerlilik": 1}, journal.bars_for(self.conn, "ESK", SIG), 0.2, 0.1)
        i = self.hazir("ESK", durum="giris", acilis=8.5, sonuc_json=json.dumps({"durum": "açık"}))
        ready.evaluate_all(self.conn)
        r = self.hz(i)
        self.assertNotIn("kural", r["sonuc"])                     # s2 kaldı
        self.assertEqual(r["sonuc"].get("net_getiri_pct"), s2.get("net_getiri_pct"))
        self.assertEqual(journal.kural_sec({"durum": "giris"}, girilmis=("giris",)), "s2")
        self.assertEqual(journal.kural_sec({"durum": "açık", "kaynak": "otomatik"}), "s2")
        self.assertEqual(journal.kural_sec({"durum": "açık", "sonuc_json": json.dumps({"kural": "s3"})}), "s3")
        self.assertEqual(journal.kural_sec({"durum": "bekliyor", "kaynak": "otomatik"}), "s3")


class GercekAlis(Temel):
    """Kullanıcının kaydettiği gerçek alış: alış korunur, çıkış VARSAYIMSAL etiketlenir."""

    def jr(self, kaynak, durum="bekliyor", fill=None, fill_day=None, sonuc_json=None, senaryo="destek"):
        cur = self.conn.execute(
            "INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,gecerlilik,"
            "gercek_giris_gunu,gercek_giris_fiyati,durum,sonuc_json) VALUES('x',?,'GRC',?,?,?,?,?,?,5,?,?,?,?)",
            (SIG, kaynak, senaryo, GIRIS, SL, TP1, TP2, fill_day, fill, durum, sonuc_json))
        self.conn.commit()
        return cur.lastrowid

    def test_real_buy_labels_and_auto_versions(self):
        bar(self.conn, "GRC", GUN, 9.9, 10.2, 9.8, 10.0)
        bar(self.conn, "GRC", GUN2, 10.0, 12.5, 9.9, 12.2)
        g = self.jr("gercek", fill=9.95, fill_day=GUN, durum="bekliyor")       # yeni kaydedilen gerçek alış
        g_eski = self.jr("gercek", fill=9.95, fill_day=GUN, durum="açık", senaryo="kirilim")   # geçişten önce açık
        a_yeni = self.jr("otomatik", durum="bekliyor")
        a_eski = self.jr("otomatik", durum="açık", sonuc_json=json.dumps({"durum": "açık", "giris_fiyati": 9.9}),
                         senaryo="geri_cekilme")
        journal.update_all(self.conn, 0.2, 0.1)
        res = {i: json.loads(self.conn.execute("SELECT sonuc_json FROM trade_journal WHERE id=?", (i,)).fetchone()[0])
               for i in (g, a_yeni, a_eski)}
        self.assertEqual(res[g]["kural"], "s3")
        self.assertEqual(res[g]["gerceklesme"], {"alis": "kullanici_kaydi", "cikis": "henuz_yok_acik_pozisyon"})
        self.assertEqual(res[g]["giris_fiyati"], 9.95)            # kullanıcının alış fiyatı korunur
        journal.update_all(self.conn, 0.2, 0.1)                    # ikinci tur: açık s3 kaydı s3 KALIR (s2'ye dönmez)
        self.assertEqual(json.loads(self.conn.execute("SELECT sonuc_json FROM trade_journal WHERE id=?",
                                                      (g,)).fetchone()[0])["kural"], "s3")
        bar(self.conn, "GRC", GUN3, 13.3, 13.5, 13.0, 13.2)        # açılış TP2 üstünde → kapanır
        self.conn.commit()
        journal.update_all(self.conn, 0.2, 0.1)
        son = json.loads(self.conn.execute("SELECT sonuc_json FROM trade_journal WHERE id=?", (g,)).fetchone()[0])
        self.assertEqual((son["durum"], son["kural"]), ("kapandı", "s3"))
        self.assertEqual(son["gerceklesme"]["alis"], "kullanici_kaydi")
        self.assertEqual(son["gerceklesme"]["cikis"], "varsayimsal_kural_simulasyonu")
        self.assertEqual(res[a_yeni]["kural"], "s3")
        self.assertEqual(res[a_yeni]["gerceklesme"]["alis"], "kural_simulasyonu")
        self.assertNotIn("kural", res[a_eski])                    # önceden açık sanal pozisyon s2 ile sürdü
        eski_g = json.loads(self.conn.execute("SELECT sonuc_json FROM trade_journal WHERE id=?", (g_eski,)).fetchone()[0])
        self.assertNotIn("kural", eski_g)                         # önceden açık GERÇEK alış da s2 ile sürdü
        self.assertEqual(eski_g["giris_fiyati"], 9.95)

    def test_record_real_still_rejects_below_stop(self):
        a = self.jr("otomatik")
        with self.assertRaises(ValueError):
            journal.record_real(self.conn, a, GUN, 8.9)


class TahminDefteriSurum(Temel):
    """Tahmin defteri: yeni sözleşme s3; s2 tahmini s2 ile sonuçlanır (FAZ 1 kanıtı değişmez); s3 yeniden
    değerlendirmesi ayrı satır ve ayrı ölçüm grubu; eski satırlar değişmez."""

    def tahmin(self, tk, kural):
        cur = self.conn.execute(
            "INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
            "parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,komisyon_pct,"
            "kayma_pct,maliyet_protokol) VALUES(?,?,?,?,'2026-01-05T19:00:00+03:00','m','f','p',0.4,'orta',"
            "'mevcut_fiyat',?,?,?,?,?,1,?,0.2,0.1,?)", (f"{tk}{kural}", tk, SIG, GUN, GIRIS, AZAMI, SL, TP1, TP2, kural,
                                                        defter.MALIYET_PROTOKOL))
        self.conn.commit()
        return cur.lastrowid

    def test_versions_separate_and_old_rows_unchanged(self):
        self.assertEqual(defter.KURAL_SURUM, "s3")
        for tk in ("A2", "A3"):                                   # aynı fiyat: açılış SL'nin ALTINDA
            bar(self.conn, tk, GUN, 8.5, 9.6, 8.4, 9.5)
            bar(self.conn, tk, GUN2, 9.5, 9.7, 9.3, 9.6)
        bar(self.conn, "B3", GUN, 9.9, 10.2, 9.8, 10.0)          # açılış SL'nin üstünde
        bar(self.conn, "B3", GUN2, 10.0, 12.5, 9.9, 12.2)          # TP1
        bar(self.conn, "B3", GUN3, 13.3, 13.5, 13.0, 13.2)         # açılış TP2 üstünde → kapanır
        t2, t3, b3 = self.tahmin("A2", "s2"), self.tahmin("A3", "s3"), self.tahmin("B3", "s3")
        now = datetime(2026, 1, 9, 18, 30, tzinfo=config.TR_TZ)
        defter.sonuclandir(self.conn, now)
        s = {r["tahmin_id"]: dict(r) for r in self.conn.execute("SELECT * FROM tahmin_sonuc")}
        self.assertEqual((s[t2]["kural_surum"], s[t2]["sonuc_turu"]), ("s2", "tamamlandi"))   # kendi sözleşmesi
        self.assertEqual((s[t3]["kural_surum"], s[t3]["sonuc_turu"], s[t3]["neden"]),
                         ("s3", "girissiz", "açılış stopun altında veya eşit"))
        self.assertEqual((s[b3]["kural_surum"], s[b3]["sonuc_turu"]), ("s3", "tamamlandi"))
        self.assertEqual(json.loads(s[b3]["ayrinti_json"])["gerceklesme"]["cikis"], "varsayimsal_kural_simulasyonu")
        d = [dict(r) for r in self.conn.execute("SELECT * FROM tahmin_degerlendirme")]
        self.assertEqual([(x["tahmin_id"], x["kural_surum"], x["sonuc_turu"]) for x in d], [(t2, "s3", "girissiz")])
        once = ozet_tablolar(self.conn, ("tahmin", "tahmin_sonuc", "tahmin_degerlendirme"))
        defter.sonuclandir(self.conn, now)                         # tekrar: hiçbir şey değişmez / çoğalmaz
        self.assertEqual(ozet_tablolar(self.conn, ("tahmin", "tahmin_sonuc", "tahmin_degerlendirme")), once)
        # ölçüm grupları ayrı: s2/ölçüm s2, s2/ölçüm s3, s3/ölçüm s3
        gs = {(g["grup"]["kural_surum"], g["grup"]["olcum_kurali"]): g for g in defter.gruplar(self.conn)}
        self.assertEqual(set(gs), {("s2", "s2"), ("s2", "s3"), ("s3", "s3")})
        o22 = defter.ozet(self.conn, gs[("s2", "s2")]["grup"])
        o23 = defter.ozet(self.conn, gs[("s2", "s3")]["grup"])
        o33 = defter.ozet(self.conn, gs[("s3", "s3")]["grup"])
        self.assertEqual((o22["olculen"], o22["sayilar"]["girissiz"]), (1, 0))      # s2 ölçümü: s2 sonucu
        self.assertEqual((o23["olculen"], o23["sayilar"]["girissiz"]), (0, 1))      # s3 yeniden değerlendirmesi
        self.assertEqual((o33["sayilar"]["tahmin"], o33["olculen"], o33["sayilar"]["girissiz"]), (2, 1, 1))
        self.assertIn("ayrı yeniden değerlendirme", defter.grup_etiketi(gs[("s2", "s3")]["grup"]))
        self.assertNotIn("ayrı yeniden değerlendirme", defter.grup_etiketi(gs[("s2", "s2")]["grup"]))

    def test_immutable_rows_still_protected(self):
        bar(self.conn, "A2", GUN, 8.5, 9.6, 8.4, 9.5)
        bar(self.conn, "A2", GUN2, 9.5, 9.7, 9.3, 9.6)
        self.tahmin("A2", "s2")
        defter.sonuclandir(self.conn, datetime(2026, 1, 9, 18, 30, tzinfo=config.TR_TZ))
        import sqlite3
        for q in ("UPDATE tahmin_sonuc SET r=0", "DELETE FROM tahmin_degerlendirme", "UPDATE tahmin SET sl=1"):
            with self.assertRaises(sqlite3.DatabaseError):
                self.conn.execute(q)


class RiskGosterimi(unittest.TestCase):
    def test_entry_source_and_budget(self):
        r = journal.risk_ozeti(100000, 1.0, AZAMI, SL, 0.3, "azami_giris")
        ps = journal.position_size(100000, 1.0, AZAMI, SL, 0.3)
        self.assertEqual({k: r[k] for k in ps}, ps)               # position_size aynen kullanıldı (değişmedi)
        self.assertEqual((r["giris_fiyati"], r["giris_kaynagi"]), (AZAMI, "azami_giris"))
        self.assertLessEqual(r["stop_kayip"], 100000 * 1.0 / 100 + 1e-9)   # azami girişte başlangıç riski ≤ bütçe
        self.assertIn("en kötü", r["giris_kaynagi_tr"])
        g = journal.risk_ozeti(100000, 1.0, 9.8, SL, 0.3, "gercek_alis")
        self.assertIn("gerçek alış", g["giris_kaynagi_tr"])
        self.assertGreater(g["adet"], r["adet"])                  # gerçek fiyat daha iyi → daha çok adet
        with self.assertRaises(ValueError):
            journal.risk_ozeti(100000, 1.0, 10, SL, 0.3, "bilinmeyen")

    def test_wording(self):
        n = journal.STOP_KAYIP_NOTU
        self.assertIn("üst sınır değildir", n)
        self.assertIn("boşluk", n)
        self.assertIn("Midas", n)
        src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn("tahmini kayıp", src)
        self.assertNotIn("SL'ye gelinirse en fazla", src)        # eski ifade kaldırıldı


if __name__ == "__main__":
    unittest.main()


from tests import test_panel_flows as _pf  # noqa: E402  (sınıfı adıyla içe aktarmak testlerini burada ikinci kez koşturur)


class PanelO2(unittest.TestCase):
    """Hazır fırsat kartında pozisyon hesabı: azami girişe göre ön hesap, isteğe bağlı gerçek alış fiyatı, uyarı metni."""
    setUp = _pf.PanelFlowTests.setUp
    app = _pf.PanelFlowTests.app
    go = _pf.PanelFlowTests.go

    def test_ready_card_risk_line_and_real_price(self):
        from datetime import date
        from bist_haber import pipeline
        pipeline.save_settings(sermaye=100000.0, risk_pct=1.0)
        c = db.connect()
        c.execute("INSERT INTO hazir_firsat(olusturuldu,analiz,signal_day,giris_gunu,ticker,tur,kapanis,giris,giris_alt,"
                  "azami_giris,sl,tp1,tp2,rr1,vade_lo,vade_hi,haber_skoru,teknik_skor,risk,neden,durum) VALUES("
                  "'2026-11-09T19:00:00+03:00','aksam','2026-11-09',?,'POS','mevcut_fiyat',100,100,99.4,100.6,96,110,114,"
                  "2.5,10,14,2.5,7,'orta','Haber: deneme','aday')", (date.today().isoformat(),))
        c.commit()
        c.close()
        at = self.app()
        self.go(at, "🎯 Fırsatlar")
        cap = [x.value for x in at.caption if "Pozisyon hesabı" in x.value]
        self.assertTrue(cap, "pozisyon satırı yok")
        self.assertIn("100.60 TL (azami girişe göre ön hesap", cap[0])
        self.assertIn("stop seviyesinde tahmini kayıp", cap[0])
        self.assertIn("üst sınır değildir", cap[0])
        self.assertIn("Midas", cap[0])
        at.number_input(key=[k for k in (n.key for n in at.number_input) if k and k.startswith("rc_px_")][0]) \
            .set_value(98.0).run()
        self.assertEqual(len(at.exception), 0, str(at.exception))
        self.assertTrue(any("98.00 TL (sizin girdiğiniz gerçek alış fiyatı)" in x.value for x in at.caption))
        at.number_input(key=[k for k in (n.key for n in at.number_input) if k and k.startswith("rc_px_")][0]) \
            .set_value(95.0).run()
        self.assertTrue(any("plan geçersizdir" in w.value for w in at.warning))
        self.go(at, "📒 İşlem Günlüğü")
        self.assertTrue(any("varsayımsaldır" in x.value for x in at.caption))


class GuvenliGeriDonus(TahminDefteriSurum):
    """Geri dönüş ayarı (gerceklesme_kurali = "s2"): YENİ kayıtlar s2 ile başlar; s3 ile başlamış kayıtlar kendi
    kuralıyla sürer (eski koda dönmek s3 sözleşmeli tahmini s2 ile sonuçlandırırdı — provada görüldü)."""

    def setUp(self):
        super().setUp()
        from unittest.mock import patch
        from bist_haber import pipeline
        p = patch.object(pipeline, "SETTINGS_FILE", self.tmp / "ayarlar.json")
        p.start()
        self.addCleanup(p.stop)
        pipeline.save_settings(gerceklesme_kurali="s2")

    def test_setting_reverts_new_records_only(self):
        self.assertEqual(journal.yeni_kural(), "s2")
        bar(self.conn, "A3", GUN, 8.5, 9.6, 8.4, 9.5)
        bar(self.conn, "A3", GUN2, 9.5, 9.7, 9.3, 9.6)
        t3 = self.tahmin("A3", "s3")                               # O2 döneminde kaydedilmiş s3 sözleşmesi
        defter.sonuclandir(self.conn, datetime(2026, 1, 9, 18, 30, tzinfo=config.TR_TZ))
        s = dict(self.conn.execute("SELECT * FROM tahmin_sonuc WHERE tahmin_id=?", (t3,)).fetchone())
        self.assertEqual((s["kural_surum"], s["sonuc_turu"]), ("s3", "girissiz"))     # kendi kuralıyla
        i = self.hazir("A3")                                       # yeni öneri: s2 davranışı (eski hâl)
        ready.evaluate_all(self.conn)
        self.assertNotEqual(self.hz(i)["durum"], "girissiz")
        self.assertNotIn("kural", self.hz(i)["sonuc"])
        self.assertEqual(journal.kural_sec({"durum": "bekliyor", "kaynak": "otomatik"}), "s2")
        self.assertEqual(journal.kural_sec({"durum": "açık", "sonuc_json": json.dumps({"kural": "s3"})}), "s3")

    test_versions_separate_and_old_rows_unchanged = None
    test_immutable_rows_still_protected = None


from tests import test_defter as _td  # noqa: E402


class BagliOneri(TahminDefteriSurum):
    """Aynı olay (hazır fırsat + bağlı tahmin) iki ayrı kuralla SESSİZCE sonuçlanmaz: öneri tahminin sözleşmesini izler."""

    def bagli(self, tk, kural):
        i = self.hazir(tk)
        t = self.tahmin(tk, kural)
        # tahmin satırı değiştirilemez: bağı kurmak için aynı satırı hazir_firsat_id ile yeniden yaz (yeni kopya)
        self.conn.execute("INSERT INTO tahmin(plan_imzasi,hazir_firsat_id,ticker,signal_day,giris_gunu,tahmin_zamani,"
                          "model_surum,ozellik_surum,parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,"
                          "gecerlilik_gun,kural_surum,komisyon_pct,kayma_pct,maliyet_protokol) SELECT plan_imzasi||'b',?,"
                          "ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,parametre_surum,olasilik,"
                          "bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,komisyon_pct,kayma_pct,"
                          "maliyet_protokol FROM tahmin WHERE id=?", (i, t))
        self.conn.commit()
        return i

    def test_ready_follows_linked_prediction_contract(self):
        for tk in ("K2", "K3"):
            bar(self.conn, tk, GUN, 8.5, 9.6, 8.4, 9.5)            # açılış SL'nin altında
            bar(self.conn, tk, GUN2, 9.5, 9.7, 9.3, 9.6)
        i2, i3 = self.bagli("K2", "s2"), self.bagli("K3", "s3")
        self.assertEqual((ready.hazir_kurali(self.conn, self.hz(i2)), ready.hazir_kurali(self.conn, self.hz(i3))),
                         ("s2", "s3"))
        ready.evaluate_all(self.conn)
        defter.sonuclandir(self.conn, datetime(2026, 1, 9, 18, 30, tzinfo=config.TR_TZ))
        h2, h3 = self.hz(i2), self.hz(i3)
        self.assertNotEqual(h2["durum"], "girissiz")              # s2 sözleşmesi: öneri de s2 (tahminle aynı)
        self.assertNotIn("kural", h2["sonuc"])
        self.assertEqual((h3["durum"], h3["sonuc"]["kural"]), ("girissiz", "s3"))
        son = {r[0]: (r[1], r[2]) for r in self.conn.execute(
            "SELECT t.ticker, s.kural_surum, s.sonuc_turu FROM tahmin t JOIN tahmin_sonuc s ON s.tahmin_id=t.id "
            "WHERE t.hazir_firsat_id IS NOT NULL")}
        self.assertEqual(son["K2"][0], "s2")
        self.assertEqual(son["K3"], ("s3", "girissiz"))           # öneri ve tahmin aynı sonucu söylüyor

    test_versions_separate_and_old_rows_unchanged = None
    test_immutable_rows_still_protected = None


class YenidenAnaliz(_td.Base):
    """Kural s3'e geçtikten sonra aynı plan yeniden analiz edilir / kaydedilirse s2 tahmini ÜZERİNE YAZILMAZ."""

    def test_same_plan_is_repeat_changed_plan_is_new_s3(self):
        from unittest.mock import patch
        with patch.object(journal, "yeni_kural", return_value="s2"):      # geçişten önce yazılmış s2 tahmini
            self.store()
        t = self.tahminler()
        self.assertEqual([x["kural_surum"] for x in t], ["s2"])
        once = [tuple(r) for r in self.conn.execute("SELECT * FROM tahmin ORDER BY id")]
        self.store()                                              # aynı plan, s3 kodu → tekrar (yeni satır yok)
        self.assertEqual([tuple(r) for r in self.conn.execute("SELECT * FROM tahmin ORDER BY id")], once)
        p2 = dict(self.plan, tp2=self.plan["tp2"] + self.atr)     # plan değişti → yeni tahmin s3 sözleşmesiyle
        self.store(p2, now=_td.at(self.day, "19:30"))
        t = self.tahminler()
        self.assertEqual([x["kural_surum"] for x in t], ["s2", "s3"])
        self.assertEqual(tuple(self.conn.execute("SELECT * FROM tahmin WHERE id=?", (t[0]["id"],)).fetchone()), once[0])
        self.assertEqual(t[1]["onceki_tahmin_id"], t[0]["id"])
        defter.sonuclandir(self.conn, _td.at(_td.next_wd(self.gday, 2), "18:30"))
        self.assertEqual(self.sonuc(t[0]["id"])["sonuc_turu"], "yerini_aldi")    # eski s2 kendi kuralıyla kapandı
        self.assertEqual(self.sonuc(t[0]["id"])["kural_surum"], "s2")
        self.assertEqual(ready.hazir_kurali(self.conn, dict(self.conn.execute(
            "SELECT * FROM hazir_firsat").fetchone())), "s3")    # öneri en güncel tahminin sözleşmesini izler
