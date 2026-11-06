"""Ekonomi haber sitelerinin RSS akışlarını toplar (Dipnot 3: hisse eşleme)."""
import calendar
import hashlib
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Dict

import feedparser
import requests

from . import config
from .textutil import effective_date, html_to_text, title_key, tr_lower
from .universe import Matcher


def article_published(url):
    """Yayın saatini yalnızca sayfanın açık saat dilimli yayın meta alanından alır."""
    class PublicationMeta(HTMLParser):
        def __init__(self):
            super().__init__()
            self.values = set()

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            name = (attributes.get("name") or attributes.get("property") or "").lower()
            if tag == "meta" and name in ("datepublished", "article:published_time"):
                raw = attributes.get("content", "")
                try:
                    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if value.tzinfo is not None:
                        self.values.add(value.astimezone(config.TR_TZ))
                except ValueError:
                    pass
    try:
        response = requests.get(url, headers=config.HTTP_HEADERS, timeout=20)
        response.raise_for_status()
        parser = PublicationMeta()
        parser.feed(response.text)
        return next(iter(parser.values)) if len(parser.values) == 1 else None
    except (requests.RequestException, ValueError):
        return None


def collect(conn, matcher: Matcher) -> Dict[str, object]:
    stats = {"seen": 0, "new": 0, "duplicate": 0, "skipped": 0, "failed_feeds": 0,
             "undated": 0, "future_dated": 0, "sources": {}}
    now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
    for name, url in config.RSS_FEEDS.items():
        source = {"state": "ok", "seen": 0, "new": 0, "undated": 0, "future_dated": 0, "error": ""}
        stats["sources"][name] = source
        try:
            r = requests.get(url, headers=config.HTTP_HEADERS, timeout=30)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
            if not feed.get("version") and not feed.entries:
                raise ValueError("Adres haber akışı yerine boş veya geçersiz içerik döndürdü.")
            if not feed.entries:
                source["state"] = "empty"
        except (requests.RequestException, ValueError) as e:
            print(f"[uyarı] {name} akışı okunamadı: {e}")
            stats["failed_feeds"] += 1
            source.update(state="error", error=str(e)[:200])
            continue
        for e in feed.entries:
            stats["seen"] += 1
            source["seen"] += 1
            link = e.get("link") or ""
            title = (e.get("title") or "").strip()
            if not link or not title:
                continue
            news_id = "rss:" + hashlib.sha1(link.encode()).hexdigest()[:16]
            if conn.execute("SELECT 1 FROM news WHERE id=?", (news_id,)).fetchone():
                stats["duplicate"] += 1
                continue
            key = title_key(title)
            if conn.execute("SELECT 1 FROM news WHERE title_key=?", (key,)).fetchone():
                stats["duplicate"] += 1
                continue
            ts = e.get("published_parsed") or e.get("updated_parsed")
            if ts is None:
                stats["undated"] += 1
                source["undated"] += 1
                continue  # bilinmeyen yayın tarihine bugünün tarihini uydurma
            published = datetime.fromtimestamp(calendar.timegm(ts), tz=timezone.utc).astimezone(config.TR_TZ)
            if name == "uzmanpara":
                # Gerçek akışta yerel saatler GMT etiketiyle sunulabiliyor. Sabit 3 saat
                # çıkarmak yerine yayın sayfasının açık saat dilimini doğrula.
                verified = article_published(link)
                if verified is None:
                    stats["undated"] += 1
                    source["undated"] += 1
                    continue
                published = verified
            if published > datetime.now(config.TR_TZ) + timedelta(minutes=5):
                stats["future_dated"] += 1
                source["future_dated"] += 1
                continue
            body = html_to_text(e.get("summary") or "")
            content = "\n".join(html_to_text(c.get("value") or "") for c in e.get("content", []))
            if len(content) > len(body):
                body = content
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
                 body or title, link, ",".join(candidates), status, note, now),
            )
            stats["new"] += 1
            source["new"] += 1
        conn.commit()
    return stats
