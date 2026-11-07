"""Kaçırılan fırsat analizi (W4, 2026-11-07).

Soru: bot bir hisseyi önermedi (ya da önerdi ama giriş oluşmadı) ve hisse sonraki günlerde ciddi yükseldi — neden?

Geriye dönük bilgi karışmaz:
- Karar, o gün bekçinin KAYDETTİĞİ karardır (signal_log; değiştirilemez). Kaydı olmayan gün yeniden kurulmaz.
- Karar anındaki "baz gün", çalıştırma saatinde kapanışı kesinleşmiş son işlem günüdür (sabah → önceki gün).
- ATR ve likidite baz gün dahil ÖNCEKİ barlarla hesaplanır; yükseliş yalnız SONRAKİ günlerin kapanışıyla ölçülür.
- "Haber sonradan geldi" ayrımı: baz günden sonra yayımlanan haber o an bilinemezdi; bu botun hatası sayılmaz.

Eşik (gerçek dağılımdan, 2026-11-07 ölçümü): canlı veritabanında son ~1 yıl, likit hisseler (20 gün ort. işlem hacmi
≥ 2 mn TL), 133.287 hisse-gün. 5 işlem günü içindeki en yüksek kapanışın, XU100'ün aynı dönemdeki getirisi düşüldükten
sonra baz gün ATR'sine oranı: medyan 0,33 · %90 2,12 · %95 3,01 · %97,5 3,98 · %99 5,48. Eşik 4 ATR = en güçlü ~%2,5
(gün başına medyan 14 hisse). 3 ATR günde ~29 hisse işaretliyordu ("ciddi yükseliş" için fazla gürültülü).
Pencere içinde ±%10,5'ten büyük günlük hareket (düzeltilmemiş bölünme/bedelsiz ya da veri hatası) varsa hisse
o pencere için değerlendirilmez ve "veri şüphesi" olarak sayılır.
"""
import json
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config, market_calendar, technical

THRESHOLD_ATR = 4.0
WINDOW_DAYS = 5
LOOKBACK_DAYS = 10       # son 10 işlem gününün kararları (bekçi birkaç gün çalışmasa da tamamlanan pencere kaydedilir)
LIQ_MIN_TL = 2e6          # tradeplan.LIQ_MIN_TL ile aynı (ölçüm bu kitleyle yapıldı)
DATA_JUMP = 0.105
BENCH = "XU100"

EXPLAIN = {
    "HABER_YOK": ("haber", "Kayıtlarda bu hisseyle eşleşen haber/KAP bildirimi yoktu."),
    "HABER_ANALIZ_BEKLIYOR": ("haber", "Haber vardı ama karar anında henüz analiz edilmemişti (analiz sırası/sınırı)."),
    "HABER_ONEMSIZ": ("haber", "Haber vardı ama ön elemede önemsiz/rutin bulundu."),
    "HABER_OLUMSUZ": ("haber", "Haber olumsuz yorumlandı, hisse ise yükseldi (yorum yanlış olabilir)."),
    "SKOR_ESIK_ALTI": ("skor", "Haber olumluydu ama fırsat puanı eşiğin (1,5) altında kaldı."),
    "TEKNIK_VERI_YOK": ("veri", "Fiyat geçmişi yetersizdi (teknik analiz yapılamadı)."),
    "VERI_KRITIK": ("veri", "Fiyat verisinde kritik sorun vardı (eski fiyat ya da düzeltilmemiş sıçrama)."),
    "LIKIDITE": ("likidite", "Likidite düşük olduğu için elendi (bilinçli koruma)."),
    "SENARYO_UYGUN_DEGIL": ("teknik", "Teknik filtre eledi: hiçbir giriş senaryosu uygun değildi."),
    "ONERILDI": ("giriş", "Önerildi ama giriş koşulu oluşmadı (limit fiyata inmedi ya da kırılım teyidi gelmedi)."),
}

