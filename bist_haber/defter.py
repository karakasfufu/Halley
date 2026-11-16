"""FAZ 1 (2026-11-16): canlı tahmin defteri. Ayrıntılı kurallar: HALLEY2_DENETIM_RAPORU.md Ek B, C ve F.

Kavramlar (ayrı kayıtlar):
  - Tahmin (tablo `tahmin`): hazır fırsat yazıldığı anda modelin söylediği olasılık + o anki bağlam (girdiler, teknik
    göstergeler, rejim, veri kalitesi, işlem seviyeleri, sürümler) + DEĞERLENDİRME SÖZLEŞMESİ (sonuçlandırma kural
    sürümü, komisyon, kayma, maliyet protokolü). YALNIZ EKLENİR; veritabanı güncellemeyi/silmeyi reddeder.
  - Tahmin sonucu (`tahmin_sonuc`): tahminin KENDİ dondurulmuş seviyeleri ve KENDİ sözleşmesiyle nihai sonucu; tahmin
    başına en fazla bir satır, YALNIZ EKLENİR.
  - Yeniden değerlendirme (`tahmin_degerlendirme`): eski kuralla (s1) yazılmış sonucun yeni kuralla (s2) ayrı, sürümlü
    değerlendirmesi. s1 kaydı DEĞİŞTİRİLMEZ; ölçüm en güncel kural sürümünü kullanır.
  - Defter olayları (`defter_olay`): kayıt hatası, veri eksikliği gibi olaylar (görünür; tekrar denemede çoğalmaz).
  - Hazır fırsat (`hazir_firsat`) ve sanal işlem (`trade_journal`) bu modülden ETKİLENMEZ.
Plan imzası (tekrar ↔ yeni tahmin ayrımı; DEĞİŞMEDİ): ticker | signal_day | giris_gunu | tur | giris | azami_giris |
sl | tp1 | tp2 | gecerlilik_gun | model_surum | ozellik_surum | parametre_surum (sayılar 4 basamak). Olasılık, rejim,
veri kalitesi ya da maliyet ayarı tek başına değişirse yeni tahmin SAYILMAZ (ilk kayıt dondurulmuş kalır).
Kural sürümü s2 (Ek F): TP1 olayı = TP1 hedefine SL'den önce ulaşıldı (doğrudan TP2 açılışı dahil); maliyet tahmin
anındaki sözleşmeden; giriş günü mumu eksikse nihai sonuç yazılmaz ("veri_eksik"); MAE/MFE yalnız pozisyon süresince
(çıkış mumunda yalnız çıkış fiyatı; günlük mum yaklaşığı).
Seçim kuralları, eşikler, TP1 modeli ve yapay zekâ kullanımı DEĞİŞMEZ; bu modül yalnız kaydeder ve ölçer. YZ yok.
"""
import hashlib
import json
import math
import sqlite3
from datetime import date, datetime
from typing import Dict, List, Optional

from . import config

KURAL_SURUM = "s2"
MALIYET_PROTOKOL = "ayar_tahmin_ani_v1"   # komisyon ve kayma, tahmin anındaki Halley ayarından dondurulur
MAE_MFE_YONTEM = ("gunluk_s2: giriş mumu (açılıştan sonra) ve aradaki mumlar tam; çıkış mumunda açılışta çıkışsa "
                  "yalnız açılış, gün içi çıkışsa yalnız çıkış fiyatı, süre dolduysa tam mum; R paydası planlanan "
                  "risk (giriş − SL)")
ACILIS_SINIRI = "09:55"           # bu saatten (giriş günü, TR) sonra kaydedilen tahmin ölçülmez ("gec_kayit")
GECERLILIK_GUN = 1                # hazır fırsat yalnız giriş günü açılışı için geçerli
OLCULMEYEN = ("girissiz", "iptal", "yerini_aldi", "gec_kayit")
TEKNIK_ALANLAR = ("tarih", "son_fiyat", "trend", "rsi14", "macd_hist", "adx", "arti_di", "eksi_di", "atr", "atr_%",
                  "sma50", "sma200", "ema20", "ema50", "ema200", "hacim_orani", "obv_egilim", "rs_20g_%", "rs_60g_%",
                  "destek_20g", "direnc_20g", "islem_hacmi_tl", "fiyat_sma50_%", "fiyat_sma200_%", "perf_20g_%")
TABLO_ANAHTAR = ("tur", "trend", "atr_%", "rsi")   # benzer durumlar tablosunun grup anahtarı (tp1_model._table_key)
GRUP_ALANLARI = ("model_surum", "ozellik_surum", "parametre_surum", "kural_surum", "maliyet_protokol", "komisyon_pct",
                 "kayma_pct")
