"""Faz 3: skor eşiği ayarı için ÖN KAYITLI test (pilot olaylarıyla).

Kurallar veri görülmeden önce yazıldı (2026-11-06) ve sonuçlara bakılarak değiştirilmemeli:

1. Olay skoru = yön × etki (1–5) × güven (0–1). (Günlük skorun sönmesiz, tek olay karşılığı.)
2. Denenecek eşik ailesi sabittir: THRESHOLDS. Yeni eşik eklemek "sonuca bakıp seçme" olur.
3. Seçim vadesi 5 işlem günüdür (swing). 1/3/10 gün yalnızca bilgi için raporlanır.
4. Ölçüt: endekse göre net getiri (maliyet düşülmüş, XU100'e göre). Tavan/taban kilidi şüphesi olan
   satırlar seçimde kullanılmaz (işlem fiilen yapılamamış olabilir).
5. Zaman bölmesi: olaylar yayın zamanına göre sıralanır; ilk %60 geliştirme, son %40 doğrulama.
   Geliştirme olaylarından vadesi doğrulama döneminin ilk giriş gününe taşanlar atılır (ambargo).
6. Eşik YALNIZCA geliştirme döneminde seçilir: en az MIN_EVENTS olayı olan eşikler arasında ortalama
   getirisi en yüksek olan; eşitlikte daha yüksek (daha temkinli) eşik. Hiçbir eşik MIN_EVENTS'e
   ulaşmazsa eşik SEÇİLMEZ ("yetersiz veri").
7. Seçilen eşik doğrulama döneminde bir kez ölçülür ve raporlanır; doğrulamaya bakarak yeniden ayar yapılmaz.
8. Bu modül canlı eşikleri (report.THRESHOLDS) DEĞİŞTİRMEZ. Değişiklik ayrıca kullanıcı onayı gerektirir.
"""
import math
from statistics import mean, median
from typing import Dict, List, Optional

THRESHOLDS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
SELECTION_HORIZON = 5
REPORT_HORIZONS = (1, 3, 5, 10)
DEV_SHARE = 0.6
MIN_EVENTS = 20
METRIC = "endekse_göre_%"


def _usable(row) -> bool:
    return not row.get("eksik") and row.get(METRIC) is not None and not row.get("uygulanabilirlik")


def _stats(values: List[float], positive: bool = True) -> Dict[str, Optional[float]]:
    if not values:
        return {"olay": 0, "ortalama": None, "medyan": None, "isabet_%": None}
    hits = [v > 0 for v in values] if positive else [v < 0 for v in values]
    return {"olay": len(values), "ortalama": mean(values), "medyan": median(values),
            "isabet_%": 100 * sum(hits) / len(hits)}


def _event_scores(conn) -> Dict[tuple, dict]:
    out = {}
    for r in conn.execute("SELECT i.news_id, i.ticker, i.direction, i.magnitude, i.confidence, i.published_at "
                          "FROM impacts i JOIN pilot_selection s ON s.news_id=i.news_id"):
        out[(r["news_id"], r["ticker"])] = {"skor": r["direction"] * r["magnitude"] * r["confidence"],
                                             "yön": r["direction"], "yayın": r["published_at"]}
    return out


def calibrate(conn, results: List[dict]) -> dict:
    """results: backtest.evaluate(...) çıktısı. Canlı ayarlara dokunmaz; yalnızca rapor üretir."""
    scores = _event_scores(conn)
    events = sorted({(r["bildirim"], r["hisse"]) for r in results if (r["bildirim"], r["hisse"]) in scores},
                    key=lambda k: (scores[k]["yayın"], k))
    report = {"kurallar": {"eşikler": THRESHOLDS, "seçim_vadesi": SELECTION_HORIZON, "en_az_olay": MIN_EVENTS,
                           "geliştirme_payı": DEV_SHARE, "ölçüt": METRIC},
              "toplam_olay": len(events), "durum": "", "seçilen_eşik": None,
              "geliştirme": [], "doğrulama": None, "taban": {}}
    if len(events) < 2:
        report["durum"] = "yetersiz veri: ölçülebilir olay yok"
        return report
    cut = math.ceil(len(events) * DEV_SHARE)
    dev_keys, val_keys = set(events[:cut]), set(events[cut:])
    rows = [dict(r, **scores[(r["bildirim"], r["hisse"])]) for r in results
            if (r["bildirim"], r["hisse"]) in scores]
    val_entries = [r["giriş"] for r in rows if (r["bildirim"], r["hisse"]) in val_keys and r.get("giriş")]
    first_val_entry = min(val_entries) if val_entries else None
    report["geliştirme_olay"] = len(dev_keys)
    report["doğrulama_olay"] = len(val_keys)
    report["doğrulama_başlangıcı"] = first_val_entry

    def in_dev(r):
        # Ambargo: vadesi doğrulama dönemine taşan geliştirme sonucu kullanılmaz.
        return ((r["bildirim"], r["hisse"]) in dev_keys
                and (first_val_entry is None or (r.get("çıkış") or "") < first_val_entry))

    def subset(pred, horizon):
        return [r for r in rows if r["vade"] == horizon and _usable(r) and pred(r)]

    for h in REPORT_HORIZONS:
        report["taban"][h] = _stats([r[METRIC] for r in subset(in_dev, h)])  # tüm geliştirme olayları
    candidates = []
    for t in THRESHOLDS:
        line = {"eşik": t}
        for h in REPORT_HORIZONS:
            pos = [r[METRIC] for r in subset(lambda r: in_dev(r) and r["skor"] >= t, h)]
            neg = [r[METRIC] for r in subset(lambda r: in_dev(r) and r["skor"] <= -t, h)]
            line[f"pozitif_{h}g"] = _stats(pos)
            line[f"negatif_{h}g"] = _stats(neg, positive=False)
        report["geliştirme"].append(line)
        sel = line[f"pozitif_{SELECTION_HORIZON}g"]
        if sel["olay"] >= MIN_EVENTS:
            candidates.append((sel["ortalama"], t))
    if not candidates:
        best = max(line[f"pozitif_{SELECTION_HORIZON}g"]["olay"] for line in report["geliştirme"])
        report["durum"] = (f"yetersiz veri: geliştirme döneminde hiçbir eşikte en az {MIN_EVENTS} pozitif olay yok "
                           f"(en fazla {best}). Eşik seçilmedi; canlı eşikler değişmedi.")
        return report
    _, chosen = max(candidates, key=lambda c: (c[0], c[1]))
    report["seçilen_eşik"] = chosen
    val = {}
    for h in REPORT_HORIZONS:
        val[f"pozitif_{h}g"] = _stats([r[METRIC] for r in subset(
            lambda r: (r["bildirim"], r["hisse"]) in val_keys and r["skor"] >= chosen, h)])
        val[f"taban_{h}g"] = _stats([r[METRIC] for r in subset(
            lambda r: (r["bildirim"], r["hisse"]) in val_keys, h)])
    report["doğrulama"] = val
    vs = val[f"pozitif_{SELECTION_HORIZON}g"]
    report["durum"] = (f"eşik {chosen} geliştirme döneminde seçildi; doğrulamada {vs['olay']} olay. "
                       "Bu bir öneridir; canlı eşikler kullanıcı onayı olmadan değişmez.")
    return report


