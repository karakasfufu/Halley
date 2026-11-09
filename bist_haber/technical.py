"""Teknik analiz göstergeleri (2026-11-07).

Fiyat verisinden KODLA hesaplanır; yapay zekâ kullanılmaz, kredi harcamaz. Haber skoruna KARIŞTIRILMAZ:
teknik görünüm ayrı bir bilgi olarak gösterilir (skora katmak geçmiş veriyle test edilmeden yapılmamalı).
Fiyatlar yfinance'tan, gecikmelidir.
"""
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config

BENCHMARK = "XU100"  # endekse göre güç için (fiyatlarla birlikte indirilir)


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


def ema(values: List[float], n: int) -> Optional[float]:
    """Standart EMA: ilk değer ilk n günün basit ortalaması, sonra k = 2/(n+1). Yeterli veri yoksa None."""
    if len(values) < n:
        return None
    k, value = 2 / (n + 1), sum(values[:n]) / n
    for v in values[n:]:
        value = v * k + value * (1 - k)
    return value


def _hl(b: dict):
    return (b.get("high") or b["close"]), (b.get("low") or b["close"])


def adx(bars: List[dict], n: int = 14):
    """Wilder ADX: (ADX, +DI, -DI). Trend GÜCÜ (yön değil): 20 altı zayıf, 25 üstü güçlü. En az 2n+1 gün."""
    if len(bars) < 2 * n + 1:
        return None
    trs, pdm, mdm = [], [], []
    for prev, cur in zip(bars[:-1], bars[1:]):
        (h, l), (ph, pl) = _hl(cur), _hl(prev)
        up, down = h - ph, pl - l
        pdm.append(up if up > down and up > 0 else 0.0)
        mdm.append(down if down > up and down > 0 else 0.0)
        trs.append(max(h - l, abs(h - prev["close"]), abs(l - prev["close"])))
    s_tr, s_p, s_m = sum(trs[:n]), sum(pdm[:n]), sum(mdm[:n])
    dxs, pdi, mdi = [], 0.0, 0.0
    for i in range(n - 1, len(trs)):
        if i >= n:
            s_tr, s_p, s_m = s_tr - s_tr / n + trs[i], s_p - s_p / n + pdm[i], s_m - s_m / n + mdm[i]
        pdi, mdi = (100 * s_p / s_tr, 100 * s_m / s_tr) if s_tr else (0.0, 0.0)
        dxs.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0)
    value = sum(dxs[:n]) / n
    for dx in dxs[n:]:
        value = (value * (n - 1) + dx) / n
    return value, pdi, mdi


def bollinger(closes: List[float], n: int = 20, k: float = 2.0):
    """(alt, orta, üst, bant genişliği %) — standart sapma nüfus formülüyle (ddof=0), yaygın tanım."""
    if len(closes) < n:
        return None
    w = closes[-n:]
    mid = sum(w) / n
    sd = (sum((x - mid) ** 2 for x in w) / n) ** 0.5
    return mid - k * sd, mid, mid + k * sd, (2 * k * sd / mid * 100) if mid else None


def obv_series(bars: List[dict]) -> Optional[List[float]]:
    """On-Balance Volume. Hacim bilgisi olmayan seride None."""
    if any(b.get("volume") is None for b in bars):
        return None
    out = [0.0]
    for prev, cur in zip(bars[:-1], bars[1:]):
        sign = 1 if cur["close"] > prev["close"] else (-1 if cur["close"] < prev["close"] else 0)
        out.append(out[-1] + sign * (cur["volume"] or 0))
    return out


def swing_low(bars: List[dict], lookback: int = 20, side: int = 2) -> Optional[float]:
    """Son `lookback` gündeki en yakın salınım dibi: iki yanındaki `side` günden daha düşük en düşük fiyat."""
    seg = bars[-lookback:]
    for i in range(len(seg) - side - 1, side - 1, -1):
        low = _hl(seg[i])[1]
        if all(low < _hl(seg[j])[1] for j in range(i - side, i + side + 1) if j != i):
            return low
    return None


def relative_strength(bars: List[dict], bench: Optional[List[dict]], days: int) -> Optional[float]:
    """Endekse göre güç (%): aynı tarihler arasında (1+hisse getirisi)/(1+endeks getirisi) - 1.
    Endeksin iki tarihte de fiyatı olmalı; yoksa None (tahmin edilmez)."""
    if not bench or len(bars) <= days:
        return None
    by_date = {b["date"]: b["close"] for b in bench}
    start, end = bars[-days - 1]["date"], bars[-1]["date"]
    if start not in by_date or end not in by_date or not by_date[start]:
        return None
    return ((bars[-1]["close"] / bars[-days - 1]["close"]) / (by_date[end] / by_date[start]) - 1) * 100


