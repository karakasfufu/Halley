"""Hazır İşlem Fırsatları (2026-11-10 kullanıcı isteği, onaylandı). Mevcut analiz motorunun ÜSTÜNDE seçme/sıralama katmanı.

Koşullu senaryolar ("4,48'e gelirse al", "kırılırsa al") silinmedi: "Bekleyen Fırsatlar" olarak kalır. Burada yalnız
analiz anında koşulu ZATEN sağlanmış, son kapanışa yakın fiyattan (ertesi gün açılışta) uygulanabilir planlar seçilir:
  - kirilim_teyitli : son kapanış önceki 20 günün zirvesinin üstünde, yükselen mum (kırılım gerçekleşmiş)
  - geri_cekilme    : yükseliş trendinde fiyat zaten 20 EMA bölgesinde (giriş = fiyat)
  - destek_teyitli  : fiyat desteğin hemen üstünde ve bugün yükselen kapanış (tepki başlamış)
  - mevcut_fiyat    : son fiyattan alım planının risk/getirisi yeterli
Ortak şartlar: olumlu haber (skor ≥ 1,50 — mevcut eşik, değişmedi), fiyat verisi/likidite sorunsuz (tradeplan),
TP1 risk/getirisi ≥ 1:2 (tradeplan.MIN_RR), zarar mesafesi ≤ %15, risk seviyesi yüksek DEĞİL, teknik skor ≥ 5/10.
En fazla 5 hisse; uygun yoksa 0 (liste doldurulmaz).

2026-11-14 Aşama 4 (kullanıcı onaylı plan): "📐 Yalnız teknik fırsatlar" — olumlu haberi OLMAYAN likit hisselerden
aynı "koşulu sağlanmış plan" kuralıyla, daha sıkı teknik şartla (≥ 7/10, yükseliş trendi; son haberleri olumsuz
olanlar hariç) seçilir; kaynak='teknik' ile kaydedilir, haberlilerden AYRI listelenir ve AYRI ölçülür. Genel fırsat
puanı (0–100) yalnız bilgi amaçlıdır: seçimi ve sıralamayı değiştirmez. 2026-11-15 Aşama 6
sınaması: 5 yıllık geçmişte TP1'i öngörmedi (AUC 0,49) — bu yüzden yalnız bilgi olarak kalır.

YENİ ve HENÜZ SINANMAMIŞ sabitler (temkinli seçildi; sonuçlar hazir_firsat tablosunda ayrı ölçülüyor):
READY_GAP_ATR, MAX_ENTRY_ATR, MIN_RR_AT_MAX, MIN_TECH. Hiçbir mevcut eşik değiştirilmedi. Yapay zekâ kullanılmaz
(isteğe bağlı sabah haber kontrolü hariç — kullanıcı düğmeyle açar, varsayılan KAPALI). Emir vermez.
"""
import json
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from . import config, entries, journal, market_calendar, tradeplan

READY_GAP_ATR = 0.5     # giriş son kapanıştan en fazla 0,5 ATR uzak olabilir (açılışta uygulanabilir)
MAX_ENTRY_ATR = 0.3     # azami giriş = giriş + 0,3 ATR (açılış bunun üstündeyse alım önerilmez)
MIN_RR_AT_MAX = 1.5     # azami girişten alınsa bile TP1 risk/getirisi en az 1:1,5 kalmalı
MIN_TECH = 5            # teknik skor (0–10) en az 5
MAX_PICKS = 5
MIN_TECH_ONLY = 7       # yalnız teknik: haber desteği olmadığı için daha sıkı (sınanmadı)
KAYNAK_TR = {"haber": "📰 Haberli", "teknik": "📐 Yalnız teknik"}
TYPE_NAMES = {"kirilim_teyitli": "Kırılım (gerçekleşmiş)", "geri_cekilme": "Geri çekilme (bölgede)",
              "destek_teyitli": "Destekten tepki (başlamış)", "mevcut_fiyat": "Mevcut fiyattan"}
STATE_TR = {"aday": "📝 akşam listesi (sabah kontrolü bekleniyor)", "onaylandi": "✅ sabah kontrolünden geçti",
            "iptal": "⛔ iptal", "giris": "🟢 girildi (izleniyor)", "kapandi": "🏁 kapandı",
            "girissiz": "↷ giriş olmadı (açılış azami girişin üstünde)"}
RISK_ORDER = {"düşük": 0, "orta": 1, "yüksek": 2}


def _now() -> datetime:
    return datetime.now(config.TR_TZ)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


# ---------------------------------------------------------------- teknik skor
def tech_score(t: Dict) -> Dict:
    """0–10, beş bileşen × 0–2 (yalnız fiyat verisi; ağırlıklar eşit, sınanmadı)."""
    parts = {}
    tr = t.get("trend") or ""
    parts["trend"] = 2 if tr.startswith("Yükseliş") else 1 if tr.startswith("Yatay") else 0
    r = t.get("rsi14")
    parts["rsi"] = 0 if r is None else 2 if 45 <= r <= 70 else 1 if (35 <= r < 45 or 70 < r <= 78) else 0
    mom = 0
    if (t.get("macd_hist") or 0) > 0:
        mom += 1
    if (t.get("adx") or 0) >= 20 and (t.get("arti_di") or 0) > (t.get("eksi_di") or 0):
        mom += 1
    parts["ivme"] = mom
    vol = 0
    if (t.get("hacim_orani") or 0) >= 1.2:
        vol += 1
    if t.get("obv_egilim") == "artıyor":
        vol += 1
    parts["hacim"] = vol
    parts["goreli_guc"] = int((t.get("rs_20g_%") or 0) > 0) + int((t.get("rs_60g_%") or 0) > 0)
    return {"skor": sum(parts.values()), "parca": parts}


TECH_TR = {"trend": "trend", "rsi": "RSI", "ivme": "ivme (MACD/ADX)", "hacim": "hacim/OBV", "goreli_guc": "endekse göre güç"}


# ---------------------------------------------------------------- aday planlar
def _bars(conn, ticker: str, upto: str, n: int = 22) -> List[Dict]:
    rows = conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND date<=? "
                        "ORDER BY date DESC LIMIT ?", (ticker, upto, n)).fetchall()
    return [dict(r) for r in reversed(rows)]


def _mk(tur: str, entry: float, sl: float, atr: float, levels, why: str, tp=None) -> Optional[Dict]:
    risk = entry - sl
    if risk <= 0 or risk / entry * 100 > entries.MAX_STOP_PCT:
        return None
    if tp:
        tp1, tp2 = tp
    else:
        tp1, _, tp2, _, _ = entries._targets(entry, risk, atr, [x for x in levels if x[0] > entry])
    rr1 = (tp1 - entry) / risk
    return {"tur": tur, "giris": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "rr1": rr1, "nasil": why}


