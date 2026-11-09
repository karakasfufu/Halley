"""Takip Listem ve otomatik senaryo takibi (2026-11-09 kullanıcı isteği, plan Aşama 1–2).

- Kullanıcı hisseyi "+ Takibe Al" ile ekler. O hissenin uygulanabilir giriş senaryoları (kırılım, geri çekilme,
  destekten tepki — entries.py, mevcut kurallar AYNEN) ayrı ayrı kaydedilir ve izlenir. Takip listesindeki hisse için
  haber skoru şartı yoktur (kullanıcının seçimi); veri kritikse ya da likidite çok düşükse senaryo üretilmez.
- Bekçi (arka plandaki okuyucu süreci içinde, `tick`) iki tür kontrol yapar:
  * Gün içi (seans açıkken ~5 dk'da bir, Yahoo ~15 dk gecikmeli): giriş seviyesine gelme, kırılım denemesi, SL/TP'ye
    değme, hacim artışı. Bunlar "gün içi, kapanışla teyit edilmedi" diye işaretlenir.
  * Kapanış sonrası (kapanıştan 20 dk sonra, günde bir kez; kaçırılırsa ilk fırsatta): günlük mum kesinleşince giriş,
    TP1, TP2, SL, başabaş, süre dolması (journal.evaluate ile — işlem günlüğüyle AYNI kurallar), kapanış altında
    geçersizleşme, alt fitil + yükselen kapanış teyidi, destek/direnç kırılımı, hacim artışı, trend değişikliği,
    yeni senaryo.
- Veri eski ya da eksikse olay ÜRETİLMEZ (sahte sinyal yok); durum dosyasına "veri yok" yazılır.
- Aynı olay bir kez kaydedilir ve bir kez bildirilir (takip_olay.anahtar UNIQUE). Gönderilemeyen bildirim 24 saat
  içinde yeniden denenir.
- Emir VERMEZ. Yapay zekâ KULLANMAZ (haber bildirimi Aşama 4'te, bütçe denetimli).
"""
import json
from datetime import date, datetime, time, timedelta
from typing import Callable, Dict, List, Optional

from . import config, entries, journal, market_calendar, technical, tradeplan

ACTIVE = ("bekliyor", "açık", "açık (TP1 görüldü)")
TYPES = {"giris": "Giriş (seviyeye gelme, teyit, gerçekleşme)", "sl": "Stop (SL, başabaş stop)",
         "tp": "Hedef (TP1, TP2)", "gecersiz": "Geçersiz / süresi doldu", "teyit": "Alt fitil + yükselen kapanış teyidi",
         "kirilim": "Destek / direnç kırılımı", "hacim": "Hacim artışı", "teknik": "Trend değişikliği, yeni senaryo",
         "haber": "Önemli yeni haber"}
INTRADAY_EVERY_MIN = 5
CLOSE_DELAY_MIN = 20          # kapanış fiyatı kesinleşsin
STALE_MIN = 45                # gün içi son veri bundan eskiyse (gecikme 15 dk + mum 5 dk + pay) olay üretilmez
VOL_MULT_CLOSE = 2.0          # günlük hacim 20 gün ortalamasının 2 katı
VOL_MULT_INTRADAY = 1.5       # gün içinde biriken hacim tam günlük ortalamanın 1,5 katı (yarım günde bile aşıldı)
RETRY_HOURS = 24


def _now() -> datetime:
    return datetime.now(config.TR_TZ)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def state_file():
    return config.DATA / "takip_durum.json"


def load_state() -> Dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(st: Dict) -> None:
    state_file().parent.mkdir(parents=True, exist_ok=True)
    state_file().write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- takip listesi
def watched(conn, active_only: bool = True) -> List[Dict]:
    q = "SELECT * FROM watchlist" + (" WHERE aktif=1" if active_only else "") + " ORDER BY ticker"
    out = []
    for r in conn.execute(q):
        d = dict(r)
        d["bildirimler"] = json.loads(d["bildirimler"]) if d.get("bildirimler") else list(TYPES)
        out.append(d)
    return out