def news_moves(bars: List[dict], effective_day: str, atr_value: Optional[float] = None) -> Dict:
    """Haber fiyatlanmış mı? Taban = haberin etki gününden (effective_date) ÖNCEKİ son kapanış. Seans kapanışından
    sonra yayınlanan haberde etki günü ertesi iş günüdür; yayın gününün kapanışı haber öncesi sayılır.
    once_5g_% : tabanın 5 işlem günü öncesine göre değişimi (beklenti/sızıntı)
    sonra_%   : tabandan son kapanışa değişim; sonra_atr: aynı hareketin ATR cinsinden büyüklüğü."""
    base_i = max((i for i, b in enumerate(bars) if b["date"] < effective_day), default=None)
    if base_i is None:
        return {}
    base = bars[base_i]["close"]
    out = {"once_5g_%": _pct(base, bars[base_i - 5]["close"]) if base_i >= 5 else None,
           "sonra_%": None, "sonra_atr": None}
    if base_i < len(bars) - 1:
        out["sonra_%"] = _pct(bars[-1]["close"], base)
        out["sonra_atr"] = (bars[-1]["close"] - base) / atr_value if atr_value else None
    return out


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
    from .market_calendar import trading_days_between  # tatiller sayılmaz (bayram sonrası yanlış "eski" uyarısı olmasın)
    stale = trading_days_between(last_day, today)
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
    last = bars[-1]
    if last.get("high") is None or last.get("low") is None or last.get("open") is None:
        warnings.append(f"Son günün ({last['date']}) açılış/en yüksek/en düşük fiyatı eksik (gün içi yarım veri): o günün "
                        "aralığı destek/direnç ve oynaklığa girmedi; seans bitince yeniden güncelleyin")
    last20 = bars[-20:]
    # Hacim bilgisi olmayan seriler (ör. pilot fiyatları) bu kontrole girmez.
    zero_vol = sum(1 for b in last20 if b.get("volume") is not None and not b["volume"])
    if zero_vol >= 3:
        warnings.append(f"Son 20 günün {zero_vol}'inde hacim yok: hisse sığ, fiyatlar yanıltıcı olabilir")
    flat = sum(1 for b in last20 if b.get("high") and b.get("low") and b["high"] == b["low"])
    if flat >= 3:
        warnings.append(f"Son 20 günün {flat}'inde fiyat gün boyu tek seviyede (tavan/taban kilidi ya da işlem azlığı)")
    return warnings, critical


