"""Akıllı Piyasa Bekçisi (W, 2026-11-07): botun kararlarını kaydeder, denetler, raporlar.

Kullanıcı isteği: sabah (borsa açılmadan) ve akşam (kapanıştan sonra) analizleri — kullanıcı ELLE başlatır; otomatik
emir YOK, ayarları kendiliğinden DEĞİŞTİRMEZ (öneriler kullanıcı onayına sunulur). Rutin kontrollerde yapay zekâ yok.

W1 — sinyal geçmişi: her çalıştırmada evrendeki her hisse için karar izi (önerildi / önerilmedi + neden + modül).
Kayıtlar yalnız eklenir (veritabanı tetikleyicileri değiştirmeyi/silmeyi reddeder): kaçırılan fırsat analizi o gün
botun BİLDİĞİ ile yapılır, geriye dönük bilgi karışmaz.
"""
import json
from collections import Counter
from datetime import date, datetime, timedelta
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
    try:   # D (2026-11-09): o günün piyasa rejimi karar kaydıyla saklanır (ileride rejime göre başarı ölçülür)
        from . import regime
        rg = regime.regime(conn, ctx.today)
        summary["rejim"] = {k: rg.get(k) for k in ("gun", "trend", "oynaklik", "genislik_%")} if not rg.get("yok") else None
    except Exception:
        summary["rejim"] = None
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


def saved_settings() -> Dict:
    """Panelde kayıtlı ayarlardan bekçi çalıştırma ayarları (otomatik akşam/sabah analizi için)."""
    from . import ai_comment, journal, notify, pipeline
    s = pipeline.load_settings()
    return {"gun": int(s.get("kap_gun", 1)), "analiz_siniri": int(s.get("panel_analiz_siniri", 10)),
            "analiz_kalitesi": s.get("analiz_kalitesi"), "pencere": int(s.get("liste_pencere", 7)),
            "komisyon_pct": float(s.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT)),
            "kayma_pct": float(s.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT)),
            "sermaye": float(s.get("sermaye", 0.0)), "risk_pct": float(s.get("risk_pct", 0.0)),
            "yz_butce_usd": float(s.get("yz_butce_usd", ai_comment.DEFAULT_BUDGET_USD)),
            "yz_rapor": False, "yz_kacirilan": False,
            "telegram": bool(notify.configured() and s.get("telegram_acik")),
            "hazir_sabah_yz": bool(s.get("hazir_sabah_yz", False))}


def run_auto(conn, kind: str, now: Optional[datetime] = None) -> Dict:
    """Bekçinin kendiliğinden başlattığı sabah/akşam analizi (2026-11-10 kullanıcı onayı). Yapay zekâ ile HABER ANALİZİ
    YAPILMAZ (ai=False); yalnız kullanıcı "sabah haber kontrolü" düğmesini açtıysa hazır fırsatların yeni haberleri
    bütçe içinde analiz edilir. Rapor arşive yazılır, Telegram özeti ayara göre gider."""
    from . import pipeline
    out = run_session(conn, pipeline.universe(conn), kind, saved_settings(), ai=False, now=now)
    return {"rapor": out.get("rapor"), "hazir": len((out.get("hazir") or {}).get("secilen") or [])}


