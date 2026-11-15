"""2026-11-15: Hisse Analizi HTML indirme — kaydedici ve markdown çevirisi."""
import unittest

import pandas as pd

from bist_haber import html_export as hx


class HtmlExport(unittest.TestCase):
    def test_markdown_subset(self):
        h = hx.md_to_html("**En uygun:** Kırılım \* not\n- **Teyit:** hacim\n- Geçersiz <b>x</b>")
        self.assertEqual(h, "<p><b>En uygun:</b> Kırılım * not</p><ul><li><b>Teyit:</b> hacim</li>"
                            "<li>Geçersiz &lt;b&gt;x&lt;/b&gt;</li></ul>")              # html izni yoksa kaçırılır
        self.assertIn("<span class='x'>", hx.md_to_html("a <span class='x'>b</span>", allow_html=True))

    def test_recorder_and_capture_restore(self):
        ns = {"st": "gercek", "DARK": True}
        seen = {}

        def draw():
            st = ns["st"]
            seen["dark"] = ns["DARK"]
            st.markdown("**Başlık**")
            c1, c2 = st.columns(2)
            c1.metric("Giriş", "10,00 TL", "+1,0%")
            c2.caption("not")
            with st.container(border=True):
                st.dataframe(pd.DataFrame([{"A": 1, "B": None}]))
            st.warning("dikkat")
            self.assertEqual(st.radio("Dönem", ["3 ay", "6 ay"], index=1), "6 ay")
            self.assertFalse(st.button("x"))
            st.bilinmeyen_cagri(1)                                   # bilinmeyen çağrı dosyayı bozmaz

        body = hx.capture(ns, draw, DARK=False)
        self.assertEqual(ns, {"st": "gercek", "DARK": True})        # her şey geri kondu
        self.assertFalse(seen["dark"])
        for want in ("<b>Başlık</b>", "<div class='row'>", "10,00 TL", "+1,0%", "<table", "—", "dikkat"):
            self.assertIn(want, body)
        self.assertLess(body.index("10,00 TL"), body.index("not"))
        with self.assertRaises(ZeroDivisionError):                   # hata olsa da geri konur
            hx.capture(ns, lambda: 1 / 0, DARK=False)
        self.assertEqual(ns, {"st": "gercek", "DARK": True})

    def test_page_wrapper(self):
        doc = hx.page("POS · A", "alt", "<p>gövde</p>", "dipnot <x>")
        self.assertTrue(doc.startswith("<!DOCTYPE html><html lang='tr'>"))
        self.assertIn("<meta charset='utf-8'>", doc)
        self.assertIn("dipnot &lt;x&gt;", doc)


if __name__ == "__main__":
    unittest.main()
