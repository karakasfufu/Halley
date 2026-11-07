"""İşlem senaryosu: risk faktörleri, zarar durdur (SL), kâr al (TP), tahmini vade ve açıklama (2026-11-07).

Tamamen KODLA hesaplanır (yapay zekâ yok, kredi harcamaz). Kurallar yaygın teknik yaklaşımlardır ve geçmiş veriyle
HENÜZ TEST EDİLMEDİ; ekranda "tahmini" olarak gösterilir. Yalnızca olumlu haberli hisseler için alım senaryosu üretilir
(açığa satış yok). Metin bilgi/senaryo dilindedir; yatırım tavsiyesi değildir, karar kullanıcıya aittir.
"""
import math
from typing import Dict, List, Optional

from . import entries

MIN_RR = 2.0              # hedef/risk oranı en az 1:2
ATR_STOP_MULT = 2.0       # destek uygun değilse SL = fiyat − 2 × ATR
MAX_STOP_PCT = 15.0       # SL fiyatın %15'inden daha aşağıda olamaz
DAILY_PROGRESS = 0.5      # vade tahmini: fiyatın hedefe günde ~0,5 ATR ilerlediği varsayımı (kaba)
HORIZON = {"kisa": (1, 5), "orta": (5, 20), "uzun": (20, 60)}  # işlem günü
# Parça A3 (2026-11-07). Eşikler gerçek veriyle seçildi, sonuca göre ayarlanmadı:
# - 630 işlem gören BIST hissesinde 20 günlük ort. işlem hacmi: %8'i < 2 mn TL, %24'ü < 10 mn TL, medyan 28 mn TL.
# - 44 hissede rastgele günlerin %1–6'sında 1–3 günde ≥ +2 ATR, %3'ünde 5 günde ≥ +3 ATR yükseliş: olağandışı hareket.
LIQ_MIN_TL = 2e6        # altında senaryo üretilmez (100 bin TL emir günlük işlemin %5'i; fiyatı kendisi oynatır)
LIQ_WARN_TL = 10e6      # altında "düşük likidite" (BIST'in en düşük dörtte biri)
PRICED_IN_ATR = 2.0     # haberden bu yana ≥ 2 ATR yükseliş → etkinin önemli kısmı fiyatlanmış olabilir
PRE_MOVE_ATR = 3.0      # haberden önceki 5 günde ≥ 3 ATR yükseliş → beklenti/sızıntı