def is_watched(conn, ticker: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM watchlist WHERE ticker=? AND aktif=1", (ticker,)).fetchone())


def ensure_prices(conn, ticker: str, price_fn: Optional[Callable] = None, now: Optional[datetime] = None) -> Optional[str]:
    """Senaryo eski fiyatla hesaplanmasın (2026-11-09 gerçek veri denemesi: kayıtlı fiyatı eski hissede senaryo hemen
    geçersiz çıktı; geçmişi kısa hissede hiç senaryo çıkmadı). Geçmiş 200 günden kısaysa 1 yıl, son fiyat son
    kapanmış işlem gününden eskiyse 1 ay indirilir. Hata olursa kayıtlı veriyle devam edilir; açıklama döner."""
    import os
    from . import prices
    if os.environ.get("HALLEY_OFFLINE") and price_fn is None:
        return None
    n, last = conn.execute("SELECT COUNT(*), MAX(date) FROM prices WHERE ticker=?", (ticker,)).fetchone()
    target = last_closed_day(now or _now())
    period = "1y" if n < 200 else ("1mo" if target and (last or "") < target.isoformat() else None)
    if not period:
        return None
    try:
        (price_fn or prices.update)(conn, [ticker], period=period)
    except Exception as e:
        return f"Fiyat güncellenemedi ({str(e)[:80]}); kayıtlı fiyatla hesaplandı."
    return None


def add(conn, ticker: str, today: Optional[date] = None, price_fn: Optional[Callable] = None) -> Dict:
    """Takibe al: listeye ekler (ya da yeniden etkinleştirir), fiyatı tazeler ve senaryoları kaydeder. Bildirim
    GÖNDERMEZ."""
    ticker = ticker.strip().upper()
    if not conn.execute("SELECT 1 FROM companies WHERE ticker=?", (ticker,)).fetchone() and ticker != technical.BENCHMARK:
        raise ValueError(f"{ticker} şirket listesinde yok.")
    conn.execute("INSERT INTO watchlist(ticker, eklendi) VALUES(?,?) ON CONFLICT(ticker) DO UPDATE SET aktif=1, "
                 "cikarildi=NULL", (ticker, _iso(_now())))
    conn.commit()
    warn = ensure_prices(conn, ticker, price_fn)
    res = refresh_scenarios(conn, ticker, today)
    if warn:
        res["uyari"] = warn
    t = res.get("teknik")
    if t:
        conn.execute("UPDATE watchlist SET son_trend=? WHERE ticker=?", (t.get("trend"), ticker))
        conn.commit()
    return res


def remove(conn, ticker: str) -> None:
    """Takipten çıkar: yeni bildirimler durur; senaryolar ve olay geçmişi SİLİNMEZ."""
    conn.execute("UPDATE watchlist SET aktif=0, cikarildi=? WHERE ticker=?", (_iso(_now()), ticker))
    conn.commit()


def set_types(conn, ticker: str, types: List[str]) -> None:
    bad = [t for t in types if t not in TYPES]
    if bad:
        raise ValueError(f"Bilinmeyen bildirim türü: {bad}")
    conn.execute("UPDATE watchlist SET bildirimler=? WHERE ticker=?", (json.dumps(types), ticker))
    conn.commit()


def set_scenario_alert(conn, scenario_id: int, on: bool) -> None:
    conn.execute("UPDATE takip_senaryo SET bildirim=? WHERE id=?", (1 if on else 0, scenario_id))
    conn.commit()


def scenarios(conn, ticker: Optional[str] = None, active_only: bool = False) -> List[Dict]:
    q, args = "SELECT * FROM takip_senaryo WHERE 1=1", []
    if ticker:
        q += " AND ticker=?"
        args.append(ticker)
    if active_only:
        q += f" AND durum IN ({','.join('?' * len(ACTIVE))})"
        args += list(ACTIVE)
    out = []
    for r in conn.execute(q + " ORDER BY id DESC", args):
        d = dict(r)
        d["sonuc"] = json.loads(d["sonuc_json"]) if d.get("sonuc_json") else {}
        out.append(d)
    return out


def events(conn, ticker: Optional[str] = None, limit: int = 100) -> List[Dict]:
    q, args = "SELECT * FROM takip_olay", []
    if ticker:
        q += " WHERE ticker=?"
        args.append(ticker)
    return [dict(r) for r in conn.execute(q + " ORDER BY id DESC LIMIT ?", args + [limit])]


def scenario_guard(t: Optional[Dict]) -> Optional[str]:
    """Senaryo üretilmeyecekse nedeni (panel Hisse Analizi ekranı ve bekçi aynı kuralı kullanır)."""
    if not t:
        return "Fiyat geçmişi yetersiz (en az 30 işlem günü gerekir); senaryo üretilmedi."
    if t.get("veri_kritik"):
        return "Fiyat verisinde kritik sorun var; senaryo üretilmedi."
    vol = t.get("islem_hacmi_tl")
    if vol is not None and vol < tradeplan.LIQ_MIN_TL:
        return f"Likidite çok düşük (günlük {vol / 1e6:.2f} milyon TL); senaryo üretilmedi."
    return None


def refresh_scenarios(conn, ticker: str, today: Optional[date] = None) -> Dict:
    """Hissenin güncel uygulanabilir senaryolarından, aynı türde etkin takibi olmayanları kaydeder."""
    t = technical.for_ticker(conn, ticker, today)
    why = scenario_guard(t)
    if why:
        return dict({"yeni": [], "neden": why}, **({"teknik": t} if t else {}))
    sc = entries.scenarios(t)
    active = {r["senaryo"] for r in conn.execute(
        f"SELECT senaryo FROM takip_senaryo WHERE ticker=? AND durum IN ({','.join('?' * len(ACTIVE))})",
        (ticker, *ACTIVE))}
    new = []
    for s in sc["senaryolar"]:
        if "uygulanamaz" in s or s["kalite"] == "elverişsiz" or s["tur"] in active:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO takip_senaryo(ticker,senaryo,signal_day,olusturuldu,emir,alarm,giris,sl,tp1,tp2,"
            "gecerlilik,kalite) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (ticker, s["tur"], t["tarih"], _iso(_now()), s["emir"], s.get("alarm"), s["giris"], s["sl"], s["tp1"],
             s["tp2"], s["gecerlilik_gun"], s["kalite"]))
        if cur.rowcount:
            new.append({"id": cur.lastrowid, "senaryo": s["tur"], "ad": s["ad"], "giris": s["giris"], "sl": s["sl"],
                        "tp1": s["tp1"], "tp2": s["tp2"]})
    conn.commit()
    out = {"yeni": new, "teknik": t}
    if not new and not active:
        out["neden"] = sc.get("neden_yok") or "Uygun giriş senaryosu yok (risk/getiri elverişsiz ya da koşul yok)."
    return out


