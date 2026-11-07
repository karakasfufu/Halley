"""Akıllı Piyasa Bekçisi (W, 2026-11-07): botun kararlarını kaydeder, denetler, raporlar.

Kullanıcı isteği: sabah (borsa açılmadan) ve akşam (kapanıştan sonra) analizleri — kullanıcı ELLE başlatır; otomatik
emir YOK, ayarları kendiliğinden DEĞİŞTİRMEZ (öneriler kullanıcı onayına sunulur). Rutin kontrollerde yapay zekâ yok.

W1 — sinyal geçmişi: her çalıştırmada evrendeki her hisse için karar izi (önerildi / önerilmedi + neden + modül).
Kayıtlar yalnız eklenir (veritabanı tetikleyicileri değiştirmeyi/silmeyi reddeder): kaçırılan fırsat analizi o gün
botun BİLDİĞİ ile yapılır, geriye dönük bilgi karışmaz.
"""
import json
from collections import Counter
from datetime import date, datetime
from typing import Dict, Optional

from . import config, report, signals


def log_run(conn, universe: Dict[str, str], kind: str, window: int = 7, today: Optional[date] = None,
            ctx: Optional[signals.Context] = None) -> Dict:
    """Bir çalıştırmanın tüm kararlarını tek işlemde kaydeder; özet döndürür."""
    if kind not in ("sabah", "aksam", "guncelleme"):
        raise ValueError("Geçersiz çalıştırma türü")
    ctx = ctx or signals.Context(conn, today)
    rows = report.build(conn, universe, days=window, as_of=ctx.today)
    decisions = signals.decisions_all(conn, universe, rows, window=window, ctx=ctx)
    counts = Counter(d["neden_kodu"] for d in decisions)
    summary = {"hisse": len(decisions), "onerilen": counts.get("ONERILDI", 0), "nedenler": dict(counts),
               "pencere_gun": window}
    now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
    with conn:  # hepsi ya da hiçbiri
        cur = conn.execute("INSERT INTO watch_runs(kind, day, started_at, summary_json) VALUES(?,?,?,?)",
                           (kind, ctx.today.isoformat(), now, json.dumps(summary, ensure_ascii=False)))
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO signal_log(run_id,ticker,karar,neden_kodu,modul,neden,haber_skoru,haber_sayisi,son_fiyat,"
            "fiyat_gunu,senaryo,giris,sl,tp1,tp2,risk_seviyesi,detay_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, d["ticker"], d["karar"], d["neden_kodu"], d.get("modul"), d.get("neden"), d.get("haber_skoru"),
              d.get("haber_sayisi"), d.get("son_fiyat"), d.get("fiyat_gunu"), d.get("senaryo"), d.get("giris"),
              d.get("sl"), d.get("tp1"), d.get("tp2"), d.get("risk_seviyesi"),
              json.dumps(d.get("detay") or {}, ensure_ascii=False)) for d in decisions])
    summary["run_id"] = run_id
    return summary


def decision_on(conn, ticker: str, day: str) -> Optional[Dict]:
    """O GÜN (ya da öncesindeki en son çalıştırmada) bu hisse için verilen karar — kaçırılan fırsat analizi için."""
    r = conn.execute("SELECT s.*, w.kind, w.day, w.started_at FROM signal_log s JOIN watch_runs w ON w.run_id=s.run_id "
                     "WHERE s.ticker=? AND w.day<=? ORDER BY w.day DESC, w.run_id DESC LIMIT 1", (ticker, day)).fetchone()
    return dict(r) if r else None


