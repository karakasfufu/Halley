"""Performans ve gelişim takibi (W5, 2026-11-07) — kullanıcı isteği bölüm 4.

Sorular: hangi haber kaynağı daha başarılı sinyal üretiyor, hangi filtre gereğinden fazla fırsat eliyor, hangi
strateji daha başarılı, hangi hata/neden tekrar ediyor, performans zamanla iyileşiyor mu?

Kurallar:
- Yalnız kayıtlı veri (işlem günlüğü, kaçırılan fırsat günlüğü, karar izi). Yapay zekâ yok.
- Öneri yalnız YETERLİ ÖRNEK ve istatistiksel olarak anlamlı fark varsa üretilir ("küçük pilotla eşik değiştirme").
- Öneriler kullanıcı onayına sunulur; onay/ret yalnız kaydedilir, HİÇBİR AYAR KENDİLİĞİNDEN DEĞİŞMEZ.
"""
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config

MIN_TRADES = 30            # strateji/kaynak karşılaştırması için en az kapanmış işlem (journal.MIN_TRADES_FOR_STATS)
MIN_FILTER_N = 200         # filtre kaçırma oranı için en az değerlendirilen hisse-gün
MIN_FILTER_MISSED = 10     # ve en az kaçırılan
FILTER_RATIO = 1.5         # filtrenin kaçırma oranı diğerlerinin en az 1,5 katı
Z_CRIT = 2.58              # %99 güven (çoklu karşılaştırmada yanlış alarmı azaltmak için sıkı)
COVERAGE_SHARE = 0.30      # analiz bekleyen hisse payı
COVERAGE_RUNS = (5, 10)    # son 10 çalıştırmanın en az 5'inde
RECENT_DAYS = 28           # tekrar eden nedenler: son 4 hafta / önceki 4 hafta
REPEAT_MATCH = 3           # eşleşme hatası en az 3 farklı hissede
REPEAT_LATE_NEWS = 5       # "haber sonra geldi" en az 5 kez
RESUGGEST_DAYS = 30        # kararı verilmiş öneri 30 gün yeniden önerilmez

FILTER_CODES = {
    "SENARYO_UYGUN_DEGIL": ("Teknik filtre (giriş senaryosu uygun değil)", "kod",
                            "Senaryo koşulları (bist_haber/entries.py) gözden geçirilmeli"),
    "SKOR_ESIK_ALTI": ("Fırsat puanı eşiği (1,5)", "kod", "Puan eşiği geçmiş veriyle yeniden ayarlanmalı (calibration)"),
    "HABER_ONEMSIZ": ("Haber ön elemesi (önemsiz/rutin)", "kod", "Ön eleme konu listesi gözden geçirilmeli"),
    "HABER_OLUMSUZ": ("Haber yönü yorumu (olumsuz)", "kod", "Bu haber türlerinin yorum kuralı gözden geçirilmeli"),
    "HABER_ANALIZ_BEKLIYOR": ("Analiz sırası/sınırı", "ayar", "Ayarlar → 'Bir güncellemede en fazla kaç haber analiz "
                              "edilsin' ya da sabah analizinde yapay zekâ kutusu (maliyet artar)"),
    "ONERILDI": ("Giriş seviyesi (önerildi ama giriş oluşmadı)", "kod", "Limit/kırılım giriş seviyeleri (entries.py)"),
}


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d


def two_prop_z(k1, n1, k2, n2) -> Optional[float]:
    if not n1 or not n2:
        return None
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se if se else None