DONEM_DISI_GEREKCE = ("Uygun dönem dışı geçmiş sınama referansı yok: 5 yıllık araştırma evreni haber şartı içermeyen "
                      "teknik plan evrenidir; canlı hazır fırsatlar ise haber skoru, en fazla 5 seçim, sabah kontrolü "
                      "gibi farklı koşullarla seçilir. Modeldeki 'benzer durumlar oranı' eğitim tablosundandır, dönem "
                      "dışı performans değildir. Bu yüzden canlı sonuç yalnız modelin kendi tahminiyle (kalibrasyon) "
                      "karşılaştırılır.")


def _now() -> datetime:
    return datetime.now(config.TR_TZ)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _sha(obj, n: int = 12) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:n]


def tablo_var(conn) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tahmin'").fetchone())


def _var(conn, tablo: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tablo,)).fetchone())


def _cols(conn, tablo: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tablo})")}


def olay(conn, ad: str, anahtar: str, mesaj: str = "", **k) -> None:
    """Görünür defter olayı (kayıt hatası, veri eksikliği…). Aynı anahtar ikinci kez yazılmaz (tekrar denemede
    çoğalmaz). Olay kaydı da başarısız olursa hazır fırsat akışı yine durmaz."""
    try:
        if not _var(conn, "defter_olay"):
            return
        conn.execute("INSERT OR IGNORE INTO defter_olay(zaman,olay,anahtar,tahmin_id,hazir_firsat_id,ticker,giris_gunu,mesaj) "
                     "VALUES(?,?,?,?,?,?,?,?)", (_iso(_now()), ad, anahtar, k.get("tahmin_id"), k.get("hazir_firsat_id"),
                                                 k.get("ticker"), k.get("giris_gunu"), (mesaj or "")[:500]))
        conn.commit()
    except Exception:
        pass


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


def maliyet_ayari() -> Dict:
    """Halley'in o anki komisyon ve kayma ayarı (alış + satış toplamı, %)."""
    from . import journal, pipeline
    st = pipeline.load_settings()
    return {"komisyon_pct": float(st.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT)),
            "kayma_pct": float(st.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT))}


# ---------------------------------------------------------------- kayıt
def kaydet(conn, p: Dict, hazir_firsat_id: Optional[int], giris_gunu: str, analiz: str,
           now: Optional[datetime] = None, sonradan: bool = False) -> Dict:
    """Hazır fırsat planından tahmin satırı. Dönüş: {"durum": "yeni"|"tekrar"|"tablo_yok"|"model_yok"|"veri_yok"|"hata",
    "id"}. Hiçbir durumda hata fırlatmaz (hazır fırsat kaydını asla engellemez); başarısızlık `defter_olay`'a yazılır."""
    tk = (p or {}).get("ticker")
    anahtar = f"{hazir_firsat_id if hazir_firsat_id is not None else tk}:{giris_gunu}"
    try:
        from . import tp1_model
        if not tablo_var(conn):
            return {"durum": "tablo_yok"}
        name = tp1_model.active_name()
        m = tp1_model.load(name)
        if not m:
            olay(conn, "model_yok", f"model_yok:{anahtar}", f"model dosyası yüklenemedi: {name}",
                 hazir_firsat_id=hazir_firsat_id, ticker=tk, giris_gunu=giris_gunu)
            return {"durum": "model_yok"}
        sv = surumler(m, name)
        imza = plan_imzasi(p, giris_gunu, sv)
        old = conn.execute("SELECT id FROM tahmin WHERE plan_imzasi=?", (imza,)).fetchone()
        if old:
            return {"durum": "tekrar", "id": old[0]}
        ctx = tp1_model.plan_context(conn, p)
        if not ctx:
            olay(conn, "veri_yok", f"veri_yok:{anahtar}", "sinyal gününe ait fiyat penceresi yok; tahmin yapılamadı",
                 hazir_firsat_id=hazir_firsat_id, ticker=tk, giris_gunu=giris_gunu)
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
        mal = maliyet_ayari()                              # değerlendirme sözleşmesi tahmin anında dondurulur
        prev = conn.execute("SELECT id FROM tahmin WHERE ticker=? AND giris_gunu=? ORDER BY id DESC LIMIT 1",
                            (p["ticker"], giris_gunu)).fetchone()
        now = now or _now()
        cur = conn.execute(
            "INSERT OR IGNORE INTO tahmin(plan_imzasi,onceki_tahmin_id,hazir_firsat_id,ticker,signal_day,giris_gunu,analiz,"
            "tahmin_zamani,model_surum,model_dosya,ozellik_surum,parametre_surum,kod_surum,olasilik,bant,benzer_n,"
            "benzer_oran,tur,giris,giris_alt,azami_giris,sl,tp1,tp2,rr1,gecerlilik_gun,genel_puan,teknik_skor,haber_skoru,"
            "kaynak,risk,girdi_json,teknik_json,rejim_json,veri_json,sonradan,kural_surum,komisyon_pct,kayma_pct,"
            "maliyet_protokol) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (imza, prev[0] if prev else None, hazir_firsat_id, p["ticker"], p["signal_day"], giris_gunu, analiz,
             _iso(now), sv["model_surum"], sv["model_dosya"], sv["ozellik_surum"], sv["parametre_surum"],
             sv["kod_surum"], float(prob), tp1_model.band(prob, m), sim.get("n"), sim.get("gercek"), p["tur"],
             p["giris"], p.get("giris_alt"), p["azami_giris"], p["sl"], p["tp1"], p["tp2"], p.get("rr1"),
             GECERLILIK_GUN, p.get("genel_puan"), p.get("teknik_skor"), p.get("haber_skoru"), p.get("kaynak", "haber"),
             p.get("risk"), json.dumps(f, ensure_ascii=False, default=str),
             json.dumps(teknik, ensure_ascii=False, default=str), json.dumps(rejim, ensure_ascii=False, default=str),
             json.dumps(veri, ensure_ascii=False, default=str), int(bool(sonradan)), KURAL_SURUM,
             mal["komisyon_pct"], mal["kayma_pct"], MALIYET_PROTOKOL))
        conn.commit()
        if not cur.rowcount:    # aynı anda başka süreç yazdıysa
            row = conn.execute("SELECT id FROM tahmin WHERE plan_imzasi=?", (imza,)).fetchone()
            return {"durum": "tekrar", "id": row[0] if row else None}
        return {"durum": "yeni", "id": cur.lastrowid}
    except Exception as e:  # defter hatası hazır fırsatı asla engellemez; ama GÖRÜNÜR kalır
        # rollback YOK: çağıran _store'un henüz kaydedilmemiş hazır fırsat yazımı da geri alınırdı
        olay(conn, "kayit_hatasi", f"kayit_hatasi:{anahtar}", f"{type(e).__name__}: {e}",
             hazir_firsat_id=hazir_firsat_id, ticker=tk, giris_gunu=giris_gunu)
        return {"durum": "hata", "hata": str(e)[:200]}