# ---------------------------------------------------------------- W2: sabah / akşam (kullanıcı elle başlatır)
def timing(kind: str, now: Optional[datetime] = None) -> Dict:
    """BIST takvimine göre zaman kontrolü: işlem günü mü, saat uygun mu? Uyarır ama engellemez."""
    from datetime import time as _t, timedelta
    from . import market_calendar
    now = now or datetime.now(config.TR_TZ)
    d = now.date()
    trading = market_calendar.is_trading_day(d)
    close = market_calendar.session_close(d)
    warn = None
    if not trading:
        warn = "Bugün Borsa İstanbul'da işlem yok (hafta sonu ya da tatil): işlem günü analizi anlamlı değil."
    elif kind == "sabah" and now.time() >= _t(9, 40):
        warn = "Saat 09:40'ı geçti: açılış seansı başladı; sabah analizi normalde borsa açılmadan yapılır."
    elif kind == "aksam" and close and now.replace(tzinfo=None) < datetime.combine(d, close) + timedelta(minutes=10):
        warn = (f"Seans henüz kapanmadı ya da kapanış fiyatları oturmadı (kapanış {close:%H:%M}, kapanış fiyatı "
                "birkaç dakika sonra kesinleşir): akşam analizi kapanıştan sonra yapılır; şimdi çalıştırılırsa son "
                "gün yarım veri olarak işaretlenir.")
    return {"islem_gunu": trading, "uyari": warn, "zaman": now.isoformat(timespec="minutes"),
            "kapanis": f"{close:%H:%M}" if close else None}


def report_dir():
    return config.DATA / "raporlar"