def run_session(conn, universe: Dict[str, str], kind: str, settings: Dict, ai: bool = False,
                progress=None, now: Optional[datetime] = None, steps=None) -> Dict:
    """Sabah ya da akşam analizi. steps: test için adım işlevleri (update/prices) değiştirilebilir."""
    from . import journal, pipeline, prices
    say = progress or (lambda m, p: None)
    now = now or datetime.now(config.TR_TZ)
    steps = steps or {}
    tm = timing(kind, now)
    out = {"tur": kind, "zaman": tm, "yz": ai, "evren": sorted(universe),
           "ayarlar": {k: settings[k] for k in ("komisyon_pct", "kayma_pct", "sermaye", "risk_pct") if k in settings}}
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
    if kind == "aksam":
        say("Kaçırılan fırsatlar inceleniyor (o günkü karar kaydına göre)...", 0.85)
        from . import missed
        res = missed.scan(conn, now.date())
        out["kacirilan"] = dict(missed.report_md(res), ham=res)
        from . import trends
        out["oneriler"] = trends.sync(conn, now.date())
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
    # 2026-11-10 Hazır Fırsatlar: akşam ertesi gün listesi, sabah yeniden kontrol (bkz. bist_haber/ready.py)
    from . import ready
    say("Hazır fırsatlar seçiliyor..." if kind == "aksam" else "Hazır fırsatlar sabah kontrolünden geçiriliyor...", 0.9)
    rows_ = report.build(conn, universe, days=int(settings.get("pencere", 7)))
    if kind == "aksam":
        out["hazir"] = ready.evening(conn, ctx, rows_, now, universe=universe)
    else:
        out["hazir"] = ready.morning(conn, ctx, rows_, now, ai=bool(settings.get("hazir_sabah_yz")),
                                     news_fn=steps.get("hazir_haber"), universe=universe)
    say("Rapor hazırlanıyor...", 0.95)
    md, data = (morning_report if kind == "sabah" else evening_report)(conn, ctx, out)
    hz = ready.report_md(out["hazir"])
    md = md.replace("## 1.", hz + "## 1.", 1) if "## 1." in md else md + hz
    data["hazir"] = {k: v for k, v in out["hazir"].items() if k in ("secilen", "elenen", "giris_gunu", "haber", "teknik")}
    md, data = _ai_sections(conn, kind, now, md, data, out, settings, steps.get("llm"), say)
    out["rapor"] = archive(now.date().isoformat(), kind, md, data)
    if settings.get("telegram"):  # 2026-11-09: rapor arşive yazıldıktan SONRA; hata analizi bozmaz
        from . import notify
        say("Telegram bildirimi gönderiliyor...", 0.99)
        from . import tracker
        watch = {w["ticker"] for w in tracker.watched(conn)}
        out["bildirim"] = notify.send(notify.session_message(kind, out, data, watch))
    say("Tamamlandı.", 1.0)
    return out


def _ai_sections(conn, kind, now, md, data, out, settings, llm, say):
    """W6: kullanıcı kutuyu açtıysa yapay zekâ yorumu (bütçe denetimli). Kodla hesaplanan bölümler değişmez."""
    from . import ai_comment
    extra = ""
    if settings.get("yz_rapor"):
        say("Yapay zekâ raporu yorumluyor...", 0.96)
        r = ai_comment.comment_report(conn, kind, f"{now.date().isoformat()}_{kind}", md, settings, llm=llm)
        extra += ai_comment.report_md(r)
        data["yz_yorum"] = r
        out["yz_yorum"] = r
    if kind == "aksam" and settings.get("yz_kacirilan") and out.get("kacirilan"):
        items = out["kacirilan"]["ham"]["liste"]
        el = ai_comment.eligible(items)
        say(f"Yapay zekâ kaçırılan fırsatları açıklıyor ({min(len(el), ai_comment.MAX_MISSED)} hisse)...", 0.97)
        rs = ai_comment.explain_missed(conn, items, settings, llm=llm)
        extra += ai_comment.missed_md(rs, len(el))
        data["yz_kacirilan"] = rs
        out["yz_kacirilan"] = rs
    if extra:
        md = md.replace(DISCLAIMER, extra + DISCLAIMER_AI) if DISCLAIMER in md else md + extra + DISCLAIMER_AI
    return md, data


def _recommended(conn, run_id):
    return [dict(r) for r in conn.execute("SELECT * FROM signal_log WHERE run_id=? AND karar='onerildi' "
                                          "ORDER BY haber_skoru DESC", (run_id,))]


def _watchlist(conn, run_id):
    return [dict(r) for r in conn.execute("SELECT * FROM signal_log WHERE run_id=? AND karar='onerilmedi' AND "
                                          "haber_skoru>=1.0 ORDER BY haber_skoru DESC", (run_id,))]


