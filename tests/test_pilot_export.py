import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from bist_haber import backtest, pilot_export


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = backtest.connect(Path(self.temp.name) / "pilot.db")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.conn.close)
        for i in range(1, 5):
            self.conn.execute("INSERT INTO news(id,source,published_at,effective_date,title,subject,fetched_at) "
                              "VALUES(?,'kap','2026-09-01T12:00:00+03:00','2026-09-01',?,'Sözleşme','now')",
                              (f"kap:{i}", f'Örnek, "şirket" {i}'))
            self.conn.execute("INSERT INTO pilot_selection VALUES(?)", (f"kap:{i}",))
        for i in (1, 2):
            self.conn.execute("INSERT INTO pilot_documents VALUES(?,'hash','[]',200,'now')", (f"kap:{i}",))
        self.conn.execute("INSERT INTO pilot_documents VALUES('kap:3','hash',?,200,'now')",
                          (json.dumps(["PDF metni uzunluk sınırını aşıyor."], ensure_ascii=False),))
        backtest._meta(self.conn, "selection", {"start": "2026-09-01", "end": "2026-09-30", "selected": 4})
        self.conn.commit()

    def record(self, nid="kap:1", direction=1, missing=""):
        return {"bildirim": nid, "hisse": "TEST", "yön": direction, "vade": 5,
                "giriş": "2026-09-02", "çıkış": "2026-09-08", "getiri_%": 2.0,
                "net_getiri_%": 1.8, "endekse_göre_%": 0.8, "en_düşük_%": -1.0, "eksik": missing}

    def test_zip_contains_all_tables_and_methods_without_losing_turkish(self):
        rows = [self.record(), self.record("kap:2", -1)]
        report = pilot_export.build_report(self.conn, rows)
        packed = pilot_export.zip_bytes(report["files"])
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            self.assertEqual(set(archive.namelist()), {"halley_pilot.csv", "halley_pozitif_ozet.csv",
                                                       "halley_belge_eksikleri.csv", "halley_yontem.txt",
                                                       "halley_esik_ayari.txt", "halley_senaryo_testi.csv",
                                                       "halley_senaryo_testi.txt"})
            full = pd.read_csv(io.BytesIO(archive.read("halley_pilot.csv")), encoding="utf-8-sig")
            summary = pd.read_csv(io.BytesIO(archive.read("halley_pozitif_ozet.csv")), encoding="utf-8-sig")
            gaps = pd.read_csv(io.BytesIO(archive.read("halley_belge_eksikleri.csv")), encoding="utf-8-sig")
            methods = archive.read("halley_yontem.txt").decode("utf-8-sig")
        self.assertEqual(len(full), 2)
        self.assertEqual(summary.iloc[0]["olay_sayısı"], 1)
        self.assertAlmostEqual(summary.iloc[0]["ortalama_net_getiri"], 1.8)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps.iloc[0]["başlık"], 'Örnek, "şirket" 3')
        self.assertEqual(gaps.iloc[1]["eksikler"], "Belge henüz denetlenmedi.")
        self.assertIn("fiyat sonucu eksik satır: 0", methods)
        self.assertIn("Eksik veya denetlenmemiş belge: 2", methods)

    def test_positive_summary_excludes_negative_neutral_and_missing_outcomes(self):
        rows = [self.record(), self.record("kap:2", -1), self.record("kap:2", 0),
                self.record("kap:3", 1, "Fiyat eksik")]
        report = pilot_export.build_report(self.conn, rows)
        self.assertEqual(report["summary"].iloc[0]["olay_sayısı"], 1)
        self.assertEqual(len(report["frame"]), 4)

    def test_empty_report_still_downloads_csv_headers_and_method(self):
        report = pilot_export.build_report(self.conn, [])
        for filename in ("halley_pilot.csv", "halley_pozitif_ozet.csv"):
            frame = pd.read_csv(io.BytesIO(report["files"][filename]), encoding="utf-8-sig")
            self.assertEqual(len(frame), 0)
        self.assertIn("bildirim", report["frame"].columns)
        self.assertIn("vade", report["summary"].columns)

    def test_export_is_read_only_and_does_not_create_api_calls(self):
        before = self.conn.total_changes
        pilot_export.build_report(self.conn, [self.record()])
        self.assertEqual(self.conn.total_changes, before)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM pilot_calls").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