def archive(day: str, kind: str, markdown: str, data: Dict) -> str:
    """Raporu tarihli dosyaya yazar; aynı gün ikinci çalıştırma yeni dosya açar (eski rapor DEĞİŞTİRİLMEZ)."""
    d = report_dir()
    d.mkdir(parents=True, exist_ok=True)
    n, name = 1, f"{day}_{kind}"
    while (d / f"{name}.md").exists():
        n += 1
        name = f"{day}_{kind}_{n}"
    (d / f"{name}.md").write_text(markdown, encoding="utf-8")
    (d / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return name


def list_reports():
    d = report_dir()
    if not d.exists():
        return []
    # yeniden eskiye, oluşturulma sırasıyla (ad sırası "_aksam"ı "_sabah"ın altına atıyordu)
    return [p.stem for p in sorted(d.glob("*.md"), key=lambda p: (p.stat().st_mtime, p.stem), reverse=True)]


def _md_table(rows, cols):
    if not rows:
        return "_Yok._\n"
    head = "| " + " | ".join(c for c, _ in cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = "".join("| " + " | ".join(str(f(r)) for _, f in cols) + " |\n" for r in rows)
    return head + body


def _fmt(v, f="{:.2f}"):
    return "—" if v is None else f.format(v)


def _journal_rows(conn):
    from . import journal
    out = []
    for r in conn.execute("SELECT * FROM trade_journal WHERE durum IN (?,?,?) ORDER BY id", journal.OPEN_STATES):
        res = json.loads(r["sonuc_json"]) if r["sonuc_json"] else {}
        last = conn.execute("SELECT close FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1", (r["ticker"],)).fetchone()
        last = last[0] if last else None
        stop = res.get("stop", r["sl"])
        out.append({"no": r["id"], "tur": "Gerçek" if r["kaynak"] == "gercek" else "Sanal", "hisse": r["ticker"],
                    "senaryo": r["senaryo"], "durum": r["durum"], "giris": res.get("giris_fiyati") or r["giris"],
                    "stop": stop, "tp1": r["tp1"], "tp2": r["tp2"], "son": last,
                    "stop_uzaklik_%": (last / stop - 1) * 100 if last and stop and r["durum"] != "bekliyor" else None,
                    "giris_uzaklik_%": (r["giris"] / last - 1) * 100 if last and r["durum"] == "bekliyor" else None,
                    "acik_getiri_%": res.get("acik_getiri_%")})
    return out


def _night_news(conn, now: datetime) -> Dict:
    from . import market_calendar
    from datetime import timedelta
    d = now.date() - timedelta(days=1)
    while not market_calendar.is_trading_day(d):
        d -= timedelta(days=1)
    since = f"{d.isoformat()}T18:00:00+03:00"
    q = lambda extra: conn.execute("SELECT COUNT(*) FROM news WHERE published_at>? AND status!='context' " + extra,
                                   (since,)).fetchone()[0]
    return {"since": since, "kap": q("AND source='kap'"), "haber_sitesi": q("AND source LIKE 'rss:%'"),
            "analiz_edilen": q("AND status='analyzed'"), "bekleyen": q("AND status='new'"),
            "onemsiz": q("AND status='skipped'")}


def _calendar_lines(conn, ctx, tickers, days=5):
    from . import timeline
    lines = []
    seen = set()
    for t in tickers:
        for x in timeline.for_ticker(conn, t, ctx.today, days)["olaylar"]:
            key = (x["tarih"], x["kapsam"], x["olay"], t if x["kapsam"] == "Hisse" else "")
            if key in seen:
                continue
            seen.add(key)
            lines.append({"tarih": x["tarih"], "kapsam": x["kapsam"], "hisse": t if x["kapsam"] == "Hisse" else "",
                          "olay": x["olay"].split(":")[0], "ayrinti": x["ayrinti"]})
    if not tickers:
        from . import macro_calendar
        for e in macro_calendar.upcoming(ctx.today, days)["olaylar"]:
            lines.append({"tarih": e["tarih"], "kapsam": "Piyasa", "hisse": "", "olay": e["ad"], "ayrinti": e.get("saat", "")})
    return sorted(lines, key=lambda x: (x["tarih"], x["kapsam"] != "Piyasa", x["hisse"]))


def _data_status(conn):
    from . import calendar_sync, kap_worker
    pend = kap_worker.pending_counts(conn)
    st = kap_worker.load()
    return {"kap_bekleyen_sayfa": pend["toplam"], "okuyucu": st.get("durum"), "takvim_kontrol": calendar_sync.summary_line()}


RISKY_STOP_PCT = 2.0   # açık işlemde son kapanış stopa bu yüzdeden yakınsa uyarı (görsel uyarı; karar kuralı değil)


def prices_retry_days() -> int:
    from . import prices
    return prices.NO_DATA_RETRY_DAYS


def data_status_md(out, ds, no) -> str:
    f = out.get("fiyat") or {}
    behind = f.get("geride") or []
    missing = f.get("fiyati_yok") or []
    lst = lambda xs: ", ".join(xs[:15]) + (" …" if len(xs) > 15 else "")
    s = (f"## {no}. Veri durumu\n- Fiyat: {f.get('hisse', 0)} şirket, son fiyat günü {f.get('son_gun') or '—'}"
         + (f"; {len(behind)} hissenin fiyatı bu günü içermiyor ({lst(behind)})" if behind else "; fiyatı olanların hepsi güncel")
         + (f"; {f['basarisiz']} hisse indirilemedi (bağlantı hatası, sonraki çalıştırmada yeniden denenir)"
            if f.get("basarisiz") else "") + "\n")
    if missing:
        s += (f"- {len(missing)} şirketin Yahoo'da hiç fiyatı yok (çoğu borsada işlem görmeyen KAP şirketi: faktoring, "
              f"varlık kiralama vb.; {prices_retry_days()} günde bir yeniden denenir): {lst(missing)}\n")
    s += f"- KAP: okunmayı bekleyen sayfa {ds['kap_bekleyen_sayfa']} (arka planda okunuyor)\n"
    s += f"- Takvim: {ds['takvim_kontrol']}\n"
    return s


def run_session(conn, universe: Dict[str, str], kind: str, settings: Dict, ai: bool = False,
                progress=None, now: Optional[datetime] = None, steps=None) -> Dict:
    """Sabah ya da akşam analizi. steps: test için adım işlevleri (update/prices) değiştirilebilir."""
    from . import journal, pipeline, prices
    say = progress or (lambda m, p: None)
    now = now or datetime.now(config.TR_TZ)
    steps = steps or {}
    tm = timing(kind, now)
    out = {"tur": kind, "zaman": tm, "yz": ai}
    commission = float(settings.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT))
    slippage = float(settings.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT))
    if kind == "sabah":
        say("Gece gelen KAP bildirimleri ve haberler toplanıyor...", 0.05)
        upd = steps.get("update") or (lambda: pipeline.update_all(
            conn, days=int(settings.get("gun", 1)), analyze=ai, analysis_limit=int(settings.get("analiz_siniri", 10)),
            quality=settings.get("analiz_kalitesi"), progress=lambda m, p: say(m, 0.05 + 0.45 * p)))
        out["guncelleme"] = upd()
    say("Tüm BIST hisselerinin fiyatları güncelleniyor (ücretsiz)...", 0.5)
    pr = steps.get("prices") or (lambda: prices.update_universe(conn, list(universe) + ["XU100"],
                                                               progress=lambda i, n: say(f"Fiyatlar ({i}/{n})...", 0.5 + 0.3 * i / max(n, 1))))
    out["fiyat"] = pr()
    say("İşlem günlüğü güncelleniyor...", 0.82)
    out["gunluk"] = journal.update_all(conn, commission, slippage)
    say("Karar izi kaydediliyor...", 0.88)
    ctx = signals.Context(conn, now.date())
    out["calistirma"] = log_run(conn, universe, kind, window=int(settings.get("pencere", 7)), ctx=ctx)
    # Önerilen senaryolar sanal işlem günlüğüne (panelin listesiyle aynı kural: hisse başına tek açık kayıt)
    out["yeni_sanal"] = []
    for r in _recommended(conn, out["calistirma"]["run_id"]):
        rid = journal.record_auto(conn, r["ticker"], ctx.plan({"ticker": r["ticker"], "score": r["haber_skoru"]}),
                                  r["fiyat_gunu"], r["haber_skoru"])
        if rid:
            out["yeni_sanal"].append({"id": rid, "hisse": r["ticker"]})
    say("Rapor hazırlanıyor...", 0.95)
    md, data = (morning_report if kind == "sabah" else evening_report)(conn, ctx, out)
    out["rapor"] = archive(now.date().isoformat(), kind, md, data)
    say("Tamamlandı.", 1.0)
    return out


