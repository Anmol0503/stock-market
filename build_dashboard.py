#!/usr/bin/env python3
"""Publish the latest briefs to the dashboard, and archive every day for history.

Copies the analyst's output into the static site so GitHub Pages (dashboard/index.html) can
render both pillars:
    output/world-latest.json  -> dashboard/world.json   (the decoded World news feed)
    output/brief-latest.json  -> dashboard/brief.json   (the Markets brief)

It ALSO keeps a dated history so you can browse any past day from the dashboard's date selector:
    dashboard/archive/world-<date>.json
    dashboard/archive/brief-<date>.json
    dashboard/archive/index.json   (list of available days, newest first)

The date comes from each brief's own "date" field. Re-running for the same day overwrites that
day's snapshot (idempotent). Either brief missing is a soft warning.

Run:  python build_dashboard.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DASH = ROOT / "dashboard"
ARCHIVE = DASH / "archive"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

COPIES = [
    (ROOT / "output" / "world-latest.json", DASH / "world.json", "world", "World"),
    (ROOT / "output" / "brief-latest.json", DASH / "brief.json", "brief", "Markets"),
    # (lessons live in dashboard/lessons.json, written directly by decode_lesson.py — not copied here)
]


def rebuild_index() -> list[dict]:
    """Scan the archive for saved days and (re)build archive/index.json, newest first."""
    days: dict[str, dict] = {}
    for p in ARCHIVE.glob("world-*.json"):
        date = p.stem[len("world-"):]
        days.setdefault(date, {"date": date})
        try:
            days[date]["world_headline"] = json.loads(p.read_text()).get("headline", "")
        except Exception:  # noqa: BLE001
            pass
    for p in ARCHIVE.glob("brief-*.json"):
        date = p.stem[len("brief-"):]
        days.setdefault(date, {"date": date})
        try:
            days[date]["market_headline"] = json.loads(p.read_text()).get("headline", "")
        except Exception:  # noqa: BLE001
            pass
    ordered = sorted(days.values(), key=lambda d: d["date"], reverse=True)
    (ARCHIVE / "index.json").write_text(json.dumps({"days": ordered}, indent=2))
    return ordered


def build_board_history(days: int = 14) -> int:
    """Compile dashboard/board-history.json — each board ticker's closes across archived briefs.

    Feeds the tiny sparklines next to board numbers (dashboard + reels). Board values are
    formatted strings like "7,483" — parse defensively; a bad value just skips that point.
    """
    series: dict[str, list[dict]] = {}
    briefs = sorted(ARCHIVE.glob("brief-*.json"))[-days:]
    for p in briefs:
        date = p.stem[len("brief-"):]
        try:
            board = json.loads(p.read_text()).get("board", []) or []
        except Exception:  # noqa: BLE001
            continue
        for row in board:
            ticker = row.get("ticker")
            try:
                val = float(str(row.get("value", "")).replace(",", "").replace("₹", "").replace("$", ""))
            except ValueError:
                continue
            if ticker:
                series.setdefault(ticker, []).append({"d": date, "v": val})
    payload = {"as_of": dt.datetime.now(IST).isoformat(timespec="seconds"), "series": series}
    (DASH / "board-history.json").write_text(json.dumps(payload, indent=2))
    print(f"Published dashboard/board-history.json ({len(series)} tickers, {len(briefs)} day(s)).")
    return len(series)


# ---------------------------------------------------------------------------
# Reels — the mobile swipe deck, compiled from data we already generate.
# ---------------------------------------------------------------------------

GLOSSARY_KEY_RE = re.compile(r"^\s{2}([a-z][a-z0-9_]*)\s*:\s*\{", re.M)
GLOSSARY_EPOCH = dt.date(2026, 1, 1)  # concept-of-the-day rotation anchor


def _glossary_keys() -> list[str]:
    """Extract glossary keys from dashboard/glossary.js, in file order."""
    try:
        return GLOSSARY_KEY_RE.findall((DASH / "glossary.js").read_text())
    except OSError:
        return []


def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text or "")
    return m.group(1) if m else (text or "")


# --- India money notation: make "₹ lakh/crore" legible for a beginner --------------------------
# DETERMINISTIC — only REFORMATS figures already present in the text; never invents a number.
# A currency prefix (₹/Rs/INR) is REQUIRED so we never mistake counts of people ("5 crore users")
# for money. lakh=1e5, crore=1e7, "lakh crore"=1e12.
_MONEY_RE = re.compile(
    r"(?:₹|Rs\.?|INR)\s?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>lakh[\s-]+crore|crore|lakh)\b",
    re.IGNORECASE)
_INR_MULT = {"lakh": 1e5, "crore": 1e7, "lakh crore": 1e12}


def _trim(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _intl_words(rupees: float) -> str:
    """A ₹ figure re-expressed in internationally-legible magnitude words."""
    if rupees >= 1e12:
        return f"₹{_trim(rupees / 1e12)} trillion"
    if rupees >= 1e9:
        return f"₹{_trim(rupees / 1e9)} billion"
    if rupees >= 1e7:
        return f"₹{_trim(rupees / 1e7)} crore"
    return f"₹{int(round(rupees)):,}"


def _usd_words(usd: float) -> str:
    if usd >= 1e10:
        return f"${int(round(usd / 1e9))}bn"          # ≥$10bn: whole billions
    if usd >= 1e9:
        return f"${_trim(round(usd / 1e9, 1))}bn"      # $1–10bn: one decimal
    if usd >= 1e6:
        return f"${int(round(usd / 1e6))}mn"
    return f"${int(round(usd)):,}"


def _inr_rate(history: dict | None) -> float | None:
    """Latest USD→INR from board-history.json (series 'INR=X'); None if implausible/absent."""
    try:
        v = (history or {}).get("series", {}).get("INR=X", [])[-1]["v"]
        return float(v) if 50 < float(v) < 150 else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _decode_figures(text: str, rate: float | None = None) -> list[dict]:
    """Return [{raw, words, usd_approx?}] for each ₹ lakh/crore figure in `text` (deduped, max 4)."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in _MONEY_RE.finditer(text or ""):
        norm = re.sub(r"\s+", " ", m.group(0).strip().lower())
        if norm in seen:
            continue
        seen.add(norm)
        try:
            num = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        unit = re.sub(r"[\s-]+", " ", m.group("unit").lower())
        rupees = num * _INR_MULT[unit]
        fig = {"raw": m.group(0).strip(), "words": _intl_words(rupees)}
        if rate and rupees >= 1e7:
            fig["usd_approx"] = "≈ " + _usd_words(rupees / rate)
        out.append(fig)
        if len(out) >= 4:
            break
    return out


