"""O2 kopya provası. Canlı (W) SALT-OKUR: kod klasörleri kopyalanır, veritabanı yedekleme API'siyle kopyalanır.
A = canlı kod (o3-canli), B = A + O2 dosyaları, C = B'de çalıştır → eski koda geri dön → eski kodla çalıştır.
Karşılaştırma: A ile B aynı işlemlerden sonra hangi satırlarda ayrılıyor; değiştirilemez tablolar birebir mi."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

W, K, P = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
O2 = ["app.py", "bist_haber/defter.py", "bist_haber/journal.py", "bist_haber/ready.py", "bist_haber/tracker.py",
      "arastirma/asama6/portfoy.py", "tests/test_defter.py", "tests/test_faz1_dogrulama.py", "tests/test_kural_s3.py",
      "tests/test_o2_s3.py"]
KOD = ["app.py", "bist_haber", "tests", "arastirma", ".streamlit"]
PY = Path.home() / ".venvs" / "bist-haber" / "Scripts" / "python.exe"
ISLEM = Path(__file__).with_name("o2_islem.py")
DEGISMEZ = ("tahmin", "tahmin_sonuc", "tahmin_degerlendirme", "defter_olay")


def kopya(ad):
    d = P / ad
    if d.exists():
        shutil.rmtree(d)
    (d / "data").mkdir(parents=True)
    for k in KOD:
        s = W / k
        (shutil.copytree(s, d / k, ignore=shutil.ignore_patterns("__pycache__")) if s.is_dir() else shutil.copy2(s, d / k))
    shutil.copy2(W / "data" / "ayarlar.json", d / "data" / "ayarlar.json")
    src = sqlite3.connect(f"file:{(W / 'data' / 'bist_haber.db').as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(d / "data" / "bist_haber.db"))
    src.backup(dst)
    dst.close()
    src.close()
    return d


def o2_uygula(d):
    for f in O2:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(K / f, d / f)


def geri(d, a):
    for f in O2:
        if (a / f).exists():
            shutil.copy2(a / f, d / f)
        elif (d / f).exists():
            (d / f).unlink()


def calistir(d, *ek):
    r = subprocess.run([str(PY), str(ISLEM), str(d), *ek], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(d))
    if r.returncode:
        raise SystemExit(f"{d.name}: {r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def tablo_ozet(db):
    c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        h = hashlib.sha256()
        n = 0
        for r in c.execute(f'SELECT * FROM "{t}" ORDER BY rowid'):
            h.update(repr(tuple(r)).encode("utf-8"))
            n += 1
        out[t] = [n, h.hexdigest()[:16]]
    out["_integrity"] = c.execute("PRAGMA integrity_check").fetchone()[0]
    out["_tetikleyici"] = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0]
    c.close()
    return out


def satir_farki(dba, dbb, tablo, anahtar="id", yok_say=("guncellendi",)):
    a = sqlite3.connect(f"file:{Path(dba).as_posix()}?mode=ro", uri=True)
    a.row_factory = sqlite3.Row
    b = sqlite3.connect(f"file:{Path(dbb).as_posix()}?mode=ro", uri=True)
    b.row_factory = sqlite3.Row
    ra = {r[anahtar]: dict(r) for r in a.execute(f"SELECT * FROM {tablo}")}
    rb = {r[anahtar]: dict(r) for r in b.execute(f"SELECT * FROM {tablo}")}
    fark = []
    for k in sorted(set(ra) | set(rb), key=str):
        x, y = ra.get(k), rb.get(k)
        if x is None or y is None:
            fark.append({"id": k, "yalniz": "A" if y is None else "B"})
            continue
        alan = {}
        for c in x:
            if c in yok_say or x[c] == y[c]:
                continue
            if c == "sonuc_json":
                ja, jb = json.loads(x[c] or "{}"), json.loads(y[c] or "{}")
                alan[c] = {kk: (ja.get(kk), jb.get(kk)) for kk in set(ja) | set(jb) if ja.get(kk) != jb.get(kk)}
            else:
                alan[c] = (x[c], y[c])
        if alan:
            fark.append({"id": k, **({"ticker": x.get("ticker"), "durum": x.get("durum")}), "fark": alan})
    return fark


P.mkdir(parents=True, exist_ok=True)
a, b, c = kopya("A"), kopya("B"), kopya("C")
o2_uygula(b)
o2_uygula(c)
once = tablo_ozet(a / "data" / "bist_haber.db")
rapor = {"once": {t: once[t] for t in DEGISMEZ + ("hazir_firsat", "trade_journal", "takip_senaryo") if t in once}}
rapor["A_eski_kod"] = calistir(a)
rapor["B_o2_kod"] = calistir(b)
sa, sb = tablo_ozet(a / "data" / "bist_haber.db"), tablo_ozet(b / "data" / "bist_haber.db")
rapor["degismez_tablolar_A_eq_B"] = {t: sa.get(t) == sb.get(t) for t in DEGISMEZ}
rapor["degismez_tablolar_once_eq_B"] = {t: once.get(t) == sb.get(t) for t in DEGISMEZ}
rapor["A_B_farkli_tablolar"] = [t for t in sa if not t.startswith("_") and sa[t] != sb.get(t)]
rapor["fark_hazir_firsat"] = satir_farki(a / "data" / "bist_haber.db", b / "data" / "bist_haber.db", "hazir_firsat")
rapor["fark_trade_journal"] = satir_farki(a / "data" / "bist_haber.db", b / "data" / "bist_haber.db", "trade_journal")
rapor["B_integrity"], rapor["B_tetikleyici"] = sb["_integrity"], sb["_tetikleyici"]
# geri dönüş provası (C): O2 ile çalıştır → eski kod → eski kodla tekrar çalıştır
rapor["C_o2"] = calistir(c)
geri(c, a)
rapor["C_geri_dosyalar_eski_ile_ayni"] = all(
    (c / f).read_bytes() == (a / f).read_bytes() if (a / f).exists() else not (c / f).exists() for f in O2)
rapor["C_eski_kod_sonra"] = calistir(c)
sc = tablo_ozet(c / "data" / "bist_haber.db")
rapor["C_degismez_tablolar_once_eq"] = {t: once.get(t) == sc.get(t) for t in DEGISMEZ}
rapor["C_integrity"] = sc["_integrity"]
# geri dönüş sınırı: s3 sözleşmeli tahmin varken eski koda dönülürse
d = kopya("D")
o2_uygula(d)
rapor["D_o2_s3_tahmin"] = calistir(d, "s3_tahmin_ekle")
dd = sqlite3.connect(str(d / "data" / "bist_haber.db"))
rapor["D_o2_sonuc"] = dd.execute("SELECT t.kural_surum, s.kural_surum, s.sonuc_turu, s.neden FROM tahmin t LEFT JOIN "
                                 "tahmin_sonuc s ON s.tahmin_id=t.id WHERE t.plan_imzasi='prova_s3'").fetchall()
dd.close()
e = kopya("E")
o2_uygula(e)
sqlite3.connect(str(e / "data" / "bist_haber.db")).close()
r1 = subprocess.run([str(PY), "-c", "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);"
                     "c.execute(\"INSERT INTO tahmin(plan_imzasi,ticker,signal_day,giris_gunu,tahmin_zamani,model_surum,"
                     "ozellik_surum,parametre_surum,olasilik,bant,tur,giris,azami_giris,sl,tp1,tp2,gecerlilik_gun,kural_surum,"
                     "komisyon_pct,kayma_pct,maliyet_protokol) SELECT 'prova_s3',ticker,signal_day,giris_gunu,tahmin_zamani,"
                     "model_surum,ozellik_surum,parametre_surum,olasilik,bant,tur,giris,163.5,163.51,tp1,tp2,gecerlilik_gun,"
                     "'s3',komisyon_pct,kayma_pct,maliyet_protokol FROM tahmin WHERE id=1\");c.commit()",
                     str(e / "data" / "bist_haber.db")], capture_output=True, text=True)
geri(e, a)
rapor["E_eski_kod_s3_tahminle"] = calistir(e)
ee = sqlite3.connect(str(e / "data" / "bist_haber.db"))
rapor["E_eski_kod_sonuc"] = ee.execute("SELECT t.kural_surum, s.kural_surum, s.sonuc_turu, s.neden FROM tahmin t LEFT JOIN "
                                       "tahmin_sonuc s ON s.tahmin_id=t.id WHERE t.plan_imzasi='prova_s3'").fetchall()
ee.close()
f = kopya("F")
o2_uygula(f)
ay = json.loads((f / "data" / "ayarlar.json").read_text(encoding="utf-8-sig"))
ay["gerceklesme_kurali"] = "s2"
(f / "data" / "ayarlar.json").write_text(json.dumps(ay, ensure_ascii=False), encoding="utf-8")
rapor["F_o2_geri_donus_ayari_s3_tahminle"] = calistir(f, "s3_tahmin_ekle")
ff = sqlite3.connect(str(f / "data" / "bist_haber.db"))
rapor["F_sonuc"] = ff.execute("SELECT t.kural_surum, s.kural_surum, s.sonuc_turu, s.neden FROM tahmin t LEFT JOIN "
                              "tahmin_sonuc s ON s.tahmin_id=t.id WHERE t.plan_imzasi='prova_s3'").fetchall()
rapor["F_gunluk_bekliyor_kural"] = sorted({(json.loads(r[0] or "{}").get("kural")) for r in ff.execute(
    "SELECT sonuc_json FROM trade_journal WHERE durum='bekliyor'")}, key=str)
ff.close()
(P / "o2_prova.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(rapor, ensure_ascii=False, indent=1, default=str))