SUGGEST = {
    "HABER_YOK": "Haber dışı (teknik/para akışı) hareket botun kapsamı dışında. Sık tekrarlarsa ayrı bir 'haber dışı "
                 "momentum' taraması düşünülebilir (onayınızla, ayrı modül).",
    "HABER_SONRA": "Hareket karar anından SONRA gelen haberle başladı; o an bilinemezdi — botun hatası değil. Haberin "
                   "hızlı yakalanması için gün içinde 'Haberleri güncelle' sıklığı artırılabilir.",
    "ESLESME": "Haber başlığında hisse kodu geçiyor ama haber bu hisseyle eşleştirilmemiş: şirket eşleştirme "
               "(takma adlar listesi) kontrol edilmeli.",
    "HABER_ANALIZ_BEKLIYOR": "Analiz sırası yetişmedi: sabah analizinde yapay zekâ kutusunu açmak ya da analiz sınırını "
                             "artırmak kapsamı artırır (maliyet artar; karar sizde).",
    "HABER_ONEMSIZ": "Ön eleme bu bildirim türünü önemsiz saydı: tekrarlıyorsa bu konu başlığının ön elemeden "
                     "çıkarılması değerlendirilebilir (W5 birikimli sayım; tek örnekle değiştirmeyin).",
    "HABER_OLUMSUZ": "Haber yorumu fiyatla ters düştü: bu haber türü için yorum kuralları gözden geçirilmeli.",
    "SKOR_ESIK_ALTI": "Eşik 1,5 tek örnekle değiştirilmemeli; W5'te eşik altı kalan kaçırılanların sıklığı ölçülecek.",
    "TEKNIK_VERI_YOK": "Veri eksikliği: yeni halka arz ya da veri sağlayıcı eksiği. Düzeltilecek bir eşik yok.",
    "VERI_KRITIK": "Veri sağlayıcı sorunu: fiyat kaynağı kontrol edilmeli.",
    "LIKIDITE": "Bilinçli koruma (sığ hissede emir fiyatı oynatır); değiştirilmesi önerilmez.",
    "SENARYO_UYGUN_DEGIL": "Teknik filtre fırsat eliyor olabilir: hangi senaryo koşulunun sık elediği W5'te sayılacak.",
    "FIYATLANMIS": "Haber fiyatlanmış (aşırı yükselmiş) diye temkinli davranıldı; hareket devam etti. Tek örnekle kural "
                   "değiştirilmez; W5'te bu durumun sıklığı izlenecek.",
    "ONERILDI": "Giriş seviyesi (limit/kırılım) fazla temkinli olabilir; senaryo türüne göre gerçekleşme oranı W5'te.",
}


def base_day(started_at: str) -> date:
    """Çalıştırma anında kapanışı kesinleşmiş son işlem günü (kapanış + 10 dk)."""
    t = datetime.fromisoformat(started_at)
    if t.tzinfo:
        t = t.astimezone(config.TR_TZ).replace(tzinfo=None)
    d = t.date()
    while True:
        close = market_calendar.session_close(d)
        if close and t >= datetime.combine(d, close) + timedelta(minutes=10):
            return d
        d -= timedelta(days=1)


def decision_groups(conn, since: date) -> Dict[str, int]:
    """Her baz gün için en son çalıştırma (o günden sonraki ilk seanstan önce verilen son karar)."""
    out: Dict[str, int] = {}
    for r in conn.execute("SELECT run_id, started_at FROM watch_runs WHERE day>=? ORDER BY run_id",
                          ((since - timedelta(days=7)).isoformat(),)):
        b = base_day(r["started_at"]).isoformat()
        if b >= since.isoformat():
            out[b] = r["run_id"]          # sonraki run_id öncekini ezer → son karar
    return out


def _bars(conn, ticker, upto_after: str, before: str, n_before: int = 40):
    pre = [dict(r) for r in conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND "
                                         "date<=? ORDER BY date DESC LIMIT ?", (ticker, before, n_before))][::-1]
    post = [dict(r) for r in conn.execute("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND "
                                          "date>? ORDER BY date LIMIT ?", (ticker, before, WINDOW_DAYS))]
    return pre, [b for b in post if b["date"] <= upto_after]


def _later_news(conn, ticker: str, after_day: str, until_day: str, started_at: str) -> int:
    like = f"%,{ticker},%"
    return conn.execute("SELECT COUNT(*) FROM news WHERE (','||candidates||',') LIKE ? AND status!='context' AND "
                        "published_at>? AND substr(published_at,1,10)<=?", (like, started_at, until_day)).fetchone()[0]


