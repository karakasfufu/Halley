"""Sektör karşılaştırması ve portföy riski (D aşaması, 2026-11-09) — yalnız BİLGİ, kararları değiştirmez.

Kaynak: KAP Sektörler sayfası (bist_haber/sektorler.json; alındığı tarih ve SHA-256 doğrulaması dosyada).
Karşılaştırma grubu: hissenin KAP alt sektörü; alt sektörde kendisi hariç 3'ten az likit hisse varsa ana sektör.
Getiri: verilen günde ya da öncesindeki son kapanış ↔ n işlem günü önceki kapanış (geriye dönük bilgi yok).
Sıralama: hissenin getirisi gruptaki hisselerin yüzde kaçından yüksek (eşik/etiket uydurulmaz).
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple

LIQ_MIN_TL = 2e6
MIN_PEERS = 3
CORR_WARN = 0.7          # açık işlemler arası 60 günlük günlük getiri korelasyonu bu değerin üstündeyse uyarı
CONC_WARN = 0.5          # açık işlemlerin yarısı ya da fazlası tek ana sektördeyse (en az 3 işlem) uyarı


@lru_cache(maxsize=1)
def load() -> Dict:
    d = json.loads((Path(__file__).with_name("sektorler.json")).read_text(encoding="utf-8"))
    of, by_alt, by_ana = {}, {}, {}
    for key, ts in d["gruplar"].items():
        ana, alt = key.split("|", 1)
        for t in ts:
            of[t] = (ana, alt)
            by_alt.setdefault(alt, []).append(t)
            by_ana.setdefault(ana, []).append(t)
    return {"of": of, "alt": by_alt, "ana": by_ana, "kaynak": d["kaynak"], "alindi": d["alindi"]}


def sector_of(ticker: str) -> Optional[Tuple[str, str]]:
    return load()["of"].get(ticker)


_CACHE: Dict = {}


def _closes(conn, ticker: str, upto: str, n: int) -> List[Tuple[str, float, float]]:
    """Son n kapanış (eskiden yeniye). Aynı bağlantı + gün için 61 satır bir kez okunur (panel her hisseyi çizerken
    aynı sektördeki hisseleri tekrar tekrar okumasın)."""
    key = (id(conn), ticker, upto)
    rows = _CACHE.get(key)
    if rows is None:
        if len(_CACHE) > 20000:
            _CACHE.clear()
        rows = [(r[0], r[1], r[2]) for r in conn.execute(
            "SELECT date, close, COALESCE(volume,0) FROM prices WHERE ticker=? AND date<=? ORDER BY date DESC LIMIT 61",
            (ticker, upto))][::-1]
        _CACHE[key] = rows
    return rows[-n:] if n <= len(rows) else list(rows)


def clear_cache() -> None:
    _CACHE.clear()


def _liquid(rows) -> bool:
    last = rows[-20:]
    return bool(last) and sum(c * v for _, c, v in last) / len(last) >= LIQ_MIN_TL


def peers(conn, ticker: str, upto: str) -> Tuple[Optional[str], List[str]]:
    s = sector_of(ticker)
    if not s:
        return None, []
    data = load()
    for level, name in (("alt", s[1]), ("ana", s[0])):
        group = [t for t in data[level][name] if t != ticker and _liquid(_closes(conn, t, upto, 25))]
        if len(group) >= MIN_PEERS:
            return name, group
    return s[0], group


def _ret(conn, ticker: str, upto: str, n: int) -> Optional[float]:
    rows = _closes(conn, ticker, upto, n + 1)
    if len(rows) < n + 1 or not rows[0][1]:
        return None
    return (rows[-1][1] / rows[0][1] - 1) * 100


def compare(conn, ticker: str, day: Optional[date] = None) -> Dict:
    """Hissenin 5 ve 20 günlük getirisi ↔ karşılaştırma grubunun ortancası ve gruptaki sırası."""
    s = sector_of(ticker)
    if not s:
        return {"yok": "Bu hisse KAP sektör listesinde yok."}
    upto = (day or date.today()).isoformat()
    last = _closes(conn, ticker, upto, 1)
    if not last:
        return {"yok": "Fiyat yok."}
    upto = last[0][0]
    grp_name, grp = peers(conn, ticker, upto)
    out = {"ana": s[0], "alt": s[1], "grup": grp_name, "grup_hisse": len(grp), "gun": upto}
    for n in (5, 20):
        mine = _ret(conn, ticker, upto, n)
        others = [v for v in (_ret(conn, t, upto, n) for t in grp) if v is not None]
        out[f"hisse_{n}g"] = mine
        out[f"sektor_{n}g"] = median(others) if others else None
        out[f"yuzdelik_{n}g"] = (100 * sum(1 for v in others if v < mine) / len(others)
                                 if others and mine is not None else None)
        out[f"sira_{n}g"] = 1 + sum(1 for v in others if v > mine) if others and mine is not None else None
        out[f"toplam_{n}g"] = len(others) + 1 if others else None
    return out


def compare_text(c: Dict) -> str:
    if c.get("yok"):
        return c["yok"]
    parts = []
    for n in (5, 20):
        if c.get(f"hisse_{n}g") is None or c.get(f"sektor_{n}g") is None:
            continue
        parts.append(f"{n} gün: hisse %{c[f'hisse_{n}g']:+.1f}, sektör ortancası %{c[f'sektor_{n}g']:+.1f} "
                     f"({c[f'toplam_{n}g']} hisse içinde {c[f'sira_{n}g']}. sırada)")
    grp = c["grup"] if c["grup"] == c["alt"] else f"{c['grup']} (alt sektörde yeterli likit hisse yok)"
    return f"{c['ana']} › {c['alt']} · karşılaştırma: {grp}" + (" · " + " · ".join(parts) if parts else "")


def day_sectors(conn, day: Optional[date] = None) -> Dict:
    """Ana sektörlerin günlük değişim ortancası (likit hisseler; en az 3 hisse)."""
    upto = (day or date.today()).isoformat()
    d0 = conn.execute("SELECT MAX(date) FROM prices WHERE ticker='XU100' AND date<=?", (upto,)).fetchone()[0]
    if not d0:
        return {"gun": None, "sektorler": []}
    out = []
    for ana, ts in load()["ana"].items():
        vals = []
        for t in ts:
            rows = _closes(conn, t, d0, 21)
            if len(rows) >= 2 and rows[-1][0] == d0 and rows[-2][1] and _liquid(rows):
                vals.append((rows[-1][1] / rows[-2][1] - 1) * 100)
        if len(vals) >= MIN_PEERS:
            out.append({"sektor": ana, "degisim_%": median(vals), "hisse": len(vals)})
    out.sort(key=lambda x: -x["degisim_%"])
    return {"gun": d0, "sektorler": out}


def _returns_series(conn, ticker: str, upto: str, n: int = 61) -> Dict[str, float]:
    rows = _closes(conn, ticker, upto, n)
    return {rows[i][0]: rows[i][1] / rows[i - 1][1] - 1 for i in range(1, len(rows)) if rows[i - 1][1]}


def _corr(a: Dict[str, float], b: Dict[str, float]) -> Optional[float]:
    keys = sorted(set(a) & set(b))
    if len(keys) < 30:
        return None
    x, y = [a[k] for k in keys], [b[k] for k in keys]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sx = sum((v - mx) ** 2 for v in x) ** 0.5
    sy = sum((v - my) ** 2 for v in y) ** 0.5
    return sum((p - mx) * (q - my) for p, q in zip(x, y)) / (sx * sy) if sx and sy else None


def portfolio(conn, day: Optional[date] = None, kaynak: Optional[str] = None) -> Dict:
    """Açık/bekleyen işlemlerin sektör dağılımı ve birlikte hareket riski (60 günlük günlük getiri korelasyonu)."""
    upto = (day or date.today()).isoformat()
    q = "SELECT DISTINCT ticker FROM trade_journal WHERE durum IN ('bekliyor','açık','açık (TP1 görüldü)')"
    args = ()
    if kaynak:
        q += " AND kaynak=?"
        args = (kaynak,)
    tickers = sorted(r[0] for r in conn.execute(q, args))
    by_ana, by_alt = {}, {}
    for t in tickers:
        s = sector_of(t) or ("bilinmiyor", "bilinmiyor")
        by_ana.setdefault(s[0], []).append(t)
        by_alt.setdefault(s[1], []).append(t)
    series = {t: _returns_series(conn, t, upto) for t in tickers}
    pairs = []
    for i, a in enumerate(tickers):
        for b in tickers[i + 1:]:
            c = _corr(series[a], series[b])
            if c is not None:
                pairs.append({"a": a, "b": b, "korelasyon": c})
    warns = []
    for alt, ts in by_alt.items():
        if len(ts) >= 2 and alt != "bilinmiyor":
            warns.append(f"Aynı alt sektörde {len(ts)} işlem: {alt} ({', '.join(ts)}) — sektör haberi hepsini birlikte etkiler.")
    if len(tickers) >= 3:
        for ana, ts in by_ana.items():
            if len(ts) / len(tickers) >= CONC_WARN and ana != "bilinmiyor":
                warns.append(f"Tek ana sektörde yoğunlaşma: {ana} — {len(tickers)} açık işlemden {len(ts)} tanesi "
                             f"(%{100 * len(ts) / len(tickers):.0f}; {', '.join(ts)}).")
    for p in pairs:
        if p["korelasyon"] >= CORR_WARN:
            warns.append(f"{p['a']} ile {p['b']} son 60 günde birlikte hareket ediyor (korelasyon {p['korelasyon']:.2f}): "
                         "ikisi aynı risk gibi düşünülmeli.")
    return {"hisse": tickers, "ana": by_ana, "alt": by_alt, "ciftler": pairs, "uyarilar": warns}
