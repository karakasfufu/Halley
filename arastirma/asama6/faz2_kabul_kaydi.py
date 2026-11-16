"""FAZ 2 KABUL KAYDI (16.11.2026): kabul edilen sürümün (commit 6d7f5d5) ana sonuçlarını sabitler.
ANA SONUÇ = emir altyapısına bağlı "önceden limit emir" modeli, kural s3, iki adet yöntemi (planlanan / azami giriş).
Teorik modeller (açılışı görüp) ve s2 koşuları ANA SONUÇ DEĞİLDİR; yalnız karşılaştırma için ayrı dosyalarda durur.
Stop altı alışlar: çıkış fiyatı VARSAYIMSALDIR (alış fiyatı; ek kayma genel kayma içinde) — çıktıda işaretli.
Kullanım: python faz2_kabul_kaydi.py <repo> <arastirma.db> <planlar.csv> <cikti_klasoru>"""
import csv
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ANA = {"onceden_limit_planlanan_s3": {"adet_temeli": "planlanan_giris", "kural": "s3", "emir_modeli": "onceden_limit"},
       "onceden_limit_azami_s3": {"adet_temeli": "azami_giris", "kural": "s3", "emir_modeli": "onceden_limit"}}

KISA = {"canli_ortak": "o", "yalniz_teknik": "t", "onceden_limit_planlanan_s3": "plan", "onceden_limit_azami_s3": "azami",
        "son_12_ay": "12a", "2024": "2024"}   # dosya adı: <evren>_<dönem>_<adet>_<tablo>.csv (Windows yol uzunluğu)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def main():
    repo, dbp, plan_csv, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    sys.path.insert(0, str(Path(__file__).parent))
    import portfoy as pf
    out = Path(cikti)
    out.mkdir(parents=True, exist_ok=True)
    git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout.strip()
    kayit = {"olusturuldu": datetime.now().isoformat(timespec="seconds"),
             "ad": "FAZ 2 kabul kaydı — teknik plan evreninin portföy backtesti (araştırma simülatörü)",
             "kabul": "Simülatör olarak kabul (kullanıcı, 16.11.2026). Strateji kârlılığı, emir uygulaması ya da canlıya "
                      "geçiş onayı DEĞİLDİR.",
             "sinif": "emir altyapısına bağlı (Midas açılış seansı limit emri, nakit blokesi, dolum fiyatı, kısmi dolum "
                      "doğrulanmadı)",
             "stop_alti_uyari": "Stop altı dolan alışlarda çıkış fiyatı varsayımsaldır (alış fiyatı); ek kayma belirsizdir.",
             "kod": {"commit": git("rev-parse", "HEAD"), "portfoy_py_sha256": sha(Path(__file__).parent / "portfoy.py"),
                     "journal_py_sha256": sha(Path(repo) / "bist_haber" / "journal.py"),
                     "izlenen_dosyalarda_degisiklik": bool(git("status", "--porcelain", "--untracked-files=no"))},
             "python": sys.version.split()[0], "ayar_varsayilan": pf.VARSAYILAN, "kosular": ANA,
             "veri": {"planlar_sha256": sha(plan_csv), "arastirma_db_boyut": Path(dbp).stat().st_size}, "sonuc": {}, "dosya_adlari": KISA}
    for evren in ("canli_ortak", "yalniz_teknik"):
        planlar = pf.plan_oku(plan_csv, evren)
        bars = pf.bar_oku(dbp, [p["ticker"] for p in planlar] + ["XU100"])
        takvim = pf.takvim_olustur(bars)
        son = takvim[-1]
        bas12 = (date.fromisoformat(son) - timedelta(days=365)).isoformat()
        donemler = {"son_12_ay": (min(d for d in takvim if d > bas12), son), "2024": ("2024-01-01", "2024-12-31")}
        kayit["veri"][evren] = {"plan_sayisi": len(planlar), "fiyat_son_gun": son, "donemler": donemler}
        for ad, (b, s) in donemler.items():
            for kosu, ayar in ANA.items():
                r = pf.simule(planlar, bars, takvim, b, s, ayar)
                kayit["sonuc"][f"{evren}/{ad}/{kosu}"] = dict(r["metrik"], stop_alti_varsayimsal_cikis=sum(
                    1 for t in r["islemler"] if t["acilis_sl_alti"]))
                for isim in ("egri", "islemler", "atlanan", "acik_son"):
                    satir = r[isim]
                    with open(out / f"{KISA[evren]}_{KISA[ad]}_{KISA[kosu]}_{isim}.csv", "w", newline="", encoding="utf-8") as f:
                        if satir:
                            w = csv.DictWriter(f, list(satir[0].keys()) + (["cikis_varsayimsal_stop_alti"]
                                                                           if isim == "islemler" else []))
                            w.writeheader()
                            for x in satir:
                                y = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                                     for k, v in x.items()}
                                if isim == "islemler":
                                    y["cikis_varsayimsal_stop_alti"] = bool(x["acilis_sl_alti"])
                                w.writerow(y)
                m = r["metrik"]
                print(evren, ad, kosu, m["toplam_getiri_%"], m["azami_dusus_%"], m["kar_faktoru"], flush=True)
    (out / "kayit.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