# ---------------------------------------------------------------- sonuçlandırma (kural sürümü s2)
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


def mae_mfe(held: List[Dict], fill: float, res: Dict, risk: float) -> Dict:
    """Pozisyon süresince en kötü/en iyi fiyat (R = (fiyat − giriş) / planlanan risk). Pencere (s2):
    giriş mumu (giriş açılışta; mumun tamamı girişten sonradır) ve aradaki mumlar TAM; çıkış mumunda açılışta çıkışsa
    yalnız açılış, gün içi çıkışsa yalnız çıkış fiyatı (mumun geri kalanı çıkıştan sonra olabilir), süre dolduysa
    (kapanışta çıkış) tam mum. Gün içi çıkışta değerler günlük mumdan çıkarılamayan sıranın alt sınırıdır → yaklaşık."""
    n = int(res.get("islem_gunu") or 1)
    bars = held[:n]
    son = (res.get("bacaklar") or [{}])[-1]
    neden, cikis = son.get("neden") or "", son.get("fiyat")
    lows, highs, yaklasik = [fill], [fill], 0
    for b in bars[:-1]:
        h, l, _ = _hl(b)
        lows.append(l)
        highs.append(h)
    if bars:
        h, l, o = _hl(bars[-1])
        if neden == "süre doldu":
            lows.append(l)
            highs.append(h)
        elif "açılış" in neden and n > 1:
            lows.append(o)
            highs.append(o)
        else:                                           # gün içi çıkış (giriş günü çıkışı dahil)
            if cikis is not None:
                lows.append(cikis)
                highs.append(cikis)
            yaklasik = 1
    if risk <= 0:
        return {"mae_r": None, "mfe_r": None, "yaklasik": yaklasik}
    return {"mae_r": round((min(lows) - fill) / risk, 3), "mfe_r": round((max(highs) - fill) / risk, 3),
            "yaklasik": yaklasik}


