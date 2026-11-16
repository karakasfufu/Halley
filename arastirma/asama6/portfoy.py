"""FAZ 2 (16.11.2026): teknik plan evreninin PORTFÖY backtesti (araştırma; canlı koda ve veritabanına yazmaz).

ÖNEMLİ: 5 yıllık geçmişte yapay zekâ haber puanı yoktur. Bu simülasyon "teknik plan evreninin portföy backtesti"dir;
canlı, haberli hazır fırsat listesinin birebir geçmiş performansı DEĞİLDİR.

Tek kaynak ilkesi (kurallar ikinci kez kodlanmaz):
  - Tek işlemin giriş/çıkışı, kısmi satış, stop'un girişe çekilmesi, TP2/SL/30 gün: bist_haber.journal.evaluate
  - Riske göre adet: bist_haber.journal.position_size
  - Sektör: bist_haber.sectors.sector_of
  - Aynı mumda TP/SL belirsizliği: bist_haber.defter.belirsiz_gunler
  - Fırsat sıralaması: canlıdaki ready.select sıralama anahtarı (ready.RISK_ORDER; haber puanı bu evrende 0)
Simülatörün kendine ait tek işi sermaye, nakit, sınırlar ve zaman sırasıdır.

ZAMAN SIRASI (gün d için):
  1) GİRİŞLER (d açılışı): adaylar sinyal günü d'den önceki işlem günü olan planlar. Karar yalnız d−1 kapanışında
     bilinenlerle verilir: sıralama anahtarı, d−1 sonu özsermaye (adet), d−1 sonu nakit, d−1 sonu açık pozisyonlar ve
     açık risk. d günü kapanan pozisyonların nakdi ve yeri d girişlerinde KULLANILMAZ (açılıştaki boşluk satışı dahil;
     muhafazakâr). Giriş fiyatı d açılışıdır; açılış azami girişin üstündeyse alınmaz (canlı kural).
  2) ÇIKIŞLAR (d içinde): her açık pozisyon journal.evaluate ile YALNIZ d dahil o güne kadarki mumlarla değerlendirilir;
     o gün oluşan satış bacakları (TP1'de yarısı, son çıkış) d gününde nakde yansır. Sonuç önceden hesaplanmaz.
  3) GÜN SONU: özsermaye = nakit + Σ kalan adet × son bilinen kapanış (gerçekleşmemiş kâr/zarar dahil).
SIRALAMA: (risk sırası, −(teknik skor + 2·min(haber,5) + min(r/g,4)), hisse, tür) — eşitlikte hisse kodu ve tür
  (deterministik). Model olasılığıyla sıralama YOK: uygun dönem dışı tahmin kaydı yok ve bu fazda model eğitilmez.
MALİYET: komisyon_pct ve kayma_pct alış+satış TOPLAMIDIR (Halley ayarı gibi). journal.evaluate ile AYNI toplam maliyet
  için: alışta adet × giriş fiyatı × (k+s)/200; her satış bacağında satılan adet × GİRİŞ fiyatı × (k+s)/200 (satış
  tutarı değil — tekil işlem sonuçlarıyla birebir mutabakat için). Toplam = adet × giriş × (k+s)/100; iki kez düşülmez.
RİSK: aday işlem riski = adet × ((plan girişi − SL) + plan girişi × (k+s)/100) (journal.position_size ile aynı).
  Açık pozisyon riski = kalan adet × max(0, giriş fiyatı − güncel stop) + kalan adet × giriş fiyatı × (k+s)/200
  (TP1 sonrası stop girişe çekildiği için yalnız kalan satış maliyeti kalır). Toplam risk sınırı, d−1 sonu özsermayenin
  yüzdesidir.
KISMİ SATIŞ: TP1'de floor(adet/2) satılır, kalan son çıkışta (tek adette TP1 satışı olmaz, hepsi son çıkışta).
SEKTÖR: ana sektör başına en fazla N pozisyon. Sektörü bilinmeyen hisseler tek bir "bilinmiyor" kovasında aynı sınıra
  tabidir (muhafazakâr; sayısı raporlanır).
SİMÜLASYON SONU: açık pozisyonlar son bilinen kapanışla değerlenir; ayrı listelenir; kapanmış işlem metriklerine
  (kâr faktörü, kazanma oranı) GİRMEZ, özsermaye eğrisine gerçekleşmemiş kâr/zarar olarak girer.
EKSİK FİYAT: pozisyonun o gün mumu yoksa son bilinen kapanış kullanılır, eksik gün sayılır; giriş günü mumu yoksa
  aday atlanır ("giriş günü fiyat yok").
Kullanım: python portfoy.py <repo> <arastirma.db> <planlar.csv> <cikti_klasoru> [--evren canli_ortak|yalniz_teknik]
"""
import hashlib
import json
import math
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