def candidates(conn, t: Dict, plan: Dict) -> List[Dict]:
    """Koşulu analiz anında sağlanmış planlar (yoksa boş). Giriş = son kapanış (ertesi açılışta uygulanabilir)."""
    close, atr = t["son_fiyat"], t.get("atr")
    if not atr:
        return []
    levels = entries._levels(t)
    bars = _bars(conn, plan.get("_ticker", ""), t["tarih"]) if plan.get("_ticker") else []
    out = []
    if len(bars) >= 12:
        b, prev = bars[-1], bars[:-1][-20:]
        hi = max((x["high"] or x["close"]) for x in prev)
        if b["close"] > hi and b["close"] > (b["open"] or b["close"]):
            c = _mk("kirilim_teyitli", close, hi - entries.BREAKOUT_STOP_ATR * atr, atr, levels,
                    f"bugün {hi:.2f} TL'lik 20 günlük zirvenin üstünde yükselen kapanış (kırılım gerçekleşti)")
            if c:
                out.append(c)
    for s in (plan.get("girisler") or {}).get("senaryolar", []):
        if "uygulanamaz" in s or abs(s["giris"] - close) > READY_GAP_ATR * atr:
            continue
        if s["tur"] == "geri_cekilme":
            c = _mk("geri_cekilme", close, s["sl"], atr, levels,
                    "yükseliş trendinde fiyat zaten 20 günlük ortalama bölgesinde", (s["tp1"], s["tp2"]))
        elif s["tur"] == "destek" and len(bars) >= 2 and bars[-1]["close"] > (bars[-1]["open"] or 0) \
                and bars[-1]["close"] > bars[-2]["close"]:
            c = _mk("destek_teyitli", close, s["sl"], atr, levels,
                    "fiyat desteğin hemen üstünde ve bugün yükselen kapanış (tepki başladı)", (s["tp1"], s["tp2"]))
        else:
            continue
        if c:
            out.append(c)
    if plan.get("durum") == "senaryo" and plan.get("sl"):
        c = _mk("mevcut_fiyat", close, plan["sl"], atr, levels, f"son fiyattan alım planı ({plan['sl_dayanak']})")
        if c:
            out.append(c)
    return out


def build(conn, ctx, r: Dict) -> Dict:
    """Bir olumlu haberli hisse için hazır plan ya da elenme nedeni: {"plan": {...}} | {"neden": "..."}."""
    tk = r["ticker"]
    if r["score"] < 1.5:
        return {"neden": f"haber skoru {r['score']:.2f} (en az 1,50)"}
    t = ctx.tech(tk)
    plan = ctx.plan(r)
    if not t or plan.get("durum") != "senaryo":
        return {"neden": plan.get("neden_yok", "teknik veri yok")[:140]}
    ts = tech_score(t)
    cands = [c for c in candidates(conn, t, dict(plan, _ticker=tk)) if c["rr1"] >= tradeplan.MIN_RR]
    if not cands:
        return {"neden": "koşulu bugün sağlanmış, risk/getirisi en az 1:2 olan plan yok (bekleyen senaryo olabilir)",
                "teknik": ts}
    order = list(TYPE_NAMES)
    best = max(cands, key=lambda c: (round(c["rr1"], 2), -order.index(c["tur"])))
    common = tradeplan._points([x for x in plan["riskler"] if not x.startswith("Risk/getiri")])
    risk = tradeplan._level(common)
    if risk == "yüksek":
        return {"neden": "risk seviyesi yüksek (" + "; ".join(x[:60] for x in plan["riskler"][:3]) + ")", "teknik": ts}
    if ts["skor"] < MIN_TECH:
        return {"neden": f"teknik skor {ts['skor']}/10 (en az {MIN_TECH})", "teknik": ts}
    atr, e, sl, tp1 = t["atr"], best["giris"], best["sl"], best["tp1"]
    cap = (tp1 + MIN_RR_AT_MAX * sl) / (1 + MIN_RR_AT_MAX)       # bu fiyattan alınsa TP1 r/g = 1:1,5
    azami = max(e, min(e + MAX_ENTRY_ATR * atr, cap))
    news = ctx.news_info(r)
    strong = [TECH_TR[k] for k, v in ts["parca"].items() if v == 2]
    raw = (news.get("reason") or news.get("summary") or "olumlu haber").strip()
    first = raw.split(". ")[0].rstrip(".")                          # cümle ortasında kesilmesin
    if len(first) > 220:
        first = first[:217].rsplit(" ", 1)[0] + "…"
    reason = (f"Haber: {first} "
              f"(haber skoru {r['score']:.2f}). Teknik {ts['skor']}/10" + (f" (güçlü: {', '.join(strong)})" if strong else "")
              + f", trend {t.get('trend', '?').lower()}. Neden şimdi: {best['nasil']}. "
              f"Risk/getiri 1:{best['rr1']:.1f}.")
    lo1, hi2 = entries._days(e, tp1, atr), entries._days(e, best["tp2"], atr)
    return {"plan": {"ticker": tk, "ad": r.get("name", ""), "tur": best["tur"], "tur_ad": TYPE_NAMES[best["tur"]],
                     "signal_day": t["tarih"], "kapanis": t["son_fiyat"], "giris": e,
                     "giris_alt": max(sl + 0.5 * (e - sl), e - MAX_ENTRY_ATR * atr), "azami_giris": azami,
                     "sl": sl, "tp1": tp1, "tp2": best["tp2"], "rr1": best["rr1"],
                     "getiri1_%": (tp1 / e - 1) * 100, "getiri2_%": (best["tp2"] / e - 1) * 100,
                     "zarar_%": (sl / e - 1) * 100, "vade_lo": lo1, "vade_hi": max(hi2, lo1),
                     "haber_skoru": r["score"], "teknik_skor": ts["skor"], "teknik": ts, "risk": risk,
                     "riskler": plan["riskler"], "neden": reason, "kaynak": "haber",
                     "genel_puan": overall_score(r["score"], ts["skor"], best["rr1"], risk)["puan"],
                     "puan": overall_score(r["score"], ts["skor"], best["rr1"], risk)}}


