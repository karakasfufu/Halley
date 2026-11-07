"""SL/TP senaryo testi: pilot olaylarında "önce TP mi geldi, SL mi?" (2026-11-07).

Kurallar (geleceği görmeden):
- Senaryo, giriş gününden ÖNCEKİ fiyatlarla hesaplanır (teknik göstergeler, SL/TP, vade). Giriş günü ve sonrası
  hesaba girmez.
- Giriş: yayından sonraki ilk işlem gününün açılışı (pilotun olay ölçümüyle aynı). Açılış SL'nin altındaysa SL,
  TP'nin üstündeyse TP açılış fiyatından gerçekleşmiş sayılır.
- Her gün en düşük SL'ye, en yüksek TP'ye değdi mi bakılır. Aynı gün ikisine de değerse gün içi sıra bilinemez:
  temkinli olarak SL sayılır.
- Gün boyu tek fiyat (tavan/taban kilidi) olan günler işaretlenir; o gün çıkış fiilen mümkün olmayabilir.
- En fazla MAX_DAYS işlem günü izlenir; ikisine de değmezse "süre doldu" ve son kapanıştaki getiri.
- Yalnızca senaryo üretilen (olumlu haber, yeterli ve kritik sorunsuz veri) olaylar test edilir.
Yapay zekâ kullanılmaz; ücretsizdir. Küçük örnekte sonuçlar kanıt değildir.
"""
from bisect import bisect_right
from datetime import datetime
from statistics import mean, median
from typing import Dict, List

from . import config, technical, tradeplan

MAX_DAYS = 30
BENCHMARK = "XU100"
COLUMNS = ["bildirim", "hisse", "haber_skoru", "giriş_günü", "giriş_fiyatı", "sl", "tp", "risk_getiri",
           "tahmini_vade", "risk_seviyesi", "sonuç", "çıkış_günü", "gün", "getiri_%", "vade_içinde", "kilitli_gün", "not"]


def _bars_by_ticker(conn) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for r in conn.execute("SELECT ticker,date,open,high,low,close FROM pilot_bars ORDER BY ticker,date"):
        out.setdefault(r["ticker"], []).append(dict(r))
    return out


def run(conn, max_days: int = MAX_DAYS) -> List[dict]:
    bars = _bars_by_ticker(conn)
    sessions = [b["date"] for b in bars.get(BENCHMARK, [])]
    rows = conn.execute("SELECT i.*, n.subject FROM impacts i JOIN pilot_selection s ON s.news_id=i.news_id "
                        "JOIN news n ON n.id=i.news_id ORDER BY i.published_at").fetchall()
    out = []
    for imp in rows:
        score = imp["direction"] * imp["magnitude"] * imp["confidence"]
        rec = {c: None for c in COLUMNS}
        rec.update(bildirim=imp["news_id"], hisse=imp["ticker"], haber_skoru=round(score, 2), **{"not": ""})
        day = datetime.fromisoformat(imp["published_at"]).astimezone(config.TR_TZ).date().isoformat()
        idx = bisect_right(sessions, day)
        series = bars.get(imp["ticker"], [])
        if idx >= len(sessions) or not series:
            rec.update(sonuç="ölçülemedi", **{"not": "giriş günü fiyatı yok"})
            out.append(rec)
            continue
        entry_day = sessions[idx]
        history = [b for b in series if b["date"] < entry_day]  # geleceği görmeden
        t = technical.analyze(history, today=datetime.fromisoformat(entry_day).date()) if history else None
        move = technical.news_moves(history, imp["effective_date"], t["atr"]) if t else {}  # yalnız girişten önceki fiyatlar
        p = tradeplan.plan(t, {"score": score, "direction": imp["direction"], "confidence": imp["confidence"],
                               "flags": imp["flag"] or "", "persistence": imp["persistence"], "reason": imp["reason"],
                               "hareket": move})
        if p["durum"] != "senaryo":
            rec.update(sonuç="senaryo yok", **{"not": p.get("neden_yok", "")})
            out.append(rec)
            continue
        forward = [b for b in series if b["date"] >= entry_day][:max_days]
        if not forward or forward[0]["date"] != entry_day or forward[0].get("open") is None:
            rec.update(sonuç="ölçülemedi", **{"not": "giriş günü hisse fiyatı eksik"})
            out.append(rec)
            continue
        entry = forward[0]["open"]
        sl, tp = p["sl"], p["tp"]
        rec.update(giriş_günü=entry_day, giriş_fiyatı=round(entry, 4), sl=round(sl, 4), tp=round(tp, 4),
                   risk_getiri=round(p["rr"], 2) if p["rr"] else None,
                   tahmini_vade="{}–{}".format(*p["vade"]), risk_seviyesi=p["risk_seviyesi"])
        locked, result = 0, None
        for n, b in enumerate(forward, start=1):
            b = dict(b, high=b.get("high") or b["close"], low=b.get("low") or b["close"])  # eksikse kapanış
            if b["high"] == b["low"] == b["close"]:
                locked += 1
            if n == 1 and entry <= sl:
                result = ("SL", b["date"], n, entry, "açılışta zarar durdurun altında")
            elif n == 1 and entry >= tp:
                result = ("TP", b["date"], n, entry, "açılışta kâr al seviyesinin üstünde")
            elif b["low"] <= sl and b["high"] >= tp:
                result = ("SL", b["date"], n, sl, "aynı gün ikisine de değdi; temkinli olarak SL sayıldı")
            elif b["low"] <= sl:
                result = ("SL", b["date"], n, sl, "")
            elif b["high"] >= tp:
                result = ("TP", b["date"], n, tp, "")
            if result:
                break
        if result is None:
            last = forward[-1]
            complete = len(forward) >= max_days
            result = ("süre doldu" if complete else "devam ediyor", last["date"], len(forward), last["close"],
                      "" if complete else f"yalnız {len(forward)} işlem günü veri var")
        outcome, exit_day, days, price, note = result
        lo, hi = p["vade"]
        rec.update(sonuç=outcome, çıkış_günü=exit_day, gün=days, **{"getiri_%": round((price / entry - 1) * 100, 2),
                   "vade_içinde": (lo <= days <= hi) if outcome == "TP" else None, "kilitli_gün": locked,
                   "not": note})
        out.append(rec)
    return out