# ---------------------------------------------------------------- olay kaydı ve bildirim
def _event(conn, now: datetime, ticker: str, tur: str, mesaj: str, key: str, sid: Optional[int] = None,
           kesin: bool = True) -> Optional[int]:
    cur = conn.execute("INSERT OR IGNORE INTO takip_olay(zaman,gun,ticker,senaryo_id,tur,mesaj,anahtar,kesin) "
                       "VALUES(?,?,?,?,?,?,?,?)", (_iso(now), now.date().isoformat(), ticker, sid, tur, mesaj, key,
                                                   1 if kesin else 0))
    return cur.lastrowid if cur.rowcount else None


def _n(v) -> str:
    return "—" if v is None else f"{v:.2f}"


NAMES = {k: v.split(" (")[0] for k, v in entries.NAMES.items()}


def _sname(rec) -> str:
    return f"{NAMES.get(rec['senaryo'], rec['senaryo'])} #{rec['id']}"


def dispatch(conn, send: Optional[Callable] = None, now: Optional[datetime] = None) -> Dict:
    """Gönderilmemiş olayları (son 24 saat) kullanıcı ayarına göre tek mesajda Telegram'a yollar."""
    from . import notify, pipeline
    now = now or _now()
    since = _iso(now - timedelta(hours=RETRY_HOURS))
    rows = [dict(r) for r in conn.execute("SELECT * FROM takip_olay WHERE gonderildi=0 AND zaman>=? ORDER BY id",
                                          (since,))]
    if not rows:
        return {"gonderilen": 0}
    lists = {w["ticker"]: w for w in watched(conn, active_only=False)}
    sc_on = {r["id"]: r["bildirim"] for r in conn.execute("SELECT id, bildirim FROM takip_senaryo")}
    settings = pipeline.load_settings()
    enabled = settings.get("takip_bildirim", True) and notify.configured()
    go, skip = [], []
    for r in rows:
        w = lists.get(r["ticker"])
        ok = (w and w["aktif"] and r["tur"] in w["bildirimler"]
              and (r["senaryo_id"] is None or sc_on.get(r["senaryo_id"], 1)))
        (go if ok else skip).append(r)
    for r in skip:
        conn.execute("UPDATE takip_olay SET gonderildi=-1 WHERE id=?", (r["id"],))
    conn.commit()
    if not go or not enabled:
        if go and not enabled:   # Telegram ayarlı değil/kapalı: kayıt kalır, panelde görünür; tekrar denenmez
            for r in go:
                conn.execute("UPDATE takip_olay SET gonderildi=-1, hata=? WHERE id=?",
                             ("Telegram kapalı ya da ayarlanmamış", r["id"]))
            conn.commit()
        return {"gonderilen": 0, "atlanan": len(skip) + (len(go) if not enabled else 0)}
    icon = {"giris": "🎯", "sl": "🛑", "tp": "✅", "gecersiz": "⌛", "teyit": "🕯️", "kirilim": "📐", "hacim": "📊",
            "teknik": "🧭", "haber": "📰"}
    text = "🛡️ Halley bekçi\n"
    for tk in sorted({r["ticker"] for r in go}):
        text += f"\n{tk}\n" + "".join(f"{icon.get(r['tur'], '•')} {r['mesaj']}"
                                      + ("" if r["kesin"] else " (gün içi, ~15 dk gecikmeli; kapanışla teyit edilmedi)")
                                      + "\n" for r in go if r["ticker"] == tk)
    res = (send or notify.send)(text + notify.FOOT)
    for r in go:
        if res.get("ok"):
            conn.execute("UPDATE takip_olay SET gonderildi=1, hata=NULL WHERE id=?", (r["id"],))
        else:
            conn.execute("UPDATE takip_olay SET hata=? WHERE id=?", ("; ".join(res.get("hatalar", []))[:300], r["id"]))
    conn.commit()
    return {"gonderilen": len(go) if res.get("ok") else 0, "hata": None if res.get("ok") else res.get("hatalar")}


