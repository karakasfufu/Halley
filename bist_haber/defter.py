"""FAZ 1 (2026-11-16): canlı tahmin defteri. Ayrıntılı kurallar: HALLEY2_DENETIM_RAPORU.md Ek B ve Ek C.

Kavramlar (ayrı kayıtlar):
  - Tahmin (tablo `tahmin`): hazır fırsat yazıldığı anda modelin söylediği olasılık + o anki bağlam (girdiler, teknik
    göstergeler, rejim, veri kalitesi, işlem seviyeleri, sürümler). YALNIZ EKLENİR; veritabanı güncellemeyi/silmeyi
    reddeder (tetikleyici). Sonraki analizler geçmiş tahmini değiştiremez; yalnız yeni satır ekleyebilir.
  - Tahmin sonucu (tablo `tahmin_sonuc`): tahminin KENDİ dondurulmuş seviyeleriyle nihai sonucu; tahmin başına en
    fazla bir satır, YALNIZ EKLENİR.
  - Hazır fırsat (`hazir_firsat`) ve sanal işlem (`trade_journal`) bu modülden ETKİLENMEZ.
Plan imzası (tekrar ↔ yeni tahmin ayrımı): ticker | signal_day | giris_gunu | tur | giris | azami_giris | sl | tp1 |
tp2 | gecerlilik_gun | model_surum | ozellik_surum | parametre_surum (sayılar 4 basamak). Olasılık, rejim ya da veri
kalitesi tek başına değişirse yeni tahmin SAYILMAZ (ilk kayıt dondurulmuş kalır).
Seçim kuralları, eşikler, TP1 modeli ve yapay zekâ kullanımı DEĞİŞMEZ; bu modül yalnız kaydeder ve ölçer. YZ yok.
"""
import hashlib
import json
import math
import sqlite3
from datetime import date, datetime
from typing import Dict, List, Optional

from . import config

KURAL_SURUM = "s1"
ACILIS_SINIRI = "09:55"           # bu saatten (giriş günü, TR) sonra kaydedilen tahmin ölçülmez ("gec_kayit")
GECERLILIK_GUN = 1                # hazır fırsat yalnız giriş günü açılışı için geçerli
OLCULMEYEN = ("girissiz", "iptal", "yerini_aldi", "gec_kayit")
TEKNIK_ALANLAR = ("tarih", "son_fiyat", "trend", "rsi14", "macd_hist", "adx", "arti_di", "eksi_di", "atr", "atr_%",
                  "sma50", "sma200", "ema20", "ema50", "ema200", "hacim_orani", "obv_egilim", "rs_20g_%", "rs_60g_%",
                  "destek_20g", "direnc_20g", "islem_hacmi_tl", "fiyat_sma50_%", "fiyat_sma200_%", "perf_20g_%")
TABLO_ANAHTAR = ("tur", "trend", "atr_%", "rsi")   # benzer durumlar tablosunun grup anahtarı (tp1_model._table_key)


def _now() -> datetime:
    return datetime.now(config.TR_TZ)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _sha(obj, n: int = 12) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:n]


def tablo_var(conn) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tahmin'").fetchone())


# ---------------------------------------------------------------- sürümler
def parametreler() -> Dict:
    """Karar sabitleri (adı → değeri). Değerlerden biri değişirse parametre sürümü değişir."""
    from . import ready, tradeplan
    return {"ready.READY_GAP_ATR": ready.READY_GAP_ATR, "ready.MAX_ENTRY_ATR": ready.MAX_ENTRY_ATR,
            "ready.MIN_RR_AT_MAX": ready.MIN_RR_AT_MAX, "ready.MIN_TECH": ready.MIN_TECH,
            "ready.MIN_TECH_ONLY": ready.MIN_TECH_ONLY, "ready.MAX_PICKS": ready.MAX_PICKS,
            "tradeplan.MIN_RR": tradeplan.MIN_RR, "tradeplan.MAX_STOP_PCT": tradeplan.MAX_STOP_PCT,
            "tradeplan.ATR_STOP_MULT": tradeplan.ATR_STOP_MULT, "tradeplan.LIQ_MIN_TL": tradeplan.LIQ_MIN_TL,
            "haber_esigi": 1.5}


