"""Aşama 6 (2026-11-15): "TP1, SL'den önce gelir mi?" olasılık modeli — yalnız BİLGİ.

Seçimi, sıralamayı ve eşikleri DEĞİŞTİRMEZ; henüz panele bağlı değildir (kullanıcı kararı bekleniyor).
Girdiler yalnız teknik veridir (haber yok) ve hepsi plan anında bilinen değerlerdir. Eğitim ve canlı kullanım AYNI
`features()` fonksiyonunu kullanır (arastirma/asama6/etiketle.py da bunu çağırır) → eğitimdeki ile canlıdaki girdiler
birebir aynı hesaplanır. Model dosyası: bist_haber/modeller/tp1_v1.json (eğitim: arastirma/asama6/egit.py). Model = benzer durumlar
tablosu ile 10 girdili sade lojistik regresyonun ortalaması (iki ileriye dönük sınamada en tutarlısı; ASAMA6_RAPOR.md).
Yapay zekâ kullanılmaz; yalnız standart kütüphane (Python 3.9).
"""
import json
import math
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from . import technical

MODEL_DIR = Path(__file__).with_name("modeller")
DEFAULT = "tp1_v1.json"
TURLER = ("kirilim_teyitli", "geri_cekilme", "destek_teyitli")
WIN = 250                       # canlıdaki 1 yıllık indirmeyle aynı pencere


def market_features(bench: Optional[List[dict]]) -> Dict[str, Optional[float]]:
    """BIST 100 durumu (son 250 gün): trend (+1/0/−1), 20 günlük getiri %, 20 günlük ortalama gerçek aralık %."""
    bars = [b for b in (bench or []) if b.get("close")][-WIN:]
    out = {"x_trend": None, "x_perf20": None, "x_atr": None}
    if len(bars) < 210:
        return out
    cl = [b["close"] for b in bars]
    e50, e200, last = technical.ema(cl, 50), technical.ema(cl, 200), cl[-1]
    out["x_trend"] = 1.0 if last > e50 > e200 else (-1.0 if last < e50 < e200 else 0.0)
    out["x_perf20"] = (last / cl[-21] - 1) * 100
    a = technical.atr(bars[-41:], 20)
    out["x_atr"] = a / last * 100 if a else None
    return out


def features(t: Dict, plan: Dict, ts: Dict, risk: str, mk: Dict) -> Dict[str, Optional[float]]:
    """t: technical.analyze; plan: ready.candidates'tan seçilen plan (tur/giris/sl/tp1/rr1); ts: ready.tech_score;
    risk: "düşük"/"orta"/"yüksek"; mk: market_features. Eksik değer None kalır (model ortanca ile doldurur)."""
    e, sl, tp1, atr = plan["giris"], plan["sl"], plan["tp1"], t.get("atr") or 0
    px = t["son_fiyat"]
    f = {"rr1": plan["rr1"], "stop_%": (e - sl) / e * 100, "tp1_%": (tp1 / e - 1) * 100,
         "stop_atr": (e - sl) / atr if atr else None, "tp1_atr": (tp1 - e) / atr if atr else None,
         "skor": ts["skor"], **{"p_" + k: v for k, v in ts["parca"].items()},
         "rsi": t.get("rsi14"), "atr_%": t.get("atr_%"), "sma50_%": t.get("fiyat_sma50_%"),
         "sma200_%": t.get("fiyat_sma200_%"), "hacim_orani": t.get("hacim_orani"), "rs20": t.get("rs_20g_%"),
         "rs60": t.get("rs_60g_%"), "adx": t.get("adx"),
         "di_fark": (t["arti_di"] - t["eksi_di"]) if t.get("arti_di") is not None and t.get("eksi_di") is not None else None,
         "macd_hist_%": t["macd_hist"] / px * 100 if t.get("macd_hist") is not None else None,
         "bb_gen": t.get("bb_genislik_%"), "sikisma": 1.0 if t.get("bb_sikisma") else 0.0,
         "zirve_%": t.get("zirveye_uzaklik_%"), "dip_%": t.get("dibe_uzaklik_%"),
         "ema20_atr": (px - t["ema20"]) / atr if t.get("ema20") and atr else None,
         "perf1": t.get("perf_1g_%"), "perf5": t.get("perf_5g_%"), "perf20": t.get("perf_20g_%"),
         "log_hacim": math.log10(max(t["islem_hacmi_tl"], 1)) if t.get("islem_hacmi_tl") else None,
         "kilitli": 1.0 if t.get("son_gun_kilitli") else 0.0,
         "trend_yuk": 1.0 if str(t.get("trend") or "").startswith("Yükseliş") else 0.0,
         "trend_dus": 1.0 if t.get("trend") == "Düşüş" else 0.0,
         "risk_orta": 1.0 if risk == "orta" else 0.0,
         **{"tur_" + k: 1.0 if plan["tur"] == k else 0.0 for k in TURLER}, **mk}
    return f


