"""İşlem günlüğü (Parça C1, 2026-11-07): sanal (otomatik) ve gerçek işlemlerin kaydı, sonucu ve performansı.

Amaç: haber sinyalinin gerçekten işe yarayıp yaramadığını zamanla ÖLÇMEK (geçmiş testte teknik kurallar tek başına
avantaj sağlamadı). Yapay zekâ kullanılmaz; yalnız kayıtlı günlük fiyatlarla hesaplanır, ücretsizdir.

Kurallar (geçmiş veri testindeki kurallarla AYNI, karşılaştırılabilir olsun diye):
- Kayıt: panelde "uygun" görünen hissenin en uygun giriş senaryosu, hesaplandığı son fiyat gününden (signal_day)
  SONRAKİ günlerle değerlendirilir (geleceği görmez). Aynı hissede açık/bekleyen otomatik kayıt varsa yenisi açılmaz.
- Giriş: kırılım → günlük kapanış alarm seviyesinin üstündeyse ERTESİ gün açılışından; limit (geri çekilme, destek)
  → gün içi en düşük ≤ limit ise limitten (açılış limitin altındaysa açılıştan). Geçerlilik süresinde gerçekleşmezse
  "iptal (gerçekleşmedi)". Gerçek kayıtta kullanıcının alış günü/fiyatı kullanılır.
- Çıkış (kullanıcı onaylı stop kuralı): TP1'de pozisyonun YARISI satılır, stop GİRİŞ fiyatına çekilir (başabaş),
  kalan yarı TP2'ye kadar izlenir. Her gün: açılış stopun altında → açılıştan; açılış hedefin üstünde → açılıştan;
  aynı gün hem stop hem hedef görülürse stop önce sayılır (temkinli); limitin dolduğu gün hedef sayılmaz (gün içi sıra
  bilinmez) ama stop sayılır. En fazla 30 işlem günü; sonra kapanıştan "süre doldu".
- Maliyet: alış+satış komisyonu ve kayma ayarlardan (varsayılan %0,20 + %0,10); net getiri bunlar düşülerek.
Bu sonuçlar geçmiş performanstır; geleceği garanti etmez, yatırım tavsiyesi değildir.
"""
import json
import math
from datetime import datetime
from statistics import mean, median, pstdev
from typing import Dict, List, Optional

from . import config

MAX_HOLD = 30
DEFAULT_COMMISSION_PCT = 0.20   # alış + satış toplamı (pilotla aynı varsayım)
DEFAULT_SLIPPAGE_PCT = 0.10     # alış + satış toplamı kayma
MIN_TRADES_FOR_STATS = 30
OPEN_STATES = ("bekliyor", "açık", "açık (TP1 görüldü)")


def _now() -> str:
    return datetime.now(config.TR_TZ).isoformat(timespec="seconds")


# ---------------------------------------------------------------- kayıt
def record_auto(conn, ticker: str, plan: Dict, signal_day: str, score: Optional[float]) -> Optional[int]:
    """Panelin en uygun giriş senaryosunu sanal işlem olarak kaydeder (gün başına hisse başına bir kez)."""
    g = plan.get("girisler") or {}
    s = next((x for x in g.get("senaryolar", []) if x["tur"] == g.get("en_uygun")), None)
    if plan.get("durum") != "senaryo" or not s:
        return None
    open_ = conn.execute("SELECT 1 FROM trade_journal WHERE ticker=? AND kaynak='otomatik' AND durum IN (?,?,?)",
                         (ticker, *OPEN_STATES)).fetchone()
    if open_:
        return None
    cur = conn.execute(
        "INSERT OR IGNORE INTO trade_journal(created_at,signal_day,ticker,kaynak,haber_skoru,risk_seviyesi,senaryo,emir,"
        "alarm,giris,sl,tp1,tp2,gecerlilik) VALUES(?,?,?,'otomatik',?,?,?,?,?,?,?,?,?,?)",
        (_now(), signal_day, ticker, score, s.get("risk_seviyesi"), s["tur"], s["emir"], s.get("alarm"), s["giris"],
         s["sl"], s["tp1"], s["tp2"], s["gecerlilik_gun"]))
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