def _degerlendir(t: Dict, bars: List[Dict], kom: float, kay: float) -> Dict:
    """Bir tahminin fiyatlara göre durumu: {"durum": "acik"|"veri_eksik"|"sonuc", "alanlar": {...}}."""
    from . import journal
    gun = next((b for b in bars if b["date"] == t["giris_gunu"]), None)
    if gun is None:
        if any(b["date"] > t["giris_gunu"] for b in bars):
            return {"durum": "veri_eksik"}             # sonraki günler var, giriş günü yok: doğrulanmadan nihai yok
        return {"durum": "acik"}
    acilis = gun.get("open") or gun["close"]
    if acilis > t["azami_giris"] + 1e-9:
        return {"durum": "sonuc", "alanlar": {"sonuc_turu": "girissiz", "neden": "açılış azami girişin üstünde",
                                               "giris_gunu_gercek": gun["date"], "ayrinti": {"acilis": acilis}}}
    rec = {"kaynak": "gercek", "gercek_giris_gunu": t["giris_gunu"], "gercek_giris_fiyati": acilis,
           "signal_day": t["signal_day"], "senaryo": t["tur"], "sl": t["sl"], "tp1": t["tp1"], "tp2": t["tp2"],
           "giris": t["giris"], "alarm": None, "gecerlilik": GECERLILIK_GUN}
    res = journal.evaluate(rec, bars, kom, kay)
    if res.get("durum") != "kapandı":
        return {"durum": "acik"}
    after = [b for b in bars if b["date"] > t["signal_day"]]
    i0 = next(i for i, b in enumerate(after) if b["date"] >= t["giris_gunu"])
    n = int(res.get("islem_gunu") or 1)
    mm = mae_mfe(after[i0:], acilis, res, t["giris"] - t["sl"])
    bel = belirsiz_gunler(after[i0:], acilis, t["sl"], t["tp1"], t["tp2"], n)
    return {"durum": "sonuc", "alanlar": {
        "sonuc_turu": "tamamlandi", "giris_gunu_gercek": res.get("giris_gunu"), "giris_fiyati": acilis,
        "tp1_goruldu": int(bool(res.get("tp1_goruldu"))), "tp1_olayi": int(bool(res.get("tp1_hedefi"))),
        "sl_goruldu": int(res.get("sonuc") == "SL" and not res.get("tp1_hedefi")),
        "cikis_nedeni": res.get("sonuc"), "cikis_gunu": res.get("cikis_gunu"), "islem_gunu": n,
        "net_getiri_pct": res.get("net_getiri_pct"), "r": res.get("r"), "mae_r": mm["mae_r"], "mfe_r": mm["mfe_r"],
        "mae_mfe_yontem": MAE_MFE_YONTEM, "mae_mfe_yaklasik": mm["yaklasik"], "ayni_gun_belirsiz": int(bool(bel)),
        "belirsiz_gunler": bel, "ayrinti": {"bacaklar": res.get("bacaklar"), "olaylar": res.get("olaylar")}}}


_SONUC_ALANLARI = ("sonuc_turu", "neden", "giris_gunu_gercek", "giris_fiyati", "tp1_goruldu", "tp1_olayi", "sl_goruldu",
                   "cikis_nedeni", "cikis_gunu", "islem_gunu", "net_getiri_pct", "r", "mae_r", "mfe_r", "mae_mfe_yontem",
                   "mae_mfe_yaklasik", "ayni_gun_belirsiz", "belirsiz_gunler", "komisyon_pct", "kayma_pct",
                   "maliyet_kaynagi", "ayrinti_json")


def _satir(k: Dict) -> Dict:
    d = {a: k.get(a) for a in _SONUC_ALANLARI}
    d["ayni_gun_belirsiz"] = int(bool(k.get("ayni_gun_belirsiz")))
    d["belirsiz_gunler"] = json.dumps(k.get("belirsiz_gunler") or [], ensure_ascii=False)
    d["ayrinti_json"] = json.dumps(k.get("ayrinti"), ensure_ascii=False, default=str) if k.get("ayrinti") is not None else None
    return d


def _sonuc_yaz(conn, tid: int, tur: str, now: datetime, **k) -> None:
    k["sonuc_turu"] = tur
    d = _satir(k)
    v2 = "tp1_olayi" in _cols(conn, "tahmin_sonuc")
    alan = [a for a in _SONUC_ALANLARI if v2 or a not in ("tp1_olayi", "komisyon_pct", "kayma_pct", "maliyet_kaynagi",
                                                            "mae_mfe_yontem", "mae_mfe_yaklasik")]
    conn.execute(f"INSERT OR IGNORE INTO tahmin_sonuc(tahmin_id,{','.join(alan)},degerlendirme_zamani,kural_surum) "
                 f"VALUES(?,{','.join('?' * len(alan))},?,?)", [tid] + [d[a] for a in alan] + [_iso(now), KURAL_SURUM])


def _degerlendirme_yaz(conn, tid: int, now: datetime, gerekce: str, **k) -> None:
    d = _satir(k)
    conn.execute(f"INSERT OR IGNORE INTO tahmin_degerlendirme(tahmin_id,kural_surum,{','.join(_SONUC_ALANLARI)},gerekce,"
                 f"degerlendirme_zamani) VALUES(?,?,{','.join('?' * len(_SONUC_ALANLARI))},?,?)",
                 [tid, KURAL_SURUM] + [d[a] for a in _SONUC_ALANLARI] + [gerekce, _iso(now)])


