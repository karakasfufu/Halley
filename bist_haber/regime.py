"""Piyasa rejimi (D aşaması, 2026-11-09) — yalnız BİLGİ: kararları değiştirmez.

Tanımlar (kayıtlı günlük fiyatlardan, yapay zekâ yok, tahmin yok):
- Trend (BIST 100): kapanış > EMA50 > EMA200 → "yükseliş"; kapanış < EMA50 < EMA200 → "düşüş"; diğerleri "kararsız".
- Oynaklık: BIST 100'ün son 20 günlük ATR'si (fiyatın %'si), son ~1 yılın günlük 20-günlük ATR% değerleri arasında hangi
  yüzdelikte: < %30 "düşük", > %70 "yüksek", arası "normal".
- Genişlik: likit hisselerin (20 gün ort. işlem hacmi ≥ 2 mn TL) yüzde kaçı kendi EMA50'sinin üstünde kapanmış.
Gün: verilen günde ya da öncesinde fiyatı olan son işlem günü (geriye dönük bilgi yok).
Bekçi her çalıştırmada rejimi karar kaydının özetine yazar → ileride "hangi rejimde hangi strateji başarılı" ölçülür.
"""
from datetime import date
from typing import Dict, List, Optional

from . import technical

BENCH = "XU100"
LIQ_MIN_TL = 2e6
LOW_PCT, HIGH_PCT = 30, 70


def _bars(conn, ticker: str, upto: str, n: int) -> List[dict]:
    return [dict(r) for r in conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND "
                                          "date<=? ORDER BY date DESC LIMIT ?", (ticker, upto, n))][::-1]


def _atr_pct_series(bars: List[dict], n: int = 20) -> List[float]:
    out = []
    for i in range(n + 1, len(bars) + 1):
        a = technical.atr(bars[i - n - 1:i], n)
        if a and bars[i - 1]["close"]:
            out.append(a / bars[i - 1]["close"] * 100)
    return out


def regime(conn, day: Optional[date] = None) -> Dict:
    day = (day or date.today()).isoformat()
    xb = _bars(conn, BENCH, day, 520)
    if len(xb) < 210:
        return {"yok": "BIST 100 için yeterli fiyat geçmişi yok (en az 210 işlem günü gerekir)."}
    closes = [b["close"] for b in xb]
    e50, e200 = technical.ema(closes, 50), technical.ema(closes, 200)
    last = closes[-1]
    trend = ("yükseliş" if last > e50 > e200 else "düşüş" if last < e50 < e200 else "kararsız")
    series = _atr_pct_series(xb[-300:])
    cur = series[-1] if series else None
    pct = 100 * sum(1 for v in series[-252:] if v <= cur) / len(series[-252:]) if series else None
    vol = None if pct is None else ("düşük" if pct < LOW_PCT else "yüksek" if pct > HIGH_PCT else "normal")
    d = xb[-1]["date"]
    above = total = 0
    tickers = [r[0] for r in conn.execute("SELECT ticker FROM prices WHERE date=? AND ticker!=?", (d, BENCH))]
    for t in tickers:
        bs = _bars(conn, t, d, 80)
        if len(bs) < 60:
            continue
        liq = sum(b["close"] * (b["volume"] or 0) for b in bs[-20:]) / 20
        if liq < LIQ_MIN_TL:
            continue
        cl = [b["close"] for b in bs]
        e = technical.ema(cl, 50)
        if e is None:
            continue
        total += 1
        above += cl[-1] > e
    out = {"gun": d, "xu100": last, "ema50": e50, "ema200": e200, "trend": trend, "atr20_%": cur,
           "oynaklik_yuzdelik": pct, "oynaklik": vol, "genislik_%": 100 * above / total if total else None,
           "genislik_hisse": total}
    out["ozet"] = summary_text(out)
    return out


def summary_text(r: Dict) -> str:
    if r.get("yok"):
        return r["yok"]
    parts = [f"BIST 100 trendi **{r['trend']}** (kapanış {r['xu100']:.0f}; EMA50 {r['ema50']:.0f}, EMA200 {r['ema200']:.0f})"]
    if r["oynaklik"]:
        parts.append(f"oynaklık **{r['oynaklik']}** (20 günlük ATR %{r['atr20_%']:.2f}; son 1 yılın %"
                     f"{r['oynaklik_yuzdelik']:.0f}'lik dilimi)")
    if r["genislik_%"] is not None:
        parts.append(f"genişlik: likit {r['genislik_hisse']} hissenin %{r['genislik_%']:.0f}'i kendi 50 günlük "
                     "ortalamasının üstünde")
    else:
        parts.append("genişlik hesaplanamadı (tüm BIST fiyatı yok — sabah analizi indirir)")
    return f"{r['gun']}: " + "; ".join(parts) + "."