def _title_mentions(conn, ticker: str, from_day: str, until: str) -> int:
    """Başlıkta hisse kodu geçen ama bu hisseyle eşleştirilmemiş haber (eşleşme kaçmış olabilir)."""
    return conn.execute("SELECT COUNT(*) FROM news WHERE status!='context' AND (' '||UPPER(title)||' ') LIKE ? AND "
                        "(','||COALESCE(candidates,'')||',') NOT LIKE ? AND substr(published_at,1,10)>=? AND "
                        "published_at<=?", (f"% {ticker} %", f"%,{ticker},%", from_day, until)).fetchone()[0]


def _filled(conn, ticker: str, signal_day: str) -> Optional[str]:
    r = conn.execute("SELECT durum FROM trade_journal WHERE ticker=? AND kaynak='otomatik' AND signal_day<=? "
                     "ORDER BY signal_day DESC LIMIT 1", (ticker, signal_day)).fetchone()
    return r["durum"] if r else None


def analyze_day(conn, b_day: str, run_id: int, today: date) -> Dict:
    """Bir baz günün kararları için kaçırılan fırsatlar (pencere bugüne kadar)."""
    run = conn.execute("SELECT * FROM watch_runs WHERE run_id=?", (run_id,)).fetchone()
    bench_pre, bench_post = _bars(conn, BENCH, today.isoformat(), b_day, 2)
    bench0 = bench_pre[-1]["close"] if bench_pre and bench_pre[-1]["date"] == b_day else None
    bench_px = {b["date"]: b["close"] for b in bench_post}
    out = {"baz_gun": b_day, "run_id": run_id, "karar_ani": run["started_at"], "kind": run["kind"],
           "kacirilan": [], "veri_suphesi": 0, "degerlendirilen": 0, "pencere_gun": len(bench_post),
           "neden_sayilari": {},     # W5: neden → değerlendirilen hisse sayısı (filtre başına kaçırma oranı için)
           "tamamlandi": len(bench_post) >= WINDOW_DAYS}
    if bench0 is None or not bench_post:
        out["yok"] = "Endeks fiyatı yok ya da baz günden sonra henüz işlem günü kapanmadı."
        return out
    for s in conn.execute("SELECT * FROM signal_log WHERE run_id=?", (run_id,)).fetchall():
        t = s["ticker"]
        pre, post = _bars(conn, t, today.isoformat(), b_day)
        if len(pre) < 15 or pre[-1]["date"] != b_day or not post:
            continue
        liq = sum(x["close"] * (x["volume"] or 0) for x in pre[-20:]) / len(pre[-20:])
        if liq < LIQ_MIN_TL and s["neden_kodu"] != "LIKIDITE":
            continue
        a = technical.atr(pre[-31:])
        if not a:
            continue
        seq = [pre[-1]] + post
        if any(abs(seq[k + 1]["close"] / seq[k]["close"] - 1) > DATA_JUMP for k in range(len(post))):
            out["veri_suphesi"] += 1
            continue
        out["degerlendirilen"] += 1
        out["neden_sayilari"][s["neden_kodu"]] = out["neden_sayilari"].get(s["neden_kodu"], 0) + 1
        c0 = pre[-1]["close"]
        best, peak = None, None
        for x in post:
            if x["date"] not in bench_px:
                continue
            v = ((x["close"] / c0 - 1) - (bench_px[x["date"]] / bench0 - 1)) * c0 / a
            if best is None or v > best:
                best, peak = v, x
        if best is None or best < THRESHOLD_ATR:
            continue
        code = s["neden_kodu"]
        detay = json.loads(s["detay_json"] or "{}")
        if code == "ONERILDI":
            st = _filled(conn, t, b_day)
            if st and st not in ("bekliyor", "iptal"):
                continue                       # önerildi ve giriş oldu → kaçırılan değil (başarı/başarısızlık bölüm 9)
        later = _later_news(conn, t, b_day, peak["date"], run["started_at"])
        mention = _title_mentions(conn, t, (date.fromisoformat(b_day) - timedelta(days=7)).isoformat(),
                                  run["started_at"]) if code == "HABER_YOK" else 0
        tags = []
        if code == "HABER_YOK" and later:
            tags.append("HABER_SONRA")
        if mention:
            tags.append("ESLESME")
        if detay.get("fiyatlanmis"):
            tags.append("FIYATLANMIS")
        mod, text = EXPLAIN.get(code, ("?", code))
        out["kacirilan"].append({
            "hisse": t, "baz_gun": b_day, "baz_kapanis": c0, "zirve_gunu": peak["date"], "zirve_kapanis": peak["close"],
            "kazanc_%": (peak["close"] / c0 - 1) * 100,
            "endeks_%": (bench_px[peak["date"]] / bench0 - 1) * 100, "endekse_gore_atr": best,
            "neden_kodu": code, "modul": mod, "aciklama": text, "etiketler": tags,
            "haber_skoru": s["haber_skoru"], "sonradan_haber": later, "baslikta_kod": mention,
            "senaryolar": detay.get("senaryolar"), "neden_yok": detay.get("neden_yok"),
            "oneri": [SUGGEST[k] for k in tags + [code] if k in SUGGEST][:2],
            "pencere_tamam": len(post) >= WINDOW_DAYS})
    out["kacirilan"].sort(key=lambda x: -x["endekse_gore_atr"])
    return out