def select(conn, ctx, rows: List[Dict]) -> Dict:
    """Tüm olumlu haberli hisselerden hazır olanları seç, sırala, en fazla 5 tane."""
    picks, rejected = [], {}
    for r in rows:
        if r["score"] < 1.5:
            continue
        b = build(conn, ctx, r)
        if "plan" in b:
            picks.append(b["plan"])
        else:
            rejected[r["ticker"]] = b["neden"]
    picks.sort(key=lambda p: (RISK_ORDER[p["risk"]], -(p["teknik_skor"] + 2 * min(p["haber_skoru"], 5) + min(p["rr1"], 4))))
    for p in picks[MAX_PICKS:]:
        rejected[p["ticker"]] = "uygun ama ilk 5'e giremedi (sıralama: risk, teknik skor, haber skoru, risk/getiri)"
    return {"secilen": picks[:MAX_PICKS], "elenen": rejected}


# ---------------------------------------------------------------- genel fırsat puanı (bilgi amaçlı)
def overall_score(haber_skoru: Optional[float], teknik_skor: int, rr1: float, risk: str, kaynak: str = "haber") -> Dict:
    """0–100 = haber (0–30) + teknik (0–30) + risk/getiri (0–20) + risk seviyesi (0–20). Ağırlıklar SINANMADI;
    yalnız gösterilir (seçim ve sıralama mevcut kurallarla yapılır). Yalnız teknik fırsatın haber puanı 0'dır
    (en fazla 70) — haber desteği olmadığı açıkça görünsün."""
    parts = {"haber": 0.0 if kaynak == "teknik" else round(max(0.0, min(haber_skoru or 0, 5.0)) / 5 * 30, 1),
             "teknik": round(max(0, min(teknik_skor or 0, 10)) / 10 * 30, 1),
             "risk_getiri": round(max(0.0, min(rr1 or 0, 4.0)) / 4 * 20, 1),
             "risk": {"düşük": 20.0, "orta": 10.0}.get(risk, 0.0)}
    return {"puan": round(sum(parts.values())), "parca": parts}


def score_text(g: Dict) -> str:
    p = g["parca"]
    return (f"genel puan {g['puan']}/100 (haber {p['haber']:.0f}/30 · teknik {p['teknik']:.0f}/30 · risk/getiri "
            f"{p['risk_getiri']:.0f}/20 · risk {p['risk']:.0f}/20; 5 yıllık sınamada TP1'i öngörmedi, yalnız bilgi)")


# ---------------------------------------------------------------- yalnız teknik fırsatlar
def build_tech(conn, ctx, tk: str, name: str = "") -> Dict:
    """Olumlu haberi olmayan hisse için koşulu bugün sağlanmış teknik plan ya da elenme nedeni."""
    from . import corp_events, earnings, tracker
    t = ctx.tech(tk)
    why = tracker.scenario_guard(t)
    if why:
        return {"neden": why}
    if not str(t.get("trend") or "").startswith("Yükseliş"):
        return {"neden": f"trend {str(t.get('trend') or '?').lower()} (yalnız teknikte yükseliş trendi aranır)"}
    ts = tech_score(t)
    if ts["skor"] < MIN_TECH_ONLY:
        return {"neden": f"teknik skor {ts['skor']}/10 (yalnız teknikte en az {MIN_TECH_ONLY})", "teknik": ts}
    g = entries.scenarios(t)
    cands = [c for c in candidates(conn, t, {"girisler": g, "_ticker": tk}) if c["rr1"] >= tradeplan.MIN_RR]
    if not cands:
        return {"neden": "koşulu bugün sağlanmış, risk/getirisi en az 1:2 olan plan yok", "teknik": ts}
    order = list(TYPE_NAMES)
    best = max(cands, key=lambda c: (round(c["rr1"], 2), -order.index(c["tur"])))
    ev = ctx.corp(tk)
    news = {"direction": 0, "score": 0, "confidence": None, "flags": "",
            "bilanco_riski": earnings.window_risk(ctx.earning(tk), ctx.today, 15),
            "olay_riskleri": corp_events.risk_lines(ev, t.get("son_fiyat")), "makro_riski": ctx.macro_risk()}
    riskler = tradeplan.risk_factors(t, news) + list(t.get("veri_uyarilari") or [])
    risk = tradeplan._level(tradeplan._points(riskler))
    if risk == "yüksek":
        return {"neden": "risk seviyesi yüksek (" + "; ".join(x[:60] for x in riskler[:3]) + ")", "teknik": ts}
    atr, e, sl, tp1 = t["atr"], best["giris"], best["sl"], best["tp1"]
    cap = (tp1 + MIN_RR_AT_MAX * sl) / (1 + MIN_RR_AT_MAX)
    azami = max(e, min(e + MAX_ENTRY_ATR * atr, cap))
    strong = [TECH_TR[k] for k, v in ts["parca"].items() if v == 2]
    reason = (f"Haber yok — yalnız teknik görünüm. Teknik {ts['skor']}/10" + (f" (güçlü: {', '.join(strong)})" if strong else "")
              + f", trend {t.get('trend', '?').lower()}. Neden şimdi: {best['nasil']}. Risk/getiri 1:{best['rr1']:.1f}. "
              "Haber desteği olmadığı için temkinli olun.")
    lo1, hi2 = entries._days(e, tp1, atr), entries._days(e, best["tp2"], atr)
    gp = overall_score(None, ts["skor"], best["rr1"], risk, "teknik")
    return {"plan": {"ticker": tk, "ad": name, "tur": best["tur"], "tur_ad": TYPE_NAMES[best["tur"]], "kaynak": "teknik",
                     "signal_day": t["tarih"], "kapanis": t["son_fiyat"], "giris": e,
                     "giris_alt": max(sl + 0.5 * (e - sl), e - MAX_ENTRY_ATR * atr), "azami_giris": azami,
                     "sl": sl, "tp1": tp1, "tp2": best["tp2"], "rr1": best["rr1"],
                     "getiri1_%": (tp1 / e - 1) * 100, "getiri2_%": (best["tp2"] / e - 1) * 100,
                     "zarar_%": (sl / e - 1) * 100, "vade_lo": lo1, "vade_hi": max(hi2, lo1),
                     "haber_skoru": None, "teknik_skor": ts["skor"], "teknik": ts, "risk": risk, "riskler": riskler,
                     "neden": reason, "genel_puan": gp["puan"], "puan": gp}}


