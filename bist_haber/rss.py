"""Ekonomi haber sitelerinin RSS akışlarını toplar (Dipnot 3: hisse eşleme)."""
import calendar
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict

import feedparser
import requests

from . import config
from .textutil import effective_date, html_to_text, title_key, tr_lower
from .universe import Matcher


def collect(conn, matcher: Matcher) -> Dict[str, int]:
    stats = {"seen": 0, "new": 0, "duplicate": 0, "skipped": 0, "failed_feeds": 0}
    now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
    for name, url in config.RSS_FEEDS.items():
        try:
            r = requests.get(url, headers=config.HTTP_HEADERS, timeout=30)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
        except requests.RequestException as e:
            print(f"[uyarı] {name} akışı okunamadı: {e}")
            stats["failed_feeds"] += 1
            continue
        for e in feed.entries:
            stats["seen"] += 1
            link = e.get("link") or ""
            title = (e.get("title") or "").strip()
            if not link or not title:
                continue
            news_id = "rss:" + hashlib.sha1(link.encode()).hexdigest()[:16]
            if conn.execute("SELECT 1 FROM news WHERE id=?", (news_id,)).fetchone():
                continue
            key = title_key(title)
            if conn.execute("SELECT 1 FROM news WHERE title_key=?", (key,)).fetchone():
                stats["duplicate"] += 1
                continue
            ts = e.get("published_parsed") or e.get("updated_parsed")
            published = (datetime.fromtimestamp(calendar.timegm(ts), tz=timezone.utc)
                         if ts else datetime.now(timezone.utc)).astimezone(config.TR_TZ)
            body = html_to_text(e.get("summary") or "")
            text = f"{title}\n{body}"
            candidates = matcher.find(text)
            status, note = "new", None
            if datetime.now(config.TR_TZ) - published > timedelta(days=config.RSS_MAX_AGE_DAYS):
                status, note = "skipped", "eski haber"
                stats["skipped"] += 1
            elif not candidates and not any(k in tr_lower(text) for k in config.RSS_MARKET_KEYWORDS):
                status, note = "skipped", "hisse/borsa ilgisi yok"
                stats["skipped"] += 1
            conn.execute(
                "INSERT INTO news(id,source,published_at,effective_date,title,title_key,body,url,candidates,status,note,fetched_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (news_id, f"rss:{name}", published.isoformat(), effective_date(published), title, key,
                 body, link, ",".join(candidates), status, note, now),
            )
            stats["new"] += 1
        conn.commit()
    return stats