def _maliyet(t: Dict, yedek: Optional[Dict], s1_ayrinti: Optional[str] = None) -> Dict:
    """Değerlendirme maliyeti: önce tahminin kendi sözleşmesi; yoksa (eski kayıt) s1 sonucunda kullanılan değerler;
    o da yoksa sonuçlandırma anındaki ayar. Hangisi kullanıldığı AÇIKÇA kaydedilir (tahmin edilerek doldurulmaz)."""
    if t.get("komisyon_pct") is not None and t.get("kayma_pct") is not None:
        return {"komisyon_pct": t["komisyon_pct"], "kayma_pct": t["kayma_pct"], "maliyet_kaynagi": "tahmin_sozlesmesi"}
    if s1_ayrinti:
        try:
            a = json.loads(s1_ayrinti) or {}
            if a.get("komisyon_pct") is not None and a.get("kayma_pct") is not None:
                return {"komisyon_pct": a["komisyon_pct"], "kayma_pct": a["kayma_pct"],
                        "maliyet_kaynagi": "s1_sonuclandirma_ayari"}
        except ValueError:
            pass
    y = yedek or maliyet_ayari()
    return {"komisyon_pct": y["komisyon_pct"], "kayma_pct": y["kayma_pct"],
            "maliyet_kaynagi": "sozlesme_eksik_sonuclandirma_ani_ayari"}


def sonuclandir(conn, now: Optional[datetime] = None, commission_pct: Optional[float] = None,
                slippage_pct: Optional[float] = None, bars_fn=None) -> Dict:
    """Açık tahminlerden nihai sonucu belli olanlara TEK sonuç satırı yazar; eski kuralla (s1) yazılmış fiyat
    sonuçlarına ayrı s2 değerlendirmesi ekler (Ek F). commission_pct/slippage_pct yalnız sözleşmesi EKSİK eski kayıtlar
    için yedek değerdir. Hata fırlatmaz; hata `defter_olay`'a yazılır."""
    from . import journal
    out = {"incelenen": 0, "yazilan": 0, "yeniden_degerlendirilen": 0, "veri_eksik": 0, "hata": None}
    if not tablo_var(conn):
        out["hata"] = "tablo_yok"
        return out
    try:
        now = now or _now()
        yedek = ({"komisyon_pct": commission_pct, "kayma_pct": slippage_pct}
                 if commission_pct is not None and slippage_pct is not None else None)
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
            mal = _maliyet(t, yedek)
            d = _degerlendir(t, bars, mal["komisyon_pct"], mal["kayma_pct"])
            if d["durum"] == "veri_eksik":
                out["veri_eksik"] += 1
                olay(conn, "veri_eksik", f"veri_eksik:{t['id']}", "giriş günü mumu yok, sonraki günler var; nihai "
                     "sonuç yazılmadı (veri doğrulanana kadar)", tahmin_id=t["id"], ticker=t["ticker"],
                     giris_gunu=t["giris_gunu"])
                continue
            if d["durum"] == "acik":
                continue
            k = dict(d["alanlar"])
            if k["sonuc_turu"] == "tamamlandi":
                k.update(mal)
                k["ayrinti"] = dict(k.get("ayrinti") or {}, komisyon_pct=mal["komisyon_pct"], kayma_pct=mal["kayma_pct"])
            _sonuc_yaz(conn, t["id"], k.pop("sonuc_turu"), now, **k)
            out["yazilan"] += 1
        # eski kural (s1) ile yazılmış FİYAT sonuçları → ayrı s2 değerlendirmesi (s1 kaydı değişmez)
        if _var(conn, "tahmin_degerlendirme"):
            eski = conn.execute(
                "SELECT t.*, s.sonuc_turu AS s_tur, s.neden AS s_neden, s.ayrinti_json AS s_ayrinti, s.kural_surum AS s_kural "
                "FROM tahmin t JOIN tahmin_sonuc s ON s.tahmin_id=t.id LEFT JOIN tahmin_degerlendirme d "
                "ON d.tahmin_id=t.id AND d.kural_surum=? WHERE s.kural_surum<>? AND d.id IS NULL "
                "AND s.sonuc_turu IN ('tamamlandi','girissiz')", (KURAL_SURUM, KURAL_SURUM)).fetchall()
            for t in eski:
                t = dict(t)
                bars = [b for b in bars_fn(t["ticker"], t["signal_day"]) if b.get("close")]
                mal = _maliyet(t, yedek, t["s_ayrinti"])
                d = _degerlendir(t, bars, mal["komisyon_pct"], mal["kayma_pct"])
                if d["durum"] != "sonuc":
                    if d["durum"] == "veri_eksik":
                        out["veri_eksik"] += 1
                    continue
                k = dict(d["alanlar"])
                if k["sonuc_turu"] == "tamamlandi":
                    k.update(mal)
                    k["ayrinti"] = dict(k.get("ayrinti") or {}, komisyon_pct=mal["komisyon_pct"], kayma_pct=mal["kayma_pct"])
                _degerlendirme_yaz(conn, t["id"], now, f"{t['s_kural']} sonucunun {KURAL_SURUM} kuralıyla ayrı "
                                   f"değerlendirmesi (s1 kaydı değiştirilmedi)", **k)
                out["yeniden_degerlendirilen"] += 1
        conn.commit()
    except Exception as e:
        out["hata"] = str(e)[:200]
        olay(conn, "sonuclandirma_hatasi", f"sonuclandirma_hatasi:{_iso(now or _now())[:13]}", f"{type(e).__name__}: {e}")
    return out


