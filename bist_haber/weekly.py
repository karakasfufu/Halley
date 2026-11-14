"""Haftalık rapor (2026-11-14, plan Aşama 4). Yalnız kayıtlı veriden, Python ile; yapay zekâ KULLANILMAZ.

İçerik: haftanın piyasası (XU100), hazır fırsatlar (haberli / yalnız teknik ayrı) ve sonuçları, işlem günlüğünde
hafta içinde kapanan işlemler, takip listesi olayları, haber akışı ve yapay zekâ maliyeti (ön eleme ve tekrar
ayıklamanın kazandırdığı dahil). Arşive "YYYY-AA-GG_haftalik" adıyla yazılır (haftanın son işlem günü).
Haftanın son işlem gününün akşam analizinden sonra bekçi kendiliğinden üretir; panelden elle de üretilebilir.
"""
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from . import config, market_calendar


def week_bounds(d: date) -> Tuple[date, date]:
    mon = d - timedelta(days=d.weekday())
    return mon, mon + timedelta(days=4)


def last_trading_day_of_week(d: date) -> Optional[date]:
    mon, fri = week_bounds(d)
    days = [mon + timedelta(days=i) for i in range(5) if market_calendar.is_trading_day(mon + timedelta(days=i))]
    return days[-1] if days else None


def _pct(a, b):
    return (a / b - 1) * 100 if a and b else None


def _index_week(conn, mon: date, fri: date) -> Dict:
    prev = conn.execute("SELECT date, close FROM prices WHERE ticker='XU100' AND date<? ORDER BY date DESC LIMIT 1",
                        (mon.isoformat(),)).fetchone()
    last = conn.execute("SELECT date, close FROM prices WHERE ticker='XU100' AND date<=? AND date>=? ORDER BY date DESC "
                        "LIMIT 1", (fri.isoformat(), mon.isoformat())).fetchone()
    if not (prev and last):
        return {}
    return {"onceki": prev["close"], "son": last["close"], "son_gun": last["date"], "degisim_%": _pct(last["close"], prev["close"])}


def _ready(conn, mon: date, fri: date) -> Dict:
    from . import ready
    rows = [r for r in ready.rows_for(conn) if mon.isoformat() <= r["giris_gunu"] <= fri.isoformat()]
    closed_week = [r for r in ready.rows_for(conn, durum=["kapandi"])
                   if mon.isoformat() <= (r["sonuc"].get("cikis_gunu") or "") <= fri.isoformat()]
    out = {}
    for k in ("haber", "teknik"):
        rr = [r for r in rows if r["kaynak"] == k]
        out[k] = {"onerilen": len(rr), "liste": rr,
                  "kapanan_bu_hafta": [r for r in closed_week if r["kaynak"] == k],
                  "genel": ready.performance(conn, k)}
    return out


def _journal(conn, mon: date, fri: date) -> List[Dict]:
    out = []
    for r in conn.execute("SELECT * FROM trade_journal WHERE sonuc_json IS NOT NULL ORDER BY id"):
        res = json.loads(r["sonuc_json"])
        if res.get("durum") == "kapandı" and mon.isoformat() <= (res.get("cikis_gunu") or "") <= fri.isoformat():
            out.append({"hisse": r["ticker"], "kaynak": r["kaynak"], "senaryo": r["senaryo"], "sonuc": res.get("sonuc"),
                        "net_%": res.get("net_getiri_pct"), "r": res.get("r"), "gun": res.get("islem_gunu")})
    return out


def _ai(conn, mon: date, fri: date) -> Dict:
    lo, hi = mon.isoformat(), (fri + timedelta(days=3)).isoformat()      # hafta sonu dahil (Pazar sonuna kadar)
    has = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_calls'").fetchone()
    calls = list(conn.execute("SELECT COUNT(*), COALESCE(SUM(usd),0), COALESCE(SUM(durum='hata'),0) FROM ai_calls "
                              "WHERE zaman>=? AND zaman<?", (lo, hi)).fetchone()) if has else [0, 0.0, 0]
    # Çağrı kaydı (ai_calls) 14.11.2026'da başladı: ondan önceki haber analizleri analyses tablosundaki tokenlardan
    from .ai_service import usd as _usd
    first = conn.execute("SELECT MIN(zaman) FROM ai_calls").fetchone()[0] if has else None
    old = conn.execute("SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM analyses "
                       "WHERE created_at>=? AND created_at<?" + (" AND created_at<?" if first else ""),
                       (lo, hi, first) if first else (lo, hi)).fetchone()
    calls[0] += old[0]
    calls[1] += _usd(old[1], old[2])
    news = dict(conn.execute("SELECT status, COUNT(*) FROM news WHERE fetched_at>=? AND fetched_at<? GROUP BY status",
                             (lo, hi)).fetchall())
    rutin = conn.execute("SELECT COUNT(*) FROM news WHERE status='skipped' AND note LIKE 'Python ön eleme:%' "
                         "AND fetched_at>=? AND fetched_at<?", (lo, hi)).fetchone()[0]
    return {"cagri": calls[0], "usd": calls[1], "hata": calls[2], "haber_durum": news, "rutin": rutin,
            "tekrar": news.get("duplicate", 0), "yeni_haber": sum(news.values())}