VARSAYILAN = {"baslangic_sermaye": 100000.0, "risk_pct": 1.0, "azami_pozisyon": 5, "azami_toplam_risk_pct": 6.0,
              "azami_sektor": 2, "komisyon_pct": 0.20, "kayma_pct": 0.10, "sabit_adet": None, "sinirsiz": False}


def _mods():
    from bist_haber import defter, journal, ready, sectors
    return defter, journal, ready, sectors


def siralama_anahtari(p: Dict, haber: float = 0.0):
    """Canlıdaki ready.select sıralaması (bu evrende haber puanı 0) + deterministik bağlayıcılar."""
    _, _, ready, _ = _mods()
    return (ready.RISK_ORDER.get(p["risk"], 1), -(p["teknik_skor"] + 2 * min(haber, 5) + min(p["rr1"], 4)),
            p["ticker"], p["tur"])


def evren_suzgeci(p: Dict, evren: str) -> bool:
    """Önceden tanımlı evrenler (canlı eşiklerden; sonuçlara bakılarak seçilmedi)."""
    _, _, ready, _ = _mods()
    if p["risk"] == "yüksek":
        return False
    if evren == "yalniz_teknik":
        return p["teknik_skor"] >= ready.MIN_TECH_ONLY and str(p.get("trend", "")).startswith("Yükseliş")
    return p["teknik_skor"] >= ready.MIN_TECH                     # canli_ortak


def _sektor(tk: str) -> str:
    _, _, _, sectors = _mods()
    s = sectors.sector_of(tk)
    return s[0] if s else "bilinmiyor"