# ---------------------------------------------------------------- ölçüm
def wilson(k: int, n: int, z: float = 1.645) -> Optional[List[float]]:
    """%90 Wilson güven aralığı (oran, yüzde olarak). Bağımsız gözlem varsayar; aynı günün tahminleri birbirine bağlı
    olabildiğinden gerçek belirsizlik daha geniş olabilir (bkz. guven)."""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1)]


def guven(n: int, gun: Optional[int] = None) -> str:
    """Güven etiketi yalnız örnek sayısına bakmaz: aynı gün/aynı piyasa koşulundaki tahminler bağımlıdır, bu yüzden
    farklı giriş günü sayısı (bağımsız gün) da yeterli olmalı (en az 20 gün → düşük güven, en az 60 gün → orta)."""
    if n < 30:
        return "çok az örnek, karar verilmez"
    if gun is not None and gun < 20:
        return f"az bağımsız gün ({gun}), karar verilmez"
    if n < 100 or (gun is not None and gun < 60):
        return "düşük güven"
    return "orta güven"


def model_surumleri(conn) -> List[Dict]:
    if not tablo_var(conn):
        return []
    return [dict(r) for r in conn.execute(
        "SELECT model_surum, COUNT(*) AS n, MIN(tahmin_zamani) AS ilk, MAX(tahmin_zamani) AS son FROM tahmin "
        "GROUP BY model_surum ORDER BY son DESC")]


def _grup_of(r: Dict) -> Dict:
    return {"model_surum": r["model_surum"], "ozellik_surum": r["ozellik_surum"], "parametre_surum": r["parametre_surum"],
            "kural_surum": r.get("kural_surum") or "eksik", "maliyet_protokol": r.get("maliyet_protokol") or "eksik",
            "komisyon_pct": r.get("komisyon_pct"), "kayma_pct": r.get("kayma_pct")}


def grup_etiketi(g: Dict) -> str:
    mal = ("maliyet eksik" if g["maliyet_protokol"] == "eksik" else
           f"maliyet %{g['komisyon_pct']:g}+%{g['kayma_pct']:g}")
    return (f"{g['model_surum']} · özellik {g['ozellik_surum'][:6]} · parametre {g['parametre_surum'][:6]} · "
            f"kural {g['kural_surum']} · {mal}")


def gruplar(conn) -> List[Dict]:
    """Performansın AYRI hesaplandığı bileşimler: model × özellik × parametre × sonuçlandırma kuralı × maliyet
    protokolü (ve değerleri). Sözleşmesi eksik eski kayıtlar 'eksik' grubundadır."""
    if not tablo_var(conn):
        return []
    v2 = "kural_surum" in _cols(conn, "tahmin")
    ek = ", kural_surum, maliyet_protokol, komisyon_pct, kayma_pct" if v2 else ""
    rows = [dict(r) for r in conn.execute(f"SELECT model_surum, ozellik_surum, parametre_surum{ek}, tahmin_zamani "
                                          "FROM tahmin")]
    acc: Dict[str, Dict] = {}
    for r in rows:
        g = _grup_of(r)
        k = json.dumps(g, sort_keys=True, default=str)
        a = acc.setdefault(k, {"grup": g, "n": 0, "son": ""})
        a["n"] += 1
        a["son"] = max(a["son"], r["tahmin_zamani"])
    return sorted(acc.values(), key=lambda a: a["son"], reverse=True)


def kayit_zamani(tahmin_zamani: str, giris_gunu: str) -> str:
    """Kaydın GERÇEK yazılma zamanından (16.11.2026, panel filtresi): giriş gününün kendisinde yazıldıysa "sabah",
    giriş gününden önceki bir tarihte yazıldıysa (gece yarısını geçen akşam analizi dahil) "aksam". Kayıtlara
    dokunmaz; yalnız okunan alanlardan hesaplanır. Not: `analiz` alanı ise "planı üreten analiz"dir (sabah onaylanan
    akşam planında "aksam" kalır)."""
    return "sabah" if (tahmin_zamani or "")[:10] >= giris_gunu else "aksam"


def _etkin_sonuclar(conn) -> Dict[int, Dict]:
    """Tahmin başına ölçümde kullanılacak sonuç: varsa güncel kuralın (s2) ayrı değerlendirmesi, yoksa nihai sonuç
    satırı. Kaynağı ('sonuc' / 'degerlendirme') ve kural sürümü işaretlenir."""
    out: Dict[int, Dict] = {}
    for r in conn.execute("SELECT * FROM tahmin_sonuc"):
        d = dict(r)
        d["_kaynak"] = "sonuc"
        out[d["tahmin_id"]] = d
    if _var(conn, "tahmin_degerlendirme"):
        for r in conn.execute("SELECT * FROM tahmin_degerlendirme WHERE kural_surum=?", (KURAL_SURUM,)):
            d = dict(r)
            d["_kaynak"] = "degerlendirme"
            out[d["tahmin_id"]] = d
    return out


