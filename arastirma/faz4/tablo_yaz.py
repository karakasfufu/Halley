"""rejim_sonuclari.json → Markdown tablolar (rapor eki için; elle kopyalama hatası olmasın)."""
import json
import sys
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
TR = {"kirilim_teyitli": "kırılım", "geri_cekilme": "geri çekilme", "destek_teyitli": "destekten tepki"}


def ci(v, k, yuzde=False):
    x = v.get(k)
    if not x:
        return "—"
    return f"{x[0]:.1f}…{x[1]:.1f}" if yuzde else f"{x[0]:+.2f}…{x[1]:+.2f}"


def tablo(gr, baslik):
    s = [f"**{baslik}**", "", "| Grup | n | gün | TP1 % (%95) | kazanma % (%95) | ort. net % | ort. R (%95) | aynı hisse 10 gün içinde % | "
         "sıçrama gösterge/tutma % | durum |", "|---|---|---|---|---|---|---|---|---|---|"]
    for g, v in gr.items():
        if not v["n"]:
            continue
        ad = " · ".join(TR.get(x, x) for x in g.split(" | "))
        dur = "**YETERSİZ**" if v["yetersiz"] else v["guven"]
        s.append(f"| {ad} | {v['n']} | {v['gun']} | {v.get('tp1_%')} ({ci(v, 'ga95_tp1_%', True)}) | {v.get('kazanma_%')} "
                 f"({ci(v, 'ga95_kazanma_%', True)}) | {v.get('ort_net_%')} | {v.get('ort_R')} ({ci(v, 'ga95_ort_R')}) | "
                 f"{v.get('ayni_hisse_tekrar_%')} | {v.get('veri_gosterge_sicrama_%')} / {v.get('veri_tutma_sicrama_%')} | {dur} |")
    return "\n".join(s) + "\n"


out = [tablo(d["donemler"]["tumu"]["ana"], "Ana gruplar — tüm dönem (2022-11 … 2026-11-13): strateji × trend × oynaklık"),
       tablo(d["donemler"]["tumu"]["tur"], "Strateji türü — tüm dönem"),
       tablo(d["donemler"]["tumu"]["rejim"], "Rejim (türler birleşik) — tüm dönem")]
for p, ad in (("2022_son", "2022 son (11–12. ay)"), ("2023", "2023"), ("2024", "2024 (FAZ 2'de incelendi)"),
              ("2025_ilk", "2025-01-01 … 2025-11-13"), ("son_12_ay", "son 12 ay 2025-11-14 … 2026-11-13 (FAZ 2'de incelendi)")):
    out.append(tablo(d["donemler"][p]["tur_trend"], f"{ad}: strateji × trend"))
Path(sys.argv[2]).write_text("\n".join(out), encoding="utf-8")
print("ok")