def select_tech(conn, ctx, rows: List[Dict], universe: Optional[Dict[str, str]] = None) -> Dict:
    """Olumlu (≥1,50) ya da olumsuz haberi olan hisseler HARİÇ evrenden en fazla 5 yalnız teknik fırsat."""
    if universe is None:
        from .universe import load_universe
        universe = load_universe(conn)
    skip = {r["ticker"] for r in rows if r["score"] >= 1.5 or r["score"] < 0}
    picks, rejected = [], {}
    for tk, name in sorted(universe.items()):
        if tk in skip:
            continue
        b = build_tech(conn, ctx, tk, name)
        if "plan" in b:
            picks.append(b["plan"])
        elif b.get("teknik") and b["teknik"]["skor"] >= MIN_TECH_ONLY:
            rejected[tk] = b["neden"]           # yalnız teknik skoru yeterli olanların nedeni (liste kısa kalsın)
    picks.sort(key=lambda p: (RISK_ORDER[p["risk"]], -(p["teknik_skor"] + min(p["rr1"], 4))))
    for p in picks[MAX_PICKS:]:
        rejected[p["ticker"]] = "uygun ama ilk 5'e giremedi (sıralama: risk, teknik skor, risk/getiri)"
    return {"secilen": picks[:MAX_PICKS], "elenen": rejected}


# ---------------------------------------------------------------- kayıt ve yaşam döngüsü
def rows_for(conn, giris_gunu: Optional[str] = None, durum: Optional[List[str]] = None,
             kaynak: Optional[str] = None) -> List[Dict]:
    q, a = "SELECT * FROM hazir_firsat WHERE 1=1", []
    if kaynak:
        q += " AND COALESCE(kaynak,'haber')=?"
        a.append(kaynak)
    if giris_gunu:
        q += " AND giris_gunu=?"
        a.append(giris_gunu)
    if durum:
        q += f" AND durum IN ({','.join('?' * len(durum))})"
        a += durum
    out = []
    for r in conn.execute(q + " ORDER BY giris_gunu DESC, id", a):
        d = dict(r)
        d["sonuc"] = json.loads(d["sonuc_json"]) if d.get("sonuc_json") else {}
        d["kaynak"] = d.get("kaynak") or "haber"
        out.append(d)
    return out


def current(conn, now: Optional[datetime] = None) -> List[Dict]:
    """Ekranda gösterilecek liste: giriş günü bugün ya da ileride olan en yakın gün."""
    now = now or _now()
    r = conn.execute("SELECT MIN(giris_gunu) FROM hazir_firsat WHERE giris_gunu>=?", (now.date().isoformat(),)).fetchone()[0]
    return rows_for(conn, r) if r else []


def model_info(conn, p: Dict, now: datetime) -> Optional[str]:
    """Aşama 6 gizli kayıt (2026-11-15, kullanıcı: "Gizli kayıt başlasın"): öneri anındaki model olasılığı JSON olarak
    saklanır; seçimi/sıralamayı/eşikleri ETKİLEMEZ, panelde gösterilmez. Amaç: canlı sonuçlarla modeli ölçmek.
    Hesap başarısız olursa öneri yine kaydedilir (None)."""
    try:
        from . import tp1_model
        r = tp1_model.plan_probability(conn, p)
    except Exception as e:  # model hatası öneriyi asla engellemesin
        return json.dumps({"hata": str(e)[:200], "hesaplandi": _iso(now)}, ensure_ascii=False)
    if not r:
        return None
    return json.dumps({"olasilik": round(r["olasilik"], 4), "bant": r["bant"], "benzer_n": r["benzer"]["n"],
                       "benzer_oran": r["benzer"]["gercek"], "surum": r["surum"], "hesaplandi": _iso(now)},
                      ensure_ascii=False)


def fill_missing_model(conn, now: Optional[datetime] = None) -> int:
    """2026-11-15 (müşteri denemesi): model kaydı olmadan oluşmuş AÇIK hazır fırsatlara (ör. güncellemeden önceki akşam
    listesi) olasılığı sonradan ekler; "sonradan": true işaretlenir. Hesap yalnız sinyal gününe kadarki veriyle yapılır
    (geleceği görme yok). Kapanmış kayıtlara dokunmaz. Eklenen kayıt sayısını döndürür; hata öneriyi etkilemez."""
    now = now or _now()
    n = 0
    for r in conn.execute("SELECT * FROM hazir_firsat WHERE model_json IS NULL AND "
                          "durum IN ('aday','onaylandi','giris')").fetchall():
        p = dict(r)
        mj = model_info(conn, p, now)
        if not mj:
            continue
        m = json.loads(mj)
        m["sonradan"] = True
        conn.execute("UPDATE hazir_firsat SET model_json=? WHERE id=?", (json.dumps(m, ensure_ascii=False), p["id"]))
        n += 1
    if n:
        conn.commit()
    return n


def _store(conn, p: Dict, analiz: str, giris_gunu: str, durum: str, now: datetime) -> None:
    cur = conn.execute(
        "INSERT INTO hazir_firsat(olusturuldu,analiz,signal_day,giris_gunu,ticker,tur,kapanis,giris,giris_alt,azami_giris,"
        "sl,tp1,tp2,rr1,vade_lo,vade_hi,haber_skoru,teknik_skor,risk,neden,durum,guncellendi,kaynak,genel_puan,model_json) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(signal_day, ticker) DO UPDATE SET "
        "kaynak=excluded.kaynak, genel_puan=excluded.genel_puan, model_json=excluded.model_json, "
        "tur=excluded.tur, giris=excluded.giris, giris_alt=excluded.giris_alt, azami_giris=excluded.azami_giris, "
        "sl=excluded.sl, tp1=excluded.tp1, tp2=excluded.tp2, rr1=excluded.rr1, vade_lo=excluded.vade_lo, "
        "vade_hi=excluded.vade_hi, haber_skoru=excluded.haber_skoru, teknik_skor=excluded.teknik_skor, "
        "risk=excluded.risk, neden=excluded.neden, durum=excluded.durum, iptal_nedeni=NULL, guncellendi=excluded.guncellendi "
        "WHERE hazir_firsat.durum IN ('aday','onaylandi','iptal')",
        (_iso(now), analiz, p["signal_day"], giris_gunu, p["ticker"], p["tur"], p["kapanis"], p["giris"], p["giris_alt"],
         p["azami_giris"], p["sl"], p["tp1"], p["tp2"], p["rr1"], p["vade_lo"], p["vade_hi"], p["haber_skoru"],
         p["teknik_skor"], p["risk"], p["neden"], durum, _iso(now), p.get("kaynak", "haber"), p.get("genel_puan"),
         model_info(conn, p, now)))
    if cur.rowcount:      # FAZ 1: plan gerçekten yazıldıysa tahmin defterine (aynı plan → tek satır; hata öneriyi engellemez)
        from . import defter
        row = conn.execute("SELECT id, giris_gunu FROM hazir_firsat WHERE signal_day=? AND ticker=?",
                           (p["signal_day"], p["ticker"])).fetchone()
        if row:
            defter.kaydet(conn, p, row["id"], row["giris_gunu"], analiz, now)


