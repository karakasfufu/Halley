"""Aylık yeniden eğitim (2026-11-15): tp1 modelini yeni fiyatlarla güncel tutar. Yapay zekâ yok, 0 $.

Adımlar (her biri ayrıca seçilebilir; hepsi araştırma veritabanında, canlı veritabanına YAZMAZ):
  1. --fiyat   : araştırma veritabanına son 3 ayın fiyatları (Yahoo, ücretsiz; mevcut günler güncellenir)
  2. --etiket  : etiketle.py ile tüm geçmiş yeniden etiketlenir (~25 dk, 4 çekirdek)
  3. (her zaman) sınama ve kapı:
     a. ileriye dönük sınama: son 12 ay öncesiyle eğitilen aday, son 12 ayda (45 gün ambargo) — isabet (AUC), olasılık
        doğruluğu (Brier, sabit orana göre), en yüksek %20'nin R'si;
     b. eski (etkin) model, kendi eğitim bitişinden SONRAKİ planlarda (onun için hiç görülmemiş veri) aynı ölçülerle.
     KAPI: aday sınamada AUC ≥ 0,55 VE Brier sabit orandan iyi VE (eski modelin görmediği ≥300 plan varsa) adayın o
     planlardaki AUC'si eskisinden en fazla 0,02 düşük. Geçmezse dosya YAZILMAZ, eski model kalır.
  4. kapı geçerse aday TÜM veriyle eğitilip modeller/tp1_vYYYYMMDD.json olarak yazılır. --etkinlestir verilirse
     modeller/aktif.txt bu dosyayı gösterir (canlı Halley bir sonraki açılışta onu kullanır); verilmezse yalnız aday
     dosya oluşur. Eski dosyalar silinmez (geri dönmek için aktif.txt'yi eski adla değiştirmek yeterli).
Kullanım: python yeniden_egit.py <repo> <arastirma.db> <calisma_klasoru> [--fiyat] [--etiket] [--etkinlestir]
          [--hisse N]  (N: deneme için ilk N hisse)
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
repo, dbp, work = sys.argv[1], sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, repo)
sys.path.insert(0, str(HERE))
import egit  # noqa: E402
import model as old  # noqa: E402
from bist_haber import db as hdb, prices, tp1_model  # noqa: E402

MIN_AUC, MAX_DROP, MIN_NEW = 0.55, 0.02, 300
work.mkdir(parents=True, exist_ok=True)
args = sys.argv[4:]
n_tk = int(args[args.index("--hisse") + 1]) if "--hisse" in args else None
log = {"tarih": date.today().isoformat(), "adimlar": []}


def say(*a):
    print(*a, flush=True)


# 1. fiyat
if "--fiyat" in args:
    conn = hdb.connect(Path(dbp))
    tks = [r[0] for r in conn.execute("SELECT DISTINCT ticker FROM prices")]
    rows = 0
    for i in range(0, len(tks), 50):
        try:
            rows += prices.update(conn, tks[i:i + 50], period="3mo")
        except Exception as e:  # bir parti başarısızsa diğerleri sürsün
            say("fiyat partisi başarısız:", e)
    last = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    conn.close()
    log["adimlar"].append({"fiyat": rows, "son_gun": last})
    say("fiyat:", rows, "satır, son gün", last)

# 2. etiket
etiket = work / "etiket.csv"
if "--etiket" in args or not etiket.exists():
    cmd = [sys.executable, str(HERE / "etiketle.py"), repo, dbp, str(etiket)] + ([str(n_tk)] if n_tk else [])
    say("etiketleme:", " ".join(cmd[-3:]))
    subprocess.run(cmd, check=True)
    log["adimlar"].append({"etiket": str(etiket)})

# 3. sınama ve kapı
df = egit.load_df(str(etiket))
last = df.tarih.max()
t12 = (pd.Timestamp(last) - pd.DateOffset(months=12)).date().isoformat()
emb = (pd.Timestamp(t12) - pd.Timedelta(days=old.EMBARGO_DAYS)).date().isoformat()
tr, te = df[df.tarih < emb], df[df.tarih >= t12]
cand = egit.fit_e2(tr)
p = egit.predict_e2(cand, te)
y = te.y.values
base = np.full(len(te), tr.y.mean())
wf = {"egitim_n": int(len(tr)), "test_n": int(len(te)), "AUC": round(old.auc(y, p), 4),
      "Brier_beceri_%": round(100 * (1 - old.brier(y, p) / old.brier(y, base)), 2),
      "ust_%20_R": old.econ(te, p)["ust_%20_ort_R"], "tum_R": round(float(te.r.mean()), 3)}
say("ileriye dönük sınama (son 12 ay):", wf)
cur_name = tp1_model.active_name()
cur = tp1_model.load(cur_name)
cmp_ = {"etkin_model": cur_name}
gate = wf["AUC"] >= MIN_AUC and wf["Brier_beceri_%"] > 0
if cur:
    new = df[df.tarih > cur["egitim"]["son"]]
    cmp_["eskinin_gormedigi_plan"] = int(len(new))
    if len(new) >= MIN_NEW and new.y.nunique() == 2:
        po = np.array([tp1_model.predict({k: (None if pd.isna(v) else float(v)) for k, v in r.items()}, cur)
                       for r in new[egit.FEATS].to_dict("records")])
        emb2 = (pd.Timestamp(cur["egitim"]["son"]) - pd.Timedelta(days=old.EMBARGO_DAYS)).date().isoformat()
        pc = egit.predict_e2(egit.fit_e2(df[df.tarih < emb2]), new)
        cmp_.update(eski_AUC=round(old.auc(new.y.values, po), 4), aday_AUC=round(old.auc(new.y.values, pc), 4))
        gate = gate and cmp_["aday_AUC"] >= cmp_["eski_AUC"] - MAX_DROP
    else:
        cmp_["not"] = f"eskinin görmediği plan {len(new)} (< {MIN_NEW}): karşılaştırma yapılmadı, yalnız sınama kapısı"
say("eski model karşılaştırması:", cmp_)
log.update(sinama=wf, karsilastirma=cmp_, kapi=bool(gate))
if not gate:
    say("KAPI GEÇİLMEDİ: yeni model yazılmadı; etkin model değişmedi:", cur_name)
else:
    name = f"tp1_v{date.today().strftime('%Y%m%d')}.json"
    path = Path(repo) / "bist_haber" / "modeller" / name
    doc, _ = egit.export(egit.fit_e2(df), df, path, {"ileriye_donuk_son12": wf, "karsilastirma": cmp_})
    doc["surum"] = name[:-5]
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log["yazilan"] = str(path)
    say("yazıldı:", path)
    if "--etkinlestir" in args:
        (path.parent / "aktif.txt").write_text(name, encoding="utf-8")
        log["etkin"] = name
        say("etkin model artık:", name)
    else:
        say("etkinleştirilmedi (aday). Etkinleştirmek için --etkinlestir ile çalıştırın ya da modeller/aktif.txt'ye",
            name, "yazın.")
(work / f"yeniden_egit_{date.today().isoformat()}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1,
                                                                             default=str), encoding="utf-8")