def scan(conn, today: Optional[date] = None, lookback_trading_days: int = LOOKBACK_DAYS) -> Dict:
    """Son baz günlerin kaçırılan fırsatları; penceresi tamamlananlar değiştirilemez günlüğe yazılır."""
    today = today or datetime.now(config.TR_TZ).date()
    since = today
    for _ in range(lookback_trading_days):
        since = since - timedelta(days=1)
        while not market_calendar.is_trading_day(since):
            since -= timedelta(days=1)
    groups = decision_groups(conn, since)
    days = []
    for b, rid in sorted(groups.items()):
        if b >= today.isoformat():
            continue
        days.append(analyze_day(conn, b, rid, today))
    stored = 0
    with conn:
        for d in days:
            if not d["tamamlandi"]:
                continue
            miss_by = Counter(x["neden_kodu"] for x in d["kacirilan"])
            for code, n in d["neden_sayilari"].items():
                conn.execute("INSERT OR IGNORE INTO missed_day_stats(baz_gun, neden_kodu, run_id, degerlendirilen, "
                             "kacirilan) VALUES(?,?,?,?,?)", (d["baz_gun"], code, d["run_id"], n, miss_by.get(code, 0)))
            for x in d["kacirilan"]:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO missed_log(baz_gun, ticker, run_id, neden_kodu, modul, kazanc_pct, "
                    "endekse_gore_atr, zirve_gunu, etiketler, kayit_ani) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (x["baz_gun"], x["hisse"], d["run_id"], x["neden_kodu"], x["modul"], round(x["kazanc_%"], 3),
                     round(x["endekse_gore_atr"], 3), x["zirve_gunu"], ",".join(x["etiketler"]),
                     datetime.now(config.TR_TZ).isoformat(timespec="seconds")))
                stored += cur.rowcount
    all_items = [x for d in days for x in d["kacirilan"]]
    # aynı hisse birden çok baz günde görünürse en eski karar günü (ilk kaçırılan) esas alınır
    first: Dict[str, dict] = {}
    for x in sorted(all_items, key=lambda x: x["baz_gun"]):
        first.setdefault(x["hisse"], x)
    items = sorted(first.values(), key=lambda x: -x["endekse_gore_atr"])
    reasons = Counter(x["neden_kodu"] for x in items)
    tags = Counter(t for x in items for t in x["etiketler"])
    return {"gunler": [{k: v for k, v in d.items() if k != "kacirilan"} for d in days], "liste": items,
            "nedenler": dict(reasons), "etiketler": dict(tags), "kaydedilen": stored,
            "esik_atr": THRESHOLD_ATR, "pencere": WINDOW_DAYS, "kayitsiz_gun": _unlogged_days(since, today, groups)}


def _unlogged_days(since: date, today: date, groups: Dict[str, int]) -> List[str]:
    out, d = [], since
    while d < today:
        if market_calendar.is_trading_day(d) and d.isoformat() not in groups:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _fmt(v, f="{:.2f}"):
    return "—" if v is None else f.format(v)


