#!/usr/bin/env python3
"""Merge the split World halves into the single world brief the dashboard/reels read.

The World feed is decoded in two smaller Claude calls (so neither response is big enough to drop
mid-stream): the GLOBAL half -> output/world-global.json, the INDIA half -> output/world-india.json.
This stitches them into output/world-latest.json (+ dated copy), global stories first then india,
ranks renumbered 1..N.

Robust by design: if only one half is present, it publishes that half (the other tab just shows
"no stories yet"). If NEITHER half is present/valid, it exits non-zero and leaves the existing
world-latest.json untouched — so a fully failed decode never wipes the last good brief.

Run:  python routine/merge_world.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _load(name: str) -> dict | None:
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (ValueError, OSError) as exc:
        print(f"  ! {name} unreadable: {exc}", file=sys.stderr)
        return None


def main() -> int:
    g = _load("world-global.json")
    i = _load("world-india.json")
    if not g and not i:
        print("  ! neither world-global nor world-india present — keeping existing world-latest.json",
              file=sys.stderr)
        return 1

    g = g or {}
    i = i or {}
    gstories = [s for s in (g.get("stories") or []) if (s.get("category") != "india")]
    istories = [s for s in (i.get("stories") or [])]
    for s in istories:
        s["category"] = "india"   # enforce, so the client routes it to the India tab

    stories = gstories + istories
    now_iso = dt.datetime.now(IST).isoformat(timespec="seconds")
    for n, s in enumerate(stories, 1):
        s["rank"] = n
        s.setdefault("added_at", now_iso)   # stamp when the story entered the feed (the hourly does its own)

    today = dt.date.today().isoformat()
    merged = {
        "date": today,
        "generated_at": dt.datetime.now(IST).isoformat(timespec="seconds"),
        "headline": g.get("headline") or "",
        "the_big_picture": g.get("the_big_picture") or "",
        "stories": stories,
        "also_notable": g.get("also_notable") or [],
        "disclaimer": g.get("disclaimer")
        or "Decoded from public reporting for general understanding. Verify before relying on any single claim; details evolve.",
    }

    pretty = json.dumps(merged, indent=2, ensure_ascii=False)
    (OUT / f"world-{today}.json").write_text(pretty)
    (OUT / "world-latest.json").write_text(pretty)
    print(f"Merged world brief: {len(gstories)} global + {len(istories)} india = {len(stories)} stories "
          f"-> output/world-latest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