def _defter_sonuclandir(conn, now: datetime) -> None:
    """FAZ 1: açık tahminlerin nihai sonuçları (yalnız kayıt; seçim kurallarını etkilemez, hata fırlatmaz)."""
    try:
        from . import defter
        defter.sonuclandir(conn, now)
    except Exception:
        pass


def _cancel(conn, rid: int, why: str, now: datetime) -> None:
    conn.execute("UPDATE hazir_firsat SET durum='iptal', iptal_nedeni=?, guncellendi=? WHERE id=?", (why, _iso(now), rid))


def evening(conn, ctx, rows: List[Dict], now: Optional[datetime] = None,
            universe: Optional[Dict[str, str]] = None) -> Dict:
    """Kapanış sonrası: ertesi işlem günü için hazır liste (durum 'aday'); önce eski önerilerin sonuçları güncellenir."""
    now = now or _now()
    ev = evaluate_all(conn)
    _defter_sonuclandir(conn, now)
    sel = select(conn, ctx, rows)
    tech = select_tech(conn, ctx, rows, universe)
    allp = sel["secilen"] + tech["secilen"]
    if not allp:
        out = dict(sel, giris_gunu=None, degerlendirme=ev, analiz="aksam", teknik=tech)
        return out
    sday = max(p["signal_day"] for p in allp)
    gday = market_calendar.next_trading_day(date.fromisoformat(sday)).isoformat()
    keep = {p["ticker"] for p in allp}
    for p in allp:
        _store(conn, p, "aksam", gday, "aday", now)
    for r in rows_for(conn, gday, ["aday"]):          # aynı akşam yeniden hesaplanınca listeden düşen
        if r["ticker"] not in keep:
            _cancel(conn, r["id"], "yeniden hesaplamada artık uygun değil", now)
    conn.commit()
    return dict(sel, giris_gunu=gday, degerlendirme=ev, analiz="aksam", teknik=tech)


def news_guard(conn, rows: List[Dict], now: datetime, analyze: bool = False, news_fn: Optional[Callable] = None) -> Dict:
    """Akşamdan bu yana olumsuz haber gelen hazır fırsatı iptal eder. analyze=True ise (kullanıcı düğmesi) önce bu
    hisselerin yeni KAP haberleri bütçe içinde yapay zekâyla analiz edilir."""
    out = {"analiz": None, "iptal": []}
    tickers = sorted({r["ticker"] for r in rows if r["durum"] in ("aday", "onaylandi")})
    if analyze and tickers:
        try:
            out["analiz"] = (news_fn or analyze_news)(conn, tickers, min(r["olusturuldu"] for r in rows))
        except Exception as e:
            out["analiz"] = {"hata": str(e)[:150]}
    for r in rows:
        if r["durum"] not in ("aday", "onaylandi"):
            continue
        bad = conn.execute("SELECT i.magnitude, n.title FROM impacts i JOIN news n ON n.id=i.news_id WHERE i.ticker=? "
                           "AND i.direction<0 AND i.published_at>? ORDER BY i.published_at DESC LIMIT 1",
                           (r["ticker"], r["olusturuldu"])).fetchone()
        if bad:
            _cancel(conn, r["id"], f"akşamdan sonra olumsuz haber (etki {bad['magnitude']}/5): {(bad['title'] or '')[:100]}", now)
            out["iptal"].append(r["ticker"])
    conn.commit()
    return out


def analyze_news(conn, tickers: List[str], since: str) -> Dict:
    """Yalnız verilen hisselerin yeni KAP bildirimleri: liste → metin → bütçe içinde analiz (tracker'daki kurallarla)."""
    import time as _t
    from . import analyzer, kap, pipeline
    from .universe import load_universe
    uni = load_universe(conn)
    settings = pipeline.load_settings()
    res = {"liste": None, "metin": 0, "analiz": None}
    try:
        res["liste"] = kap.collect(conn, uni, days=2, fetch_bodies=False).get("new", 0)
    except Exception as e:
        res["hata"] = str(e)[:120]
    like = " OR ".join("(','||candidates||',') LIKE ?" for _ in tickers)
    args = tuple(f"%,{t},%" for t in tickers)
    for r in conn.execute(f"SELECT * FROM news WHERE source='kap' AND ({like}) AND status='new' AND body IS NULL "
                          "AND published_at>=?", args + (since,)).fetchall():
        try:
            body = kap.fetch_body(int(r["id"].split(":")[1]), r["subject"] or "")
        except Exception:
            break
        finally:
            _t.sleep(config.KAP_REQUEST_DELAY)
        if body.strip():
            conn.execute("UPDATE news SET body=? WHERE id=?", (body, r["id"]))
            conn.commit()
            res["metin"] += 1
    if pipeline.has_api_key():
        todo = conn.execute(f"SELECT * FROM news WHERE ({like}) AND status='new' AND body IS NOT NULL AND TRIM(body)!='' "
                            "AND published_at>=?", args + (since,)).fetchall()
        if todo:
            a = analyzer.analyze(conn, uni, rows=todo, quality=settings.get("analiz_kalitesi"), modul="hazir_haber",
                                 budget_usd=float(settings.get("haber_butce_usd", config.NEWS_BUDGET_USD)))
            res["analiz"] = {k: a.get(k) for k in ("analyzed", "filtered_out", "errors", "butce_disi") if k in a}
        else:
            res["analiz"] = {"analyzed": 0}
    else:
        res["analiz"] = "API anahtarı yok"
    return res


