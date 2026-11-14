"""Profesyonel fiyat grafiği ve olası fiyat aralığı konisi (2026-11-15, plan Aşama 5). Yapay zekâ KULLANILMAZ.

- Mum grafiği (açılış/en yüksek/en düşük/kapanış), hacim, EMA 20/50/200 (technical.ema ile aynı yöntem: ilk değer
  basit ortalama, sonra k = 2/(n+1)), destek/direnç ve plan seviyeleri (giriş, azami giriş bandı, SL, TP1, TP2).
- Olası fiyat aralığı konisi: son 60 işlem gününün günlük log-getiri oynaklığıyla, YÖN VARSAYMADAN (ortalama getiri 0)
  √t ile genişleyen %50 ve %80 aralıkları. Bu bir tahmin modeli değildir; "geçmiş oynaklık sürerse fiyatın
  bulunabileceği aralık"tır. Aşama 6–7'deki modeller ileride bu koninin yerine/yanına eklenebilir.
"""
import math
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from . import market_calendar

Z = {"p10": -1.2816, "p25": -0.6745, "p75": 0.6745, "p90": 1.2816}
VOL_DAYS = 60
UP, DOWN = "#22c55e", "#ef4444"
EMA_COLORS = {"EMA 20": "#38bdf8", "EMA 50": "#f59e0b", "EMA 200": "#a78bfa"}
LEVEL_COLORS = {"Giriş": "#e5e7eb", "Zarar durdur (SL)": DOWN, "TP1": UP, "TP2": "#16a34a",
                "Destek (20g)": "#64748b", "Direnç (20g)": "#64748b"}


def _ema_series(values: List[float], n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < n:
        return out
    k, v = 2 / (n + 1), sum(values[:n]) / n
    out[n - 1] = v
    for i in range(n, len(values)):
        v = values[i] * k + v * (1 - k)
        out[i] = v
    return out


def history(conn, ticker: str, days: int = 120, upto: Optional[str] = None) -> pd.DataFrame:
    """Son `days` işlem günü + EMA'lar (EMA bütün geçmişten hesaplanır, sonra kırpılır)."""
    q = "SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND close IS NOT NULL"
    a = [ticker]
    if upto:
        q += " AND date<=?"
        a.append(upto)
    rows = [dict(r) for r in conn.execute(q + " ORDER BY date", a)]
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows)
    for c in ("open", "high", "low"):
        df[c] = df[c].fillna(df["close"])
    df["volume"] = df["volume"].fillna(0)
    closes = df["close"].tolist()
    for n in (20, 50, 200):
        df[f"EMA {n}"] = _ema_series(closes, n)
    df["date"] = pd.to_datetime(df["date"])
    return df.tail(days).reset_index(drop=True)


def daily_vol(df: pd.DataFrame, n: int = VOL_DAYS) -> Optional[float]:
    c = df["close"].tolist()[-(n + 1):]
    rets = [math.log(c[i] / c[i - 1]) for i in range(1, len(c)) if c[i] > 0 and c[i - 1] > 0]
    if len(rets) < 20:
        return None
    m = sum(rets) / len(rets)
    return math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))


def cone(last_close: float, last_day: date, sigma: Optional[float], horizon: int = 10) -> pd.DataFrame:
    """Yön varsaymadan (drift 0) log-normal aralık: fiyat × exp(z·σ·√t). t = işlem günü (tatiller atlanır)."""
    if not sigma or not last_close:
        return pd.DataFrame(columns=["date", "t", "p10", "p25", "p50", "p75", "p90"])
    out, d = [{"date": pd.Timestamp(last_day), "t": 0, **{k: last_close for k in ("p10", "p25", "p50", "p75", "p90")}}], last_day
    for t in range(1, horizon + 1):
        d = market_calendar.next_trading_day(d)
        s = sigma * math.sqrt(t)
        row = {"date": pd.Timestamp(d), "t": t, "p50": last_close}
        row.update({k: last_close * math.exp(z * s) for k, z in Z.items()})
        out.append(row)
    return pd.DataFrame(out)


