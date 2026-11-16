"""FAZ 6 (16.11.2026) — model izleme uyarıları. HAZIRLIK: bekçiye bağlı değil; yalnız yerel kayıt ve panel.
Ön kayıt: arastirma/faz6/izleme_tanimi.json (eşikler, pencereler, asgari örnek, teyit, bastırma). Yapay zekâ yok.

Dört durum AYRI değerlendirilir:
  P1 ayırt etme (AUC), P2 sabit eğitim oranına göre Brier becerisi, K1 kalibrasyon   → 'uyari' türü
  R1 piyasa rejimi, G1 girdi dağılımı (PSI)                                           → 'bilgi' türü (tek başına
      "model başarısız" anlamına GELMEZ)
Ölçüm yalnız defter.olculen_kayitlar (ozet ile aynı seçim) ve sözleşmesi tam (kural + maliyet) gruplarla yapılır.
Geçmiş backteste göre bozulma ÖLÇÜLMEZ (tp1_v1 bütün veriyle eğitildi; uygun dönem dışı referans yok).
Uyarılar modeli yeniden eğitmez, kapatmaz, etkin modeli ya da işlem kurallarını DEĞİŞTİRMEZ; harici bildirim yok."""
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

Z90 = 1.645
SON_GUN = 60
TEYIT_YENI_GUN = 20
ASGARI = {"P1": (100, 30), "P2": (50, 20), "K1": (50, 20), "G1": (50, 0), "R1": (0, 20)}
P1_ASGARI_SINIF = 10
PSI_ORTA, PSI_BELIRGIN = 0.10, 0.25
NADIR_REJIM = 0.05
REF_YOLU = Path(__file__).with_name("izleme_ref") / "tp1_v1.json"


# ---------------------------------------------------------------- gün kümesine dayanıklı aralıklar
def kume_ortalama(gunler: List[str], x: List[float]) -> Dict:
    """Ortalama ve %90 aralık; standart hata gün kümeleriyle (K/(K−1) düzeltmeli)."""
    n = len(x)
    m = sum(x) / n
    top = defaultdict(float)
    for g, v in zip(gunler, x):
        top[g] += v - m
    k = len(top)
    if k < 2:
        return {"deger": m, "aralik": None}
    se = math.sqrt(k / (k - 1) * sum(s * s for s in top.values())) / n
    return {"deger": m, "aralik": [m - Z90 * se, m + Z90 * se], "se": se}


def kume_auc(gunler: List[str], y: List[int], p: List[float]) -> Optional[Dict]:
    """AUC ve kümeli DeLong (Obuchowski 1997) varyansı; %90 aralık."""
    pos = [(g, q) for g, t, q in zip(gunler, y, p) if t]
    neg = [(g, q) for g, t, q in zip(gunler, y, p) if not t]
    m, n = len(pos), len(neg)
    if not m or not n:
        return None
    negs = sorted(q for _, q in neg)
    poss = sorted(q for _, q in pos)
    from bisect import bisect_left, bisect_right

    v10 = [(bisect_left(negs, q) + 0.5 * (bisect_right(negs, q) - bisect_left(negs, q))) / n for _, q in pos]
    v01 = [(m - bisect_right(poss, q) + 0.5 * (bisect_right(poss, q) - bisect_left(poss, q))) / m for _, q in neg]
    auc = sum(v10) / m
    s10, s01 = defaultdict(float), defaultdict(float)
    for (g, _), v in zip(pos, v10):
        s10[g] += v - auc
    for (g, _), v in zip(neg, v01):
        s01[g] += v - auc
    kumeler = set(s10) | set(s01)
    k = len(kumeler)
    if k < 2:
        return {"deger": auc, "aralik": None}
    var = k / (k - 1) * (sum(s10[c] ** 2 for c in kumeler) / m ** 2 + sum(s01[c] ** 2 for c in kumeler) / n ** 2
                         + 2 * sum(s10[c] * s01[c] for c in kumeler) / (m * n))
    se = math.sqrt(max(var, 0.0))
    return {"deger": auc, "aralik": [auc - Z90 * se, auc + Z90 * se], "se": se}