def risk_factors(t: Dict, news: Dict) -> List[str]:
    """Okunur risk maddeleri. news: {"score", "confidence", "flags", "direction"}."""
    out = []
    if t.get("atr_%") is not None and t["atr_%"] >= 5:
        out.append(f"Yüksek oynaklık: günlük ortalama hareket %{t['atr_%']:.1f}")
    if t.get("rsi14") is not None and t["rsi14"] >= 70:
        out.append(f"RSI {t['rsi14']:.0f}: aşırı alım bölgesi, kısa vadeli geri çekilme riski")
    if t.get("fiyat_sma50_%") is not None and t["fiyat_sma50_%"] >= 15:
        out.append(f"Fiyat 50 günlük ortalamanın %{t['fiyat_sma50_%']:.0f} üstünde: hızlı yükselmiş")
    if t.get("hacim_orani") is not None and t["hacim_orani"] < 0.7:
        out.append("Hacim zayıf: son günlerde ilgi azalmış, emir gerçekleşmesi zorlaşabilir")
    if news.get("direction", 1) > 0 and t.get("trend") == "Düşüş":
        out.append("Haber olumlu ama teknik trend düşüşte: piyasa haberi henüz fiyatlamamış ya da şüpheyle karşılamış olabilir")
    if t.get("macd_hist") is not None and t["macd_hist"] < 0:
        out.append("MACD ivmesi zayıf")
    if news.get("confidence") is not None and news["confidence"] < 0.6:
        out.append(f"Haber analizinin güveni düşük (%{news['confidence'] * 100:.0f})")
    if any(f in (news.get("flags") or "") for f in ("çelişkili", "etki belirsiz", "tek görüş", "yorumsuz")):
        out.append("Yapay zekâ analizleri tam uzlaşmadı (⚠️ kontrol et): haberi kendiniz okuyun")
    if t.get("son_gun_kilitli"):
        out.append("Son işlem günü tek fiyatla geçti (tavan/taban kilidi olabilir): emir gerçekleşmeyebilir")
    if t.get("gun_sayisi", 0) < 200:
        out.append("Fiyat geçmişi 200 günden kısa: uzun vadeli trend hesaplanamadı")
    vol = t.get("islem_hacmi_tl")
    if vol is not None and LIQ_MIN_TL <= vol < LIQ_WARN_TL:
        out.append(f"Düşük likidite: günlük ortalama işlem hacmi {vol / 1e6:.1f} milyon TL (BIST hisselerinin en düşük "
                   "dörtte birinde); emir gerçekleşmesi zorlaşabilir, alış-satış farkı büyük olabilir")
    move = news.get("hareket") or {}
    if news.get("direction", 1) > 0 and move.get("sonra_atr") is not None and move["sonra_atr"] >= PRICED_IN_ATR:
        out.append(f"Haberden bu yana fiyat %{move['sonra_%']:.1f} yükseldi ({move['sonra_atr']:.1f} günlük ortalama "
                   "hareket): haberin etkisinin önemli kısmı fiyata yansımış olabilir")
    if news.get("direction", 1) > 0 and move.get("sonra_atr") is not None and move["sonra_atr"] <= -PRICED_IN_ATR:
        out.append(f"Haber olumlu ama fiyat haberden bu yana %{abs(move['sonra_%']):.1f} düştü ({move['sonra_atr']:.1f} "
                   "günlük ortalama hareket): piyasa haberi olumsuz karşılamış ya da başka bir gelişme olabilir; haberi ve "
                   "gerekçeyi kendiniz kontrol edin")
    pre, atr_pct = move.get("once_5g_%"), t.get("atr_%")
    if news.get("direction", 1) > 0 and pre is not None and atr_pct and pre / atr_pct >= PRE_MOVE_ATR:
        out.append(f"Haberden önceki 5 işlem gününde fiyat %{pre:.1f} yükselmiş ({pre / atr_pct:.1f} günlük ortalama "
                   "hareket): beklenti ya da bilgi sızıntısı; haber kısmen önceden fiyatlanmış olabilir")
    return out


def _horizon(persistence: str, entry: float, tp: float, atr: Optional[float]):
    """Haberin kalıcılığına göre temel aralık; hedefe uzaklık (ATR cinsinden) bunu uzatabilir."""
    base_lo, base_hi = HORIZON.get(persistence, HORIZON["orta"])
    if not atr:
        return base_lo, base_hi
    need = max(1, math.ceil((tp - entry) / (DAILY_PROGRESS * atr)))
    return max(base_lo, min(need, base_hi)), max(base_hi, need)