def _recommended(conn, run_id):
    return [dict(r) for r in conn.execute("SELECT * FROM signal_log WHERE run_id=? AND karar='onerildi' "
                                          "ORDER BY haber_skoru DESC", (run_id,))]


def _watchlist(conn, run_id):
    return [dict(r) for r in conn.execute("SELECT * FROM signal_log WHERE run_id=? AND karar='onerilmedi' AND "
                                          "haber_skoru>=1.0 ORDER BY haber_skoru DESC", (run_id,))]


def _header(kind, now_iso, tm):
    title = {"sabah": "🌅 Sabah analizi", "aksam": "🌙 Akşam analizi"}[kind]
    h = f"# {title} — {now_iso[:10]} {now_iso[11:16]}\n\n"
    if tm.get("uyari"):
        h += f"> ⚠️ {tm['uyari']}\n\n"
    return h


DISCLAIMER = ("\n---\n_Bu rapor kayıtlı veriden kodla üretildi (yapay zekâ yorumu yok). Senaryolar bilgi amaçlıdır; "
              "yatırım tavsiyesi değildir. Emirleri kullanıcı Midas'tan elle verir._\n")


def morning_report(conn, ctx, out) -> tuple:
    run_id = out["calistirma"]["run_id"]
    rec, watch = _recommended(conn, run_id), _watchlist(conn, run_id)
    open_rows = _journal_rows(conn)
    risky = [r for r in open_rows if r["stop_uzaklik_%"] is not None and r["stop_uzaklik_%"] < RISKY_STOP_PCT]
    invalid = [c for c in out["gunluk"]["degisenler"] if c["yeni"] == "iptal"]
    night = _night_news(conn, datetime.fromisoformat(out["zaman"]["zaman"]))
    tickers = sorted({r["ticker"] for r in rec + watch} | {r["hisse"] for r in open_rows})
    cal = _calendar_lines(conn, ctx, tickers, 5) if tickers else _calendar_lines(conn, ctx, [], 5)
    md = _header("sabah", out["zaman"]["zaman"], out["zaman"])
    md += (f"## 1. Gece gelen haberler\nÖnceki kapanıştan ({night['since'][:16].replace('T', ' ')}) bu yana: KAP "
           f"{night['kap']}, haber siteleri {night['haber_sitesi']}. Bunlardan {night['onemsiz']} tanesi ön elemede "
           f"önemsiz/rutin bulundu, {night['analiz_edilen']} tanesi analiz edildi, {night['bekleyen']} tanesi analiz "
           "bekliyor." + ("" if out["yz"] else " Yapay zekâ analizi bu çalıştırmada "
                                                     "yapılmadı (kullanıcı seçimi).") + "\n\n")
    md += "## 2. Günün fırsatları (önerilen)\n" + _md_table(rec, [
        ("Hisse", lambda r: r["ticker"]), ("Senaryo", lambda r: r["senaryo"]), ("Giriş", lambda r: _fmt(r["giris"])),
        ("SL", lambda r: _fmt(r["sl"])), ("TP1", lambda r: _fmt(r["tp1"])), ("TP2", lambda r: _fmt(r["tp2"])),
        ("Risk", lambda r: r["risk_seviyesi"] or "—"), ("Haber skoru", lambda r: _fmt(r["haber_skoru"]))]) + "\n"
    md += "## 3. Takip listesi (haberi var, henüz önerilmiyor)\n" + _md_table(watch, [
        ("Hisse", lambda r: r["ticker"]), ("Haber skoru", lambda r: _fmt(r["haber_skoru"])),
        ("Neden önerilmedi", lambda r: r["neden"])]) + "\n"
    md += "## 4. Açık sanal ve gerçek işlemler\n" + _md_table(open_rows, [
        ("No", lambda r: r["no"]), ("Tür", lambda r: r["tur"]), ("Hisse", lambda r: r["hisse"]),
        ("Durum", lambda r: r["durum"]), ("Giriş", lambda r: _fmt(r["giris"])), ("Stop", lambda r: _fmt(r["stop"])),
        ("Son kapanış", lambda r: _fmt(r["son"])), ("Stopa uzaklık %", lambda r: _fmt(r["stop_uzaklik_%"], "{:+.1f}")),
        ("Girişe uzaklık %", lambda r: _fmt(r["giris_uzaklik_%"], "{:+.1f}"))]) + "\n"
    md += ("_Stopa uzaklık: açık işlemde son kapanışın stopun ne kadar üstünde olduğu. Girişe uzaklık: bekleyen "
           "senaryoda giriş için fiyatın ne kadar değişmesi gerektiği._\n\n")
    md += "## 5. Riskli ve süresi dolan senaryolar\n"
    md += ("".join(f"- ⚠️ #{r['no']} {r['hisse']}: son kapanış stopun yalnız %{r['stop_uzaklik_%']:.1f} üstünde "
                   f"(eşik %{RISKY_STOP_PCT:g})\n" if r['stop_uzaklik_%'] >= 0 else
                   f"- ⚠️ #{r['no']} {r['hisse']}: son kapanış stopun %{-r['stop_uzaklik_%']:.1f} ALTINDA (stop gün "
                   "içinde çalışmış olabilir; Midas'ta kontrol edin)\n" for r in risky)
           + "".join(f"- ⌛ #{c['id']} {c['hisse']}: geçerlilik süresi doldu, giriş koşulu oluşmadı — senaryo artık "
                     "geçerli değil (yeniden hesaplanmalı)\n" for c in invalid)
           or "_Yok._\n") + "\n"
    md += "## 6. Önümüzdeki 5 işlem günü takvimi (ilgili hisseler + piyasa)\n" + _md_table(cal, [
        ("Tarih", lambda r: r["tarih"]), ("Kapsam", lambda r: r["kapsam"]), ("Hisse", lambda r: r["hisse"] or "—"),
        ("Olay", lambda r: r["olay"]), ("Ayrıntı", lambda r: r["ayrinti"] or "")]) + "\n"
    ds = _data_status(conn)
    md += data_status_md(out, ds, "7")
    md += DISCLAIMER
    data = {"tur": "sabah", "zaman": out["zaman"], "onerilen": rec, "takip": watch, "acik": open_rows,
            "riskli": risky, "gecersiz": invalid, "gece_haberleri": night, "takvim": cal, "veri": ds,
            "calistirma": out["calistirma"]}
    return md, data


def evening_report(conn, ctx, out) -> tuple:
    """W3'te 10 bölümle genişletilecek; şimdilik temel bölümler."""
    run_id = out["calistirma"]["run_id"]
    rec = _recommended(conn, run_id)
    md = _header("aksam", out["zaman"]["zaman"], out["zaman"])
    md += "## Botun önerileri\n" + _md_table(rec, [("Hisse", lambda r: r["ticker"]), ("Senaryo", lambda r: r["senaryo"])])
    md += DISCLAIMER
    return md, {"tur": "aksam", "zaman": out["zaman"], "onerilen": rec, "calistirma": out["calistirma"]}
