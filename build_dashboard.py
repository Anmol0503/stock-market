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

    # The reels are a PURE, TIMESTAMPED NEWS FEED now: no cover, no markets/learn cards — just the
    # ~20 global + ~20 india decoded stories in two tabs. Flip these to bring those sections back.
    REELS_INCLUDE_MARKETS = False
    REELS_INCLUDE_LEARN = False

    cards: list[dict] = []
    stories = (world or {}).get("stories", []) or []
    watch = (brief or {}).get("what_to_watch", []) or []

    # -- world stories, already ranked/curated by the analyst (no cover — first swipe IS the top story)
    for s in stories:
        src = (s.get("sources") or [{}])[0].get("name")
        cards.append({
            "type": "story", "id": f"story-{s.get('rank')}",
            "rank": s.get("rank"), "category": s.get("category"),
            "published_iso": s.get("published_iso"), "source": src,
            "importance": s.get("importance"), "regions": s.get("regions") or [],
            "title": s.get("title") or "", "what_happened": s.get("what_happened") or "",
            "key_points": s.get("key_points") or [],
            "moot": s.get("the_lesson") or _first_sentence(s.get("why_it_matters", "")),
            **({"thread": s["thread"]} if s.get("thread") else {}),
            "concepts": s.get("concepts") or [],
            "depth": {k: s.get(k) for k in (
                "background", "why_it_matters", "ripple_effects", "why_now",
                "watch_next", "market_link", "key_terms", "sources")},
        })

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

    days = rebuild_index()
    print(f"Archive index rebuilt: {len(days)} day(s) available"
          + (f" ({days[0]['date']} … {days[-1]['date']})" if days else "") + ".")


if __name__ == "__main__":
    main()
