"""FAZ 3 (araştırma): portföy metriklerinin BAĞIMSIZ yeniden hesabı ve ek metrikler/dağılımlar.
portfoy.metrikler ile aynı tanımlar, farklı kodla (çapraz doğrulama). Simülasyon yeniden çalıştırılmaz: FAZ 2 kabul
dosyaları (egri/islemler CSV) okunur.

TANIMLAR
  özsermaye serisi  : [başlangıç] + gün sonu özsermayeleri (açık pozisyon son kapanışla değerli)
  MDD               : min_t (E_t / max_{s≤t} E_s − 1); gün sonu verisiyle (gün içi dip görülmez)
  düşüş süresi      : son zirveden bu yana geçen gözlem sayısı (işlem günü), en uzunu
  Sortino (yıllık)  : ort(r) / sqrt(ort(min(r,0)²)) × √252; r günlük basit getiri, hedef 0, risksiz faiz 0
  Sharpe (yıllık)   : ort(r) / std_örneklem(r) × √252
  PF                : Σ net_tl(>0) / |Σ net_tl(≤0)|, yalnız kapanmış işlemler, maliyet dahil
  CAGR              : (E_son / E_0)^(252 / gün) − 1   (dönem < 1 yıl ise yıllıklaştırma yanıltıcı olabilir)
  Calmar            : CAGR / |MDD|;  kurtarma çarpanı: (E_son − E_0) / (azami TL düşüş)
  Ulcer endeksi     : sqrt(ort(düşüş_%²))
  maruziyet         : en az bir açık pozisyonlu gün / gün
  beklenen değer    : ort(net_tl), ort(R); ödeme oranı: ort kazanç / |ort kayıp|
  ardışık kayıp     : çıkış gününe (sonra hisse koduna) göre sıralı kapanmış işlemlerde net_tl ≤ 0 serileri"""
import csv
import json
import math
from collections import Counter
from typing import Dict, List

YIL = 252


def yuzdelik(x: List[float], q: float):
    if not x:
        return None
    s = sorted(x)
    k = (len(s) - 1) * q
    a, b = math.floor(k), math.ceil(k)
    return s[a] + (s[b] - s[a]) * (k - a)


def seri_metrikleri(oz: List[float]) -> Dict:
    r = [oz[i] / oz[i - 1] - 1 for i in range(1, len(oz))]
    tepe, mdd, mdd_tl, sure, en_uzun, dd2 = oz[0], 0.0, 0.0, 0, 0, []
    tepe_i = 0
    for i, v in enumerate(oz):
        if v >= tepe:
            tepe, tepe_i = v, i
        dd = v / tepe - 1
        mdd = min(mdd, dd)
        mdd_tl = max(mdd_tl, tepe - v)
        en_uzun = max(en_uzun, i - tepe_i)
        dd2.append((100 * dd) ** 2)
    n = len(r)
    ort = sum(r) / n if n else 0.0
    sd = math.sqrt(sum((x - ort) ** 2 for x in r) / (n - 1)) if n > 1 else 0.0
    asagi = math.sqrt(sum(min(x, 0.0) ** 2 for x in r) / n) if n else 0.0
    cagr = (oz[-1] / oz[0]) ** (YIL / n) - 1 if n else None
    return {"mdd_%": 100 * mdd, "mdd_tl": mdd_tl, "en_uzun_dusus_gun": en_uzun,
            "sharpe": ort / sd * math.sqrt(YIL) if sd else None, "sortino": ort / asagi * math.sqrt(YIL) if asagi else None,
            "cagr_%": 100 * cagr if cagr is not None else None, "yillik_oynaklik_%": 100 * sd * math.sqrt(YIL),
            "calmar": (cagr / abs(mdd)) if mdd and cagr is not None else None,
            "kurtarma_carpani": (oz[-1] - oz[0]) / mdd_tl if mdd_tl else None,
            "ulcer": math.sqrt(sum(dd2) / len(dd2)), "gunluk_getiri_en_kotu_%": 100 * min(r) if r else None,
            "gunluk_getiri_en_iyi_%": 100 * max(r) if r else None}


