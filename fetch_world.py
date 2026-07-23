#!/usr/bin/env python3
"""Pull broad WORLD news (not just markets) for the daily decoded brief.

This is the raw-material gatherer for the World pillar. It casts a wide net across
categories — geopolitics, economy/business, technology, science, health, climate/energy,
and India — using free RSS feeds (no API key), plus a best-effort GDELT pull for a global
pulse. The analyst (Claude, on your subscription) then reads this, cross-checks with
WebSearch, and writes the DECODED brief (what happened / why it matters / ripple effects /
why you're seeing it) to output/world-latest.json.

Writes:
    output/world-raw-<YYYY-MM-DD>.json   (dated archive)
    output/world-raw-latest.json         (what the analyst reads)

Everything here is free. Run:  python fetch_world.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import requests

try:
    import feedparser
except ImportError:
    feedparser = None

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

HTTP_TIMEOUT = 20
# A full browser UA — required by Reddit (generic "Mozilla/5.0" → 403) and accepted by the
# official feeds (PIB/RBI) that reject feedparser's default agent. One UA that works everywhere.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# Broad, reputable, free RSS across everything you "shouldn't miss".
# (category, source, url). Edit freely — breadth is the point.
WORLD_FEEDS = [
    # --- Geopolitics / world ---
    ("geopolitics", "BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("geopolitics", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("geopolitics", "Guardian World", "https://www.theguardian.com/world/rss"),
    ("geopolitics", "NPR World", "https://feeds.npr.org/1004/rss.xml"),
    # --- Economy / business / markets-adjacent ---
    ("economy", "BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ("economy", "Guardian Business", "https://www.theguardian.com/uk/business/rss"),
    ("economy", "CNBC Economy", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    # --- Technology / AI ---
    ("technology", "BBC Technology", "http://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("technology", "Ars Technica", "http://feeds.arstechnica.com/arstechnica/index"),
    ("technology", "The Verge", "https://www.theverge.com/rss/index.xml"),
    # --- Science ---
    ("science", "BBC Science & Environment", "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("science", "ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml"),
    # --- Health ---
    ("health", "BBC Health", "http://feeds.bbci.co.uk/news/health/rss.xml"),
    # --- Climate / energy ---
    ("climate", "Guardian Environment", "https://www.theguardian.com/environment/rss"),
    # --- India (national + business + world-view — the user lives here, so we cast a WIDE net) ---
    ("india", "The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("india", "The Hindu Business", "https://www.thehindu.com/business/feeder/default.rss"),
    ("india", "Times of India Top", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
    ("india", "NDTV Top Stories", "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("india", "Indian Express", "https://indianexpress.com/feed/"),
    ("india", "Livemint", "https://www.livemint.com/rss/news"),
    ("india", "Business Standard", "https://www.business-standard.com/rss/home_page_top_stories.rss"),
    ("india", "The Hindu Economy", "https://www.thehindu.com/business/Economy/feeder/default.rss"),
    ("india", "Livemint Markets", "https://www.livemint.com/rss/markets"),
    # --- Primary sources: the policy-makers themselves (press releases, no middleman) ---
    ("india", "RBI Press", "https://www.rbi.org.in/pressreleases_rss.xml"),
    ("india", "PIB (Govt of India)", "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"),
    ("economy", "US Fed Press", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("economy", "ECB Press", "https://www.ecb.europa.eu/rss/press.html"),
    # --- Wire copy + tech pulse ---
    ("geopolitics", "Reuters (via Google News)",
     "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en"),
    ("geopolitics", "AP (via Google News)",
     "https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en"),
    ("geopolitics", "NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("technology", "Hacker News", "https://news.ycombinator.com/rss"),
    ("technology", "Guardian Technology", "https://www.theguardian.com/technology/rss"),
    # --- More India depth (national + economy + markets) ---
    ("india", "Reuters India (via Google News)",
     "https://news.google.com/rss/search?q=site:reuters.com+india&hl=en-IN&gl=IN&ceid=IN:en"),
    ("india", "Livemint Economy", "https://www.livemint.com/rss/economy"),
    ("india", "ET Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),

    # === HIGH-VOLUME AGGREGATORS: Google News top + topic feeds (fresh, timestamped) ===
    # World / global
    ("geopolitics", "Google News — World", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
    ("geopolitics", "Google News — World topic",
     "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
    ("economy", "Google News — Business",
     "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("technology", "Google News — Technology",
     "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"),
    ("science", "Google News — Science",
     "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en"),
    ("health", "Google News — Health",
     "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=en-US&gl=US&ceid=US:en"),
    # India
    ("india", "Google News — India top", "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"),
    ("india", "Google News — India nation",
     "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-IN&gl=IN&ceid=IN:en"),
    ("india", "Google News — India business",
     "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en"),

    # === FORMULA 1 (its own tab — pull broadly, the analyst picks the most-trending) ===
    ("f1", "BBC Sport F1", "http://feeds.bbci.co.uk/sport/formula1/rss.xml"),
    ("f1", "Autosport F1", "https://www.autosport.com/rss/f1/news/"),
    ("f1", "Motorsport F1", "https://www.motorsport.com/rss/f1/news/"),
    ("f1", "The Race F1", "https://www.the-race.com/formula-1/feed/"),
    ("f1", "PlanetF1", "https://www.planetf1.com/feed"),
    ("f1", "RaceFans", "https://www.racefans.net/feed/"),
    ("f1", "GPblog", "https://www.gpblog.com/en/rss"),
    ("f1", "Google News — F1",
     "https://news.google.com/rss/search?q=Formula+1+F1+when:3d&hl=en-US&gl=US&ceid=US:en"),
    ("f1", "Google News — F1 driver market",
     "https://news.google.com/rss/search?q=F1+(Verstappen+OR+standings+OR+Grand+Prix)+when:3d&hl=en-US&gl=US&ceid=US:en"),
    ("f1", "Reddit r/formula1", "https://www.reddit.com/r/formula1/hot/.rss"),

    # === CRICKET (its own tab — global + India-heavy, the analyst picks the most-trending) ===
    ("cricket", "BBC Sport Cricket", "http://feeds.bbci.co.uk/sport/cricket/rss.xml"),
    ("cricket", "ESPNcricinfo", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml"),
    ("cricket", "The Hindu Cricket", "https://www.thehindu.com/sport/cricket/feeder/default.rss"),
    ("cricket", "TOI Cricket", "https://timesofindia.indiatimes.com/rssfeeds/54829575.cms"),
    ("cricket", "NDTV Cricket", "https://feeds.feedburner.com/ndtvsports-cricket"),
    ("cricket", "Cricbuzz (Google News)",
     "https://news.google.com/rss/search?q=site:cricbuzz.com+when:3d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("cricket", "Google News — Cricket",
     "https://news.google.com/rss/search?q=cricket+when:3d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("cricket", "Google News — Cricket intl",
     "https://news.google.com/rss/search?q=cricket+(Test+OR+ODI+OR+T20+OR+series)+when:3d&hl=en-US&gl=US&ceid=US:en"),
    ("cricket", "Reddit r/Cricket", "https://www.reddit.com/r/Cricket/hot/.rss"),

    # === REDDIT (per-subreddit .rss — the JSON API is 403-blocked, but RSS still serves) ===
    # These are LEADS to verify, not sources of record — the analyst confirms via WebSearch.
    ("geopolitics", "Reddit r/worldnews", "https://www.reddit.com/r/worldnews/hot/.rss"),
    ("geopolitics", "Reddit r/news", "https://www.reddit.com/r/news/hot/.rss"),
    ("geopolitics", "Reddit r/geopolitics", "https://www.reddit.com/r/geopolitics/hot/.rss"),
    ("economy", "Reddit r/Economics", "https://www.reddit.com/r/Economics/hot/.rss"),
    ("technology", "Reddit r/technology", "https://www.reddit.com/r/technology/hot/.rss"),
    ("india", "Reddit r/india", "https://www.reddit.com/r/india/hot/.rss"),
    ("india", "Reddit r/IndiaNews", "https://www.reddit.com/r/IndiaNews/hot/.rss"),
    ("india", "Reddit r/unitedstatesofindia", "https://www.reddit.com/r/unitedstatesofindia/hot/.rss"),

    # === TWITTER/X via nitter (BEST-EFFORT — nitter instances are flaky and may 403/die;
    #     wrapped per-feed so a dead instance never breaks the run. Breaking-news accounts only) ===
    ("geopolitics", "X · BBC Breaking", "https://nitter.net/BBCBreaking/rss"),
    ("geopolitics", "X · Reuters", "https://nitter.net/Reuters/rss"),
    ("geopolitics", "X · AP", "https://nitter.net/AP/rss"),
    ("india", "X · ANI", "https://nitter.net/ANI/rss"),
    ("india", "X · PTI", "https://nitter.net/PTI_News/rss"),
    ("india", "X · NDTV", "https://nitter.net/ndtv/rss"),
]

# GDELT: a global pulse of what the world's press is covering most right now.
# Best-effort; skipped silently if unavailable. A broad importance query keeps it general.
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = (
    '(crisis OR election OR war OR ceasefire OR "central bank" OR sanctions OR '
    'breakthrough OR summit OR outbreak OR tariffs) sourcelang:english'
)


def _looks_image(u: str) -> bool:
    import re
    return bool(re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", (u or "").lower()))


def _entry_image(entry) -> str | None:
    """Pull a lead image URL from a feed entry (media:content / media:thumbnail / enclosure).

    feedparser already parses these — we just never read them before. Returns the first plausible
    image URL, or None. Best-effort: never raise on a weird entry shape."""
    try:
        for mc in (entry.get("media_content") or []):
            u = mc.get("url")
            if u and (mc.get("medium") == "image" or str(mc.get("type", "")).startswith("image")
                      or _looks_image(u)):
                return u
        for mt in (entry.get("media_thumbnail") or []):
            if mt.get("url"):
                return mt["url"]
        for en in (entry.get("enclosures") or []):
            u = en.get("href") or en.get("url")
            if u and (str(en.get("type", "")).startswith("image") or _looks_image(u)):
                return u
        for ln in (entry.get("links") or []):
            if ln.get("rel") == "enclosure" and str(ln.get("type", "")).startswith("image") and ln.get("href"):
                return ln["href"]
    except Exception:  # noqa: BLE001 - media is a nice-to-have, never break ingestion
        pass
    return None


# Rough source-credibility tiers (1 = wire/established, 2 = other outlet, 3 = social/aggregator "lead only").
# Keyword-matched against the human source name so it works for the whole feed set without an exhaustive map.
_TIER1_KW = ("reuters", "associated press", "ap news", "afp", "bloomberg", "bbc", "guardian",
             "financial times", "wsj", "wall street journal", "new york times", "washington post",
             "npr", "al jazeera", "the hindu", "press trust", "espncricinfo", "autosport", "nature",
             "science", "economist", "cnbc", "cnn", "the race", "planetf1", "sky sport")
_TIER3_KW = ("reddit", "nitter", "twitter", "/r/", "gnews", "google news", "substack", "medium", "blog")


def _source_tier(source: str) -> int:
    s = (source or "").lower()
    if any(k in s for k in _TIER3_KW):
        return 3
    if any(k in s for k in _TIER1_KW):
        return 1
    return 2


def _sig(headline: str) -> set:
    import re
    _stop = {"the", "a", "an", "of", "to", "in", "on", "and", "for", "is", "are", "as", "at", "by",
             "with", "from", "its", "it", "after", "over", "amid", "says", "say", "new", "will",
             "has", "have", "was", "were", "be", "that", "this", "up", "out"}
    toks = re.findall(r"[a-z0-9]+", (headline or "").lower())
    return {t for t in toks if len(t) > 2 and t not in _stop}


def rss_world(per_feed: int = 12) -> list[dict]:
    if feedparser is None:
        print("  ! feedparser not installed; skipping RSS", file=sys.stderr)
        return []
    import socket
    socket.setdefaulttimeout(HTTP_TIMEOUT)   # bound a slow/hanging feed (esp. flaky nitter)
    items = []
    for category, source, url in WORLD_FEEDS:
        region = {"india": "india", "f1": "f1", "cricket": "cricket"}.get(category, "global")
        try:
            # A real browser UA matters: Reddit 403s a generic one, and PIB/RBI reject feedparser's default.
            feed = feedparser.parse(url, agent=BROWSER_UA)
            for entry in feed.entries[:per_feed]:
                summary = entry.get("summary", "") or entry.get("description", "")
                published = entry.get("published", entry.get("updated", ""))
                title = entry.get("title")
                if not title:
                    continue
                items.append({
                    "category": category,
                    "region": region,
                    "source": source,
                    "headline": title,
                    "url": entry.get("link"),
                    "summary": _clean(summary)[:400],
                    "published": published,
                    "published_iso": _parse_published(published),
                    "image": _entry_image(entry),   # lead image straight from the feed, if any
                })
        except Exception as e:  # noqa: BLE001 - never let one feed break the run
            print(f"  ! rss {source} failed: {e}", file=sys.stderr)
    return items


def gdelt_pulse(maxrecords: int = 40) -> list[dict]:
    try:
        r = requests.get(
            GDELT_URL,
            params={"query": GDELT_QUERY, "mode": "ArtList", "maxrecords": maxrecords,
                    "sort": "HybridRel", "timespan": "1d", "format": "json"},
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "stock-market-world-brief/1.0"},
        )
        if r.status_code != 200:
            print(f"  ! gdelt -> HTTP {r.status_code}", file=sys.stderr)
            return []
        arts = (r.json() or {}).get("articles", []) or []
        return [
            {"category": "gdelt", "source": a.get("domain"), "headline": a.get("title"),
             "url": a.get("url"), "published": a.get("seendate", ""),
             "published_iso": _parse_published(a.get("seendate", "")),
             "country": a.get("sourcecountry", "")}
            for a in arts
        ]
    except Exception as e:  # noqa: BLE001
        print(f"  ! gdelt failed: {e}", file=sys.stderr)
        return []


def _clean(text: str) -> str:
    """Strip HTML tags/entities that RSS summaries often carry."""
    import re
    import html as _html
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = _html.unescape(text)
    return " ".join(text.split())


def _parse_published(raw: str) -> str | None:
    """Normalize the wild mix of feed timestamps to UTC ISO-8601 (or None).

    Real formats seen in the data: RFC-2822 ("Wed, 01 Jul 2026 07:30:53 GMT",
    "... -0400", "... EDT"), ISO ("2026-06-30T14:14:05-04:00"), and GDELT's
    compact "20260701T093000Z". Naive results are assumed UTC.
    """
    if not raw:
        return None
    raw = raw.strip()
    parsed = None
    try:
        from email.utils import parsedate_to_datetime
        parsed = parsedate_to_datetime(raw)
    except Exception:  # noqa: BLE001
        pass
    if parsed is None:
        try:
            parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            pass
    if parsed is None:
        try:
            parsed = dt.datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        except Exception:  # noqa: BLE001
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _dedupe(items: list[dict]) -> list[dict]:
    """Collapse the same story across feeds, but KEEP the corroboration signal we used to throw away.

    Groups near-duplicate headlines (token-signature Jaccard ≥ 0.5), keeps one representative, and stamps
    it with how many DISTINCT outlets carried it (`corroboration`), which ones (`corroborating`), and the
    best source tier in the group (`tier`, 1 = wire). Also borrows an image from any group member if the
    representative lacks one. This many-outlets-agree count is the backbone of the credibility badge."""
    clusters: list[dict] = []   # {"rep", "sig", "sources": set, "members": []}
    for it in items:
        sig = _sig(it.get("headline"))
        best = None
        for cl in clusters:
            if sig and cl["sig"] and len(sig & cl["sig"]) / len(sig | cl["sig"]) >= 0.5:
                best = cl
                break
        if best is None:
            clusters.append({"rep": it, "sig": sig, "sources": {it.get("source")}, "members": [it]})
        else:
            best["sources"].add(it.get("source"))
            best["members"].append(it)

    out = []
    for cl in clusters:
        rep = cl["rep"]
        srcs = sorted({s for s in cl["sources"] if s})
        rep["corroboration"] = len(srcs)
        rep["corroborating"] = srcs[:12]
        rep["tier"] = min((_source_tier(s) for s in srcs), default=3)
        if not rep.get("image"):                     # borrow a picture from any outlet that had one
            for m in cl["members"]:
                if m.get("image"):
                    rep["image"] = m["image"]
                    break
        out.append(rep)
    return out


def main() -> None:
    # Compute per-run (NOT at import) so a long-lived server can call main() days later.
    today = dt.date.today()
    now_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    print("Fetching world news (free RSS across all categories)...")
    rss = _dedupe(rss_world())
    by_cat: dict[str, list] = {}
    for it in rss:
        by_cat.setdefault(it["category"], []).append(it)

    print("Fetching GDELT global pulse (best-effort)...")
    gdelt = _dedupe(gdelt_pulse())

    raw = {
        "date": today.isoformat(),
        "as_of": now_iso,
        "by_category": by_cat,
        "all_headlines": rss,
        "gdelt_pulse": gdelt,
        "sources": {
            "rss_feeds": [{"category": c, "source": s} for c, s, _ in WORLD_FEEDS],
            "gdelt": bool(gdelt),
        },
        "note": "Raw material. The analyst decodes the most important of these into output/world-latest.json.",
    }

    dated = OUT / f"world-raw-{today.isoformat()}.json"
    latest = OUT / "world-raw-latest.json"
    for path in (dated, latest):
        with open(path, "w") as f:
            json.dump(raw, f, indent=2, default=str)

    cats = ", ".join(f"{c}:{len(v)}" for c, v in by_cat.items())
    print(f"Done. {len(rss)} headlines ({cats}); {len(gdelt)} GDELT items.")
    print(f"Wrote {latest.relative_to(ROOT)} (and dated copy).")


if __name__ == "__main__":
    main()