def record_real(conn, auto_id: int, fill_day: str, fill_price: float) -> int:
    """Kullanıcı "Bu işleme girdim": aynı seviyelerle gerçek kayıt (alış günü/fiyatı kullanıcının)."""
    r = conn.execute("SELECT * FROM trade_journal WHERE id=?", (auto_id,)).fetchone()
    if r is None:
        raise ValueError("Kayıt bulunamadı")
    # 2026-11-09 uçtan uca kontrol: "Kaydet"e ikinci kez basınca veritabanı hatası paneli çökertiyordu; kullanıcı
    # hatalarına (ileri tarih, sinyalden önce alış, yanlış yazılmış fiyat) açık Türkçe uyarı.
    dup = conn.execute("SELECT id FROM trade_journal WHERE kaynak='gercek' AND ticker=? AND signal_day=? AND senaryo=?",
                       (r["ticker"], r["signal_day"], r["senaryo"])).fetchone()
    if dup:
        raise ValueError(f"Bu sanal kayıt için gerçek işleminiz zaten kaydedilmiş (#{dup['id']}).")
    if not (fill_price > 0):
        raise ValueError("Alış fiyatı geçersiz")
    today = datetime.now(config.TR_TZ).date().isoformat()
    if fill_day > today:
        raise ValueError("Alış günü bugünden ileri olamaz.")
    if fill_day <= r["signal_day"]:
        raise ValueError(f"Alış günü, senaryonun hesaplandığı günden ({r['signal_day']}) sonra olmalı.")
    if fill_price <= r["sl"] or fill_price >= r["tp2"]:
        raise ValueError(f"Alış fiyatı {fill_price:.2f} TL, senaryonun SL ({r['sl']:.2f}) – TP2 ({r['tp2']:.2f}) aralığı "
                         "dışında: yanlış yazılmış olabilir (ör. virgül). Bu aralık dışında alındıysa senaryo zaten "
                         "geçersizdir.")
    cur = conn.execute(
        "INSERT INTO trade_journal(created_at,signal_day,ticker,kaynak,haber_skoru,risk_seviyesi,senaryo,emir,alarm,giris,"
        "sl,tp1,tp2,gecerlilik,gercek_giris_gunu,gercek_giris_fiyati,ana_id) "
        "VALUES(?,?,?,'gercek',?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (_now(), r["signal_day"], r["ticker"], r["haber_skoru"], r["risk_seviyesi"], r["senaryo"], r["emir"], r["alarm"],
         r["giris"], r["sl"], r["tp1"], r["tp2"], r["gecerlilik"], fill_day, fill_price, auto_id))
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------- değerlendirme
def giris_kosulu(acilis: Optional[float], azami: float, sl: float) -> Optional[str]:
    """Ek H4 (araştırma, kural s3): HENÜZ ALINMAMIŞ yeni önerinin açılışta giriş koşulu. None = geçerli; aksi halde
    girişsiz nedeni. Açılış SL'ye eşit ya da altındaysa plan geçersizdir (alış yapılmaz, getiri yazılmaz).
    Canlı kodda henüz KULLANILMIYOR; canlı kural ayrı onayla değişir."""
    if not acilis:
        return "açılış fiyatı yok"
    if acilis > azami + 1e-9:
        return "açılış azami girişin üstünde"
    if acilis <= sl + 1e-9:
        return "açılış stopun altında veya eşit"
    return None