# ---------------------------------------------------------------- haber girdileri (yapay zekâsız, KAP konu başlığından)
# 1. aşama (2026-11-15, kullanıcı: "Yalnız 1'e devam"): haberin İÇERİĞİ okunmaz; yalnız KAP bildiriminin konusu ve
# zamanı. Haberin yönü/gücü (yapay zekâ skoru) 2. aşamaya bırakıldı.
NOISE = ("Devre Kesici", "Pay Dışında Sermaye Piyasası Aracı", "Şirket Genel Bilgi Formu", "Faaliyet Raporu",
         "Sorumluluk Beyanı", "Kurumsal Yönetim", "Katılım Finansı", "İzahname", "İhraç Tavanı", "Varant",
         "BISTECH", "Bağımsız Denetim", "Sürdürülebilirlik", "Fon ", "Borçlanma Aracı")
KATEGORI = {"h_is": ("Yeni İş İlişkisi", "Sözleşme", "İhale"), "h_geri_alim": ("Geri Alın",),
            "h_pay_alim": ("Pay Alım Satım",), "h_sermaye": ("Sermaye Artırımı", "Bedelsiz"),
            "h_finansal": ("Finansal Rapor",), "h_kar_payi": ("Kar Payı", "Kâr Payı"),
            "h_ozel": ("Özel Durum Açıklaması (Genel)",), "h_olagan": ("Olağan Dışı",),
            "h_genel_kurul": ("Genel Kurul",)}
HABER_GUN = 5                    # sinyal gününden önceki 5 takvim günü (~3 işlem günü)


def news_features(items: Iterable[Tuple[str, str]], signal_day: str) -> Dict[str, float]:
    """items: (yayın zamanı 'YYYY-MM-DDTHH:MM:SS' TR saati, KAP konusu) — bu hissenin KAP bildirimleri.
    Yalnız sinyal günü 18:00'e kadar yayımlananlar sayılır (akşam analizi 18:20'de; geleceği görme yok)."""
    d = date.fromisoformat(signal_day)
    end = signal_day + "T18:00:00"
    w0 = (d - timedelta(days=HABER_GUN)).isoformat() + "T18:00:00"
    m0 = (d - timedelta(days=30)).isoformat() + "T18:00:00"
    f = {k: 0.0 for k in KATEGORI}
    f.update(h_say=0.0, h_say30=0.0, h_devre=0.0, h_gun=30.0)
    for ts, subj in items:
        ts, subj = str(ts)[:19], subj or ""
        if not (m0 < ts <= end):
            continue
        if "Devre Kesici" in subj:
            if ts > w0:
                f["h_devre"] = 1.0
            continue
        if any(n in subj for n in NOISE):
            continue
        f["h_say30"] += 1
        f["h_gun"] = min(f["h_gun"], float((d - date.fromisoformat(ts[:10])).days))
        if ts > w0:
            f["h_say"] += 1
            for k, keys in KATEGORI.items():
                if any(x in subj for x in keys):
                    f[k] = 1.0
    f["h_var"] = 1.0 if f["h_say"] else 0.0
    f["h_say"] = math.log1p(min(f["h_say"], 10))
    f["h_say30"] = math.log1p(f["h_say30"])
    return f


