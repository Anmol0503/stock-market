#!/usr/bin/env python3
"""Hourly top-up: decode a few trending NEW stories and prepend them to the live feed.

Runs every 30 minutes the laptop is on. Per run it decodes:
  • 2 new GLOBAL stories   • 2 new INDIA stories   (every run)
  • 1 new F1 story + 1 new CRICKET story   (only ~every 2h — they move slower, and it keeps the
    Claude burn down; gated by SPORTS_EVERY_MIN since the last sports story was added)

Guarantees:
  • NO same-day repeats — dedup against everything added today (a persisted ledger) + the live feed.
  • Development-aware — if a pick is a major update to a story we covered on a PRIOR day, the analyst
    fills a `thread` + names the earlier story; we tag the card as a 🔄 development and link back to it.
  • Usage-logged — the Claude call goes through routine/usage.run_claude (JSON output → token/cost ledger).

The heavy full decode stays on-demand (routine/run_daily.sh). This just keeps the feed growing fresh.
Run:  python routine/hourly_top.py     (called by routine/run_hourly.sh)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))        # so `build_dashboard` (repo root) imports when run as a script

import build_dashboard                # noqa: E402
import progress as pg                 # noqa: E402  (routine/ is already on sys.path)
import publish_status                 # noqa: E402  (writes dashboard/status.json)
import usage                          # noqa: E402  (routine/usage.py — token/cost ledger)

OUT = ROOT / "output"
ROUTINE = ROOT / "routine"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# how many NEW stories to add per region each run, and which categories count as that region
REGION_PLAN = {
    "global":  {"count": 2, "cap": 20, "sports": False},
    "india":   {"count": 2, "cap": 20, "sports": False},
    "f1":      {"count": 2, "cap": 20, "sports": True},
    "cricket": {"count": 2, "cap": 20, "sports": True},
}
SPORTS_EVERY_MIN = 55       # F1/cricket refresh at most this often (≈ hourly given 30-min ticks)
STALE_MAX_H = 72            # reject a pick older than this (sport can lag a little; keeps the feed fresh-ish)

ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"]
CLAUDE = os.environ.get("CLAUDE_BIN") or str(pathlib.Path.home() / ".local" / "bin" / "claude")
if not pathlib.Path(CLAUDE).exists():
    CLAUDE = "claude"

LEDGER = OUT / "hourly-today.json"     # {date, added:[{title, category, published_iso}]}  same-day no-repeat
CONTEXT = OUT / "hourly-context.json"  # what we ask the analyst to fill this run (regions, counts, dedup, prior)


def _region(s: dict) -> str:
    c = s.get("category")
    return c if c in ("india", "f1", "cricket") else "global"


def _norm(t: str | None) -> str:
    return (t or "").strip().lower()


def _one_line(s: dict) -> str:
    return (s.get("what_happened") or s.get("the_lesson") or s.get("why_it_matters") or "")[:180]


def _load(p: pathlib.Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _insert_top_of_region(stories: list[dict], story: dict, region: str) -> list[dict]:
    for i, s in enumerate(stories):
        if _region(s) == region:
            stories.insert(i, story)
            return stories
    stories.append(story)
    return stories


def _cap_per_region(stories: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    out = []
    for s in stories:
        r = _region(s)
        cap = REGION_PLAN.get(r, {}).get("cap", 20)
        if seen.get(r, 0) < cap:
            out.append(s)
            seen[r] = seen.get(r, 0) + 1
    return out


def _sports_due(stories: list[dict], now: dt.datetime) -> bool:
    """True if no F1/cricket story was added within SPORTS_EVERY_MIN (so it's time for a sports refresh)."""
    freshest = None
    for s in stories:
        if _region(s) in ("f1", "cricket"):
            mins = build_dashboard._minutes_since(s.get("added_at"), now)
            if mins is None:
                mins = (build_dashboard._age_hours(s, now) or 999) * 60
            freshest = mins if freshest is None else min(freshest, mins)
    return freshest is None or freshest >= SPORTS_EVERY_MIN


def _load_ledger(today: str) -> dict:
    led = _load(LEDGER) or {}
    if led.get("date") != today:
        led = {"date": today, "added": []}
    return led


def _prior_stories(today: str) -> list[dict]:
    """Stories from the previous day (for development detection) — title + one-liner + date."""
    y = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
    out = []
    for f in (OUT / f"world-{y}.json",):
        w = _load(f) or {}
        for s in (w.get("stories") or []):
            out.append({"title": s.get("title"), "one_line": _one_line(s),
                        "date": y, "category": s.get("category")})
    return out[:60]


def _decode_region(region: str, count: int, already: set, prior: list[dict], today: str) -> list[dict]:
    """One small, reliable Claude call for a SINGLE region. Returns its picked stories (may be empty).

    Splitting the run into per-region calls (vs one big call for all 6 stories) keeps each call small
    enough to finish inside the timeout — the all-in-one call kept timing out. A region that fails here
    just returns [] and is retried on the next 30-min tick."""
    CONTEXT.write_text(json.dumps({
        "date": today,
        "regions": [{"key": region, "count": count}],
        "already_today": sorted(already),
        "prior_stories": prior if region in ("global", "india") else [],   # dev-linking is for news
    }, indent=2, ensure_ascii=False))
    hf = OUT / "world-hourly.json"
    if hf.exists():
        hf.unlink()
    usage.run_claude((ROUTINE / "hourly_prompt.md").read_text(), claude_bin=CLAUDE, allowed=ALLOWED,
                     cwd=ROOT, label=f"hourly {region}", timeout=300, retries=1)
    payload = _load(hf)
    if not isinstance(payload, dict):
        print(f"  ! {region}: no usable output this run (will retry next tick)", file=sys.stderr)
        return []
    picks = payload.get("stories")
    if not isinstance(picks, list):        # tolerate a bare {region: story} / single-object shape
        picks = [v for v in payload.values() if isinstance(v, dict) and v.get("title")]
    return [p for p in picks if isinstance(p, dict) and p.get("title")]


def main() -> int:
    latest = OUT / "world-latest.json"
    if not latest.exists():
        print("  ! no world-latest.json — run the full decode first (nothing to top up)", file=sys.stderr)
        return 1

    now = dt.datetime.now(IST)
    today = dt.date.today().isoformat()
    world = json.loads(latest.read_text())
    stories = world.get("stories") or []
    ledger = _load_ledger(today)

    # -- decide which regions to fill this run (sports only ~hourly) --
    sports_due = _sports_due(stories, now)
    regions = []
    for key, plan in REGION_PLAN.items():
        if plan["sports"] and not sports_due:
            continue
        regions.append({"key": key, "count": plan["count"]})

    # -- everything already covered today (live feed + today's ledger) → never repeat --
    already = {_norm(s.get("title")) for s in stories}
    already |= {_norm(a.get("title")) for a in ledger["added"]}
    toks_by_region: dict[str, list[set]] = {k: [] for k in REGION_PLAN}
    for s in stories:
        toks_by_region.setdefault(_region(s), []).append(build_dashboard._sig_tokens(s))

    prior = _prior_stories(today)

    # --merge-only: skip the local `claude` CLI entirely and merge picks a caller already wrote to
    # output/world-hourly.json ({stories:[{...,region}]}). This is how the CLOUD routine runs — there the
    # agent IS Claude, so it decodes the stories itself and hands them to this deterministic merge/cap/build.
    merge_only = "--merge-only" in sys.argv
    preloaded: dict[str, list[dict]] | None = None
    if merge_only:
        payload = _load(OUT / "world-hourly.json") or {}
        raw = payload.get("stories") if isinstance(payload.get("stories"), list) else \
            [v for v in payload.values() if isinstance(v, dict) and v.get("title")]
        preloaded = {}
        for st in (raw or []):
            if isinstance(st, dict) and st.get("title"):
                rk = st.get("region") if st.get("region") in REGION_PLAN else _region(st)
                preloaded.setdefault(rk, []).append(st)
        regions = [{"key": k, "count": len(v)} for k, v in preloaded.items()]
        if not regions:
            print("  ! --merge-only: world-hourly.json has no stories — nothing to merge", file=sys.stderr)
            publish_status.write_status("hourly", added=None)
            return 1

    pg.set_progress("decoding_global", "Finding the top trending stories", 0, len(regions),
                    " + ".join(f"{r['count']} {r['key']}" for r in regions))

    # Decode ONE region per Claude call (small + reliable). The all-in-one call for 6 stories kept
    # timing out; each region here is 2 stories, finishes fast, and a failed region retries next tick.
    added = []
    for ri, r in enumerate(regions, 1):
        region, count = r["key"], r["count"]
        pg.set_progress("decoding_global", f"Finding trending {region} stories", ri, len(regions), region)
        picks = preloaded[region] if merge_only else _decode_region(region, count, already, prior, today)
        for st in picks:
            nt = _norm(st.get("title"))
            stoks = build_dashboard._sig_tokens(st)
            if nt in already or build_dashboard._is_near_dup(stoks, toks_by_region.get(region, [])):
                print(f"  · {region}: '{(st.get('title') or '')[:50]}' already covered / rehash — skipped",
                      file=sys.stderr)
                continue
            age = build_dashboard._age_hours(st, now)
            if age is not None and age > STALE_MAX_H:
                print(f"  · {region}: too old ({age:.0f}h) — skipped", file=sys.stderr)
                continue
            st["category"] = region if region in ("india", "f1", "cricket") else (st.get("category") or "geopolitics")
            st["added_at"] = now.isoformat(timespec="seconds")
            # development of a prior-day story? the analyst names it in `develops` + fills `thread`
            dev = (st.get("develops") or "").strip()
            if dev and st.get("thread"):
                st["development"] = True
                st.setdefault("prev_ref", {"title": dev, "date": st.get("develops_date")})
            st.pop("develops", None)
            stories = _insert_top_of_region(stories, st, region)
            already.add(nt)
            toks_by_region.setdefault(region, []).append(stoks)
            ledger["added"].append({"title": st.get("title"), "category": st.get("category"),
                                    "published_iso": st.get("published_iso"), "added_at": st["added_at"]})
            added.append({"title": st.get("title"), "region": region,
                          "development": bool(st.get("development")),
                          "published_iso": st.get("published_iso")})

    if not added:
        print("  · nothing new trending this run — feed unchanged", file=sys.stderr)
        publish_status.write_status("hourly", added=None)
        return 0

    stories = _cap_per_region(stories)
    for n, s in enumerate(stories, 1):
        s["rank"] = n
    world["stories"] = stories
    world["date"] = today
    world["generated_at"] = dt.datetime.now(IST).isoformat(timespec="seconds")

    pretty = json.dumps(world, indent=2, ensure_ascii=False)
    latest.write_text(pretty)
    (OUT / f"world-{today}.json").write_text(pretty)
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False))

    titles = [a["title"] for a in added]
    pg.set_progress("publishing", "Publishing the fresh stories", len(added), len(added),
                    "; ".join(titles)[:80])
    build_dashboard.main()
    publish_status.write_status("hourly", added=added)
    print(f"hourly: added {len(added)} — {' | '.join(titles)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
