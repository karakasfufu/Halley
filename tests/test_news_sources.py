import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import patch
from xml.sax.saxutils import escape

from bist_haber import config, db, pipeline, rss
from bist_haber.universe import Matcher


def feed(title="TEST yeni sözleşme imzaladı", url="https://example.test/1", published=True, age=0):
    date = datetime.now(timezone.utc) - timedelta(days=age)
    pub = "<pubDate>{}</pubDate>".format(format_datetime(date)) if published else ""
    raw = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" '
           'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>Haber</title>'
           '<item><title>{}</title><link>{}</link>{}<description>Özet</description>'
           '<content:encoded><![CDATA[<p>Ayrıntılı şirket sözleşmesi metni.</p>]]></content:encoded>'
           '</item></channel></rss>').format(escape(title), escape(url), pub)
    return SimpleNamespace(content=raw.encode("utf-8"), raise_for_status=lambda: None)


class NewsSourceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(db.SCHEMA)
        self.addCleanup(self.conn.close)
        self.matcher = Matcher({"TEST": "Deneme"})
        dates = patch.object(rss, "article_published", return_value=datetime.now(config.TR_TZ))
        self.date_lookup = dates.start()
        self.addCleanup(dates.stop)
        self.feeds = {"bloomberght": config.RSS_FEEDS["bloomberght"], "uzmanpara": config.RSS_FEEDS["uzmanpara"]}

    def test_both_requested_sources_are_stored_and_richer_content_is_used(self):
        replies = [feed(), feed("TEST yeni yatırım açıkladı", "https://example.test/2")]
        with patch.object(config, "RSS_FEEDS", self.feeds), patch.object(rss.requests, "get", side_effect=replies):
            stats = rss.collect(self.conn, self.matcher)
        self.assertEqual(stats["new"], 2)
        self.assertEqual({r[0] for r in self.conn.execute("SELECT source FROM news")},
                         {"rss:bloomberght", "rss:uzmanpara"})
        self.assertTrue(all("Ayrıntılı" in r[0] for r in self.conn.execute("SELECT body FROM news")))
        self.assertEqual(stats["sources"]["uzmanpara"]["state"], "ok")

    def test_same_title_across_sources_is_not_inserted_twice(self):
        with patch.object(config, "RSS_FEEDS", self.feeds), \
                patch.object(rss.requests, "get", side_effect=[feed(), feed(url="https://another.test/2")]):
            stats = rss.collect(self.conn, self.matcher)
        self.assertEqual(stats["new"], 1)
        self.assertEqual(stats["duplicate"], 1)

    def test_unknown_publication_date_is_not_replaced_with_today(self):
        with patch.object(config, "RSS_FEEDS", {"uzmanpara": self.feeds["uzmanpara"]}), \
                patch.object(rss.requests, "get", return_value=feed(published=False)):
            stats = rss.collect(self.conn, self.matcher)
        self.assertEqual(stats["undated"], 1)
        self.assertEqual(stats["new"], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM news").fetchone()[0], 0)

    def test_old_news_are_stored_as_skipped_without_becoming_ready(self):
        self.date_lookup.return_value = datetime.now(config.TR_TZ) - timedelta(days=7)
        with patch.object(config, "RSS_FEEDS", {"uzmanpara": self.feeds["uzmanpara"]}), \
                patch.object(rss.requests, "get", return_value=feed(age=7)):
            stats = rss.collect(self.conn, self.matcher)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(self.conn.execute("SELECT status FROM news").fetchone()[0], "skipped")

    def test_html_response_is_reported_and_other_source_continues(self):
        html = SimpleNamespace(content=b"<html>Access denied</html>", raise_for_status=lambda: None)
        with patch.object(config, "RSS_FEEDS", self.feeds), \
                patch.object(rss.requests, "get", side_effect=[html, feed()]):
            stats = rss.collect(self.conn, self.matcher)
        self.assertEqual(stats["failed_feeds"], 1)
        self.assertEqual(stats["sources"]["bloomberght"]["state"], "error")
        self.assertEqual(stats["sources"]["uzmanpara"]["state"], "ok")
        self.assertEqual(stats["new"], 1)

    def test_future_date_is_not_processed_as_current_news(self):
        self.date_lookup.return_value = datetime.now(config.TR_TZ) + timedelta(days=1)
        with patch.object(config, "RSS_FEEDS", {"uzmanpara": self.feeds["uzmanpara"]}), \
                patch.object(rss.requests, "get", return_value=feed(age=-1)):
            stats = rss.collect(self.conn, self.matcher)
        self.assertEqual(stats["future_dated"], 1)
        self.assertEqual(stats["new"], 0)

    def test_unverified_uzmanpara_date_does_not_fall_back_to_wrong_gmt(self):
        self.date_lookup.return_value = None
        with patch.object(config, "RSS_FEEDS", {"uzmanpara": self.feeds["uzmanpara"]}), \
                patch.object(rss.requests, "get", return_value=feed()):
            stats = rss.collect(self.conn, self.matcher)
        self.assertEqual(stats["new"], 0)
        self.assertEqual(stats["undated"], 1)


    def test_live_update_passes_analysis_limit_without_real_api(self):
        with patch.object(pipeline, "universe", return_value={"TEST": "Deneme"}), \
                patch.object(pipeline.kap, "collect", return_value={}), \
                patch.object(pipeline.kap, "list_disclosures", return_value=[]), \
                patch.object(pipeline.kap, "fetch_missing_bodies", return_value={}), \
                patch.object(pipeline.rss, "collect", return_value={}), \
                patch.object(pipeline, "has_api_key", return_value=True), \
                patch.object(pipeline.analyzer, "analyze", return_value={"analyzed": 0}) as analyze, \
                patch.object(pipeline.analyzer, "pending", return_value=[]), \
                patch.object(pipeline.prices, "update", return_value=0):
            pipeline.update_all(self.conn, analysis_limit=3)
        self.assertEqual(analyze.call_args.kwargs["limit"], 3)

    def test_live_limit_cannot_be_silently_increased_above_ten(self):
        with patch.object(pipeline, "universe") as universe:
            with self.assertRaises(ValueError):
                pipeline.update_all(self.conn, analysis_limit=100)
        universe.assert_not_called()


class PublicationDateTests(unittest.TestCase):
    def test_explicit_timezone_is_kept_and_modified_time_is_ignored(self):
        page = ('<meta name="datePublished" content="2026-11-06T13:39:04+03:00">'
                '<meta name="dateModified" content="2026-11-06T15:00:00+03:00">')
        response = SimpleNamespace(text=page, raise_for_status=lambda: None)
        with patch.object(rss.requests, "get", return_value=response):
            published = rss.article_published("https://example.test/article")
        self.assertEqual(published.isoformat(), "2026-11-06T13:39:04+03:00")

    def test_missing_timezone_or_conflicting_publication_dates_are_not_guessed(self):
        pages = ['<meta name="datePublished" content="2026-11-06T13:39:04">',
                 '<meta name="datePublished" content="2026-11-06T13:39:04+03:00">'
                 '<meta property="article:published_time" content="2026-11-06T12:00:00+03:00">']
        for page in pages:
            with self.subTest(page=page), patch.object(rss.requests, "get", return_value=SimpleNamespace(
                    text=page, raise_for_status=lambda: None)):
                self.assertIsNone(rss.article_published("https://example.test/article"))


if __name__ == "__main__":
    unittest.main()
