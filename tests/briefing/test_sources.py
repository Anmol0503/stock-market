"""Gathering, Wikipedia parsing and clustering: pure code, no network."""
from __future__ import annotations

import datetime as dt

from routine.briefing import cluster, config, gather, sources, wiki

from .conftest import NOW, iso

WIKITEXT = """{{Current events|year=2026|month=11|day=1|top=yes}}
'''Armed conflicts and attacks'''
*[[Gaza war]]
**[[Israeli bombing of the Gaza Strip]]
***Five [[Palestinian Civil Police Force (Hamas)|civil police officers]] are killed in an [[Israel]]i [[airstrike]] in [[Rafah]]. [https://www.aljazeera.com/news/a (Al Jazeera)]
'''Health and environment'''
*[[Air pollution in Delhi]]
**The government of [[Delhi]] introduces stricter controls as [[PM2.5|PM{{sub|2.5}}]] levels reach 201. [https://example.com/b (AFP via ''The Manila Times'')]
"""

GN_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>RBI keeps repo rate unchanged at 5.5% - The Hindu</title><link>https://news.google.com/rss/articles/x</link>
<pubDate>Mon, 02 Nov 2026 20:00:00 GMT</pubDate><source url="https://www.thehindu.com">The Hindu</source></item>
</channel></rss>"""


def test_wiki_parse_events_categories_topics_and_links():
    ev = wiki.parse(WIKITEXT, "2026-11-01")
    assert len(ev) == 2
    assert ev[0]["category"] == "Armed conflicts and attacks"
    assert ev[0]["topic"] == "Gaza war › Israeli bombing of the Gaza Strip"
    assert ev[0]["text"].startswith("Five civil police officers are killed in an Israeli airstrike")
    assert ev[0]["urls"] == [{"url": "https://www.aljazeera.com/news/a", "source": "Al Jazeera"}]
    assert "PM2.5" in ev[1]["text"] and ev[1]["urls"][0]["source"] == "AFP via The Manila Times"


def test_google_news_publisher_and_title_suffix(monkeypatch):
    class R:
        status_code, content = 200, GN_RSS
    monkeypatch.setattr(gather.requests, "get", lambda *a, **k: R())
    items, health = gather.fetch_feed("india", "Google News — India top", "https://news.google.com/rss?x")
    assert health["ok"] and len(items) == 1
    assert items[0]["pub"] == "The Hindu"                       # publisher, not the feed label
    assert items[0]["title"] == "RBI keeps repo rate unchanged at 5.5%"
    assert items[0]["published"] == "2026-11-02T20:00:00+00:00"


def test_feed_failure_is_isolated(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError("slow")
    monkeypatch.setattr(gather.requests, "get", boom)
    items, health = gather.fetch_feed("india", "X", "https://x.example/rss")
    assert items == [] and not health["ok"] and "TimeoutError" in health["error"]


def test_window_edges():
    start, end = NOW - dt.timedelta(hours=26), NOW
    assert gather.in_window(iso(1), start, end)
    assert not gather.in_window(iso(30), start, end)
    assert not gather.in_window(None, start, end)


def test_feed_list_drops_dead_and_blocked_hosts():
    urls = [u for _, _, u in sources.feeds()]
    assert not any("reddit.com" in u or "nitter.net" in u for u in urls)
    assert any("site%3Areuters.com" in u and "when:1d" in u for u in urls)


def _raw(items, wiki_events=()):
    return {"date": "2026-11-03", "window": {"start": "x", "end": "y"}, "items": items,
            "wiki_events": list(wiki_events), "markets": {"quotes": []}, "sport": {}, "beats": [], "source_health": []}


def _item(title, pub, cat="geopolitics", hours=2, beat=None):
    return {"title": title, "url": f"https://{pub.lower().replace(' ', '')}.com/{abs(hash(title)) % 999}",
            "summary": "", "published": iso(hours), "pub": pub, "via": pub, "category": cat, "kind": "rss", "beat": beat}


def test_cluster_counts_distinct_publishers_and_merges_same_story():
    leads = cluster.build(_raw([
        _item("Binance hacked for $6.3 billion in record crypto theft", "Reuters"),
        _item("Record $6.3 billion crypto theft hits Binance exchange", "BBC"),
        _item("Binance hacked: $6.3 billion stolen in record theft", "Reuters"),     # same publisher again
        _item("Delhi air quality turns severe as GRAP stage 3 begins", "The Hindu", cat="india", beat="weather"),
    ]))
    top = leads["clusters"][0]
    assert "Binance" in top["title"] and top["publishers"] == 2      # Reuters counted once
    delhi = next(c for c in leads["clusters"] if "Delhi" in c["title"])
    assert delhi["signals"]["beats"] == ["weather"] and delhi["section_hint"] == "india"


def test_wiki_event_attaches_or_stands_alone():
    ev = wiki.parse(WIKITEXT, "2026-11-01")
    leads = cluster.build(_raw([_item("Delhi introduces stricter pollution controls as PM2.5 levels reach 201", "NDTV",
                                      cat="india")], ev))
    delhi = next(c for c in leads["clusters"] if "Delhi" in c["title"])
    assert delhi["signals"]["wiki"] == ["Health and environment"]
    gaza = next(c for c in leads["clusters"] if "airstrike" in c["title"])
    assert gaza["members"][0]["url"] == "https://www.aljazeera.com/news/a"


def test_edition_date_is_ist_not_utc():
    late_utc = dt.datetime(2026, 11, 2, 22, 35, tzinfo=config.UTC)       # = 04:05 IST on 3 Nov
    assert config.edition_date(late_utc) == "2026-11-03"
    assert config.deadline_for(late_utc.astimezone(config.IST)).strftime("%H:%M") == "05:40"