def cone_summary(c: pd.DataFrame) -> Dict:
    if c.empty:
        return {}
    e = c.iloc[-1]
    base = c.iloc[0]["p50"]
    pct = lambda v: (v / base - 1) * 100
    out = {"gun": int(e["t"]), "bitis": e["date"].date().isoformat(), "fiyat": float(base)}
    for k in ("p10", "p25", "p75", "p90"):
        out[k], out[k + "_%"] = float(e[k]), float(pct(e[k]))
    return out


def cone_text(cs: Dict, levels: Optional[Dict] = None) -> str:
    """Koninin sade Türkçe açıklaması; TP1/SL koni içinde mi (yalnız bilgi, olasılık hesabı değil)."""
    if not cs:
        return "Olası fiyat aralığı hesaplanamadı (en az 20 günlük fiyat gerekir)."
    b = cs["bitis"]
    txt = (f"**{cs['gun']} işlem günü sonra ({b[8:10]}.{b[5:7]})**: geçmiş 60 günün oynaklığı sürerse fiyatın "
           f"%80 ihtimalle **{cs['p10']:.2f}–{cs['p90']:.2f} TL** ({cs['p10_%']:+.1f}% / {cs['p90_%']:+.1f}%), "
           f"%50 ihtimalle {cs['p25']:.2f}–{cs['p75']:.2f} TL aralığında olması beklenir.")
    levels = levels or {}
    notes = []
    tp1, sl, entry = levels.get("TP1"), levels.get("Zarar durdur (SL)"), levels.get("Giriş")
    if entry and abs(entry / cs["fiyat"] - 1) > 0.015:
        # Giriş henüz gerçekleşmemiş (koşullu senaryo): koni bugünkü fiyattan; SL/TP yorumu girişten sonra anlamlı
        where = ("aralığın içinde: oynaklığa göre bu sürede giriş koşulu oluşabilir" if cs["p10"] <= entry <= cs["p90"]
                 else "aralığın dışında: bu sürede giriş koşulunun oluşması olağandışı bir hareket gerektirir")
        return txt + f" Giriş ({entry:.2f}) {where}. SL ve TP'nin değerlendirmesi giriş gerçekleşince anlamlıdır."
    if tp1:
        notes.append(f"TP1 ({tp1:.2f}) bu aralığın " + ("içinde: oynaklığa göre bu sürede ulaşılabilir bir mesafe"
                     if tp1 <= cs["p90"] else "dışında: bu sürede ulaşmak için olağandışı bir yükseliş gerekir"))
    if sl:
        notes.append(f"SL ({sl:.2f}) " + ("aralığın içinde: oynaklık bu sürede stopu tetikleyebilir"
                     if sl >= cs["p10"] else "aralığın altında: olağan oynaklıkla tetiklenmesi beklenmez"))
    return txt + (" " + "; ".join(notes) + "." if notes else "")


def plan_levels(t: Optional[Dict] = None, scenario: Optional[Dict] = None, ready: Optional[Dict] = None) -> Dict:
    """Grafikte çizilecek yatay seviyeler. Öncelik: hazır fırsat planı > en uygun giriş senaryosu; destek/direnç her zaman."""
    lv: Dict = {}
    src = ready or scenario
    if src:
        lv["Giriş"] = src.get("giris")
        lv["Zarar durdur (SL)"] = src.get("sl")
        lv["TP1"] = src.get("tp1")
        lv["TP2"] = src.get("tp2")
    if ready and ready.get("azami_giris"):
        lv["_band"] = (ready.get("giris_alt") or ready["giris"], ready["azami_giris"])
    if t:
        lv["Destek (20g)"] = t.get("destek_20g")
        lv["Direnç (20g)"] = t.get("direnc_20g")
    return {k: v for k, v in lv.items() if v}