def summary(results: List[dict]) -> Dict:
    done = [r for r in results if r["sonuç"] in ("TP", "SL", "süre doldu")]
    tp = [r for r in done if r["sonuç"] == "TP"]
    sl = [r for r in done if r["sonuç"] == "SL"]
    rets = [r["getiri_%"] for r in done]
    return {
        "olay": len(results), "test_edilen": len(done), "tp": len(tp), "sl": len(sl),
        "süre_doldu": len(done) - len(tp) - len(sl),
        "senaryo_yok": sum(r["sonuç"] == "senaryo yok" for r in results),
        "devam_eden": sum(r["sonuç"] == "devam ediyor" for r in results),
        "tp_oranı_%": 100 * len(tp) / len(done) if done else None,
        "ortalama_getiri_%": mean(rets) if rets else None, "medyan_getiri_%": median(rets) if rets else None,
        "tp_vade_içinde_%": 100 * sum(1 for r in tp if r["vade_içinde"]) / len(tp) if tp else None,
    }


def as_text(results: List[dict]) -> str:
    s = summary(results)
    f = lambda v, fmt="{:.1f}": "—" if v is None else fmt.format(v)
    lines = [
        "HALLEY — SL/TP SENARYO TESTİ (geleceği görmeden)", "",
        f"Pilot olayı: {s['olay']} · senaryo test edilen: {s['test_edilen']} · senaryo üretilmeyen: {s['senaryo_yok']}"
        f" · henüz sonuçlanmayan: {s['devam_eden']}",
        f"TP (kâr al) önce: {s['tp']} · SL (zarar durdur) önce: {s['sl']} · {MAX_DAYS} günde ikisi de yok: {s['süre_doldu']}",
        f"TP oranı: %{f(s['tp_oranı_%'], '{:.0f}')} · ortalama getiri: %{f(s['ortalama_getiri_%'])} · medyan: %{f(s['medyan_getiri_%'])}",
        f"TP'lerin tahmini vade içinde gerçekleşme oranı: %{f(s['tp_vade_içinde_%'], '{:.0f}')}",
        "",
        "Kurallar: senaryo giriş gününden önceki fiyatlarla hesaplanır; giriş ilk işlem günü açılışı; aynı gün hem SL hem TP",
        "görülürse temkinli olarak SL sayılır; işlem maliyeti dahil değildir. Küçük örnekte bu oranlar kanıt değildir.",
    ]
    return "\n".join(lines) + "\n"