DISCLAIMER_AI = ("\n---\n_Bu rapor kayıtlı veriden kodla üretildi; yalnız 🤖 işaretli bölümler yapay zekâ yorumudur "
                 "(kodla hesaplanan bölümleri değiştirmez). Senaryolar bilgi amaçlıdır; yatırım tavsiyesi değildir. "
                 "Emirleri kullanıcı Midas'tan elle verir._\n")


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
    from . import regime
    md += "**📊 Piyasa durumu:** " + regime.regime(conn, ctx.today).get("ozet", "—") + "\n\n"
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
    from . import sectors
    pf = sectors.portfolio(conn, ctx.today)
    if pf["uyarilar"]:
        md += "**🧺 Portföy riski:**\n" + "".join(f"- {w}\n" for w in pf["uyarilar"]) + "\n"
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


def market_summary(conn, universe, today: date) -> Dict:
    """Bölüm 1: son işlem gününün piyasa özeti (kayıtlı OHLCV'den; tahmin yok).
    Sıralamalar likit hisselerle yapılır (20 günlük ort. işlem hacmi ≥ tradeplan.LIQ_MIN_TL): sığ hisselerin
    sıçramaları özeti bozmasın."""
    from . import tradeplan
    bench = "XU100"
    days = [r[0] for r in conn.execute("SELECT DISTINCT date FROM prices WHERE ticker=? AND date<=? ORDER BY date DESC "
                                       "LIMIT 21", (bench, today.isoformat()))]
    if len(days) < 2:
        return {"yok": "Endeks (XU100) fiyatı kayıtlı değil: piyasa özeti hesaplanamadı."}
    d, prev = days[0], days[1]
    px = {}
    for r in conn.execute("SELECT ticker, date, close, volume FROM prices WHERE date IN (?,?)", (d, prev)):
        px.setdefault(r["ticker"], {})[r["date"]] = (r["close"], r["volume"] or 0)
    liq = dict(conn.execute("SELECT ticker, AVG(close*volume) FROM prices WHERE date>=? AND date<=? GROUP BY ticker",
                            (days[-1], d)).fetchall())
    out = {"gun": d, "onceki_gun": prev, "bugun_islem_gunu_degil": d != today.isoformat()}
    b = px.get(bench, {})
    if d in b and prev in b:
        out["xu100"] = b[d][0]
        out["xu100_%"] = (b[d][0] / b[prev][0] - 1) * 100
    moves = []
    for t in universe:
        p = px.get(t, {})
        if d in p and prev in p and p[prev][0]:
            moves.append({"hisse": t, "kapanis": p[d][0], "degisim_%": (p[d][0] / p[prev][0] - 1) * 100,
                          "hacim_tl": p[d][0] * p[d][1], "ort_hacim_tl": liq.get(t)})
    if not moves:
        out["yok"] = f"{d} için hisse fiyatı yok."
        return out
    ch = sorted(m["degisim_%"] for m in moves)
    out.update({"hisse": len(moves), "yukselen": sum(1 for x in ch if x > 0.005),
                "dusen": sum(1 for x in ch if x < -0.005), "medyan_%": ch[len(ch) // 2],
                "toplam_hacim_tl": sum(m["hacim_tl"] for m in moves),
                "tavana_yakin": sum(1 for x in ch if x >= 9.5), "tabana_yakin": sum(1 for x in ch if x <= -9.5)})
    out["esit"] = len(ch) - out["yukselen"] - out["dusen"]
    out["limit_disi"] = sorted((m for m in moves if abs(m["degisim_%"]) > 10.5), key=lambda m: -abs(m["degisim_%"]))
    liquid = [m for m in moves if (m["ort_hacim_tl"] or 0) >= tradeplan.LIQ_MIN_TL]
    liquid.sort(key=lambda m: m["degisim_%"])
    out["likit_hisse"] = len(liquid)
    out["en_cok_yukselen"] = list(reversed(liquid[-5:]))
    out["en_cok_dusen"] = liquid[:5]
    return out


def _journal_all(conn):
    out = []
    for r in conn.execute("SELECT * FROM trade_journal ORDER BY id"):
        x = dict(r)
        x["res"] = json.loads(r["sonuc_json"]) if r["sonuc_json"] else {}
        out.append(x)
    return out


def _unrealized(rec, last):
    """Açık işlemin gerçekleşmemiş getirisi (%): TP1'de yarısı satıldıysa o yarı TP1'den sayılır (o kısım gerçekleşmiş)."""
    res = rec["res"]
    fill = res.get("giris_fiyati")
    if not fill or not last:
        return None, None
    if res.get("tp1_goruldu"):
        return 0.5 * (last / fill - 1) * 100, 0.5 * (rec["tp1"] / fill - 1) * 100
    return (last / fill - 1) * 100, 0.0


def _tl(settings, rec, pct):
    """Plan büyüklüğüyle TL karşılığı (Ayarlar'da sermaye ve risk yüzdesi girildiyse)."""
    from . import journal
    cap, risk = float(settings.get("sermaye") or 0), float(settings.get("risk_pct") or 0)
    if pct is None or not (cap > 0 and risk > 0):
        return None
    entry = rec["res"].get("giris_fiyati") or rec["giris"]
    try:
        ps = journal.position_size(cap, risk, rec["giris"], rec["sl"],
                                   float(settings.get("komisyon_pct", 0.2)) + float(settings.get("kayma_pct", 0.1)))
    except ValueError:
        return None
    return ps["adet"] * entry * pct / 100


def _closed_class(res) -> str:
    s = res.get("sonuc")
    if s == "TP2":
        return "başarılı"
    if s == "başabaş (TP1 sonrası)":
        return "başarılı (TP1 alındı, kalan başabaş)"
    if s == "SL":
        return "başarısız"
    return "olumlu" if (res.get("net_getiri_pct") or 0) > 0 else "olumsuz"   # süre doldu


def evening_report(conn, ctx, out) -> tuple:
    """Akşam raporu — kullanıcının istediği 10 bölüm. Yalnız kayıtlı veri; yapay zekâ yok."""
    from . import journal
    settings = out.get("ayarlar") or {}
    cost = float(settings.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT)) + \
        float(settings.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT))
    run_id = out["calistirma"]["run_id"]
    uni = out.get("evren") or []
    ms = market_summary(conn, uni, ctx.today)
    D = ms.get("gun") or ctx.today.isoformat()
    md = _header("aksam", out["zaman"]["zaman"], out["zaman"])
    if ms.get("bugun_islem_gunu_degil"):
        md += f"> ℹ️ Bugün için fiyat yok; rapor son işlem günü **{D}** verisiyle hazırlandı.\n\n"

    # 1 — piyasa özeti
    md += "## 1. Günlük piyasa özeti\n"
    from . import regime
    md += "**📊 Piyasa rejimi:** " + regime.regime(conn, ctx.today).get("ozet", "—") + "\n\n"
    if ms.get("yok") and "hisse" not in ms:
        md += f"_{ms['yok']}_\n\n"
    else:
        md += (f"- BIST 100: {_fmt(ms.get('xu100'))} ({_fmt(ms.get('xu100_%'), '{:+.2f}')}%) · {D} (önceki: "
               f"{ms['onceki_gun']})\n- {ms['hisse']} hissede: {ms['yukselen']} yükselen, {ms['dusen']} düşen, "
               f"{ms['esit']} değişmeyen · medyan değişim %{ms['medyan_%']:+.2f} · toplam işlem hacmi "
               f"{ms['toplam_hacim_tl'] / 1e9:.1f} milyar TL\n- %9,5 ve üzeri yükselen: {ms['tavana_yakin']} · %9,5 ve "
               f"üzeri düşen: {ms['tabana_yakin']}\n")
        if ms.get("limit_disi"):
            md += (f"- ⚠️ Günlük ±%10 fiyat limitini aşmış görünen {len(ms['limit_disi'])} hisse: "
                   + ", ".join(f"{x['hisse']} %{x['degisim_%']:+.1f}" for x in ms["limit_disi"][:10])
                   + " — bedelsiz/temettü düzeltmesi, yeni halka arz ya da veri hatası olabilir; kontrol edin.\n")
        md += "\n"
        cols = [("Hisse", lambda r: r["hisse"]), ("Kapanış", lambda r: _fmt(r["kapanis"])),
                ("Değişim %", lambda r: _fmt(r["degisim_%"], "{:+.2f}")),
                ("Günlük hacim (mn TL)", lambda r: _fmt(r["hacim_tl"] / 1e6, "{:.1f}"))]
        md += (f"En çok yükselen / düşen likit hisseler ({ms['likit_hisse']} hisse; 20 günlük ortalama işlem hacmi ≥ 2 "
               "milyon TL):\n\n**En çok yükselen**\n\n" + _md_table(ms["en_cok_yukselen"], cols)
               + "\n**En çok düşen**\n\n" + _md_table(ms["en_cok_dusen"], cols) + "\n")
        from . import sectors
        ds = sectors.day_sectors(conn, ctx.today)
        if ds["sektorler"]:
            fmt_ = lambda xs: ", ".join(f"{x['sektor'].title()} %{x['degisim_%']:+.1f}" for x in xs)
            md += ("**Günün sektörleri** (KAP ana sektörleri; likit hisselerin günlük değişim ortancası): en iyi — "
                   + fmt_(ds["sektorler"][:3]) + " · en zayıf — " + fmt_(ds["sektorler"][-3:][::-1]) + "\n\n")

    # 2 — botun önerileri (bugünkü çalıştırmalar)
    rec = _recommended(conn, run_id)
    morning = conn.execute("SELECT run_id FROM watch_runs WHERE kind='sabah' AND day=? ORDER BY run_id DESC LIMIT 1",
                           (ctx.today.isoformat(),)).fetchone()
    m_rec = _recommended(conn, morning["run_id"]) if morning else []
    last_px = {r["ticker"]: r for r in conn.execute(
        "SELECT ticker, close FROM prices WHERE date=?", (D,))}
    md += "## 2. Botun ürettiği hisse önerileri\n"
    if morning:
        md += f"Sabah analizinde {len(m_rec)} öneri vardı" + (": " + ", ".join(r["ticker"] for r in m_rec) if m_rec else "") + ".\n\n"
    else:
        md += "_Bugün sabah analizi çalıştırılmamış._\n\n"
    md += "Akşam (kapanış verisiyle) önerilen:\n\n" + _md_table(rec, [
        ("Hisse", lambda r: r["ticker"]), ("Senaryo", lambda r: r["senaryo"]), ("Giriş", lambda r: _fmt(r["giris"])),
        ("SL", lambda r: _fmt(r["sl"])), ("TP1", lambda r: _fmt(r["tp1"])), ("TP2", lambda r: _fmt(r["tp2"])),
        ("Risk", lambda r: r["risk_seviyesi"] or "—"), ("Haber skoru", lambda r: _fmt(r["haber_skoru"]))]) + "\n"

    # 3–6 — işlem günlüğü
    rows = _journal_all(conn)
    for r in rows:
        r["son"] = last_px[r["ticker"]]["close"] if r["ticker"] in last_px else None
    opened = [r for r in rows if r["res"].get("giris_gunu") == D and r["durum"] != "iptal"]
    closed_today = [r for r in rows if r["res"].get("cikis_gunu") == D]
    ongoing = [r for r in rows if r["durum"] in journal.OPEN_STATES]
    changes = {c["id"]: c for c in (out.get("gunluk") or {}).get("degisenler", [])}
    cancelled = [r for r in rows if r["id"] in changes and changes[r["id"]]["yeni"] == "iptal"]
    tur = lambda r: "Gerçek" if r["kaynak"] == "gercek" else "Sanal"
    md += "## 3. Gerçekleşen ve devam eden işlemler\n"
    md += (f"Bugün ({D}) girişi gerçekleşen: {len(opened)} · kapanan: {len(closed_today)} · süresi dolup iptal olan: "
           f"{len(cancelled)} · devam eden (açık + giriş bekleyen): {len(ongoing)}\n\n")
    for r in ongoing:
        r["gerc_disi_%"], r["gerc_%"] = _unrealized(r, r["son"]) if r["durum"] != "bekliyor" else (None, None)
    md += _md_table(ongoing, [
        ("No", lambda r: r["id"]), ("Tür", tur), ("Hisse", lambda r: r["ticker"]), ("Senaryo", lambda r: r["senaryo"]),
        ("Durum", lambda r: r["durum"] + (" (bugün girildi)" if r in opened else "")),
        ("Giriş", lambda r: _fmt(r["res"].get("giris_fiyati") or r["giris"])),
        ("Stop", lambda r: _fmt(r["res"].get("stop", r["sl"]))), ("Son kapanış", lambda r: _fmt(r["son"]))]) + "\n"
    if cancelled:
        md += "".join(f"- ⌛ #{r['id']} {r['ticker']} ({tur(r)}): {r['gecerlilik']} işlem gününde giriş koşulu oluşmadı\n"
                      for r in cancelled) + "\n"

    md += "## 4. TP1, TP2 ve SL sonuçları\n"
    tp1_today = [r for r in rows if any(str(e).startswith(D) and "TP1" in str(e) for e in r["res"].get("olaylar", []))]
    md += (f"Bugün: TP1 görülen {len(tp1_today)}" + (f" ({', '.join(r['ticker'] for r in tp1_today)})" if tp1_today else "")
           + " · kapanış sonuçları: " + (", ".join(f"{r['ticker']} {r['res']['sonuc']}" for r in closed_today) or "yok")
           + "\n\n")
    closed = [r for r in rows if r["durum"] == "kapandı"]
    for k in ("otomatik", "gercek"):
        m = journal.metrics(conn, k)
        if m["kayit"]:
            md += (f"- Toplam ({'sanal' if k == 'otomatik' else 'gerçek'}): {m['kayit']} kayıt, {m['kapanan']} kapandı, "
                   f"{m['acik_bekleyen']} açık/bekliyor, {m['iptal']} gerçekleşmedi"
                   + (" · sonuçlar: " + ", ".join(f"{s} {n}" for s, n in m["sonuc_dagilimi"].items())
                      if m.get("sonuc_dagilimi") else "") + "\n")
    md += ("_Aynı gün hem SL hem TP görülürse SL sayılır; limit emrin dolduğu gün TP sayılmaz (mum içi sıra bilinmez — "
           "temkinli kural)._\n\n")

    md += "## 5. Gerçekleşmiş ve gerçekleşmemiş net kâr/zarar\n"
    real_today = [r for r in closed_today]
    tl_note = not (float(settings.get("sermaye") or 0) > 0 and float(settings.get("risk_pct") or 0) > 0)
    md += _md_table(real_today, [
        ("No", lambda r: r["id"]), ("Tür", tur), ("Hisse", lambda r: r["ticker"]), ("Sonuç", lambda r: r["res"]["sonuc"]),
        ("Brüt %", lambda r: _fmt(r["res"].get("brut_getiri_pct"), "{:+.2f}")),
        ("Net %", lambda r: _fmt(r["res"].get("net_getiri_pct"), "{:+.2f}")), ("R", lambda r: _fmt(r["res"].get("r"))),
        ("Net TL (plan büyüklüğü)", lambda r: _fmt(_tl(settings, r, r["res"].get("net_getiri_pct")), "{:+,.0f}"))])
    tot = {k: [r for r in closed if r["kaynak"] == k] for k in ("otomatik", "gercek")}
    for k, xs in tot.items():
        if xs:
            nets = [r["res"]["net_getiri_pct"] for r in xs]
            rs = [r["res"]["r"] for r in xs if r["res"].get("r") is not None]
            tls = [_tl(settings, r, r["res"]["net_getiri_pct"]) for r in xs]
            md += (f"- Gerçekleşmiş toplam ({'sanal' if k == 'otomatik' else 'gerçek'}): {len(xs)} işlem, net getiri "
                   f"toplamı %{sum(nets):+.2f}, toplam {sum(rs):+.2f} R"
                   + (f", plan büyüklüğüyle {sum(tls):+,.0f} TL" if all(v is not None for v in tls) else "") + "\n")
    opn = [r for r in ongoing if r.get("gerc_disi_%") is not None]
    if opn:
        md += "\nGerçekleşmemiş (açık işlemler, son kapanışla; çıkış maliyeti düşülmüş tahmini):\n\n" + _md_table(opn, [
            ("No", lambda r: r["id"]), ("Tür", tur), ("Hisse", lambda r: r["ticker"]),
            ("Açık kısım %", lambda r: _fmt(r["gerc_disi_%"], "{:+.2f}")),
            ("TP1'de alınan %", lambda r: _fmt(r["gerc_%"], "{:+.2f}")),
            ("Toplam net % (tahmini)", lambda r: _fmt(r["gerc_disi_%"] + r["gerc_%"] - cost, "{:+.2f}")),
            ("TL (plan)", lambda r: _fmt(_tl(settings, r, r["gerc_disi_%"] + r["gerc_%"] - cost), "{:+,.0f}"))])
    if tl_note:
        md += "\n_TL karşılığı için Ayarlar'da sermaye ve risk yüzdesini girin._\n"
    md += "\n"

    md += "## 6. İşlem maliyetleri\n"
    md += (f"Varsayım: komisyon %{float(settings.get('komisyon_pct', journal.DEFAULT_COMMISSION_PCT)):.2f} + kayma "
           f"%{float(settings.get('kayma_pct', journal.DEFAULT_SLIPPAGE_PCT)):.2f} = alış+satış toplam %{cost:.2f} "
           "(Ayarlar'dan değiştirilebilir; Midas'ın gerçek oranını girin).\n")
    if closed:
        diff = sum(r["res"]["brut_getiri_pct"] - r["res"]["net_getiri_pct"] for r in closed)
        tls = [_tl(settings, r, r["res"]["brut_getiri_pct"] - r["res"]["net_getiri_pct"]) for r in closed]
        md += (f"- Kapanan {len(closed)} işlemde maliyetin getiriye etkisi toplam %{diff:.2f} puan"
               + (f" (plan büyüklüğüyle ≈ {sum(tls):,.0f} TL)" if all(v is not None for v in tls) else "") + "\n")
    md += f"- Bugün kapanan {len(closed_today)} işlemin maliyeti net getiriye dahildir.\n\n"

    # 7–8 — kaçırılan fırsatlar (W4)
    missed = out.get("kacirilan")
    md += "## 7. Kaçırılan fırsatlar\n"
    md += (missed["md_liste"] if missed else
           "_Hazırlanıyor (W4): önerilmeyip ciddi yükselen hisseler, o gün botun bildiği veriyle incelenecek._\n") + "\n"
    md += "## 8. Kaçırılma nedenleri\n"
    md += (missed["md_neden"] if missed else "_Hazırlanıyor (W4)._\n") + "\n"

    # 9 — başarılı / başarısız analizler
    md += "## 9. Botun başarılı ve başarısız analizleri\n"
    recent = [r for r in closed if r["res"].get("cikis_gunu", "") >= (ctx.today - timedelta(days=30)).isoformat()]
    for r in recent:
        r["sinif"] = _closed_class(r["res"])
    md += "Son 30 günde kapanan işlemler:\n\n" + _md_table(recent, [
        ("No", lambda r: r["id"]), ("Tür", tur), ("Hisse", lambda r: r["ticker"]), ("Senaryo", lambda r: r["senaryo"]),
        ("Risk", lambda r: r["risk_seviyesi"] or "—"), ("Haber skoru", lambda r: _fmt(r["haber_skoru"])),
        ("Sonuç", lambda r: r["res"]["sonuc"]), ("Net %", lambda r: _fmt(r["res"]["net_getiri_pct"], "{:+.2f}")),
        ("Değerlendirme", lambda r: r["sinif"])]) + "\n"
    m = journal.metrics(conn, "otomatik")
    if m.get("kapanan"):
        md += (f"Sanal toplam: kazanma oranı %{m['kazanma_orani_%']}, ortalama {_fmt(m.get('ortalama_R'))} R, kâr faktörü "
               f"{_fmt(m.get('kar_faktoru'))}" + ("" if m["yeterli_ornek"] else
                                                f" — **örnek az ({m['kapanan']} < {journal.MIN_TRADES_FOR_STATS}): bu "
                                                "oranlar henüz güvenilir değil**") + ".\n\n")

    # 10 — iyileştirme önerileri (veriden gözlem; ayar DEĞİŞTİRİLMEZ)
    md += "## 10. Sistem iyileştirme önerileri\n"
    notes = observations(conn, out)
    md += ("".join(f"- {n}\n" for n in notes) or "_Bugün veriden çıkan bir gözlem yok._\n")
    from . import trends
    md += trends.summary_md(conn, ctx.today)
    new = (out.get("oneriler") or {}).get("eklenen") or []
    if new:
        md += f"- Bu akşam {len(new)} yeni öneri eklendi: " + "; ".join(
            r["baslik"] for r in trends.pending(conn) if r["id"] in new) + "\n"
    md += ("\n_Öneriler bilgi amaçlıdır; hiçbir ayar kendiliğinden değiştirilmez. Geçmiş raporlarla karşılaştırmalı "
           "eğilim ve onay listesi 🧭 Gelişim sekmesinde._\n\n")
    md += data_status_md(out, _data_status(conn), "Ek")
    md += DISCLAIMER
    strip = lambda xs: [{k: v for k, v in r.items() if k not in ("sonuc_json",)} for r in xs]
    data = {"tur": "aksam", "gun": D, "zaman": out["zaman"], "piyasa": ms, "onerilen": rec, "sabah_onerilen": m_rec,
            "girilen": [r["id"] for r in opened], "kapanan": strip(closed_today), "devam": strip(ongoing),
            "iptal": [r["id"] for r in cancelled], "tp1_bugun": [r["id"] for r in tp1_today],
            "metrikler": {k: journal.metrics(conn, k) for k in ("otomatik", "gercek")}, "maliyet_%": cost,
            "gozlemler": notes, "kacirilan": missed, "calistirma": out["calistirma"]}
    return md, data


