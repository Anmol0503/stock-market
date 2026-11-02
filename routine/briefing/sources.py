"""Where the Morning Briefing looks. Feeds and APIs only, never article pages.

Each source has a one-line reason, so a future edit knows why it's there. Publishers that block Claude's
fetcher (Reuters, AP, BBC, The Hindu, …) are still read through their own RSS or Google News headlines,
which they publish for syndication. We never scrape around a block.
"""
from __future__ import annotations

import json
import urllib.parse

from . import config

import fetch_world  # noqa: E402  (config puts the repo root on sys.path)

# Feeds from the old pipeline we drop: Reddit (blocked from datacenter IPs; leads only anyway) and
# nitter (dead). Everything else in fetch_world.WORLD_FEEDS is kept.
_DROP_HOSTS = ("reddit.com", "nitter.net")
_DROP_NAMES = {"GPblog", "PlanetF1", "The Race F1", "Hacker News"}   # dead feeds (404) / HN RSS rate-limits; HN via API


def _gn_search(q: str, *, india: bool = False, days: int = 1) -> str:
    """Google News search RSS, restricted to the last `days` days."""
    loc = "hl=en-IN&gl=IN&ceid=IN:en" if india else "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(q)}+when:{days}d&{loc}"


# (category, feed name, url, why)
EXTRA_FEEDS: list[tuple[str, str, str, str]] = [
    ("geopolitics", "Reuters (Google News, 24h)", _gn_search("site:reuters.com"), "wire copy, the world's paper of record"),
    ("geopolitics", "AP (Google News, 24h)", _gn_search("site:apnews.com"), "wire copy, US + world"),
    ("india", "Reuters India (Google News, 24h)", _gn_search("site:reuters.com india", india=True), "wire view of India"),
    ("india", "BBC India", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml", "outside view of India"),
    ("geopolitics", "BBC Asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml", "neighbourhood: China, Pakistan, SE Asia"),
    ("geopolitics", "DW", "https://rss.dw.com/rdf/rss-en-all", "European view"),
    ("india", "Scroll", "https://scroll.in/feed", "Indian politics and policy depth"),
    ("india", "ThePrint", "https://theprint.in/feed/", "Indian politics, defence, governance"),
    ("india", "SEBI", "https://www.sebi.gov.in/sebirss.xml", "primary: market regulator orders and circulars"),
    ("technology", "Techmeme", "https://www.techmeme.com/feed.xml", "tech consensus (algorithm + editors)"),
    ("science", "Nature", "https://www.nature.com/nature.rss", "primary science news"),
    ("science", "Science", "https://www.science.org/rss/news_current.xml", "primary science news"),
    ("f1", "Formula1.com", "https://www.formula1.com/en/latest/all.xml", "official F1 news"),
    ("cricket", "BBC Cricket", "https://feeds.bbci.co.uk/sport/cricket/rss.xml", "international cricket"),
]

# Kagi News daily clusters (CC BY-NC): used ONLY as leads + a significance signal (unique_domains), never republished.
KAGI_BASE = "https://news.kagi.com/"
KAGI_CATEGORIES = {   # kagi file -> our section hint
    "world.json": "world", "india.json": "india", "asia.json": "world", "business.json": "markets",
    "economy.json": "markets", "tech.json": "tech_ai", "ai.json": "tech_ai", "science.json": "science",
    "formula_1.json": "f1",   # (no general sports file: it's football/NBA; cricket comes from feeds)
}

WIKI_API = "https://en.wikipedia.org/w/api.php"
JOLPICA = "https://api.jolpi.ca/ergast/f1"
HN_FRONT = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=40"

USER_AGENT = fetch_world.BROWSER_UA
API_AGENT = "MorningBriefing/1.0 (+https://github.com/Anmol0503/stock-market)"   # for Wikipedia/Jolpica


def feeds() -> list[tuple[str, str, str]]:
    """All RSS feeds as (category, name, url): the old list minus dead/blocked hosts, plus the extras."""
    out, seen = [], set()
    for cat, name, url in fetch_world.WORLD_FEEDS:
        if any(h in url for h in _DROP_HOSTS) or name in _DROP_NAMES:
            continue
        if "site:reuters.com" in url or "site:apnews.com" in url:   # replaced by the 24h versions above
            continue
        out.append((cat, name, url))
        seen.add(url)
    for cat, name, url, _why in EXTRA_FEEDS:
        if url not in seen:
            out.append((cat, name, url))
    return out


def beats() -> list[dict]:
    """Must-check beats (config/briefing_beats.json): each becomes a Google News query; empty ones get scouted."""
    path = config.CONFIG_DIR / "briefing_beats.json"
    data = json.loads(path.read_text())
    out = []
    for b in data["beats"]:
        out.append({**b, "url": _gn_search(b["query"], india=b.get("india", False), days=b.get("days", 1))})
    return out


# Publisher names for direct feeds (Google News items carry their own <source> element).
_PUBLISHER_PREFIXES = [
    ("BBC", "BBC"), ("Al Jazeera", "Al Jazeera"), ("Guardian", "The Guardian"), ("NPR", "NPR"),
    ("CNBC", "CNBC"), ("Ars Technica", "Ars Technica"), ("The Verge", "The Verge"), ("ScienceDaily", "ScienceDaily"),
    ("The Hindu", "The Hindu"), ("Times of India", "Times of India"), ("TOI", "Times of India"), ("NDTV", "NDTV"),
    ("Indian Express", "Indian Express"), ("Livemint", "Mint"), ("Business Standard", "Business Standard"),
    ("RBI", "RBI"), ("PIB", "PIB"), ("US Fed", "US Federal Reserve"), ("ECB", "ECB"), ("NYT", "New York Times"),
    ("Hacker News", "Hacker News"), ("ET Markets", "Economic Times"), ("Autosport", "Autosport"),
    ("Motorsport", "Motorsport.com"), ("The Race", "The Race"), ("PlanetF1", "PlanetF1"), ("RaceFans", "RaceFans"),
    ("GPblog", "GPblog"), ("ESPNcricinfo", "ESPNcricinfo"), ("DW", "DW"), ("Scroll", "Scroll"),
    ("ThePrint", "ThePrint"), ("SEBI", "SEBI"), ("Techmeme", "Techmeme"), ("Nature", "Nature"),
    ("Science", "Science"), ("Formula1.com", "Formula1.com"),
]

PRIMARY_PUBLISHERS = {"RBI", "PIB", "US Federal Reserve", "ECB", "SEBI"}


def publisher_for_feed(feed_name: str) -> str:
    for prefix, pub in _PUBLISHER_PREFIXES:
        if feed_name.startswith(prefix):
            return pub
    return feed_name