# ---------------------------------------------------------------- kapanış sonrası kontrol
def _bars(conn, ticker: str, upto: str, n: int = 25) -> List[Dict]:
    rows = conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND date<=? "
                        "ORDER BY date DESC LIMIT ?", (ticker, upto, n)).fetchall()
    return [dict(r) for r in reversed(rows)]


def close_check(conn, day: str, now: Optional[datetime] = None) -> Dict:
    """Günlük mum kesinleşmiş `day` için tüm aktif takip hisselerini değerlendirir (fiyatlar önceden indirilmiş olmalı).
    Fiyatı o güne ait olmayan hisse için OLAY ÜRETİLMEZ."""
    from . import pipeline
    now = now or _now()
    st = pipeline.load_settings()
    comm = float(st.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT))
    slip = float(st.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT))
    out = {"gun": day, "hisse": 0, "olay": 0, "veri_yok": []}
    d = date.fromisoformat(day)
    for w in watched(conn):
        tk = w["ticker"]
        bars = _bars(conn, tk, day)
        if not bars or bars[-1]["date"] != day or not bars[-1].get("close"):
            out["veri_yok"].append(tk)
            continue
        out["hisse"] += 1
        b, prev = bars[-1], bars[:-1]
        n0 = _count(conn, tk)
        # 1) senaryoların durumu (işlem günlüğüyle aynı kurallar)
        for rec in scenarios(conn, tk, active_only=True):
            res = journal.evaluate(dict(rec, kaynak="takip"), journal.bars_for(conn, tk, rec["signal_day"]), comm, slip)
            old, new = rec["durum"], res["durum"]
            sid, nm = rec["id"], _sname(rec)
            if old == "bekliyor" and res.get("giris_gunu"):
                _event(conn, now, tk, "giris", f"{nm}: giriş gerçekleşti ({res['giris_gunu']}, {_n(res['giris_fiyati'])} "
                                               "TL)", f"s{sid}:giris", sid)
            if new == "bekliyor" and any("kırılım teyidi" in x for x in res.get("olaylar", [])):
                _event(conn, now, tk, "giris", f"{nm}: kırılım kapanışla teyit edildi (kapanış {_n(b['close'])} > alarm "
                                               f"{_n(rec['alarm'])}); senaryoya göre giriş ertesi gün açılışta",
                       f"s{sid}:teyit_kirilim", sid)
            if res.get("tp1_goruldu") and old != "açık (TP1 görüldü)":
                _event(conn, now, tk, "tp", f"{nm}: TP1 ({_n(rec['tp1'])}) görüldü — senaryoya göre yarısı satılır, stop "
                                            f"girişe ({_n(res.get('giris_fiyati'))}) çekilir", f"s{sid}:tp1", sid)
            if new == "kapandı":
                son = res.get("sonuc")
                tur = {"TP2": "tp", "SL": "sl", "başabaş (TP1 sonrası)": "sl"}.get(son, "gecersiz")
                txt = {"TP2": f"TP2 ({_n(rec['tp2'])}) görüldü", "SL": f"SL ({_n(rec['sl'])}) çalıştı",
                       "başabaş (TP1 sonrası)": "başabaş stop çalıştı (TP1 sonrası)",
                       "süre doldu": "30 işlem günü doldu, kapanıştan çıkış"}.get(son, son)
                _event(conn, now, tk, tur, f"{nm}: {txt} · net %{res.get('net_getiri_pct', 0):+.2f}", f"s{sid}:son", sid)
            elif new == "iptal":
                _event(conn, now, tk, "gecersiz", f"{nm}: {rec['gecerlilik']} işlem gününde giriş koşulu oluşmadı, süre "
                                                  "doldu", f"s{sid}:son", sid)
            elif new == "bekliyor" and rec["senaryo"] != "kirilim" and b["close"] < rec["sl"]:
                # kırılımda SL kırılan seviyenin altıdır, kırılımdan önce fiyatın SL altında olması olağandır
                new = "geçersiz"
                res = dict(res, durum=new, sonuc="geçersiz", olaylar=res.get("olaylar", []) +
                           [f"{day} kapanış ({b['close']:.2f}) SL ({rec['sl']:.2f}) altında, giriş olmadan"])
                _event(conn, now, tk, "gecersiz", f"{nm}: giriş olmadan kapanış SL'nin altında ({_n(b['close'])} < "
                                                  f"{_n(rec['sl'])}) — senaryo geçersiz", f"s{sid}:son", sid)
            conn.execute("UPDATE takip_senaryo SET durum=?, sonuc_json=?, guncellendi=? WHERE id=?",
                         (new, json.dumps(res, ensure_ascii=False), _iso(now), sid))
        # 2) mum ve seviye olayları (bugünkü mum + önceki 20 gün; bugün hariç seviyeler)
        p20 = prev[-20:]
        if len(p20) >= 10:
            hi20, lo20 = max(x["high"] or x["close"] for x in p20), min(x["low"] or x["close"] for x in p20)
            if b["close"] > hi20:
                _event(conn, now, tk, "kirilim", f"Direnç kırılımı: kapanış {_n(b['close'])}, 20 günlük zirvenin "
                                                 f"({_n(hi20)}) üstünde", f"{tk}:{day}:direnc")
            elif b["close"] < lo20:
                _event(conn, now, tk, "kirilim", f"Destek kırıldı (aşağı): kapanış {_n(b['close'])}, 20 günlük dibin "
                                                 f"({_n(lo20)}) altında", f"{tk}:{day}:destek")
            vols = [x["volume"] for x in p20 if x.get("volume")]
            if vols and b.get("volume") and b["volume"] >= VOL_MULT_CLOSE * (sum(vols) / len(vols)):
                _event(conn, now, tk, "hacim", f"Hacim artışı: günlük hacim 20 gün ortalamasının "
                                               f"{b['volume'] / (sum(vols) / len(vols)):.1f} katı (kapanış "
                                               f"{_n(b['close'])}, %{(b['close'] / prev[-1]['close'] - 1) * 100:+.1f})",
                       f"{tk}:{day}:hacim")
        o, h, l, c = b.get("open") or b["close"], b.get("high") or b["close"], b.get("low") or b["close"], b["close"]
        rng = h - l
        if prev and rng > 0 and c > o and c > prev[-1]["close"] and (min(o, c) - l) >= 0.5 * rng:
            for rec in scenarios(conn, tk, active_only=True):
                if rec["senaryo"] in ("destek", "geri_cekilme") and l <= rec["giris"] * 1.01:
                    _event(conn, now, tk, "teyit", f"{_sname(rec)}: giriş bölgesinde ({_n(rec['giris'])}) alt fitil + "
                                                   f"yükselen kapanış teyidi (dip {_n(l)}, kapanış {_n(c)})",
                           f"s{rec['id']}:{day}:fitil", rec["id"])
        # 3) teknik görünüm ve yeni senaryolar
        rs = refresh_scenarios(conn, tk, d)
        for s in rs["yeni"]:
            _event(conn, now, tk, "teknik", f"Yeni senaryo: {NAMES.get(s['senaryo'])} #{s['id']} — giriş {_n(s['giris'])}, "
                                            f"SL {_n(s['sl'])}, TP1 {_n(s['tp1'])}, TP2 {_n(s['tp2'])}",
                   f"s{s['id']}:yeni", s["id"])
        t = rs.get("teknik")
        if t and t.get("trend"):
            if w.get("son_trend") and t["trend"] != w["son_trend"]:
                _event(conn, now, tk, "teknik", f"Teknik görünüm değişti: trend {w['son_trend'].lower()} → "
                                                f"{t['trend'].lower()}", f"{tk}:{day}:trend")
            conn.execute("UPDATE watchlist SET son_trend=? WHERE ticker=?", (t["trend"], tk))
        conn.commit()
        out["olay"] += _count(conn, tk) - n0
    return out