def _load_json(path: pathlib.Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def _yesterday_world(today: str) -> dict | None:
    """The most recent archived world brief strictly before `today` (for the flashback quiz)."""
    dates = sorted(p.stem[len("world-"):] for p in ARCHIVE.glob("world-*.json"))
    prior = [d for d in dates if d < today]
    return _load_json(ARCHIVE / f"world-{prior[-1]}.json") if prior else None


# ---- rolling news archive: the live feed shows the top-N per region; everything else collects here ----
NEWS_ARCHIVE = DASH / "news-archive.json"
LIVE_PER_REGION = 20      # the live reels feed shows at most this many stories per tab (Global / India)
NEWS_ARCHIVE_CAP = 300    # rolling history depth (dedup by title, newest-first)
FRESH_HOURS = 30          # a story older than this drops OUT of the live feed (still kept in the archive)
MIN_LIVE = 8              # ...but always keep at least this many newest per region, so it's never empty
_STOP_WORDS = set("the a an of to in and for on as is it its at by with after from this that was were will "
                  "has have had over into out up down amid new now says say said amid than then but or "
                  "india indias indian first big back again live goes get gets".split())


def _norm_title(t: str | None) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


def _story_region(c: dict) -> str:
    return "india" if c.get("category") == "india" else "global"


def _story_ts(c: dict):
    try:
        return dt.datetime.fromisoformat(str(c.get("published_iso") or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _age_hours(c: dict, now: dt.datetime):
    t = _story_ts(c)
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=now.tzinfo)
    return (now - t).total_seconds() / 3600


def _sig_tokens(c: dict) -> set:
    words = re.findall(r"[a-z0-9]+", (c.get("title") or "").lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _is_near_dup(toks: set, seen: list) -> bool:
    """True if this title's significant words overlap an already-kept story enough to be the SAME event
    (e.g. a developing story re-decoded with new wording). Jaccard >= 0.55 over 4+ tokens."""
    if len(toks) < 4:
        return False
    return any((len(toks & s) / len(toks | s)) >= 0.55 for s in seen if s)


def update_news_archive(story_cards: list[dict]) -> int:
    """Merge the currently-live story cards into dashboard/news-archive.json (dedup by title, newest
    first). So every story that rotates out of the live top-20 is preserved as history, never lost."""
    data = _load_json(NEWS_ARCHIVE) or {}
    old = data.get("stories") or []
    have = {_norm_title(s.get("title")) for s in old}
    fresh = [c for c in story_cards
             if _norm_title(c.get("title")) and _norm_title(c.get("title")) not in have]
    merged = fresh + old
    merged.sort(key=lambda s: s.get("published_iso") or "", reverse=True)   # newest first, undated sink
    seen: set[str] = set()
    out: list[dict] = []
    for s in merged:
        k = _norm_title(s.get("title"))
        if k and k not in seen:
            seen.add(k)
            out.append(s)
        if len(out) >= NEWS_ARCHIVE_CAP:
            break
    NEWS_ARCHIVE.write_text(json.dumps(
        {"generated_at": dt.datetime.now(IST).isoformat(timespec="seconds"),
         "count": len(out), "stories": out}, indent=2, ensure_ascii=False))
    return len(out)


def build_reels() -> int:
    """Compile dashboard/reels.json — the ordered mobile card deck.

    Pure Python over already-generated JSON (no AI cost). Every content card carries a `moot`:
    the one bold takeaway the card is built around. Degrades: world missing -> markets-only
    deck (and vice versa); both missing -> skip with a warning.
    """
    world = _load_json(DASH / "world.json")
    brief = _load_json(DASH / "brief.json")
    if not world and not brief:
        print("  ! no briefs published — skipping reels.", file=sys.stderr)
        return 0

    date = (world or brief).get("date") or dt.date.today().isoformat()
    try:
        day = dt.date.fromisoformat(date)
    except ValueError:
        day = dt.date.today()
    history = _load_json(DASH / "board-history.json") or {}
    sparks = history.get("series", {})
    inr_rate = _inr_rate(history)   # for the "by the numbers" ₹→$ approximation

    # The reels are a PURE, TIMESTAMPED NEWS FEED now: no cover, no markets/learn cards — just the
    # ~20 global + ~20 india decoded stories in two tabs. Flip these to bring those sections back.
    REELS_INCLUDE_MARKETS = False
    REELS_INCLUDE_LEARN = False

    cards: list[dict] = []
    stories = (world or {}).get("stories", []) or []
    watch = (brief or {}).get("what_to_watch", []) or []

    # -- world stories, already ranked/curated by the analyst (no cover — first swipe IS the top story)
    story_cards: list[dict] = []
    for s in stories:
        src = (s.get("sources") or [{}])[0].get("name")
        story_cards.append({
            "type": "story", "id": f"story-{s.get('rank')}",
            "rank": s.get("rank"), "category": s.get("category"),
            "published_iso": s.get("published_iso"), "source": src,
            "importance": s.get("importance"), "regions": s.get("regions") or [],
            "title": s.get("title") or "", "what_happened": s.get("what_happened") or "",
            "key_points": s.get("key_points") or [],
            "moot": s.get("the_lesson") or _first_sentence(s.get("why_it_matters", "")),
            **({"thread": s["thread"]} if s.get("thread") else {}),
            "concepts": s.get("concepts") or [],
            "figures": _decode_figures(
                (s.get("what_happened") or "") + " " + " ".join(s.get("key_points") or []), inr_rate),
            "depth": {k: s.get(k) for k in (
                "background", "why_it_matters", "ripple_effects", "why_now",
                "watch_next", "market_link", "key_terms", "sources")},
        })

    # Archive EVERYTHING first (nothing is lost), then build a FRESH, de-duped live feed per region:
    # newest-published first, drop stories older than FRESH_HOURS (beyond a MIN_LIVE floor so it's never
    # empty), and skip near-duplicate events (a developing story re-decoded with different wording).
    update_news_archive(story_cards)
    now = dt.datetime.now(IST)
    by_region: dict[str, list[dict]] = {"global": [], "india": []}
    for c in story_cards:
        by_region[_story_region(c)].append(c)
    for region in ("global", "india"):
        ranked = sorted(by_region[region], key=lambda c: c.get("published_iso") or "", reverse=True)
        live: list[dict] = []
        seen_toks: list[set] = []
        for c in ranked:
            if len(live) >= LIVE_PER_REGION:
                break
            toks = _sig_tokens(c)
            if _is_near_dup(toks, seen_toks):
                continue                       # same event, already shown → skip the rehash
            age = _age_hours(c, now)
            if len(live) >= MIN_LIVE and age is not None and age > FRESH_HOURS:
                continue                       # past the floor and stale → keep it in the archive only
            live.append(c)
            if toks:
                seen_toks.append(toks)
        cards.extend(live)
    live_titles = {_norm_title(c.get("title")) for c in cards if c.get("type") == "story"}
    archive_data = _load_json(NEWS_ARCHIVE) or {}
    for region, cat in (("global", "geopolitics"), ("india", "india")):
        older = [s for s in (archive_data.get("stories") or [])
                 if _story_region(s) == region and _norm_title(s.get("title")) not in live_titles]
        if older:
            cards.append({"type": "archive", "id": f"archive-{region}", "category": cat,
                          "region": region, "older_count": len(older)})

    # -- 🎓 Learn tab is built CLIENT-SIDE in the reels from dashboard/lessons.json (the catalog written
    #    by routine/decode_lesson.py) so the reader can walk it at their own pace + browse the library.
    #    Nothing lesson-related goes into reels.json anymore.

    # -- markets section (skipped for now — set REELS_INCLUDE_MARKETS = True to restore)
    if brief and REELS_INCLUDE_MARKETS:
        cards.append({"type": "divider", "id": "mkt", "title": "Markets", "emoji": "📈",
                      "subtitle": brief.get("headline") or ""})
        if brief.get("market_story"):
            gs = brief.get("global_summary") or {}
            cards.append({
                "type": "market_story", "id": "mkt-story",
                "story": brief["market_story"],
                "themes": [f"{t.get('theme')}: {t.get('note')}" for t in (brief.get("themes") or [])],
                "moot": brief.get("headline") or "",
                "depth": {"global_summary": gs,
                          "catalysts_today": [f"{c.get('when')} — {c.get('event')}"
                                              for c in (brief.get("catalysts_today") or [])],
                          "risks": brief.get("risks") or []},
            })
        board = brief.get("board") or []
        if board:
            movers = sorted(board, key=lambda b: abs(b.get("change_pct") or 0), reverse=True)[:6]
            items = []
            for b in movers:
                row = {k: b.get(k) for k in ("name", "ticker", "currency", "value", "change_pct", "read")}
                pts = [p["v"] for p in sparks.get(b.get("ticker"), [])]
                if len(pts) >= 3:
                    row["spark"] = pts
                items.append(row)
            cards.append({"type": "board", "id": "board",
                          "moot": _first_sentence(movers[0].get("read", "")) if movers else "",
                          "items": items})
        for w in watch:
            cards.append({
                "type": "watch", "id": f"watch-{w.get('rank')}",
                "rank": w.get("rank"), "title": w.get("title") or "",
                "gist": w.get("gist") or "", "what_it_means": w.get("what_it_means") or "",
                "key_points": w.get("key_points") or [],
                "moot": w.get("the_lesson") or _first_sentence(w.get("why_it_matters", "")),
                "concepts": w.get("concepts") or [],
                "tickers": w.get("tickers") or [], "market": w.get("market"),
                "depth": {k: w.get(k) for k in ("why_it_matters", "watch", "key_terms", "sources")},
            })
        favs = brief.get("favorites") or []
        favs = sorted(favs, key=lambda f: (not f.get("whats_new"),
                                           -abs(f.get("change_pct") or 0)))[:3]
        for f in favs:
            cards.append({
                "type": "favorite", "id": f"fav-{f.get('ticker')}",
                "ticker": f.get("ticker"), "name": f.get("name"),
                "price": f.get("price"), "change_pct": f.get("change_pct"),
                "currency": f.get("currency", ""),
                "whats_new": f.get("whats_new") or "",
                "moot": (f.get("stance") or "").capitalize(),
                "depth": {k: f.get(k) for k in
                          ("news", "fundamentals", "technicals", "catalysts", "risks")},
            })

    # -- learn cards: concept of the day (deterministic rotation) + flashback quiz
    keys = _glossary_keys() if REELS_INCLUDE_LEARN else []
    if keys:
        key = keys[(day - GLOSSARY_EPOCH).days % len(keys)]
        live = set()
        for s in stories:
            live.update(s.get("concepts") or [])
        for w in watch:
            live.update(w.get("concepts") or [])
        cards.append({"type": "concept", "id": "learn-concept", "key": key,
                      **({"why_today": "This one is live in today's brief."} if key in live else {})})
    yworld = _yesterday_world(date) if REELS_INCLUDE_LEARN else None
    if yworld:
        pool = [s for s in (yworld.get("stories") or [])[:5] if s.get("the_lesson")]
        if pool:
            pick = pool[day.timetuple().tm_yday % len(pool)]
            cards.append({
                "type": "quiz", "id": "learn-quiz",
                "context_date": yworld.get("date"), "context_title": pick.get("title") or "",
                "question": "Yesterday we decoded this story. What's the transferable lesson?",
                "answer": pick["the_lesson"], "concepts": pick.get("concepts") or [],
            })

    # -- outro
    cards.append({
        "type": "outro", "id": "outro",
        "also_notable": (world or {}).get("also_notable") or [],
        "disclaimer": (world or {}).get("disclaimer") or (brief or {}).get("disclaimer") or "",
        "dashboard_url": "../",
    })

    payload = {
        "date": date,
        "generated_at": dt.datetime.now(IST).isoformat(timespec="seconds"),
        "day_label": day.strftime("%A · %-d %B %Y"),
        "dashboard_url": "../",
        "cards": cards,
    }
    pretty = json.dumps(payload, indent=2, ensure_ascii=False)
    (DASH / "reels.json").write_text(pretty)
    (ARCHIVE / f"reels-{date}.json").write_text(pretty)
    print(f"Published dashboard/reels.json ({len(cards)} cards, date: {date}) + archived.")
    return len(cards)


# ---------------------------------------------------------------------------
# Entity pages — turn the `regions` on every story into a followable knowledge graph.
# ---------------------------------------------------------------------------

# Canonicalise region names so aliases collapse into ONE entity (else "US" / "United States" split).
_ENTITY_ALIASES = {
    "us": "United States", "u.s.": "United States", "usa": "United States",
    "united states": "United States", "america": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom",
    "united kingdom": "United Kingdom",
    "eu": "Europe", "european union": "Europe", "europe": "Europe",
    "middle east": "Middle East", "mideast": "Middle East", "gulf": "Middle East",
    "uae": "UAE", "u.a.e.": "UAE",
    "russia": "Russia", "china": "China", "india": "India", "iran": "Iran",
    "israel": "Israel", "pakistan": "Pakistan", "ukraine": "Ukraine",
}
# Too generic to be a useful "entity" page.
_ENTITY_STOP = {"global", "world", "international", "", "asia", "worldwide"}
ENTITY_MIN_STORIES = 3           # ignore one-off mentions
ENTITY_MAX_STORIES = 40          # cap a timeline's length


def _entity_slug(region: str) -> tuple[str, str] | None:
    """(slug, display_name) for a region string, applying the alias map; None if stop-listed."""
    raw = (region or "").strip()
    key = raw.lower()
    if key in _ENTITY_STOP:
        return None
    name = _ENTITY_ALIASES.get(key, raw)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug or name.lower() in _ENTITY_STOP:
        return None
    return slug, name


def build_entities(days: int = 20) -> int:
    """Compile dashboard/entities.json — per-entity standing primer + reverse-chron story timeline.

    Pure Python over the archived world briefs (no AI cost). Buckets every story by its `regions`,
    dedupes repeated headlines, and uses each entity's most notable `background` as a free primer.
    Public-safe: only titles/dates/urls/categories already in the public world.json.
    """
    ent: dict[str, dict] = {}
    seen: dict[str, set] = {}
    for p in sorted(ARCHIVE.glob("world-*.json"))[-days:]:
        data = _load_json(p) or {}
        for s in data.get("stories", []) or []:
            date = data.get("date") or p.stem[len("world-"):]
            title = (s.get("title") or "").strip()
            if not title:
                continue
            moot = s.get("the_lesson") or _first_sentence(s.get("why_it_matters", ""))
            url = ((s.get("sources") or [{}])[0] or {}).get("url", "")
            imp = {"critical": 0, "high": 1, "notable": 2}.get(s.get("importance"), 3)
            for region in (s.get("regions") or []):
                sl = _entity_slug(region)
                if not sl:
                    continue
                slug, name = sl
                e = ent.setdefault(slug, {"slug": slug, "name": name, "primer": "",
                                          "_bg": None, "_bg_imp": 9, "_bg_date": "", "stories": []})
                seen.setdefault(slug, set())
                nt = re.sub(r"\s+", " ", title.lower())
                if nt in seen[slug]:
                    continue                                   # dedupe a headline that recurs across days
                seen[slug].add(nt)
                e["stories"].append({"date": date, "title": title, "category": s.get("category"),
                                     "url": url, "rank": s.get("rank"), "moot": moot})
                # standing primer = the background from the most-important, then most-recent, story
                bg = (s.get("background") or "").strip()
                if bg and (imp < e["_bg_imp"] or (imp == e["_bg_imp"] and date > e["_bg_date"])):
                    e["_bg"], e["_bg_imp"], e["_bg_date"] = bg, imp, date

    out = {}
    for slug, e in ent.items():
        if len(e["stories"]) < ENTITY_MIN_STORIES:
            continue
        e["stories"].sort(key=lambda x: (x["date"], -(x["rank"] or 999)), reverse=True)
        e["stories"] = e["stories"][:ENTITY_MAX_STORIES]
        e["primer"] = e.pop("_bg") or ""
        e.pop("_bg_imp", None)
        e.pop("_bg_date", None)
        out[slug] = e

    payload = {"generated_at": dt.datetime.now(IST).isoformat(timespec="seconds"),
               "count": len(out), "entities": out}
    (DASH / "entities.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Published dashboard/entities.json ({len(out)} entities).")
    return len(out)


def main() -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    published = 0
    for src, dst, kind, label in COPIES:
        if not src.exists():
            print(f"  ! no {label} brief at {src.relative_to(ROOT)} — skipping.", file=sys.stderr)
            continue
        data = json.loads(src.read_text())
        pretty = json.dumps(data, indent=2)
        dst.write_text(pretty)                                   # latest (what the dashboard opens by default)
        date = data.get("date")
        if date:
            (ARCHIVE / f"{kind}-{date}.json").write_text(pretty)  # dated snapshot for history
        print(f"Published {dst.relative_to(ROOT)} ({label}, date: {date}) + archived.")
        published += 1

    if not published:
        print("Nothing published. Run the analysis steps first.", file=sys.stderr)
        sys.exit(1)

    # Board history feeds the reels board card's sparklines — build it first.
    try:
        build_board_history()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! board-history build failed: {exc}", file=sys.stderr)
    try:
        build_reels()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! reels build failed: {exc}", file=sys.stderr)
    try:
        build_entities()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! entities build failed: {exc}", file=sys.stderr)

    days = rebuild_index()
    print(f"Archive index rebuilt: {len(days)} day(s) available"
          + (f" ({days[0]['date']} … {days[-1]['date']})" if days else "") + ".")


if __name__ == "__main__":
    main()