# ---------------------------------------------------------------- veriler
def filter_rates(conn, since: Optional[str] = None) -> Dict:
    rows = conn.execute("SELECT neden_kodu, SUM(degerlendirilen) n, SUM(kacirilan) k, COUNT(DISTINCT baz_gun) g "
                        "FROM missed_day_stats WHERE baz_gun>=? GROUP BY neden_kodu", (since or "",)).fetchall()
    tot_n = sum(r["n"] for r in rows)
    tot_k = sum(r["k"] for r in rows)
    out = []
    for r in rows:
        on, ok = tot_n - r["n"], tot_k - r["k"]
        lo, hi = wilson(r["k"], r["n"])
        out.append({"neden": r["neden_kodu"], "degerlendirilen": r["n"], "kacirilan": r["k"], "gun": r["g"],
                    "oran_%": 100 * r["k"] / r["n"] if r["n"] else None, "alt_%": 100 * lo if lo is not None else None,
                    "ust_%": 100 * hi if hi is not None else None,
                    "digerleri_%": 100 * ok / on if on else None, "z": two_prop_z(r["k"], r["n"], ok, on)})
    out.sort(key=lambda x: -(x["oran_%"] or 0))
    return {"satirlar": out, "toplam_n": tot_n, "toplam_k": tot_k,
            "genel_%": 100 * tot_k / tot_n if tot_n else None,
            "gun": conn.execute("SELECT COUNT(DISTINCT baz_gun) FROM missed_day_stats WHERE baz_gun>=?",
                                (since or "",)).fetchone()[0]}


def _source_label(src: Optional[str]) -> str:
    if not src:
        return "bilinmiyor"
    if src == "kap":
        return "KAP"
    if src.startswith("rss:"):
        return config.RSS_SOURCE_LABELS.get(src[4:], src[4:])
    return src


def _closed(conn, kaynak="otomatik") -> List[Dict]:
    out = []
    for r in conn.execute("SELECT * FROM trade_journal WHERE kaynak=? AND durum='kapandı'", (kaynak,)):
        res = json.loads(r["sonuc_json"]) if r["sonuc_json"] else {}
        if res.get("net_getiri_pct") is None:
            continue
        src = conn.execute("SELECT n.source FROM impacts i JOIN news n ON n.id=i.news_id WHERE i.ticker=? AND "
                           "i.direction>0 AND i.effective_date<=? ORDER BY i.published_at DESC LIMIT 1",
                           (r["ticker"], r["signal_day"])).fetchone()
        out.append({"id": r["id"], "hisse": r["ticker"], "senaryo": r["senaryo"], "risk": r["risk_seviyesi"] or "—",
                    "kaynak_haber": _source_label(src["source"] if src else None), "cikis": res.get("cikis_gunu") or "",
                    "net": res["net_getiri_pct"], "r": res.get("r"), "sonuc": res.get("sonuc")})
    return sorted(out, key=lambda x: (x["cikis"], x["id"]))


def _stats(xs: List[Dict]) -> Dict:
    n = len(xs)
    rs = [x["r"] for x in xs if x["r"] is not None]
    wins = sum(1 for x in xs if x["net"] > 0)
    mr = sum(rs) / len(rs) if rs else None
    sd = math.sqrt(sum((v - mr) ** 2 for v in rs) / (len(rs) - 1)) if len(rs) > 1 else None
    return {"n": n, "kazanma_%": 100 * wins / n if n else None, "ort_R": mr, "toplam_R": sum(rs) if rs else None,
            "ort_net_%": sum(x["net"] for x in xs) / n if n else None, "sd_R": sd, "yeterli": n >= MIN_TRADES}


def strategy_stats(conn) -> Dict[str, List[Dict]]:
    xs = _closed(conn)
    out = {}
    for key, label in (("senaryo", "Senaryo"), ("risk", "Risk seviyesi"), ("kaynak_haber", "Haber kaynağı")):
        g = defaultdict(list)
        for x in xs:
            g[x[key]].append(x)
        out[key] = sorted(({"grup": k, **_stats(v)} for k, v in g.items()), key=lambda r: -r["n"])
    return out


def performance(conn) -> Dict:
    xs = _closed(conn)
    weeks = defaultdict(list)
    for x in xs:
        if x["cikis"]:
            y, w, _ = date.fromisoformat(x["cikis"]).isocalendar()
            weeks[f"{y}-H{w:02d}"].append(x)
    out = {"toplam": _stats(xs), "haftalik": [{"hafta": k, **_stats(v)} for k, v in sorted(weeks.items())]}
    if len(xs) >= 2 * MIN_TRADES:
        a, b = _stats(xs[-MIN_TRADES:]), _stats(xs[-2 * MIN_TRADES:-MIN_TRADES])
        out["karsilastirma"] = {"son": a, "onceki": b}
    return out