def morning(conn, ctx, rows: List[Dict], now: Optional[datetime] = None, ai: bool = False,
            news_fn: Optional[Callable] = None, universe: Optional[Dict[str, str]] = None) -> Dict:
    """Açılış öncesi: akşam listesini yeniden değerlendir (kötü haber, bozulan plan), uygunları onayla; yeni uygun
    çıkan varsa ekle (toplam en fazla 5)."""
    now = now or _now()
    ev = evaluate_all(conn)
    _defter_sonuclandir(conn, now)
    today = now.date().isoformat()
    gday = today if market_calendar.is_trading_day(now.date()) else market_calendar.next_trading_day(now.date()).isoformat()
    olds = rows_for(conn, gday, ["aday", "onaylandi"])
    guard = news_guard(conn, olds, now, analyze=ai, news_fn=news_fn)
    by = {r["ticker"]: r for r in rows}
    for o in rows_for(conn, gday, ["aday", "onaylandi"]):
        r = by.get(o["ticker"])
        if o["kaynak"] == "teknik":
            b = (build_tech(conn, ctx, o["ticker"]) if not (r and r["score"] < 0)
                 else {"neden": "akşamdan sonra olumsuz haber skoru"})
        else:
            b = build(conn, ctx, r) if r else {"neden": "haber listesinden çıktı (haber penceresi dışında)"}
        if "plan" not in b:
            _cancel(conn, o["id"], "sabah kontrolünde koşul bozuldu: " + b["neden"], now)
            continue
        p = b["plan"]
        if p["azami_giris"] < o["giris"] - 1e-9 or p["rr1"] < tradeplan.MIN_RR:
            _cancel(conn, o["id"], "sabah kontrolünde risk/getiri bozuldu", now)
            continue
        _store(conn, p, o["analiz"], gday, "onaylandi", now)        # seviyeler güncel veriyle yenilenir
    sel = select(conn, ctx, rows)
    tech = select_tech(conn, ctx, rows, universe)
    cancelled = {r["ticker"] for r in rows_for(conn, gday, ["iptal"])}
    from datetime import time as _time
    late = gday == today and now.time() >= _time(9, 55)   # açılış geçti: bugünkü açılışa yeni öneri eklenmez
    actives = {}
    for kaynak, picks in (("haber", sel["secilen"]), ("teknik", tech["secilen"])):
        active = actives[kaynak] = {r["ticker"] for r in rows_for(conn, gday, ["onaylandi"], kaynak)}
        taken = {r["ticker"] for r in rows_for(conn, gday, ["onaylandi"])}
        for p in ([] if late else picks):
            if len(active) >= MAX_PICKS:
                break
            if p["ticker"] not in taken and p["ticker"] not in cancelled:
                _store(conn, p, "sabah", gday, "onaylandi", now)
                active.add(p["ticker"])
                taken.add(p["ticker"])
    conn.commit()
    return {"analiz": "sabah", "giris_gunu": gday, "gec": late,
            "secilen": [p for p in sel["secilen"] if p["ticker"] in actives["haber"]],
            "elenen": sel["elenen"], "haber": guard, "degerlendirme": ev,
            "teknik": {"secilen": [p for p in tech["secilen"] if p["ticker"] in actives["teknik"]],
                       "elenen": tech["elenen"]},
            "liste": rows_for(conn, gday)}


def opening_check(conn, quotes: Dict[str, Dict], now: Optional[datetime] = None) -> Dict:
    """Açılıştan sonra (~15 dk gecikmeli Yahoo): açılış azami girişin üstündeyse fırsat iptal (eski fiyattan alım yok)."""
    now = now or _now()
    out = {"uygun": [], "iptal": [], "veri_yok": []}
    for r in rows_for(conn, now.date().isoformat(), ["aday", "onaylandi"]):
        q = quotes.get(r["ticker"])
        if not q or q.get("acilis") is None or q["zaman"].date() != now.date():
            out["veri_yok"].append(r["ticker"])
            continue
        conn.execute("UPDATE hazir_firsat SET acilis=?, guncellendi=? WHERE id=?", (q["acilis"], _iso(now), r["id"]))
        if q["acilis"] > r["azami_giris"]:
            # 2026-11-15 denetim: bu "giriş olmadı"dır, sabah iptali değil (Performans'ta yanlış kutuya düşüyordu);
            # evaluate_all ile aynı durum ('girissiz') ve sonuç kaydı.
            conn.execute("UPDATE hazir_firsat SET durum='girissiz', iptal_nedeni=?, sonuc_json=?, guncellendi=? WHERE id=?",
                         (f"açılış {q['acilis']:.2f} TL, azami girişin ({r['azami_giris']:.2f}) üstünde — eski fiyattan "
                          "alım önerilmez", json.dumps({"sonuc": "açılış azami girişin üstünde", "acilis": q["acilis"]},
                                                       ensure_ascii=False), _iso(now), r["id"]))
            out["iptal"].append((r["ticker"], q["acilis"], r["azami_giris"]))
        else:
            out["uygun"].append((r["ticker"], q["acilis"], r["azami_giris"]))
    conn.commit()
    return out


def evaluate_all(conn) -> Dict:
    """Önerilerin gerçek sonucu: giriş = giriş günü AÇILIŞI (azami girişin üstündeyse giriş yok), sonra işlem
    günlüğüyle aynı çıkış kuralları (TP1'de yarısı, stop girişe; TP2; SL; 30 işlem günü). Komisyon/kayma ayardan."""
    from . import pipeline
    st = pipeline.load_settings()
    comm = float(st.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT))
    slip = float(st.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT))
    n = changed = 0
    for r in rows_for(conn, durum=["aday", "onaylandi", "giris"]):
        bars = journal.bars_for(conn, r["ticker"], r["signal_day"])
        first = next((b for b in bars if b["date"] >= r["giris_gunu"]), None)
        if not first or not first.get("open"):
            continue
        n += 1
        if first["date"] != r["giris_gunu"]:
            pass   # o gün işlem yoksa (veri eksikse) ilk işlem gününün açılışı kullanılır
        if first["open"] > r["azami_giris"] + 1e-9:
            conn.execute("UPDATE hazir_firsat SET durum='girissiz', acilis=?, sonuc_json=?, guncellendi=? WHERE id=?",
                         (first["open"], json.dumps({"sonuc": "açılış azami girişin üstünde", "acilis": first["open"]},
                                                    ensure_ascii=False), _iso(_now()), r["id"]))
            changed += 1
            continue
        rec = {"kaynak": "gercek", "gercek_giris_gunu": first["date"], "gercek_giris_fiyati": first["open"],
               "signal_day": r["signal_day"], "senaryo": r["tur"], "sl": r["sl"], "tp1": r["tp1"], "tp2": r["tp2"],
               "giris": r["giris"], "alarm": None, "gecerlilik": 1}
        res = journal.evaluate(rec, bars, comm, slip)
        durum = "kapandi" if res["durum"] == "kapandı" else "giris"
        if durum != r["durum"] or json.dumps(res, ensure_ascii=False) != r.get("sonuc_json"):
            changed += 1
        conn.execute("UPDATE hazir_firsat SET durum=?, acilis=?, sonuc_json=?, guncellendi=? WHERE id=?",
                     (durum, first["open"], json.dumps(res, ensure_ascii=False), _iso(_now()), r["id"]))
    conn.commit()
    return {"degerlendirilen": n, "degisen": changed}