def ozellik_surum(m: Dict) -> str:
    return _sha({"lojistik": list(m["lojistik"]["girdiler"]), "tablo": list(TABLO_ANAHTAR)})


def kod_surum() -> str:
    """Kurulu pakette surum.txt (kök klasör); geliştirme klasöründe 'gelistirme'."""
    for p in (config.ROOT.parent / "surum.txt", config.ROOT / "surum.txt"):
        try:
            if p.exists() and (config.ROOT.parent / "Halley.exe").exists():
                return p.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return "gelistirme"


def surumler(m: Dict, model_dosya: str) -> Dict:
    return {"model_surum": str(m.get("surum") or model_dosya), "model_dosya": model_dosya,
            "ozellik_surum": ozellik_surum(m), "parametre_surum": _sha(parametreler()), "kod_surum": kod_surum()}


def plan_imzasi(p: Dict, giris_gunu: str, sv: Dict) -> str:
    r4 = lambda v: None if v is None else round(float(v), 4)
    alan = [p["ticker"], p["signal_day"], giris_gunu, p["tur"], r4(p["giris"]), r4(p["azami_giris"]), r4(p["sl"]),
            r4(p["tp1"]), r4(p["tp2"]), GECERLILIK_GUN, sv["model_surum"], sv["ozellik_surum"], sv["parametre_surum"]]
    return hashlib.sha256("|".join(str(x) for x in alan).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- kayıt
def kaydet(conn, p: Dict, hazir_firsat_id: Optional[int], giris_gunu: str, analiz: str,
           now: Optional[datetime] = None, sonradan: bool = False) -> Dict:
    """Hazır fırsat planından tahmin satırı. Dönüş: {"durum": "yeni"|"tekrar"|"tablo_yok"|"model_yok"|"veri_yok"|"hata",
    "id"}. Hiçbir durumda hata fırlatmaz (hazır fırsat kaydını asla engellemez)."""
    try:
        from . import tp1_model
        if not tablo_var(conn):
            return {"durum": "tablo_yok"}
        name = tp1_model.active_name()
        m = tp1_model.load(name)
        if not m:
            return {"durum": "model_yok"}
        sv = surumler(m, name)
        imza = plan_imzasi(p, giris_gunu, sv)
        old = conn.execute("SELECT id FROM tahmin WHERE plan_imzasi=?", (imza,)).fetchone()
        if old:
            return {"durum": "tekrar", "id": old[0]}
        ctx = tp1_model.plan_context(conn, p)
        if not ctx:
            return {"durum": "veri_yok"}
        f, t, ts = ctx["girdiler"], ctx["teknik"], ctx["teknik_skor"]
        prob = tp1_model.predict(f, m)
        sim = tp1_model.similar(f, m) or {}
        try:
            from . import regime
            rg = regime.regime(conn, date.fromisoformat(p["signal_day"]))
            rejim = None if rg.get("yok") else {k: rg.get(k) for k in ("gun", "trend", "oynaklik", "genislik_%")}
        except Exception:
            rejim = None
        teknik = {k: t.get(k) for k in TEKNIK_ALANLAR if k in t}
        teknik["teknik_skor"] = ts.get("skor")
        teknik["teknik_parca"] = ts.get("parca")
        veri = {"veri_uyarilari": list(t.get("veri_uyarilari") or []), "veri_kritik": bool(t.get("veri_kritik")),
                "gun_sayisi": t.get("gun_sayisi"), "son_fiyat_gunu": t.get("tarih")}
        prev = conn.execute("SELECT id FROM tahmin WHERE ticker=? AND giris_gunu=? ORDER BY id DESC LIMIT 1",
                            (p["ticker"], giris_gunu)).fetchone()
        now = now or _now()
        cur = conn.execute(
            "INSERT OR IGNORE INTO tahmin(plan_imzasi,onceki_tahmin_id,hazir_firsat_id,ticker,signal_day,giris_gunu,analiz,"
            "tahmin_zamani,model_surum,model_dosya,ozellik_surum,parametre_surum,kod_surum,olasilik,bant,benzer_n,"
            "benzer_oran,tur,giris,giris_alt,azami_giris,sl,tp1,tp2,rr1,gecerlilik_gun,genel_puan,teknik_skor,haber_skoru,"
            "kaynak,risk,girdi_json,teknik_json,rejim_json,veri_json,sonradan) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (imza, prev[0] if prev else None, hazir_firsat_id, p["ticker"], p["signal_day"], giris_gunu, analiz,
             _iso(now), sv["model_surum"], sv["model_dosya"], sv["ozellik_surum"], sv["parametre_surum"],
             sv["kod_surum"], float(prob), tp1_model.band(prob, m), sim.get("n"), sim.get("gercek"), p["tur"],
             p["giris"], p.get("giris_alt"), p["azami_giris"], p["sl"], p["tp1"], p["tp2"], p.get("rr1"),
             GECERLILIK_GUN, p.get("genel_puan"), p.get("teknik_skor"), p.get("haber_skoru"), p.get("kaynak", "haber"),
             p.get("risk"), json.dumps(f, ensure_ascii=False, default=str),
             json.dumps(teknik, ensure_ascii=False, default=str), json.dumps(rejim, ensure_ascii=False, default=str),
             json.dumps(veri, ensure_ascii=False, default=str), int(bool(sonradan))))
        conn.commit()
        if not cur.rowcount:    # aynı anda başka süreç yazdıysa
            row = conn.execute("SELECT id FROM tahmin WHERE plan_imzasi=?", (imza,)).fetchone()
            return {"durum": "tekrar", "id": row[0] if row else None}
        return {"durum": "yeni", "id": cur.lastrowid}
    except Exception as e:  # defter hatası hazır fırsatı asla engellemez
        return {"durum": "hata", "hata": str(e)[:200]}