def simule(planlar: List[Dict], bars: Dict[str, List[Dict]], takvim: List[str], bas: str, son: str,
           ayar: Optional[Dict] = None, sektor_fn=None) -> Dict:
    """Saf simülasyon (dosya/veritabanı yok). planlar: ticker, tarih (sinyal günü), tur, risk, teknik_skor, rr1, giris,
    sl, tp1, tp2, azami. bars: hisse → tarih sıralı mum listesi. takvim: işlem günleri (sıralı)."""
    defter, journal, ready, _ = _mods()
    a = dict(VARSAYILAN, **(ayar or {}))
    sektor_fn = sektor_fn or _sektor
    kom, kay = a["komisyon_pct"], a["kayma_pct"]
    c2 = (kom + kay) / 200.0                                      # bacak başına oran (alış ya da satış)
    gunler = [d for d in takvim if bas <= d <= son]
    onceki = {takvim[i]: takvim[i - 1] for i in range(1, len(takvim))}
    adaylar: Dict[str, List[Dict]] = {}
    for p in planlar:
        adaylar.setdefault(p["tarih"], []).append(p)
    idx = {tk: {b["date"]: i for i, b in enumerate(bs)} for tk, bs in bars.items()}
    nakit, acik, islemler, atlanan, egri = float(a["baslangic_sermaye"]), [], [], [], []
    kucultulen, eksik_fiyat = 0, Counter()
    ozsermaye_onceki = nakit
    son_kapanis: Dict[str, float] = {}

    def acik_risk(pozlar):
        return sum(x["kalan"] * max(0.0, x["fill"] - x["stop"]) + x["kalan"] * x["fill"] * c2 for x in pozlar)

    for d in gunler:
        # ---- 1) girişler: yalnız d−1 sonu bilgisiyle
        pd_ = onceki.get(d)
        nakit_kullanilabilir = nakit
        risk_bas = acik_risk(acik)
        bugun = []
        for p in sorted(adaylar.get(pd_, []), key=siralama_anahtari):
            tk = p["ticker"]
            neden = None
            if any(x["ticker"] == tk for x in acik + bugun):
                neden = "zaten açık pozisyon"
            bar = bars.get(tk, [])[idx[tk][d]] if tk in idx and d in idx[tk] else None
            if not neden and bar is None:
                neden = "giriş günü fiyat yok"
            if not neden and (bar.get("open") or bar["close"]) > p["azami"] + 1e-9:
                neden = "açılış azami girişin üstünde"
            if not neden and not a["sinirsiz"] and len(acik) + len(bugun) >= a["azami_pozisyon"]:
                neden = "pozisyon sınırı"
            sek = sektor_fn(tk)
            if not neden and not a["sinirsiz"] and \
                    sum(1 for x in acik + bugun if x["sektor"] == sek) >= a["azami_sektor"]:
                neden = "sektör sınırı" + (" (sektör bilinmiyor)" if sek == "bilinmiyor" else "")
            adet = 0
            if not neden:
                if a["sabit_adet"]:
                    adet = int(a["sabit_adet"])
                else:
                    try:
                        adet = journal.position_size(ozsermaye_onceki, a["risk_pct"], p["giris"], p["sl"],
                                                     kom + kay)["adet"]
                    except ValueError:
                        neden = "geçersiz seviye (SL ≥ giriş)"
                if not neden and adet <= 0:
                    neden = "risk bütçesiyle 0 adet"
            kucuk = False
            if not neden:                                       # nakit sınırı: son adet (d−1 sonu nakit)
                acilis = bar.get("open") or bar["close"]
                if adet * acilis * (1 + c2) > nakit_kullanilabilir + 1e-9 and not a["sinirsiz"]:
                    adet2 = math.floor(nakit_kullanilabilir / (acilis * (1 + c2)))
                    if adet2 <= 0:
                        neden = "nakit yetersiz"
                    else:
                        adet, kucuk = adet2, True
            if not neden:                                       # toplam açık risk: son adetle
                risk_aday = adet * ((p["giris"] - p["sl"]) + p["giris"] * (kom + kay) / 100)
                if not a["sinirsiz"] and risk_bas + sum(x["risk_giris"] for x in bugun) + risk_aday > \
                        a["azami_toplam_risk_pct"] / 100 * ozsermaye_onceki + 1e-9:
                    neden = "toplam risk sınırı"
            if neden:
                atlanan.append({"gun": d, "sinyal_gunu": pd_, "ticker": tk, "tur": p["tur"], "neden": neden})
                continue
            if kucuk:
                kucultulen += 1
            alis_maliyet = adet * acilis * c2
            nakit -= adet * acilis + alis_maliyet
            nakit_kullanilabilir -= adet * acilis + alis_maliyet
            bugun.append({"ticker": tk, "plan": p, "giris_gunu": d, "fill": acilis, "adet": adet, "kalan": adet,
                          "stop": p["sl"], "tp1_satildi": False, "sektor": sek, "maliyet": alis_maliyet,
                          "bacaklar": [], "nakit_kucultme": kucuk, "eksik_gun": 0,
                          "risk_giris": adet * ((p["giris"] - p["sl"]) + p["giris"] * (kom + kay) / 100)})
        acik.extend(bugun)
        # ---- 2) çıkışlar: journal.evaluate yalnız d dahil o güne kadarki mumlarla
        kalan_acik = []
        for x in acik:
            tk, p = x["ticker"], x["plan"]
            bs = bars.get(tk, [])
            if tk in idx and d in idx[tk]:
                son_kapanis[tk] = bs[idx[tk][d]]["close"]
            else:
                eksik_fiyat[tk] += 1
                x["eksik_gun"] += 1
            upto = [b for b in bs if p["tarih"] < b["date"] <= d]
            rec = {"kaynak": "gercek", "gercek_giris_gunu": x["giris_gunu"], "gercek_giris_fiyati": x["fill"],
                   "signal_day": p["tarih"], "senaryo": p["tur"], "sl": p["sl"], "tp1": p["tp1"], "tp2": p["tp2"],
                   "giris": p["giris"], "alarm": None, "gecerlilik": 1}
            res = journal.evaluate(rec, upto, kom, kay)
            if res.get("durum") == "kapandı":
                legs = res.get("bacaklar") or []
                if x["tp1_satildi"]:
                    if abs(legs[0]["fiyat"] - x["bacaklar"][0]["fiyat"]) > 1e-6:
                        raise AssertionError(f"{tk}: önceden işlenen TP1 fiyatı journal sonucuyla uyuşmuyor")
                    legs = legs[1:]
                for j, lg in enumerate(legs):
                    son_bacak = j == len(legs) - 1
                    sh = x["kalan"] if son_bacak else min(x["kalan"], math.floor(x["adet"] / 2))
                    _sat(x, d, sh, lg["fiyat"], lg["neden"], c2)
                    nakit += sh * lg["fiyat"] - sh * x["fill"] * c2
                n = int(res.get("islem_gunu") or 1)
                i0 = next(i for i, b in enumerate(upto) if b["date"] >= x["giris_gunu"])
                bel = defter.belirsiz_gunler(upto[i0:], x["fill"], p["sl"], p["tp1"], p["tp2"], n)
                brut = sum(b["adet"] * (b["fiyat"] - x["fill"]) for b in x["bacaklar"])
                net = brut - x["maliyet"]
                islemler.append({"ticker": tk, "sinyal_gunu": p["tarih"], "giris_gunu": x["giris_gunu"], "cikis_gunu": d,
                                 "tur": p["tur"], "sektor": x["sektor"], "adet": x["adet"], "giris_fiyati": x["fill"],
                                 "sonuc": res.get("sonuc"), "bacaklar": x["bacaklar"], "brut_tl": round(brut, 2),
                                 "maliyet_tl": round(x["maliyet"], 2), "net_tl": round(net, 2), "r": res.get("r"),
                                 "journal_net_%": res.get("net_getiri_pct"), "islem_gunu": n,
                                 "ayni_mum_belirsiz": bool(bel), "belirsiz_gunler": bel,
                                 "nakit_kucultme": x["nakit_kucultme"], "eksik_fiyat_gunu": x["eksik_gun"]})
                continue
            if res.get("tp1_goruldu") and not x["tp1_satildi"]:
                b = bs[idx[tk][d]] if tk in idx and d in idx[tk] else None
                if b is None or not any(o.startswith(d) and "TP1" in o for o in res.get("olaylar") or []):
                    raise AssertionError(f"{tk}: TP1 {d} günü dışında görüldü (sıra hatası)")
                px = round(b["open"] if (b.get("open") or 0) >= p["tp1"] else p["tp1"], 4)   # journal ile aynı (4 basamak)
                sh = math.floor(x["adet"] / 2)
                if sh > 0:
                    _sat(x, d, sh, px, "TP1 (yarısı)", c2)
                    nakit += sh * px - sh * x["fill"] * c2
                else:
                    x["bacaklar"].append({"gun": d, "adet": 0, "fiyat": px, "neden": "TP1 (tek adet: satış yok)"})
                x["tp1_satildi"] = True
                x["stop"] = x["fill"]
            kalan_acik.append(x)
        acik = kalan_acik
        # ---- 3) gün sonu
        piyasa = sum(x["kalan"] * son_kapanis.get(x["ticker"], x["fill"]) for x in acik)
        ozsermaye = nakit + piyasa
        egri.append({"gun": d, "nakit": round(nakit, 2), "piyasa_degeri": round(piyasa, 2),
                     "ozsermaye": round(ozsermaye, 2), "acik_pozisyon": len(acik), "acik_risk": round(acik_risk(acik), 2)})
        ozsermaye_onceki = ozsermaye
    acik_son = [{"ticker": x["ticker"], "giris_gunu": x["giris_gunu"], "adet_bas": x["adet"], "kalan": x["kalan"],
                 "giris_fiyati": x["fill"], "son_kapanis": son_kapanis.get(x["ticker"], x["fill"]),
                 "tp1_satildi": x["tp1_satildi"], "gerceklesen_tl": round(sum(b["adet"] * (b["fiyat"] - x["fill"]) for b in x["bacaklar"]), 2),
                 "gerceklesmemis_tl": round(x["kalan"] * (son_kapanis.get(x["ticker"], x["fill"]) - x["fill"]), 2),
                 "eksik_fiyat_gunu": x["eksik_gun"]} for x in acik]
    return {"ayar": a, "bas": bas, "son": son, "egri": egri, "islemler": islemler, "atlanan": atlanan,
            "acik_son": acik_son, "kucultulen": kucultulen, "eksik_fiyat": dict(eksik_fiyat),
            "metrik": metrikler(egri, islemler, atlanan, a["baslangic_sermaye"], acik_son, kucultulen)}