def performance(conn, kaynak: Optional[str] = None) -> Dict:
    rows = rows_for(conn, kaynak=kaynak)
    res = {"onerilen": len(rows), "sabah_iptal": sum(r["durum"] == "iptal" for r in rows),
           "girissiz": sum(r["durum"] == "girissiz" for r in rows), "acik": sum(r["durum"] == "giris" for r in rows),
           "bekleyen": sum(r["durum"] in ("aday", "onaylandi") for r in rows)}
    closed = [r for r in rows if r["durum"] == "kapandi"]
    res["kapanan"] = len(closed)
    if closed:
        s = [r["sonuc"] for r in closed]
        pct = lambda f: round(100 * sum(1 for x in s if f(x)) / len(s), 1)
        res.update({"TP1 %": pct(lambda x: x.get("tp1_goruldu") or x.get("sonuc") == "TP2"),
                    "TP2 %": pct(lambda x: x.get("sonuc") == "TP2"), "SL %": pct(lambda x: x.get("sonuc") == "SL"),
                    "Başabaş %": pct(lambda x: str(x.get("sonuc", "")).startswith("başabaş")),
                    "Süre doldu %": pct(lambda x: x.get("sonuc") == "süre doldu"),
                    "Ort. net %": round(sum(x.get("net_getiri_pct", 0) for x in s) / len(s), 2),
                    "Ort. işlem günü": round(sum(x.get("islem_gunu", 0) for x in s) / len(s), 1),
                    "Kazanma %": pct(lambda x: (x.get("net_getiri_pct") or 0) > 0)})
    return res


# ---------------------------------------------------------------- metin (rapor, Telegram)
def plan_lines(p: Dict, when: str) -> str:
    return (f"{p['ticker']} — {TYPE_NAMES.get(p['tur'], p['tur'])} · {when}\n"
            f"   giriş {p['giris']:.2f} (aralık {p['giris_alt']:.2f}–{p['azami_giris']:.2f}; azami {p['azami_giris']:.2f} "
            f"üstünde ALMA) · SL {p['sl']:.2f} · TP1 {p['tp1']:.2f} · TP2 {p['tp2']:.2f} · r/g 1:{p['rr1']:.1f}\n"
            + (f"   haber {p['haber_skoru']:.2f}" if p.get("haber_skoru") is not None else "   haber yok (yalnız teknik)")
            + f" · teknik {p['teknik_skor']}/10 · risk {p['risk']} · vade ~{p['vade_lo']}–{p['vade_hi']} işlem günü"
            + (f" · genel puan {p['genel_puan']}/100" if p.get("genel_puan") is not None else ""))


def report_md(res: Optional[Dict]) -> str:
    if not res:
        return ""
    picks = res.get("secilen") or []
    gday = res.get("giris_gunu")
    head = "## ✅ Hazır Fırsatlar" + (f" — giriş günü {gday}" if gday else "") + "\n"
    if not picks:
        md = head + "_Bugün koşulu sağlanmış, yeterince uygun hazır fırsat yok. Liste doldurulmaz; bekleyen senaryolar " \
                    "aşağıda._\n\n"
    else:
        md = head + ("Koşulu analiz anında sağlanmış planlar (ertesi işlem günü açılışında değerlendirilebilir). "
                     "**Açılış azami girişin üstündeyse alım yapılmaz.**\n\n")
        md += ("| Hisse | Tür | Kapanış | Giriş aralığı | Azami | SL | TP1 | TP2 | R/G | Getiri TP1/TP2 | Vade | Haber | "
               "Teknik | Risk | Genel puan |\n")
        md += "|" + "---|" * 15 + "\n"
        for p in picks:
            md += (f"| {p['ticker']} | {TYPE_NAMES[p['tur']]} | {p['kapanis']:.2f} | {p['giris_alt']:.2f}–{p['azami_giris']:.2f} | "
                   f"{p['azami_giris']:.2f} | {p['sl']:.2f} | {p['tp1']:.2f} | {p['tp2']:.2f} | 1:{p['rr1']:.1f} | "
                   f"%{p['getiri1_%']:+.1f} / %{p['getiri2_%']:+.1f} | {p['vade_lo']}–{p['vade_hi']} gün | "
                   f"{p['haber_skoru']:.2f} | {p['teknik_skor']}/10 | {p['risk']} | {p.get('genel_puan', '—')}/100 |\n")
        md += "\n" + "".join(f"- **{p['ticker']}:** {p['neden']}\n" for p in picks) + "\n"
    if res.get("gec"):
        md += ("- ⏰ Sabah kontrolü açılıştan sonra yapıldı: bugünkü açılışa yeni hazır fırsat eklenmedi (yalnız akşam "
               "listesi kontrol edildi). Yeni liste akşam analizinde.\n")
    g = (res.get("haber") or {})
    if g.get("iptal"):
        md += f"- ⛔ Sabah kontrolünde olumsuz haber nedeniyle iptal: {', '.join(g['iptal'])}\n"
    cancelled = [r for r in res.get("liste") or [] if r["durum"] == "iptal"]
    if cancelled:
        md += "".join(f"- ⛔ {r['ticker']} iptal: {r['iptal_nedeni']}\n" for r in cancelled) + "\n"
    tech = (res.get("teknik") or {}).get("secilen") or []
    md += "### 📐 Yalnız teknik fırsatlar (haber desteği yok)\n"
    if not tech:
        md += "_Bugün yalnız teknik görünümle seçilecek kadar güçlü (teknik ≥7/10, yükseliş trendi) hisse yok._\n\n"
    else:
        md += ("Olumlu haberi olmayan, yalnız fiyat verisiyle seçilen planlar. Haberlilerden **ayrı ölçülür**; haber "
               "desteği olmadığı için daha temkinli olun.\n\n")
        md += "| Hisse | Tür | Kapanış | Giriş aralığı | SL | TP1 | TP2 | R/G | Teknik | Risk | Genel puan |\n"
        md += "|" + "---|" * 11 + "\n"
        for p in tech:
            md += (f"| {p['ticker']} | {TYPE_NAMES[p['tur']]} | {p['kapanis']:.2f} | {p['giris_alt']:.2f}–{p['azami_giris']:.2f} | "
                   f"{p['sl']:.2f} | {p['tp1']:.2f} | {p['tp2']:.2f} | 1:{p['rr1']:.1f} | {p['teknik_skor']}/10 | "
                   f"{p['risk']} | {p.get('genel_puan', '—')}/100 |\n")
        md += "\n"
    md += ("_Hazır fırsat kuralları yeni ve henüz sınanmadı (son kapanışa ≤0,5 ATR, r/g ≥1:2, teknik ≥5/10 — yalnız "
           "teknikte ≥7/10 ve yükseliş trendi —, risk yüksek değil); sonuçlar ayrıca ölçülüyor (🏁 Performans). Genel "
           "puan yalnız bilgi amaçlıdır; 5 yıllık geçmiş sınamada TP1'i öngörmedi (yazı-tura düzeyi). Yatırım tavsiyesi değildir._\n\n")
    return md