# ---------------------------------------------------------------- sonuçlandırma (kural sürümü s1)
def _hl(b):
    return (b.get("high") or b["close"], b.get("low") or b["close"], b.get("open") or b["close"])


def belirsiz_gunler(held: List[Dict], fill: float, sl: float, tp1: float, tp2: float, n: int) -> List[str]:
    """journal.evaluate ile aynı aşama sırasını izleyerek, aynı mumda aynı aşamanın stopu ve hedefinin BİRLİKTE
    görüldüğü günleri döndürür (gerçekleşme sırası bilinmez; kural SL'yi önce sayar)."""
    out, half, stop = [], False, sl
    for j, b in enumerate(held[:n]):
        h, l, o = _hl(b)
        if j == 0:                                    # giriş günü: yalnız SL sayılır
            if l <= sl and h >= tp1:
                out.append(b["date"])
            if l <= sl:
                break
            continue
        if o <= stop:
            break
        if not half and o >= tp1:
            if o >= tp2:
                break
            half, stop = True, fill
            continue
        if half and o >= tp2:
            break
        target = tp2 if half else tp1
        if l <= stop and h >= target:
            out.append(b["date"])
        if l <= stop:
            break
        if not half and h >= tp1:
            half, stop = True, fill
            continue
        if half and h >= tp2:
            break
    return out


def _sonuc_yaz(conn, tid: int, tur: str, now: datetime, **k) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO tahmin_sonuc(tahmin_id,sonuc_turu,neden,giris_gunu_gercek,giris_fiyati,tp1_goruldu,"
        "sl_goruldu,cikis_nedeni,cikis_gunu,islem_gunu,net_getiri_pct,r,mae_r,mfe_r,ayni_gun_belirsiz,belirsiz_gunler,"
        "ayrinti_json,degerlendirme_zamani,kural_surum) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tid, tur, k.get("neden"), k.get("giris_gunu_gercek"), k.get("giris_fiyati"), k.get("tp1_goruldu"),
         k.get("sl_goruldu"), k.get("cikis_nedeni"), k.get("cikis_gunu"), k.get("islem_gunu"), k.get("net_getiri_pct"),
         k.get("r"), k.get("mae_r"), k.get("mfe_r"), int(bool(k.get("ayni_gun_belirsiz"))),
         json.dumps(k.get("belirsiz_gunler") or [], ensure_ascii=False),
         json.dumps(k.get("ayrinti"), ensure_ascii=False, default=str) if k.get("ayrinti") is not None else None,
         _iso(now), KURAL_SURUM))