def repeated(conn, today: date) -> Dict:
    r0 = (today - timedelta(days=RECENT_DAYS)).isoformat()
    p0 = (today - timedelta(days=2 * RECENT_DAYS)).isoformat()
    rows = conn.execute("SELECT * FROM missed_log WHERE baz_gun>=?", (p0,)).fetchall()
    rec = [r for r in rows if r["baz_gun"] >= r0]
    prev = [r for r in rows if r["baz_gun"] < r0]
    tag = lambda rs: Counter(t for r in rs for t in (r["etiketler"] or "").split(",") if t)
    return {"son_neden": dict(Counter(r["neden_kodu"] for r in rec)),
            "onceki_neden": dict(Counter(r["neden_kodu"] for r in prev)),
            "son_etiket": dict(tag(rec)), "onceki_etiket": dict(tag(prev)),
            "eslesme_hisse": sorted({r["ticker"] for r in rec if "ESLESME" in (r["etiketler"] or "")}),
            "son_sayi": len(rec), "onceki_sayi": len(prev)}


def coverage(conn, last: int = COVERAGE_RUNS[1]) -> List[Dict]:
    out = []
    for r in conn.execute("SELECT run_id, kind, day, summary_json FROM watch_runs WHERE kind IN ('sabah','aksam') "
                          "ORDER BY run_id DESC LIMIT ?", (last,)):
        s = json.loads(r["summary_json"] or "{}")
        n = s.get("nedenler") or {}
        tot = sum(n.values())
        if tot:
            out.append({"gun": r["day"], "tur": r["kind"], "bekleyen": n.get("HABER_ANALIZ_BEKLIYOR", 0), "toplam": tot,
                        "pay": n.get("HABER_ANALIZ_BEKLIYOR", 0) / tot})
    return out