def analyze(bars: List[dict], today: Optional[date] = None, bench: Optional[List[dict]] = None) -> Optional[Dict]:
    """bars: tarihe göre sıralı [{"date","open","high","low","close","volume"}]. En az 30 gün gerekir.
    bench: XU100 barları (endekse göre güç için; yoksa o gösterge boş kalır, tahmin edilmez)."""
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
    # 2026-11-07 (kullanıcı onayı): tepki senaryosu için destek BUGÜN HARİÇ önceki günlerden. Bugünkü dip "destek"
    # sayılınca çöküş gününde tepki alımı öneriliyordu (SOKM 06.11: %-9,9, destek = günün dibi). Gerçek veri (44 hisse,
    # ~3 yıl): destek = bugünkü dip olan tepki senaryoları ort. −0,02 R / SL %70 (n=328), önceden oluşmuş destek +0,14 R
    # / SL %59 (n=648); fark anlamlı (z≈2,7).
    prior20, prior60 = bars[-21:-1], bars[-61:-1]
    prior_support = min(b.get("low") or b["close"] for b in prior20) if prior20 else None
    prior_support60 = min(b.get("low") or b["close"] for b in prior60) if prior60 else None
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
    e20, e50, e200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    ax = adx(bars)
    bb = bollinger(closes)
    # Sıkışma: bugünkü bant genişliği son 120 günün en dar %20'lik diliminde mi?
    widths = [bollinger(closes[:i])[3] for i in range(max(20, len(closes) - 119), len(closes) + 1)] if len(closes) >= 60 else []
    squeeze = bool(widths and bb and bb[3] is not None and bb[3] <= sorted(widths)[len(widths) // 5])
    has_volume = all(b.get("volume") is not None for b in bars[-21:]) and any(b.get("volume") for b in bars[-21:])
    obv = obv_series(bars[-21:]) if has_volume else None
    obv_trend = None if not obv else ("artıyor" if obv[-1] > 0 else ("azalıyor" if obv[-1] < 0 else "yatay"))
    turnover = sum(b["close"] * b["volume"] for b in bars[-20:]) / 20 if has_volume else None
    rs20, rs60 = relative_strength(bars, bench, 20), relative_strength(bars, bench, 60)
    perf20 = _pct(last, closes[-21]) if len(closes) >= 21 else None
    if ax and ax[0] < 20:
        notes.append(f"ADX {ax[0]:.0f}: trend gücü zayıf")
    elif ax and ax[0] >= 25:
        notes.append(f"ADX {ax[0]:.0f}: güçlü trend")
    if squeeze:
        notes.append("Bollinger bantları daralmış (sıkışma): sert hareket olasılığı artar, yönü belli değil")
    if rs20 is not None and abs(rs20) >= 5:
        notes.append(f"son 20 günde endeksten %{abs(rs20):.0f} {'güçlü' if rs20 > 0 else 'zayıf'}")
    if obv_trend == "azalıyor" and perf20 is not None and perf20 > 0:
        notes.append("fiyat 20 günde yükselirken OBV düştü: yükseliş hacimle desteklenmiyor")
    return {
        "son_fiyat": last, "tarih": bars[-1]["date"], "trend": trend,
        "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "fiyat_sma50_%": _pct(last, sma50), "fiyat_sma200_%": _pct(last, sma200),
        "rsi14": r, "macd": m[0] if m else None, "macd_sinyal": m[1] if m else None,
        "macd_hist": m[2] if m else None, "hacim_orani": vol_ratio,
        "zirve_52h": max(highs), "dip_52h": min(lows),
        "zirveye_uzaklik_%": _pct(last, max(highs)), "dibe_uzaklik_%": _pct(last, min(lows)),
        "destek_20g": support, "direnc_20g": resistance, "destek_60g": support60, "direnc_60g": resistance60,
        "onceki_destek_20g": prior_support, "onceki_destek_60g": prior_support60,
        "atr_%": atr_pct, "atr": a,
        "ema20": e20, "ema50": e50, "ema200": e200,
        "adx": ax[0] if ax else None, "arti_di": ax[1] if ax else None, "eksi_di": ax[2] if ax else None,
        "bb_alt": bb[0] if bb else None, "bb_ust": bb[2] if bb else None, "bb_genislik_%": bb[3] if bb else None,
        "bb_sikisma": squeeze, "obv_egilim": obv_trend, "islem_hacmi_tl": turnover,
        "rs_20g_%": rs20, "rs_60g_%": rs60, "salinim_dibi": swing_low(bars),
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
    # W4 (2026-11-07): "today" verildiğinde o günden SONRAKİ fiyatlar kullanılmaz (geçmiş bir gün için hesapta
    # geleceği görme hatası vardı; bugünkü kullanımda gelecek fiyat olmadığından davranış değişmez).
    cut = (today or date.max).isoformat()
    q = "SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND date<=? ORDER BY date"
    bars = [dict(r) for r in conn.execute(q, (ticker, cut))]
    t = analyze(bars, today, bench=[dict(r) for r in conn.execute(q, (BENCHMARK, cut))])
    if t is None:
        return None
    since = (date.fromisoformat(t["tarih"]) - timedelta(days=60)).isoformat()
    # 2026-11-09 hız: hisse eşleşmesi önce dizinden (metin okunmadan), olay koşulu yalnız eşleşen satırlarda
    rowids = [r[0] for r in conn.execute("SELECT rowid FROM news INDEXED BY ix_news_subject_cand WHERE "
                                         "(','||candidates||',') LIKE ? AND subject IS NOT NULL", (f"%,{ticker},%",))]
    rowids += [r[0] for r in conn.execute("SELECT rowid FROM news WHERE subject IS NULL AND published_at>=? AND "
                                          "(','||candidates||',') LIKE ?", (since, f"%,{ticker},%"))]
    events = conn.execute(
        "SELECT DISTINCT substr(n.published_at,1,10) d, COALESCE(n.subject, i.event_type) s FROM news n "
        "LEFT JOIN impacts i ON i.news_id=n.id AND i.ticker=? "
        "WHERE n.rowid IN (SELECT value FROM json_each(?)) AND n.published_at>=? AND (i.event_type IN (%s) OR %s) "
        "ORDER BY d DESC"
        % (",".join("?" * len(EVENT_TYPES)), " OR ".join("n.subject LIKE ?" for _ in EVENT_SUBJECTS)),
        (ticker, json.dumps(rowids), since, *EVENT_TYPES, *[f"%{s}%" for s in EVENT_SUBJECTS])).fetchall() if rowids else []
    for e in events[:3]:
        t["veri_uyarilari"].append(f"{e['d']} kurumsal olay ({e['s']}): fiyat düzeltmesi destek/direnç ve "
                                   "ortalamaları bozmuş olabilir")
    return t


def news_moves_for(conn, ticker: str, effective_day: str, atr_value: Optional[float] = None) -> Dict:
    """Panel için: hissenin kayıtlı fiyatlarıyla haber öncesi/sonrası hareket (etki gününe göre)."""
    day = effective_day
    bars = [dict(r) for r in conn.execute("SELECT date, close FROM prices WHERE ticker=? ORDER BY date", (ticker,))]
    return news_moves(bars, day, atr_value)


TREND_ICON = {"Yükseliş": "↗", "Düşüş": "↘"}


def short_label(t: Optional[Dict]) -> str:
    if not t:
        return "teknik veri yok"
    return f"teknik {TREND_ICON.get(t['trend'], '→')} {t['trend'].lower()}"