def psi(degerler: List[float], ref: Dict) -> Optional[float]:
    from bisect import bisect_right
    v = [x for x in degerler if x is not None]
    if not v:
        return None
    k = len(ref["oranlar"])
    say = [0] * k
    for x in v:
        say[bisect_right(ref["sinirlar"], x)] += 1
    out = 0.0
    for a, e in zip(say, ref["oranlar"]):
        a, e = max(a / len(v), 1e-4), max(e, 1e-4)
        out += (a - e) * math.log(a / e)
    return out


# ---------------------------------------------------------------- tek pencere ölçümü (saf; yapay seride de kullanılır)
def _orneklem(k: List[Dict]) -> Dict:
    gun = sorted({x["gun"] for x in k})
    tek = defaultdict(list)
    for x in k:
        tek[x["ticker"]].append(x["gun"])
    return {"n": len(k), "gun": len(gun), "hisse": len(tek), "ilk": gun[0] if gun else None, "son": gun[-1] if gun else None,
            "pozitif": sum(x["y"] for x in k if x.get("y") is not None)}


def _yetersiz(kod: str, orn: Dict, ek: str = "") -> Dict:
    n_min, g_min = ASGARI[kod]
    return {"durum": "yetersiz", "neden": f"yetersiz veri: n={orn['n']} (en az {n_min}), bağımsız gün={orn['gun']} "
                                          f"(en az {g_min}){ek}. 'Model sağlıklı' sonucu çıkarılmaz."}