def _watch(conn, mon: date, fri: date) -> Dict:
    rows = conn.execute("SELECT tur, COUNT(*) FROM takip_olay WHERE gun>=? AND gun<=? GROUP BY tur",
                        (mon.isoformat(), fri.isoformat())).fetchall()
    return {r[0]: r[1] for r in rows}


def _fmt(v, f="{:+.2f}"):
    return "—" if v is None else f.format(v)


def _perf_line(g: Dict) -> str:
    if not g.get("kapanan"):
        return f"önerilen {g['onerilen']}, kapanan 0 (henüz sonuç yok)"
    return (f"önerilen {g['onerilen']}, kapanan {g['kapanan']} · kazanma %{g['Kazanma %']:.0f} · TP1 %{g['TP1 %']:.0f} · "
            f"SL %{g['SL %']:.0f} · ort. net %{g['Ort. net %']:+.2f}"
            + (" · ⚠️ 30'dan az kapanan: oranlar güvenilir değil" if g["kapanan"] < 30 else ""))


TR_TUR = {"giris": "giriş", "sl": "zarar durdur", "tp": "hedef", "gecersiz": "geçersiz", "hacim": "hacim",
          "kirilim": "kırılım", "teyit": "teyit", "haber": "haber", "teknik": "teknik"}