def _sat(x: Dict, d: str, sh: int, px: float, neden: str, c2: float) -> None:
    if sh <= 0:
        return
    x["kalan"] -= sh
    x["maliyet"] += sh * x["fill"] * c2
    x["bacaklar"].append({"gun": d, "adet": sh, "fiyat": px, "neden": neden})


def metrikler(egri: List[Dict], islemler: List[Dict], atlanan: List[Dict], bas_sermaye: float,
              acik_son: List[Dict], kucultulen: int) -> Dict:
    if not egri:
        return {}
    oz = [bas_sermaye] + [e["ozsermaye"] for e in egri]
    getiri = [oz[i] / oz[i - 1] - 1 for i in range(1, len(oz))]
    tepe, mdd, mdd_gun, tepe_gun, sure, en_uzun = oz[0], 0.0, None, 0, 0, 0
    for i, v in enumerate(oz):
        if v >= tepe:
            tepe, tepe_gun = v, i
        dd = v / tepe - 1
        if dd < mdd:
            mdd, mdd_gun = dd, egri[i - 1]["gun"] if i else None
        en_uzun = max(en_uzun, i - tepe_gun)
    n = len(getiri)
    ort = sum(getiri) / n
    sd = math.sqrt(sum((g - ort) ** 2 for g in getiri) / (n - 1)) if n > 1 else 0.0
    asagi = math.sqrt(sum(min(g, 0.0) ** 2 for g in getiri) / n) if n else 0.0
    kazanc = [t["net_tl"] for t in islemler if t["net_tl"] > 0]
    kayip = [t["net_tl"] for t in islemler if t["net_tl"] <= 0]
    seri, en_seri = 0, 0
    for t in sorted(islemler, key=lambda t: (t["cikis_gunu"], t["ticker"])):
        seri = seri + 1 if t["net_tl"] <= 0 else 0
        en_seri = max(en_seri, seri)
    rs = [t["r"] for t in islemler if t["r"] is not None]
    return {
        "baslangic": bas_sermaye, "bitis_ozsermaye": oz[-1], "toplam_getiri_%": round(100 * (oz[-1] / bas_sermaye - 1), 2),
        "azami_dusus_%": round(100 * mdd, 2), "azami_dusus_gunu": mdd_gun, "en_uzun_dusus_suresi_gun": en_uzun,
        "sharpe_yillik": round(ort / sd * math.sqrt(252), 3) if sd else None,
        "sortino_yillik": round(ort / asagi * math.sqrt(252), 3) if asagi else None,
        "kapanan_islem": len(islemler), "kazanan": len(kazanc), "kaybeden": len(kayip),
        "kazanma_orani_%": round(100 * len(kazanc) / len(islemler), 1) if islemler else None,
        "kar_faktoru": round(sum(kazanc) / abs(sum(kayip)), 3) if kayip and sum(kayip) else None,
        "beklenen_net_tl": round(sum(t["net_tl"] for t in islemler) / len(islemler), 2) if islemler else None,
        "ort_R": round(sum(rs) / len(rs), 3) if rs else None,
        "ort_kazanc_tl": round(sum(kazanc) / len(kazanc), 2) if kazanc else None,
        "ort_kayip_tl": round(sum(kayip) / len(kayip), 2) if kayip else None,
        "en_uzun_ardisik_kayip": en_seri,
        "ort_islem_gunu": round(sum(t["islem_gunu"] for t in islemler) / len(islemler), 1) if islemler else None,
        "ort_acik_pozisyon": round(sum(e["acik_pozisyon"] for e in egri) / len(egri), 2),
        "ayni_mum_belirsiz_islem": sum(1 for t in islemler if t["ayni_mum_belirsiz"]),
        "nakitle_kucultulen": kucultulen,
        "atlanan": dict(Counter(x["neden"] for x in atlanan)),
        "sonda_acik_pozisyon": len(acik_son),
        "sonda_gerceklesmemis_tl": round(sum(x["gerceklesmemis_tl"] for x in acik_son), 2),
        "kapanan_net_toplam_tl": round(sum(t["net_tl"] for t in islemler), 2)}


