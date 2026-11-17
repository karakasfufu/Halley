"""O5 (17.11.2026): kabul edilmiş izleme bileşenlerinin bekçiye ve panele bağlanması. K1 kapalı (hiçbir koşulda olay
yok); bekçi çağrısı akşamda, günde bir kez, hata yalıtımlı; sürüm grupları (O2 ölçüm kuralı dahil) birleştirilmez;
panel salt-okur ve yetersiz veriyi 'sağlıklı' göstermez. Model eğitilmez / değiştirilmez."""
import json
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bist_haber import config, db, defter, izleme, watchdog
from tests.test_faz6_izleme import REF, iyi, kayitlar


class K1Kapali(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_k1_never_produces_event_even_if_breached(self):
        o = izleme.olc(kayitlar(120, 3, iyi), REF)
        o["K1"] = {"durum": "esik_asildi", "neden": "zorla", "orneklem": o["P2"]["orneklem"]}   # olsa bile
        e = [{"grup": {}, "etiket": "G", "pencereler": {"birikimli": o, "son_60_gun": o}}]
        with patch.object(izleme, "degerlendir", lambda conn: e):
            for gun in range(1, 29):                              # 28 farklı gün: P1/P2 için teyit bile oluşabilir
                r = izleme.kontrol_et(None, self.tmp, datetime(2026, 12, gun, 19))
                self.assertFalse(any(x["olcut"] == "K1" for x in r.get("olaylar", [])))
        durum = json.loads((self.tmp / "izleme_durumu.json").read_text(encoding="utf-8"))
        self.assertFalse(any("|K1" in k for k in durum))
        self.assertEqual(izleme.UYARI_OLCUTLERI, ("P1", "P2"))


class Bekci(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = self.tmp / "bist_haber.db"
        self.conn = db.connect(self.p)
        for x in (patch.object(config, "DATA", self.tmp),):
            x.start()
            self.addCleanup(x.stop)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_daily_once_and_local_files_only(self):
        r1 = watchdog.izleme_kontrolu(self.conn, datetime(2026, 12, 1, 19, tzinfo=config.TR_TZ))
        r2 = watchdog.izleme_kontrolu(self.conn, datetime(2026, 12, 1, 21, tzinfo=config.TR_TZ))
        self.assertEqual(r1.get("olay"), 0)
        self.assertIn("atlandi", r2)                              # günde en çok bir kontrol
        self.assertTrue((self.tmp / "izleme_durumu.json").exists())

    def test_error_isolated(self):
        with patch.object(izleme, "kontrol_et", side_effect=RuntimeError("bozuk")):
            r = watchdog.izleme_kontrolu(self.conn)
        self.assertIn("bozuk", r["hata"])                         # bekçiyi durdurmaz

    def test_called_in_evening_session_only(self):
        with patch.object(watchdog, "izleme_kontrolu", return_value={"olay": 0}) as m:
            src = Path(watchdog.__file__).read_text(encoding="utf-8")
        self.assertIn('if kind == "aksam":\n        out["izleme"] = izleme_kontrolu(conn, now)',
                      src.replace("\r\n", "\n"))
        m.assert_not_called()


class SurumGruplari(unittest.TestCase):
    """O2 ölçüm kuralı grupları izlemede de ayrı: s2 tahminin s3 yeniden değerlendirmesi kendi grubunda ölçülür."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.conn = db.connect(self.tmp / "bist_haber.db")

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tahmin(self, i, kural, sonuc_kural=None, deger_kural=None):
        cur = self.conn.execute(
            "INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,ozellik_surum,"
            "parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,komisyon_pct,"
            "kayma_pct,maliyet_protokol) VALUES(?,?,'2026-01-01','2026-01-02','2026-01-01T19:00:00+03:00','tp1_v1','f',"
            "'p',0.4,'orta','t',10,10.3,9,12,13,1,?,0.2,0.1,?)", (f"k{i}", f"T{i}", kural, defter.MALIYET_PROTOKOL))
        tid = cur.lastrowid
        if sonuc_kural:
            self.conn.execute("INSERT INTO tahmin_sonuc(tahmin_id,sonuc_turu,tp1_goruldu,tp1_olayi,r,net_getiri_pct,"
                              "degerlendirme_zamani,kural_surum) VALUES(?,'tamamlandi',1,1,1,2,'z',?)", (tid, sonuc_kural))
        if deger_kural:
            self.conn.execute("INSERT INTO tahmin_degerlendirme(tahmin_id,kural_surum,sonuc_turu,tp1_olayi,r,"
                              "net_getiri_pct,gerekce,degerlendirme_zamani) VALUES(?,?,'girissiz',0,NULL,NULL,'g','z')",
                              (tid, deger_kural))
        self.conn.commit()

    def test_groups_not_merged(self):
        self.tahmin(1, "s2", sonuc_kural="s2", deger_kural="s3")
        self.tahmin(2, "s3", sonuc_kural="s3")
        e = {(x["grup"]["kural_surum"], x["grup"]["olcum_kurali"]): x for x in izleme.degerlendir(self.conn, REF)}
        self.assertEqual(set(e), {("s2", "s2"), ("s2", "s3"), ("s3", "s3")})
        n = {k: v["pencereler"]["birikimli"]["P2"]["orneklem"]["n"] for k, v in e.items()}
        self.assertEqual(n, {("s2", "s2"): 1, ("s2", "s3"): 0, ("s3", "s3"): 1})   # s3 değerlendirmesi girişsiz → ölçülmez
        for v in e.values():
            self.assertEqual(v["pencereler"]["birikimli"]["P2"]["durum"], "yetersiz")   # az veri: sağlıklı denmez


from tests import test_panel_flows as _pf  # noqa: E402


class PanelO5(unittest.TestCase):
    setUp = _pf.PanelFlowTests.setUp
    app = _pf.PanelFlowTests.app
    go = _pf.PanelFlowTests.go

    def test_performance_shows_monitoring_k1_closed_read_only(self):
        once = sorted(p.name for p in config.DATA.iterdir())
        at = self.app("🏁 Performans")
        metin = " ".join(x.value for x in at.caption) + " ".join(getattr(x, "label", "") for x in at.expander)
        self.assertIn("Model izleme", metin)
        self.assertIn("Kalibrasyon (K1) kapalıdır", metin)
        self.assertIn("sağlıklı olduğu anlamına gelmez", metin)
        self.assertNotIn("izleme_durumu.json", sorted(p.name for p in config.DATA.iterdir()))   # panel yazmaz
        self.assertEqual([x for x in sorted(p.name for p in config.DATA.iterdir()) if x.startswith("izleme")], [])


if __name__ == "__main__":
    unittest.main()