def build(conn, d: Optional[date] = None) -> Tuple[str, Dict]:
    from . import ready
    d = d or datetime.now(config.TR_TZ).date()
    mon, fri = week_bounds(d)
    rng = f"{mon.strftime('%d.%m')}–{fri.strftime('%d.%m.%Y')}"
    idx, rd, jr, ai, wt = _index_week(conn, mon, fri), _ready(conn, mon, fri), _journal(conn, mon, fri), \
        _ai(conn, mon, fri), _watch(conn, mon, fri)
    md = f"# 📅 Haftalık rapor — {rng}\n\n_Yalnız kayıtlı veriden kodla hesaplandı; yapay zekâ kullanılmadı. " \
         "Yatırım tavsiyesi değildir._\n\n"
    md += "## 1. Piyasa\n"
    md += (f"- BIST 100 hafta: **%{idx['degisim_%']:+.2f}** ({idx['onceki']:.0f} → {idx['son']:.0f}, son gün {idx['son_gun']})\n\n"
           if idx.get("degisim_%") is not None else "- BIST 100 haftalık değişim hesaplanamadı (fiyat kaydı yok).\n\n")
    md += "## 2. Hazır fırsatlar bu hafta\n"
    for k, title in (("haber", "📰 Haberli"), ("teknik", "📐 Yalnız teknik")):
        x = rd[k]
        md += f"### {title}\n"
        if not x["liste"]:
            md += "- Bu hafta öneri yok (uygun yoksa liste doldurulmaz).\n"
        else:
            md += "| Giriş günü | Hisse | Tür | Giriş | SL | TP1 | Durum | Sonuç | Net % |\n|---|---|---|---|---|---|---|---|---|\n"
            for r in x["liste"]:
                md += (f"| {r['giris_gunu']} | {r['ticker']} | {ready.TYPE_NAMES.get(r['tur'], r['tur'])} | {r['giris']:.2f} | "
                       f"{r['sl']:.2f} | {r['tp1']:.2f} | {ready.STATE_TR.get(r['durum'], r['durum'])} | "
                       f"{r['sonuc'].get('sonuc') or (r.get('iptal_nedeni') or '')[:50]} | {_fmt(r['sonuc'].get('net_getiri_pct'))} |\n")
        if x["kapanan_bu_hafta"]:
            md += "- Bu hafta kapanan: " + ", ".join(
                f"{r['ticker']} {r['sonuc'].get('sonuc')} (%{r['sonuc'].get('net_getiri_pct', 0):+.2f})"
                for r in x["kapanan_bu_hafta"]) + "\n"
        md += f"- Başından beri: {_perf_line(x['genel'])}\n\n"
    md += "## 3. İşlem günlüğü — bu hafta kapananlar\n"
    if not jr:
        md += "- Bu hafta kapanan işlem yok.\n\n"
    else:
        md += "| Hisse | Tür | Senaryo | Sonuç | Net % | R | İşlem günü |\n|---|---|---|---|---|---|---|\n"
        for r in jr:
            md += (f"| {r['hisse']} | {'gerçek' if r['kaynak'] == 'gercek' else 'sanal'} | {r['senaryo']} | {r['sonuc']} | "
                   f"{_fmt(r['net_%'])} | {_fmt(r['r'])} | {r['gun'] or '—'} |\n")
        wins = [r for r in jr if (r["net_%"] or 0) > 0]
        md += f"\n- {len(jr)} işlemden {len(wins)} kazançlı; ortalama net %{sum(r['net_%'] or 0 for r in jr) / len(jr):+.2f}.\n\n"
    md += "## 4. Takip listesi (bekçi olayları)\n"
    md += ("- " + " · ".join(f"{TR_TUR.get(k, k)}: {v}" for k, v in sorted(wt.items())) + "\n\n") if wt else \
        "- Bu hafta takip olayı yok.\n\n"
    md += "## 5. Haber akışı ve yapay zekâ maliyeti\n"
    md += (f"- Gelen haber: {ai['yeni_haber']} · Python ön elemesiyle atlanan rutin haber: {ai['rutin']} · tekrar diye "
           f"atlanan: {ai['tekrar']} (bunlar ücretlendirilmedi)\n"
           f"- Yapay zekâ çağrısı: {ai['cagri']} (hata {ai['hata']}) · tahmini maliyet **{ai['usd']:.3f} $**\n\n")
    md += ("_Kurallar (hazır fırsat, yalnız teknik, genel puan) yeni ve henüz sınanmadı; oranlar en az 30 kapanmış "
           "öneriden sonra anlamlı olur._\n")
    data = {"hafta": [mon.isoformat(), fri.isoformat()], "endeks": idx, "gunluk": jr, "takip": wt, "yz": ai,
            "hazir": {k: {"onerilen": v["onerilen"], "genel": v["genel"],
                          "kapanan_bu_hafta": [r["ticker"] for r in v["kapanan_bu_hafta"]]} for k, v in rd.items()}}
    return md, data


def telegram_text(data: Dict) -> str:
    h, idx, ai = data["hazir"], data["endeks"], data["yz"]
    t = f"📅 Halley haftalık özet ({data['hafta'][0][8:10]}.{data['hafta'][0][5:7]}–{data['hafta'][1][8:10]}.{data['hafta'][1][5:7]})\n"
    if idx.get("degisim_%") is not None:
        t += f"BIST 100: %{idx['degisim_%']:+.2f}\n"
    for k, name in (("haber", "Haberli hazır fırsat"), ("teknik", "Yalnız teknik")):
        t += f"{name}: bu hafta {h[k]['onerilen']} öneri · başından beri {_perf_line(h[k]['genel'])}\n"
    if data["gunluk"]:
        t += f"İşlem günlüğü: bu hafta {len(data['gunluk'])} işlem kapandı\n"
    t += f"Yapay zekâ: {ai['cagri']} çağrı ≈ {ai['usd']:.3f} $ · ücretsiz atlanan rutin/tekrar haber: {ai['rutin'] + ai['tekrar']}\n"
    t += "Ayrıntı: Halley → 🛡️ Bekçi → rapor arşivi (Tür: Haftalık)."
    return t


def run(conn, d: Optional[date] = None, send=None) -> str:
    """Raporu üretir ve arşive yazar; Telegram açıksa kısa özet gönderir. Arşiv adını döndürür."""
    from . import notify, pipeline, watchdog
    d = d or datetime.now(config.TR_TZ).date()
    day = last_trading_day_of_week(d) or week_bounds(d)[1]
    md, data = build(conn, d)
    name = watchdog.archive(day.isoformat(), "haftalik", md, data)
    if notify.configured() and pipeline.load_settings().get("telegram_acik"):
        try:
            (send or notify.send)(telegram_text(data) + notify.FOOT)
        except Exception:
            pass
    return name