def _fmt(s: Dict[str, Optional[float]]) -> str:
    if not s or not s.get("olay"):
        return "olay yok"
    return (f"{s['olay']} olay · ortalama {s['ortalama']:+.2f}% · medyan {s['medyan']:+.2f}% · "
            f"isabet %{s['isabet_%']:.0f}")


def as_text(report: dict) -> str:
    """Programı kullanan kişinin okuyup geliştiriciye geri gönderebileceği sade rapor."""
    k = report["kurallar"]
    lines = [
        "HALLEY — SKOR EŞİĞİ AYARI (FAZ 3) · ÖN KAYITLI TEST",
        "",
        "Bu rapor geçmiş veri pilotundaki analiz edilmiş olaylardan üretilir. Canlı eşikleri DEĞİŞTİRMEZ.",
        f"Durum: {report['durum']}",
        "",
        f"Toplam ölçülebilir olay: {report['toplam_olay']} · geliştirme: {report.get('geliştirme_olay', 0)} · "
        f"doğrulama: {report.get('doğrulama_olay', 0)} (doğrulama başlangıcı: {report.get('doğrulama_başlangıcı') or '-'})",
        f"Kurallar: denenen eşikler {', '.join(str(t) for t in k['eşikler'])}; seçim {k['seçim_vadesi']} işlem günü "
        f"vadesinde; eşik başına en az {k['en_az_olay']} pozitif olay; ölçüt XU100'e göre net getiri (%0,20 maliyet "
        "düşülmüş); tavan/taban kilidi şüpheli satırlar hariç.",
        "Olay skoru = yön × etki (1–5) × güven (0–1). 'İsabet' pozitifte endeksi geçme, negatifte endeksin altında kalma oranıdır.",
        "",
        "GELİŞTİRME DÖNEMİ (eşik burada seçilir)",
    ]
    for h in REPORT_HORIZONS:
        lines.append(f"  Tüm olaylar, {h} gün: {_fmt(report['taban'].get(h))}")
    for line in report["geliştirme"]:
        lines.append(f"  Eşik {line['eşik']}:")
        for h in REPORT_HORIZONS:
            lines.append(f"    {h} gün · pozitif: {_fmt(line[f'pozitif_{h}g'])} | negatif: {_fmt(line[f'negatif_{h}g'])}")
    lines.append("")
    if report.get("doğrulama"):
        lines.append(f"DOĞRULAMA DÖNEMİ (seçilen eşik {report['seçilen_eşik']}, bir kez ölçülür)")
        for h in REPORT_HORIZONS:
            v = report["doğrulama"]
            lines.append(f"  {h} gün · seçilen eşik: {_fmt(v[f'pozitif_{h}g'])} | tüm olaylar: {_fmt(v[f'taban_{h}g'])}")
    else:
        lines.append("DOĞRULAMA DÖNEMİ: eşik seçilmediği için ölçülmedi.")
    lines += ["", "Bu sonuçlar istatistiksel kanıt veya yatırım tavsiyesi değildir. Aynı hisseye ait yakın olaylar ve "
              "örtüşen vadeler bağımsız gözlem sayılmaz. Rapor, geliştiriciye geri bildirim için ZIP içinde gönderilebilir."]
    return "\n".join(lines) + "\n"