def sonuclandir(conn, now: Optional[datetime] = None, commission_pct: Optional[float] = None,
                slippage_pct: Optional[float] = None, bars_fn=None) -> Dict:
    """Açık tahminlerden nihai sonucu belli olanlara TEK sonuç satırı yazar (bkz. Ek C3). Hata fırlatmaz."""
    from . import journal
    out = {"incelenen": 0, "yazilan": 0, "hata": None}
    if not tablo_var(conn):
        out["hata"] = "tablo_yok"
        return out
    try:
        if commission_pct is None or slippage_pct is None:
            from . import pipeline
            st = pipeline.load_settings()
            commission_pct = float(st.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT))
            slippage_pct = float(st.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT))
        now = now or _now()
        bars_fn = bars_fn or (lambda tk, after: journal.bars_for(conn, tk, after))
        acik = conn.execute("SELECT t.* FROM tahmin t LEFT JOIN tahmin_sonuc s ON s.tahmin_id=t.id "
                            "WHERE s.id IS NULL ORDER BY t.id").fetchall()
        for t in acik:
            out["incelenen"] += 1
            t = dict(t)
            sinir = f"{t['giris_gunu']}T{ACILIS_SINIRI}"
            if t["tahmin_zamani"][:16] >= sinir:
                _sonuc_yaz(conn, t["id"], "gec_kayit", now, neden=f"giriş günü {ACILIS_SINIRI}'ten sonra kaydedildi")
                out["yazilan"] += 1
                continue
            newer = conn.execute("SELECT id FROM tahmin WHERE ticker=? AND giris_gunu=? AND id>? AND substr(tahmin_zamani,1,16)<? "
                                 "ORDER BY id DESC LIMIT 1", (t["ticker"], t["giris_gunu"], t["id"], sinir)).fetchone()
            if newer:
                _sonuc_yaz(conn, t["id"], "yerini_aldi", now, neden=f"açılıştan önce daha yeni tahmin: #{newer[0]}")
                out["yazilan"] += 1
                continue
            if t["hazir_firsat_id"]:
                hf = conn.execute("SELECT durum, iptal_nedeni FROM hazir_firsat WHERE id=?",
                                  (t["hazir_firsat_id"],)).fetchone()
                if hf and hf["durum"] == "iptal":
                    _sonuc_yaz(conn, t["id"], "iptal", now, neden=hf["iptal_nedeni"] or "hazır fırsat iptal edildi")
                    out["yazilan"] += 1
                    continue
            bars = [b for b in bars_fn(t["ticker"], t["signal_day"]) if b.get("close")]
            gun = next((b for b in bars if b["date"] == t["giris_gunu"]), None)
            if gun is None:
                if any(b["date"] > t["giris_gunu"] for b in bars):
                    _sonuc_yaz(conn, t["id"], "girissiz", now, neden="giriş günü işlem verisi yok")
                    out["yazilan"] += 1
                continue                                          # henüz veri yok → açık
            acilis = gun.get("open") or gun["close"]
            if acilis > t["azami_giris"] + 1e-9:
                _sonuc_yaz(conn, t["id"], "girissiz", now, neden="açılış azami girişin üstünde",
                           giris_gunu_gercek=gun["date"], ayrinti={"acilis": acilis})
                out["yazilan"] += 1
                continue
            rec = {"kaynak": "gercek", "gercek_giris_gunu": t["giris_gunu"], "gercek_giris_fiyati": acilis,
                   "signal_day": t["signal_day"], "senaryo": t["tur"], "sl": t["sl"], "tp1": t["tp1"], "tp2": t["tp2"],
                   "giris": t["giris"], "alarm": None, "gecerlilik": GECERLILIK_GUN}
            res = journal.evaluate(rec, bars, commission_pct, slippage_pct)
            if res.get("durum") != "kapandı":
                continue                                          # pozisyon sürüyor → açık
            after = [b for b in bars if b["date"] > t["signal_day"]]
            i0 = next(i for i, b in enumerate(after) if b["date"] >= t["giris_gunu"])
            n = int(res.get("islem_gunu") or 1)
            held = after[i0:i0 + n]
            risk = t["giris"] - t["sl"]
            mae = mfe = None
            if held and risk > 0:
                mae = round((min(_hl(b)[1] for b in held) - acilis) / risk, 3)
                mfe = round((max(_hl(b)[0] for b in held) - acilis) / risk, 3)
            bel = belirsiz_gunler(after[i0:], acilis, t["sl"], t["tp1"], t["tp2"], n)
            _sonuc_yaz(conn, t["id"], "tamamlandi", now, giris_gunu_gercek=res.get("giris_gunu"), giris_fiyati=acilis,
                       tp1_goruldu=int(bool(res.get("tp1_goruldu"))),
                       sl_goruldu=int(res.get("sonuc") == "SL" and not res.get("tp1_goruldu")),
                       cikis_nedeni=res.get("sonuc"), cikis_gunu=res.get("cikis_gunu"), islem_gunu=n,
                       net_getiri_pct=res.get("net_getiri_pct"), r=res.get("r"), mae_r=mae, mfe_r=mfe,
                       ayni_gun_belirsiz=bool(bel), belirsiz_gunler=bel,
                       ayrinti={"bacaklar": res.get("bacaklar"), "olaylar": res.get("olaylar"),
                                "komisyon_pct": commission_pct, "kayma_pct": slippage_pct})
            out["yazilan"] += 1
        conn.commit()
    except Exception as e:
        out["hata"] = str(e)[:200]
    return out