def _y(s: Dict) -> int:
    """TP1 olayı: s2'de açık alan; eski satırda tp1_goruldu ya da TP2 çıkışı (aynı anlam)."""
    if s.get("tp1_olayi") is not None:
        return int(bool(s["tp1_olayi"]))
    return int(bool(s.get("tp1_goruldu")) or s.get("cikis_nedeni") == "TP2")


def _veri_eksik_mi(conn, t: Dict) -> bool:
    r = conn.execute("SELECT MIN(date) FROM prices WHERE ticker=? AND date>? AND close IS NOT NULL",
                     (t["ticker"], t["signal_day"])).fetchone()
    return bool(r and r[0] and r[0] > t["giris_gunu"])


def kapsam(conn) -> Dict:
    """Kayıt kapsamı: defter etkinleştikten sonra yazılan hazır fırsatların kaçının tahmini var? Eksikler ve son
    defter olayları (kayıt hatası, veri yok…) görünür."""
    if not tablo_var(conn):
        return {"hazir_firsat": 0, "tahminli": 0, "eksik": 0, "eksikler": [], "olaylar": []}
    # pencere: defterin gördüğü en erken giriş günü (tahmin ya da olay); o günden itibaren yazılan hazır fırsatlar
    bas = [conn.execute("SELECT MIN(giris_gunu) FROM tahmin").fetchone()[0]]
    if _var(conn, "defter_olay"):
        bas.append(conn.execute("SELECT MIN(giris_gunu) FROM defter_olay WHERE giris_gunu IS NOT NULL").fetchone()[0])
    bas = [b for b in bas if b]
    if not bas:
        return {"hazir_firsat": 0, "tahminli": 0, "eksik": 0, "eksikler": [], "olaylar": [], "baslangic": None}
    start = min(bas)
    hf = [dict(r) for r in conn.execute("SELECT id, ticker, giris_gunu, durum, guncellendi FROM hazir_firsat "
                                        "WHERE giris_gunu>=?", (start,))]
    with_t = {r[0] for r in conn.execute("SELECT DISTINCT hazir_firsat_id FROM tahmin WHERE hazir_firsat_id IS NOT NULL")}
    eks = [h for h in hf if h["id"] not in with_t]
    ol = ([dict(r) for r in conn.execute("SELECT zaman, olay, ticker, giris_gunu, mesaj FROM defter_olay "
                                         "ORDER BY id DESC LIMIT 20")] if _var(conn, "defter_olay") else [])
    return {"hazir_firsat": len(hf), "tahminli": len(hf) - len(eks), "eksik": len(eks), "eksikler": eks,
            "olaylar": ol, "baslangic": start}