def evaluate(rec: Dict, bars: List[Dict], commission_pct: float = DEFAULT_COMMISSION_PCT,
             slippage_pct: float = DEFAULT_SLIPPAGE_PCT, kural: str = "s2") -> Dict:
    """rec: günlük satırı; bars: signal_day SONRASI günlük barlar (tarih sıralı). Durum ve sonucu döndürür.
    kural: "s2" (varsayılan, canlıdaki mevcut davranış) | "s3" (Ek H4, araştırma): alış fiyatı SL'ye eşit ya da altındaysa
    (gerçekleşmiş alış ya da açılışta dolan limit emir) alış günü satışı STOP fiyatından değil ALIŞ fiyatından yazılır —
    stop alışla birlikte tetiklenmiş sayılır; ek kayma, genel kayma varsayımı içindedir. Yapay kâr oluşmaz."""
    if kural not in ("s2", "s3"):
        raise ValueError("kural: s2 | s3")
    sl, tp1, tp2, kind = rec["sl"], rec["tp1"], rec["tp2"], rec["senaryo"]
    bars = [b for b in bars if b["date"] > rec["signal_day"] and b.get("close")]
    hl = lambda b: (b.get("high") or b["close"], b.get("low") or b["close"], b.get("open") or b["close"])
    log = []
    fill_i = fill = None
    if rec["kaynak"] == "gercek":
        days = [i for i, b in enumerate(bars) if b["date"] >= rec["gercek_giris_gunu"]]
        if not days:
            return {"durum": "açık", "giris_gunu": rec["gercek_giris_gunu"],
                    "giris_fiyati": rec["gercek_giris_fiyati"], "olaylar": ["Alış girildi; fiyat verisi bekleniyor"]}
        fill_i, fill = days[0], rec["gercek_giris_fiyati"]
        limit_day = True  # alış günü gün içi sıra bilinmez: o gün hedef sayılmaz
    else:
        for i, b in enumerate(bars[:rec["gecerlilik"]]):
            h, l, o = hl(b)
            if kind == "kirilim":
                if rec["alarm"] and b["close"] > rec["alarm"] and i + 1 < len(bars):
                    fill_i, fill = i + 1, hl(bars[i + 1])[2]
                    log.append(f"{b['date']} kapanış alarm ({rec['alarm']:.2f}) üstünde → {bars[i + 1]['date']} açılışta alış")
                    break
                if rec["alarm"] and b["close"] > rec["alarm"]:
                    return {"durum": "bekliyor", "olaylar": [f"{b['date']} kırılım teyidi; ertesi gün açılışta alış"]}
            elif l <= rec["giris"]:
                fill_i, fill = i, min(o, rec["giris"])
                log.append(f"{b['date']} limit doldu ({fill:.2f})")
                break
        if fill_i is None:
            if len(bars) >= rec["gecerlilik"]:
                return {"durum": "iptal", "sonuc": "gerçekleşmedi", "olaylar": [f"{rec['gecerlilik']} işlem gününde giriş "
                                                                                 "koşulu oluşmadı"]}
            return {"durum": "bekliyor", "olaylar": []}
        limit_day = kind != "kirilim"
    stop, half_done, legs = sl, False, []   # legs: (pay, çıkış fiyatı, neden)
    tp2_gap = False                          # 16.11 (Ek F-A): TP1'e hiç dokunmadan doğrudan TP2 üstünde açılış
    held = bars[fill_i:fill_i + MAX_HOLD]
    exit_idx = None
    for j, b in enumerate(held):
        exit_idx = j
        h, l, o = hl(b)
        if j == 0 and limit_day:
            if kural == "s3" and fill <= stop + 1e-12:
                legs.append((1.0, fill, "SL (alış stopun altında)"))
                break
            if l <= stop:
                legs.append((1.0, stop, "SL (alış günü)"))
                break
            continue
        rem = 0.5 if half_done else 1.0
        if o <= stop:
            legs.append((rem, o, "başabaş stop (açılış)" if half_done else "SL (açılışta boşluk)"))
            break
        if not half_done and o >= tp1:
            if o >= tp2:
                legs.append((1.0, o, "TP2 (açılışta)"))
                tp2_gap = True
                break
            legs.append((0.5, o, "TP1 (açılışta, yarısı)"))
            half_done, stop = True, fill
            log.append(f"{b['date']} TP1 açılışta; yarısı satıldı, stop girişe ({fill:.2f}) çekildi")
            continue
        if half_done and o >= tp2:
            legs.append((0.5, o, "TP2 (açılışta)"))
            break
        if l <= stop:
            legs.append((rem, stop, "başabaş stop" if half_done else "SL"))
            break
        if not half_done and h >= tp1:
            legs.append((0.5, tp1, "TP1 (yarısı)"))
            half_done, stop = True, fill
            log.append(f"{b['date']} TP1 görüldü; yarısı satıldı, stop girişe ({fill:.2f}) çekildi")
            continue   # TP1 ile aynı gün TP2 sayılmaz (temkinli)
        if half_done and h >= tp2:
            legs.append((0.5, tp2, "TP2"))
            break
    exited = sum(p for p, _, _ in legs)
    # tp1_goruldu: TP1'de yarısı satıldı (anlamı DEĞİŞMEDİ). tp1_hedefi: TP1 hedefine SL'den önce ulaşıldı —
    # doğrudan TP2 açılışında yarı satış olmasa da hedef geçilmiştir (canlı ölçüm ve eğitim etiketi bunu kullanır).
    out = {"giris_gunu": bars[fill_i]["date"], "giris_fiyati": round(fill, 4), "olaylar": log,
           "tp1_goruldu": half_done, "tp1_hedefi": half_done or tp2_gap, "stop": round(stop, 4)}
    if exited < 0.999:
        if len(held) >= MAX_HOLD:
            last = held[-1]
            legs.append((1.0 - exited, last["close"], "süre doldu"))
        else:
            out["durum"] = "açık (TP1 görüldü)" if half_done else "açık"
            out["son_kapanis"] = held[-1]["close"] if held else None
            if held:
                out["acik_getiri_%"] = round((held[-1]["close"] / fill - 1) * 100, 2)
            return out
    gross = sum(p * (px / fill - 1) for p, px, _ in legs) * 100
    # R = planlanan risk mesafesine (giriş − SL) göre; kırılımda alış açılışı SL altına düşebilir (gerçek veride görüldü)
    risk = rec["giris"] - sl
    r_mult = sum(p * (px - fill) for p, px, _ in legs) / risk if risk > 0 else None
    cost = commission_pct + slippage_pct
    final = legs[-1][2]
    sonuc = ("TP2" if final.startswith("TP2") else "başabaş (TP1 sonrası)" if final.startswith("başabaş") and half_done
             else "süre doldu" if final == "süre doldu" else "SL")
    out.update(durum="kapandı", sonuc=sonuc, cikis_gunu=held[exit_idx]["date"],
               bacaklar=[{"pay": p, "fiyat": round(px, 4), "neden": n} for p, px, n in legs],
               brut_getiri_pct=round(gross, 3), net_getiri_pct=round(gross - cost, 3),
               r=round(r_mult - cost / 100 * fill / risk, 3) if r_mult is not None else None,
               acilis_sl_alti=fill <= sl,
               islem_gunu=exit_idx + 1)
    return out


