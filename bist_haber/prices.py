"""Fiyat/hacim ve şirket büyüklüğü verisi (yfinance, gecikmeli; sadece prototip için)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Iterable

import pandas as pd
import yfinance as yf

from . import config


def update(conn, tickers: Iterable[str], period: str = "3mo") -> int:
    tickers = sorted(set(tickers))
    if not tickers:
        return 0
    df = yf.download([t + ".IS" for t in tickers], period=period, interval="1d",
                     auto_adjust=True, progress=False, group_by="ticker", threads=False)
    rows = 0
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
            conn.execute("INSERT OR REPLACE INTO prices(ticker,date,close,volume) VALUES(?,?,?,?)",
                         (t, idx.date().isoformat(), float(rec["Close"]), float(rec.get("Volume", 0) or 0)))
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