# ---------------------------------------------------------------- öneri kuralları
def generate(conn, today: date) -> List[Dict]:
    sug = []
    fr = filter_rates(conn, (today - timedelta(days=180)).isoformat())
    for r in fr["satirlar"]:
        if r["neden"] not in FILTER_CODES:
            continue
        if r["degerlendirilen"] < MIN_FILTER_N or r["kacirilan"] < MIN_FILTER_MISSED or r["z"] is None:
            continue
        if r["z"] >= Z_CRIT and r["oran_%"] >= FILTER_RATIO * (r["digerleri_%"] or 0):
            name, tur, where = FILTER_CODES[r["neden"]]
            sug.append({"anahtar": f"filtre:{r['neden']}", "tur": tur, "baslik": f"{name} fazla fırsat eliyor olabilir",
                        "metin": (f"Bu nedenle elenen {r['degerlendirilen']} hisse-günün %{r['oran_%']:.1f}'i sonra ciddi "
                                  f"yükseldi; diğer nedenlerde bu oran %{r['digerleri_%']:.1f} ({r['gun']} karar günü, "
                                  f"fark istatistiksel olarak anlamlı, z = {r['z']:.1f}). Öneri: ilgili kural gözden "
                                  "geçirilsin. Onaylarsanız bu bir yapılacak iş olarak kaydedilir; kural kendiliğinden "
                                  "değişmez."),
                        "nerede": where, "kanit": r})
    st = strategy_stats(conn)
    for key, what in (("senaryo", "Senaryo"), ("kaynak_haber", "Haber kaynağı")):
        rows = st[key]
        for r in rows:
            if r["n"] < MIN_TRADES or r["ort_R"] is None or not r["sd_R"]:
                continue
            hi = r["ort_R"] + 1.96 * r["sd_R"] / math.sqrt(r["n"])
            if hi < 0:
                sug.append({"anahtar": f"{key}:{r['grup']}:zayif", "tur": "kod",
                            "baslik": f"{what} '{r['grup']}' zarar ettiriyor",
                            "metin": (f"{r['n']} kapanmış sanal işlemde ortalama {r['ort_R']:+.2f} R (güven aralığının üstü "
                                      f"de sıfırın altında: {hi:+.2f} R); kazanma oranı %{r['kazanma_%']:.0f}. Öneri: bu "
                                      f"{what.lower()} için sinyaller durdurulsun ya da kuralı gözden geçirilsin."),
                            "nerede": "entries.py / tradeplan.py" if key == "senaryo" else "haber kaynağı ağırlığı (report.py)",
                            "kanit": r})
    cov = coverage(conn)
    hits = sum(1 for c in cov if c["pay"] >= COVERAGE_SHARE)
    if len(cov) >= COVERAGE_RUNS[1] and hits >= COVERAGE_RUNS[0]:
        avg = sum(c["pay"] for c in cov) / len(cov)
        sug.append({"anahtar": "kapsam:analiz_bekleyen", "tur": "ayar",
                    "baslik": "Haberlerin çoğu analiz edilmeden karar veriliyor",
                    "metin": (f"Son {len(cov)} çalıştırmanın {hits}'inde hisselerin %{100 * COVERAGE_SHARE:.0f}'ından "
                              f"fazlası 'haber analiz bekliyor' nedeniyle değerlendirilemedi (ortalama %{100 * avg:.0f}). "
                              "Öneri: analiz sınırını artırmak ya da sabah analizinde yapay zekâ kutusunu açmak. "
                              "Maliyet artar; tahmini maliyet düğmenin yanında gösterilir."),
                    "nerede": FILTER_CODES["HABER_ANALIZ_BEKLIYOR"][2], "kanit": {"calistirmalar": cov}})
    rep = repeated(conn, today)
    if len(rep["eslesme_hisse"]) >= REPEAT_MATCH:
        sug.append({"anahtar": "eslesme:takma_ad", "tur": "kod", "baslik": "Haber–şirket eşleştirmesi kaçıyor",
                    "metin": (f"Son {RECENT_DAYS} günde {len(rep['eslesme_hisse'])} hissede ({', '.join(rep['eslesme_hisse'][:8])})"
                              " başlıkta hisse kodu geçen haber bu hisseyle eşleştirilmemiş ve hisse sonra ciddi "
                              "yükselmiş. Öneri: şirket eşleştirme / takma adlar listesi gözden geçirilsin."),
                    "nerede": "data/aliases.csv ve eşleştirme kodu (universe.py)", "kanit": rep})
    late = rep["son_etiket"].get("HABER_SONRA", 0)
    if late >= REPEAT_LATE_NEWS:
        sug.append({"anahtar": "haber_sonra:siklik", "tur": "bilgi", "baslik": "Hareketler çoğu zaman karardan sonra gelen haberle başlıyor",
                    "metin": (f"Son {RECENT_DAYS} günde {late} kaçırılan fırsatta haber karar anından sonra geldi (o an "
                              "bilinemezdi). Öneri: gün içinde 'Haberleri güncelle' daha sık kullanılabilir."),
                    "nerede": "kullanım alışkanlığı (ayar değil)", "kanit": {"sayi": late}})
    return sug


def sync(conn, today: Optional[date] = None) -> Dict:
    """Yeni önerileri kaydeder (aynı öneri beklerken ya da 30 gün içinde karar verildiyse tekrar eklenmez)."""
    today = today or datetime.now(config.TR_TZ).date()
    now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
    cutoff = (today - timedelta(days=RESUGGEST_DAYS)).isoformat()
    added = []
    with conn:
        for s in generate(conn, today):
            dup = conn.execute("SELECT 1 FROM suggestions WHERE anahtar=? AND (durum='bekliyor' OR karar_ani>=?)",
                               (s["anahtar"], cutoff)).fetchone()
            if dup:
                continue
            cur = conn.execute("INSERT INTO suggestions(anahtar,tur,baslik,metin,kanit_json,nerede,olusturma) "
                               "VALUES(?,?,?,?,?,?,?)", (s["anahtar"], s["tur"], s["baslik"], s["metin"],
                                                          json.dumps(s["kanit"], ensure_ascii=False, default=str),
                                                          s.get("nerede"), now))
            added.append(cur.lastrowid)
    return {"eklenen": added, "bekleyen": pending(conn)}