def olc(kayitlar: List[Dict], ref: Dict) -> Dict[str, Dict]:
    """kayitlar: {gun, ticker, y (0/1 | None = sonuç yok), p, girdi (dict), rejim (str | None)}."""
    sonuclu = [x for x in kayitlar if x.get("y") is not None]
    orn = _orneklem(sonuclu)
    gunler, y, p = [x["gun"] for x in sonuclu], [int(x["y"]) for x in sonuclu], [float(x["p"]) for x in sonuclu]
    out = {}
    # P1
    neg = orn["n"] - orn["pozitif"]
    if orn["n"] < ASGARI["P1"][0] or orn["gun"] < ASGARI["P1"][1] or orn["pozitif"] < P1_ASGARI_SINIF or neg < P1_ASGARI_SINIF:
        out["P1"] = _yetersiz("P1", orn, f", olumlu={orn['pozitif']}, olumsuz={neg} (her biri en az {P1_ASGARI_SINIF})")
    else:
        a = kume_auc(gunler, y, p)
        esik = a["aralik"] is not None and a["aralik"][1] < 0.5
        out["P1"] = {"durum": "esik_asildi" if esik else "esik_alti", "olcum": "AUC", "deger": round(a["deger"], 4),
                     "aralik_%90": [round(v, 4) for v in a["aralik"]] if a["aralik"] else None,
                     "referans": "0,50 (rastgele sıralama); geçmiş backtest referansı YOK",
                     "neden": "AUC aralığının üstü 0,50'nin altında: ayırt etme yok ya da ters" if esik else
                              "eşik aşılmadı (bu, modelin iyi olduğu anlamına gelmez)"}
    # P2 ve K1
    if orn["n"] < ASGARI["P2"][0] or orn["gun"] < ASGARI["P2"][1]:
        out["P2"] = _yetersiz("P2", orn)
        out["K1"] = _yetersiz("K1", orn)
    else:
        b = ref["egitim_tp1_orani"]
        fark = [(q - t) ** 2 - (b - t) ** 2 for q, t in zip(p, y)]
        d = kume_ortalama(gunler, fark)
        brier_m = sum((q - t) ** 2 for q, t in zip(p, y)) / len(y)
        brier_b = sum((b - t) ** 2 for t in y) / len(y)
        esik = d["aralik"] is not None and d["aralik"][0] > 0
        out["P2"] = {"durum": "esik_asildi" if esik else "esik_alti", "olcum": "Brier becerisi (sabit eğitim oranına göre)",
                     "deger": round(1 - brier_m / brier_b, 4) if brier_b else None,
                     "aralik_%90": [round(-v[1] / brier_b, 4), round(-v[0] / brier_b, 4)] if (v := d["aralik"]) else None,
                     "referans": f"sabit eğitim oranı %{100 * b:.2f}",
                     "neden": "model, sabit orandan anlamlı biçimde kötü" if esik else "eşik aşılmadı"}
        oran = kume_ortalama(gunler, [float(t) for t in y])
        ort_p = sum(p) / len(p)
        ar = oran["aralik"]
        esik = ar is not None and not (ar[0] <= ort_p <= ar[1])
        yon = "model fazla tahmin ediyor" if ar and ort_p > ar[1] else "model az tahmin ediyor"
        out["K1"] = {"durum": "esik_asildi" if esik else "esik_alti", "olcum": "gerçek TP1 oranı ↔ ortalama tahmin",
                     "deger": round(oran["deger"], 4), "ortalama_tahmin": round(ort_p, 4),
                     "aralik_%90": [round(v, 4) for v in ar] if ar else None, "referans": "modelin ortalama tahmini",
                     "neden": f"kalibrasyon bozulması: {yon}" if esik else "eşik aşılmadı"}
    # G1 (sonuç gerekmez)
    tum = _orneklem(kayitlar)
    if tum["n"] < ASGARI["G1"][0]:
        out["G1"] = _yetersiz("G1", tum)
    else:
        ps = {}
        for k_, r in ref["girdi"].items():
            v = psi([(x.get("girdi") or {}).get(k_) for x in kayitlar], r)
            if v is not None:
                ps[k_] = round(v, 4)
        enb = max(ps.items(), key=lambda z: z[1]) if ps else (None, None)
        sev = ("belirgin kayma" if enb[1] is not None and enb[1] >= PSI_BELIRGIN else
               "orta kayma" if enb[1] is not None and enb[1] >= PSI_ORTA else "kayma yok")
        out["G1"] = {"durum": "bilgi", "olcum": "PSI (eğitim dilimlerine göre)", "psi": ps, "en_buyuk": enb, "seviye": sev,
                     "referans": "tp1_v1 eğitim örnekleri", "neden": f"girdi dağılımı: {sev}. Tek başına model başarısızlığı "
                                                                   "anlamına gelmez."}
    # R1
    if tum["gun"] < ASGARI["R1"][1]:
        out["R1"] = _yetersiz("R1", tum)
    else:
        gunluk = {}
        for x in kayitlar:
            if x.get("rejim"):
                gunluk[x["gun"]] = x["rejim"]
        say = defaultdict(int)
        for r in gunluk.values():
            say[r] += 1
        top = sum(say.values()) or 1
        dag = {k: v / top for k, v in say.items()}
        eg = ref["rejim_gun_payi"]
        tvd = 0.5 * sum(abs(dag.get(k, 0) - eg.get(k, 0)) for k in set(dag) | set(eg))
        baskin = max(dag.items(), key=lambda z: z[1])[0] if dag else None
        nadir = baskin is not None and eg.get(baskin, 0) < NADIR_REJIM
        out["R1"] = {"durum": "bilgi", "olcum": "rejim dağılımı", "pencere_dagilimi": {k: round(v, 3) for k, v in dag.items()},
                     "egitim_payi_baskin": round(eg.get(baskin, 0), 4) if baskin else None, "baskin": baskin,
                     "toplam_degisim_uzakligi": round(tvd, 3), "referans": "tp1_v1 eğitim dönemi sinyal günleri",
                     "neden": (f"baskın rejim '{baskin}' eğitimde nadir (%{100 * eg.get(baskin, 0):.1f})" if nadir else
                               "rejim eğitimde görülen aralıkta") + ". Tek başına model başarısızlığı anlamına gelmez."}
    for k_, v in out.items():
        v["orneklem"] = tum if k_ in ("G1", "R1") else orn
    return out


