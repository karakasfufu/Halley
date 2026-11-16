"""FAZ 6 hız ölçümü (canlı veritabanının KOPYASINDA; ağ yok, yapay zekâ yok). Aynı iş yükü: bir akşam çalıştırmasında
aynı gün için rejimin hesaplandığı yerler — bekçi özeti (1), akşam raporu (1), her tahmin kaydı (defter.kaydet; k).
Önce (önbelleksiz) / sonra (önbellekli) süre ve sonuçların birebir aynılığı. Kullanım: python hiz_olcum.py <repo> <kopya.db> <cikti.json> [k=3] [tekrar=5]"""
import json
import sys
import time
from datetime import date
from pathlib import Path


def main():
    repo, kopya, cikti = sys.argv[1:4]
    k = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    tekrar = int(sys.argv[5]) if len(sys.argv) > 5 else 5
    sys.path.insert(0, repo)
    from bist_haber import db, regime
    c = db.connect(Path(kopya))
    gun = date.fromisoformat(c.execute("SELECT MAX(date) FROM prices").fetchone()[0])
    cagri = 2 + k
    def is_yuku(onbellek):
        regime._ONBELLEK.clear()
        t = time.perf_counter()
        sonuc = [regime.regime(c, gun, onbellek=onbellek) for _ in range(cagri)]
        return time.perf_counter() - t, sonuc
    once, sonra = [], []
    for _ in range(tekrar):
        a, ra = is_yuku(False)
        b, rb = is_yuku(True)
        once.append(a)
        sonra.append(b)
        assert all(x == ra[0] for x in ra + rb), "sonuçlar farklı"
    tek = []
    for _ in range(tekrar):
        regime._ONBELLEK.clear()
        t = time.perf_counter(); regime._anahtar(c, gun.isoformat()); tek.append(time.perf_counter() - t)
    out = {"gun": gun.isoformat(), "cagri_sayisi": cagri, "tekrar": tekrar,
           "once_ms_medyan": round(1000 * sorted(once)[tekrar // 2], 1), "sonra_ms_medyan": round(1000 * sorted(sonra)[tekrar // 2], 1),
           "anahtar_sorgusu_ms_medyan": round(1000 * sorted(tek)[tekrar // 2], 1),
           "sonuclar_birebir_ayni": True, "fiyat_satiri": c.execute("SELECT COUNT(*) FROM prices").fetchone()[0]}
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
