"""Fiyat/hacim ve şirket büyüklüğü verisi (yfinance, gecikmeli; sadece prototip için)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Iterable

import pandas as pd
import yfinance as yf

from . import config


def update(conn, tickers: Iterable[str], period: str = "1y") -> int:
    """Günlük açılış/en yüksek/en düşük/kapanış ve hacim. Teknik analiz için 1 yıl (200 gün ortalaması,
    52 haftalık zirve/dip) indirilir; ücretsizdir, yapay zekâ kullanmaz."""
    tickers = sorted(set(tickers))
    if not tickers:
        return 0
    df = yf.download([t + ".IS" for t in tickers], period=period, interval="1d",
                     auto_adjust=True, progress=False, group_by="ticker", threads=False)
    rows = 0

    def num(rec, col):
        v = rec.get(col)
        return None if v is None or pd.isna(v) else float(v)

    for t in tickers:
        sym = t + ".IS"
        if isinstance(df.columns, pd.MultiIndex):
            if sym not in df.columns.get_level_values(0):
                continue
            sub = df[sym]
        else:
            sub = df
        sub = sub.dropna(subset=["Close"])
        for idx, rec in sub.iterrows():
            conn.execute("INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
                         (t, idx.date().isoformat(), num(rec, "Open"), num(rec, "High"), num(rec, "Low"),
                          float(rec["Close"]), float(rec.get("Volume", 0) or 0)))
            rows += 1
    conn.commit()
    return rows


def _fetch_stats(ticker: str):
    try:
        fi = yf.Ticker(ticker + ".IS").fast_info
        return ticker, float(fi["marketCap"]), float(fi["lastPrice"])
    except Exception:
        return ticker, None, None


def company_stats(conn, tickers: Iterable[str]) -> Dict[str, dict]:
    """{ticker: {market_cap, last_price}}; günde bir kez çekilir, veritabanında önbelleklenir.

    Yapay zekâ bir tutarın (sözleşme, pay alımı) şirkete göre büyük mü küçük mü olduğunu
    tahmin etmek yerine bilsin diye kullanılır.
    """
    tickers = sorted(set(t for t in tickers if t))
    today = datetime.now(config.TR_TZ).date().isoformat()
    have = {r["ticker"]: r for r in conn.execute(
        f"SELECT * FROM company_stats WHERE date=? AND ticker IN ({','.join('?' * len(tickers))})",
        [today, *tickers])} if tickers else {}
    missing = [t for t in tickers if t not in have]
    if missing:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for t, cap, price in ex.map(_fetch_stats, missing):
                conn.execute("INSERT OR REPLACE INTO company_stats(ticker,date,market_cap,last_price) VALUES(?,?,?,?)",
                             (t, today, cap, price))
        conn.commit()
        have = {r["ticker"]: r for r in conn.execute(
            f"SELECT * FROM company_stats WHERE date=? AND ticker IN ({','.join('?' * len(tickers))})",
            [today, *tickers])}
    return {t: {"market_cap": r["market_cap"], "last_price": r["last_price"]} for t, r in have.items()}


NO_DATA_RETRY_DAYS = 7


def update_universe(conn, tickers: Iterable[str], progress=None, batch: int = 100) -> Dict[str, int]:
    """Tüm evrenin günlük OHLCV fiyatı (bekçi: tarama ve kaçırılan fırsatlar). Yapay zekâ yok, ücretsiz.
    Son 40 günde fiyatı olan hisse için yalnız son 1 ay indirilir (artımlı), olmayan için 1 yıl."""
    import json
    from datetime import timedelta
    tickers = sorted(set(t for t in tickers if t))
    today = datetime.now(config.TR_TZ).date()
    recent = (today - timedelta(days=40)).isoformat()
    have = {r[0] for r in conn.execute("SELECT ticker FROM prices GROUP BY ticker HAVING MAX(date)>=?", (recent,))}
    # Yahoo'da hiç fiyatı olmayanlar (çoğu borsada işlem görmeyen KAP şirketi: faktoring, varlık kiralama...)
    # her sabah boşuna 1 yıllık indirme denenmesin: NO_DATA_RETRY_DAYS günde bir yeniden denenir.
    nd_file = config.DATA / "fiyat_yok.json"
    try:
        no_data = json.loads(nd_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        no_data = {}
    cutoff = (today - timedelta(days=NO_DATA_RETRY_DAYS)).isoformat()
    skipped = sorted(t for t in tickers if t not in have and no_data.get(t, "") > cutoff)
    groups = [("1mo", [t for t in tickers if t in have]),
              ("1y", [t for t in tickers if t not in have and t not in skipped])]
    total = sum(len(g) for _, g in groups)
    done, rows, failed = 0, 0, 0
    for period, group in groups:
        for i in range(0, len(group), batch):
            part = group[i:i + batch]
            try:
                rows += update(conn, part, period=period)
            except Exception:  # bir parti başarısızsa diğerleri sürsün
                failed += len(part)
            done += len(part)
            if progress:
                progress(done, total)
    # 2026-11-09: piyasa rejimindeki BIST 100 EMA200'ü 1 yıllık geçmişte başlangıç değerine duyarlı (251 günde SMA ve
    # ilk değer başlangıcı arasında %0,6 fark ölçüldü) → endeksin geçmişi 600 günden kısaysa bir kez 3 yıl indirilir.
    if "XU100" in tickers and conn.execute("SELECT COUNT(*) FROM prices WHERE ticker='XU100'").fetchone()[0] < 600:
        try:
            rows += update(conn, ["XU100"], period="3y")
        except Exception:
            pass
    last = dict(conn.execute("SELECT ticker, MAX(date) FROM prices WHERE ticker IN (%s) GROUP BY ticker"
                             % ",".join("?" * len(tickers)), tickers).fetchall()) if tickers else {}
    newest = max(last.values()) if last else None
    missing = sorted(t for t in tickers if t not in last)            # hiç fiyatı yok
    behind = sorted(t for t in tickers if t in last and last[t] != newest)   # fiyatı var ama son günü içermiyor
    tried = set(groups[1][1])
    for t in missing:
        if t in tried:
            no_data[t] = today.isoformat()
    for t in list(no_data):
        if t in last:
            no_data.pop(t)
    try:
        config.DATA.mkdir(parents=True, exist_ok=True)
        nd_file.write_text(json.dumps(no_data, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
    return {"hisse": total, "satir": rows, "basarisiz": failed, "artimli": len(groups[0][1]), "tam": len(groups[1][1]),
            "son_gun": newest, "geride": behind, "fiyati_yok": missing, "atlanan": len(skipped)}
