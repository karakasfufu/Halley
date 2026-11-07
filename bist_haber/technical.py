"""Teknik analiz göstergeleri (2026-11-07).

Fiyat verisinden KODLA hesaplanır; yapay zekâ kullanılmaz, kredi harcamaz. Haber skoruna KARIŞTIRILMAZ:
teknik görünüm ayrı bir bilgi olarak gösterilir (skora katmak geçmiş veriyle test edilmeden yapılmamalı).
Fiyatlar yfinance'tan, gecikmelidir.
"""
from typing import Dict, List, Optional


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
    signal = _ema_series(line[25:], 9)
    return line[-1], signal[-1], line[-1] - signal[-1]


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or not b else (a / b - 1) * 100


def analyze(bars: List[dict]) -> Optional[Dict]:
    """bars: tarihe göre sıralı [{"date","open","high","low","close","volume"}]. En az 30 gün gerekir."""
    bars = [b for b in bars if b.get("close")]
    if len(bars) < 30:
        return None
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
    # Oynaklık: ATR(14) fiyatın yüzdesi (en yüksek/en düşük yoksa kapanış farkı).
    trs = []
    for prev, cur in zip(bars[-15:-1], bars[-14:]):
        h, l = cur.get("high") or cur["close"], cur.get("low") or cur["close"]
        trs.append(max(h - l, abs(h - prev["close"]), abs(l - prev["close"])))
    atr_pct = (sum(trs) / len(trs)) / last * 100 if trs else None

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
        "destek_20g": support, "direnc_20g": resistance, "atr_%": atr_pct,
        "perf_1g_%": _pct(last, closes[-2]) if len(closes) >= 2 else None,
        "perf_5g_%": _pct(last, closes[-6]) if len(closes) >= 6 else None,
        "perf_20g_%": _pct(last, closes[-21]) if len(closes) >= 21 else None,
        "gun_sayisi": len(bars), "notlar": notes,
    }


def for_ticker(conn, ticker: str) -> Optional[Dict]:
    rows = conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? ORDER BY date",
                        (ticker,)).fetchall()
    return analyze([dict(r) for r in rows])


TREND_ICON = {"Yükseliş": "↗", "Düşüş": "↘"}


def short_label(t: Optional[Dict]) -> str:
    if not t:
        return "teknik veri yok"
    return f"teknik {TREND_ICON.get(t['trend'], '→')} {t['trend'].lower()}"