def plan(t: Optional[Dict], news: Dict) -> Dict:
    """news: {"score","direction","confidence","flags","persistence","reason","summary"}.

    Dönüş: {"durum": "senaryo"|"yok", "neden_yok"?, "giris","sl","tp","rr","vade","risk_seviyesi","riskler","aciklama"}.
    """
    if not t:
        return {"durum": "yok", "neden_yok": "Teknik veri yok (en az 30 işlem günü fiyat gerekir).", "riskler": []}
    risks = risk_factors(t, news) + list(t.get("veri_uyarilari") or [])
    if t.get("veri_kritik"):
        # Eski fiyat ya da son 60 günde sınırı aşan sıçrama: seviyeler güvenilmez, senaryo üretme.
        return {"durum": "yok", "neden_yok": "Fiyat verisinde kritik sorun var; SL/TP seviyeleri güvenilir "
                "hesaplanamaz. Ayrıntı aşağıdaki veri uyarılarında.", "riskler": risks}
    vol = t.get("islem_hacmi_tl")
    if vol is not None and vol < LIQ_MIN_TL:
        return {"durum": "yok", "neden_yok": f"Likidite çok düşük: günlük ortalama işlem hacmi {vol / 1e6:.2f} milyon TL "
                "(BIST'in en düşük %8'i). Emir gerçekleşmesi ve fiyatlar güvenilmez; senaryo üretilmedi.",
                "riskler": risks}
    if news.get("direction", 0) <= 0 or news.get("score", 0) < 1.5:
        return {"durum": "yok", "neden_yok": "Olumlu bir haber sinyali olmadığı için alım senaryosu üretilmedi.",
                "riskler": risks}
    entry = t["son_fiyat"]
    atr = (t["atr_%"] or 0) * entry / 100 or None
    support, resistance = t.get("destek_20g"), t.get("direnc_20g")
    # SL: destek uygun mesafedeyse hemen altı, değilse fiyat − 2 ATR. Fiyatın %15 altına inmez.
    if atr and support and atr <= entry - support <= 3 * atr:
        sl, sl_basis = support * 0.99, "20 günlük desteğin hemen altı"
    elif atr:
        sl, sl_basis = entry - ATR_STOP_MULT * atr, "fiyat − 2 × günlük ortalama hareket"
    else:
        sl, sl_basis = entry * 0.93, "sabit %7 (oynaklık hesaplanamadı)"
    sl = max(sl, entry * (1 - MAX_STOP_PCT / 100))
    risk = entry - sl
    target_rr = entry + MIN_RR * risk
    notes = []
    # Hedef (temkinli): fiyatın üstündeki direnç seviyeleri (20 gün, 60 gün, 52 hafta) içinden, fiyata 1 günlük
    # ortalama hareketten (1 ATR) daha yakın olanlar gürültü sayılır; hedef ondan sonraki İLK gerçek dirençtir.
    # Daha uzak seviyelere atlanmaz (aradaki direnç risk/getiriyi olduğundan iyi gösterirdi).
    noise = entry + (atr or entry * 0.01)
    all_levels = sorted({(lvl, name) for lvl, name in ((resistance, "20 günlük direnç"),
                                                      (t.get("direnc_60g"), "60 günlük direnç"),
                                                      (t.get("zirve_52h"), "52 haftalık zirve"))
                         if lvl and lvl > entry * 1.005})
    # Yalnızca kısa vadeli (20 günlük) seviye gürültü sayılabilir; 60 günlük direnç ve 52 haftalık zirve güçlü
    # seviyelerdir, fiyata ne kadar yakın olursa olsun hedef olarak dikkate alınır.
    near = [name for lvl, name in all_levels if lvl < noise and name == "20 günlük direnç"]
    real = [(lvl, name) for lvl, name in all_levels if not (lvl < noise and name == "20 günlük direnç")]
    if near:
        notes.append(f"Fiyatın hemen üstünde (1 günlük hareket içinde) küçük direnç var: {', '.join(near)}")
    if real:
        tp, tp_basis = real[0]
    else:
        tp, tp_basis = target_rr, "risk/getiri 1:2 hedefi (üstte belirgin direnç yok)"
    if t.get("zirve_52h") and tp > t["zirve_52h"]:
        notes.append("Hedef 52 haftalık zirvenin üstünde: geçmiş direnç bölgesi aşılmalı")
    rr = (tp - entry) / risk if risk > 0 else None
    unfavorable = rr is not None and rr < 1
    if unfavorable:
        risks.append(f"Risk/getiri elverişsiz (1:{rr:.1f}): olası zarar olası kazançtan büyük")
    elif rr is not None and rr < MIN_RR:
        risks.append(f"Risk/getiri zayıf (1:{rr:.1f})")
    lo, hi = _horizon(news.get("persistence", "orta"), entry, tp, atr)
    # Ağırlıklı risk puanı: elverişsiz risk/getiri ve haber–trend çelişkisi daha ağır sayılır.
    points = sum(4 if r.startswith("Risk/getiri elverişsiz") else  # elverişsiz → en az "yüksek"
                 2 if r.startswith(("Haber olumlu ama teknik trend", "Risk/getiri zayıf", "Düşük likidite",
                                    "Haberden bu yana", "Haber olumlu ama fiyat")) else 1 for r in risks)
    level = "düşük" if points <= 1 else ("orta" if points <= 3 else "yüksek")
    pct = lambda x: (x / entry - 1) * 100
    tech_line = (f"Teknik trend {t['trend'].lower()}, RSI {t['rsi14']:.0f}" if t.get("rsi14") is not None
                 else f"Teknik trend {t['trend'].lower()}")
    if t.get("macd_hist") is not None:
        tech_line += ", MACD ivmesi " + ("olumlu" if t["macd_hist"] > 0 else "zayıf")
    explanation = (
        f"Neden olumlu görünüyor: {(news.get('reason') or news.get('summary') or 'olumlu haber').strip().rstrip('.')}. "
        f"{tech_line}. "
        f"Senaryo: referans {entry:.2f} TL; zarar durdur {sl:.2f} TL ({pct(sl):+.1f}%), "
        f"kâr al {tp:.2f} TL ({pct(tp):+.1f}%), risk/getiri 1:{rr:.1f}; tahmini {lo}–{hi} işlem günü. "
        f"Risk seviyesi {level}" + (f" ({len(risks)} risk maddesi)." if risks else ".")
        + (" Mevcut seviyelerde senaryo elverişsiz görünüyor." if unfavorable else "")
        + " Bu bir senaryodur, yatırım tavsiyesi değildir; seviyeler geçmiş veriyle henüz test edilmedi."
    )
    return {"durum": "senaryo", "elverissiz": unfavorable, "giris": entry, "sl": sl, "sl_dayanak": sl_basis, "tp": tp, "tp_dayanak": tp_basis,
            "sl_%": pct(sl), "tp_%": pct(tp), "rr": rr, "vade": (lo, hi), "risk_seviyesi": level,
            "riskler": risks, "notlar": notes, "aciklama": explanation,
            # Parça A2: mevcut fiyattan girişin yanında üç koşullu giriş senaryosu (kırılım/geri çekilme/destek).
            "girisler": entries.scenarios(t)}