# ---------------------------------------------------------------- veri ve kayıt (CLI)
def plan_oku(path: str, evren: str) -> List[Dict]:
    import csv
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                p = {"ticker": r["ticker"], "tarih": r["tarih"], "tur": r["tur"], "risk": r["risk"], "trend": r["trend"],
                     "teknik_skor": int(float(r["teknik_skor"])), "rr1": float(r["rr1"]),
                     **{k: float(r[k]) for k in ("giris", "sl", "tp1", "tp2", "azami")}}
            except (KeyError, ValueError):
                continue
            if evren_suzgeci(p, evren):
                out.append(p)
    return out


def bar_oku(dbp: str, tickers: List[str]) -> Dict[str, List[Dict]]:
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    out: Dict[str, List[Dict]] = {}
    for tk in sorted(set(tickers)):
        out[tk] = [dict(zip(("date", "open", "high", "low", "close"), r)) for r in c.execute(
            "SELECT date, open, high, low, close FROM prices WHERE ticker=? AND close IS NOT NULL ORDER BY date", (tk,))]
    c.close()
    return out


def _sha_dosya(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    import csv
    repo, dbp, plan_csv, cikti = sys.argv[1:5]
    evren = sys.argv[sys.argv.index("--evren") + 1] if "--evren" in sys.argv else "canli_ortak"
    sys.path.insert(0, repo)
    out = Path(cikti)
    out.mkdir(parents=True, exist_ok=True)
    planlar = plan_oku(plan_csv, evren)
    bars = bar_oku(dbp, [p["ticker"] for p in planlar] + ["XU100"])
    takvim = [b["date"] for b in bars["XU100"]]
    son_gun = takvim[-1]
    from datetime import date as _d, timedelta
    bas12 = (_d.fromisoformat(son_gun) - timedelta(days=365)).isoformat()
    donemler = {"son_12_ay": (min(d for d in takvim if d > bas12), son_gun), "2024": ("2024-01-01", "2024-12-31")}
    try:
        kod = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        kirli = bool(subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    except Exception:
        kod, kirli = "?", None
    kayit = {"olusturuldu": datetime.now().isoformat(timespec="seconds"), "ad": "teknik plan evreninin portföy backtesti",
             "uyari": "Geçmiş yapay zekâ haber puanı yok; canlı haberli hazır fırsat listesinin geçmiş performansı değildir.",
             "evren": evren, "ayar": VARSAYILAN, "donemler": donemler, "kod": {"commit": kod, "calisma_agaci_kirli": kirli},
             "python": sys.version.split()[0],
             "veri": {"planlar": plan_csv, "planlar_sha256": _sha_dosya(plan_csv), "plan_sayisi_evrende": len(planlar),
                      "plan_tarih_araligi": [min(p["tarih"] for p in planlar), max(p["tarih"] for p in planlar)],
                      "arastirma_db": dbp, "db_boyut": Path(dbp).stat().st_size, "fiyat_son_gun": son_gun,
                      "hisse_sayisi": len({p["ticker"] for p in planlar}),
                      "sektoru_bilinmeyen_hisse": sorted({p["ticker"] for p in planlar if _sektor(p["ticker"]) == "bilinmiyor"})}}
    ozet = {}
    for ad, (b, s) in donemler.items():
        r = simule(planlar, bars, takvim, b, s)
        ozet[ad] = r["metrik"]
        for isim, satirlar in (("egri", r["egri"]), ("islemler", r["islemler"]), ("atlanan", r["atlanan"]),
                               ("acik_son", r["acik_son"])):
            with open(out / f"{ad}_{isim}.csv", "w", newline="", encoding="utf-8") as f:
                if satirlar:
                    w = csv.DictWriter(f, list(satirlar[0].keys()))
                    w.writeheader()
                    for x in satirlar:
                        w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                                    for k, v in x.items()})
        print(ad, json.dumps(r["metrik"], ensure_ascii=False), flush=True)
    kayit["sonuc"] = ozet
    (out / "kayit.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