def observations(conn, out) -> list:
    """Bölüm 10 için kodla çıkarılan gözlemler (yapay zekâ yok, eşik değiştirmez)."""
    from . import journal
    n = (out.get("calistirma") or {}).get("nedenler") or {}
    total = sum(n.values()) or 1
    obs = []
    wait = n.get("HABER_ANALIZ_BEKLIYOR", 0)
    if wait:
        obs.append(f"{wait} hissenin haberi henüz analiz edilmedi (evrenin yüzde {100 * wait / total:.0f}): bu hisseler "
                   "için karar verilemedi. Sabah analizinde yapay zekâ kutusunu açmak ya da analiz sınırını artırmak "
                   "kapsamı artırır (maliyet artar; karar sizde).")
    sc = n.get("SENARYO_UYGUN_DEGIL", 0)
    if sc:
        obs.append(f"{sc} hissede haber olumlu ama giriş senaryosu uygun değildi (koşul yok ya da risk/getiri zayıf). "
                   "Bu filtre fırsat eliyor mu, kaçırılan fırsat bölümünde (7–8) izlenir; tek günlük veriyle eşik "
                   "değiştirilmemeli.")
    lq = n.get("LIKIDITE", 0)
    if lq:
        obs.append(f"{lq} hisse düşük likidite nedeniyle elendi (bilinçli koruma: sığ hissede emir fiyatı oynatır).")
    if (out.get("fiyat") or {}).get("basarisiz"):
        obs.append(f"{out['fiyat']['basarisiz']} hissenin fiyatı indirilemedi: veri sağlayıcı (Yahoo) hatası; sonraki "
                   "çalıştırmada yeniden denenir.")
    m = journal.metrics(conn, "otomatik")
    if m.get("kapanan") and not m["yeterli_ornek"]:
        obs.append(f"Sanal işlem sayısı henüz {m['kapanan']}: strateji karşılaştırması için en az "
                   f"{journal.MIN_TRADES_FOR_STATS} kapanmış işlem gerekir.")
    return obs