def figure(df: pd.DataFrame, cone_df: Optional[pd.DataFrame] = None, levels: Optional[Dict] = None,
           height: int = 380, dark: bool = True):
    """Altair katmanlı grafik: üstte mum + EMA + seviyeler + koni, altta hacim. df boşsa None."""
    import altair as alt
    if df is None or df.empty:
        return None
    levels = levels or {}
    d = df.copy()
    d["yon"] = ["yükseliş" if c >= o else "düşüş" for o, c in zip(d["open"], d["close"])]
    d["Tarih"] = d["date"].dt.strftime("%d.%m.%Y")
    color = alt.Color("yon:N", scale=alt.Scale(domain=["yükseliş", "düşüş"], range=[UP, DOWN]), legend=None)
    x_end = d["date"].max()
    if cone_df is not None and not cone_df.empty:
        x_end = max(x_end, cone_df["date"].max())
    x = alt.X("date:T", title=None, scale=alt.Scale(domain=[d["date"].min(), x_end]),
              axis=alt.Axis(format="%d.%m", labelAngle=0, grid=False))
    lvals = [v for k, v in levels.items() if not k.startswith("_") and v]
    lo, hi = min([d["low"].min()] + lvals), max([d["high"].max()] + lvals)
    if cone_df is not None and not cone_df.empty:
        lo, hi = min(lo, cone_df["p10"].min()), max(hi, cone_df["p90"].max())
    pad = (hi - lo) * 0.04 or hi * 0.02
    ys = alt.Scale(domain=[lo - pad, hi + pad], zero=False)
    tip = [alt.Tooltip("Tarih:N"), alt.Tooltip("open:Q", title="Açılış", format=".2f"),
           alt.Tooltip("high:Q", title="En yüksek", format=".2f"), alt.Tooltip("low:Q", title="En düşük", format=".2f"),
           alt.Tooltip("close:Q", title="Kapanış", format=".2f"), alt.Tooltip("volume:Q", title="Hacim", format=",.0f")]
    base = alt.Chart(d).encode(x=x)
    wick = base.mark_rule().encode(y=alt.Y("low:Q", title="TL", scale=ys), y2="high:Q", color=color, tooltip=tip)
    body = base.mark_bar(size=max(2, min(9, int(600 / max(len(d), 1))))).encode(
        y=alt.Y("open:Q", scale=ys), y2="close:Q", color=color, tooltip=tip)
    layers = []
    band = levels.get("_band")
    if band:
        bdf = pd.DataFrame([{"y1": band[0], "y2": band[1], "x1": d["date"].min(), "x2": x_end}])
        layers.append(alt.Chart(bdf).mark_rect(opacity=0.12, color="#e5e7eb").encode(
            x="x1:T", x2="x2:T", y=alt.Y("y1:Q", scale=ys), y2="y2:Q",
            tooltip=[alt.Tooltip("y1:Q", title="Giriş aralığı alt", format=".2f"),
                     alt.Tooltip("y2:Q", title="Azami giriş (üstünde ALMA)", format=".2f")]))
    if cone_df is not None and not cone_df.empty:
        cd = cone_df.copy()
        cd["Gün"] = cd["t"].astype(int)
        ctip = [alt.Tooltip("Gün:Q", title="İşlem günü sonra"), alt.Tooltip("p10:Q", title="%10 alt", format=".2f"),
                alt.Tooltip("p25:Q", title="%25", format=".2f"), alt.Tooltip("p75:Q", title="%75", format=".2f"),
                alt.Tooltip("p90:Q", title="%90 üst", format=".2f")]
        cb = alt.Chart(cd).encode(x="date:T")
        layers += [cb.mark_area(opacity=0.13, color="#38bdf8").encode(y=alt.Y("p10:Q", scale=ys), y2="p90:Q",
                                                                      tooltip=ctip),
                   cb.mark_area(opacity=0.22, color="#38bdf8").encode(y=alt.Y("p25:Q", scale=ys), y2="p75:Q",
                                                                      tooltip=ctip),
                   cb.mark_line(strokeDash=[4, 3], color="#38bdf8", opacity=0.8).encode(y=alt.Y("p50:Q", scale=ys))]
    emas = d.melt(id_vars=["date"], value_vars=[c for c in EMA_COLORS if c in d.columns], var_name="Ortalama",
                  value_name="v").dropna()
    ema_layer = alt.Chart(emas).mark_line(strokeWidth=1.4).encode(
        x="date:T", y=alt.Y("v:Q", scale=ys),
        color=alt.Color("Ortalama:N", scale=alt.Scale(domain=list(EMA_COLORS), range=list(EMA_COLORS.values())),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("Ortalama:N"), alt.Tooltip("v:Q", title="Değer", format=".2f")])
    lv = sorted(({"ad": k, "deger": v, "renk": LEVEL_COLORS.get(k, "#94a3b8"), "etiket": f"{k} {v:.2f}"}
                 for k, v in levels.items() if not k.startswith("_")), key=lambda r: r["deger"])
    gap, last = (hi - lo) * 0.045, None          # yakın seviyelerin etiketleri üst üste binmesin
    for r in lv:
        r["ly"] = r["deger"] if last is None or r["deger"] - last >= gap else last + gap
        last = r["ly"]
    lv_layers = []
    if lv:
        ldf = pd.DataFrame(lv)
        dash = alt.condition(alt.FieldOneOfPredicate("ad", ["Destek (20g)", "Direnç (20g)"]),
                             alt.value([2, 3]), alt.value([6, 3]))
        lv_layers = [alt.Chart(ldf).mark_rule(strokeWidth=1.2).encode(
                         y=alt.Y("deger:Q", scale=ys), color=alt.Color("renk:N", scale=None), strokeDash=dash,
                         tooltip=[alt.Tooltip("ad:N", title="Seviye"), alt.Tooltip("deger:Q", title="TL", format=".2f")]),
                     alt.Chart(ldf).mark_text(align="left", dx=4, dy=-6, fontSize=11).encode(
                         x=alt.value(4), y=alt.Y("ly:Q", scale=ys), text="etiket:N",
                         color=alt.Color("renk:N", scale=None))]
    price = alt.layer(*layers, wick, body, ema_layer, *lv_layers).resolve_scale(color="independent").properties(height=height)
    vol = alt.Chart(d).mark_bar(opacity=0.55).encode(
        x=alt.X("date:T", title=None, scale=alt.Scale(domain=[d["date"].min(), x_end]),
                axis=alt.Axis(format="%d.%m", labelAngle=0, grid=False)),
        y=alt.Y("volume:Q", title="Hacim", axis=alt.Axis(format="~s")), color=color,
        tooltip=[alt.Tooltip("Tarih:N"), alt.Tooltip("volume:Q", title="Hacim", format=",.0f")]).properties(height=80)
    # 2026-11-15: renkler Halley'in karanlık mod ayarından (Streamlit temasına bırakılınca Halley penceresinde beyaz
    # zemin görünüyordu). Zemin saydam: kartın rengini alır.
    fg, grid = ("#cbd5e1", "#334155") if dark else ("#334155", "#e2e8f0")
    return (alt.vconcat(price, vol, spacing=4).resolve_scale(x="shared", color="independent")
            .configure(background="transparent")
            .configure_view(strokeWidth=0, fill="transparent")
            .configure_axis(labelColor=fg, titleColor=fg, gridColor=grid, domainColor=grid, tickColor=grid,
                            labelFontSize=11, titleFontSize=11)
            .configure_axisX(labelOverlap="greedy", labelSeparation=8, tickCount=8)
            .configure_legend(labelColor=fg, titleColor=fg))