def telegram_text(res: Optional[Dict], kind: str) -> str:
    if not res:
        return ""
    picks = res.get("secilen") or []
    gday = res.get("giris_gunu") or ""
    when = "ertesi gün açılış" if kind == "aksam" else "bugün açılış"
    t = f"\n✅ Hazır fırsatlar ({len(picks)})" + (f" — giriş {gday[8:10]}.{gday[5:7]}" if gday else "") + ":\n"
    t += ("\n".join(plan_lines(p, when) for p in picks) + "\n") if picks else \
        "Bugün yeterince uygun hazır fırsat yok (liste doldurulmaz).\n"
    tech = (res.get("teknik") or {}).get("secilen") or []
    if tech:
        t += f"\n📐 Yalnız teknik ({len(tech)}, haber desteği yok — temkinli):\n"
        t += "\n".join(plan_lines(p, when) for p in tech) + "\n"
    return t


# ---------------------------------------------------------------- otomatik çalışma (arka plan bekçisi)
def state_file():
    return config.DATA / "hazir_durum.json"


def load_state() -> Dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(st: Dict) -> None:
    state_file().parent.mkdir(parents=True, exist_ok=True)
    state_file().write_text(json.dumps(st, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def tick(conn, now: Optional[datetime] = None, run_fn: Optional[Callable] = None, quote_fn: Optional[Callable] = None,
         send: Optional[Callable] = None, weekly_fn: Optional[Callable] = None) -> Dict:
    """Akşam (kapanış+20 dk) ve sabah (08:30–09:55, günde bir) analizini kendiliğinden çalıştırır; açılıştan sonra
    (10:05–17:30, günde bir) açılış fiyatını azami girişle karşılaştırır. Otomatik sabah analizi yalnız 08:30–09:55
    (açılıştan önce); seans başladıysa yapılmaz (gün içi yarım fiyatla analiz olmasın) — elle her zaman yapılabilir. Kullanıcı aynı analizi elle yaptıysa
    yinelemez (rapor arşivi). run_fn(kind) testte değiştirilebilir."""
    import os
    from . import notify, pipeline, tracker, watchdog
    from datetime import time as _time
    now = now or _now()
    st = load_state()
    out = {}
    if os.environ.get("HALLEY_OFFLINE") and run_fn is None:      # deneme kipinde ağa çıkan analiz başlatılmaz
        return out
    today = now.date()
    trading = market_calendar.is_trading_day(today)
    done = lambda day, kind: any(n.startswith(f"{day}_{kind}") for n in watchdog.list_reports())
    run = run_fn or (lambda kind: watchdog.run_auto(conn, kind, now))
    last = tracker.last_closed_day(now)
    if last and last.isoformat() > st.get("aksam_gunu", ""):
        # Kaçırılan akşam analizi, yeni seans BAŞLAMADIYSA yapılır: aynı akşam, ertesi işlem günü 09:30'dan önce, ya da
        # hafta sonu/tatil (seans yok, son kapanış kesin). Seans başladıysa gün içi YARIM fiyatla "akşam" listesi
        # üretilmez (o günün listesini sabah kontrolü yönetir). 2026-11-15 denetim: önceden hafta sonu açılışta da
        # "seans başladı" sanılıp atlanıyordu → Cuma akşamı kaçırılınca Pazartesi listesi ve evren fiyatları hiç
        # güncellenmiyordu.
        session_started = trading and last != today and now.time() >= _time(9, 30)
        if not session_started and not done(last.isoformat(), "aksam"):
            out["aksam"] = run("aksam")
        elif session_started:
            out["aksam_atlandi"] = "seans başladı; kaçırılan akşam analizi yapılmadı"
        st["aksam_gunu"] = last.isoformat()
    elif trading and _time(8, 30) <= now.time() <= _time(9, 55) and st.get("sabah_gunu") != today.isoformat():
        if not done(today.isoformat(), "sabah"):
            out["sabah"] = run("sabah")
        st["sabah_gunu"] = today.isoformat()
    # 2026-11-14 Aşama 4: haftanın son işlem gününün akşam turu işlendiyse haftalık rapor (bir kez, YZ yok). Arşiv
    # adına değil "akşam turu işlendi" bilgisine (aksam_gunu) bakılır. (2026-11-15 denetim: bu blok yanlışlıkla
    # akşam/sabah if–elif zincirinin ortasına girmişti; ayrı bloğa alındı.)
    from . import weekly
    if (last and last == weekly.last_trading_day_of_week(last) and st.get("aksam_gunu") == last.isoformat()
            and not done(last.isoformat(), "haftalik") and st.get("haftalik_gunu") != last.isoformat()):
        try:
            out["haftalik"] = (weekly_fn or (lambda d: weekly.run(conn, d, send=send)))(last)
        finally:
            st["haftalik_gunu"] = last.isoformat()
    if trading and _time(10, 5) <= now.time() <= _time(17, 30) and st.get("acilis_gunu") != today.isoformat():
        rows = rows_for(conn, today.isoformat(), ["aday", "onaylandi"])
        if rows:
            res = opening_check(conn, (quote_fn or tracker.fetch_intraday)([r["ticker"] for r in rows]), now)
            out["acilis"] = res
            if res["iptal"] or res["uygun"]:
                st["acilis_gunu"] = today.isoformat()
                if notify.configured() and pipeline.load_settings().get("hazir_bildirim", True):
                    txt = "🔔 Halley açılış kontrolü (hazır fırsatlar, ~15 dk gecikmeli veri)\n"
                    txt += "".join(f"✅ {tk}: açılış {o:.2f} ≤ azami {m:.2f} — plan geçerli\n" for tk, o, m in res["uygun"])
                    txt += "".join(f"⛔ {tk}: açılış {o:.2f} > azami {m:.2f} — eski fiyattan ALMAYIN, fırsat iptal\n"
                                   for tk, o, m in res["iptal"])
                    out["bildirim"] = (send or notify.send)(txt + notify.FOOT)
        else:
            st["acilis_gunu"] = today.isoformat()
    st["nabiz"] = _iso(now)
    st.pop("hata", None)
    _save_state(st)
    return out


def safe_tick(db_path=None) -> None:
    from . import db
    try:
        conn = db.connect(db_path)
        try:
            tick(conn)
        finally:
            conn.close()
    except Exception as e:
        st = load_state()
        st.update(hata=str(e)[:300], hata_zaman=_iso(_now()))
        _save_state(st)
