"""FAZ 3 Ek I2 (araştırma; MODEL EĞİTMEZ): etkin model tp1_v1 SABİT; aynı örnekler ve girdiler, eski ve düzeltilmiş
sonuç etiketleri ile metriklerin yeniden hesabı + model–etiket bağlantısının sayım kontrolü.

ÖNEMLİ: tp1_v1, egit.py export() ile kapanmış TÜM veriyle (2022-11-09 … 2026-11-12) uydurulmuştur. Bu yüzden bu
veride tp1_v1 ile hesaplanan her metrik EĞİTİM İÇİDİR (dönem dışı DEĞİLDİR). tp1_v1.json'daki dönem dışı sınama
sonuçları, test döneminden önceki verilerle ayrı uydurulan kat modellerinden gelir; o kat modelleri ve tahminleri
SAKLANMAMIŞTIR → dönem dışı metriği düzeltilmiş etiketle yeniden hesaplamak, kat modellerini yeniden uydurmayı
(eğitimi) gerektirir; YAPILMADI.

Model–etiket bağlantısı: tp1_v1.json "tablo.sayi" (grup başına eğitim örneği sayısı) ve "tablo.ham" (grup TP1 oranı)
eğitim verisinden SAYIM ile üretilmiştir; aday etiket dosyası egit.load_df süzgeciyle aynı sayıları veriyorsa bağlantı
güçlenir (kesin kanıt değildir: aynı sayıları veren başka dosya olabilir).
Kullanım: python yeniden_degerlendirme.py <repo> <etiket_klasoru> <planlar_seviyeli.csv> <cikti.json>"""
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

KAPANAN = {"SL", "TP2", "başabaş (TP1 sonrası)", "süre doldu"}


def f_(v):
    if v in (None, "", "nan", "NaN", "None"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def suz(rows):
    """egit.load_df ile aynı süzgeç (sonuç kapanmış, risk ≠ yüksek, stop ≥ %1, x_trend dolu)."""
    return [r for r in rows if r["sonuc"] in KAPANAN and r["risk"] != "yüksek" and (f_(r["stop_%"]) or 0) >= 1
            and f_(r.get("x_trend")) is not None]


def auc(y, p):
    pos = [q for q, t in zip(p, y) if t == 1]
    neg = [q for q, t in zip(p, y) if t == 0]
    if not pos or not neg:
        return None
    s = sorted((q, i) for i, q in enumerate(p))
    rank, i = [0.0] * len(p), 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1][0] == s[i][0]:
            j += 1
        for k in range(i, j + 1):
            rank[s[k][1]] = (i + j) / 2 + 1
        i = j + 1
    rp = sum(rank[i] for i, t in enumerate(y) if t == 1)
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def brier(y, p):
    return sum((q - t) ** 2 for q, t in zip(p, y)) / len(y)


def main():
    repo, edir, plan_csv, cikti = sys.argv[1:5]
    sys.path.insert(0, repo)
    from bist_haber import tp1_model
    m = tp1_model.load("tp1_v1.json")
    out = {"not": __doc__.split("\n\n")[1].replace("\n", " "), "model": "tp1_v1.json (sabit)", "etiket_kontrolu": {}}
    tb = m["tablo"]
    for ad in ("etiket.csv", "etiket2.csv", "etiket3.csv"):
        rows = suz(list(csv.DictReader(open(Path(edir) / ad, encoding="utf-8"))))
        if not rows or "trend_yuk" not in rows[0]:
            out["etiket_kontrolu"][ad] = {"suzulmus": len(rows), "tablo_karsilastirma": "girdi sütunları yok (tablo "
                                                                                       "anahtarı kurulamaz)"}
            continue
        say, pozitif = Counter(), Counter()
        for r in rows:
            f = {k: f_(v) for k, v in r.items()}
            k = tp1_model._table_key(f, tb)
            say[k] += 1
            pozitif[k] += int(float(r["y"]) == 1)
        ayni_sayi = all(int(tb["sayi"].get(k, 0)) == v for k, v in say.items()) and \
            all(say.get(k, 0) == int(v) for k, v in tb["sayi"].items())
        ham_fark = max((abs(pozitif[k] / say[k] - tb["ham"][k]) for k in say if k in tb["ham"]), default=None)
        out["etiket_kontrolu"][ad] = {"suzulmus": len(rows), "model_plan_sayisi": m["egitim"]["plan"],
                                      "grup_sayilari_birebir": ayni_sayi, "grup_tp1_orani_en_buyuk_fark": ham_fark,
                                      "tp1_%": round(100 * sum(float(r["y"]) == 1 for r in rows) / len(rows), 2)}
    # yeniden değerlendirme: etiket2 örnekleri ve girdileri (eğitimle eşleşen), eski y ↔ düzeltilmiş y
    e2 = {(r["ticker"], r["tarih"]): r for r in suz(list(csv.DictReader(open(Path(edir) / "etiket2.csv", encoding="utf-8"))))}
    yeni = {(r["ticker"], r["tarih"]): r for r in csv.DictReader(open(plan_csv, encoding="utf-8"))}
    ortak = [k for k in e2 if k in yeni]
    p_, y_eski, y_yeni, girdi_fark, s3_girissiz = [], [], [], 0, []
    for k in ortak:
        r, n = e2[k], yeni[k]
        f = {kk: f_(v) for kk, v in r.items()}
        p_.append(tp1_model.predict(f, m))
        y_eski.append(int(float(r["y"])))
        yy = n["y"]
        y_yeni.append(int(float(yy)) if yy not in ("", None) else None)
        if any(abs((f_(r[c]) or 0) - (f_(n[c]) or 0)) > 1e-4 for c in ("rr1", "stop_%", "rsi", "atr_%", "perf20")):
            girdi_fark += 1
        acilis = f_(n["kapanis"]) * (1 + f_(n["acilis_bosluk_%"]) / 100) if f_(n["acilis_bosluk_%"]) is not None else None
        s3_girissiz.append(acilis is not None and acilis <= f_(n["sl"]) * (1 + 1e-4))
    deg = [i for i in range(len(ortak)) if y_yeni[i] is not None and y_yeni[i] != y_eski[i]]
    gecerli = [i for i in range(len(ortak)) if y_yeni[i] is not None]
    s3 = [i for i in gecerli if not s3_girissiz[i]]
    met = lambda idx, y: {"n": len(idx), "AUC": round(auc([y[i] for i in idx], [p_[i] for i in idx]), 4),
                          "Brier": round(brier([y[i] for i in idx], [p_[i] for i in idx]), 5),
                          "tp1_%": round(100 * sum(y[i] for i in idx) / len(idx), 2)}
    out["yeniden_degerlendirme_EGITIM_ICI"] = {
        "etiket2_suzulmus": len(e2), "yeni_etiketle_eslesen": len(ortak), "eslesmeyen": len(e2) - len(ortak),
        "girdisi_farkli_eslesen": girdi_fark, "yeni_etikette_kapanmamis": len(ortak) - len(gecerli),
        "etiketi_degisen": len(deg), "degisim_yonu": dict(Counter(f"{y_eski[i]}→{y_yeni[i]}" for i in deg)),
        "A_eski_etiket": met(gecerli, y_eski), "B_duzeltilmis_etiket_tp1_hedefi": met(gecerli, y_yeni),
        "C_duzeltilmis_ve_s3_stop_alti_girissiz_cikarilmis": met(s3, y_yeni),
        "s3_ile_cikan": len(gecerli) - len(s3)}
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
