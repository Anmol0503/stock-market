#!/usr/bin/env python3
"""Hourly top-up: decode ONE trending new story per region and prepend it to the live feed.

Small + reliable (only 2 stories decoded), so it runs every hour the laptop is on without the
oversized-generation drop. It:
  1. runs routine/hourly_prompt.md  → output/world-hourly.json  ({global, india} — either may be null)
  2. prepends each new story to the TOP of its region in output/world-latest.json (skipping duplicates),
     caps each region at CAP, renumbers ranks, refreshes generated_at
  3. rebuilds the dashboard/reels (build_dashboard.main)
The full ~40-story decode stays on-demand (routine/run_daily.sh); this just keeps the feed growing fresh.

Run:  python routine/hourly_top.py     (called by routine/run_hourly.sh)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

import build_dashboard
import progress as pg

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
ROUTINE = ROOT / "routine"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

CAP = 40   # keep at most this many stories per region (newest kept)
ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"]
CLAUDE = os.environ.get("CLAUDE_BIN") or str(pathlib.Path.home() / ".local" / "bin" / "claude")
if not pathlib.Path(CLAUDE).exists():
    CLAUDE = "claude"


def claude(prompt: str, retries: int = 2, timeout: int = 600) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            r = subprocess.run(
                [CLAUDE, "-p", prompt, "--permission-mode", "acceptEdits",
                 "--allowedTools", *ALLOWED, "--disallowedTools", "Bash", "--output-format", "text"],
                cwd=ROOT, capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode == 0:
                return r.stdout or ""
            print(f"  claude rc={r.returncode} (attempt {attempt})", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"  claude timeout (attempt {attempt})", file=sys.stderr)
    return None


def _region(s: dict) -> str:
    return "india" if s.get("category") == "india" else "global"


def _norm(t: str | None) -> str:
    return (t or "").strip().lower()


def _insert_top_of_region(stories: list[dict], story: dict, region: str) -> list[dict]:
    for i, s in enumerate(stories):
        if _region(s) == region:
            stories.insert(i, story)
            return stories
    stories.append(story)
    return stories


def _cap_per_region(stories: list[dict], cap: int) -> list[dict]:
    seen = {"global": 0, "india": 0}
    out = []
    for s in stories:
        r = _region(s)
        if seen[r] < cap:
            out.append(s)
            seen[r] += 1
    return out


def main() -> int:
    latest = OUT / "world-latest.json"
    if not latest.exists():
        print("  ! no world-latest.json — run the full decode first (nothing to top up)", file=sys.stderr)
        return 1

    pg.set_progress("decoding_global", "Finding the top trending stories", 0, 2, "1 global + 1 india")
    hf = OUT / "world-hourly.json"
    if hf.exists():
        hf.unlink()
    claude((ROUTINE / "hourly_prompt.md").read_text())
    try:
        new = json.loads(hf.read_text())
    except (ValueError, OSError) as e:
        print(f"  ! no usable world-hourly.json ({e}) — nothing added this hour", file=sys.stderr)
        return 1

    world = json.loads(latest.read_text())
    stories = world.get("stories") or []
    existing = {_norm(s.get("title")) for s in stories}

    added = []
    for key, region in (("global", "global"), ("india", "india")):
        st = new.get(key)
        if not isinstance(st, dict) or not st.get("title"):
            continue
        if _norm(st.get("title")) in existing:
            print(f"  · {key}: already covered — skipped", file=sys.stderr)
            continue
        st["category"] = "india" if region == "india" else (st.get("category") or "geopolitics")
        stories = _insert_top_of_region(stories, st, region)
        existing.add(_norm(st.get("title")))
        added.append(st.get("title"))

    if not added:
        print("  · nothing new trending this hour — feed unchanged", file=sys.stderr)
        return 0

    stories = _cap_per_region(stories, CAP)
    for n, s in enumerate(stories, 1):
        s["rank"] = n
    world["stories"] = stories
    world["date"] = dt.date.today().isoformat()
    world["generated_at"] = dt.datetime.now(IST).isoformat(timespec="seconds")

    pretty = json.dumps(world, indent=2, ensure_ascii=False)
    latest.write_text(pretty)
    (OUT / f"world-{world['date']}.json").write_text(pretty)

    pg.set_progress("publishing", "Publishing the fresh stories", len(added), 2, "; ".join(added)[:80])
    build_dashboard.main()
    print(f"hourly: added {len(added)} — {' | '.join(added)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