def report_md(res: Dict) -> Dict[str, str]:
    """Akşam raporunun 7. ve 8. bölümleri."""
    items = res["liste"]
    head = (f"_Yöntem: karar anında kaydedilen karar (geriye dönük bilgi yok); baz günden sonraki en fazla "
            f"{res['pencere']} işlem gününde kapanış, endeksin en az {res['esik_atr']:g} ATR üstüne çıktıysa "
            "(son 1 yılın en güçlü ~%2,5'i) 'ciddi yükseliş' sayılır. Sığ hisseler (20 gün ort. hacim < 2 mn TL) "
            "yalnız likidite nedeniyle elendiyse listelenir._\n\n")
    if res["kayitsiz_gun"]:
        head += (f"_Bekçi kaydı olmayan işlem günleri ({', '.join(res['kayitsiz_gun'])}): o günlerin kararı bilinmediği "
                 "için kaçırılan fırsat analizi yapılamaz (yeniden kurulmaz)._\n\n")
    ev = sum(d.get("degerlendirilen", 0) for d in res["gunler"])
    sus = sum(d.get("veri_suphesi", 0) for d in res["gunler"])
    if not res["gunler"]:
        lst = head + "_Değerlendirilecek karar günü yok: kaçırılan fırsat analizi için bekçinin en az bir gün önce " \
                     "çalışmış olması ve sonrasında en az bir seansın kapanmış olması gerekir._\n"
        return {"md_liste": lst, "md_neden": "_Kaçırılan fırsat yok._\n"}
    lst = head + (f"{len(res['gunler'])} karar gününde {ev} hisse-gün değerlendirildi"
                  + (f" ({sus} veri şüphesi nedeniyle dışarıda)" if sus else "") + f"; **{len(items)} kaçırılan fırsat**.\n\n")
    if items:
        lst += "| Hisse | Karar (baz) günü | Zirve günü | Kazanç % | Endeks % | Endekse göre ATR | Pencere | Karar |\n" \
               "|---|---|---|---|---|---|---|---|\n"
        for x in items[:15]:
            lst += (f"| {x['hisse']} | {x['baz_gun']} | {x['zirve_gunu']} | {x['kazanc_%']:+.1f} | {x['endeks_%']:+.1f} | "
                    f"{x['endekse_gore_atr']:.1f} | {'tamam' if x['pencere_tamam'] else 'sürüyor'} | {x['neden_kodu']} |\n")
        if len(items) > 15:
            lst += f"\n_… ve {len(items) - 15} hisse daha (tamamı raporun .json dosyasında)._\n"
    if not items:
        return {"md_liste": lst, "md_neden": "_Kaçırılan fırsat yok._\n"}
    by = Counter(x["neden_kodu"] for x in items)
    neden = "| Neden | Modül | Hisse sayısı | Örnekler |\n|---|---|---|---|\n"
    for code, n in by.most_common():
        mod, text = EXPLAIN.get(code, ("?", code))
        ex = ", ".join(x["hisse"] for x in items if x["neden_kodu"] == code)[:80]
        neden += f"| {text} | {mod} | {n} | {ex} |\n"
    t = res["etiketler"]
    extra = []
    if t.get("HABER_SONRA"):
        extra.append(f"{t['HABER_SONRA']} hissede hareket karar anından SONRA gelen haberle başladı (o an bilinemezdi; "
                     "botun hatası sayılmaz).")
    if t.get("ESLESME"):
        extra.append(f"{t['ESLESME']} hissede başlıkta hisse kodu geçen ama eşleştirilmemiş haber var (şirket eşleştirme "
                     "kontrol edilmeli).")
    if t.get("FIYATLANMIS"):
        extra.append(f"{t['FIYATLANMIS']} hisse 'haber fiyatlanmış / aşırı yükselmiş' uyarısı alan hisselerdendi.")
    neden += "\n" + "".join(f"- {e}\n" for e in extra)
    neden += "\n**İyileştirme önerileri (onayınız olmadan hiçbir ayar değişmez):**\n"
    seen = []
    for x in items:
        for o in x["oneri"]:
            if o not in seen:
                seen.append(o)
    neden += "".join(f"- {o}\n" for o in seen[:6])
    return {"md_liste": lst, "md_neden": neden}