def opportunity_summary(plans: Dict[str, Dict]) -> Dict:
    """plans: {hisse: plan()} (olumlu haber alanlar). Uygun = en az bir giriş senaryosu elverişsiz değil.
    Dönüş: {"uygun": [(hisse, senaryo adı, risk seviyesi)], "nedenler": {neden: sayı}}."""
    ok, reasons = [], {}
    for ticker, p in plans.items():
        g = p.get("girisler") or {}
        best = next((s for s in g.get("senaryolar", []) if s["tur"] == g.get("en_uygun")), None)
        if p.get("durum") == "senaryo" and best:
            ok.append((ticker, best["ad"], p.get("risk_seviyesi", "")))
            continue
        if p.get("durum") != "senaryo":
            text = p.get("neden_yok", "")
            key = ("likidite çok düşük" if text.startswith("Likidite") else
                   "fiyat verisi sorunlu/yetersiz" if text.startswith(("Fiyat verisinde", "Teknik veri yok")) else
                   "haber sinyali yeterince güçlü değil")
        else:
            key = "giriş senaryoları uygun değil (risk/getiri elverişsiz ya da koşul yok)"
        reasons[key] = reasons.get(key, 0) + 1
    order = {"yüksek": 2, "orta": 1, "düşük": 0}
    ok.sort(key=lambda x: order.get(x[2], 3))
    return {"uygun": ok, "nedenler": reasons}