# ---------------------------------------------------------------- teyit ve tekrar bastırma (saf durum makinesi)
def gecis(onceki: Optional[Dict], esik: bool, gun_sayisi: int) -> Dict:
    """onceki: {'durum': normal|izleniyor|acik|kapanma_izleniyor, 'gun0': int}. gun_sayisi: penceredeki bağımsız sonuç
    günü. Teyit için ilk aşımdan sonra ≥ TEYIT_YENI_GUN YENİ gün gerekir (aynı kanıt ikinci doğrulama sayılmaz)."""
    o = onceki or {"durum": "normal"}
    d = o["durum"]
    yeni = gun_sayisi - o.get("gun0", gun_sayisi)
    if d == "normal":
        return {"durum": "izleniyor", "gun0": gun_sayisi, "olay": "ilk_asim"} if esik else {"durum": "normal", "olay": None}
    if d == "izleniyor":
        if not esik:
            return {"durum": "normal", "olay": "teyit_edilmedi"}
        if yeni >= TEYIT_YENI_GUN:
            return {"durum": "acik", "gun0": gun_sayisi, "olay": "uyari_acildi"}
        return dict(o, olay=None)
    if d == "acik":
        if esik:
            return dict(o, gun0=gun_sayisi, olay=None)              # devam: yeni uyarı ÜRETİLMEZ
        return {"durum": "kapanma_izleniyor", "gun0": gun_sayisi, "olay": None}
    if d == "kapanma_izleniyor":
        if esik:
            return {"durum": "acik", "gun0": gun_sayisi, "olay": None}
        if yeni >= TEYIT_YENI_GUN:
            return {"durum": "normal", "olay": "uyari_kapandi"}
        return dict(o, olay=None)
    raise ValueError(d)


# ---------------------------------------------------------------- canlı defterle (yerel kayıt / panel)
def _kayitlar(conn, grup: Dict) -> List[Dict]:
    from . import defter
    say, done = defter.olculen_kayitlar(conn, grup)
    out = []
    for r in done:
        s = {k[2:]: v for k, v in r.items() if k.startswith("s_")}
        rj = json.loads(r.get("rejim_json") or "null") or {}
        out.append({"gun": r["giris_gunu"], "ticker": r["ticker"], "y": defter._y(s), "p": float(r["olasilik"]),
                    "girdi": json.loads(r.get("girdi_json") or "{}"),
                    "rejim": f"{rj['trend']} / {rj['oynaklik']}" if rj.get("trend") and rj.get("oynaklik") else None})
    # girdi ve rejim için sonuçlanmamış tahminler de kullanılır (sonuç gerekmez)
    olculen = {(x["gun"], x["ticker"]) for x in out}
    for r in conn.execute("SELECT * FROM tahmin"):
        r = dict(r)
        if r["sonradan"] or defter._grup_of(r) != {k: grup.get(k) for k in defter.GRUP_ALANLARI}:
            continue
        if (r["giris_gunu"], r["ticker"]) in olculen:
            continue
        rj = json.loads(r.get("rejim_json") or "null") or {}
        out.append({"gun": r["giris_gunu"], "ticker": r["ticker"], "y": None, "p": float(r["olasilik"]),
                    "girdi": json.loads(r.get("girdi_json") or "{}"),
                    "rejim": f"{rj['trend']} / {rj['oynaklik']}" if rj.get("trend") and rj.get("oynaklik") else None})
    return out


def degerlendir(conn, ref: Optional[Dict] = None) -> List[Dict]:
    from . import defter
    ref = ref or json.loads(REF_YOLU.read_text(encoding="utf-8"))
    out = []
    for g in defter.gruplar(conn):
        grup = g["grup"]
        e = {"grup": grup, "etiket": defter.grup_etiketi(grup)}
        if grup["kural_surum"] == "eksik" or grup["maliyet_protokol"] == "eksik":
            e["durum"] = "sozlesme_eksik"
            e["neden"] = "değerlendirme sözleşmesi eksik eski kayıtlar: izleme ölçümüne girmez"
            out.append(e)
            continue
        if grup["model_surum"] != "tp1_v1":
            e["durum"] = "referans_yok"
            e["neden"] = f"{grup['model_surum']} için izleme referansı yok"
            out.append(e)
            continue
        k = _kayitlar(conn, grup)
        sonuc_gunleri = sorted({x["gun"] for x in k if x["y"] is not None})
        son_gunler = set(sonuc_gunleri[-SON_GUN:])
        e["pencereler"] = {"birikimli": olc(k, ref),
                           "son_60_gun": olc([x for x in k if x["y"] is None or x["gun"] in son_gunler], ref)}
        e["tekrar_%"] = _tekrar(k)
        out.append(e)
    return out


