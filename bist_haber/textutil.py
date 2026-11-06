"""Türkçe metin ve zaman yardımcıları."""
import html
import re
from datetime import date, datetime, timedelta

from . import config


def tr_lower(s: str) -> str:
    """Türkçe kurallarına göre küçük harf (I→ı, İ→i)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def html_to_text(s: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</tr>|</div>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def title_key(title: str) -> str:
    """Farklı sitelerdeki aynı haberi yakalamak için normalize başlık."""
    return re.sub(r"[^0-9a-zçğıöşü]+", "", tr_lower(title))[:80]


def next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def effective_date(published: datetime) -> str:
    """Haberin en erken işlem görebileceği gün (Dipnot 7).

    Hafta içi seans kapanışından önce → aynı gün; sonra ya da hafta sonu → sonraki
    iş günü. Resmi tatiller henüz hesaba katılmıyor.
    """
    local = published.astimezone(config.TR_TZ)
    d = local.date()
    if d.weekday() >= 5 or local.hour >= config.SESSION_CLOSE_HOUR:
        return next_weekday(d).isoformat()
    return d.isoformat()