def ozet(conn, grup: Dict, kaynak: Optional[str] = None, tur: Optional[str] = None,
         analiz: Optional[str] = None, bant: Optional[str] = None, belirsiz_dahil: bool = True,
         kayit: Optional[str] = None) -> Dict:
    """TEK bir sürüm grubu için canlı performans (model × özellik × parametre × kural × maliyet; gruplar asla
    birleştirilmez). Yalnız 'tamamlandi' sonuçlar metrik hesabına girer; açık ve veri eksik tahminler yalnız sayılır;
    sonradan eklenenler ana hesaba katılmaz. analiz = planı üreten analiz; kayit = kaydın yazıldığı zaman."""
    if not isinstance(grup, dict):
        raise TypeError("ozet() bir sürüm grubu (gruplar() öğesi) ister; yalnız model sürümüyle birleşik hesap yapılmaz")
    if not tablo_var(conn):
        return {"tablo_yok": True}
    rows = [dict(r) for r in conn.execute("SELECT * FROM tahmin")]
    rows = [r for r in rows if _grup_of(r) == {k: grup.get(k) for k in GRUP_ALANLARI}]
    for col, val in (("kaynak", kaynak), ("tur", tur), ("analiz", analiz), ("bant", bant)):
        if val:
            rows = [r for r in rows if r.get(col) == val]
    if kayit:
        rows = [r for r in rows if kayit_zamani(r["tahmin_zamani"], r["giris_gunu"]) == kayit]
    son = _etkin_sonuclar(conn)
    say = {"tahmin": len(rows), "sonradan": sum(r["sonradan"] for r in rows), "acik": 0, "veri_eksik": 0,
           "s1_bekliyor": 0, "tamamlandi": 0, "belirsiz": 0}
    for k in OLCULMEYEN:
        say[k] = 0
    done = []
    for r in rows:
        if r["sonradan"]:
            continue
        s = son.get(r["id"])
        if s is None:
            say["veri_eksik" if _veri_eksik_mi(conn, r) else "acik"] += 1
            continue
        tur_ = s["sonuc_turu"]
        if s["_kaynak"] == "sonuc" and s.get("kural_surum") != KURAL_SURUM and tur_ in ("tamamlandi", "girissiz"):
            if tur_ == "girissiz" and s.get("neden") == "giriş günü işlem verisi yok":
                say["veri_eksik"] += 1                      # s1'in eksik veride yazdığı "girişsiz" nihai sayılmaz
            else:
                say["s1_bekliyor"] += 1                     # s2 değerlendirmesi henüz yok → metrik dışında
            continue
        say[tur_] = say.get(tur_, 0) + 1
        if tur_ == "tamamlandi":
            done.append(dict(r, **{f"s_{a}": s.get(a) for a in s}))
    say["belirsiz"] = sum(bool(r["s_ayni_gun_belirsiz"]) for r in done)
    if not belirsiz_dahil:
        done = [r for r in done if not r["s_ayni_gun_belirsiz"]]
    n = len(done)
    gun = len({r["giris_gunu"] for r in done})
    out = {"grup": grup, "sayilar": say, "olculen": n, "bagimsiz_gun": gun, "guven": guven(n, gun), "metrik": None,
           "kalibrasyon": [], "rejim": [], "beklenti": None,
           "aralik_notu": "%90 aralıklar bağımsızlık varsayar; aynı günün tahminleri bağımlı olabilir."}
    if not n:
        return out
    y = [_y({k[2:]: v for k, v in r.items() if k.startswith("s_")}) for r in done]
    p = [min(max(float(r["olasilik"]), 1e-6), 1 - 1e-6) for r in done]
    rs = [r["s_r"] for r in done if r["s_r"] is not None]
    nets = [r["s_net_getiri_pct"] for r in done if r["s_net_getiri_pct"] is not None]
    mae = [r["s_mae_r"] for r in done if r["s_mae_r"] is not None]
    mfe = [r["s_mfe_r"] for r in done if r["s_mfe_r"] is not None]
    out["metrik"] = {
        "kazanma_%": round(100 * sum(x > 0 for x in nets) / len(nets), 1) if nets else None,
        "tp1_%": round(100 * sum(y) / n, 1), "tp1_%90": wilson(sum(y), n),
        "beklenen_R": round(sum(rs) / len(rs), 3) if rs else None,
        "ort_net_%": round(sum(nets) / len(nets), 2) if nets else None,
        "brier": round(sum((a - b) ** 2 for a, b in zip(p, y)) / n, 4),
        "log_loss": round(-sum(b * math.log(a) + (1 - b) * math.log(1 - a) for a, b in zip(p, y)) / n, 4),
        "ort_tahmin_%": round(100 * sum(p) / n, 1),
        "ort_mae_r": round(sum(mae) / len(mae), 3) if mae else None,
        "ort_mfe_r": round(sum(mfe) / len(mfe), 3) if mfe else None,
        "mae_mfe_yaklasik": sum(bool(r["s_mae_mfe_yaklasik"]) for r in done),
        "ort_islem_gunu": round(sum(r["s_islem_gunu"] or 0 for r in done) / n, 1)}
    for b in ("düşük", "orta", "yüksek"):
        g = [(pp, yy, r["giris_gunu"]) for pp, yy, r in zip(p, y, done) if r["bant"] == b]
        if g:
            k = sum(yy for _, yy, _ in g)
            out["kalibrasyon"].append({"bant": b, "n": len(g), "ort_tahmin_%": round(100 * sum(pp for pp, _, _ in g) / len(g), 1),
                                       "gercek_%": round(100 * k / len(g), 1), "gercek_%90": wilson(k, len(g)),
                                       "guven": guven(len(g), len({d for _, _, d in g}))})
    reg: Dict[str, List] = {}
    for r, yy in zip(done, y):
        rg = json.loads(r["rejim_json"] or "null") or {}
        key = f"{rg.get('trend') or '?'} / oynaklık {rg.get('oynaklik') or '?'}"
        reg.setdefault(key, []).append((yy, r["s_r"], r["giris_gunu"]))
    for key, v in sorted(reg.items()):
        rr = [x for _, x, _ in v if x is not None]
        out["rejim"].append({"rejim": key, "n": len(v), "tp1_%": round(100 * sum(a for a, _, _ in v) / len(v), 1),
                             "ort_R": round(sum(rr) / len(rr), 3) if rr else None,
                             "guven": guven(len(v), len({d for _, _, d in v}))})
    out["beklenti"] = {"model_ort_tahmin_%": out["metrik"]["ort_tahmin_%"], "canli_tp1_%": out["metrik"]["tp1_%"],
                       "canli_tp1_%90": out["metrik"]["tp1_%90"],
                       "not": "Kalibrasyon: canlı oranın aralığı modelin ortalama tahminini içeriyorsa fark anlamlı "
                              "değildir.",
                       "donem_disi_referans": None, "donem_disi_gerekce": DONEM_DISI_GEREKCE}
    return out
