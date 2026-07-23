#!/usr/bin/env python3
"""Best-effort media + credibility for news stories — all free, no API keys, deterministic (never trusts
the LLM to copy URLs).

Two jobs, both attached onto a decoded story dict by `enrich(story, raw_index, cache)`:
  • `image` (+ `image_credit`) — a lead picture. First choice: the image the RSS feed already carried
    (matched from output/world-raw-latest.json). Fallback: the article's own <meta og:image> (the same
    link-preview tag WhatsApp/Slack use). We only ever store the URL and hotlink it — nothing is downloaded.
  • `credibility` — a trust verdict from the story's CITED sources (count + best source tier), optionally
    boosted by how many raw feeds carried the same story. This is the reliable backbone of the badge.

The og:image cache (output/image-cache.json, gitignored) means each article page is fetched at most once.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
# The image cache is COMMITTED (a plain {source_url: image_url} map — no secrets) so the cloud, which can't
# reach arbitrary article hosts to read og:image, can still attach images the Mac resolved. Only the Mac
# writes it (routine/resolve_images.py); build_reels everywhere just READS it.
CACHE_PATH = ROOT / "dashboard" / "image-cache.json"
UA = "Mozilla/5.0 (compatible; DailyIntel/1.0; +https://anmol0503.github.io/stock-market)"

_STOP = {"the", "a", "an", "of", "to", "in", "on", "and", "for", "is", "are", "as", "at", "by", "with",
         "from", "its", "it", "after", "over", "amid", "says", "say", "new", "will", "has", "have",
         "was", "were", "be", "that", "this", "up", "out"}
_TIER1_KW = ("reuters", "associated press", "ap news", "afp", "bloomberg", "bbc", "guardian",
             "financial times", "wsj", "wall street journal", "new york times", "washington post",
             "npr", "al jazeera", "the hindu", "press trust", "espncricinfo", "autosport", "nature",
             "science", "economist", "cnbc", "cnn", "the race", "planetf1", "sky sport", "reuters")
_TIER3_KW = ("reddit", "nitter", "twitter", "/r/", "gnews", "google news", "substack", "medium", "blog")


def _load(p: pathlib.Path) -> dict:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def sig(s: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) > 2 and t not in _STOP}


def source_tier(name: str) -> int:
    s = (name or "").lower()
    if any(k in s for k in _TIER3_KW):
        return 3
    if any(k in s for k in _TIER1_KW):
        return 1
    return 2


def credibility(source_names: list[str], corroboration: int = 0) -> dict:
    """Verdict from the story's cited outlets (+ optional raw-feed corroboration count).

    confirmed  🟢 — a wire cited, OR ≥3 distinct outlets, OR corroborated across many feeds
    developing 🟡 — 2 outlets, or a single established (tier-2) outlet
    single     ⚪ — one low-tier/social source only
    """
    names = sorted({n for n in source_names if n})
    tier = min((source_tier(n) for n in names), default=3)
    count = max(len(names), 0)
    if count >= 3 or tier == 1 or corroboration >= 4:
        level = "confirmed"
    elif count == 2 or tier <= 2 or corroboration >= 2:
        level = "developing"
    else:
        level = "single"
    return {"level": level, "count": count, "tier": tier, "outlets": names[:10],
            "corroboration": corroboration}


def og_image(url: str, cache: dict, timeout: int = 6) -> str:
    """Fetch a page's og:image / twitter:image (cached). Returns "" on any failure."""
    if not url:
        return ""
    if url in cache:
        return cache[url]
    img = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - fixed http(s) news URLs
            page = r.read(200_000).decode("utf-8", "ignore")      # <head> is all we need
        for pat in (r'<meta[^>]+property=["\']og:image(?::url)?["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)'):
            m = re.search(pat, page, re.I)
            if m:
                img = html.unescape(m.group(1).strip())    # decode &amp; etc. so query params survive
                break
    except Exception:  # noqa: BLE001 - images are a nice-to-have
        img = ""
    cache[url] = img
    return img


def build_raw_index(raw_path: pathlib.Path) -> list[tuple]:
    """(token-signature, raw_item) for every deduped raw headline — for best-effort story→feed matching."""
    heads = (_load(raw_path).get("all_headlines") or [])
    return [(sig(h.get("headline")), h) for h in heads]


def load_cache() -> dict:
    """The committed {source_url: image_url} map that build_reels reads on every machine."""
    return _load(CACHE_PATH)


def resolve_all(world_path: pathlib.Path, cap: int = 40) -> tuple:
    """Mac-side: fetch og:image for the current stories' primary sources into the COMMITTED cache.

    The Mac has real network; the cloud sandbox doesn't, so it just reads what we resolve here. Only fetches
    URLs not already cached (bounded by `cap`). Returns (total_cached, newly_resolved)."""
    stories = (_load(pathlib.Path(world_path)).get("stories") or [])
    cache = _load(CACHE_PATH)
    new = 0
    for st in stories:
        srcs = st.get("sources") or []
        url = (srcs[0] if srcs else {}).get("url")
        if url and url not in cache:
            if new >= cap:
                break
            og_image(url, cache)
            new += 1
    if new:
        try:
            CACHE_PATH.write_text(json.dumps(cache, indent=0, ensure_ascii=False))
        except OSError:
            pass
    return len(cache), new


def enrich(story: dict, raw_index: list[tuple], cache: dict, *, fetch_ok: bool = True) -> dict:
    """Attach `image`, `image_credit`, `credibility` to one story dict (in place). Returns the story."""
    srcs = story.get("sources") or []
    primary = srcs[0] if srcs else {}

    # best-effort fuzzy match to the raw feed (adds the feed's image + extra corroborating outlets)
    ssig = sig(story.get("title"))
    matched, best = None, 0.0
    for rsig, item in raw_index:
        if ssig and rsig:
            j = len(ssig & rsig) / len(ssig | rsig)
            if j > best:
                best, matched = j, item
    matched = matched if best >= 0.35 else None

    # image: feed image → committed cache → live og:image (only where there's network). URL only.
    img = (matched or {}).get("image") or ""
    purl = primary.get("url")
    if not img and purl:
        if purl in cache:
            img = cache[purl] or ""               # what the Mac already resolved (works on the cloud too)
        elif fetch_ok:
            img = og_image(purl, cache)           # live fetch — succeeds on the Mac, no-ops on the cloud
    story["image"] = img or None
    story["image_credit"] = primary.get("name") or (matched or {}).get("source")

    # credibility: cited outlets + (bonus) raw-feed corroboration count when a match was found
    names = [s.get("name") for s in srcs] + ((matched or {}).get("corroborating") or [])
    story["credibility"] = credibility(names, (matched or {}).get("corroboration") or 0)
    return story