def pending(conn) -> List[Dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM suggestions WHERE durum='bekliyor' ORDER BY id")]


def decided(conn, limit: int = 50) -> List[Dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM suggestions WHERE durum!='bekliyor' ORDER BY karar_ani DESC "
                                          "LIMIT ?", (limit,))]


def decide(conn, sid: int, durum: str, note: str = "") -> bool:
    """Kullanıcının kararı: onaylandı | reddedildi. Yalnız kayıt; hiçbir ayar değişmez."""
    if durum not in ("onaylandı", "reddedildi"):
        raise ValueError("Geçersiz karar")
    with conn:
        cur = conn.execute("UPDATE suggestions SET durum=?, karar_ani=?, karar_notu=? WHERE id=? AND durum='bekliyor'",
                           (durum, datetime.now(config.TR_TZ).isoformat(timespec="seconds"), note.strip() or None, sid))
    return cur.rowcount == 1


def _f(v, f="{:.2f}"):
    return "—" if v is None else f.format(v)


def summary_md(conn, today: date) -> str:
    """Akşam raporu bölüm 10'a eklenen gelişim özeti."""
    p = performance(conn)
    t = p["toplam"]
    s = "\n**Gelişim takibi (geçmişle karşılaştırma):**\n"
    if t["n"]:
        s += (f"- Kapanan sanal işlem: {t['n']}, kazanma %{_f(t['kazanma_%'], '{:.0f}')}, ortalama {_f(t['ort_R'])} R"
              + ("" if t["yeterli"] else f" — örnek az (< {MIN_TRADES}): karşılaştırma ve öneri için yetersiz") + "\n")
    else:
        s += "- Henüz kapanmış sanal işlem yok: strateji/kaynak karşılaştırması yapılamıyor.\n"
    if "karsilastirma" in p:
        a, b = p["karsilastirma"]["son"], p["karsilastirma"]["onceki"]
        s += (f"- Son {MIN_TRADES} işlem: {_f(a['ort_R'])} R / kazanma %{_f(a['kazanma_%'], '{:.0f}')} · önceki {MIN_TRADES}: "
              f"{_f(b['ort_R'])} R / %{_f(b['kazanma_%'], '{:.0f}')}\n")
    fr = filter_rates(conn, (today - timedelta(days=180)).isoformat())
    if fr["toplam_n"]:
        s += (f"- Kaçırılan fırsat oranı: %{_f(fr['genel_%'], '{:.1f}')} ({fr['gun']} karar günü, {fr['toplam_n']} hisse-gün, "
              f"{fr['toplam_k']} kaçırılan)"
              + (f"; en yüksek: {fr['satirlar'][0]['neden']} %{_f(fr['satirlar'][0]['oran_%'], '{:.1f}')} "
                 f"({fr['satirlar'][0]['degerlendirilen']} hisse-gün)" if fr["satirlar"] else "") + "\n")
    rep = repeated(conn, today)
    if rep["son_sayi"] or rep["onceki_sayi"]:
        s += f"- Kaçırılan (penceresi tamamlanan): son {RECENT_DAYS} gün {rep['son_sayi']}, önceki {RECENT_DAYS} gün {rep['onceki_sayi']}\n"
    pend = pending(conn)
    s += (f"- Onayınızı bekleyen öneri: **{len(pend)}** (🧭 Gelişim sekmesi)\n" if pend else
          "- Onay bekleyen öneri yok (öneri için yeterli örnek ve anlamlı fark gerekir).\n")
    return s