def _count(conn, ticker: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM takip_olay WHERE ticker=?", (ticker,)).fetchone()[0]


# ---------------------------------------------------------------- gün içi kontrol
def fetch_intraday(tickers: List[str]) -> Dict[str, Dict]:
    """Yahoo 5 dakikalık mumlarından bugünün özeti (~15 dk gecikmeli). Fiyat tablosuna YAZILMAZ (yarım mum)."""
    import pandas as pd
    import yfinance as yf
    if not tickers:
        return {}
    df = yf.download([t + ".IS" for t in tickers], period="1d", interval="5m", auto_adjust=False, progress=False,
                     group_by="ticker", threads=False)
    out = {}
    for t in tickers:
        sym = t + ".IS"
        if isinstance(df.columns, pd.MultiIndex):
            if sym not in df.columns.get_level_values(0):
                continue
            sub = df[sym]
        else:
            sub = df
        sub = sub.dropna(subset=["Close"])
        if sub.empty:
            continue
        idx = sub.index.tz_convert(config.TR_TZ) if sub.index.tz is not None else sub.index.tz_localize(config.TR_TZ)
        last = idx[-1].to_pydatetime()
        today = sub[[i.date() == last.date() for i in idx]]
        out[t] = {"zaman": last, "son": float(today["Close"].iloc[-1]), "yuksek": float(today["High"].max()),
                  "dusuk": float(today["Low"].min()), "hacim": float(today["Volume"].fillna(0).sum())}
    return out


def intraday_check(conn, quotes: Dict[str, Dict], now: Optional[datetime] = None) -> Dict:
    now = now or _now()
    day = now.date().isoformat()
    out = {"hisse": 0, "veri_yok": []}
    for w in watched(conn):
        tk = w["ticker"]
        q = quotes.get(tk)
        if not q or q["zaman"].date() != now.date() or (now - q["zaman"]).total_seconds() > STALE_MIN * 60:
            out["veri_yok"].append(tk)          # eski/eksik veri: olay üretme
            continue
        out["hisse"] += 1
        for rec in scenarios(conn, tk, active_only=True):
            sid, nm = rec["id"], _sname(rec)
            if rec["durum"] == "bekliyor":
                if rec["senaryo"] == "kirilim":
                    if rec.get("alarm") and q["son"] > rec["alarm"]:
                        _event(conn, now, tk, "kirilim", f"{nm}: fiyat ({_n(q['son'])}) alarm seviyesinin "
                                                         f"({_n(rec['alarm'])}) üstünde — kırılım deneniyor; teyit için "
                                                         "günlük kapanış da üstünde olmalı", f"s{sid}:{day}:kirilim_gi",
                               sid, kesin=False)
                elif q["dusuk"] <= rec["giris"]:
                    _event(conn, now, tk, "giris", f"{nm}: fiyat giriş seviyesine geldi (giriş {_n(rec['giris'])}, gün "
                                                   f"içi dip {_n(q['dusuk'])}, son {_n(q['son'])})",
                           f"s{sid}:giris_gi", sid, kesin=False)
            else:
                stop = rec["sonuc"].get("stop", rec["sl"])
                if q["dusuk"] <= stop:
                    _event(conn, now, tk, "sl", f"{nm}: fiyat stop seviyesine ({_n(stop)}) değdi (gün içi dip "
                                                f"{_n(q['dusuk'])})", f"s{sid}:sl_gi:{stop:.4f}", sid, kesin=False)
                if q["yuksek"] >= rec["tp1"] and rec["durum"] == "açık":
                    _event(conn, now, tk, "tp", f"{nm}: fiyat TP1'e ({_n(rec['tp1'])}) ulaştı (gün içi zirve "
                                                f"{_n(q['yuksek'])})", f"s{sid}:tp1_gi", sid, kesin=False)
                if q["yuksek"] >= rec["tp2"]:
                    _event(conn, now, tk, "tp", f"{nm}: fiyat TP2'ye ({_n(rec['tp2'])}) ulaştı (gün içi zirve "
                                                f"{_n(q['yuksek'])})", f"s{sid}:tp2_gi", sid, kesin=False)
        vols = [x["volume"] for x in _bars(conn, tk, (now.date() - timedelta(days=1)).isoformat(), 20)
                if x.get("volume")]
        if vols and q["hacim"] >= VOL_MULT_INTRADAY * (sum(vols) / len(vols)):
            _event(conn, now, tk, "hacim", f"Hacim artışı: gün içinde biriken hacim günlük ortalamanın "
                                           f"{q['hacim'] / (sum(vols) / len(vols)):.1f} katı (son {_n(q['son'])})",
                   f"{tk}:{day}:hacim_gi", kesin=False)
    conn.commit()
    return out


# ---------------------------------------------------------------- zamanlama (arka plan)
def last_closed_day(now: datetime) -> Optional[date]:
    """Kapanışı (+20 dk) geçmiş en son işlem günü."""
    d = now.date()
    for _ in range(10):
        close = market_calendar.session_close(d)
        if close and (d < now.date() or now.time() >= (datetime.combine(d, close) +
                                                          timedelta(minutes=CLOSE_DELAY_MIN)).time()):
            return d
        d -= timedelta(days=1)
    return None


def in_session(now: datetime) -> bool:
    close = market_calendar.session_close(now.date())
    return bool(close) and time(10, 0) <= now.time() <= close


def tick(conn, now: Optional[datetime] = None, price_fn: Optional[Callable] = None,
         quote_fn: Optional[Callable] = None, send: Optional[Callable] = None) -> Dict:
    """Arka plan bekçisinin bir turu (okuyucu döngüsü ~2 dk'da bir çağırır). Ağ işlevleri testte değiştirilebilir."""
    from . import prices
    now = now or _now()
    st = load_state()
    out = {}
    tickers = [w["ticker"] for w in watched(conn)]
    if tickers:
        target = last_closed_day(now)
        if target and target.isoformat() > st.get("kapanis_gunu", ""):   # yalnız ileri; eski günü yeniden işleme
            # günlük mum kesinleşti: fiyatları indir (yeni eklenen hissede 1 yıl, diğerlerinde 1 ay yeterli)
            short = [t for t in tickers if conn.execute("SELECT COUNT(*) FROM prices WHERE ticker=?", (t,)).fetchone()[0]
                     >= 200]
            long_ = [t for t in tickers if t not in short]
            fn = price_fn or prices.update
            if short:
                fn(conn, short + [technical.BENCHMARK], period="1mo")
            if long_:
                fn(conn, long_, period="1y")
            res = close_check(conn, target.isoformat(), now)
            out["kapanis"] = res
            st.update(kapanis_gunu=target.isoformat(), kapanis_zaman=_iso(now), kapanis_sonuc=res)
        elif in_session(now):
            last = st.get("gunici_son")
            if not last or (now - datetime.fromisoformat(last)).total_seconds() >= INTRADAY_EVERY_MIN * 60 - 5:
                res = intraday_check(conn, (quote_fn or fetch_intraday)(tickers), now)
                out["gunici"] = res
                st.update(gunici_son=_iso(now), gunici_sonuc=res)
    out["bildirim"] = dispatch(conn, send, now)
    st["nabiz"] = _iso(now)
    st.pop("hata", None)
    _save_state(st)
    return out


def safe_tick(db_path=None) -> None:
    """Okuyucu döngüsünden çağrılır: hata olursa durum dosyasına yazar, okuyucuyu asla durdurmaz."""
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


# ---------------------------------------------------------------- performans (strateji başarı oranları)
def performance(conn) -> List[Dict]:
    """Kapanan takip senaryolarının strateji türüne göre sonuçları (TP1/TP2/SL oranları). Örnek az uyarısı panelde."""
    rows = {}
    for r in scenarios(conn):
        if r["durum"] not in ("kapandı", "iptal", "geçersiz"):
            continue
        k = rows.setdefault(r["senaryo"], {"senaryo": r["senaryo"], "ad": NAMES.get(r["senaryo"]), "toplam": 0,
                                           "giris_olan": 0, "tp1": 0, "tp2": 0, "sl": 0, "basabas": 0,
                                           "sure_doldu": 0, "girissiz": 0, "net": []})
        k["toplam"] += 1
        res = r["sonuc"]
        if r["durum"] != "kapandı":
            k["girissiz"] += 1
            continue
        k["giris_olan"] += 1
        k["tp1"] += 1 if res.get("tp1_goruldu") or res.get("sonuc") == "TP2" else 0
        son = res.get("sonuc")
        k["tp2"] += son == "TP2"
        k["sl"] += son == "SL"
        k["basabas"] += son == "başabaş (TP1 sonrası)"
        k["sure_doldu"] += son == "süre doldu"
        if res.get("net_getiri_pct") is not None:
            k["net"].append(res["net_getiri_pct"])
    out = []
    for k in rows.values():
        n = k["giris_olan"]
        pct = lambda x: round(100 * x / n, 1) if n else None
        out.append({"Strateji": k["ad"], "Senaryo": k["toplam"], "Giriş olan": n, "Girişsiz biten": k["girissiz"],
                    "TP1 %": pct(k["tp1"]), "TP2 %": pct(k["tp2"]), "SL %": pct(k["sl"]),
                    "Başabaş %": pct(k["basabas"]), "Süre doldu %": pct(k["sure_doldu"]),
                    "Ort. net %": round(sum(k["net"]) / len(k["net"]), 2) if k["net"] else None})
    return out
