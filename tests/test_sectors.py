"""D: sektör karşılaştırması ve portföy riski — KAP sektör listesi, elle hesaplanmış beklentiler."""
import hashlib
import json
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from bist_haber import db, sectors

END = date(2026, 11, 6)


def days(n):
    out, d = [], END
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return out[::-1]


class SectorFileTests(unittest.TestCase):
    def test_file_matches_recorded_hash_and_known_members(self):
        p = Path(sectors.__file__).with_name("sektorler.json")
        d = json.loads(p.read_text(encoding="utf-8"))
        rows = {}
        for key, ts in d["gruplar"].items():
            ana, alt = key.split("|", 1)
            for t in ts:
                rows[t] = (ana, alt)
        txt = "\n".join(f"{t}\t{a}\t{b}" for t, (a, b) in sorted(rows.items()))
        self.assertEqual(hashlib.sha256(txt.encode("utf-8")).hexdigest(), d["dogrulama_sha256"])   # dosya bozulmadı
        self.assertEqual(sectors.sector_of("AKBNK"), ("MALİ KURULUŞLAR", "BANKALAR"))
        self.assertEqual(sectors.sector_of("SOKM"), ("TOPTAN VE PERAKENDE TİCARET", "PERAKENDE TİCARET"))
        self.assertEqual(sectors.sector_of("KRDMD")[1], "ANA METAL SANAYİ")     # çok pay gruplu şirket
        self.assertIsNone(sectors.sector_of("TGB"))                            # 3 harfli borçlanma kodu yok


class CompareTests(unittest.TestCase):
    def setUp(self):
        sectors.clear_cache()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.conn.close)

    def put(self, t, closes, vol=1e6):
        for d, c in zip(days(len(closes)), closes):
            self.conn.execute("INSERT INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                              (t, d, c, c, c, c, vol))

    def test_rank_against_sub_sector_median(self):
        # bankalar: AKBNK son 5 günde +10%, diğerleri 0, +2, +4, +6 → ortanca +3; AKBNK 5 hisse içinde 1.
        flat = [100.0] * 25
        self.put("AKBNK", flat[:-5] + [102, 104, 106, 108, 110])
        for t, g in (("GARAN", 0), ("HALKB", 2), ("ISCTR", 4), ("YKBNK", 6)):
            self.put(t, flat[:-1] + [100 * (1 + g / 100)])
        self.put("TSKB", flat, vol=10)                    # sığ → gruba girmez
        self.conn.commit()
        c = sectors.compare(self.conn, "AKBNK", END)
        self.assertEqual((c["grup"], c["grup_hisse"]), ("BANKALAR", 4))
        self.assertAlmostEqual(c["hisse_5g"], 10.0)
        self.assertAlmostEqual(c["sektor_5g"], 3.0)
        self.assertEqual((c["sira_5g"], c["toplam_5g"]), (1, 5))
        self.assertIn("5 hisse içinde 1. sırada", sectors.compare_text(c))

    def test_falls_back_to_main_sector_when_sub_too_small(self):
        for t in ("TCELL", "TTKOM", "HURGZ", "IHGZT", "BIGTK"):
            self.put(t, [100.0] * 25)
        self.conn.commit()
        c = sectors.compare(self.conn, "TCELL", END)
        self.assertEqual((c["alt"], c["grup"], c["grup_hisse"]), ("TELEKOMÜNİKASYON", "BİLGİ VE İLETİŞİM", 4))
        self.assertIn("alt sektörde yeterli likit hisse yok", sectors.compare_text(c))

    def test_no_lookahead_and_unknown(self):
        self.put("AKBNK", [100.0] * 25)
        self.conn.execute("INSERT INTO prices(ticker,date,close,volume) VALUES('AKBNK','2026-11-09',500,1e6)")
        self.conn.commit()
        self.assertEqual(sectors.compare(self.conn, "AKBNK", END)["gun"], "2026-11-06")
        self.assertIn("listesinde yok", sectors.compare(self.conn, "XXXX", END)["yok"])

    def test_portfolio_concentration_and_correlation(self):
        import random
        random.seed(1)
        base = [100.0]
        for _ in range(70):
            base.append(base[-1] * (1 + random.uniform(-0.03, 0.03)))
        self.put("AKBNK", base)
        self.put("GARAN", [x * 1.5 for x in base])                       # aynı hareket → korelasyon 1
        other = [100.0]
        for _ in range(70):
            other.append(other[-1] * (1 + random.uniform(-0.03, 0.03)))
        self.put("THYAO", other)
        for t in ("AKBNK", "GARAN", "THYAO"):
            self.conn.execute("INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,senaryo,giris,sl,tp1,tp2,"
                              "gecerlilik) VALUES('x','2026-11-05',?,'otomatik','destek',10,9,11,12,5)", (t,))
        self.conn.commit()
        pf = sectors.portfolio(self.conn, END)
        self.assertEqual(pf["alt"]["BANKALAR"], ["AKBNK", "GARAN"])
        text = " ".join(pf["uyarilar"])
        self.assertIn("Aynı alt sektörde 2 işlem: BANKALAR", text)
        self.assertIn("Tek ana sektörde yoğunlaşma: MALİ KURULUŞLAR — 3 açık işlemden 2 tanesi (%67", text)
        self.assertIn("AKBNK ile GARAN son 60 günde birlikte hareket ediyor (korelasyon 1.00)", text)
        self.assertFalse(any("THYAO ile" in w or "ile THYAO" in w for w in pf["uyarilar"]))

    def test_day_sectors_median(self):
        for t, chg in (("AKBNK", 1), ("GARAN", 3), ("HALKB", 5)):
            self.put(t, [100.0] * 21 + [100 + chg])
        self.put("XU100", [1000.0] * 22, vol=0)
        self.conn.commit()
        ds = sectors.day_sectors(self.conn, END)
        mali = next(x for x in ds["sektorler"] if x["sektor"] == "MALİ KURULUŞLAR")
        self.assertEqual(mali["hisse"], 3)
        self.assertAlmostEqual(mali["degisim_%"], 3.0)


if __name__ == "__main__":
    unittest.main()