def news_items(conn, ticker: str, signal_day: str) -> List[Tuple[str, str]]:
    """Canlı veritabanından bu hissenin son 31 günlük KAP bildirimleri (news tablosu; analiz edilmiş/edilmemiş hepsi)."""
    since = (date.fromisoformat(signal_day) - timedelta(days=31)).isoformat()
    rows = conn.execute("SELECT published_at, subject FROM news WHERE source='kap' AND published_at>=? AND "
                        "(','||candidates||',') LIKE ?", (since, f"%,{ticker},%")).fetchall()
    return [(r[0], r[1]) for r in rows]


# ---------------------------------------------------------------- model dosyası ve tahmin
_CACHE: Dict[str, Dict] = {}


def load(name: str = DEFAULT) -> Optional[Dict]:
    if name not in _CACHE:
        try:
            _CACHE[name] = json.loads((MODEL_DIR / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return _CACHE[name]


def _table_key(f: Dict, tb: Dict) -> str:
    tur = next((k for k in TURLER if f.get("tur_" + k)), TURLER[1])
    trend = "Yük" if f.get("trend_yuk") else ("Düş" if f.get("trend_dus") else "Yat")
    atr = f.get("atr_%") if f.get("atr_%") is not None else tb["atr_ortanca"]
    rsi = f.get("rsi") if f.get("rsi") is not None else 55.0
    a = sum(atr >= e for e in tb["atr_sinir"])          # numpy.digitize ile aynı: sınıra eşitse üst dilim
    r = sum(rsi >= e for e in (45, 70))
    return f"{tur}|{trend}|a{a}|r{r}"


def table_prob(f: Dict, tb: Dict) -> float:
    """Benzer durumlar tablosu: senaryo türü × trend × oynaklık dilimi × RSI bandı grubunun geçmiş TP1 oranı
    (küçük gruplar senaryo türü oranına doğru büzülmüş)."""
    k = _table_key(f, tb)
    if k in tb["oran"]:
        return tb["oran"][k]
    return tb["tur_orani"].get(k.split("|")[0], tb["genel"])


def logit_prob(f: Dict, lg: Dict) -> float:
    z = lg["sabit"]
    for i, k in enumerate(lg["girdiler"]):
        v = f.get(k)
        v = lg["ortanca"][i] if v is None else v
        v = min(max(v, lg["alt"][i]), lg["ust"][i])
        z += lg["agirlik"][i] * (v - lg["ort"][i]) / lg["sd"][i]
    return 1 / (1 + math.exp(-z))


def predict(f: Dict, m: Optional[Dict] = None) -> Optional[float]:
    """TP1'in SL'den önce görülme olasılığı (0–1) = (tablo + sade lojistik) / 2. Model dosyası yoksa None."""
    m = m or load()
    if not m:
        return None
    return (table_prob(f, m["tablo"]) + logit_prob(f, m["lojistik"])) / 2


def similar(f: Dict, m: Optional[Dict] = None) -> Optional[Dict]:
    """Kartta gösterilecek açıklama: benzer geçmiş durum sayısı ve gerçekleşen oranı."""
    m = m or load()
    if not m:
        return None
    tb = m["tablo"]
    k = _table_key(f, tb)
    return {"grup": k, "n": int(tb["sayi"].get(k, 0)), "gercek": tb["ham"].get(k)}


def band(p: Optional[float], m: Optional[Dict] = None) -> Optional[str]:
    """Olasılığı eğitim dağılımına göre üç banda ayırır: "düşük" / "orta" / "yüksek" (alt/üst %20 sınırları)."""
    m = m or load()
    if p is None or not m:
        return None
    lo, hi = m["bantlar"]
    return "düşük" if p < lo else ("yüksek" if p >= hi else "orta")


# ---------------------------------------------------------------- canlı: kayıtlı bir plan için tek çağrı
def _window(conn, ticker: str, upto: str) -> List[dict]:
    rows = conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND date<=? "
                        "ORDER BY date DESC LIMIT ?", (ticker, upto, WIN)).fetchall()
    return [dict(zip(("date", "open", "high", "low", "close", "volume"), tuple(r))) for r in reversed(rows)]


def plan_features(conn, plan: Dict) -> Optional[Dict[str, Optional[float]]]:
    """plan: hazır fırsat (ticker, signal_day, tur, giris, sl, tp1, rr1, risk). Eğitimle AYNI pencere (son 250 gün,
    endeks de 250 gün) ve aynı fonksiyonlar. Haber girdileri de eklenir (tp1_v1 kullanmaz; sonraki sürümler için).
    Fiyat geçmişi yetersizse None."""
    from . import ready
    day = plan["signal_day"]
    bars = _window(conn, plan["ticker"], day)
    if not bars or bars[-1]["date"] != day:
        return None
    bench = _window(conn, technical.BENCHMARK, day)
    t = technical.analyze(bars, date.fromisoformat(day), bench or None)
    if not t or not t.get("atr"):
        return None
    f = features(t, plan, ready.tech_score(t), plan.get("risk") or "orta", market_features(bench))
    f.update(news_features(news_items(conn, plan["ticker"], day), day))
    return f


def plan_probability(conn, plan: Dict, m: Optional[Dict] = None) -> Optional[Dict]:
    """{"olasilik", "bant", "benzer": {"n", "gercek"}, "surum"} — yalnız bilgi; hesaplanamazsa None."""
    m = m or load()
    f = plan_features(conn, plan) if m else None
    if not f:
        return None
    p = predict(f, m)
    return {"olasilik": p, "bant": band(p, m), "benzer": similar(f, m), "surum": m.get("surum")}


# ---------------------------------------------------------------- gizli kaydın ölçümü (canlı doğrulama)
def _auc(y: List[int], p: List[float]) -> Optional[float]:
    pos = [b for a, b in zip(y, p) if a]
    neg = [b for a, b in zip(y, p) if not a]
    if not pos or not neg:
        return None
    wins = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def live_check(conn, min_n: int = 30) -> Dict:
    """Kapanmış hazır fırsatlarda öneri anındaki model olasılığı (model_json) ile gerçek sonuç (TP1 SL'den önce görüldü
    mü). Yalnız bilgi; panelde gösterilmez. n < min_n iken isabet (AUC) hesaplanmaz (az örnekte yanıltıcı)."""
    rows = conn.execute("SELECT model_json, sonuc_json, kaynak FROM hazir_firsat WHERE durum='kapandi' AND "
                        "model_json IS NOT NULL").fetchall()
    ys, ps, bands = [], [], {}
    for mj, sj, _k in rows:
        try:
            m, s = json.loads(mj), json.loads(sj or "{}")
        except ValueError:
            continue
        if m.get("olasilik") is None:
            continue
        y = 1 if (s.get("tp1_goruldu") or s.get("sonuc") == "TP2") else 0
        ys.append(y)
        ps.append(float(m["olasilik"]))
        b = bands.setdefault(m.get("bant") or "?", [0, 0])
        b[0] += 1
        b[1] += y
    n = len(ys)
    out = {"kapanan": n, "bantlar": {k: {"n": v[0], "gercek_%": round(100 * v[1] / v[0], 1)} for k, v in bands.items()}}
    if n:
        out.update(ort_tahmin_pct=round(100 * sum(ps) / n, 1), gercek_pct=round(100 * sum(ys) / n, 1),
                   brier=round(sum((p - y) ** 2 for p, y in zip(ps, ys)) / n, 4))
    out["auc"] = round(_auc(ys, ps), 3) if n >= min_n and _auc(ys, ps) is not None else None
    if n < min_n:
        out["not"] = f"{n} kapanan öneri: en az {min_n} olmadan isabet hesaplanmaz"
    return out