def bars_for(conn, ticker: str, after: str) -> List[Dict]:
    return [dict(r) for r in conn.execute("SELECT date, open, high, low, close FROM prices WHERE ticker=? AND date>? "
                                          "ORDER BY date", (ticker, after))]


def update_all(conn, commission_pct: float = DEFAULT_COMMISSION_PCT, slippage_pct: float = DEFAULT_SLIPPAGE_PCT) -> Dict:
    """Açık/bekleyen kayıtları kayıtlı fiyatlarla baştan değerlendirir (her seferinde aynı sonucu verir)."""
    n = changed = 0
    changes = []
    for r in conn.execute("SELECT * FROM trade_journal WHERE durum IN (?,?,?)", OPEN_STATES).fetchall():
        res = evaluate(dict(r), bars_for(conn, r["ticker"], r["signal_day"]), commission_pct, slippage_pct)
        conn.execute("UPDATE trade_journal SET durum=?, sonuc_json=?, guncellendi=? WHERE id=?",
                     (res["durum"], json.dumps(res, ensure_ascii=False), _now(), r["id"]))
        n += 1
        if res["durum"] != r["durum"]:
            changed += 1
            changes.append({"id": r["id"], "hisse": r["ticker"], "kaynak": r["kaynak"], "onceki": r["durum"],
                            "yeni": res["durum"], "sonuc": res.get("sonuc"), "net_%": res.get("net_getiri_pct")})
    conn.commit()
    return {"degerlendirilen": n, "durumu_degisen": changed, "degisenler": changes}