def islem_metrikleri(islemler: List[Dict]) -> Dict:
    net = [t["net_tl"] for t in islemler]
    kaz, kay = [x for x in net if x > 0], [x for x in net if x <= 0]
    rs = [t["r"] for t in islemler if t["r"] is not None]
    pct = [100 * t["net_tl"] / (t["adet"] * t["giris_fiyati"]) for t in islemler]
    gun = [t["islem_gunu"] for t in islemler]
    seriler, s = [], 0
    for t in sorted(islemler, key=lambda t: (t["cikis_gunu"], t["ticker"])):
        if t["net_tl"] <= 0:
            s += 1
        else:
            if s:
                seriler.append(s)
            s = 0
    if s:
        seriler.append(s)
    q = lambda x: {f"p{int(p * 100)}": (round(yuzdelik(x, p), 3) if x else None) for p in (0.05, 0.25, 0.5, 0.75, 0.95)}
    return {"kapanan": len(net), "pf": sum(kaz) / abs(sum(kay)) if kay and sum(kay) else None,
            "kazanma_%": 100 * len(kaz) / len(net) if net else None,
            "beklenen_net_tl": sum(net) / len(net) if net else None, "ort_R": sum(rs) / len(rs) if rs else None,
            "odeme_orani": (sum(kaz) / len(kaz)) / abs(sum(kay) / len(kay)) if kaz and kay and sum(kay) else None,
            "en_uzun_ardisik_kayip": max(seriler) if seriler else 0,
            "ardisik_kayip_dagilimi": dict(sorted(Counter(seriler).items())),
            "net_getiri_%_dagilimi": q(pct), "R_dagilimi": q(rs), "islem_gunu_dagilimi": q(gun),
            "R_kovalari": dict(sorted(Counter(("<-1.5" if x < -1.5 else "-1.5..-0.5" if x < -0.5 else "-0.5..0.5"
                                              if x < 0.5 else "0.5..1.5" if x < 1.5 else ">=1.5") for x in rs).items())),
            "sonuc_dagilimi": dict(Counter(t["sonuc"] for t in islemler))}


def egri_oku(p) -> List[Dict]:
    return [{k: (float(v) if k != "gun" else v) for k, v in r.items()} for r in csv.DictReader(open(p, encoding="utf-8"))]


def islem_oku(p) -> List[Dict]:
    out = []
    for r in csv.DictReader(open(p, encoding="utf-8")):
        out.append({"ticker": r["ticker"], "giris_gunu": r["giris_gunu"], "cikis_gunu": r["cikis_gunu"],
                    "sonuc": r["sonuc"], "net_tl": float(r["net_tl"]), "adet": int(r["adet"]),
                    "giris_fiyati": float(r["giris_fiyati"]), "r": float(r["r"]) if r["r"] not in ("", "None") else None,
                    "islem_gunu": int(r["islem_gunu"]), "sl": float(r["sl"]), "planlanan_giris": float(r["planlanan_giris"]),
                    "bacaklar": json.loads(r["bacaklar"]), "sinyal_gunu": r["sinyal_gunu"],
                    "varsayimsal": r.get("cikis_varsayimsal_stop_alti") == "True"})
    return out


def hesapla(egri: List[Dict], islemler: List[Dict], bas: float) -> Dict:
    oz = [bas] + [e["ozsermaye"] for e in egri]
    m = seri_metrikleri(oz)
    m.update(islem_metrikleri(islemler))
    m["maruziyet_%"] = 100 * sum(1 for e in egri if e["acik_pozisyon"] > 0) / len(egri)
    aylik, onceki, ay_son = {}, bas, {}
    for e in egri:
        ay_son[e["gun"][:7]] = e["ozsermaye"]
    for ay, v in sorted(ay_son.items()):
        aylik[ay] = round(100 * (v / onceki - 1), 2)
        onceki = v
    m["aylik_getiri_%"] = aylik
    return m
