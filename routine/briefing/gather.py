"""Stage 1: sweep every source for the news window. Pure code, no model calls.

Writes output/briefing/<date>/raw.json:
  {window, items[], wiki_events[], markets, sport, beats[], source_health[]}
Each item: {title, url, summary, published, pub, via, category, kind, beat?, kagi_domains?, hn_points?}
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import threading
import time

import requests

from . import config, markets, sources, sport, wiki

import fetch_world  # noqa: E402

try:
    import feedparser
except ImportError:  # pragma: no cover
    feedparser = None

_GN_SLOTS = threading.Semaphore(4)       # be gentle with Google News from one IP


def _gn_title(title: str, publisher: str) -> str:
    """Google News titles end with ' - Publisher'; strip it."""
    suffix = f" - {publisher}"
    return title[: -len(suffix)] if publisher and title.endswith(suffix) else title


def fetch_feed(category: str, name: str, url: str, *, kind: str = "rss", beat: str | None = None,
               per_feed: int = 30, timeout: int = 15) -> tuple[list[dict], dict]:
    """Fetch one RSS/Atom feed. Returns (items, health). Never raises."""
    t0 = time.monotonic()
    health = {"name": name, "kind": kind, "ok": False, "items": 0, "fresh": 0, "ms": 0, "error": None}
    is_gn = "news.google.com" in url
    try:
        if is_gn:
            _GN_SLOTS.acquire()
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": sources.USER_AGENT})
        finally:
            if is_gn:
                _GN_SLOTS.release()
        if r.status_code != 200:
            health["error"] = f"HTTP {r.status_code}"
            return [], health
        feed = feedparser.parse(r.content)
        items = []
        for e in feed.entries[:per_feed]:
            title = (e.get("title") or "").strip()
            link = e.get("link")
            if not title or not link:
                continue
            if is_gn:
                src = e.get("source") or {}
                pub = (src.get("title") if isinstance(src, dict) else None) or "Google News"
                title = _gn_title(title, pub)
                summary = ""                      # GN summaries just repeat the title
            else:
                pub = sources.publisher_for_feed(name)
                summary = fetch_world._clean(e.get("summary") or e.get("description") or "")[:300]
            items.append({
                "title": title, "url": link, "summary": summary,
                "published": fetch_world._parse_published(e.get("published") or e.get("updated") or ""),
                "pub": pub, "via": name, "category": category, "kind": kind, "beat": beat,
            })
        health.update(ok=True, items=len(items))
        return items, health
    except Exception as e:  # noqa: BLE001 - one feed must never break the run
        health["error"] = f"{type(e).__name__}: {e}"[:200]
        return [], health
    finally:
        health["ms"] = int((time.monotonic() - t0) * 1000)


def fetch_kagi() -> tuple[list[dict], list[dict]]:
    """Kagi News daily clusters -> one lead per cluster (articles as members). Leads only (CC BY-NC)."""
    items, health = [], []
    for fname, section in sources.KAGI_CATEGORIES.items():
        h = {"name": f"Kagi {fname}", "kind": "kagi", "ok": False, "items": 0, "fresh": 0, "ms": 0, "error": None}
        t0 = time.monotonic()
        try:
            r = requests.get(sources.KAGI_BASE + fname, timeout=20, headers={"User-Agent": sources.USER_AGENT})
            if r.status_code != 200:
                h["error"] = f"HTTP {r.status_code}"
            else:
                for c in (r.json().get("clusters") or [])[:15]:
                    arts = c.get("articles") or []
                    dates = [fetch_world._parse_published(a.get("date") or "") for a in arts]
                    dates = [d for d in dates if d]
                    items.append({
                        "title": c.get("title") or "", "url": (arts[0].get("link") if arts else None),
                        "summary": (c.get("short_summary") or "")[:300], "published": max(dates) if dates else None,
                        "pub": "Kagi News", "via": f"Kagi {fname}", "category": section, "kind": "kagi",
                        "section_hint": section, "kagi_domains": int(c.get("unique_domains") or 0),
                        "articles": [{"title": a.get("title"), "url": a.get("link"), "pub": a.get("domain"),
                                      "published": fetch_world._parse_published(a.get("date") or "")} for a in arts[:6]],
                    })
                    h["items"] += 1
                h["ok"] = True
        except Exception as e:  # noqa: BLE001
            h["error"] = f"{type(e).__name__}: {e}"[:200]
        h["ms"] = int((time.monotonic() - t0) * 1000)
        health.append(h)
    return items, health


def fetch_hn(min_points: int = 250) -> tuple[list[dict], dict]:
    h = {"name": "Hacker News front page", "kind": "api", "ok": False, "items": 0, "fresh": 0, "ms": 0, "error": None}
    try:
        r = requests.get(sources.HN_FRONT, timeout=15, headers={"User-Agent": sources.API_AGENT})
        r.raise_for_status()
        items = []
        for hit in r.json().get("hits") or []:
            if int(hit.get("points") or 0) < min_points or not hit.get("url"):
                continue
            items.append({"title": hit.get("title") or "", "url": hit["url"], "summary": "",
                          "published": fetch_world._parse_published(hit.get("created_at") or ""),
                          "pub": "Hacker News", "via": "Hacker News front page", "category": "technology",
                          "kind": "hn", "hn_points": int(hit.get("points") or 0)})
        h.update(ok=True, items=len(items))
        return items, h
    except Exception as e:  # noqa: BLE001
        h["error"] = f"{type(e).__name__}: {e}"[:200]
        return [], h


def in_window(published: str | None, start: dt.datetime, end: dt.datetime) -> bool:
    t = config.parse_ts(published)
    return t is not None and start <= t <= end + dt.timedelta(hours=1)


def run(date: str, window: dict) -> dict:
    """Sweep everything for [window.start, window.end] and write raw.json. Returns the raw dict."""
    start, end = config.parse_ts(window["start"]), config.parse_ts(window["end"])
    feed_list = [(c, n, u, "rss", None) for c, n, u in sources.feeds()]
    beat_list = sources.beats()
    feed_list += [(b["section"], f"Beat: {b['label']}", b["url"], "beat", b["id"]) for b in beat_list]

    items: list[dict] = []
    health: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(fetch_feed, c, n, u, kind=k, beat=b,
                            per_feed=15 if k == "beat" else 30): (n, k) for c, n, u, k, b in feed_list}
        kagi_f = pool.submit(fetch_kagi)
        hn_f = pool.submit(fetch_hn)
        utc_end = end.astimezone(config.UTC).date()
        wiki_f = [pool.submit(wiki.fetch_day, d) for d in (utc_end - dt.timedelta(days=1), utc_end)]
        mk_f = pool.submit(markets.snapshot)
        f1_f = pool.submit(sport.f1)
        for f in cf.as_completed(futs):
            its, h = f.result()
            fresh = [i for i in its if in_window(i["published"], start, end)
                     or (i["published"] is None and i["pub"] in sources.PRIMARY_PUBLISHERS)]
            h["fresh"] = len(fresh)
            items.extend(fresh)
            health.append(h)
        kagi_items, kagi_health = kagi_f.result()
        health.extend(kagi_health)
        items.extend(kagi_items)            # Kagi is a daily digest: its clusters count even if ~12 h old
        hn_items, hn_health = hn_f.result()
        hn_fresh = [i for i in hn_items if in_window(i["published"], start, end)]
        hn_health["fresh"] = len(hn_fresh)
        items.extend(hn_fresh)
        health.append(hn_health)
        wiki_events = []
        for f in wiki_f:
            ev, h = f.result()
            wiki_events.extend(ev)
            health.append(h)
        mk, mk_h = mk_f.result()
        f1, f1_h = f1_f.result()
        health += [mk_h, f1_h]

    beats_out = []
    for b in beat_list:
        hits = sum(1 for i in items if i.get("beat") == b["id"])
        beats_out.append({k: b[k] for k in ("id", "section", "label", "must_check")} | {"hits": hits})

    raw = {
        "date": date, "window": window, "generated_at": config.iso(config.now_ist()),
        "items": items, "wiki_events": wiki_events, "markets": mk, "sport": {"f1": f1},
        "beats": beats_out, "source_health": sorted(health, key=lambda h: (h["ok"], h["name"])),
    }
    (config.day_dir(date) / "raw.json").write_text(json.dumps(raw, ensure_ascii=False))
    return raw


def health_summary(raw: dict) -> str:
    hs = raw["source_health"]
    ok = sum(1 for h in hs if h["ok"])
    return (f"{len(raw['items'])} fresh items from {ok}/{len(hs)} sources, "
            f"{len(raw['wiki_events'])} Wikipedia events, {len(raw['markets']['quotes'])} market quotes")