# ---------------------------------------------------------------- ölçüm
def wilson(k: int, n: int, z: float = 1.645) -> Optional[List[float]]:
    """%90 Wilson güven aralığı (oran, yüzde olarak)."""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1)]


def guven(n: int) -> str:
    return ("çok az örnek, karar verilmez" if n < 30 else "düşük güven" if n < 100 else "orta güven")


def model_surumleri(conn) -> List[Dict]:
    if not tablo_var(conn):
        return []
    return [dict(r) for r in conn.execute(
        "SELECT model_surum, COUNT(*) AS n, MIN(tahmin_zamani) AS ilk, MAX(tahmin_zamani) AS son FROM tahmin "
        "GROUP BY model_surum ORDER BY son DESC")]


def ozet(conn, model_surum: str, kaynak: Optional[str] = None, tur: Optional[str] = None,
         analiz: Optional[str] = None, bant: Optional[str] = None, belirsiz_dahil: bool = True) -> Dict:
    """TEK model sürümü için canlı performans (sürümler asla birleştirilmez). Yalnız 'tamamlandi' sonuçlar metrik
    hesabına girer; açık tahminler yalnız sayılır. Sonradan eklenen tahminler ana hesaba katılmaz."""
    if not tablo_var(conn):
        return {"tablo_yok": True}
    q = ("SELECT t.*, s.sonuc_turu, s.tp1_goruldu, s.sl_goruldu, s.net_getiri_pct, s.r, s.mae_r, s.mfe_r, "
         "s.ayni_gun_belirsiz, s.cikis_nedeni, s.islem_gunu FROM tahmin t LEFT JOIN tahmin_sonuc s ON s.tahmin_id=t.id "
         "WHERE t.model_surum=?")
    args: List = [model_surum]
    for col, val in (("kaynak", kaynak), ("tur", tur), ("analiz", analiz), ("bant", bant)):
        if val:
            q += f" AND t.{col}=?"
            args.append(val)
    rows = [dict(r) for r in conn.execute(q, args)]
    say = {"tahmin": len(rows), "sonradan": sum(r["sonradan"] for r in rows)}
    main = [r for r in rows if not r["sonradan"]]
    say["acik"] = sum(r["sonuc_turu"] is None for r in main)
    for k in ("tamamlandi",) + OLCULMEYEN:
        say[k] = sum(r["sonuc_turu"] == k for r in main)
    done = [r for r in main if r["sonuc_turu"] == "tamamlandi"]
    say["belirsiz"] = sum(bool(r["ayni_gun_belirsiz"]) for r in done)
    if not belirsiz_dahil:
        done = [r for r in done if not r["ayni_gun_belirsiz"]]
    n = len(done)
    out = {"model_surum": model_surum, "sayilar": say, "olculen": n, "guven": guven(n),
           "surum_uyarisi": None, "metrik": None, "kalibrasyon": [], "rejim": [], "beklenti": None}
    oz = sorted({(r["ozellik_surum"], r["parametre_surum"]) for r in rows})
    if len(oz) > 1:
        out["surum_uyarisi"] = (f"Bu model sürümünde {len(oz)} farklı özellik/parametre sürümü var; ayrı ayrı "
                                "değerlendirin: " + ", ".join(f"{a}/{b}" for a, b in oz))
    if not n:
        return out
    y = [int(bool(r["tp1_goruldu"])) for r in done]
    p = [min(max(float(r["olasilik"]), 1e-6), 1 - 1e-6) for r in done]
    rs = [r["r"] for r in done if r["r"] is not None]
    nets = [r["net_getiri_pct"] for r in done if r["net_getiri_pct"] is not None]
    out["metrik"] = {
        "kazanma_%": round(100 * sum(x > 0 for x in nets) / len(nets), 1) if nets else None,
        "tp1_%": round(100 * sum(y) / n, 1), "tp1_%90": wilson(sum(y), n),
        "beklenen_R": round(sum(rs) / len(rs), 3) if rs else None,
        "ort_net_%": round(sum(nets) / len(nets), 2) if nets else None,
        "brier": round(sum((a - b) ** 2 for a, b in zip(p, y)) / n, 4),
        "log_loss": round(-sum(b * math.log(a) + (1 - b) * math.log(1 - a) for a, b in zip(p, y)) / n, 4),
        "ort_tahmin_%": round(100 * sum(p) / n, 1),
        "ort_mae_r": round(sum(r["mae_r"] for r in done if r["mae_r"] is not None) / max(1, sum(r["mae_r"] is not None for r in done)), 3),
        "ort_mfe_r": round(sum(r["mfe_r"] for r in done if r["mfe_r"] is not None) / max(1, sum(r["mfe_r"] is not None for r in done)), 3),
        "ort_islem_gunu": round(sum(r["islem_gunu"] or 0 for r in done) / n, 1)}
    for b in ("düşük", "orta", "yüksek"):
        g = [(pp, yy) for pp, yy, r in zip(p, y, done) if r["bant"] == b]
        if g:
            k = sum(yy for _, yy in g)
            out["kalibrasyon"].append({"bant": b, "n": len(g), "ort_tahmin_%": round(100 * sum(pp for pp, _ in g) / len(g), 1),
                                       "gercek_%": round(100 * k / len(g), 1), "gercek_%90": wilson(k, len(g)),
                                       "guven": guven(len(g))})
    reg: Dict[str, List] = {}
    for r, yy in zip(done, y):
        rg = json.loads(r["rejim_json"] or "null") or {}
        key = f"{rg.get('trend') or '?'} / oynaklık {rg.get('oynaklik') or '?'}"
        reg.setdefault(key, []).append((yy, r["r"]))
    for key, v in sorted(reg.items()):
        rr = [x for _, x in v if x is not None]
        out["rejim"].append({"rejim": key, "n": len(v), "tp1_%": round(100 * sum(a for a, _ in v) / len(v), 1),
                             "ort_R": round(sum(rr) / len(rr), 3) if rr else None, "guven": guven(len(v))})
    bo = [r["benzer_oran"] for r in done if r["benzer_oran"] is not None]
    out["beklenti"] = {"model_ort_tahmin_%": out["metrik"]["ort_tahmin_%"],
                       "gecmis_benzer_oran_%": round(100 * sum(bo) / len(bo), 1) if bo else None,
                       "canli_tp1_%": out["metrik"]["tp1_%"], "canli_tp1_%90": out["metrik"]["tp1_%90"],
                       "not": "Canlı oranın güven aralığı model beklentisini içeriyorsa fark anlamlı değildir."}
    return out