def open_tickers(conn) -> List[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT ticker FROM trade_journal WHERE durum IN (?,?,?)", OPEN_STATES)]


# ---------------------------------------------------------------- metrikler
def slippage_stats(conn) -> Dict:
    """Gerçek alışlarınızda kayma (plan 2026-11-09): gerçek alış fiyatı ↔ aynı senaryonun sanal giriş fiyatı.
    Referans: sanal kayıt gerçekleştiyse onun giriş fiyatı (limit = limit fiyatı/açılış; kırılım = alarm sonrası açılış),
    gerçekleşmediyse planlanan giriş. Pozitif = planlanandan pahalı aldınız. Yalnız ALIŞ tarafı ölçülür (satışlar
    kaydedilmiyor). Ayar kendiliğinden değişmez."""
    rows = conn.execute("SELECT g.id, g.ticker, g.senaryo, g.gercek_giris_fiyati AS fill, a.giris AS plan, "
                        "a.sonuc_json AS a_res FROM trade_journal g JOIN trade_journal a ON a.id=g.ana_id "
                        "WHERE g.kaynak='gercek' AND g.gercek_giris_fiyati>0").fetchall()
    items = []
    for r in rows:
        ares = json.loads(r["a_res"]) if r["a_res"] else {}
        ref = ares.get("giris_fiyati") or r["plan"]
        if ref:
            items.append({"id": r["id"], "hisse": r["ticker"], "senaryo": r["senaryo"], "referans": ref,
                          "alis": r["fill"], "kayma_%": (r["fill"] / ref - 1) * 100})
    vals = sorted(x["kayma_%"] for x in items)
    out = {"n": len(items), "islemler": items}
    if vals:
        out.update(ortalama_pct=sum(vals) / len(vals), medyan_pct=vals[len(vals) // 2], en_kotu_pct=vals[-1])
    return out


def metrics(conn, kaynak: str = "otomatik") -> Dict:
    rows = conn.execute("SELECT durum, sonuc_json FROM trade_journal WHERE kaynak=?", (kaynak,)).fetchall()
    res = [json.loads(r["sonuc_json"]) for r in rows if r["sonuc_json"]]
    closed = [x for x in res if x.get("durum") == "kapandı"]
    cancelled = sum(1 for x in res if x.get("durum") == "iptal")
    open_n = sum(1 for r in rows if r["durum"] in OPEN_STATES)
    out = {"kayit": len(rows), "kapanan": len(closed), "acik_bekleyen": open_n, "iptal": cancelled,
           "yeterli_ornek": len(closed) >= MIN_TRADES_FOR_STATS}
    filled = len(closed) + sum(1 for x in res if str(x.get("durum", "")).startswith("açık"))
    out["gerceklesme_orani_%"] = round(100 * filled / (filled + cancelled), 1) if filled + cancelled else None
    if not closed:
        return out
    nets = [x["net_getiri_pct"] for x in closed]
    rs = [x["r"] for x in closed if x.get("r") is not None]
    wins, losses = [v for v in nets if v > 0], [v for v in nets if v <= 0]
    eq, peak, mdd = 0.0, 0.0, 0.0
    for x in sorted(closed, key=lambda x: x.get("cikis_gunu") or ""):
        eq += x.get("r") or 0
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    sd = pstdev(nets) if len(nets) > 1 else 0
    out.update({
        "kazanma_orani_%": round(100 * len(wins) / len(nets), 1),
        "ortalama_net_%": round(mean(nets), 2), "medyan_net_%": round(median(nets), 2),
        "ortalama_R": round(mean(rs), 2) if rs else None,
        "kar_faktoru": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
        "maks_dusus_R": round(mdd, 2),
        "sharpe_islem_basina": round(mean(nets) / sd, 2) if sd else None,
        "sonuc_dagilimi": dict(sorted({s: sum(1 for x in closed if x["sonuc"] == s) for s in
                                        {x["sonuc"] for x in closed}}.items())),
    })
    return out


# ---------------------------------------------------------------- pozisyon hesabı
def position_size(capital: float, risk_pct: float, entry: float, sl: float,
                  cost_pct: float = DEFAULT_COMMISSION_PCT + DEFAULT_SLIPPAGE_PCT) -> Dict:
    """Sermaye ve işlem başına göze alınan risk (%) kullanıcıdan. Kaç adet pay ve SL'de en fazla kayıp (maliyet dahil).
    Kişiye özel tavsiye değildir; yalnız hesaplamadır."""
    if not (capital > 0 and 0 < risk_pct <= 100 and entry > 0 and 0 < sl < entry):
        raise ValueError("Sermaye, risk yüzdesi, giriş ve zarar durdur (girişin altında) geçerli olmalı")
    per_share = (entry - sl) + entry * cost_pct / 100
    by_risk = math.floor(capital * risk_pct / 100 / per_share)
    by_cash = math.floor(capital / (entry * (1 + cost_pct / 200)))
    shares = max(0, min(by_risk, by_cash))
    return {"adet": shares, "tutar": round(shares * entry, 2), "azami_kayip": round(shares * per_share, 2),
            "azami_kayip_%": round(shares * per_share / capital * 100, 2),
            "sinirlayan": "risk" if by_risk <= by_cash else "nakit"}


def daily_refresh(conn, today: Optional[str] = None, price_fn=None) -> Dict:
    """Günde bir kez (bekçi): açık/bekleyen kayıtların hisseleri + XU100 fiyatlarını indir, günlüğü güncelle.
    Ücretsiz (yfinance), yapay zekâ yok. Maliyet ayarları panel ayarlarından (data/ayarlar.json)."""
    from . import pipeline, prices, technical
    today = today or datetime.now(config.TR_TZ).date().isoformat()
    tickers = open_tickers(conn)
    if not tickers:
        return {"hisse": 0}
    (price_fn or prices.update)(conn, tickers + [technical.BENCHMARK])
    st = pipeline.load_settings()
    res = update_all(conn, float(st.get("komisyon_pct", DEFAULT_COMMISSION_PCT)),
                     float(st.get("kayma_pct", DEFAULT_SLIPPAGE_PCT)))
    res["hisse"] = len(tickers)
    res["gun"] = today
    return res
