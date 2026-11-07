"""Teknik analiz göstergeleri (2026-11-07).

Fiyat verisinden KODLA hesaplanır; yapay zekâ kullanılmaz, kredi harcamaz. Haber skoruna KARIŞTIRILMAZ:
teknik görünüm ayrı bir bilgi olarak gösterilir (skora katmak geçmiş veriyle test edilmeden yapılmamalı).
Fiyatlar yfinance'tan, gecikmelidir.
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config


def _sma(values: List[float], n: int) -> Optional[float]:
    return sum(values[-n:]) / n if len(values) >= n else None


def _ema_series(values: List[float], n: int) -> List[float]:
    k = 2 / (n + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes: List[float], n: int = 14) -> Optional[float]:
    """Wilder RSI. 70 üstü "aşırı alım", 30 altı "aşırı satım" bölgesi kabul edilir."""
    if len(closes) <= n:
        return None
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    avg_g, avg_l = sum(gains[:n]) / n, sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        avg_g = (avg_g * (n - 1) + g) / n
        avg_l = (avg_l * (n - 1) + l) / n
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    return 100 - 100 / (1 + avg_g / avg_l)


def macd(closes: List[float]):
    """(MACD, sinyal, histogram) — 12/26/9. Yeterli veri yoksa None."""
    if len(closes) < 35:
        return None
    fast, slow = _ema_series(closes, 12), _ema_series(closes, 26)
    line = [f - s for f, s in zip(fast, slow)]
    signal = _ema_series(line, 9)  # standart: sinyal = MACD çizgisinin tüm seri üzerinde 9 günlük EMA'sı
    return line[-1], signal[-1], line[-1] - signal[-1]


def atr(bars: List[dict], n: int = 14) -> Optional[float]:
    """Wilder ATR (standart): ilk değer ilk n gerçek aralığın ortalaması, sonra (önceki×(n−1)+TR)/n."""
    if len(bars) <= n:
        return None
    trs = []
    for prev, cur in zip(bars[:-1], bars[1:]):
        h, l = cur.get("high") or cur["close"], cur.get("low") or cur["close"]
        trs.append(max(h - l, abs(h - prev["close"]), abs(l - prev["close"])))
    value = sum(trs[:n]) / n
    for tr in trs[n:]:
        value = (value * (n - 1) + tr) / n
    return value


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or not b else (a / b - 1) * 100


DAILY_LIMIT = 0.105      # BIST pay piyasasında günlük fiyat sınırı ±%10; üstü düzeltilmemiş bölünme/veri hatası şüphesi
STALE_BUSINESS_DAYS = 3  # son fiyat bundan eski iş günü ise "güncel değil"
GAP_DAYS = 10            # iki fiyat günü arasında bundan uzun boşluk (bayram tatilleri ~9 güne kadar olabilir)


def _business_days_between(a: date, b: date) -> int:
    days, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def data_checks(bars: List[dict], today: Optional[date] = None):
    """(uyarılar, kritik_mi). Kritik sorunda SL/TP senaryosu üretilmez; gösterge yine gösterilir."""
    warnings, critical = [], False
    today = today or datetime.now(config.TR_TZ).date()
    last_day = date.fromisoformat(bars[-1]["date"])
    stale = _business_days_between(last_day, today)
    if stale > STALE_BUSINESS_DAYS:
        warnings.append(f"Fiyat verisi güncel değil: son fiyat {bars[-1]['date']} ({stale} iş günü önce)")
        critical = stale > 2 * STALE_BUSINESS_DAYS
    recent60 = bars[-61:]
    for prev, cur in zip(recent60[:-1], recent60[1:]):
        gap = (date.fromisoformat(cur["date"]) - date.fromisoformat(prev["date"])).days
        if gap > GAP_DAYS:
            warnings.append(f"Fiyat serisinde {gap} günlük boşluk ({prev['date']} → {cur['date']}): işlem durması/veri eksiği olabilir")
    for i, (prev, cur) in enumerate(zip(bars[-253:-1], bars[-252:])):
        change = cur["close"] / prev["close"] - 1 if prev["close"] else 0
        if abs(change) > DAILY_LIMIT:
            recent = i >= len(bars[-252:]) - 60
            warnings.append(f"{cur['date']} tarihinde %{change * 100:+.0f} sıçrama (günlük sınır ±%10): düzeltilmemiş "
                            "bölünme/bedelsiz ya da veri hatası olabilir" + ("; son 60 günde, seviyeler güvenilmez" if recent else ""))
            critical = critical or recent
    last20 = bars[-20:]
    # Hacim bilgisi olmayan seriler (ör. pilot fiyatları) bu kontrole girmez.
    zero_vol = sum(1 for b in last20 if b.get("volume") is not None and not b["volume"])
    if zero_vol >= 3:
        warnings.append(f"Son 20 günün {zero_vol}'inde hacim yok: hisse sığ, fiyatlar yanıltıcı olabilir")
    flat = sum(1 for b in last20 if b.get("high") and b.get("low") and b["high"] == b["low"])
    if flat >= 3:
        warnings.append(f"Son 20 günün {flat}'inde fiyat gün boyu tek seviyede (tavan/taban kilidi ya da işlem azlığı)")
    return warnings, critical


def analyze(bars: List[dict], today: Optional[date] = None) -> Optional[Dict]:
    """bars: tarihe göre sıralı [{"date","open","high","low","close","volume"}]. En az 30 gün gerekir."""
    bars = [b for b in bars if b.get("close")]
    if len(bars) < 30:
        return None
    data_warnings, data_critical = data_checks(bars, today)
    closes = [b["close"] for b in bars]
    last = closes[-1]
    sma20, sma50, sma200 = _sma(closes, 20), _sma(closes, 50), _sma(closes, 200)
    r = rsi(closes)
    m = macd(closes)
    vols = [b.get("volume") or 0 for b in bars]
    vol_ratio = (sum(vols[-5:]) / 5) / (sum(vols[-25:-5]) / 20) if len(vols) >= 25 and sum(vols[-25:-5]) else None
    window = bars[-252:]
    highs = [b.get("high") or b["close"] for b in window]
    lows = [b.get("low") or b["close"] for b in window]
    recent = bars[-20:]
    support = min(b.get("low") or b["close"] for b in recent)
    resistance = max(b.get("high") or b["close"] for b in recent)
    mid = bars[-60:]  # daha uzak destek/direnç (hedef ve zarar durdur için ikinci seviye)
    support60 = min(b.get("low") or b["close"] for b in mid)
    resistance60 = max(b.get("high") or b["close"] for b in mid)
    # Oynaklık: Wilder ATR(14), fiyatın yüzdesi (en yüksek/en düşük yoksa kapanış farkı).
    a = atr(bars)
    atr_pct = a / last * 100 if a else None

    if sma50 and sma200 and last > sma50 > sma200:
        trend = "Yükseliş"
    elif sma50 and sma200 and last < sma50 < sma200:
        trend = "Düşüş"
    elif sma50 and not sma200:
        trend = "Yükseliş" if last > sma50 and (sma20 or 0) > sma50 else ("Düşüş" if last < sma50 and (sma20 or 0) < sma50 else "Yatay")
    else:
        trend = "Yatay / kararsız"
    notes = []
    if r is not None and r >= 70:
        notes.append("RSI aşırı alım bölgesinde")
    elif r is not None and r <= 30:
        notes.append("RSI aşırı satım bölgesinde")
    if m is not None:
        notes.append("MACD sinyalin üstünde (olumlu ivme)" if m[2] > 0 else "MACD sinyalin altında (zayıf ivme)")
    if vol_ratio and vol_ratio >= 1.5:
        notes.append(f"hacim son 5 günde ortalamanın {vol_ratio:.1f} katı")
    return {
        "son_fiyat": last, "tarih": bars[-1]["date"], "trend": trend,
        "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "fiyat_sma50_%": _pct(last, sma50), "fiyat_sma200_%": _pct(last, sma200),
        "rsi14": r, "macd": m[0] if m else None, "macd_sinyal": m[1] if m else None,
        "macd_hist": m[2] if m else None, "hacim_orani": vol_ratio,
        "zirve_52h": max(highs), "dip_52h": min(lows),
        "zirveye_uzaklik_%": _pct(last, max(highs)), "dibe_uzaklik_%": _pct(last, min(lows)),
        "destek_20g": support, "direnc_20g": resistance, "destek_60g": support60, "direnc_60g": resistance60,
        "atr_%": atr_pct,
        "perf_1g_%": _pct(last, closes[-2]) if len(closes) >= 2 else None,
        "perf_5g_%": _pct(last, closes[-6]) if len(closes) >= 6 else None,
        "perf_20g_%": _pct(last, closes[-21]) if len(closes) >= 21 else None,
        "gun_sayisi": len(bars), "notlar": notes,
        "veri_uyarilari": data_warnings, "veri_kritik": data_critical,
        # Son gün açılış=en yüksek=en düşük=kapanış: tavan/taban kilidi olabilir (emir gerçekleşmeyebilir).
        "son_gun_kilitli": bool(bars[-1].get("high") and bars[-1].get("low")
                                and bars[-1]["high"] == bars[-1]["low"] == bars[-1]["close"]),
    }


# Fiyat serisini bozabilen kurumsal olaylar (bölünme/bedelsiz/temettü düzeltmeleri).
EVENT_TYPES = ("bedelsiz_sermaye_artirimi", "bedelli_sermaye_artirimi", "temettu")
EVENT_SUBJECTS = ("Sermaye Artırımı", "Kar Payı", "Bölünme")


def for_ticker(conn, ticker: str, today: Optional[date] = None) -> Optional[Dict]:
    rows = conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? ORDER BY date",
                        (ticker,)).fetchall()
    t = analyze([dict(r) for r in rows], today)
    if t is None:
        return None
    since = (date.fromisoformat(t["tarih"]) - timedelta(days=60)).isoformat()
    events = conn.execute(
        "SELECT DISTINCT substr(n.published_at,1,10) d, COALESCE(n.subject, i.event_type) s FROM news n "
        "LEFT JOIN impacts i ON i.news_id=n.id AND i.ticker=? "
        "WHERE (','||n.candidates||',') LIKE ? AND n.published_at>=? AND (i.event_type IN (%s) OR %s) ORDER BY d DESC"
        % (",".join("?" * len(EVENT_TYPES)), " OR ".join("n.subject LIKE ?" for _ in EVENT_SUBJECTS)),
        (ticker, f"%,{ticker},%", since, *EVENT_TYPES, *[f"%{s}%" for s in EVENT_SUBJECTS])).fetchall()
    for e in events[:3]:
        t["veri_uyarilari"].append(f"{e['d']} kurumsal olay ({e['s']}): fiyat düzeltmesi destek/direnç ve "
                                   "ortalamaları bozmuş olabilir")
    return t


TREND_ICON = {"Yükseliş": "↗", "Düşüş": "↘"}


def short_label(t: Optional[Dict]) -> str:
    if not t:
        return "teknik veri yok"
    return f"teknik {TREND_ICON.get(t['trend'], '→')} {t['trend'].lower()}"