def _tekrar(k: List[Dict]) -> Optional[float]:
    by = defaultdict(list)
    for x in sorted(k, key=lambda z: z["gun"]):
        by[x["ticker"]].append(datetime.fromisoformat(x["gun"]))
    t = sum(1 for v in by.values() for a, b in zip(v, v[1:]) if (b - a).days <= 14)
    return round(100 * t / len(k), 1) if k else None


def kontrol_et(conn, klasor: Path, simdi: Optional[datetime] = None) -> Dict:
    """Günlük kontrol: durum dosyasını günceller; YALNIZ geçişleri (ilk aşım, uyarı açıldı, teyit edilmedi, kapandı)
    ekle-yalnız kayda yazar. Aynı gün ikinci çağrı durum değiştirmez (aynı kanıt)."""
    simdi = simdi or datetime.now()
    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    durum_yolu, kayit_yolu = klasor / "izleme_durumu.json", klasor / "izleme_kayit.jsonl"
    durum = json.loads(durum_yolu.read_text(encoding="utf-8")) if durum_yolu.exists() else {}
    bugun = simdi.date().isoformat()
    if durum.get("_son_kontrol") == bugun:
        return {"atlandi": "bugün zaten kontrol edildi (günde en çok bir kontrol)"}
    olaylar = []
    for e in degerlendir(conn):
        if "pencereler" not in e:
            continue
        # teyit için "yeni kanıt" = grubun TOPLAM bağımsız sonuç günü artışı (60 günlük pencerede gün sayısı doyar)
        toplam_gun = e["pencereler"]["birikimli"]["P2"]["orneklem"]["gun"]
        for pad, olcum in e["pencereler"].items():
            for kod in ("P1", "P2", "K1"):
                o = olcum[kod]
                if o["durum"] == "yetersiz":
                    continue
                anahtar = f"{e['etiket']}|{pad}|{kod}"
                g = gecis(durum.get(anahtar), o["durum"] == "esik_asildi", toplam_gun)
                durum[anahtar] = {k: v for k, v in g.items() if k != "olay"}
                if g["olay"]:
                    olaylar.append({"zaman": simdi.isoformat(timespec="seconds"), "olay": g["olay"], "grup": e["etiket"],
                                    "pencere": pad, "olcut": kod, "olcum": o})
    durum["_son_kontrol"] = bugun
    with open(kayit_yolu, "a", encoding="utf-8") as f:
        for x in olaylar:
            f.write(json.dumps(x, ensure_ascii=False, default=str) + "\n")
    durum_yolu.write_text(json.dumps(durum, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"olay": len(olaylar), "olaylar": olaylar}


def panel_ozeti(conn, klasor: Optional[Path] = None) -> Dict:
    """Panel için SALT-OKUR özet: anlık ölçümler + (varsa) kayıtlı uyarı durumları. Hiçbir şey yazmaz."""
    durum = {}
    if klasor and (Path(klasor) / "izleme_durumu.json").exists():
        durum = json.loads((Path(klasor) / "izleme_durumu.json").read_text(encoding="utf-8"))
    return {"degerlendirme": degerlendir(conn),
            "acik_uyarilar": {k: v for k, v in durum.items() if isinstance(v, dict) and v.get("durum") == "acik"},
            "son_kontrol": durum.get("_son_kontrol"),
            "not": "Uyarılar modeli değiştirmez; harici bildirim yok. Geçmiş backteste göre bozulma ölçülmez."}
