"""FAZ 3: fiyat_izi_v1 göçünün CANLI VERİTABANI KOPYASINDA provası. Canlı dosya yalnız okunur (sqlite backup ile
kopyalanır). Adımlar: kopya → bütünlük → tablo sayıları/özetleri → göç (otomatik yedekli) → bütünlük → bütün eski
tabloların satır özetleri aynı mı → bugünkü db.connect açıyor mu → eski yazma ifadesi çalışıyor mu → yeni yazıcıyla
sahte bir indirme → önceki durum geri kuruluyor mu → geri dönüş (yedeği geri yükleme) birebir mi.
Kullanım: python kopyada_goc.py <repo> <canli.db> <calisma_klasoru> <cikti.json>"""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path


def tablo_ozetleri(c):
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                          "AND name NOT IN ('fiyat_indirme','fiyat_eski','veri_anlik') ORDER BY name"):
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})") if r[1] != "indirme_id"]
        h = hashlib.sha256()
        n = 0
        for row in c.execute(f"SELECT {','.join(cols)} FROM {t} ORDER BY {','.join(cols)}"):
            h.update(repr(tuple(row)).encode())
            n += 1
        out[t] = (n, h.hexdigest()[:16])
    return out


def main():
    repo, canli, klasor, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    from bist_haber import db, fiyat_izi as fz
    k = Path(klasor)
    if k.exists():
        shutil.rmtree(k)
    k.mkdir(parents=True)
    kopya = k / "bist_haber.db"
    src = sqlite3.connect(f"file:{canli}?mode=ro", uri=True)
    dst = sqlite3.connect(kopya)
    src.backup(dst)
    src.close()
    r = {"canli_dosya": canli, "kopya": str(kopya)}
    r["kopya_butunluk"] = dst.execute("PRAGMA integrity_check").fetchone()[0]
    once = tablo_ozetleri(dst)
    r["tablo_sayisi"] = len(once)
    fiyat_once = fz.veri_ozeti(dst)
    g = fz.migrate(dst, kopya)
    r["goc"] = g
    r["goc_sonrasi_butunluk"] = dst.execute("PRAGMA integrity_check").fetchone()[0]
    sonra = tablo_ozetleri(dst)
    r["eski_tablolar_ayni"] = once == sonra
    r["fiyat_ozeti_ayni"] = fz.veri_ozeti(dst) == fiyat_once
    r["indirme_id_dolu_satir"] = dst.execute("SELECT COUNT(*) FROM prices WHERE indirme_id IS NOT NULL").fetchone()[0]
    dst.close()
    c2 = db.connect(kopya)                                   # bugünkü uygulama bağlantısı (şema ekleri dahil)
    r["db_connect_acti"] = True
    tk, gun = c2.execute("SELECT ticker, MAX(date) FROM prices WHERE ticker='THYAO'").fetchone()
    eski = c2.execute("SELECT ticker,date,open,high,low,close,volume FROM prices WHERE ticker=? ORDER BY date DESC "
                      "LIMIT 3", (tk,)).fetchall()
    once_durum = {(x[0], x[1]): tuple(x[2:7]) for x in c2.execute(
        "SELECT ticker,date,open,high,low,close,volume FROM prices")}
    sahte = [(x[0], x[1], x[2], x[3], x[4], round(x[5] * 0.99, 4), x[6]) for x in eski] + \
            [(tk, "2099-01-01", 1.0, 1.0, 1.0, 1.0, 1.0)]
    iid = fz.yaz(c2, sahte, "deneme", {"period": "1y", "auto_adjust": True}, "sahte düzeltme (prova)", None, "prova")
    kay = c2.execute("SELECT satir_sayisi, degisen_satir FROM fiyat_indirme WHERE id=?", (iid,)).fetchone()
    r["sahte_indirme"] = {"id": iid, "satir": kay[0], "degisen": kay[1],
                          "fiyat_eski_satir": c2.execute("SELECT COUNT(*) FROM fiyat_eski").fetchone()[0]}
    geri = {kk: v[:5] for kk, v in fz.durum_once(c2, iid).items()}
    r["onceki_durum_birebir"] = geri == once_durum
    c2.execute("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
               (tk, "2099-01-02", 1, 1, 1, 1, 1))            # prices.update'in bugünkü ifadesi
    r["eski_yazma_ifadesi_calisti"] = True
    c2.close()
    # geri dönüş: göç yedeğini geri yükle (prova: göçten sonra gerçek kullanıcı verisi yok)
    geri_dosya = k / "geri_donus.db"
    shutil.copyfile(g["yedek"], geri_dosya)
    c3 = sqlite3.connect(geri_dosya)
    r["geri_donus_butunluk"] = c3.execute("PRAGMA integrity_check").fetchone()[0]
    r["geri_donus_tablolar_once_ile_ayni"] = tablo_ozetleri(c3) == once
    r["geri_donusta_yeni_tablo_yok"] = c3.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name IN ('fiyat_indirme','fiyat_eski','veri_anlik')").fetchone()[0] == 0
    c3.close()
    r["tamam"] = all(r[x] in (True, "ok") for x in ("kopya_butunluk", "goc_sonrasi_butunluk", "eski_tablolar_ayni",
                                                    "fiyat_ozeti_ayni", "onceki_durum_birebir", "geri_donus_butunluk",
                                                    "geri_donus_tablolar_once_ile_ayni", "geri_donusta_yeni_tablo_yok"))
    Path(cikti).write_text(json.dumps(r, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
